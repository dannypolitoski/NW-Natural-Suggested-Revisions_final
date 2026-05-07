"""
Range-checking and IRP comparison module for NW Natural End-Use Forecasting Model.

Implements validation by:
1. Flagging results outside expected ranges
2. Comparing model UPC vs IRP 10-year forecast
3. Comparing vintage-cohort UPC vs era anchors (820/720/650)
4. Logging and reporting discrepancies

Requirements: 10.1, 10.2, 10.3, 10.4
"""

import os
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import json
from datetime import datetime

from src.config import (
    OUTPUT_DIR, BASE_YEAR, IRP_LOAD_DECAY_FORECAST, NWN_DATA_DIR
)
from src.data_ingestion import load_load_decay_forecast, load_premise_data
from src.aggregation import compute_use_per_customer

logger = logging.getLogger(__name__)

# Expected ranges for validation
EXPECTED_RANGES = {
    'space_heating': (100, 800),      # therms/customer/year
    'water_heating': (50, 200),       # therms/customer/year
    'cooking': (10, 50),              # therms/customer/year
    'drying': (10, 50),               # therms/customer/year
    'fireplace': (0, 100),            # therms/customer/year
    'other': (0, 50),                 # therms/customer/year
}

# Era anchors from IRP load decay data
ERA_ANCHORS = {
    'pre_2010': 820,      # therms/customer/year
    '2011_2019': 720,     # therms/customer/year
    '2020_plus': 650,     # therms/customer/year
}


def load_irp_forecast() -> pd.DataFrame:
    """
    Load NW Natural IRP 10-year forecast.
    
    Returns:
        DataFrame with columns:
            - year: Forecast year (from Year column)
            - upc: Use Per Customer (therms/customer/year, from Avg_Res_UPC_Therms)
    """
    logger.info("Loading IRP forecast...")
    
    try:
        irp = load_load_decay_forecast(IRP_LOAD_DECAY_FORECAST)
        
        # Rename columns to standard names
        if 'Year' in irp.columns:
            irp = irp.rename(columns={'Year': 'year'})
        if 'Avg_Res_UPC_Therms' in irp.columns:
            irp = irp.rename(columns={'Avg_Res_UPC_Therms': 'upc'})
        
        # Keep only year and upc columns
        irp = irp[['year', 'upc']].copy()
        
        logger.info(f"Loaded IRP forecast: {len(irp)} years")
        return irp
    except Exception as e:
        logger.warning(f"Failed to load IRP forecast: {e}")
        return pd.DataFrame()


def check_range_violations(
    simulation_results: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Flag results outside expected ranges.
    
    Args:
        simulation_results: Simulation results with columns:
            - end_use: End-use category
            - annual_therms: Annual consumption (therms)
            - blinded_id: Premise identifier
    
    Returns:
        Tuple of (violations_df, summary_dict)
        
        violations_df columns:
            - blinded_id: Premise identifier
            - end_use: End-use category
            - annual_therms: Annual consumption
            - expected_min: Expected minimum
            - expected_max: Expected maximum
            - violation_type: 'below_min' or 'above_max'
            - severity: 'warning' or 'critical'
        
        summary_dict keys:
            - total_violations: Total number of violations
            - by_end_use: Dict of violations by end-use
            - critical_count: Number of critical violations
    """
    logger.info("Checking range violations...")
    
    violations = []
    
    for end_use, (min_val, max_val) in EXPECTED_RANGES.items():
        end_use_data = simulation_results[
            simulation_results['end_use'] == end_use
        ].copy()
        
        # Check below minimum
        below_min = end_use_data[end_use_data['annual_therms'] < min_val].copy()
        below_min['expected_min'] = min_val
        below_min['expected_max'] = max_val
        below_min['violation_type'] = 'below_min'
        below_min['severity'] = 'warning'
        violations.append(below_min)
        
        # Check above maximum
        above_max = end_use_data[end_use_data['annual_therms'] > max_val].copy()
        above_max['expected_min'] = min_val
        above_max['expected_max'] = max_val
        above_max['violation_type'] = 'above_max'
        # Mark as critical if significantly above max (>150%)
        above_max['severity'] = np.where(
            above_max['annual_therms'] > max_val * 1.5,
            'critical',
            'warning'
        )
        violations.append(above_max)
    
    if violations:
        violations_df = pd.concat(violations, ignore_index=True)
        violations_df = violations_df[[
            'blinded_id', 'end_use', 'annual_therms', 'expected_min',
            'expected_max', 'violation_type', 'severity'
        ]].sort_values('annual_therms', ascending=False)
    else:
        violations_df = pd.DataFrame()
    
    # Summary
    summary = {
        'total_violations': int(len(violations_df)),
        'by_end_use': {k: int(v) for k, v in violations_df['end_use'].value_counts().to_dict().items()} if len(violations_df) > 0 else {},
        'critical_count': int((violations_df['severity'] == 'critical').sum()) if len(violations_df) > 0 else 0
    }
    
    logger.info(
        f"Found {summary['total_violations']} range violations, "
        f"{summary['critical_count']} critical"
    )
    
    return violations_df, summary


def compare_model_vs_irp_upc(
    model_results: pd.DataFrame,
    irp_forecast: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Compare model UPC vs IRP 10-year forecast.
    
    Args:
        model_results: Aggregated model results with columns:
            - year: Simulation year
            - total_therms: Total demand (therms)
            - customer_count: Number of customers
        
        irp_forecast: IRP forecast with columns:
            - year: Forecast year
            - upc: IRP UPC (therms/customer/year)
    
    Returns:
        Tuple of (comparison_df, metrics_dict)
        
        comparison_df columns:
            - year: Year
            - model_upc: Model UPC (therms/customer/year)
            - irp_upc: IRP UPC (therms/customer/year)
            - difference: model_upc - irp_upc
            - percent_deviation: (model_upc - irp_upc) / irp_upc * 100
            - flag: 'OK', 'WARNING', or 'CRITICAL'
        
        metrics_dict keys:
            - mean_deviation_percent: Mean percent deviation
            - max_deviation_percent: Maximum percent deviation
            - rmse: Root Mean Squared Error
            - years_within_5_percent: Number of years within 5% of IRP
    """
    logger.info("Comparing model UPC vs IRP forecast...")
    
    # Compute model UPC
    model_upc = model_results.groupby('year').agg({
        'total_therms': 'sum',
        'customer_count': 'sum'
    }).reset_index()
    
    model_upc['upc'] = np.where(
        model_upc['customer_count'] > 0,
        model_upc['total_therms'] / model_upc['customer_count'],
        np.nan
    )
    
    # Merge with IRP forecast
    comparison = model_upc[['year', 'upc']].copy()
    comparison.columns = ['year', 'model_upc']
    
    comparison = comparison.merge(
        irp_forecast[['year', 'upc']].copy().rename(columns={'upc': 'irp_upc'}),
        on='year',
        how='outer'
    )
    
    # Compute differences
    comparison['difference'] = comparison['model_upc'] - comparison['irp_upc']
    comparison['percent_deviation'] = np.where(
        comparison['irp_upc'] > 0,
        (comparison['model_upc'] - comparison['irp_upc']) / comparison['irp_upc'] * 100,
        np.nan
    )
    
    # Flag based on deviation
    comparison['flag'] = 'OK'
    comparison.loc[
        np.abs(comparison['percent_deviation']) > 10, 'flag'
    ] = 'WARNING'
    comparison.loc[
        np.abs(comparison['percent_deviation']) > 20, 'flag'
    ] = 'CRITICAL'
    
    # Metrics
    valid_rows = comparison.dropna(subset=['percent_deviation'])
    
    metrics = {
        'mean_deviation_percent': float(valid_rows['percent_deviation'].mean()) if len(valid_rows) > 0 else np.nan,
        'max_deviation_percent': float(np.abs(valid_rows['percent_deviation']).max()) if len(valid_rows) > 0 else np.nan,
        'rmse': float(np.sqrt((valid_rows['difference'] ** 2).mean())) if len(valid_rows) > 0 else np.nan,
        'years_within_5_percent': int((np.abs(valid_rows['percent_deviation']) <= 5).sum()) if len(valid_rows) > 0 else 0,
        'total_years': len(valid_rows)
    }
    
    logger.info(
        f"Model vs IRP: mean deviation {metrics['mean_deviation_percent']:.1f}%, "
        f"max deviation {metrics['max_deviation_percent']:.1f}%"
    )
    
    return comparison, metrics


def compare_vintage_cohort_upc(
    simulation_results: pd.DataFrame,
    premises: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Compare vintage-cohort UPC vs era anchors (820/720/650).
    
    Args:
        simulation_results: Simulation results with columns:
            - blinded_id: Premise identifier
            - annual_therms: Annual consumption
        
        premises: Premise data with columns:
            - blinded_id: Premise identifier
            - vintage_year or construction_year: Year built
    
    Returns:
        Tuple of (comparison_df, metrics_dict)
        
        comparison_df columns:
            - era: Era (pre_2010, 2011_2019, 2020_plus)
            - model_upc: Model UPC for era
            - anchor_upc: Era anchor UPC
            - difference: model_upc - anchor_upc
            - percent_deviation: (model_upc - anchor_upc) / anchor_upc * 100
            - premise_count: Number of premises in era
        
        metrics_dict keys:
            - pre_2010_deviation: Percent deviation for pre-2010 era
            - 2011_2019_deviation: Percent deviation for 2011-2019 era
            - 2020_plus_deviation: Percent deviation for 2020+ era
            - overall_rmse: Overall RMSE across eras
    """
    logger.info("Comparing vintage-cohort UPC vs era anchors...")
    
    # Aggregate simulation by premise
    sim_agg = simulation_results.groupby('blinded_id').agg({
        'annual_therms': 'sum'
    }).reset_index()
    
    # Merge with premises to get vintage
    merged = sim_agg.merge(
        premises[['blinded_id', 'vintage_year']],
        on='blinded_id',
        how='left'
    )
    
    # Assign to era
    def assign_era(year):
        if pd.isna(year):
            return None
        if year < 2010:
            return 'pre_2010'
        elif year < 2020:
            return '2011_2019'
        else:
            return '2020_plus'
    
    merged['era'] = merged['vintage_year'].apply(assign_era)
    
    # Compute UPC by era
    era_upc = merged.groupby('era').agg({
        'annual_therms': 'sum',
        'blinded_id': 'count'
    }).reset_index()
    
    era_upc.columns = ['era', 'total_therms', 'premise_count']
    era_upc['model_upc'] = era_upc['total_therms'] / era_upc['premise_count']
    
    # Add anchor values
    era_upc['anchor_upc'] = era_upc['era'].map(ERA_ANCHORS)
    
    # Compute differences
    era_upc['difference'] = era_upc['model_upc'] - era_upc['anchor_upc']
    era_upc['percent_deviation'] = np.where(
        era_upc['anchor_upc'] > 0,
        (era_upc['model_upc'] - era_upc['anchor_upc']) / era_upc['anchor_upc'] * 100,
        np.nan
    )
    
    # Metrics
    metrics = {}
    for _, row in era_upc.iterrows():
        era = row['era']
        metrics[f'{era}_deviation'] = float(row['percent_deviation']) if pd.notna(row['percent_deviation']) else np.nan
    
    # Overall RMSE
    valid_rows = era_upc.dropna(subset=['percent_deviation'])
    metrics['overall_rmse'] = float(np.sqrt((valid_rows['difference'] ** 2).mean())) if len(valid_rows) > 0 else np.nan
    
    logger.info(
        f"Vintage cohort comparison: "
        f"pre-2010 {metrics.get('pre_2010_deviation', np.nan):.1f}%, "
        f"2011-2019 {metrics.get('2011_2019_deviation', np.nan):.1f}%, "
        f"2020+ {metrics.get('2020_plus_deviation', np.nan):.1f}%"
    )
    
    return era_upc, metrics


def run_range_checking_and_irp_comparison(
    simulation_results: pd.DataFrame,
    model_results: pd.DataFrame,
    premises: pd.DataFrame,
    output_dir: str = OUTPUT_DIR
) -> Dict[str, any]:
    """
    Run complete range-checking and IRP comparison workflow.
    
    Args:
        simulation_results: Premise-level simulation results
        model_results: Aggregated model results
        premises: Premise data
        output_dir: Output directory for reports
    
    Returns:
        Dictionary with results:
            - range_violations: Range violations DataFrame
            - range_summary: Range violations summary
            - irp_comparison: IRP comparison DataFrame
            - irp_metrics: IRP comparison metrics
            - vintage_comparison: Vintage cohort comparison DataFrame
            - vintage_metrics: Vintage cohort metrics
            - report_path: Path to output directory
    """
    logger.info("Running range-checking and IRP comparison...")
    
    # Check range violations
    range_violations, range_summary = check_range_violations(simulation_results)
    
    # Load IRP forecast
    irp_forecast = load_irp_forecast()
    
    # Compare model vs IRP UPC
    if not irp_forecast.empty:
        irp_comparison, irp_metrics = compare_model_vs_irp_upc(model_results, irp_forecast)
    else:
        irp_comparison = pd.DataFrame()
        irp_metrics = {}
    
    # Compare vintage cohort UPC
    vintage_comparison, vintage_metrics = compare_vintage_cohort_upc(
        simulation_results, premises
    )
    
    # Save results
    output_path = Path(output_dir) / "validation"
    output_path.mkdir(parents=True, exist_ok=True)
    
    if not range_violations.empty:
        range_violations.to_csv(output_path / "range_violations.csv", index=False)
    
    with open(output_path / "range_violations_summary.json", 'w') as f:
        json.dump(range_summary, f, indent=2)
    
    if not irp_comparison.empty:
        irp_comparison.to_csv(output_path / "irp_comparison.csv", index=False)
    
    with open(output_path / "irp_metrics.json", 'w') as f:
        json.dump(irp_metrics, f, indent=2)
    
    if not vintage_comparison.empty:
        vintage_comparison.to_csv(output_path / "vintage_cohort_comparison.csv", index=False)
    
    with open(output_path / "vintage_metrics.json", 'w') as f:
        json.dump(vintage_metrics, f, indent=2)
    
    logger.info(f"Saved range-checking results to {output_path}")
    
    return {
        'range_violations': range_violations,
        'range_summary': range_summary,
        'irp_comparison': irp_comparison,
        'irp_metrics': irp_metrics,
        'vintage_comparison': vintage_comparison,
        'vintage_metrics': vintage_metrics,
        'report_path': str(output_path)
    }
