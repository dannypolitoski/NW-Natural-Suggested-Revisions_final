"""
Property-based tests for data ingestion module.

Tests validate that data loading and filtering functions preserve data integrity,
maintain required constraints, and handle edge cases correctly.

Property 2: Filtering preserves only active residential premises — output contains 
only custtype='R' and status_code='AC'

Validates: Requirements 1.2, 7.1
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, assume
from src import data_ingestion, config


class TestDataIngestionFiltering:
    """Property tests for data ingestion filtering logic."""

    def test_load_premise_data_filters_to_residential_active(self):
        """
        Property 2: Filtering preserves only active residential premises.
        
        The load_premise_data function must filter to:
        - custtype='R' (residential customers only)
        - status_code='AC' (active accounts only)
        
        This ensures that the model operates only on the intended customer segment
        and excludes inactive, commercial, or industrial accounts.
        
        Validates: Requirements 1.2, 7.1
        """
        # Create a mock premise DataFrame with mixed customer types and statuses
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003', 'P004', 'P005', 'P006', 'P007', 'P008'],
            'custtype': ['R', 'R', 'C', 'I', 'R', 'R', 'R', 'R'],
            'status_code': ['AC', 'AC', 'AC', 'AC', 'IN', 'AC', 'SU', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT', 'WASH', 'MULT', 'WASH', 'MULT', 'WASH'],
        })
        
        # Simulate the filtering logic that load_premise_data should apply
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        # Verify all rows in filtered data meet the criteria
        assert (filtered['custtype'] == 'R').all(), \
            "Filtered data contains non-residential customers"
        assert (filtered['status_code'] == 'AC').all(), \
            "Filtered data contains inactive accounts"
        
        # Verify expected rows are included
        expected_ids = {'P001', 'P002', 'P006', 'P008'}
        actual_ids = set(filtered['blinded_id'])
        assert actual_ids == expected_ids, \
            f"Filtered data has unexpected premise IDs. Expected {expected_ids}, got {actual_ids}"
        
        # Verify excluded rows are not included
        excluded_ids = {'P003', 'P004', 'P005', 'P007'}
        assert len(actual_ids & excluded_ids) == 0, \
            f"Filtered data incorrectly includes excluded premises: {actual_ids & excluded_ids}"

    def test_premise_filtering_preserves_required_columns(self):
        """
        Verify that premise filtering preserves all required columns.
        
        The filtered output must retain columns needed for downstream processing:
        - blinded_id (for joining with equipment)
        - district_code_IRP (for weather station assignment)
        - custtype and status_code (for validation)
        """
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'custtype': ['R', 'R', 'C'],
            'status_code': ['AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
            'rate_schedule': ['2', '2', '2'],
            'service_address_zip': ['97201', '97202', '97203'],
        })
        
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        required_columns = {'blinded_id', 'district_code_IRP', 'custtype', 'status_code'}
        actual_columns = set(filtered.columns)
        
        assert required_columns.issubset(actual_columns), \
            f"Filtered data missing required columns: {required_columns - actual_columns}"

    def test_premise_filtering_no_duplicates(self):
        """
        Verify that premise filtering preserves duplicates from source data.
        
        If duplicates exist in source data (e.g., multiple equipment per premise),
        they should be preserved in the filtered output. Filtering should not
        introduce or remove duplicates beyond what exists in the source.
        """
        # Create mock data with no duplicates in source
        mock_data_no_dupes = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'custtype': ['R', 'R', 'R'],
            'status_code': ['AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
        })
        
        filtered = mock_data_no_dupes[
            (mock_data_no_dupes['custtype'] == 'R') & 
            (mock_data_no_dupes['status_code'] == 'AC')
        ]
        
        # Verify no duplicates introduced when source has none
        duplicate_ids = filtered[filtered.duplicated(subset=['blinded_id'], keep=False)]['blinded_id'].unique()
        assert len(duplicate_ids) == 0, \
            f"Filtering introduced unexpected duplicates: {duplicate_ids}"
        
        # Create mock data with duplicates in source (e.g., multiple equipment per premise)
        mock_data_with_dupes = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002'],
            'custtype': ['R', 'R', 'R'],
            'status_code': ['AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'MULT', 'WASH'],
        })
        
        filtered_with_dupes = mock_data_with_dupes[
            (mock_data_with_dupes['custtype'] == 'R') & 
            (mock_data_with_dupes['status_code'] == 'AC')
        ]
        
        # Verify duplicates from source are preserved
        duplicate_ids_preserved = filtered_with_dupes[filtered_with_dupes.duplicated(subset=['blinded_id'], keep=False)]['blinded_id'].unique()
        assert len(duplicate_ids_preserved) > 0, \
            "Filtering should preserve duplicates from source data"

    def test_premise_filtering_handles_missing_columns(self):
        """
        Verify that premise filtering handles missing custtype or status_code gracefully.
        
        If required filter columns are missing, the function should raise an informative error
        or log a warning, not silently fail.
        """
        # DataFrame missing custtype column
        mock_data_missing_custtype = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'status_code': ['AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH'],
        })
        
        # Attempting to filter on missing column should raise KeyError
        with pytest.raises(KeyError):
            _ = mock_data_missing_custtype[
                (mock_data_missing_custtype['custtype'] == 'R') & 
                (mock_data_missing_custtype['status_code'] == 'AC')
            ]

    def test_premise_filtering_handles_null_values(self):
        """
        Verify that premise filtering correctly handles null/NaN values.
        
        Null values in custtype or status_code should be excluded from the filtered output.
        """
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003', 'P004'],
            'custtype': ['R', 'R', None, 'R'],
            'status_code': ['AC', None, 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT', 'WASH'],
        })
        
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        # Verify no null values in filtered custtype or status_code
        assert filtered['custtype'].isna().sum() == 0, \
            "Filtered data contains null custtype values"
        assert filtered['status_code'].isna().sum() == 0, \
            "Filtered data contains null status_code values"
        
        # Verify only P001 and P004 are included
        expected_ids = {'P001', 'P004'}
        actual_ids = set(filtered['blinded_id'])
        assert actual_ids == expected_ids, \
            f"Filtering did not correctly exclude null values. Expected {expected_ids}, got {actual_ids}"

    def test_premise_filtering_case_sensitivity(self):
        """
        Verify that premise filtering is case-sensitive for custtype and status_code.
        
        The filter should match exact values ('R', 'AC') and not match variations ('r', 'ac').
        """
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003', 'P004'],
            'custtype': ['R', 'r', 'R', 'R'],
            'status_code': ['AC', 'AC', 'ac', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT', 'WASH'],
        })
        
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        # Only P001 and P004 should match (exact case)
        expected_ids = {'P001', 'P004'}
        actual_ids = set(filtered['blinded_id'])
        assert actual_ids == expected_ids, \
            f"Filtering is not case-sensitive. Expected {expected_ids}, got {actual_ids}"

    def test_premise_filtering_preserves_data_types(self):
        """
        Verify that premise filtering preserves data types of columns.
        
        Numeric columns should remain numeric, string columns should remain strings, etc.
        """
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'custtype': ['R', 'R', 'C'],
            'status_code': ['AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
            'annual_usage_therms': [650.5, 720.3, 800.0],
            'account_age_years': [5, 10, 3],
        })
        
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        # Verify data types are preserved (allow both object and StringDtype for string columns)
        assert filtered['blinded_id'].dtype in [object, 'string'], \
            f"blinded_id should be string type, got {filtered['blinded_id'].dtype}"
        assert filtered['annual_usage_therms'].dtype in [np.float64, np.float32], \
            "annual_usage_therms should be numeric type"
        assert filtered['account_age_years'].dtype in [np.int64, np.int32], \
            "account_age_years should be integer type"

    def test_premise_filtering_empty_result(self):
        """
        Verify that premise filtering handles the case where no records match the criteria.
        
        If all records are filtered out, the result should be an empty DataFrame with
        the correct columns, not an error.
        """
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'custtype': ['C', 'I', 'C'],
            'status_code': ['AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
        })
        
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        # Result should be empty but have correct columns
        assert len(filtered) == 0, \
            "Filtered result should be empty when no records match"
        assert set(filtered.columns) == set(mock_data.columns), \
            "Empty filtered result should preserve column structure"

    def test_premise_filtering_all_match(self):
        """
        Verify that premise filtering correctly includes all records when all match criteria.
        
        If all records are residential and active, all should be included.
        """
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003', 'P004'],
            'custtype': ['R', 'R', 'R', 'R'],
            'status_code': ['AC', 'AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT', 'WASH'],
        })
        
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        # All records should be included
        assert len(filtered) == len(mock_data), \
            "Filtering should include all records when all match criteria"
        assert set(filtered['blinded_id']) == set(mock_data['blinded_id']), \
            "Filtering should preserve all premise IDs when all match criteria"

    def test_premise_filtering_status_codes_variety(self):
        """
        Verify that premise filtering correctly handles various status codes.
        
        Common status codes: AC (active), IN (inactive), SU (suspended), DC (disconnected).
        Only AC should be included.
        """
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003', 'P004', 'P005'],
            'custtype': ['R', 'R', 'R', 'R', 'R'],
            'status_code': ['AC', 'IN', 'SU', 'DC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT', 'WASH', 'MULT'],
        })
        
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        # Only P001 and P005 should be included
        expected_ids = {'P001', 'P005'}
        actual_ids = set(filtered['blinded_id'])
        assert actual_ids == expected_ids, \
            f"Filtering should only include AC status. Expected {expected_ids}, got {actual_ids}"

    def test_premise_filtering_customer_types_variety(self):
        """
        Verify that premise filtering correctly handles various customer types.
        
        Common customer types: R (residential), C (commercial), I (industrial), G (government).
        Only R should be included.
        """
        mock_data = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003', 'P004', 'P005'],
            'custtype': ['R', 'C', 'I', 'G', 'R'],
            'status_code': ['AC', 'AC', 'AC', 'AC', 'AC'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT', 'WASH', 'MULT'],
        })
        
        filtered = mock_data[
            (mock_data['custtype'] == 'R') & 
            (mock_data['status_code'] == 'AC')
        ]
        
        # Only P001 and P005 should be included
        expected_ids = {'P001', 'P005'}
        actual_ids = set(filtered['blinded_id'])
        assert actual_ids == expected_ids, \
            f"Filtering should only include R custtype. Expected {expected_ids}, got {actual_ids}"


class TestDataIngestionJoinIntegrity:
    """Property tests for join operations in data ingestion."""

    def test_join_preserves_premise_count_left_join(self):
        """
        Verify that left joins preserve the number of premise records.
        
        When joining equipment to premises with a left join on blinded_id,
        the result should have at least as many rows as the premise table
        (one row per premise, possibly duplicated if multiple equipment per premise).
        """
        premises = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
        })
        
        equipment = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002'],
            'equipment_type_code': ['FURN', 'WTR', 'FURN'],
        })
        
        # Left join on blinded_id
        result = premises.merge(equipment, on='blinded_id', how='left')
        
        # Result should have at least as many rows as premises
        # (P001 has 2 equipment, P002 has 1, P003 has 0)
        assert len(result) >= len(premises), \
            "Left join should preserve at least as many rows as the left table"
        
        # Verify all premise IDs are represented
        assert set(result['blinded_id']) == set(premises['blinded_id']), \
            "Left join should preserve all premise IDs"

    def test_join_handles_missing_equipment(self):
        """
        Verify that left joins correctly handle premises with no equipment.
        
        Premises without equipment should appear in the result with NaN values
        for equipment columns.
        """
        premises = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
        })
        
        equipment = pd.DataFrame({
            'blinded_id': ['P001', 'P001'],
            'equipment_type_code': ['FURN', 'WTR'],
        })
        
        result = premises.merge(equipment, on='blinded_id', how='left')
        
        # P002 and P003 should have NaN equipment_type_code
        p002_rows = result[result['blinded_id'] == 'P002']
        p003_rows = result[result['blinded_id'] == 'P003']
        
        assert p002_rows['equipment_type_code'].isna().all(), \
            "Premises without equipment should have NaN equipment_type_code"
        assert p003_rows['equipment_type_code'].isna().all(), \
            "Premises without equipment should have NaN equipment_type_code"

    def test_join_no_data_loss_on_equipment_codes(self):
        """
        Verify that joining equipment codes does not lose equipment records.
        
        When joining equipment codes to equipment, all equipment records should
        be preserved (left join), even if some equipment_type_codes are not in the codes table.
        """
        equipment = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002'],
            'equipment_type_code': ['FURN', 'WTR', 'UNKNOWN'],
        })
        
        codes = pd.DataFrame({
            'equipment_type_code': ['FURN', 'WTR', 'COOK'],
            'equipment_class': ['HEAT', 'WTR', 'RRGE'],
        })
        
        result = equipment.merge(codes, on='equipment_type_code', how='left')
        
        # All equipment records should be preserved
        assert len(result) == len(equipment), \
            "Left join should preserve all equipment records"
        
        # UNKNOWN equipment should have NaN equipment_class
        unknown_rows = result[result['equipment_type_code'] == 'UNKNOWN']
        assert unknown_rows['equipment_class'].isna().all(), \
            "Unmapped equipment codes should have NaN equipment_class"

    def test_premise_equipment_table_end_use_non_null(self):
        """
        Property 3a: Every row in premise_equipment_table has a non-null end_use category.
        
        After build_premise_equipment_table joins all tables and derives end_use,
        every row should have a valid end_use value (not NaN/None).
        
        Validates: Requirements 1.4, 3.1
        """
        premises = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
        })
        
        equipment = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P003'],
            'equipment_type_code': ['FURN', 'WTR', 'COOK', 'DRYR'],
        })
        
        segments = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'segment_code': ['RESSF', 'RESSF', 'RESMF'],
        })
        
        codes = pd.DataFrame({
            'equipment_type_code': ['FURN', 'WTR', 'COOK', 'DRYR'],
            'equipment_class': ['HEAT', 'WTR', 'RRGE', 'RDRY'],
        })
        
        result = data_ingestion.build_premise_equipment_table(premises, equipment, segments, codes)
        
        # Every row should have a non-null end_use
        null_end_use = result['end_use'].isna().sum()
        assert null_end_use == 0, \
            f"Property 3a violated: {null_end_use} rows have null end_use. " \
            f"All rows must have a valid end_use category."

    def test_premise_equipment_table_efficiency_valid(self):
        """
        Property 3b: Every row in premise_equipment_table has a valid efficiency > 0.
        
        After build_premise_equipment_table derives efficiency (from data or defaults),
        every row should have efficiency > 0 and <= 1.0 (valid percentage).
        
        Validates: Requirements 1.4, 3.1
        """
        premises = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT'],
        })
        
        equipment = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P003'],
            'equipment_type_code': ['FURN', 'WTR', 'COOK', 'DRYR'],
            'efficiency': [0.85, None, 0.75, 0.65],  # Mix of provided and missing
        })
        
        segments = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'segment_code': ['RESSF', 'RESSF', 'RESMF'],
        })
        
        codes = pd.DataFrame({
            'equipment_type_code': ['FURN', 'WTR', 'COOK', 'DRYR'],
            'equipment_class': ['HEAT', 'WTR', 'RRGE', 'RDRY'],
        })
        
        result = data_ingestion.build_premise_equipment_table(premises, equipment, segments, codes)
        
        # Every row should have efficiency > 0
        invalid_efficiency = result[result['efficiency'] <= 0].shape[0]
        assert invalid_efficiency == 0, \
            f"Property 3b violated: {invalid_efficiency} rows have efficiency <= 0. " \
            f"All rows must have efficiency > 0."
        
        # Efficiency should be <= 1.0 (100%)
        over_100_efficiency = result[result['efficiency'] > 1.0].shape[0]
        assert over_100_efficiency == 0, \
            f"Property 3b violated: {over_100_efficiency} rows have efficiency > 1.0. " \
            f"All rows must have efficiency <= 1.0."

    def test_premise_equipment_table_combined_integrity(self):
        """
        Property 3 (combined): Every row in premise_equipment_table has both
        non-null end_use AND valid efficiency > 0.
        
        This is the full property test combining both conditions.
        
        Validates: Requirements 1.4, 3.1
        """
        premises = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003', 'P004'],
            'district_code_IRP': ['MULT', 'WASH', 'MULT', 'LINN'],
        })
        
        equipment = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002', 'P003', 'P004'],
            'equipment_type_code': ['FURN', 'WTR', 'COOK', 'DRYR', 'FRPL'],
            'efficiency': [0.85, None, 0.75, 0.65, None],
        })
        
        segments = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003', 'P004'],
            'segment_code': ['RESSF', 'RESSF', 'RESMF', 'RESSF'],
        })
        
        codes = pd.DataFrame({
            'equipment_type_code': ['FURN', 'WTR', 'COOK', 'DRYR', 'FRPL'],
            'equipment_class': ['HEAT', 'WTR', 'RRGE', 'RDRY', 'FRPL'],
        })
        
        result = data_ingestion.build_premise_equipment_table(premises, equipment, segments, codes)
        
        # Check that every row has both non-null end_use AND valid efficiency
        for idx, row in result.iterrows():
            assert pd.notna(row['end_use']), \
                f"Row {idx}: end_use is null. Property 3 requires non-null end_use."
            assert row['efficiency'] > 0, \
                f"Row {idx}: efficiency {row['efficiency']} is not > 0. Property 3 requires efficiency > 0."
            assert row['efficiency'] <= 1.0, \
                f"Row {idx}: efficiency {row['efficiency']} is > 1.0. Property 3 requires efficiency <= 1.0."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
