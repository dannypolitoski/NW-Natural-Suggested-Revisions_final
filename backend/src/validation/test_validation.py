"""
Test script for validation module (Task 13).

Tests all three subtasks:
1. Billing-based calibration
2. Range-checking and IRP comparison
3. Metadata and limitation reporting

Run with: python -m src.validation.test_validation
"""

import os
import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.config import OUTPUT_DIR, BASE_YEAR
from src.validation import (
    run_billing_calibration,
    run_range_checking_and_irp_comparison,
    build_standard_metadata,
    generate_limitation_report,
    run_full_validation
)


def create_test_data() -> tuple:
    """
    Create synthetic test data for validation testing.
    
    Returns:
        Tuple of (simulation_results, model_results, premises)
    """
    logger.info("Creating test data...")
    
    # Create synthetic simulation results
    np.random.seed(42)
    n_premises = 100
    n_years = 1
    
    premises_list = [f"PREM_{i:05d}" for i in range(n_premises)]
    end_uses = ['space_heating', 'water_heating', 'cooking', 'drying', 'fireplace', 'other']
    
    sim_data = []
    for premise in premises_list:
        for end_use in end_uses:
            # Generate realistic consumption values
            if end_use == 'space_heating':
                therms = np.random.normal(400, 100)
            elif end_use == 'water_heating':
                therms = np.random.normal(100, 20)
            elif end_use == 'cooking':
                therms = np.random.normal(25, 5)
            elif end_use == 'drying':
                therms = np.random.normal(20, 5)
            elif end_use == 'fireplace':
                therms = np.random.normal(30, 20)
            else:
                therms = np.random.normal(10, 5)
            
            therms = max(0, therms)  # Ensure non-negative
            
            sim_data.append({
                'blinded_id': premise,
                'end_use': end_use,
                'annual_therms': therms,
                'year': BASE_YEAR
            })
    
    simulation_results = pd.DataFrame(sim_data)
    
    # Create model results (aggregated)
    model_data = []
    for year in range(BASE_YEAR, BASE_YEAR + 1):
        total_therms = simulation_results[simulation_results['year'] == year]['annual_therms'].sum()
        model_data.append({
            'year': year,
            'total_therms': total_therms,
            'customer_count': n_premises
        })
    
    model_results = pd.DataFrame(model_data)
    
    # Create premises data
    premises_data = []
    for i, premise in enumerate(premises_list):
        state = 'OR' if i % 2 == 0 else 'WA'
        vintage_year = np.random.choice([1980, 2000, 2015, 2022])
        
        premises_data.append({
            'blinded_id': premise,
            'state': state,
            'vintage_year': vintage_year,
            'district_code_IRP': f'DIST_{i % 5:02d}'
        })
    
    premises = pd.DataFrame(premises_data)
    
    logger.info(f"Created test data: {len(simulation_results)} simulation records, {len(premises)} premises")
    return simulation_results, model_results, premises


def test_subtask_13_1():
    """Test subtask 13.1: Billing-based calibration."""
    logger.info("\n" + "="*60)
    logger.info("Testing Subtask 13.1: Billing-based Calibration")
    logger.info("="*60)
    
    try:
        sim_results, model_results, premises = create_test_data()
        
        # Run billing calibration
        results = run_billing_calibration(sim_results, premises, OUTPUT_DIR)
        
        logger.info(f"✓ Billing calibration completed")
        logger.info(f"  - Comparison records: {len(results['comparison'])}")
        logger.info(f"  - Flagged premises: {len(results['flagged'])}")
        logger.info(f"  - Metrics: {results['metrics']}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Billing calibration failed: {e}", exc_info=True)
        return False


def test_subtask_13_2():
    """Test subtask 13.2: Range-checking and IRP comparison."""
    logger.info("\n" + "="*60)
    logger.info("Testing Subtask 13.2: Range-Checking and IRP Comparison")
    logger.info("="*60)
    
    try:
        sim_results, model_results, premises = create_test_data()
        
        # Run range checking
        results = run_range_checking_and_irp_comparison(
            sim_results, model_results, premises, OUTPUT_DIR
        )
        
        logger.info(f"✓ Range checking completed")
        logger.info(f"  - Range violations: {len(results['range_violations'])}")
        logger.info(f"  - Range summary: {results['range_summary']}")
        logger.info(f"  - IRP comparison records: {len(results['irp_comparison'])}")
        logger.info(f"  - IRP metrics: {results['irp_metrics']}")
        logger.info(f"  - Vintage comparison records: {len(results['vintage_comparison'])}")
        logger.info(f"  - Vintage metrics: {results['vintage_metrics']}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Range checking failed: {e}", exc_info=True)
        return False


def test_subtask_13_3():
    """Test subtask 13.3: Metadata and limitation reporting."""
    logger.info("\n" + "="*60)
    logger.info("Testing Subtask 13.3: Metadata and Limitation Reporting")
    logger.info("="*60)
    
    try:
        # Build standard metadata
        metadata = build_standard_metadata(
            'Test Scenario',
            {'housing_growth_rate': 0.01, 'electrification_rate': 0.05}
        )
        
        logger.info(f"✓ Metadata created")
        logger.info(f"  - Run ID: {metadata.run_id}")
        logger.info(f"  - Data sources: {len(metadata.data_sources)}")
        logger.info(f"  - Data gaps: {len(metadata.data_gaps)}")
        logger.info(f"  - Assumptions: {len(metadata.assumptions)}")
        logger.info(f"  - Limitations: {len(metadata.limitations)}")
        
        # Generate limitation report
        output_dir = Path(OUTPUT_DIR) / "validation"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = generate_limitation_report(metadata, OUTPUT_DIR)
        logger.info(f"✓ Limitation report generated: {report_path}")
        
        # Save metadata
        metadata.to_json(str(output_dir / "test_metadata.json"))
        metadata.to_markdown(str(output_dir / "test_metadata.md"))
        logger.info(f"✓ Metadata saved to JSON and Markdown")
        
        return True
    except Exception as e:
        logger.error(f"✗ Metadata and limitation reporting failed: {e}", exc_info=True)
        return False


def test_full_validation():
    """Test full validation workflow."""
    logger.info("\n" + "="*60)
    logger.info("Testing Full Validation Workflow")
    logger.info("="*60)
    
    try:
        sim_results, model_results, premises = create_test_data()
        
        # Run full validation
        results = run_full_validation(
            sim_results,
            model_results,
            premises,
            scenario_name='Test Scenario',
            scenario_parameters={'housing_growth_rate': 0.01},
            output_dir=OUTPUT_DIR
        )
        
        logger.info(f"✓ Full validation completed")
        logger.info(f"  - HTML report: {results['report_html']}")
        logger.info(f"  - Markdown report: {results['report_md']}")
        logger.info(f"  - Output directory: {results['output_dir']}")
        
        # Verify files exist
        assert Path(results['report_html']).exists(), "HTML report not found"
        assert Path(results['report_md']).exists(), "Markdown report not found"
        
        logger.info(f"✓ All report files verified")
        
        return True
    except Exception as e:
        logger.error(f"✗ Full validation failed: {e}", exc_info=True)
        return False


def main():
    """Run all tests."""
    logger.info("Starting validation module tests...")
    
    results = {
        'Subtask 13.1 (Billing Calibration)': test_subtask_13_1(),
        'Subtask 13.2 (Range Checking)': test_subtask_13_2(),
        'Subtask 13.3 (Metadata & Limitations)': test_subtask_13_3(),
        'Full Validation Workflow': test_full_validation()
    }
    
    logger.info("\n" + "="*60)
    logger.info("Test Summary")
    logger.info("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("\n✓ All tests passed!")
        return 0
    else:
        logger.error("\n✗ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
