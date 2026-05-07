"""
Unit tests for aggregation module with mock data.

Tests the aggregation functions with synthetic data to verify
correctness without requiring actual NW Natural data files.
"""

import pytest
import pandas as pd
import numpy as np
from src.aggregation import (
    aggregate_by_end_use,
    aggregate_by_segment,
    aggregate_by_district,
    compute_use_per_customer,
    compare_to_irp_forecast,
    export_results
)
import tempfile
import os


class TestAggregateByEndUse:
    """Tests for aggregate_by_end_use function."""
    
    def test_basic_aggregation(self):
        """Test basic aggregation by end-use."""
        # Create mock simulation results
        results = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P002'],
            'end_use': ['space_heating', 'water_heating', 'space_heating', 'water_heating'],
            'annual_therms': [500.0, 200.0, 450.0, 180.0],
            'year': [2025, 2025, 2025, 2025]
        })
        
        # Aggregate
        agg = aggregate_by_end_use(results)
        
        # Verify
        assert len(agg) == 2
        assert agg[agg['end_use'] == 'space_heating']['total_therms'].values[0] == 950.0
        assert agg[agg['end_use'] == 'water_heating']['total_therms'].values[0] == 380.0
        assert agg[agg['end_use'] == 'space_heating']['premise_count'].values[0] == 2
    
    def test_multiple_years(self):
        """Test aggregation across multiple years."""
        results = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P001', 'P001'],
            'end_use': ['space_heating', 'space_heating', 'water_heating', 'water_heating'],
            'annual_therms': [500.0, 480.0, 200.0, 190.0],
            'year': [2025, 2026, 2025, 2026]
        })
        
        agg = aggregate_by_end_use(results)
        
        # Should have 4 rows (2 years × 2 end-uses)
        assert len(agg) == 4
        assert agg[agg['year'] == 2025]['total_therms'].sum() == 700.0
        assert agg[agg['year'] == 2026]['total_therms'].sum() == 670.0
    
    def test_missing_columns(self):
        """Test error handling for missing columns."""
        results = pd.DataFrame({
            'blinded_id': ['P001'],
            'end_use': ['space_heating']
            # Missing 'annual_therms' and 'year'
        })
        
        with pytest.raises(ValueError):
            aggregate_by_end_use(results)


class TestAggregateBySegment:
    """Tests for aggregate_by_segment function."""
    
    def test_basic_segment_aggregation(self):
        """Test basic aggregation by segment."""
        results = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P002'],
            'end_use': ['space_heating', 'water_heating', 'space_heating', 'water_heating'],
            'annual_therms': [500.0, 200.0, 450.0, 180.0],
            'year': [2025, 2025, 2025, 2025]
        })
        
        segments = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'segment_code': ['RESSF', 'RESMF']
        })
        
        agg = aggregate_by_segment(results, segments)
        
        # Verify
        assert len(agg) == 4  # 2 segments × 2 end-uses
        assert agg[agg['segment_code'] == 'RESSF']['total_therms'].sum() == 700.0
        assert agg[agg['segment_code'] == 'RESMF']['total_therms'].sum() == 630.0
    
    def test_missing_segment_data(self):
        """Test handling of premises without segment data."""
        results = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'end_use': ['space_heating', 'space_heating'],
            'annual_therms': [500.0, 450.0],
            'year': [2025, 2025]
        })
        
        segments = pd.DataFrame({
            'blinded_id': ['P001'],  # P002 missing
            'segment_code': ['RESSF']
        })
        
        agg = aggregate_by_segment(results, segments)
        
        # Should still include P002 with NaN segment_code
        assert len(agg) >= 1


class TestAggregateByDistrict:
    """Tests for aggregate_by_district function."""
    
    def test_basic_district_aggregation(self):
        """Test basic aggregation by district."""
        results = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P002'],
            'end_use': ['space_heating', 'water_heating', 'space_heating', 'water_heating'],
            'annual_therms': [500.0, 200.0, 450.0, 180.0],
            'year': [2025, 2025, 2025, 2025]
        })
        
        premises = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'district_code_IRP': ['D001', 'D002']
        })
        
        agg = aggregate_by_district(results, premises)
        
        # Verify
        assert len(agg) == 4  # 2 districts × 2 end-uses
        assert agg[agg['district_code_IRP'] == 'D001']['total_therms'].sum() == 700.0
        assert agg[agg['district_code_IRP'] == 'D002']['total_therms'].sum() == 630.0


class TestComputeUsePerCustomer:
    """Tests for compute_use_per_customer function."""
    
    def test_basic_upc_computation(self):
        """Test basic UPC computation."""
        total_demand = pd.DataFrame({
            'year': [2025, 2026],
            'total_therms': [1000000.0, 950000.0]
        })
        
        customer_count = pd.DataFrame({
            'year': [2025, 2026],
            'customer_count': [1000, 1000]
        })
        
        upc = compute_use_per_customer(total_demand, customer_count)
        
        # Verify
        assert len(upc) == 2
        assert upc[upc['year'] == 2025]['use_per_customer'].values[0] == 1000.0
        assert upc[upc['year'] == 2026]['use_per_customer'].values[0] == 950.0
    
    def test_zero_customer_count(self):
        """Test handling of zero customer count."""
        total_demand = pd.DataFrame({
            'year': [2025],
            'total_therms': [1000000.0]
        })
        
        customer_count = pd.DataFrame({
            'year': [2025],
            'customer_count': [0]
        })
        
        upc = compute_use_per_customer(total_demand, customer_count)
        
        # Should return NaN for zero customer count
        assert pd.isna(upc['use_per_customer'].values[0])
    
    def test_upc_with_segments(self):
        """Test UPC computation with segment breakdown."""
        total_demand = pd.DataFrame({
            'year': [2025, 2025],
            'segment_code': ['RESSF', 'RESMF'],
            'total_therms': [500000.0, 500000.0]
        })
        
        customer_count = pd.DataFrame({
            'year': [2025, 2025],
            'segment_code': ['RESSF', 'RESMF'],
            'customer_count': [500, 500]
        })
        
        upc = compute_use_per_customer(total_demand, customer_count)
        
        # Verify
        assert len(upc) == 2
        assert all(upc['use_per_customer'] == 1000.0)


class TestCompareToIRPForecast:
    """Tests for compare_to_irp_forecast function."""
    
    def test_basic_comparison(self):
        """Test basic comparison to IRP forecast."""
        model_upc = pd.DataFrame({
            'year': [2025, 2026, 2027],
            'use_per_customer': [650.0, 640.0, 630.0]
        })
        
        irp_forecast = pd.DataFrame({
            'year': [2025, 2026, 2027],
            'upc': [648.0, 638.0, 628.0]
        })
        
        comparison = compare_to_irp_forecast(model_upc, irp_forecast)
        
        # Verify
        assert len(comparison) == 3
        assert comparison[comparison['year'] == 2025]['difference'].values[0] == pytest.approx(2.0)
        assert comparison[comparison['year'] == 2025]['percent_deviation'].values[0] == pytest.approx(0.309, rel=0.01)
    
    def test_missing_irp_data(self):
        """Test handling of missing IRP data."""
        model_upc = pd.DataFrame({
            'year': [2025, 2026, 2027],
            'use_per_customer': [650.0, 640.0, 630.0]
        })
        
        irp_forecast = pd.DataFrame({
            'year': [2025, 2026],  # Missing 2027
            'upc': [648.0, 638.0]
        })
        
        comparison = compare_to_irp_forecast(model_upc, irp_forecast)
        
        # Should include all years, with NaN for missing IRP data
        assert len(comparison) == 3
        assert pd.isna(comparison[comparison['year'] == 2027]['irp_upc'].values[0])


class TestExportResults:
    """Tests for export_results function."""
    
    def test_export_csv(self):
        """Test CSV export."""
        results = pd.DataFrame({
            'year': [2025, 2026],
            'end_use': ['space_heating', 'space_heating'],
            'total_therms': [1000000.0, 950000.0]
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'results.csv')
            export_results(results, output_path, format='csv')
            
            # Verify file exists and can be read
            assert os.path.exists(output_path)
            loaded = pd.read_csv(output_path)
            assert len(loaded) == 2
            assert list(loaded.columns) == ['year', 'end_use', 'total_therms']
    
    def test_export_json(self):
        """Test JSON export."""
        results = pd.DataFrame({
            'year': [2025, 2026],
            'end_use': ['space_heating', 'space_heating'],
            'total_therms': [1000000.0, 950000.0]
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'results.json')
            export_results(results, output_path, format='json')
            
            # Verify file exists and can be read
            assert os.path.exists(output_path)
            loaded = pd.read_json(output_path)
            assert len(loaded) == 2
    
    def test_invalid_format(self):
        """Test error handling for invalid format."""
        results = pd.DataFrame({'year': [2025]})
        
        with pytest.raises(ValueError):
            export_results(results, 'output.txt', format='txt')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
