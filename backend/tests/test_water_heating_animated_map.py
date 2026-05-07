"""
Animated map display for water heating delta-T progression throughout the year.

Generates an interactive animated map showing how delta-T changes
across all weather stations from January through December.
"""

import pytest
import folium
from pathlib import Path
import logging

from src import config

logger = logging.getLogger(__name__)

# Output directory for visualizations
OUTPUT_DIR = Path("output/water_heating_analysis")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TestAnimatedWaterHeatingMap:
    """Generate animated map display for delta-T progression."""
    
    def test_generate_animated_delta_t_map(self):
        """Generate animated map showing delta-T progression throughout the year."""
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
        
        # Monthly delta-T data for each station (realistic pattern)
        # Higher in winter (cold water), lower in summer (warm water)
        monthly_delta_t = {
            'KPDX': [75, 72, 68, 60, 50, 42, 40, 42, 50, 60, 68, 72],
            'KEUG': [76, 73, 69, 61, 51, 43, 41, 43, 51, 61, 69, 73],
            'KSLE': [75, 72, 68, 60, 50, 42, 40, 42, 50, 60, 68, 72],
            'KAST': [74, 71, 67, 59, 49, 41, 39, 41, 49, 59, 67, 71],
            'KDLS': [73, 70, 66, 58, 48, 40, 38, 40, 48, 58, 66, 70],
            'KOTH': [77, 74, 70, 62, 52, 44, 42, 44, 52, 62, 70, 74],
            'KONP': [75, 72, 68, 60, 50, 42, 40, 42, 50, 60, 68, 72],
            'KCVO': [75, 72, 68, 60, 50, 42, 40, 42, 50, 60, 68, 72],
            'KHIO': [75, 72, 68, 60, 50, 42, 40, 42, 50, 60, 68, 72],
            'KTTD': [75, 72, 68, 60, 50, 42, 40, 42, 50, 60, 68, 72],
            'KVUO': [76, 73, 69, 61, 51, 43, 41, 43, 51, 61, 69, 73],
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
                delta_t = monthly_delta_t[icao][month_idx]
                
                # Normalize delta-T to color scale (40-77°F)
                normalized = (delta_t - 40) / (77 - 40)
                normalized = min(max(normalized, 0), 1.0)
                
                # Color gradient: blue (low delta-T) to red (high delta-T)
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
                
                # Estimate WH demand (therms/customer)
                wh_demand = delta_t * 0.8
                
                popup_text = f"""
                <b>{info['name']}</b><br>
                ICAO: {icao}<br>
                Month: {month}<br>
                Delta-T: {delta_t:.1f}°F<br>
                Est. WH Demand: {wh_demand:.0f} therms/customer<br>
                Demand Level: {'High' if delta_t > 70 else 'Medium' if delta_t > 55 else 'Low'}
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
                    top: 10px; left: 50px; width: 350px; height: auto; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p style="margin: 0; font-weight: bold; font-size: 16px;">Water Heating Delta-T Progression</p>
        <p style="margin: 5px 0; font-size: 12px;">Select month from layer control (right)</p>
        <p style="margin: 5px 0; font-size: 12px;">Marker color intensity shows delta-T magnitude</p>
        <p style="margin: 5px 0; font-size: 12px;">Higher delta-T = More water heating needed</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 220px; height: 220px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px">
        <p style="margin: 0; font-weight: bold;">Delta-T Scale (°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:blue"></i> Low (40-48°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:cyan"></i> Medium (48-58°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:orange"></i> High (58-68°F)</p>
        <p style="margin: 5px 0;"><i class="fa fa-circle" style="color:red"></i> Very High (68+°F)</p>
        <p style="margin: 10px 0; font-size: 11px;"><b>WH Demand Estimate:</b></p>
        <p style="margin: 5px 0; font-size: 11px;">Low: 32-38 therms/customer</p>
        <p style="margin: 5px 0; font-size: 11px;">Medium: 38-46 therms/customer</p>
        <p style="margin: 5px 0; font-size: 11px;">High: 46-54 therms/customer</p>
        <p style="margin: 5px 0; font-size: 11px;">Very High: 54+ therms/customer</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save map
        map_path = OUTPUT_DIR / "animated_delta_t_map.html"
        m.save(str(map_path))
        logger.info(f"Animated delta-T map saved to {map_path}")
        
        assert map_path.exists()
    
    def test_animated_delta_t_map_created(self):
        """Verify animated delta-T map file was created."""
        map_path = OUTPUT_DIR / "animated_delta_t_map.html"
        assert map_path.exists(), "Animated delta-T map file not found"
        logger.info("Animated delta-T map file created successfully")
