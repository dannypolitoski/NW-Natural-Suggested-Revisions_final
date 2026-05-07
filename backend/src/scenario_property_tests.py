"""
Property-based tests for scenario management module.

Tests scenario determinism (Property 13) and validation (Property 14).
Generates HTML and Markdown reports with test results and visualizations.
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
import json
from datetime import datetime

from src.scenarios import ScenarioConfig, validate_scenario, run_scenario, compare_scenarios
from src.config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_path: str) -> str:
    """Encode image file to base64 string for embedding in HTML."""
    import base64
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def validate_scenario_determinism(
    config: ScenarioConfig,
    premise_equipment: pd.DataFrame,
    weather_data: pd.DataFrame,
    water_temp_data: pd.DataFrame,
    baseload_factors: Dict[str, float]
) -> Dict[str, Any]:
    """
    Property 13: Running the same config twice should produce identical results.
    
    Runs the same scenario twice and compares results for exact equality.
    
    Args:
        config: ScenarioConfig to test
        premise_equipment: DataFrame with premise-equipment data
        weather_data: DataFrame with weather data
        water_temp_data: DataFrame with water temperature data
        baseload_factors: Dict mapping end_use to annual consumption
    
    Returns:
        Dict with keys:
            - 'passed': bool, True if results are identical
            - 'run1_rows': int, number of rows in first run
            - 'run2_rows': int, number of rows in second run
            - 'max_abs_diff': float, maximum absolute difference in therms
            - 'max_rel_diff': float, maximum relative difference in therms
            - 'differences': DataFrame with any differences found
    """
    logger.info(f"Testing scenario determinism for '{config.name}'")
    
    # Run scenario twice
    results1, meta1 = run_scenario(config, premise_equipment, weather_data, water_temp_data, baseload_factors)
    results2, meta2 = run_scenario(config, premise_equipment, weather_data, water_temp_data, baseload_factors)
    
    # Compare results
    results1_sorted = results1.sort_values(['year', 'end_use', 'scenario_name']).reset_index(drop=True)
    results2_sorted = results2.sort_values(['year', 'end_use', 'scenario_name']).reset_index(drop=True)
    
    # Check if DataFrames are identical
    identical = results1_sorted.equals(results2_sorted)
    
    # Compute differences
    if identical:
        max_abs_diff = 0.0
        max_rel_diff = 0.0
        differences = pd.DataFrame()
    else:
        # Merge results for comparison
        merged = results1_sorted.merge(
            results2_sorted,
            on=['year', 'end_use', 'scenario_name'],
            suffixes=('_run1', '_run2'),
            how='outer'
        )
        
        # Compute absolute and relative differences
        merged['abs_diff'] = (merged['total_therms_run1'] - merged['total_therms_run2']).abs()
        merged['rel_diff'] = (merged['abs_diff'] / (merged['total_therms_run1'].abs() + 1e-6)) * 100
        
        max_abs_diff = merged['abs_diff'].max()
        max_rel_diff = merged['rel_diff'].max()
        
        # Filter to rows with differences
        differences = merged[merged['abs_diff'] > 1e-6][
            ['year', 'end_use', 'total_therms_run1', 'total_therms_run2', 'abs_diff', 'rel_diff']
        ].copy()
    
    passed = identical and max_abs_diff < 1e-6
    
    logger.info(
        f"Scenario determinism test: passed={passed}, "
        f"max_abs_diff={max_abs_diff:.6f}, max_rel_diff={max_rel_diff:.6f}"
    )
    
    return {
        'passed': passed,
        'run1_rows': len(results1),
        'run2_rows': len(results2),
        'max_abs_diff': max_abs_diff,
        'max_rel_diff': max_rel_diff,
        'differences': differences,
        'results1': results1_sorted,
        'results2': results2_sorted,
    }


def validate_scenario_validation() -> Dict[str, Any]:
    """
    Property 14: validate_scenario should warn for rates outside [0,1] and horizon <= 0.
    
    Tests validation logic with various parameter combinations.
    
    Returns:
        Dict with keys:
            - 'passed': bool, True if all validation checks work correctly
            - 'test_cases': DataFrame with test case results
            - 'summary': Dict with pass/fail counts
    """
    logger.info("Testing scenario validation logic")
    
    test_cases = []
    
    # Test case 1: Valid baseline scenario
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
    test_cases.append({
        'test_name': 'Valid baseline',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': True,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == True and len(result['errors']) == 0
    })
    
    # Test case 2: Negative forecast_horizon (should error)
    config = ScenarioConfig(
        name='negative_horizon',
        forecast_horizon=-5
    )
    result = validate_scenario(config)
    test_cases.append({
        'test_name': 'Negative forecast_horizon',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': False,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == False and len(result['errors']) > 0
    })
    
    # Test case 3: Zero forecast_horizon (should error)
    config = ScenarioConfig(
        name='zero_horizon',
        forecast_horizon=0
    )
    result = validate_scenario(config)
    test_cases.append({
        'test_name': 'Zero forecast_horizon',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': False,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == False and len(result['errors']) > 0
    })
    
    # Test case 4: housing_growth_rate > 1.0 (should error)
    config = ScenarioConfig(
        name='high_growth',
        housing_growth_rate=1.5
    )
    result = validate_scenario(config)
    test_cases.append({
        'test_name': 'housing_growth_rate > 1.0',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': False,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == False and len(result['errors']) > 0
    })
    
    # Test case 5: electrification_rate > 1.0 (should error)
    config = ScenarioConfig(
        name='high_electrification',
        electrification_rate=1.5
    )
    result = validate_scenario(config)
    test_cases.append({
        'test_name': 'electrification_rate > 1.0',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': False,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == False and len(result['errors']) > 0
    })
    
    # Test case 6: efficiency_improvement > 1.0 (should error)
    config = ScenarioConfig(
        name='high_efficiency',
        efficiency_improvement=1.5
    )
    result = validate_scenario(config)
    test_cases.append({
        'test_name': 'efficiency_improvement > 1.0',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': False,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == False and len(result['errors']) > 0
    })
    
    # Test case 7: Invalid weather_assumption (should error)
    config = ScenarioConfig(
        name='invalid_weather',
        weather_assumption='extreme'
    )
    result = validate_scenario(config)
    test_cases.append({
        'test_name': 'Invalid weather_assumption',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': False,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == False and len(result['errors']) > 0
    })
    
    # Test case 8: All rates at boundary (0.0) - should be valid
    config = ScenarioConfig(
        name='zero_rates',
        housing_growth_rate=0.0,
        electrification_rate=0.0,
        efficiency_improvement=0.0
    )
    result = validate_scenario(config)
    test_cases.append({
        'test_name': 'All rates at 0.0',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': True,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == True and len(result['errors']) == 0
    })
    
    # Test case 9: All rates at upper boundary (0.05) - should be valid
    config = ScenarioConfig(
        name='max_rates',
        housing_growth_rate=0.05,
        electrification_rate=0.05,
        efficiency_improvement=0.05
    )
    result = validate_scenario(config)
    test_cases.append({
        'test_name': 'All rates at 0.05',
        'config_name': config.name,
        'housing_growth_rate': config.housing_growth_rate,
        'electrification_rate': config.electrification_rate,
        'efficiency_improvement': config.efficiency_improvement,
        'forecast_horizon': config.forecast_horizon,
        'expected_valid': True,
        'actual_valid': result['valid'],
        'warnings': len(result['warnings']),
        'errors': len(result['errors']),
        'passed': result['valid'] == True and len(result['errors']) == 0
    })
    
    # Convert to DataFrame
    test_df = pd.DataFrame(test_cases)
    
    # Check if all tests passed
    all_passed = test_df['passed'].all()
    
    summary = {
        'total_tests': len(test_df),
        'passed_tests': test_df['passed'].sum(),
        'failed_tests': (~test_df['passed']).sum(),
        'all_passed': all_passed
    }
    
    logger.info(
        f"Scenario validation tests: {summary['passed_tests']}/{summary['total_tests']} passed"
    )
    
    return {
        'passed': all_passed,
        'test_cases': test_df,
        'summary': summary
    }


def generate_property13_report(
    determinism_result: Dict[str, Any],
    output_dir: str = "output/scenarios"
) -> None:
    """
    Generate HTML and Markdown reports for Property 13 (scenario determinism).
    
    Args:
        determinism_result: Result dict from validate_scenario_determinism
        output_dir: Directory to save reports
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create comparison table
    comparison_data = []
    for idx, row in determinism_result['results1'].iterrows():
        run2_row = determinism_result['results2'][
            (determinism_result['results2']['year'] == row['year']) &
            (determinism_result['results2']['end_use'] == row['end_use'])
        ]
        if not run2_row.empty:
            run2_therms = run2_row['total_therms'].values[0]
            diff = abs(row['total_therms'] - run2_therms)
            comparison_data.append({
                'year': row['year'],
                'end_use': row['end_use'],
                'run1_therms': row['total_therms'],
                'run2_therms': run2_therms,
                'abs_diff': diff,
                'match': 'YES' if diff < 1e-6 else 'NO'
            })
    
    comparison_df = pd.DataFrame(comparison_data)
    
    # Generate HTML report
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Property 13: Scenario Determinism Test Results</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            .pass {{ color: green; font-weight: bold; }}
            .fail {{ color: red; font-weight: bold; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .summary {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>Property 13: Scenario Determinism Test Results</h1>
        <p><strong>Validates: Requirements 6.2, 6.3</strong></p>
        
        <div class="summary">
            <h2>Test Summary</h2>
            <p><strong>Status:</strong> <span class="{'pass' if determinism_result['passed'] else 'fail'}">
                {'PASSED' if determinism_result['passed'] else 'FAILED'}
            </span></p>
            <p><strong>Description:</strong> Running the same scenario configuration twice should produce identical results.</p>
            <p><strong>Run 1 Rows:</strong> {determinism_result['run1_rows']}</p>
            <p><strong>Run 2 Rows:</strong> {determinism_result['run2_rows']}</p>
            <p><strong>Max Absolute Difference:</strong> {determinism_result['max_abs_diff']:.10f} therms</p>
            <p><strong>Max Relative Difference:</strong> {determinism_result['max_rel_diff']:.6f}%</p>
        </div>
        
        <h2>Side-by-Side Comparison (First 20 rows)</h2>
        <table>
            <tr>
                <th>Year</th>
                <th>End Use</th>
                <th>Run 1 Therms</th>
                <th>Run 2 Therms</th>
                <th>Absolute Difference</th>
                <th>Match</th>
            </tr>
    """
    
    for idx, row in comparison_df.head(20).iterrows():
        html_content += f"""
            <tr>
                <td>{row['year']}</td>
                <td>{row['end_use']}</td>
                <td>{row['run1_therms']:.2f}</td>
                <td>{row['run2_therms']:.2f}</td>
                <td>{row['abs_diff']:.10f}</td>
                <td>{row['match']}</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <h2>Interpretation</h2>
        <p>If the test PASSED, the scenario produces deterministic results (identical output for identical input).
        This is critical for reproducibility and validation.</p>
        <p>If the test FAILED, there may be non-deterministic elements in the simulation (e.g., random number generation,
        floating-point rounding differences, or data loading order issues).</p>
    </body>
    </html>
    """
    
    # Write HTML report
    html_path = output_path / 'property13_results.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Wrote HTML report to {html_path}")
    
    # Generate Markdown report
    md_content = f"""# Property 13: Scenario Determinism Test Results

**Validates: Requirements 6.2, 6.3**

## Test Summary

- **Status:** {'✓ PASSED' if determinism_result['passed'] else '✗ FAILED'}
- **Description:** Running the same scenario configuration twice should produce identical results.
- **Run 1 Rows:** {determinism_result['run1_rows']}
- **Run 2 Rows:** {determinism_result['run2_rows']}
- **Max Absolute Difference:** {determinism_result['max_abs_diff']:.10f} therms
- **Max Relative Difference:** {determinism_result['max_rel_diff']:.6f}%

## Side-by-Side Comparison (First 20 rows)

| Year | End Use | Run 1 Therms | Run 2 Therms | Absolute Difference | Match |
|------|---------|--------------|--------------|---------------------|-------|
"""
    
    for idx, row in comparison_df.head(20).iterrows():
        md_content += f"| {row['year']} | {row['end_use']} | {row['run1_therms']:.2f} | {row['run2_therms']:.2f} | {row['abs_diff']:.10f} | {row['match']} |\n"
    
    md_content += """
## Interpretation

If the test **PASSED**, the scenario produces deterministic results (identical output for identical input).
This is critical for reproducibility and validation.

If the test **FAILED**, there may be non-deterministic elements in the simulation (e.g., random number generation,
floating-point rounding differences, or data loading order issues).
"""
    
    # Write Markdown report
    md_path = output_path / 'property13_results.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    logger.info(f"Wrote Markdown report to {md_path}")


def generate_property14_report(
    validation_result: Dict[str, Any],
    output_dir: str = "output/scenarios"
) -> None:
    """
    Generate HTML and Markdown reports for Property 14 (scenario validation).
    
    Args:
        validation_result: Result dict from validate_scenario_validation
        output_dir: Directory to save reports
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    test_df = validation_result['test_cases']
    summary = validation_result['summary']
    
    # Generate HTML report
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Property 14: Scenario Validation Test Results</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            .pass {{ color: green; font-weight: bold; }}
            .fail {{ color: red; font-weight: bold; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .summary {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>Property 14: Scenario Validation Test Results</h1>
        <p><strong>Validates: Requirements 6.4</strong></p>
        
        <div class="summary">
            <h2>Test Summary</h2>
            <p><strong>Status:</strong> <span class="{'pass' if validation_result['passed'] else 'fail'}">
                {'PASSED' if validation_result['passed'] else 'FAILED'}
            </span></p>
            <p><strong>Description:</strong> validate_scenario should warn for rates outside [0,1] and horizon <= 0.</p>
            <p><strong>Total Tests:</strong> {summary['total_tests']}</p>
            <p><strong>Passed:</strong> {summary['passed_tests']}</p>
            <p><strong>Failed:</strong> {summary['failed_tests']}</p>
        </div>
        
        <h2>Test Cases with Expected vs Actual Results</h2>
        <table>
            <tr>
                <th>Test Name</th>
                <th>housing_growth_rate</th>
                <th>electrification_rate</th>
                <th>efficiency_improvement</th>
                <th>forecast_horizon</th>
                <th>Expected Valid</th>
                <th>Actual Valid</th>
                <th>Warnings</th>
                <th>Errors</th>
                <th>Result</th>
            </tr>
    """
    
    for idx, row in test_df.iterrows():
        result_class = 'pass' if row['passed'] else 'fail'
        result_text = '✓ PASS' if row['passed'] else '✗ FAIL'
        html_content += f"""
            <tr>
                <td>{row['test_name']}</td>
                <td>{row['housing_growth_rate']:.4f}</td>
                <td>{row['electrification_rate']:.4f}</td>
                <td>{row['efficiency_improvement']:.4f}</td>
                <td>{row['forecast_horizon']}</td>
                <td>{row['expected_valid']}</td>
                <td>{row['actual_valid']}</td>
                <td>{row['warnings']}</td>
                <td>{row['errors']}</td>
                <td class="{result_class}">{result_text}</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <h2>Interpretation</h2>
        <p>The validation function should:</p>
        <ul>
            <li>Accept valid parameter ranges: rates in [0.0, 1.0], horizon > 0</li>
            <li>Reject invalid parameter ranges: rates outside [0.0, 1.0], horizon <= 0</li>
            <li>Warn for unusual but technically valid values (e.g., very long horizons)</li>
            <li>Provide clear error messages for invalid combinations</li>
        </ul>
    </body>
    </html>
    """
    
    # Write HTML report
    html_path = output_path / 'property14_results.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"Wrote HTML report to {html_path}")
    
    # Generate Markdown report
    md_content = f"""# Property 14: Scenario Validation Test Results

**Validates: Requirements 6.4**

## Test Summary

- **Status:** {'✓ PASSED' if validation_result['passed'] else '✗ FAILED'}
- **Description:** validate_scenario should warn for rates outside [0,1] and horizon <= 0.
- **Total Tests:** {summary['total_tests']}
- **Passed:** {summary['passed_tests']}
- **Failed:** {summary['failed_tests']}

## Test Cases with Expected vs Actual Results

| Test Name | housing_growth_rate | electrification_rate | efficiency_improvement | forecast_horizon | Expected Valid | Actual Valid | Warnings | Errors | Result |
|-----------|---------------------|----------------------|------------------------|------------------|----------------|--------------|----------|--------|--------|
"""
    
    for idx, row in test_df.iterrows():
        result_text = '✓ PASS' if row['passed'] else '✗ FAIL'
        md_content += f"| {row['test_name']} | {row['housing_growth_rate']:.4f} | {row['electrification_rate']:.4f} | {row['efficiency_improvement']:.4f} | {row['forecast_horizon']} | {row['expected_valid']} | {row['actual_valid']} | {row['warnings']} | {row['errors']} | {result_text} |\n"
    
    md_content += """
## Interpretation

The validation function should:

- Accept valid parameter ranges: rates in [0.0, 1.0], horizon > 0
- Reject invalid parameter ranges: rates outside [0.0, 1.0], horizon <= 0
- Warn for unusual but technically valid values (e.g., very long horizons)
- Provide clear error messages for invalid combinations
"""
    
    # Write Markdown report
    md_path = output_path / 'property14_results.md'
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    logger.info(f"Wrote Markdown report to {md_path}")
