"""
Equipment replacement property test for Weibull survival monotonicity.

Validates:
- Property 5: S(t) <= S(t-1) for all t > 0, and S(0) = 1.0
- Property 5b: replacement_probability is always in [0, 1]

Generates comprehensive HTML and Markdown reports with visualizations:
- Line graph: Weibull survival curves by end-use category
- Line graph: replacement probability by equipment age per end-use
- Scatter: equipment age distribution with replacement probability overlay
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
from typing import Dict, Tuple, List

from src.equipment import weibull_survival, replacement_probability, median_to_eta
from src import config

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_path: str) -> str:
    """Encode image file to base64 string for embedding in HTML."""
    with open(image_path, 'rb') as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')


def validate_weibull_monotonicity() -> Dict:
    """
    Validate Property 5: S(t) <= S(t-1) for all t > 0, and S(0) = 1.0
    
    Tests across all end-use categories and reasonable parameter ranges.
    
    Returns:
        Dictionary with validation results
    """
    results = {
        'property_name': 'Property 5: Weibull Survival Monotonicity',
        'test_passed': True,
        'violations': [],
        'statistics': {}
    }
    
    # Test S(0) = 1.0 for all end-uses
    for end_use, beta in config.WEIBULL_BETA.items():
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        s_0 = weibull_survival(0, eta, beta)
        if abs(s_0 - 1.0) > 1e-10:
            results['test_passed'] = False
            results['violations'].append(
                f"S(0) != 1.0 for {end_use}: S(0) = {s_0}"
            )
    
    # Test monotonicity: S(t) <= S(t-1) for t in [1, 100]
    for end_use, beta in config.WEIBULL_BETA.items():
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        for t in range(1, 101):
            s_t = weibull_survival(t, eta, beta)
            s_t_minus_1 = weibull_survival(t - 1, eta, beta)
            
            if s_t > s_t_minus_1 + 1e-10:  # Allow small numerical error
                results['test_passed'] = False
                results['violations'].append(
                    f"Monotonicity violation for {end_use} at t={t}: "
                    f"S({t}) = {s_t} > S({t-1}) = {s_t_minus_1}"
                )
        
        # Store statistics
        results['statistics'][end_use] = {
            'eta': eta,
            'beta': beta,
            'useful_life': useful_life,
            's_0': weibull_survival(0, eta, beta),
            's_median': weibull_survival(useful_life, eta, beta),
            's_2x_median': weibull_survival(2 * useful_life, eta, beta),
        }
    
    return results


def validate_replacement_probability_bounds() -> Dict:
    """
    Validate Property 5b: replacement_probability is always in [0, 1]
    
    Tests across all end-use categories and reasonable age ranges.
    
    Returns:
        Dictionary with validation results
    """
    results = {
        'property_name': 'Property 5b: Replacement Probability Bounds',
        'test_passed': True,
        'violations': [],
        'statistics': {}
    }
    
    for end_use, beta in config.WEIBULL_BETA.items():
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        min_prob = 1.0
        max_prob = 0.0
        
        for age in np.linspace(0, 100, 1001):
            prob = replacement_probability(age, eta, beta)
            
            if prob < 0 or prob > 1:
                results['test_passed'] = False
                results['violations'].append(
                    f"Probability out of bounds for {end_use} at age={age}: "
                    f"P = {prob}"
                )
            
            min_prob = min(min_prob, prob)
            max_prob = max(max_prob, prob)
        
        results['statistics'][end_use] = {
            'min_probability': min_prob,
            'max_probability': max_prob,
            'prob_at_median': replacement_probability(useful_life, eta, beta),
            'prob_at_2x_median': replacement_probability(2 * useful_life, eta, beta),
        }
    
    return results


def generate_property5_report(output_dir: str = "output/equipment_replacement") -> Dict:
    """
    Generate comprehensive Property 5 validation report.
    
    Args:
        output_dir: Directory to save report files
    
    Returns:
        Dictionary with validation results and file paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("Generating Property 5 Weibull survival monotonicity report...")
    
    # Run validations
    monotonicity_results = validate_weibull_monotonicity()
    probability_results = validate_replacement_probability_bounds()
    
    # Combine results
    validation_results = {
        'property_5': monotonicity_results,
        'property_5b': probability_results,
        'overall_passed': monotonicity_results['test_passed'] and probability_results['test_passed'],
        'timestamp': datetime.now().isoformat(),
    }
    
    # Generate visualizations
    viz_files = _generate_visualizations(output_path)
    
    # Generate HTML report
    html_path = output_path / "property5_results.html"
    generate_html_report(validation_results, viz_files, html_path)
    
    # Generate Markdown report
    md_path = output_path / "property5_results.md"
    generate_markdown_report(validation_results, viz_files, md_path)
    
    logger.info(f"Property 5 report generated: {html_path}")
    logger.info(f"Property 5 report generated: {md_path}")
    
    return {
        'validation_results': validation_results,
        'html_path': str(html_path),
        'md_path': str(md_path),
        'viz_files': viz_files,
    }


def _generate_visualizations(output_path: Path) -> Dict[str, str]:
    """Generate all visualization files for Property 5."""
    viz_files = {}
    
    # 1. Weibull survival curves by end-use category
    fig, ax = plt.subplots(figsize=(14, 8))
    
    ages = np.linspace(0, 100, 1001)
    colors = plt.cm.tab10(np.linspace(0, 1, len(config.WEIBULL_BETA)))
    
    for (end_use, beta), color in zip(config.WEIBULL_BETA.items(), colors):
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        survivals = [weibull_survival(t, eta, beta) for t in ages]
        ax.plot(ages, survivals, label=f'{end_use} (β={beta})', 
                linewidth=2.5, color=color)
    
    ax.set_xlabel('Equipment Age (years)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Survival Probability S(t)', fontsize=12, fontweight='bold')
    ax.set_title('Weibull Survival Curves by End-Use Category', 
                fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1.05])
    plt.tight_layout()
    
    survival_path = output_path / "weibull_survival_curves.png"
    plt.savefig(survival_path, dpi=150, bbox_inches='tight')
    plt.close()
    viz_files['survival_curves'] = str(survival_path)
    
    # 2. Replacement probability by equipment age per end-use
    fig, ax = plt.subplots(figsize=(14, 8))
    
    for (end_use, beta), color in zip(config.WEIBULL_BETA.items(), colors):
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        probs = [replacement_probability(t, eta, beta) for t in ages]
        ax.plot(ages, probs, label=f'{end_use} (β={beta})', 
                linewidth=2.5, color=color)
    
    ax.set_xlabel('Equipment Age (years)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Replacement Probability', fontsize=12, fontweight='bold')
    ax.set_title('Replacement Probability by Equipment Age per End-Use', 
                fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1.05])
    plt.tight_layout()
    
    prob_path = output_path / "replacement_probability.png"
    plt.savefig(prob_path, dpi=150, bbox_inches='tight')
    plt.close()
    viz_files['replacement_probability'] = str(prob_path)
    
    # 3. Scatter: equipment age distribution with replacement probability overlay
    # Generate synthetic equipment age distribution
    np.random.seed(42)
    equipment_ages = []
    equipment_end_uses = []
    
    for end_use in config.WEIBULL_BETA.keys():
        # Simulate equipment ages with realistic distribution
        # Most equipment is relatively young, some is old
        ages = np.random.gamma(shape=2, scale=8, size=500)
        ages = np.clip(ages, 0, 100)
        equipment_ages.extend(ages)
        equipment_end_uses.extend([end_use] * len(ages))
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    for end_use, color in zip(config.WEIBULL_BETA.keys(), colors):
        mask = np.array(equipment_end_uses) == end_use
        ages_subset = np.array(equipment_ages)[mask]
        
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        beta = config.WEIBULL_BETA[end_use]
        eta = median_to_eta(useful_life, beta)
        
        probs = [replacement_probability(age, eta, beta) for age in ages_subset]
        
        ax.scatter(ages_subset, probs, alpha=0.4, s=20, color=color, 
                  label=f'{end_use} (n={len(ages_subset)})')
    
    ax.set_xlabel('Equipment Age (years)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Replacement Probability', fontsize=12, fontweight='bold')
    ax.set_title('Equipment Age Distribution with Replacement Probability Overlay', 
                fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='upper left', ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1.05])
    plt.tight_layout()
    
    scatter_path = output_path / "age_distribution_scatter.png"
    plt.savefig(scatter_path, dpi=150, bbox_inches='tight')
    plt.close()
    viz_files['age_distribution_scatter'] = str(scatter_path)
    
    return viz_files


def generate_html_report(validation_results: dict, viz_files: dict, output_path: Path) -> str:
    """Generate HTML report with embedded visualizations."""
    
    # Encode images to base64
    images_b64 = {}
    for key, filepath in viz_files.items():
        if Path(filepath).exists():
            images_b64[key] = encode_image_to_base64(filepath)
    
    overall_status = "[PASSED]" if validation_results['overall_passed'] else "[FAILED]"
    status_color = "#28a745" if validation_results['overall_passed'] else "#dc3545"
    
    # Build statistics table
    stats_html = "<h3>Weibull Parameters and Statistics</h3>\n<table border='1' cellpadding='8'>\n"
    stats_html += "<tr><th>End-Use</th><th>β (Shape)</th><th>η (Scale)</th><th>Useful Life</th><th>S(0)</th><th>S(median)</th><th>S(2×median)</th></tr>\n"
    
    for end_use, stats in validation_results['property_5']['statistics'].items():
        stats_html += f"""<tr>
            <td>{end_use}</td>
            <td>{stats['beta']:.2f}</td>
            <td>{stats['eta']:.2f}</td>
            <td>{stats['useful_life']}</td>
            <td>{stats['s_0']:.6f}</td>
            <td>{stats['s_median']:.6f}</td>
            <td>{stats['s_2x_median']:.6f}</td>
        </tr>\n"""
    
    stats_html += "</table>\n"
    
    # Build replacement probability bounds table
    prob_html = "<h3>Replacement Probability Bounds</h3>\n<table border='1' cellpadding='8'>\n"
    prob_html += "<tr><th>End-Use</th><th>Min P</th><th>Max P</th><th>P(median)</th><th>P(2×median)</th></tr>\n"
    
    for end_use, stats in validation_results['property_5b']['statistics'].items():
        prob_html += f"""<tr>
            <td>{end_use}</td>
            <td>{stats['min_probability']:.6f}</td>
            <td>{stats['max_probability']:.6f}</td>
            <td>{stats['prob_at_median']:.6f}</td>
            <td>{stats['prob_at_2x_median']:.6f}</td>
        </tr>\n"""
    
    prob_html += "</table>\n"
    
    # Build violations list
    violations_html = ""
    if validation_results['property_5']['violations']:
        violations_html += "<h3>Property 5 Violations</h3>\n<ul>\n"
        for violation in validation_results['property_5']['violations']:
            violations_html += f"<li>{violation}</li>\n"
        violations_html += "</ul>\n"
    
    if validation_results['property_5b']['violations']:
        violations_html += "<h3>Property 5b Violations</h3>\n<ul>\n"
        for violation in validation_results['property_5b']['violations']:
            violations_html += f"<li>{violation}</li>\n"
        violations_html += "</ul>\n"
    
    if not violations_html:
        violations_html = "<p style='color: green; font-weight: bold;'>[OK] No violations detected</p>\n"
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property 5: Weibull Survival Monotonicity Report</title>
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
        ul {{
            line-height: 1.8;
        }}
        .property-description {{
            background-color: #e7f3ff;
            padding: 15px;
            border-radius: 4px;
            margin: 15px 0;
            border-left: 4px solid #2196F3;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">Property 5: Weibull Survival Monotonicity</div>
            <div class="status">{overall_status}</div>
            <div class="timestamp">Generated: {validation_results['timestamp']}</div>
        </div>
        
        <div class="section">
            <h2>Test Summary</h2>
            <div class="property-description">
                <strong>Property 5:</strong> S(t) ≤ S(t-1) for all t > 0, and S(0) = 1.0<br>
                <strong>Property 5b:</strong> replacement_probability is always in [0, 1]
            </div>
            <p><strong>Validates: Requirements 3.3</strong></p>
            
            <h3>Property 5: Survival Monotonicity</h3>
            <p><strong>Status:</strong> {'[PASSED]' if validation_results['property_5']['test_passed'] else '[FAILED]'}</p>
            {f"<p><strong>Violations:</strong> {len(validation_results['property_5']['violations'])}</p>" if validation_results['property_5']['violations'] else "<p style='color: green;'>[OK] No violations detected</p>"}
            
            <h3>Property 5b: Probability Bounds</h3>
            <p><strong>Status:</strong> {'[PASSED]' if validation_results['property_5b']['test_passed'] else '[FAILED]'}</p>
            {f"<p><strong>Violations:</strong> {len(validation_results['property_5b']['violations'])}</p>" if validation_results['property_5b']['violations'] else "<p style='color: green;'>[OK] No violations detected</p>"}
        </div>
        
        <div class="section">
            <h2>Detailed Results</h2>
            {stats_html}
            {prob_html}
            {violations_html}
        </div>
        
        <div class="section">
            <h2>Visualizations</h2>
            
            <h3>1. Weibull Survival Curves by End-Use Category</h3>
            <p>Shows how survival probability decreases with equipment age for each end-use category. 
            All curves should be monotonically decreasing and start at S(0) = 1.0.</p>
            <div class="visualization">
                <img src="data:image/png;base64,{images_b64.get('survival_curves', '')}" alt="Survival Curves">
            </div>
            
            <h3>2. Replacement Probability by Equipment Age per End-Use</h3>
            <p>Shows the conditional probability that equipment fails in the next year, given its current age. 
            All values should be in [0, 1].</p>
            <div class="visualization">
                <img src="data:image/png;base64,{images_b64.get('replacement_probability', '')}" alt="Replacement Probability">
            </div>
            
            <h3>3. Equipment Age Distribution with Replacement Probability Overlay</h3>
            <p>Scatter plot showing synthetic equipment age distribution with replacement probability for each unit. 
            Demonstrates how replacement probability varies across the equipment population.</p>
            <div class="visualization">
                <img src="data:image/png;base64,{images_b64.get('age_distribution_scatter', '')}" alt="Age Distribution Scatter">
            </div>
        </div>
        
        <div class="section">
            <h2>Interpretation</h2>
            <ul>
                <li><strong>Monotonicity:</strong> The survival function S(t) represents the probability that equipment survives to age t. 
                It must be monotonically decreasing (or flat) because equipment cannot "un-fail".</li>
                <li><strong>S(0) = 1.0:</strong> New equipment (age 0) always survives, so S(0) must equal 1.0.</li>
                <li><strong>Replacement Probability Bounds:</strong> The replacement probability P(t) represents the conditional probability 
                that equipment fails in the next year. It must be in [0, 1] to be a valid probability.</li>
                <li><strong>Shape Parameter β:</strong> Higher β values (e.g., 3.0 for HVAC) indicate concentrated replacement windows 
                (most equipment fails around the median life). Lower β values (e.g., 2.0 for fireplaces) indicate more gradual failure.</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return str(output_path)


def generate_markdown_report(validation_results: dict, viz_files: dict, output_path: Path) -> str:
    """Generate Markdown report with visualization references."""
    
    overall_status = "✓ PASSED" if validation_results['overall_passed'] else "✗ FAILED"
    
    md_content = f"""# Property 5: Weibull Survival Monotonicity Report

**Status:** {overall_status}

**Generated:** {validation_results['timestamp']}

**Validates:** Requirements 3.3

## Test Summary

### Property 5: Survival Monotonicity
- **Definition:** S(t) ≤ S(t-1) for all t > 0, and S(0) = 1.0
- **Status:** {'✓ PASSED' if validation_results['property_5']['test_passed'] else '✗ FAILED'}
- **Violations:** {len(validation_results['property_5']['violations'])}

### Property 5b: Probability Bounds
- **Definition:** replacement_probability is always in [0, 1]
- **Status:** {'✓ PASSED' if validation_results['property_5b']['test_passed'] else '✗ FAILED'}
- **Violations:** {len(validation_results['property_5b']['violations'])}

## Weibull Parameters and Statistics

| End-Use | β (Shape) | η (Scale) | Useful Life | S(0) | S(median) | S(2×median) |
|---------|-----------|-----------|-------------|------|-----------|-------------|
"""
    
    for end_use, stats in validation_results['property_5']['statistics'].items():
        md_content += f"| {end_use} | {stats['beta']:.2f} | {stats['eta']:.2f} | {stats['useful_life']} | {stats['s_0']:.6f} | {stats['s_median']:.6f} | {stats['s_2x_median']:.6f} |\n"
    
    md_content += "\n## Replacement Probability Bounds\n\n"
    md_content += "| End-Use | Min P | Max P | P(median) | P(2×median) |\n"
    md_content += "|---------|-------|-------|-----------|-------------|\n"
    
    for end_use, stats in validation_results['property_5b']['statistics'].items():
        md_content += f"| {end_use} | {stats['min_probability']:.6f} | {stats['max_probability']:.6f} | {stats['prob_at_median']:.6f} | {stats['prob_at_2x_median']:.6f} |\n"
    
    if validation_results['property_5']['violations']:
        md_content += "\n## Property 5 Violations\n\n"
        for violation in validation_results['property_5']['violations']:
            md_content += f"- {violation}\n"
    
    if validation_results['property_5b']['violations']:
        md_content += "\n## Property 5b Violations\n\n"
        for violation in validation_results['property_5b']['violations']:
            md_content += f"- {violation}\n"
    
    if not validation_results['property_5']['violations'] and not validation_results['property_5b']['violations']:
        md_content += "\n## Violations\n\n✓ No violations detected\n"
    
    md_content += """
## Visualizations

### 1. Weibull Survival Curves by End-Use Category
Shows how survival probability decreases with equipment age for each end-use category. 
All curves should be monotonically decreasing and start at S(0) = 1.0.

![Survival Curves](weibull_survival_curves.png)

### 2. Replacement Probability by Equipment Age per End-Use
Shows the conditional probability that equipment fails in the next year, given its current age. 
All values should be in [0, 1].

![Replacement Probability](replacement_probability.png)

### 3. Equipment Age Distribution with Replacement Probability Overlay
Scatter plot showing synthetic equipment age distribution with replacement probability for each unit. 
Demonstrates how replacement probability varies across the equipment population.

![Age Distribution Scatter](age_distribution_scatter.png)

## Interpretation

- **Monotonicity:** The survival function S(t) represents the probability that equipment survives to age t. 
  It must be monotonically decreasing (or flat) because equipment cannot "un-fail".

- **S(0) = 1.0:** New equipment (age 0) always survives, so S(0) must equal 1.0.

- **Replacement Probability Bounds:** The replacement probability P(t) represents the conditional probability 
  that equipment fails in the next year. It must be in [0, 1] to be a valid probability.

- **Shape Parameter β:** Higher β values (e.g., 3.0 for HVAC) indicate concentrated replacement windows 
  (most equipment fails around the median life). Lower β values (e.g., 2.0 for fireplaces) indicate more gradual failure.

## Mathematical Background

The Weibull survival function is defined as:

```
S(t) = exp(-(t/η)^β)
```

Where:
- t = equipment age (years)
- η = scale parameter (characteristic life)
- β = shape parameter (controls failure rate distribution)

The replacement probability is the conditional probability of failure in the next year:

```
P(t) = 1 - S(t) / S(t-1)
```

This represents the probability that equipment should be replaced at age t.
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return str(output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = generate_property5_report()
    print(f"Report generated successfully")
    print(f"HTML: {result['html_path']}")
    print(f"Markdown: {result['md_path']}")
