"""
Integration test for build_premise_equipment_table function.

This test verifies that the build_premise_equipment_table function correctly
joins premise, equipment, segment, and equipment_codes data to produce a valid
premise-equipment table with end-use and efficiency columns derived from config.
"""

import pytest
import pandas as pd
import numpy as np
from src.data_ingestion import build_premise_equipment_table
from src.config import END_USE_MAP, DEFAULT_EFFICIENCY


class TestBuildPremiseEquipmentTable:
    """Test suite for build_premise_equipment_table integration."""

    def test_build_premise_equipment_table_with_mock_data(self):
        """
        Test build_premise_equipment_table with mock data that simulates
        the structure of real NW Natural CSV files.
        """
        # Create mock premise data
        premise_df = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'custtype': ['R', 'R', 'R'],
            'status_code': ['AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
            'service_address_zip': ['97201', '98660', '97214'],
        })

        # Create mock equipment data
        equipment_df = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P003'],
            'equipment_type_code': ['HEAT', 'WTR', 'HEAT', 'HEAT'],
            'install_year': [2010, 2015, 2005, 2018],
            'efficiency': [0.85, 0.82, 0.78, 0.92],
        })

        # Create mock segment data
        segment_df = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'segment_code': ['RESSF', 'RESSF', 'RESMF'],
        })

        # Create mock equipment_codes data
        equipment_codes_df = pd.DataFrame({
            'equipment_type_code': ['HEAT', 'WTR', 'FRPL', 'RRGE', 'RDRY'],
            'equipment_class': ['HEAT', 'WTR', 'FRPL', 'OTHR', 'OTHR'],
            'description': ['Furnace', 'Water Heater', 'Fireplace', 'Range/Oven', 'Clothes Dryer'],
        })

        # Call the function
        result = build_premise_equipment_table(
            premise_df, equipment_df, segment_df, equipment_codes_df
        )

        # Verify result is a DataFrame
        assert isinstance(result, pd.DataFrame), "Result should be a DataFrame"

        # Verify result has expected columns
        expected_columns = {
            'blinded_id', 'equipment_type_code', 'end_use', 'efficiency',
            'install_year', 'segment_code', 'district_code_IRP'
        }
        assert expected_columns.issubset(set(result.columns)), \
            f"Result missing expected columns. Expected {expected_columns}, got {set(result.columns)}"

        # Verify result has correct number of rows (should match equipment_df)
        assert len(result) == len(equipment_df), \
            f"Result should have {len(equipment_df)} rows, got {len(result)}"

        # Verify end_use column is populated correctly
        assert result['end_use'].notna().all(), \
            "All rows should have a non-null end_use value"

        # Verify end_use values are valid (in END_USE_MAP values)
        valid_end_uses = set(END_USE_MAP.values())
        invalid_end_uses = set(result['end_use']) - valid_end_uses
        assert len(invalid_end_uses) == 0, \
            f"Result contains invalid end_use values: {invalid_end_uses}"

        # Verify efficiency column is populated
        assert result['efficiency'].notna().all(), \
            "All rows should have a non-null efficiency value"

        # Verify efficiency values are reasonable (between 0 and 1)
        assert (result['efficiency'] > 0).all() and (result['efficiency'] <= 1).all(), \
            "All efficiency values should be between 0 and 1"

        # Verify join preserved premise attributes
        assert result['district_code_IRP'].notna().all(), \
            "All rows should have district_code_IRP from premise data"

        assert result['segment_code'].notna().all(), \
            "All rows should have segment_code from segment data"

    def test_build_premise_equipment_table_handles_missing_efficiency(self):
        """
        Test that build_premise_equipment_table fills missing efficiency values
        with defaults from config.DEFAULT_EFFICIENCY.
        """
        premise_df = pd.DataFrame({
            'blinded_id': ['P001'],
            'custtype': ['R'],
            'status_code': ['AC'],
            'district_code_IRP': ['MULT'],
        })

        equipment_df = pd.DataFrame({
            'blinded_id': ['P001'],
            'equipment_type_code': ['HEAT'],
            'install_year': [2010],
            'efficiency': [np.nan],  # Missing efficiency
        })

        segment_df = pd.DataFrame({
            'blinded_id': ['P001'],
            'segment_code': ['RESSF'],
        })

        equipment_codes_df = pd.DataFrame({
            'equipment_type_code': ['HEAT'],
            'equipment_class': ['HEAT'],
            'description': ['Furnace'],
        })

        result = build_premise_equipment_table(
            premise_df, equipment_df, segment_df, equipment_codes_df
        )

        # Verify efficiency was filled with default
        assert result['efficiency'].notna().all(), \
            "Missing efficiency should be filled with default value"

        # Verify filled efficiency is from DEFAULT_EFFICIENCY
        expected_efficiency = DEFAULT_EFFICIENCY.get('space_heating', 0.85)
        assert result['efficiency'].iloc[0] == expected_efficiency, \
            f"Expected efficiency {expected_efficiency}, got {result['efficiency'].iloc[0]}"

    def test_build_premise_equipment_table_left_join_behavior(self):
        """
        Test that build_premise_equipment_table performs a left join on equipment,
        preserving all equipment rows even if some premises lack segment data.
        """
        premise_df = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'custtype': ['R', 'R'],
            'status_code': ['AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH'],
        })

        equipment_df = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002'],
            'equipment_type_code': ['HEAT', 'WTR', 'HEAT'],
            'install_year': [2010, 2015, 2005],
            'efficiency': [0.85, 0.82, 0.78],
        })

        # Segment data missing P002
        segment_df = pd.DataFrame({
            'blinded_id': ['P001'],
            'segment_code': ['RESSF'],
        })

        equipment_codes_df = pd.DataFrame({
            'equipment_type_code': ['HEAT', 'WTR'],
            'equipment_class': ['HEAT', 'WTR'],
            'description': ['Furnace', 'Water Heater'],
        })

        result = build_premise_equipment_table(
            premise_df, equipment_df, segment_df, equipment_codes_df
        )

        # Verify all equipment rows are preserved
        assert len(result) == len(equipment_df), \
            "Left join should preserve all equipment rows"

        # Verify P002 equipment is included even though segment data is missing
        p002_equipment = result[result['blinded_id'] == 'P002']
        assert len(p002_equipment) > 0, \
            "Equipment for P002 should be included even if segment data is missing"

    def test_build_premise_equipment_table_end_use_mapping(self):
        """
        Test that build_premise_equipment_table correctly maps equipment_type_code
        to end_use using END_USE_MAP from config.
        """
        premise_df = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P001', 'P001'],
            'custtype': ['R', 'R', 'R', 'R'],
            'status_code': ['AC', 'AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'MULT', 'MULT', 'MULT'],
        })

        # Create equipment with different types
        equipment_df = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P001', 'P001'],
            'equipment_type_code': ['HEAT', 'WTR', 'FRPL', 'RRGE'],
            'install_year': [2010, 2015, 2005, 2018],
            'efficiency': [0.85, 0.82, 0.78, 0.92],
        })

        segment_df = pd.DataFrame({
            'blinded_id': ['P001'],
            'segment_code': ['RESSF'],
        })

        equipment_codes_df = pd.DataFrame({
            'equipment_type_code': ['HEAT', 'WTR', 'FRPL', 'RRGE'],
            'equipment_class': ['HEAT', 'WTR', 'FRPL', 'OTHR'],
            'description': ['Furnace', 'Water Heater', 'Fireplace', 'Range/Oven'],
        })

        result = build_premise_equipment_table(
            premise_df, equipment_df, segment_df, equipment_codes_df
        )

        # Verify end_use mapping
        for idx, row in result.iterrows():
            equipment_code = row['equipment_type_code']
            expected_end_use = END_USE_MAP.get(equipment_code)
            actual_end_use = row['end_use']
            assert actual_end_use == expected_end_use, \
                f"Equipment {equipment_code} should map to {expected_end_use}, got {actual_end_use}"
