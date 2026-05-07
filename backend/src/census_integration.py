"""
Census ACS integration for housing model enrichment.

Uses B25024 (Units in Structure), B25034 (Year Built), and B25040 (Heating Fuel)
to fill gaps in NW Natural's premise data:
- B25024: Assign segment (SF/MF/Mobile) to unclassified premises
- B25034: Assign vintage era to premises without setyear
- B25040: Track gas heating market share for electrification validation
"""

import os
import logging
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd
import numpy as np

from src import config

logger = logging.getLogger(__name__)


def load_census_distributions() -> Dict[str, Dict]:
    """Load the latest Census ACS distributions for the NW Natural service territory."""
    result = {}
    
    # B25024 - Units in Structure (SF/MF/Mobile split)
    b24_dir = config.B25024_COUNTY_DIR
    if os.path.exists(b24_dir):
        files = sorted([f for f in os.listdir(b24_dir) if f.endswith('.csv')])
        if files:
            df = pd.read_csv(os.path.join(b24_dir, files[-1]))
            total = df['B25024_001E'].sum()
            sf = df['B25024_002E'].sum() + df['B25024_003E'].sum()  # 1-det + 1-att
            mf = df[['B25024_004E','B25024_005E','B25024_006E','B25024_007E','B25024_008E','B25024_009E']].sum().sum()
            mobile = df['B25024_010E'].sum()
            result['segment_distribution'] = {
                'RESSF': sf / total if total > 0 else 0.67,
                'RESMF': mf / total if total > 0 else 0.275,
                'MOBILE': mobile / total if total > 0 else 0.053,
            }
            result['total_housing_units'] = int(total)
            logger.info(f"B25024: SF={sf/total*100:.1f}%, MF={mf/total*100:.1f}%, Mobile={mobile/total*100:.1f}% (n={total:,})")
    
    # B25034 - Year Structure Built (vintage distribution)
    b34_dir = config.B25034_COUNTY_DIR
    if os.path.exists(b34_dir):
        files = sorted([f for f in os.listdir(b34_dir) if f.endswith('.csv')])
        if files:
            df = pd.read_csv(os.path.join(b34_dir, files[-1]))
            total = df['B25034_001E'].sum()
            # _002E=2020+, _003E=2010-19, _004E=2000-09, _005E=1990-99, _006E=1980-89
            # _007E=1970-79, _008E=1960-69, _009E=1950-59, _010E=1940-49, _011E=pre-1939
            result['vintage_distribution'] = {
                '2015+': (df['B25034_002E'].sum() * 0.5) / total if total > 0 else 0.08,  # half of 2020+ decade
                '2010-2014': (df['B25034_002E'].sum() * 0.5 + df['B25034_003E'].sum() * 0.5) / total if total > 0 else 0.07,
                '2000-2009': (df['B25034_003E'].sum() * 0.5 + df['B25034_004E'].sum()) / total if total > 0 else 0.15,
                '1980-1999': (df['B25034_005E'].sum() + df['B25034_006E'].sum()) / total if total > 0 else 0.25,
                'pre-1980': (df['B25034_007E'].sum() + df['B25034_008E'].sum() + df['B25034_009E'].sum() + df['B25034_010E'].sum() + df['B25034_011E'].sum()) / total if total > 0 else 0.45,
            }
            logger.info(f"B25034: vintage distribution loaded (n={total:,})")
    
    # B25040 - House Heating Fuel (gas market share over time)
    b40_dir = config.B25040_COUNTY_DIR
    if os.path.exists(b40_dir):
        files = sorted([f for f in os.listdir(b40_dir) if f.endswith('.csv')])
        gas_share_by_year = {}
        for f in files:
            # Extract year from filename like B25040_acs5_2023.csv
            try:
                year = int(f.split('_')[-1].replace('.csv', ''))
            except ValueError:
                continue
            df = pd.read_csv(os.path.join(b40_dir, f))
            total = df['B25040_001E'].sum()
            gas = df['B25040_002E'].sum()
            elec = df['B25040_004E'].sum()
            if total > 0:
                # Estimate hybrid share within gas category
                # Heat pump adoption in PNW grew from ~0% (pre-2015) to ~3-5% of gas homes by 2023
                # Hybrids report as "gas" in Census since they still have gas connection
                if year < 2015:
                    hybrid_of_gas = 0.0
                elif year < 2018:
                    hybrid_of_gas = 0.005  # 0.5% of gas homes
                elif year < 2021:
                    hybrid_of_gas = 0.015  # 1.5%
                else:
                    hybrid_of_gas = 0.03   # 3% by 2021-2023
                
                gas_only = gas * (1 - hybrid_of_gas)
                hybrid = gas * hybrid_of_gas
                
                gas_share_by_year[year] = {
                    'gas_pct': round(gas / total * 100, 1),
                    'gas_only_pct_est': round(gas_only / total * 100, 1),
                    'hybrid_pct_est': round(hybrid / total * 100, 2),
                    'electric_pct': round(elec / total * 100, 1),
                    'total': int(total),
                    'gas_units': int(gas),
                    'hybrid_units_est': int(hybrid),
                }
        result['heating_fuel_trend'] = gas_share_by_year
        if gas_share_by_year:
            years = sorted(gas_share_by_year.keys())
            latest = gas_share_by_year[years[-1]]
            logger.info(
                f"B25040: gas share {gas_share_by_year[years[0]]['gas_pct']}% ({years[0]}) → "
                f"{latest['gas_pct']}% ({years[-1]}) "
                f"[est. hybrid: {latest['hybrid_pct_est']}%]"
            )
    
    return result


def enrich_premise_equipment(
    premise_equipment: pd.DataFrame,
    census: Dict[str, Dict]
) -> pd.DataFrame:
    """
    Enrich premise-equipment data using Census distributions.
    
    1. Assign segment to unclassified premises using B25024 SF/MF/Mobile proportions
    2. Assign vintage era to premises without setyear using B25034 distribution
    3. Apply vintage heating multiplier to newly assigned premises
    """
    df = premise_equipment.copy()
    
    # --- B25024: Fill unclassified segments ---
    seg_dist = census.get('segment_distribution', {})
    if seg_dist and 'segment' in df.columns:
        unclassified = df['segment'].isna() | (df['segment'] == 'Unclassified') | (df['segment'] == '')
        n_unclassified = unclassified.sum()
        
        if n_unclassified > 0 and seg_dist:
            # Assign proportionally based on Census SF/MF/Mobile split
            # But only SF and MF (NW Natural doesn't have mobile home gas service typically)
            sf_share = seg_dist.get('RESSF', 0.67)
            mf_share = seg_dist.get('RESMF', 0.275)
            # Normalize to SF+MF only
            total_share = sf_share + mf_share
            sf_norm = sf_share / total_share if total_share > 0 else 0.7
            
            np.random.seed(42)
            random_vals = np.random.uniform(0, 1, n_unclassified)
            assigned = np.where(random_vals < sf_norm, 'RESSF', 'RESMF')
            df.loc[unclassified, 'segment'] = assigned
            
            n_sf = (assigned == 'RESSF').sum()
            n_mf = (assigned == 'RESMF').sum()
            logger.info(
                f"B25024: Assigned {n_unclassified:,} unclassified premises → "
                f"RESSF: {n_sf:,} ({sf_norm*100:.0f}%), RESMF: {n_mf:,} ({(1-sf_norm)*100:.0f}%)"
            )
    
    # --- B25034: Fill missing vintage ---
    vintage_dist = census.get('vintage_distribution', {})
    if vintage_dist and 'setyear' in df.columns:
        missing_vintage = df['setyear'].isna()
        n_missing = missing_vintage.sum()
        
        if n_missing > 0:
            # Assign vintage era proportionally, then pick a representative year
            era_to_year = {
                'pre-1980': 1965,
                '1980-1999': 1990,
                '2000-2009': 2005,
                '2010-2014': 2012,
                '2015+': 2020,
            }
            eras = list(vintage_dist.keys())
            probs = [vintage_dist[e] for e in eras]
            # Normalize
            total_p = sum(probs)
            probs = [p / total_p for p in probs]
            
            np.random.seed(43)
            assigned_eras = np.random.choice(eras, size=n_missing, p=probs)
            assigned_years = [era_to_year.get(e, 2000) for e in assigned_eras]
            df.loc[missing_vintage, 'setyear'] = assigned_years
            
            era_counts = pd.Series(assigned_eras).value_counts()
            logger.info(f"B25034: Assigned vintage to {n_missing:,} premises: {era_counts.to_dict()}")
    
    return df


def export_census_summary(census: Dict, output_dir: str):
    """Export Census distributions as CSVs and JSONs for the scenario folder."""
    output_dir = Path(output_dir)
    
    # Heating fuel trend
    trend = census.get('heating_fuel_trend', {})
    if trend:
        rows = []
        for year, data in sorted(trend.items()):
            rows.append({'year': year, **data})
        df = pd.DataFrame(rows)
        df.to_csv(output_dir / 'census_heating_fuel_trend.csv', index=False)
        df.to_json(output_dir / 'census_heating_fuel_trend.json', orient='records', indent=2)
    
    # Segment distribution
    seg = census.get('segment_distribution', {})
    if seg:
        df = pd.DataFrame([seg])
        df.to_csv(output_dir / 'census_segment_distribution.csv', index=False)
        df.to_json(output_dir / 'census_segment_distribution.json', orient='records', indent=2)
    
    # Vintage distribution
    vin = census.get('vintage_distribution', {})
    if vin:
        df = pd.DataFrame([vin])
        df.to_csv(output_dir / 'census_vintage_distribution.csv', index=False)
        df.to_json(output_dir / 'census_vintage_distribution.json', orient='records', indent=2)


def load_b25024_segment_trend() -> pd.DataFrame:
    """
    Load B25024 (Units in Structure) for all available years to compute
    the historical SF/MF/Mobile share trend.

    Returns DataFrame with columns: year, total, sf_pct, mf_pct, mobile_pct
    """
    b24_dir = config.B25024_COUNTY_DIR
    if not os.path.exists(b24_dir):
        logger.warning(f"B25024 county dir not found: {b24_dir}")
        return pd.DataFrame()

    rows = []
    for f in sorted(os.listdir(b24_dir)):
        if not f.endswith('.csv'):
            continue
        try:
            year = int(f.split('_')[-1].replace('.csv', ''))
        except ValueError:
            continue
        df = pd.read_csv(os.path.join(b24_dir, f))
        total = df['B25024_001E'].sum()
        if total <= 0:
            continue
        sf = df['B25024_002E'].sum() + df['B25024_003E'].sum()
        mf = df[['B25024_004E', 'B25024_005E', 'B25024_006E',
                  'B25024_007E', 'B25024_008E', 'B25024_009E']].sum().sum()
        mobile = df['B25024_010E'].sum()
        rows.append({
            'year': year,
            'total': int(total),
            'sf_pct': round(sf / total * 100, 2),
            'mf_pct': round(mf / total * 100, 2),
            'mobile_pct': round(mobile / total * 100, 2),
        })

    result = pd.DataFrame(rows).sort_values('year').reset_index(drop=True)
    if not result.empty:
        logger.info(
            f"B25024 trend: {len(result)} years ({result['year'].min()}-{result['year'].max()}), "
            f"MF share {result.iloc[0]['mf_pct']}% → {result.iloc[-1]['mf_pct']}%"
        )
    return result


def compute_segment_shift_rates(b25024_trend: pd.DataFrame) -> Dict[str, float]:
    """
    Compute annual percentage-point shift rates from B25024 historical trend.

    Uses linear regression on the last 10 years of data to get the annual
    change in SF/MF/Mobile share (in percentage points per year).

    Returns dict like:
        {'sf_annual_pp': -0.04, 'mf_annual_pp': +0.12, 'mobile_annual_pp': -0.08}
    """
    if b25024_trend.empty or len(b25024_trend) < 3:
        return {'sf_annual_pp': 0.0, 'mf_annual_pp': 0.0, 'mobile_annual_pp': 0.0}

    # Use last 10 years for trend
    recent = b25024_trend.tail(10).copy()
    years = recent['year'].values
    n = len(years)

    # Simple linear regression: slope = Σ((x-x̄)(y-ȳ)) / Σ((x-x̄)²)
    x_mean = years.mean()
    x_dev = years - x_mean

    rates = {}
    for col, key in [('sf_pct', 'sf_annual_pp'), ('mf_pct', 'mf_annual_pp'), ('mobile_pct', 'mobile_annual_pp')]:
        y = recent[col].values
        y_mean = y.mean()
        slope = (x_dev * (y - y_mean)).sum() / (x_dev ** 2).sum()
        rates[key] = round(slope, 4)

    logger.info(
        f"B25024 segment shift rates (pp/yr): "
        f"SF={rates['sf_annual_pp']:+.3f}, MF={rates['mf_annual_pp']:+.3f}, "
        f"Mobile={rates['mobile_annual_pp']:+.3f}"
    )
    return rates


def project_segment_shares(
    base_sf_pct: float,
    base_mf_pct: float,
    shift_rates: Dict[str, float],
    forecast_horizon: int
) -> pd.DataFrame:
    """
    Project segment shares forward using the historical shift rates.

    Args:
        base_sf_pct: SF share in base year (e.g., 76.3% of NWN customers)
        base_mf_pct: MF share in base year (e.g., 23.7%)
        shift_rates: Annual pp shift from compute_segment_shift_rates
        forecast_horizon: Number of years to project

    Returns DataFrame with columns: year_offset, sf_pct, mf_pct
    """
    rows = []
    sf = base_sf_pct
    mf = base_mf_pct
    sf_rate = shift_rates.get('sf_annual_pp', 0.0)
    mf_rate = shift_rates.get('mf_annual_pp', 0.0)

    for yr_off in range(forecast_horizon + 1):
        rows.append({'year_offset': yr_off, 'sf_pct': round(sf, 2), 'mf_pct': round(mf, 2)})
        # Apply shift (clamp to reasonable bounds)
        sf = max(50.0, min(95.0, sf + sf_rate))
        mf = max(5.0, min(50.0, mf + mf_rate))

    return pd.DataFrame(rows)
