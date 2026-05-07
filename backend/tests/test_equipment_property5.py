"""
Property-based tests for Weibull survival monotonicity (Property 5 and 5b).

**Validates: Requirements 3.3**

Tests:
- Property 5: S(t) <= S(t-1) for all t > 0, and S(0) = 1.0
- Property 5b: replacement_probability is always in [0, 1]
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import numpy as np
from src.equipment import weibull_survival, replacement_probability, median_to_eta
from src import config


class TestProperty5WeibullMonotonicity:
    """Test Property 5: Weibull survival monotonicity."""
    
    @given(
        end_use=st.sampled_from(list(config.WEIBULL_BETA.keys())),
        t=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_survival_monotonicity(self, end_use: str, t: int):
        """
        **Validates: Requirements 3.3**
        
        Property: S(t) <= S(t-1) for all t > 0
        
        The survival function must be monotonically decreasing because
        equipment cannot "un-fail".
        """
        beta = config.WEIBULL_BETA[end_use]
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        s_t = weibull_survival(t, eta, beta)
        s_t_minus_1 = weibull_survival(t - 1, eta, beta)
        
        # Allow small numerical error (1e-10)
        assert s_t <= s_t_minus_1 + 1e-10, \
            f"Monotonicity violation for {end_use}: S({t}) = {s_t} > S({t-1}) = {s_t_minus_1}"
    
    @given(
        end_use=st.sampled_from(list(config.WEIBULL_BETA.keys()))
    )
    @settings(max_examples=100)
    def test_survival_at_zero(self, end_use: str):
        """
        **Validates: Requirements 3.3**
        
        Property: S(0) = 1.0 for all end-uses
        
        New equipment always survives, so survival at age 0 must be 1.0.
        """
        beta = config.WEIBULL_BETA[end_use]
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        s_0 = weibull_survival(0, eta, beta)
        
        assert abs(s_0 - 1.0) < 1e-10, \
            f"S(0) != 1.0 for {end_use}: S(0) = {s_0}"
    
    @given(
        end_use=st.sampled_from(list(config.WEIBULL_BETA.keys())),
        t=st.floats(min_value=0, max_value=100)
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_survival_in_valid_range(self, end_use: str, t: float):
        """
        **Validates: Requirements 3.3**
        
        Property: 0 <= S(t) <= 1 for all t >= 0
        
        Survival probability must be a valid probability.
        """
        beta = config.WEIBULL_BETA[end_use]
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        s_t = weibull_survival(t, eta, beta)
        
        assert 0 <= s_t <= 1, \
            f"Survival out of range for {end_use} at t={t}: S(t) = {s_t}"


class TestProperty5bReplacementProbability:
    """Test Property 5b: Replacement probability bounds."""
    
    @given(
        end_use=st.sampled_from(list(config.WEIBULL_BETA.keys())),
        age=st.floats(min_value=0, max_value=100)
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_replacement_probability_bounds(self, end_use: str, age: float):
        """
        **Validates: Requirements 3.3**
        
        Property: 0 <= replacement_probability(age) <= 1 for all age >= 0
        
        Replacement probability must be a valid probability.
        """
        beta = config.WEIBULL_BETA[end_use]
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        prob = replacement_probability(age, eta, beta)
        
        assert 0 <= prob <= 1, \
            f"Replacement probability out of bounds for {end_use} at age={age}: P = {prob}"
    
    @given(
        end_use=st.sampled_from(list(config.WEIBULL_BETA.keys()))
    )
    @settings(max_examples=100)
    def test_replacement_probability_at_zero(self, end_use: str):
        """
        **Validates: Requirements 3.3**
        
        Property: replacement_probability(0) = 0 for all end-uses
        
        New equipment should not need replacement.
        """
        beta = config.WEIBULL_BETA[end_use]
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        prob = replacement_probability(0, eta, beta)
        
        assert prob == 0, \
            f"Replacement probability at age 0 should be 0 for {end_use}: P(0) = {prob}"
    
    @given(
        end_use=st.sampled_from(list(config.WEIBULL_BETA.keys())),
        age1=st.floats(min_value=0, max_value=50),
        age2=st.floats(min_value=50, max_value=100)
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_replacement_probability_increases_with_age(self, end_use: str, age1: float, age2: float):
        """
        **Validates: Requirements 3.3**
        
        Property: replacement_probability(age) is generally increasing with age
        
        Older equipment is more likely to need replacement.
        """
        beta = config.WEIBULL_BETA[end_use]
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        prob1 = replacement_probability(age1, eta, beta)
        prob2 = replacement_probability(age2, eta, beta)
        
        # Allow for numerical precision issues
        assert prob2 >= prob1 - 1e-10, \
            f"Replacement probability should increase with age for {end_use}: " \
            f"P({age1}) = {prob1} > P({age2}) = {prob2}"


class TestWeibullParameterValidation:
    """Test Weibull parameter validation."""
    
    def test_all_end_uses_have_beta(self):
        """All end-uses in USEFUL_LIFE should have corresponding beta values."""
        for end_use in config.USEFUL_LIFE.keys():
            assert end_use in config.WEIBULL_BETA, \
                f"End-use {end_use} missing from WEIBULL_BETA"
    
    def test_all_end_uses_have_useful_life(self):
        """All end-uses in WEIBULL_BETA should have corresponding useful life values."""
        for end_use in config.WEIBULL_BETA.keys():
            assert end_use in config.USEFUL_LIFE, \
                f"End-use {end_use} missing from USEFUL_LIFE"
    
    @given(
        end_use=st.sampled_from(list(config.WEIBULL_BETA.keys()))
    )
    @settings(max_examples=100)
    def test_eta_computed_correctly(self, end_use: str):
        """
        Test that eta is computed correctly from median_to_eta.
        
        At median life, survival should be approximately 0.5.
        """
        beta = config.WEIBULL_BETA[end_use]
        useful_life = config.USEFUL_LIFE.get(end_use, 15)
        eta = median_to_eta(useful_life, beta)
        
        # At median life, S(t) should be 0.5
        s_median = weibull_survival(useful_life, eta, beta)
        
        assert abs(s_median - 0.5) < 0.01, \
            f"Survival at median life should be ~0.5 for {end_use}: S({useful_life}) = {s_median}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
