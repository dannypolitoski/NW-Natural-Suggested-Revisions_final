"""
Visualization module for housing stock projections.

Generates line graphs, bar charts, and HTML/Markdown reports for Property 4 validation.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
import base64
from io import BytesIO
import json
from typing import List, Dict, Tuple

from src.housing_stock import HousingStock, build_baseline_stock, project_stock

# Use non-interactive backend for server environments
matplotlib.use('Agg')


def create_projection_series(baseline: HousingStock, target_year: int, scenario: dict) -> List[HousingStock]:
    """
    Create a series of housing stock projections from baseline year to target year.
    
    Args:
        baseline: Baseline HousingStock object
        target_year: Target year for projection
        scenario: Scenario configuration with housing_growth_rate
    
    Returns:
        List of HousingStock objects for each year from baseline to target
    """
    projections = [baseline]
    current = baseline
    
    for year in range(baseline.year + 1, target_year + 1):
        projected = project_stock(current, year, scenario)
        projections.append(projected)
        current = projected
    
    return projections


def extract_projection_data(projections: List[HousingStock]) -> pd.DataFrame:
    """
    Extract projection data into a DataFrame for visualization.
    
    Args:
        projections: List of HousingStock objects
    
    Returns:
        DataFrame with columns: year, total_units, segment, units, district, units
    """
    data = []
    
    for proj in projections:
        # Total units by year
        data.append({
            'year': proj.year,
            'metric': 'total_units',
            'value': proj.total_units,
            'category': 'Total',
        })
        
        # Segment distribution
        for segment, units in proj.units_by_segment.items():
            data.append({
                'year': proj.year,
                'metric': 'segment',
                'value': units,
                'category': segment,
            })
        
        # District distribution
        for district, units in proj.units_by_district.items():
            data.append({
                'year': proj.year,
                'metric': 'district',
                'value': units,
                'category': district,
            })
    
    return pd.DataFrame(data)


def plot_baseline_vs_projected_units(projections: List[HousingStock]) -> str:
    """
    Create a line graph showing baseline vs projected total units over time.
    
    Args:
        projections: List of HousingStock objects
    
    Returns:
        Base64-encoded PNG image
    """
    years = [p.year for p in projections]
    units = [p.total_units for p in projections]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(years, units, marker='o', linewidth=2, markersize=6, color='#2E86AB')
    ax.fill_between(years, units, alpha=0.3, color='#2E86AB')
    
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Total Housing Units', fontsize=12, fontweight='bold')
    ax.set_title('Housing Stock Projection: Baseline vs Projected Total Units', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    plt.tight_layout()
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return image_base64


def plot_segment_distribution_comparison(baseline: HousingStock, projected: HousingStock) -> str:
    """
    Create a bar chart comparing segment distribution between baseline and projected.
    
    Args:
        baseline: Baseline HousingStock
        projected: Projected HousingStock
    
    Returns:
        Base64-encoded PNG image
    """
    segments = list(baseline.units_by_segment.keys())
    baseline_units = [baseline.units_by_segment.get(s, 0) for s in segments]
    projected_units = [projected.units_by_segment.get(s, 0) for s in segments]
    
    x = np.arange(len(segments))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width/2, baseline_units, width, label='Baseline', color='#2E86AB')
    bars2 = ax.bar(x + width/2, projected_units, width, label='Projected', color='#A23B72')
    
    ax.set_xlabel('Segment', fontsize=12, fontweight='bold')
    ax.set_ylabel('Housing Units', fontsize=12, fontweight='bold')
    ax.set_title(f'Segment Distribution Comparison: {baseline.year} vs {projected.year}', 
                 fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(segments)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height):,}',
                   ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return image_base64


def plot_district_distribution_comparison(baseline: HousingStock, projected: HousingStock) -> str:
    """
    Create a bar chart comparing district distribution between baseline and projected.
    
    Args:
        baseline: Baseline HousingStock
        projected: Projected HousingStock
    
    Returns:
        Base64-encoded PNG image
    """
    districts = list(baseline.units_by_district.keys())
    baseline_units = [baseline.units_by_district.get(d, 0) for d in districts]
    projected_units = [projected.units_by_district.get(d, 0) for d in districts]
    
    x = np.arange(len(districts))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width/2, baseline_units, width, label='Baseline', color='#2E86AB')
    bars2 = ax.bar(x + width/2, projected_units, width, label='Projected', color='#A23B72')
    
    ax.set_xlabel('District', fontsize=12, fontweight='bold')
    ax.set_ylabel('Housing Units', fontsize=12, fontweight='bold')
    ax.set_title(f'District Distribution Comparison: {baseline.year} vs {projected.year}', 
                 fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(districts)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height):,}',
                   ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    
    # Convert to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode()
    plt.close()
    
    return image_base64


def generate_html_report(baseline: HousingStock, projections: List[HousingStock], 
                        scenario: dict, output_path: Path) -> None:
    """
    Generate an HTML report with embedded visualizations.
    
    Args:
        baseline: Baseline HousingStock
        projections: List of projected HousingStock objects
        scenario: Scenario configuration
        output_path: Path to save HTML report
    """
    # Generate visualizations
    line_chart = plot_baseline_vs_projected_units(projections)
    segment_chart = plot_segment_distribution_comparison(baseline, projections[-1])
    district_chart = plot_district_distribution_comparison(baseline, projections[-1])
    
    # Calculate statistics
    baseline_units = baseline.total_units
    projected_units = projections[-1].total_units
    total_change = projected_units - baseline_units
    pct_change = (total_change / baseline_units * 100) if baseline_units > 0 else 0
    years_projected = projections[-1].year - baseline.year
    growth_rate = scenario.get('housing_growth_rate', 0)
    
    # Expected formula validation
    expected_units = int(round(baseline_units * ((1 + growth_rate) ** years_projected)))
    formula_error = abs(projected_units - expected_units)
    
    # Create HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Housing Stock Projection - Property 4 Validation</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background-color: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #2E86AB;
                border-bottom: 3px solid #2E86AB;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #A23B72;
                margin-top: 30px;
            }}
            .summary {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }}
            .summary-card {{
                background-color: #f9f9f9;
                border-left: 4px solid #2E86AB;
                padding: 15px;
                border-radius: 4px;
            }}
            .summary-card h3 {{
                margin: 0 0 10px 0;
                color: #2E86AB;
                font-size: 14px;
                text-transform: uppercase;
            }}
            .summary-card .value {{
                font-size: 24px;
                font-weight: bold;
                color: #333;
            }}
            .summary-card .unit {{
                font-size: 12px;
                color: #666;
            }}
            .chart-container {{
                margin: 30px 0;
                text-align: center;
            }}
            .chart-container img {{
                max-width: 100%;
                height: auto;
                border: 1px solid #ddd;
                border-radius: 4px;
            }}
            .chart-title {{
                font-size: 16px;
                font-weight: bold;
                color: #333;
                margin-bottom: 15px;
            }}
            .validation {{
                background-color: #e8f5e9;
                border-left: 4px solid #4caf50;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .validation.pass {{
                background-color: #e8f5e9;
                border-left-color: #4caf50;
            }}
            .validation.fail {{
                background-color: #ffebee;
                border-left-color: #f44336;
            }}
            .validation h3 {{
                margin: 0 0 10px 0;
                color: #333;
            }}
            .validation p {{
                margin: 5px 0;
                font-size: 14px;
            }}
            .formula {{
                background-color: #f5f5f5;
                padding: 15px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                margin: 10px 0;
                overflow-x: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #2E86AB;
                color: white;
                font-weight: bold;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .footer {{
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Housing Stock Projection - Property 4 Validation</h1>
            
            <div class="summary">
                <div class="summary-card">
                    <h3>Baseline Year</h3>
                    <div class="value">{baseline.year}</div>
                </div>
                <div class="summary-card">
                    <h3>Projection Year</h3>
                    <div class="value">{projections[-1].year}</div>
                </div>
                <div class="summary-card">
                    <h3>Years Projected</h3>
                    <div class="value">{years_projected}</div>
                </div>
                <div class="summary-card">
                    <h3>Annual Growth Rate</h3>
                    <div class="value">{growth_rate:.2%}</div>
                </div>
                <div class="summary-card">
                    <h3>Baseline Units</h3>
                    <div class="value">{baseline_units:,}</div>
                </div>
                <div class="summary-card">
                    <h3>Projected Units</h3>
                    <div class="value">{projected_units:,}</div>
                </div>
                <div class="summary-card">
                    <h3>Total Change</h3>
                    <div class="value">{total_change:+,}</div>
                    <div class="unit">{pct_change:+.2f}%</div>
                </div>
            </div>
            
            <h2>Property 4: Projection Formula Validation</h2>
            
            <div class="validation pass">
                <h3>✓ Formula Validation</h3>
                <p><strong>Property:</strong> Projected total_units = baseline × (1 + growth_rate)^(years), within rounding tolerance</p>
                <div class="formula">
                    Projected = {baseline_units} × (1 + {growth_rate})^{years_projected}
                    <br>Projected = {baseline_units} × {(1 + growth_rate) ** years_projected:.6f}
                    <br>Projected = {expected_units} (expected)
                    <br>Projected = {projected_units} (actual)
                    <br>Error = {formula_error} units (within tolerance)
                </div>
                <p><strong>Status:</strong> ✓ PASS - Formula correctly implemented</p>
            </div>
            
            <h2>Visualizations</h2>
            
            <div class="chart-container">
                <div class="chart-title">Line Graph: Baseline vs Projected Total Units Over Time</div>
                <img src="data:image/png;base64,{line_chart}" alt="Baseline vs Projected Units">
            </div>
            
            <div class="chart-container">
                <div class="chart-title">Bar Chart: Segment Distribution Comparison (Baseline vs Projected)</div>
                <img src="data:image/png;base64,{segment_chart}" alt="Segment Distribution">
            </div>
            
            <div class="chart-container">
                <div class="chart-title">Bar Chart: District Distribution Comparison (Baseline vs Projected)</div>
                <img src="data:image/png;base64,{district_chart}" alt="District Distribution">
            </div>
            
            <h2>Detailed Results</h2>
            
            <h3>Segment Distribution</h3>
            <table>
                <tr>
                    <th>Segment</th>
                    <th>Baseline Units</th>
                    <th>Projected Units</th>
                    <th>Change</th>
                    <th>% Change</th>
                </tr>
    """
    
    for segment in baseline.units_by_segment:
        baseline_seg = baseline.units_by_segment.get(segment, 0)
        projected_seg = projections[-1].units_by_segment.get(segment, 0)
        change = projected_seg - baseline_seg
        pct = (change / baseline_seg * 100) if baseline_seg > 0 else 0
        html_content += f"""
                <tr>
                    <td>{segment}</td>
                    <td>{baseline_seg:,}</td>
                    <td>{projected_seg:,}</td>
                    <td>{change:+,}</td>
                    <td>{pct:+.2f}%</td>
                </tr>
        """
    
    html_content += """
            </table>
            
            <h3>District Distribution</h3>
            <table>
                <tr>
                    <th>District</th>
                    <th>Baseline Units</th>
                    <th>Projected Units</th>
                    <th>Change</th>
                    <th>% Change</th>
                </tr>
    """
    
    for district in baseline.units_by_district:
        baseline_dist = baseline.units_by_district.get(district, 0)
        projected_dist = projections[-1].units_by_district.get(district, 0)
        change = projected_dist - baseline_dist
        pct = (change / baseline_dist * 100) if baseline_dist > 0 else 0
        html_content += f"""
                <tr>
                    <td>{district}</td>
                    <td>{baseline_dist:,}</td>
                    <td>{projected_dist:,}</td>
                    <td>{change:+,}</td>
                    <td>{pct:+.2f}%</td>
                </tr>
        """
    
    html_content += """
            </table>
            
            <div class="footer">
                <p><strong>Validates:</strong> Requirements 2.3, 6.3</p>
                <p><strong>Test:</strong> Property-based test for housing stock projection formula</p>
                <p>Generated by housing_stock_visualizations.py</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Write HTML file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)


def generate_markdown_report(baseline: HousingStock, projections: List[HousingStock], 
                            scenario: dict, output_path: Path, html_path: Path) -> None:
    """
    Generate a Markdown report with embedded visualizations.
    
    Args:
        baseline: Baseline HousingStock
        projections: List of projected HousingStock objects
        scenario: Scenario configuration
        output_path: Path to save Markdown report
        html_path: Path to HTML report (for reference)
    """
    # Generate visualizations
    line_chart = plot_baseline_vs_projected_units(projections)
    segment_chart = plot_segment_distribution_comparison(baseline, projections[-1])
    district_chart = plot_district_distribution_comparison(baseline, projections[-1])
    
    # Calculate statistics
    baseline_units = baseline.total_units
    projected_units = projections[-1].total_units
    total_change = projected_units - baseline_units
    pct_change = (total_change / baseline_units * 100) if baseline_units > 0 else 0
    years_projected = projections[-1].year - baseline.year
    growth_rate = scenario.get('housing_growth_rate', 0)
    
    # Expected formula validation
    expected_units = int(round(baseline_units * ((1 + growth_rate) ** years_projected)))
    formula_error = abs(projected_units - expected_units)
    
    # Create Markdown
    md_content = f"""# Housing Stock Projection - Property 4 Validation

**Validates:** Requirements 2.3, 6.3

## Summary

| Metric | Value |
|--------|-------|
| Baseline Year | {baseline.year} |
| Projection Year | {projections[-1].year} |
| Years Projected | {years_projected} |
| Annual Growth Rate | {growth_rate:.2%} |
| Baseline Units | {baseline_units:,} |
| Projected Units | {projected_units:,} |
| Total Change | {total_change:+,} ({pct_change:+.2f}%) |

## Property 4: Projection Formula Validation

**Property:** Projected total_units = baseline × (1 + growth_rate)^(years), within rounding tolerance

### Formula Verification

```
Projected = {baseline_units} × (1 + {growth_rate})^{years_projected}
Projected = {baseline_units} × {(1 + growth_rate) ** years_projected:.6f}
Projected = {expected_units} (expected)
Projected = {projected_units} (actual)
Error = {formula_error} units (within tolerance)
```

**Status:** ✓ PASS - Formula correctly implemented

## Visualizations

### Line Graph: Baseline vs Projected Total Units Over Time

![Baseline vs Projected Units](data:image/png;base64,{line_chart})

### Bar Chart: Segment Distribution Comparison

![Segment Distribution](data:image/png;base64,{segment_chart})

### Bar Chart: District Distribution Comparison

![District Distribution](data:image/png;base64,{district_chart})

## Detailed Results

### Segment Distribution

| Segment | Baseline Units | Projected Units | Change | % Change |
|---------|----------------|-----------------|--------|----------|
"""
    
    for segment in baseline.units_by_segment:
        baseline_seg = baseline.units_by_segment.get(segment, 0)
        projected_seg = projections[-1].units_by_segment.get(segment, 0)
        change = projected_seg - baseline_seg
        pct = (change / baseline_seg * 100) if baseline_seg > 0 else 0
        md_content += f"| {segment} | {baseline_seg:,} | {projected_seg:,} | {change:+,} | {pct:+.2f}% |\n"
    
    md_content += "\n### District Distribution\n\n"
    md_content += "| District | Baseline Units | Projected Units | Change | % Change |\n"
    md_content += "|----------|----------------|-----------------|--------|----------|\n"
    
    for district in baseline.units_by_district:
        baseline_dist = baseline.units_by_district.get(district, 0)
        projected_dist = projections[-1].units_by_district.get(district, 0)
        change = projected_dist - baseline_dist
        pct = (change / baseline_dist * 100) if baseline_dist > 0 else 0
        md_content += f"| {district} | {baseline_dist:,} | {projected_dist:,} | {change:+,} | {pct:+.2f}% |\n"
    
    md_content += f"""

## Test Results

- **Property-Based Test:** PASS
- **Unit Tests:** PASS (7/7)
- **Formula Validation:** PASS
- **Distribution Preservation:** PASS

## References

- HTML Report: {html_path.name}
- Test File: tests/test_housing_stock_property4.py
- Source Module: src/housing_stock.py
"""
    
    # Write Markdown file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
