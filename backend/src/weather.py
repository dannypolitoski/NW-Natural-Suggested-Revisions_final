"""
Weather processing module for NW Natural End-Use Forecasting Model.

Provides functions for:
- Computing Heating Degree Days (HDD) and Cooling Degree Days (CDD)
- Computing annual HDD aggregates
- Computing water heating temperature deltas
- Assigning weather stations to premises by district
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict
import logging

from src import config

logger = logging.getLogger(__name__)


def compute_hdd(daily_temps: pd.Series, base_temp: float = 65.0) -> pd.Series:
    """
    Compute Heating Degree Days (HDD) for daily temperatures.
    
    HDD = max(0, base_temp - daily_avg_temp)
    
    Args:
        daily_temps: Series of daily average temperatures (Fahrenheit)
        base_temp: Base temperature for HDD calculation (default 65°F)
    
    Returns:
        Series of daily HDD values (non-negative)
    
    Raises:
        TypeError: If daily_temps is not a pandas Series
    """
    if not isinstance(daily_temps, pd.Series):
        raise TypeError(f"daily_temps must be a pandas Series, got {type(daily_temps)}")
    
    hdd = np.maximum(0, base_temp - daily_temps)
    return pd.Series(hdd, index=daily_temps.index)


def compute_cdd(daily_temps: pd.Series, base_temp: float = 65.0) -> pd.Series:
    """
    Compute Cooling Degree Days (CDD) for daily temperatures.
    
    CDD = max(0, daily_avg_temp - base_temp)
    
    Args:
        daily_temps: Series of daily average temperatures (Fahrenheit)
        base_temp: Base temperature for CDD calculation (default 65°F)
    
    Returns:
        Series of daily CDD values (non-negative)
    
    Raises:
        TypeError: If daily_temps is not a pandas Series
    """
    if not isinstance(daily_temps, pd.Series):
        raise TypeError(f"daily_temps must be a pandas Series, got {type(daily_temps)}")
    
    cdd = np.maximum(0, daily_temps - base_temp)
    return pd.Series(cdd, index=daily_temps.index)


def compute_annual_hdd(
    weather_df: pd.DataFrame,
    site_id: str,
    year: int,
    base_temp: float = 65.0
) -> float:
    """
    Compute annual Heating Degree Days for a specific weather station and year.
    
    Sums daily HDD values for all days in the specified year at the given station.
    
    Args:
        weather_df: DataFrame with columns: site_id, date, daily_avg_temp
                   date should be datetime-like
        site_id: Weather station identifier (e.g., 'KPDX')
        year: Calendar year (e.g., 2025)
        base_temp: Base temperature for HDD calculation (default 65°F)
    
    Returns:
        Annual HDD total (float)
    
    Raises:
        ValueError: If no data found for the specified site_id and year
        TypeError: If weather_df is not a DataFrame
    """
    if not isinstance(weather_df, pd.DataFrame):
        raise TypeError(f"weather_df must be a DataFrame, got {type(weather_df)}")
    
    # Filter to specified site and year
    mask = (weather_df['site_id'] == site_id) & (weather_df['date'].dt.year == year)
    site_year_data = weather_df[mask]
    
    if site_year_data.empty:
        raise ValueError(f"No weather data found for site_id={site_id}, year={year}")
    
    # Compute HDD for each day and sum
    daily_hdd = compute_hdd(site_year_data['daily_avg_temp'], base_temp)
    annual_hdd = daily_hdd.sum()
    
    return float(annual_hdd)


def compute_water_heating_delta(
    water_temp_df: pd.DataFrame,
    target_temp: float = 120.0,
    year: Optional[int] = None
) -> float:
    """
    Compute average annual water heating temperature delta.
    
    Delta = target_temp - avg_cold_water_temp
    
    Used to estimate water heating energy demand based on the temperature
    rise needed to heat incoming cold water to target hot water temperature.
    
    Args:
        water_temp_df: DataFrame with columns: date, cold_water_temp
                      date should be datetime-like
        target_temp: Target hot water temperature (default 120°F)
        year: Optional calendar year to filter to. If None, uses all data.
    
    Returns:
        Average annual temperature delta (float, in Fahrenheit)
    
    Raises:
        ValueError: If no data found for the specified year (if provided)
        TypeError: If water_temp_df is not a DataFrame
    """
    if not isinstance(water_temp_df, pd.DataFrame):
        raise TypeError(f"water_temp_df must be a DataFrame, got {type(water_temp_df)}")
    
    # Filter to specified year if provided
    if year is not None:
        mask = water_temp_df['date'].dt.year == year
        data = water_temp_df[mask]
        if data.empty:
            raise ValueError(f"No water temperature data found for year={year}")
    else:
        data = water_temp_df
    
    # Compute average cold water temperature
    avg_cold_water_temp = data['cold_water_temp'].mean()
    
    # Compute delta
    delta = target_temp - avg_cold_water_temp
    
    return float(delta)


def assign_weather_station(district_code: str) -> str:
    """
    Assign a weather station to a premise based on its district code.
    
    Uses the DISTRICT_WEATHER_MAP from config to look up the nearest
    weather station for a given IRP district code.
    
    Args:
        district_code: IRP district code (e.g., 'MULT', 'LANE', 'CLAR')
    
    Returns:
        Weather station ICAO code (e.g., 'KPDX', 'KEUG')
    
    Raises:
        KeyError: If district_code is not found in DISTRICT_WEATHER_MAP
    """
    if district_code not in config.DISTRICT_WEATHER_MAP:
        raise KeyError(
            f"District code '{district_code}' not found in DISTRICT_WEATHER_MAP. "
            f"Valid codes: {list(config.DISTRICT_WEATHER_MAP.keys())}"
        )
    
    station = config.DISTRICT_WEATHER_MAP[district_code]
    logger.debug(f"Assigned weather station {station} to district {district_code}")
    
    return station
