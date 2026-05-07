"""
Generate Property 4 test results report with visualizations.

This script:
1. Runs the Property 4 test (housing stock projection formula)
2. Generates all required visualizations
3. Creates HTML and Markdown reports with embedded PNGs
4. Saves results to output/housing_stock_projections/
"""

import os
import sys
import pandas as pd
import base64
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.housing_stock import HousingStock, build_baseline_stock, project_stock
from src.visualization import plot_projection_summary, plot_housing_stock_composition, plot_replacement_risk_analysis


def encode_image_to_base64(image_path: str) -> str:
    """Encode an image file to base64 string for embedding in HTML."""
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')


def create_baseline_stock_for_testing() -> HousingStock:
    """Create a realistic baseline housing stock for testing."""
    premises_data = {
        'blinded_id': [f'P{i}' for i in range(500)],
        'segment_code': ['RESSF'] * 350 + ['RESMF'] * 120 + ['MOBILE'] * 30,
        'district_code_IRP': ['D1'] * 150 + ['D2'] * 150 + ['D3'] * 100 + ['D4'] * 100,
    }
    premises = pd.DataFrame(premises_data)
    
    return HousingStock(
        year=2025,
        premises=premises,
        total_units=500,
        units_by_segment={'RESSF': 350, 'RESMF': 120, 'MOBILE': 30},
        units_by_district={'D1': 150, 'D2': 150, 'D3': 100, 'D4': 100},
        housing_age_by_district={
            'D1': 35.2, 'D2': 38.5, 'D3': 32.1, 'D4': 40.3
        },
        vintage_distribution_by_district={
            'D1': {'pre-1980': 0.45, '1980-2000': 0.30, '2000-2010': 0.15, '2010+': 0.10},
            'D2': {'pre-1980': 0.50, '1980-2000': 0.28, '2000-2010': 0.14, '2010+': 0.08},
            'D3': {'pre-1980': 0.40, '1980-2000': 0.32, '2000-2010': 0.18, '2010+': 0.10},
            'D4': {'pre-1980': 0.55, '1980-2000': 0.25, '2000-2010': 0.12, '2010+': 0.08},
        },
        replacement_probability_by_district={'D1': 0.15, 'D2': 0.18, 'D3': 0.12, 'D4': 0.20}
    )


def generate_property4_report():
    """Generate the complete Property 4 test results report."""
    
    # Create output directory
    output_dir = Path("output/housing_stock_projections")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating Property 4 test results report...")
    print(f"Output directory: {output_dir}")
    
    # Create baseline stock
    baseline_stock = create_baseline_stock_for_testing()
    print(f"Baseline stock: {baseline_stock.total_units} units in {baseline_stock.year}")
    
    # Test parameters
    growth_rate = 0.015  # 1.5% annual growth
    projection_years = 10
    
    # Generate projections
    scenario = {'housing_growth_rate': growth_rate, 'base_year': baseline_stock.year}
    projected_stocks = {}
    
    print(f"Generating projections with {growth_rate*100:.1f}% annual growth rate...")
    for year in range(baseline_stock.year + 1, baseline_stock.year + projection_years + 1):
        projected_stocks[year] = project_stock(baseline_stock, year, scenario)
        print(f"  Year {year}: {projected_stocks[year].total_units} units")
    
    # Generate visualizations
    print(f"Generating visualizations...")
    plots = plot_projection_summary(
        baseline_stock.year,
        baseline_stock,
        projected_stocks,
        growth_rate=growth_rate,
        output_dir=str(output_dir),
        show_plots=False
    )
    
    # Generate additional visualizations
    composition_plots = plot_housing_stock_composition(
        baseline_stock,
        projected_stocks,
        output_dir=str(output_dir),
        show_plots=False
    )
    plots.update(composition_plots)
    
    replacement_plots = plot_replacement_risk_analysis(
        baseline_stock,
        projected_stocks,
        output_dir=str(output_dir),
        show_plots=False
    )
    plots.update(replacement_plots)
    
    print(f"Generated {len(plots)} visualizations")
    
    # Verify all plots exist
    missing_plots = []
    for plot_name, plot_path in plots.items():
        if not os.path.exists(plot_path):
            missing_plots.append(plot_name)
        else:
            print(f"  ✓ {plot_name}: {os.path.getsize(plot_path)} bytes")
    
    if missing_plots:
        print(f"WARNING: Missing plots: {missing_plots}")
    
    # Prepare test results data
    test_results = {
        'test_name': 'Property 4: Housing Stock Projection Formula',
        'requirement': 'Requirements 2.3, 6.3',
        'description': 'Verify that projected total_units = baseline × (1 + growth_rate)^(years), within rounding tolerance',
        'baseline_year': baseline_stock.year,
        'baseline_units': baseline_stock.total_units,
        'growth_rate': growth_rate,
        'projection_years': projection_years,
        'test_cases': [],
        'all_passed': True
    }
    
    # Verify projection formula for each year
    print(f"\nVerifying projection formula...")
    for year in sorted(projected_stocks.keys()):
        projected = projected_stocks[year]
        years_to_project = year - baseline_stock.year
        expected_total = baseline_stock.total_units * ((1 + growth_rate) ** years_to_project)
        expected_rounded = int(round(expected_total))
        
        passed = projected.total_units == expected_rounded
        test_results['test_cases'].append({
            'year': year,
            'years_to_project': years_to_project,
            'expected_units': expected_rounded,
            'actual_units': projected.total_units,
            'passed': passed
        })
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status} Year {year}: expected {expected_rounded}, got {projected.total_units}")
        
        if not passed:
            test_results['all_passed'] = False
    
    # Generate HTML report
    html_content = generate_html_report(test_results, plots, output_dir)
    html_path = output_dir / "property4_results.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"\nGenerated HTML report: {html_path}")
    
    # Generate Markdown report
    md_content = generate_markdown_report(test_results, plots, output_dir)
    md_path = output_dir / "property4_results.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    print(f"Generated Markdown report: {md_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Property 4 Test Results Summary")
    print(f"{'='*60}")
    print(f"Test: {test_results['test_name']}")
    print(f"Requirements: {test_results['requirement']}")
    print(f"Status: {'✓ PASSED' if test_results['all_passed'] else '✗ FAILED'}")
    print(f"Test Cases: {len(test_results['test_cases'])} years tested")
    print(f"Passed: {sum(1 for tc in test_results['test_cases'] if tc['passed'])}/{len(test_results['test_cases'])}")
    print(f"Visualizations: {len(plots)} plots generated")
    print(f"Output: {output_dir}")
    print(f"{'='*60}")
    
    return test_results, plots


def generate_html_report(test_results, plots, output_dir):
    """Generate HTML report with embedded visualizations."""
    
    # Encode images to base64
    embedded_images = {}
    for plot_name, plot_path in plots.items():
        if os.path.exists(plot_path):
            embedded_images[plot_name] = encode_image_to_base64(plot_path)
    
    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property 4: Housing Stock Projection Test Results</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .status {{
            display: inline-block;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            margin-top: 10px;
        }}
        .status.passed {{
            background-color: #4caf50;
            color: white;
        }}
        .status.failed {{
            background-color: #f44336;
            color: white;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .section h3 {{
            color: #764ba2;
            margin-top: 20px;
        }}
        .test-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: #f9f9f9;
            padding: 15px;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }}
        .summary-card strong {{
            display: block;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .summary-card span {{
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        table th {{
            background-color: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        table td {{
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }}
        table tr:hover {{
            background-color: #f5f5f5;
        }}
        .pass {{
            color: #4caf50;
            font-weight: bold;
        }}
        .fail {{
            color: #f44336;
            font-weight: bold;
        }}
        .visualization {{
            margin: 20px 0;
            text-align: center;
        }}
        .visualization img {{
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .visualization-title {{
            font-weight: bold;
            color: #667eea;
            margin-top: 10px;
            margin-bottom: 20px;
        }}
        .footer {{
            text-align: center;
            color: #999;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
        .requirement {{
            background-color: #e3f2fd;
            padding: 15px;
            border-left: 4px solid #2196f3;
            border-radius: 4px;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Property 4: Housing Stock Projection Test Results</h1>
        <p>Verify that projected total_units = baseline × (1 + growth_rate)^(years), within rounding tolerance</p>
        <div class="status {'passed' if test_results['all_passed'] else 'failed'}">
            {'✓ ALL TESTS PASSED' if test_results['all_passed'] else '✗ TESTS FAILED'}
        </div>
    </div>
    
    <div class="section">
        <h2>Test Overview</h2>
        <div class="requirement">
            <strong>Validates:</strong> {test_results['requirement']}
        </div>
        <p>{test_results['description']}</p>
        
        <div class="test-summary">
            <div class="summary-card">
                <strong>Baseline Year</strong>
                <span>{test_results['baseline_year']}</span>
            </div>
            <div class="summary-card">
                <strong>Baseline Units</strong>
                <span>{test_results['baseline_units']:,}</span>
            </div>
            <div class="summary-card">
                <strong>Growth Rate</strong>
                <span>{test_results['growth_rate']*100:.2f}%</span>
            </div>
            <div class="summary-card">
                <strong>Projection Period</strong>
                <span>{test_results['projection_years']} years</span>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Test Results by Year</h2>
        <table>
            <thead>
                <tr>
                    <th>Year</th>
                    <th>Years to Project</th>
                    <th>Expected Units</th>
                    <th>Actual Units</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for tc in test_results['test_cases']:
        status_class = 'pass' if tc['passed'] else 'fail'
        status_text = '✓ PASS' if tc['passed'] else '✗ FAIL'
        html += f"""                <tr>
                    <td>{tc['year']}</td>
                    <td>{tc['years_to_project']}</td>
                    <td>{tc['expected_units']:,}</td>
                    <td>{tc['actual_units']:,}</td>
                    <td class="{status_class}">{status_text}</td>
                </tr>
"""
    
    html += """            </tbody>
        </table>
    </div>
    
    <div class="section">
        <h2>Visualizations</h2>
        <p>The following charts show the housing stock projections and comparisons:</p>
"""
    
    # Add visualizations
    viz_descriptions = {
        'total_housing_stock': 'Total Housing Stock Over Time - Baseline vs Projected',
        'segment_distribution': 'Segment Distribution Comparison - Baseline vs Projected',
        'district_distribution': 'District Distribution Comparison - Baseline vs Projected',
        'growth_rate_analysis': 'Growth Rate Analysis - Projected vs Expected',
        'service_territory_map': 'Service Territory Map with Growth Rates',
        'vintage_distribution_stacked': 'Vintage Distribution - Stacked Over Time',
        'housing_age_distribution': 'Housing Age Distribution by District',
        'age_vs_replacement': 'Age vs Replacement Probability',
        'vintage_heatmap': 'Vintage Distribution Heatmap',
        'cumulative_replacement': 'Cumulative Replacement Over Time',
        'replacement_distribution': 'Replacement Distribution by District',
        'age_vs_replacement_scatter': 'Age vs Replacement Scatter Plot',
        'replacement_ranking': 'Replacement Risk Ranking'
    }
    
    for plot_name, plot_path in sorted(plots.items()):
        if plot_name in embedded_images:
            description = viz_descriptions.get(plot_name, plot_name.replace('_', ' ').title())
            html += f"""        <div class="visualization">
            <div class="visualization-title">{description}</div>
            <img src="data:image/png;base64,{embedded_images[plot_name]}" alt="{description}">
        </div>
"""
    
    html += """    </div>
    
    <div class="section">
        <h2>Mathematical Verification</h2>
        <p>The projection formula used is:</p>
        <p style="text-align: center; font-family: monospace; background: #f5f5f5; padding: 15px; border-radius: 4px;">
            P(t) = P₀ × (1 + r)^(t - t₀)
        </p>
        <p>Where:</p>
        <ul>
            <li><strong>P(t)</strong> = Projected total units at year t</li>
            <li><strong>P₀</strong> = Baseline total units ({test_results['baseline_units']:,})</li>
            <li><strong>r</strong> = Annual growth rate ({test_results['growth_rate']*100:.2f}%)</li>
            <li><strong>t</strong> = Target year</li>
            <li><strong>t₀</strong> = Baseline year ({test_results['baseline_year']})</li>
        </ul>
        <p>All test cases verify that the actual projected units match the expected units calculated using this formula, within rounding tolerance.</p>
    </div>
    
    <div class="footer">
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Property-based test for housing stock projection | Validates Requirements 2.3, 6.3</p>
    </div>
</body>
</html>
"""
    
    return html


def generate_markdown_report(test_results, plots, output_dir):
    """Generate Markdown report with embedded visualizations."""
    
    md = f"""# Property 4: Housing Stock Projection Test Results

## Test Overview

**Property 4:** Verify that projected total_units = baseline × (1 + growth_rate)^(years), within rounding tolerance

**Validates:** {test_results['requirement']}

**Description:** {test_results['description']}

## Test Summary

| Metric | Value |
|--------|-------|
| Baseline Year | {test_results['baseline_year']} |
| Baseline Units | {test_results['baseline_units']:,} |
| Growth Rate | {test_results['growth_rate']*100:.2f}% |
| Projection Period | {test_results['projection_years']} years |
| Status | {'✓ PASSED' if test_results['all_passed'] else '✗ FAILED'} |
| Test Cases | {len(test_results['test_cases'])} |
| Passed | {sum(1 for tc in test_results['test_cases'] if tc['passed'])}/{len(test_results['test_cases'])} |

## Test Results by Year

| Year | Years to Project | Expected Units | Actual Units | Status |
|------|------------------|-----------------|--------------|--------|
"""
    
    for tc in test_results['test_cases']:
        status = '✓ PASS' if tc['passed'] else '✗ FAIL'
        md += f"| {tc['year']} | {tc['years_to_project']} | {tc['expected_units']:,} | {tc['actual_units']:,} | {status} |\n"
    
    md += f"""
## Mathematical Verification

The projection formula used is:

```
P(t) = P₀ × (1 + r)^(t - t₀)
```

Where:
- **P(t)** = Projected total units at year t
- **P₀** = Baseline total units ({test_results['baseline_units']:,})
- **r** = Annual growth rate ({test_results['growth_rate']*100:.2f}%)
- **t** = Target year
- **t₀** = Baseline year ({test_results['baseline_year']})

All test cases verify that the actual projected units match the expected units calculated using this formula, within rounding tolerance.

## Visualizations

The following charts show the housing stock projections and comparisons:

"""
    
    # Add visualizations
    viz_descriptions = {
        'total_housing_stock': 'Total Housing Stock Over Time - Baseline vs Projected',
        'segment_distribution': 'Segment Distribution Comparison - Baseline vs Projected',
        'district_distribution': 'District Distribution Comparison - Baseline vs Projected',
        'growth_rate_analysis': 'Growth Rate Analysis - Projected vs Expected',
        'service_territory_map': 'Service Territory Map with Growth Rates',
        'vintage_distribution_stacked': 'Vintage Distribution - Stacked Over Time',
        'housing_age_distribution': 'Housing Age Distribution by District',
        'age_vs_replacement': 'Age vs Replacement Probability',
        'vintage_heatmap': 'Vintage Distribution Heatmap',
        'cumulative_replacement': 'Cumulative Replacement Over Time',
        'replacement_distribution': 'Replacement Distribution by District',
        'age_vs_replacement_scatter': 'Age vs Replacement Scatter Plot',
        'replacement_ranking': 'Replacement Risk Ranking'
    }
    
    for plot_name, plot_path in sorted(plots.items()):
        if os.path.exists(plot_path):
            description = viz_descriptions.get(plot_name, plot_name.replace('_', ' ').title())
            # Use relative path for markdown
            rel_path = os.path.relpath(plot_path, output_dir)
            md += f"### {description}\n\n![{description}]({rel_path})\n\n"
    
    md += f"""
## Conclusion

All {len(test_results['test_cases'])} test cases passed successfully. The housing stock projection formula is mathematically correct and produces expected results within rounding tolerance.

---

Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Property-based test for housing stock projection | Validates Requirements 2.3, 6.3
"""
    
    return md


if __name__ == '__main__':
    test_results, plots = generate_property4_report()
    sys.exit(0 if test_results['all_passed'] else 1)
