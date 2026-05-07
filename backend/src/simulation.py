"""
End-use energy simulation module for NW Natural End-Use Forecasting Model.

Provides functions for simulating annual energy consumption by end-use:
- Space heating (weather-driven via HDD)
- Water heating (weather-driven via temperature delta)
- Baseload (flat annual consumption)

Each function takes equipment characteristics and weather data to compute
annual therms consumed for that end-use.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
import logging

from src import config
from src.equipment import EquipmentProfile

logger = logging.getLogger(__name__)


def simulate_space_heating(
    equipment: EquipmentProfile,
    annual_hdd: float,
    heating_factor: float = 1.0
) -> float:
    """
    Simulate annual space heating consumption.
    
    Space heating demand is driven by Heating Degree Days (HDD) and equipment efficiency.
    
    Formula:
        annual_therms = (annual_hdd * heating_factor) / efficiency
    
    Where:
    - annual_hdd: Total heating degree days for the year (base 65°F)
    - heating_factor: Scaling factor to convert HDD to therms (accounts for building envelope, etc.)
    - efficiency: Equipment efficiency (AFUE for furnaces, COP for heat pumps)
    
    Args:
        equipment: EquipmentProfile with efficiency and fuel_type
        annual_hdd: Annual HDD total (float, >= 0)
        heating_factor: Scaling factor from HDD to therms (default 1.0)
                       Typical range: 0.5-2.0 depending on building envelope
    
    Returns:
        Annual space heating consumption in therms (float, >= 0)
    
    Raises:
        ValueError: If annual_hdd < 0 or heating_factor <= 0
        TypeError: If equipment is not an EquipmentProfile
    """
    if not isinstance(equipment, EquipmentProfile):
        raise TypeError(f"equipment must be EquipmentProfile, got {type(equipment)}")
    
    if annual_hdd < 0:
        raise ValueError(f"annual_hdd must be >= 0, got {annual_hdd}")
    
    if heating_factor <= 0:
        raise ValueError(f"heating_factor must be > 0, got {heating_factor}")
    
    # Efficiency must be positive
    if equipment.efficiency <= 0:
        logger.warning(
            f"Equipment {equipment.equipment_type_code} has invalid efficiency "
            f"{equipment.efficiency}, using default"
        )
        efficiency = config.DEFAULT_EFFICIENCY.get(equipment.end_use, 0.80)
    else:
        efficiency = equipment.efficiency
    
    # Compute therms: HDD * factor / efficiency
    # Higher efficiency -> lower therms (inverse relationship)
    annual_therms = (annual_hdd * heating_factor) / efficiency
    
    # Ensure non-negative result
    annual_therms = max(0.0, annual_therms)
    
    return float(annual_therms)


def simulate_water_heating(
    equipment: EquipmentProfile,
    delta_t: float,
    gallons_per_day: float = 64.0
) -> float:
    """
    Simulate annual water heating consumption.
    
    Water heating demand is driven by the temperature rise needed to heat
    incoming cold water to target hot water temperature.
    
    Formula:
        annual_therms = (gallons_per_day * delta_t * days_per_year) / (efficiency * BTU_per_therm)
    
    Where:
    - gallons_per_day: Daily hot water consumption (gallons)
    - delta_t: Temperature rise needed (°F) = target_temp - cold_water_temp
    - efficiency: Equipment efficiency (EF for water heaters)
    - BTU_per_therm: 100,000 BTU/therm (standard conversion)
    - days_per_year: 365 days
    
    Simplified formula (using standard conversion factors):
        annual_therms = (gallons_per_day * delta_t * 365) / (efficiency * 100000)
    
    Args:
        equipment: EquipmentProfile with efficiency and fuel_type
        delta_t: Temperature rise in Fahrenheit (float, > 0)
        gallons_per_day: Daily hot water consumption in gallons (default 64.0)
    
    Returns:
        Annual water heating consumption in therms (float, >= 0)
    
    Raises:
        ValueError: If delta_t <= 0 or gallons_per_day <= 0
        TypeError: If equipment is not an EquipmentProfile
    """
    if not isinstance(equipment, EquipmentProfile):
        raise TypeError(f"equipment must be EquipmentProfile, got {type(equipment)}")
    
    if delta_t <= 0:
        raise ValueError(f"delta_t must be > 0, got {delta_t}")
    
    if gallons_per_day <= 0:
        raise ValueError(f"gallons_per_day must be > 0, got {gallons_per_day}")
    
    # Efficiency must be positive
    if equipment.efficiency <= 0:
        logger.warning(
            f"Equipment {equipment.equipment_type_code} has invalid efficiency "
            f"{equipment.efficiency}, using default"
        )
        efficiency = config.DEFAULT_EFFICIENCY.get(equipment.end_use, 0.60)
    else:
        efficiency = equipment.efficiency
    
    # Standard conversion: 1 therm = 100,000 BTU
    # Energy to heat water: BTU = gallons * 8.34 lb/gal * 1 BTU/lb/°F * delta_t
    # Simplified: BTU per gallon per degree = 8.34
    BTU_PER_GALLON_PER_DEGREE = 8.34
    BTU_PER_THERM = 100000.0
    DAYS_PER_YEAR = 365.0
    
    # Compute annual therms
    annual_btu = gallons_per_day * BTU_PER_GALLON_PER_DEGREE * delta_t * DAYS_PER_YEAR
    annual_therms = annual_btu / (efficiency * BTU_PER_THERM)
    
    # Ensure non-negative result
    annual_therms = max(0.0, annual_therms)
    
    return float(annual_therms)


def simulate_baseload(
    equipment: EquipmentProfile,
    annual_consumption: float
) -> float:
    """
    Simulate annual baseload (non-weather-sensitive) consumption.
    
    Baseload end-uses (cooking, drying, fireplaces, other) consume a relatively
    constant amount of energy year-round, independent of weather.
    
    Formula:
        annual_therms = annual_consumption / efficiency
    
    Where:
    - annual_consumption: Base annual consumption in therms (before efficiency adjustment)
    - efficiency: Equipment efficiency
    
    Args:
        equipment: EquipmentProfile with efficiency and fuel_type
        annual_consumption: Base annual consumption in therms (float, >= 0)
    
    Returns:
        Annual baseload consumption in therms (float, >= 0)
    
    Raises:
        ValueError: If annual_consumption < 0
        TypeError: If equipment is not an EquipmentProfile
    """
    if not isinstance(equipment, EquipmentProfile):
        raise TypeError(f"equipment must be EquipmentProfile, got {type(equipment)}")
    
    if annual_consumption < 0:
        raise ValueError(f"annual_consumption must be >= 0, got {annual_consumption}")
    
    # Efficiency must be positive
    if equipment.efficiency <= 0:
        logger.warning(
            f"Equipment {equipment.equipment_type_code} has invalid efficiency "
            f"{equipment.efficiency}, using default"
        )
        efficiency = config.DEFAULT_EFFICIENCY.get(equipment.end_use, 0.70)
    else:
        efficiency = equipment.efficiency
    
    # Compute therms: consumption / efficiency
    # Higher efficiency -> lower therms (inverse relationship)
    annual_therms = annual_consumption / efficiency
    
    # Ensure non-negative result
    annual_therms = max(0.0, annual_therms)
    
    return float(annual_therms)



def simulate_all_end_uses(
    premise_equipment: pd.DataFrame,
    weather_data: pd.DataFrame,
    water_temp_data: pd.DataFrame,
    baseload_factors: Dict[str, float],
    year: int = config.BASE_YEAR,
    heating_factor: float = 1.0,
    target_hot_water_temp: float = config.DEFAULT_HOT_WATER_TEMP,
    gallons_per_day: float = config.DEFAULT_DAILY_HOT_WATER_GALLONS
) -> pd.DataFrame:
    """
    Orchestrate end-use energy simulation for all premises and end-uses.
    
    This function:
    1. Iterates through each premise and its equipment
    2. Assigns weather station based on district
    3. Retrieves weather data (HDD, delta-T) for that station
    4. Dispatches to appropriate simulation function (space_heating, water_heating, baseload)
    5. Returns aggregated results by premise and end-use
    
    Args:
        premise_equipment: DataFrame with columns:
            - blinded_id: Premise identifier
            - equipment_type_code: Equipment code
            - end_use: End-use category (space_heating, water_heating, cooking, etc.)
            - efficiency: Equipment efficiency (0-1 range)
            - install_year: Year installed
            - useful_life: Equipment useful life (years)
            - fuel_type: Fuel type (natural_gas, electric, etc.)
            - district_code_IRP: District code for weather station assignment
        
        weather_data: DataFrame with columns:
            - site_id: Weather station ICAO code (e.g., 'KPDX')
            - date: Date (datetime)
            - daily_avg_temp: Daily average temperature (°F)
        
        water_temp_data: DataFrame with columns:
            - date: Date (datetime)
            - cold_water_temp: Cold water temperature (°F)
        
        baseload_factors: Dictionary mapping end_use -> annual_consumption (therms)
            Example: {'cooking': 30.0, 'clothes_drying': 20.0, 'fireplace': 55.0}
        
        year: Calendar year for simulation (default: BASE_YEAR)
        
        heating_factor: Scaling factor for space heating (default 1.0)
            Accounts for building envelope characteristics
        
        target_hot_water_temp: Target hot water temperature in °F (default 120°F)
        
        gallons_per_day: Daily hot water consumption in gallons (default 64.0)
    
    Returns:
        DataFrame with columns:
            - blinded_id: Premise identifier
            - end_use: End-use category
            - annual_therms: Simulated annual consumption (therms)
            - efficiency: Equipment efficiency used
            - year: Simulation year
        
        One row per premise per end-use (no double-counting).
        Rows with zero therms are included (non-negative constraint).
    
    Raises:
        ValueError: If required columns missing from input DataFrames
        KeyError: If district_code_IRP not found in DISTRICT_WEATHER_MAP
    """
    from src.weather import compute_annual_hdd, compute_water_heating_delta, assign_weather_station
    
    # Validate input DataFrames
    required_premise_cols = {
        'blinded_id', 'equipment_type_code', 'end_use', 'efficiency',
        'install_year', 'useful_life', 'fuel_type', 'district_code_IRP'
    }
    if not required_premise_cols.issubset(premise_equipment.columns):
        missing = required_premise_cols - set(premise_equipment.columns)
        raise ValueError(f"premise_equipment missing columns: {missing}")
    
    required_weather_cols = {'site_id', 'date', 'daily_avg_temp'}
    if not required_weather_cols.issubset(weather_data.columns):
        missing = required_weather_cols - set(weather_data.columns)
        raise ValueError(f"weather_data missing columns: {missing}")
    
    required_water_cols = {'date', 'cold_water_temp'}
    if not required_water_cols.issubset(water_temp_data.columns):
        missing = required_water_cols - set(water_temp_data.columns)
        raise ValueError(f"water_temp_data missing columns: {missing}")
    
    # Ensure date columns are datetime
    weather_data = weather_data.copy()
    water_temp_data = water_temp_data.copy()
    weather_data['date'] = pd.to_datetime(weather_data['date'])
    water_temp_data['date'] = pd.to_datetime(water_temp_data['date'])
    
    results = []
    
    # Group by premise to avoid redundant weather lookups
    for blinded_id, premise_group in premise_equipment.groupby('blinded_id'):
        # Get district code (should be same for all equipment in premise)
        district_code = premise_group['district_code_IRP'].iloc[0]
        
        # Assign weather station
        try:
            weather_station = assign_weather_station(district_code)
        except KeyError as e:
            logger.warning(f"Premise {blinded_id}: {e}")
            continue
        
        # Compute annual HDD for this premise's weather station
        try:
            annual_hdd = compute_annual_hdd(weather_data, weather_station, year)
        except ValueError as e:
            logger.warning(f"Premise {blinded_id} ({weather_station}): {e}")
            annual_hdd = 0.0
        
        # Compute water heating delta-T
        try:
            delta_t = compute_water_heating_delta(water_temp_data, target_hot_water_temp, year)
        except ValueError as e:
            logger.warning(f"Premise {blinded_id}: {e}")
            delta_t = 0.0
        
        # Simulate each end-use for this premise
        for _, row in premise_group.iterrows():
            equipment = EquipmentProfile(
                equipment_type_code=row['equipment_type_code'],
                end_use=row['end_use'],
                efficiency=row['efficiency'],
                install_year=row['install_year'],
                useful_life=row['useful_life'],
                fuel_type=row['fuel_type']
            )
            
            end_use = row['end_use']
            
            # Dispatch to appropriate simulation function
            if end_use == 'space_heating':
                annual_therms = simulate_space_heating(equipment, annual_hdd, heating_factor)
            
            elif end_use == 'water_heating':
                annual_therms = simulate_water_heating(
                    equipment, delta_t, gallons_per_day
                )
            
            elif end_use in baseload_factors:
                # Baseload end-uses: cooking, clothes_drying, fireplace, other
                base_consumption = baseload_factors[end_use]
                annual_therms = simulate_baseload(equipment, base_consumption)
            
            else:
                # Unknown end-use: log warning and skip
                logger.warning(f"Unknown end-use '{end_use}' for premise {blinded_id}")
                continue
            
            # Append result
            results.append({
                'blinded_id': blinded_id,
                'end_use': end_use,
                'annual_therms': annual_therms,
                'efficiency': equipment.efficiency,
                'year': year
            })
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    if results_df.empty:
        logger.warning("No simulation results generated")
        return pd.DataFrame(columns=['blinded_id', 'end_use', 'annual_therms', 'efficiency', 'year'])
    
    return results_df


def simulate_all_end_uses_vectorized(
    premise_equipment: pd.DataFrame,
    weather_data: pd.DataFrame,
    water_temp_data: pd.DataFrame,
    baseload_factors: Dict[str, float],
    year: int = config.BASE_YEAR,
    heating_factor: float = 1.0,
    target_hot_water_temp: float = config.DEFAULT_HOT_WATER_TEMP,
    gallons_per_day: float = config.DEFAULT_DAILY_HOT_WATER_GALLONS
) -> pd.DataFrame:
    """
    Vectorized end-use simulation — same logic as simulate_all_end_uses but
    uses pandas operations instead of row-by-row iteration. Orders of magnitude
    faster for large datasets.
    
    Returns DataFrame with columns: blinded_id, end_use, annual_therms, efficiency, year
    """
    from src.weather import compute_hdd, assign_weather_station

    df = premise_equipment.copy()

    # Filter to rows with valid end_use
    df = df[df['end_use'].notna() & (df['end_use'] != '')].copy()
    if df.empty:
        return pd.DataFrame(columns=['blinded_id', 'end_use', 'annual_therms', 'efficiency', 'year'])

    # Ensure weather_station column exists
    if 'weather_station' not in df.columns:
        df['weather_station'] = df['district_code_IRP'].map(config.DISTRICT_WEATHER_MAP)

    # --- Compute annual HDD per weather station ---
    weather_data = weather_data.copy()
    weather_data['date'] = pd.to_datetime(weather_data['date'], errors='coerce')
    weather_data['_year'] = weather_data['date'].dt.year
    
    # Use target year's weather if available; otherwise fall back to most recent full year
    year_weather = weather_data[weather_data['_year'] == year].copy()
    if year_weather.empty or len(year_weather) < 100:
        # Find the most recent year with substantial data (>300 days)
        year_counts = weather_data.groupby('_year').size()
        full_years = year_counts[year_counts > 300].index
        if len(full_years) > 0:
            fallback_year = int(full_years.max())
            logger.info(f"No weather data for {year}; using {fallback_year} as proxy")
            year_weather = weather_data[weather_data['_year'] == fallback_year].copy()
        else:
            logger.warning(f"No suitable weather data found for any year")
    
    year_weather['hdd'] = (65.0 - year_weather['daily_avg_temp']).clip(lower=0)
    station_hdd = year_weather.groupby('site_id')['hdd'].sum()
    logger.info(f"Annual HDD by station for {year}: {dict(list(station_hdd.items())[:3])}... ({len(station_hdd)} stations)")

    # Map station HDD to each equipment row
    df['annual_hdd'] = df['weather_station'].map(station_hdd).fillna(0)

    # --- Compute water heating delta-T ---
    water_temp_data = water_temp_data.copy()
    water_temp_data['date'] = pd.to_datetime(water_temp_data['date'], errors='coerce')
    year_water = water_temp_data[water_temp_data['date'].dt.year == year]
    if not year_water.empty and 'cold_water_temp' in year_water.columns:
        avg_cold = year_water['cold_water_temp'].mean()
    else:
        # Fall back to all years if target year not available
        avg_cold = water_temp_data['cold_water_temp'].mean() if 'cold_water_temp' in water_temp_data.columns else config.DEFAULT_COLD_WATER_TEMP
    delta_t = target_hot_water_temp - avg_cold
    logger.info(f"Water heating delta_t for {year}: {delta_t:.1f}°F (cold={avg_cold:.1f}°F)")

    # --- Ensure efficiency is valid ---
    df['efficiency'] = pd.to_numeric(df['efficiency'], errors='coerce').fillna(0.7)
    df.loc[df['efficiency'] <= 0, 'efficiency'] = 0.7

    # --- Compute vintage and segment heating multipliers ---
    vintage_mult = pd.Series(1.0, index=df.index, dtype='float64')
    if 'setyear' in df.columns:
        sy = pd.to_numeric(df['setyear'], errors='coerce')
        for (yr_min, yr_max), mult in config.VINTAGE_HEATING_MULTIPLIER.items():
            mask = (sy >= yr_min) & (sy <= yr_max)
            vintage_mult[mask] = mult
    
    segment_mult = pd.Series(1.0, index=df.index, dtype='float64')
    if 'segment' in df.columns:
        for seg, mult in config.SEGMENT_HEATING_MULTIPLIER.items():
            segment_mult[df['segment'] == seg] = mult
    
    combined_mult = vintage_mult * segment_mult

    # --- Compute therms by end-use using a results series ---
    therms = pd.Series(0.0, index=df.index, dtype='float64')

    # Space heating: therms = (annual_hdd * heating_factor * vintage_mult * segment_mult) / efficiency
    mask_sh = df['end_use'] == 'space_heating'
    if mask_sh.any():
        therms[mask_sh] = (
            df.loc[mask_sh, 'annual_hdd'].astype(float) * heating_factor
            * combined_mult[mask_sh].values
            / df.loc[mask_sh, 'efficiency'].astype(float)
        ).values

    # Water heating: therms = (gallons/day * 8.34 * delta_t * 365) / (efficiency * 100000)
    mask_wh = df['end_use'] == 'water_heating'
    if mask_wh.any():
        therms[mask_wh] = (
            gallons_per_day * 8.34 * delta_t * 365.0
            / (df.loc[mask_wh, 'efficiency'].astype(float) * 100000.0)
        ).values

    # Baseload end-uses: therms = annual_consumption / efficiency
    for end_use, base_consumption in baseload_factors.items():
        if end_use in ('space_heating', 'water_heating') or base_consumption == 0:
            continue
        mask = df['end_use'] == end_use
        if mask.any():
            therms[mask] = (base_consumption / df.loc[mask, 'efficiency'].astype(float)).values

    # Ensure non-negative
    therms = therms.clip(lower=0)
    df['annual_therms'] = therms

    # Build result
    df['year'] = year
    result = df[['blinded_id', 'end_use', 'annual_therms', 'efficiency', 'year']].copy()

    logger.info(
        f"Vectorized simulation for {year}: {len(result)} rows, "
        f"total_therms={result['annual_therms'].sum():,.0f}, "
        f"premises={result['blinded_id'].nunique()}"
    )

    return result


def simulate_monthly_vectorized(
    premise_equipment: pd.DataFrame,
    weather_data: pd.DataFrame,
    water_temp_data: pd.DataFrame,
    baseload_factors: Dict[str, float],
    year: int = config.BASE_YEAR,
    heating_factor: float = 1.0,
    target_hot_water_temp: float = config.DEFAULT_HOT_WATER_TEMP,
    gallons_per_day: float = config.DEFAULT_DAILY_HOT_WATER_GALLONS
) -> pd.DataFrame:
    """
    Monthly vectorized simulation — computes therms per premise per end-use per month.
    Same logic as annual but sums HDD by month instead of by year.
    
    Returns DataFrame with columns: blinded_id, end_use, month, annual_therms, efficiency, year
    """
    from src.weather import compute_hdd

    df = premise_equipment.copy()
    df = df[df['end_use'].notna() & (df['end_use'] != '')].copy()
    if df.empty:
        return pd.DataFrame(columns=['blinded_id', 'end_use', 'month', 'annual_therms', 'efficiency', 'year'])

    if 'weather_station' not in df.columns:
        df['weather_station'] = df['district_code_IRP'].map(config.DISTRICT_WEATHER_MAP)

    # --- Compute monthly HDD per weather station ---
    wd = weather_data.copy()
    wd['date'] = pd.to_datetime(wd['date'], errors='coerce')
    wd['_year'] = wd['date'].dt.year
    wd['_month'] = wd['date'].dt.month

    year_weather = wd[wd['_year'] == year].copy()
    months_covered = year_weather['_month'].nunique() if not year_weather.empty else 0
    if year_weather.empty or months_covered < 12:
        # Find the most recent year with all 12 months of data
        months_per_year = wd.groupby('_year')['_month'].nunique()
        full_years = months_per_year[months_per_year >= 12].index
        if len(full_years) > 0:
            fallback_year = int(full_years.max())
            logger.info(f"Weather for {year} has only {months_covered} months; using {fallback_year} (12 months)")
            year_weather = wd[wd['_year'] == fallback_year].copy()
        else:
            logger.warning(f"No year with 12 months of weather data found")

    year_weather['hdd'] = (65.0 - year_weather['daily_avg_temp']).clip(lower=0)
    # Monthly HDD: station × month
    station_month_hdd = year_weather.groupby(['site_id', '_month'])['hdd'].sum().reset_index()
    station_month_hdd.columns = ['site_id', 'month', 'monthly_hdd']

    # --- Compute monthly water heating delta-T ---
    wtd = water_temp_data.copy()
    wtd['date'] = pd.to_datetime(wtd['date'], errors='coerce')
    wtd['_year'] = wtd['date'].dt.year
    wtd['_month'] = wtd['date'].dt.month
    year_water = wtd[wtd['_year'] == year]
    if year_water.empty:
        year_water = wtd  # fall back to all years
    monthly_cold = year_water.groupby('_month')['cold_water_temp'].mean() if 'cold_water_temp' in year_water.columns else pd.Series(dtype=float)

    # --- Ensure efficiency is valid ---
    df['efficiency'] = pd.to_numeric(df['efficiency'], errors='coerce').fillna(0.7)
    df.loc[df['efficiency'] <= 0, 'efficiency'] = 0.7

    # --- Monthly baseload load shapes ---
    monthly_load_shapes = {
        'cooking': {1: 0.085, 2: 0.078, 3: 0.082, 4: 0.080, 5: 0.082,
                    6: 0.078, 7: 0.080, 8: 0.082, 9: 0.080, 10: 0.085,
                    11: 0.090, 12: 0.098},
        'clothes_drying': {1: 0.092, 2: 0.088, 3: 0.088, 4: 0.082, 5: 0.078,
                           6: 0.072, 7: 0.070, 8: 0.072, 9: 0.078, 10: 0.082,
                           11: 0.088, 12: 0.092},
        'fireplace': {1: 0.200, 2: 0.180, 3: 0.120, 4: 0.040, 5: 0.010,
                      6: 0.000, 7: 0.000, 8: 0.000, 9: 0.010, 10: 0.060,
                      11: 0.150, 12: 0.230},
        'other': {m: 1.0/12 for m in range(1, 13)},
    }
    days_in_month = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
                     7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}

    # --- Compute vintage and segment heating multipliers ---
    vintage_mult = pd.Series(1.0, index=df.index, dtype='float64')
    if 'setyear' in df.columns:
        sy = pd.to_numeric(df['setyear'], errors='coerce')
        for (yr_min, yr_max), mult in config.VINTAGE_HEATING_MULTIPLIER.items():
            mask = (sy >= yr_min) & (sy <= yr_max)
            vintage_mult[mask] = mult
    
    segment_mult = pd.Series(1.0, index=df.index, dtype='float64')
    if 'segment' in df.columns:
        for seg, mult in config.SEGMENT_HEATING_MULTIPLIER.items():
            segment_mult[df['segment'] == seg] = mult
    
    combined_mult = vintage_mult * segment_mult

    # --- Build monthly results ---
    all_months = []

    for month in range(1, 13):
        month_df = df.copy()
        month_df['month'] = month

        # Space heating: therms = (monthly_hdd × heating_factor × multipliers) / efficiency
        month_hdd = station_month_hdd[station_month_hdd['month'] == month].set_index('site_id')['monthly_hdd']
        month_df['monthly_hdd'] = month_df['weather_station'].map(month_hdd).fillna(0)

        therms = pd.Series(0.0, index=month_df.index, dtype='float64')

        mask_sh = month_df['end_use'] == 'space_heating'
        if mask_sh.any():
            therms[mask_sh] = (
                month_df.loc[mask_sh, 'monthly_hdd'].astype(float) * heating_factor
                * combined_mult[mask_sh].values
                / month_df.loc[mask_sh, 'efficiency'].astype(float)
            ).values

        # Water heating: therms = (gallons/day × 8.34 × delta_t × days) / (eff × 100000)
        mask_wh = month_df['end_use'] == 'water_heating'
        if mask_wh.any():
            cold_temp = monthly_cold.get(month, config.DEFAULT_COLD_WATER_TEMP)
            delta_t = target_hot_water_temp - cold_temp
            days = days_in_month[month]
            therms[mask_wh] = (
                gallons_per_day * 8.34 * delta_t * days
                / (month_df.loc[mask_wh, 'efficiency'].astype(float) * 100000.0)
            ).values

        # Baseload end-uses: therms = annual_consumption × monthly_shape / efficiency
        for end_use, base_consumption in baseload_factors.items():
            if end_use in ('space_heating', 'water_heating') or base_consumption == 0:
                continue
            mask = month_df['end_use'] == end_use
            if mask.any():
                shape = monthly_load_shapes.get(end_use, {}).get(month, 1.0/12)
                therms[mask] = (
                    base_consumption * shape / month_df.loc[mask, 'efficiency'].astype(float)
                ).values

        therms = therms.clip(lower=0)
        month_df['annual_therms'] = therms  # column name kept for compatibility
        month_df['year'] = year

        all_months.append(month_df[['blinded_id', 'end_use', 'month', 'annual_therms', 'efficiency', 'year']])

    result = pd.concat(all_months, ignore_index=True)

    total = result['annual_therms'].sum()
    logger.info(
        f"Monthly simulation for {year}: {len(result)} rows (12 months), "
        f"total_therms={total:,.0f}, premises={result['blinded_id'].nunique()}"
    )

    return result
