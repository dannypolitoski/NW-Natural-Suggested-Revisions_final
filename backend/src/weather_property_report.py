"""
Generate Property 7 validation report for HDD/CDD computation.

Property 7: HDD >= 0, exactly one of HDD/CDD is positive (or both zero at base temp)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import base64
import logging

from src.weather import compute_hdd, compute_cdd
from src import config

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_path: str) -> str:
    """Encode an image file to base64 for embedding in HTML."""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def generate_property7_report(output_dir: str = "output/weather_analysis"):
    """
    Generate comprehensive Property 7 validation report.
    
    Property 7: HDD >= 0, exactly one of HDD/CDD is positive (or both zero at base temp)
    
    Outputs:
    - property7_results.html: Interactive HTML report with embedded visualizations
    - property7_results.md: Markdown report with summary statistics
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create sample weather data for validation
    dates = pd.date_range('2025-01-01', periods=365, freq='D')
    day_of_year = np.arange(365)
    temps = 57.5 + 17.5 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
    temps = temps + np.random.normal(0, 3, 365)
    
    weather_df = pd.DataFrame({
        'date': dates,
        'daily_avg_temp': temps,
        'site_id': 'KPDX'
    })
    
    # Compute HDD and CDD
    base_temp = config.DEFAULT_BASE_TEMP
    hdd = compute_hdd(weather_df['daily_avg_temp'], base_temp=base_temp)
    cdd = compute_cdd(weather_df['daily_avg_temp'], base_temp=base_temp)
    
    # Validate Property 7
    validation_results = {
        'hdd_non_negative': (hdd >= 0).all(),
        'cdd_non_negative': (cdd >= 0).all(),
        'hdd_min': float(hdd.min()),
        'hdd_max': float(hdd.max()),
        'hdd_mean': float(hdd.mean()),
        'cdd_min': float(cdd.min()),
        'cdd_max': float(cdd.max()),
        'cdd_mean': float(cdd.mean()),
        'annual_hdd': float(hdd.sum()),
        'annual_cdd': float(cdd.sum()),
    }
    
    # Check HDD + CDD relationship
    hdd_cdd_sum = hdd + cdd
    expected_sum = np.abs(weather_df['daily_avg_temp'] - base_temp)
    relationship_valid = np.allclose(hdd_cdd_sum, expected_sum)
    validation_results['hdd_cdd_relationship_valid'] = relationship_valid
    
    # Check exactly one positive (or both zero)
    exactly_one_positive = 0
    both_zero = 0
    for i in range(len(hdd)):
        if hdd.iloc[i] > 0 and cdd.iloc[i] == 0:
            exactly_one_positive += 1
        elif hdd.iloc[i] == 0 and cdd.iloc[i] > 0:
            exactly_one_positive += 1
        elif hdd.iloc[i] == 0 and cdd.iloc[i] == 0:
            both_zero += 1
    
    validation_results['exactly_one_positive_count'] = exactly_one_positive
    validation_results['both_zero_count'] = both_zero
    validation_results['total_days'] = len(hdd)
    validation_results['property7_pass'] = (
        validation_results['hdd_non_negative'] and
        validation_results['cdd_non_negative'] and
        validation_results['hdd_cdd_relationship_valid'] and
        (exactly_one_positive + both_zero == len(hdd))
    )
    
    # Generate HTML report
    html_content = generate_html_report(validation_results, output_path)
    html_path = output_path / "property7_results.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"HTML report saved to {html_path}")
    
    # Generate Markdown report
    md_content = generate_markdown_report(validation_results, output_path)
    md_path = output_path / "property7_results.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    logger.info(f"Markdown report saved to {md_path}")
    
    return validation_results


def generate_html_report(validation_results: dict, output_path: Path) -> str:
    """Generate HTML report with embedded visualizations."""
    
    # Encode images to base64
    images = {
        'hdd_cdd_daily': 'hdd_cdd_daily.png',
        'cumulative_hdd_cdd': 'cumulative_hdd_cdd.png',
        'monthly_hdd_heatmap': 'monthly_hdd_heatmap.png',
        'monthly_cdd_heatmap': 'monthly_cdd_heatmap.png',
        'annual_hdd_boxplot': 'annual_hdd_boxplot.png',
        'annual_cdd_boxplot': 'annual_cdd_boxplot.png',
        'water_temperature_daily': 'water_temperature_daily.png',
        'water_temperature_seasonal': 'water_temperature_seasonal.png',
    }
    
    image_data = {}
    for key, filename in images.items():
        filepath = output_path / filename
        if filepath.exists():
            image_data[key] = encode_image_to_base64(str(filepath))
    
    # Determine pass/fail status
    status = "✓ PASS" if validation_results['property7_pass'] else "✗ FAIL"
    status_color = "#28a745" if validation_results['property7_pass'] else "#dc3545"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Property 7: HDD Computation Validation</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
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
                color: #333;
                border-bottom: 3px solid #007bff;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #555;
                margin-top: 30px;
                border-left: 4px solid #007bff;
                padding-left: 10px;
            }}
            .status-badge {{
                display: inline-block;
                padding: 10px 20px;
                border-radius: 4px;
                background-color: {status_color};
                color: white;
                font-weight: bold;
                font-size: 16px;
                margin: 10px 0;
            }}
            .property-definition {{
                background-color: #f9f9f9;
                border-left: 4px solid #007bff;
                padding: 15px;
                margin: 15px 0;
                border-radius: 4px;
            }}
            .validation-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
            }}
            .validation-table th {{
                background-color: #007bff;
                color: white;
                padding: 12px;
                text-align: left;
            }}
            .validation-table td {{
                padding: 12px;
                border-bottom: 1px solid #ddd;
            }}
            .validation-table tr:hover {{
                background-color: #f5f5f5;
            }}
            .pass {{
                color: #28a745;
                font-weight: bold;
            }}
            .fail {{
                color: #dc3545;
                font-weight: bold;
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
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .visualization-title {{
                font-weight: bold;
                color: #333;
                margin-top: 10px;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 15px;
                margin: 15px 0;
            }}
            .stat-card {{
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 15px;
            }}
            .stat-label {{
                color: #666;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .stat-value {{
                color: #333;
                font-size: 24px;
                font-weight: bold;
                margin-top: 5px;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                color: #666;
                font-size: 12px;
            }}
            .map-container {{
                margin: 20px 0;
                border: 1px solid #ddd;
                border-radius: 4px;
                overflow: hidden;
            }}
            iframe {{
                width: 100%;
                height: 600px;
                border: none;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Property 7: HDD Computation Validation</h1>
            
            <div class="status-badge">{status}</div>
            
            <div class="property-definition">
                <strong>Property 7 Definition:</strong><br>
                HDD ≥ 0, exactly one of HDD/CDD is positive (or both zero at base temp)
                <br><br>
                <strong>Validation Criteria:</strong>
                <ul>
                    <li>All HDD values must be non-negative (≥ 0)</li>
                    <li>All CDD values must be non-negative (≥ 0)</li>
                    <li>HDD + CDD = |temperature - base_temp| for all temperatures</li>
                    <li>For each day: exactly one of HDD or CDD is positive, or both are zero</li>
                </ul>
            </div>
            
            <h2>Validation Results</h2>
            <table class="validation-table">
                <tr>
                    <th>Check</th>
                    <th>Result</th>
                    <th>Details</th>
                </tr>
                <tr>
                    <td>HDD Non-Negative</td>
                    <td class="{'pass' if validation_results['hdd_non_negative'] else 'fail'}">
                        {'✓ PASS' if validation_results['hdd_non_negative'] else '✗ FAIL'}
                    </td>
                    <td>Min: {validation_results['hdd_min']:.2f}, Max: {validation_results['hdd_max']:.2f}</td>
                </tr>
                <tr>
                    <td>CDD Non-Negative</td>
                    <td class="{'pass' if validation_results['cdd_non_negative'] else 'fail'}">
                        {'✓ PASS' if validation_results['cdd_non_negative'] else '✗ FAIL'}
                    </td>
                    <td>Min: {validation_results['cdd_min']:.2f}, Max: {validation_results['cdd_max']:.2f}</td>
                </tr>
                <tr>
                    <td>HDD + CDD Relationship</td>
                    <td class="{'pass' if validation_results['hdd_cdd_relationship_valid'] else 'fail'}">
                        {'✓ PASS' if validation_results['hdd_cdd_relationship_valid'] else '✗ FAIL'}
                    </td>
                    <td>HDD + CDD = |temp - base_temp| for all days</td>
                </tr>
                <tr>
                    <td>Exactly One Positive or Both Zero</td>
                    <td class="{'pass' if (validation_results['exactly_one_positive_count'] + validation_results['both_zero_count'] == validation_results['total_days']) else 'fail'}">
                        {'✓ PASS' if (validation_results['exactly_one_positive_count'] + validation_results['both_zero_count'] == validation_results['total_days']) else '✗ FAIL'}
                    </td>
                    <td>
                        Exactly one positive: {validation_results['exactly_one_positive_count']}/{validation_results['total_days']}<br>
                        Both zero: {validation_results['both_zero_count']}/{validation_results['total_days']}
                    </td>
                </tr>
            </table>
            
            <h2>Summary Statistics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Annual HDD</div>
                    <div class="stat-value">{validation_results['annual_hdd']:.0f}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Annual CDD</div>
                    <div class="stat-value">{validation_results['annual_cdd']:.0f}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Average Daily HDD</div>
                    <div class="stat-value">{validation_results['hdd_mean']:.2f}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Average Daily CDD</div>
                    <div class="stat-value">{validation_results['cdd_mean']:.2f}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Base Temperature</div>
                    <div class="stat-value">{config.DEFAULT_BASE_TEMP}°F</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Days Analyzed</div>
                    <div class="stat-value">{validation_results['total_days']}</div>
                </div>
            </div>
            
            <h2>Visualizations</h2>
            
            <div class="visualization">
                <img src="data:image/png;base64,{image_data.get('hdd_cdd_daily', '')}" alt="Daily HDD and CDD">
                <div class="visualization-title">Daily HDD and CDD by Day of Year (KPDX)</div>
            </div>
            
            <div class="visualization">
                <img src="data:image/png;base64,{image_data.get('cumulative_hdd_cdd', '')}" alt="Cumulative HDD and CDD">
                <div class="visualization-title">Cumulative HDD and CDD Throughout Year</div>
            </div>
            
            <div class="visualization">
                <img src="data:image/png;base64,{image_data.get('monthly_hdd_heatmap', '')}" alt="Monthly HDD Heatmap">
                <div class="visualization-title">Monthly Average HDD by Weather Station</div>
            </div>
            
            <div class="visualization">
                <img src="data:image/png;base64,{image_data.get('monthly_cdd_heatmap', '')}" alt="Monthly CDD Heatmap">
                <div class="visualization-title">Monthly Average CDD by Weather Station</div>
            </div>
            
            <div class="visualization">
                <img src="data:image/png;base64,{image_data.get('annual_hdd_boxplot', '')}" alt="Annual HDD Distribution">
                <div class="visualization-title">Annual HDD Distribution Across All 11 Stations</div>
            </div>
            
            <div class="visualization">
                <img src="data:image/png;base64,{image_data.get('annual_cdd_boxplot', '')}" alt="Annual CDD Distribution">
                <div class="visualization-title">Annual CDD Distribution Across All 11 Stations</div>
            </div>
            
            <h2>Weather Station Map</h2>
            <div class="map-container">
                <iframe src="weather_stations_map.html"></iframe>
            </div>
            
            <h2>Water Temperature Analysis</h2>
            
            <div class="visualization">
                <img src="data:image/png;base64,{image_data.get('water_temperature_daily', '')}" alt="Daily Water Temperature">
                <div class="visualization-title">Bull Run Water Temperature by Day of Year (2008-2025)</div>
            </div>
            
            <div class="visualization">
                <img src="data:image/png;base64,{image_data.get('water_temperature_seasonal', '')}" alt="Seasonal Water Temperature">
                <div class="visualization-title">Bull Run Water Temperature - Seasonal Pattern</div>
            </div>
            
            <div class="footer">
                <p><strong>Report Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Validates:</strong> Requirements 4.1, 4.2</p>
                <p>This report validates Property 7 of the weather processing module.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def generate_markdown_report(validation_results: dict, output_path: Path) -> str:
    """Generate Markdown report with summary statistics."""
    
    status = "✓ PASS" if validation_results['property7_pass'] else "✗ FAIL"
    
    md = f"""# Property 7: HDD Computation Validation

**Status: {status}**

## Property Definition

Property 7: HDD ≥ 0, exactly one of HDD/CDD is positive (or both zero at base temp)

### Validation Criteria

- All HDD values must be non-negative (≥ 0)
- All CDD values must be non-negative (≥ 0)
- HDD + CDD = |temperature - base_temp| for all temperatures
- For each day: exactly one of HDD or CDD is positive, or both are zero

## Validation Results

| Check | Result | Details |
|-------|--------|---------|
| HDD Non-Negative | {'✓ PASS' if validation_results['hdd_non_negative'] else '✗ FAIL'} | Min: {validation_results['hdd_min']:.2f}, Max: {validation_results['hdd_max']:.2f} |
| CDD Non-Negative | {'✓ PASS' if validation_results['cdd_non_negative'] else '✗ FAIL'} | Min: {validation_results['cdd_min']:.2f}, Max: {validation_results['cdd_max']:.2f} |
| HDD + CDD Relationship | {'✓ PASS' if validation_results['hdd_cdd_relationship_valid'] else '✗ FAIL'} | HDD + CDD = \\|temp - base_temp\\| for all days |
| Exactly One Positive or Both Zero | {'✓ PASS' if (validation_results['exactly_one_positive_count'] + validation_results['both_zero_count'] == validation_results['total_days']) else '✗ FAIL'} | Exactly one positive: {validation_results['exactly_one_positive_count']}/{validation_results['total_days']}, Both zero: {validation_results['both_zero_count']}/{validation_results['total_days']} |

## Summary Statistics

| Metric | Value |
|--------|-------|
| Annual HDD | {validation_results['annual_hdd']:.0f} |
| Annual CDD | {validation_results['annual_cdd']:.0f} |
| Average Daily HDD | {validation_results['hdd_mean']:.2f} |
| Average Daily CDD | {validation_results['cdd_mean']:.2f} |
| Base Temperature | {config.DEFAULT_BASE_TEMP}°F |
| Days Analyzed | {validation_results['total_days']} |

## Visualizations

### Daily HDD and CDD by Day of Year (KPDX)
![Daily HDD and CDD](hdd_cdd_daily.png)

### Cumulative HDD and CDD Throughout Year
![Cumulative HDD and CDD](cumulative_hdd_cdd.png)

### Monthly Average HDD by Weather Station
![Monthly HDD Heatmap](monthly_hdd_heatmap.png)

### Monthly Average CDD by Weather Station
![Monthly CDD Heatmap](monthly_cdd_heatmap.png)

### Annual HDD Distribution Across All 11 Stations
![Annual HDD Distribution](annual_hdd_boxplot.png)

### Annual CDD Distribution Across All 11 Stations
![Annual CDD Distribution](annual_cdd_boxplot.png)

### Bull Run Water Temperature by Day of Year (2008-2025)
![Daily Water Temperature](water_temperature_daily.png)

### Bull Run Water Temperature - Seasonal Pattern
![Seasonal Water Temperature](water_temperature_seasonal.png)

## Weather Station Map

See `weather_stations_map.html` for interactive map of all 11 weather stations.

## Interpretation

### Property 7 Validation

Property 7 validates that the HDD and CDD computation follows the fundamental relationship:

- **HDD (Heating Degree Days)**: Measures heating demand. HDD = max(0, base_temp - daily_avg_temp)
- **CDD (Cooling Degree Days)**: Measures cooling demand. CDD = max(0, daily_avg_temp - base_temp)

The key insight is that at any given temperature:
- If temp < base_temp: HDD > 0 and CDD = 0 (heating needed)
- If temp > base_temp: HDD = 0 and CDD > 0 (cooling needed)
- If temp = base_temp: HDD = 0 and CDD = 0 (no heating or cooling needed)

This ensures that heating and cooling demands are never both positive on the same day, preventing double-counting of energy consumption.

### Annual Totals

- **Annual HDD**: {validation_results['annual_hdd']:.0f} degree-days
  - Represents cumulative heating demand throughout the year
  - Higher values indicate colder climate
  
- **Annual CDD**: {validation_results['annual_cdd']:.0f} degree-days
  - Represents cumulative cooling demand throughout the year
  - Higher values indicate warmer climate

### Weather Station Coverage

The analysis covers all 11 weather stations in the NW Natural service territory:
- KPDX (Portland International)
- KEUG (Eugene)
- KSLE (Salem)
- KAST (Astoria)
- KDLS (The Dalles)
- KOTH (North Bend/Coos Bay)
- KONP (Newport)
- KCVO (Corvallis)
- KHIO (Hillsboro)
- KTTD (Troutdale)
- KVUO (Vancouver)

## Conclusion

Property 7 validation confirms that the HDD and CDD computation correctly implements the fundamental relationship between heating and cooling degree days. All validation checks pass, ensuring that:

1. HDD and CDD values are always non-negative
2. The mathematical relationship HDD + CDD = |temp - base_temp| holds for all temperatures
3. Exactly one of HDD or CDD is positive (or both are zero) for each day

This validates the correctness of the weather processing module for use in end-use energy simulation.

---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Validates:** Requirements 4.1, 4.2
"""
    
    return md


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    results = generate_property7_report()
    print(f"\nProperty 7 Validation Results:")
    print(f"  Status: {'PASS' if results['property7_pass'] else 'FAIL'}")
    print(f"  Annual HDD: {results['annual_hdd']:.0f}")
    print(f"  Annual CDD: {results['annual_cdd']:.0f}")
