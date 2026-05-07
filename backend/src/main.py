"""
CLI entry point for NW Natural End-Use Forecasting Model.

Provides command-line interface for running scenarios, comparing results,
and generating outputs. Orchestrates the complete pipeline:
  config → ingest → stock → simulate → aggregate → export

Usage:
    python -m src.main scenarios/baseline.json --output-dir output/baseline
    python -m src.main scenarios/baseline.json scenarios/high_electrification.json --compare
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any

import pandas as pd

from src.config import (
    BASE_YEAR, OUTPUT_DIR, PREMISE_DATA, EQUIPMENT_DATA, EQUIPMENT_CODES,
    SEGMENT_DATA, WEATHER_CALDAY, WATER_TEMP
)
from src.data_ingestion import (
    load_premise_data, load_equipment_data, load_equipment_codes,
    load_segment_data, load_weather_data, load_water_temperature,
    build_premise_equipment_table
)
from src.scenarios import ScenarioConfig, run_scenario, compare_scenarios
from src.aggregation import export_results
from src.scenario_charts import generate_scenario_charts
from src.census_integration import (
    load_census_distributions, enrich_premise_equipment, export_census_summary,
    load_b25024_segment_trend, compute_segment_shift_rates, project_segment_shares
)
from src.recs_integration import load_recs_enduse_trend, compute_non_heating_ratios, export_recs_summary
from src.envelope_efficiency import project_envelope_trend
from src import parameter_curves as pc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_scenario_config(config_path: str) -> ScenarioConfig:
    """
    Load scenario configuration from JSON file.
    
    Args:
        config_path: Path to scenario JSON file
    
    Returns:
        ScenarioConfig object
    
    Raises:
        FileNotFoundError: If config file not found
        json.JSONDecodeError: If JSON is invalid
        ValueError: If required fields missing
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Scenario config not found: {config_path}")
    
    logger.info(f"Loading scenario config: {config_path}")
    
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    # Validate required fields
    required_fields = {'name', 'base_year', 'forecast_horizon'}
    if not required_fields.issubset(data.keys()):
        missing = required_fields - set(data.keys())
        raise ValueError(f"Missing required fields in config: {missing}")
    
    config = ScenarioConfig.from_dict(data)
    logger.info(f"Loaded scenario: {config.name}")
    
    return config


def load_pipeline_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, float], Dict, pd.DataFrame, Dict[str, float], pd.DataFrame, Dict[str, float]]:
    """
    Load all data required for the pipeline.
    
    Loads premise, equipment, weather, water temperature, Census ACS, and RECS data.
    Builds the unified premise-equipment table, enriches it with Census
    distributions (B25024 segment, B25034 vintage, B25040 heating fuel),
    and prepares baseload factors.
    
    Returns:
        Tuple of:
            - premise_equipment: Unified premise-equipment DataFrame (Census-enriched)
            - weather_data: Weather data by station and year
            - water_temp_data: Water temperature data
            - baseload_factors: Dict mapping end_use to annual consumption
            - census: Dict with Census ACS distributions
            - recs_trend: DataFrame with RECS end-use shares by survey year
            - recs_ratios: Dict with non-heating ratios relative to space heating
    
    Raises:
        FileNotFoundError: If any required data file not found
        ValueError: If data loading or joining fails
    """
    logger.info("Loading pipeline data...")
    
    # Load core NW Natural data
    logger.info("Loading premise data...")
    premises = load_premise_data(PREMISE_DATA)
    logger.info(f"  Loaded {len(premises)} premises")
    
    logger.info("Loading equipment data...")
    equipment = load_equipment_data(EQUIPMENT_DATA)
    logger.info(f"  Loaded {len(equipment)} equipment records")
    
    logger.info("Loading equipment codes...")
    codes = load_equipment_codes(EQUIPMENT_CODES)
    logger.info(f"  Loaded {len(codes)} equipment codes")
    
    logger.info("Loading segment data...")
    segments = load_segment_data(SEGMENT_DATA)
    logger.info(f"  Loaded {len(segments)} segment records")
    
    # Build unified premise-equipment table
    logger.info("Building premise-equipment table...")
    premise_equipment = build_premise_equipment_table(premises, equipment, segments, codes)
    logger.info(f"  Built table with {len(premise_equipment)} records")
    
    # Load weather data
    logger.info("Loading weather data...")
    weather_data = load_weather_data(WEATHER_CALDAY)
    # Normalize column names to match simulation expectations
    weather_col_map = {'SiteId': 'site_id', 'Date': 'date', 'TempHA': 'daily_avg_temp'}
    weather_data = weather_data.rename(columns={k: v for k, v in weather_col_map.items() if k in weather_data.columns})
    if 'date' in weather_data.columns:
        weather_data['date'] = pd.to_datetime(weather_data['date'], errors='coerce')
    logger.info(f"  Loaded weather data: {len(weather_data)} records")
    
    # Load water temperature data
    logger.info("Loading water temperature data...")
    water_temp_data = load_water_temperature(WATER_TEMP)
    # Normalize column names to match simulation expectations
    water_col_map = {'Date': 'date', 'BullRunWaterTemp': 'cold_water_temp'}
    water_temp_data = water_temp_data.rename(columns={k: v for k, v in water_col_map.items() if k in water_temp_data.columns})
    if 'date' in water_temp_data.columns:
        water_temp_data['date'] = pd.to_datetime(water_temp_data['date'], errors='coerce')
    logger.info(f"  Loaded water temperature data: {len(water_temp_data)} records")
    
    # Prepare baseload factors (placeholder - can be extended with actual factors)
    baseload_factors = {
        'space_heating': 0.0,      # Weather-driven, not baseload
        'water_heating': 0.0,      # Weather-driven, not baseload
        'cooking': 30.0,           # therms/year
        'clothes_drying': 20.0,    # therms/year
        'fireplace': 55.0,         # therms/year
        'other': 10.0,             # therms/year
    }
    
    logger.info("Pipeline data loaded successfully")
    
    # Load Census ACS distributions and enrich premise-equipment table
    logger.info("Loading Census ACS distributions (B25024, B25034, B25040)...")
    census = load_census_distributions()
    if census:
        logger.info(f"  Census data loaded: {list(census.keys())}")
        premise_equipment = enrich_premise_equipment(premise_equipment, census)
        logger.info(f"  Enriched premise-equipment table with Census distributions")
    else:
        logger.warning("  No Census data loaded; skipping enrichment")
        census = {}
    
    # Load RECS end-use trend (1993-2020) and compute non-heating ratios
    logger.info("Loading RECS end-use trend (1993-2020)...")
    recs_trend = load_recs_enduse_trend()
    recs_ratios = compute_non_heating_ratios(recs_trend)
    
    # Load B25024 segment trend for SF→MF shift projection
    logger.info("Loading B25024 segment trend for SF/MF shift...")
    b25024_trend = load_b25024_segment_trend()
    segment_shift_rates = compute_segment_shift_rates(b25024_trend)
    
    return premise_equipment, weather_data, water_temp_data, baseload_factors, census, recs_trend, recs_ratios, b25024_trend, segment_shift_rates


def run_single_scenario(
    config: ScenarioConfig,
    premise_equipment: pd.DataFrame,
    weather_data: pd.DataFrame,
    water_temp_data: pd.DataFrame,
    baseload_factors: Dict[str, float],
    output_dir: str,
    non_heating_ratios: Dict[str, float] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Run a single scenario and return results.
    
    Args:
        config: ScenarioConfig object
        premise_equipment: Unified premise-equipment DataFrame
        weather_data: Weather data
        water_temp_data: Water temperature data
        baseload_factors: Baseload consumption factors
        output_dir: Directory to save results
        non_heating_ratios: RECS-derived non-heating end-use ratios
    
    Returns:
        Tuple of (results_df, metadata)
    """
    logger.info(f"Running scenario: {config.name}")
    
    results_df, metadata = run_scenario(
        config,
        premise_equipment,
        weather_data,
        water_temp_data,
        baseload_factors,
        output_dir=output_dir,
        non_heating_ratios=non_heating_ratios
    )
    
    logger.info(f"Scenario complete: {config.name}")
    logger.info(f"  Total rows: {len(results_df)}")
    logger.info(f"  Years: {config.base_year}-{config.base_year + config.forecast_horizon}")
    logger.info(f"  End-uses: {results_df['end_use'].nunique()}")
    
    return results_df, metadata


def print_summary_statistics(results_df: pd.DataFrame, metadata: Dict[str, Any]) -> None:
    """
    Print summary statistics to stdout.
    
    Args:
        results_df: Results DataFrame
        metadata: Scenario metadata
    """
    print("\n" + "="*70)
    print(f"SCENARIO: {metadata['scenario_name']}")
    print("="*70)
    
    print(f"\nConfiguration:")
    print(f"  Base Year: {metadata['base_year']}")
    print(f"  Forecast Horizon: {metadata['forecast_horizon']} years")
    def _fmt_param(v):
        """Format a parameter value — handles both numbers and curve dicts."""
        if isinstance(v, (int, float)):
            return f"{v:.2%}"
        if isinstance(v, dict):
            return "curve (see JSON)"
        return str(v)
    
    print(f"  Housing Growth Rate: {_fmt_param(metadata['housing_growth_rate'])}")
    print(f"  Electrification Rate: {_fmt_param(metadata['electrification_rate'])}")
    print(f"  Efficiency Improvement: {_fmt_param(metadata['efficiency_improvement'])}")
    print(f"  Weather Assumption: {metadata['weather_assumption']}")
    print(f"  End-Use Scope: {metadata.get('end_use_scope', 'all')}")
    print(f"  Max Premises: {metadata.get('max_premises', 0)} (0=all)")
    print(f"  Vectorized: {metadata.get('vectorized', False)}")
    
    print(f"\nResults Summary:")
    print(f"  Total Rows: {metadata['total_rows']}")
    print(f"  Years Simulated: {metadata['years_simulated']}")
    print(f"  End-Uses: {metadata['end_uses']}")
    
    # Aggregate by year (sum months if monthly resolution)
    agg_cols = {'total_therms': 'sum', 'premise_count': 'first'}
    if 'irp_upc_therms' in results_df.columns:
        agg_cols['irp_upc_therms'] = 'first'
    by_year = results_df.groupby('year').agg(agg_cols).reset_index()
    by_year['use_per_customer'] = by_year['total_therms'] / by_year['premise_count'].clip(lower=1)

    has_irp = 'irp_upc_therms' in by_year.columns and by_year['irp_upc_therms'].notna().any()
    
    print(f"\nDemand by Year:")
    if has_irp:
        print(f"  {'Year':<8} {'Total Therms':<18} {'Model UPC':<12} {'IRP UPC':<12} {'Diff %':<10} {'Premises':<10}")
        print(f"  {'-'*70}")
        for _, row in by_year.iterrows():
            irp = row.get('irp_upc_therms', None)
            if irp and irp > 0 and row['use_per_customer'] > 0:
                diff_pct = (row['use_per_customer'] - irp) / irp * 100
                print(f"  {int(row['year']):<8} {row['total_therms']:>15,.0f} {row['use_per_customer']:>10.1f} {irp:>10.1f} {diff_pct:>+8.1f}% {int(row['premise_count']):>8,}")
            else:
                print(f"  {int(row['year']):<8} {row['total_therms']:>15,.0f} {row['use_per_customer']:>10.1f} {'N/A':>10} {'':>10} {int(row['premise_count']):>8,}")
    else:
        print(f"  {'Year':<8} {'Total Therms':<18} {'UPC':<12} {'Premises':<12}")
        print(f"  {'-'*50}")
    print(f"  {'-'*50}")
    for _, row in by_year.iterrows():
        print(f"  {int(row['year']):<8} {row['total_therms']:>15,.0f} {row['use_per_customer']:>10.1f} {int(row['premise_count']):>10,}")
    
    # Aggregate by end-use
    by_enduse = results_df.groupby('end_use')['total_therms'].sum().sort_values(ascending=False)
    
    print(f"\nDemand by End-Use (Total across all years):")
    print(f"  {'End-Use':<25} {'Total Therms':<18} {'Share':<10}")
    print(f"  {'-'*53}")
    total = by_enduse.sum()
    for enduse, therms in by_enduse.items():
        share = therms / total if total > 0 else 0
        print(f"  {enduse:<25} {therms:>15,.0f} {share:>8.1%}")
    
    print("\n" + "="*70 + "\n")


def _write_summary_report(scenario_dir: Path, results_df: pd.DataFrame, metadata: dict, by_year: pd.DataFrame):
    """Write a human-readable SUMMARY.md into the scenario folder."""
    from datetime import datetime
    ts = datetime.now().isoformat()
    name = metadata['scenario_name']
    has_irp = 'irp_upc_therms' in by_year.columns and by_year['irp_upc_therms'].notna().any()
    is_monthly = 'month' in results_df.columns

    def _fmt_md(v):
        if isinstance(v, (int, float)):
            return f"{v:.2%}"
        return "curve (see JSON)"

    lines = [
        f"# Scenario Results: {name}",
        f"Generated: {ts}", "",
        "## Configuration",
        f"- Base Year: {metadata['base_year']}",
        f"- Forecast Horizon: {metadata['forecast_horizon']} years",
        f"- Temporal Resolution: {'Monthly' if is_monthly else 'Annual'}",
        f"- Housing Growth Rate: {_fmt_md(metadata['housing_growth_rate'])}",
        f"- Electrification Rate: {_fmt_md(metadata['electrification_rate'])}",
        f"- Efficiency Improvement: {_fmt_md(metadata['efficiency_improvement'])}",
        f"- Weather Assumption: {metadata['weather_assumption']}",
        f"- End-Use Scope: {metadata.get('end_use_scope', 'all')}",
        f"- Max Premises: {metadata.get('max_premises', 0)} (0=all)",
        f"- Vectorized: {metadata.get('vectorized', False)}", "",
        "## Yearly Demand Summary", "",
    ]

    if has_irp:
        lines.append("| Year | Total Therms | Model UPC | IRP UPC | Diff % | Premises |")
        lines.append("|------|-------------|-----------|---------|--------|----------|")
        for _, row in by_year.iterrows():
            irp = row.get('irp_upc_therms', None)
            if irp and irp > 0 and row['use_per_customer'] > 0:
                diff = (row['use_per_customer'] - irp) / irp * 100
                lines.append(f"| {int(row['year'])} | {row['total_therms']:,.0f} | {row['use_per_customer']:.1f} | {irp:.1f} | {diff:+.1f}% | {int(row['premise_count']):,} |")
            else:
                lines.append(f"| {int(row['year'])} | {row['total_therms']:,.0f} | {row['use_per_customer']:.1f} | N/A | | {int(row['premise_count']):,} |")
    else:
        lines.append("| Year | Total Therms | UPC | Premises |")
        lines.append("|------|-------------|-----|----------|")
        for _, row in by_year.iterrows():
            lines.append(f"| {int(row['year'])} | {row['total_therms']:,.0f} | {row['use_per_customer']:.1f} | {int(row['premise_count']):,} |")

    # Monthly breakdown table — all years, all months
    if is_monthly:
        month_names = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
                       7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
        # Read from monthly_summary.csv if it exists (already written to disk)
        monthly_path = scenario_dir / 'monthly_summary.csv'
        if monthly_path.exists():
            import csv as _csv
            with open(monthly_path, newline='', encoding='utf-8') as f:
                monthly_rows = list(_csv.DictReader(f))
        else:
            # Build from results_df directly
            monthly_agg = results_df.groupby(['year', 'month']).agg(
                total_therms=('total_therms', 'sum'),
                premise_count=('premise_count', 'first')
            ).reset_index()
            monthly_agg['use_per_customer'] = monthly_agg['total_therms'] / monthly_agg['premise_count'].clip(lower=1)
            monthly_rows = monthly_agg.to_dict('records')

        lines += ["", "## Monthly Demand Summary (All Years)", ""]
        lines.append("| Year | Month | Total Therms | UPC (therms/customer) |")
        lines.append("|------|-------|-------------|----------------------|")
        for row in monthly_rows:
            yr = int(float(row['year']))
            mo = int(float(row['month']))
            therms = float(row['total_therms'])
            upc = float(row['use_per_customer'])
            mo_name = month_names.get(mo, str(mo))
            lines.append(f"| {yr} | {mo_name} | {therms:,.0f} | {upc:.1f} |")

    by_enduse = results_df.groupby('end_use')['total_therms'].sum().sort_values(ascending=False)
    total = by_enduse.sum()
    lines += ["", "## End-Use Breakdown (All Years)", ""]
    lines.append("| End-Use | Total Therms | Share |")
    lines.append("|---------|-------------|-------|")
    for eu, therms in by_enduse.items():
        share = therms / total * 100 if total > 0 else 0
        lines.append(f"| {eu} | {therms:,.0f} | {share:.1f}% |")

    output_files = [
        "- `results.csv` — Full results (year x end-use)" + (" x month" if is_monthly else ""),
        "- `results.json` — Same data in JSON format",
        "- `yearly_summary.csv` — Year-by-year aggregated summary",
    ]
    if is_monthly:
        output_files.append("- `monthly_summary.csv` — Month-by-month aggregated summary")
        output_files.append("- `monthly_summary.json` — Same data in JSON format")
    output_files += [
        "- `metadata.json` — Scenario configuration and run metadata",
        f"- `{name}.json` — Input configuration (copy)",
        "- `SUMMARY.md` — This file",
    ]
    lines += ["", "## Output Files", ""] + output_files

    with open(scenario_dir / 'SUMMARY.md', 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    logger.info(f"Wrote summary: {scenario_dir / 'SUMMARY.md'}")


def main():
    """
    Main CLI entry point.
    
    Parses arguments, loads data, runs scenario(s), and exports results.
    """
    parser = argparse.ArgumentParser(
        description='NW Natural End-Use Forecasting Model - CLI Entry Point',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run single scenario
  python -m src.main scenarios/baseline.json

  # Run scenario with custom output directory
  python -m src.main scenarios/baseline.json --output-dir output/my_run

  # Run baseline-only (skip comparison)
  python -m src.main scenarios/baseline.json --baseline-only

  # Compare two scenarios
  python -m src.main scenarios/baseline.json scenarios/high_electrification.json --compare
        """
    )
    
    parser.add_argument(
        'scenario_configs',
        nargs='+',
        help='Path(s) to scenario JSON config file(s)'
    )
    
    parser.add_argument(
        '--output-dir',
        default=OUTPUT_DIR,
        help=f'Output directory for results (default: {OUTPUT_DIR})'
    )
    
    parser.add_argument(
        '--baseline-only',
        action='store_true',
        help='Run only the first scenario (baseline), skip comparison'
    )
    
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare multiple scenarios (requires 2+ scenario configs)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Load pipeline data once
        logger.info("Initializing pipeline...")
        premise_equipment, weather_data, water_temp_data, baseload_factors, census, recs_trend, recs_ratios, b25024_trend, segment_shift_rates = load_pipeline_data()
        
        # Load scenario configs
        logger.info(f"Loading {len(args.scenario_configs)} scenario config(s)...")
        configs = [load_scenario_config(path) for path in args.scenario_configs]
        
        # Run scenarios — each gets its own folder under scenarios/{name}/
        scenario_results = []
        for i, config in enumerate(configs):
            config_path = Path(args.scenario_configs[i])
            
            # Output folder: scenarios/{scenario_name}/ (next to the .json config)
            scenario_dir = config_path.parent / config.name
            scenario_dir.mkdir(parents=True, exist_ok=True)
            
            results_df, metadata = run_single_scenario(
                config,
                premise_equipment,
                weather_data,
                water_temp_data,
                baseload_factors,
                output_dir=str(scenario_dir),
                non_heating_ratios=recs_ratios if config.use_recs_ratios else None
            )
            scenario_results.append((results_df, metadata))
            
            # Print summary for this scenario
            print_summary_statistics(results_df, metadata)
            
            # --- Export all results into scenarios/{name}/ ---
            
            # 1. Copy the input config into the results folder
            import shutil
            shutil.copy2(str(config_path), str(scenario_dir / config_path.name))
            
            # 2. Main results CSV
            export_results(results_df, str(scenario_dir / 'results.csv'), format='csv')
            
            # 3. Results as JSON
            export_results(results_df, str(scenario_dir / 'results.json'), format='json')
            
            # 4. Year-by-year summary CSV (always annual, regardless of temporal_resolution)
            is_monthly_run = config.temporal_resolution == 'monthly' and 'month' in results_df.columns
            agg_cols = {'total_therms': 'sum', 'premise_count': 'first'}
            if 'irp_upc_therms' in results_df.columns:
                agg_cols['irp_upc_therms'] = 'first'
            # Aggregate months → year before computing yearly summary
            by_year = results_df.groupby('year').agg(agg_cols).reset_index()
            by_year['use_per_customer'] = by_year['total_therms'] / by_year['premise_count'].clip(lower=1)
            by_year['scenario_name'] = config.name
            export_results(by_year, str(scenario_dir / 'yearly_summary.csv'), format='csv')

            # 4b. Monthly summary CSV (only when temporal_resolution == 'monthly')
            if is_monthly_run:
                month_agg_cols = {'total_therms': 'sum', 'premise_count': 'first'}
                if 'irp_upc_therms' in results_df.columns:
                    month_agg_cols['irp_upc_therms'] = 'first'
                by_month = results_df.groupby(['year', 'month']).agg(month_agg_cols).reset_index()
                by_month['use_per_customer'] = by_month['total_therms'] / by_month['premise_count'].clip(lower=1)
                by_month['scenario_name'] = config.name
                month_names = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
                               7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}
                by_month['month_name'] = by_month['month'].map(month_names)
                export_results(by_month, str(scenario_dir / 'monthly_summary.csv'), format='csv')
                export_results(by_month, str(scenario_dir / 'monthly_summary.json'), format='json')
                logger.info(f"Wrote monthly_summary.csv: {len(by_month)} rows")
            
            # 5. Metadata JSON (strip internal DataFrames)
            import json as json_mod
            meta_clean = {k: v for k, v in metadata.items() if not k.startswith('_')}
            with open(scenario_dir / 'metadata.json', 'w') as f:
                json_mod.dump(meta_clean, f, indent=2, default=str)
            
            # 6. Summary text report
            _write_summary_report(scenario_dir, results_df, metadata, by_year)
            
            # 7. Equipment stats over time (gas vs electric, efficiency, replacements)
            equip_stats = metadata.get('_equipment_stats')
            if equip_stats is not None and not equip_stats.empty:
                export_results(equip_stats, str(scenario_dir / 'equipment_stats.csv'), format='csv')
                export_results(equip_stats, str(scenario_dir / 'equipment_stats.json'), format='json')
            
            # 8. Per-premise therms distribution by year (for histogram/box plot)
            premise_dist = metadata.get('_premise_distributions')
            if premise_dist is not None and not premise_dist.empty:
                export_results(premise_dist, str(scenario_dir / 'premise_distribution.csv'), format='csv')
                export_results(premise_dist, str(scenario_dir / 'premise_distribution.json'), format='json')
            
            # 9. Demand by segment over time
            seg_demand = metadata.get('_segment_demand')
            if seg_demand is not None and not seg_demand.empty:
                export_results(seg_demand, str(scenario_dir / 'segment_demand.csv'), format='csv')
                export_results(seg_demand, str(scenario_dir / 'segment_demand.json'), format='json')
            
            # 9b. Sample-derived yearly rates (replacement, efficiency, electrification)
            sample_rates = metadata.get('_sample_rates')
            if sample_rates is not None and not sample_rates.empty:
                export_results(sample_rates, str(scenario_dir / 'sample_rates.csv'), format='csv')
                export_results(sample_rates, str(scenario_dir / 'sample_rates.json'), format='json')
            
            # 9b2. Vintage demand breakdown
            vintage_demand = metadata.get('_vintage_demand')
            if vintage_demand is not None and not vintage_demand.empty:
                export_results(vintage_demand, str(scenario_dir / 'vintage_demand.csv'), format='csv')
                export_results(vintage_demand, str(scenario_dir / 'vintage_demand.json'), format='json')
            
            # 9c. Estimated total UPC with end-use breakdown
            est_total = metadata.get('_estimated_total')
            if est_total is not None and not est_total.empty:
                export_results(est_total, str(scenario_dir / 'estimated_total_upc.csv'), format='csv')
                export_results(est_total, str(scenario_dir / 'estimated_total_upc.json'), format='json')
            
            # 9d. HDD info and history
            hdd_info = metadata.get('_hdd_info')
            if hdd_info:
                pd.DataFrame([hdd_info]).to_csv(scenario_dir / 'hdd_info.csv', index=False)
            hdd_history = metadata.get('_hdd_history')
            if hdd_history is not None and not hdd_history.empty:
                export_results(hdd_history, str(scenario_dir / 'hdd_history.csv'), format='csv')
            
            # 10. IRP comparison (model vs NW Natural forecast)
            if 'irp_upc_therms' in results_df.columns and results_df['irp_upc_therms'].notna().any():
                # Always annual — sum months first if monthly resolution
                irp_agg_cols = {'total_therms': 'sum', 'premise_count': 'first', 'irp_upc_therms': 'first'}
                irp_by_year = results_df.groupby('year').agg(irp_agg_cols).reset_index()
                irp_by_year['use_per_customer'] = irp_by_year['total_therms'] / irp_by_year['premise_count'].clip(lower=1)
                irp_compare = irp_by_year[['year', 'use_per_customer', 'irp_upc_therms', 'total_therms', 'premise_count']].copy()
                irp_compare.columns = ['year', 'model_upc', 'irp_upc', 'total_therms', 'premise_count']
                irp_compare['model_upc_label'] = 'space_heating_only'
                # Add estimated total UPC if available
                est_total = metadata.get('_estimated_total')
                if est_total is not None and not est_total.empty and 'estimated_total_upc' in est_total.columns:
                    irp_compare = irp_compare.merge(
                        est_total[['year', 'estimated_total_upc']],
                        on='year', how='left'
                    )
                irp_compare['diff_therms'] = irp_compare['model_upc'] - irp_compare['irp_upc']
                irp_compare['diff_pct'] = (irp_compare['diff_therms'] / irp_compare['irp_upc'] * 100).round(1)
                export_results(irp_compare, str(scenario_dir / 'irp_comparison.csv'), format='csv')
                export_results(irp_compare, str(scenario_dir / 'irp_comparison.json'), format='json')
            
            # 11. Housing stock projection with segment breakdown (using B25024 shift)
            equip_stats_df = metadata.get('_equipment_stats', pd.DataFrame())
            seg_demand_df = metadata.get('_segment_demand', pd.DataFrame())
            
            # Get base year segment counts from segment_demand
            base_seg_counts = {}
            if not seg_demand_df.empty:
                base_yr_seg = seg_demand_df[seg_demand_df['year'] == config.base_year]
                for _, r in base_yr_seg.iterrows():
                    base_seg_counts[r['segment']] = int(r['equipment_count'])
            
            base_total = equip_stats_df.iloc[0]['total_premises'] if not equip_stats_df.empty else 0
            
            # Compute base year SF/MF shares for shift projection
            base_seg_total = sum(base_seg_counts.values()) if base_seg_counts else 1
            base_sf_pct = base_seg_counts.get('RESSF', 0) / base_seg_total * 100 if base_seg_total > 0 else 76.0
            base_mf_pct = base_seg_counts.get('RESMF', 0) / base_seg_total * 100 if base_seg_total > 0 else 24.0
            
            # Project segment shares using B25024 historical shift rates
            seg_projection = project_segment_shares(
                base_sf_pct, base_mf_pct, segment_shift_rates, config.forecast_horizon
            )
            
            stock_rows = []
            for yr_off in range(config.forecast_horizon + 1):
                yr = config.base_year + yr_off
                if yr_off == 0:
                    total = base_total
                else:
                    yr_growth = pc.resolve(config.housing_growth_rate, yr, 0.01)
                    total = int(round(base_total * ((1 + yr_growth) ** yr_off)))
                
                row = {'year': yr, 'total_units': total}
                # Use projected segment shares (shifting over time)
                if not seg_projection.empty and base_seg_counts:
                    proj_row = seg_projection[seg_projection['year_offset'] == yr_off].iloc[0]
                    row['RESSF'] = int(round(total * proj_row['sf_pct'] / 100))
                    row['RESMF'] = int(round(total * proj_row['mf_pct'] / 100))
                elif base_seg_counts and base_total > 0:
                    # Fallback: flat proportional
                    for seg, base_count in base_seg_counts.items():
                        proportion = base_count / base_seg_total
                        row[seg] = int(round(total * proportion))
                
                stock_rows.append(row)
            
            stock_df = pd.DataFrame(stock_rows)
            stock_df['growth_rate'] = config.housing_growth_rate
            stock_df['scenario_name'] = config.name
            export_results(stock_df, str(scenario_dir / 'housing_stock.csv'), format='csv')
            
            # 12b. Census ACS summary CSVs
            if census:
                export_census_summary(census, str(scenario_dir))
                logger.info(f"Exported Census ACS summary to {scenario_dir}")
            
            # 12c. Census vs Model housing comparison CSV
            if census and census.get('heating_fuel_trend'):
                trend = census['heating_fuel_trend']
                comp_rows = []
                # Historical Census data (B25040 total housing units + gas share)
                for yr, data in sorted(trend.items()):
                    census_total = data['total']
                    census_gas = int(round(census_total * data['gas_pct'] / 100.0))
                    comp_rows.append({
                        'year': yr,
                        'source': 'census',
                        'census_total_units': census_total,
                        'census_gas_units': census_gas,
                        'census_gas_pct': data['gas_pct'],
                        'model_total_units': None,
                    })
                # Model projection (from housing_stock.csv we just built)
                for _, row in stock_df.iterrows():
                    yr = int(row['year'])
                    model_total = int(row['total_units'])
                    # Estimate territory total from model using initial_gas_pct
                    territory_total = int(round(model_total / (config.initial_gas_pct / 100.0))) if config.initial_gas_pct > 0 else model_total
                    comp_rows.append({
                        'year': yr,
                        'source': 'model',
                        'census_total_units': None,
                        'census_gas_units': None,
                        'census_gas_pct': None,
                        'model_total_units': model_total,
                        'model_territory_total': territory_total,
                    })
                comp_df = pd.DataFrame(comp_rows)
                export_results(comp_df, str(scenario_dir / 'census_vs_model_housing.csv'), format='csv')
                export_results(comp_df, str(scenario_dir / 'census_vs_model_housing.json'), format='json')
            
            # 12d. RECS end-use trend and non-heating ratios
            if not recs_trend.empty:
                export_recs_summary(recs_trend, recs_ratios, str(scenario_dir))
                logger.info(f"Exported RECS end-use trend to {scenario_dir}")
            
            # 12e. B25024 segment trend and shift rates
            if not b25024_trend.empty:
                export_results(b25024_trend, str(scenario_dir / 'census_b25024_segment_trend.csv'), format='csv')
                export_results(b25024_trend, str(scenario_dir / 'census_b25024_segment_trend.json'), format='json')
                pd.DataFrame([segment_shift_rates]).to_csv(scenario_dir / 'census_segment_shift_rates.csv', index=False)
            
            # 12f. Envelope efficiency projection
            vintage_counts_for_env = {}
            vd = metadata.get('_vintage_demand', pd.DataFrame())
            if not vd.empty:
                base_vd = vd[vd['year'] == config.base_year]
                for _, r in base_vd.iterrows():
                    vintage_counts_for_env[r['vintage_era']] = int(r['equipment_count'])
            if vintage_counts_for_env:
                env_trend = project_envelope_trend(
                    config.base_year, config.forecast_horizon,
                    vintage_counts_for_env, config.segment_heating_multipliers,
                    config.housing_growth_rate, config.demolition_rate
                )
                export_results(env_trend, str(scenario_dir / 'envelope_efficiency.csv'), format='csv')
                export_results(env_trend, str(scenario_dir / 'envelope_efficiency.json'), format='json')
            
            # 13. Generate charts from the CSV outputs (before billing load which is slow)
            generate_scenario_charts(scenario_dir)
            
            # 12. Observed billing UPC by year (for three-way comparison chart)
            # NOTE: This loads 48M billing records (~90s). Done last to avoid blocking other exports.
            try:
                from src.calibration import load_annual_billing_therms
                annual_billing = load_annual_billing_therms()
                obs_upc = annual_billing.groupby('year')['annual_therms'].agg(['mean', 'median', 'count']).reset_index()
                obs_upc.columns = ['year', 'mean_upc', 'median_upc', 'premise_count']
                obs_upc = obs_upc[(obs_upc['year'] >= 2009) & (obs_upc['year'] <= 2025)]
                export_results(obs_upc, str(scenario_dir / 'observed_billing_upc.csv'), format='csv')
            except Exception as e:
                logger.warning(f"Could not generate observed billing UPC: {e}")
            
            logger.info(f"All results saved to: {scenario_dir}/")
        
        # Compare scenarios if requested and multiple scenarios provided
        if args.compare and len(scenario_results) > 1:
            logger.info(f"Comparing {len(scenario_results)} scenarios...")
            comparison_df = compare_scenarios(scenario_results)
            
            # Save comparison in the scenarios/ parent folder
            scenarios_parent = Path(args.scenario_configs[0]).parent
            comparison_dir = scenarios_parent / '_comparison'
            comparison_dir.mkdir(parents=True, exist_ok=True)
            export_results(comparison_df, str(comparison_dir / 'comparison_results.csv'), format='csv')
            logger.info(f"Exported comparison results: {comparison_dir}")
            
            print("\n" + "="*70)
            print("SCENARIO COMPARISON")
            print("="*70)
            print(f"\nScenarios compared: {', '.join([m['scenario_name'] for _, m in scenario_results])}")
            print(f"Years: {comparison_df['year'].min()}-{comparison_df['year'].max()}")
            print(f"\nResults saved to: {comparison_dir}/")
            print("="*70 + "\n")
        
        elif args.baseline_only:
            logger.info("Baseline-only mode: skipping comparison")
        
        elif len(scenario_results) > 1 and not args.compare:
            logger.warning(
                f"Multiple scenarios provided ({len(scenario_results)}) but --compare not specified. "
                "Use --compare to generate comparison results."
            )
        
        logger.info("Pipeline execution completed successfully")
        return 0
    
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
