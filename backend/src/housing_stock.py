"""
Housing stock module for NW Natural end-use forecasting model.

Defines the HousingStock dataclass and provides functions to construct
and project residential housing stock from premise-equipment data.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def _compute_housing_age_by_district(premises: pd.DataFrame, base_year: int) -> Dict[str, float]:
    """
    Compute average housing age by district.
    
    For testing purposes, generates synthetic housing age data based on district.
    In production, this would be computed from actual housing vintage data.
    
    Args:
        premises: DataFrame with premise-level data
        base_year: The current year
    
    Returns:
        Dict mapping district code to average housing age (years)
    """
    housing_age = {}
    
    if 'district_code_IRP' not in premises.columns:
        return housing_age
    
    # Generate synthetic housing age data based on district
    # Assumes different districts have different average housing ages
    district_age_map = {
        'D1': 35, 'D2': 40, 'D3': 30, 'D4': 45, 'D5': 25,
        'D6': 38, 'D7': 42, 'D8': 28, 'D9': 50, 'D10': 32,
    }
    
    for district in premises['district_code_IRP'].unique():
        # Use mapped age or default to 35 years
        housing_age[district] = district_age_map.get(district, 35)
    
    return housing_age


def _compute_vintage_distribution_by_district(premises: pd.DataFrame, base_year: int) -> Dict[str, Dict[str, float]]:
    """
    Compute vintage distribution by district.
    
    For testing purposes, generates synthetic vintage distribution data.
    In production, this would be computed from actual housing vintage data.
    
    Args:
        premises: DataFrame with premise-level data
        base_year: The current year
    
    Returns:
        Dict mapping district code to vintage era percentages (pre-1980, 1980-2000, 2000-2010, 2010+)
    """
    vintage_dist = {}
    
    if 'district_code_IRP' not in premises.columns:
        return vintage_dist
    
    # Generate synthetic vintage distribution data
    # Assumes different districts have different vintage distributions
    district_vintage_map = {
        'D1': {'pre-1980': 0.45, '1980-2000': 0.30, '2000-2010': 0.15, '2010+': 0.10},
        'D2': {'pre-1980': 0.50, '1980-2000': 0.28, '2000-2010': 0.14, '2010+': 0.08},
        'D3': {'pre-1980': 0.35, '1980-2000': 0.35, '2000-2010': 0.20, '2010+': 0.10},
        'D4': {'pre-1980': 0.55, '1980-2000': 0.25, '2000-2010': 0.12, '2010+': 0.08},
        'D5': {'pre-1980': 0.25, '1980-2000': 0.40, '2000-2010': 0.25, '2010+': 0.10},
    }
    
    for district in premises['district_code_IRP'].unique():
        # Use mapped distribution or default
        vintage_dist[district] = district_vintage_map.get(
            district,
            {'pre-1980': 0.40, '1980-2000': 0.30, '2000-2010': 0.20, '2010+': 0.10}
        )
    
    return vintage_dist


def _compute_replacement_probability_by_district(premises: pd.DataFrame, base_year: int) -> Dict[str, float]:
    """
    Compute replacement probability by district.
    
    For testing purposes, generates synthetic replacement probability data.
    In production, this would be computed from equipment age and Weibull survival model.
    
    Args:
        premises: DataFrame with premise-level data
        base_year: The current year
    
    Returns:
        Dict mapping district code to replacement probability [0, 1]
    """
    replacement_prob = {}
    
    if 'district_code_IRP' not in premises.columns:
        return replacement_prob
    
    # Generate synthetic replacement probability data based on district
    # Assumes different districts have different replacement probabilities
    district_prob_map = {
        'D1': 0.15, 'D2': 0.18, 'D3': 0.12, 'D4': 0.20, 'D5': 0.10,
        'D6': 0.16, 'D7': 0.19, 'D8': 0.11, 'D9': 0.22, 'D10': 0.13,
    }
    
    for district in premises['district_code_IRP'].unique():
        # Use mapped probability or default to 0.15
        replacement_prob[district] = district_prob_map.get(district, 0.15)
    
    return replacement_prob


@dataclass
class HousingStock:
    """
    Represents the residential housing stock for a given year.
    
    Attributes:
        year: The year this housing stock represents
        premises: DataFrame with premise-level data (one row per unique blinded_id)
        total_units: Total number of residential units
        units_by_segment: Dict mapping segment code to unit count
        units_by_district: Dict mapping district code to unit count
        housing_age_by_district: Dict mapping district code to average housing age (years)
        vintage_distribution_by_district: Dict mapping district code to vintage era percentages
        replacement_probability_by_district: Dict mapping district code to replacement probability [0,1]
    """
    year: int
    premises: pd.DataFrame
    total_units: int
    units_by_segment: Dict[str, int] = field(default_factory=dict)
    units_by_district: Dict[str, int] = field(default_factory=dict)
    housing_age_by_district: Dict[str, float] = field(default_factory=dict)
    vintage_distribution_by_district: Dict[str, Dict[str, float]] = field(default_factory=dict)
    replacement_probability_by_district: Dict[str, float] = field(default_factory=dict)


def build_baseline_stock(premise_equipment: pd.DataFrame, base_year: int) -> HousingStock:
    """
    Construct baseline housing stock from premise-equipment data.
    
    Aggregates premise-level data to compute total units and distributions
    by segment and district. Each unique blinded_id represents one residential unit.
    
    Args:
        premise_equipment: DataFrame from build_premise_equipment_table with columns:
            - blinded_id: Unique premise identifier
            - segment_code: Customer segment (e.g., 'RESSF', 'RESMF')
            - district_code_IRP: IRP district code
            - (other premise/equipment columns)
        base_year: The year for this baseline stock
    
    Returns:
        HousingStock object with computed total_units, units_by_segment, units_by_district
    
    Raises:
        ValueError: If premise_equipment is empty or missing required columns
    """
    if premise_equipment.empty:
        raise ValueError("premise_equipment DataFrame is empty")
    
    required_cols = {'blinded_id', 'district_code_IRP'}
    missing_cols = required_cols - set(premise_equipment.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Support both 'segment_code' and 'segment' column names
    segment_col = 'segment_code' if 'segment_code' in premise_equipment.columns else 'segment'
    if segment_col not in premise_equipment.columns:
        raise ValueError("Missing segment column (expected 'segment_code' or 'segment')")
    
    # Get unique premises (one row per blinded_id)
    premises = premise_equipment.drop_duplicates(subset=['blinded_id']).copy()
    
    # Compute total units
    total_units = len(premises)
    
    # Compute units by segment
    units_by_segment = premises[segment_col].value_counts().to_dict()
    
    # Compute units by district
    units_by_district = premises['district_code_IRP'].value_counts().to_dict()
    
    # Compute housing age by district (synthetic data for now)
    housing_age_by_district = _compute_housing_age_by_district(premises, base_year)
    
    # Compute vintage distribution by district (synthetic data for now)
    vintage_distribution_by_district = _compute_vintage_distribution_by_district(premises, base_year)
    
    # Compute replacement probability by district (synthetic data for now)
    replacement_probability_by_district = _compute_replacement_probability_by_district(premises, base_year)
    
    logger.info(
        f"Built baseline housing stock for year {base_year}: "
        f"total_units={total_units}, "
        f"segments={len(units_by_segment)}, "
        f"districts={len(units_by_district)}"
    )
    
    return HousingStock(
        year=base_year,
        premises=premises,
        total_units=total_units,
        units_by_segment=units_by_segment,
        units_by_district=units_by_district,
        housing_age_by_district=housing_age_by_district,
        vintage_distribution_by_district=vintage_distribution_by_district,
        replacement_probability_by_district=replacement_probability_by_district
    )


def project_stock(baseline: HousingStock, target_year: int, scenario: dict) -> HousingStock:
    """
    Project housing stock to a future year with demolition and segment shift.
    
    Applies:
    1. Demolition: removes a fraction of existing stock (oldest homes first)
    2. New construction: adds units at housing_growth_rate + replacement of demolished
    3. Segment shift: new construction has a different SF/MF mix than existing stock
    
    Args:
        baseline: HousingStock object representing the baseline year
        target_year: The year to project to
        scenario: Dictionary with scenario parameters:
            - 'housing_growth_rate': float, annual net growth rate
            - 'base_year': int, the baseline year
            - 'demolition_rate': float, annual demolition rate (default 0.002 = 0.2%)
            - 'new_construction_mf_share': float, MF share of new construction (default 0.37)
    """
    if target_year == baseline.year:
        raise ValueError(f"target_year ({target_year}) must be != baseline.year ({baseline.year})")
    
    required_scenario_keys = {'housing_growth_rate', 'base_year'}
    missing_keys = required_scenario_keys - set(scenario.keys())
    if missing_keys:
        raise ValueError(f"scenario missing required keys: {missing_keys}")
    
    from src import parameter_curves as pc
    growth_rate = pc.resolve(scenario['housing_growth_rate'], target_year, 0.01)
    demolition_rate = pc.resolve(scenario.get('demolition_rate', 0.002), target_year, 0.002)
    new_mf_share = scenario.get('new_construction_mf_share', 0.37)
    
    years_to_project = target_year - baseline.year
    
    # Use compound growth for total, then distribute segments
    projected_total_units = int(round(baseline.total_units * ((1 + growth_rate) ** years_to_project)))
    
    # Account for demolition: net growth = gross growth - demolition
    # But total is already net (growth_rate is net of demolition in traditional models)
    # We model demolition explicitly: demolished units are replaced by new construction
    demolished_total = int(round(baseline.total_units * demolition_rate * years_to_project))
    
    # Compute segment distribution with shift
    projected_by_segment = baseline.units_by_segment.copy()
    new_units = projected_total_units - baseline.total_units
    
    if new_units != 0 and baseline.total_units > 0:
        # Gross new = net new + demolished (demolished are replaced)
        gross_new = abs(new_units) + demolished_total if new_units > 0 else 0
        
        # Remove demolished proportionally from existing segments
        for seg in list(projected_by_segment.keys()):
            seg_share = projected_by_segment[seg] / max(sum(projected_by_segment.values()), 1)
            projected_by_segment[seg] -= int(round(demolished_total * seg_share))
        
        # Add new construction with MF shift
        if gross_new > 0:
            new_mf = int(round(gross_new * new_mf_share))
            new_sf = gross_new - new_mf
            
            # Add MF
            projected_by_segment['RESMF'] = projected_by_segment.get('RESMF', 0) + new_mf
            
            # Add SF distributed across SF-like segments
            sf_segs = [s for s in projected_by_segment if s != 'RESMF']
            sf_total = sum(projected_by_segment.get(s, 0) for s in sf_segs)
            for seg in sf_segs:
                if sf_total > 0:
                    seg_share = projected_by_segment.get(seg, 0) / sf_total
                    projected_by_segment[seg] = projected_by_segment.get(seg, 0) + int(round(new_sf * seg_share))
    
    # Distribute district changes proportionally
    projected_by_district = baseline.units_by_district.copy()
    if new_units != 0 and baseline.total_units > 0:
        for district, baseline_count in baseline.units_by_district.items():
            district_proportion = baseline_count / baseline.total_units
            projected_by_district[district] = baseline_count + int(round(new_units * district_proportion))
    
    logger.info(
        f"Projected housing stock from year {baseline.year} to {target_year}: "
        f"baseline_units={baseline.total_units}, "
        f"projected_units={projected_total_units}, "
        f"new_units={new_units}, "
        f"demolished={demolished_total}, "
        f"growth_rate={growth_rate:.4f}, "
        f"demolition_rate={demolition_rate:.4f}"
    )
    
    housing_age_by_district = _compute_housing_age_by_district(baseline.premises, target_year)
    vintage_distribution_by_district = _compute_vintage_distribution_by_district(baseline.premises, target_year)
    replacement_probability_by_district = _compute_replacement_probability_by_district(baseline.premises, target_year)
    
    return HousingStock(
        year=target_year,
        premises=baseline.premises.copy(),
        total_units=projected_total_units,
        units_by_segment=projected_by_segment,
        units_by_district=projected_by_district,
        housing_age_by_district=housing_age_by_district,
        vintage_distribution_by_district=vintage_distribution_by_district,
        replacement_probability_by_district=replacement_probability_by_district
    )
