"""
Aggregation and output module for NW Natural End-Use Forecasting Model.

Provides functions for rolling up premise-level simulation results to
system-level totals by end-use, customer segment, and district.
Includes comparison to NW Natural's IRP forecast and export functions.

Functions:
- aggregate_by_end_use: Sum demand across all premises by end-use
- aggregate_by_segment: Sum demand by customer segment (RESSF, RESMF, MOBILE)
- aggregate_by_district: Sum demand by geographic district
- compute_use_per_customer: Calculate UPC (therms/customer/year)
- compare_to_irp_forecast: Compare model UPC to IRP forecast
- export_results: Export aggregated results to CSV/JSON
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import logging
import json
from pathlib import Path

from src import config

logger = logging.getLogger(__name__)


def aggregate_by_end_use(
    simulation_results: pd.DataFrame
) -> pd.DataFrame:
    """
    Aggregate simulation results by end-use category.
    
    Sums annual therms across all premises for each end-use, producing
    system-level demand by end-use.
    
    Args:
        simulation_results: DataFrame with columns:
            - blinded_id: Premise identifier
            - end_use: End-use category (space_heating, water_heating, etc.)
            - annual_therms: Annual consumption (therms)
            - year: Simulation year
    
    Returns:
        DataFrame with columns:
            - end_use: End-use category
            - total_therms: Total demand across all premises (therms)
            - year: Simulation year
            - premise_count: Number of premises with this end-use
        
        Sorted by year, then end_use.
    
    Raises:
        ValueError: If required columns missing
    """
    required_cols = {'end_use', 'annual_therms', 'year'}
    if not required_cols.issubset(simulation_results.columns):
        missing = required_cols - set(simulation_results.columns)
        raise ValueError(f"simulation_results missing columns: {missing}")
    
    # Group by end_use and year, sum therms
    agg = simulation_results.groupby(['year', 'end_use']).agg({
        'annual_therms': 'sum',
        'blinded_id': 'nunique'
    }).reset_index()
    
    agg.columns = ['year', 'end_use', 'total_therms', 'premise_count']
    
    # Sort by year, then end_use
    agg = agg.sort_values(['year', 'end_use']).reset_index(drop=True)
    
    logger.info(
        f"Aggregated by end-use: {len(agg)} rows, "
        f"total demand {agg['total_therms'].sum():.0f} therms"
    )
    
    return agg


def aggregate_by_segment(
    simulation_results: pd.DataFrame,
    segments: pd.DataFrame
) -> pd.DataFrame:
    """
    Aggregate simulation results by customer segment.
    
    Joins simulation results with segment data (RESSF, RESMF, MOBILE)
    and sums demand by segment and end-use.
    
    Args:
        simulation_results: DataFrame with columns:
            - blinded_id: Premise identifier
            - end_use: End-use category
            - annual_therms: Annual consumption (therms)
            - year: Simulation year
        
        segments: DataFrame with columns:
            - blinded_id: Premise identifier
            - segment_code: Segment code (RESSF, RESMF, MOBILE, etc.)
    
    Returns:
        DataFrame with columns:
            - year: Simulation year
            - segment_code: Customer segment
            - end_use: End-use category
            - total_therms: Total demand (therms)
            - premise_count: Number of premises in segment with this end-use
        
        Sorted by year, segment_code, end_use.
    
    Raises:
        ValueError: If required columns missing
    """
    required_sim_cols = {'blinded_id', 'end_use', 'annual_therms', 'year'}
    if not required_sim_cols.issubset(simulation_results.columns):
        missing = required_sim_cols - set(simulation_results.columns)
        raise ValueError(f"simulation_results missing columns: {missing}")
    
    required_seg_cols = {'blinded_id', 'segment_code'}
    if not required_seg_cols.issubset(segments.columns):
        missing = required_seg_cols - set(segments.columns)
        raise ValueError(f"segments missing columns: {missing}")
    
    # Join simulation results with segments
    merged = simulation_results.merge(
        segments[['blinded_id', 'segment_code']],
        on='blinded_id',
        how='left'
    )
    
    # Group by year, segment_code, end_use
    agg = merged.groupby(['year', 'segment_code', 'end_use']).agg({
        'annual_therms': 'sum',
        'blinded_id': 'nunique'
    }).reset_index()
    
    agg.columns = ['year', 'segment_code', 'end_use', 'total_therms', 'premise_count']
    
    # Sort by year, segment_code, end_use
    agg = agg.sort_values(['year', 'segment_code', 'end_use']).reset_index(drop=True)
    
    logger.info(
        f"Aggregated by segment: {len(agg)} rows, "
        f"segments: {agg['segment_code'].nunique()}"
    )
    
    return agg


def aggregate_by_district(
    simulation_results: pd.DataFrame,
    premises: pd.DataFrame
) -> pd.DataFrame:
    """
    Aggregate simulation results by geographic district.
    
    Joins simulation results with premise data (district_code_IRP)
    and sums demand by district and end-use.
    
    Args:
        simulation_results: DataFrame with columns:
            - blinded_id: Premise identifier
            - end_use: End-use category
            - annual_therms: Annual consumption (therms)
            - year: Simulation year
        
        premises: DataFrame with columns:
            - blinded_id: Premise identifier
            - district_code_IRP: District code
    
    Returns:
        DataFrame with columns:
            - year: Simulation year
            - district_code_IRP: District code
            - end_use: End-use category
            - total_therms: Total demand (therms)
            - premise_count: Number of premises in district with this end-use
        
        Sorted by year, district_code_IRP, end_use.
    
    Raises:
        ValueError: If required columns missing
    """
    required_sim_cols = {'blinded_id', 'end_use', 'annual_therms', 'year'}
    if not required_sim_cols.issubset(simulation_results.columns):
        missing = required_sim_cols - set(simulation_results.columns)
        raise ValueError(f"simulation_results missing columns: {missing}")
    
    required_prem_cols = {'blinded_id', 'district_code_IRP'}
    if not required_prem_cols.issubset(premises.columns):
        missing = required_prem_cols - set(premises.columns)
        raise ValueError(f"premises missing columns: {missing}")
    
    # Join simulation results with premises
    merged = simulation_results.merge(
        premises[['blinded_id', 'district_code_IRP']],
        on='blinded_id',
        how='left'
    )
    
    # Group by year, district_code_IRP, end_use
    agg = merged.groupby(['year', 'district_code_IRP', 'end_use']).agg({
        'annual_therms': 'sum',
        'blinded_id': 'nunique'
    }).reset_index()
    
    agg.columns = ['year', 'district_code_IRP', 'end_use', 'total_therms', 'premise_count']
    
    # Sort by year, district_code_IRP, end_use
    agg = agg.sort_values(['year', 'district_code_IRP', 'end_use']).reset_index(drop=True)
    
    logger.info(
        f"Aggregated by district: {len(agg)} rows, "
        f"districts: {agg['district_code_IRP'].nunique()}"
    )
    
    return agg


def compute_use_per_customer(
    total_demand: pd.DataFrame,
    customer_count: pd.DataFrame
) -> pd.DataFrame:
    """
    Compute Use Per Customer (UPC) from total demand and customer counts.
    
    UPC = total_therms / customer_count for each year and segment.
    Handles division by zero by returning NaN for zero customer counts.
    
    Args:
        total_demand: DataFrame with columns:
            - year: Simulation year
            - segment_code (optional): Customer segment
            - total_therms: Total demand (therms)
        
        customer_count: DataFrame with columns:
            - year: Simulation year
            - segment_code (optional): Customer segment
            - customer_count: Number of customers
    
    Returns:
        DataFrame with columns:
            - year: Simulation year
            - segment_code (optional): Customer segment
            - total_therms: Total demand (therms)
            - customer_count: Number of customers
            - use_per_customer: UPC (therms/customer/year)
        
        Rows with customer_count == 0 have use_per_customer = NaN.
    
    Raises:
        ValueError: If required columns missing
    """
    required_demand_cols = {'year', 'total_therms'}
    if not required_demand_cols.issubset(total_demand.columns):
        missing = required_demand_cols - set(total_demand.columns)
        raise ValueError(f"total_demand missing columns: {missing}")
    
    required_count_cols = {'year', 'customer_count'}
    if not required_count_cols.issubset(customer_count.columns):
        missing = required_count_cols - set(customer_count.columns)
        raise ValueError(f"customer_count missing columns: {missing}")
    
    # Merge on year (and segment_code if present)
    merge_cols = ['year']
    if 'segment_code' in total_demand.columns and 'segment_code' in customer_count.columns:
        merge_cols.append('segment_code')
    
    merged = total_demand.merge(customer_count, on=merge_cols, how='left')
    
    # Compute UPC: therms / customer_count
    # Handle division by zero: customer_count == 0 -> UPC = NaN
    merged['use_per_customer'] = np.where(
        merged['customer_count'] > 0,
        merged['total_therms'] / merged['customer_count'],
        np.nan
    )
    
    logger.info(
        f"Computed UPC: {len(merged)} rows, "
        f"mean UPC {merged['use_per_customer'].mean():.1f} therms/customer"
    )
    
    return merged


def compare_to_irp_forecast(
    model_upc: pd.DataFrame,
    irp_forecast: pd.DataFrame
) -> pd.DataFrame:
    """
    Compare model UPC to NW Natural's IRP forecast.
    
    Joins model UPC with IRP forecast data and computes differences
    and percent deviations.
    
    Args:
        model_upc: DataFrame with columns:
            - year: Simulation year
            - use_per_customer: Model UPC (therms/customer/year)
        
        irp_forecast: DataFrame with columns:
            - year: Forecast year
            - upc: IRP forecast UPC (therms/customer/year)
    
    Returns:
        DataFrame with columns:
            - year: Year
            - model_upc: Model UPC (therms/customer/year)
            - irp_upc: IRP forecast UPC (therms/customer/year)
            - difference: model_upc - irp_upc (therms/customer)
            - percent_deviation: (model_upc - irp_upc) / irp_upc * 100 (%)
        
        Sorted by year.
        Rows with missing IRP data are included with NaN values.
    
    Raises:
        ValueError: If required columns missing
    """
    required_model_cols = {'year', 'use_per_customer'}
    if not required_model_cols.issubset(model_upc.columns):
        missing = required_model_cols - set(model_upc.columns)
        raise ValueError(f"model_upc missing columns: {missing}")
    
    required_irp_cols = {'year', 'upc'}
    if not required_irp_cols.issubset(irp_forecast.columns):
        missing = required_irp_cols - set(irp_forecast.columns)
        raise ValueError(f"irp_forecast missing columns: {missing}")
    
    # Rename columns for clarity
    model_upc_renamed = model_upc[['year', 'use_per_customer']].copy()
    model_upc_renamed.columns = ['year', 'model_upc']
    
    irp_renamed = irp_forecast[['year', 'upc']].copy()
    irp_renamed.columns = ['year', 'irp_upc']
    
    # Merge on year (outer join to include all years)
    comparison = model_upc_renamed.merge(irp_renamed, on='year', how='outer')
    
    # Compute differences
    comparison['difference'] = comparison['model_upc'] - comparison['irp_upc']
    comparison['percent_deviation'] = np.where(
        comparison['irp_upc'] > 0,
        (comparison['model_upc'] - comparison['irp_upc']) / comparison['irp_upc'] * 100,
        np.nan
    )
    
    # Sort by year
    comparison = comparison.sort_values('year').reset_index(drop=True)
    
    logger.info(
        f"Compared to IRP forecast: {len(comparison)} years, "
        f"mean deviation {comparison['percent_deviation'].mean():.1f}%"
    )
    
    return comparison


def export_results(
    results: pd.DataFrame,
    output_path: str,
    format: str = 'csv'
) -> str:
    """
    Export aggregated results to file.
    
    Supports CSV and JSON formats. Creates output directory if needed.
    
    Args:
        results: DataFrame to export
        output_path: Path to output file (e.g., 'output/results.csv')
        format: Output format ('csv' or 'json', default 'csv')
    
    Returns:
        Path to exported file (str)
    
    Raises:
        ValueError: If format not supported
        IOError: If file write fails
    """
    if format not in ('csv', 'json'):
        raise ValueError(f"Unsupported format: {format}. Use 'csv' or 'json'.")
    
    # Create output directory if needed
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export based on format
    if format == 'csv':
        results.to_csv(output_path, index=False)
        logger.info(f"Exported {len(results)} rows to CSV: {output_path}")
    
    elif format == 'json':
        results.to_json(output_path, orient='records', indent=2)
        logger.info(f"Exported {len(results)} rows to JSON: {output_path}")
    
    return str(output_path)
