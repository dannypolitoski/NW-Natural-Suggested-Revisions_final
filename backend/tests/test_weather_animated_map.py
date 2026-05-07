"""
Animated map display for HDD/CDD progression throughout the year.

Generates an interactive animated map showing how HDD/CDD changes
across all weather stations from January through December.
"""

import pytest
import pandas as pd
import numpy as np
import folium
from folium import plugins
from pathlib import Path
import json
import logging

from src import config

logger = logging.getLogger(__name__)

# Output directory for visualizations
OUTPUT_DIR = Path("output/weather_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TestAnimatedWeatherMap:
    """Generate animated map display for HDD/CDD progression."""
    
    def test_generate_animated_hdd_map(self):
        """Generate animated map showing HDD progression throughout the year."""
        # Weather station data with coordinates
        stations = {
            'KPDX': {'lat': 45.5891, 'lon': -122.5975, 'name': 'Portland International'},
            'KEUG': {'lat': 44.1239, 'lon': -123.2171, 'name': 'Eugene Airport'},
            'KSLE': {'lat': 44.9209, 'lon': -123.0065, 'name': 'Salem-Leckrone'},
            'KAST': {'lat': 46.1583, 'lon': -123.8783, 'name': 'Astoria Regional'},
            'KDLS': {'lat': 45.6089, 'lon': -121.3089, 'name': 'The Dalles Municipal'},
            'KOTH': {'lat': 43.4089, 'lon': -124.2539, 'name': 'North Bend/Coos Bay'},
            'KONP': {'lat': 44.5847, 'lon': -124.0503, 'name': 'Newport Airport'},
            'KCVO': {'lat': 44.4915, 'lon': -123.2803, 'name': 'Corvallis Airport'},
            'KHIO': {'lat': 45.5411, 'lon': -122.9897, 'name': 'Hillsboro Airport'},
            'KTTD': {'lat': 45.5550, 'lon': -122.2742, 'name': 'Troutdale Airport'},
            'KVUO': {'lat': 45.6872, 'lon': -122.6611, 'name': 'Vancouver-Pearson'},
        }
        
        # Monthly HDD data for each station (realistic pattern)
        monthly_hdd = {
            'KPDX': [600, 550, 450, 250, 100, 20, 10, 15, 80, 200, 400, 550],
            'KEUG': [700, 650, 550, 300, 120, 30, 15, 20, 100, 250, 450, 650],
            'KSLE': [650, 600, 500, 280, 110, 25, 12, 18, 90, 230, 420, 600],
            'KAST': [750, 700, 600, 350, 150, 40, 20, 25, 120, 280, 500, 700],
            'KDLS': [800, 750, 650, 400, 180, 50, 30, 35, 140, 320, 550, 750],
            'KOTH': [550, 500, 400, 200, 80, 15, 5, 10, 60, 180, 350, 500],
            'KONP': [600, 550, 450, 250, 100, 20, 10, 15, 80, 200, 400, 550],
            'KCVO': [650, 600, 500, 280, 110, 25, 12, 18, 90, 230, 420, 600],
            'KHIO': [600, 550, 450, 250, 100, 20, 10, 15, 80, 200, 400, 550],
            'KTTD': [600, 550, 450, 250, 100, 20, 10, 15, 80, 200, 400, 550],
            'KVUO': [700, 650, 550, 300, 120, 30, 15, 20, 100, 250, 450, 650],
        }
        
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                 'July', 'August', 'September', 'October', 'November', 'December']
        
        # Create base map
        center_lat = 45.0
        center_lon = -122.5
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles='OpenStreetMap'
        )
        
        # Create feature groups for each month
        feature_groups = {}
        for month_idx, month in enumerate(months):
            fg = folium.FeatureGroup(name=month, show=(month_idx == 0))
            
            for icao, info in stations.items():
                hdd_value = monthly_hdd[icao][month_idx]
                
                # Normalize HDD to color scale (0-800)
                normalized = min(hdd_value / 800.0, 1.0)
                
                # Color gradient: green (low HDD) to red (high HDD)
                if normalized < 0.25:
                    color = 'green'
                    intensity = 0.3
                elif normalized < 0.5:
                    color = 'yellow'
                    intensity = 0.5
                elif normalized < 0.75:
                    color = 'orange'
                    intensity = 0.7
                else:
                    color = 'red'
                    intensity = 0.9
                
                popup_text = f"""
                <b>{info['name']}</b><br>
                ICAO: {icao}<br>
                Month: {month}<br>
                HDD: {hdd_value:.0f}°F-days<br>
                Heating Demand: {'High' if hdd_value > 500 else 'Medium' if hdd_value > 200 else 'Low'}
                """
                
                folium.CircleMarker(
                    location=[info['lat'], info['lon']],
                    radius=12,
                    popup=folium.Popup(popup_text, max_width=300),
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=intensity,
                    weight=2
                ).add_to(fg)
            
            feature_groups[month] = fg
            m.add_child(fg)
        
        # Add layer control for month selection
        folium.LayerControl(collapsed=False).add_to(m)
        
        # Add title and legend
        title_html = '''
        <div style="position: fixed; 
                    top: 10px; left: 50px; width: 300px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p style="margin: 0; font-weight: bold; font-size: 16px;">HDD Progression Map</p>
        <p style="margin: 5px 0; font-size: 12px;">Select month from layer control (right)</p>
        <p style="margin: 5px 0; font-size: 12px;">Marker color intensity shows HDD magnitude</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 200px; height: 200px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px">
        <p style="margin: 0; font-weight: bold;">HDD Scale</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:green"></i> Low (0-200)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:yellow"></i> Medium (200-400)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:orange"></i> High (400-600)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:red"></i> Very High (600+)</p>
        <p style="margin: 10px 0; font-size: 11px;">Opacity indicates intensity</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save map
        map_path = OUTPUT_DIR / "animated_hdd_map.html"
        m.save(str(map_path))
        logger.info(f"Animated HDD map saved to {map_path}")
        
        assert map_path.exists()
    
    def test_generate_animated_cdd_map(self):
        """Generate animated map showing CDD progression throughout the year."""
        stations = {
            'KPDX': {'lat': 45.5891, 'lon': -122.5975, 'name': 'Portland International'},
            'KEUG': {'lat': 44.1239, 'lon': -123.2171, 'name': 'Eugene Airport'},
            'KSLE': {'lat': 44.9209, 'lon': -123.0065, 'name': 'Salem-Leckrone'},
            'KAST': {'lat': 46.1583, 'lon': -123.8783, 'name': 'Astoria Regional'},
            'KDLS': {'lat': 45.6089, 'lon': -121.3089, 'name': 'The Dalles Municipal'},
            'KOTH': {'lat': 43.4089, 'lon': -124.2539, 'name': 'North Bend/Coos Bay'},
            'KONP': {'lat': 44.5847, 'lon': -124.0503, 'name': 'Newport Airport'},
            'KCVO': {'lat': 44.4915, 'lon': -123.2803, 'name': 'Corvallis Airport'},
            'KHIO': {'lat': 45.5411, 'lon': -122.9897, 'name': 'Hillsboro Airport'},
            'KTTD': {'lat': 45.5550, 'lon': -122.2742, 'name': 'Troutdale Airport'},
            'KVUO': {'lat': 45.6872, 'lon': -122.6611, 'name': 'Vancouver-Pearson'},
        }
        
        # Monthly CDD data for each station (realistic pattern)
        monthly_cdd = {
            'KPDX': [0, 0, 0, 5, 30, 80, 120, 100, 50, 10, 0, 0],
            'KEUG': [0, 0, 0, 2, 15, 50, 80, 70, 30, 5, 0, 0],
            'KSLE': [0, 0, 0, 3, 20, 60, 90, 80, 40, 8, 0, 0],
            'KAST': [0, 0, 0, 1, 10, 40, 70, 60, 25, 3, 0, 0],
            'KDLS': [0, 0, 0, 0, 5, 20, 40, 35, 15, 1, 0, 0],
            'KOTH': [0, 0, 0, 8, 40, 100, 150, 130, 60, 15, 0, 0],
            'KONP': [0, 0, 0, 5, 30, 80, 120, 100, 50, 10, 0, 0],
            'KCVO': [0, 0, 0, 3, 20, 60, 90, 80, 40, 8, 0, 0],
            'KHIO': [0, 0, 0, 5, 30, 80, 120, 100, 50, 10, 0, 0],
            'KTTD': [0, 0, 0, 5, 30, 80, 120, 100, 50, 10, 0, 0],
            'KVUO': [0, 0, 0, 2, 15, 50, 80, 70, 30, 5, 0, 0],
        }
        
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                 'July', 'August', 'September', 'October', 'November', 'December']
        
        # Create base map
        center_lat = 45.0
        center_lon = -122.5
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles='OpenStreetMap'
        )
        
        # Create feature groups for each month
        for month_idx, month in enumerate(months):
            fg = folium.FeatureGroup(name=month, show=(month_idx == 0))
            
            for icao, info in stations.items():
                cdd_value = monthly_cdd[icao][month_idx]
                
                # Normalize CDD to color scale (0-150)
                normalized = min(cdd_value / 150.0, 1.0)
                
                # Color gradient: blue (low CDD) to red (high CDD)
                if normalized < 0.25:
                    color = 'blue'
                    intensity = 0.3
                elif normalized < 0.5:
                    color = 'cyan'
                    intensity = 0.5
                elif normalized < 0.75:
                    color = 'orange'
                    intensity = 0.7
                else:
                    color = 'red'
                    intensity = 0.9
                
                popup_text = f"""
                <b>{info['name']}</b><br>
                ICAO: {icao}<br>
                Month: {month}<br>
                CDD: {cdd_value:.0f}°F-days<br>
                Cooling Demand: {'High' if cdd_value > 80 else 'Medium' if cdd_value > 20 else 'Low'}
                """
                
                folium.CircleMarker(
                    location=[info['lat'], info['lon']],
                    radius=12,
                    popup=folium.Popup(popup_text, max_width=300),
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=intensity,
                    weight=2
                ).add_to(fg)
            
            m.add_child(fg)
        
        # Add layer control
        folium.LayerControl(collapsed=False).add_to(m)
        
        # Add title
        title_html = '''
        <div style="position: fixed; 
                    top: 10px; left: 50px; width: 300px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p style="margin: 0; font-weight: bold; font-size: 16px;">CDD Progression Map</p>
        <p style="margin: 5px 0; font-size: 12px;">Select month from layer control (right)</p>
        <p style="margin: 5px 0; font-size: 12px;">Marker color intensity shows CDD magnitude</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 200px; height: 200px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px">
        <p style="margin: 0; font-weight: bold;">CDD Scale</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:blue"></i> Low (0-40)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:cyan"></i> Medium (40-75)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:orange"></i> High (75-112)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:red"></i> Very High (112+)</p>
        <p style="margin: 10px 0; font-size: 11px;">Opacity indicates intensity</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save map
        map_path = OUTPUT_DIR / "animated_cdd_map.html"
        m.save(str(map_path))
        logger.info(f"Animated CDD map saved to {map_path}")
        
        assert map_path.exists()
    
    def test_animated_maps_created(self):
        """Verify animated map files were created."""
        expected_files = [
            "animated_hdd_map.html",
            "animated_cdd_map.html",
        ]
        
        for filename in expected_files:
            filepath = OUTPUT_DIR / filename
            assert filepath.exists(), f"Expected animated map file {filename} not found"
        
        logger.info(f"All {len(expected_files)} animated map files created successfully")
