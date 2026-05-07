"""
Test for Property 8 water heating delta report generation.

Validates that the property 8 report is generated correctly with all visualizations.
"""

import pytest
from pathlib import Path
from src.water_heating_property_report import generate_property8_report


class TestProperty8Report:
    """Test Property 8 report generation."""
    
    def test_generate_property8_report(self):
        """Test that Property 8 report is generated with all required outputs."""
        output_dir = "output/water_heating"
        
        # Generate report
        result = generate_property8_report(output_dir)
        
        # Verify results structure
        assert 'validation_results' in result
        assert 'html_path' in result
        assert 'md_path' in result
        assert 'viz_files' in result
        
        # Verify validation results
        val_results = result['validation_results']
        assert val_results['test_passed'] is True
        assert val_results['avg_delta_t'] > 0
        assert bool(val_results['all_positive']) is True
        
        # Verify files exist
        html_path = Path(result['html_path'])
        md_path = Path(result['md_path'])
        
        assert html_path.exists(), f"HTML report not found at {html_path}"
        assert md_path.exists(), f"Markdown report not found at {md_path}"
        
        # Verify HTML content
        with open(html_path, 'r') as f:
            html_content = f.read()
            assert 'Property 8' in html_content
            assert 'PASSED' in html_content
            assert 'Water Heating Delta-T' in html_content
        
        # Verify Markdown content
        with open(md_path, 'r') as f:
            md_content = f.read()
            assert 'Property 8' in md_content
            assert 'PASSED' in md_content
            assert 'Water Heating Delta-T' in md_content
        
        # Verify visualization files
        viz_files = result['viz_files']
        assert 'daily_delta_t' in viz_files
        assert 'seasonal_delta_t' in viz_files
        assert 'water_air_temp_scatter' in viz_files
        assert 'wh_demand_by_station' in viz_files
        
        for key, filepath in viz_files.items():
            assert Path(filepath).exists(), f"Visualization file {filepath} not found"
