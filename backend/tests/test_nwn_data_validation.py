"""
Tests for NW Natural source data validation suite (Task 15).

Runs the validation suite and verifies outputs are generated.
"""

import os
import pytest

OUT_DIR = os.path.join("output", "nwn_data_validation")


def _data_available():
    """Check if NW Natural data files are available."""
    from src import config
    return os.path.exists(config.PREMISE_DATA)


# Skip all tests if data files are not available
pytestmark = pytest.mark.skipif(
    not _data_available(),
    reason="NW Natural data files not available"
)


class TestReferentialIntegrity:
    """15.1 Premise referential integrity."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_referential_integrity
        result = validate_referential_integrity()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "referential_integrity.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "referential_integrity.md"))

    def test_orphan_counts_are_dict(self):
        from src.validation.nwn_data_validation import validate_referential_integrity
        result = validate_referential_integrity()
        assert "orphan_counts" in result
        assert isinstance(result["orphan_counts"], dict)


class TestEquipmentCodeValidity:
    """15.2 Equipment code validity."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_equipment_codes
        result = validate_equipment_codes()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "equipment_code_validity.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "equipment_code_validity.md"))

    def test_valid_and_unknown_counts(self):
        from src.validation.nwn_data_validation import validate_equipment_codes
        result = validate_equipment_codes()
        assert result["valid"] >= 0
        assert result["unknown"] >= 0


class TestDuplicateDetection:
    """15.3 Duplicate premise-equipment detection."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_duplicate_equipment
        result = validate_duplicate_equipment()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "duplicate_detection.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "duplicate_detection.md"))


class TestWeatherStationCoverage:
    """15.4 Weather station coverage."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_weather_station_coverage
        result = validate_weather_station_coverage()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "weather_station_coverage.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "weather_station_coverage.md"))


class TestBillingCoverage:
    """15.5 Billing coverage analysis."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_billing_coverage
        result = validate_billing_coverage()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "billing_coverage.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "billing_coverage.md"))

    def test_coverage_percentage(self):
        from src.validation.nwn_data_validation import validate_billing_coverage
        result = validate_billing_coverage()
        assert 0 <= result["coverage_pct"] <= 100


class TestWeatherContinuity:
    """15.6 Weather date continuity."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_weather_continuity
        result = validate_weather_continuity()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "weather_continuity.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "weather_continuity.md"))


class TestSegmentConsistency:
    """15.7 Segment consistency."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_segment_consistency
        result = validate_segment_consistency()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "segment_consistency.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "segment_consistency.md"))


class TestEquipmentQuantity:
    """15.8 Equipment quantity sanity."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_equipment_quantity
        result = validate_equipment_quantity()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "equipment_quantity.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "equipment_quantity.md"))


class TestStateDistrictCrossCheck:
    """15.9 State-district cross-check."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_state_district
        result = validate_state_district()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "state_district_crosscheck.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "state_district_crosscheck.md"))


class TestBillingReasonableness:
    """15.10 Billing amount reasonableness."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_billing_reasonableness
        result = validate_billing_reasonableness()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "billing_reasonableness.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "billing_reasonableness.md"))


class TestTemperatureBounds:
    """15.11 Weather temperature bounds."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_temperature_bounds
        result = validate_temperature_bounds()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "temperature_bounds.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "temperature_bounds.md"))


class TestTemporalAlignment:
    """15.12 Temporal alignment audit."""

    def test_runs_and_produces_output(self):
        from src.validation.nwn_data_validation import validate_temporal_alignment
        result = validate_temporal_alignment()
        assert result["status"] == "OK"
        assert os.path.exists(os.path.join(OUT_DIR, "temporal_alignment.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "temporal_alignment.md"))


class TestDashboard:
    """Test the full validation suite and dashboard generation."""

    def test_run_all_validations(self):
        from src.validation.nwn_data_validation import run_all_validations
        results = run_all_validations()
        assert isinstance(results, dict)
        assert len(results) == 12
        assert os.path.exists(os.path.join(OUT_DIR, "validation_dashboard.html"))
        assert os.path.exists(os.path.join(OUT_DIR, "validation_dashboard.md"))

    def test_all_checks_produce_status(self):
        from src.validation.nwn_data_validation import run_all_validations
        results = run_all_validations()
        for label, r in results.items():
            assert "status" in r, f"Missing status for {label}"
