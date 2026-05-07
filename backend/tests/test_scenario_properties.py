"""
Property-based tests for scenario management (Properties 13 and 14).

Tests scenario determinism and validation logic.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from src.scenarios import ScenarioConfig, validate_scenario
from src.scenario_property_tests import (
    validate_scenario_validation,
    generate_property14_report
)


class TestScenarioProperties:
    """Tests for scenario properties."""
    
    def test_property14_scenario_validation(self):
        """
        Property 14: validate_scenario should warn for rates outside [0,1] and horizon <= 0.
        
        Validates: Requirements 6.4
        """
        result = validate_scenario_validation()
        
        # Check that all tests passed
        assert bool(result['passed']), "Property 14 validation tests failed"
        assert result['summary']['failed_tests'] == 0, "Some validation tests failed"
        assert result['summary']['passed_tests'] > 0, "No validation tests passed"
        
        # Verify test cases DataFrame has expected structure
        test_df = result['test_cases']
        assert 'test_name' in test_df.columns
        assert 'expected_valid' in test_df.columns
        assert 'actual_valid' in test_df.columns
        assert 'passed' in test_df.columns
        
        # Verify specific test cases
        # Test case: negative horizon should fail
        negative_horizon_test = test_df[test_df['test_name'] == 'Negative forecast_horizon']
        assert not negative_horizon_test.empty
        assert bool(negative_horizon_test['passed'].values[0])
        
        # Test case: zero horizon should fail
        zero_horizon_test = test_df[test_df['test_name'] == 'Zero forecast_horizon']
        assert not zero_horizon_test.empty
        assert bool(zero_horizon_test['passed'].values[0])
        
        # Test case: valid baseline should pass
        valid_test = test_df[test_df['test_name'] == 'Valid baseline']
        assert not valid_test.empty
        assert bool(valid_test['passed'].values[0])
    
    def test_property14_report_generation(self, tmp_path):
        """Test that Property 14 report generation works."""
        result = validate_scenario_validation()
        
        # Generate reports
        output_dir = str(tmp_path / 'scenarios')
        generate_property14_report(result, output_dir)
        
        # Verify output files exist
        html_path = Path(output_dir) / 'property14_results.html'
        md_path = Path(output_dir) / 'property14_results.md'
        
        assert html_path.exists(), f"HTML report not created at {html_path}"
        assert md_path.exists(), f"Markdown report not created at {md_path}"
        
        # Verify content
        html_content = html_path.read_text()
        assert 'Property 14' in html_content
        assert 'PASSED' in html_content or 'FAILED' in html_content
        
        md_content = md_path.read_text()
        assert 'Property 14' in md_content
        assert 'PASSED' in md_content or 'FAILED' in md_content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
