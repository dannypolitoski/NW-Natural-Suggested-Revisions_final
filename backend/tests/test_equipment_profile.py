"""
Unit and property-based tests for equipment module.

Tests validate:
- EquipmentProfile dataclass creation and attributes
- Weibull survival function properties and edge cases
- Median-to-eta conversion accuracy
- Replacement probability computation
- Equipment inventory building from premise data
"""

import pytest
import math
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, assume
from src import equipment, config


class TestEquipmentProfile:
    """Tests for EquipmentProfile dataclass."""

    def test_equipment_profile_creation(self):
        """Test basic EquipmentProfile instantiation."""
        profile = equipment.EquipmentProfile(
            equipment_type_code="RFAU",
            end_use="space_heating",
            efficiency=0.85,
            install_year=2010,
            useful_life=20,
            fuel_type="natural_gas"
        )
        
        assert profile.equipment_type_code == "RFAU"
        assert profile.end_use == "space_heating"
        assert profile.efficiency == 0.85
        assert profile.install_year == 2010
        assert profile.useful_life == 20
        assert profile.fuel_type == "natural_gas"

    def test_equipment_profile_all_fields_required(self):
        """Test that all EquipmentProfile fields are required."""
        with pytest.raises(TypeError):
            equipment.EquipmentProfile(
                equipment_type_code="RFAU",
                end_use="space_heating",
                efficiency=0.85,
                install_year=2010,
                useful_life=20
                # Missing fuel_type
            )


class TestWeibullSurvival:
    """Tests for Weibull survival function."""

    def test_survival_at_zero_age(self):
        """
        Property: S(0) = 1.0 for all valid eta and beta.
        
        New equipment always survives (has not failed).
        """
        assert equipment.weibull_survival(0, 20, 3.0) == 1.0
        assert equipment.weibull_survival(0, 15, 2.5) == 1.0
        assert equipment.weibull_survival(0, 100, 1.5) == 1.0

    def test_survival_at_characteristic_life(self):
        """
        Property: S(eta) = exp(-1) ≈ 0.3679 for all beta.
        
        At the characteristic life (scale parameter), survival is always e^-1.
        """
        eta = 20
        beta = 3.0
        s_eta = equipment.weibull_survival(eta, eta, beta)
        expected = math.exp(-1)
        assert abs(s_eta - expected) < 1e-10

    def test_survival_monotonically_decreasing(self):
        """
        Property 5: Weibull survival function is monotonically decreasing.
        
        S(t) <= S(t-1) for all t > 0.
        
        Validates: Requirements 3.3
        """
        eta = 20
        beta = 3.0
        
        for t in range(1, 100):
            s_t = equipment.weibull_survival(t, eta, beta)
            s_t_minus_1 = equipment.weibull_survival(t - 1, eta, beta)
            assert s_t <= s_t_minus_1, \
                f"Survival not monotonic: S({t}) = {s_t} > S({t-1}) = {s_t_minus_1}"

    def test_survival_approaches_zero(self):
        """
        Property: S(t) approaches 0 as t → ∞.
        
        Very old equipment has very low survival probability.
        """
        eta = 20
        beta = 3.0
        
        s_100 = equipment.weibull_survival(100, eta, beta)
        assert s_100 < 0.01, f"S(100) = {s_100} should be very small"
        
        s_200 = equipment.weibull_survival(200, eta, beta)
        assert s_200 < s_100, "Survival should continue decreasing"

    def test_survival_negative_age_returns_one(self):
        """Test that negative age returns survival = 1.0 (no failure before age 0)."""
        assert equipment.weibull_survival(-5, 20, 3.0) == 1.0
        assert equipment.weibull_survival(-100, 20, 3.0) == 1.0

    def test_survival_invalid_eta_raises_error(self):
        """Test that eta <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            equipment.weibull_survival(10, 0, 3.0)
        
        with pytest.raises(ValueError):
            equipment.weibull_survival(10, -5, 3.0)

    def test_survival_invalid_beta_raises_error(self):
        """Test that beta <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            equipment.weibull_survival(10, 20, 0)
        
        with pytest.raises(ValueError):
            equipment.weibull_survival(10, 20, -2.0)

    @given(
        t=st.floats(min_value=0, max_value=200),
        eta=st.floats(min_value=0.1, max_value=100),
        beta=st.floats(min_value=0.1, max_value=10)
    )
    def test_survival_in_valid_range(self, t, eta, beta):
        """
        Property: S(t) is always in [0, 1] for valid inputs.
        
        Validates: Requirements 3.3
        """
        s = equipment.weibull_survival(t, eta, beta)
        assert 0 <= s <= 1, f"S({t}, {eta}, {beta}) = {s} outside [0, 1]"

    @given(
        eta=st.floats(min_value=0.1, max_value=100),
        beta=st.floats(min_value=0.1, max_value=10)
    )
    def test_survival_decreases_with_age(self, eta, beta):
        """
        Property: For fixed eta and beta, S(t) decreases as t increases.
        """
        ages = [0, 10, 20, 30, 40, 50]
        survivals = [equipment.weibull_survival(t, eta, beta) for t in ages]
        
        for i in range(len(survivals) - 1):
            assert survivals[i] >= survivals[i + 1], \
                f"Survival not decreasing: S({ages[i]}) = {survivals[i]} < S({ages[i+1]}) = {survivals[i+1]}"


class TestMedianToEta:
    """Tests for median-to-eta conversion."""

    def test_median_to_eta_basic(self):
        """Test basic median-to-eta conversion."""
        median_life = 20
        beta = 3.0
        eta = equipment.median_to_eta(median_life, beta)
        
        # Verify that S(median) ≈ 0.5
        s_median = equipment.weibull_survival(median_life, eta, beta)
        assert abs(s_median - 0.5) < 1e-10, \
            f"S(median) = {s_median}, expected 0.5"

    def test_median_to_eta_different_betas(self):
        """Test median-to-eta for different beta values."""
        median_life = 20
        
        for beta in [1.5, 2.0, 2.5, 3.0, 4.0]:
            eta = equipment.median_to_eta(median_life, beta)
            s_median = equipment.weibull_survival(median_life, eta, beta)
            assert abs(s_median - 0.5) < 1e-10, \
                f"For beta={beta}: S(median) = {s_median}, expected 0.5"

    def test_median_to_eta_eta_decreases_with_beta(self):
        """
        Property: For fixed median_life, eta decreases as beta increases.
        
        Higher beta means sharper failure peak, so eta must be smaller to maintain
        the same median. This is because eta = median / (ln(2))^(1/beta), and
        (ln(2))^(1/beta) increases with beta.
        """
        median_life = 20
        betas = [1.0, 2.0, 3.0, 4.0, 5.0]
        etas = [equipment.median_to_eta(median_life, b) for b in betas]
        
        for i in range(len(etas) - 1):
            assert etas[i] >= etas[i + 1], \
                f"eta not decreasing with beta: eta({betas[i]}) = {etas[i]} < eta({betas[i+1]}) = {etas[i+1]}"

    def test_median_to_eta_invalid_median_raises_error(self):
        """Test that median_life <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            equipment.median_to_eta(0, 3.0)
        
        with pytest.raises(ValueError):
            equipment.median_to_eta(-10, 3.0)

    def test_median_to_eta_invalid_beta_raises_error(self):
        """Test that beta <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            equipment.median_to_eta(20, 0)
        
        with pytest.raises(ValueError):
            equipment.median_to_eta(20, -2.0)

    @given(
        median_life=st.floats(min_value=1, max_value=100),
        beta=st.floats(min_value=0.1, max_value=10)
    )
    def test_median_to_eta_produces_valid_eta(self, median_life, beta):
        """
        Property: median_to_eta always produces eta > 0.
        """
        eta = equipment.median_to_eta(median_life, beta)
        assert eta > 0, f"eta = {eta} should be positive"


class TestReplacementProbability:
    """Tests for replacement probability computation."""

    def test_replacement_probability_at_zero_age(self):
        """
        Property 5b: Replacement probability at age 0 is 0.
        
        New equipment doesn't need replacement.
        """
        assert equipment.replacement_probability(0, 20, 3.0) == 0.0
        assert equipment.replacement_probability(0, 15, 2.5) == 0.0

    def test_replacement_probability_negative_age(self):
        """Test that negative age returns 0 (no replacement before age 0)."""
        assert equipment.replacement_probability(-5, 20, 3.0) == 0.0

    def test_replacement_probability_in_valid_range(self):
        """
        Property 5b: Replacement probability is always in [0, 1].
        
        Validates: Requirements 3.3
        """
        eta = 20
        beta = 3.0
        
        for age in range(0, 100):
            prob = equipment.replacement_probability(age, eta, beta)
            assert 0 <= prob <= 1, \
                f"Replacement probability at age {age}: {prob} outside [0, 1]"

    def test_replacement_probability_increases_with_age(self):
        """
        Property: Replacement probability increases with equipment age.
        
        Older equipment is more likely to fail.
        """
        eta = 20
        beta = 3.0
        
        probs = [equipment.replacement_probability(t, eta, beta) for t in range(0, 50)]
        
        for i in range(len(probs) - 1):
            assert probs[i] <= probs[i + 1], \
                f"Replacement probability not increasing: P({i}) = {probs[i]} > P({i+1}) = {probs[i+1]}"

    def test_replacement_probability_approaches_one(self):
        """
        Property: Replacement probability approaches 1 as age → ∞.
        
        Very old equipment is almost certain to fail. At age 100 with eta=20, beta=3.0,
        the probability should be very high (>0.97).
        """
        eta = 20
        beta = 3.0
        
        prob_100 = equipment.replacement_probability(100, eta, beta)
        assert prob_100 > 0.97, f"P(100) = {prob_100} should be very high"

    def test_replacement_probability_invalid_eta_raises_error(self):
        """Test that eta <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            equipment.replacement_probability(10, 0, 3.0)
        
        with pytest.raises(ValueError):
            equipment.replacement_probability(10, -5, 3.0)

    def test_replacement_probability_invalid_beta_raises_error(self):
        """Test that beta <= 0 raises ValueError."""
        with pytest.raises(ValueError):
            equipment.replacement_probability(10, 20, 0)
        
        with pytest.raises(ValueError):
            equipment.replacement_probability(10, 20, -2.0)

    @given(
        age=st.floats(min_value=0, max_value=200),
        eta=st.floats(min_value=0.1, max_value=100),
        beta=st.floats(min_value=0.1, max_value=10)
    )
    def test_replacement_probability_in_range(self, age, eta, beta):
        """
        Property 5b: Replacement probability is always in [0, 1] for valid inputs.
        
        Validates: Requirements 3.3
        """
        prob = equipment.replacement_probability(age, eta, beta)
        assert 0 <= prob <= 1, f"P({age}, {eta}, {beta}) = {prob} outside [0, 1]"


class TestBuildEquipmentInventory:
    """Tests for equipment inventory builder."""

    def test_build_equipment_inventory_basic(self):
        """Test basic equipment inventory building."""
        df = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P002'],
            'equipment_type_code': ['RFAU', 'RAWH', 'RRGE'],
            'end_use': ['space_heating', 'water_heating', 'cooking'],
            'efficiency': [0.85, 0.65, 0.75],
            'install_year': [2010, 2015, 2012],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'state': ['OR', 'OR', 'OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        assert len(result) == 3
        assert 'eta' in result.columns
        assert 'beta' in result.columns
        assert (result['eta'] > 0).all()
        assert (result['beta'] > 0).all()

    def test_build_equipment_inventory_fills_missing_efficiency(self):
        """Test that missing efficiency is filled with defaults."""
        df = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'equipment_type_code': ['RFAU', 'RAWH'],
            'end_use': ['space_heating', 'water_heating'],
            'efficiency': [0.85, np.nan],
            'install_year': [2010, 2015],
            'fuel_type': ['natural_gas', 'natural_gas'],
            'state': ['OR', 'OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        assert result.loc[0, 'efficiency'] == 0.85
        assert result.loc[1, 'efficiency'] == config.DEFAULT_EFFICIENCY['water_heating']
        assert (result['efficiency'] > 0).all()

    def test_build_equipment_inventory_fills_missing_install_year(self):
        """Test that missing install_year is filled with reasonable defaults."""
        df = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'equipment_type_code': ['RFAU', 'RAWH'],
            'end_use': ['space_heating', 'water_heating'],
            'efficiency': [0.85, 0.65],
            'install_year': [2010, np.nan],
            'fuel_type': ['natural_gas', 'natural_gas'],
            'state': ['OR', 'OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        assert result.loc[0, 'install_year'] == 2010
        # Missing install_year should be filled with BASE_YEAR - (useful_life // 2)
        assert result.loc[1, 'install_year'] < config.BASE_YEAR

    def test_build_equipment_inventory_fills_missing_fuel_type(self):
        """Test that missing fuel_type is filled with 'natural_gas'."""
        df = pd.DataFrame({
            'blinded_id': ['P001', 'P002'],
            'equipment_type_code': ['RFAU', 'RAWH'],
            'end_use': ['space_heating', 'water_heating'],
            'efficiency': [0.85, 0.65],
            'install_year': [2010, 2015],
            'fuel_type': ['natural_gas', np.nan],
            'state': ['OR', 'OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        assert result.loc[0, 'fuel_type'] == 'natural_gas'
        assert result.loc[1, 'fuel_type'] == 'natural_gas'

    def test_build_equipment_inventory_computes_eta_and_beta(self):
        """Test that eta and beta are computed correctly."""
        df = pd.DataFrame({
            'blinded_id': ['P001'],
            'equipment_type_code': ['RFAU'],
            'end_use': ['space_heating'],
            'efficiency': [0.85],
            'install_year': [2010],
            'fuel_type': ['natural_gas'],
            'state': ['OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        # Verify eta and beta are computed
        assert result.loc[0, 'beta'] == equipment.WEIBULL_BETA['space_heating']
        
        # Verify eta is derived from useful_life
        useful_life = config.USEFUL_LIFE['space_heating']
        beta = equipment.WEIBULL_BETA['space_heating']
        expected_eta = equipment.median_to_eta(useful_life, beta)
        assert abs(result.loc[0, 'eta'] - expected_eta) < 1e-10

    def test_build_equipment_inventory_preserves_input_columns(self):
        """Test that all input columns are preserved in output."""
        df = pd.DataFrame({
            'blinded_id': ['P001'],
            'equipment_type_code': ['RFAU'],
            'end_use': ['space_heating'],
            'efficiency': [0.85],
            'install_year': [2010],
            'fuel_type': ['natural_gas'],
            'state': ['OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        for col in df.columns:
            assert col in result.columns

    def test_build_equipment_inventory_multiple_end_uses(self):
        """Test inventory building with multiple end-use categories."""
        df = pd.DataFrame({
            'blinded_id': ['P001', 'P001', 'P001', 'P001'],
            'equipment_type_code': ['RFAU', 'RAWH', 'RRGE', 'RDRY'],
            'end_use': ['space_heating', 'water_heating', 'cooking', 'clothes_drying'],
            'efficiency': [0.85, 0.65, 0.75, 0.70],
            'install_year': [2010, 2015, 2012, 2014],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas', 'natural_gas'],
            'state': ['OR', 'OR', 'OR', 'OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        assert len(result) == 4
        
        # Verify different beta values for different end-uses
        assert result.loc[0, 'beta'] == equipment.WEIBULL_BETA['space_heating']
        assert result.loc[1, 'beta'] == equipment.WEIBULL_BETA['water_heating']
        assert result.loc[2, 'beta'] == equipment.WEIBULL_BETA['cooking']
        assert result.loc[3, 'beta'] == equipment.WEIBULL_BETA['clothes_drying']

    def test_build_equipment_inventory_efficiency_bounds(self):
        """Test that all efficiencies are within valid bounds."""
        df = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'equipment_type_code': ['RFAU', 'RAWH', 'RRGE'],
            'end_use': ['space_heating', 'water_heating', 'cooking'],
            'efficiency': [np.nan, np.nan, np.nan],
            'install_year': [2010, 2015, 2012],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'state': ['OR', 'OR', 'OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        assert (result['efficiency'] > 0).all()
        assert (result['efficiency'] <= 1.0).all()

    def test_build_equipment_inventory_eta_positive(self):
        """Test that all eta values are positive."""
        df = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'equipment_type_code': ['RFAU', 'RAWH', 'RRGE'],
            'end_use': ['space_heating', 'water_heating', 'cooking'],
            'efficiency': [0.85, 0.65, 0.75],
            'install_year': [2010, 2015, 2012],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'state': ['OR', 'OR', 'OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        assert (result['eta'] > 0).all()

    def test_build_equipment_inventory_beta_positive(self):
        """Test that all beta values are positive."""
        df = pd.DataFrame({
            'blinded_id': ['P001', 'P002', 'P003'],
            'equipment_type_code': ['RFAU', 'RAWH', 'RRGE'],
            'end_use': ['space_heating', 'water_heating', 'cooking'],
            'efficiency': [0.85, 0.65, 0.75],
            'install_year': [2010, 2015, 2012],
            'fuel_type': ['natural_gas', 'natural_gas', 'natural_gas'],
            'state': ['OR', 'OR', 'OR']
        })
        
        result = equipment.build_equipment_inventory(df)
        
        assert (result['beta'] > 0).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
