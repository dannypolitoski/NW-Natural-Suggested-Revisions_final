"""
Billing-based calibration module for NW Natural End-Use Forecasting Model.

Implements validation against billing data by:
1. Loading billing data and building historical rate table
2. Converting billing dollars to therms
3. Comparing simulated vs billing-derived therms per premise
4. Computing MAE, mean bias, R²
5. Flagging premises with divergence > threshold

Requirements: 7.1, 10.2, 10.3
"""

import os
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
from scipy import stats
import json

from src.config import (
    NWN_DATA_DIR, BILLING_DATA, OR_RATES, WA_RATES,
    OR_RATE_CASE_HISTORY, WA_RATE_CASE_HISTORY, OR_WACOG_HISTORY,
    WA_WACOG_HISTORY, OUTPUT_DIR, BASE_YEAR
)
from src.data_ingestion import (
    load_billing_data, load_or_rates, load_wa_rates,
    load_wacog_history, load_rate_case_history,
    build_historical_rate_table, convert_billing_to_therms,
    load_premise_data
)

logger = logging.getLogger(__name__)


def load_and_prepare_billing_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load billing data and build historical rate table.
    
    Returns:
        Tuple of (billing_df, rate_table_df)
        
        billing_df columns:
            - blinded_id: Premise identifier
            - utility_usage: Billing amount (dollars)
            - GL_revenue_date: Billing date
            - year: Extracted year
            - month: Extracted month
            - state: OR or WA
        
        rate_table_df columns:
            - year: Year
            - state: OR or WA
            - rate_per_therm: $/therm (base + WACOG)
    """
    logger.info("Loading billing data...")
    
    try:
        billing = load_billing_data(os.path.join(NWN_DATA_DIR, "billing_data_blinded.csv"))
    except Exception as e:
        logger.warning(f"Failed to load billing data: {e}")
        return pd.DataFrame(), pd.DataFrame()
    
    # Load rate data
    logger.info("Loading rate data...")
    try:
        or_rates = load_or_rates(OR_RATES)
        wa_rates = load_wa_rates(WA_RATES)
        or_wacog = load_wacog_history(OR_WACOG_HISTORY)
        wa_wacog = load_wacog_history(WA_WACOG_HISTORY)
        or_rate_cases = load_rate_case_history(OR_RATE_CASE_HISTORY)
        wa_rate_cases = load_rate_case_history(WA_RATE_CASE_HISTORY)
    except Exception as e:
        logger.warning(f"Failed to load rate data: {e}")
        return billing, pd.DataFrame()
    
    # Build historical rate tables
    logger.info("Building historical rate tables...")
    try:
        or_rate_table = build_historical_rate_table(
            or_rate_cases, or_wacog, or_rates, 'OR'
        )
        wa_rate_table = build_historical_rate_table(
            wa_rate_cases, wa_wacog, wa_rates, 'WA'
        )
        rate_table = pd.concat([or_rate_table, wa_rate_table], ignore_index=True)
    except Exception as e:
        logger.warning(f"Failed to build rate table: {e}")
        return billing, pd.DataFrame()
    
    logger.info(f"Loaded {len(billing)} billing records, {len(rate_table)} rate records")
    return billing, rate_table


def convert_billing_to_therms_per_premise(
    billing: pd.DataFrame,
    rate_table: pd.DataFrame,
    premises: pd.DataFrame
) -> pd.DataFrame:
    """
    Convert billing dollars to estimated therms per premise.
    
    Args:
        billing: Billing data with utility_usage (dollars) and year
        rate_table: Historical rate table with rate_per_therm by year/state
        premises: Premise data with state information
    
    Returns:
        DataFrame with columns:
            - blinded_id: Premise identifier
            - year: Billing year
            - billing_dollars: Total billing amount (dollars)
            - estimated_therms: Estimated therms (dollars / rate_per_therm)
            - rate_per_therm: Rate used for conversion
            - state: OR or WA
    """
    logger.info("Converting billing dollars to therms...")
    
    # Merge billing with premises to get state
    merged = billing.merge(
        premises[['blinded_id', 'state']],
        on='blinded_id',
        how='left'
    )
    
    # Merge with rate table
    merged = merged.merge(
        rate_table,
        on=['year', 'state'],
        how='left'
    )
    
    # Convert dollars to therms
    merged['estimated_therms'] = np.where(
        merged['rate_per_therm'] > 0,
        merged['utility_usage'] / merged['rate_per_therm'],
        np.nan
    )
    
    # Aggregate by premise and year (sum multiple billing periods)
    result = merged.groupby(['blinded_id', 'year', 'state']).agg({
        'utility_usage': 'sum',
        'estimated_therms': 'sum',
        'rate_per_therm': 'first'  # Use first rate (should be consistent)
    }).reset_index()
    
    result.columns = ['blinded_id', 'year', 'state', 'billing_dollars', 'estimated_therms', 'rate_per_therm']
    
    logger.info(f"Converted {len(result)} premise-year records to therms")
    return result


def compare_simulated_vs_billing(
    simulated: pd.DataFrame,
    billing_therms: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Compare simulated vs billing-derived therms per premise.
    
    Args:
        simulated: Simulation results with columns:
            - blinded_id: Premise identifier
            - year: Simulation year
            - annual_therms: Simulated annual therms
        
        billing_therms: Billing-derived therms with columns:
            - blinded_id: Premise identifier
            - year: Year
            - estimated_therms: Billing-derived therms
    
    Returns:
        Tuple of (comparison_df, metrics_dict)
        
        comparison_df columns:
            - blinded_id: Premise identifier
            - year: Year
            - simulated_therms: Simulated therms
            - billing_therms: Billing-derived therms
            - difference: simulated - billing (therms)
            - percent_error: (simulated - billing) / billing * 100 (%)
            - abs_percent_error: |percent_error|
        
        metrics_dict keys:
            - mae: Mean Absolute Error (therms)
            - mean_bias: Mean (simulated - billing) (therms)
            - rmse: Root Mean Squared Error (therms)
            - r_squared: R² correlation coefficient
            - num_premises: Number of premises compared
            - num_outliers: Premises with |percent_error| > 50%
    """
    logger.info("Comparing simulated vs billing-derived therms...")
    
    # Aggregate simulated by premise and year
    sim_agg = simulated.groupby(['blinded_id', 'year']).agg({
        'annual_therms': 'sum'
    }).reset_index()
    sim_agg.columns = ['blinded_id', 'year', 'simulated_therms']
    
    # Merge simulated with billing
    comparison = sim_agg.merge(
        billing_therms[['blinded_id', 'year', 'estimated_therms']],
        on=['blinded_id', 'year'],
        how='inner'
    )
    
    # Compute differences
    comparison['difference'] = comparison['simulated_therms'] - comparison['estimated_therms']
    comparison['percent_error'] = np.where(
        comparison['estimated_therms'] > 0,
        (comparison['simulated_therms'] - comparison['estimated_therms']) / comparison['estimated_therms'] * 100,
        np.nan
    )
    comparison['abs_percent_error'] = np.abs(comparison['percent_error'])
    
    # Compute metrics
    valid_rows = comparison.dropna(subset=['percent_error'])
    
    mae = np.abs(valid_rows['difference']).mean()
    mean_bias = valid_rows['difference'].mean()
    rmse = np.sqrt((valid_rows['difference'] ** 2).mean())
    
    # R² correlation
    if len(valid_rows) > 1:
        r_squared = stats.linregress(
            valid_rows['estimated_therms'],
            valid_rows['simulated_therms']
        ).rvalue ** 2
    else:
        r_squared = np.nan
    
    # Count outliers (|percent_error| > 50%)
    num_outliers = (comparison['abs_percent_error'] > 50).sum()
    
    metrics = {
        'mae': float(mae),
        'mean_bias': float(mean_bias),
        'rmse': float(rmse),
        'r_squared': float(r_squared),
        'num_premises': len(comparison),
        'num_outliers': int(num_outliers),
        'outlier_percent': float(num_outliers / len(comparison) * 100) if len(comparison) > 0 else 0
    }
    
    logger.info(
        f"Comparison metrics: MAE={mae:.1f} therms, "
        f"bias={mean_bias:.1f} therms, R²={r_squared:.3f}, "
        f"outliers={num_outliers}/{len(comparison)}"
    )
    
    return comparison, metrics


def flag_divergent_premises(
    comparison: pd.DataFrame,
    threshold_percent: float = 50.0
) -> pd.DataFrame:
    """
    Flag premises with divergence > threshold.
    
    Args:
        comparison: Comparison DataFrame from compare_simulated_vs_billing
        threshold_percent: Percent error threshold for flagging (default 50%)
    
    Returns:
        DataFrame with flagged premises:
            - blinded_id: Premise identifier
            - year: Year
            - simulated_therms: Simulated therms
            - billing_therms: Billing-derived therms
            - percent_error: Percent error
            - flag_reason: Reason for flag (e.g., "High divergence: 75% error")
    """
    logger.info(f"Flagging premises with divergence > {threshold_percent}%...")
    
    flagged = comparison[
        comparison['abs_percent_error'] > threshold_percent
    ].copy()
    
    flagged['flag_reason'] = flagged.apply(
        lambda row: f"High divergence: {row['abs_percent_error']:.1f}% error",
        axis=1
    )
    
    flagged = flagged[[
        'blinded_id', 'year', 'simulated_therms', 'estimated_therms',
        'percent_error', 'flag_reason'
    ]].sort_values('abs_percent_error', ascending=False)
    
    logger.info(f"Flagged {len(flagged)} premise-year records")
    return flagged


def run_billing_calibration(
    simulated: pd.DataFrame,
    premises: pd.DataFrame,
    output_dir: str = OUTPUT_DIR
) -> Dict[str, any]:
    """
    Run complete billing-based calibration workflow.
    
    Args:
        simulated: Simulation results DataFrame
        premises: Premise data DataFrame
        output_dir: Output directory for reports
    
    Returns:
        Dictionary with results:
            - comparison: Comparison DataFrame
            - metrics: Metrics dictionary
            - flagged: Flagged premises DataFrame
            - report_path: Path to HTML report
    """
    logger.info("Running billing-based calibration...")
    
    # Load and prepare billing data
    billing, rate_table = load_and_prepare_billing_data()
    
    if billing.empty or rate_table.empty:
        logger.warning("Billing or rate data unavailable, skipping calibration")
        return {
            'comparison': pd.DataFrame(),
            'metrics': {},
            'flagged': pd.DataFrame(),
            'report_path': None
        }
    
    # Convert billing to therms
    billing_therms = convert_billing_to_therms_per_premise(billing, rate_table, premises)
    
    # Compare simulated vs billing
    comparison, metrics = compare_simulated_vs_billing(simulated, billing_therms)
    
    # Flag divergent premises
    flagged = flag_divergent_premises(comparison, threshold_percent=50.0)
    
    # Save results
    output_path = Path(output_dir) / "validation"
    output_path.mkdir(parents=True, exist_ok=True)
    
    comparison.to_csv(output_path / "billing_calibration_comparison.csv", index=False)
    flagged.to_csv(output_path / "billing_calibration_flagged.csv", index=False)
    
    with open(output_path / "billing_calibration_metrics.json", 'w') as f:
        json.dump(metrics, f, indent=2)
    
    logger.info(f"Saved calibration results to {output_path}")
    
    return {
        'comparison': comparison,
        'metrics': metrics,
        'flagged': flagged,
        'report_path': str(output_path)
    }
