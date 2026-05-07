"""
Tests for zone geographic visualization module.
"""

import json
import os
import tempfile
from pathlib import Path
import pytest

from src.zone_visualization import (
    load_zone_geojson,
    load_all_zones,
    get_zone_center,
    create_zone_map,
    generate_zone_verification_report,
    ZONE_COLORS,
    ZONE_METADATA
)


class TestZoneLoading:
    """Test zone GeoJSON loading."""
    
    def test_load_zone_geojson(self):
        """Test loading a single zone GeoJSON file."""
        try:
            geojson = load_zone_geojson(1, 'public/zones')
            assert geojson is not None
            assert 'features' in geojson
            assert len(geojson['features']) > 0
        except FileNotFoundError:
            pytest.skip("Zone files not found")
    
    def test_load_all_zones(self):
        """Test loading all zone GeoJSON files."""
        try:
            zones = load_all_zones('public/zones')
            assert len(zones) > 0
            assert all(isinstance(z, dict) for z in zones.values())
        except FileNotFoundError:
            pytest.skip("Zone files not found")
    
    def test_load_nonexistent_zone(self):
        """Test loading a zone that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_zone_geojson(999, 'public/zones')


class TestZoneGeometry:
    """Test zone geometry calculations."""
    
    def test_get_zone_center(self):
        """Test calculating zone center point."""
        try:
            geojson = load_zone_geojson(1, 'public/zones')
            center = get_zone_center(geojson)
            
            assert isinstance(center, tuple)
            assert len(center) == 2
            assert -90 <= center[0] <= 90  # Latitude
            assert -180 <= center[1] <= 180  # Longitude
        except FileNotFoundError:
            pytest.skip("Zone files not found")
    
    def test_get_zone_center_empty(self):
        """Test getting center of empty GeoJSON."""
        empty_geojson = {'features': []}
        center = get_zone_center(empty_geojson)
        
        # Should return default Oregon center
        assert center == (44.0, -121.0)


class TestZoneMetadata:
    """Test zone metadata."""
    
    def test_zone_colors_defined(self):
        """Test that all zones have colors defined."""
        for zone_num in range(1, 11):
            assert zone_num in ZONE_COLORS
            assert isinstance(ZONE_COLORS[zone_num], str)
            assert ZONE_COLORS[zone_num].startswith('#')
    
    def test_zone_metadata_defined(self):
        """Test that all zones have metadata defined."""
        for zone_num in range(1, 11):
            assert zone_num in ZONE_METADATA
            metadata = ZONE_METADATA[zone_num]
            assert 'name' in metadata
            assert 'region' in metadata
            assert 'population' in metadata


class TestMapGeneration:
    """Test map generation."""
    
    def test_create_zone_map(self):
        """Test creating zone map."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_file = os.path.join(tmpdir, 'test_map.html')
                result = create_zone_map('public/zones', output_file)
                
                assert os.path.exists(result)
                assert result.endswith('.html')
                
                # Check file has content
                with open(result, 'r') as f:
                    content = f.read()
                    assert len(content) > 0
                    assert 'folium' in content.lower() or 'leaflet' in content.lower()
        except FileNotFoundError:
            pytest.skip("Zone files not found")
        except ImportError:
            pytest.skip("folium not installed")


class TestReportGeneration:
    """Test report generation."""
    
    def test_generate_zone_verification_report(self):
        """Test generating complete zone verification report."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                outputs = generate_zone_verification_report('public/zones', tmpdir)
                
                assert 'map' in outputs
                assert 'report' in outputs
                
                # Check files exist
                assert os.path.exists(outputs['map'])
                assert os.path.exists(outputs['report'])
                
                # Check report content
                with open(outputs['report'], 'r') as f:
                    content = f.read()
                    assert 'Zone Geographic Verification' in content
                    assert 'Zone Summary' in content
        except FileNotFoundError:
            pytest.skip("Zone files not found")
        except ImportError:
            pytest.skip("folium not installed")


class TestZoneCoverage:
    """Test zone coverage verification."""
    
    def test_all_zones_have_geojson(self):
        """Test that all zones have GeoJSON files."""
        try:
            zones = load_all_zones('public/zones')
            assert len(zones) == 10, f"Expected 10 zones, got {len(zones)}"
        except FileNotFoundError:
            pytest.skip("Zone files not found")
    
    def test_zone_boundaries_valid(self):
        """Test that zone boundaries are valid GeoJSON."""
        try:
            zones = load_all_zones('public/zones')
            
            for zone_num, geojson in zones.items():
                assert 'features' in geojson
                assert len(geojson['features']) > 0
                
                feature = geojson['features'][0]
                assert 'geometry' in feature
                assert 'coordinates' in feature['geometry']
                assert feature['geometry']['type'] in ['Polygon', 'MultiPolygon']
        except FileNotFoundError:
            pytest.skip("Zone files not found")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
