"""
Property-based tests for housing stock projection.

Tests the project_stock function to ensure:
1. Projected total_units equals baseline total_units × (1 + growth_rate)^(target_year - base_year)
2. New units are distributed proportionally across segments
3. New units are distributed proportionally across districts
4. Segment and district distributions are preserved
"""

import pytest
import pandas as pd
from src.housing_stock import HousingStock, build_baseline_stock, project_stock


class TestProjectStock:
    """Test suite for project_stock function."""
    
    @pytest.fixture
    def baseline_stock(self):
        """Create a baseline housing stock for testing."""
        # Create a simple premises DataFrame
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
            units_by_district={'D1': 50, 'D2': 50}
        )
    
    def test_project_stock_zero_growth(self, baseline_stock):
        """Test projection with zero growth rate."""
        scenario = {'housing_growth_rate': 0.0, 'base_year': 2025}
        projected = project_stock(baseline_stock, 2030, scenario)
        
        assert projected.year == 2030
        assert projected.total_units == 100  # No growth
        assert projected.units_by_segment == {'RESSF': 70, 'RESMF': 30}
        assert projected.units_by_district == {'D1': 50, 'D2': 50}
    
    def test_project_stock_positive_growth(self, baseline_stock):
        """Test projection with positive growth rate."""
        scenario = {'housing_growth_rate': 0.01, 'base_year': 2025}
        projected = project_stock(baseline_stock, 2030, scenario)
        
        # Expected: 100 * (1.01)^5 ≈ 105.1
        expected_total = int(round(100 * ((1.01) ** 5)))
        assert projected.year == 2030
        assert projected.total_units == expected_total
        assert projected.total_units > baseline_stock.total_units
    
    def test_project_stock_compound_growth(self, baseline_stock):
        """Test that growth is compounded correctly over multiple years."""
        scenario = {'housing_growth_rate': 0.02, 'base_year': 2025}
        
        # Project 1 year
        projected_1yr = project_stock(baseline_stock, 2026, scenario)
        expected_1yr = int(round(100 * 1.02))
        assert projected_1yr.total_units == expected_1yr
        
        # Project 10 years
        projected_10yr = project_stock(baseline_stock, 2035, scenario)
        expected_10yr = int(round(100 * ((1.02) ** 10)))
        assert projected_10yr.total_units == expected_10yr
    
    def test_project_stock_segment_distribution_preserved(self, baseline_stock):
        """Test that segment distribution is preserved proportionally."""
        scenario = {'housing_growth_rate': 0.01, 'base_year': 2025}
        projected = project_stock(baseline_stock, 2030, scenario)
        
        # Segment proportions should be maintained
        ressf_proportion = projected.units_by_segment['RESSF'] / projected.total_units
        resmf_proportion = projected.units_by_segment['RESMF'] / projected.total_units
        
        # Original proportions: RESSF=70%, RESMF=30%
        assert abs(ressf_proportion - 0.70) < 0.01  # Allow small rounding error
        assert abs(resmf_proportion - 0.30) < 0.01
    
    def test_project_stock_district_distribution_preserved(self, baseline_stock):
        """Test that district distribution is preserved proportionally."""
        scenario = {'housing_growth_rate': 0.015, 'base_year': 2025}
        projected = project_stock(baseline_stock, 2030, scenario)
        
        # District proportions should be maintained
        d1_proportion = projected.units_by_district['D1'] / projected.total_units
        d2_proportion = projected.units_by_district['D2'] / projected.total_units
        
        # Original proportions: D1=50%, D2=50%
        assert abs(d1_proportion - 0.50) < 0.01  # Allow small rounding error
        assert abs(d2_proportion - 0.50) < 0.01
    
    def test_project_stock_invalid_target_year(self, baseline_stock):
        """Test that invalid target year raises ValueError."""
        scenario = {'housing_growth_rate': 0.01, 'base_year': 2025}
        
        # Target year equal to baseline year
        with pytest.raises(ValueError, match="target_year.*must be !="):
            project_stock(baseline_stock, 2025, scenario)
    
    def test_project_stock_missing_scenario_keys(self, baseline_stock):
        """Test that missing scenario keys raise ValueError."""
        # Missing housing_growth_rate
        scenario = {'base_year': 2025}
        with pytest.raises(ValueError, match="scenario missing required keys"):
            project_stock(baseline_stock, 2030, scenario)
        
        # Missing base_year
        scenario = {'housing_growth_rate': 0.01}
        with pytest.raises(ValueError, match="scenario missing required keys"):
            project_stock(baseline_stock, 2030, scenario)
    
    def test_project_stock_invalid_growth_rate(self, baseline_stock):
        """Test that invalid growth rate raises ValueError."""
        # Negative growth rate too low
        scenario = {'housing_growth_rate': -0.06, 'base_year': 2025}
        with pytest.raises(ValueError, match="housing_growth_rate must be in"):
            project_stock(baseline_stock, 2030, scenario)
        
        # Growth rate too high
        scenario = {'housing_growth_rate': 0.06, 'base_year': 2025}
        with pytest.raises(ValueError, match="housing_growth_rate must be in"):
            project_stock(baseline_stock, 2030, scenario)
    
    def test_project_stock_new_units_calculation(self, baseline_stock):
        """Test that new units are calculated correctly."""
        scenario = {'housing_growth_rate': 0.05, 'base_year': 2025}
        projected = project_stock(baseline_stock, 2026, scenario)
        
        # Expected: 100 * 1.05 = 105, so 5 new units
        expected_new_units = 5
        actual_new_units = projected.total_units - baseline_stock.total_units
        assert actual_new_units == expected_new_units
    
    def test_project_stock_segment_totals_match(self, baseline_stock):
        """Test that segment totals sum to projected total units."""
        scenario = {'housing_growth_rate': 0.02, 'base_year': 2025}
        projected = project_stock(baseline_stock, 2030, scenario)
        
        segment_total = sum(projected.units_by_segment.values())
        assert segment_total == projected.total_units
    
    def test_project_stock_district_totals_match(self, baseline_stock):
        """Test that district totals sum to projected total units."""
        scenario = {'housing_growth_rate': 0.015, 'base_year': 2025}
        projected = project_stock(baseline_stock, 2030, scenario)
        
        district_total = sum(projected.units_by_district.values())
        assert district_total == projected.total_units
    
    def test_project_stock_year_attribute(self, baseline_stock):
        """Test that projected stock has correct year attribute."""
        scenario = {'housing_growth_rate': 0.01, 'base_year': 2025}
        
        for target_year in [2026, 2030, 2035, 2050]:
            projected = project_stock(baseline_stock, target_year, scenario)
            assert projected.year == target_year
    
    def test_project_stock_multiple_segments(self):
        """Test projection with multiple segments."""
        premises_data = {
            'blinded_id': [f'P{i}' for i in range(200)],
            'segment_code': ['RESSF'] * 100 + ['RESMF'] * 60 + ['MOBILE'] * 40,
            'district_code_IRP': ['D1'] * 100 + ['D2'] * 100,
        }
        premises = pd.DataFrame(premises_data)
        
        baseline = HousingStock(
            year=2025,
            premises=premises,
            total_units=200,
            units_by_segment={'RESSF': 100, 'RESMF': 60, 'MOBILE': 40},
            units_by_district={'D1': 100, 'D2': 100}
        )
        
        scenario = {'housing_growth_rate': 0.01, 'base_year': 2025}
        projected = project_stock(baseline, 2030, scenario)
        
        # Check that all segments are present
        assert 'RESSF' in projected.units_by_segment
        assert 'RESMF' in projected.units_by_segment
        assert 'MOBILE' in projected.units_by_segment
        
        # Check proportions are maintained
        ressf_prop = projected.units_by_segment['RESSF'] / projected.total_units
        assert abs(ressf_prop - 0.50) < 0.02  # 100/200 = 50%
    
    def test_project_stock_round_trip_consistency(self, baseline_stock):
        """Test that projecting forward then backward recovers the baseline.
        
        This is a consistency check: if we project from year Y to year Y+N with
        growth rate r, then project backward from Y+N to Y with the inverse growth
        rate (1/(1+r) - 1), we should recover approximately the original baseline.
        
        The key insight: to reverse a forward projection with growth rate r over
        N years, we project forward again with the inverse growth rate over the
        same N years. This is because:
        - Forward: P(Y+N) = P(Y) * (1+r)^N
        - Backward: P(Y) = P(Y+N) * (1+r_inv)^N where r_inv = 1/(1+r) - 1
        
        Note: Due to rounding in the proportional distribution of units across
        segments and districts, the round-trip may not be exact, but should be
        within 1-2 units for reasonable growth rates and time horizons.
        """
        growth_rate = 0.02
        scenario_forward = {'housing_growth_rate': growth_rate, 'base_year': 2025}
        
        # Project forward from 2025 to 2035 (10 years)
        projected_forward = project_stock(baseline_stock, 2035, scenario_forward)
        forward_total = projected_forward.total_units
        assert forward_total > baseline_stock.total_units
        
        # To reverse growth, we need the inverse growth rate
        # r_inv = 1/(1+r) - 1
        inverse_growth_rate = 1.0 / (1 + growth_rate) - 1
        
        # Now project forward again from 2035 to 2045 (another 10 years) with inverse rate
        # This simulates going backward in time mathematically
        scenario_backward = {'housing_growth_rate': inverse_growth_rate, 'base_year': 2035}
        projected_backward = project_stock(projected_forward, 2045, scenario_backward)
        
        # Check that we recover approximately the original baseline
        # Allow for rounding errors in proportional distribution
        assert abs(projected_backward.total_units - baseline_stock.total_units) <= 2
