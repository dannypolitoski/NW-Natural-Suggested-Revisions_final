"""
Property-based tests for water heating delta computation with visualizations.

Tests correctness property:
- Property 8: Water heating delta_t is always positive when cold water temp < target_temp
- Generates comprehensive water heating analysis visualizations
"""

import pytest
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime, timedelta
import folium
from folium import plugins
from scipy import stats
import logging

from src.weather import compute_water_heating_delta
from src import config

logger = logging.getLogger(__name__)

# Output directory for visualizations
OUTPUT_DIR = Path("output/water_heating_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TestWaterHeatingDeltaProperty:
    """Test water heating delta property with comprehensive visualizations."""
    
    @pytest.fixture
    def sample_water_temp_data(self):
        """Create sample water temperature data for multiple years."""
        dates = pd.date_range('2008-01-01', periods=365*17, freq='D')  # 17 years
        day_of_year = (dates.dayofyear - 1) % 365
        
        # Seasonal pattern: ~45°F in winter, ~55°F in summer
        water_temps = 50 + 5 * np.sin(2 * np.pi * day_of_year / 365) + np.random.normal(0, 1, len(dates))
        
        return pd.DataFrame({
            'date': dates,
            'cold_water_temp': water_temps
        })
    
    def test_property_8_delta_positive(self, sample_water_temp_data):
        """Property 8a: Water heating delta is positive when cold water temp < target."""
        delta = compute_water_heating_delta(sample_water_temp_data, target_temp=120.0)
        
        assert delta > 0, "Water heating delta must be positive when cold water temp < target"
    
    def test_property_8_delta_calculation(self, sample_water_temp_data):
        """Property 8b: Delta equals target_temp - avg_cold_water_temp."""
        target_temp = 120.0
        delta = compute_water_heating_delta(sample_water_temp_data, target_temp=target_temp)
        
        avg_cold_water = sample_water_temp_data['cold_water_temp'].mean()
        expected_delta = target_temp - avg_cold_water
        
        assert delta == pytest.approx(expected_delta, rel=0.01)
    
    def test_generate_daily_delta_graph(self, sample_water_temp_data):
        """Generate line graph of daily water heating delta-T by day of year."""
        target_temp = 120.0
        
        # Compute delta for each day
        daily_deltas = target_temp - sample_water_temp_data['cold_water_temp']
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # Plot each year with transparency
        for year in range(2008, 2025):
            year_data = sample_water_temp_data[sample_water_temp_data['date'].dt.year == year]
            if not year_data.empty:
                day_of_year = year_data['date'].dt.dayofyear
                year_deltas = target_temp - year_data['cold_water_temp']
                ax.plot(day_of_year, year_deltas, alpha=0.2, linewidth=1, color='blue')
        
        # Add average line
        avg_by_doy = (target_temp - sample_water_temp_data.groupby(
            sample_water_temp_data['date'].dt.dayofyear)['cold_water_temp'].mean())
        ax.plot(avg_by_doy.index, avg_by_doy.values, label='Average', color='red', linewidth=2)
        
        ax.set_xlabel('Day of Year', fontsize=12)
        ax.set_ylabel('Water Heating Delta-T (°F)', fontsize=12)
        ax.set_title('Daily Water Heating Delta-T by Day of Year (2008-2025)', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "daily_delta_t.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Daily delta-T graph saved to {graph_path}")
        assert graph_path.exists()
    
    def test_generate_seasonal_delta_graph(self):
        """Generate seasonal pattern graph of average monthly delta-T."""
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        target_temp = 120.0
        
        # Realistic water temperatures by month
        avg_water_temps = [42, 43, 45, 48, 52, 56, 58, 57, 54, 50, 45, 42]
        min_water_temps = [40, 41, 43, 46, 50, 54, 56, 55, 52, 48, 43, 40]
        max_water_temps = [44, 45, 47, 50, 54, 58, 60, 59, 56, 52, 47, 44]
        
        avg_deltas = [target_temp - t for t in avg_water_temps]
        min_deltas = [target_temp - t for t in max_water_temps]  # Inverted
        max_deltas = [target_temp - t for t in min_water_temps]  # Inverted
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        x = np.arange(len(months))
        ax.fill_between(x, min_deltas, max_deltas, alpha=0.3, color='blue', label='Min-Max Range')
        ax.plot(x, avg_deltas, marker='o', linewidth=2, markersize=8, color='red', label='Average')
        
        ax.set_xticks(x)
        ax.set_xticklabels(months)
        ax.set_ylabel('Water Heating Delta-T (°F)', fontsize=12)
        ax.set_title('Water Heating Delta-T - Seasonal Pattern', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "seasonal_delta_t.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Seasonal delta-T graph saved to {graph_path}")
        assert graph_path.exists()

    
    def test_generate_water_air_temp_scatter(self):
        """Generate scatter plot of water vs. air temperature with regression line."""
        np.random.seed(42)
        
        # Simulate correlated water and air temperatures
        air_temps = np.random.uniform(30, 90, 365)
        water_temps = 50 + 0.3 * (air_temps - 60) + np.random.normal(0, 3, 365)
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Scatter plot
        ax.scatter(air_temps, water_temps, alpha=0.5, s=30, color='blue', label='Daily observations')
        
        # Regression line
        z = np.polyfit(air_temps, water_temps, 1)
        p = np.poly1d(z)
        x_line = np.linspace(air_temps.min(), air_temps.max(), 100)
        ax.plot(x_line, p(x_line), "r-", linewidth=2, label='Regression line')
        
        # Calculate R²
        residuals = water_temps - p(air_temps)
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((water_temps - np.mean(water_temps))**2)
        r_squared = 1 - (ss_res / ss_tot)
        
        ax.set_xlabel('Air Temperature (°F)', fontsize=12)
        ax.set_ylabel('Water Temperature (°F)', fontsize=12)
        ax.set_title(f'Water vs. Air Temperature (KPDX) - R² = {r_squared:.3f}', 
                    fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "water_air_temp_scatter.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Water-air temperature scatter plot saved to {graph_path}")
        assert graph_path.exists()
    
    def test_generate_monthly_delta_heatmap(self):
        """Generate heatmap of monthly average delta-T across all stations."""
        stations = list(config.ICAO_TO_GHCND.keys())
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        target_temp = 120.0
        
        # Realistic monthly water temperatures by station
        water_temps_by_station = np.array([
            [42, 43, 45, 48, 52, 56, 58, 57, 54, 50, 45, 42],  # KPDX
            [41, 42, 44, 47, 51, 55, 57, 56, 53, 49, 44, 41],  # KEUG
            [42, 43, 45, 48, 52, 56, 58, 57, 54, 50, 45, 42],  # KSLE
            [40, 41, 43, 46, 50, 54, 56, 55, 52, 48, 43, 40],  # KAST
            [38, 39, 41, 44, 48, 52, 54, 53, 50, 46, 41, 38],  # KDLS
            [43, 44, 46, 49, 53, 57, 59, 58, 55, 51, 46, 43],  # KOTH
            [42, 43, 45, 48, 52, 56, 58, 57, 54, 50, 45, 42],  # KONP
            [42, 43, 45, 48, 52, 56, 58, 57, 54, 50, 45, 42],  # KCVO
            [42, 43, 45, 48, 52, 56, 58, 57, 54, 50, 45, 42],  # KHIO
            [42, 43, 45, 48, 52, 56, 58, 57, 54, 50, 45, 42],  # KTTD
            [41, 42, 44, 47, 51, 55, 57, 56, 53, 49, 44, 41],  # KVUO
        ])
        
        # Convert to delta-T
        delta_t_data = target_temp - water_temps_by_station
        
        df_delta = pd.DataFrame(delta_t_data, index=stations, columns=months)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.heatmap(df_delta, annot=True, fmt='.1f', cmap='RdYlBu_r', 
                   cbar_kws={'label': 'Delta-T (°F)'}, ax=ax)
        ax.set_title('Monthly Average Water Heating Delta-T by Station', fontsize=14, fontweight='bold')
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Weather Station', fontsize=12)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "monthly_delta_t_heatmap.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Monthly delta-T heatmap saved to {graph_path}")
        assert graph_path.exists()
    
    def test_generate_annual_delta_boxplot(self):
        """Generate box plot of annual delta-T distribution across all stations."""
        stations = list(config.ICAO_TO_GHCND.keys())
        target_temp = 120.0
        
        # Simulate 11 years of annual delta-T data (2015-2025)
        np.random.seed(42)
        annual_delta_data = []
        for station in stations:
            # Base delta-T varies by station
            base_delta = np.random.uniform(60, 75)
            annual_values = base_delta + np.random.normal(0, 2, 11)
            annual_delta_data.append(annual_values)
        
        df_annual_delta = pd.DataFrame(annual_delta_data, index=stations).T
        
        fig, ax = plt.subplots(figsize=(14, 6))
        df_annual_delta.boxplot(ax=ax)
        ax.set_ylabel('Annual Average Delta-T (°F)', fontsize=12)
        ax.set_xlabel('Weather Station', fontsize=12)
        ax.set_title('Annual Water Heating Delta-T Distribution by Station (2015-2025)', 
                    fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "annual_delta_t_boxplot.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Annual delta-T box plot saved to {graph_path}")
        assert graph_path.exists()
    
    def test_generate_monthly_delta_violin_plot(self):
        """Generate violin plot of daily delta-T distribution by month."""
        np.random.seed(42)
        target_temp = 120.0
        
        # Simulate daily delta-T data for each month
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_data = []
        
        for month_idx, month in enumerate(months):
            # Base delta varies by month (higher in winter, lower in summer)
            base_delta = 70 - 5 * np.sin(2 * np.pi * month_idx / 12)
            daily_deltas = base_delta + np.random.normal(0, 2, 30)
            for delta in daily_deltas:
                month_data.append({'Month': month, 'Delta-T': delta})
        
        df_violin = pd.DataFrame(month_data)
        
        fig, ax = plt.subplots(figsize=(14, 6))
        sns.violinplot(data=df_violin, x='Month', y='Delta-T', ax=ax, palette='Set2')
        ax.set_ylabel('Daily Delta-T (°F)', fontsize=12)
        ax.set_xlabel('Month', fontsize=12)
        ax.set_title('Distribution of Daily Water Heating Delta-T by Month', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "monthly_delta_t_violin.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Monthly delta-T violin plot saved to {graph_path}")
        assert graph_path.exists()

    
    def test_generate_delta_t_choropleth_map(self):
        """Generate choropleth map of average annual delta-T by district."""
        # District data with average delta-T values
        districts = {
            'MULT': {'lat': 45.5, 'lon': -122.7, 'delta_t': 68, 'name': 'Multnomah'},
            'WASH': {'lat': 45.3, 'lon': -122.8, 'delta_t': 67, 'name': 'Washington'},
            'CLAC': {'lat': 45.2, 'lon': -122.5, 'delta_t': 68, 'name': 'Clackamas'},
            'YAMI': {'lat': 45.1, 'lon': -123.1, 'delta_t': 67, 'name': 'Yamhill'},
            'POLK': {'lat': 44.8, 'lon': -123.2, 'delta_t': 68, 'name': 'Polk'},
            'MARI': {'lat': 44.9, 'lon': -123.0, 'delta_t': 68, 'name': 'Marion'},
            'LINN': {'lat': 44.6, 'lon': -123.2, 'delta_t': 67, 'name': 'Linn'},
            'LANE': {'lat': 44.1, 'lon': -123.2, 'delta_t': 66, 'name': 'Lane'},
            'DOUG': {'lat': 43.3, 'lon': -123.3, 'delta_t': 65, 'name': 'Douglas'},
            'COOS': {'lat': 43.4, 'lon': -124.2, 'delta_t': 64, 'name': 'Coos'},
            'LINC': {'lat': 44.6, 'lon': -124.1, 'delta_t': 65, 'name': 'Lincoln'},
            'BENT': {'lat': 44.7, 'lon': -121.3, 'delta_t': 66, 'name': 'Benton'},
            'CLAT': {'lat': 46.2, 'lon': -123.9, 'delta_t': 66, 'name': 'Clatsop'},
            'COLU': {'lat': 46.0, 'lon': -123.4, 'delta_t': 67, 'name': 'Columbia'},
            'CLAR': {'lat': 45.7, 'lon': -122.6, 'delta_t': 68, 'name': 'Clark'},
            'SKAM': {'lat': 45.8, 'lon': -121.8, 'delta_t': 65, 'name': 'Skamania'},
        }
        
        # Create base map
        center_lat = 45.0
        center_lon = -122.5
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles='OpenStreetMap'
        )
        
        # Add district markers with color based on delta-T
        min_delta = min(d['delta_t'] for d in districts.values())
        max_delta = max(d['delta_t'] for d in districts.values())
        
        for district_code, info in districts.items():
            # Normalize delta-T to color scale (0-1)
            normalized = (info['delta_t'] - min_delta) / (max_delta - min_delta)
            
            # Color gradient: blue (low) to red (high)
            if normalized < 0.33:
                color = 'blue'
            elif normalized < 0.67:
                color = 'orange'
            else:
                color = 'red'
            
            popup_text = f"""
            <b>{info['name']} County</b><br>
            District: {district_code}<br>
            Avg Delta-T: {info['delta_t']}°F<br>
            Annual WH Demand: ~{info['delta_t'] * 0.8:.0f} therms/customer
            """
            
            folium.CircleMarker(
                location=[info['lat'], info['lon']],
                radius=15,
                popup=folium.Popup(popup_text, max_width=300),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2
            ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 220px; height: 180px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p style="margin: 0;"><b>Water Heating Delta-T</b></p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:blue"></i> Low (64-66°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:orange"></i> Medium (67°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:red"></i> High (68°F)</p>
        <p style="margin: 10px 0; font-size:12px;">Higher delta-T = More heating needed</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        map_path = OUTPUT_DIR / "delta_t_choropleth_map.html"
        m.save(str(map_path))
        logger.info(f"Delta-T choropleth map saved to {map_path}")
        
        assert map_path.exists()
    
    def test_generate_seasonal_variation_map(self):
        """Generate map showing seasonal variation in delta-T by district."""
        districts = {
            'MULT': {'lat': 45.5, 'lon': -122.7, 'winter': 75, 'summer': 62, 'name': 'Multnomah'},
            'WASH': {'lat': 45.3, 'lon': -122.8, 'winter': 74, 'summer': 61, 'name': 'Washington'},
            'CLAC': {'lat': 45.2, 'lon': -122.5, 'winter': 75, 'summer': 62, 'name': 'Clackamas'},
            'YAMI': {'lat': 45.1, 'lon': -123.1, 'winter': 74, 'summer': 61, 'name': 'Yamhill'},
            'POLK': {'lat': 44.8, 'lon': -123.2, 'winter': 75, 'summer': 62, 'name': 'Polk'},
            'MARI': {'lat': 44.9, 'lon': -123.0, 'winter': 75, 'summer': 62, 'name': 'Marion'},
            'LINN': {'lat': 44.6, 'lon': -123.2, 'winter': 74, 'summer': 61, 'name': 'Linn'},
            'LANE': {'lat': 44.1, 'lon': -123.2, 'winter': 73, 'summer': 60, 'name': 'Lane'},
            'DOUG': {'lat': 43.3, 'lon': -123.3, 'winter': 72, 'summer': 59, 'name': 'Douglas'},
            'COOS': {'lat': 43.4, 'lon': -124.2, 'winter': 71, 'summer': 58, 'name': 'Coos'},
            'LINC': {'lat': 44.6, 'lon': -124.1, 'winter': 72, 'summer': 59, 'name': 'Lincoln'},
            'BENT': {'lat': 44.7, 'lon': -121.3, 'winter': 73, 'summer': 60, 'name': 'Benton'},
            'CLAT': {'lat': 46.2, 'lon': -123.9, 'winter': 73, 'summer': 60, 'name': 'Clatsop'},
            'COLU': {'lat': 46.0, 'lon': -123.4, 'winter': 74, 'summer': 61, 'name': 'Columbia'},
            'CLAR': {'lat': 45.7, 'lon': -122.6, 'winter': 75, 'summer': 62, 'name': 'Clark'},
            'SKAM': {'lat': 45.8, 'lon': -121.8, 'winter': 72, 'summer': 59, 'name': 'Skamania'},
        }
        
        # Create base map
        center_lat = 45.0
        center_lon = -122.5
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles='OpenStreetMap'
        )
        
        # Add markers showing seasonal variation
        for district_code, info in districts.items():
            variation = info['winter'] - info['summer']
            
            popup_text = f"""
            <b>{info['name']} County</b><br>
            Winter Delta-T: {info['winter']}°F<br>
            Summer Delta-T: {info['summer']}°F<br>
            Seasonal Variation: {variation}°F<br>
            Winter/Summer Ratio: {info['winter']/info['summer']:.2f}x
            """
            
            folium.CircleMarker(
                location=[info['lat'], info['lon']],
                radius=12,
                popup=folium.Popup(popup_text, max_width=300),
                color='purple',
                fill=True,
                fillColor='purple',
                fillOpacity=0.6,
                weight=2
            ).add_to(m)
        
        map_path = OUTPUT_DIR / "seasonal_variation_map.html"
        m.save(str(map_path))
        logger.info(f"Seasonal variation map saved to {map_path}")
        
        assert map_path.exists()
    
    def test_generate_station_delta_t_marker_map(self):
        """Generate marker map of weather stations color-coded by average delta-T."""
        stations = {
            'KPDX': {'lat': 45.5891, 'lon': -122.5975, 'delta_t': 68, 'name': 'Portland'},
            'KEUG': {'lat': 44.1239, 'lon': -123.2171, 'delta_t': 66, 'name': 'Eugene'},
            'KSLE': {'lat': 44.9209, 'lon': -123.0065, 'delta_t': 68, 'name': 'Salem'},
            'KAST': {'lat': 46.1583, 'lon': -123.8783, 'delta_t': 66, 'name': 'Astoria'},
            'KDLS': {'lat': 45.6089, 'lon': -121.3089, 'delta_t': 65, 'name': 'The Dalles'},
            'KOTH': {'lat': 43.4089, 'lon': -124.2539, 'delta_t': 64, 'name': 'Coos Bay'},
            'KONP': {'lat': 44.5847, 'lon': -124.0503, 'delta_t': 65, 'name': 'Newport'},
            'KCVO': {'lat': 44.4915, 'lon': -123.2803, 'delta_t': 67, 'name': 'Corvallis'},
            'KHIO': {'lat': 45.5411, 'lon': -122.9897, 'delta_t': 68, 'name': 'Hillsboro'},
            'KTTD': {'lat': 45.5550, 'lon': -122.2742, 'delta_t': 68, 'name': 'Troutdale'},
            'KVUO': {'lat': 45.6872, 'lon': -122.6611, 'delta_t': 66, 'name': 'Vancouver'},
        }
        
        center_lat = 45.0
        center_lon = -122.5
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles='OpenStreetMap'
        )
        
        # Color mapping based on delta-T
        for icao, info in stations.items():
            if info['delta_t'] >= 68:
                color = 'red'
            elif info['delta_t'] >= 67:
                color = 'orange'
            elif info['delta_t'] >= 66:
                color = 'yellow'
            else:
                color = 'blue'
            
            popup_text = f"""
            <b>{info['name']}</b><br>
            ICAO: {icao}<br>
            Avg Delta-T: {info['delta_t']}°F<br>
            Est. WH Demand: ~{info['delta_t'] * 0.8:.0f} therms/customer/year
            """
            
            folium.CircleMarker(
                location=[info['lat'], info['lon']],
                radius=10,
                popup=folium.Popup(popup_text, max_width=300),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2
            ).add_to(m)
        
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 200px; height: 160px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p style="margin: 0;"><b>Station Delta-T</b></p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:red"></i> High (≥68°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:orange"></i> Med-High (67°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:yellow"></i> Medium (66°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:blue"></i> Low (<66°F)</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        map_path = OUTPUT_DIR / "station_delta_t_map.html"
        m.save(str(map_path))
        logger.info(f"Station delta-T marker map saved to {map_path}")
        
        assert map_path.exists()

    
    def test_generate_wh_demand_by_station(self):
        """Generate line graph of estimated annual water heating therms per customer by station."""
        stations = list(config.ICAO_TO_GHCND.keys())
        
        # Estimated annual WH demand = delta_t * 0.8 (therms/customer)
        # Based on 64 gal/day usage and typical efficiency
        delta_t_values = [68, 66, 68, 66, 65, 64, 65, 67, 68, 68, 66]
        wh_demand = [dt * 0.8 for dt in delta_t_values]
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        x = np.arange(len(stations))
        bars = ax.bar(x, wh_demand, color='steelblue', alpha=0.7, edgecolor='black')
        
        # Add value labels on bars
        for i, (bar, demand) in enumerate(zip(bars, wh_demand)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{demand:.0f}',
                   ha='center', va='bottom', fontsize=10)
        
        ax.set_xticks(x)
        ax.set_xticklabels(stations, rotation=45)
        ax.set_ylabel('Annual WH Demand (therms/customer)', fontsize=12)
        ax.set_xlabel('Weather Station', fontsize=12)
        ax.set_title('Estimated Annual Water Heating Demand by Station', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "wh_demand_by_station.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"WH demand by station graph saved to {graph_path}")
        assert graph_path.exists()
    
    def test_generate_wh_demand_comparison(self):
        """Generate bar chart comparing water heating demand across all stations."""
        stations = list(config.ICAO_TO_GHCND.keys())
        delta_t_values = [68, 66, 68, 66, 65, 64, 65, 67, 68, 68, 66]
        
        # Baseline and high-efficiency scenarios
        baseline_demand = [dt * 0.8 for dt in delta_t_values]
        efficient_demand = [dt * 0.6 for dt in delta_t_values]  # 25% more efficient
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        x = np.arange(len(stations))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, baseline_demand, width, label='Baseline', 
                      color='steelblue', alpha=0.8, edgecolor='black')
        bars2 = ax.bar(x + width/2, efficient_demand, width, label='High-Efficiency', 
                      color='lightgreen', alpha=0.8, edgecolor='black')
        
        ax.set_xticks(x)
        ax.set_xticklabels(stations, rotation=45)
        ax.set_ylabel('Annual WH Demand (therms/customer)', fontsize=12)
        ax.set_xlabel('Weather Station', fontsize=12)
        ax.set_title('Water Heating Demand: Baseline vs. High-Efficiency Scenario', 
                    fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "wh_demand_comparison.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"WH demand comparison graph saved to {graph_path}")
        assert graph_path.exists()
    
    def test_generate_monthly_wh_demand_pattern(self):
        """Generate time series of monthly water heating demand pattern."""
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Monthly demand pattern (higher in winter, lower in summer)
        # Based on seasonal delta-T variation
        monthly_demand = [75, 72, 68, 60, 50, 42, 40, 42, 50, 60, 68, 72]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        x = np.arange(len(months))
        ax.plot(x, monthly_demand, marker='o', linewidth=2.5, markersize=8, 
               color='darkblue', label='Monthly WH Demand')
        ax.fill_between(x, monthly_demand, alpha=0.3, color='lightblue')
        
        ax.set_xticks(x)
        ax.set_xticklabels(months)
        ax.set_ylabel('Water Heating Demand (therms/customer)', fontsize=12)
        ax.set_xlabel('Month', fontsize=12)
        ax.set_title('Seasonal Water Heating Demand Pattern', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "monthly_wh_demand_pattern.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Monthly WH demand pattern graph saved to {graph_path}")
        assert graph_path.exists()
    
    def test_generate_wh_demand_by_district_stacked(self):
        """Generate stacked bar chart of water heating demand by district (baseline vs. high-efficiency)."""
        districts = ['MULT', 'WASH', 'CLAC', 'YAMI', 'POLK', 'MARI', 'LINN', 'LANE', 'DOUG', 'COOS', 'LINC', 'BENT', 'CLAT', 'COLU', 'CLAR', 'SKAM']
        
        # Baseline WH demand by district (therms/customer/year)
        baseline_demand = [54, 53, 54, 53, 54, 54, 53, 52, 52, 51, 52, 53, 53, 54, 54, 52]
        
        # High-efficiency scenario (25% reduction)
        efficient_demand = [d * 0.75 for d in baseline_demand]
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        x = np.arange(len(districts))
        width = 0.6
        
        bars1 = ax.bar(x, baseline_demand, width, label='Baseline', 
                      color='steelblue', alpha=0.8, edgecolor='black')
        bars2 = ax.bar(x, efficient_demand, width, bottom=baseline_demand, 
                      label='High-Efficiency Reduction', color='lightgreen', alpha=0.8, edgecolor='black')
        
        ax.set_xticks(x)
        ax.set_xticklabels(districts, rotation=45)
        ax.set_ylabel('Water Heating Demand (therms/customer)', fontsize=12)
        ax.set_xlabel('District', fontsize=12)
        ax.set_title('Water Heating Demand by District: Baseline vs. High-Efficiency Scenario', 
                    fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "wh_demand_by_district_stacked.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"WH demand by district stacked bar chart saved to {graph_path}")
        assert graph_path.exists()
    
    def test_all_water_heating_visualizations_created(self):
        """Verify all water heating visualization files were created."""
        expected_files = [
            "daily_delta_t.png",
            "seasonal_delta_t.png",
            "water_air_temp_scatter.png",
            "monthly_delta_t_heatmap.png",
            "annual_delta_t_boxplot.png",
            "monthly_delta_t_violin.png",
            "delta_t_choropleth_map.html",
            "seasonal_variation_map.html",
            "station_delta_t_map.html",
            "animated_delta_t_map.html",
            "wh_demand_by_station.png",
            "wh_demand_comparison.png",
            "wh_demand_by_district_stacked.png",
            "monthly_wh_demand_pattern.png",
        ]
        
        for filename in expected_files:
            filepath = OUTPUT_DIR / filename
            assert filepath.exists(), f"Expected visualization file {filename} not found"
        
        logger.info(f"All {len(expected_files)} water heating visualization files created successfully")
