"""Data ingestion validation suite for NW Natural End-Use Forecasting Model."""

from src.validation.billing_calibration import (
    load_and_prepare_billing_data,
    convert_billing_to_therms_per_premise,
    compare_simulated_vs_billing,
    flag_divergent_premises,
    run_billing_calibration
)

from src.validation.range_checking import (
    load_irp_forecast,
    check_range_violations,
    compare_model_vs_irp_upc,
    compare_vintage_cohort_upc,
    run_range_checking_and_irp_comparison,
    EXPECTED_RANGES,
    ERA_ANCHORS
)

from src.validation.metadata_and_limitations import (
    ModelMetadata,
    create_export_with_metadata,
    generate_limitation_report,
    build_standard_metadata
)

from src.validation.validation_report import (
    run_full_validation,
    generate_html_report,
    generate_markdown_report
)

__all__ = [
    # Billing calibration
    'load_and_prepare_billing_data',
    'convert_billing_to_therms_per_premise',
    'compare_simulated_vs_billing',
    'flag_divergent_premises',
    'run_billing_calibration',
    # Range checking
    'load_irp_forecast',
    'check_range_violations',
    'compare_model_vs_irp_upc',
    'compare_vintage_cohort_upc',
    'run_range_checking_and_irp_comparison',
    'EXPECTED_RANGES',
    'ERA_ANCHORS',
    # Metadata and limitations
    'ModelMetadata',
    'create_export_with_metadata',
    'generate_limitation_report',
    'build_standard_metadata',
    # Validation report
    'run_full_validation',
    'generate_html_report',
    'generate_markdown_report'
]
