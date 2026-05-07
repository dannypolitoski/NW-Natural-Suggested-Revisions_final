"""
Generate zone GeoJSON files for NW Natural service territory.

Creates 10 zones covering Oregon and Southwest Washington service territory.
Zones are organized by region: NW, SW, Central, NE, Eastern.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Zone definitions with approximate boundaries for NW Natural service territory
# Coordinates are [longitude, latitude] in GeoJSON format
ZONE_DEFINITIONS = {
    1: {
        'name': 'Portland Metro',
        'region': 'NW',
        'description': 'Portland metropolitan area including Multnomah, Washington, Clackamas counties',
        'coordinates': [[
            [-123.5, 45.8],
            [-122.0, 45.8],
            [-122.0, 45.0],
            [-123.5, 45.0],
            [-123.5, 45.8]
        ]]
    },
    2: {
        'name': 'Eugene-Springfield',
        'region': 'SW',
        'description': 'Eugene-Springfield area in Lane County',
        'coordinates': [[
            [-123.5, 44.5],
            [-122.5, 44.5],
            [-122.5, 43.5],
            [-123.5, 43.5],
            [-123.5, 44.5]
        ]]
    },
    3: {
        'name': 'Salem-Keizer',
        'region': 'Central',
        'description': 'Salem-Keizer area in Marion and Polk counties',
        'coordinates': [[
            [-123.5, 45.2],
            [-122.5, 45.2],
            [-122.5, 44.5],
            [-123.5, 44.5],
            [-123.5, 45.2]
        ]]
    },
    4: {
        'name': 'Gorge Region',
        'region': 'NW',
        'description': 'Columbia River Gorge area including Hood River and Wasco counties',
        'coordinates': [[
            [-122.0, 45.8],
            [-120.5, 45.8],
            [-120.5, 45.2],
            [-122.0, 45.2],
            [-122.0, 45.8]
        ]]
    },
    5: {
        'name': 'Bend-Redmond',
        'region': 'Central',
        'description': 'Bend-Redmond area in Deschutes County',
        'coordinates': [[
            [-122.0, 44.5],
            [-120.5, 44.5],
            [-120.5, 43.5],
            [-122.0, 43.5],
            [-122.0, 44.5]
        ]]
    },
    6: {
        'name': 'Medford-Ashland',
        'region': 'SW',
        'description': 'Medford-Ashland area in Jackson County',
        'coordinates': [[
            [-123.5, 43.5],
            [-122.0, 43.5],
            [-122.0, 42.0],
            [-123.5, 42.0],
            [-123.5, 43.5]
        ]]
    },
    7: {
        'name': 'Corvallis-Albany',
        'region': 'Central',
        'description': 'Corvallis-Albany area in Benton and Linn counties',
        'coordinates': [[
            [-123.5, 44.8],
            [-122.5, 44.8],
            [-122.5, 44.2],
            [-123.5, 44.2],
            [-123.5, 44.8]
        ]]
    },
    8: {
        'name': 'Tillamook County',
        'region': 'NW',
        'description': 'Tillamook County coastal area',
        'coordinates': [[
            [-124.0, 45.5],
            [-123.5, 45.5],
            [-123.5, 45.0],
            [-124.0, 45.0],
            [-124.0, 45.5]
        ]]
    },
    9: {
        'name': 'Pendleton-La Grande',
        'region': 'NE',
        'description': 'Pendleton-La Grande area in Umatilla and Union counties',
        'coordinates': [[
            [-119.5, 45.8],
            [-118.0, 45.8],
            [-118.0, 45.0],
            [-119.5, 45.0],
            [-119.5, 45.8]
        ]]
    },
    10: {
        'name': 'Baker City',
        'region': 'Eastern',
        'description': 'Baker City area in Baker County',
        'coordinates': [[
            [-118.5, 45.0],
            [-117.5, 45.0],
            [-117.5, 44.2],
            [-118.5, 44.2],
            [-118.5, 45.0]
        ]]
    }
}


def create_zone_geojson(zone_num: int, zone_def: Dict) -> Dict:
    """
    Create a GeoJSON FeatureCollection for a zone.
    
    Args:
        zone_num: Zone number
        zone_def: Zone definition dictionary
        
    Returns:
        GeoJSON FeatureCollection
    """
    feature = {
        'type': 'Feature',
        'properties': {
            'zone_id': zone_num,
            'name': zone_def['name'],
            'region': zone_def['region'],
            'description': zone_def['description']
        },
        'geometry': {
            'type': 'Polygon',
            'coordinates': zone_def['coordinates']
        }
    }
    
    geojson = {
        'type': 'FeatureCollection',
        'features': [feature]
    }
    
    return geojson


def generate_all_zones(output_dir: str = 'public/zones') -> Dict[int, str]:
    """
    Generate all zone GeoJSON files.
    
    Args:
        output_dir: Directory to save zone files
        
    Returns:
        Dictionary mapping zone_num to file path
    """
    os.makedirs(output_dir, exist_ok=True)
    
    outputs = {}
    
    for zone_num, zone_def in ZONE_DEFINITIONS.items():
        geojson = create_zone_geojson(zone_num, zone_def)
        
        output_file = os.path.join(output_dir, f'zone_{zone_num}.geojson')
        
        with open(output_file, 'w') as f:
            json.dump(geojson, f, indent=2)
        
        outputs[zone_num] = output_file
        print(f"Created {output_file}")
    
    return outputs


if __name__ == '__main__':
    outputs = generate_all_zones()
    print(f"\nGenerated {len(outputs)} zone files in public/zones/")
