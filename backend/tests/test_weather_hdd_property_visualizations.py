"""
Property-based tests for weather module HDD computation with visualizations.

Tests correctness property:
- Property 7: HDD values are always non-negative, and HDD + CDD relationship holds
- Generates comprehensive weather analysis visualizations
"""

import pytest
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime, timedelta
import folium
from folium import plugins
import logging

from src.weather import compute_hdd, compute_cdd
from src import config

logger = logging.getLogger(__name__)

# Output directory for visualizations
OUTPUT_DIR = Path("output/weather_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TestHDDPropertyWithVisualizations:
    """Test HDD computation property with comprehensive visualizations."""
    
    @pytest.fixture
    def sample_weather_data(self):
        """Create sample weather data for a full year."""
        dates = pd.date_range('2025-01-01', periods=365, freq='D')
        # Simulate realistic Portland weather: cold winters, warm summers
        day_of_year = np.arange(365)
        # Sinusoidal pattern: ~40°F in winter, ~75°F in summer
        temps = 57.5 + 17.5 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
        # Add some random noise
        temps = temps + np.random.normal(0, 3, 365)
        
        return pd.DataFrame({
            'date': dates,
            'daily_avg_temp': temps,
            'site_id': 'KPDX'
        })
    
    def test_property_7_hdd_non_negative(self, sample_weather_data):
        """Property 7a: HDD values are always non-negative."""
        hdd = compute_hdd(sample_weather_data['daily_avg_temp'], base_temp=65.0)
        
        assert (hdd >= 0).all(), "All HDD values must be non-negative"
        assert hdd.min() >= 0, "Minimum HDD must be >= 0"
    
    def test_property_7_cdd_non_negative(self, sample_weather_data):
        """Property 7b: CDD values are always non-negative."""
        cdd = compute_cdd(sample_weather_data['daily_avg_temp'], base_temp=65.0)
        
        assert (cdd >= 0).all(), "All CDD values must be non-negative"
        assert cdd.min() >= 0, "Minimum CDD must be >= 0"
    
    def test_property_7_hdd_cdd_relationship(self, sample_weather_data):
        """Property 7c: HDD + CDD = |temp - base_temp| for all temperatures."""
        temps = sample_weather_data['daily_avg_temp']
        base_temp = 65.0
        
        hdd = compute_hdd(temps, base_temp)
        cdd = compute_cdd(temps, base_temp)
        
        expected_sum = np.abs(temps - base_temp)
        actual_sum = hdd + cdd
        
        np.testing.assert_array_almost_equal(actual_sum, expected_sum, decimal=5)
    
    def test_generate_weather_station_map(self):
        """Generate OpenStreetMap showing all weather stations classified by source."""
        # Weather station data with coordinates and classifications
        stations = {
            'KPDX': {'lat': 45.5891, 'lon': -122.5975, 'name': 'Portland International', 'source': 'NW Natural'},
            'KEUG': {'lat': 44.1239, 'lon': -123.2171, 'name': 'Eugene Airport', 'source': 'NW Natural'},
            'KSLE': {'lat': 44.9209, 'lon': -123.0065, 'name': 'Salem-Leckrone', 'source': 'NW Natural'},
            'KAST': {'lat': 46.1583, 'lon': -123.8783, 'name': 'Astoria Regional', 'source': 'NW Natural'},
            'KDLS': {'lat': 45.6089, 'lon': -121.3089, 'name': 'The Dalles Municipal', 'source': 'NW Natural'},
            'KOTH': {'lat': 43.4089, 'lon': -124.2539, 'name': 'North Bend/Coos Bay', 'source': 'Proxy'},
            'KONP': {'lat': 44.5847, 'lon': -124.0503, 'name': 'Newport Airport', 'source': 'Proxy'},
            'KCVO': {'lat': 44.4915, 'lon': -123.2803, 'name': 'Corvallis Airport', 'source': 'Proxy'},
            'KHIO': {'lat': 45.5411, 'lon': -122.9897, 'name': 'Hillsboro Airport', 'source': 'Proxy'},
            'KTTD': {'lat': 45.5550, 'lon': -122.2742, 'name': 'Troutdale Airport', 'source': 'Proxy'},
            'KVUO': {'lat': 45.6872, 'lon': -122.6611, 'name': 'Vancouver-Pearson', 'source': 'Proxy'},
        }
        
        # Create base map centered on NW Natural service territory
        center_lat = 45.0
        center_lon = -122.5
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles='OpenStreetMap'
        )
        
        # Color mapping for sources
        color_map = {
            'NW Natural': 'blue',
            'NOAA': 'green',
            'Proxy': 'orange'
        }
        
        # Add markers for each station
        for icao, info in stations.items():
            color = color_map.get(info['source'], 'gray')
            
            popup_text = f"""
            <b>{info['name']}</b><br>
            ICAO: {icao}<br>
            GHCND: {config.ICAO_TO_GHCND.get(icao, 'N/A')}<br>
            Source: {info['source']}<br>
            Lat: {info['lat']:.4f}, Lon: {info['lon']:.4f}
            """
            
            folium.CircleMarker(
                location=[info['lat'], info['lon']],
                radius=8,
                popup=folium.Popup(popup_text, max_width=300),
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.7,
                weight=2
            ).add_to(m)
            
            # Add station label
            folium.Marker(
                location=[info['lat'], info['lon']],
                icon=folium.Icon(prefix='fa', icon='info', color=color),
                popup=icao
            ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 200px; height: 150px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p style="margin: 0;"><b>Weather Station Sources</b></p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:blue"></i> NW Natural</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:green"></i> NOAA</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:orange"></i> Proxy</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save map
        map_path = OUTPUT_DIR / "weather_stations_map.html"
        m.save(str(map_path))
        logger.info(f"Weather station map saved to {map_path}")
        
        assert map_path.exists(), "Weather station map file should exist"
    
    def test_generate_hdd_cdd_daily_graph(self, sample_weather_data):
        """Generate line graph of daily HDD and CDD by day of year."""
        temps = sample_weather_data['daily_avg_temp']
        hdd = compute_hdd(temps, base_temp=65.0)
        cdd = compute_cdd(temps, base_temp=65.0)
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        day_of_year = np.arange(1, 366)
        ax.plot(day_of_year, hdd, label='HDD', color='blue', linewidth=2)
        ax.plot(day_of_year, cdd, label='CDD', color='red', linewidth=2)
        
        ax.set_xlabel('Day of Year', fontsize=12)
        ax.set_ylabel('Degree Days', fontsize=12)
        ax.set_title('Daily HDD and CDD for Portland (KPDX) - 2025', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "hdd_cdd_daily.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Daily HDD/CDD graph saved to {graph_path}")
        assert graph_path.exists(), "Daily HDD/CDD graph should exist"
    
    def test_generate_cumulative_hdd_cdd_graph(self, sample_weather_data):
        """Generate stacked area chart of cumulative HDD and CDD."""
        temps = sample_weather_data['daily_avg_temp']
        hdd = compute_hdd(temps, base_temp=65.0)
        cdd = compute_cdd(temps, base_temp=65.0)
        
        cumulative_hdd = hdd.cumsum()
        cumulative_cdd = cdd.cumsum()
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        day_of_year = np.arange(1, 366)
        ax.fill_between(day_of_year, 0, cumulative_hdd, label='Cumulative HDD', alpha=0.6, color='blue')
        ax.fill_between(day_of_year, cumulative_hdd, cumulative_hdd + cumulative_cdd, 
                        label='Cumulative CDD', alpha=0.6, color='red')
        
        ax.set_xlabel('Day of Year', fontsize=12)
        ax.set_ylabel('Cumulative Degree Days', fontsize=12)
        ax.set_title('Cumulative HDD and CDD for Portland (KPDX) - 2025', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "cumulative_hdd_cdd.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Cumulative HDD/CDD graph saved to {graph_path}")
        assert graph_path.exists(), "Cumulative HDD/CDD graph should exist"
    
    def test_generate_monthly_hdd_heatmap(self):
        """Generate heatmap of monthly average HDD across all stations."""
        # Create synthetic monthly HDD data for all 11 stations
        stations = list(config.ICAO_TO_GHCND.keys())
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Realistic HDD patterns: high in winter, low in summer
        hdd_data = np.array([
            [600, 550, 450, 250, 100, 20, 10, 15, 80, 200, 400, 550],  # KPDX
            [700, 650, 550, 300, 120, 30, 15, 20, 100, 250, 450, 650],  # KEUG
            [650, 600, 500, 280, 110, 25, 12, 18, 90, 230, 420, 600],   # KSLE
            [750, 700, 600, 350, 150, 40, 20, 25, 120, 280, 500, 700],  # KAST
            [800, 750, 650, 400, 180, 50, 30, 35, 140, 320, 550, 750],  # KDLS
            [550, 500, 400, 200, 80, 15, 5, 10, 60, 180, 350, 500],     # KOTH
            [600, 550, 450, 250, 100, 20, 10, 15, 80, 200, 400, 550],   # KONP
            [650, 600, 500, 280, 110, 25, 12, 18, 90, 230, 420, 600],   # KCVO
            [600, 550, 450, 250, 100, 20, 10, 15, 80, 200, 400, 550],   # KHIO
            [600, 550, 450, 250, 100, 20, 10, 15, 80, 200, 400, 550],   # KTTD
            [700, 650, 550, 300, 120, 30, 15, 20, 100, 250, 450, 650],  # KVUO
        ])
        
        df_hdd = pd.DataFrame(hdd_data, index=stations, columns=months)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.heatmap(df_hdd, annot=True, fmt='d', cmap='YlOrRd', cbar_kws={'label': 'HDD'}, ax=ax)
        ax.set_title('Monthly Average HDD by Weather Station', fontsize=14, fontweight='bold')
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Weather Station', fontsize=12)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "monthly_hdd_heatmap.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Monthly HDD heatmap saved to {graph_path}")
        assert graph_path.exists(), "Monthly HDD heatmap should exist"
    
    def test_generate_monthly_cdd_heatmap(self):
        """Generate heatmap of monthly average CDD across all stations."""
        stations = list(config.ICAO_TO_GHCND.keys())
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Realistic CDD patterns: low in winter, high in summer
        cdd_data = np.array([
            [0, 0, 0, 5, 30, 80, 120, 100, 50, 10, 0, 0],      # KPDX
            [0, 0, 0, 2, 15, 50, 80, 70, 30, 5, 0, 0],         # KEUG
            [0, 0, 0, 3, 20, 60, 90, 80, 40, 8, 0, 0],         # KSLE
            [0, 0, 0, 1, 10, 40, 70, 60, 25, 3, 0, 0],         # KAST
            [0, 0, 0, 0, 5, 20, 40, 35, 15, 1, 0, 0],          # KDLS
            [0, 0, 0, 8, 40, 100, 150, 130, 60, 15, 0, 0],     # KOTH
            [0, 0, 0, 5, 30, 80, 120, 100, 50, 10, 0, 0],      # KONP
            [0, 0, 0, 3, 20, 60, 90, 80, 40, 8, 0, 0],         # KCVO
            [0, 0, 0, 5, 30, 80, 120, 100, 50, 10, 0, 0],      # KHIO
            [0, 0, 0, 5, 30, 80, 120, 100, 50, 10, 0, 0],      # KTTD
            [0, 0, 0, 2, 15, 50, 80, 70, 30, 5, 0, 0],         # KVUO
        ])
        
        df_cdd = pd.DataFrame(cdd_data, index=stations, columns=months)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        sns.heatmap(df_cdd, annot=True, fmt='d', cmap='YlGnBu', cbar_kws={'label': 'CDD'}, ax=ax)
        ax.set_title('Monthly Average CDD by Weather Station', fontsize=14, fontweight='bold')
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Weather Station', fontsize=12)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "monthly_cdd_heatmap.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Monthly CDD heatmap saved to {graph_path}")
        assert graph_path.exists(), "Monthly CDD heatmap should exist"
    
    def test_generate_annual_hdd_boxplot(self):
        """Generate box plot of annual HDD distribution across all stations."""
        stations = list(config.ICAO_TO_GHCND.keys())
        
        # Simulate 11 years of annual HDD data (2015-2025)
        np.random.seed(42)
        annual_hdd_data = []
        for station in stations:
            # Base HDD varies by station, with year-to-year variation
            base_hdd = np.random.uniform(4000, 6000)
            annual_values = base_hdd + np.random.normal(0, 300, 11)
            annual_hdd_data.append(annual_values)
        
        df_annual_hdd = pd.DataFrame(annual_hdd_data, index=stations).T
        
        fig, ax = plt.subplots(figsize=(14, 6))
        df_annual_hdd.boxplot(ax=ax)
        ax.set_ylabel('Annual HDD', fontsize=12)
        ax.set_xlabel('Weather Station', fontsize=12)
        ax.set_title('Annual HDD Distribution by Station (2015-2025)', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "annual_hdd_boxplot.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Annual HDD box plot saved to {graph_path}")
        assert graph_path.exists(), "Annual HDD box plot should exist"
    
    def test_generate_annual_cdd_boxplot(self):
        """Generate box plot of annual CDD distribution across all stations."""
        stations = list(config.ICAO_TO_GHCND.keys())
        
        # Simulate 11 years of annual CDD data (2015-2025)
        np.random.seed(42)
        annual_cdd_data = []
        for station in stations:
            # Base CDD varies by station, with year-to-year variation
            base_cdd = np.random.uniform(200, 800)
            annual_values = base_cdd + np.random.normal(0, 50, 11)
            annual_cdd_data.append(annual_values)
        
        df_annual_cdd = pd.DataFrame(annual_cdd_data, index=stations).T
        
        fig, ax = plt.subplots(figsize=(14, 6))
        df_annual_cdd.boxplot(ax=ax)
        ax.set_ylabel('Annual CDD', fontsize=12)
        ax.set_xlabel('Weather Station', fontsize=12)
        ax.set_title('Annual CDD Distribution by Station (2015-2025)', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "annual_cdd_boxplot.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Annual CDD box plot saved to {graph_path}")
        assert graph_path.exists(), "Annual CDD box plot should exist"
    
    def test_generate_water_temperature_graph(self):
        """Generate line graph of daily Bull Run water temperature by day of year."""
        # Simulate realistic Bull Run water temperature data
        dates = pd.date_range('2008-01-01', periods=365*17, freq='D')  # 17 years
        day_of_year = (dates.dayofyear - 1) % 365
        
        # Seasonal pattern: ~45°F in winter, ~55°F in summer
        water_temps = 50 + 5 * np.sin(2 * np.pi * day_of_year / 365) + np.random.normal(0, 1, len(dates))
        
        df_water = pd.DataFrame({
            'date': dates,
            'water_temp': water_temps
        })
        
        # Plot overlay of all years
        fig, ax = plt.subplots(figsize=(14, 6))
        
        for year in range(2008, 2025):
            year_data = df_water[df_water['date'].dt.year == year]
            if not year_data.empty:
                day_of_year = year_data['date'].dt.dayofyear
                ax.plot(day_of_year, year_data['water_temp'], alpha=0.3, linewidth=1, color='blue')
        
        # Add average line
        avg_by_doy = df_water.groupby(df_water['date'].dt.dayofyear)['water_temp'].mean()
        ax.plot(avg_by_doy.index, avg_by_doy.values, label='Average', color='red', linewidth=2)
        
        ax.set_xlabel('Day of Year', fontsize=12)
        ax.set_ylabel('Water Temperature (°F)', fontsize=12)
        ax.set_title('Bull Run Water Temperature by Day of Year (2008-2025)', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "water_temperature_daily.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Water temperature daily graph saved to {graph_path}")
        assert graph_path.exists(), "Water temperature daily graph should exist"
    
    def test_generate_monthly_water_temperature_graph(self):
        """Generate seasonal pattern graph of average monthly water temperature."""
        # Simulate monthly water temperature data
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        avg_temps = [42, 43, 45, 48, 52, 56, 58, 57, 54, 50, 45, 42]
        min_temps = [40, 41, 43, 46, 50, 54, 56, 55, 52, 48, 43, 40]
        max_temps = [44, 45, 47, 50, 54, 58, 60, 59, 56, 52, 47, 44]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        x = np.arange(len(months))
        ax.fill_between(x, min_temps, max_temps, alpha=0.3, color='blue', label='Min-Max Range')
        ax.plot(x, avg_temps, marker='o', linewidth=2, markersize=8, color='red', label='Average')
        
        ax.set_xticks(x)
        ax.set_xticklabels(months)
        ax.set_ylabel('Water Temperature (°F)', fontsize=12)
        ax.set_title('Bull Run Water Temperature - Seasonal Pattern', fontsize=14, fontweight='bold')
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        graph_path = OUTPUT_DIR / "water_temperature_seasonal.png"
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Water temperature seasonal graph saved to {graph_path}")
        assert graph_path.exists(), "Water temperature seasonal graph should exist"
    
    def test_all_visualizations_created(self):
        """Verify all visualization files were created."""
        expected_files = [
            "weather_stations_map.html",
            "hdd_cdd_daily.png",
            "cumulative_hdd_cdd.png",
            "monthly_hdd_heatmap.png",
            "monthly_cdd_heatmap.png",
            "annual_hdd_boxplot.png",
            "annual_cdd_boxplot.png",
            "water_temperature_daily.png",
            "water_temperature_seasonal.png",
        ]
        
        for filename in expected_files:
            filepath = OUTPUT_DIR / filename
            assert filepath.exists(), f"Expected visualization file {filename} not found"
        
        logger.info(f"All {len(expected_files)} visualization files created successfully")
