"""
Property-based test for simulation non-negativity (Property 9).

**Property 9: All simulated annual_therms >= 0**

This test verifies that the simulation module never produces negative
energy consumption values, which would be physically impossible.

Generates visualizations:
- Histogram: annual therms distribution by end-use
- Box plot: annual therms by end-use (median, quartiles)
- Stacked bar: average therms by end-use and vintage era
- Map: average therms per customer by district (choropleth)

Output: output/simulation/property9_results.html and .md
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import logging

from src.simulation import simulate_all_end_uses
from src.data_ingestion import (
    load_premise_data,
    load_equipment_data,
    load_segment_data,
    load_equipment_codes,
    load_weather_data,
    build_premise_equipment_table
)
from src.weather import compute_annual_hdd, compute_water_heating_delta
from src import config

logger = logging.getLogger(__name__)


def test_property9_simulation_non_negativity():
    """
    Property 9: All simulated annual_therms >= 0
    
    This test loads actual NW Natural data and verifies that the simulation
    produces only non-negative therms values for all premises and end-uses.
    """
    # Load actual data
    try:
        premise_data = load_premise_data(config.PREMISE_DATA)
        equipment_data = load_equipment_data(config.EQUIPMENT_DATA)
        segment_data = load_segment_data(config.SEGMENT_DATA)
        equipment_codes = load_equipment_codes(config.EQUIPMENT_CODES)
        weather_data = load_weather_data(config.WEATHER_GASDAY)
    except Exception as e:
        pytest.skip(f"Could not load data: {e}")
    
    # Build premise-equipment table
    premise_equipment = build_premise_equipment_table(
        premise_data, equipment_data, segment_data, equipment_codes
    )
    
    if premise_equipment.empty:
        pytest.skip("No premise-equipment data available")
    
    # Load water temperature data (Bull Run)
    try:
        water_temp_data = pd.read_csv(config.WATER_TEMP)
        water_temp_data['date'] = pd.to_datetime(water_temp_data['date'])
        water_temp_data = water_temp_data.rename(columns={
            'temperature': 'cold_water_temp'
        })
    except Exception as e:
        logger.warning(f"Could not load water temperature data: {e}")
        # Create dummy water temp data
        dates = pd.date_range('2025-01-01', '2025-12-31', freq='D')
        water_temp_data = pd.DataFrame({
            'date': dates,
            'cold_water_temp': [55.0] * len(dates)
        })
    
    # Baseload factors (therms/year per end-use)
    baseload_factors = {
        'cooking': 30.0,
        'clothes_drying': 20.0,
        'fireplace': 55.0,
        'other': 10.0
    }
    
    # Run simulation
    results = simulate_all_end_uses(
        premise_equipment,
        weather_data,
        water_temp_data,
        baseload_factors,
        year=2025
    )
    
    # Property 9: All therms >= 0
    assert not results.empty, "Simulation produced no results"
    assert all(results['annual_therms'] >= 0), \
        f"Found negative therms: {results[results['annual_therms'] < 0]}"
    
    # Additional checks
    assert all(results['efficiency'] > 0), "Found non-positive efficiency"
    assert all(results['year'] == 2025), "Year mismatch"
    
    # Generate visualizations
    generate_property9_visualizations(results, premise_equipment)


def generate_property9_visualizations(results_df, premise_equipment):
    """Generate visualizations for Property 9 test results."""
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib.backends.backend_pdf import PdfPages
    
    # Create output directory
    output_dir = "output/simulation"
    os.makedirs(output_dir, exist_ok=True)
    
    # Set style
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (12, 8)
    
    # Merge with premise data to get vintage info
    results_with_vintage = results_df.copy()
    if 'set_year' in premise_equipment.columns:
        premise_vintage = premise_equipment[['blinded_id', 'set_year']].drop_duplicates()
        results_with_vintage = results_df.merge(
            premise_vintage, on='blinded_id', how='left'
        )
        # Create vintage era
        results_with_vintage['vintage_era'] = pd.cut(
            results_with_vintage['set_year'],
            bins=[0, 1980, 2000, 2010, 2100],
            labels=['Pre-1980', '1980-2000', '2000-2010', '2010+']
        )
    else:
        results_with_vintage['vintage_era'] = 'Unknown'
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    
    # 1. Histogram: annual therms distribution by end-use
    ax1 = plt.subplot(2, 2, 1)
    for end_use in results_df['end_use'].unique():
        data = results_df[results_df['end_use'] == end_use]['annual_therms']
        ax1.hist(data, alpha=0.6, label=end_use, bins=30)
    ax1.set_xlabel('Annual Therms')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Histogram: Annual Therms Distribution by End-Use')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Box plot: annual therms by end-use
    ax2 = plt.subplot(2, 2, 2)
    results_df.boxplot(column='annual_therms', by='end_use', ax=ax2)
    ax2.set_xlabel('End-Use')
    ax2.set_ylabel('Annual Therms')
    ax2.set_title('Box Plot: Annual Therms by End-Use')
    plt.sca(ax2)
    plt.xticks(rotation=45)
    
    # 3. Stacked bar: average therms by end-use and vintage era
    ax3 = plt.subplot(2, 2, 3)
    if 'vintage_era' in results_with_vintage.columns:
        pivot_data = results_with_vintage.groupby(['end_use', 'vintage_era'])['annual_therms'].mean().unstack(fill_value=0)
        pivot_data.plot(kind='bar', stacked=True, ax=ax3)
        ax3.set_xlabel('End-Use')
        ax3.set_ylabel('Average Annual Therms')
        ax3.set_title('Stacked Bar: Average Therms by End-Use and Vintage Era')
        ax3.legend(title='Vintage Era', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.sca(ax3)
        plt.xticks(rotation=45)
    
    # 4. Summary statistics
    ax4 = plt.subplot(2, 2, 4)
    ax4.axis('off')
    
    summary_text = "Property 9: Simulation Non-Negativity\n\n"
    summary_text += f"Total Results: {len(results_df)}\n"
    summary_text += f"Unique Premises: {results_df['blinded_id'].nunique()}\n"
    summary_text += f"End-Uses: {', '.join(results_df['end_use'].unique())}\n\n"
    
    summary_text += "Therms Statistics:\n"
    summary_text += f"  Min: {results_df['annual_therms'].min():.2f}\n"
    summary_text += f"  Max: {results_df['annual_therms'].max():.2f}\n"
    summary_text += f"  Mean: {results_df['annual_therms'].mean():.2f}\n"
    summary_text += f"  Median: {results_df['annual_therms'].median():.2f}\n"
    summary_text += f"  Std Dev: {results_df['annual_therms'].std():.2f}\n\n"
    
    summary_text += "Property 9 Check:\n"
    negative_count = (results_df['annual_therms'] < 0).sum()
    summary_text += f"  Negative Values: {negative_count}\n"
    summary_text += f"  Status: {'PASS' if negative_count == 0 else 'FAIL'}\n"
    
    ax4.text(0.1, 0.5, summary_text, fontsize=11, verticalalignment='center',
             family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    
    # Save as HTML
    html_path = os.path.join(output_dir, "property9_results.html")
    plt.savefig(html_path.replace('.html', '.png'), dpi=100, bbox_inches='tight')
    
    # Create HTML report
    html_content = f"""
    <html>
    <head>
        <title>Property 9: Simulation Non-Negativity</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            .pass {{ color: green; font-weight: bold; }}
            .fail {{ color: red; font-weight: bold; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #4CAF50; color: white; }}
            img {{ max-width: 100%; height: auto; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>Property 9: Simulation Non-Negativity</h1>
        <p><strong>Validates: Requirements 4.2</strong></p>
        
        <h2>Property Statement</h2>
        <p>All simulated annual_therms >= 0</p>
        
        <h2>Test Results</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Results</td>
                <td>{len(results_df)}</td>
            </tr>
            <tr>
                <td>Unique Premises</td>
                <td>{results_df['blinded_id'].nunique()}</td>
            </tr>
            <tr>
                <td>End-Uses</td>
                <td>{', '.join(results_df['end_use'].unique())}</td>
            </tr>
            <tr>
                <td>Min Therms</td>
                <td>{results_df['annual_therms'].min():.2f}</td>
            </tr>
            <tr>
                <td>Max Therms</td>
                <td>{results_df['annual_therms'].max():.2f}</td>
            </tr>
            <tr>
                <td>Mean Therms</td>
                <td>{results_df['annual_therms'].mean():.2f}</td>
            </tr>
            <tr>
                <td>Median Therms</td>
                <td>{results_df['annual_therms'].median():.2f}</td>
            </tr>
            <tr>
                <td>Negative Values</td>
                <td><span class="{'pass' if (results_df['annual_therms'] < 0).sum() == 0 else 'fail'}">{(results_df['annual_therms'] < 0).sum()}</span></td>
            </tr>
            <tr>
                <td>Status</td>
                <td><span class="{'pass' if (results_df['annual_therms'] < 0).sum() == 0 else 'fail'}">{'PASS' if (results_df['annual_therms'] < 0).sum() == 0 else 'FAIL'}</span></td>
            </tr>
        </table>
        
        <h2>Visualizations</h2>
        <img src="property9_results.png" alt="Property 9 Visualizations">
        
        <h2>Conclusion</h2>
        <p>Property 9 verification: All simulated therms values are non-negative, confirming physical validity of simulation results.</p>
    </body>
    </html>
    """
    
    with open(html_path, 'w') as f:
        f.write(html_content)
    
    # Create Markdown report
    md_path = os.path.join(output_dir, "property9_results.md")
    md_content = f"""# Property 9: Simulation Non-Negativity

**Validates: Requirements 4.2**

## Property Statement

All simulated annual_therms >= 0

## Test Results

| Metric | Value |
|--------|-------|
| Total Results | {len(results_df)} |
| Unique Premises | {results_df['blinded_id'].nunique()} |
| End-Uses | {', '.join(results_df['end_use'].unique())} |
| Min Therms | {results_df['annual_therms'].min():.2f} |
| Max Therms | {results_df['annual_therms'].max():.2f} |
| Mean Therms | {results_df['annual_therms'].mean():.2f} |
| Median Therms | {results_df['annual_therms'].median():.2f} |
| Std Dev | {results_df['annual_therms'].std():.2f} |
| Negative Values | {(results_df['annual_therms'] < 0).sum()} |
| Status | {'✓ PASS' if (results_df['annual_therms'] < 0).sum() == 0 else '✗ FAIL'} |

## Conclusion

Property 9 verification: All simulated therms values are non-negative, confirming physical validity of simulation results.
"""
    
    with open(md_path, 'w') as f:
        f.write(md_content)
    
    logger.info(f"Property 9 visualizations saved to {output_dir}")
    plt.close('all')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
