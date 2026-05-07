"""Generate the top-down vs bottom-up comparison chart for MODEL_VS_IRP_COMPARISON.md."""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from pathlib import Path

def generate():
    est = pd.read_csv('scenarios/baseline/estimated_total_upc.csv')
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # --- Top left: Three lines (SH only, estimated total, IRP) ---
    ax = axes[0, 0]
    ax.plot(est['year'], est['space_heating'], marker='o', color='#4e79a7',
            linewidth=2, label='Model: Space Heating Only')
    ax.plot(est['year'], est['estimated_total_upc'], marker='s', color='#59a14f',
            linewidth=2, label='Model: Estimated Total')
    ax.plot(est['year'], est['irp_upc'], marker='^', color='#e15759',
            linewidth=2, linestyle='--', label='NW Natural IRP')
    ax.fill_between(est['year'], est['space_heating'], est['estimated_total_upc'],
                     alpha=0.1, color='#59a14f')
    ax.set_title('UPC Trajectories: Three Views', fontsize=11)
    ax.set_ylabel('Therms / Customer / Year')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(est['year'].min(), est['year'].max())
    
    # --- Top right: Zoom on estimated total vs IRP ---
    ax = axes[0, 1]
    ax.plot(est['year'], est['estimated_total_upc'], marker='s', color='#59a14f',
            linewidth=2.5, label='Model Estimated Total')
    ax.plot(est['year'], est['irp_upc'], marker='^', color='#e15759',
            linewidth=2.5, linestyle='--', label='NW Natural IRP')
    ax.fill_between(est['year'], est['estimated_total_upc'], est['irp_upc'],
                     alpha=0.15, color='#e15759')
    vals = list(est['estimated_total_upc']) + list(est['irp_upc'])
    ax.set_ylim(min(vals) * 0.92, max(vals) * 1.08)
    # Annotate gap at start and end
    for i in [0, len(est) - 1]:
        r = est.iloc[i]
        diff = r['estimated_total_upc'] - r['irp_upc']
        mid = (r['estimated_total_upc'] + r['irp_upc']) / 2
        ax.annotate(f'+{diff:.0f} ({r["diff_vs_irp_pct"]:.1f}%)',
                     xy=(r['year'], mid), textcoords="offset points",
                     xytext=(15 if i == 0 else -80, 0), fontsize=9,
                     fontweight='bold', color='#e15759',
                     arrowprops=dict(arrowstyle='->', color='#e15759'))
    ax.set_title('Zoom: Model vs IRP Gap', fontsize=11)
    ax.set_ylabel('Therms / Customer / Year')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(est['year'].min(), est['year'].max())
    
    # --- Bottom left: Annual decline rates ---
    ax = axes[1, 0]
    model_pct = est['estimated_total_upc'].pct_change() * 100
    irp_pct = est['irp_upc'].pct_change() * 100
    ax.plot(est['year'], model_pct, marker='s', color='#59a14f',
            linewidth=2, label='Model decline rate')
    ax.plot(est['year'], irp_pct, marker='^', color='#e15759',
            linewidth=2, linestyle='--', label='IRP decline rate (-1.19%)')
    ax.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax.set_title('Annual Decline Rate (%)', fontsize=11)
    ax.set_ylabel('Year-over-Year Change (%)')
    ax.set_xlabel('Year')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(est['year'].min(), est['year'].max())
    
    # --- Bottom right: End-use breakdown stacked ---
    ax = axes[1, 1]
    enduses = ['space_heating', 'water_heating', 'cooking', 'clothes_drying', 'fireplace', 'other']
    colors = ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', '#bab0ac']
    bottom = np.zeros(len(est))
    for eu, color in zip(enduses, colors):
        if eu in est.columns:
            label = eu.replace('_', ' ').title()
            ax.fill_between(est['year'], bottom, bottom + est[eu].values,
                             color=color, alpha=0.7, label=label)
            bottom += est[eu].values
    ax.plot(est['year'], est['irp_upc'], color='black', linewidth=2.5,
            linestyle='--', marker='^', markersize=5, label='IRP Forecast')
    ax.set_title('End-Use Breakdown vs IRP', fontsize=11)
    ax.set_ylabel('Therms / Customer / Year')
    ax.set_xlabel('Year')
    ax.legend(fontsize=7, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(est['year'].min(), est['year'].max())
    
    fig.suptitle('NW Natural IRP (Top-Down) vs Bottom-Up End-Use Model', fontsize=14, fontweight='bold')
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    
    out = Path('output/model_vs_irp_comparison.png')
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"Chart saved to {out}")
    
    # Also copy to both scenario folders
    import shutil
    for folder in ['scenarios/baseline', 'scenarios/baseline_monthly']:
        if Path(folder).exists():
            shutil.copy2(str(out), f'{folder}/chart_model_vs_irp.png')
            print(f"Copied to {folder}/chart_model_vs_irp.png")

if __name__ == '__main__':
    generate()
