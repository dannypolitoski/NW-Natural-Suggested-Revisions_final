"""
Chart generation for scenario results.

Reads CSV outputs from a scenario folder and produces PNG charts
for manual verification and presentation.

Usage:
    from src.scenario_charts import generate_scenario_charts
    generate_scenario_charts(Path('scenarios/baseline'))
"""

import logging
from pathlib import Path

import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

logger = logging.getLogger(__name__)

# Consistent color palette
COLORS = {
    'model': '#4e79a7',
    'irp': '#e15759',
    'gas': '#4e79a7',
    'electric': '#f28e2b',
    'RESSF': '#4e79a7',
    'RESMF': '#f28e2b',
    'MOBILE': '#59a14f',
    'Unknown': '#bab0ac',
    'Unclassified': '#bab0ac',
    'replaced': '#e15759',
    'kept': '#76b7b2',
}


def _save(fig, path: Path):
    # Auto-add projection marker to any axis with year-based x-axis
    for ax in fig.get_axes():
        xlim = ax.get_xlim()
        # Heuristic: if x-axis range looks like years (2020-2040 range)
        if 2020 <= xlim[0] <= 2030 and 2030 <= xlim[1] <= 2050:
            _mark_projection(ax)
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    logger.info(f"  Chart -> {path}")


# Base year dividing historical from projected
_BASE_YEAR = 2025


def _mark_projection(ax, base_year=None):
    """Add a vertical line and labels marking where projection begins."""
    by = base_year or _BASE_YEAR
    xlim = ax.get_xlim()
    if xlim[0] <= by <= xlim[1]:
        ax.axvline(x=by, color='#7f7f7f', linestyle=':', linewidth=1.5, alpha=0.6, zorder=1)
        ylim = ax.get_ylim()
        y_top = ylim[1] - (ylim[1] - ylim[0]) * 0.02
        ax.text(by - 0.3, y_top, '← Historical', fontsize=7, color='#7f7f7f',
                ha='right', va='top')
        ax.text(by + 0.3, y_top, 'Projected →', fontsize=7, color='#7f7f7f',
                ha='left', va='top')


def _is_monthly_run(scenario_dir: Path) -> bool:
    """Return True if this scenario was run with monthly temporal resolution."""
    results_path = scenario_dir / 'results.csv'
    if not results_path.exists():
        return False
    try:
        header = pd.read_csv(results_path, nrows=0).columns.tolist()
        return 'month' in header
    except Exception:
        return False


def _load_results_annual(scenario_dir: Path) -> pd.DataFrame:
    """Load results.csv and aggregate months → year if monthly resolution."""
    path = scenario_dir / 'results.csv'
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if 'month' in df.columns:
        agg_cols = {'total_therms': 'sum', 'premise_count': 'first'}
        for col in ('use_per_customer', 'irp_upc_therms', 'scenario_name', 'data_type'):
            if col in df.columns:
                agg_cols[col] = 'first'
        df = df.groupby(['year', 'end_use']).agg(agg_cols).reset_index()
        if 'premise_count' in df.columns:
            df['use_per_customer'] = df['total_therms'] / df['premise_count'].clip(lower=1)
    return df


def chart_upc_trajectory(scenario_dir: Path):
    """1. Model UPC vs IRP UPC over time — shows both SH-only and estimated total."""
    irp_path = scenario_dir / 'irp_comparison.csv'
    est_path = scenario_dir / 'estimated_total_upc.csv'
    monthly_path = scenario_dir / 'monthly_summary.csv'
    if not irp_path.exists():
        return

    is_monthly = _is_monthly_run(scenario_dir)

    # IRP comparison is always annual (annual UPC)
    irp = pd.read_csv(irp_path)
    # Deduplicate to one row per year (irp_comparison has annual rows)
    irp_annual = irp.drop_duplicates('year').sort_values('year')

    has_est = est_path.exists()
    if has_est:
        est = pd.read_csv(est_path).drop_duplicates('year').sort_values('year')

    fig, ax = plt.subplots(figsize=(14 if is_monthly else 10, 5))

    if is_monthly and monthly_path.exists():
        # Monthly UPC on decimal-year axis (132 points)
        mo = pd.read_csv(monthly_path).sort_values(['year', 'month'])
        mo['decimal_year'] = mo['year'] + (mo['month'] - 1) / 12.0

        ax.plot(mo['decimal_year'], mo['use_per_customer'],
                color=COLORS['model'], linewidth=1.5, alpha=0.9,
                label='Model UPC / Month (space heating)')
        ax.fill_between(mo['decimal_year'], 0, mo['use_per_customer'],
                        color=COLORS['model'], alpha=0.1)

        # IRP annual reference line (step/flat between Jan ticks)
        ax.step(irp_annual['year'], irp_annual['irp_upc'],
                color=COLORS['irp'], linewidth=2, linestyle='--',
                where='post', label='NW Natural IRP (annual, all end-uses)')

        # Mark projection start
        base_year = int(mo['year'].min())
        ax.axvline(x=base_year + 1, color='#7f7f7f', linestyle=':', linewidth=1.5, alpha=0.6)
        ax.text(base_year + 1.05, mo['use_per_customer'].max() * 0.97,
                'Projected ->', fontsize=8, color='#7f7f7f', va='top')

        years = sorted(mo['year'].unique())
        ax.set_xticks([float(y) for y in years])
        ax.set_xticklabels([str(int(y)) for y in years], fontsize=9)
        ax.set_xlabel('Year (monthly resolution)')
        ax.set_ylabel('Therms / Customer / Month')
        ax.set_title('UPC Trajectory — Monthly Resolution vs IRP Annual Forecast')
    else:
        # Annual: original behaviour
        ax.plot(irp_annual['year'], irp_annual['model_upc'],
                marker='o', color=COLORS['model'], linewidth=2,
                label='Model: Space Heating Only')

        if has_est and 'estimated_total_upc' in est.columns:
            ax.plot(est['year'], est['estimated_total_upc'],
                    marker='D', color='#59a14f', linewidth=2,
                    label='Model: Estimated Total (all end-uses)')

        ax.plot(irp_annual['year'], irp_annual['irp_upc'],
                marker='s', color=COLORS['irp'], linewidth=2, linestyle='--',
                label='NW Natural IRP (all end-uses)')

        if has_est and 'estimated_total_upc' in est.columns:
            ax.fill_between(est['year'], est['estimated_total_upc'],
                            irp_annual['irp_upc'], alpha=0.1, color=COLORS['irp'])
        else:
            ax.fill_between(irp_annual['year'], irp_annual['model_upc'],
                            irp_annual['irp_upc'], alpha=0.1, color=COLORS['irp'])

        ax.set_xlim(irp_annual['year'].min(), irp_annual['year'].max())
        ax.set_xlabel('Year')
        ax.set_ylabel('Therms / Customer / Year')
        ax.set_title('Use Per Customer: Model vs NW Natural IRP Forecast')

    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    _save(fig, scenario_dir / 'chart_upc_trajectory.png')


def chart_equipment_fuel_mix(scenario_dir: Path):
    """2. Territory-wide heating fuel mix over time (% gas vs electric vs hybrid)."""
    path = scenario_dir / 'equipment_stats.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)

    has_territory = 'territory_gas_pct' in df.columns
    has_hybrid = 'hybrid_pct' in df.columns and df['hybrid_pct'].sum() > 0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left panel: NW Natural customer fuel mix (gas / hybrid / electric)
    gas_pct = df['gas_units'] / df['total_equipment'] * 100
    hybrid_pct = df['hybrid_units'] / df['total_equipment'] * 100 if has_hybrid else pd.Series(0, index=df.index)
    elec_pct = df['electric_units'] / df['total_equipment'] * 100

    ax1.fill_between(df['year'], 0, gas_pct,
                     color=COLORS['gas'], alpha=0.7, label='Gas Only')
    if has_hybrid:
        ax1.fill_between(df['year'], gas_pct, gas_pct + hybrid_pct,
                         color='#9b59b6', alpha=0.7, label='Hybrid (Gas + Heat Pump)')
        ax1.fill_between(df['year'], gas_pct + hybrid_pct, 100,
                         color=COLORS['electric'], alpha=0.7, label='Full Electric')
    else:
        ax1.fill_between(df['year'], gas_pct, 100,
                         color=COLORS['electric'], alpha=0.7, label='Electric')

    ax1.set_title('NW Natural Customer Heating Fuel Mix')
    ax1.set_ylabel('Share of NW Natural Customers (%)')
    ax1.set_ylim(0, 100)
    ax1.legend(loc='center right', fontsize=8)
    # Annotate gas share at start and end
    ax1.annotate(f"Gas: {gas_pct.iloc[0]:.1f}%",
                 xy=(df.iloc[0]['year'], gas_pct.iloc[0] / 2),
                 ha='center', fontsize=9, color='white', fontweight='bold')
    ax1.annotate(f"Gas: {gas_pct.iloc[-1]:.1f}%",
                 xy=(df.iloc[-1]['year'], gas_pct.iloc[-1] / 2),
                 ha='center', fontsize=9, color='white', fontweight='bold')
    ax1.set_xlabel('Year')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(df['year'].min(), df['year'].max())

    # Right panel: stacked bar of switching volume (electric + hybrid)
    bar_width = 0.7
    if has_hybrid:
        ax2.bar(df['year'], df['hybrid_units'], bar_width,
                color='#9b59b6', edgecolor='white', label='Hybrid')
        ax2.bar(df['year'], df['electric_units'], bar_width,
                bottom=df['hybrid_units'],
                color='#2ecc71', edgecolor='white', label='Full Electric')
    else:
        ax2.bar(df['year'], df['electric_units'], bar_width,
                color='#2ecc71', edgecolor='white', label='Switched to Electric')

    ax2.set_title('Cumulative Fuel Switching')
    ax2.set_xlabel('Year')
    ax2.set_ylabel('Units')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    # Annotate total at final bar
    final_total = df.iloc[-1]['electric_units'] + (df.iloc[-1].get('hybrid_units', 0) if has_hybrid else 0)
    if final_total > 0:
        ax2.annotate(f"{int(final_total):,}",
                     xy=(df.iloc[-1]['year'], final_total),
                     textcoords="offset points", xytext=(0, 8), ha='center', fontsize=9)

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_fuel_mix.png')


def chart_efficiency_trajectory(scenario_dir: Path):
    """3. Average fleet efficiency and new equipment efficiency over time."""
    path = scenario_dir / 'equipment_stats.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)

    has_new_eff = 'new_equip_efficiency' in df.columns

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df['year'], df['avg_efficiency'] * 100, marker='o',
            color=COLORS['model'], linewidth=2, label='Fleet Average AFUE')
    
    if has_new_eff:
        ax.plot(df['year'], df['new_equip_efficiency'] * 100, marker='D',
                color='#59a14f', linewidth=2, linestyle='--', label='New Equipment AFUE')
        # Mark the 2028 condensing mandate
        if df['year'].max() >= 2028:
            ax.axvline(x=2028, color='gray', linestyle=':', alpha=0.5)
            ax.text(2028.2, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 96,
                    '2028: 95% AFUE\nmandate', fontsize=8, color='gray', va='top')

    ax.set_title('Equipment Efficiency Over Time — Space Heating')
    ax.set_xlabel('Year')
    ax.set_ylabel('AFUE (%)')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(df['year'].min(), df['year'].max())
    # Set y-axis to show meaningful range
    all_vals = list(df['avg_efficiency'] * 100)
    if has_new_eff:
        all_vals += list(df['new_equip_efficiency'] * 100)
    ymin = min(all_vals) - 2
    ymax = max(all_vals) + 2
    ax.set_ylim(max(0, ymin), min(100, ymax))
    _save(fig, scenario_dir / 'chart_efficiency.png')


def chart_replacements(scenario_dir: Path):
    """4. Equipment status: stacked bar of working/malfunctioning/repaired/replaced + total line."""
    path = scenario_dir / 'equipment_stats.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)

    has_all = all(c in df.columns for c in ['units_working', 'units_malfunctioning', 'units_repaired', 'units_replaced'])
    end_use = df['end_use'].iloc[0] if 'end_use' in df.columns else 'Space Heating'

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    years = df['year'].values
    x = np.arange(len(years))
    bar_width = 0.7

    if has_all:
        # Left: stacked bar — working + malfunctioning + repaired + replaced = total
        working = df['units_working'].values
        malfunction = df['units_malfunctioning'].values
        repaired = df['units_repaired'].values
        replaced = df['units_replaced'].values
        total = df['total_equipment'].values

        ax1.bar(x, working, bar_width, color='#59a14f', alpha=0.8, label='Working', edgecolor='white')
        ax1.bar(x, malfunction, bar_width, bottom=working, color='#e15759', alpha=0.8, label='Malfunctioning', edgecolor='white')
        ax1.bar(x, repaired, bar_width, bottom=working + malfunction, color='#f28e2b', alpha=0.8, label='Repaired (this year)', edgecolor='white')
        ax1.bar(x, replaced, bar_width, bottom=working + malfunction + repaired, color='#4e79a7', alpha=0.8, label='Replaced (this year)', edgecolor='white')

        # Total line on top
        ax1.plot(x, total, color='black', linewidth=2, marker='o', markersize=4, label='Total In Service', zorder=5)

        ax1.set_title(f'Equipment Fleet Status — {end_use.replace("_", " ").title()}')
        ax1.set_xlabel('Year')
        ax1.set_ylabel('Units')
        ax1.set_xticks(x)
        ax1.set_xticklabels([str(int(y)) for y in years], fontsize=8)
        ax1.legend(fontsize=7, loc='upper left')
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
        ax1.set_ylim(bottom=0)

        # Right: just replacements and repairs (zoomed in)
        ax2.bar(x - 0.2, replaced, 0.35, color='#4e79a7', edgecolor='white', label='Replaced')
        ax2.bar(x + 0.2, repaired, 0.35, color='#f28e2b', edgecolor='white', label='Repaired')

        # Annotate
        for i in range(len(years)):
            if replaced[i] > 0:
                ax2.text(i - 0.2, replaced[i] + max(replaced) * 0.02,
                         f"{int(replaced[i]):,}", ha='center', fontsize=7)
            if repaired[i] > 0:
                ax2.text(i + 0.2, repaired[i] + max(max(replaced), max(repaired)) * 0.02,
                         f"{int(repaired[i]):,}", ha='center', fontsize=7)

        # Add malfunctioning as a line
        ax2_twin = ax2.twinx()
        ax2_twin.plot(x, malfunction, color='#e15759', linewidth=2, marker='s', markersize=5, label='Malfunctioning')
        ax2_twin.set_ylabel('Malfunctioning Units', color='#e15759')
        ax2_twin.tick_params(axis='y', labelcolor='#e15759')
        ax2_twin.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))

        ax2.set_title(f'Replacements, Repairs & Malfunctions — {end_use.replace("_", " ").title()}')
        ax2.set_xlabel('Year')
        ax2.set_ylabel('Units Replaced / Repaired')
        ax2.set_xticks(x)
        ax2.set_xticklabels([str(int(y)) for y in years], fontsize=8)
        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc='upper left')
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    else:
        # Fallback: simple grouped bar
        ax1.bar(x - 0.2, df['units_replaced'], 0.35, color=COLORS['replaced'], edgecolor='white', label='Replaced')
        if 'units_repaired' in df.columns:
            ax1.bar(x + 0.2, df['units_repaired'], 0.35, color='#f28e2b', edgecolor='white', label='Repaired')
        ax1.set_title('Equipment Replacements & Repairs Per Year')
        ax1.set_xlabel('Year')
        ax1.set_ylabel('Units')
        ax1.set_xticks(x)
        ax1.set_xticklabels([str(int(y)) for y in years], fontsize=8)
        ax1.legend()
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
        ax2.set_visible(False)

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_replacements.png')


def chart_housing_stock(scenario_dir: Path):
    """5. Housing stock projection by segment over time."""
    path = scenario_dir / 'housing_stock.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)

    seg_cols = [c for c in df.columns if c not in ['year', 'total_units', 'growth_rate', 'scenario_name']]

    fig, ax = plt.subplots(figsize=(10, 5))

    if seg_cols:
        # Stacked area by segment
        bottom = np.zeros(len(df))
        seg_colors = {'RESSF': '#4e79a7', 'RESMF': '#f28e2b', 'Unclassified': '#bab0ac', 'MOBILE': '#59a14f'}
        for seg in seg_cols:
            color = seg_colors.get(seg, '#76b7b2')
            ax.fill_between(df['year'], bottom, bottom + df[seg].values,
                             alpha=0.7, color=color, label=seg)
            bottom += df[seg].values
        ax.legend(loc='upper left', fontsize=8)
    else:
        ax.fill_between(df['year'], 0, df['total_units'], alpha=0.3, color=COLORS['model'])
        ax.plot(df['year'], df['total_units'], marker='o', color=COLORS['model'], linewidth=2)

    ax.set_title('Projected Housing Stock by Segment')
    ax.set_xlabel('Year')
    ax.set_ylabel('Total Residential Units')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(df['year'].min(), df['year'].max())
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    # Annotate start and end totals
    ax.annotate(f"{int(df.iloc[0]['total_units']):,}",
                xy=(df.iloc[0]['year'], df.iloc[0]['total_units']),
                textcoords="offset points", xytext=(10, 10), fontsize=9)
    ax.annotate(f"{int(df.iloc[-1]['total_units']):,}",
                xy=(df.iloc[-1]['year'], df.iloc[-1]['total_units']),
                textcoords="offset points", xytext=(-50, 10), fontsize=9)

    _save(fig, scenario_dir / 'chart_housing_stock.png')


def chart_premise_distribution(scenario_dir: Path):
    """6. Per-premise therms distribution by segment (SF vs MF) over time."""
    path = scenario_dir / 'premise_distribution.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)

    has_segment = 'segment' in df.columns
    segments = df['segment'].unique().tolist() if has_segment else ['ALL']
    
    # If we have segment data, show 3 panels: RESSF, RESMF, ALL
    if has_segment and 'RESSF' in segments and 'RESMF' in segments:
        fig, axes = plt.subplots(1, 3, figsize=(20, 6))
        panel_segs = [('RESSF', 'Single Family', '#4e79a7'),
                      ('RESMF', 'Multi-Family', '#f28e2b'),
                      ('ALL', 'All Premises', '#59a14f')]
    else:
        fig, axes = plt.subplots(1, 1, figsize=(10, 5))
        axes = [axes]
        panel_segs = [('ALL', 'All Premises', COLORS['model'])]

    for ax, (seg, title, color) in zip(axes, panel_segs):
        if has_segment:
            sdf = df[df['segment'] == seg]
        else:
            sdf = df
        
        if sdf.empty:
            ax.set_visible(False)
            continue

        ax.fill_between(sdf['year'], sdf['p10_therms'], sdf['p90_therms'],
                         alpha=0.15, color=color, label='P10–P90')
        ax.fill_between(sdf['year'], sdf['p25_therms'], sdf['p75_therms'],
                         alpha=0.3, color=color, label='P25–P75')
        ax.plot(sdf['year'], sdf['median_therms'], marker='o', color=color,
                linewidth=2, label='Median')
        ax.plot(sdf['year'], sdf['mean_therms'], marker='s', color='gray',
                linewidth=1.5, linestyle='--', label='Mean')
        
        n = sdf.iloc[0]['premise_count'] if not sdf.empty else 0
        ax.set_title(f'{title} (n={int(n):,})')
        ax.set_xlabel('Year')
        ax.set_ylabel('Annual Therms per Premise')
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(sdf['year'].min(), sdf['year'].max())
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    fig.suptitle('Per-Premise Therms Distribution by Segment', fontsize=13, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save(fig, scenario_dir / 'chart_premise_distribution.png')


def chart_segment_demand(scenario_dir: Path):
    """7. Demand by segment (stacked area) over time."""
    path = scenario_dir / 'segment_demand.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)

    is_monthly = 'month' in df.columns

    if is_monthly:
        # Decimal-year axis: 132 points
        df = df.sort_values(['year', 'month']).copy()
        df['decimal_year'] = df['year'] + (df['month'] - 1) / 12.0

        preferred = ['RESSF', 'RESMF', 'MOBILE', 'Unclassified', 'Unknown']
        segments = [s for s in preferred if s in df['segment'].unique()]
        segments += [s for s in df['segment'].unique() if s not in segments]

        fig, ax = plt.subplots(figsize=(14, 5))
        bottom = np.zeros(len(df['decimal_year'].unique()))
        x_vals = sorted(df['decimal_year'].unique())

        for seg in segments:
            color = COLORS.get(seg, '#76b7b2')
            seg_data = df[df['segment'] == seg].set_index('decimal_year')['total_therms'].reindex(x_vals, fill_value=0)
            ax.fill_between(x_vals, bottom, bottom + seg_data.values,
                            label=seg, color=color, alpha=0.7)
            bottom += seg_data.values

        years = sorted(df['year'].unique())
        ax.set_xticks([float(y) for y in years])
        ax.set_xticklabels([str(int(y)) for y in years], fontsize=9)
        ax.set_xlabel('Year (monthly resolution)')
        base_year = int(df['year'].min())
        ax.axvline(x=base_year + 1, color='#7f7f7f', linestyle=':', linewidth=1.5, alpha=0.6)
    else:
        pivot = df.pivot(index='year', columns='segment', values='total_therms').fillna(0)
        preferred = ['RESSF', 'RESMF', 'MOBILE', 'Unclassified', 'Unknown']
        cols = [c for c in preferred if c in pivot.columns]
        cols += [c for c in pivot.columns if c not in cols]
        pivot = pivot[cols]

        fig, ax = plt.subplots(figsize=(10, 5))
        bottom = np.zeros(len(pivot))
        for seg in pivot.columns:
            color = COLORS.get(seg, '#76b7b2')
            ax.fill_between(pivot.index, bottom, bottom + pivot[seg].values,
                            label=seg, color=color, alpha=0.7)
            bottom += pivot[seg].values
        ax.set_xlim(pivot.index.min(), pivot.index.max())
        ax.set_xlabel('Year')

    ax.set_title('Total Demand by Segment Over Time')
    ax.set_ylabel('Total Therms')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    _save(fig, scenario_dir / 'chart_segment_demand.png')


def chart_total_demand(scenario_dir: Path):
    """8. Total system demand over time with MoM/YoY change."""
    monthly_path = scenario_dir / 'monthly_summary.csv'
    yearly_path = scenario_dir / 'yearly_summary.csv'

    is_monthly = monthly_path.exists() and _is_monthly_run(scenario_dir)

    if is_monthly:
        df = pd.read_csv(monthly_path)
        df = df.sort_values(['year', 'month']).copy()
        df['decimal_year'] = df['year'] + (df['month'] - 1) / 12.0
        x = df['decimal_year'].values
        y = df['total_therms'].values
        pct_change = pd.Series(y).pct_change() * 100
        x_label = 'Year (monthly resolution)'
        change_label = 'Month-over-Month Change %'
        title = 'Total System Demand — Monthly Resolution'
        base_year = int(df['year'].min())
    else:
        if not yearly_path.exists():
            return
        df = pd.read_csv(yearly_path)
        x = df['year'].values
        y = df['total_therms'].values
        pct_change = pd.Series(y).pct_change() * 100
        # Mask first two points (no prior year + calibrated→projected transition)
        pct_change.iloc[0] = np.nan
        if len(pct_change) > 1:
            pct_change.iloc[1] = np.nan
        x_label = 'Year'
        change_label = 'Year-over-Year Change %'
        title = 'Total System Demand and Year-over-Year Change'
        base_year = None

    fig, ax1 = plt.subplots(figsize=(14 if is_monthly else 10, 5))

    if is_monthly:
        # Line + fill for monthly (too many points for bars)
        ax1.plot(x, y, color=COLORS['model'], linewidth=1.5, alpha=0.9, label='Total Demand')
        ax1.fill_between(x, 0, y, color=COLORS['model'], alpha=0.15)
        # Mark projection start
        ax1.axvline(x=base_year + 1, color='#7f7f7f', linestyle=':', linewidth=1.5, alpha=0.6)
        ax1.text(base_year + 1.05, max(y) * 0.97, 'Projected →',
                 fontsize=8, color='#7f7f7f', va='top')
        # Year tick marks
        years = sorted(df['year'].unique())
        ax1.set_xticks([float(yr) for yr in years])
        ax1.set_xticklabels([str(int(yr)) for yr in years], fontsize=9)
    else:
        ax1.bar(x, y, color=COLORS['model'], alpha=0.6, edgecolor='white', label='Total Demand')
        # Annotate initial drop
        if len(df) > 1:
            initial_drop = (y[1] / y[0] - 1) * 100
            ax1.annotate(f'{initial_drop:+.1f}%\n(initial\nadjustment)',
                         xy=(x[1], y[1]),
                         textcoords="offset points", xytext=(-40, -30),
                         fontsize=8, color=COLORS['irp'], ha='center',
                         arrowprops=dict(arrowstyle='->', color=COLORS['irp'], lw=0.8))

    ax1.set_xlabel(x_label)
    ax1.set_ylabel('Total Therms', color=COLORS['model'])
    ax1.tick_params(axis='y', labelcolor=COLORS['model'])
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f'{v:,.0f}'))
    ax1.grid(True, alpha=0.3)

    # Secondary axis: % change
    ax2 = ax1.twinx()
    ax2.plot(x, pct_change.values, color=COLORS['irp'],
             marker=None if is_monthly else 'o',
             linewidth=1.0 if is_monthly else 1.5,
             alpha=0.7, label=change_label)
    ax2.set_ylabel(change_label, color=COLORS['irp'])
    ax2.tick_params(axis='y', labelcolor=COLORS['irp'])
    ax2.axhline(y=0, color=COLORS['irp'], linestyle='--', alpha=0.3)

    ax1.set_title(title)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=8)
    _save(fig, scenario_dir / 'chart_total_demand.png')


def chart_cumulative_reduction(scenario_dir: Path):
    """9. Cumulative demand reduction from efficiency + electrification."""
    path = scenario_dir / 'yearly_summary.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)
    if len(df) < 2:
        return

    base_demand = df.iloc[0]['total_therms']
    df['reduction'] = base_demand - df['total_therms']
    df['cumulative_reduction'] = df['reduction'].cumsum()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.fill_between(df['year'], 0, df['cumulative_reduction'],
                     alpha=0.3, color='#59a14f')
    ax.plot(df['year'], df['cumulative_reduction'], marker='o',
            color='#59a14f', linewidth=2)
    ax.set_title('Cumulative Demand Reduction vs Base Year')
    ax.set_xlabel('Year')
    ax.set_ylabel('Cumulative Therms Avoided')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(df['year'].min(), df['year'].max())
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    _save(fig, scenario_dir / 'chart_cumulative_reduction.png')


def chart_territory_electrification(scenario_dir: Path):
    """10. Territory-wide households by heating fuel — stacked bar with 4 categories."""
    path = scenario_dir / 'equipment_stats.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)
    if 'territory_gas_pct' not in df.columns or 'total_premises' not in df.columns:
        return

    base_gas_pct = df.iloc[0]['territory_gas_pct']
    if base_gas_pct <= 0:
        return

    df = df.copy()
    base_nwn = df.iloc[0]['total_premises']
    territory_total_base = base_nwn / (base_gas_pct / 100.0)

    # Compute territory totals per year (grow with housing)
    df['territory_total'] = territory_total_base * (df['total_premises'] / base_nwn)
    df['territory_gas'] = df['territory_total'] * df['territory_gas_pct'] / 100.0
    df['territory_elec'] = df['territory_total'] - df['territory_gas']

    # Base year counts
    base_gas = df.iloc[0]['territory_gas']
    base_elec = df.iloc[0]['territory_elec']

    # 4 categories per year (5 if hybrid exists):
    # 1. Original gas customers still on gas-only
    # 2. Gas customers who converted to hybrid
    # 3. Gas customers who converted to full electric
    # 4. New gas customers (from housing growth)
    # 5. New electric customers (from housing growth + conversions)
    has_hybrid_col = 'hybrid_fraction_of_nwn' in df.columns
    rows = []
    for _, row in df.iterrows():
        yr = int(row['year'])
        total = row['territory_total']
        gas_now = row['territory_gas']
        elec_now = row['territory_elec']

        # Original gas still on gas = base_gas × (current gas_fraction / base gas_fraction)
        gas_retention = row['gas_fraction_of_nwn'] / 100.0 if 'gas_fraction_of_nwn' in row.index else 1.0
        hybrid_frac = row['hybrid_fraction_of_nwn'] / 100.0 if has_hybrid_col else 0.0
        
        original_gas_remaining = base_gas * gas_retention
        converted_to_hybrid = base_gas * hybrid_frac
        converted_to_electric = base_gas - original_gas_remaining - converted_to_hybrid

        # New customers = total - base territory
        new_total = max(0, total - territory_total_base)
        new_gas = max(0, gas_now - original_gas_remaining)
        new_electric = max(0, new_total - new_gas)

        rows.append({
            'year': yr,
            'original_gas': int(original_gas_remaining),
            'converted_to_hybrid': int(converted_to_hybrid),
            'converted_to_electric': int(converted_to_electric),
            'new_gas': int(new_gas),
            'new_electric': int(new_electric),
            'total': int(total),
        })

    chart_df = pd.DataFrame(rows)

    # Also export this as CSV
    chart_df.to_csv(scenario_dir / 'territory_household_breakdown.csv', index=False)

    fig, ax = plt.subplots(figsize=(12, 7))

    bar_width = 0.7
    years = chart_df['year']

    # Stack order (bottom to top): original gas, new gas, hybrid, converted electric, new electric
    b1 = ax.bar(years, chart_df['original_gas'], bar_width,
                color='#4e79a7', label='Original Gas Customers')
    b2 = ax.bar(years, chart_df['new_gas'], bar_width,
                bottom=chart_df['original_gas'],
                color='#76b7b2', label='New Gas Customers')
    cum = chart_df['original_gas'] + chart_df['new_gas']
    if chart_df['converted_to_hybrid'].sum() > 0:
        b2h = ax.bar(years, chart_df['converted_to_hybrid'], bar_width,
                    bottom=cum,
                    color='#9b59b6', label='Converted Gas → Hybrid')
        cum = cum + chart_df['converted_to_hybrid']
    b3 = ax.bar(years, chart_df['converted_to_electric'], bar_width,
                bottom=cum,
                color='#e15759', label='Converted Gas → Electric')
    cum = cum + chart_df['converted_to_electric']
    b4 = ax.bar(years, chart_df['new_electric'], bar_width,
                bottom=cum,
                color='#f28e2b', label='New Electric Customers')

    ax.set_title('Territory-Wide Households by Heating Fuel', fontsize=13)
    ax.set_xlabel('Year')
    ax.set_ylabel('Households')
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_xlim(years.min() - 0.5, years.max() + 0.5)

    # Start y-axis at nearest 100,000 below the smallest bar base
    y_floor = (chart_df['original_gas'].min() // 100000) * 100000
    ax.set_ylim(bottom=y_floor)

    # Annotate totals on top
    for _, row in chart_df.iterrows():
        total = row['original_gas'] + row['new_gas'] + row.get('converted_to_hybrid', 0) + row['converted_to_electric'] + row['new_electric']
        ax.text(row['year'], total + total * 0.005, f"{total:,.0f}",
                ha='center', va='bottom', fontsize=7, color='gray')

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_territory_electrification.png')


def chart_estimated_total_upc(scenario_dir: Path):
    """11. Estimated total UPC vs IRP — overview and zoom."""
    path = scenario_dir / 'estimated_total_upc.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)
    has_irp = 'irp_upc' in df.columns and df['irp_upc'].notna().any()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # --- Left: full view with all three lines ---
    ax1.plot(df['year'], df['space_heating'], marker='o', color=COLORS['model'],
             linewidth=2, label='Model: Space Heating Only')
    ax1.plot(df['year'], df['estimated_total_upc'], marker='s', color='#59a14f',
             linewidth=2, label='Model: Estimated Total')
    if has_irp:
        ax1.plot(df['year'], df['irp_upc'], marker='^', color=COLORS['irp'],
                 linewidth=2, linestyle='--', label='NW Natural IRP Forecast')
    ax1.fill_between(df['year'], df['space_heating'], df['estimated_total_upc'],
                      alpha=0.15, color='#59a14f')
    ax1.set_title('UPC: Full View')
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Therms / Customer / Year')
    ax1.legend(fontsize=7)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(df['year'].min(), df['year'].max())

    # --- Right: zoom on estimated total vs IRP ---
    if has_irp:
        ax2.plot(df['year'], df['estimated_total_upc'], marker='s', color='#59a14f',
                 linewidth=2.5, label='Model Estimated Total')
        ax2.plot(df['year'], df['irp_upc'], marker='^', color=COLORS['irp'],
                 linewidth=2.5, linestyle='--', label='NW Natural IRP')

        # Shade the gap
        ax2.fill_between(df['year'], df['estimated_total_upc'], df['irp_upc'],
                          alpha=0.2, color='#e15759')

        # Set y-axis to zoom into the range
        all_vals = list(df['estimated_total_upc']) + list(df['irp_upc'].dropna())
        y_min = min(all_vals) * 0.95
        y_max = max(all_vals) * 1.05
        ax2.set_ylim(y_min, y_max)

        # Annotate the difference
        for i in [0, len(df) - 1]:
            row = df.iloc[i]
            diff = row['estimated_total_upc'] - row['irp_upc']
            mid_y = (row['estimated_total_upc'] + row['irp_upc']) / 2
            sign = '+' if diff >= 0 else ''
            ax2.annotate(f'{sign}{diff:.1f}',
                         xy=(row['year'], mid_y),
                         textcoords="offset points", xytext=(15, 0),
                         fontsize=9, fontweight='bold', color='#e15759',
                         arrowprops=dict(arrowstyle='->', color='#e15759', lw=1))

        ax2.set_title('Zoom: Model Estimated Total vs IRP')
        ax2.legend(fontsize=8)
    else:
        ax2.plot(df['year'], df['estimated_total_upc'], marker='s', color='#59a14f',
                 linewidth=2.5, label='Model Estimated Total')
        ax2.set_title('Estimated Total UPC')
        ax2.legend()

    ax2.set_xlabel('Year')
    ax2.set_ylabel('Therms / Customer / Year')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(df['year'].min(), df['year'].max())
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_estimated_total_upc.png')


def chart_enduse_breakdown(scenario_dir: Path):
    """12. Stacked area of estimated end-use breakdown over time."""
    path = scenario_dir / 'estimated_total_upc.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)

    enduse_cols = ['space_heating', 'water_heating', 'cooking', 'clothes_drying', 'fireplace', 'other']
    enduse_cols = [c for c in enduse_cols if c in df.columns]
    if not enduse_cols:
        return

    enduse_colors = {
        'space_heating': '#4e79a7',
        'water_heating': '#f28e2b',
        'cooking': '#e15759',
        'clothes_drying': '#76b7b2',
        'fireplace': '#59a14f',
        'other': '#bab0ac',
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Left: stacked area (absolute therms)
    bottom = np.zeros(len(df))
    for eu in enduse_cols:
        color = enduse_colors.get(eu, '#bab0ac')
        label = eu.replace('_', ' ').title()
        ax1.fill_between(df['year'], bottom, bottom + df[eu].values,
                         color=color, alpha=0.7, label=label)
        bottom += df[eu].values

    if 'irp_upc' in df.columns and df['irp_upc'].notna().any():
        ax1.plot(df['year'], df['irp_upc'], color='black', linewidth=2,
                 linestyle='--', marker='^', markersize=5, label='IRP Forecast')

    ax1.set_title('Estimated End-Use Breakdown (Therms/Customer)')
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Therms / Customer / Year')
    ax1.legend(fontsize=7, loc='upper right')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(df['year'].min(), df['year'].max())

    # Right: 100% stacked (share)
    totals = df[enduse_cols].sum(axis=1)
    bottom2 = np.zeros(len(df))
    for eu in enduse_cols:
        color = enduse_colors.get(eu, '#bab0ac')
        label = eu.replace('_', ' ').title()
        pct = df[eu].values / totals.values * 100
        ax2.fill_between(df['year'], bottom2, bottom2 + pct,
                         color=color, alpha=0.7, label=label)
        bottom2 += pct

    ax2.set_title('End-Use Share of Total (%)')
    ax2.set_xlabel('Year')
    ax2.set_ylabel('Share (%)')
    ax2.set_ylim(0, 100)
    ax2.legend(fontsize=7, loc='center right')
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(df['year'].min(), df['year'].max())

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_enduse_breakdown.png')


def chart_three_way_comparison(scenario_dir: Path):
    """13. Three-way comparison: observed billing vs NW Natural IRP vs model estimate."""
    est_path = scenario_dir / 'estimated_total_upc.csv'
    obs_path = scenario_dir / 'observed_billing_upc.csv'
    monthly_path = scenario_dir / 'monthly_summary.csv'
    if not est_path.exists():
        return

    est = pd.read_csv(est_path).drop_duplicates('year').sort_values('year')
    is_monthly = _is_monthly_run(scenario_dir)

    has_observed = obs_path.exists()
    obs = pd.read_csv(obs_path) if has_observed else pd.DataFrame()

    irp_hist_data = [
        (2005, 835), (2010, 812), (2015, 744), (2020, 688), (2022, 672), (2025, 648)
    ]
    irp_hist = pd.DataFrame(irp_hist_data, columns=['year', 'irp_upc'])
    has_irp = 'irp_upc' in est.columns and est['irp_upc'].notna().any()

    fig, ax = plt.subplots(figsize=(16 if is_monthly else 14, 7))

    # 1. Observed billing (historical actuals — always annual)
    if has_observed and not obs.empty:
        ax.plot(obs['year'], obs['mean_upc'], marker='o', color='#4e79a7',
                linewidth=2, markersize=5, label='Observed Billing (mean UPC)', zorder=3)
        ax.plot(obs['year'], obs['median_upc'], color='#4e79a7',
                linewidth=1, linestyle=':', alpha=0.6, label='Observed Billing (median)')

    # 2. NW Natural IRP — historical benchmarks + forward forecast (always annual)
    ax.scatter(irp_hist['year'], irp_hist['irp_upc'], color=COLORS['irp'],
               s=80, zorder=4, marker='D', label='NW Natural IRP (historical benchmarks)')
    if has_irp:
        ax.step(est['year'], est['irp_upc'], color=COLORS['irp'],
                linewidth=2.5, linestyle='--', where='post',
                label='NW Natural IRP (forecast)', zorder=3)

    # 3. Model — monthly line or annual markers
    if is_monthly and monthly_path.exists():
        mo = pd.read_csv(monthly_path).sort_values(['year', 'month'])
        mo['decimal_year'] = mo['year'] + (mo['month'] - 1) / 12.0
        ax.plot(mo['decimal_year'], mo['use_per_customer'],
                color='#59a14f', linewidth=1.5, alpha=0.9,
                label='Model UPC / Month (space heating)', zorder=3)
        ax.fill_between(mo['decimal_year'], 0, mo['use_per_customer'],
                        color='#59a14f', alpha=0.08)
        # Year tick marks
        years = sorted(mo['year'].unique())
        ax.set_xticks([float(y) for y in years])
        ax.set_xticklabels([str(int(y)) for y in years], fontsize=9)
        ax.set_ylabel('Therms / Customer (annual IRP) or / Month (model)')
    else:
        ax.plot(est['year'], est['estimated_total_upc'], color='#59a14f',
                linewidth=2.5, marker='s', markersize=6,
                label='Model Estimated Total', zorder=3)
        if has_irp:
            ax.fill_between(est['year'], est['estimated_total_upc'], est['irp_upc'],
                            alpha=0.1, color='#e15759')
        ax.set_ylabel('Therms / Customer / Year')

    ax.set_title('Three-Way UPC Comparison:\nObserved Billing vs NW Natural IRP vs Model', fontsize=13)
    ax.set_xlabel('Year')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3)

    x_min = 2009 if has_observed and not obs.empty else est['year'].min()
    x_max = est['year'].max()
    ax.set_xlim(x_min - 0.5, x_max + 0.5)

    base_year = int(est['year'].min())
    ax.axvline(x=base_year, color='gray', linestyle=':', alpha=0.5)
    ylim = ax.get_ylim()
    ax.text(base_year + 0.2, ylim[1] * 0.98, 'Forecast ->', fontsize=8, color='gray', va='top')
    ax.text(base_year - 0.2, ylim[1] * 0.98, '<- Historical', fontsize=8, color='gray', va='top', ha='right')

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    _save(fig, scenario_dir / 'chart_three_way_comparison.png')


def chart_monthly_seasonal(scenario_dir: Path):
    """14. Monthly seasonal demand pattern (only for monthly resolution runs)."""
    path = scenario_dir / 'results.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)
    if 'month' not in df.columns:
        return  # Annual resolution — skip

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Left: monthly demand by year (each year as a line)
    for yr in sorted(df['year'].unique()):
        yr_data = df[df['year'] == yr].groupby('month')['total_therms'].sum().reset_index()
        yr_data = yr_data.sort_values('month')
        alpha = 0.3 if yr != df['year'].max() else 1.0
        lw = 1 if yr != df['year'].max() else 2.5
        ax1.plot(yr_data['month'], yr_data['total_therms'], marker='o', markersize=3,
                 linewidth=lw, alpha=alpha, label=str(int(yr)))

    ax1.set_title('Monthly Total Demand by Year')
    ax1.set_xlabel('Month')
    ax1.set_ylabel('Total Therms')
    ax1.set_xticks(range(1, 13))
    ax1.set_xticklabels(month_names, fontsize=8)
    ax1.legend(fontsize=7, ncol=3)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    # Right: monthly UPC for base year vs final year
    years = sorted(df['year'].unique())
    base_yr, final_yr = years[0], years[-1]
    for yr, color, style in [(base_yr, COLORS['model'], '-'), (final_yr, COLORS['irp'], '--')]:
        yr_data = df[df['year'] == yr].groupby('month').agg(
            total_therms=('total_therms', 'sum'),
            premises=('premise_count', 'first')
        ).reset_index()
        yr_data['upc'] = yr_data['total_therms'] / yr_data['premises'].clip(lower=1)
        ax2.plot(yr_data['month'], yr_data['upc'], marker='o', markersize=5,
                 linewidth=2, linestyle=style, color=color, label=f'{int(yr)}')

    ax2.set_title(f'Monthly UPC: {int(base_yr)} vs {int(final_yr)}')
    ax2.set_xlabel('Month')
    ax2.set_ylabel('Therms / Customer / Month')
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(month_names, fontsize=8)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_monthly_seasonal.png')


def chart_hdd_history(scenario_dir: Path):
    """15. Historical HDD by year with calibration markers and forecast projection."""
    path = scenario_dir / 'hdd_history.csv'
    info_path = scenario_dir / 'hdd_info.csv'
    meta_path = scenario_dir / 'metadata.json'
    if not path.exists():
        return
    df = pd.read_csv(path)
    df = df[(df['year'] >= 1990) & (df['year'] <= 2025)]
    if df.empty:
        return

    # Load HDD info for annotations
    hdd_info = {}
    if info_path.exists():
        info_df = pd.read_csv(info_path)
        if not info_df.empty:
            hdd_info = info_df.iloc[0].to_dict()

    # Load scenario metadata for forecast horizon
    forecast_horizon = 10
    base_year = 2025
    weather_assumption = 'normal'
    if meta_path.exists():
        import json
        with open(meta_path) as f:
            meta = json.load(f)
        forecast_horizon = meta.get('forecast_horizon', 10)
        base_year = meta.get('base_year', 2025)
        weather_assumption = meta.get('weather_assumption', 'normal')

    fig, ax = plt.subplots(figsize=(14, 6))

    # Mark 2025 as partial year (different color)
    full_years = df[df['year'] < 2025]
    partial = df[df['year'] == 2025]

    ax.bar(full_years['year'], full_years['weighted_hdd'], color=COLORS['model'], alpha=0.6, edgecolor='white')
    if not partial.empty:
        ax.bar(partial['year'], partial['weighted_hdd'], color=COLORS['irp'], alpha=0.4, edgecolor='white',
               hatch='//', label=f'2025 (partial — {partial.iloc[0]["weighted_hdd"]:,.0f} HDD)')
    ax.plot(full_years['year'], full_years['weighted_hdd'], color=COLORS['model'], linewidth=1.5, marker='o', markersize=3)

    # 30-year average (excluding partial 2025)
    avg_hdd = full_years['weighted_hdd'].mean()
    ax.axhline(y=avg_hdd, color='gray', linestyle='--', alpha=0.7, linewidth=1.5)
    ax.text(full_years['year'].min() + 0.5, avg_hdd + 30, f'Average: {avg_hdd:,.0f} HDD',
            fontsize=9, color='gray')

    # Projection line through the forecast period
    # Use the average HDD for "normal", adjust for warm/cold
    weather_mult = {'normal': 1.0, 'warm': 0.90, 'cold': 1.10}.get(weather_assumption, 1.0)
    projected_hdd = avg_hdd * weather_mult
    proj_years = list(range(base_year, base_year + forecast_horizon + 1))
    proj_values = [projected_hdd] * len(proj_years)

    ax.plot(proj_years, proj_values, color='#59a14f', linewidth=2.5, linestyle='--',
            marker='D', markersize=4, label=f'Forecast ({weather_assumption}): {projected_hdd:,.0f} HDD')
    ax.fill_between(proj_years, projected_hdd * 0.9, projected_hdd * 1.1,
                     color='#59a14f', alpha=0.1)

    # Mark calibration year
    calib_year = hdd_info.get('calibration_year')
    calib_hdd = hdd_info.get('calibration_hdd')
    if calib_year and calib_hdd:
        ax.axvline(x=calib_year, color=COLORS['irp'], linestyle=':', alpha=0.7)
        ax.annotate(f'Calibration: {int(calib_year)}\n{calib_hdd:,.0f} HDD',
                    xy=(calib_year, calib_hdd), textcoords="offset points",
                    xytext=(15, 20), fontsize=9, color=COLORS['irp'],
                    arrowprops=dict(arrowstyle='->', color=COLORS['irp']))

    # Mark actual weather year used (if different)
    actual_year = hdd_info.get('actual_weather_year')
    actual_hdd = hdd_info.get('actual_hdd')
    if actual_year and actual_hdd and actual_year != calib_year:
        ax.annotate(f'Weather proxy: {int(actual_year)}\n{actual_hdd:,.0f} HDD',
                    xy=(actual_year, actual_hdd), textcoords="offset points",
                    xytext=(-60, 20), fontsize=9, color='#59a14f',
                    arrowprops=dict(arrowstyle='->', color='#59a14f'))

    # Show effective heating factor
    eff_hf = hdd_info.get('effective_heating_factor')
    cfg_hf = hdd_info.get('config_heating_factor')
    if eff_hf and cfg_hf:
        note = f'Config HF: {cfg_hf:.6f}'
        if abs(eff_hf - cfg_hf) > 0.0001:
            note += f' → Effective: {eff_hf:.6f}'
        ax.text(0.02, 0.02, note, transform=ax.transAxes, fontsize=8,
                color='gray', va='bottom')

    ax.set_title('Historical & Projected Heating Degree Days (Weighted Average)')
    ax.set_xlabel('Year')
    ax.set_ylabel('Annual HDD (base 65°F)')
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(df['year'].min() - 0.5, max(proj_years) + 0.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    _save(fig, scenario_dir / 'chart_hdd_history.png')


def chart_model_vs_irp(scenario_dir: Path):
    """16. Four-panel top-down vs bottom-up comparison."""
    path = scenario_dir / 'estimated_total_upc.csv'
    if not path.exists():
        return
    est = pd.read_csv(path)
    if 'irp_upc' not in est.columns or est['irp_upc'].isna().all():
        return

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Top left: three lines
    ax = axes[0, 0]
    ax.plot(est['year'], est['space_heating'], marker='o', color=COLORS['model'],
            linewidth=2, label='Model: Space Heating Only')
    ax.plot(est['year'], est['estimated_total_upc'], marker='s', color='#59a14f',
            linewidth=2, label='Model: Estimated Total')
    ax.plot(est['year'], est['irp_upc'], marker='^', color=COLORS['irp'],
            linewidth=2, linestyle='--', label='NW Natural IRP')
    ax.fill_between(est['year'], est['space_heating'], est['estimated_total_upc'],
                     alpha=0.1, color='#59a14f')
    ax.set_title('UPC Trajectories: Three Views')
    ax.set_ylabel('Therms / Customer / Year')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(est['year'].min(), est['year'].max())

    # Top right: zoom on gap
    ax = axes[0, 1]
    ax.plot(est['year'], est['estimated_total_upc'], marker='s', color='#59a14f',
            linewidth=2.5, label='Model Estimated Total')
    ax.plot(est['year'], est['irp_upc'], marker='^', color=COLORS['irp'],
            linewidth=2.5, linestyle='--', label='NW Natural IRP')
    ax.fill_between(est['year'], est['estimated_total_upc'], est['irp_upc'],
                     alpha=0.15, color=COLORS['irp'])
    vals = list(est['estimated_total_upc']) + list(est['irp_upc'].dropna())
    ax.set_ylim(min(vals) * 0.92, max(vals) * 1.08)
    if 'diff_vs_irp' in est.columns and 'diff_vs_irp_pct' in est.columns:
        for i in [0, len(est) - 1]:
            r = est.iloc[i]
            if pd.notna(r.get('diff_vs_irp')) and pd.notna(r.get('diff_vs_irp_pct')):
                mid = (r['estimated_total_upc'] + r['irp_upc']) / 2
                sign = '+' if r['diff_vs_irp'] >= 0 else ''
                ax.annotate(f'{sign}{r["diff_vs_irp"]:.0f} ({sign}{r["diff_vs_irp_pct"]:.1f}%)',
                             xy=(r['year'], mid), textcoords="offset points",
                             xytext=(15 if i == 0 else -90, 0), fontsize=9,
                             fontweight='bold', color=COLORS['irp'],
                             arrowprops=dict(arrowstyle='->', color=COLORS['irp']))
    ax.set_title('Zoom: Model vs IRP Gap')
    ax.set_ylabel('Therms / Customer / Year')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(est['year'].min(), est['year'].max())

    # Bottom left: decline rates
    ax = axes[1, 0]
    model_pct = est['estimated_total_upc'].pct_change() * 100
    irp_pct = est['irp_upc'].pct_change() * 100
    ax.plot(est['year'], model_pct, marker='s', color='#59a14f',
            linewidth=2, label='Model decline rate')
    ax.plot(est['year'], irp_pct, marker='^', color=COLORS['irp'],
            linewidth=2, linestyle='--', label='IRP decline rate')
    ax.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax.set_title('Annual Decline Rate (%)')
    ax.set_ylabel('Year-over-Year Change (%)')
    ax.set_xlabel('Year')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(est['year'].min(), est['year'].max())

    # Bottom right: end-use stacked vs IRP
    ax = axes[1, 1]
    enduses = ['space_heating', 'water_heating', 'cooking', 'clothes_drying', 'fireplace', 'other']
    eu_colors = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', '#bab0ac']
    bottom = np.zeros(len(est))
    for eu, color in zip(enduses, eu_colors):
        if eu in est.columns:
            label = eu.replace('_', ' ').title()
            ax.fill_between(est['year'], bottom, bottom + est[eu].values,
                             color=color, alpha=0.7, label=label)
            bottom += est[eu].values
    ax.plot(est['year'], est['irp_upc'], color='black', linewidth=2.5,
            linestyle='--', marker='^', markersize=5, label='IRP Forecast')
    ax.set_title('End-Use Breakdown vs IRP')
    ax.set_ylabel('Therms / Customer / Year')
    ax.set_xlabel('Year')
    ax.legend(fontsize=7, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(est['year'].min(), est['year'].max())

    fig.suptitle('NW Natural IRP (Top-Down) vs Bottom-Up End-Use Model', fontsize=14, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    _save(fig, scenario_dir / 'chart_model_vs_irp.png')


def chart_vintage_demand(scenario_dir: Path):
    """17. Demand by vintage era over time."""
    path = scenario_dir / 'vintage_demand.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)
    if df.empty:
        return

    era_colors = {
        'pre-1980': '#e15759', '1980-1999': '#f28e2b', '2000-2009': '#4e79a7',
        '2010-2014': '#76b7b2', '2015+': '#59a14f', 'Unknown': '#bab0ac',
    }
    ordered = ['pre-1980', '1980-1999', '2000-2009', '2010-2014', '2015+', 'Unknown']
    is_monthly = 'month' in df.columns

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    if is_monthly:
        df = df.sort_values(['year', 'month']).copy()
        df['decimal_year'] = df['year'] + (df['month'] - 1) / 12.0
        x_vals = sorted(df['decimal_year'].unique())
        eras = [e for e in ordered if e in df['vintage_era'].unique()]

        bottom = np.zeros(len(x_vals))
        for era in eras:
            color = era_colors.get(era, '#bab0ac')
            era_data = df[df['vintage_era'] == era].set_index('decimal_year')['total_therms'].reindex(x_vals, fill_value=0)
            ax1.fill_between(x_vals, bottom, bottom + era_data.values, color=color, alpha=0.7, label=era)
            bottom += era_data.values

        for era in eras:
            color = era_colors.get(era, '#bab0ac')
            era_data = df[df['vintage_era'] == era].set_index('decimal_year')['avg_therms'].reindex(x_vals)
            ax2.plot(x_vals, era_data.values, color=color, linewidth=1.5, label=era)

        years = sorted(df['year'].unique())
        base_year = int(df['year'].min())
        for ax in (ax1, ax2):
            ax.set_xticks([float(y) for y in years])
            ax.set_xticklabels([str(int(y)) for y in years], fontsize=9)
            ax.set_xlabel('Year (monthly resolution)')
            ax.axvline(x=base_year + 1, color='#7f7f7f', linestyle=':', linewidth=1.5, alpha=0.6)
    else:
        pivot = df.pivot(index='year', columns='vintage_era', values='total_therms').fillna(0)
        cols = [c for c in ordered if c in pivot.columns]
        pivot = pivot[cols]
        bottom = np.zeros(len(pivot))
        for era in cols:
            color = era_colors.get(era, '#bab0ac')
            ax1.fill_between(pivot.index, bottom, bottom + pivot[era].values, color=color, alpha=0.7, label=era)
            bottom += pivot[era].values
        ax1.set_xlim(pivot.index.min(), pivot.index.max())
        ax1.set_xlabel('Year')

        pivot_avg = df.pivot(index='year', columns='vintage_era', values='avg_therms').fillna(0)
        pivot_avg = pivot_avg[[c for c in ordered if c in pivot_avg.columns]]
        for era in pivot_avg.columns:
            color = era_colors.get(era, '#bab0ac')
            ax2.plot(pivot_avg.index, pivot_avg[era], marker='o', markersize=3, color=color, linewidth=1.5, label=era)
        ax2.set_xlim(pivot_avg.index.min(), pivot_avg.index.max())
        ax2.set_xlabel('Year')

    ax1.set_title('Total Demand by Vintage Era')
    ax1.set_ylabel('Total Therms')
    ax1.legend(fontsize=7)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    ax2.set_title('Avg Therms per Premise by Vintage')
    ax2.set_ylabel('Therms / Premise')
    ax2.legend(fontsize=7)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_vintage_demand.png')


def chart_new_stock_type(scenario_dir: Path):
    """18. Housing stock composition showing new vs existing by segment."""
    path = scenario_dir / 'housing_stock.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)

    seg_cols = [c for c in df.columns if c not in ['year', 'total_units', 'growth_rate', 'scenario_name']]
    if not seg_cols:
        return

    # Sort so RESSF is first (bottom), RESMF second
    preferred = ['RESSF', 'RESMF', 'Unclassified']
    seg_cols = [c for c in preferred if c in seg_cols] + [c for c in seg_cols if c not in preferred]

    seg_colors = {'RESSF': '#4e79a7', 'RESMF': '#f28e2b', 'Unclassified': '#bab0ac'}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Left: stacked bar of stock by segment (y-axis starts at 0 to show both)
    bar_width = 0.7
    bottom = np.zeros(len(df))
    for seg in seg_cols:
        color = seg_colors.get(seg, '#76b7b2')
        ax1.bar(df['year'], df[seg], bar_width, bottom=bottom,
                color=color, edgecolor='white', label=seg, alpha=0.8)
        bottom += df[seg].values
    ax1.set_title('Housing Stock by Segment Type')
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Units')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax1.set_ylim(bottom=0)

    # Right: segment share over time (100% stacked area)
    totals = df[seg_cols].sum(axis=1)
    bottom2 = np.zeros(len(df))
    for seg in seg_cols:
        color = seg_colors.get(seg, '#76b7b2')
        pct = df[seg].values / totals.values * 100
        ax2.fill_between(df['year'], bottom2, bottom2 + pct,
                         color=color, alpha=0.7, label=seg)
        # Annotate the share at start and end
        mid = bottom2 + pct / 2
        ax2.text(df['year'].iloc[0], mid[0], f'{pct[0]:.1f}%',
                 ha='center', va='center', fontsize=8, fontweight='bold', color='white')
        ax2.text(df['year'].iloc[-1], mid[-1], f'{pct[-1]:.1f}%',
                 ha='center', va='center', fontsize=8, fontweight='bold', color='white')
        bottom2 += pct
    ax2.set_title('Segment Share Over Time (%)')
    ax2.set_xlabel('Year')
    ax2.set_ylabel('Share (%)')
    ax2.set_ylim(0, 100)
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(df['year'].min(), df['year'].max())

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_new_stock_type.png')


def chart_recs_enduse_trend(scenario_dir: Path):
    """Chart 21: RECS end-use shares over time (1993-2020)."""
    csv = scenario_dir / 'recs_enduse_trend.csv'
    if not csv.exists():
        return
    try:
        df = pd.read_csv(csv)
        if df.empty:
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Left: stacked area of end-use shares
        ax1.fill_between(df['year'], 0, df['sh_pct'],
                         color='#4e79a7', alpha=0.7, label='Space Heating')
        ax1.fill_between(df['year'], df['sh_pct'], df['sh_pct'] + df['wh_pct'],
                         color='#f28e2b', alpha=0.7, label='Water Heating')
        ax1.fill_between(df['year'], df['sh_pct'] + df['wh_pct'], 100,
                         color='#59a14f', alpha=0.7, label='Appliances (Cook/Dry/Other)')
        ax1.set_title('RECS Pacific Division: Gas End-Use Shares\n(1993-2020)')
        ax1.set_xlabel('Survey Year')
        ax1.set_ylabel('Share of Total Gas (%)')
        ax1.set_ylim(0, 100)
        ax1.legend(fontsize=8, loc='center right')
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(df['year'].min(), df['year'].max())

        # Right: total therms/yr trend
        ax2.plot(df['year'], df['total_therms'], 'o-', color='#4e79a7',
                 linewidth=2, markersize=8)
        for _, row in df.iterrows():
            ax2.annotate(f"{row['total_therms']:.0f}",
                         xy=(row['year'], row['total_therms']),
                         textcoords="offset points", xytext=(0, 10),
                         ha='center', fontsize=8)
        ax2.set_title('RECS Pacific Division: Total Gas UPC\n(Therms/Customer/Year)')
        ax2.set_xlabel('Survey Year')
        ax2.set_ylabel('Therms / Customer / Year')
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(df['year'].min() - 1, df['year'].max() + 1)
        # Don't start at 0
        ymin = df['total_therms'].min() * 0.85
        ax2.set_ylim(bottom=ymin)

        fig.tight_layout()
        _save(fig, scenario_dir / 'chart_recs_enduse_trend.png')
    except Exception as e:
        logger.warning(f"chart_recs_enduse_trend failed: {e}")


def chart_census_vs_model_housing(scenario_dir: Path):
    """Chart 20: Census total housing vs model NW Natural gas customers by year."""
    csv = scenario_dir / 'census_vs_model_housing.csv'
    if not csv.exists():
        return
    try:
        df = pd.read_csv(csv)
        census = df[df['source'] == 'census'].copy()
        model = df[df['source'] == 'model'].copy()
        if census.empty and model.empty:
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # --- Left panel: total housing units (Census) vs NW Natural gas customers (model) ---
        if not census.empty:
            ax1.plot(census['year'], census['census_total_units'], 'o-',
                     color='#2c3e50', linewidth=2, markersize=5,
                     label='Census: All Housing Units')
            ax1.plot(census['year'], census['census_gas_units'], 's-',
                     color=COLORS['gas'], linewidth=2, markersize=5,
                     label='Census: Gas-Heated Units')
        if not model.empty:
            ax1.plot(model['year'], model['model_total_units'], '^-',
                     color='#e74c3c', linewidth=2, markersize=6,
                     label='Model: NW Natural Gas Customers')
            if 'model_territory_total' in model.columns:
                ax1.plot(model['year'], model['model_territory_total'], 'D--',
                         color='#95a5a6', linewidth=1.5, markersize=5,
                         label='Model: Est. Territory Total')

        ax1.set_title('Census Housing Units vs Model Gas Customers')
        ax1.set_xlabel('Year')
        ax1.set_ylabel('Housing Units')
        ax1.legend(fontsize=7, loc='upper left')
        ax1.grid(True, alpha=0.3)
        ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

        # --- Right panel: gas share % over time (Census historical + model projection) ---
        if not census.empty:
            ax2.plot(census['year'], census['census_gas_pct'], 'o-',
                     color=COLORS['gas'], linewidth=2, markersize=5,
                     label='Census: Gas Heating %')
            # Add electric % on same axis
            if 'electric_pct' not in census.columns:
                # Load from the trend CSV
                trend_csv = scenario_dir / 'census_heating_fuel_trend.csv'
                if trend_csv.exists():
                    trend = pd.read_csv(trend_csv)
                    ax2.plot(trend['year'], trend['electric_pct'], 's-',
                             color=COLORS['electric'], linewidth=2, markersize=5,
                             label='Census: Electric Heating %')

        ax2.set_title('Heating Fuel Market Share (Census B25040)')
        ax2.set_xlabel('Year')
        ax2.set_ylabel('Share of Occupied Housing Units (%)')
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        # Add vertical line at transition from historical to forecast
        if not census.empty and not model.empty:
            transition_year = census['year'].max()
            for ax in [ax1, ax2]:
                ax.axvline(x=transition_year, color='gray', linestyle=':', alpha=0.5)
            ax1.text(transition_year + 0.3, ax1.get_ylim()[1] * 0.98,
                     'Forecast →', fontsize=8, color='gray', va='top')
            ax1.text(transition_year - 0.3, ax1.get_ylim()[1] * 0.98,
                     '← Census', fontsize=8, color='gray', va='top', ha='right')

        fig.tight_layout()
        _save(fig, scenario_dir / 'chart_census_vs_model_housing.png')
    except Exception as e:
        logger.warning(f"chart_census_vs_model_housing failed: {e}")


def chart_census_heating_fuel_trend(scenario_dir: Path):
    """Chart 19: Census B25040 gas (with hybrid split) vs electric heating share over time."""
    csv = scenario_dir / 'census_heating_fuel_trend.csv'
    if not csv.exists():
        return
    try:
        df = pd.read_csv(csv)
        if df.empty or 'year' not in df.columns:
            return

        has_hybrid = 'hybrid_pct_est' in df.columns and df['hybrid_pct_est'].sum() > 0
        has_gas_only = 'gas_only_pct_est' in df.columns

        fig, ax = plt.subplots(figsize=(12, 6))

        if has_hybrid and has_gas_only:
            ax.plot(df['year'], df['gas_only_pct_est'], 'o-', color='#e67e22', linewidth=2, markersize=6, label='Gas Only (est.) %')
            ax.plot(df['year'], df['hybrid_pct_est'], 'D-', color='#9b59b6', linewidth=2, markersize=6, label='Hybrid (est.) %')
            ax.plot(df['year'], df['gas_pct'], 's--', color='#e67e22', linewidth=1, markersize=4, alpha=0.5, label='Total Gas (Census reported) %')
        else:
            ax.plot(df['year'], df['gas_pct'], 'o-', color='#e67e22', linewidth=2, markersize=6, label='Gas Heating %')

        ax.plot(df['year'], df['electric_pct'], 's-', color='#3498db', linewidth=2, markersize=6, label='Electric Heating %')

        ax.set_xlabel('Year')
        ax.set_ylabel('Share of Occupied Housing Units (%)')
        ax.set_title('Census B25040: Heating Fuel Trend\nNW Natural Service Territory Counties (hybrid estimated from heat pump adoption)')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(df['year'].min() - 0.5, df['year'].max() + 0.5)
        fig.tight_layout()
        _save(fig, scenario_dir / 'chart_census_heating_fuel_trend.png')
    except Exception as e:
        logger.warning(f"chart_census_heating_fuel_trend failed: {e}")


def chart_housing_vintage_stock(scenario_dir: Path):
    """Chart 22: Housing stock by vintage era over time (stacked area)."""
    csv = scenario_dir / 'vintage_demand.csv'
    if not csv.exists():
        return
    try:
        df = pd.read_csv(csv)
        if df.empty or 'vintage_era' not in df.columns:
            return

        # Pivot to get equipment_count per vintage era per year
        pivot = df.pivot_table(index='year', columns='vintage_era',
                               values='equipment_count', aggfunc='sum').fillna(0)

        # Order eras chronologically
        era_order = ['pre-1980', '1980-1999', '2000-2009', '2010-2014', '2015+']
        era_order = [e for e in era_order if e in pivot.columns]
        # Add any extras (like 'Unknown')
        extras = [c for c in pivot.columns if c not in era_order]
        cols = era_order + extras
        pivot = pivot[cols]

        era_colors = {
            'pre-1980': '#e15759',
            '1980-1999': '#f28e2b',
            '2000-2009': '#edc948',
            '2010-2014': '#76b7b2',
            '2015+': '#59a14f',
            'Unknown': '#bab0ac',
        }

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Left: stacked area (absolute counts)
        bottom = np.zeros(len(pivot))
        for era in cols:
            color = era_colors.get(era, '#bab0ac')
            ax1.fill_between(pivot.index, bottom, bottom + pivot[era].values,
                             color=color, alpha=0.7, label=era)
            bottom += pivot[era].values

        ax1.set_title('Housing Stock by Vintage Era')
        ax1.set_xlabel('Year')
        ax1.set_ylabel('Equipment Units')
        ax1.legend(fontsize=8, loc='upper left')
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(pivot.index.min(), pivot.index.max())
        ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

        # Right: 100% stacked (share over time)
        totals = pivot.sum(axis=1)
        bottom2 = np.zeros(len(pivot))
        for era in cols:
            color = era_colors.get(era, '#bab0ac')
            pct = pivot[era].values / totals.values * 100
            ax2.fill_between(pivot.index, bottom2, bottom2 + pct,
                             color=color, alpha=0.7, label=era)
            bottom2 += pct

        ax2.set_title('Vintage Share of Housing Stock (%)')
        ax2.set_xlabel('Year')
        ax2.set_ylabel('Share (%)')
        ax2.set_ylim(0, 100)
        ax2.legend(fontsize=8, loc='center right')
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(pivot.index.min(), pivot.index.max())

        fig.tight_layout()
        _save(fig, scenario_dir / 'chart_housing_vintage_stock.png')
    except Exception as e:
        logger.warning(f"chart_housing_vintage_stock failed: {e}")


def chart_envelope_efficiency(scenario_dir: Path):
    """Chart 23: Building envelope efficiency by segment over time."""
    csv = scenario_dir / 'envelope_efficiency.csv'
    if not csv.exists():
        return
    try:
        df = pd.read_csv(csv)
        if df.empty:
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

        # Left: fleet average envelope index by segment
        ax1.plot(df['year'], df['envelope_index_sf'], 'o-', color='#4e79a7',
                 linewidth=2, markersize=6, label='Single Family (fleet avg)')
        ax1.plot(df['year'], df['envelope_index_mf'], 's-', color='#f28e2b',
                 linewidth=2, markersize=6, label='Multi-Family (fleet avg)')
        ax1.plot(df['year'], df['envelope_index_all'], 'D--', color='#59a14f',
                 linewidth=1.5, markersize=5, label='All Premises (fleet avg)')
        ax1.plot(df['year'], df['new_construction_index'], '^:', color='#e15759',
                 linewidth=2, markersize=6, label='New Construction')

        ax1.set_title('Building Envelope Efficiency Index\n(1.0 = 2000-2009 baseline, lower = more efficient)')
        ax1.set_xlabel('Year')
        ax1.set_ylabel('Envelope Efficiency Index')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(df['year'].min(), df['year'].max())
        ax1.invert_yaxis()  # Lower = better, so invert

        # Right: improvement rate (% change from base year)
        base_sf = df.iloc[0]['envelope_index_sf']
        base_mf = df.iloc[0]['envelope_index_mf']
        base_new = df.iloc[0]['new_construction_index']
        ax2.plot(df['year'], (1 - df['envelope_index_sf'] / base_sf) * 100, 'o-',
                 color='#4e79a7', linewidth=2, markersize=6, label='SF improvement')
        ax2.plot(df['year'], (1 - df['envelope_index_mf'] / base_mf) * 100, 's-',
                 color='#f28e2b', linewidth=2, markersize=6, label='MF improvement')
        ax2.plot(df['year'], (1 - df['new_construction_index'] / base_new) * 100, '^:',
                 color='#e15759', linewidth=2, markersize=6, label='New construction improvement')

        ax2.set_title('Cumulative Envelope Improvement (%)')
        ax2.set_xlabel('Year')
        ax2.set_ylabel('Improvement from Base Year (%)')
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(df['year'].min(), df['year'].max())

        fig.suptitle('Building Envelope Efficiency: Fleet Average & New Construction', fontsize=13, fontweight='bold')
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        _save(fig, scenario_dir / 'chart_envelope_efficiency.png')
    except Exception as e:
        logger.warning(f"chart_envelope_efficiency failed: {e}")




def chart_monthly_upc_heatmap(scenario_dir: Path):
    """Monthly UPC heatmap: rows=year, columns=month, color=therms/customer/month."""
    path = scenario_dir / 'monthly_summary.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)
    if 'month' not in df.columns or 'use_per_customer' not in df.columns:
        return

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    years = sorted(df['year'].unique())

    pivot = df.pivot_table(index='year', columns='month', values='use_per_customer', aggfunc='sum')
    pivot = pivot.reindex(columns=range(1, 13))

    fig, ax = plt.subplots(figsize=(13, max(4, len(years) * 0.6 + 1.5)))
    im = ax.imshow(pivot.values, aspect='auto', cmap='YlOrRd', interpolation='nearest')

    ax.set_xticks(range(12))
    ax.set_xticklabels(month_names, fontsize=9)
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels([str(int(y)) for y in years], fontsize=9)

    vmax = float(np.nanmax(pivot.values))
    for i in range(len(years)):
        for j in range(12):
            try:
                val = float(pivot.iloc[i, j])
            except Exception:
                continue
            if not pd.isna(val):
                text_color = 'white' if val > vmax * 0.65 else 'black'
                ax.text(j, i, f'{val:.0f}', ha='center', va='center',
                        fontsize=7, color=text_color)

    plt.colorbar(im, ax=ax, label='Therms / Customer / Month', shrink=0.8)
    ax.set_title('Monthly UPC Heatmap (therms/customer/month)')
    ax.set_xlabel('Month')
    ax.set_ylabel('Year')
    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_monthly_upc_heatmap.png')


def chart_monthly_demand_profile(scenario_dir: Path):
    """Continuous monthly time-series: 12 x N points on a decimal-year axis."""
    path = scenario_dir / 'monthly_summary.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)
    if 'month' not in df.columns:
        return

    # Decimal year: Jan 2025 = 2025.0, Feb = 2025.083, ..., Dec = 2025.917
    df = df.sort_values(['year', 'month']).copy()
    df['decimal_year'] = df['year'] + (df['month'] - 1) / 12.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Top: total therms per month (all N*12 points)
    ax1.plot(df['decimal_year'], df['total_therms'],
             color=COLORS['model'], linewidth=1.5, alpha=0.85)
    ax1.fill_between(df['decimal_year'], 0, df['total_therms'],
                     color=COLORS['model'], alpha=0.15)
    ax1.set_ylabel('Total Therms / Month')
    ax1.set_title('Monthly Total Demand — Full Forecast Horizon')
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax1.grid(True, alpha=0.3)

    # Mark projection start
    base_year = int(df['year'].min())
    ax1.axvline(x=base_year + 1, color='#7f7f7f', linestyle=':', linewidth=1.5, alpha=0.6)
    ylim1 = ax1.get_ylim()
    ax1.text(base_year + 1.05, ylim1[1] * 0.95, 'Projected ->',
             fontsize=8, color='#7f7f7f', va='top')

    # Bottom: monthly UPC (therms/customer/month)
    ax2.plot(df['decimal_year'], df['use_per_customer'],
             color=COLORS['irp'], linewidth=1.5, alpha=0.85)
    ax2.fill_between(df['decimal_year'], 0, df['use_per_customer'],
                     color=COLORS['irp'], alpha=0.15)
    ax2.set_ylabel('Therms / Customer / Month')
    ax2.set_title('Monthly UPC — Full Forecast Horizon')
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.1f}'))
    ax2.grid(True, alpha=0.3)
    ax2.axvline(x=base_year + 1, color='#7f7f7f', linestyle=':', linewidth=1.5, alpha=0.6)

    # X-axis: year labels at Jan of each year
    years = sorted(df['year'].unique())
    ax2.set_xticks([float(y) for y in years])
    ax2.set_xticklabels([str(int(y)) for y in years], fontsize=9)
    ax2.set_xlabel('Year')

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_monthly_demand_profile.png')


def chart_monthly_seasonal_overlay(scenario_dir: Path):
    """Seasonal overlay: each year's 12-month profile on a single Jan-Dec axis."""
    path = scenario_dir / 'monthly_summary.csv'
    if not path.exists():
        return
    df = pd.read_csv(path)
    if 'month' not in df.columns:
        return

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    years = sorted(df['year'].unique())
    cmap_vals = plt.cm.Blues(np.linspace(0.3, 0.95, len(years)))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Left: total therms by month, each year as a line
    for i, yr in enumerate(years):
        yr_data = df[df['year'] == yr].sort_values('month')
        is_edge = yr in (years[0], years[-1])
        lw = 2.5 if is_edge else 1.0
        alpha = 1.0 if is_edge else 0.45
        label = str(int(yr)) if is_edge else None
        ax1.plot(yr_data['month'], yr_data['total_therms'],
                 color=cmap_vals[i], linewidth=lw, alpha=alpha,
                 marker='o', markersize=4 if is_edge else 2, label=label)

    ax1.set_title('Monthly Total Demand by Year')
    ax1.set_xlabel('Month')
    ax1.set_ylabel('Total Therms')
    ax1.set_xticks(range(1, 13))
    ax1.set_xticklabels(month_names, fontsize=8)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    # Right: seasonal share (% of annual) for base vs final year
    for yr, color, style, label in [
        (years[0], COLORS['model'], '-', f'{int(years[0])} (base)'),
        (years[-1], COLORS['irp'], '--', f'{int(years[-1])} (final)'),
    ]:
        yr_data = df[df['year'] == yr].sort_values('month')
        annual_total = yr_data['total_therms'].sum()
        if annual_total > 0:
            pct = yr_data['total_therms'] / annual_total * 100
            ax2.plot(yr_data['month'], pct.values, color=color, linewidth=2,
                     linestyle=style, marker='o', markersize=5, label=label)

    ax2.set_title('Seasonal Share of Annual Demand (%)')
    ax2.set_xlabel('Month')
    ax2.set_ylabel('Share of Annual Total (%)')
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(month_names, fontsize=8)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    _save(fig, scenario_dir / 'chart_monthly_seasonal_overlay.png')


def generate_scenario_charts(scenario_dir: Path):
    """Generate all charts for a scenario folder."""
    scenario_dir = Path(scenario_dir)
    logger.info(f"Generating charts for {scenario_dir}...")

    chart_upc_trajectory(scenario_dir)
    chart_equipment_fuel_mix(scenario_dir)
    chart_efficiency_trajectory(scenario_dir)
    chart_replacements(scenario_dir)
    chart_housing_stock(scenario_dir)
    chart_premise_distribution(scenario_dir)
    chart_segment_demand(scenario_dir)
    chart_total_demand(scenario_dir)
    chart_cumulative_reduction(scenario_dir)
    chart_territory_electrification(scenario_dir)
    chart_estimated_total_upc(scenario_dir)
    chart_enduse_breakdown(scenario_dir)
    chart_three_way_comparison(scenario_dir)
    chart_monthly_seasonal(scenario_dir)
    chart_hdd_history(scenario_dir)
    chart_model_vs_irp(scenario_dir)
    chart_vintage_demand(scenario_dir)
    chart_new_stock_type(scenario_dir)
    chart_census_heating_fuel_trend(scenario_dir)
    chart_census_vs_model_housing(scenario_dir)
    chart_recs_enduse_trend(scenario_dir)
    chart_housing_vintage_stock(scenario_dir)
    chart_envelope_efficiency(scenario_dir)

    # Monthly-only charts (only when temporal_resolution == 'monthly')
    if _is_monthly_run(scenario_dir):
        logger.info("  Monthly resolution detected — generating monthly charts...")
        chart_monthly_upc_heatmap(scenario_dir)
        chart_monthly_demand_profile(scenario_dir)
        chart_monthly_seasonal_overlay(scenario_dir)

    logger.info(f"Charts complete for {scenario_dir}")
