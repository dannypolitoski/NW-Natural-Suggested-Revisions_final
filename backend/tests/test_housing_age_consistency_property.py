"""
Property-based test for housing age data consistency.

Tests Properties 4c and 4d:
- Property 4c: Housing age by district is always non-negative and less than 150 years (reasonable bounds)
- Property 4d: Vintage distribution percentages by district sum to 100% (±0.1% tolerance for rounding)

Validates Requirements 2.1, 2.2

This test verifies:
- All housing ages are in valid range [0, 150]
- All vintage percentages are in [0, 1]
- Vintage percentages sum to 100% per district
- Housing age correlates with vintage distribution (older vintage eras = higher average age)
- No NaN or infinite values in housing age data
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from src.housing_stock import HousingStock, build_baseline_stock, project_stock
from src import config


class TestHousingAgeConsistency:
    """Test suite for housing age and vintage distribution data consistency."""
    
    @pytest.fixture
    def baseline_stock(self):
        """Create a baseline housing stock for testing."""
        premises_data = {
            'blinded_id': [f'P{i}' for i in range(100)],
            'segment_code': ['RESSF'] * 70 + ['RESMF'] * 30,
            'district_code_IRP': ['D1'] * 50 + ['D2'] * 50,
        }
        premises = pd.DataFrame(premises_data)
        
        return HousingStock(
            year=2025,
            premises=premises,
            total_units=100,
            units_by_segment={'RESSF': 70, 'RESMF': 30},
            units_by_district={'D1': 50, 'D2': 50},
            housing_age_by_district={'D1': 35, 'D2': 40},
            vintage_distribution_by_district={
                'D1': {'pre-1980': 0.45, '1980-2000': 0.30, '2000-2010': 0.15, '2010+': 0.10},
                'D2': {'pre-1980': 0.50, '1980-2000': 0.28, '2000-2010': 0.14, '2010+': 0.08},
            },
            replacement_probability_by_district={'D1': 0.15, 'D2': 0.18}
        )
    
    def test_property_4c_housing_age_bounds_baseline(self, baseline_stock):
        """
        **Property 4c: Housing age by district is always non-negative and less than 150 years (reasonable bounds)**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that all housing ages in the baseline stock are within reasonable bounds.
        Housing age should be non-negative (cannot be negative) and less than 150 years
        (reasonable upper bound for residential buildings).
        """
        housing_ages = baseline_stock.housing_age_by_district
        
        # Verify all districts have housing age data
        assert len(housing_ages) > 0, "housing_age_by_district should not be empty"
        
        for district, age in housing_ages.items():
            # Check non-negative
            assert age >= 0, f"Housing age for district {district} is negative: {age}"
            
            # Check upper bound
            assert age < 150, f"Housing age for district {district} exceeds 150 years: {age}"
            
            # Check not NaN or infinite
            assert not np.isnan(age), f"Housing age for district {district} is NaN"
            assert not np.isinf(age), f"Housing age for district {district} is infinite"
            
            # Check is numeric
            assert isinstance(age, (int, float, np.number)), (
                f"Housing age for district {district} is not numeric: {type(age)}"
            )
    
    def test_property_4d_vintage_percentages_sum_baseline(self, baseline_stock):
        """
        **Property 4d: Vintage distribution percentages by district sum to 100% (±0.1% tolerance for rounding)**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that vintage distribution percentages sum to 100% for each district,
        with a tolerance of ±0.1% to account for floating-point rounding errors.
        """
        vintage_dist = baseline_stock.vintage_distribution_by_district
        
        # Verify all districts have vintage distribution data
        assert len(vintage_dist) > 0, "vintage_distribution_by_district should not be empty"
        
        for district, distribution in vintage_dist.items():
            # Verify distribution is a dict
            assert isinstance(distribution, dict), (
                f"Vintage distribution for district {district} is not a dict: {type(distribution)}"
            )
            
            # Verify all percentages are in [0, 1]
            for era, percentage in distribution.items():
                assert 0 <= percentage <= 1, (
                    f"Vintage percentage for district {district}, era {era} is out of bounds: {percentage}"
                )
                
                # Check not NaN or infinite
                assert not np.isnan(percentage), (
                    f"Vintage percentage for district {district}, era {era} is NaN"
                )
                assert not np.isinf(percentage), (
                    f"Vintage percentage for district {district}, era {era} is infinite"
                )
            
            # Verify sum is approximately 1.0 (100%)
            total = sum(distribution.values())
            tolerance = 0.001  # ±0.1% tolerance
            assert abs(total - 1.0) <= tolerance, (
                f"Vintage percentages for district {district} sum to {total:.4f}, "
                f"expected 1.0 ± {tolerance}"
            )
    
    def test_property_4c_housing_age_bounds_projected(self, baseline_stock):
        """
        **Property 4c: Housing age by district is always non-negative and less than 150 years (reasonable bounds)**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that housing ages remain within bounds after projection to future years.
        """
        scenario = {'housing_growth_rate': 0.01, 'base_year': baseline_stock.year}
        projected = project_stock(baseline_stock, 2035, scenario)
        
        housing_ages = projected.housing_age_by_district
        
        # Verify all districts have housing age data
        assert len(housing_ages) > 0, "housing_age_by_district should not be empty"
        
        for district, age in housing_ages.items():
            # Check non-negative
            assert age >= 0, f"Housing age for district {district} is negative: {age}"
            
            # Check upper bound
            assert age < 150, f"Housing age for district {district} exceeds 150 years: {age}"
            
            # Check not NaN or infinite
            assert not np.isnan(age), f"Housing age for district {district} is NaN"
            assert not np.isinf(age), f"Housing age for district {district} is infinite"
    
    def test_property_4d_vintage_percentages_sum_projected(self, baseline_stock):
        """
        **Property 4d: Vintage distribution percentages by district sum to 100% (±0.1% tolerance for rounding)**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that vintage distribution percentages remain valid after projection.
        """
        scenario = {'housing_growth_rate': 0.01, 'base_year': baseline_stock.year}
        projected = project_stock(baseline_stock, 2035, scenario)
        
        vintage_dist = projected.vintage_distribution_by_district
        
        # Verify all districts have vintage distribution data
        assert len(vintage_dist) > 0, "vintage_distribution_by_district should not be empty"
        
        for district, distribution in vintage_dist.items():
            # Verify all percentages are in [0, 1]
            for era, percentage in distribution.items():
                assert 0 <= percentage <= 1, (
                    f"Vintage percentage for district {district}, era {era} is out of bounds: {percentage}"
                )
            
            # Verify sum is approximately 1.0 (100%)
            total = sum(distribution.values())
            tolerance = 0.001  # ±0.1% tolerance
            assert abs(total - 1.0) <= tolerance, (
                f"Vintage percentages for district {district} sum to {total:.4f}, "
                f"expected 1.0 ± {tolerance}"
            )
    
    def test_housing_age_correlates_with_vintage_distribution(self, baseline_stock):
        """
        **Property 4c/4d: Housing age correlates with vintage distribution (older vintage eras = higher average age)**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that districts with higher percentages of older vintage eras
        (pre-1980, 1980-2000) have higher average housing ages.
        """
        housing_ages = baseline_stock.housing_age_by_district
        vintage_dist = baseline_stock.vintage_distribution_by_district
        
        # Calculate weighted average vintage year for each district
        # Assume: pre-1980 = 1960, 1980-2000 = 1990, 2000-2010 = 2005, 2010+ = 2015
        vintage_year_map = {
            'pre-1980': 1960,
            '1980-2000': 1990,
            '2000-2010': 2005,
            '2010+': 2015,
        }
        
        base_year = baseline_stock.year
        
        for district in housing_ages.keys():
            if district not in vintage_dist:
                continue
            
            distribution = vintage_dist[district]
            
            # Calculate weighted average vintage year
            weighted_vintage_year = sum(
                distribution.get(era, 0) * vintage_year_map.get(era, base_year)
                for era in vintage_year_map.keys()
            )
            
            # Calculate expected housing age from weighted vintage year
            expected_age = base_year - weighted_vintage_year
            
            # Get actual housing age
            actual_age = housing_ages[district]
            
            # Verify correlation: actual age should be close to expected age
            # Allow ±5 years tolerance for rounding and synthetic data generation
            tolerance = 5
            assert abs(actual_age - expected_age) <= tolerance, (
                f"Housing age for district {district} ({actual_age} years) does not correlate "
                f"with vintage distribution (expected ~{expected_age} years). "
                f"Weighted vintage year: {weighted_vintage_year:.1f}"
            )
    
    @given(
        growth_rate=st.floats(min_value=-0.05, max_value=0.05),
        target_year=st.integers(min_value=2026, max_value=2050),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_property_4c_housing_age_bounds_hypothesis(self, baseline_stock, growth_rate, target_year):
        """
        **Property 4c: Housing age by district is always non-negative and less than 150 years (reasonable bounds)**
        
        **Validates: Requirements 2.1, 2.2**
        
        Property-based test using Hypothesis to generate random growth rates and target years.
        Verifies that housing ages remain within bounds for all projected years.
        """
        # Skip if target year is same as baseline year
        assume(target_year != baseline_stock.year)
        
        scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
        projected = project_stock(baseline_stock, target_year, scenario)
        
        housing_ages = projected.housing_age_by_district
        
        # Verify all districts have housing age data
        assert len(housing_ages) > 0, "housing_age_by_district should not be empty"
        
        for district, age in housing_ages.items():
            # Check non-negative
            assert age >= 0, f"Housing age for district {district} is negative: {age}"
            
            # Check upper bound
            assert age < 150, f"Housing age for district {district} exceeds 150 years: {age}"
            
            # Check not NaN or infinite
            assert not np.isnan(age), f"Housing age for district {district} is NaN"
            assert not np.isinf(age), f"Housing age for district {district} is infinite"
    
    @given(
        growth_rate=st.floats(min_value=-0.05, max_value=0.05),
        target_year=st.integers(min_value=2026, max_value=2050),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_property_4d_vintage_percentages_sum_hypothesis(self, baseline_stock, growth_rate, target_year):
        """
        **Property 4d: Vintage distribution percentages by district sum to 100% (±0.1% tolerance for rounding)**
        
        **Validates: Requirements 2.1, 2.2**
        
        Property-based test using Hypothesis to generate random growth rates and target years.
        Verifies that vintage distribution percentages sum to 100% for all projected years.
        """
        # Skip if target year is same as baseline year
        assume(target_year != baseline_stock.year)
        
        scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
        projected = project_stock(baseline_stock, target_year, scenario)
        
        vintage_dist = projected.vintage_distribution_by_district
        
        # Verify all districts have vintage distribution data
        assert len(vintage_dist) > 0, "vintage_distribution_by_district should not be empty"
        
        for district, distribution in vintage_dist.items():
            # Verify all percentages are in [0, 1]
            for era, percentage in distribution.items():
                assert 0 <= percentage <= 1, (
                    f"Vintage percentage for district {district}, era {era} is out of bounds: {percentage}"
                )
                
                # Check not NaN or infinite
                assert not np.isnan(percentage), (
                    f"Vintage percentage for district {district}, era {era} is NaN"
                )
                assert not np.isinf(percentage), (
                    f"Vintage percentage for district {district}, era {era} is infinite"
                )
            
            # Verify sum is approximately 1.0 (100%)
            total = sum(distribution.values())
            tolerance = 0.001  # ±0.1% tolerance
            assert abs(total - 1.0) <= tolerance, (
                f"Vintage percentages for district {district} sum to {total:.4f}, "
                f"expected 1.0 ± {tolerance}"
            )
    
    def test_no_nan_or_infinite_values_in_housing_age(self, baseline_stock):
        """
        **Property 4c: No NaN or infinite values in housing age data**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that housing age data contains no NaN or infinite values.
        """
        housing_ages = baseline_stock.housing_age_by_district
        
        for district, age in housing_ages.items():
            assert not np.isnan(age), f"Housing age for district {district} is NaN"
            assert not np.isinf(age), f"Housing age for district {district} is infinite"
            assert isinstance(age, (int, float, np.number)), (
                f"Housing age for district {district} is not numeric: {type(age)}"
            )
    
    def test_no_nan_or_infinite_values_in_vintage_distribution(self, baseline_stock):
        """
        **Property 4d: No NaN or infinite values in vintage distribution data**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that vintage distribution data contains no NaN or infinite values.
        """
        vintage_dist = baseline_stock.vintage_distribution_by_district
        
        for district, distribution in vintage_dist.items():
            for era, percentage in distribution.items():
                assert not np.isnan(percentage), (
                    f"Vintage percentage for district {district}, era {era} is NaN"
                )
                assert not np.isinf(percentage), (
                    f"Vintage percentage for district {district}, era {era} is infinite"
                )
                assert isinstance(percentage, (int, float, np.number)), (
                    f"Vintage percentage for district {district}, era {era} is not numeric: {type(percentage)}"
                )
    
    def test_housing_age_consistency_across_multiple_projections(self, baseline_stock):
        """
        **Property 4c: Housing age remains consistent across multiple projections**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that housing age data remains valid when projecting
        multiple times in sequence.
        """
        current_stock = baseline_stock
        
        for year in [2026, 2030, 2035, 2040]:
            scenario = {'housing_growth_rate': 0.01, 'base_year': current_stock.year}
            current_stock = project_stock(current_stock, year, scenario)
            
            housing_ages = current_stock.housing_age_by_district
            
            for district, age in housing_ages.items():
                assert age >= 0, f"Housing age for district {district} is negative: {age}"
                assert age < 150, f"Housing age for district {district} exceeds 150 years: {age}"
                assert not np.isnan(age), f"Housing age for district {district} is NaN"
                assert not np.isinf(age), f"Housing age for district {district} is infinite"
    
    def test_vintage_distribution_consistency_across_multiple_projections(self, baseline_stock):
        """
        **Property 4d: Vintage distribution remains consistent across multiple projections**
        
        **Validates: Requirements 2.1, 2.2**
        
        This test verifies that vintage distribution data remains valid when projecting
        multiple times in sequence.
        """
        current_stock = baseline_stock
        
        for year in [2026, 2030, 2035, 2040]:
            scenario = {'housing_growth_rate': 0.01, 'base_year': current_stock.year}
            current_stock = project_stock(current_stock, year, scenario)
            
            vintage_dist = current_stock.vintage_distribution_by_district
            
            for district, distribution in vintage_dist.items():
                total = sum(distribution.values())
                tolerance = 0.001  # ±0.1% tolerance
                assert abs(total - 1.0) <= tolerance, (
                    f"Vintage percentages for district {district} sum to {total:.4f}, "
                    f"expected 1.0 ± {tolerance}"
                )
