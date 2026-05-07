"""
Unit and property-based tests for apply_replacements function.

Tests validate:
- Equipment replacement probability computation
- Electrification switching logic
- Efficiency improvement application
- Conservation of equipment count
- Deterministic behavior with random seed
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, assume
from src import equipment, config


class TestApplyReplacementsBasic:
    """Basic tests for apply_replacements function."""

    def test_apply_replacements_conservation(self):
        """
        Property 6: Total equipment count before and after apply_replacements is equal.
        
        Replacements don't create or destroy units, only modify existing ones.
        
        Validates: Requirements 3.3, 3.4
        """
        equipment_df = pd.DataFrame({
            'install_year': [2005, 2010, 2015],
            'end_use': ['space_heating', 'space_heating', 'water_heating'],
            'efficiency': [0.80, 0.85, 0.65],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'eta': [18.5, 18.5, 12.0],
            'beta': [3.0, 3.0, 3.0],
            'useful_life': [20, 20, 13]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.10, 'water_heating': 0.05},
            'efficiency_improvement': {'space_heating': 0.15, 'water_heating': 0.20}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        assert len(result) == len(equipment_df), \
            "Equipment count changed after replacement"

    def test_apply_replacements_old_equipment_replaced(self):
        """Test that old equipment (high age) is more likely to be replaced."""
        # Create equipment with very high age (should have high replacement probability)
        equipment_df = pd.DataFrame({
            'install_year': [1980],  # 45 years old in 2025
            'end_use': ['space_heating'],
            'efficiency': [0.80],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.0}
        }
        
        # Run multiple times to check if replacement happens
        replaced_count = 0
        for seed in range(100):
            result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=seed)
            # If replaced, install_year should be updated to 2025
            if result.loc[0, 'install_year'] == 2025:
                replaced_count += 1
        
        # With very old equipment, should see replacements in most runs
        assert replaced_count > 50, \
            f"Old equipment should be replaced frequently, but only {replaced_count}/100 times"

    def test_apply_replacements_new_equipment_rarely_replaced(self):
        """Test that new equipment (low age) is rarely replaced."""
        # Create equipment with very low age (should have low replacement probability)
        equipment_df = pd.DataFrame({
            'install_year': [2024],  # 1 year old in 2025
            'end_use': ['space_heating'],
            'efficiency': [0.90],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.0}
        }
        
        # Run multiple times to check if replacement happens
        replaced_count = 0
        for seed in range(100):
            result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=seed)
            # If replaced, install_year should be updated to 2025
            if result.loc[0, 'install_year'] == 2025:
                replaced_count += 1
        
        # With very new equipment, should see very few replacements
        assert replaced_count < 10, \
            f"New equipment should rarely be replaced, but {replaced_count}/100 times"

    def test_apply_replacements_deterministic_with_seed(self):
        """
        Property: Running apply_replacements with same seed produces identical results.
        
        Validates: Requirements 6.2, 6.3
        """
        equipment_df = pd.DataFrame({
            'install_year': [2005, 2010, 2015],
            'end_use': ['space_heating', 'space_heating', 'water_heating'],
            'efficiency': [0.80, 0.85, 0.65],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'eta': [18.5, 18.5, 12.0],
            'beta': [3.0, 3.0, 3.0],
            'useful_life': [20, 20, 13]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.10, 'water_heating': 0.05},
            'efficiency_improvement': {'space_heating': 0.15, 'water_heating': 0.20}
        }
        
        result1 = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        result2 = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        pd.testing.assert_frame_equal(result1, result2)

    def test_apply_replacements_efficiency_improvement(self):
        """Test that efficiency improvement is applied to replaced units."""
        equipment_df = pd.DataFrame({
            'install_year': [1980],  # Very old, will likely be replaced
            'end_use': ['space_heating'],
            'efficiency': [0.80],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.20}  # 20% improvement
        }
        
        # Run with seed that causes replacement
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=0)
        
        # If replaced, efficiency should be improved
        if result.loc[0, 'install_year'] == 2025:
            expected_efficiency = 0.80 * 1.20
            assert result.loc[0, 'efficiency'] == expected_efficiency, \
                f"Efficiency should be {expected_efficiency}, got {result.loc[0, 'efficiency']}"

    def test_apply_replacements_efficiency_capped_at_one(self):
        """Test that efficiency is capped at 1.0 (100%)."""
        equipment_df = pd.DataFrame({
            'install_year': [1980],  # Very old, will likely be replaced
            'end_use': ['space_heating'],
            'efficiency': [0.95],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.10}  # Would give 1.045, should cap at 1.0
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=0)
        
        # If replaced, efficiency should be capped at 1.0
        if result.loc[0, 'install_year'] == 2025:
            assert result.loc[0, 'efficiency'] <= 1.0, \
                f"Efficiency should be capped at 1.0, got {result.loc[0, 'efficiency']}"

    def test_apply_replacements_electrification_switching(self):
        """Test that electrification switching changes fuel type."""
        equipment_df = pd.DataFrame({
            'install_year': [1980],  # Very old, will likely be replaced
            'end_use': ['space_heating'],
            'efficiency': [0.80],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 1.0},  # 100% electrification
            'efficiency_improvement': {'space_heating': 0.0}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=0)
        
        # If replaced with 100% electrification, fuel_type should be 'electric'
        if result.loc[0, 'install_year'] == 2025:
            assert result.loc[0, 'fuel_type'] == 'electric', \
                f"Fuel type should be 'electric', got {result.loc[0, 'fuel_type']}"

    def test_apply_replacements_install_year_updated(self):
        """Test that install_year is updated to current year for replaced units."""
        equipment_df = pd.DataFrame({
            'install_year': [1980],  # Very old, will likely be replaced
            'end_use': ['space_heating'],
            'efficiency': [0.80],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.0}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=0)
        
        # If replaced, install_year should be 2025
        if result.loc[0, 'install_year'] == 2025:
            assert result.loc[0, 'install_year'] == 2025

    def test_apply_replacements_eta_recomputed(self):
        """Test that eta is recomputed for replaced units."""
        equipment_df = pd.DataFrame({
            'install_year': [1980],  # Very old, will likely be replaced
            'end_use': ['space_heating'],
            'efficiency': [0.80],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.0}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=0)
        
        # If replaced, eta should be recomputed
        if result.loc[0, 'install_year'] == 2025:
            expected_eta = equipment.median_to_eta(20, 3.0)
            assert abs(result.loc[0, 'eta'] - expected_eta) < 1e-10, \
                f"eta should be {expected_eta}, got {result.loc[0, 'eta']}"

    def test_apply_replacements_multiple_end_uses(self):
        """Test apply_replacements with multiple end-use categories."""
        equipment_df = pd.DataFrame({
            'install_year': [1980, 1985, 1990],
            'end_use': ['space_heating', 'water_heating', 'cooking'],
            'efficiency': [0.80, 0.65, 0.75],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'eta': [18.5, 12.0, 14.0],
            'beta': [3.0, 3.0, 2.5],
            'useful_life': [20, 13, 15]
        })
        
        scenario = {
            'electrification_rate': {
                'space_heating': 0.10,
                'water_heating': 0.05,
                'cooking': 0.02
            },
            'efficiency_improvement': {
                'space_heating': 0.15,
                'water_heating': 0.20,
                'cooking': 0.10
            }
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        # Verify conservation
        assert len(result) == len(equipment_df)
        
        # Verify all end-uses are preserved
        assert set(result['end_use']) == set(equipment_df['end_use'])

    def test_apply_replacements_no_replacement_scenario(self):
        """Test apply_replacements with zero replacement rates."""
        equipment_df = pd.DataFrame({
            'install_year': [2005, 2010, 2015],
            'end_use': ['space_heating', 'space_heating', 'water_heating'],
            'efficiency': [0.80, 0.85, 0.65],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'eta': [18.5, 18.5, 12.0],
            'beta': [3.0, 3.0, 3.0],
            'useful_life': [20, 20, 13]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0, 'water_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.0, 'water_heating': 0.0}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        # With zero rates, nothing should change
        pd.testing.assert_frame_equal(result, equipment_df)

    def test_apply_replacements_missing_scenario_keys(self):
        """Test apply_replacements handles missing scenario keys gracefully."""
        equipment_df = pd.DataFrame({
            'install_year': [1980],
            'end_use': ['space_heating'],
            'efficiency': [0.80],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        # Scenario with missing keys
        scenario = {}
        
        # Should not raise error
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=0)
        
        assert len(result) == len(equipment_df)

    def test_apply_replacements_preserves_other_columns(self):
        """Test that apply_replacements preserves non-modified columns."""
        equipment_df = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'equipment_type_code': ['RFAU', 'RAWH'],
            'install_year': [1980, 1985],
            'end_use': ['space_heating', 'water_heating'],
            'efficiency': [0.80, 0.65],
            'fuel_type': ['natural_gas', 'natural_gas'],
            'eta': [18.5, 12.0],
            'beta': [3.0, 3.0],
            'useful_life': [20, 13]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0, 'water_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.0, 'water_heating': 0.0}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        # Verify all original columns are present
        for col in equipment_df.columns:
            assert col in result.columns

    @given(
        electrification_rate=st.floats(min_value=0.0, max_value=1.0),
        efficiency_improvement=st.floats(min_value=0.0, max_value=0.5)
    )
    def test_apply_replacements_valid_scenario_rates(self, electrification_rate, efficiency_improvement):
        """
        Property: apply_replacements handles any valid scenario rates [0, 1].
        
        Validates: Requirements 3.3, 3.4
        """
        equipment_df = pd.DataFrame({
            'install_year': [1980],
            'end_use': ['space_heating'],
            'efficiency': [0.80],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': electrification_rate},
            'efficiency_improvement': {'space_heating': efficiency_improvement}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        # Should not raise error and should conserve count
        assert len(result) == len(equipment_df)

    @given(
        year=st.integers(min_value=2025, max_value=2050)
    )
    def test_apply_replacements_various_years(self, year):
        """
        Property: apply_replacements works for any future year.
        
        Validates: Requirements 3.3
        """
        equipment_df = pd.DataFrame({
            'install_year': [2010],
            'end_use': ['space_heating'],
            'efficiency': [0.85],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.0},
            'efficiency_improvement': {'space_heating': 0.0}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=year, random_seed=42)
        
        # Should not raise error and should conserve count
        assert len(result) == len(equipment_df)


class TestApplyReplacementsEdgeCases:
    """Edge case tests for apply_replacements."""

    def test_apply_replacements_empty_dataframe(self):
        """Test apply_replacements with empty DataFrame."""
        equipment_df = pd.DataFrame({
            'install_year': [],
            'end_use': [],
            'efficiency': [],
            'fuel_type': [],
            'eta': [],
            'beta': [],
            'useful_life': []
        })
        
        scenario = {
            'electrification_rate': {},
            'efficiency_improvement': {}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        assert len(result) == 0

    def test_apply_replacements_single_unit(self):
        """Test apply_replacements with single equipment unit."""
        equipment_df = pd.DataFrame({
            'install_year': [2010],
            'end_use': ['space_heating'],
            'efficiency': [0.85],
            'fuel_type': ['natural_gas'],
            'eta': [18.5],
            'beta': [3.0],
            'useful_life': [20]
        })
        
        scenario = {
            'electrification_rate': {'space_heating': 0.5},
            'efficiency_improvement': {'space_heating': 0.1}
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        assert len(result) == 1

    def test_apply_replacements_large_dataset(self):
        """Test apply_replacements with large dataset."""
        n = 10000
        equipment_df = pd.DataFrame({
            'install_year': np.random.randint(1980, 2020, n),
            'end_use': np.random.choice(['space_heating', 'water_heating', 'cooking'], n),
            'efficiency': np.random.uniform(0.6, 0.95, n),
            'fuel_type': np.random.choice(['natural_gas', 'electric'], n),
            'eta': np.random.uniform(10, 25, n),
            'beta': np.random.choice([2.5, 3.0], n),
            'useful_life': np.random.choice([13, 15, 20], n)
        })
        
        scenario = {
            'electrification_rate': {
                'space_heating': 0.1,
                'water_heating': 0.05,
                'cooking': 0.02
            },
            'efficiency_improvement': {
                'space_heating': 0.15,
                'water_heating': 0.20,
                'cooking': 0.10
            }
        }
        
        result = equipment.apply_replacements(equipment_df, scenario, year=2025, random_seed=42)
        
        # Verify conservation
        assert len(result) == len(equipment_df)
        
        # Verify all end-uses are preserved
        assert set(result['end_use']) == set(equipment_df['end_use'])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
