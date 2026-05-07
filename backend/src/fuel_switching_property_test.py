"""
Fuel switching conservation property test.

Validates:
- Property 6: Total equipment count before and after apply_replacements is equal

Generates comprehensive HTML and Markdown reports with visualizations:
- Pie chart: fuel type split before vs after replacements
- Bar chart: fuel switching volume by end-use category
- Stacked bar: equipment count by end-use before vs after
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
import base64
import logging
from typing import Dict, Tuple

from src.equipment import apply_replacements, build_equipment_inventory
from src.data_ingestion import build_premise_equipment_table
from src import config

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_path: str) -> str:
    """Encode image file to base64 string for embedding in HTML."""
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')


def validate_equipment_conservation(equipment_before: pd.DataFrame, equipment_after: pd.DataFrame) -> Dict:
    """
    Validate Property 6: Total equipment count before and after apply_replacements is equal.
    
    Tests that the total number of equipment units is conserved during replacement operations.
    
    Args:
        equipment_before: Equipment DataFrame before replacements
        equipment_after: Equipment DataFrame after replacements
    
    Returns:
        Dictionary with validation results
    """
    results = {
        'property_name': 'Property 6: Equipment Count Conservation',
        'test_passed': True,
        'violations': [],
        'statistics': {}
    }
    
    # Count total equipment before and after
    count_before = len(equipment_before)
    count_after = len(equipment_after)
    
    results['statistics']['total_count_before'] = count_before
    results['statistics']['total_count_after'] = count_after
    results['statistics']['difference'] = count_after - count_before
    
    # Check conservation
    if count_before != count_after:
        results['test_passed'] = False
        results['violations'].append(
            f"Equipment count not conserved: {count_before} before → {count_after} after "
            f"(difference: {count_after - count_before})"
        )
    
    # Count by end-use before and after
    before_by_enduse = equipment_before.groupby('end_use').size().to_dict()
    after_by_enduse = equipment_after.groupby('end_use').size().to_dict()
    
    results['statistics']['by_end_use_before'] = before_by_enduse
    results['statistics']['by_end_use_after'] = after_by_enduse
    
    # Check conservation per end-use
    for end_use in set(list(before_by_enduse.keys()) + list(after_by_enduse.keys())):
        count_before_eu = before_by_enduse.get(end_use, 0)
        count_after_eu = after_by_enduse.get(end_use, 0)
        
        if count_before_eu != count_after_eu:
            results['test_passed'] = False
            results['violations'].append(
                f"Equipment count not conserved for {end_use}: {count_before_eu} before → {count_after_eu} after"
            )
    
    # Count fuel type changes
    fuel_type_before = equipment_before['fuel_type'].value_counts().to_dict()
    fuel_type_after = equipment_after['fuel_type'].value_counts().to_dict()
    
    results['statistics']['fuel_type_before'] = fuel_type_before
    results['statistics']['fuel_type_after'] = fuel_type_after
    
    # Calculate fuel switching volume
    fuel_switching_volume = {}
    for end_use in config.END_USE_MAP.values():
        before_subset = equipment_before[equipment_before['end_use'] == end_use]
        after_subset = equipment_after[equipment_after['end_use'] == end_use]
        
        # Count gas equipment before and after
        gas_before = (before_subset['fuel_type'] == 'natural_gas').sum()
        gas_after = (after_subset['fuel_type'] == 'natural_gas').sum()
        
        switched = gas_before - gas_after
        fuel_switching_volume[end_use] = {
            'gas_before': gas_before,
            'gas_after': gas_after,
            'switched_to_electric': switched,
            'total_equipment': len(before_subset)
        }
    
    results['statistics']['fuel_switching_volume'] = fuel_switching_volume
    
    return results


def generate_property6_report(
    equipment_before: pd.DataFrame = None,
    equipment_after: pd.DataFrame = None,
    scenario_config: dict = None,
    output_dir: str = "output/fuel_switching"
) -> Dict:
    """
    Generate comprehensive Property 6 validation report.
    
    If equipment_before and equipment_after are not provided, generates synthetic test data.
    
    Args:
        equipment_before: Equipment DataFrame before replacements (optional)
        equipment_after: Equipment DataFrame after replacements (optional)
        scenario_config: Scenario configuration used for replacements (optional)
        output_dir: Directory to save report files
    
    Returns:
        Dictionary with validation results and file paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("Generating Property 6 fuel switching conservation report...")
    
    # If no data provided, generate synthetic test data
    if equipment_before is None or equipment_after is None:
        equipment_before, equipment_after, scenario_config = _generate_synthetic_test_data()
    
    # Run validation
    validation_results = validate_equipment_conservation(equipment_before, equipment_after)
    
    # Generate visualizations
    viz_files = _generate_visualizations(equipment_before, equipment_after, output_path)
    
    # Combine results
    report_results = {
        'property_6': validation_results,
        'overall_passed': validation_results['test_passed'],
        'timestamp': datetime.now().isoformat(),
        'scenario_config': scenario_config or {},
    }
    
    # Generate HTML report
    html_path = output_path / "property6_results.html"
    generate_html_report(report_results, equipment_before, equipment_after, viz_files, html_path)
    
    # Generate Markdown report
    md_path = output_path / "property6_results.md"
    generate_markdown_report(report_results, equipment_before, equipment_after, viz_files, md_path)
    
    logger.info(f"Property 6 report generated: {html_path}")
    logger.info(f"Property 6 report generated: {md_path}")
    
    return {
        'validation_results': report_results,
        'html_path': str(html_path),
        'md_path': str(md_path),
        'viz_files': viz_files,
    }


def _generate_synthetic_test_data() -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Generate synthetic equipment data for testing."""
    np.random.seed(42)
    
    # Create synthetic equipment before replacements
    n_equipment = 1000
    end_uses = list(config.END_USE_MAP.values())
    
    equipment_before = pd.DataFrame({
        'equipment_id': range(n_equipment),
        'end_use': np.random.choice(end_uses, n_equipment),
        'fuel_type': np.random.choice(['natural_gas', 'electric'], n_equipment, p=[0.7, 0.3]),
        'efficiency': np.random.uniform(0.6, 0.95, n_equipment),
        'install_year': np.random.randint(1990, 2020, n_equipment),
        'useful_life': 15,
        'eta': 18.5,
        'beta': 3.0,
    })
    
    # Apply replacements with scenario config
    scenario_config = {
        'electrification_rate': {
            'space_heating': 0.15,
            'water_heating': 0.10,
            'cooking': 0.05,
            'clothes_drying': 0.08,
            'fireplace': 0.0,
            'other': 0.05,
        },
        'efficiency_improvement': {
            'space_heating': 0.15,
            'water_heating': 0.20,
            'cooking': 0.10,
            'clothes_drying': 0.15,
            'fireplace': 0.0,
            'other': 0.10,
        }
    }
    
    equipment_after = apply_replacements(
        equipment_before,
        scenario_config,
        year=2025,
        random_seed=42
    )
    
    return equipment_before, equipment_after, scenario_config


def _generate_visualizations(
    equipment_before: pd.DataFrame,
    equipment_after: pd.DataFrame,
    output_path: Path
) -> Dict[str, str]:
    """Generate all visualization files for Property 6."""
    viz_files = {}
    
    # 1. Pie chart: fuel type split before vs after replacements
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    fuel_before = equipment_before['fuel_type'].value_counts()
    fuel_after = equipment_after['fuel_type'].value_counts()
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
    
    ax1.pie(fuel_before.values, labels=fuel_before.index, autopct='%1.1f%%',
            colors=colors[:len(fuel_before)], startangle=90)
    ax1.set_title('Fuel Type Distribution BEFORE Replacements', fontsize=12, fontweight='bold')
    
    ax2.pie(fuel_after.values, labels=fuel_after.index, autopct='%1.1f%%',
            colors=colors[:len(fuel_after)], startangle=90)
    ax2.set_title('Fuel Type Distribution AFTER Replacements', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    pie_path = output_path / "fuel_type_split.png"
    plt.savefig(pie_path, dpi=150, bbox_inches='tight')
    plt.close()
    viz_files['fuel_type_split'] = str(pie_path)
    
    # 2. Bar chart: fuel switching volume by end-use category
    end_uses = equipment_before['end_use'].unique()
    switching_data = []
    
    for end_use in sorted(end_uses):
        before_subset = equipment_before[equipment_before['end_use'] == end_use]
        after_subset = equipment_after[equipment_after['end_use'] == end_use]
        
        gas_before = (before_subset['fuel_type'] == 'natural_gas').sum()
        gas_after = (after_subset['fuel_type'] == 'natural_gas').sum()
        switched = gas_before - gas_after
        
        switching_data.append({
            'end_use': end_use,
            'switched': switched,
            'gas_before': gas_before,
            'gas_after': gas_after,
        })
    
    switching_df = pd.DataFrame(switching_data)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x_pos = np.arange(len(switching_df))
    bars = ax.bar(x_pos, switching_df['switched'], color='#FF6B6B', alpha=0.8, edgecolor='black')
    
    ax.set_xlabel('End-Use Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Units Switched to Electric', fontsize=12, fontweight='bold')
    ax.set_title('Fuel Switching Volume by End-Use Category', fontsize=14, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(switching_df['end_use'], rotation=45, ha='right')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    switching_path = output_path / "fuel_switching_volume.png"
    plt.savefig(switching_path, dpi=150, bbox_inches='tight')
    plt.close()
    viz_files['fuel_switching_volume'] = str(switching_path)
    
    # 3. Stacked bar: equipment count by end-use before vs after
    fig, ax = plt.subplots(figsize=(12, 6))
    
    end_use_counts_before = equipment_before['end_use'].value_counts().sort_index()
    end_use_counts_after = equipment_after['end_use'].value_counts().sort_index()
    
    # Ensure both have same index
    all_end_uses = sorted(set(list(end_use_counts_before.index) + list(end_use_counts_after.index)))
    before_counts = [end_use_counts_before.get(eu, 0) for eu in all_end_uses]
    after_counts = [end_use_counts_after.get(eu, 0) for eu in all_end_uses]
    
    x_pos = np.arange(len(all_end_uses))
    width = 0.35
    
    bars1 = ax.bar(x_pos - width/2, before_counts, width, label='Before', 
                   color='#4ECDC4', alpha=0.8, edgecolor='black')
    bars2 = ax.bar(x_pos + width/2, after_counts, width, label='After',
                   color='#45B7D1', alpha=0.8, edgecolor='black')
    
    ax.set_xlabel('End-Use Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('Equipment Count', fontsize=12, fontweight='bold')
    ax.set_title('Equipment Count by End-Use: Before vs After Replacements', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(all_end_uses, rotation=45, ha='right')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    stacked_path = output_path / "equipment_count_comparison.png"
    plt.savefig(stacked_path, dpi=150, bbox_inches='tight')
    plt.close()
    viz_files['equipment_count_comparison'] = str(stacked_path)
    
    return viz_files


def generate_html_report(
    report_results: dict,
    equipment_before: pd.DataFrame,
    equipment_after: pd.DataFrame,
    viz_files: dict,
    output_path: Path
) -> str:
    """Generate HTML report with embedded visualizations."""
    
    # Encode images to base64
    images_b64 = {}
    for key, filepath in viz_files.items():
        if Path(filepath).exists():
            images_b64[key] = encode_image_to_base64(filepath)
    
    validation_results = report_results['property_6']
    overall_status = "[PASSED]" if report_results['overall_passed'] else "[FAILED]"
    status_color = "#28a745" if report_results['overall_passed'] else "#dc3545"
    
    # Build statistics table
    stats = validation_results['statistics']
    
    fuel_switching_html = "<h3>Fuel Switching Volume by End-Use</h3>\n<table border='1' cellpadding='8'>\n"
    fuel_switching_html += "<tr><th>End-Use</th><th>Gas Before</th><th>Gas After</th><th>Switched to Electric</th><th>Total Equipment</th></tr>\n"
    
    for end_use, data in stats['fuel_switching_volume'].items():
        fuel_switching_html += f"""<tr>
            <td>{end_use}</td>
            <td>{data['gas_before']}</td>
            <td>{data['gas_after']}</td>
            <td>{data['switched_to_electric']}</td>
            <td>{data['total_equipment']}</td>
        </tr>\n"""
    
    fuel_switching_html += "</table>\n"
    
    # Build violations list
    violations_html = ""
    if validation_results['violations']:
        violations_html += "<h3>Violations</h3>\n<ul>\n"
        for violation in validation_results['violations']:
            violations_html += f"<li>{violation}</li>\n"
        violations_html += "</ul>\n"
    else:
        violations_html = "<p style='color: green; font-weight: bold;'>[OK] No violations detected - Equipment count conserved</p>\n"
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property 6: Fuel Switching Conservation Report</title>
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
        .header {{
            border-bottom: 3px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .title {{
            font-size: 28px;
            font-weight: bold;
            color: #333;
            margin: 0 0 10px 0;
        }}
        .status {{
            display: inline-block;
            padding: 10px 20px;
            border-radius: 4px;
            background-color: {status_color};
            color: white;
            font-weight: bold;
            font-size: 16px;
            margin-top: 10px;
        }}
        .timestamp {{
            color: #666;
            font-size: 12px;
            margin-top: 10px;
        }}
        .section {{
            margin: 30px 0;
            padding: 20px;
            background-color: #f9f9f9;
            border-left: 4px solid #007bff;
            border-radius: 4px;
        }}
        .section h2 {{
            margin-top: 0;
            color: #007bff;
        }}
        .section h3 {{
            color: #333;
            margin-top: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            background-color: white;
        }}
        table th {{
            background-color: #007bff;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        table tr:hover {{
            background-color: #f5f5f5;
        }}
        .visualization {{
            margin: 20px 0;
            text-align: center;
        }}
        .visualization img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .property-description {{
            background-color: #e7f3ff;
            padding: 15px;
            border-radius: 4px;
            margin: 15px 0;
            border-left: 4px solid #2196F3;
        }}
        .summary-box {{
            background-color: #f0f8ff;
            padding: 15px;
            border-radius: 4px;
            margin: 15px 0;
            border-left: 4px solid #4ECDC4;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">Property 6: Fuel Switching Conservation</div>
            <div class="status">{overall_status}</div>
            <div class="timestamp">Generated: {report_results['timestamp']}</div>
        </div>
        
        <div class="section">
            <h2>Test Summary</h2>
            <div class="property-description">
                <strong>Property 6:</strong> Total equipment count before and after apply_replacements is equal
            </div>
            <p><strong>Validates: Requirements 3.3, 3.4</strong></p>
            
            <div class="summary-box">
                <h3>Conservation Check</h3>
                <p><strong>Equipment Count Before:</strong> {stats['total_count_before']}</p>
                <p><strong>Equipment Count After:</strong> {stats['total_count_after']}</p>
                <p><strong>Difference:</strong> {stats['difference']}</p>
                <p><strong>Status:</strong> {'✓ CONSERVED' if stats['difference'] == 0 else '✗ NOT CONSERVED'}</p>
            </div>
            
            {violations_html}
        </div>
        
        <div class="section">
            <h2>Detailed Results</h2>
            
            <h3>Equipment Count by End-Use</h3>
            <table border='1' cellpadding='8'>
                <tr><th>End-Use</th><th>Before</th><th>After</th><th>Difference</th></tr>
"""
    
    for end_use in sorted(set(list(stats['by_end_use_before'].keys()) + list(stats['by_end_use_after'].keys()))):
        before = stats['by_end_use_before'].get(end_use, 0)
        after = stats['by_end_use_after'].get(end_use, 0)
        diff = after - before
        html_content += f"<tr><td>{end_use}</td><td>{before}</td><td>{after}</td><td>{diff}</td></tr>\n"
    
    html_content += """</table>
            
"""
    
    html_content += fuel_switching_html
    
    html_content += """
        </div>
        
        <div class="section">
            <h2>Visualizations</h2>
            
            <h3>1. Fuel Type Distribution: Before vs After Replacements</h3>
            <p>Pie charts showing the proportion of natural gas vs electric equipment before and after replacements. 
            The total count should remain the same, but the fuel type mix may shift due to electrification.</p>
            <div class="visualization">
                <img src="data:image/png;base64,""" + images_b64.get('fuel_type_split', '') + """" alt="Fuel Type Split">
            </div>
            
            <h3>2. Fuel Switching Volume by End-Use Category</h3>
            <p>Bar chart showing how many units were switched from natural gas to electric for each end-use category. 
            This demonstrates the electrification impact of the replacement scenario.</p>
            <div class="visualization">
                <img src="data:image/png;base64,""" + images_b64.get('fuel_switching_volume', '') + """" alt="Fuel Switching Volume">
            </div>
            
            <h3>3. Equipment Count by End-Use: Before vs After</h3>
            <p>Grouped bar chart comparing equipment counts by end-use category before and after replacements. 
            Each end-use should have the same count before and after (conservation property).</p>
            <div class="visualization">
                <img src="data:image/png;base64,""" + images_b64.get('equipment_count_comparison', '') + """" alt="Equipment Count Comparison">
            </div>
        </div>
        
        <div class="section">
            <h2>Interpretation</h2>
            <ul>
                <li><strong>Equipment Conservation:</strong> The total number of equipment units must remain constant during replacements. 
                Replacements change equipment characteristics (efficiency, fuel type, age) but do not create or destroy units.</li>
                <li><strong>Fuel Switching:</strong> When equipment is replaced, some units may be switched from natural gas to electric 
                based on the electrification_rate in the scenario configuration.</li>
                <li><strong>End-Use Preservation:</strong> Equipment replacements do not change the end-use category. 
                A space heating unit remains a space heating unit after replacement.</li>
                <li><strong>Scenario Impact:</strong> The fuel switching volume shows the impact of the electrification scenario 
                on the equipment mix across different end-uses.</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return str(output_path)


def generate_markdown_report(
    report_results: dict,
    equipment_before: pd.DataFrame,
    equipment_after: pd.DataFrame,
    viz_files: dict,
    output_path: Path
) -> str:
    """Generate Markdown report with visualization references."""
    
    validation_results = report_results['property_6']
    overall_status = "✓ PASSED" if report_results['overall_passed'] else "✗ FAILED"
    stats = validation_results['statistics']
    
    md_content = f"""# Property 6: Fuel Switching Conservation Report

**Status:** {overall_status}

**Generated:** {report_results['timestamp']}

**Validates:** Requirements 3.3, 3.4

## Test Summary

### Property 6: Equipment Count Conservation
- **Definition:** Total equipment count before and after apply_replacements is equal
- **Status:** {overall_status}
- **Violations:** {len(validation_results['violations'])}

### Conservation Check
- **Equipment Count Before:** {stats['total_count_before']}
- **Equipment Count After:** {stats['total_count_after']}
- **Difference:** {stats['difference']}
- **Result:** {'✓ CONSERVED' if stats['difference'] == 0 else '✗ NOT CONSERVED'}

## Equipment Count by End-Use

| End-Use | Before | After | Difference |
|---------|--------|-------|------------|
"""
    
    for end_use in sorted(set(list(stats['by_end_use_before'].keys()) + list(stats['by_end_use_after'].keys()))):
        before = stats['by_end_use_before'].get(end_use, 0)
        after = stats['by_end_use_after'].get(end_use, 0)
        diff = after - before
        md_content += f"| {end_use} | {before} | {after} | {diff} |\n"
    
    md_content += "\n## Fuel Switching Volume by End-Use\n\n"
    md_content += "| End-Use | Gas Before | Gas After | Switched to Electric | Total Equipment |\n"
    md_content += "|---------|-----------|-----------|----------------------|-----------------|\n"
    
    for end_use, data in stats['fuel_switching_volume'].items():
        md_content += f"| {end_use} | {data['gas_before']} | {data['gas_after']} | {data['switched_to_electric']} | {data['total_equipment']} |\n"
    
    if validation_results['violations']:
        md_content += "\n## Violations\n\n"
        for violation in validation_results['violations']:
            md_content += f"- {violation}\n"
    else:
        md_content += "\n## Violations\n\n✓ No violations detected - Equipment count conserved\n"
    
    md_content += """
## Visualizations

### 1. Fuel Type Distribution: Before vs After Replacements
Pie charts showing the proportion of natural gas vs electric equipment before and after replacements. 
The total count should remain the same, but the fuel type mix may shift due to electrification.

![Fuel Type Split](fuel_type_split.png)

### 2. Fuel Switching Volume by End-Use Category
Bar chart showing how many units were switched from natural gas to electric for each end-use category. 
This demonstrates the electrification impact of the replacement scenario.

![Fuel Switching Volume](fuel_switching_volume.png)

### 3. Equipment Count by End-Use: Before vs After
Grouped bar chart comparing equipment counts by end-use category before and after replacements. 
Each end-use should have the same count before and after (conservation property).

![Equipment Count Comparison](equipment_count_comparison.png)

## Interpretation

- **Equipment Conservation:** The total number of equipment units must remain constant during replacements. 
  Replacements change equipment characteristics (efficiency, fuel type, age) but do not create or destroy units.

- **Fuel Switching:** When equipment is replaced, some units may be switched from natural gas to electric 
  based on the electrification_rate in the scenario configuration.

- **End-Use Preservation:** Equipment replacements do not change the end-use category. 
  A space heating unit remains a space heating unit after replacement.

- **Scenario Impact:** The fuel switching volume shows the impact of the electrification scenario 
  on the equipment mix across different end-uses.

## Mathematical Background

The conservation property ensures that:

```
count_before = count_after
```

For each end-use category:

```
count_before[end_use] = count_after[end_use]
```

This is a fundamental requirement for the replacement model to maintain data integrity.
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return str(output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = generate_property6_report()
    print(f"Report generated successfully")
    print(f"HTML: {result['html_path']}")
    print(f"Markdown: {result['md_path']}")
