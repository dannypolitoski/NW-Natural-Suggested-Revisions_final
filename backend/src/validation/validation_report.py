"""
Comprehensive validation report generator for NW Natural End-Use Forecasting Model.

Orchestrates all three validation subtasks:
1. Billing-based calibration
2. Range-checking and IRP comparison
3. Metadata and limitation reporting

Generates HTML and Markdown reports with visualizations and summary statistics.

Requirements: 7.1, 8.1, 8.2, 8.4, 10.1, 10.2, 10.3, 10.4
"""

import os
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional, Any
from datetime import datetime
import json

from src.config import OUTPUT_DIR, BASE_YEAR
from src.validation.billing_calibration import run_billing_calibration
from src.validation.range_checking import run_range_checking_and_irp_comparison
from src.validation.metadata_and_limitations import (
    ModelMetadata, build_standard_metadata, generate_limitation_report,
    create_export_with_metadata
)

logger = logging.getLogger(__name__)


def generate_html_report(
    title: str,
    sections: Dict[str, str],
    output_path: str
) -> str:
    """
    Generate HTML report from sections.
    
    Args:
        title: Report title
        sections: Dictionary of section_name -> HTML content
        output_path: Path to output HTML file
    
    Returns:
        Path to generated HTML file
    """
    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<title>{title}</title>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }",
        "h1 { color: #333; border-bottom: 3px solid #0066cc; padding-bottom: 10px; }",
        "h2 { color: #0066cc; margin-top: 30px; }",
        "h3 { color: #666; }",
        ".section { background-color: white; padding: 20px; margin: 20px 0; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        ".metric { display: inline-block; margin: 10px 20px 10px 0; padding: 10px; background-color: #f0f0f0; border-radius: 3px; }",
        ".metric-value { font-size: 24px; font-weight: bold; color: #0066cc; }",
        ".metric-label { font-size: 12px; color: #666; }",
        ".warning { background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }",
        ".critical { background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 10px; margin: 10px 0; }",
        ".ok { background-color: #d4edda; border-left: 4px solid #28a745; padding: 10px; margin: 10px 0; }",
        "table { width: 100%; border-collapse: collapse; margin: 10px 0; }",
        "th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }",
        "th { background-color: #0066cc; color: white; }",
        "tr:hover { background-color: #f5f5f5; }",
        ".footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{title}</h1>",
        f"<p><em>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>",
    ]
    
    for section_name, section_html in sections.items():
        html_lines.append(f"<div class='section'>")
        html_lines.append(f"<h2>{section_name}</h2>")
        html_lines.append(section_html)
        html_lines.append(f"</div>")
    
    html_lines.extend([
        "<div class='footer'>",
        "<p><strong>Disclaimer:</strong> This model is a prototype framework for academic and illustrative purposes only. "
        "Outputs are not suitable for regulatory filings or production forecasting.</p>",
        "</div>",
        "</body>",
        "</html>"
    ])
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_lines))
    
    logger.info(f"Generated HTML report: {output_path}")
    return output_path


def generate_markdown_report(
    title: str,
    sections: Dict[str, str],
    output_path: str
) -> str:
    """
    Generate Markdown report from sections.
    
    Args:
        title: Report title
        sections: Dictionary of section_name -> Markdown content
        output_path: Path to output Markdown file
    
    Returns:
        Path to generated Markdown file
    """
    md_lines = [
        f"# {title}\n",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "\n"
    ]
    
    for section_name, section_md in sections.items():
        md_lines.append(f"## {section_name}\n")
        md_lines.append(section_md)
        md_lines.append("\n")
    
    md_lines.append("## Disclaimer\n")
    md_lines.append(
        "This model is a prototype framework for academic and illustrative purposes only. "
        "Outputs are not suitable for regulatory filings or production forecasting. "
        "See LIMITATIONS_AND_DISCLAIMERS.md for details.\n"
    )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(md_lines)
    
    logger.info(f"Generated Markdown report: {output_path}")
    return output_path


def format_billing_calibration_section(
    results: Dict[str, Any]
) -> Tuple[str, str]:
    """
    Format billing calibration results as HTML and Markdown.
    
    Returns:
        Tuple of (html_content, markdown_content)
    """
    metrics = results.get('metrics', {})
    flagged = results.get('flagged', pd.DataFrame())
    
    # HTML
    html_lines = []
    
    html_lines.append("<h3>Summary Metrics</h3>")
    html_lines.append("<div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{metrics.get('mae', 0):.1f}</div><div class='metric-label'>MAE (therms)</div></div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{metrics.get('mean_bias', 0):.1f}</div><div class='metric-label'>Mean Bias (therms)</div></div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{metrics.get('r_squared', 0):.3f}</div><div class='metric-label'>R²</div></div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{metrics.get('num_outliers', 0)}</div><div class='metric-label'>Outliers (>50% error)</div></div>")
    html_lines.append("</div>")
    
    if metrics.get('outlier_percent', 0) > 10:
        html_lines.append(f"<div class='warning'>⚠️ {metrics.get('outlier_percent', 0):.1f}% of premises have >50% error. Review flagged premises.</div>")
    else:
        html_lines.append(f"<div class='ok'>✓ {100 - metrics.get('outlier_percent', 0):.1f}% of premises within acceptable range.</div>")
    
    if not flagged.empty:
        html_lines.append("<h3>Top Flagged Premises (by error magnitude)</h3>")
        html_lines.append("<table>")
        html_lines.append("<tr><th>Premise ID</th><th>Year</th><th>Simulated (therms)</th><th>Billing (therms)</th><th>Error (%)</th></tr>")
        for _, row in flagged.head(10).iterrows():
            html_lines.append(f"<tr><td>{row['blinded_id']}</td><td>{row['year']}</td><td>{row['simulated_therms']:.0f}</td><td>{row['estimated_therms']:.0f}</td><td>{row['percent_error']:.1f}%</td></tr>")
        html_lines.append("</table>")
    
    html_content = '\n'.join(html_lines)
    
    # Markdown
    md_lines = []
    md_lines.append("### Summary Metrics\n")
    md_lines.append(f"- **MAE:** {metrics.get('mae', 0):.1f} therms\n")
    md_lines.append(f"- **Mean Bias:** {metrics.get('mean_bias', 0):.1f} therms\n")
    md_lines.append(f"- **R²:** {metrics.get('r_squared', 0):.3f}\n")
    md_lines.append(f"- **Outliers:** {metrics.get('num_outliers', 0)} premises ({metrics.get('outlier_percent', 0):.1f}%)\n")
    
    if metrics.get('outlier_percent', 0) > 10:
        md_lines.append(f"\n⚠️ **Warning:** {metrics.get('outlier_percent', 0):.1f}% of premises have >50% error. Review flagged premises.\n")
    else:
        md_lines.append(f"\n✓ **Good:** {100 - metrics.get('outlier_percent', 0):.1f}% of premises within acceptable range.\n")
    
    if not flagged.empty:
        md_lines.append("\n### Top Flagged Premises\n")
        md_lines.append("| Premise ID | Year | Simulated (therms) | Billing (therms) | Error (%) |\n")
        md_lines.append("|---|---|---|---|---|\n")
        for _, row in flagged.head(10).iterrows():
            md_lines.append(f"| {row['blinded_id']} | {row['year']} | {row['simulated_therms']:.0f} | {row['estimated_therms']:.0f} | {row['percent_error']:.1f}% |\n")
    
    markdown_content = ''.join(md_lines)
    
    return html_content, markdown_content


def format_range_checking_section(
    results: Dict[str, Any]
) -> Tuple[str, str]:
    """
    Format range checking results as HTML and Markdown.
    
    Returns:
        Tuple of (html_content, markdown_content)
    """
    range_summary = results.get('range_summary', {})
    irp_metrics = results.get('irp_metrics', {})
    vintage_metrics = results.get('vintage_metrics', {})
    
    # HTML
    html_lines = []
    
    html_lines.append("<h3>Range Violations</h3>")
    html_lines.append("<div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{range_summary.get('total_violations', 0)}</div><div class='metric-label'>Total Violations</div></div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{range_summary.get('critical_count', 0)}</div><div class='metric-label'>Critical</div></div>")
    html_lines.append("</div>")
    
    if range_summary.get('critical_count', 0) > 0:
        html_lines.append(f"<div class='critical'>🔴 {range_summary.get('critical_count', 0)} critical violations detected.</div>")
    else:
        html_lines.append(f"<div class='ok'>✓ No critical violations.</div>")
    
    html_lines.append("<h3>IRP Comparison</h3>")
    html_lines.append("<div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{irp_metrics.get('mean_deviation_percent', 0):.1f}%</div><div class='metric-label'>Mean Deviation</div></div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{irp_metrics.get('max_deviation_percent', 0):.1f}%</div><div class='metric-label'>Max Deviation</div></div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{irp_metrics.get('years_within_5_percent', 0)}/{irp_metrics.get('total_years', 0)}</div><div class='metric-label'>Years Within 5%</div></div>")
    html_lines.append("</div>")
    
    html_lines.append("<h3>Vintage Cohort Comparison</h3>")
    html_lines.append("<div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{vintage_metrics.get('pre_2010_deviation', 0):.1f}%</div><div class='metric-label'>Pre-2010 Deviation</div></div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{vintage_metrics.get('2011_2019_deviation', 0):.1f}%</div><div class='metric-label'>2011-2019 Deviation</div></div>")
    html_lines.append(f"<div class='metric'><div class='metric-value'>{vintage_metrics.get('2020_plus_deviation', 0):.1f}%</div><div class='metric-label'>2020+ Deviation</div></div>")
    html_lines.append("</div>")
    
    html_content = '\n'.join(html_lines)
    
    # Markdown
    md_lines = []
    md_lines.append("### Range Violations\n")
    md_lines.append(f"- **Total Violations:** {range_summary.get('total_violations', 0)}\n")
    md_lines.append(f"- **Critical:** {range_summary.get('critical_count', 0)}\n")
    
    if range_summary.get('critical_count', 0) > 0:
        md_lines.append(f"\n🔴 **Critical:** {range_summary.get('critical_count', 0)} critical violations detected.\n")
    else:
        md_lines.append("\n✓ **Good:** No critical violations.\n")
    
    md_lines.append("\n### IRP Comparison\n")
    md_lines.append(f"- **Mean Deviation:** {irp_metrics.get('mean_deviation_percent', 0):.1f}%\n")
    md_lines.append(f"- **Max Deviation:** {irp_metrics.get('max_deviation_percent', 0):.1f}%\n")
    md_lines.append(f"- **Years Within 5%:** {irp_metrics.get('years_within_5_percent', 0)}/{irp_metrics.get('total_years', 0)}\n")
    
    md_lines.append("\n### Vintage Cohort Comparison\n")
    md_lines.append(f"- **Pre-2010 Deviation:** {vintage_metrics.get('pre_2010_deviation', 0):.1f}%\n")
    md_lines.append(f"- **2011-2019 Deviation:** {vintage_metrics.get('2011_2019_deviation', 0):.1f}%\n")
    md_lines.append(f"- **2020+ Deviation:** {vintage_metrics.get('2020_plus_deviation', 0):.1f}%\n")
    
    markdown_content = ''.join(md_lines)
    
    return html_content, markdown_content


def run_full_validation(
    simulation_results: pd.DataFrame,
    model_results: pd.DataFrame,
    premises: pd.DataFrame,
    scenario_name: str = 'Baseline',
    scenario_parameters: Optional[Dict[str, Any]] = None,
    output_dir: str = OUTPUT_DIR
) -> Dict[str, Any]:
    """
    Run complete validation workflow with all three subtasks.
    
    Args:
        simulation_results: Premise-level simulation results
        model_results: Aggregated model results
        premises: Premise data
        scenario_name: Name of scenario
        scenario_parameters: Scenario parameters dictionary
        output_dir: Output directory
    
    Returns:
        Dictionary with all validation results and report paths
    """
    logger.info(f"Running full validation for scenario: {scenario_name}")
    
    # Create output directory
    output_path = Path(output_dir) / "validation"
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Build metadata
    metadata = build_standard_metadata(scenario_name, scenario_parameters)
    
    # Subtask 13.1: Billing-based calibration
    logger.info("Running subtask 13.1: Billing-based calibration...")
    billing_results = run_billing_calibration(simulation_results, premises, output_dir)
    
    # Subtask 13.2: Range-checking and IRP comparison
    logger.info("Running subtask 13.2: Range-checking and IRP comparison...")
    range_results = run_range_checking_and_irp_comparison(
        simulation_results, model_results, premises, output_dir
    )
    
    # Subtask 13.3: Metadata and limitation reporting
    logger.info("Running subtask 13.3: Metadata and limitation reporting...")
    generate_limitation_report(metadata, output_dir)
    
    # Generate comprehensive validation report
    logger.info("Generating comprehensive validation report...")
    
    sections_html = {}
    sections_md = {}
    
    # Billing calibration section
    html, md = format_billing_calibration_section(billing_results)
    sections_html['Billing-Based Calibration'] = html
    sections_md['Billing-Based Calibration'] = md
    
    # Range checking section
    html, md = format_range_checking_section(range_results)
    sections_html['Range Checking and IRP Comparison'] = html
    sections_md['Range Checking and IRP Comparison'] = md
    
    # Generate reports
    report_html_path = output_path / "VALIDATION_REPORT.html"
    report_md_path = output_path / "VALIDATION_REPORT.md"
    
    generate_html_report(
        f"Validation Report: {scenario_name}",
        sections_html,
        str(report_html_path)
    )
    
    generate_markdown_report(
        f"Validation Report: {scenario_name}",
        sections_md,
        str(report_md_path)
    )
    
    # Save metadata
    metadata.to_json(str(output_path / "metadata.json"))
    metadata.to_markdown(str(output_path / "metadata.md"))
    
    logger.info(f"Validation complete. Reports saved to {output_path}")
    
    return {
        'billing_results': billing_results,
        'range_results': range_results,
        'metadata': metadata,
        'report_html': str(report_html_path),
        'report_md': str(report_md_path),
        'output_dir': str(output_path)
    }
