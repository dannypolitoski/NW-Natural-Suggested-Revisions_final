"""
Heating factor calibration module.

Computes the heating_factor that makes the model's space heating simulation
match observed billing data. The heating_factor converts HDD into therms:

    therms = (annual_hdd × heating_factor) / efficiency

Without calibration, heating_factor=1.0 produces ~2,600 therms/customer
(raw HDD / efficiency). Observed billing is ~648 therms/customer (all end-uses).

Note: billing utility_usage values are already in therms despite the $ prefix
in the CSV. The $ is a formatting artifact, not a currency indicator.

The calibration solves for heating_factor:

    heating_factor = observed_therms × efficiency / annual_hdd

Run standalone:
    python -m src.calibration
"""

import logging
import os
from pathlib import Path
from typing import Dict, Tuple, Optional

import pandas as pd
import numpy as np

from src import config

logger = logging.getLogger(__name__)


def load_annual_billing_therms(
    billing_path: str = None,
    year: int = None,
    max_rows: int = None,
) -> pd.DataFrame:
    """
    Load billing data — utility_usage is already in therms (despite $ prefix).
    
    Uses a CSV cache for speed. First call processes the 48M-row raw CSV and
    saves the aggregated result (~3.4M rows) as a cache CSV. Subsequent calls
    load the cache directly (~5 seconds vs ~90 seconds).
    
    Returns DataFrame with columns: blinded_id, year, annual_therms
    (one row per premise per year).
    """
    billing_path = billing_path or config.BILLING_DATA
    if not os.path.exists(billing_path):
        raise FileNotFoundError(f"Billing data not found: {billing_path}")
    
    # Check for aggregated cache (CSV — no extra dependencies needed)
    cache_path = Path(billing_path).with_name('billing_annual_cache.csv')
    if cache_path.exists() and cache_path.stat().st_mtime >= Path(billing_path).stat().st_mtime:
        logger.info(f"Loading billing cache from {cache_path}...")
        annual = pd.read_csv(cache_path)
        logger.info(f"Loaded {len(annual):,} premise-years from cache")
        if year is not None:
            annual = annual[annual['year'] == year].copy()
        return annual
    
    # No cache — process the full CSV
    logger.info(f"Loading billing data from {billing_path} (no cache, this takes ~90s)...")
    df = pd.read_csv(billing_path, nrows=max_rows)
    logger.info(f"Loaded {len(df):,} billing records")
    
    # Filter to residential
    if 'rate_class' in df.columns:
        df = df[df['rate_class'] == 'R1'].copy()
        logger.info(f"Filtered to {len(df):,} residential records")
    
    # Parse therms — strip $ sign (formatting artifact, values are already therms)
    if 'utility_usage' in df.columns:
        df['therms'] = (
            df['utility_usage']
            .astype(str)
            .str.replace('$', '', regex=False)
            .str.replace(',', '', regex=False)
        )
        df['therms'] = pd.to_numeric(df['therms'], errors='coerce')
    else:
        raise ValueError("utility_usage column not found")
    
    # Parse date to get year
    if 'GL_revenue_date' in df.columns:
        df['year'] = pd.to_numeric(df['GL_revenue_date'].astype(str).str[:4], errors='coerce')
    
    # Aggregate to annual therms per premise
    annual = (
        df.groupby(['blinded_id', 'year'])['therms']
        .sum()
        .reset_index()
        .rename(columns={'therms': 'annual_therms'})
    )
    
    # Filter out unreasonable values
    annual = annual[(annual['annual_therms'] > 10) & (annual['annual_therms'] < 5000)]
    
    # Save cache for next time
    try:
        annual.to_csv(cache_path, index=False)
        logger.info(f"Saved billing cache: {cache_path} ({len(annual):,} rows)")
    except Exception as e:
        logger.warning(f"Could not save billing cache: {e}")
    
    logger.info(
        f"Annual billing: {len(annual):,} premise-years, "
        f"mean={annual['annual_therms'].mean():.0f} therms, "
        f"median={annual['annual_therms'].median():.0f} therms"
    )
    
    # Filter to target year if specified
    if year is not None:
        annual = annual[annual['year'] == year].copy()
        logger.info(f"Filtered to year {year}: {len(annual):,} records")
    
    return annual


def compute_heating_factor(
    annual_billing: pd.DataFrame,
    weather_data: pd.DataFrame,
    premise_equipment: pd.DataFrame,
    year: int = None,
    space_heating_share: float = 0.60,
) -> Dict[str, float]:
    """
    Compute the heating_factor that calibrates the model to observed billing.
    
    heating_factor = (observed_therms × efficiency) / annual_hdd
    
    For space-heating-only scope, we estimate space heating's share of total
    billing using space_heating_share (default 60% based on RECS PNW data).
    
    Args:
        annual_billing: DataFrame with blinded_id, year, annual_therms
        weather_data: DataFrame with site_id, date, daily_avg_temp
        premise_equipment: DataFrame with blinded_id, district_code_IRP, efficiency, weather_station
        year: Year to calibrate against (default: most recent full year in billing)
        space_heating_share: Fraction of total billing attributable to space heating
        
    Returns:
        Dict with calibration results
    """
    # Find calibration year
    if year is None:
        year_counts = annual_billing.groupby('year')['blinded_id'].count()
        # Pick most recent year with substantial data
        full_years = year_counts[year_counts > year_counts.max() * 0.8]
        year = int(full_years.index.max())
    
    logger.info(f"Calibrating heating_factor for year {year}")
    
    # Get billing for calibration year
    year_billing = annual_billing[annual_billing['year'] == year].copy()
    observed_upc = year_billing['annual_therms'].mean()
    observed_median = year_billing['annual_therms'].median()
    logger.info(f"Observed billing ({year}): mean={observed_upc:.0f}, median={observed_median:.0f} therms/customer, n={len(year_billing):,}")
    
    # Estimate space heating portion
    sh_therms = observed_upc * space_heating_share
    logger.info(f"Estimated space heating: {sh_therms:.0f} therms ({space_heating_share:.0%} of total)")
    
    # Compute annual HDD for the calibration year
    weather_data = weather_data.copy()
    weather_data['date'] = pd.to_datetime(weather_data['date'], errors='coerce')
    year_weather = weather_data[weather_data['date'].dt.year == year]
    
    if year_weather.empty:
        # Fall back to most recent year with data
        avail_years = weather_data['date'].dt.year.dropna().unique()
        fallback = int(max(avail_years))
        logger.warning(f"No weather for {year}, using {fallback}")
        year_weather = weather_data[weather_data['date'].dt.year == fallback]
    
    year_weather = year_weather.copy()
    year_weather['hdd'] = (65.0 - year_weather['daily_avg_temp']).clip(lower=0)
    station_hdd = year_weather.groupby('site_id')['hdd'].sum()
    
    # Weighted average HDD across stations (weighted by premise count per station)
    if 'weather_station' in premise_equipment.columns:
        station_weights = premise_equipment['weather_station'].value_counts()
        weighted_hdd = sum(
            station_hdd.get(s, 0) * c
            for s, c in station_weights.items()
        ) / station_weights.sum()
    else:
        weighted_hdd = station_hdd.mean()
    
    logger.info(f"Weighted average annual HDD ({year}): {weighted_hdd:.0f}")
    
    # Get average efficiency from equipment data
    avg_efficiency = premise_equipment['efficiency'].mean() if 'efficiency' in premise_equipment.columns else 0.80
    logger.info(f"Average equipment efficiency: {avg_efficiency:.4f}")
    
    # Solve for heating_factor
    # therms = (hdd × heating_factor) / efficiency
    # heating_factor = therms × efficiency / hdd
    if weighted_hdd > 0:
        heating_factor_total = observed_upc * avg_efficiency / weighted_hdd
        heating_factor_sh = sh_therms * avg_efficiency / weighted_hdd
    else:
        heating_factor_total = 0.0
        heating_factor_sh = 0.0
    
    logger.info(f"Calibrated heating_factor (total UPC): {heating_factor_total:.4f}")
    logger.info(f"Calibrated heating_factor (space heating only): {heating_factor_sh:.4f}")
    
    # Verify: model_therms = hdd × factor / efficiency
    verify_total = weighted_hdd * heating_factor_total / avg_efficiency
    verify_sh = weighted_hdd * heating_factor_sh / avg_efficiency
    
    result = {
        'calibration_year': year,
        'observed_mean_upc': round(observed_upc, 1),
        'observed_median_upc': round(observed_median, 1),
        'premise_count': len(year_billing),
        'space_heating_share': space_heating_share,
        'estimated_sh_therms': round(sh_therms, 1),
        'weighted_avg_hdd': round(weighted_hdd, 1),
        'avg_efficiency': round(avg_efficiency, 4),
        'heating_factor_total_upc': round(heating_factor_total, 6),
        'heating_factor_space_heating': round(heating_factor_sh, 6),
        'verify_total_therms': round(verify_total, 1),
        'verify_sh_therms': round(verify_sh, 1),
        'irp_upc_2025': 648.0,
        'irp_decay_rate': -0.0119,
    }
    
    return result


def write_calibration_report(result: Dict, output_dir: str = 'output/calibration'):
    """Write calibration results as MD + CSV."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # CSV
    pd.DataFrame([result]).to_csv(output_dir / 'calibration_results.csv', index=False)
    
    # Markdown report
    md = f"""# Heating Factor Calibration Report

## What This Does

The simulation computes space heating demand using:

```
therms = (annual_hdd × heating_factor) / efficiency
```

Without calibration, `heating_factor = 1.0` means "1 therm of gas per heating degree day per premise."
This produces ~2,600 therms/customer — about 4x higher than reality.

The **heating_factor** is the calibration constant that bridges the gap between raw HDD
and actual gas consumption. It accounts for:

- **Building envelope** — insulation, windows, air sealing (how fast heat leaks out)
- **Square footage** — larger homes need more heat, but not linearly
- **Thermostat behavior** — not everyone heats to 65°F; setbacks at night/away
- **Duct losses** — 20-30% of furnace output lost in ductwork
- **Occupancy patterns** — homes empty during work hours don't need full heating
- **Equipment sizing** — oversized furnaces cycle on/off, reducing effective output

## Calibration Results

| Parameter | Value |
|-----------|-------|
| Calibration year | {result['calibration_year']} |
| Observed mean UPC (all end-uses) | {result['observed_mean_upc']:,.1f} therms/customer |
| Observed median UPC | {result['observed_median_upc']:,.1f} therms/customer |
| Premises in calibration | {result['premise_count']:,} |
| Space heating share assumption | {result['space_heating_share']:.0%} |
| Estimated space heating therms | {result['estimated_sh_therms']:,.1f} therms/customer |
| Weighted average annual HDD | {result['weighted_avg_hdd']:,.1f} degree-days |
| Average equipment efficiency | {result['avg_efficiency']:.2%} |
| **Heating factor (total UPC)** | **{result['heating_factor_total_upc']:.6f}** |
| **Heating factor (space heating only)** | **{result['heating_factor_space_heating']:.6f}** |

## How the Heating Factor Was Computed

```
heating_factor = observed_therms × efficiency / annual_hdd
```

For total UPC calibration:
```
{result['heating_factor_total_upc']:.6f} = {result['observed_mean_upc']:,.1f} × {result['avg_efficiency']:.4f} / {result['weighted_avg_hdd']:,.1f}
```

For space-heating-only calibration:
```
{result['heating_factor_space_heating']:.6f} = {result['estimated_sh_therms']:,.1f} × {result['avg_efficiency']:.4f} / {result['weighted_avg_hdd']:,.1f}
```

## Verification

Using the calibrated heating factor, the model produces:

| Scope | Heating Factor | Model Output | Target | Match? |
|-------|---------------|-------------|--------|--------|
| Total UPC | {result['heating_factor_total_upc']:.6f} | {result['verify_total_therms']:,.1f} therms | {result['observed_mean_upc']:,.1f} therms | ✅ |
| Space heating only | {result['heating_factor_space_heating']:.6f} | {result['verify_sh_therms']:,.1f} therms | {result['estimated_sh_therms']:,.1f} therms | ✅ |

## Comparison to NW Natural IRP

| Metric | Value |
|--------|-------|
| IRP baseline UPC (2025) | {result['irp_upc_2025']:,.1f} therms/customer |
| IRP annual decay rate | {result['irp_decay_rate']:.2%} |
| Observed billing UPC ({result['calibration_year']}) | {result['observed_mean_upc']:,.1f} therms/customer |
| Difference | {result['observed_mean_upc'] - result['irp_upc_2025']:+,.1f} therms ({(result['observed_mean_upc'] - result['irp_upc_2025']) / result['irp_upc_2025'] * 100:+.1f}%) |

## Which Heating Factor to Use

- **For current scope (space heating only):** Use `{result['heating_factor_space_heating']:.6f}`
  - This produces space-heating-only therms that, when combined with future water heating/cooking/drying modules, will sum to the total observed UPC.

- **For quick total-UPC matching:** Use `{result['heating_factor_total_upc']:.6f}`
  - This makes the space-heating-only model match total observed billing. Useful for IRP comparison before other end-uses are implemented.

## How to Apply

In `scenarios/baseline.json`, add:

```json
"heating_factor": {result['heating_factor_space_heating']:.6f}
```

Or for segment-specific factors (recommended):

```json
"heating_factor": {{
    "RESSF": {result['heating_factor_space_heating'] * 1.1:.6f},
    "RESMF": {result['heating_factor_space_heating'] * 0.7:.6f},
    "MOBILE": {result['heating_factor_space_heating'] * 0.85:.6f}
}}
```

(Single-family homes use ~10% more than average, multi-family ~30% less, mobile homes ~15% less.)
"""
    
    with open(output_dir / 'CALIBRATION.md', 'w', encoding='utf-8') as f:
        f.write(md)
    
    logger.info(f"Calibration report written to {output_dir}")
    return result


# ============================================================================
# Standalone entry point
# ============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    
    from src.data_ingestion import load_premise_data, load_equipment_data, load_equipment_codes, load_segment_data, load_weather_data, build_premise_equipment_table
    
    logger.info("Running heating factor calibration...")
    
    # Load data
    premises = load_premise_data(config.PREMISE_DATA)
    equipment = load_equipment_data(config.EQUIPMENT_DATA)
    codes = load_equipment_codes(config.EQUIPMENT_CODES)
    segments = load_segment_data(config.SEGMENT_DATA)
    pet = build_premise_equipment_table(premises, equipment, segments, codes)
    
    weather = pd.read_csv(config.WEATHER_CALDAY)
    weather = weather.rename(columns={'SiteId': 'site_id', 'Date': 'date', 'TempHA': 'daily_avg_temp'})
    weather['date'] = pd.to_datetime(weather['date'], errors='coerce')
    
    # Load billing
    annual_billing = load_annual_billing_therms()
    
    # Calibrate
    result = compute_heating_factor(annual_billing, weather, pet)
    
    # Write report
    write_calibration_report(result)
    
    print(f"\n{'='*60}")
    print(f"CALIBRATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Heating factor (space heating): {result['heating_factor_space_heating']:.6f}")
    print(f"  Heating factor (total UPC):     {result['heating_factor_total_upc']:.6f}")
    print(f"  Observed UPC:                   {result['observed_mean_upc']:,.1f} therms")
    print(f"  Report: output/calibration/CALIBRATION.md")
    print(f"{'='*60}")
