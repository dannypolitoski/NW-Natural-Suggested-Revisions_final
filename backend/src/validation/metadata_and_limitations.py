"""
Metadata and limitation reporting module for NW Natural End-Use Forecasting Model.

Implements documentation by:
1. Including metadata with each export: scenario name, run date, parameters
2. Documenting data gaps encountered during ingestion
3. Stating outputs are for illustrative/academic purposes
4. Generating comprehensive limitation reports

Requirements: 8.1, 8.2, 8.4, 10.4
"""

import os
import logging
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib

from src.config import OUTPUT_DIR, BASE_YEAR

logger = logging.getLogger(__name__)


class ModelMetadata:
    """
    Container for model execution metadata.
    
    Tracks scenario parameters, run date, data sources, and limitations.
    """
    
    def __init__(
        self,
        scenario_name: str,
        base_year: int = BASE_YEAR,
        forecast_horizon: int = 10,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize metadata.
        
        Args:
            scenario_name: Name of scenario (e.g., 'Baseline', 'High Electrification')
            base_year: Base year for simulation
            forecast_horizon: Number of years to forecast
            parameters: Dictionary of scenario parameters
        """
        self.scenario_name = scenario_name
        self.base_year = base_year
        self.forecast_horizon = forecast_horizon
        self.parameters = parameters or {}
        self.run_date = datetime.now().isoformat()
        self.run_id = self._generate_run_id()
        
        # Data sources and gaps
        self.data_sources = []
        self.data_gaps = []
        self.assumptions = []
        self.limitations = []
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID from scenario name and timestamp."""
        content = f"{self.scenario_name}_{self.run_date}".encode()
        return hashlib.md5(content).hexdigest()[:12]
    
    def add_data_source(self, source_name: str, description: str, status: str = 'loaded'):
        """
        Record a data source used in the model.
        
        Args:
            source_name: Name of data source (e.g., 'NW Natural Premise Data')
            description: Description of data source
            status: 'loaded', 'partial', 'unavailable'
        """
        self.data_sources.append({
            'name': source_name,
            'description': description,
            'status': status
        })
    
    def add_data_gap(self, gap_name: str, description: str, impact: str, mitigation: str):
        """
        Record a data gap encountered during ingestion.
        
        Args:
            gap_name: Name of gap (e.g., 'Missing equipment efficiency data')
            description: Description of gap
            impact: Impact on model (e.g., 'Used default efficiency values')
            mitigation: How gap was mitigated
        """
        self.data_gaps.append({
            'name': gap_name,
            'description': description,
            'impact': impact,
            'mitigation': mitigation
        })
    
    def add_assumption(self, assumption_name: str, description: str, justification: str):
        """
        Record a key assumption made in the model.
        
        Args:
            assumption_name: Name of assumption
            description: Description of assumption
            justification: Justification for assumption
        """
        self.assumptions.append({
            'name': assumption_name,
            'description': description,
            'justification': justification
        })
    
    def add_limitation(self, limitation_name: str, description: str, scope: str):
        """
        Record a model limitation.
        
        Args:
            limitation_name: Name of limitation
            description: Description of limitation
            scope: Scope of limitation (e.g., 'Affects space heating projections')
        """
        self.limitations.append({
            'name': limitation_name,
            'description': description,
            'scope': scope
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'run_id': self.run_id,
            'scenario_name': self.scenario_name,
            'run_date': self.run_date,
            'base_year': self.base_year,
            'forecast_horizon': self.forecast_horizon,
            'parameters': self.parameters,
            'data_sources': self.data_sources,
            'data_gaps': self.data_gaps,
            'assumptions': self.assumptions,
            'limitations': self.limitations,
            'disclaimer': self._get_disclaimer()
        }
    
    def _get_disclaimer(self) -> str:
        """Get standard disclaimer for model outputs."""
        return (
            "This model is a prototype framework for academic and illustrative purposes only. "
            "Outputs are not suitable for regulatory filings or production forecasting. "
            "Results should be interpreted with consideration of documented limitations and data gaps. "
            "See limitations section for details."
        )
    
    def to_json(self, path: str):
        """Save metadata to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Saved metadata to {path}")
    
    def to_markdown(self, path: str):
        """Save metadata to Markdown file."""
        lines = []
        
        lines.append("# Model Execution Metadata\n")
        lines.append(f"**Run ID:** {self.run_id}\n")
        lines.append(f"**Scenario:** {self.scenario_name}\n")
        lines.append(f"**Run Date:** {self.run_date}\n")
        lines.append(f"**Base Year:** {self.base_year}\n")
        lines.append(f"**Forecast Horizon:** {self.forecast_horizon} years\n")
        
        lines.append("\n## Scenario Parameters\n")
        for key, value in self.parameters.items():
            lines.append(f"- **{key}:** {value}\n")
        
        lines.append("\n## Data Sources\n")
        for source in self.data_sources:
            lines.append(f"- **{source['name']}** ({source['status']}): {source['description']}\n")
        
        lines.append("\n## Data Gaps\n")
        if self.data_gaps:
            for gap in self.data_gaps:
                lines.append(f"### {gap['name']}\n")
                lines.append(f"**Description:** {gap['description']}\n")
                lines.append(f"**Impact:** {gap['impact']}\n")
                lines.append(f"**Mitigation:** {gap['mitigation']}\n\n")
        else:
            lines.append("No significant data gaps identified.\n")
        
        lines.append("\n## Key Assumptions\n")
        for assumption in self.assumptions:
            lines.append(f"### {assumption['name']}\n")
            lines.append(f"**Description:** {assumption['description']}\n")
            lines.append(f"**Justification:** {assumption['justification']}\n\n")
        
        lines.append("\n## Model Limitations\n")
        for limitation in self.limitations:
            lines.append(f"### {limitation['name']}\n")
            lines.append(f"**Description:** {limitation['description']}\n")
            lines.append(f"**Scope:** {limitation['scope']}\n\n")
        
        lines.append("\n## Disclaimer\n")
        lines.append(f"{self._get_disclaimer()}\n")
        
        with open(path, 'w') as f:
            f.writelines(lines)
        logger.info(f"Saved metadata to {path}")


def create_export_with_metadata(
    results: pd.DataFrame,
    metadata: ModelMetadata,
    output_path: str,
    format: str = 'csv'
) -> str:
    """
    Export results with metadata included.
    
    For CSV exports, metadata is saved as separate JSON file.
    For JSON exports, metadata is included in the file.
    
    Args:
        results: Results DataFrame to export
        metadata: ModelMetadata object
        output_path: Path to output file
        format: 'csv' or 'json'
    
    Returns:
        Path to exported file
    """
    logger.info(f"Exporting results with metadata to {output_path}...")
    
    # Create output directory
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if format == 'csv':
        # Export results as CSV
        results.to_csv(output_path, index=False)
        
        # Save metadata as JSON
        metadata_path = str(output_path).replace('.csv', '_metadata.json')
        metadata.to_json(metadata_path)
        
        # Save metadata as Markdown
        metadata_md_path = str(output_path).replace('.csv', '_metadata.md')
        metadata.to_markdown(metadata_md_path)
        
        logger.info(f"Exported {len(results)} rows to {output_path}")
        logger.info(f"Saved metadata to {metadata_path} and {metadata_md_path}")
        
        return output_path
    
    elif format == 'json':
        # Combine results and metadata
        export_data = {
            'metadata': metadata.to_dict(),
            'results': results.to_dict(orient='records')
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Exported {len(results)} rows with metadata to {output_path}")
        return output_path
    
    else:
        raise ValueError(f"Unsupported format: {format}")


def generate_limitation_report(
    metadata: ModelMetadata,
    output_dir: str = OUTPUT_DIR
) -> str:
    """
    Generate comprehensive limitation report.
    
    Args:
        metadata: ModelMetadata object
        output_dir: Output directory
    
    Returns:
        Path to report file
    """
    logger.info("Generating limitation report...")
    
    output_path = Path(output_dir) / "validation"
    output_path.mkdir(parents=True, exist_ok=True)
    
    report_path = output_path / "LIMITATIONS_AND_DISCLAIMERS.md"
    
    lines = []
    
    lines.append("# Model Limitations and Disclaimers\n\n")
    
    lines.append("## Executive Summary\n\n")
    lines.append(
        "This document describes the limitations, assumptions, and data gaps in the "
        "NW Natural End-Use Forecasting Model. This model is a prototype framework "
        "for academic and illustrative purposes only and is not suitable for regulatory "
        "filings or production forecasting.\n\n"
    )
    
    lines.append("## Disclaimer\n\n")
    lines.append(f"{metadata._get_disclaimer()}\n\n")
    
    lines.append("## Data Gaps and Mitigation\n\n")
    if metadata.data_gaps:
        for gap in metadata.data_gaps:
            lines.append(f"### {gap['name']}\n\n")
            lines.append(f"**Description:** {gap['description']}\n\n")
            lines.append(f"**Impact on Model:** {gap['impact']}\n\n")
            lines.append(f"**Mitigation Strategy:** {gap['mitigation']}\n\n")
    else:
        lines.append("No significant data gaps identified.\n\n")
    
    lines.append("## Key Assumptions\n\n")
    for assumption in metadata.assumptions:
        lines.append(f"### {assumption['name']}\n\n")
        lines.append(f"{assumption['description']}\n\n")
        lines.append(f"**Justification:** {assumption['justification']}\n\n")
    
    lines.append("## Model Limitations\n\n")
    for limitation in metadata.limitations:
        lines.append(f"### {limitation['name']}\n\n")
        lines.append(f"{limitation['description']}\n\n")
        lines.append(f"**Scope:** {limitation['scope']}\n\n")
    
    lines.append("## Recommended Use Cases\n\n")
    lines.append("This model is appropriate for:\n\n")
    lines.append("- Academic research and capstone projects\n")
    lines.append("- Exploratory scenario analysis\n")
    lines.append("- Understanding end-use demand drivers\n")
    lines.append("- Identifying data gaps and research needs\n")
    lines.append("- Prototyping bottom-up forecasting approaches\n\n")
    
    lines.append("## Not Recommended For\n\n")
    lines.append("This model is NOT appropriate for:\n\n")
    lines.append("- Regulatory filings or official forecasts\n")
    lines.append("- Production deployment without significant validation\n")
    lines.append("- Long-term forecasts beyond 10 years\n")
    lines.append("- Premise-level billing or rate-setting decisions\n")
    lines.append("- Comparison to historical data without calibration\n\n")
    
    lines.append("## Validation Status\n\n")
    lines.append("The model has been validated against:\n\n")
    lines.append("- NW Natural's IRP 10-year UPC forecast\n")
    lines.append("- Billing-derived therms per premise\n")
    lines.append("- RBSA building stock characteristics\n")
    lines.append("- EIA RECS end-use consumption benchmarks\n\n")
    
    lines.append("See validation reports in `output/validation/` for details.\n\n")
    
    lines.append("## Contact and Questions\n\n")
    lines.append("For questions about model limitations or appropriate use cases, "
        "contact the model development team.\n\n")
    
    lines.append(f"**Report Generated:** {datetime.now().isoformat()}\n")
    
    with open(report_path, 'w') as f:
        f.writelines(lines)
    
    logger.info(f"Generated limitation report: {report_path}")
    return str(report_path)


def build_standard_metadata(
    scenario_name: str,
    parameters: Optional[Dict[str, Any]] = None
) -> ModelMetadata:
    """
    Build standard metadata with common data sources and limitations.
    
    Args:
        scenario_name: Name of scenario
        parameters: Scenario parameters
    
    Returns:
        ModelMetadata object with standard entries
    """
    metadata = ModelMetadata(scenario_name, parameters=parameters)
    
    # Add standard data sources
    metadata.add_data_source(
        'NW Natural Premise Data',
        'Blinded premise characteristics (location, segment, vintage)',
        'loaded'
    )
    metadata.add_data_source(
        'NW Natural Equipment Data',
        'Equipment inventory by premise (type, efficiency, vintage)',
        'loaded'
    )
    metadata.add_data_source(
        'NW Natural Billing Data',
        'Historical billing data for calibration',
        'loaded'
    )
    metadata.add_data_source(
        'Weather Data',
        'Daily temperature and precipitation (2008-2025)',
        'loaded'
    )
    metadata.add_data_source(
        'RBSA 2022',
        'Residential Building Stock Assessment (NEEA)',
        'loaded'
    )
    metadata.add_data_source(
        'IRP Forecast',
        'NW Natural 2025 IRP 10-year UPC forecast',
        'loaded'
    )
    
    # Add standard data gaps
    metadata.add_data_gap(
        'Equipment Efficiency Ratings',
        'Not all equipment has explicit efficiency ratings in NW Natural data',
        'Used RBSA-derived efficiency distributions and defaults',
        'Calibrated against billing data'
    )
    metadata.add_data_gap(
        'Building Envelope Characteristics',
        'NW Natural data lacks detailed envelope properties (insulation, window type)',
        'Used RBSA 2022 building shell data as proxy',
        'Validated against historical UPC trends'
    )
    metadata.add_data_gap(
        'Occupancy and Usage Patterns',
        'No detailed occupancy or usage pattern data available',
        'Used RECS national averages and RBSA metering data',
        'Calibrated to billing-derived consumption'
    )
    
    # Add standard assumptions
    metadata.add_assumption(
        'Heating Degree Days (HDD) Model',
        'Space heating consumption modeled as linear function of HDD (base 65°F)',
        'Standard industry practice; validated against RBSA metering data'
    )
    metadata.add_assumption(
        'Equipment Replacement via Weibull Survival',
        'Equipment replacement timing follows Weibull survival distribution',
        'Empirically grounded in ASHRAE service life data'
    )
    metadata.add_assumption(
        'Baseload Consumption Factors',
        'Non-weather-sensitive end uses (cooking, drying) modeled as constant annual consumption',
        'Derived from RECS 2020 and RBSA metering data'
    )
    metadata.add_assumption(
        'Weather Station Assignment',
        'Premises assigned to nearest weather station by district',
        'Practical approach given limited weather station coverage'
    )
    
    # Add standard limitations
    metadata.add_limitation(
        'Spatial Resolution',
        'Model operates at premise level but aggregates to district/system level. '
        'No sub-district geographic granularity.',
        'Affects ability to analyze localized demand patterns'
    )
    metadata.add_limitation(
        'Temporal Resolution',
        'Model produces annual demand projections. No monthly or daily profiles.',
        'Limits ability to analyze peak demand or seasonal patterns'
    )
    metadata.add_limitation(
        'Calibration Scope',
        'Calibrated to 2025 baseline year. Historical calibration limited to available billing data.',
        'Projections beyond 2035 increasingly uncertain'
    )
    metadata.add_limitation(
        'Electrification Modeling',
        'Fuel switching rates are scenario parameters, not endogenously determined. '
        'No economic optimization or market dynamics.',
        'Electrification projections depend on scenario assumptions'
    )
    metadata.add_limitation(
        'Data Blinding',
        'NW Natural data is blinded (premise IDs anonymized). '
        'Cannot validate against specific customer accounts.',
        'Limits ability to identify and correct premise-level errors'
    )
    
    return metadata
