"""
Property-based tests for config module completeness.

Tests validate that configuration dictionaries are complete and consistent,
ensuring that all equipment codes map to valid end-use categories.
"""

import pytest
from hypothesis import given, strategies as st
from src import config


class TestConfigCompleteness:
    """Property tests for config module completeness."""

    def test_end_use_map_values_are_valid_strings(self):
        """
        Property 1: All equipment_type_codes in END_USE_MAP resolve to a valid end-use category string.
        
        Validates: Requirements 1.1, 1.4
        
        This property ensures that every value in the END_USE_MAP dictionary is a non-empty string,
        representing a valid end-use category. This is critical for downstream modules that rely on
        end-use categories for simulation and aggregation.
        """
        # Verify END_USE_MAP exists and is a dictionary
        assert isinstance(config.END_USE_MAP, dict), "END_USE_MAP must be a dictionary"
        assert len(config.END_USE_MAP) > 0, "END_USE_MAP must not be empty"
        
        # Verify all keys are non-empty strings
        for equipment_code, end_use_category in config.END_USE_MAP.items():
            assert isinstance(equipment_code, str), \
                f"Equipment code key must be string, got {type(equipment_code)}"
            assert len(equipment_code) > 0, \
                "Equipment code key must not be empty"
            
            # Verify all values are non-empty strings
            assert isinstance(end_use_category, str), \
                f"End-use category for {equipment_code} must be string, got {type(end_use_category)}"
            assert len(end_use_category) > 0, \
                f"End-use category for {equipment_code} must not be empty"
            
            # Verify end-use category follows naming convention (lowercase with underscores)
            assert end_use_category.islower() or "_" in end_use_category, \
                f"End-use category '{end_use_category}' should be lowercase with underscores"

    def test_end_use_categories_are_consistent(self):
        """
        Verify that all end-use categories in END_USE_MAP are consistent with DEFAULT_EFFICIENCY.
        
        This ensures that every end-use category that appears in END_USE_MAP has a corresponding
        default efficiency value, preventing runtime errors during simulation.
        """
        end_use_categories = set(config.END_USE_MAP.values())
        
        for end_use in end_use_categories:
            assert end_use in config.DEFAULT_EFFICIENCY, \
                f"End-use category '{end_use}' in END_USE_MAP but missing from DEFAULT_EFFICIENCY"
            
            # Verify efficiency is a valid number between 0 and 1
            efficiency = config.DEFAULT_EFFICIENCY[end_use]
            assert isinstance(efficiency, (int, float)), \
                f"Efficiency for '{end_use}' must be numeric, got {type(efficiency)}"
            assert 0 < efficiency <= 1.0, \
                f"Efficiency for '{end_use}' must be in (0, 1], got {efficiency}"

    def test_end_use_categories_have_useful_life(self):
        """
        Verify that all end-use categories in END_USE_MAP have corresponding useful life values.
        
        This ensures that equipment replacement modeling can proceed without missing data.
        """
        end_use_categories = set(config.END_USE_MAP.values())
        
        for end_use in end_use_categories:
            assert end_use in config.USEFUL_LIFE, \
                f"End-use category '{end_use}' in END_USE_MAP but missing from USEFUL_LIFE"
            
            # Verify useful life is a positive integer
            life = config.USEFUL_LIFE[end_use]
            assert isinstance(life, int), \
                f"Useful life for '{end_use}' must be integer, got {type(life)}"
            assert life > 0, \
                f"Useful life for '{end_use}' must be positive, got {life}"

    def test_end_use_categories_have_weibull_beta(self):
        """
        Verify that all end-use categories in END_USE_MAP have corresponding Weibull beta parameters.
        
        This ensures that equipment replacement probability calculations can proceed without missing data.
        """
        end_use_categories = set(config.END_USE_MAP.values())
        
        for end_use in end_use_categories:
            assert end_use in config.WEIBULL_BETA, \
                f"End-use category '{end_use}' in END_USE_MAP but missing from WEIBULL_BETA"
            
            # Verify beta is a positive number
            beta = config.WEIBULL_BETA[end_use]
            assert isinstance(beta, (int, float)), \
                f"Weibull beta for '{end_use}' must be numeric, got {type(beta)}"
            assert beta > 0, \
                f"Weibull beta for '{end_use}' must be positive, got {beta}"

    def test_district_weather_map_values_are_valid_stations(self):
        """
        Verify that all weather station codes in DISTRICT_WEATHER_MAP are valid ICAO codes.
        
        This ensures that weather data can be correctly assigned to premises by district.
        """
        valid_stations = set(config.ICAO_TO_GHCND.keys())
        
        for district, station in config.DISTRICT_WEATHER_MAP.items():
            assert isinstance(district, str), \
                f"District code must be string, got {type(district)}"
            assert isinstance(station, str), \
                f"Weather station for district {district} must be string, got {type(station)}"
            assert station in valid_stations, \
                f"Weather station '{station}' for district '{district}' not in ICAO_TO_GHCND"

    def test_efficiency_values_are_reasonable(self):
        """
        Verify that all default efficiency values are within reasonable bounds.
        
        Efficiency should be between 0 (no useful output) and 1.0 (perfect conversion).
        Typical gas equipment ranges: furnace 0.78-0.95, water heater 0.55-0.90, appliances 0.60-0.80.
        """
        for end_use, efficiency in config.DEFAULT_EFFICIENCY.items():
            assert 0 < efficiency <= 1.0, \
                f"Efficiency for '{end_use}' ({efficiency}) outside valid range (0, 1]"
            
            # Warn if efficiency seems unusually low (< 0.1) or high (> 0.99)
            if efficiency < 0.1:
                pytest.warns(UserWarning, 
                    f"Efficiency for '{end_use}' is very low ({efficiency})")
            if efficiency > 0.99:
                pytest.warns(UserWarning,
                    f"Efficiency for '{end_use}' is very high ({efficiency})")

    def test_no_duplicate_end_use_mappings(self):
        """
        Verify that END_USE_MAP does not have conflicting mappings for the same equipment code.
        
        This is a sanity check to ensure the mapping is deterministic.
        """
        # This test is somewhat redundant (dict keys are unique by definition),
        # but it documents the expectation explicitly.
        equipment_codes = list(config.END_USE_MAP.keys())
        assert len(equipment_codes) == len(set(equipment_codes)), \
            "END_USE_MAP has duplicate equipment codes"

    def test_end_use_map_not_empty(self):
        """
        Verify that END_USE_MAP contains at least the core end-use categories.
        
        This ensures the model has mappings for the primary end uses.
        """
        required_end_uses = {
            "space_heating",
            "water_heating",
            "cooking",
            "clothes_drying",
            "fireplace",
            "other"
        }
        
        mapped_end_uses = set(config.END_USE_MAP.values())
        missing = required_end_uses - mapped_end_uses
        
        assert len(missing) == 0, \
            f"END_USE_MAP missing required end-use categories: {missing}"

    def test_default_efficiency_covers_all_end_uses(self):
        """
        Verify that DEFAULT_EFFICIENCY has entries for all end-use categories.
        
        This ensures that simulation can proceed without missing efficiency data.
        """
        end_use_categories = set(config.END_USE_MAP.values())
        efficiency_categories = set(config.DEFAULT_EFFICIENCY.keys())
        
        missing = end_use_categories - efficiency_categories
        assert len(missing) == 0, \
            f"DEFAULT_EFFICIENCY missing entries for: {missing}"

    def test_useful_life_covers_all_end_uses(self):
        """
        Verify that USEFUL_LIFE has entries for all end-use categories.
        
        This ensures that equipment replacement modeling can proceed without missing data.
        """
        end_use_categories = set(config.END_USE_MAP.values())
        life_categories = set(config.USEFUL_LIFE.keys())
        
        missing = end_use_categories - life_categories
        assert len(missing) == 0, \
            f"USEFUL_LIFE missing entries for: {missing}"

    def test_weibull_beta_covers_all_end_uses(self):
        """
        Verify that WEIBULL_BETA has entries for all end-use categories.
        
        This ensures that equipment replacement probability calculations can proceed without missing data.
        """
        end_use_categories = set(config.END_USE_MAP.values())
        beta_categories = set(config.WEIBULL_BETA.keys())
        
        missing = end_use_categories - beta_categories
        assert len(missing) == 0, \
            f"WEIBULL_BETA missing entries for: {missing}"

    def test_district_weather_map_not_empty(self):
        """
        Verify that DISTRICT_WEATHER_MAP contains mappings for all expected districts.
        
        This ensures that premises can be assigned to weather stations.
        """
        assert len(config.DISTRICT_WEATHER_MAP) > 0, \
            "DISTRICT_WEATHER_MAP must not be empty"
        
        # Verify at least Oregon and Washington districts are present
        oregon_districts = {"MULT", "WASH", "CLAC", "YAMI", "POLK", "MARI", "LINN", "LANE"}
        washington_districts = {"CLAR", "SKAM", "KLIC"}
        
        mapped_districts = set(config.DISTRICT_WEATHER_MAP.keys())
        
        # At least some Oregon districts should be present
        assert len(oregon_districts & mapped_districts) > 0, \
            "DISTRICT_WEATHER_MAP missing Oregon district mappings"
        
        # At least some Washington districts should be present
        assert len(washington_districts & mapped_districts) > 0, \
            "DISTRICT_WEATHER_MAP missing Washington district mappings"

    def test_icao_to_ghcnd_mapping_valid(self):
        """
        Verify that ICAO_TO_GHCND mapping contains valid GHCND station IDs.
        
        GHCND IDs follow the format: USW00XXXXXX (6 digits) or similar.
        """
        for icao, ghcnd in config.ICAO_TO_GHCND.items():
            assert isinstance(icao, str), \
                f"ICAO code must be string, got {type(icao)}"
            assert isinstance(ghcnd, str), \
                f"GHCND ID for {icao} must be string, got {type(ghcnd)}"
            
            # GHCND IDs typically start with US and have 8+ characters
            assert len(ghcnd) >= 8, \
                f"GHCND ID '{ghcnd}' for {icao} seems too short"
            assert ghcnd.startswith("US"), \
                f"GHCND ID '{ghcnd}' for {icao} should start with 'US'"

    def test_simulation_parameters_valid(self):
        """
        Verify that simulation parameters are within reasonable bounds.
        """
        # BASE_YEAR should be a reasonable year
        assert isinstance(config.BASE_YEAR, int), \
            f"BASE_YEAR must be integer, got {type(config.BASE_YEAR)}"
        assert 2000 <= config.BASE_YEAR <= 2030, \
            f"BASE_YEAR {config.BASE_YEAR} outside reasonable range [2000, 2030]"
        
        # Temperature parameters should be reasonable (Fahrenheit)
        assert isinstance(config.DEFAULT_BASE_TEMP, (int, float)), \
            f"DEFAULT_BASE_TEMP must be numeric, got {type(config.DEFAULT_BASE_TEMP)}"
        assert 50 <= config.DEFAULT_BASE_TEMP <= 75, \
            f"DEFAULT_BASE_TEMP {config.DEFAULT_BASE_TEMP} outside reasonable range [50, 75]"
        
        assert isinstance(config.DEFAULT_HOT_WATER_TEMP, (int, float)), \
            f"DEFAULT_HOT_WATER_TEMP must be numeric, got {type(config.DEFAULT_HOT_WATER_TEMP)}"
        assert 100 <= config.DEFAULT_HOT_WATER_TEMP <= 140, \
            f"DEFAULT_HOT_WATER_TEMP {config.DEFAULT_HOT_WATER_TEMP} outside reasonable range [100, 140]"
        
        assert isinstance(config.DEFAULT_COLD_WATER_TEMP, (int, float)), \
            f"DEFAULT_COLD_WATER_TEMP must be numeric, got {type(config.DEFAULT_COLD_WATER_TEMP)}"
        assert 40 <= config.DEFAULT_COLD_WATER_TEMP <= 70, \
            f"DEFAULT_COLD_WATER_TEMP {config.DEFAULT_COLD_WATER_TEMP} outside reasonable range [40, 70]"
        
        # Hot water consumption should be reasonable (gallons per day)
        assert isinstance(config.DEFAULT_DAILY_HOT_WATER_GALLONS, (int, float)), \
            f"DEFAULT_DAILY_HOT_WATER_GALLONS must be numeric, got {type(config.DEFAULT_DAILY_HOT_WATER_GALLONS)}"
        assert 20 <= config.DEFAULT_DAILY_HOT_WATER_GALLONS <= 150, \
            f"DEFAULT_DAILY_HOT_WATER_GALLONS {config.DEFAULT_DAILY_HOT_WATER_GALLONS} outside reasonable range [20, 150]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
