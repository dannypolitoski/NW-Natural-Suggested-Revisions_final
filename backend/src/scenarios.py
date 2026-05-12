"""
Scenario management module for NW Natural end-use forecasting model.

Defines scenario configurations, validation logic, and orchestration functions
for running independent forecasting scenarios with different assumptions about
technology adoption, electrification, and efficiency improvements.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Union
import pandas as pd
import numpy as np
import logging
from pathlib import Path
import json

from src.data_ingestion import build_premise_equipment_table
from src.housing_stock import build_baseline_stock, project_stock
from src.equipment import build_equipment_inventory, apply_replacements
from src.simulation import simulate_all_end_uses, simulate_all_end_uses_vectorized, simulate_monthly_vectorized
from src.aggregation import aggregate_by_end_use, aggregate_by_segment, aggregate_by_district, compute_use_per_customer
from src.config import BASE_YEAR, OUTPUT_DIR, IRP_LOAD_DECAY_FORECAST
from src import parameter_curves as pc

logger = logging.getLogger(__name__)


@dataclass
class ScenarioConfig:
    """
    Configuration for a forecasting scenario.
    
    Attributes:
        name: Scenario identifier (e.g., 'baseline', 'high_electrification')
        base_year: Starting year for projections (typically 2025)
        forecast_horizon: Number of years to project (e.g., 10 for 2025-2035)
        housing_growth_rate: Annual housing unit growth rate (0.0-0.05)
        electrification_rate: Annual rate of gas-to-electric fuel switching (0.0-0.10)
        efficiency_improvement: Annual efficiency improvement rate (0.0-0.05)
        weather_assumption: Weather scenario ('normal', 'warm', 'cold')
        end_use_scope: List of end-uses to simulate. Default ['space_heating'] (current scope).
                       Future work: ['water_heating', 'cooking', 'clothes_drying', 'fireplace', 'other']
        max_premises: Maximum number of premises to simulate (0 = all). Use for quick testing.
        vectorized: Use vectorized pandas operations instead of row-by-row loop. Much faster.
    """
    name: str
    base_year: int = BASE_YEAR
    forecast_horizon: int = 10
    housing_growth_rate: Union[float, dict] = 0.01
    electrification_rate: Union[float, dict] = 0.02
    efficiency_improvement: Union[float, dict] = 0.01
    weather_assumption: str = 'normal'
    end_use_scope: list = field(default_factory=lambda: ['space_heating'])
    max_premises: int = 0
    vectorized: bool = True
    sample_size: int = 100
    initial_gas_pct: float = 38.7
    heating_factor: float = 1.0
    temporal_resolution: str = 'annual'
    annual_degradation_rate: Union[float, dict] = 0.005
    repair_efficiency_recovery: float = 0.85
    new_equipment_efficiency: Union[float, dict] = 0.92
    demolition_rate: Union[float, dict] = 0.002
    new_construction_mf_share: float = 0.37
    # Hybrid heating
    hybrid_adoption_rate: Union[float, dict] = 0.03
    hybrid_gas_usage_factor: Union[float, dict] = 0.35
    # Vintage heating multipliers (relative to calibrated heating_factor)
    # Keys are "pre-1980", "1980-1999", "2000-2009", "2010-2014", "2015+"
    vintage_heating_multipliers: dict = field(default_factory=lambda: {
        'pre-1980': 1.35, '1980-1999': 1.15, '2000-2009': 1.00,
        '2010-2014': 0.85, '2015+': 0.70
    })
    # Segment heating multipliers (relative to calibrated heating_factor)
    segment_heating_multipliers: dict = field(default_factory=lambda: {
        'RESSF': 1.05, 'RESMF': 0.70, 'Unclassified': 1.00
    })
    # Whether to use RECS-derived non-heating ratios (true) or hardcoded fallback (false)
    use_recs_ratios: bool = True
    # Whether to enrich premise data with Census ACS distributions
    use_census_enrichment: bool = True
    # Calibrate the baseline scenario's estimated total UPC to the IRP UPC series
    # after bottom-up model effects have been applied. Non-baseline scenarios keep
    # their model-derived deltas so scenario comparisons remain meaningful.
    baseline_irp_alignment: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScenarioConfig':
        """Create config from dictionary, ignoring underscore-prefixed metadata keys."""
        # Filter out metadata keys (e.g., _comment, _parameters, _notes)
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if not k.startswith('_') and k in valid_fields}
        return cls(**filtered)


def _build_fallback_irp_forecast(base_year: int, forecast_horizon: int) -> pd.DataFrame:
    """Build a documented IRP UPC fallback when the forecast file is unavailable."""
    base_upc = 648.0
    annual_decay_rate = -0.0119
    rows = []
    for offset in range(forecast_horizon + 1):
        year = base_year + offset
        upc = base_upc * ((1 + annual_decay_rate) ** (year - BASE_YEAR))
        rows.append({
            'year': year,
            'irp_upc_therms': round(upc, 1),
            'irp_decay_rate': 0.0 if year == BASE_YEAR else annual_decay_rate,
            'irp_era': 'fallback_assumption',
            'irp_source': 'embedded_2025_irp_decay_assumption',
        })
    return pd.DataFrame(rows)


def _is_baseline_scenario(name: str) -> bool:
    """Return True when a scenario name represents the baseline/reference case."""
    normalized = str(name or '').strip().lower().replace('-', '_')
    return normalized == 'baseline' or normalized.startswith('baseline_')


def _align_baseline_to_irp(
    results_df: pd.DataFrame,
    estimated_total_df: pd.DataFrame,
    config: ScenarioConfig
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Scale baseline UPC outputs to the IRP total UPC trajectory when available.

    The model still computes the bottom-up shape first.  For the baseline/reference
    case only, this final calibration removes residual level/slope differences so
    dashboards compare alternative scenarios against an IRP-anchored baseline.
    """
    summary: Dict[str, Any] = {
        'enabled': False,
        'reason': 'disabled',
        'years_aligned': 0,
    }

    alignment_setting = getattr(config, 'baseline_irp_alignment', None)
    should_align = _is_baseline_scenario(config.name) if alignment_setting is None else bool(alignment_setting)
    if not should_align:
        return results_df, estimated_total_df, summary

    if estimated_total_df.empty or 'estimated_total_upc' not in estimated_total_df.columns or 'irp_upc' not in estimated_total_df.columns:
        summary['reason'] = 'missing_estimated_total_or_irp_columns'
        return results_df, estimated_total_df, summary

    aligned_results = results_df.copy()
    aligned_estimated = estimated_total_df.copy()
    aligned_estimated['irp_alignment_factor'] = 1.0
    aligned_estimated['irp_aligned'] = False

    scaled_estimated_cols = [
        col for col in aligned_estimated.columns
        if col not in {'year', 'irp_upc', 'diff_vs_irp', 'diff_vs_irp_pct', 'data_type', 'irp_alignment_factor', 'irp_aligned'}
        and pd.api.types.is_numeric_dtype(aligned_estimated[col])
    ]

    factors = []
    pre_alignment_pct = []
    for idx, row in aligned_estimated.iterrows():
        model_upc = row.get('estimated_total_upc')
        irp_upc = row.get('irp_upc')
        if pd.isna(model_upc) or pd.isna(irp_upc) or model_upc <= 0 or irp_upc <= 0:
            continue

        factor = float(irp_upc) / float(model_upc)
        year = int(row['year'])
        factors.append(factor)
        pre_alignment_pct.append(abs((float(model_upc) - float(irp_upc)) / float(irp_upc) * 100.0))

        result_mask = aligned_results['year'].astype(int) == year
        aligned_results.loc[result_mask, 'total_therms'] = aligned_results.loc[result_mask, 'total_therms'] * factor
        aligned_results.loc[result_mask, 'use_per_customer'] = aligned_results.loc[result_mask, 'use_per_customer'] * factor

        aligned_estimated.loc[idx, scaled_estimated_cols] = aligned_estimated.loc[idx, scaled_estimated_cols] * factor
        aligned_estimated.loc[idx, 'estimated_total_upc'] = round(float(irp_upc), 1)
        aligned_estimated.loc[idx, 'diff_vs_irp'] = 0.0
        aligned_estimated.loc[idx, 'diff_vs_irp_pct'] = 0.0
        aligned_estimated.loc[idx, 'irp_alignment_factor'] = round(factor, 6)
        aligned_estimated.loc[idx, 'irp_aligned'] = True

    if not factors:
        summary['reason'] = 'no_valid_irp_overlap'
        return results_df, estimated_total_df, summary

    for col in scaled_estimated_cols:
        aligned_estimated[col] = aligned_estimated[col].round(1)
    aligned_results['total_therms'] = aligned_results['total_therms'].astype(float)
    aligned_results['use_per_customer'] = aligned_results['use_per_customer'].astype(float)

    summary = {
        'enabled': True,
        'reason': 'baseline_irp_alignment',
        'years_aligned': len(factors),
        'min_factor': round(min(factors), 6),
        'max_factor': round(max(factors), 6),
        'mean_factor': round(float(np.mean(factors)), 6),
        'mean_abs_pct_before_alignment': round(float(np.mean(pre_alignment_pct)), 3),
    }
    logger.info(
        "Baseline IRP alignment applied to %s years: factor range %.4f–%.4f; "
        "mean pre-alignment absolute gap %.2f%%",
        summary['years_aligned'], summary['min_factor'], summary['max_factor'],
        summary['mean_abs_pct_before_alignment']
    )
    return aligned_results, aligned_estimated, summary


def validate_scenario(config: ScenarioConfig) -> Dict[str, Any]:
    """
    Validate scenario configuration parameters.
    
    Checks parameter ranges and interdependencies. Returns validation results
    with warnings for out-of-range values and errors for invalid combinations.
    
    Args:
        config: ScenarioConfig object to validate
    
    Returns:
        Dictionary with keys:
            - 'valid': bool, True if all checks pass
            - 'warnings': List[str], non-critical issues
            - 'errors': List[str], critical issues that prevent execution
            - 'details': Dict with per-parameter validation results
    
    Raises:
        TypeError: If config is not a ScenarioConfig instance
    """
    if not isinstance(config, ScenarioConfig):
        raise TypeError(f"config must be ScenarioConfig, got {type(config)}")
    
    warnings = []
    errors = []
    details = {}
    
    # Validate base_year
    if config.base_year < 2000 or config.base_year > 2100:
        errors.append(f"base_year {config.base_year} outside valid range [2000, 2100]")
        details['base_year'] = 'ERROR'
    else:
        details['base_year'] = 'OK'
    
    # Validate forecast_horizon
    if config.forecast_horizon <= 0:
        errors.append(f"forecast_horizon {config.forecast_horizon} must be > 0")
        details['forecast_horizon'] = 'ERROR'
    elif config.forecast_horizon > 100:
        warnings.append(f"forecast_horizon {config.forecast_horizon} is unusually long (>100 years)")
        details['forecast_horizon'] = 'WARNING'
    else:
        details['forecast_horizon'] = 'OK'
    
    # Validate housing_growth_rate (skip if curve)
    if isinstance(config.housing_growth_rate, (int, float)) and not (0.0 <= config.housing_growth_rate <= 0.05):
        warnings.append(f"housing_growth_rate {config.housing_growth_rate} outside typical range [0.0, 0.05]")
        details['housing_growth_rate'] = 'WARNING'
    else:
        details['housing_growth_rate'] = 'OK'
    
    # Validate electrification_rate (skip if curve)
    if isinstance(config.electrification_rate, (int, float)) and not (0.0 <= config.electrification_rate <= 0.10):
        warnings.append(f"electrification_rate {config.electrification_rate} outside typical range [0.0, 0.10]")
        details['electrification_rate'] = 'WARNING'
    else:
        details['electrification_rate'] = 'OK'
    
    # Validate efficiency_improvement (skip if curve)
    if isinstance(config.efficiency_improvement, (int, float)) and not (0.0 <= config.efficiency_improvement <= 0.05):
        warnings.append(f"efficiency_improvement {config.efficiency_improvement} outside typical range [0.0, 0.05]")
        details['efficiency_improvement'] = 'WARNING'
    else:
        details['efficiency_improvement'] = 'OK'
    
    # Validate weather_assumption
    valid_weather = {'normal', 'warm', 'cold'}
    if config.weather_assumption not in valid_weather:
        errors.append(f"weather_assumption '{config.weather_assumption}' not in {valid_weather}")
        details['weather_assumption'] = 'ERROR'
    else:
        details['weather_assumption'] = 'OK'
    
    # Check for rate constraints (all rates should be in [0, 1])
    rate_fields = {
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
    }
    for field_name, value in rate_fields.items():
        if isinstance(value, (int, float)) and not (0.0 <= value <= 1.0):
            errors.append(f"{field_name} {value} outside valid range [0.0, 1.0]")

    # Guardrails for the current space-heating-first workflow.
    # A total-UPC-calibrated heating factor combined with RECS adders will
    # effectively count non-heating demand twice.
    details['heating_factor'] = 'OK'
    if 'space_heating' in config.end_use_scope:
        if config.heating_factor == 1.0:
            warnings.append(
                "heating_factor is 1.0 for a scenario that includes space_heating. "
                "This is typically uncalibrated and can materially overstate demand."
            )
            details['heating_factor'] = 'WARNING'
        elif (
            len(config.end_use_scope) == 1
            and config.end_use_scope[0] == 'space_heating'
            and config.use_recs_ratios
            and config.heating_factor > 0.15
        ):
            warnings.append(
                "space_heating-only scenario is using RECS non-heating adders with a large "
                "heating_factor. If this factor was calibrated to total UPC instead of "
                "space-heating-only UPC, estimated total demand will be overstated."
            )
            details['heating_factor'] = 'WARNING'

    details['estimated_total_method'] = 'OK'
    if len(config.end_use_scope) == 1 and config.end_use_scope[0] == 'space_heating' and config.use_recs_ratios:
        warnings.append(
            "estimated total UPC is being reconstructed from RECS ratios on top of a "
            "space_heating-only simulation. Treat this as a provisional benchmark; "
            "prefer explicit non-heating modules or residual calibration before "
            "using it as the primary IRP comparison."
        )
        details['estimated_total_method'] = 'WARNING'
    
    valid = len(errors) == 0
    
    logger.info(
        f"Validated scenario '{config.name}': "
        f"valid={valid}, warnings={len(warnings)}, errors={len(errors)}"
    )
    
    return {
        'valid': valid,
        'warnings': warnings,
        'errors': errors,
        'details': details,
        'config': config
    }


def _load_irp_forecast(base_year: int, forecast_horizon: int) -> Optional[pd.DataFrame]:
    """Load NW Natural IRP 10-Year Load Decay Forecast for comparison.

    If the external CSV is unavailable, use the documented 2025 IRP planning
    assumption (648 therms/customer in 2025 with -1.19% annual decay) so model
    outputs still include an IRP UPC comparison.
    """
    try:
        irp_path = IRP_LOAD_DECAY_FORECAST
        if not Path(irp_path).exists():
            logger.warning(
                "IRP forecast file not found: %s; using embedded 2025 IRP decay fallback",
                irp_path
            )
            return _build_fallback_irp_forecast(base_year, forecast_horizon)
        df = pd.read_csv(irp_path)
        # Standardize column names
        df = df.rename(columns={
            'Year': 'year',
            'Avg_Res_UPC_Therms': 'irp_upc_therms',
            'Annual_Decay_Rate': 'irp_decay_rate',
            'Era': 'irp_era',
        })
        # Filter to our forecast range
        df = df[(df['year'] >= base_year) & (df['year'] <= base_year + forecast_horizon)]
        if 'irp_source' not in df.columns:
            df['irp_source'] = 'csv_forecast'
        logger.info(f"Loaded IRP forecast: {len(df)} years, UPC range {df['irp_upc_therms'].min():.1f}-{df['irp_upc_therms'].max():.1f}")
        return df
    except Exception as e:
        logger.warning(f"Failed to load IRP forecast: {e}; using embedded fallback")
        return _build_fallback_irp_forecast(base_year, forecast_horizon)


def run_scenario(
    config: ScenarioConfig,
    premise_equipment: pd.DataFrame,
    weather_data: pd.DataFrame,
    water_temp_data: pd.DataFrame,
    baseload_factors: Dict[str, float],
    output_dir: Optional[str] = None,
    non_heating_ratios: Optional[Dict[str, float]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Run a complete forecasting scenario from baseline through projection years.
    
    Orchestrates the full pipeline: load base data, build baseline housing stock,
    then for each year in forecast_horizon: project stock, apply replacements,
    simulate, and aggregate. Stores per-year results with scenario_name label.
    
    Args:
        config: ScenarioConfig object with scenario parameters
        premise_equipment: DataFrame from build_premise_equipment_table
        weather_data: DataFrame with weather data (HDD, etc.) by station and year
        water_temp_data: DataFrame with water temperature data
        baseload_factors: Dict mapping end_use to annual consumption (therms)
        output_dir: Optional directory to save per-year results
    
    Returns:
        Tuple of:
            - results_df: DataFrame with columns:
                year, end_use, scenario_name, total_therms, use_per_customer, premise_count
            - metadata: Dict with scenario metadata and execution summary
    
    Raises:
        ValueError: If config validation fails
        ValueError: If premise_equipment or weather_data is empty
    """
    # Validate scenario
    validation = validate_scenario(config)
    if not validation['valid']:
        raise ValueError(f"Scenario validation failed: {validation['errors']}")
    
    if premise_equipment.empty:
        raise ValueError("premise_equipment DataFrame is empty")
    if weather_data.empty:
        raise ValueError("weather_data DataFrame is empty")
    
    output_dir = Path(output_dir or OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Running scenario '{config.name}' for years {config.base_year}-{config.base_year + config.forecast_horizon}")
    
    # Filter to end-use scope
    scope = config.end_use_scope
    logger.info(f"End-use scope: {scope}")
    scoped_equipment = premise_equipment[premise_equipment['end_use'].isin(scope)].copy()
    if scoped_equipment.empty:
        # Fall back to all equipment if scope filter removes everything
        logger.warning(f"No equipment matches end_use_scope {scope}; using all equipment")
        scoped_equipment = premise_equipment.copy()
    else:
        logger.info(f"Filtered to {len(scoped_equipment)} equipment records in scope (from {len(premise_equipment)})")
    
    # Limit premises for quick testing
    if config.max_premises > 0:
        unique_ids = scoped_equipment['blinded_id'].unique()
        if len(unique_ids) > config.max_premises:
            sampled_ids = unique_ids[:config.max_premises]
            scoped_equipment = scoped_equipment[scoped_equipment['blinded_id'].isin(sampled_ids)].copy()
            logger.info(f"Limited to {config.max_premises} premises ({len(scoped_equipment)} equipment records)")
    
    # Build baseline housing stock (full dataset)
    baseline_stock = build_baseline_stock(scoped_equipment, config.base_year)
    logger.info(f"Built baseline stock: {baseline_stock.total_units} units")
    
    # =========================================================================
    # PHASE 1: Run Weibull replacement on SAMPLE to derive yearly rates
    # =========================================================================
    sample_size = config.sample_size
    unique_ids = scoped_equipment['blinded_id'].unique()
    
    if sample_size > 0 and len(unique_ids) > sample_size:
        np.random.seed(42)  # Reproducible sample
        sample_ids = np.random.choice(unique_ids, size=sample_size, replace=False)
        sample_equipment = scoped_equipment[scoped_equipment['blinded_id'].isin(sample_ids)].copy()
        logger.info(f"Phase 1: Running Weibull replacement on {sample_size}-premise sample ({len(sample_equipment)} equipment records)")
    else:
        sample_equipment = scoped_equipment.copy()
        sample_size = len(unique_ids)
        logger.info(f"Phase 1: Running Weibull replacement on full dataset ({sample_size} premises)")
    
    sample_inventory = build_equipment_inventory(sample_equipment)
    
    # Run replacement simulation on sample to extract yearly REPLACEMENT rates
    # Electrification is computed analytically (too rare for small samples)
    sample_current = sample_inventory.copy()
    yearly_rates = []
    base_year_avg_eff = sample_current['efficiency'].mean()
    base_year_gas_pct = (sample_current['fuel_type'] == 'natural_gas').mean() if 'fuel_type' in sample_current.columns else 1.0
    cumulative_gas_fraction = base_year_gas_pct
    cumulative_hybrid_fraction = 0.0  # starts at 0, grows as replacements happen
    
    for year_offset in range(config.forecast_horizon + 1):
        year = config.base_year + year_offset
        
        if year_offset == 0:
            yearly_rates.append({
                'year': year,
                'efficiency_multiplier': 1.0,
                'gas_fraction': cumulative_gas_fraction,
                'hybrid_fraction': cumulative_hybrid_fraction,
                'replacement_rate': 0.0,
                'repair_rate': 0.0,
                'avg_efficiency': base_year_avg_eff,
            })
        else:
            # Resolve curve parameters for this year
            yr_elec_rate = pc.resolve(config.electrification_rate, year, 0.02)
            yr_hybrid_rate = pc.resolve(config.hybrid_adoption_rate, year, 0.03)
            yr_degrad_rate = pc.resolve(config.annual_degradation_rate, year, 0.005)
            yr_eff_improve = pc.resolve(config.efficiency_improvement, year, 0.01)
            yr_new_eff = pc.resolve(config.new_equipment_efficiency, year, 0.92)
            
            scenario_dict = {
                'electrification_rate': {
                    'space_heating': yr_elec_rate,
                    'water_heating': yr_elec_rate,
                    'cooking': 0.0,
                    'clothes_drying': yr_elec_rate,
                    'fireplace': 0.0,
                    'other': 0.0
                },
                'efficiency_improvement': {
                    'space_heating': yr_eff_improve,
                    'water_heating': yr_eff_improve,
                    'cooking': yr_eff_improve,
                    'clothes_drying': yr_eff_improve,
                    'fireplace': 0.0,
                    'other': 0.0
                },
                'annual_degradation_rate': yr_degrad_rate,
                'repair_efficiency_recovery': config.repair_efficiency_recovery,
                'new_equipment_efficiency': yr_new_eff,
            }
            
            sample_current = apply_replacements(sample_current, scenario_dict, year)
            
            new_avg_eff = sample_current['efficiency'].mean()
            replaced = int((sample_current['install_year'] == year).sum()) if 'install_year' in sample_current.columns else 0
            repl_rate = replaced / max(len(sample_current), 1)
            
            # Count repaired: units past half useful life that weren't replaced
            if 'useful_life' in sample_current.columns:
                age = year - sample_current['install_year']
                repair_count = int(((age > sample_current['useful_life'] / 2) & (sample_current['install_year'] != year)).sum())
                repair_rate = repair_count / max(len(sample_current), 1)
            else:
                repair_rate = repl_rate * 2.0
            
            # Compute gas/hybrid/electric fractions analytically:
            # Each year, repl_rate fraction of units are replaced.
            # Of those replaced:
            #   - electrification_rate go full electric (0 gas)
            #   - hybrid_adoption_rate go hybrid (reduced gas usage)
            #   - remainder stay full gas
            # Units leaving full-gas pool this year:
            leaving_gas = cumulative_gas_fraction * repl_rate
            new_electric = leaving_gas * yr_elec_rate
            new_hybrid = leaving_gas * yr_hybrid_rate
            new_gas_back = leaving_gas - new_electric - new_hybrid  # replaced but stay gas
            
            cumulative_gas_fraction = cumulative_gas_fraction - leaving_gas + new_gas_back
            cumulative_hybrid_fraction = cumulative_hybrid_fraction + new_hybrid
            # electric fraction = 1.0 - gas - hybrid (implicit)
            
            yearly_rates.append({
                'year': year,
                'efficiency_multiplier': base_year_avg_eff / new_avg_eff if new_avg_eff > 0 else 1.0,
                'gas_fraction': round(cumulative_gas_fraction, 6),
                'hybrid_fraction': round(cumulative_hybrid_fraction, 6),
                'replacement_rate': repl_rate,
                'repair_rate': repair_rate,
                'avg_efficiency': new_avg_eff,
            })
    
    rates_df = pd.DataFrame(yearly_rates)
    
    # Ensure efficiency is monotonically non-decreasing over time.
    # The sample can show dips due to degradation compounding on a small fleet,
    # but the real fleet-wide average should keep improving as old units are replaced.
    best_eff = rates_df['avg_efficiency'].iloc[0]
    for i in range(1, len(rates_df)):
        if rates_df.loc[i, 'avg_efficiency'] < best_eff:
            rates_df.loc[i, 'avg_efficiency'] = best_eff
        else:
            best_eff = rates_df.loc[i, 'avg_efficiency']
        # Recompute multiplier from corrected efficiency
        rates_df.loc[i, 'efficiency_multiplier'] = base_year_avg_eff / rates_df.loc[i, 'avg_efficiency'] if rates_df.loc[i, 'avg_efficiency'] > 0 else 1.0
    
    # Backfill base year replacement and repair rates with averages from projection years
    projection_rates = rates_df[rates_df['replacement_rate'] > 0]['replacement_rate']
    if len(projection_rates) > 0:
        avg_repl_rate = projection_rates.mean()
        rates_df.loc[rates_df['year'] == config.base_year, 'replacement_rate'] = avg_repl_rate
    projection_repair = rates_df[rates_df['repair_rate'] > 0]['repair_rate']
    if len(projection_repair) > 0:
        avg_repair_rate = projection_repair.mean()
        rates_df.loc[rates_df['year'] == config.base_year, 'repair_rate'] = avg_repair_rate
    
    logger.info(f"Phase 1 complete: derived {len(rates_df)} yearly rates from {sample_size}-premise sample")
    logger.info(f"  Efficiency: {rates_df['avg_efficiency'].iloc[0]:.4f} → {rates_df['avg_efficiency'].iloc[-1]:.4f}")
    logger.info(f"  Gas fraction: {rates_df['gas_fraction'].iloc[0]:.4f} → {rates_df['gas_fraction'].iloc[-1]:.4f}")
    
    # =========================================================================
    # PHASE 2: Simulate base year on FULL dataset, then scale using sample rates
    # =========================================================================
    logger.info(f"Phase 2: Simulating base year on full dataset ({len(scoped_equipment)} equipment records)")
    
    full_inventory = build_equipment_inventory(scoped_equipment)
    
    # --- Compute actual HDD for the weather year being used ---
    # This is needed to normalize the heating factor if the simulation uses
    # a different weather year than the one the heating factor was calibrated against.
    wd_copy = weather_data.copy()
    wd_copy['date'] = pd.to_datetime(wd_copy['date'], errors='coerce')
    wd_copy['_year'] = wd_copy['date'].dt.year
    
    # Determine which weather year will actually be used by the simulation
    # Annual path: uses target year if >100 records (partial year OK)
    # Monthly path: requires all 12 months
    target_year_data = wd_copy[wd_copy['_year'] == config.base_year]
    months_avail = target_year_data['date'].dt.month.nunique() if not target_year_data.empty else 0
    records_avail = len(target_year_data)
    
    is_monthly = config.temporal_resolution == 'monthly'
    months_per_year = wd_copy.groupby('_year')['date'].apply(lambda x: x.dt.month.nunique())
    full_years = months_per_year[months_per_year >= 12].index
    
    if is_monthly:
        # Monthly path needs 12 months
        if months_avail >= 12:
            actual_weather_year = config.base_year
        elif len(full_years) > 0:
            actual_weather_year = int(full_years.max())
        else:
            actual_weather_year = config.base_year
    else:
        # Annual path uses target year if it has any substantial data
        if records_avail >= 100:
            actual_weather_year = config.base_year
        elif len(full_years) > 0:
            actual_weather_year = int(full_years.max())
        else:
            actual_weather_year = config.base_year
    
    # Compute HDD for both the calibration year and the actual weather year
    wd_copy['hdd'] = (65.0 - wd_copy['daily_avg_temp']).clip(lower=0)
    
    # Weighted average HDD for the actual weather year
    actual_year_hdd = wd_copy[wd_copy['_year'] == actual_weather_year].groupby('site_id')['hdd'].sum()
    if 'weather_station' in full_inventory.columns:
        station_weights = full_inventory['weather_station'].value_counts()
        weighted_actual_hdd = sum(actual_year_hdd.get(s, 0) * c for s, c in station_weights.items()) / max(station_weights.sum(), 1)
    else:
        weighted_actual_hdd = actual_year_hdd.mean() if len(actual_year_hdd) > 0 else 0
    
    # Calibration year HDD (what the heating factor was calibrated against)
    calib_year_hdd_data = wd_copy[wd_copy['_year'] == config.base_year].groupby('site_id')['hdd'].sum()
    if 'weather_station' in full_inventory.columns:
        weighted_calib_hdd = sum(calib_year_hdd_data.get(s, 0) * c for s, c in station_weights.items()) / max(station_weights.sum(), 1)
    else:
        weighted_calib_hdd = calib_year_hdd_data.mean() if len(calib_year_hdd_data) > 0 else 0
    
    # Normalize heating factor: if using a different weather year, adjust proportionally
    effective_heating_factor = config.heating_factor
    if actual_weather_year != config.base_year and weighted_actual_hdd > 0 and weighted_calib_hdd > 0:
        hdd_ratio = weighted_calib_hdd / weighted_actual_hdd
        effective_heating_factor = config.heating_factor * hdd_ratio
        logger.info(
            f"HDD normalization: calibration year {config.base_year} HDD={weighted_calib_hdd:.0f}, "
            f"actual weather year {actual_weather_year} HDD={weighted_actual_hdd:.0f}, "
            f"ratio={hdd_ratio:.4f}, heating_factor {config.heating_factor:.6f} → {effective_heating_factor:.6f}"
        )
    else:
        logger.info(f"Using weather year {actual_weather_year}, HDD={weighted_actual_hdd:.0f}, heating_factor={effective_heating_factor:.6f}")
    
    # Store HDD info for output
    hdd_info = {
        'calibration_year': config.base_year,
        'calibration_hdd': round(weighted_calib_hdd, 1),
        'actual_weather_year': actual_weather_year,
        'actual_hdd': round(weighted_actual_hdd, 1),
        'hdd_ratio': round(weighted_calib_hdd / weighted_actual_hdd, 4) if weighted_actual_hdd > 0 else 1.0,
        'config_heating_factor': config.heating_factor,
        'effective_heating_factor': round(effective_heating_factor, 6),
    }
    
    # Compute historical HDD by year for the chart
    yearly_hdd = wd_copy.groupby(['_year', 'site_id'])['hdd'].sum().reset_index()
    if 'weather_station' in full_inventory.columns:
        # Weighted average across stations
        yearly_hdd_weighted = []
        for yr in sorted(yearly_hdd['_year'].unique()):
            yr_data = yearly_hdd[yearly_hdd['_year'] == yr].set_index('site_id')['hdd']
            w_hdd = sum(yr_data.get(s, 0) * c for s, c in station_weights.items()) / max(station_weights.sum(), 1)
            yearly_hdd_weighted.append({'year': int(yr), 'weighted_hdd': round(w_hdd, 1)})
        hdd_history_df = pd.DataFrame(yearly_hdd_weighted)
    else:
        hdd_history_df = yearly_hdd.groupby('_year')['hdd'].mean().reset_index()
        hdd_history_df.columns = ['year', 'weighted_hdd']
    
    # Simulate base year on full dataset (one pass)
    # Override config-level multipliers with scenario-specific values
    import src.config as _cfg
    _saved_vintage = _cfg.VINTAGE_HEATING_MULTIPLIER
    _saved_segment = _cfg.SEGMENT_HEATING_MULTIPLIER
    # Convert scenario dict keys to config format: {"pre-1980": 1.35} → {(0, 1979): 1.35}
    _era_to_range = {'pre-1980': (0, 1979), '1980-1999': (1980, 1999), '2000-2009': (2000, 2009),
                     '2010-2014': (2010, 2014), '2015+': (2015, 2099)}
    _cfg.VINTAGE_HEATING_MULTIPLIER = {_era_to_range.get(k, k): v for k, v in config.vintage_heating_multipliers.items()}
    _cfg.SEGMENT_HEATING_MULTIPLIER = config.segment_heating_multipliers
    logger.info(f"Vintage multipliers: {config.vintage_heating_multipliers}")
    logger.info(f"Segment multipliers: {config.segment_heating_multipliers}")
    
    is_monthly = config.temporal_resolution == 'monthly'
    if is_monthly:
        logger.info("Using MONTHLY temporal resolution")
        base_year_sim = simulate_monthly_vectorized(
            full_inventory, weather_data, water_temp_data, baseload_factors,
            year=config.base_year,
            heating_factor=effective_heating_factor
        )
    elif config.vectorized:
        base_year_sim = simulate_all_end_uses_vectorized(
            full_inventory, weather_data, water_temp_data, baseload_factors,
            year=config.base_year,
            heating_factor=effective_heating_factor
        )
    else:
        base_year_sim = simulate_all_end_uses(
            full_inventory, weather_data, water_temp_data, baseload_factors,
            year=config.base_year,
            heating_factor=effective_heating_factor
        )
    
    logger.info(f"Base year simulation: {len(base_year_sim)} rows, {base_year_sim['annual_therms'].sum():,.0f} total therms")
    
    # Restore config-level multipliers
    _cfg.VINTAGE_HEATING_MULTIPLIER = _saved_vintage
    _cfg.SEGMENT_HEATING_MULTIPLIER = _saved_segment
    
    # Collect results for all years
    all_results = []
    yearly_equipment_stats = []
    yearly_premise_distributions = []
    yearly_segment_demand = []
    yearly_vintage_demand = []
    
    for year_offset in range(config.forecast_horizon + 1):
        year = config.base_year + year_offset
        rate = rates_df[rates_df['year'] == year].iloc[0]
        
        logger.info(f"Processing year {year} (offset {year_offset})")
        
        # Project housing stock
        if year_offset == 0:
            stock = baseline_stock
        else:
            stock = project_stock(baseline_stock, year, config.to_dict())
        
        # Scale base-year simulation results using TWO combined effects:
        # 1. EQUIPMENT EFFICIENCY: Weibull-driven per-premise failure/repair/replacement
        # 2. HOUSING ENVELOPE: vintage mix shift (old leaky homes demolished, new tight homes built)
        # These are multiplicative: therms = base_therms × equipment_factor × envelope_factor
        sim_results = base_year_sim.copy()
        sim_results['year'] = year
        
        if year_offset > 0 and 'setyear' in full_inventory.columns:
            from src.equipment import replacement_probability, median_to_eta
            from src.config import USEFUL_LIFE, WEIBULL_BETA
            
            _ul_local = USEFUL_LIFE.get('space_heating', 20)
            _beta_local = WEIBULL_BETA.get('space_heating', 3.0)
            _eta_local = median_to_eta(_ul_local, _beta_local)
            
            # Get per-premise equipment age and vintage
            sy_lookup = full_inventory.drop_duplicates('blinded_id')[['blinded_id', 'setyear']].set_index('blinded_id')['setyear']
            sy = sim_results['blinded_id'].map(sy_lookup)
            sy = pd.to_numeric(sy, errors='coerce').fillna(2000)
            equip_age = (config.base_year - sy).clip(lower=0)
            effective_age = equip_age + year_offset
            
            # =====================================================================
            # EFFECT 1: Equipment efficiency (Weibull-driven per-premise)
            # =====================================================================
            base_eff = 0.80  # DEFAULT_EFFICIENCY for space_heating
            
            # Year-dependent new equipment AFUE — resolved from curve or fixed value
            new_eff = pc.resolve(config.new_equipment_efficiency, year, 0.92)
            new_eff = min(new_eff, 0.98)  # physical limit for gas
            
            # Weibull failure probability per premise
            fail_prob = effective_age.apply(lambda a: replacement_probability(a, _eta_local, _beta_local))
            
            # Stochastic: does this premise's equipment fail this year?
            np.random.seed(42 + year)
            random_draw = np.random.uniform(0, 1, len(sim_results))
            fails = random_draw < fail_prob
            
            is_replaced = fails & (effective_age >= _ul_local)
            is_repaired = fails & (effective_age < _ul_local)
            
            # Equipment efficiency multiplier per premise
            yr_degrad = pc.resolve(config.annual_degradation_rate, year, 0.005)
            degradation = (1 - yr_degrad) ** year_offset
            equip_mult = pd.Series(degradation, index=sim_results.index)
            
            # Replaced: efficiency jumps to new AFUE (big improvement for old equipment)
            equip_mult[is_replaced] = base_eff / new_eff
            
            # Repaired: partial recovery of degradation
            repair_factor = degradation + (1.0 - degradation) * config.repair_efficiency_recovery
            equip_mult[is_repaired] = repair_factor
            
            # =====================================================================
            # EFFECT 2: Housing envelope improvement (code-driven + weatherization)
            # =====================================================================
            # Uses the envelope efficiency model which tracks how building codes
            # have improved over time. New homes built in 2030 are ~38% more
            # efficient than 2000-era homes. The fleet average improves as old
            # homes are demolished and new efficient homes are built.
            from src.envelope_efficiency import get_envelope_index
            
            envelope_mult = pd.Series(1.0, index=sim_results.index)
            
            # Each premise's envelope improvement = ratio of its era's index
            # at base year vs what it would be after weatherization + code improvements
            for yr_min, yr_max, annual_weatherization in [
                (0, 1979, 0.0045),      # Pre-1980: 0.45%/yr from weatherization programs
                (1980, 1999, 0.003),     # 1980-99: 0.3%/yr
                (2000, 2014, 0.001),     # 2000-14: 0.1%/yr (already decent)
                (2015, 2099, 0.0),       # 2015+: already tight, no improvement
            ]:
                mask = (sy >= yr_min) & (sy <= yr_max)
                if mask.any():
                    envelope_mult[mask] = (1 - annual_weatherization) ** year_offset
            
            # =====================================================================
            # COMBINE: therms = base × equipment_factor × envelope_factor
            # =====================================================================
            sim_results['annual_therms'] = sim_results['annual_therms'] * equip_mult * envelope_mult
            
            # =====================================================================
            # EFFECT 3: Gas fraction (electrification/hybrid, vintage-weighted)
            # =====================================================================
            base_gas = rates_df.iloc[0]['gas_fraction']
            if base_gas > 0:
                effective_gas = rate['gas_fraction'] + rate.get('hybrid_fraction', 0) * config.hybrid_gas_usage_factor
                base_effective = base_gas + rates_df.iloc[0].get('hybrid_fraction', 0) * config.hybrid_gas_usage_factor
                gas_scale = effective_gas / base_effective
                
                gas_reduction = 1.0 - gas_scale
                gas_adj = pd.Series(gas_scale, index=sim_results.index)
                gas_adj[sy < 1980] = gas_scale - gas_reduction * 0.15
                gas_adj[(sy >= 1980) & (sy < 2000)] = gas_scale - gas_reduction * 0.05
                gas_adj[sy >= 2015] = gas_scale + gas_reduction * 0.10
                gas_adj = gas_adj.clip(lower=0)
                sim_results['annual_therms'] = sim_results['annual_therms'] * gas_adj
        else:
            # Base year or no vintage data: use uniform scaling
            base_eff_mult = rate['efficiency_multiplier']
            sim_results['annual_therms'] = sim_results['annual_therms'] * base_eff_mult

        # Scale system demand for the projected customer count before calculating UPC.
        # Without this, housing growth only increases the UPC denominator, causing an
        # artificial load-decay signal when new customers are not represented as rows.
        customer_scale = stock.total_units / max(baseline_stock.total_units, 1)
        sim_results['annual_therms'] = sim_results['annual_therms'] * customer_scale
        
        # Equipment stats: Weibull age-cohort model for failures/repairs/replacements
        # Each year, compute failure probability by age using Weibull, then determine
        # whether failed units get repaired (young) or replaced (old).
        total_equip_for_year = int(round(len(full_inventory) * stock.total_units / baseline_stock.total_units))
        
        if year_offset == 0:
            # Build age distribution from actual fleet
            from src.equipment import replacement_probability, median_to_eta
            from src.config import USEFUL_LIFE, WEIBULL_BETA
            
            _ul = USEFUL_LIFE.get('space_heating', 20)
            _beta = WEIBULL_BETA.get('space_heating', 3.0)
            _eta = median_to_eta(_ul, _beta)
            
            # Count units at each age
            if 'install_year' in full_inventory.columns:
                ages = (config.base_year - pd.to_numeric(full_inventory['install_year'], errors='coerce')).fillna(_ul)
                ages = ages.clip(lower=0, upper=80).astype(int)
                _age_dist = ages.value_counts().sort_index().to_dict()  # {age: count}
            else:
                # Assume uniform distribution 0-40 years
                _age_dist = {a: len(full_inventory) // 40 for a in range(40)}
            
            _base_total = sum(_age_dist.values())
            logger.info(f"Age-cohort model: {len(_age_dist)} age bins, total={_base_total}, "
                        f"eta={_eta:.1f}, beta={_beta}, useful_life={_ul}")
        
        # Scale age distribution to current year's total equipment
        scale = total_equip_for_year / _base_total if _base_total > 0 else 1.0
        
        # Compute failures, repairs, replacements from Weibull
        yr_failures = 0
        yr_repairs = 0
        yr_replacements = 0
        for age, count in _age_dist.items():
            scaled_count = count * scale
            # Weibull failure probability at this age
            fail_prob = replacement_probability(age + year_offset, _eta, _beta)
            failures = scaled_count * fail_prob
            
            # Failed units: repair if age < useful_life, replace if >= useful_life
            effective_age = age + year_offset
            if effective_age < _ul:
                yr_repairs += failures
            else:
                yr_replacements += failures
            yr_failures += failures
        
        # Add new construction failures (age 0-2, very low failure rate)
        if year_offset > 0:
            new_units = total_equip_for_year - int(round(len(full_inventory) * baseline_stock.total_units / baseline_stock.total_units))
            # New units have near-zero failure rate, but add a small amount
            yr_repairs += new_units * 0.005  # 0.5% infant failure rate
        
        replaced = int(round(yr_replacements))
        repaired = int(round(yr_repairs))
        total_failures = int(round(yr_failures))
        # Malfunctioning = failures not yet addressed (backlog). In practice,
        # most failures get repaired or replaced within the year, but some
        # units run degraded. Model assumes ~10% backlog.
        malfunctioning = int(round(total_failures * 0.10))
        working = total_equip_for_year - malfunctioning
        
        gas_units = int(total_equip_for_year * rate['gas_fraction'])
        hybrid_units = int(total_equip_for_year * rate.get('hybrid_fraction', 0))
        elec_units = total_equip_for_year - gas_units - hybrid_units
        
        # Territory-wide gas share: initial_gas_pct adjusted by electrification
        territory_gas_pct = config.initial_gas_pct * rate['gas_fraction'] / 100.0
        territory_elec_pct = 100.0 - territory_gas_pct * 100.0
        
        yearly_equipment_stats.append({
            'year': year,
            'total_equipment': total_equip_for_year,
            'gas_units': gas_units,
            'hybrid_units': hybrid_units,
            'electric_units': elec_units,
            'electrification_pct': round(elec_units / max(total_equip_for_year, 1) * 100, 2),
            'hybrid_pct': round(hybrid_units / max(total_equip_for_year, 1) * 100, 2),
            'avg_efficiency': round(rate['avg_efficiency'], 4),
            'new_equip_efficiency': round(pc.resolve(config.new_equipment_efficiency, year, 0.92), 4),
            'units_replaced': replaced,
            'units_repaired': repaired,
            'units_malfunctioning': malfunctioning,
            'units_working': working,
            'total_failures': total_failures,
            'end_use': 'space_heating',
            'total_premises': stock.total_units,
            'gas_fraction_of_nwn': round(rate['gas_fraction'] * 100, 2),
            'hybrid_fraction_of_nwn': round(rate.get('hybrid_fraction', 0) * 100, 2),
            'territory_gas_pct': round(territory_gas_pct * 100, 2),
            'territory_elec_pct': round(territory_elec_pct, 2),
            'data_type': 'calibrated' if year_offset == 0 else 'projected',
        })
        
        # Per-premise distribution for this year (overall + by segment)
        if not sim_results.empty:
            # Build segment lookup
            seg_lookup = None
            if 'segment' in full_inventory.columns:
                seg_lookup = full_inventory.drop_duplicates('blinded_id')[['blinded_id', 'segment']].set_index('blinded_id')['segment']
            
            premise_therms = sim_results.groupby('blinded_id')['annual_therms'].sum()
            
            # Compute distribution for overall and each segment
            for seg_name in ['ALL', 'RESSF', 'RESMF']:
                if seg_name == 'ALL':
                    pt = premise_therms
                elif seg_lookup is not None:
                    seg_ids = seg_lookup[seg_lookup == seg_name].index
                    pt = premise_therms[premise_therms.index.isin(seg_ids)]
                else:
                    continue
                
                if len(pt) == 0:
                    continue
                
                yearly_premise_distributions.append({
                    'year': year,
                    'segment': seg_name,
                    'min_therms': round(pt.min(), 1),
                    'p10_therms': round(pt.quantile(0.10), 1),
                    'p25_therms': round(pt.quantile(0.25), 1),
                    'median_therms': round(pt.median(), 1),
                    'p75_therms': round(pt.quantile(0.75), 1),
                    'p90_therms': round(pt.quantile(0.90), 1),
                    'max_therms': round(pt.max(), 1),
                    'mean_therms': round(pt.mean(), 1),
                    'std_therms': round(pt.std(), 1),
                    'premise_count': len(pt),
                })
            
            # Demand by segment
            if seg_lookup is not None:
                sim_with_seg = sim_results.copy()
                sim_with_seg['segment'] = sim_with_seg['blinded_id'].map(seg_lookup).fillna('Unclassified')
                if is_monthly and 'month' in sim_with_seg.columns:
                    seg_demand = sim_with_seg.groupby(['segment', 'month'])['annual_therms'].agg(['sum', 'count']).reset_index()
                    seg_demand.columns = ['segment', 'month', 'total_therms', 'equipment_count']
                else:
                    seg_demand = sim_with_seg.groupby('segment')['annual_therms'].agg(['sum', 'count']).reset_index()
                    seg_demand.columns = ['segment', 'total_therms', 'equipment_count']
                seg_demand['year'] = year
                yearly_segment_demand.append(seg_demand)
            
            # Demand by vintage era (with demolition and new construction adjustments)
            if 'setyear' in full_inventory.columns:
                sy_lookup = full_inventory.drop_duplicates('blinded_id')[['blinded_id', 'setyear']].set_index('blinded_id')['setyear']
                sim_with_vy = sim_results.copy()
                sy = sim_with_vy['blinded_id'].map(sy_lookup)
                sy = pd.to_numeric(sy, errors='coerce')
                bins = [0, 1979, 1999, 2009, 2014, 2099]
                labels = ['pre-1980', '1980-1999', '2000-2009', '2010-2014', '2015+']
                sim_with_vy['vintage_era'] = pd.cut(sy, bins=bins, labels=labels).astype(str).replace('nan', 'Unknown')
                if is_monthly and 'month' in sim_with_vy.columns:
                    vy_demand = sim_with_vy.groupby(['vintage_era', 'month'])['annual_therms'].agg(['sum', 'count', 'mean']).reset_index()
                    vy_demand.columns = ['vintage_era', 'month', 'total_therms', 'equipment_count', 'avg_therms']
                else:
                    vy_demand = sim_with_vy.groupby('vintage_era')['annual_therms'].agg(['sum', 'count', 'mean']).reset_index()
                    vy_demand.columns = ['vintage_era', 'total_therms', 'equipment_count', 'avg_therms']
                vy_demand['year'] = year
                
                # Adjust vintage counts for demolition and new construction
                # Only applies to annual aggregation — monthly rows are already proportional
                if year_offset > 0 and not (is_monthly and 'month' in vy_demand.columns):
                    demo_rate = config.demolition_rate
                    # Older homes demolished at higher rate
                    vintage_demo_rates = {
                        'pre-1980': demo_rate * 2.5,   # 0.5%/yr — oldest homes demolished fastest
                        '1980-1999': demo_rate * 1.5,   # 0.3%/yr
                        '2000-2009': demo_rate * 0.5,   # 0.1%/yr
                        '2010-2014': demo_rate * 0.2,   # 0.04%/yr — very few demolished
                        '2015+': demo_rate * 0.0,       # 0%/yr — too new to demolish
                    }
                    for era, era_demo in vintage_demo_rates.items():
                        mask = vy_demand['vintage_era'] == era
                        if mask.any():
                            original = vy_demand.loc[mask, 'equipment_count'].values[0]
                            surviving = int(round(original * ((1 - era_demo) ** year_offset)))
                            vy_demand.loc[mask, 'equipment_count'] = surviving
                            # Scale therms proportionally
                            if original > 0:
                                vy_demand.loc[mask, 'total_therms'] *= surviving / original
                    
                    # New construction goes into 2015+ bucket with proportional therms
                    new_units = int(round(stock.total_units - baseline_stock.total_units))
                    if new_units > 0:
                        mask_new = vy_demand['vintage_era'] == '2015+'
                        if mask_new.any():
                            # New units produce therms at the 2015+ avg rate
                            avg_therms_new = vy_demand.loc[mask_new, 'avg_therms'].values[0]
                            vy_demand.loc[mask_new, 'equipment_count'] += new_units
                            vy_demand.loc[mask_new, 'total_therms'] += new_units * avg_therms_new
                
                yearly_vintage_demand.append(vy_demand)
        
        # Aggregate by end-use (and month if monthly resolution)
        if is_monthly and 'month' in sim_results.columns:
            # Group by end_use and month
            agg_results = sim_results.groupby(['end_use', 'month']).agg(
                total_therms=('annual_therms', 'sum'),
                premise_count=('blinded_id', 'nunique')
            ).reset_index()
        else:
            agg_results = aggregate_by_end_use(sim_results)
        agg_results['year'] = year
        agg_results['scenario_name'] = config.name
        
        # Compute use-per-customer against the projected customer count.
        # Use the same customer count in the exported row so downstream IRP comparisons
        # do not recompute UPC against the fixed base-year simulated premise count.
        total_demand = agg_results['total_therms'].sum()
        total_customers = stock.total_units
        agg_results['premise_count'] = int(total_customers)
        upc = total_demand / total_customers if total_customers > 0 else 0.0
        agg_results['use_per_customer'] = upc
        
        all_results.append(agg_results)
        
        logger.info(
            f"Year {year}: total_demand={total_demand:.0f} therms, "
            f"UPC={upc:.1f} therms/customer, "
            f"{'monthly' if is_monthly else 'annual'}"
        )
    
    # Combine all years into single results DataFrame
    results_df = pd.concat(all_results, ignore_index=True)
    
    # Add data_type column: 'calibrated' for base year, 'projected' for forecast years
    results_df['data_type'] = np.where(results_df['year'] == config.base_year, 'calibrated', 'projected')
    
    # Reorder columns for consistency
    base_cols = ['year']
    if 'month' in results_df.columns:
        base_cols.append('month')
    base_cols += ['end_use', 'scenario_name', 'total_therms', 'use_per_customer', 'premise_count', 'data_type']
    results_df = results_df[[c for c in base_cols if c in results_df.columns]]
    
    # Load NW Natural IRP forecast for comparison
    irp_forecast = _load_irp_forecast(config.base_year, config.forecast_horizon)
    if irp_forecast is not None:
        # Merge IRP UPC into results for side-by-side comparison
        irp_cols = ['year', 'irp_upc_therms']
        if 'irp_source' in irp_forecast.columns:
            irp_cols.append('irp_source')
        results_df = results_df.merge(
            irp_forecast[irp_cols],
            on='year', how='left'
        )
        logger.info("Added NW Natural IRP forecast UPC to results")
    else:
        results_df['irp_upc_therms'] = None
    
    # =========================================================================
    # Compute estimated total UPC by adding non-heating end-uses
    # =========================================================================
    # Instead of forcing the total to match IRP, we estimate non-heating end-uses
    # independently using RECS PNW proportions relative to space heating.
    # If RECS-derived ratios were passed in, use those; otherwise fall back to defaults.
    estimated_total_rows = []
    
    # Use dynamic RECS ratios if provided, otherwise hardcoded fallback
    non_sh_ratios = non_heating_ratios or {
        'water_heating': 0.41,
        'cooking': 0.08,
        'clothes_drying': 0.05,
        'fireplace': 0.07,
        'other': 0.03,
    }
    logger.info(f"Non-heating ratios: {non_sh_ratios}")
    
    for _, row in results_df.iterrows():
        yr = int(row['year'])
        sh_upc = row['use_per_customer']
        irp_upc = row.get('irp_upc_therms', None)
        irp_source = row.get('irp_source', None)
        
        row_data = {
            'year': yr,
            'space_heating': round(sh_upc, 1),
        }
        non_heating_total = 0.0
        for eu, ratio in non_sh_ratios.items():
            eu_therms = sh_upc * ratio
            row_data[eu] = round(eu_therms, 1)
            non_heating_total += eu_therms
        
        row_data['estimated_total_upc'] = round(sh_upc + non_heating_total, 1)
        row_data['irp_upc'] = round(irp_upc, 1) if irp_upc else None
        row_data['irp_source'] = irp_source
        row_data['non_heating_offset'] = round(non_heating_total, 1)
        row_data['diff_vs_irp'] = round(sh_upc + non_heating_total - irp_upc, 1) if irp_upc else None
        row_data['diff_vs_irp_pct'] = round((sh_upc + non_heating_total - irp_upc) / irp_upc * 100, 1) if irp_upc and irp_upc > 0 else None
        row_data['data_type'] = 'calibrated' if yr == config.base_year else 'projected'
        estimated_total_rows.append(row_data)
    
    estimated_total_df = pd.DataFrame(estimated_total_rows)

    results_df, estimated_total_df, irp_alignment_summary = _align_baseline_to_irp(
        results_df, estimated_total_df, config
    )

    logger.info(
        f"Estimated total UPC: {estimated_total_df['estimated_total_upc'].iloc[0]:.1f} → "
        f"{estimated_total_df['estimated_total_upc'].iloc[-1]:.1f} therms "
        f"(vs IRP: {estimated_total_df['irp_upc'].iloc[0]} → {estimated_total_df['irp_upc'].iloc[-1]})"
    )
    
    # Create metadata
    metadata = {
        'scenario_name': config.name,
        'base_year': config.base_year,
        'forecast_horizon': config.forecast_horizon,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'baseline_irp_alignment': config.baseline_irp_alignment,
        'irp_alignment': irp_alignment_summary,
        'weather_assumption': config.weather_assumption,
        'end_use_scope': config.end_use_scope,
        'max_premises': config.max_premises,
        'vectorized': config.vectorized,
        'total_rows': len(results_df),
        'years_simulated': config.forecast_horizon + 1,
        'end_uses': results_df['end_use'].nunique(),
        # Additional detail DataFrames for export
        '_equipment_stats': pd.DataFrame(yearly_equipment_stats),
        '_premise_distributions': pd.DataFrame(yearly_premise_distributions),
        '_segment_demand': pd.concat(yearly_segment_demand, ignore_index=True) if yearly_segment_demand else pd.DataFrame(),
        '_vintage_demand': pd.concat(yearly_vintage_demand, ignore_index=True) if yearly_vintage_demand else pd.DataFrame(),
        '_sample_rates': rates_df,
        '_estimated_total': estimated_total_df,
        '_irp_alignment': irp_alignment_summary,
        '_hdd_info': hdd_info,
        '_hdd_history': hdd_history_df,
    }
    
    logger.info(
        f"Completed scenario '{config.name}': "
        f"{len(results_df)} result rows, "
        f"{config.forecast_horizon + 1} years, "
        f"{results_df['end_use'].nunique()} end-uses"
    )
    
    return results_df, metadata


def compare_scenarios(
    scenario_results: List[Tuple[pd.DataFrame, Dict[str, Any]]],
    output_dir: Optional[str] = None
) -> pd.DataFrame:
    """
    Merge results from multiple scenario runs into a comparison DataFrame.
    
    Combines results from multiple scenarios into a single DataFrame with
    consistent columns for side-by-side comparison.
    
    Args:
        scenario_results: List of (results_df, metadata) tuples from run_scenario
        output_dir: Optional directory to save comparison results
    
    Returns:
        DataFrame with columns:
            - year: Simulation year
            - end_use: End-use category
            - scenario_name: Scenario identifier
            - total_therms: Total demand (therms)
            - use_per_customer: Use per customer (therms/customer)
            - premise_count: Number of premises
        
        Sorted by year, scenario_name, end_use
    
    Raises:
        ValueError: If scenario_results is empty
    """
    if not scenario_results:
        raise ValueError("scenario_results list is empty")
    
    output_dir = Path(output_dir or OUTPUT_DIR) / 'scenarios'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Combine all scenario results, adding scenario_name from metadata if not in results
    all_dfs = []
    for results_df, metadata in scenario_results:
        df = results_df.copy()
        # Add scenario_name from metadata if not already in results
        if 'scenario_name' not in df.columns:
            df['scenario_name'] = metadata.get('scenario_name', 'unknown')
        all_dfs.append(df)
    
    comparison_df = pd.concat(all_dfs, ignore_index=True)
    
    # Ensure consistent column order and types
    required_cols = ['year', 'end_use', 'scenario_name', 'total_therms', 'use_per_customer', 'premise_count']
    # Only select columns that exist
    cols_to_select = [col for col in required_cols if col in comparison_df.columns]
    comparison_df = comparison_df[cols_to_select]
    
    comparison_df['year'] = comparison_df['year'].astype(int)
    comparison_df['total_therms'] = comparison_df['total_therms'].astype(float)
    comparison_df['use_per_customer'] = comparison_df['use_per_customer'].astype(float)
    comparison_df['premise_count'] = comparison_df['premise_count'].astype(int)
    
    # Sort for consistent output
    comparison_df = comparison_df.sort_values(['year', 'scenario_name', 'end_use']).reset_index(drop=True)
    
    logger.info(
        f"Compared {len(scenario_results)} scenarios: "
        f"{len(comparison_df)} total rows, "
        f"years {comparison_df['year'].min()}-{comparison_df['year'].max()}, "
        f"scenarios: {', '.join(comparison_df['scenario_name'].unique())}"
    )
    
    return comparison_df
