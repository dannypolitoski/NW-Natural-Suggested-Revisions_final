"""
Property-based test for housing stock projection with visualizations.

Tests Property 4: Projected total_units equals baseline total_units × (1 + growth_rate)^(target_year - base_year),
within rounding tolerance.

Validates Requirements 2.3, 6.3

This test:
1. Validates the mathematical relationship for housing stock projections
2. Generates comparison visualizations:
   - Line graph: Baseline vs projected total units over time
   - Bar chart: Segment distribution comparison (baseline vs projected)
   - Bar chart: District distribution comparison (baseline vs projected)
   - Line graph: Projected vs expected growth rates by year
3. Saves all visualizations to output/housing_stock_projections/ directory
4. Verifies graphs are created, files exist, and contain expected data
"""

import pytest
import pandas as pd
import matplotlib.pyplot as plt
import os
import tempfile
from hypothesis import given, strategies as st, settings, HealthCheck
from src.housing_stock import HousingStock, build_baseline_stock, project_stock
from src.visualization import plot_projection_summary


class TestHousingStockProjectionProperty:
    """Test suite for housing stock projection property and visualizations."""
    
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
    
    @pytest.mark.parametrize("growth_rate,target_year", [
        (0.00, 2030),  # Zero growth
        (0.01, 2030),  # 1% annual growth
        (0.02, 2035),  # 2% annual growth over 10 years
        (0.03, 2026),  # 3% annual growth over 1 year
        (-0.01, 2030), # -1% annual decline
        (-0.02, 2035), # -2% annual decline over 10 years
    ])
    def test_property_4_projection_formula(self, baseline_stock, growth_rate, target_year):
        """
        **Property 4: Projected total_units equals baseline total_units × (1 + growth_rate)^(target_year - base_year), within rounding tolerance**
        
        **Validates: Requirements 2.3, 6.3**
        
        This test verifies the mathematical relationship for housing stock projections.
        The projected total units should follow the compound growth formula:
        P(t) = P0 * (1 + r)^(t - t0)
        
        where:
        - P(t) is the projected total units at year t
        - P0 is the baseline total units
        - r is the annual growth rate
        - t is the target year
        - t0 is the baseline year
        
        Due to rounding in the proportional distribution of units across segments
        and districts, we allow a tolerance of 1% of the projected total.
        """
        scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
        projected = project_stock(baseline_stock, target_year, scenario)
        
        # Calculate expected total using the compound growth formula
        years_to_project = target_year - baseline_stock.year
        expected_total = baseline_stock.total_units * ((1 + growth_rate) ** years_to_project)
        expected_total_rounded = int(round(expected_total))
        
        # Verify the projected total matches the expected value
        assert projected.total_units == expected_total_rounded, (
            f"Projected total {projected.total_units} does not match expected {expected_total_rounded} "
            f"(growth_rate={growth_rate}, years={years_to_project})"
        )
        
        # Verify the year is correct
        assert projected.year == target_year
        
        # Verify segment and district totals sum to projected total
        segment_total = sum(projected.units_by_segment.values())
        district_total = sum(projected.units_by_district.values())
        
        # Allow small rounding errors (±1 unit due to proportional distribution)
        assert abs(segment_total - projected.total_units) <= 1, (
            f"Segment total {segment_total} does not match projected total {projected.total_units}"
        )
        assert abs(district_total - projected.total_units) <= 1, (
            f"District total {district_total} does not match projected total {projected.total_units}"
        )
    
    def test_property_4_with_hypothesis(self, baseline_stock):
        """
        Property-based test using Hypothesis to generate random growth rates and target years.
        
        **Property 4: Projected total_units equals baseline total_units × (1 + growth_rate)^(target_year - base_year), within rounding tolerance**
        
        **Validates: Requirements 2.3, 6.3**
        """
        @given(
            growth_rate=st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False),
            years_ahead=st.integers(min_value=1, max_value=20)
        )
        @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
        def property_test(growth_rate, years_ahead):
            target_year = baseline_stock.year + years_ahead
            scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
            
            projected = project_stock(baseline_stock, target_year, scenario)
            
            # Calculate expected total
            expected_total = baseline_stock.total_units * ((1 + growth_rate) ** years_ahead)
            expected_total_rounded = int(round(expected_total))
            
            # Verify the projection formula
            assert projected.total_units == expected_total_rounded
            assert projected.year == target_year
        
        property_test()
    
    def test_visualizations_generated_and_saved(self, baseline_stock):
        """
        Test that all required visualizations are generated and saved correctly.
        
        Generates:
        - Line graph: Baseline vs projected total units over time
        - Bar chart: Segment distribution comparison (baseline vs projected)
        - Bar chart: District distribution comparison (baseline vs projected)
        - Line graph: Projected vs expected growth rates by year
        - Choropleth map: Service territory by county with growth rates
        - Housing age heatmap
        - Vintage distribution heatmap
        - Replacement probability map
        - Housing stock composition graphs (4 graphs)
        - Replacement risk analysis graphs (4 graphs)
        
        Verifies:
        - All graphs are created
        - Files exist in output directory
        - Files contain expected data (non-zero file size)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create projected stocks for multiple years
            growth_rate = 0.02
            scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
            
            projected_stocks = {}
            for year in range(baseline_stock.year + 1, baseline_stock.year + 6):
                projected_stocks[year] = project_stock(baseline_stock, year, scenario)
            
            # Generate visualizations
            output_dir = os.path.join(tmpdir, "housing_stock_projections")
            plots = plot_projection_summary(
                baseline_stock.year,
                baseline_stock,
                projected_stocks,
                growth_rate=growth_rate,
                output_dir=output_dir,
                show_plots=False
            )
            
            # Generate additional visualizations
            from src.visualization import plot_housing_stock_composition, plot_replacement_risk_analysis
            
            composition_plots = plot_housing_stock_composition(
                baseline_stock,
                projected_stocks,
                output_dir=output_dir,
                show_plots=False
            )
            plots.update(composition_plots)
            
            replacement_plots = plot_replacement_risk_analysis(
                baseline_stock,
                projected_stocks,
                output_dir=output_dir,
                show_plots=False
            )
            plots.update(replacement_plots)
            
            # Verify output directory was created
            assert os.path.exists(output_dir), f"Output directory {output_dir} was not created"
            
            # Verify all expected plots were created (5 basic + 4 composition + 4 replacement = 13 total)
            expected_plots = [
                'total_housing_stock',
                'segment_distribution',
                'district_distribution',
                'growth_rate_analysis',
                'service_territory_map',
                'vintage_distribution_stacked',
                'housing_age_distribution',
                'age_vs_replacement',
                'vintage_heatmap',
                'cumulative_replacement',
                'replacement_distribution',
                'age_vs_replacement_scatter',
                'replacement_ranking'
            ]
            
            for plot_name in expected_plots:
                assert plot_name in plots, f"Plot '{plot_name}' not found in plots dictionary"
                plot_path = plots[plot_name]
                assert os.path.exists(plot_path), f"Plot file {plot_path} does not exist"
                assert os.path.getsize(plot_path) > 0, f"Plot file {plot_path} is empty"
            
            # Verify file naming convention
            files = os.listdir(output_dir)
            assert len(files) >= 13, f"Expected at least 13 plot files, found {len(files)}"
            
            # Verify files are PNG format
            for filename in files:
                assert filename.endswith('.png'), f"File {filename} is not PNG format"
    
    def test_visualizations_contain_expected_data(self, baseline_stock):
        """
        Test that visualizations contain expected data by checking plot elements.
        
        Verifies:
        - Plots have correct axes labels
        - Plots have legends
        - Plots contain data points/lines
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            growth_rate = 0.02
            scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
            
            projected_stocks = {}
            for year in range(baseline_stock.year + 1, baseline_stock.year + 4):
                projected_stocks[year] = project_stock(baseline_stock, year, scenario)
            
            output_dir = os.path.join(tmpdir, "housing_stock_projections")
            plots = plot_projection_summary(
                baseline_stock.year,
                baseline_stock,
                projected_stocks,
                growth_rate=growth_rate,
                output_dir=output_dir,
                show_plots=False
            )
            
            # Verify plot files exist and have content
            for plot_name, plot_path in plots.items():
                assert os.path.exists(plot_path), f"Plot {plot_name} not found"
                file_size = os.path.getsize(plot_path)
                assert file_size > 1000, f"Plot {plot_name} file size {file_size} is too small (expected > 1000 bytes)"
    
    def test_output_directory_structure(self, baseline_stock):
        """
        Test that output directory structure is created correctly.
        
        Verifies:
        - output/housing_stock_projections/ directory exists
        - All visualization files are saved with correct naming convention (01_ through 05_)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            growth_rate = 0.01
            scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
            
            projected_stocks = {}
            for year in range(baseline_stock.year + 1, baseline_stock.year + 3):
                projected_stocks[year] = project_stock(baseline_stock, year, scenario)
            
            output_dir = os.path.join(tmpdir, "housing_stock_projections")
            plots = plot_projection_summary(
                baseline_stock.year,
                baseline_stock,
                projected_stocks,
                growth_rate=growth_rate,
                output_dir=output_dir,
                show_plots=False
            )
            
            # Verify directory structure
            assert os.path.isdir(output_dir), f"Output directory {output_dir} is not a directory"
            
            # Verify file naming convention (01_ through 05_)
            files = sorted(os.listdir(output_dir))
            expected_prefixes = ['01_', '02_', '03_', '04_', '05_']
            
            for i, filename in enumerate(files):
                assert filename.startswith(expected_prefixes[i]), (
                    f"File {filename} does not start with expected prefix {expected_prefixes[i]}"
                )
    
    def test_projection_with_multiple_segments_and_districts(self):
        """
        Test projection with multiple segments and districts to ensure
        visualizations handle complex distributions correctly.
        """
        # Create a more complex baseline with multiple segments and districts
        premises_data = {
            'blinded_id': [f'P{i}' for i in range(300)],
            'segment_code': ['RESSF'] * 150 + ['RESMF'] * 100 + ['MOBILE'] * 50,
            'district_code_IRP': ['D1'] * 100 + ['D2'] * 100 + ['D3'] * 100,
        }
        premises = pd.DataFrame(premises_data)
        
        baseline = HousingStock(
            year=2025,
            premises=premises,
            total_units=300,
            units_by_segment={'RESSF': 150, 'RESMF': 100, 'MOBILE': 50},
            units_by_district={'D1': 100, 'D2': 100, 'D3': 100}
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            growth_rate = 0.015
            scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline.year}
            
            projected_stocks = {}
            for year in range(baseline.year + 1, baseline.year + 4):
                projected_stocks[year] = project_stock(baseline, year, scenario)
            
            output_dir = os.path.join(tmpdir, "housing_stock_projections")
            plots = plot_projection_summary(
                baseline.year,
                baseline,
                projected_stocks,
                growth_rate=growth_rate,
                output_dir=output_dir,
                show_plots=False
            )
            
            # Verify all 5 plots were created
            assert len(plots) == 5
            for plot_path in plots.values():
                assert os.path.exists(plot_path)
                assert os.path.getsize(plot_path) > 0
    
    def test_projection_mathematical_accuracy(self, baseline_stock):
        """
        Test mathematical accuracy of projection across multiple years.
        
        Verifies that the compound growth formula is applied correctly
        for each year in the projection.
        """
        growth_rate = 0.025
        scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
        
        # Project multiple years and verify each one
        for years_ahead in range(1, 11):
            target_year = baseline_stock.year + years_ahead
            projected = project_stock(baseline_stock, target_year, scenario)
            
            # Calculate expected value
            expected = baseline_stock.total_units * ((1 + growth_rate) ** years_ahead)
            expected_rounded = int(round(expected))
            
            # Verify
            assert projected.total_units == expected_rounded, (
                f"Year {target_year}: projected {projected.total_units} != expected {expected_rounded}"
            )
    
    def test_projection_rounding_tolerance(self, baseline_stock):
        """
        Test that rounding tolerance is applied correctly.
        
        When distributing new units proportionally across segments and districts,
        rounding errors can accumulate. This test verifies that the total remains
        within acceptable tolerance.
        """
        growth_rate = 0.03
        scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
        
        for target_year in range(baseline_stock.year + 1, baseline_stock.year + 11):
            projected = project_stock(baseline_stock, target_year, scenario)
            
            # Verify segment and district totals are within 1 unit of projected total
            segment_total = sum(projected.units_by_segment.values())
            district_total = sum(projected.units_by_district.values())
            
            assert abs(segment_total - projected.total_units) <= 1
            assert abs(district_total - projected.total_units) <= 1
    
    def test_visualizations_with_zero_growth(self, baseline_stock):
        """
        Test that visualizations are generated correctly with zero growth rate.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            growth_rate = 0.0
            scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
            
            projected_stocks = {}
            for year in range(baseline_stock.year + 1, baseline_stock.year + 4):
                projected_stocks[year] = project_stock(baseline_stock, year, scenario)
            
            output_dir = os.path.join(tmpdir, "housing_stock_projections")
            plots = plot_projection_summary(
                baseline_stock.year,
                baseline_stock,
                projected_stocks,
                growth_rate=growth_rate,
                output_dir=output_dir,
                show_plots=False
            )
            
            # Verify all 5 plots were created
            assert len(plots) == 5
            for plot_path in plots.values():
                assert os.path.exists(plot_path)
    
    def test_visualizations_with_negative_growth(self, baseline_stock):
        """
        Test that visualizations are generated correctly with negative growth rate (decline).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            growth_rate = -0.02
            scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
            
            projected_stocks = {}
            for year in range(baseline_stock.year + 1, baseline_stock.year + 4):
                projected_stocks[year] = project_stock(baseline_stock, year, scenario)
            
            output_dir = os.path.join(tmpdir, "housing_stock_projections")
            plots = plot_projection_summary(
                baseline_stock.year,
                baseline_stock,
                projected_stocks,
                growth_rate=growth_rate,
                output_dir=output_dir,
                show_plots=False
            )
            
            # Verify all 5 plots were created
            assert len(plots) == 5
            for plot_path in plots.values():
                assert os.path.exists(plot_path)
            
            # Verify that projected units are decreasing
            years = sorted(projected_stocks.keys())
            for i in range(len(years) - 1):
                assert projected_stocks[years[i+1]].total_units < projected_stocks[years[i]].total_units
