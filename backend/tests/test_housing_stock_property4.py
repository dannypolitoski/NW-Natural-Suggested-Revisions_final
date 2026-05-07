"""
Property-based test for housing stock projection formula.

**Validates: Requirements 2.3, 6.3**

Property 4: Projected total_units = baseline × (1 + growth_rate)^(years), within rounding tolerance
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import pandas as pd
import numpy as np
from pathlib import Path
import json
import base64
from io import BytesIO

from src.housing_stock import HousingStock, build_baseline_stock, project_stock


# ============================================================================
# Property-Based Test Strategies
# ============================================================================

def create_test_premise_equipment(num_premises: int, num_segments: int = 2) -> pd.DataFrame:
    """Create a test premise-equipment DataFrame with specified number of premises."""
    segments = [f"SEG{i}" for i in range(num_segments)]
    districts = [f"D{i}" for i in range(3)]
    
    data = {
        'blinded_id': range(1, num_premises + 1),
        'segment_code': [segments[i % num_segments] for i in range(num_premises)],
        'district_code_IRP': [districts[i % 3] for i in range(num_premises)],
        'equipment_type_code': ['FURNACE'] * num_premises,
        'equipment_class': ['HEAT'] * num_premises,
    }
    return pd.DataFrame(data)


@st.composite
def projection_scenarios(draw):
    """Generate valid projection scenarios with baseline units, growth rate, and years."""
    baseline_units = draw(st.integers(min_value=100, max_value=100000))
    growth_rate = draw(st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False))
    years_to_project = draw(st.integers(min_value=1, max_value=20))
    
    return {
        'baseline_units': baseline_units,
        'growth_rate': growth_rate,
        'years_to_project': years_to_project,
    }


# ============================================================================
# Property 4: Projection Formula Correctness
# ============================================================================

@given(projection_scenarios())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property4_projection_formula(scenario):
    """
    Property 4: Projected total_units = baseline × (1 + growth_rate)^(years), within rounding tolerance
    
    This property validates that the projection formula is mathematically correct.
    The projected total units should equal the baseline multiplied by the compound growth factor,
    within a rounding tolerance of ±1 unit (due to integer rounding).
    """
    baseline_units = scenario['baseline_units']
    growth_rate = scenario['growth_rate']
    years_to_project = scenario['years_to_project']
    
    # Create baseline housing stock
    premise_equipment = create_test_premise_equipment(baseline_units)
    baseline = build_baseline_stock(premise_equipment, base_year=2025)
    
    # Verify baseline total_units matches input
    assert baseline.total_units == baseline_units, \
        f"Baseline total_units {baseline.total_units} != {baseline_units}"
    
    # Project to future year
    target_year = 2025 + years_to_project
    scenario_config = {
        'housing_growth_rate': growth_rate,
        'base_year': 2025,
    }
    projected = project_stock(baseline, target_year, scenario_config)
    
    # Calculate expected projected units using the formula
    expected_projected_units = baseline_units * ((1 + growth_rate) ** years_to_project)
    expected_projected_units_rounded = int(round(expected_projected_units))
    
    # Verify projection formula: projected = baseline × (1 + r)^t
    # Allow ±1 unit tolerance due to rounding
    assert abs(projected.total_units - expected_projected_units_rounded) <= 1, \
        f"Projection formula failed: projected={projected.total_units}, " \
        f"expected={expected_projected_units_rounded}, " \
        f"baseline={baseline_units}, growth_rate={growth_rate}, years={years_to_project}"
    
    # Verify segment distribution is maintained proportionally
    # Note: Due to rounding in proportional allocation, allow ±1 unit tolerance
    total_projected_by_segment = sum(projected.units_by_segment.values())
    assert abs(total_projected_by_segment - projected.total_units) <= 1, \
        f"Segment distribution sum {total_projected_by_segment} != total {projected.total_units}"
    
    # Verify district distribution is maintained proportionally
    # Note: Due to rounding in proportional allocation, allow ±1 unit tolerance
    total_projected_by_district = sum(projected.units_by_district.values())
    assert abs(total_projected_by_district - projected.total_units) <= 1, \
        f"District distribution sum {total_projected_by_district} != total {projected.total_units}"
    
    # Verify segment proportions are preserved (within rounding tolerance)
    for segment, baseline_count in baseline.units_by_segment.items():
        baseline_proportion = baseline_count / baseline.total_units
        projected_count = projected.units_by_segment.get(segment, 0)
        projected_proportion = projected_count / projected.total_units if projected.total_units > 0 else 0
        
        # Allow 2% tolerance for rounding effects
        assert abs(projected_proportion - baseline_proportion) <= 0.02, \
            f"Segment {segment} proportion changed: baseline={baseline_proportion:.4f}, " \
            f"projected={projected_proportion:.4f}"
    
    # Verify district proportions are preserved (within rounding tolerance)
    for district, baseline_count in baseline.units_by_district.items():
        baseline_proportion = baseline_count / baseline.total_units
        projected_count = projected.units_by_district.get(district, 0)
        projected_proportion = projected_count / projected.total_units if projected.total_units > 0 else 0
        
        # Allow 2% tolerance for rounding effects
        assert abs(projected_proportion - baseline_proportion) <= 0.02, \
            f"District {district} proportion changed: baseline={baseline_proportion:.4f}, " \
            f"projected={projected_proportion:.4f}"


# ============================================================================
# Unit Tests for Projection Formula
# ============================================================================

class TestProjectionFormula:
    """Unit tests for the projection formula with known examples."""
    
    def test_zero_growth_rate(self):
        """With zero growth rate, projected units should equal baseline."""
        baseline_units = 1000
        premise_equipment = create_test_premise_equipment(baseline_units)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        scenario_config = {
            'housing_growth_rate': 0.0,
            'base_year': 2025,
        }
        projected = project_stock(baseline, 2030, scenario_config)
        
        assert projected.total_units == baseline_units
    
    def test_positive_growth_rate(self):
        """With positive growth rate, projected units should increase."""
        baseline_units = 1000
        premise_equipment = create_test_premise_equipment(baseline_units)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        scenario_config = {
            'housing_growth_rate': 0.02,  # 2% annual growth
            'base_year': 2025,
        }
        projected = project_stock(baseline, 2030, scenario_config)  # 5 years
        
        # Expected: 1000 * (1.02)^5 = 1104.08
        expected = int(round(1000 * (1.02 ** 5)))
        assert projected.total_units == expected
    
    def test_negative_growth_rate(self):
        """With negative growth rate, projected units should decrease."""
        baseline_units = 1000
        premise_equipment = create_test_premise_equipment(baseline_units)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        scenario_config = {
            'housing_growth_rate': -0.01,  # -1% annual decline
            'base_year': 2025,
        }
        projected = project_stock(baseline, 2030, scenario_config)  # 5 years
        
        # Expected: 1000 * (0.99)^5 = 950.59
        expected = int(round(1000 * (0.99 ** 5)))
        assert projected.total_units == expected
    
    def test_segment_distribution_preserved(self):
        """Segment distribution should be preserved in projection."""
        baseline_units = 1000
        premise_equipment = create_test_premise_equipment(baseline_units, num_segments=3)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        scenario_config = {
            'housing_growth_rate': 0.03,
            'base_year': 2025,
        }
        projected = project_stock(baseline, 2030, scenario_config)
        
        # Check that segment proportions are preserved
        for segment in baseline.units_by_segment:
            baseline_prop = baseline.units_by_segment[segment] / baseline.total_units
            projected_prop = projected.units_by_segment[segment] / projected.total_units
            
            # Allow small tolerance for rounding
            assert abs(baseline_prop - projected_prop) < 0.01
    
    def test_district_distribution_preserved(self):
        """District distribution should be preserved in projection."""
        baseline_units = 1000
        premise_equipment = create_test_premise_equipment(baseline_units)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        scenario_config = {
            'housing_growth_rate': 0.02,
            'base_year': 2025,
        }
        projected = project_stock(baseline, 2030, scenario_config)
        
        # Check that district proportions are preserved
        for district in baseline.units_by_district:
            baseline_prop = baseline.units_by_district[district] / baseline.total_units
            projected_prop = projected.units_by_district[district] / projected.total_units
            
            # Allow small tolerance for rounding
            assert abs(baseline_prop - projected_prop) < 0.01
    
    def test_backward_projection(self):
        """Backward projection (negative years) should work correctly."""
        baseline_units = 1000
        premise_equipment = create_test_premise_equipment(baseline_units)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        scenario_config = {
            'housing_growth_rate': 0.02,
            'base_year': 2025,
        }
        # Project backward to 2020 (5 years back)
        projected = project_stock(baseline, 2020, scenario_config)
        
        # Expected: 1000 * (1.02)^(-5) = 905.73
        expected = int(round(1000 * (1.02 ** -5)))
        assert projected.total_units == expected


# ============================================================================
# Visualization Tests
# ============================================================================

class TestProjectionVisualizations:
    """Tests for generating projection visualizations."""
    
    def test_generate_projection_data(self):
        """Generate projection data for visualization."""
        baseline_units = 5000
        premise_equipment = create_test_premise_equipment(baseline_units, num_segments=2)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        # Project multiple years
        years = list(range(2025, 2036))
        projections = [baseline]
        
        scenario_config = {
            'housing_growth_rate': 0.015,
            'base_year': 2025,
        }
        
        for year in years[1:]:
            projected = project_stock(projections[-1], year, scenario_config)
            projections.append(projected)
        
        # Verify we have projections for all years
        assert len(projections) == len(years)
        
        # Verify total units increase monotonically with positive growth
        for i in range(1, len(projections)):
            assert projections[i].total_units >= projections[i-1].total_units
    
    def test_segment_distribution_over_time(self):
        """Verify segment distribution remains consistent over projection period."""
        baseline_units = 5000
        premise_equipment = create_test_premise_equipment(baseline_units, num_segments=2)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        baseline_segment_props = {
            seg: count / baseline.total_units 
            for seg, count in baseline.units_by_segment.items()
        }
        
        # Project to 2035
        scenario_config = {
            'housing_growth_rate': 0.02,
            'base_year': 2025,
        }
        projected = project_stock(baseline, 2035, scenario_config)
        
        projected_segment_props = {
            seg: count / projected.total_units 
            for seg, count in projected.units_by_segment.items()
        }
        
        # Verify proportions are preserved
        for segment in baseline_segment_props:
            assert abs(baseline_segment_props[segment] - projected_segment_props[segment]) < 0.01
    
    def test_district_distribution_over_time(self):
        """Verify district distribution remains consistent over projection period."""
        baseline_units = 5000
        premise_equipment = create_test_premise_equipment(baseline_units)
        baseline = build_baseline_stock(premise_equipment, base_year=2025)
        
        baseline_district_props = {
            dist: count / baseline.total_units 
            for dist, count in baseline.units_by_district.items()
        }
        
        # Project to 2035
        scenario_config = {
            'housing_growth_rate': 0.02,
            'base_year': 2025,
        }
        projected = project_stock(baseline, 2035, scenario_config)
        
        projected_district_props = {
            dist: count / projected.total_units 
            for dist, count in projected.units_by_district.items()
        }
        
        # Verify proportions are preserved
        for district in baseline_district_props:
            assert abs(baseline_district_props[district] - projected_district_props[district]) < 0.01


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
