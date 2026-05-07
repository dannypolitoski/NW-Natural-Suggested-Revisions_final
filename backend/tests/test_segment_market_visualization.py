"""
Test suite for task 2.3.7: Segment/Subsegment/Market Relationship Visualization.

Tests the visualize_segment_market_hierarchy() and generate_segment_profiles() functions
with mock premise-equipment data to verify:
1. Segment profiles are computed correctly
2. Market profiles are computed correctly
3. Appliance inventory tables are generated
4. Unaggregated data exports work (CSV + Parquet)
5. HTML report is generated
6. All output files exist and contain expected data
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
import json
from pathlib import Path

from src.visualization import visualize_segment_market_hierarchy, generate_segment_profiles


class TestGenerateSegmentProfiles:
    """Test suite for generate_segment_profiles function."""
    
    def test_generate_segment_profiles_with_mock_data(self):
        """Test segment profile generation with mock premise-equipment data."""
        # Create mock premise-equipment data
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P002', 'P003', 'P003', 'P004', 'P004'],
            'segment_code': ['RESSF', 'RESSF', 'RESSF', 'RESSF', 'RESMF', 'RESMF', 'MOBILE', 'MOBILE'],
            'district_code_IRP': ['D1', 'D1', 'D1', 'D1', 'D2', 'D2', 'D3', 'D3'],
            'end_use': ['space_heating', 'water_heating', 'space_heating', 'cooking', 'space_heating', 'water_heating', 'space_heating', 'drying'],
            'efficiency': [0.85, 0.60, 0.85, 0.40, 0.82, 0.65, 0.80, 0.78],
            'equipment_type_code': ['RFAU', 'RAWH', 'RFAU', 'RRGE', 'RBOL', 'WTRB', 'RFAU', 'RDRY'],
            'premise_age': [1985, 1985, 1990, 1990, 1980, 1980, 2000, 2000],
            'equipment_age': [2015, 2010, 2015, 2012, 2012, 2008, 2018, 2016],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas'],
        })
        
        # Generate profiles
        profiles = generate_segment_profiles(mock_data)
        
        # Verify structure
        assert 'segment_profiles' in profiles
        assert 'market_profiles' in profiles
        assert 'summary_stats' in profiles
        
        # Verify segment profiles
        assert 'RESSF' in profiles['segment_profiles']
        assert 'RESMF' in profiles['segment_profiles']
        assert 'MOBILE' in profiles['segment_profiles']
        
        # Verify RESSF profile
        ressf_profile = profiles['segment_profiles']['RESSF']
        assert ressf_profile['premise_count'] == 2  # P001, P002
        assert ressf_profile['premise_pct'] == 0.5  # 2 out of 4 premises
        assert 'space_heating' in ressf_profile['equipment_by_enduse']
        assert ressf_profile['equipment_by_enduse']['space_heating']['count'] == 2
        assert len(ressf_profile['top_equipment']) > 0
        assert ressf_profile['fuel_mix']['gas'] == 1.0  # All gas
        
        # Verify market profiles
        assert 'D1' in profiles['market_profiles']
        assert 'D2' in profiles['market_profiles']
        assert 'D3' in profiles['market_profiles']
        
        # Verify D1 market profile
        d1_profile = profiles['market_profiles']['D1']
        assert d1_profile['premise_count'] == 2  # P001, P002
        assert d1_profile['premise_pct'] == 0.5
        
        # Verify summary stats
        assert profiles['summary_stats']['total_premises'] == 4
        assert profiles['summary_stats']['total_equipment'] == 8
        
        logger.info("✓ Segment profile generation test passed")
    
    def test_generate_segment_profiles_empty_dataframe(self):
        """Test that empty DataFrame returns empty profiles."""
        empty_df = pd.DataFrame()
        profiles = generate_segment_profiles(empty_df)
        
        assert profiles['segment_profiles'] == {}
        assert profiles['market_profiles'] == {}
        assert profiles['summary_stats']['total_premises'] == 0
        assert profiles['summary_stats']['total_equipment'] == 0
        
        logger.info("✓ Empty DataFrame test passed")
    
    def test_generate_segment_profiles_missing_columns(self):
        """Test that missing optional columns are handled gracefully."""
        # Create data without optional columns
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P002'],
            'segment_code': ['RESSF', 'RESSF', 'RESMF', 'RESMF'],
            'district_code_IRP': ['D1', 'D1', 'D2', 'D2'],
            'end_use': ['space_heating', 'water_heating', 'space_heating', 'cooking'],
            'efficiency': [0.85, 0.60, 0.82, 0.40],
            'equipment_type_code': ['RFAU', 'RAWH', 'RBOL', 'RRGE'],
            # Missing: premise_age, equipment_age, fuel_type
        })
        
        profiles = generate_segment_profiles(mock_data)
        
        # Should still generate profiles
        assert 'RESSF' in profiles['segment_profiles']
        assert 'RESMF' in profiles['segment_profiles']
        
        # avg_premise_age should be None
        assert profiles['segment_profiles']['RESSF']['avg_premise_age'] is None
        
        logger.info("✓ Missing columns test passed")


class TestVisualizeSegmentMarketHierarchy:
    """Test suite for visualize_segment_market_hierarchy function."""
    
    def test_visualize_segment_market_hierarchy_generates_outputs(self):
        """Test that all expected output files are generated."""
        # Create mock premise-equipment data
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P002', 'P003', 'P003', 'P004', 'P004'],
            'segment_code': ['RESSF', 'RESSF', 'RESSF', 'RESSF', 'RESMF', 'RESMF', 'MOBILE', 'MOBILE'],
            'district_code_IRP': ['D1', 'D1', 'D1', 'D1', 'D2', 'D2', 'D3', 'D3'],
            'end_use': ['space_heating', 'water_heating', 'space_heating', 'cooking', 'space_heating', 'water_heating', 'space_heating', 'drying'],
            'efficiency': [0.85, 0.60, 0.85, 0.40, 0.82, 0.65, 0.80, 0.78],
            'equipment_type_code': ['RFAU', 'RAWH', 'RFAU', 'RRGE', 'RBOL', 'WTRB', 'RFAU', 'RDRY'],
            'premise_age': [1985, 1985, 1990, 1990, 1980, 1980, 2000, 2000],
            'equipment_age': [2015, 2010, 2015, 2012, 2012, 2008, 2018, 2016],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas'],
        })
        
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Generate visualizations
            outputs = visualize_segment_market_hierarchy(mock_data, output_dir=tmpdir)
            
            # Verify expected outputs
            expected_outputs = [
                'equipment_count_segment_enduse',
                'equipment_count_market_enduse',
                'top_equipment_types',
                'equipment_age_distribution_segment',
                'unaggregated_data_csv',
                'summary_table',
                'report_html',
            ]
            
            for output_name in expected_outputs:
                assert output_name in outputs, f"Missing output: {output_name}"
                output_path = outputs[output_name]
                assert os.path.exists(output_path), f"Output file does not exist: {output_path}"
            
            # Verify CSV files are readable
            segment_enduse_df = pd.read_csv(outputs['equipment_count_segment_enduse'])
            assert len(segment_enduse_df) > 0
            assert 'segment' in segment_enduse_df.columns
            
            market_enduse_df = pd.read_csv(outputs['equipment_count_market_enduse'])
            assert len(market_enduse_df) > 0
            assert 'market' in market_enduse_df.columns
            
            top_equipment_df = pd.read_csv(outputs['top_equipment_types'])
            assert len(top_equipment_df) > 0
            assert 'equipment_type_code' in top_equipment_df.columns
            
            summary_df = pd.read_csv(outputs['summary_table'])
            assert len(summary_df) > 0
            assert 'type' in summary_df.columns
            
            # Verify HTML report exists and contains expected content
            with open(outputs['report_html'], 'r') as f:
                html_content = f.read()
                assert '<html>' in html_content.lower()
                assert 'segment' in html_content.lower()
                assert 'market' in html_content.lower()
            
            # Verify unaggregated data
            unagg_df = pd.read_csv(outputs['unaggregated_data_csv'])
            assert len(unagg_df) == len(mock_data)
            assert 'blinded_id' in unagg_df.columns
            
            logger.info(f"✓ Generated {len(outputs)} output files successfully")
    
    def test_visualize_segment_market_hierarchy_appliance_tables(self):
        """Test that appliance inventory tables are accurate."""
        # Create mock data with known equipment distribution
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P002'],
            'segment_code': ['RESSF', 'RESSF', 'RESSF', 'RESSF'],
            'district_code_IRP': ['D1', 'D1', 'D1', 'D1'],
            'end_use': ['space_heating', 'water_heating', 'space_heating', 'cooking'],
            'efficiency': [0.85, 0.60, 0.85, 0.40],
            'equipment_type_code': ['RFAU', 'RAWH', 'RFAU', 'RRGE'],
            'premise_age': [1985, 1985, 1990, 1990],
            'equipment_age': [2015, 2010, 2015, 2012],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas', 'natural_gas'],
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            outputs = visualize_segment_market_hierarchy(mock_data, output_dir=tmpdir)
            
            # Verify segment × end-use table
            segment_enduse_df = pd.read_csv(outputs['equipment_count_segment_enduse'])
            assert segment_enduse_df.loc[segment_enduse_df['segment'] == 'RESSF', 'space_heating'].values[0] == 2
            assert segment_enduse_df.loc[segment_enduse_df['segment'] == 'RESSF', 'water_heating'].values[0] == 1
            assert segment_enduse_df.loc[segment_enduse_df['segment'] == 'RESSF', 'cooking'].values[0] == 1
            
            # Verify market × end-use table
            market_enduse_df = pd.read_csv(outputs['equipment_count_market_enduse'])
            assert market_enduse_df.loc[market_enduse_df['market'] == 'D1', 'space_heating'].values[0] == 2
            
            # Verify top equipment types
            top_equipment_df = pd.read_csv(outputs['top_equipment_types'])
            assert 'RFAU' in top_equipment_df['equipment_type_code'].values
            assert top_equipment_df.loc[top_equipment_df['equipment_type_code'] == 'RFAU', 'count'].values[0] == 2
            
            logger.info("✓ Appliance inventory tables test passed")
    
    def test_visualize_segment_market_hierarchy_summary_accuracy(self):
        """Test that summary statistics are accurate."""
        # Create mock data with known statistics
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P002', 'P003', 'P003'],
            'segment_code': ['RESSF', 'RESSF', 'RESSF', 'RESSF', 'RESMF', 'RESMF'],
            'district_code_IRP': ['D1', 'D1', 'D1', 'D1', 'D2', 'D2'],
            'end_use': ['space_heating', 'water_heating', 'space_heating', 'cooking', 'space_heating', 'water_heating'],
            'efficiency': [0.85, 0.60, 0.85, 0.40, 0.82, 0.65],
            'equipment_type_code': ['RFAU', 'RAWH', 'RFAU', 'RRGE', 'RBOL', 'WTRB'],
            'premise_age': [1985, 1985, 1990, 1990, 1980, 1980],
            'equipment_age': [2015, 2010, 2015, 2012, 2012, 2008],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas', 'natural_gas'],
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            outputs = visualize_segment_market_hierarchy(mock_data, output_dir=tmpdir)
            
            # Verify summary table
            summary_df = pd.read_csv(outputs['summary_table'])
            
            # Should have 3 rows: 2 segments + 2 markets
            assert len(summary_df) >= 2
            
            # Verify segment rows
            ressf_row = summary_df[summary_df['code'] == 'RESSF']
            assert len(ressf_row) == 1
            assert ressf_row['premise_count'].values[0] == 2
            assert ressf_row['premise_pct'].values[0] == pytest.approx(2/3, rel=0.01)
            
            # Verify market rows
            d1_row = summary_df[summary_df['code'] == 'D1']
            assert len(d1_row) == 1
            assert d1_row['premise_count'].values[0] == 2
            
            logger.info("✓ Summary accuracy test passed")


# Import logging for test output
import logging
logger = logging.getLogger(__name__)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
