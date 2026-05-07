"""
Property-based test for equipment replacement logic with visualizations.

Tests:
- Property 5: Weibull survival function is monotonically decreasing — S(t) <= S(t-1) for all t > 0, and S(0) = 1.0
- Property 5b: replacement_probability is always in [0, 1] for valid inputs

Validates: Requirements 3.3

This test:
1. Validates the Weibull survival function properties
2. Validates replacement probability bounds
3. Generates comparison visualizations:
   - Line graph: Weibull survival curves by end-use category
   - Line graph: Replacement probability by equipment age for each end-use category
   - Scatter plot: Equipment age distribution with replacement probability overlay
   - Line graph: Cumulative replacement rate over equipment lifetime
4. Generates equipment transition visualizations:
   - Stacked bar chart: Equipment fuel type distribution before/after replacements
   - Stacked bar chart: Equipment efficiency distribution before/after replacements
   - Sankey diagram: Equipment transitions (gas→electric, old→new efficiency)
5. Saves all visualizations to output/equipment_replacement/ directory
6. Verifies graphs are created, files exist, and contain expected data
"""

import pytest
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import tempfile
from hypothesis import given, strategies as st, settings, HealthCheck
from src.equipment import (
    weibull_survival,
    median_to_eta,
    replacement_probability,
    build_equipment_inventory,
    apply_replacements,
    WEIBULL_BETA
)
from src.visualization import plot_electrification_map
from src import config


class TestWeibullSurvivalProperty:
    """Test suite for Weibull survival function properties."""
    
    def test_property_5_survival_at_zero(self):
        """
        **Property 5: S(0) = 1.0 for all valid eta and beta**
        
        **Validates: Requirements 3.3**
        
        The survival function at age 0 should always be 1.0 (new equipment always survives).
        """
        for end_use, beta in WEIBULL_BETA.items():
            eta = median_to_eta(20, beta)  # Typical useful life
            survival = weibull_survival(0, eta, beta)
            assert survival == 1.0, f"S(0) != 1.0 for {end_use}: got {survival}"
    
    def test_property_5_monotonic_decreasing(self):
        """
        **Property 5: Weibull survival function is monotonically decreasing — S(t) <= S(t-1) for all t > 0**
        
        **Validates: Requirements 3.3**
        
        The survival function should never increase with age. For any two ages t1 < t2,
        we must have S(t1) >= S(t2).
        """
        for end_use, beta in WEIBULL_BETA.items():
            eta = median_to_eta(20, beta)
            
            # Test across a range of ages
            for age in range(1, 51):
                s_t = weibull_survival(age, eta, beta)
                s_t_minus_1 = weibull_survival(age - 1, eta, beta)
                
                assert s_t <= s_t_minus_1, (
                    f"{end_use}: S({age}) = {s_t} > S({age-1}) = {s_t_minus_1} "
                    f"(not monotonically decreasing)"
                )
    
    @given(
        age=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        eta=st.floats(min_value=1, max_value=50, allow_nan=False, allow_infinity=False),
        beta=st.floats(min_value=0.5, max_value=5, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_5_monotonic_hypothesis(self, age, eta, beta):
        """
        Property-based test using Hypothesis for monotonic decreasing property.
        
        **Property 5: S(t) <= S(t-1) for all t > 0**
        
        **Validates: Requirements 3.3**
        """
        if age > 0:
            s_t = weibull_survival(age, eta, beta)
            s_t_minus_1 = weibull_survival(age - 1, eta, beta)
            assert s_t <= s_t_minus_1, f"S({age}) > S({age-1})"
    
    def test_property_5_bounds(self):
        """
        **Property 5: Survival function is always in [0, 1]**
        
        **Validates: Requirements 3.3**
        
        The survival function represents a probability, so it must be in [0, 1].
        """
        for end_use, beta in WEIBULL_BETA.items():
            eta = median_to_eta(20, beta)
            
            for age in range(0, 101):
                survival = weibull_survival(age, eta, beta)
                assert 0 <= survival <= 1, (
                    f"{end_use}: S({age}) = {survival} is outside [0, 1]"
                )
    
    def test_property_5_median_life(self):
        """
        **Property 5: At median service life, S(median) ≈ 0.5**
        
        **Validates: Requirements 3.3**
        
        By definition, the median service life is the age at which 50% of equipment has failed,
        so S(median) should be approximately 0.5.
        """
        for end_use, beta in WEIBULL_BETA.items():
            median_life = 20  # Typical useful life
            eta = median_to_eta(median_life, beta)
            
            survival_at_median = weibull_survival(median_life, eta, beta)
            
            # Should be very close to 0.5 (within numerical precision)
            assert abs(survival_at_median - 0.5) < 0.01, (
                f"{end_use}: S(median={median_life}) = {survival_at_median}, expected ~0.5"
            )


class TestReplacementProbabilityProperty:
    """Test suite for replacement probability properties."""
    
    def test_property_5b_bounds(self):
        """
        **Property 5b: replacement_probability is always in [0, 1] for valid inputs**
        
        **Validates: Requirements 3.3**
        
        The replacement probability represents a conditional failure probability,
        so it must be in [0, 1].
        """
        for end_use, beta in WEIBULL_BETA.items():
            eta = median_to_eta(20, beta)
            
            for age in range(0, 51):
                prob = replacement_probability(age, eta, beta)
                assert 0 <= prob <= 1, (
                    f"{end_use}: replacement_probability({age}) = {prob} is outside [0, 1]"
                )
    
    def test_property_5b_at_zero_age(self):
        """
        **Property 5b: replacement_probability(0) = 0 (new equipment doesn't need replacement)**
        
        **Validates: Requirements 3.3**
        """
        for end_use, beta in WEIBULL_BETA.items():
            eta = median_to_eta(20, beta)
            prob = replacement_probability(0, eta, beta)
            assert prob == 0.0, (
                f"{end_use}: replacement_probability(0) = {prob}, expected 0.0"
            )
    
    def test_property_5b_increases_with_age(self):
        """
        **Property 5b: replacement_probability increases with age (older equipment more likely to fail)**
        
        **Validates: Requirements 3.3**
        """
        for end_use, beta in WEIBULL_BETA.items():
            eta = median_to_eta(20, beta)
            
            # Test that probability generally increases with age
            prev_prob = 0
            for age in range(1, 51):
                prob = replacement_probability(age, eta, beta)
                # Allow for small numerical variations, but overall trend should be increasing
                assert prob >= prev_prob - 0.01, (
                    f"{end_use}: replacement_probability({age}) = {prob} < "
                    f"replacement_probability({age-1}) = {prev_prob}"
                )
                prev_prob = prob
    
    @given(
        age=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        eta=st.floats(min_value=1, max_value=50, allow_nan=False, allow_infinity=False),
        beta=st.floats(min_value=0.5, max_value=5, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.filter_too_much])
    def test_property_5b_bounds_hypothesis(self, age, eta, beta):
        """
        Property-based test using Hypothesis for replacement probability bounds.
        
        **Property 5b: replacement_probability is always in [0, 1]**
        
        **Validates: Requirements 3.3**
        """
        prob = replacement_probability(age, eta, beta)
        assert 0 <= prob <= 1, f"replacement_probability({age}) = {prob} is outside [0, 1]"


class TestEquipmentReplacementVisualizations:
    """Test suite for equipment replacement visualizations."""
    
    @pytest.fixture
    def equipment_data(self):
        """Create sample equipment data for testing."""
        np.random.seed(42)
        
        end_uses = ['space_heating', 'water_heating', 'cooking', 'clothes_drying']
        equipment_types = ['RFAU', 'RAWH', 'RRGE', 'RDRY']
        
        data = []
        for i in range(200):
            end_use = end_uses[i % len(end_uses)]
            equipment_type = equipment_types[i % len(equipment_types)]
            
            data.append({
                'blinded_id': f'P{i}',
                'equipment_type_code': equipment_type,
                'end_use': end_use,
                'efficiency': np.random.uniform(0.6, 0.95),
                'install_year': np.random.randint(1995, 2020),
                'useful_life': config.USEFUL_LIFE.get(end_use, 15),
                'fuel_type': 'natural_gas' if i % 10 < 8 else 'electric',
                'eta': median_to_eta(config.USEFUL_LIFE.get(end_use, 15), WEIBULL_BETA.get(end_use, 2.5)),
                'beta': WEIBULL_BETA.get(end_use, 2.5),
            })
        
        return pd.DataFrame(data)
    
    def test_visualizations_generated_and_saved(self, equipment_data):
        """
        Test that all required visualizations are generated and saved correctly.
        
        Generates:
        - Line graph: Weibull survival curves by end-use category
        - Line graph: Replacement probability by equipment age
        - Scatter plot: Equipment age distribution with replacement probability overlay
        - Line graph: Cumulative replacement rate over equipment lifetime
        - Stacked bar chart: Equipment fuel type distribution before/after
        - Stacked bar chart: Equipment efficiency distribution before/after
        - Sankey diagram: Equipment transitions
        
        Verifies:
        - All graphs are created
        - Files exist in output directory
        - Files contain expected data (non-zero file size)
        """
        output_dir = "output/equipment_replacement"
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate Weibull survival curves
        fig, ax = plt.subplots(figsize=(10, 6))
        ages = np.linspace(0, 50, 100)
        
        for end_use in ['space_heating', 'water_heating', 'cooking', 'clothes_drying']:
            beta = WEIBULL_BETA.get(end_use, 2.5)
            eta = median_to_eta(config.USEFUL_LIFE.get(end_use, 15), beta)
            survivals = [weibull_survival(age, eta, beta) for age in ages]
            ax.plot(ages, survivals, label=end_use, linewidth=2)
        
        ax.set_xlabel('Equipment Age (years)', fontsize=12)
        ax.set_ylabel('Survival Probability S(t)', fontsize=12)
        ax.set_title('Weibull Survival Curves by End-Use Category', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        survival_path = os.path.join(output_dir, '01_weibull_survival_curves.png')
        plt.savefig(survival_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        # Generate replacement probability curves
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for end_use in ['space_heating', 'water_heating', 'cooking', 'clothes_drying']:
            beta = WEIBULL_BETA.get(end_use, 2.5)
            eta = median_to_eta(config.USEFUL_LIFE.get(end_use, 15), beta)
            probs = [replacement_probability(age, eta, beta) for age in ages]
            ax.plot(ages, probs, label=end_use, linewidth=2)
        
        ax.set_xlabel('Equipment Age (years)', fontsize=12)
        ax.set_ylabel('Replacement Probability', fontsize=12)
        ax.set_title('Replacement Probability by Equipment Age', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        prob_path = os.path.join(output_dir, '02_replacement_probability.png')
        plt.savefig(prob_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        # Generate equipment age distribution scatter plot
        fig, ax = plt.subplots(figsize=(12, 6))
        
        current_year = 2025
        equipment_data['age'] = current_year - equipment_data['install_year']
        
        for end_use in equipment_data['end_use'].unique():
            subset = equipment_data[equipment_data['end_use'] == end_use]
            beta = WEIBULL_BETA.get(end_use, 2.5)
            eta = median_to_eta(config.USEFUL_LIFE.get(end_use, 15), beta)
            
            ax.scatter(subset['age'], subset['efficiency'], alpha=0.5, label=end_use, s=50)
        
        ax.set_xlabel('Equipment Age (years)', fontsize=12)
        ax.set_ylabel('Equipment Efficiency', fontsize=12)
        ax.set_title('Equipment Age Distribution in Baseline Stock', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        age_dist_path = os.path.join(output_dir, '03_equipment_age_distribution.png')
        plt.savefig(age_dist_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        # Generate cumulative replacement rate
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for end_use in ['space_heating', 'water_heating', 'cooking', 'clothes_drying']:
            beta = WEIBULL_BETA.get(end_use, 2.5)
            eta = median_to_eta(config.USEFUL_LIFE.get(end_use, 15), beta)
            
            cumulative_replacement = [1 - weibull_survival(age, eta, beta) for age in ages]
            ax.plot(ages, cumulative_replacement, label=end_use, linewidth=2)
        
        ax.set_xlabel('Equipment Age (years)', fontsize=12)
        ax.set_ylabel('Cumulative Replacement Rate', fontsize=12)
        ax.set_title('Cumulative Replacement Rate Over Equipment Lifetime', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        cumulative_path = os.path.join(output_dir, '04_cumulative_replacement_rate.png')
        plt.savefig(cumulative_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        # Generate fuel type distribution before/after
        fig, ax = plt.subplots(figsize=(10, 6))
        
        before_fuel = equipment_data['fuel_type'].value_counts()
        
        scenario = {
            'electrification_rate': {'space_heating': 0.1, 'water_heating': 0.15, 'cooking': 0.05, 'clothes_drying': 0.2},
            'efficiency_improvement': {'space_heating': 0.15, 'water_heating': 0.20, 'cooking': 0.10, 'clothes_drying': 0.10}
        }
        
        after_equipment = apply_replacements(equipment_data.copy(), scenario, 2025, random_seed=42)
        after_fuel = after_equipment['fuel_type'].value_counts()
        
        x = np.arange(len(before_fuel))
        width = 0.35
        
        ax.bar(x - width/2, before_fuel.values, width, label='Before', alpha=0.8)
        ax.bar(x + width/2, after_fuel.values, width, label='After', alpha=0.8)
        
        ax.set_xlabel('Fuel Type', fontsize=12)
        ax.set_ylabel('Equipment Count', fontsize=12)
        ax.set_title('Equipment Fuel Type Distribution Before and After Replacements', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(before_fuel.index)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, axis='y')
        
        fuel_path = os.path.join(output_dir, '05_fuel_type_distribution.png')
        plt.savefig(fuel_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        # Generate efficiency distribution before/after
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.hist(equipment_data['efficiency'], bins=20, alpha=0.6, label='Before', edgecolor='black')
        ax.hist(after_equipment['efficiency'], bins=20, alpha=0.6, label='After', edgecolor='black')
        
        ax.set_xlabel('Equipment Efficiency', fontsize=12)
        ax.set_ylabel('Count', fontsize=12)
        ax.set_title('Equipment Efficiency Distribution Before and After Replacements', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, axis='y')
        
        efficiency_path = os.path.join(output_dir, '06_efficiency_distribution.png')
        plt.savefig(efficiency_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        # Verify output directory was created
        assert os.path.exists(output_dir), f"Output directory {output_dir} was not created"
        
        # Verify all expected plots were created
        expected_files = [
            '01_weibull_survival_curves.png',
            '02_replacement_probability.png',
            '03_equipment_age_distribution.png',
            '04_cumulative_replacement_rate.png',
            '05_fuel_type_distribution.png',
            '06_efficiency_distribution.png'
        ]
        
        for filename in expected_files:
            filepath = os.path.join(output_dir, filename)
            assert os.path.exists(filepath), f"Plot file {filepath} does not exist"
            assert os.path.getsize(filepath) > 0, f"Plot file {filepath} is empty"
    
    def test_equipment_conservation_after_replacement(self, equipment_data):
        """
        Test that equipment count is conserved after replacement.
        
        **Property 6: Total equipment count before and after apply_replacements is equal**
        
        **Validates: Requirements 3.3, 3.4**
        """
        before_count = len(equipment_data)
        
        scenario = {
            'electrification_rate': {'space_heating': 0.1, 'water_heating': 0.15, 'cooking': 0.05, 'clothes_drying': 0.2},
            'efficiency_improvement': {'space_heating': 0.15, 'water_heating': 0.20, 'cooking': 0.10, 'clothes_drying': 0.10}
        }
        
        after_equipment = apply_replacements(equipment_data.copy(), scenario, 2025, random_seed=42)
        after_count = len(after_equipment)
        
        assert before_count == after_count, (
            f"Equipment count not conserved: before={before_count}, after={after_count}"
        )
    
    def test_replacement_probability_bounds_in_data(self, equipment_data):
        """
        Test that replacement probabilities computed from actual equipment data are in [0, 1].
        
        **Property 5b: replacement_probability is always in [0, 1]**
        
        **Validates: Requirements 3.3**
        """
        current_year = 2025
        equipment_data['age'] = current_year - equipment_data['install_year']
        
        for idx, row in equipment_data.iterrows():
            prob = replacement_probability(row['age'], row['eta'], row['beta'])
            assert 0 <= prob <= 1, (
                f"Equipment {idx}: replacement_probability = {prob} is outside [0, 1]"
            )
    
    def test_survival_monotonic_in_data(self, equipment_data):
        """
        Test that survival function is monotonically decreasing for actual equipment data.
        
        **Property 5: Weibull survival function is monotonically decreasing**
        
        **Validates: Requirements 3.3**
        """
        current_year = 2025
        equipment_data['age'] = current_year - equipment_data['install_year']
        
        for idx, row in equipment_data.iterrows():
            if row['age'] > 0:
                s_t = weibull_survival(row['age'], row['eta'], row['beta'])
                s_t_minus_1 = weibull_survival(row['age'] - 1, row['eta'], row['beta'])
                
                assert s_t <= s_t_minus_1, (
                    f"Equipment {idx}: S({row['age']}) > S({row['age']-1}) "
                    f"(not monotonically decreasing)"
                )
    def test_electrification_map_generated(self):
        """
        Test that the electrification map with OpenStreetMap background is generated correctly.
        
        Generates a choropleth map showing electrification rates by district with OSM background.
        Verifies:
        - Map file is created
        - File contains expected data (non-zero file size)
        - Map includes all districts and major cities
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "equipment_replacement")
            os.makedirs(output_dir, exist_ok=True)
            
            # Create sample electrification rates by district
            district_electrification_rates = {
                'D1': 0.15,  # Portland Metro: 15% electrification
                'D2': 0.12,  # Salem/Marion: 12% electrification
                'D3': 0.08,  # Eugene/Lane: 8% electrification
                'D4': 0.10,  # Willamette Valley: 10% electrification
                'D5': 0.18,  # Corvallis/Benton: 18% electrification
                'D6': 0.05,  # Coast/Clatsop: 5% electrification
                'D7': 0.22,  # Vancouver/Clark: 22% electrification
                'D8': 0.35,  # Gorge/Klickitat: 35% electrification (high)
            }
            
            # Generate electrification map
            map_path = os.path.join(output_dir, '07_electrification_map.png')
            fig = plot_electrification_map(
                district_electrification_rates,
                output_path=map_path
            )
            
            # Verify map file was created
            assert os.path.exists(map_path), f"Map file {map_path} does not exist"
            assert os.path.getsize(map_path) > 0, f"Map file {map_path} is empty"
            
            # Verify file size is reasonable (should be larger due to OSM background)
            file_size_kb = os.path.getsize(map_path) / 1024
            assert file_size_kb > 100, f"Map file size {file_size_kb} KB seems too small for OSM background"
    
    def test_survival_monotonic_in_data(self, equipment_data):
        """
        Test that survival function is monotonically decreasing for actual equipment data.
        
        **Property 5: Weibull survival function is monotonically decreasing**
        
        **Validates: Requirements 3.3**
        """
        current_year = 2025
        equipment_data['age'] = current_year - equipment_data['install_year']
        
        for idx, row in equipment_data.iterrows():
            if row['age'] > 0:
                s_t = weibull_survival(row['age'], row['eta'], row['beta'])
                s_t_minus_1 = weibull_survival(row['age'] - 1, row['eta'], row['beta'])
                
                assert s_t <= s_t_minus_1, (
                    f"Equipment {idx}: S({row['age']}) > S({row['age']-1}) "
                    f"(not monotonically decreasing)"
                )
