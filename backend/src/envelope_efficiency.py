"""
Building envelope efficiency model.

Converts vintage heating multipliers into a continuous envelope efficiency
index and projects forward based on energy code improvement trends.

The envelope efficiency index represents how much heat a building needs
relative to a 2000-2009 baseline (index = 1.0). Lower = more efficient.
"""

import logging
from typing import Dict, List

import pandas as pd
import numpy as np

from src import parameter_curves as pc

logger = logging.getLogger(__name__)

# Historical envelope efficiency by construction year (from config vintage multipliers)
# These represent heating demand relative to 2000-2009 baseline
# Source: RBSA building shell data, nw_energy_proxies.csv
HISTORICAL_ENVELOPE = {
    1960: 1.40,   # Pre-1970: worst insulation, single-pane
    1970: 1.35,   # 1970s: slightly better
    1980: 1.25,   # First energy codes (Oregon 1978)
    1990: 1.15,   # Improved codes
    2000: 1.00,   # Baseline era
    2005: 1.00,   # Baseline
    2010: 0.85,   # 2009 IECC adoption
    2015: 0.75,   # 2012 IECC + Oregon amendments
    2020: 0.70,   # 2018 IECC
    2023: 0.65,   # 2021 IECC + Oregon 2023 ORSC
    2025: 0.62,   # 2025 OEESC (ASHRAE 90.1-2022)
}

# Projected improvement rate: ~2% per year from tightening codes + technology
# Oregon mandated 15% improvement by 2015 (from 2006 baseline), and codes
# continue to tighten roughly every 3 years
PROJECTED_ANNUAL_IMPROVEMENT = 0.02  # 2%/yr envelope improvement for new construction


def get_envelope_index(construction_year: int) -> float:
    """Get the envelope efficiency index for a given construction year."""
    years = sorted(HISTORICAL_ENVELOPE.keys())
    
    if construction_year <= years[0]:
        return HISTORICAL_ENVELOPE[years[0]]
    if construction_year >= years[-1]:
        # Project forward from last known point
        last_year = years[-1]
        last_val = HISTORICAL_ENVELOPE[last_year]
        years_forward = construction_year - last_year
        return max(0.40, last_val * (1 - PROJECTED_ANNUAL_IMPROVEMENT) ** years_forward)
    
    # Interpolate between known points
    for i in range(len(years) - 1):
        if years[i] <= construction_year <= years[i + 1]:
            frac = (construction_year - years[i]) / (years[i + 1] - years[i])
            return HISTORICAL_ENVELOPE[years[i]] * (1 - frac) + HISTORICAL_ENVELOPE[years[i + 1]] * frac
    
    return 1.0


def compute_fleet_envelope_efficiency(
    vintage_counts: Dict[str, int],
    segment_multipliers: Dict[str, float],
    segment_counts: Dict[str, int],
    forecast_year: int = None,
) -> Dict[str, float]:
    """
    Compute fleet-wide average envelope efficiency index by segment.
    
    Args:
        vintage_counts: {vintage_era: count} e.g. {'pre-1980': 76424, ...}
        segment_multipliers: {'RESSF': 1.05, 'RESMF': 0.70}
        segment_counts: {'RESSF': 163000, 'RESMF': 50700}
        forecast_year: If set, include projected new construction
    
    Returns:
        {'RESSF': avg_index, 'RESMF': avg_index, 'ALL': avg_index}
    """
    # Map vintage eras to representative years
    era_to_year = {
        'pre-1980': 1965, '1980-1999': 1990, '2000-2009': 2005,
        '2010-2014': 2012, '2015+': 2020,
    }
    
    # Compute weighted average envelope index
    total_weighted = 0.0
    total_count = 0
    for era, count in vintage_counts.items():
        rep_year = era_to_year.get(era, 2000)
        idx = get_envelope_index(rep_year)
        total_weighted += idx * count
        total_count += count
    
    avg_all = total_weighted / total_count if total_count > 0 else 1.0
    
    result = {'ALL': round(avg_all, 4)}
    for seg, mult in segment_multipliers.items():
        # Segment multiplier adjusts the envelope index
        # MF (0.70) means 30% less heat needed → better envelope effective index
        result[seg] = round(avg_all * mult / 1.0, 4)  # relative to average
    
    return result


def project_envelope_trend(
    base_year: int,
    forecast_horizon: int,
    vintage_counts: Dict[str, int],
    segment_multipliers: Dict[str, float],
    housing_growth_rate: float = 0.01,
    demolition_rate: float = 0.002,
) -> pd.DataFrame:
    """
    Project fleet-wide envelope efficiency over the forecast period.
    
    As old homes are demolished and new efficient homes are built,
    the fleet average improves.
    
    Returns DataFrame with: year, envelope_index_all, envelope_index_sf, envelope_index_mf,
                            new_construction_index
    """
    era_to_year = {
        'pre-1980': 1965, '1980-1999': 1990, '2000-2009': 2005,
        '2010-2014': 2012, '2015+': 2020,
    }
    
    # Vintage demolition rates (older homes demolished faster)
    vintage_demo = {
        'pre-1980': demolition_rate * 2.5,
        '1980-1999': demolition_rate * 1.5,
        '2000-2009': demolition_rate * 0.5,
        '2010-2014': demolition_rate * 0.2,
        '2015+': 0.0,
    }
    
    rows = []
    current_counts = dict(vintage_counts)
    base_total = sum(current_counts.values())
    
    for yr_off in range(forecast_horizon + 1):
        year = base_year + yr_off
        
        # New construction envelope index for this year
        new_idx = get_envelope_index(year)
        
        # Compute fleet average
        total_weighted = 0.0
        total_count = 0
        for era, count in current_counts.items():
            rep_year = era_to_year.get(era, 2000)
            idx = get_envelope_index(rep_year)
            total_weighted += idx * count
            total_count += count
        
        avg_all = total_weighted / total_count if total_count > 0 else 1.0
        sf_mult = segment_multipliers.get('RESSF', 1.05)
        mf_mult = segment_multipliers.get('RESMF', 0.70)
        
        rows.append({
            'year': year,
            'envelope_index_all': round(avg_all, 4),
            'envelope_index_sf': round(avg_all * sf_mult, 4),
            'envelope_index_mf': round(avg_all * mf_mult, 4),
            'new_construction_index': round(new_idx, 4),
        })
        
        # Evolve vintage counts for next year
        if yr_off < forecast_horizon:
            # Demolitions by vintage
            for era in list(current_counts.keys()):
                demo = vintage_demo.get(era, 0)
                current_counts[era] = int(round(current_counts[era] * (1 - demo)))
            
            # New construction goes into 2015+ bucket
            new_total = int(round(base_total * ((1 + pc.resolve(housing_growth_rate, base_year + yr_off + 1, 0.01)) ** (yr_off + 1))))
            current_total = sum(current_counts.values())
            new_units = max(0, new_total - current_total)
            current_counts['2015+'] = current_counts.get('2015+', 0) + new_units
    
    df = pd.DataFrame(rows)
    logger.info(
        f"Envelope efficiency: {df.iloc[0]['envelope_index_all']:.3f} → "
        f"{df.iloc[-1]['envelope_index_all']:.3f} "
        f"(new construction: {df.iloc[0]['new_construction_index']:.3f} → "
        f"{df.iloc[-1]['new_construction_index']:.3f})"
    )
    return df
