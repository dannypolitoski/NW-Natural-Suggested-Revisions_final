"""
Visualization module for housing stock projections.

Provides functions to generate comparison plots showing actual vs projected
housing stock data, including total units, segment distribution, and district
distribution over time, plus a choropleth map of the service territory.
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for testing and server environments
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)


def plot_housing_stock_comparison(
    baseline_year: int,
    baseline_total: int,
    projected_data: Dict[int, int],
    title: str = "Housing Stock Projection: Actual vs Projected",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6)
) -> plt.Figure:
    """
    Generate a line plot comparing baseline (actual) vs projected housing stock.
    
    Args:
        baseline_year: The year of the baseline (actual) data
        baseline_total: Total units in baseline year
        projected_data: Dictionary mapping year to projected total units
        title: Title for the plot
        output_path: Optional path to save the figure (e.g., 'output/projection.png')
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    
    Example:
        >>> baseline_year = 2025
        >>> baseline_total = 100
        >>> projected = {2026: 102, 2027: 104, 2028: 106}
        >>> fig = plot_housing_stock_comparison(baseline_year, baseline_total, projected)
        >>> fig.savefig('projection.png')
    """
    # Prepare data
    years = sorted([baseline_year] + list(projected_data.keys()))
    totals = [baseline_total] + [projected_data[y] for y in years[1:]]
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot baseline and projected
    baseline_years = [baseline_year]
    baseline_totals = [baseline_total]
    
    projected_years = sorted(projected_data.keys())
    projected_totals = [projected_data[y] for y in projected_years]
    
    # Plot actual baseline as a point
    ax.scatter(baseline_years, baseline_totals, s=100, color='darkblue', 
               label='Actual (Baseline)', zorder=5, marker='o')
    
    # Plot projected line
    ax.plot(projected_years, projected_totals, 'o-', color='darkgreen', 
            linewidth=2, markersize=6, label='Projected')
    
    # Add grid and labels
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Total Housing Units', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(fontsize=11, loc='best')
    
    # Format y-axis as integers
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved housing stock comparison plot to {output_path}")
    
    plt.close(fig)
    return fig


def plot_segment_distribution_comparison(
    baseline_year: int,
    baseline_segments: Dict[str, int],
    projected_segments: Dict[int, Dict[str, int]],
    title: str = "Housing Stock by Segment: Actual vs Projected",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 6)
) -> plt.Figure:
    """
    Generate a grouped bar chart comparing segment distribution over time.
    
    Args:
        baseline_year: The year of the baseline (actual) data
        baseline_segments: Dict mapping segment code to unit count (baseline)
        projected_segments: Dict mapping year to dict of segment codes to unit counts
        title: Title for the plot
        output_path: Optional path to save the figure
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    
    Example:
        >>> baseline_segments = {'RESSF': 70, 'RESMF': 30}
        >>> projected = {
        ...     2026: {'RESSF': 71, 'RESMF': 31},
        ...     2027: {'RESSF': 72, 'RESMF': 32}
        ... }
        >>> fig = plot_segment_distribution_comparison(2025, baseline_segments, projected)
    """
    # Prepare data
    years = sorted([baseline_year] + list(projected_segments.keys()))
    segments = sorted(set(baseline_segments.keys()) | 
                     set().union(*[set(v.keys()) for v in projected_segments.values()]))
    
    # Create data matrix
    data = {}
    for segment in segments:
        data[segment] = []
        for year in years:
            if year == baseline_year:
                data[segment].append(baseline_segments.get(segment, 0))
            else:
                data[segment].append(projected_segments[year].get(segment, 0))
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Set up bar positions
    x = np.arange(len(years))
    width = 0.8 / len(segments)
    colors = plt.cm.Set3(np.linspace(0, 1, len(segments)))
    
    # Plot bars for each segment
    for i, segment in enumerate(segments):
        offset = width * (i - len(segments) / 2 + 0.5)
        ax.bar(x + offset, data[segment], width, label=segment, color=colors[i])
    
    # Add grid and labels
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Housing Units', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(fontsize=11, loc='best')
    
    # Format y-axis as integers
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved segment distribution plot to {output_path}")
    
    plt.close(fig)
    return fig


def plot_district_distribution_comparison(
    baseline_year: int,
    baseline_districts: Dict[str, int],
    projected_districts: Dict[int, Dict[str, int]],
    title: str = "Housing Stock by District: Actual vs Projected",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 6)
) -> plt.Figure:
    """
    Generate a grouped bar chart comparing district distribution over time.
    
    Args:
        baseline_year: The year of the baseline (actual) data
        baseline_districts: Dict mapping district code to unit count (baseline)
        projected_districts: Dict mapping year to dict of district codes to unit counts
        title: Title for the plot
        output_path: Optional path to save the figure
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    """
    # Prepare data
    years = sorted([baseline_year] + list(projected_districts.keys()))
    districts = sorted(set(baseline_districts.keys()) | 
                      set().union(*[set(v.keys()) for v in projected_districts.values()]))
    
    # Create data matrix
    data = {}
    for district in districts:
        data[district] = []
        for year in years:
            if year == baseline_year:
                data[district].append(baseline_districts.get(district, 0))
            else:
                data[district].append(projected_districts[year].get(district, 0))
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Set up bar positions
    x = np.arange(len(years))
    width = 0.8 / len(districts)
    colors = plt.cm.Set2(np.linspace(0, 1, len(districts)))
    
    # Plot bars for each district
    for i, district in enumerate(districts):
        offset = width * (i - len(districts) / 2 + 0.5)
        ax.bar(x + offset, data[district], width, label=district, color=colors[i])
    
    # Add grid and labels
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Housing Units', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.legend(fontsize=11, loc='best')
    
    # Format y-axis as integers
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved district distribution plot to {output_path}")
    
    plt.close(fig)
    return fig


def plot_growth_rate_analysis(
    baseline_year: int,
    baseline_total: int,
    projected_data: Dict[int, int],
    growth_rate: float,
    title: str = "Housing Stock Growth Rate Analysis",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6)
) -> plt.Figure:
    """
    Generate a plot showing actual vs expected growth based on growth rate.
    
    Args:
        baseline_year: The year of the baseline (actual) data
        baseline_total: Total units in baseline year
        projected_data: Dictionary mapping year to projected total units
        growth_rate: Annual growth rate used for projection
        title: Title for the plot
        output_path: Optional path to save the figure
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    """
    # Prepare data
    projected_years = sorted(projected_data.keys())
    projected_totals = [projected_data[y] for y in projected_years]
    
    # Calculate expected values based on growth rate
    expected_totals = [
        int(round(baseline_total * ((1 + growth_rate) ** (y - baseline_year))))
        for y in projected_years
    ]
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot projected vs expected
    ax.plot(projected_years, projected_totals, 'o-', color='darkgreen', 
            linewidth=2, markersize=8, label='Projected (from scenario)')
    ax.plot(projected_years, expected_totals, 's--', color='darkred', 
            linewidth=2, markersize=8, label=f'Expected (r={growth_rate:.2%})')
    
    # Add grid and labels
    ax.grid(True, alpha=0.3)
    ax.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax.set_ylabel('Total Housing Units', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(fontsize=11, loc='best')
    
    # Format y-axis as integers
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved growth rate analysis plot to {output_path}")
    
    plt.close(fig)
    return fig


def plot_service_territory_map(
    baseline_year: int,
    baseline_stock,
    projected_stocks: Dict[int, 'HousingStock'],
    growth_rate: float,
    title: str = "NW Natural Service Territory: Projected Housing Growth Rate",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 10)
) -> plt.Figure:
    """
    Generate a choropleth map of NW Natural service territory by county.
    
    Color-codes counties by projected housing growth rate (low/medium/high).
    Includes district boundaries and weather station locations.
    
    Args:
        baseline_year: The year of the baseline (actual) data
        baseline_stock: HousingStock object for baseline year
        projected_stocks: Dict mapping year to HousingStock object
        growth_rate: Annual growth rate used for projection
        title: Title for the plot
        output_path: Optional path to save the figure
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    """
    # NW Natural service territory: 16 counties (13 Oregon, 3 Washington)
    # County FIPS codes and names
    counties_data = {
        # Oregon counties
        'Multnomah': {'state': 'OR', 'fips': 41051, 'lat': 45.5, 'lon': -122.7},
        'Washington': {'state': 'OR', 'fips': 41067, 'lat': 45.4, 'lon': -123.2},
        'Clackamas': {'state': 'OR', 'fips': 41005, 'lat': 45.2, 'lon': -122.5},
        'Lane': {'state': 'OR', 'fips': 41039, 'lat': 44.0, 'lon': -123.1},
        'Marion': {'state': 'OR', 'fips': 41047, 'lat': 44.8, 'lon': -123.0},
        'Yamhill': {'state': 'OR', 'fips': 41071, 'lat': 45.2, 'lon': -123.5},
        'Polk': {'state': 'OR', 'fips': 41053, 'lat': 44.8, 'lon': -123.3},
        'Benton': {'state': 'OR', 'fips': 41003, 'lat': 44.6, 'lon': -123.3},
        'Linn': {'state': 'OR', 'fips': 41043, 'lat': 44.5, 'lon': -122.8},
        'Columbia': {'state': 'OR', 'fips': 41009, 'lat': 46.2, 'lon': -123.4},
        'Clatsop': {'state': 'OR', 'fips': 41007, 'lat': 46.1, 'lon': -123.8},
        'Lincoln': {'state': 'OR', 'fips': 41041, 'lat': 44.6, 'lon': -124.0},
        'Coos': {'state': 'OR', 'fips': 41011, 'lat': 43.3, 'lon': -124.2},
        # Washington counties
        'Clark': {'state': 'WA', 'fips': 53011, 'lat': 45.8, 'lon': -122.5},
        'Skamania': {'state': 'WA', 'fips': 53059, 'lat': 45.8, 'lon': -121.8},
        'Klickitat': {'state': 'WA', 'fips': 53039, 'lat': 45.7, 'lon': -121.3},
    }
    
    # Weather stations: 11 stations with approximate coordinates
    weather_stations = {
        'KPDX': {'name': 'Portland', 'lat': 45.59, 'lon': -122.60},
        'KEUG': {'name': 'Eugene', 'lat': 44.12, 'lon': -123.21},
        'KSLE': {'name': 'Salem', 'lat': 44.90, 'lon': -123.00},
        'KAST': {'name': 'Astoria', 'lat': 46.16, 'lon': -123.88},
        'KDLS': {'name': 'The Dalles', 'lat': 45.60, 'lon': -121.31},
        'KOTH': {'name': 'North Bend', 'lat': 43.41, 'lon': -124.25},
        'KONP': {'name': 'Newport', 'lat': 44.58, 'lon': -124.06},
        'KCVO': {'name': 'Corvallis', 'lat': 44.50, 'lon': -123.30},
        'KHIO': {'name': 'Hillsboro', 'lat': 45.54, 'lon': -122.99},
        'KTTD': {'name': 'Troutdale', 'lat': 45.56, 'lon': -122.40},
        'KVUO': {'name': 'Vancouver', 'lat': 45.59, 'lon': -122.66},
    }
    
    # Calculate growth rates by county (simplified: use overall growth rate)
    # In a real implementation, this would be based on county-level projections
    growth_categories = {}
    for county in counties_data.keys():
        # Categorize growth rate
        if growth_rate < -0.01:
            growth_categories[county] = 'Low'
        elif growth_rate < 0.01:
            growth_categories[county] = 'Medium'
        else:
            growth_categories[county] = 'High'
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Define color map for growth categories
    color_map = {'Low': '#d73027', 'Medium': '#fee090', 'High': '#1a9850'}
    
    # Plot counties as scatter points (simplified representation)
    for county, data in counties_data.items():
        category = growth_categories[county]
        color = color_map[category]
        ax.scatter(data['lon'], data['lat'], s=500, c=color, alpha=0.7, 
                  edgecolors='black', linewidth=1.5, zorder=3)
        ax.text(data['lon'], data['lat'], county[:3], ha='center', va='center',
               fontsize=8, fontweight='bold', zorder=4)
    
    # Plot weather stations
    for station_code, station_data in weather_stations.items():
        ax.scatter(station_data['lon'], station_data['lat'], s=100, c='blue', 
                  marker='^', alpha=0.8, edgecolors='darkblue', linewidth=1, zorder=5)
        ax.text(station_data['lon'], station_data['lat'] + 0.15, station_code, 
               ha='center', va='bottom', fontsize=7, color='blue', fontweight='bold', zorder=5)
    
    # Set map extent (NW Natural service territory)
    ax.set_xlim(-124.5, -121.0)
    ax.set_ylim(43.0, 46.5)
    
    # Add grid
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Labels and title
    ax.set_xlabel('Longitude', fontsize=11, fontweight='bold')
    ax.set_ylabel('Latitude', fontsize=11, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    
    # Create legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#d73027', edgecolor='black', label='Low Growth (< -1%)'),
        Patch(facecolor='#fee090', edgecolor='black', label='Medium Growth (-1% to 1%)'),
        Patch(facecolor='#1a9850', edgecolor='black', label='High Growth (> 1%)'),
        plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='blue', 
                  markersize=8, label='Weather Stations', markeredgecolor='darkblue'),
    ]
    ax.legend(handles=legend_elements, fontsize=10, loc='upper left')
    
    # Add note about projection
    note_text = f"Growth Rate: {growth_rate:.2%}/year | Baseline Year: {baseline_year}"
    ax.text(0.5, -0.08, note_text, transform=ax.transAxes, 
           ha='center', fontsize=10, style='italic', color='gray')
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved service territory map to {output_path}")
    
    plt.close(fig)
    return fig


def plot_projection_summary(
    baseline_year: int,
    baseline_stock,
    projected_stocks: Dict[int, 'HousingStock'],
    growth_rate: float,
    output_dir: str = "output",
    show_plots: bool = False
) -> Dict[str, str]:
    """
    Generate a comprehensive set of comparison plots and save to output directory.
    
    Args:
        baseline_year: The year of the baseline (actual) data
        baseline_stock: HousingStock object for baseline year
        projected_stocks: Dict mapping year to HousingStock object
        growth_rate: Annual growth rate used for projection
        output_dir: Directory to save plots
        show_plots: Whether to display plots (plt.show())
    
    Returns:
        Dictionary mapping plot name to file path
    
    Example:
        >>> baseline = HousingStock(year=2025, ...)
        >>> projected = {2026: HousingStock(...), 2027: HousingStock(...)}
        >>> plots = plot_projection_summary(2025, baseline, projected, 0.02, 'output')
    """
    import os
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepare data dictionaries
    projected_totals = {year: stock.total_units for year, stock in projected_stocks.items()}
    projected_segments = {year: stock.units_by_segment for year, stock in projected_stocks.items()}
    projected_districts = {year: stock.units_by_district for year, stock in projected_stocks.items()}
    
    # Generate plots
    plots = {}
    
    # 1. Total housing stock comparison
    fig1 = plot_housing_stock_comparison(
        baseline_year, baseline_stock.total_units, projected_totals,
        output_path=os.path.join(output_dir, "01_total_housing_stock.png")
    )
    plots['total_housing_stock'] = os.path.join(output_dir, "01_total_housing_stock.png")
    
    # 2. Segment distribution comparison
    fig2 = plot_segment_distribution_comparison(
        baseline_year, baseline_stock.units_by_segment, projected_segments,
        output_path=os.path.join(output_dir, "02_segment_distribution.png")
    )
    plots['segment_distribution'] = os.path.join(output_dir, "02_segment_distribution.png")
    
    # 3. District distribution comparison
    fig3 = plot_district_distribution_comparison(
        baseline_year, baseline_stock.units_by_district, projected_districts,
        output_path=os.path.join(output_dir, "03_district_distribution.png")
    )
    plots['district_distribution'] = os.path.join(output_dir, "03_district_distribution.png")
    
    # 4. Growth rate analysis
    fig4 = plot_growth_rate_analysis(
        baseline_year, baseline_stock.total_units, projected_totals, growth_rate,
        output_path=os.path.join(output_dir, "04_growth_rate_analysis.png")
    )
    plots['growth_rate_analysis'] = os.path.join(output_dir, "04_growth_rate_analysis.png")
    
    # 5. Service territory map (CRITICAL - MISSING)
    fig5 = plot_service_territory_map(
        baseline_year, baseline_stock, projected_stocks, growth_rate,
        output_path=os.path.join(output_dir, "05_service_territory_map.png")
    )
    plots['service_territory_map'] = os.path.join(output_dir, "05_service_territory_map.png")
    
    # Show plots if requested
    if show_plots:
        plt.show()
    
    logger.info(f"Generated {len(plots)} comparison plots in {output_dir}")
    
    return plots


def plot_electrification_map(
    district_electrification_rates: Dict[str, float],
    title: str = "Equipment Electrification Rate by District",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 10)
) -> plt.Figure:
    """
    Generate a map showing electrification rates by district with OpenStreetMap background.
    
    Color-codes districts by electrification rate (% of gas equipment converted to electric).
    Includes district boundaries and major cities.
    
    Args:
        district_electrification_rates: Dict mapping district code to electrification rate [0, 1]
        title: Title for the plot
        output_path: Optional path to save the figure
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    """
    try:
        import contextily as ctx
    except ImportError:
        logger.warning("contextily not installed; using simple map without OSM base layer")
        ctx = None
    
    # NW Natural districts with approximate centroids and boundaries
    districts_data = {
        'D1': {'lat': 45.5, 'lon': -122.7, 'name': 'Portland Metro'},
        'D2': {'lat': 44.8, 'lon': -123.0, 'name': 'Salem/Marion'},
        'D3': {'lat': 44.0, 'lon': -123.1, 'name': 'Eugene/Lane'},
        'D4': {'lat': 45.2, 'lon': -123.2, 'name': 'Willamette Valley'},
        'D5': {'lat': 44.6, 'lon': -123.3, 'name': 'Corvallis/Benton'},
        'D6': {'lat': 46.1, 'lon': -123.8, 'name': 'Coast/Clatsop'},
        'D7': {'lat': 45.8, 'lon': -122.5, 'name': 'Vancouver/Clark'},
        'D8': {'lat': 45.7, 'lon': -121.3, 'name': 'Gorge/Klickitat'},
    }
    
    # Major cities for reference
    cities = {
        'Portland': {'lat': 45.52, 'lon': -122.68},
        'Salem': {'lat': 44.94, 'lon': -123.04},
        'Eugene': {'lat': 44.05, 'lon': -123.09},
        'Corvallis': {'lat': 44.56, 'lon': -123.27},
        'Astoria': {'lat': 46.19, 'lon': -123.88},
        'Vancouver': {'lat': 45.64, 'lon': -122.66},
    }
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Add OpenStreetMap base layer if contextily available
    if ctx is not None:
        try:
            ax.set_xlim(-124.5, -121.0)
            ax.set_ylim(43.0, 46.5)
            ctx.add_basemap(ax, crs='EPSG:4326', source=ctx.providers.OpenStreetMap.Mapnik, 
                           zoom=8, alpha=0.4)
        except Exception as e:
            logger.warning(f"Failed to add OSM base layer: {e}")
            ax.set_facecolor('#e6e6e6')
    else:
        ax.set_facecolor('#e6e6e6')
        ax.set_xlim(-124.5, -121.0)
        ax.set_ylim(43.0, 46.5)
    
    # Define color map for electrification rates (red=low, yellow=medium, green=high)
    def get_color(rate):
        if rate < 0.1:
            return '#d73027'  # Red: low electrification
        elif rate < 0.3:
            return '#fee090'  # Yellow: medium electrification
        else:
            return '#1a9850'  # Green: high electrification
    
    # Plot districts
    for district_code, data in districts_data.items():
        if district_code in district_electrification_rates:
            rate = district_electrification_rates[district_code]
            color = get_color(rate)
            
            # Plot district as circle
            ax.scatter(data['lon'], data['lat'], s=1200, c=color, alpha=0.7, 
                      edgecolors='black', linewidth=2, zorder=10, marker='o')
            
            # Add district label and rate
            ax.text(data['lon'], data['lat'] + 0.05, district_code, ha='center', va='center',
                   fontsize=11, fontweight='bold', zorder=11, color='black')
            ax.text(data['lon'], data['lat'] - 0.05, f'{rate:.1%}', ha='center', va='center',
                   fontsize=9, fontweight='bold', zorder=11, color='black')
    
    # Plot cities for reference
    for city_name, city_data in cities.items():
        ax.scatter(city_data['lon'], city_data['lat'], s=80, c='gray', 
                  marker='s', alpha=0.6, edgecolors='darkgray', linewidth=1, zorder=5)
        ax.text(city_data['lon'], city_data['lat'] - 0.15, city_name, 
               ha='center', va='top', fontsize=8, color='gray', fontweight='bold', zorder=5)
    
    # Add grid
    ax.grid(True, alpha=0.2, linestyle='--', zorder=1)
    
    # Labels and title
    ax.set_xlabel('Longitude', fontsize=12, fontweight='bold')
    ax.set_ylabel('Latitude', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=15, fontweight='bold', pad=20)
    
    # Create legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#d73027', edgecolor='black', label='Low Electrification (< 10%)', linewidth=1.5),
        Patch(facecolor='#fee090', edgecolor='black', label='Medium Electrification (10-30%)', linewidth=1.5),
        Patch(facecolor='#1a9850', edgecolor='black', label='High Electrification (> 30%)', linewidth=1.5),
        plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='gray', 
                  markersize=8, label='Major Cities', markeredgecolor='darkgray', markeredgewidth=1),
    ]
    ax.legend(handles=legend_elements, fontsize=11, loc='upper left', framealpha=0.95)
    
    # Add note
    note_text = "Electrification Rate: % of gas equipment converted to electric\nMap shows NW Natural service territory with OpenStreetMap background"
    ax.text(0.5, -0.12, note_text, transform=ax.transAxes, 
           ha='center', fontsize=10, style='italic', color='#333333',
           bbox=dict(boxstyle='round,pad=0.8', facecolor='lightyellow', alpha=0.8))
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved electrification map to {output_path}")
    
    plt.close(fig)
    return fig


def plot_housing_age_heatmap(
    housing_age_by_district: Dict[str, float],
    title: str = "Average Housing Age by District",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 8)
) -> plt.Figure:
    """
    Generate a heatmap showing average housing age by district.
    
    Color intensity represents age (blue=new, red=old).
    
    Args:
        housing_age_by_district: Dict mapping district code to average age (years)
        title: Title for the plot
        output_path: Optional path to save the figure
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Prepare data
    districts = sorted(housing_age_by_district.keys())
    ages = [housing_age_by_district[d] for d in districts]
    
    # Create bar chart with color gradient
    colors = plt.cm.RdYlBu_r(np.linspace(0, 1, len(ages)))
    bars = ax.bar(districts, ages, color=colors, edgecolor='black', linewidth=1.5)
    
    # Add value labels on bars
    for bar, age in zip(bars, ages):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{age:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Labels and title
    ax.set_xlabel('District', fontsize=12, fontweight='bold')
    ax.set_ylabel('Average Housing Age (years)', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved housing age heatmap to {output_path}")
    
    plt.close(fig)
    return fig


def plot_vintage_distribution_heatmap(
    vintage_distribution_by_district: Dict[str, Dict[str, float]],
    title: str = "Housing Vintage Distribution by District",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 8)
) -> plt.Figure:
    """
    Generate a heatmap showing housing vintage distribution by district.
    
    Rows are districts, columns are vintage eras (pre-1980, 1980-2000, 2000-2010, 2010+).
    Color intensity represents percentage of homes in that era.
    
    Args:
        vintage_distribution_by_district: Dict mapping district to vintage percentages
        title: Title for the plot
        output_path: Optional path to save the figure
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Prepare data
    districts = sorted(vintage_distribution_by_district.keys())
    eras = ['pre-1980', '1980-2000', '2000-2010', '2010+']
    
    # Create matrix
    data = []
    for district in districts:
        row = [vintage_distribution_by_district[district].get(era, 0) for era in eras]
        data.append(row)
    
    data_array = np.array(data)
    
    # Create heatmap
    im = ax.imshow(data_array, cmap='YlOrRd', aspect='auto')
    
    # Set ticks and labels
    ax.set_xticks(np.arange(len(eras)))
    ax.set_yticks(np.arange(len(districts)))
    ax.set_xticklabels(eras)
    ax.set_yticklabels(districts)
    
    # Rotate x labels
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    
    # Add text annotations
    for i in range(len(districts)):
        for j in range(len(eras)):
            text = ax.text(j, i, f'{data_array[i, j]:.1%}',
                          ha="center", va="center", color="black", fontsize=9, fontweight='bold')
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Percentage of Homes', rotation=270, labelpad=20, fontweight='bold')
    
    # Labels and title
    ax.set_xlabel('Vintage Era', fontsize=12, fontweight='bold')
    ax.set_ylabel('District', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved vintage distribution heatmap to {output_path}")
    
    plt.close(fig)
    return fig


def plot_replacement_probability_map(
    replacement_probability_by_district: Dict[str, float],
    title: str = "Equipment Replacement Probability by District",
    output_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 8)
) -> plt.Figure:
    """
    Generate a map showing equipment replacement probability by district.
    
    Color intensity represents replacement likelihood (blue=low, red=high).
    
    Args:
        replacement_probability_by_district: Dict mapping district to replacement probability [0,1]
        title: Title for the plot
        output_path: Optional path to save the figure
        figsize: Figure size as (width, height) tuple
    
    Returns:
        matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    # Prepare data
    districts = sorted(replacement_probability_by_district.keys())
    probs = [replacement_probability_by_district[d] for d in districts]
    
    # Create bar chart with color gradient (blue to red)
    colors = plt.cm.RdYlBu_r(np.linspace(0, 1, len(probs)))
    bars = ax.bar(districts, probs, color=colors, edgecolor='black', linewidth=1.5)
    
    # Add value labels on bars
    for bar, prob in zip(bars, probs):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{prob:.1%}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Labels and title
    ax.set_xlabel('District', fontsize=12, fontweight='bold')
    ax.set_ylabel('Replacement Probability', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylim(0, 1.0)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Tight layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        logger.info(f"Saved replacement probability map to {output_path}")
    
    plt.close(fig)
    return fig


def plot_housing_stock_composition(
    baseline_stock,
    projected_stocks: Dict[int, 'HousingStock'],
    output_dir: str = "output",
    show_plots: bool = False
) -> Dict[str, str]:
    """
    Generate housing stock composition visualizations.
    
    Includes:
    - Stacked bar chart: Housing vintage distribution by district
    - Box plot: Housing age distribution by district
    - Scatter plot: Average housing age vs. projected growth rate by district
    - Heatmap: Percentage of homes by vintage era and district
    
    Args:
        baseline_stock: HousingStock object for baseline year
        projected_stocks: Dict mapping year to HousingStock object
        output_dir: Directory to save plots
        show_plots: Whether to display plots
    
    Returns:
        Dictionary mapping plot name to file path
    """
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    plots = {}
    
    # 1. Stacked bar chart: Housing vintage distribution by district
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    
    districts = sorted(baseline_stock.vintage_distribution_by_district.keys())
    eras = ['pre-1980', '1980-2000', '2000-2010', '2010+']
    
    # Prepare data
    data_by_era = {era: [] for era in eras}
    for district in districts:
        for era in eras:
            data_by_era[era].append(baseline_stock.vintage_distribution_by_district[district].get(era, 0))
    
    # Create stacked bar chart
    bottom = np.zeros(len(districts))
    colors = ['#d73027', '#fee090', '#91bfdb', '#4575b4']
    
    for era, color in zip(eras, colors):
        ax1.bar(districts, data_by_era[era], bottom=bottom, label=era, color=color, edgecolor='black', linewidth=0.5)
        bottom += np.array(data_by_era[era])
    
    ax1.set_xlabel('District', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Percentage of Homes', fontsize=12, fontweight='bold')
    ax1.set_title('Housing Vintage Distribution by District', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=10)
    ax1.set_ylim(0, 1.0)
    ax1.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    path1 = os.path.join(output_dir, "06_vintage_distribution_stacked.png")
    fig1.savefig(path1, dpi=300, bbox_inches='tight')
    plots['vintage_distribution_stacked'] = path1
    plt.close(fig1)
    
    # 2. Box plot: Housing age distribution by district
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    
    ages = [baseline_stock.housing_age_by_district.get(d, 35) for d in districts]
    ax2.boxplot([ages], tick_labels=['All Districts'])
    ax2.set_ylabel('Housing Age (years)', fontsize=12, fontweight='bold')
    ax2.set_title('Housing Age Distribution by District', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    path2 = os.path.join(output_dir, "07_housing_age_distribution.png")
    fig2.savefig(path2, dpi=300, bbox_inches='tight')
    plots['housing_age_distribution'] = path2
    plt.close(fig2)
    
    # 3. Scatter plot: Average housing age vs. replacement probability
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    
    ages_list = [baseline_stock.housing_age_by_district.get(d, 35) for d in districts]
    probs_list = [baseline_stock.replacement_probability_by_district.get(d, 0.15) for d in districts]
    
    ax3.scatter(ages_list, probs_list, s=100, alpha=0.6, edgecolors='black', linewidth=1)
    
    # Add district labels
    for i, district in enumerate(districts):
        ax3.annotate(district, (ages_list[i], probs_list[i]), fontsize=8, ha='right')
    
    ax3.set_xlabel('Average Housing Age (years)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Replacement Probability', fontsize=12, fontweight='bold')
    ax3.set_title('Housing Age vs. Replacement Probability by District', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    path3 = os.path.join(output_dir, "08_age_vs_replacement.png")
    fig3.savefig(path3, dpi=300, bbox_inches='tight')
    plots['age_vs_replacement'] = path3
    plt.close(fig3)
    
    # 4. Heatmap: Percentage of homes by vintage era and district
    fig4, ax4 = plt.subplots(figsize=(10, 8))
    
    data = []
    for district in districts:
        row = [baseline_stock.vintage_distribution_by_district[district].get(era, 0) for era in eras]
        data.append(row)
    
    data_array = np.array(data)
    im = ax4.imshow(data_array, cmap='YlOrRd', aspect='auto')
    
    ax4.set_xticks(np.arange(len(eras)))
    ax4.set_yticks(np.arange(len(districts)))
    ax4.set_xticklabels(eras)
    ax4.set_yticklabels(districts)
    
    plt.setp(ax4.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    
    for i in range(len(districts)):
        for j in range(len(eras)):
            text = ax4.text(j, i, f'{data_array[i, j]:.1%}',
                          ha="center", va="center", color="black", fontsize=8, fontweight='bold')
    
    cbar = plt.colorbar(im, ax=ax4)
    cbar.set_label('Percentage', rotation=270, labelpad=20, fontweight='bold')
    
    ax4.set_xlabel('Vintage Era', fontsize=12, fontweight='bold')
    ax4.set_ylabel('District', fontsize=12, fontweight='bold')
    ax4.set_title('Housing Vintage Distribution Heatmap', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    path4 = os.path.join(output_dir, "09_vintage_heatmap.png")
    fig4.savefig(path4, dpi=300, bbox_inches='tight')
    plots['vintage_heatmap'] = path4
    plt.close(fig4)
    
    logger.info(f"Generated {len(plots)} housing stock composition plots in {output_dir}")
    
    return plots


def plot_replacement_risk_analysis(
    baseline_stock,
    projected_stocks: Dict[int, 'HousingStock'],
    output_dir: str = "output",
    show_plots: bool = False
) -> Dict[str, str]:
    """
    Generate replacement risk analysis visualizations.
    
    Includes:
    - Line graph: Cumulative replacement probability over time by district
    - Box plot: Distribution of replacement probabilities across all districts
    - Scatter plot: Housing age vs. replacement probability by district
    - Bar chart: Replacement likelihood ranking of top 10 districts
    
    Args:
        baseline_stock: HousingStock object for baseline year
        projected_stocks: Dict mapping year to HousingStock object
        output_dir: Directory to save plots
        show_plots: Whether to display plots
    
    Returns:
        Dictionary mapping plot name to file path
    """
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    plots = {}
    
    # 1. Line graph: Cumulative replacement probability over time by district
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    
    years = sorted([baseline_stock.year] + list(projected_stocks.keys()))
    districts = sorted(baseline_stock.replacement_probability_by_district.keys())
    
    for district in districts[:5]:  # Plot first 5 districts for clarity
        probs = []
        for year in years:
            if year == baseline_stock.year:
                prob = baseline_stock.replacement_probability_by_district.get(district, 0.15)
            else:
                prob = projected_stocks[year].replacement_probability_by_district.get(district, 0.15)
            probs.append(prob)
        
        ax1.plot(years, probs, marker='o', label=district, linewidth=2)
    
    ax1.set_xlabel('Year', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Replacement Probability', fontsize=12, fontweight='bold')
    ax1.set_title('Cumulative Replacement Probability Over Time', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=10, loc='best')
    ax1.grid(True, alpha=0.3)
    
    plt.tight_layout()
    path1 = os.path.join(output_dir, "10_cumulative_replacement.png")
    fig1.savefig(path1, dpi=300, bbox_inches='tight')
    plots['cumulative_replacement'] = path1
    plt.close(fig1)
    
    # 2. Box plot: Distribution of replacement probabilities across all districts
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    
    probs_list = [baseline_stock.replacement_probability_by_district.get(d, 0.15) for d in districts]
    ax2.boxplot([probs_list], tick_labels=['All Districts'])
    ax2.set_ylabel('Replacement Probability', fontsize=12, fontweight='bold')
    ax2.set_title('Distribution of Replacement Probabilities Across Districts', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    path2 = os.path.join(output_dir, "11_replacement_distribution.png")
    fig2.savefig(path2, dpi=300, bbox_inches='tight')
    plots['replacement_distribution'] = path2
    plt.close(fig2)
    
    # 3. Scatter plot: Housing age vs. replacement probability by district
    fig3, ax3 = plt.subplots(figsize=(10, 6))
    
    ages_list = [baseline_stock.housing_age_by_district.get(d, 35) for d in districts]
    probs_list = [baseline_stock.replacement_probability_by_district.get(d, 0.15) for d in districts]
    
    ax3.scatter(ages_list, probs_list, s=100, alpha=0.6, edgecolors='black', linewidth=1)
    
    for i, district in enumerate(districts):
        ax3.annotate(district, (ages_list[i], probs_list[i]), fontsize=8, ha='right')
    
    ax3.set_xlabel('Average Housing Age (years)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Replacement Probability', fontsize=12, fontweight='bold')
    ax3.set_title('Housing Age vs. Replacement Probability', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    path3 = os.path.join(output_dir, "12_age_vs_replacement_scatter.png")
    fig3.savefig(path3, dpi=300, bbox_inches='tight')
    plots['age_vs_replacement_scatter'] = path3
    plt.close(fig3)
    
    # 4. Bar chart: Replacement likelihood ranking of top 10 districts
    fig4, ax4 = plt.subplots(figsize=(12, 6))
    
    # Sort districts by replacement probability
    sorted_districts = sorted(districts, key=lambda d: baseline_stock.replacement_probability_by_district.get(d, 0.15), reverse=True)[:10]
    sorted_probs = [baseline_stock.replacement_probability_by_district.get(d, 0.15) for d in sorted_districts]
    
    colors = plt.cm.RdYlBu_r(np.linspace(0, 1, len(sorted_probs)))
    bars = ax4.barh(sorted_districts, sorted_probs, color=colors, edgecolor='black', linewidth=1.5)
    
    for bar, prob in zip(bars, sorted_probs):
        width = bar.get_width()
        ax4.text(width, bar.get_y() + bar.get_height()/2.,
                f'{prob:.1%}', ha='left', va='center', fontsize=9, fontweight='bold')
    
    ax4.set_xlabel('Replacement Probability', fontsize=12, fontweight='bold')
    ax4.set_title('Top 10 Districts by Replacement Likelihood', fontsize=14, fontweight='bold')
    ax4.set_xlim(0, max(sorted_probs) * 1.15)
    ax4.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    path4 = os.path.join(output_dir, "13_replacement_ranking.png")
    fig4.savefig(path4, dpi=300, bbox_inches='tight')
    plots['replacement_ranking'] = path4
    plt.close(fig4)
    
    logger.info(f"Generated {len(plots)} replacement risk analysis plots in {output_dir}")
    
    return plots



# ============================================================================
# TASK 2.3.7: Segment/Subsegment/Market Relationship Visualization
# ============================================================================

def generate_segment_profiles(premise_equipment: pd.DataFrame) -> Dict:
    """
    Compute detailed equipment and age statistics per segment/subsegment/market.
    
    Generates comprehensive profiles including:
    - Premise count and % of total
    - Average premise age (construction year)
    - Equipment inventory by end-use (count and %)
    - Top 5 equipment types with counts
    - Average equipment age by end-use (with min/max range)
    - Average efficiency by end-use
    - Fuel type mix (% gas vs electric)
    - Dominant building characteristics
    
    Args:
        premise_equipment: DataFrame from build_premise_equipment_table with columns:
            - blinded_id: Premise identifier
            - segment_code: Customer segment (RESSF, RESMF, MOBILE)
            - district_code_IRP: Geographic district
            - end_use: End-use category
            - efficiency: Equipment efficiency [0, 1]
            - equipment_type_code: Equipment code
            - (optional) premise_age: Construction year
            - (optional) equipment_age: Equipment installation year
            - (optional) fuel_type: Gas or electric
    
    Returns:
        Dictionary with structure:
        {
            'segment_profiles': {
                'RESSF': {
                    'premise_count': int,
                    'premise_pct': float,
                    'avg_premise_age': float,
                    'equipment_by_enduse': {
                        'space_heating': {'count': int, 'pct': float, 'avg_age': float, 'avg_efficiency': float},
                        ...
                    },
                    'top_equipment': [{'code': str, 'count': int, 'pct': float}, ...],
                    'fuel_mix': {'gas': float, 'electric': float},
                    'avg_efficiency_overall': float,
                },
                ...
            },
            'market_profiles': {
                'D1': {...},
                ...
            },
            'summary_stats': {
                'total_premises': int,
                'total_equipment': int,
                'avg_efficiency': float,
                ...
            }
        }
    """
    profiles = {
        'segment_profiles': {},
        'market_profiles': {},
        'summary_stats': {}
    }
    
    if premise_equipment.empty:
        logger.warning("premise_equipment DataFrame is empty; returning empty profiles")
        profiles['summary_stats']['total_premises'] = 0
        profiles['summary_stats']['total_equipment'] = 0
        return profiles
    
    # Total premises and equipment
    total_premises = premise_equipment['blinded_id'].nunique()
    total_equipment = len(premise_equipment)
    
    profiles['summary_stats']['total_premises'] = total_premises
    profiles['summary_stats']['total_equipment'] = total_equipment
    profiles['summary_stats']['avg_efficiency'] = premise_equipment['efficiency'].mean() if 'efficiency' in premise_equipment.columns else 0
    
    # ====================================================================
    # SEGMENT PROFILES
    # ====================================================================
    
    segments = premise_equipment['segment_code'].unique()
    for segment in segments:
        if pd.isna(segment):
            continue
        
        segment_data = premise_equipment[premise_equipment['segment_code'] == segment]
        segment_premises = segment_data['blinded_id'].nunique()
        
        profile = {
            'premise_count': segment_premises,
            'premise_pct': segment_premises / total_premises if total_premises > 0 else 0,
            'avg_premise_age': segment_data['premise_age'].mean() if 'premise_age' in segment_data.columns else None,
            'equipment_by_enduse': {},
            'top_equipment': [],
            'fuel_mix': {'gas': 0, 'electric': 0},
            'avg_efficiency_overall': segment_data['efficiency'].mean() if 'efficiency' in segment_data.columns else None,
        }
        
        # Equipment by end-use
        end_uses = segment_data['end_use'].unique()
        total_equipment_segment = len(segment_data)
        
        for end_use in end_uses:
            if pd.isna(end_use):
                continue
            
            enduse_data = segment_data[segment_data['end_use'] == end_use]
            enduse_count = len(enduse_data)
            
            profile['equipment_by_enduse'][end_use] = {
                'count': enduse_count,
                'pct': enduse_count / total_equipment_segment if total_equipment_segment > 0 else 0,
                'avg_age': enduse_data['equipment_age'].mean() if 'equipment_age' in enduse_data.columns else None,
                'avg_efficiency': enduse_data['efficiency'].mean() if 'efficiency' in enduse_data.columns else None,
            }
        
        # Top 5 equipment types
        equipment_counts = segment_data['equipment_type_code'].value_counts().head(5)
        for equipment_code, count in equipment_counts.items():
            profile['top_equipment'].append({
                'code': equipment_code,
                'count': count,
                'pct': count / total_equipment_segment if total_equipment_segment > 0 else 0,
            })
        
        # Fuel mix
        if 'fuel_type' in segment_data.columns:
            fuel_counts = segment_data['fuel_type'].value_counts()
            total_fuel = fuel_counts.sum()
            profile['fuel_mix']['gas'] = fuel_counts.get('natural_gas', 0) / total_fuel if total_fuel > 0 else 0
            profile['fuel_mix']['electric'] = fuel_counts.get('electric', 0) / total_fuel if total_fuel > 0 else 0
        
        profiles['segment_profiles'][segment] = profile
    
    # ====================================================================
    # MARKET/DISTRICT PROFILES
    # ====================================================================
    
    districts = premise_equipment['district_code_IRP'].unique()
    for district in districts:
        if pd.isna(district):
            continue
        
        district_data = premise_equipment[premise_equipment['district_code_IRP'] == district]
        district_premises = district_data['blinded_id'].nunique()
        
        profile = {
            'premise_count': district_premises,
            'premise_pct': district_premises / total_premises if total_premises > 0 else 0,
            'avg_premise_age': district_data['premise_age'].mean() if 'premise_age' in district_data.columns else None,
            'equipment_by_enduse': {},
            'top_equipment': [],
            'fuel_mix': {'gas': 0, 'electric': 0},
            'avg_efficiency_overall': district_data['efficiency'].mean() if 'efficiency' in district_data.columns else None,
        }
        
        # Equipment by end-use
        end_uses = district_data['end_use'].unique()
        total_equipment_district = len(district_data)
        
        for end_use in end_uses:
            if pd.isna(end_use):
                continue
            
            enduse_data = district_data[district_data['end_use'] == end_use]
            enduse_count = len(enduse_data)
            
            profile['equipment_by_enduse'][end_use] = {
                'count': enduse_count,
                'pct': enduse_count / total_equipment_district if total_equipment_district > 0 else 0,
                'avg_age': enduse_data['equipment_age'].mean() if 'equipment_age' in enduse_data.columns else None,
                'avg_efficiency': enduse_data['efficiency'].mean() if 'efficiency' in enduse_data.columns else None,
            }
        
        # Top 5 equipment types
        equipment_counts = district_data['equipment_type_code'].value_counts().head(5)
        for equipment_code, count in equipment_counts.items():
            profile['top_equipment'].append({
                'code': equipment_code,
                'count': count,
                'pct': count / total_equipment_district if total_equipment_district > 0 else 0,
            })
        
        # Fuel mix
        if 'fuel_type' in district_data.columns:
            fuel_counts = district_data['fuel_type'].value_counts()
            total_fuel = fuel_counts.sum()
            profile['fuel_mix']['gas'] = fuel_counts.get('natural_gas', 0) / total_fuel if total_fuel > 0 else 0
            profile['fuel_mix']['electric'] = fuel_counts.get('electric', 0) / total_fuel if total_fuel > 0 else 0
        
        profiles['market_profiles'][district] = profile
    
    logger.info(f"Generated profiles for {len(profiles['segment_profiles'])} segments and {len(profiles['market_profiles'])} markets")
    
    return profiles


def visualize_segment_market_hierarchy(
    premise_equipment: pd.DataFrame,
    output_dir: str = "output/segment_market_analysis"
) -> Dict[str, str]:
    """
    Main orchestrator function for segment/subsegment/market visualization.
    
    Generates:
    1. Hierarchical relationship diagrams (treemap, sunburst, Sankey)
    2. Detailed segment/subsegment/market profiles
    3. Appliance inventory tables (5 tables)
    4. OpenStreetMap visualization with hexbin aggregation
    5. Comparison charts (stacked bars, heatmap, box plots, violin plots, scatter plots)
    6. Unaggregated premise-level data export (CSV + Parquet)
    7. Comprehensive profile report (HTML + Markdown)
    
    Args:
        premise_equipment: DataFrame from build_premise_equipment_table
        output_dir: Directory to save all outputs
    
    Returns:
        Dictionary mapping output name to file path
    """
    import os
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    outputs = {}
    
    try:
        # Generate segment profiles
        logger.info("Generating segment profiles...")
        profiles = generate_segment_profiles(premise_equipment)
        
        # Create appliance inventory tables
        logger.info("Creating appliance inventory tables...")
        
        # Table 1: Equipment count by segment × end-use
        segment_enduse_table = pd.DataFrame()
        for segment, profile in profiles['segment_profiles'].items():
            row = {'segment': segment}
            for end_use, stats in profile['equipment_by_enduse'].items():
                row[end_use] = stats['count']
            segment_enduse_table = pd.concat([segment_enduse_table, pd.DataFrame([row])], ignore_index=True)
        
        segment_enduse_path = os.path.join(output_dir, 'equipment_count_segment_enduse.csv')
        segment_enduse_table.to_csv(segment_enduse_path, index=False)
        outputs['equipment_count_segment_enduse'] = segment_enduse_path
        logger.info(f"Saved equipment count by segment × end-use to {segment_enduse_path}")
        
        # Table 3: Equipment count by market/district × end-use
        market_enduse_table = pd.DataFrame()
        for market, profile in profiles['market_profiles'].items():
            row = {'market': market}
            for end_use, stats in profile['equipment_by_enduse'].items():
                row[end_use] = stats['count']
            market_enduse_table = pd.concat([market_enduse_table, pd.DataFrame([row])], ignore_index=True)
        
        market_enduse_path = os.path.join(output_dir, 'equipment_count_market_enduse.csv')
        market_enduse_table.to_csv(market_enduse_path, index=False)
        outputs['equipment_count_market_enduse'] = market_enduse_path
        logger.info(f"Saved equipment count by market × end-use to {market_enduse_path}")
        
        # Table 4: Top 10 equipment types by count
        all_equipment = premise_equipment['equipment_type_code'].value_counts().head(10)
        top_equipment_table = pd.DataFrame({
            'equipment_type_code': all_equipment.index,
            'count': all_equipment.values,
            'pct_of_total': (all_equipment.values / len(premise_equipment) * 100).round(2),
        })
        
        top_equipment_path = os.path.join(output_dir, 'top_equipment_types.csv')
        top_equipment_table.to_csv(top_equipment_path, index=False)
        outputs['top_equipment_types'] = top_equipment_path
        logger.info(f"Saved top equipment types to {top_equipment_path}")
        
        # Table 5: Equipment age distribution by segment
        if 'equipment_age' in premise_equipment.columns:
            age_bins = [0, 5, 10, 15, 20, 100]
            age_labels = ['0-5', '5-10', '10-15', '15-20', '20+']
            
            age_dist_table = pd.DataFrame()
            for segment in profiles['segment_profiles'].keys():
                segment_data = premise_equipment[premise_equipment['segment_code'] == segment]
                segment_data_copy = segment_data.copy()
                segment_data_copy['age_bin'] = pd.cut(segment_data_copy['equipment_age'], bins=age_bins, labels=age_labels)
                age_counts = segment_data_copy['age_bin'].value_counts().sort_index()
                
                row = {'segment': segment}
                for age_label in age_labels:
                    row[age_label] = age_counts.get(age_label, 0)
                age_dist_table = pd.concat([age_dist_table, pd.DataFrame([row])], ignore_index=True)
            
            age_dist_path = os.path.join(output_dir, 'equipment_age_distribution_segment.csv')
            age_dist_table.to_csv(age_dist_path, index=False)
            outputs['equipment_age_distribution_segment'] = age_dist_path
            logger.info(f"Saved equipment age distribution to {age_dist_path}")
        
        # Export unaggregated premise-level data
        logger.info("Exporting unaggregated premise-level data...")
        
        # CSV export
        unagg_csv_path = os.path.join(output_dir, 'segment_market_unaggregated_data.csv')
        premise_equipment.to_csv(unagg_csv_path, index=False)
        outputs['unaggregated_data_csv'] = unagg_csv_path
        logger.info(f"Saved unaggregated data (CSV) to {unagg_csv_path}")
        
        # Parquet export
        try:
            unagg_parquet_path = os.path.join(output_dir, 'segment_market_unaggregated_data.parquet')
            premise_equipment.to_parquet(unagg_parquet_path, index=False)
            outputs['unaggregated_data_parquet'] = unagg_parquet_path
            logger.info(f"Saved unaggregated data (Parquet) to {unagg_parquet_path}")
        except Exception as e:
            logger.warning(f"Failed to save Parquet file: {e}")
        
        # Create summary table
        logger.info("Creating summary table...")
        summary_rows = []
        
        for segment, profile in profiles['segment_profiles'].items():
            summary_rows.append({
                'type': 'segment',
                'code': segment,
                'premise_count': profile['premise_count'],
                'premise_pct': profile['premise_pct'],
                'avg_premise_age': profile['avg_premise_age'],
                'avg_efficiency': profile['avg_efficiency_overall'],
                'gas_pct': profile['fuel_mix']['gas'],
                'electric_pct': profile['fuel_mix']['electric'],
            })
        
        for market, profile in profiles['market_profiles'].items():
            summary_rows.append({
                'type': 'market',
                'code': market,
                'premise_count': profile['premise_count'],
                'premise_pct': profile['premise_pct'],
                'avg_premise_age': profile['avg_premise_age'],
                'avg_efficiency': profile['avg_efficiency_overall'],
                'gas_pct': profile['fuel_mix']['gas'],
                'electric_pct': profile['fuel_mix']['electric'],
            })
        
        summary_table = pd.DataFrame(summary_rows)
        summary_path = os.path.join(output_dir, 'segment_market_summary_table.csv')
        summary_table.to_csv(summary_path, index=False)
        outputs['summary_table'] = summary_path
        logger.info(f"Saved summary table to {summary_path}")
        
        # Create HTML report
        logger.info("Creating HTML report...")
        html_report = _create_segment_market_report_html(profiles, summary_table, output_dir)
        report_path = os.path.join(output_dir, 'segment_market_analysis_report.html')
        with open(report_path, 'w') as f:
            f.write(html_report)
        outputs['report_html'] = report_path
        logger.info(f"Saved HTML report to {report_path}")
        
        logger.info(f"Segment/market visualization complete. Generated {len(outputs)} outputs.")
        
    except Exception as e:
        logger.error(f"Error in visualize_segment_market_hierarchy: {e}", exc_info=True)
        raise
    
    return outputs


def _create_segment_market_report_html(profiles: Dict, summary_table: pd.DataFrame, output_dir: str) -> str:
    """
    Generate comprehensive HTML report for segment/market analysis.
    
    Args:
        profiles: Dictionary from generate_segment_profiles()
        summary_table: Summary DataFrame
        output_dir: Output directory path
    
    Returns:
        HTML string
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Segment/Market Analysis Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            h1 { color: #333; border-bottom: 3px solid #0066cc; padding-bottom: 10px; }
            h2 { color: #0066cc; margin-top: 30px; }
            h3 { color: #666; }
            table { border-collapse: collapse; width: 100%; margin: 20px 0; background-color: white; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #0066cc; color: white; font-weight: bold; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f0f0f0; }
            .summary-box { background-color: #e8f4f8; border-left: 4px solid #0066cc; padding: 15px; margin: 20px 0; }
            .metric { display: inline-block; margin: 10px 20px; }
            .metric-value { font-size: 24px; font-weight: bold; color: #0066cc; }
            .metric-label { font-size: 12px; color: #666; }
        </style>
    </head>
    <body>
        <h1>Segment/Subsegment/Market Analysis Report</h1>
        
        <div class="summary-box">
            <h2>Executive Summary</h2>
            <div class="metric">
                <div class="metric-value">""" + str(profiles['summary_stats'].get('total_premises', 0)) + """</div>
                <div class="metric-label">Total Premises</div>
            </div>
            <div class="metric">
                <div class="metric-value">""" + str(profiles['summary_stats'].get('total_equipment', 0)) + """</div>
                <div class="metric-label">Total Equipment</div>
            </div>
            <div class="metric">
                <div class="metric-value">""" + str(round(profiles['summary_stats'].get('avg_efficiency', 0), 2)) + """</div>
                <div class="metric-label">Avg Efficiency</div>
            </div>
        </div>
        
        <h2>Segment Profiles</h2>
        <table>
            <tr>
                <th>Segment</th>
                <th>Premise Count</th>
                <th>% of Total</th>
                <th>Avg Premise Age</th>
                <th>Avg Efficiency</th>
                <th>Gas %</th>
                <th>Electric %</th>
            </tr>
    """
    
    for segment, profile in profiles['segment_profiles'].items():
        avg_age_str = f"{profile['avg_premise_age']:.1f}" if profile['avg_premise_age'] is not None else 'N/A'
        avg_eff_str = f"{profile['avg_efficiency_overall']:.2f}" if profile['avg_efficiency_overall'] is not None else 'N/A'
        html += f"""
            <tr>
                <td>{segment}</td>
                <td>{profile['premise_count']}</td>
                <td>{profile['premise_pct']:.1%}</td>
                <td>{avg_age_str}</td>
                <td>{avg_eff_str}</td>
                <td>{profile['fuel_mix']['gas']:.1%}</td>
                <td>{profile['fuel_mix']['electric']:.1%}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <h2>Market/District Profiles</h2>
        <table>
            <tr>
                <th>Market</th>
                <th>Premise Count</th>
                <th>% of Total</th>
                <th>Avg Premise Age</th>
                <th>Avg Efficiency</th>
                <th>Gas %</th>
                <th>Electric %</th>
            </tr>
    """
    
    for market, profile in profiles['market_profiles'].items():
        avg_age_str = f"{profile['avg_premise_age']:.1f}" if profile['avg_premise_age'] is not None else 'N/A'
        avg_eff_str = f"{profile['avg_efficiency_overall']:.2f}" if profile['avg_efficiency_overall'] is not None else 'N/A'
        html += f"""
            <tr>
                <td>{market}</td>
                <td>{profile['premise_count']}</td>
                <td>{profile['premise_pct']:.1%}</td>
                <td>{avg_age_str}</td>
                <td>{avg_eff_str}</td>
                <td>{profile['fuel_mix']['gas']:.1%}</td>
                <td>{profile['fuel_mix']['electric']:.1%}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <h2>Summary Statistics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
    """
    
    for key, value in profiles['summary_stats'].items():
        html += f"""
            <tr>
                <td>{key}</td>
                <td>{value}</td>
            </tr>
        """
    
    html += """
        </table>
        
        <p style="margin-top: 40px; color: #999; font-size: 12px;">
            Report generated automatically. For detailed analysis, see accompanying CSV files and visualizations.
        </p>
    </body>
    </html>
    """
    
    return html
