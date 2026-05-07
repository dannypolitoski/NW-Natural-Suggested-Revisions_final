"""
Property-based tests for weather module HDD/CDD computation.

Tests correctness properties:
- Property 7: HDD values are always non-negative, and HDD + CDD relationship holds
- Property 8: Water heating delta_t is always positive when cold water temp < target_temp
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, assume
from datetime import datetime, timedelta

from src.weather import (
    compute_hdd,
    compute_cdd,
    compute_annual_hdd,
    compute_water_heating_delta,
    assign_weather_station,
)
from src import config


class TestHDDCDDComputation:
    """Test HDD and CDD computation functions."""
    
    def test_compute_hdd_basic(self):
        """Test basic HDD computation with known values."""
        temps = pd.Series([50.0, 60.0, 65.0, 70.0, 75.0])
        hdd = compute_hdd(temps, base_temp=65.0)
        
        expected = pd.Series([15.0, 5.0, 0.0, 0.0, 0.0])
        pd.testing.assert_series_equal(hdd, expected)
    
    def test_compute_cdd_basic(self):
        """Test basic CDD computation with known values."""
        temps = pd.Series([50.0, 60.0, 65.0, 70.0, 75.0])
        cdd = compute_cdd(temps, base_temp=65.0)
        
        expected = pd.Series([0.0, 0.0, 0.0, 5.0, 10.0])
        pd.testing.assert_series_equal(cdd, expected)
    
    def test_hdd_non_negative(self):
        """Property 7a: HDD values are always non-negative."""
        temps = pd.Series(np.random.uniform(-50, 100, 100))
        hdd = compute_hdd(temps, base_temp=65.0)
        
        assert (hdd >= 0).all(), "HDD values must be non-negative"
    
    def test_cdd_non_negative(self):
        """Property 7b: CDD values are always non-negative."""
        temps = pd.Series(np.random.uniform(-50, 100, 100))
        cdd = compute_cdd(temps, base_temp=65.0)
        
        assert (cdd >= 0).all(), "CDD values must be non-negative"
    
    def test_hdd_cdd_relationship(self):
        """Property 7c: For any temperature, exactly one of HDD or CDD is positive (or both zero)."""
        temps = pd.Series(np.random.uniform(-50, 100, 100))
        base_temp = 65.0
        
        hdd = compute_hdd(temps, base_temp)
        cdd = compute_cdd(temps, base_temp)
        
        # At base_temp, both should be zero
        # Below base_temp, HDD > 0 and CDD = 0
        # Above base_temp, HDD = 0 and CDD > 0
        for i, temp in enumerate(temps):
            if temp < base_temp:
                assert hdd.iloc[i] > 0, f"HDD should be positive for temp {temp} < {base_temp}"
                assert cdd.iloc[i] == 0, f"CDD should be zero for temp {temp} < {base_temp}"
            elif temp > base_temp:
                assert hdd.iloc[i] == 0, f"HDD should be zero for temp {temp} > {base_temp}"
                assert cdd.iloc[i] > 0, f"CDD should be positive for temp {temp} > {base_temp}"
            else:  # temp == base_temp
                assert hdd.iloc[i] == 0, f"HDD should be zero for temp {temp} == {base_temp}"
                assert cdd.iloc[i] == 0, f"CDD should be zero for temp {temp} == {base_temp}"
    
    def test_hdd_cdd_sum_relationship(self):
        """Property 7d: HDD + CDD = |temp - base_temp| for all temperatures."""
        temps = pd.Series(np.random.uniform(-50, 100, 100))
        base_temp = 65.0
        
        hdd = compute_hdd(temps, base_temp)
        cdd = compute_cdd(temps, base_temp)
        
        # HDD + CDD should equal the absolute difference from base_temp
        expected_sum = np.abs(temps - base_temp)
        actual_sum = hdd + cdd
        
        np.testing.assert_array_almost_equal(actual_sum, expected_sum)
    
    @given(st.lists(st.floats(min_value=-50, max_value=100, allow_nan=False, allow_infinity=False), min_size=1, max_size=365))
    def test_hdd_property_non_negative(self, temps_list):
        """Property 7 (hypothesis): HDD is always non-negative."""
        temps = pd.Series(temps_list)
        hdd = compute_hdd(temps, base_temp=65.0)
        
        assert (hdd >= 0).all(), "HDD must be non-negative for all temperatures"
    
    @given(st.lists(st.floats(min_value=-50, max_value=100, allow_nan=False, allow_infinity=False), min_size=1, max_size=365))
    def test_cdd_property_non_negative(self, temps_list):
        """Property 7 (hypothesis): CDD is always non-negative."""
        temps = pd.Series(temps_list)
        cdd = compute_cdd(temps, base_temp=65.0)
        
        assert (cdd >= 0).all(), "CDD must be non-negative for all temperatures"
    
    def test_compute_hdd_type_error(self):
        """Test that compute_hdd raises TypeError for non-Series input."""
        with pytest.raises(TypeError):
            compute_hdd([50, 60, 70], base_temp=65.0)
    
    def test_compute_cdd_type_error(self):
        """Test that compute_cdd raises TypeError for non-Series input."""
        with pytest.raises(TypeError):
            compute_cdd([50, 60, 70], base_temp=65.0)


class TestAnnualHDD:
    """Test annual HDD computation."""
    
    def test_compute_annual_hdd_basic(self):
        """Test annual HDD computation with known data."""
        # Create a simple weather dataframe
        dates = pd.date_range('2025-01-01', periods=365, freq='D')
        temps = pd.Series([50.0] * 365)  # All days at 50°F
        
        weather_df = pd.DataFrame({
            'site_id': 'KPDX',
            'date': dates,
            'daily_avg_temp': temps
        })
        
        # At 50°F with base 65°F, HDD = 15 per day
        # Annual HDD = 15 * 365 = 5475
        annual_hdd = compute_annual_hdd(weather_df, 'KPDX', 2025, base_temp=65.0)
        
        assert annual_hdd == pytest.approx(15.0 * 365, rel=0.01)
    
    def test_compute_annual_hdd_mixed_temps(self):
        """Test annual HDD with mixed temperatures."""
        dates = pd.date_range('2025-01-01', periods=365, freq='D')
        # 180 days at 50°F (HDD=15), 185 days at 70°F (HDD=0)
        temps = pd.Series([50.0] * 180 + [70.0] * 185)
        
        weather_df = pd.DataFrame({
            'site_id': 'KEUG',
            'date': dates,
            'daily_avg_temp': temps
        })
        
        annual_hdd = compute_annual_hdd(weather_df, 'KEUG', 2025, base_temp=65.0)
        
        # Expected: 180 * 15 + 185 * 0 = 2700
        assert annual_hdd == pytest.approx(2700.0, rel=0.01)
    
    def test_compute_annual_hdd_no_data_error(self):
        """Test that compute_annual_hdd raises ValueError when no data found."""
        dates = pd.date_range('2025-01-01', periods=365, freq='D')
        temps = pd.Series([50.0] * 365)
        
        weather_df = pd.DataFrame({
            'site_id': 'KPDX',
            'date': dates,
            'daily_avg_temp': temps
        })
        
        with pytest.raises(ValueError):
            compute_annual_hdd(weather_df, 'KEUG', 2025)  # Wrong site_id
    
    def test_compute_annual_hdd_type_error(self):
        """Test that compute_annual_hdd raises TypeError for non-DataFrame input."""
        with pytest.raises(TypeError):
            compute_annual_hdd([1, 2, 3], 'KPDX', 2025)


class TestWaterHeatingDelta:
    """Test water heating temperature delta computation."""
    
    def test_compute_water_heating_delta_basic(self):
        """Test basic water heating delta computation."""
        dates = pd.date_range('2025-01-01', periods=365, freq='D')
        cold_temps = pd.Series([55.0] * 365)  # All days at 55°F
        
        water_temp_df = pd.DataFrame({
            'date': dates,
            'cold_water_temp': cold_temps
        })
        
        # Delta = 120 - 55 = 65°F
        delta = compute_water_heating_delta(water_temp_df, target_temp=120.0)
        
        assert delta == pytest.approx(65.0, rel=0.01)
    
    def test_compute_water_heating_delta_with_year_filter(self):
        """Test water heating delta with year filtering."""
        dates = pd.date_range('2024-01-01', periods=730, freq='D')  # 2 years
        cold_temps = pd.Series([50.0] * 365 + [60.0] * 365)
        
        water_temp_df = pd.DataFrame({
            'date': dates,
            'cold_water_temp': cold_temps
        })
        
        # For 2025 only (second year), avg = 60°F
        # Delta = 120 - 60 = 60°F
        delta = compute_water_heating_delta(water_temp_df, target_temp=120.0, year=2025)
        
        assert delta == pytest.approx(60.0, rel=0.01)
    
    def test_compute_water_heating_delta_positive(self):
        """Property 8a: Water heating delta is positive when cold water temp < target."""
        dates = pd.date_range('2025-01-01', periods=365, freq='D')
        cold_temps = pd.Series(np.random.uniform(40, 70, 365))  # All < 120°F
        
        water_temp_df = pd.DataFrame({
            'date': dates,
            'cold_water_temp': cold_temps
        })
        
        delta = compute_water_heating_delta(water_temp_df, target_temp=120.0)
        
        assert delta > 0, "Water heating delta must be positive when cold water temp < target"
    
    def test_compute_water_heating_delta_no_data_error(self):
        """Test that compute_water_heating_delta raises ValueError when no data for year."""
        dates = pd.date_range('2025-01-01', periods=365, freq='D')
        cold_temps = pd.Series([55.0] * 365)
        
        water_temp_df = pd.DataFrame({
            'date': dates,
            'cold_water_temp': cold_temps
        })
        
        with pytest.raises(ValueError):
            compute_water_heating_delta(water_temp_df, target_temp=120.0, year=2024)
    
    def test_compute_water_heating_delta_type_error(self):
        """Test that compute_water_heating_delta raises TypeError for non-DataFrame input."""
        with pytest.raises(TypeError):
            compute_water_heating_delta([55, 60, 65], target_temp=120.0)


class TestWeatherStationAssignment:
    """Test weather station assignment by district."""
    
    def test_assign_weather_station_valid_districts(self):
        """Test weather station assignment for all valid districts."""
        for district_code, expected_station in config.DISTRICT_WEATHER_MAP.items():
            station = assign_weather_station(district_code)
            assert station == expected_station
    
    def test_assign_weather_station_invalid_district(self):
        """Test that invalid district code raises KeyError."""
        with pytest.raises(KeyError):
            assign_weather_station('INVALID')
    
    def test_assign_weather_station_returns_string(self):
        """Test that assign_weather_station returns a string."""
        station = assign_weather_station('MULT')
        assert isinstance(station, str)
    
    def test_assign_weather_station_coverage(self):
        """Test that all districts in DISTRICT_WEATHER_MAP are covered."""
        for district_code in config.DISTRICT_WEATHER_MAP.keys():
            station = assign_weather_station(district_code)
            assert station in config.ICAO_TO_GHCND.keys(), \
                f"Station {station} for district {district_code} not in ICAO_TO_GHCND"
