"""
Unit tests for simulation module.

Tests the three per-end-use simulation functions:
- simulate_space_heating
- simulate_water_heating
- simulate_baseload
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.simulation import (
    simulate_space_heating,
    simulate_water_heating,
    simulate_baseload,
    simulate_all_end_uses
)
from src.equipment import EquipmentProfile
from src import config


class TestSimulateSpaceHeating:
    """Tests for simulate_space_heating function."""
    
    def test_basic_calculation(self):
        """Test basic space heating calculation."""
        equipment = EquipmentProfile(
            equipment_type_code="FURN",
            end_use="space_heating",
            efficiency=0.80,
            install_year=2010,
            useful_life=20,
            fuel_type="natural_gas"
        )
        
        # 5000 HDD, 0.80 efficiency, factor 1.0 -> 5000 / 0.80 = 6250 therms
        annual_therms = simulate_space_heating(equipment, 5000.0, 1.0)
        assert annual_therms == pytest.approx(6250.0, rel=0.01)
    
    def test_zero_hdd(self):
        """Test with zero HDD (no heating needed)."""
        equipment = EquipmentProfile(
            equipment_type_code="FURN",
            end_use="space_heating",
            efficiency=0.80,
            install_year=2010,
            useful_life=20,
            fuel_type="natural_gas"
        )
        
        annual_therms = simulate_space_heating(equipment, 0.0, 1.0)
        assert annual_therms == 0.0
    
    def test_efficiency_impact(self):
        """Test that higher efficiency reduces therms."""
        equipment_low = EquipmentProfile(
            equipment_type_code="FURN",
            end_use="space_heating",
            efficiency=0.75,
            install_year=2000,
            useful_life=20,
            fuel_type="natural_gas"
        )
        
        equipment_high = EquipmentProfile(
            equipment_type_code="FURN",
            end_use="space_heating",
            efficiency=0.95,
            install_year=2020,
            useful_life=20,
            fuel_type="natural_gas"
        )
        
        therms_low = simulate_space_heating(equipment_low, 5000.0, 1.0)
        therms_high = simulate_space_heating(equipment_high, 5000.0, 1.0)
        
        # Higher efficiency should result in lower therms
        assert therms_high < therms_low
    
    def test_heating_factor_impact(self):
        """Test that heating factor scales therms linearly."""
        equipment = EquipmentProfile(
            equipment_type_code="FURN",
            end_use="space_heating",
            efficiency=0.80,
            install_year=2010,
            useful_life=20,
            fuel_type="natural_gas"
        )
        
        therms_factor_1 = simulate_space_heating(equipment, 5000.0, 1.0)
        therms_factor_2 = simulate_space_heating(equipment, 5000.0, 2.0)
        
        # Factor 2.0 should double the therms
        assert therms_factor_2 == pytest.approx(therms_factor_1 * 2.0, rel=0.01)
    
    def test_invalid_hdd(self):
        """Test that negative HDD raises error."""
        equipment = EquipmentProfile(
            equipment_type_code="FURN",
            end_use="space_heating",
            efficiency=0.80,
            install_year=2010,
            useful_life=20,
            fuel_type="natural_gas"
        )
        
        with pytest.raises(ValueError):
            simulate_space_heating(equipment, -100.0, 1.0)
    
    def test_invalid_heating_factor(self):
        """Test that non-positive heating factor raises error."""
        equipment = EquipmentProfile(
            equipment_type_code="FURN",
            end_use="space_heating",
            efficiency=0.80,
            install_year=2010,
            useful_life=20,
            fuel_type="natural_gas"
        )
        
        with pytest.raises(ValueError):
            simulate_space_heating(equipment, 5000.0, 0.0)
        
        with pytest.raises(ValueError):
            simulate_space_heating(equipment, 5000.0, -1.0)
    
    def test_invalid_equipment_type(self):
        """Test that non-EquipmentProfile raises error."""
        with pytest.raises(TypeError):
            simulate_space_heating("not_equipment", 5000.0, 1.0)


class TestSimulateWaterHeating:
    """Tests for simulate_water_heating function."""
    
    def test_basic_calculation(self):
        """Test basic water heating calculation."""
        equipment = EquipmentProfile(
            equipment_type_code="WTRH",
            end_use="water_heating",
            efficiency=0.60,
            install_year=2010,
            useful_life=13,
            fuel_type="natural_gas"
        )
        
        # 64 gal/day, 65°F delta, 0.60 efficiency
        # Expected: (64 * 8.34 * 65 * 365) / (0.60 * 100000) ≈ 203 therms
        annual_therms = simulate_water_heating(equipment, 65.0, 64.0)
        assert annual_therms > 0
        assert annual_therms < 300  # Reasonable range
    
    def test_zero_delta_t(self):
        """Test that zero delta-T raises error."""
        equipment = EquipmentProfile(
            equipment_type_code="WTRH",
            end_use="water_heating",
            efficiency=0.60,
            install_year=2010,
            useful_life=13,
            fuel_type="natural_gas"
        )
        
        with pytest.raises(ValueError):
            simulate_water_heating(equipment, 0.0, 64.0)
    
    def test_negative_delta_t(self):
        """Test that negative delta-T raises error."""
        equipment = EquipmentProfile(
            equipment_type_code="WTRH",
            end_use="water_heating",
            efficiency=0.60,
            install_year=2010,
            useful_life=13,
            fuel_type="natural_gas"
        )
        
        with pytest.raises(ValueError):
            simulate_water_heating(equipment, -10.0, 64.0)
    
    def test_delta_t_impact(self):
        """Test that higher delta-T increases therms."""
        equipment = EquipmentProfile(
            equipment_type_code="WTRH",
            end_use="water_heating",
            efficiency=0.60,
            install_year=2010,
            useful_life=13,
            fuel_type="natural_gas"
        )
        
        therms_low = simulate_water_heating(equipment, 30.0, 64.0)
        therms_high = simulate_water_heating(equipment, 60.0, 64.0)
        
        # Higher delta-T should result in higher therms
        assert therms_high > therms_low
        # Should be approximately linear
        assert therms_high / therms_low == pytest.approx(2.0, rel=0.01)
    
    def test_efficiency_impact(self):
        """Test that higher efficiency reduces therms."""
        equipment_low = EquipmentProfile(
            equipment_type_code="WTRH",
            end_use="water_heating",
            efficiency=0.50,
            install_year=2000,
            useful_life=13,
            fuel_type="natural_gas"
        )
        
        equipment_high = EquipmentProfile(
            equipment_type_code="WTRH",
            end_use="water_heating",
            efficiency=0.80,
            install_year=2020,
            useful_life=13,
            fuel_type="natural_gas"
        )
        
        therms_low = simulate_water_heating(equipment_low, 65.0, 64.0)
        therms_high = simulate_water_heating(equipment_high, 65.0, 64.0)
        
        # Higher efficiency should result in lower therms
        assert therms_high < therms_low
    
    def test_invalid_equipment_type(self):
        """Test that non-EquipmentProfile raises error."""
        with pytest.raises(TypeError):
            simulate_water_heating("not_equipment", 65.0, 64.0)


class TestSimulateBaseload:
    """Tests for simulate_baseload function."""
    
    def test_basic_calculation(self):
        """Test basic baseload calculation."""
        equipment = EquipmentProfile(
            equipment_type_code="RRGE",
            end_use="cooking",
            efficiency=0.75,
            install_year=2010,
            useful_life=15,
            fuel_type="natural_gas"
        )
        
        # 30 therms base, 0.75 efficiency -> 30 / 0.75 = 40 therms
        annual_therms = simulate_baseload(equipment, 30.0)
        assert annual_therms == pytest.approx(40.0, rel=0.01)
    
    def test_zero_consumption(self):
        """Test with zero base consumption."""
        equipment = EquipmentProfile(
            equipment_type_code="RRGE",
            end_use="cooking",
            efficiency=0.75,
            install_year=2010,
            useful_life=15,
            fuel_type="natural_gas"
        )
        
        annual_therms = simulate_baseload(equipment, 0.0)
        assert annual_therms == 0.0
    
    def test_efficiency_impact(self):
        """Test that higher efficiency reduces therms."""
        equipment_low = EquipmentProfile(
            equipment_type_code="RRGE",
            end_use="cooking",
            efficiency=0.60,
            install_year=2000,
            useful_life=15,
            fuel_type="natural_gas"
        )
        
        equipment_high = EquipmentProfile(
            equipment_type_code="RRGE",
            end_use="cooking",
            efficiency=0.90,
            install_year=2020,
            useful_life=15,
            fuel_type="natural_gas"
        )
        
        therms_low = simulate_baseload(equipment_low, 30.0)
        therms_high = simulate_baseload(equipment_high, 30.0)
        
        # Higher efficiency should result in lower therms
        assert therms_high < therms_low
    
    def test_negative_consumption(self):
        """Test that negative consumption raises error."""
        equipment = EquipmentProfile(
            equipment_type_code="RRGE",
            end_use="cooking",
            efficiency=0.75,
            install_year=2010,
            useful_life=15,
            fuel_type="natural_gas"
        )
        
        with pytest.raises(ValueError):
            simulate_baseload(equipment, -10.0)
    
    def test_invalid_equipment_type(self):
        """Test that non-EquipmentProfile raises error."""
        with pytest.raises(TypeError):
            simulate_baseload("not_equipment", 30.0)


class TestSimulateAllEndUses:
    """Tests for simulate_all_end_uses orchestrator function."""
    
    def test_basic_orchestration(self):
        """Test basic orchestration with minimal data."""
        # Create minimal premise-equipment data
        premise_equipment = pd.DataFrame({
            'blinded_id': ['P001', 'P001'],
            'equipment_type_code': ['FURN', 'WTRH'],
            'end_use': ['space_heating', 'water_heating'],
            'efficiency': [0.80, 0.60],
            'install_year': [2010, 2010],
            'useful_life': [20, 13],
            'fuel_type': ['natural_gas', 'natural_gas'],
            'district_code_IRP': ['MULT', 'MULT']
        })
        
        # Create weather data
        dates = pd.date_range('2025-01-01', '2025-12-31', freq='D')
        weather_data = pd.DataFrame({
            'site_id': ['KPDX'] * len(dates),
            'date': dates,
            'daily_avg_temp': [50.0] * len(dates)  # Constant 50°F
        })
        
        # Create water temperature data
        water_temp_data = pd.DataFrame({
            'date': dates,
            'cold_water_temp': [55.0] * len(dates)  # Constant 55°F
        })
        
        # Baseload factors
        baseload_factors = {
            'cooking': 30.0,
            'clothes_drying': 20.0,
            'fireplace': 55.0,
            'other': 10.0
        }
        
        # Run simulation
        results = simulate_all_end_uses(
            premise_equipment,
            weather_data,
            water_temp_data,
            baseload_factors,
            year=2025
        )
        
        # Verify results
        assert not results.empty
        assert len(results) == 2  # One row per end-use
        assert set(results['blinded_id']) == {'P001'}
        assert set(results['end_use']) == {'space_heating', 'water_heating'}
        assert all(results['annual_therms'] >= 0)
        assert all(results['year'] == 2025)
    
    def test_missing_columns_premise(self):
        """Test that missing columns in premise_equipment raises error."""
        premise_equipment = pd.DataFrame({
            'blinded_id': ['P001'],
            'equipment_type_code': ['FURN']
            # Missing other required columns
        })
        
        weather_data = pd.DataFrame({
            'site_id': ['KPDX'],
            'date': [pd.Timestamp('2025-01-01')],
            'daily_avg_temp': [50.0]
        })
        
        water_temp_data = pd.DataFrame({
            'date': [pd.Timestamp('2025-01-01')],
            'cold_water_temp': [55.0]
        })
        
        with pytest.raises(ValueError, match="premise_equipment missing columns"):
            simulate_all_end_uses(
                premise_equipment,
                weather_data,
                water_temp_data,
                {}
            )
    
    def test_missing_columns_weather(self):
        """Test that missing columns in weather_data raises error."""
        premise_equipment = pd.DataFrame({
            'blinded_id': ['P001'],
            'equipment_type_code': ['FURN'],
            'end_use': ['space_heating'],
            'efficiency': [0.80],
            'install_year': [2010],
            'useful_life': [20],
            'fuel_type': ['natural_gas'],
            'district_code_IRP': ['MULT']
        })
        
        weather_data = pd.DataFrame({
            'site_id': ['KPDX']
            # Missing other required columns
        })
        
        water_temp_data = pd.DataFrame({
            'date': [pd.Timestamp('2025-01-01')],
            'cold_water_temp': [55.0]
        })
        
        with pytest.raises(ValueError, match="weather_data missing columns"):
            simulate_all_end_uses(
                premise_equipment,
                weather_data,
                water_temp_data,
                {}
            )
    
    def test_non_negativity(self):
        """Test that all simulated therms are non-negative."""
        premise_equipment = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'equipment_type_code': ['FURN', 'WTRH', 'RRGE'],
            'end_use': ['space_heating', 'water_heating', 'cooking'],
            'efficiency': [0.80, 0.60, 0.75],
            'install_year': [2010, 2010, 2010],
            'useful_life': [20, 13, 15],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'district_code_IRP': ['MULT', 'MULT', 'MULT']
        })
        
        dates = pd.date_range('2025-01-01', '2025-12-31', freq='D')
        weather_data = pd.DataFrame({
            'site_id': ['KPDX'] * len(dates),
            'date': dates,
            'daily_avg_temp': [50.0] * len(dates)
        })
        
        water_temp_data = pd.DataFrame({
            'date': dates,
            'cold_water_temp': [55.0] * len(dates)
        })
        
        baseload_factors = {'cooking': 30.0}
        
        results = simulate_all_end_uses(
            premise_equipment,
            weather_data,
            water_temp_data,
            baseload_factors,
            year=2025
        )
        
        # All therms should be non-negative
        assert all(results['annual_therms'] >= 0)
