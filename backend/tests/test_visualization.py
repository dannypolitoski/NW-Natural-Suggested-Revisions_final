"""
Tests for housing stock visualization module.

Tests the visualization functions to ensure they generate correct plots
and handle edge cases properly.
"""

import pytest
import pandas as pd
import matplotlib.pyplot as plt
import tempfile
import os
from src.housing_stock import HousingStock
from src.visualization import (
    plot_housing_stock_comparison,
    plot_segment_distribution_comparison,
    plot_district_distribution_comparison,
    plot_growth_rate_analysis,
    plot_projection_summary
)


class TestVisualization:
    """Test suite for visualization functions."""
    
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
            units_by_district={'D1': 50, 'D2': 50}
        )
    
    @pytest.fixture
    def projected_stocks(self, baseline_stock):
        """Create projected housing stocks for testing."""
        stocks = {}
        for year in [2026, 2027, 2028]:
            factor = (year - 2025) * 0.02
            total = int(baseline_stock.total_units * (1 + factor))
            stocks[year] = HousingStock(
                year=year,
                premises=baseline_stock.premises.copy(),
                total_units=total,
                units_by_segment={
                    'RESSF': int(70 * (1 + factor)),
                    'RESMF': int(30 * (1 + factor))
                },
                units_by_district={
                    'D1': int(50 * (1 + factor)),
                    'D2': int(50 * (1 + factor))
                }
            )
        return stocks
    
    def test_plot_housing_stock_comparison_creates_figure(self, baseline_stock, projected_stocks):
        """Test that plot_housing_stock_comparison creates a valid figure."""
        projected_data = {year: stock.total_units for year, stock in projected_stocks.items()}
        
        fig = plot_housing_stock_comparison(
            baseline_stock.year,
            baseline_stock.total_units,
            projected_data
        )
        
        assert fig is not None
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) > 0
        plt.close(fig)
    
    def test_plot_housing_stock_comparison_saves_file(self, baseline_stock, projected_stocks):
        """Test that plot_housing_stock_comparison saves to file."""
        projected_data = {year: stock.total_units for year, stock in projected_stocks.items()}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_plot.png")
            
            fig = plot_housing_stock_comparison(
                baseline_stock.year,
                baseline_stock.total_units,
                projected_data,
                output_path=output_path
            )
            
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            plt.close(fig)
    
    def test_plot_segment_distribution_comparison_creates_figure(self, baseline_stock, projected_stocks):
        """Test that plot_segment_distribution_comparison creates a valid figure."""
        projected_segments = {year: stock.units_by_segment for year, stock in projected_stocks.items()}
        
        fig = plot_segment_distribution_comparison(
            baseline_stock.year,
            baseline_stock.units_by_segment,
            projected_segments
        )
        
        assert fig is not None
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) > 0
        plt.close(fig)
    
    def test_plot_segment_distribution_comparison_saves_file(self, baseline_stock, projected_stocks):
        """Test that plot_segment_distribution_comparison saves to file."""
        projected_segments = {year: stock.units_by_segment for year, stock in projected_stocks.items()}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_segments.png")
            
            fig = plot_segment_distribution_comparison(
                baseline_stock.year,
                baseline_stock.units_by_segment,
                projected_segments,
                output_path=output_path
            )
            
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            plt.close(fig)
    
    def test_plot_district_distribution_comparison_creates_figure(self, baseline_stock, projected_stocks):
        """Test that plot_district_distribution_comparison creates a valid figure."""
        projected_districts = {year: stock.units_by_district for year, stock in projected_stocks.items()}
        
        fig = plot_district_distribution_comparison(
            baseline_stock.year,
            baseline_stock.units_by_district,
            projected_districts
        )
        
        assert fig is not None
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) > 0
        plt.close(fig)
    
    def test_plot_district_distribution_comparison_saves_file(self, baseline_stock, projected_stocks):
        """Test that plot_district_distribution_comparison saves to file."""
        projected_districts = {year: stock.units_by_district for year, stock in projected_stocks.items()}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_districts.png")
            
            fig = plot_district_distribution_comparison(
                baseline_stock.year,
                baseline_stock.units_by_district,
                projected_districts,
                output_path=output_path
            )
            
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            plt.close(fig)
    
    def test_plot_growth_rate_analysis_creates_figure(self, baseline_stock, projected_stocks):
        """Test that plot_growth_rate_analysis creates a valid figure."""
        projected_data = {year: stock.total_units for year, stock in projected_stocks.items()}
        
        fig = plot_growth_rate_analysis(
            baseline_stock.year,
            baseline_stock.total_units,
            projected_data,
            growth_rate=0.02
        )
        
        assert fig is not None
        assert isinstance(fig, plt.Figure)
        assert len(fig.axes) > 0
        plt.close(fig)
    
    def test_plot_growth_rate_analysis_saves_file(self, baseline_stock, projected_stocks):
        """Test that plot_growth_rate_analysis saves to file."""
        projected_data = {year: stock.total_units for year, stock in projected_stocks.items()}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "test_growth.png")
            
            fig = plot_growth_rate_analysis(
                baseline_stock.year,
                baseline_stock.total_units,
                projected_data,
                growth_rate=0.02,
                output_path=output_path
            )
            
            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0
            plt.close(fig)
    
    def test_plot_projection_summary_creates_all_plots(self, baseline_stock, projected_stocks):
        """Test that plot_projection_summary creates all expected plots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plots = plot_projection_summary(
                baseline_stock.year,
                baseline_stock,
                projected_stocks,
                growth_rate=0.02,
                output_dir=tmpdir,
                show_plots=False
            )
            
            # Check that all expected plots were created
            assert 'total_housing_stock' in plots
            assert 'segment_distribution' in plots
            assert 'district_distribution' in plots
            assert 'growth_rate_analysis' in plots
            
            # Check that files exist
            for plot_name, plot_path in plots.items():
                assert os.path.exists(plot_path), f"Plot {plot_name} not found at {plot_path}"
                assert os.path.getsize(plot_path) > 0, f"Plot {plot_name} is empty"
    
    def test_plot_projection_summary_creates_output_directory(self, baseline_stock, projected_stocks):
        """Test that plot_projection_summary creates output directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "nested", "output", "dir")
            
            plots = plot_projection_summary(
                baseline_stock.year,
                baseline_stock,
                projected_stocks,
                growth_rate=0.02,
                output_dir=output_dir,
                show_plots=False
            )
            
            assert os.path.exists(output_dir)
            assert len(plots) == 4
    
    def test_plot_housing_stock_comparison_with_custom_figsize(self, baseline_stock, projected_stocks):
        """Test that custom figsize is applied correctly."""
        projected_data = {year: stock.total_units for year, stock in projected_stocks.items()}
        
        fig = plot_housing_stock_comparison(
            baseline_stock.year,
            baseline_stock.total_units,
            projected_data,
            figsize=(16, 8)
        )
        
        assert fig.get_figwidth() == 16
        assert fig.get_figheight() == 8
        plt.close(fig)
    
    def test_plot_housing_stock_comparison_with_custom_title(self, baseline_stock, projected_stocks):
        """Test that custom title is applied correctly."""
        projected_data = {year: stock.total_units for year, stock in projected_stocks.items()}
        custom_title = "Custom Housing Stock Title"
        
        fig = plot_housing_stock_comparison(
            baseline_stock.year,
            baseline_stock.total_units,
            projected_data,
            title=custom_title
        )
        
        # Check that title is in the figure (check axes title)
        ax = fig.axes[0]
        assert custom_title in ax.get_title()
        plt.close(fig)
    
    def test_plot_with_zero_growth(self, baseline_stock):
        """Test plotting with zero growth rate."""
        projected_data = {2026: 100, 2027: 100, 2028: 100}
        
        fig = plot_housing_stock_comparison(
            baseline_stock.year,
            baseline_stock.total_units,
            projected_data
        )
        
        assert fig is not None
        plt.close(fig)
    
    def test_plot_with_negative_growth(self, baseline_stock):
        """Test plotting with negative growth rate (decline)."""
        projected_data = {2026: 98, 2027: 96, 2028: 94}
        
        fig = plot_housing_stock_comparison(
            baseline_stock.year,
            baseline_stock.total_units,
            projected_data
        )
        
        assert fig is not None
        plt.close(fig)
