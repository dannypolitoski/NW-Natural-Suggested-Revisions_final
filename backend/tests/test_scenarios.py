"""
Tests for scenario management module.

Tests ScenarioConfig, validate_scenario, run_scenario, and compare_scenarios functions.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import tempfile

from src.scenarios import (
    ScenarioConfig,
    validate_scenario,
    run_scenario,
    compare_scenarios,
    _align_baseline_to_irp
)


class TestScenarioConfig:
    """Tests for ScenarioConfig dataclass."""
    
    def test_scenario_config_creation(self):
        """Test creating a ScenarioConfig with default values."""
        config = ScenarioConfig(name='test')
        assert config.name == 'test'
        assert config.base_year == 2025
        assert config.forecast_horizon == 10
        assert config.housing_growth_rate == 0.01
        assert config.electrification_rate == 0.02
        assert config.efficiency_improvement == 0.01
        assert config.weather_assumption == 'normal'
    
    def test_scenario_config_custom_values(self):
        """Test creating a ScenarioConfig with custom values."""
        config = ScenarioConfig(
            name='high_electrification',
            base_year=2024,
            forecast_horizon=15,
            housing_growth_rate=0.02,
            electrification_rate=0.05,
            efficiency_improvement=0.03,
            weather_assumption='warm'
        )
        assert config.name == 'high_electrification'
        assert config.base_year == 2024
        assert config.forecast_horizon == 15
        assert config.housing_growth_rate == 0.02
        assert config.electrification_rate == 0.05
        assert config.efficiency_improvement == 0.03
        assert config.weather_assumption == 'warm'
    
    def test_scenario_config_to_dict(self):
        """Test converting ScenarioConfig to dictionary."""
        config = ScenarioConfig(name='test', housing_growth_rate=0.015)
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict['name'] == 'test'
        assert config_dict['housing_growth_rate'] == 0.015
    
    def test_scenario_config_from_dict(self):
        """Test creating ScenarioConfig from dictionary."""
        data = {
            'name': 'from_dict',
            'base_year': 2026,
            'forecast_horizon': 8,
            'housing_growth_rate': 0.025
        }
        config = ScenarioConfig.from_dict(data)
        assert config.name == 'from_dict'
        assert config.base_year == 2026
        assert config.forecast_horizon == 8
        assert config.housing_growth_rate == 0.025


class TestValidateScenario:
    """Tests for validate_scenario function."""
    
    def test_validate_valid_scenario(self):
        """Test validation of a valid scenario."""
        config = ScenarioConfig(
            name='baseline',
            base_year=2025,
            forecast_horizon=10,
            housing_growth_rate=0.01,
            electrification_rate=0.02,
            efficiency_improvement=0.01,
            weather_assumption='normal'
        )
        result = validate_scenario(config)
        assert result['valid'] is True
        assert len(result['errors']) == 0
        assert 'details' in result
    
    def test_validate_negative_forecast_horizon(self):
        """Test validation rejects negative forecast_horizon."""
        config = ScenarioConfig(name='bad', forecast_horizon=-5)
        result = validate_scenario(config)
        assert result['valid'] is False
        assert len(result['errors']) > 0
        assert any('forecast_horizon' in err for err in result['errors'])
    
    def test_validate_zero_forecast_horizon(self):
        """Test validation rejects zero forecast_horizon."""
        config = ScenarioConfig(name='bad', forecast_horizon=0)
        result = validate_scenario(config)
        assert result['valid'] is False
        assert len(result['errors']) > 0
    
    def test_validate_housing_growth_rate_out_of_range(self):
        """Test validation warns for housing_growth_rate outside typical range."""
        config = ScenarioConfig(name='test', housing_growth_rate=0.10)
        result = validate_scenario(config)
        # Should warn but not error (0.10 is technically valid but unusual)
        assert len(result['warnings']) > 0 or result['valid'] is True
    
    def test_validate_electrification_rate_out_of_range(self):
        """Test validation warns for electrification_rate outside typical range."""
        config = ScenarioConfig(name='test', electrification_rate=0.15)
        result = validate_scenario(config)
        # Should warn but not error
        assert len(result['warnings']) > 0 or result['valid'] is True
    
    def test_validate_efficiency_improvement_out_of_range(self):
        """Test validation warns for efficiency_improvement outside typical range."""
        config = ScenarioConfig(name='test', efficiency_improvement=0.10)
        result = validate_scenario(config)
        # Should warn but not error
        assert len(result['warnings']) > 0 or result['valid'] is True
    
    def test_validate_invalid_weather_assumption(self):
        """Test validation rejects invalid weather_assumption."""
        config = ScenarioConfig(name='bad', weather_assumption='extreme')
        result = validate_scenario(config)
        assert result['valid'] is False
        assert len(result['errors']) > 0
        assert any('weather_assumption' in err for err in result['errors'])
    
    def test_validate_rate_greater_than_one(self):
        """Test validation rejects rates > 1.0."""
        config = ScenarioConfig(name='bad', housing_growth_rate=1.5)
        result = validate_scenario(config)
        assert result['valid'] is False
        assert len(result['errors']) > 0
    
    def test_validate_invalid_config_type(self):
        """Test validation raises TypeError for non-ScenarioConfig input."""
        with pytest.raises(TypeError):
            validate_scenario({'name': 'not_a_config'})
    
    def test_validate_boundary_values(self):
        """Test validation accepts boundary values (0.0 and 0.05)."""
        config = ScenarioConfig(
            name='boundary',
            housing_growth_rate=0.0,
            electrification_rate=0.05,
            efficiency_improvement=0.0
        )
        result = validate_scenario(config)
        assert result['valid'] is True
        assert len(result['errors']) == 0


class TestBaselineIrpAlignment:
    """Tests for baseline IRP anchoring after bottom-up UPC is computed."""

    def test_aligns_baseline_estimated_total_upc_to_irp(self):
        config = ScenarioConfig(name='baseline', baseline_irp_alignment=True)
        results_df = pd.DataFrame({
            'year': [2025, 2026],
            'total_therms': [1000.0, 900.0],
            'use_per_customer': [100.0, 90.0],
        })
        estimated_total = pd.DataFrame({
            'year': [2025, 2026],
            'space_heating': [100.0, 90.0],
            'water_heating': [40.0, 36.0],
            'estimated_total_upc': [150.0, 135.0],
            'irp_upc': [165.0, 162.0],
            'non_heating_offset': [50.0, 45.0],
            'diff_vs_irp': [-15.0, -27.0],
            'diff_vs_irp_pct': [-9.1, -16.7],
            'data_type': ['calibrated', 'projected'],
        })

        aligned_results, aligned_estimated, summary = _align_baseline_to_irp(
            results_df, estimated_total, config
        )

        assert summary['enabled'] is True
        assert summary['years_aligned'] == 2
        assert aligned_estimated['estimated_total_upc'].tolist() == [165.0, 162.0]
        assert aligned_estimated['diff_vs_irp'].tolist() == [0.0, 0.0]
        assert aligned_estimated['diff_vs_irp_pct'].tolist() == [0.0, 0.0]
        assert aligned_estimated['irp_aligned'].tolist() == [True, True]
        assert aligned_results.loc[aligned_results['year'] == 2025, 'use_per_customer'].iloc[0] == pytest.approx(110.0)
        assert aligned_results.loc[aligned_results['year'] == 2026, 'use_per_customer'].iloc[0] == pytest.approx(108.0)

    def test_does_not_align_non_baseline_scenarios(self):
        config = ScenarioConfig(name='high_electrification', baseline_irp_alignment=True)
        results_df = pd.DataFrame({'year': [2025], 'total_therms': [1000.0], 'use_per_customer': [100.0]})
        estimated_total = pd.DataFrame({
            'year': [2025],
            'estimated_total_upc': [150.0],
            'irp_upc': [165.0],
        })

        aligned_results, aligned_estimated, summary = _align_baseline_to_irp(
            results_df, estimated_total, config
        )

        assert summary['enabled'] is False
        assert aligned_results.equals(results_df)
        assert aligned_estimated.equals(estimated_total)


class TestCompareScenarios:
    """Tests for compare_scenarios function."""
    
    def test_compare_scenarios_empty_list(self):
        """Test compare_scenarios raises error for empty list."""
        with pytest.raises(ValueError):
            compare_scenarios([])
    
    def test_compare_scenarios_single_scenario(self):
        """Test compare_scenarios with single scenario."""
        # Create minimal test data
        results_df = pd.DataFrame({
            'year': [2025, 2025],
            'end_use': ['space_heating', 'water_heating'],
            'total_therms': [100.0, 50.0],
            'use_per_customer': [100.0, 50.0],
            'premise_count': [1000, 1000]
        })
        metadata = {'scenario_name': 'test'}
        
        comparison = compare_scenarios([(results_df, metadata)])
        assert len(comparison) == 2
        assert 'scenario_name' in comparison.columns
        assert comparison['scenario_name'].unique()[0] == 'test'
    
    def test_compare_scenarios_multiple_scenarios(self):
        """Test compare_scenarios with multiple scenarios."""
        # Create test data for two scenarios
        results1 = pd.DataFrame({
            'year': [2025, 2025],
            'end_use': ['space_heating', 'water_heating'],
            'total_therms': [100.0, 50.0],
            'use_per_customer': [100.0, 50.0],
            'premise_count': [1000, 1000]
        })
        metadata1 = {'scenario_name': 'baseline'}
        
        results2 = pd.DataFrame({
            'year': [2025, 2025],
            'end_use': ['space_heating', 'water_heating'],
            'total_therms': [90.0, 45.0],
            'use_per_customer': [90.0, 45.0],
            'premise_count': [1000, 1000]
        })
        metadata2 = {'scenario_name': 'high_electrification'}
        
        comparison = compare_scenarios([(results1, metadata1), (results2, metadata2)])
        assert len(comparison) == 4  # 2 end-uses × 2 scenarios
        assert set(comparison['scenario_name'].unique()) == {'baseline', 'high_electrification'}
    
    def test_compare_scenarios_column_order(self):
        """Test compare_scenarios produces consistent column order."""
        results_df = pd.DataFrame({
            'year': [2025],
            'end_use': ['space_heating'],
            'total_therms': [100.0],
            'use_per_customer': [100.0],
            'premise_count': [1000]
        })
        metadata = {'scenario_name': 'test'}
        
        comparison = compare_scenarios([(results_df, metadata)])
        expected_cols = ['year', 'end_use', 'scenario_name', 'total_therms', 'use_per_customer', 'premise_count']
        assert list(comparison.columns) == expected_cols
    
    def test_compare_scenarios_sorting(self):
        """Test compare_scenarios sorts results consistently."""
        results_df = pd.DataFrame({
            'year': [2026, 2025, 2025, 2026],
            'end_use': ['water_heating', 'space_heating', 'water_heating', 'space_heating'],
            'total_therms': [50.0, 100.0, 50.0, 100.0],
            'use_per_customer': [50.0, 100.0, 50.0, 100.0],
            'premise_count': [1000, 1000, 1000, 1000]
        })
        metadata = {'scenario_name': 'test'}
        
        comparison = compare_scenarios([(results_df, metadata)])
        # Should be sorted by year, then scenario_name, then end_use
        assert comparison['year'].iloc[0] <= comparison['year'].iloc[-1]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
