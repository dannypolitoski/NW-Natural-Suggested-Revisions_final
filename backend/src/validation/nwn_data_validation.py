"""
NW Natural source data validation suite — Task 15.

Comprehensive validation of all NW Natural source data files.
All outputs saved to output/nwn_data_validation/ as HTML + MD + PNG charts.

Run standalone:
    python -m src.validation.nwn_data_validation
"""

import os
import io
import base64
import logging
import warnings
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import config

logger = logging.getLogger(__name__)

OUT_DIR = os.path.join("output", "nwn_data_validation")

# ============================================================================
# Test descriptions — injected into every HTML + MD report
# ============================================================================

DESCRIPTIONS = {
    "referential_integrity": {
        "purpose": "Verify that every blinded_id referenced in equipment_data, segment_data, and billing_data also exists in premise_data.",
        "why": (
            "Orphan IDs indicate records that cannot be linked back to a known premise. "
            "These rows will be silently dropped during the premise-equipment join, potentially "
            "under-counting equipment or billing history. A high orphan rate may signal a data "
            "extract mismatch (e.g., equipment exported for all customers but premises filtered "
            "to active-residential only)."
        ),
        "how_to_read": (
            "The match rate should be close to 100% for each source table. "
            "Orphan counts > 0 are common for billing (closed accounts) but should be near zero "
            "for equipment and segment. The time-series chart shows whether orphans cluster in "
            "specific vintage years, which may indicate a historical data cutoff."
        ),
        "action": (
            "If equipment orphan rate > 5%, investigate whether the premise filter (custtype='R', "
            "status_code='AC') is too restrictive. If billing orphan rate is high, confirm that "
            "billing data includes closed/inactive accounts that are excluded from premise_data."
        ),
    },
    "equipment_code_validity": {
        "purpose": "Verify that every equipment_type_code in equipment_data exists in the equipment_codes.csv lookup table.",
        "why": (
            "Unknown equipment codes cannot be mapped to an end-use category (space heating, "
            "water heating, etc.) via END_USE_MAP. Rows with unknown codes will receive a null "
            "end_use and may be excluded from simulation, leading to under-counted demand."
        ),
        "how_to_read": (
            "The valid rate should be close to 100%. The bar chart shows the most common codes "
            "color-coded green (valid) or red (unknown). The pie chart gives the overall split. "
            "The unknown codes table lists specific codes that need to be added to equipment_codes.csv "
            "or mapped in END_USE_MAP."
        ),
        "action": (
            "If unknown codes represent > 1% of rows, add them to equipment_codes.csv and update "
            "END_USE_MAP in src/config.py. Check whether unknown codes are typos, deprecated codes, "
            "or genuinely new equipment types."
        ),
    },
    "duplicate_detection": {
        "purpose": "Detect exact duplicate rows in equipment_data (same blinded_id + equipment_type_code + QTY).",
        "why": (
            "Duplicate equipment rows inflate the equipment count per premise, which directly "
            "inflates simulated demand. A premise with two identical furnace records will be "
            "modeled as having two furnaces, doubling its space heating consumption."
        ),
        "how_to_read": (
            "The duplication rate should be low (< 5%). The bar chart shows which equipment types "
            "are most duplicated — if a single code dominates, it may be a systematic data entry "
            "issue. The histogram shows how many duplicates each affected premise has."
        ),
        "action": (
            "Review duplicate_equipment.csv for patterns. If duplicates are systematic (e.g., "
            "every premise has exactly 2 rows for the same code), consider deduplicating in the "
            "data ingestion pipeline. If sporadic, they may be legitimate (e.g., two identical "
            "water heaters in a large home)."
        ),
    },
    "weather_station_coverage": {
        "purpose": "Verify that every district_code_IRP in premise_data maps to a weather station via DISTRICT_WEATHER_MAP.",
        "why": (
            "Weather-sensitive end-use simulation (space heating, water heating) requires daily "
            "temperature data from a nearby weather station. Premises in unmapped districts will "
            "have no weather data and cannot be simulated, creating a gap in demand projections."
        ),
        "how_to_read": (
            "All districts should be mapped (0 unmapped). The bar chart shows premise counts by "
            "district — unmapped districts in red represent premises that will be excluded from "
            "weather-driven simulation."
        ),
        "action": (
            "If any districts are unmapped, add them to DISTRICT_WEATHER_MAP in src/config.py. "
            "Choose the nearest weather station based on geographic proximity and climate similarity."
        ),
    },
    "billing_coverage": {
        "purpose": "Measure what fraction of active residential premises have billing history available.",
        "why": (
            "Billing data is the primary calibration target — the model's simulated demand should "
            "match observed billing therms. Premises without billing data cannot be validated, and "
            "low coverage reduces confidence in calibration. Coverage by district reveals whether "
            "certain areas are systematically under-represented."
        ),
        "how_to_read": (
            "Coverage should be > 80% for reliable calibration. The district bar chart shows "
            "whether coverage is uniform or concentrated in certain areas. The time-series shows "
            "billing data availability over time — gaps indicate periods where calibration is weak. "
            "The histogram shows billing history depth per premise (more records = better calibration)."
        ),
        "action": (
            "If coverage < 80%, investigate whether billing data was filtered or truncated during "
            "extraction. If certain districts have very low coverage, consider using district-level "
            "aggregate billing data as a fallback calibration target."
        ),
    },
    "weather_continuity": {
        "purpose": "Check for missing dates in the daily weather time series for each weather station.",
        "why": (
            "Missing weather days create gaps in HDD calculations. If a cold week is missing, "
            "the model will under-estimate space heating demand for that period. Systematic gaps "
            "(e.g., a station offline for months) can bias annual HDD totals and distort the "
            "weather-normalization process."
        ),
        "how_to_read": (
            "Each station should have close to 100% of expected days. The heatmap shows "
            "completeness by station and month — red cells indicate months with significant gaps. "
            "The daily record count should be a flat line at the number of stations (11). "
            "The annual HDD chart should show smooth trends — sudden drops indicate data gaps."
        ),
        "action": (
            "If a station has > 30 missing days, consider interpolating from nearby stations or "
            "using NOAA Climate Normals as a fill. If the longest gap exceeds 90 days, that "
            "station's annual HDD is unreliable for the affected year."
        ),
    },
    "segment_consistency": {
        "purpose": "Verify that every active residential premise has exactly one segment record (RESSF, RESMF, or MOBILE).",
        "why": (
            "The segment determines the building type used in simulation (single-family, "
            "multi-family, mobile home). Premises with 0 segments cannot be classified and will "
            "be excluded. Premises with 2+ segments create ambiguity — the model may double-count "
            "them or pick an arbitrary segment."
        ),
        "how_to_read": (
            "Ideally: 0 premises with 0 segments, all premises with exactly 1 segment, and 0 "
            "premises with 2+ segments. The segment distribution bar chart shows the overall mix. "
            "The set-year histogram reveals when segments were assigned — a spike in a single year "
            "may indicate a bulk data migration."
        ),
        "action": (
            "If premises have 0 segments, check whether the segment_data filter (RESSF/RESMF/MOBILE) "
            "is too restrictive. If premises have 2+ segments, deduplicate by keeping the most "
            "recent setyear or the segment with the highest confidence."
        ),
    },
    "equipment_quantity": {
        "purpose": "Check QTY_OF_EQUIPMENT_TYPE values for sanity — most premises should have 1-3 units per equipment type.",
        "why": (
            "Equipment quantity directly multiplies simulated demand. A QTY of 10 furnaces for a "
            "single-family home is almost certainly a data error and would inflate that premise's "
            "space heating demand by 10x. Conversely, QTY ≤ 0 is invalid and would produce zero "
            "or negative demand."
        ),
        "how_to_read": (
            "The histogram should be heavily concentrated at QTY = 1, with a small tail at 2-3. "
            "QTY > 5 is flagged as suspicious (exported to suspicious_quantities.csv). QTY ≤ 0 "
            "is flagged as invalid. The bar chart shows average QTY by equipment type — types "
            "with high averages may have systematic data issues."
        ),
        "action": (
            "Review suspicious_quantities.csv. If QTY > 5 rows are concentrated in a single "
            "equipment type, it may be a coding convention (e.g., total BTU capacity encoded as "
            "quantity). Cap QTY at a reasonable maximum (e.g., 5) or investigate with the data provider."
        ),
    },
    "state_district_crosscheck": {
        "purpose": "Verify that service_state is consistent with district_code_IRP — Oregon districts should have state='OR', Washington districts should have state='WA'.",
        "why": (
            "State determines which tariff rates, ASHRAE service life data, and regulatory "
            "assumptions apply. A premise in an Oregon district coded as WA would use the wrong "
            "rate schedule and equipment life assumptions, biasing its simulated cost and "
            "replacement timing."
        ),
        "how_to_read": (
            "Mismatches should be 0. The stacked bar chart shows the state composition of each "
            "district — any district with mixed colors has mismatched records. The mismatch table "
            "lists specific district-state pairs that are inconsistent."
        ),
        "action": (
            "If mismatches exist, determine whether the district or the state is wrong. Cross-reference "
            "with the NW Natural service territory map. Fix the incorrect field in the source data "
            "or add a correction rule in the data ingestion pipeline."
        ),
    },
    "billing_reasonableness": {
        "purpose": "Flag billing records with suspiciously low (< 1 therm) or high (> 500 therms) usage per billing period.",
        "why": (
            "Extreme billing values distort calibration. A record of 0.01 therms may be a meter "
            "read error or an estimated bill for a vacant unit. A record of 500+ therms in a "
            "single billing period (typically monthly) is implausible for a residential customer "
            "and may indicate a commercial account miscoded as residential, or a data entry error."
        ),
        "how_to_read": (
            "The flagged percentage should be low (< 5%). The log-scale histogram shows the full "
            "distribution with threshold lines at 1 and 500 therms. The monthly time-series shows "
            "seasonal patterns (higher in winter, lower in summer) — anomalies indicate data issues. "
            "The box plot by rate schedule reveals whether certain schedules have unusual distributions."
        ),
        "action": (
            "If > 5% of records are flagged, investigate the source. Low-therm records may be "
            "summer months with minimal gas use (legitimate) or estimated reads (filter out). "
            "High-therm records should be cross-checked against the premise's segment — a RESMF "
            "premise with 500 therms/month may be a master-metered building (legitimate but needs "
            "different treatment in simulation)."
        ),
    },
    "temperature_bounds": {
        "purpose": "Check that daily average temperatures (TempHA) fall within the reasonable Pacific Northwest range of -10°F to 115°F.",
        "why": (
            "Out-of-range temperatures produce extreme HDD values that distort space heating "
            "simulation. A spurious -50°F reading would generate 115 HDD for that day, massively "
            "inflating heating demand. These are almost always sensor errors or data processing "
            "artifacts (e.g., missing values coded as -999)."
        ),
        "how_to_read": (
            "Out-of-range records should be 0 or very few. The daily time-series overlays all "
            "stations — red dots mark out-of-range values. The heatmap shows average temperature "
            "by station and month — anomalous cells indicate systematic issues. The annual average "
            "chart should show a gradual warming trend consistent with climate change."
        ),
        "action": (
            "If out-of-range records exist, replace them with interpolated values from the same "
            "station (adjacent days) or from NOAA Climate Normals for that date. If a station has "
            "many outliers, it may have a sensor calibration issue — consider excluding it and "
            "reassigning its premises to a nearby station."
        ),
    },
    "temporal_alignment": {
        "purpose": "Compare date ranges across all time-series datasets (weather, billing, water temperature, snow) to identify overlap and gaps.",
        "why": (
            "The simulation requires all time-series datasets to overlap for the analysis period. "
            "If weather data ends in 2024 but billing data extends to 2025, the model cannot "
            "calibrate the most recent year. If water temperature data starts in 2010 but weather "
            "starts in 1985, water heating simulation is limited to the shorter range."
        ),
        "how_to_read": (
            "The Gantt chart shows each dataset's date range as a horizontal bar — the overlap "
            "region is the usable analysis window. The stacked area chart shows monthly record "
            "counts — dips indicate periods where some datasets are missing. The year matrix "
            "heatmap shows record density by dataset and year."
        ),
        "action": (
            "If the overlap period is shorter than expected, check whether any dataset was "
            "truncated during extraction. The model's base year (2025) should fall within the "
            "overlap period for all critical datasets (weather + billing at minimum). If a dataset "
            "is missing for recent years, request an updated extract from the data provider."
        ),
    },
    "customer_count_over_time": {
        "purpose": "Track the number of unique active customers over time, broken down by segment type (RESSF, RESMF, MOBILE).",
        "why": (
            "Understanding how the customer base evolves over time is fundamental to demand "
            "forecasting. Growth or decline in specific segments (single-family vs. multi-family "
            "vs. mobile home) directly affects total gas demand and the equipment mix. This chart "
            "also reveals data completeness — a sudden drop in customer count likely indicates "
            "missing billing data rather than actual customer loss."
        ),
        "how_to_read": (
            "The stacked area chart shows unique customers per year by segment type. The total "
            "should grow gradually over time, consistent with housing growth in the service territory. "
            "The line chart shows the same data as individual lines for easier comparison. "
            "The table provides exact counts per year and segment. Look for: (a) steady growth "
            "matching PSU/OFM housing forecasts, (b) no sudden drops (data gaps), (c) RESSF "
            "dominating the mix (~70-80% of customers)."
        ),
        "action": (
            "If customer counts drop sharply in recent years, check whether billing data is "
            "complete for those years. If the RESSF/RESMF/MOBILE mix shifts dramatically, "
            "investigate whether segment assignments changed or new construction patterns shifted. "
            "Compare growth rates against Census B25024 (Units in Structure) data for validation."
        ),
    },
}

# ============================================================================
# HTML / MD report helpers
# ============================================================================

CSS = """
body { font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f8f9fa; }
h1 { font-size: 1.4em; color: #212529; }
h2 { font-size: 1.15em; color: #343a40; margin-top: 24px; }
h3 { font-size: 1.0em; color: #495057; }
table { border-collapse: collapse; width: 100%; background: #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
th { background: #343a40; color: #fff; padding: 8px 10px; text-align: left; font-size: 0.85em; }
td { padding: 6px 10px; border-bottom: 1px solid #e9ecef; font-size: 0.84em; }
tr:hover { background: #f1f3f5; }
.meta { color: #666; font-size: 0.9em; }
.pass { color: #28a745; font-weight: bold; }
.warn { color: #ffc107; font-weight: bold; }
.fail { color: #dc3545; font-weight: bold; }
img { max-width: 100%; margin: 10px 0; border: 1px solid #dee2e6; }
.chart-container { margin: 16px 0; }
"""


def _ensure_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


def _write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Wrote {path}")


def _fig_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 PNG string for HTML embedding."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


def _save_chart(fig, name: str) -> str:
    """Save chart as PNG and return base64 for HTML embedding."""
    _ensure_dir()
    png_path = os.path.join(OUT_DIR, f"{name}.png")
    fig.savefig(png_path, dpi=120, bbox_inches="tight")
    b64 = _fig_to_base64(fig)
    return b64


def _html_table(rows: list, cols: list) -> str:
    if not rows:
        return "<p><em>No data available</em></p>"
    ths = "".join(f"<th>{c}</th>" for c in cols)
    trs = ""
    for r in rows:
        tds = "".join(f"<td>{r.get(c, '')}</td>" for c in cols)
        trs += f"<tr>{tds}</tr>"
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"


def _md_table(rows: list, cols: list) -> str:
    if not rows:
        return "_No data available_\n"
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    body = "\n".join("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows)
    return f"{header}\n{sep}\n{body}\n"


def _html_img(b64: str, alt: str = "chart") -> str:
    return f'<div class="chart-container"><img src="data:image/png;base64,{b64}" alt="{alt}"></div>'


def _build_html(title: str, body: str) -> str:
    ts = datetime.now().isoformat()
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{title}</title>
<style>{CSS}</style></head><body>
<h1>{title}</h1>
<p class="meta">Generated: {ts}</p>
{body}
</body></html>"""


def _build_md(title: str, body: str) -> str:
    ts = datetime.now().isoformat()
    return f"# {title}\nGenerated: {ts}\n\n{body}\n"


def _desc_html(key: str) -> str:
    """Return an HTML block with the test description, or empty string if not found."""
    d = DESCRIPTIONS.get(key)
    if not d:
        return ""
    return (
        '<div style="background:#e9ecef;padding:12px 16px;border-radius:6px;margin-bottom:20px;'
        'border-left:4px solid #4e79a7;">'
        f'<p><strong>Purpose:</strong> {d["purpose"]}</p>'
        f'<p><strong>Why it matters:</strong> {d["why"]}</p>'
        f'<p><strong>How to read:</strong> {d["how_to_read"]}</p>'
        f'<p><strong>Recommended action:</strong> {d["action"]}</p>'
        '</div>'
    )


def _desc_md(key: str) -> str:
    """Return a Markdown block with the test description, or empty string if not found."""
    d = DESCRIPTIONS.get(key)
    if not d:
        return ""
    return (
        f'> **Purpose:** {d["purpose"]}\n>\n'
        f'> **Why it matters:** {d["why"]}\n>\n'
        f'> **How to read:** {d["how_to_read"]}\n>\n'
        f'> **Recommended action:** {d["action"]}\n\n'
    )


def _load_safe(loader_fn, *args, **kwargs):
    """Call a loader, return (df, error_str). Returns (None, msg) on failure."""
    try:
        df = loader_fn(*args, **kwargs)
        return df, None
    except Exception as e:
        logger.warning(f"Loader failed: {e}")
        return None, str(e)


def _load_premise_raw() -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Load premise data directly from CSV, filtering to active (status_code=AC).

    The standard load_premise_data() requires a 'custtype' column that may not
    exist in the blinded dataset.  Fall back to raw CSV read when the loader fails.
    """
    from src.loaders.load_premise_data import load_premise_data
    df, err = _load_safe(load_premise_data)
    if df is not None:
        return df, None
    # Fallback: load raw CSV
    try:
        if not os.path.exists(config.PREMISE_DATA):
            return None, f"File not found: {config.PREMISE_DATA}"
        df = pd.read_csv(config.PREMISE_DATA)
        # Filter to active if status_code exists
        if "status_code" in df.columns:
            df = df[df["status_code"] == "AC"].copy()
        logger.info(f"Loaded {len(df)} premise records (raw fallback)")
        return df, None
    except Exception as e2:
        return None, str(e2)


# ============================================================================
# 15.1 Premise referential integrity
# ============================================================================

def validate_referential_integrity() -> dict:
    """Check that blinded_ids in equipment/segment/billing exist in premise_data."""
    from src.loaders.load_equipment_data import load_equipment_data
    from src.loaders.load_segment_data import load_segment_data
    from src.loaders.load_billing_data import load_billing_data

    _ensure_dir()
    result = {"name": "referential_integrity", "status": "SKIPPED"}

    prem_df, err = _load_premise_raw()
    if prem_df is None:
        return {**result, "error": err}

    premise_ids = set(prem_df["blinded_id"].dropna().unique())
    sources = {}

    equip_df, _ = _load_safe(load_equipment_data)
    if equip_df is not None and "blinded_id" in equip_df.columns:
        sources["equipment"] = set(equip_df["blinded_id"].dropna().unique())

    seg_df, _ = _load_safe(load_segment_data)
    if seg_df is not None and "blinded_id" in seg_df.columns:
        sources["segment"] = set(seg_df["blinded_id"].dropna().unique())

    bill_df, _ = _load_safe(load_billing_data)
    if bill_df is not None and "blinded_id" in bill_df.columns:
        sources["billing"] = set(bill_df["blinded_id"].dropna().unique())

    # Compute orphans
    rows = []
    orphan_counts = {}
    for src_name, ids in sources.items():
        orphans = ids - premise_ids
        matched = ids & premise_ids
        orphan_counts[src_name] = len(orphans)
        rows.append({
            "source": src_name,
            "total_ids": f"{len(ids):,}",
            "matched": f"{len(matched):,}",
            "orphans": f"{len(orphans):,}",
            "match_rate": f"{100 * len(matched) / max(len(ids), 1):.1f}%",
        })

    # Bar chart: orphan counts
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    names = list(orphan_counts.keys())
    counts = [orphan_counts[n] for n in names]
    colors = ["#e15759" if c > 0 else "#59a14f" for c in counts]
    ax1.bar(names, counts, color=colors, edgecolor="white")
    ax1.set_title("Orphan blinded_id Counts by Source Table")
    ax1.set_ylabel("Orphan Count")
    for i, v in enumerate(counts):
        ax1.text(i, v + max(counts) * 0.01, f"{v:,}", ha="center", fontsize=9)
    b64_1 = _save_chart(fig1, "referential_integrity_orphans")

    # Time series: orphan rate by setyear (if available)
    b64_2 = ""
    if seg_df is not None and "setyear" in seg_df.columns:
        seg_df = seg_df.copy()
        seg_df["is_orphan"] = ~seg_df["blinded_id"].isin(premise_ids)
        yearly = seg_df.groupby("setyear").agg(
            total=("blinded_id", "count"),
            orphans=("is_orphan", "sum")
        ).reset_index()
        yearly["orphan_rate"] = yearly["orphans"] / yearly["total"].clip(lower=1) * 100
        yearly = yearly[yearly["setyear"].between(1980, 2025)]
        if not yearly.empty:
            fig2, ax2 = plt.subplots(figsize=(10, 4))
            ax2.plot(yearly["setyear"], yearly["orphan_rate"], marker="o", color="#4e79a7")
            ax2.set_title("Segment Orphan Rate by Set Year")
            ax2.set_xlabel("Set Year")
            ax2.set_ylabel("Orphan Rate (%)")
            ax2.grid(True, alpha=0.3)
            b64_2 = _save_chart(fig2, "referential_integrity_orphan_by_year")

    # Build reports
    cols = ["source", "total_ids", "matched", "orphans", "match_rate"]
    html_body = _desc_html("referential_integrity")
    html_body += "<h2>Referential Integrity Summary</h2>"
    html_body += f"<p>Total active residential premises: <strong>{len(premise_ids):,}</strong></p>"
    html_body += _html_table(rows, cols)
    html_body += _html_img(b64_1, "Orphan counts")
    if b64_2:
        html_body += _html_img(b64_2, "Orphan rate by year")

    md_body = _desc_md("referential_integrity")
    md_body += f"## Summary\n\nTotal active residential premises: {len(premise_ids):,}\n\n"
    md_body += _md_table(rows, cols)
    md_body += f"\n![Orphan counts](referential_integrity_orphans.png)\n"
    if b64_2:
        md_body += f"\n![Orphan rate by year](referential_integrity_orphan_by_year.png)\n"

    _write(os.path.join(OUT_DIR, "referential_integrity.html"),
           _build_html("15.1 Premise Referential Integrity", html_body))
    _write(os.path.join(OUT_DIR, "referential_integrity.md"),
           _build_md("15.1 Premise Referential Integrity", md_body))

    result["status"] = "OK"
    result["orphan_counts"] = orphan_counts
    return result



# ============================================================================
# 15.2 Equipment code validity
# ============================================================================

def validate_equipment_codes() -> dict:
    """Verify equipment_type_codes against equipment_codes.csv."""
    from src.loaders.load_equipment_data import load_equipment_data
    from src.loaders.load_equipment_codes import load_equipment_codes

    _ensure_dir()
    result = {"name": "equipment_code_validity", "status": "SKIPPED"}

    equip_df, err = _load_safe(load_equipment_data)
    if equip_df is None:
        return {**result, "error": err}

    codes_df, err2 = _load_safe(load_equipment_codes)
    if codes_df is None:
        return {**result, "error": err2}

    valid_codes = set(codes_df["equipment_type_code"].dropna().unique())
    equip_codes = equip_df["equipment_type_code"].dropna()
    equip_df_clean = equip_df[equip_df["equipment_type_code"].notna()].copy()
    equip_df_clean["is_valid"] = equip_df_clean["equipment_type_code"].isin(valid_codes)

    total_valid = equip_df_clean["is_valid"].sum()
    total_unknown = (~equip_df_clean["is_valid"]).sum()
    unknown_codes = equip_df_clean[~equip_df_clean["is_valid"]]["equipment_type_code"].value_counts()

    summary_rows = [
        {"metric": "Total equipment rows", "value": f"{len(equip_df_clean):,}"},
        {"metric": "Valid codes", "value": f"{total_valid:,}"},
        {"metric": "Unknown codes", "value": f"{total_unknown:,}"},
        {"metric": "Valid rate", "value": f"{100 * total_valid / max(len(equip_df_clean), 1):.1f}%"},
    ]

    unknown_rows = []
    for code, cnt in unknown_codes.head(20).items():
        unknown_rows.append({"code": code, "row_count": f"{cnt:,}"})

    # Bar chart: top 20 codes by frequency, color-coded
    code_freq = equip_df_clean["equipment_type_code"].value_counts().head(20)
    fig1, ax1 = plt.subplots(figsize=(12, 5))
    colors = ["#59a14f" if c in valid_codes else "#e15759" for c in code_freq.index]
    ax1.bar(range(len(code_freq)), code_freq.values, color=colors, edgecolor="white")
    ax1.set_xticks(range(len(code_freq)))
    ax1.set_xticklabels(code_freq.index, rotation=45, ha="right", fontsize=8)
    ax1.set_title("Top 20 Equipment Codes by Frequency (green=valid, red=unknown)")
    ax1.set_ylabel("Row Count")
    b64_1 = _save_chart(fig1, "equipment_code_frequency")

    # Pie chart: valid vs unknown
    fig2, ax2 = plt.subplots(figsize=(6, 6))
    ax2.pie([total_valid, total_unknown], labels=["Valid", "Unknown"],
            colors=["#59a14f", "#e15759"], autopct="%1.1f%%", startangle=90)
    ax2.set_title("Equipment Code Validity")
    b64_2 = _save_chart(fig2, "equipment_code_pie")

    # Build reports
    html_body = _desc_html("equipment_code_validity")
    html_body += "<h2>Equipment Code Validity Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    if unknown_rows:
        html_body += "<h2>Unknown Codes (top 20)</h2>"
        html_body += _html_table(unknown_rows, ["code", "row_count"])
    html_body += _html_img(b64_1, "Code frequency")
    html_body += _html_img(b64_2, "Code validity pie")

    md_body = _desc_md("equipment_code_validity")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    if unknown_rows:
        md_body += "\n## Unknown Codes (top 20)\n\n" + _md_table(unknown_rows, ["code", "row_count"])
    md_body += "\n![Code frequency](equipment_code_frequency.png)\n"
    md_body += "\n![Code validity](equipment_code_pie.png)\n"

    _write(os.path.join(OUT_DIR, "equipment_code_validity.html"),
           _build_html("15.2 Equipment Code Validity", html_body))
    _write(os.path.join(OUT_DIR, "equipment_code_validity.md"),
           _build_md("15.2 Equipment Code Validity", md_body))

    result["status"] = "OK"
    result["valid"] = int(total_valid)
    result["unknown"] = int(total_unknown)
    return result


# ============================================================================
# 15.3 Duplicate premise-equipment detection
# ============================================================================

def validate_duplicate_equipment() -> dict:
    """Check for exact duplicate rows in equipment_data."""
    from src.loaders.load_equipment_data import load_equipment_data

    _ensure_dir()
    result = {"name": "duplicate_detection", "status": "SKIPPED"}

    equip_df, err = _load_safe(load_equipment_data)
    if equip_df is None:
        return {**result, "error": err}

    # Determine QTY column name
    qty_col = None
    for c in equip_df.columns:
        if "qty" in c.lower():
            qty_col = c
            break

    dup_cols = ["blinded_id", "equipment_type_code"]
    if qty_col:
        dup_cols.append(qty_col)

    dupes = equip_df[equip_df.duplicated(subset=dup_cols, keep=False)]
    unique_duped_ids = dupes["blinded_id"].nunique() if not dupes.empty else 0
    dup_rate = len(dupes) / max(len(equip_df), 1) * 100

    summary_rows = [
        {"metric": "Total equipment rows", "value": f"{len(equip_df):,}"},
        {"metric": "Duplicate rows", "value": f"{len(dupes):,}"},
        {"metric": "Unique duplicated blinded_ids", "value": f"{unique_duped_ids:,}"},
        {"metric": "Duplication rate", "value": f"{dup_rate:.1f}%"},
    ]

    # Export duplicates
    if not dupes.empty:
        dupes.to_csv(os.path.join(OUT_DIR, "duplicate_equipment.csv"), index=False)

    # Bar chart: duplicate count by equipment_type_code (top 20)
    b64_1 = ""
    if not dupes.empty and "equipment_type_code" in dupes.columns:
        dup_by_code = dupes["equipment_type_code"].value_counts().head(20)
        fig1, ax1 = plt.subplots(figsize=(12, 5))
        ax1.bar(range(len(dup_by_code)), dup_by_code.values, color="#e15759", edgecolor="white")
        ax1.set_xticks(range(len(dup_by_code)))
        ax1.set_xticklabels(dup_by_code.index, rotation=45, ha="right", fontsize=8)
        ax1.set_title("Duplicate Count by Equipment Type Code (Top 20)")
        ax1.set_ylabel("Duplicate Rows")
        b64_1 = _save_chart(fig1, "duplicate_by_code")

    # Histogram: duplicates per blinded_id
    b64_2 = ""
    if not dupes.empty:
        dup_per_id = dupes.groupby("blinded_id").size()
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        bins = [0.5, 1.5, 2.5, 3.5, max(dup_per_id.max() + 0.5, 4.5)]
        ax2.hist(dup_per_id, bins=bins, color="#f28e2b", edgecolor="white")
        ax2.set_title("Duplicates per blinded_id")
        ax2.set_xlabel("Number of Duplicate Rows")
        ax2.set_ylabel("Number of Premises")
        b64_2 = _save_chart(fig2, "duplicate_per_id")

    # Build reports
    html_body = _desc_html("duplicate_detection")
    html_body += "<h2>Duplicate Detection Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    if b64_1:
        html_body += _html_img(b64_1, "Duplicates by code")
    if b64_2:
        html_body += _html_img(b64_2, "Duplicates per ID")

    md_body = _desc_md("duplicate_detection")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    if b64_1:
        md_body += "\n![Duplicates by code](duplicate_by_code.png)\n"
    if b64_2:
        md_body += "\n![Duplicates per ID](duplicate_per_id.png)\n"

    _write(os.path.join(OUT_DIR, "duplicate_detection.html"),
           _build_html("15.3 Duplicate Premise-Equipment Detection", html_body))
    _write(os.path.join(OUT_DIR, "duplicate_detection.md"),
           _build_md("15.3 Duplicate Premise-Equipment Detection", md_body))

    result["status"] = "OK"
    result["duplicates"] = len(dupes)
    return result


# ============================================================================
# 15.4 Weather station coverage
# ============================================================================

def validate_weather_station_coverage() -> dict:
    """Verify district_code_IRP maps to weather stations via DISTRICT_WEATHER_MAP."""

    _ensure_dir()
    result = {"name": "weather_station_coverage", "status": "SKIPPED"}

    prem_df, err = _load_premise_raw()
    if prem_df is None:
        return {**result, "error": err}

    if "district_code_IRP" not in prem_df.columns:
        return {**result, "error": "district_code_IRP column not found"}

    district_counts = prem_df["district_code_IRP"].value_counts()
    all_districts = set(district_counts.index)
    mapped = {d for d in all_districts if d in config.DISTRICT_WEATHER_MAP}
    unmapped = all_districts - mapped

    summary_rows = [
        {"metric": "Total unique districts", "value": f"{len(all_districts)}"},
        {"metric": "Mapped districts", "value": f"{len(mapped)}"},
        {"metric": "Unmapped districts", "value": f"{len(unmapped)}"},
        {"metric": "Mapped premise count", "value": f"{district_counts[list(mapped)].sum():,}" if mapped else "0"},
        {"metric": "Unmapped premise count", "value": f"{district_counts[list(unmapped)].sum():,}" if unmapped else "0"},
    ]

    unmapped_rows = []
    for d in sorted(unmapped):
        unmapped_rows.append({"district": d, "premise_count": f"{district_counts[d]:,}"})

    # Bar chart: premise count by district, color-coded
    fig1, ax1 = plt.subplots(figsize=(12, 5))
    sorted_districts = district_counts.sort_values(ascending=False)
    colors = ["#59a14f" if d in mapped else "#e15759" for d in sorted_districts.index]
    ax1.bar(range(len(sorted_districts)), sorted_districts.values, color=colors, edgecolor="white")
    ax1.set_xticks(range(len(sorted_districts)))
    ax1.set_xticklabels(sorted_districts.index, rotation=45, ha="right", fontsize=8)
    ax1.set_title("Premise Count by District (green=mapped, red=unmapped)")
    ax1.set_ylabel("Premise Count")
    b64_1 = _save_chart(fig1, "weather_station_coverage")

    # Folium map (optional)
    map_note = ""
    try:
        import folium
        # Simple map with district labels (no real coordinates, just a note)
        map_note = "<p><em>Folium map: district centroids not available in blinded data.</em></p>"
    except ImportError:
        map_note = "<p><em>Folium not installed — map visualization skipped.</em></p>"

    html_body = _desc_html("weather_station_coverage")
    html_body += "<h2>Weather Station Coverage Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    if unmapped_rows:
        html_body += "<h2>Unmapped Districts</h2>"
        html_body += _html_table(unmapped_rows, ["district", "premise_count"])
    html_body += _html_img(b64_1, "Coverage chart")
    html_body += map_note

    md_body = _desc_md("weather_station_coverage")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    if unmapped_rows:
        md_body += "\n## Unmapped Districts\n\n" + _md_table(unmapped_rows, ["district", "premise_count"])
    md_body += "\n![Coverage](weather_station_coverage.png)\n"

    _write(os.path.join(OUT_DIR, "weather_station_coverage.html"),
           _build_html("15.4 Weather Station Coverage", html_body))
    _write(os.path.join(OUT_DIR, "weather_station_coverage.md"),
           _build_md("15.4 Weather Station Coverage", md_body))

    result["status"] = "OK"
    result["unmapped"] = len(unmapped)
    return result


# ============================================================================
# 15.5 Billing coverage analysis
# ============================================================================

def validate_billing_coverage() -> dict:
    """Count unique blinded_ids in billing vs active residential premises."""
    from src.loaders.load_billing_data import load_billing_data

    _ensure_dir()
    result = {"name": "billing_coverage", "status": "SKIPPED"}

    prem_df, err = _load_premise_raw()
    if prem_df is None:
        return {**result, "error": err}

    bill_df, err2 = _load_safe(load_billing_data)
    if bill_df is None:
        return {**result, "error": err2}

    premise_ids = set(prem_df["blinded_id"].dropna().unique())
    billing_ids = set(bill_df["blinded_id"].dropna().unique()) if "blinded_id" in bill_df.columns else set()
    with_billing = premise_ids & billing_ids
    without_billing = premise_ids - billing_ids
    coverage_pct = 100 * len(with_billing) / max(len(premise_ids), 1)

    summary_rows = [
        {"metric": "Total active residential premises", "value": f"{len(premise_ids):,}"},
        {"metric": "Premises with billing data", "value": f"{len(with_billing):,}"},
        {"metric": "Coverage %", "value": f"{coverage_pct:.1f}%"},
        {"metric": "Premises without billing", "value": f"{len(without_billing):,}"},
    ]

    # Bar chart: billing coverage by district
    b64_1 = ""
    if "district_code_IRP" in prem_df.columns:
        prem_df = prem_df.copy()
        prem_df["has_billing"] = prem_df["blinded_id"].isin(billing_ids)
        dist_cov = prem_df.groupby("district_code_IRP").agg(
            total=("blinded_id", "count"),
            with_billing=("has_billing", "sum")
        ).reset_index()
        dist_cov["coverage_pct"] = dist_cov["with_billing"] / dist_cov["total"].clip(lower=1) * 100
        dist_cov = dist_cov.sort_values("total", ascending=False)

        fig1, ax1 = plt.subplots(figsize=(12, 5))
        x = range(len(dist_cov))
        ax1.bar(x, dist_cov["total"], color="#bab0ac", edgecolor="white", label="Total")
        ax1.bar(x, dist_cov["with_billing"], color="#4e79a7", edgecolor="white", label="With Billing")
        ax1.set_xticks(x)
        ax1.set_xticklabels(dist_cov["district_code_IRP"], rotation=45, ha="right", fontsize=8)
        ax1.set_title("Billing Coverage by District")
        ax1.set_ylabel("Premise Count")
        ax1.legend()
        b64_1 = _save_chart(fig1, "billing_coverage_by_district")

    # Time series: billing records by year-month
    b64_2 = ""
    if "GL_revenue_date" in bill_df.columns:
        bill_df = bill_df.copy()
        bill_df["GL_revenue_date"] = pd.to_datetime(bill_df["GL_revenue_date"], errors="coerce")
        bill_df["ym"] = bill_df["GL_revenue_date"].dt.to_period("M")
        monthly = bill_df.groupby("ym").size()
        monthly = monthly[monthly.index.notnull()]
        if not monthly.empty:
            fig2, ax2 = plt.subplots(figsize=(14, 4))
            ax2.plot(monthly.index.astype(str), monthly.values, color="#4e79a7", linewidth=0.8)
            ax2.set_title("Billing Record Count by Year-Month")
            ax2.set_xlabel("Year-Month")
            ax2.set_ylabel("Record Count")
            # Show fewer x-ticks
            n = len(monthly)
            step = max(n // 20, 1)
            ax2.set_xticks(range(0, n, step))
            ax2.set_xticklabels([str(monthly.index[i]) for i in range(0, n, step)], rotation=45, fontsize=7)
            ax2.grid(True, alpha=0.3)
            b64_2 = _save_chart(fig2, "billing_records_by_month")

    # Histogram: billing records per premise
    b64_3 = ""
    if "blinded_id" in bill_df.columns:
        records_per_premise = bill_df["blinded_id"].value_counts()
        fig3, ax3 = plt.subplots(figsize=(8, 4))
        ax3.hist(records_per_premise.values, bins=50, color="#f28e2b", edgecolor="white")
        ax3.set_title("Billing Records per Premise (Distribution)")
        ax3.set_xlabel("Number of Billing Records")
        ax3.set_ylabel("Number of Premises")
        b64_3 = _save_chart(fig3, "billing_records_per_premise")

    html_body = _desc_html("billing_coverage")
    html_body += "<h2>Billing Coverage Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    if b64_1:
        html_body += _html_img(b64_1, "Coverage by district")
    if b64_2:
        html_body += _html_img(b64_2, "Records by month")
    if b64_3:
        html_body += _html_img(b64_3, "Records per premise")

    md_body = _desc_md("billing_coverage")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    if b64_1:
        md_body += "\n![Coverage by district](billing_coverage_by_district.png)\n"
    if b64_2:
        md_body += "\n![Records by month](billing_records_by_month.png)\n"
    if b64_3:
        md_body += "\n![Records per premise](billing_records_per_premise.png)\n"

    _write(os.path.join(OUT_DIR, "billing_coverage.html"),
           _build_html("15.5 Billing Coverage Analysis", html_body))
    _write(os.path.join(OUT_DIR, "billing_coverage.md"),
           _build_md("15.5 Billing Coverage Analysis", md_body))

    result["status"] = "OK"
    result["coverage_pct"] = round(coverage_pct, 1)
    return result


# ============================================================================
# 15.6 Weather date continuity
# ============================================================================

def validate_weather_continuity() -> dict:
    """Check for missing dates in weather time series by station."""
    from src.loaders.load_weather_data import load_weather_data

    _ensure_dir()
    result = {"name": "weather_continuity", "status": "SKIPPED"}

    weather_df, err = _load_safe(load_weather_data, config.WEATHER_CALDAY)
    if weather_df is None:
        return {**result, "error": err}

    # Find date and site columns
    date_col = next((c for c in weather_df.columns if "date" in c.lower()), None)
    site_col = next((c for c in weather_df.columns if "site" in c.lower()), None)
    hdd_col = next((c for c in weather_df.columns if c.lower() in ("hdd", "hdd65")), None)
    temp_col = next((c for c in weather_df.columns if "tempha" in c.lower() or "avgtemp" in c.lower() or "tavg" in c.lower()), None)

    if not date_col or not site_col:
        return {**result, "error": f"Missing date ({date_col}) or site ({site_col}) column"}

    weather_df = weather_df.copy()
    weather_df[date_col] = pd.to_datetime(weather_df[date_col], errors="coerce")
    weather_df = weather_df.dropna(subset=[date_col])

    stations = weather_df[site_col].unique()
    gap_rows = []
    for station in sorted(stations):
        sdf = weather_df[weather_df[site_col] == station].sort_values(date_col)
        min_date = sdf[date_col].min()
        max_date = sdf[date_col].max()
        expected = (max_date - min_date).days + 1
        actual = len(sdf)
        gaps = expected - actual
        # Find longest gap
        dates_sorted = sdf[date_col].sort_values()
        diffs = dates_sorted.diff().dt.days.dropna()
        longest_gap = int(diffs.max()) - 1 if len(diffs) > 0 else 0
        gap_rows.append({
            "station": station,
            "min_date": str(min_date.date()),
            "max_date": str(max_date.date()),
            "expected_days": f"{expected:,}",
            "actual_days": f"{actual:,}",
            "missing_days": f"{gaps:,}",
            "longest_gap": f"{longest_gap}",
        })

    # Heatmap: station × month completeness
    b64_1 = ""
    weather_df["_month"] = weather_df[date_col].dt.month
    weather_df["_year"] = weather_df[date_col].dt.year
    completeness = weather_df.groupby([site_col, "_month"]).size().unstack(fill_value=0)
    # Normalize by expected days per month × number of years
    n_years = weather_df["_year"].nunique()
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not completeness.empty:
        norm = completeness.copy()
        for m in range(1, 13):
            if m in norm.columns:
                norm[m] = norm[m] / (days_per_month[m - 1] * max(n_years, 1)) * 100
        fig1, ax1 = plt.subplots(figsize=(12, 6))
        im = ax1.imshow(norm.values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=100)
        ax1.set_yticks(range(len(norm.index)))
        ax1.set_yticklabels(norm.index, fontsize=8)
        ax1.set_xticks(range(len(norm.columns)))
        ax1.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(norm.columns)], fontsize=8)
        ax1.set_title("Weather Data Completeness (% of expected days) by Station × Month")
        plt.colorbar(im, ax=ax1, label="% Complete")
        b64_1 = _save_chart(fig1, "weather_completeness_heatmap")

    # Time series: daily record count
    b64_2 = ""
    daily_count = weather_df.groupby(date_col).size()
    if not daily_count.empty:
        fig2, ax2 = plt.subplots(figsize=(14, 4))
        ax2.plot(daily_count.index, daily_count.values, color="#4e79a7", linewidth=0.5)
        ax2.axhline(y=len(stations), color="#e15759", linestyle="--", alpha=0.7, label=f"Expected ({len(stations)} stations)")
        ax2.set_title("Daily Weather Record Count")
        ax2.set_xlabel("Date")
        ax2.set_ylabel("Records per Day")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        b64_2 = _save_chart(fig2, "weather_daily_count")

    # Annual HDD by station
    b64_3 = ""
    if hdd_col and hdd_col in weather_df.columns:
        weather_df["_hdd"] = pd.to_numeric(weather_df[hdd_col], errors="coerce")
    elif temp_col and temp_col in weather_df.columns:
        weather_df["_hdd"] = (65 - pd.to_numeric(weather_df[temp_col], errors="coerce")).clip(lower=0)
    else:
        weather_df["_hdd"] = np.nan

    if weather_df["_hdd"].notna().any():
        annual_hdd = weather_df.groupby([site_col, "_year"])["_hdd"].sum().reset_index()
        fig3, ax3 = plt.subplots(figsize=(14, 5))
        for station in sorted(stations):
            sdata = annual_hdd[annual_hdd[site_col] == station]
            ax3.plot(sdata["_year"], sdata["_hdd"], marker=".", markersize=2, label=station, linewidth=0.8)
        ax3.set_title("Annual HDD by Station (1985-2025)")
        ax3.set_xlabel("Year")
        ax3.set_ylabel("Annual HDD (base 65°F)")
        ax3.legend(fontsize=6, ncol=3)
        ax3.grid(True, alpha=0.3)
        b64_3 = _save_chart(fig3, "weather_annual_hdd")

    cols = ["station", "min_date", "max_date", "expected_days", "actual_days", "missing_days", "longest_gap"]
    html_body = _desc_html("weather_continuity")
    html_body += "<h2>Weather Date Continuity Summary</h2>"
    html_body += _html_table(gap_rows, cols)
    if b64_1:
        html_body += _html_img(b64_1, "Completeness heatmap")
    if b64_2:
        html_body += _html_img(b64_2, "Daily record count")
    if b64_3:
        html_body += _html_img(b64_3, "Annual HDD")

    md_body = _desc_md("weather_continuity")
    md_body += "## Summary\n\n" + _md_table(gap_rows, cols)
    if b64_1:
        md_body += "\n![Completeness](weather_completeness_heatmap.png)\n"
    if b64_2:
        md_body += "\n![Daily count](weather_daily_count.png)\n"
    if b64_3:
        md_body += "\n![Annual HDD](weather_annual_hdd.png)\n"

    _write(os.path.join(OUT_DIR, "weather_continuity.html"),
           _build_html("15.6 Weather Date Continuity", html_body))
    _write(os.path.join(OUT_DIR, "weather_continuity.md"),
           _build_md("15.6 Weather Date Continuity", md_body))

    result["status"] = "OK"
    return result


# ============================================================================
# 15.7 Segment consistency
# ============================================================================

def validate_segment_consistency() -> dict:
    """Check that every active residential premise has exactly one segment record."""
    from src.loaders.load_segment_data import load_segment_data

    _ensure_dir()
    result = {"name": "segment_consistency", "status": "SKIPPED"}

    prem_df, err = _load_premise_raw()
    if prem_df is None:
        return {**result, "error": err}

    seg_df, err2 = _load_safe(load_segment_data)
    if seg_df is None:
        return {**result, "error": err2}

    premise_ids = set(prem_df["blinded_id"].dropna().unique())
    seg_counts = seg_df.groupby("blinded_id").size()

    with_0 = len(premise_ids - set(seg_counts.index))
    with_1 = (seg_counts == 1).sum()
    with_2plus = (seg_counts >= 2).sum()

    summary_rows = [
        {"metric": "Total active residential premises", "value": f"{len(premise_ids):,}"},
        {"metric": "Premises with 0 segments", "value": f"{with_0:,}"},
        {"metric": "Premises with 1 segment", "value": f"{with_1:,}"},
        {"metric": "Premises with 2+ segments", "value": f"{with_2plus:,}"},
    ]

    # Bar chart: segment distribution
    seg_dist = seg_df["segment"].value_counts()
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    seg_dist.plot(kind="bar", ax=ax1, color="#b07aa1", edgecolor="white")
    ax1.set_title("Segment Distribution")
    ax1.set_xlabel("Segment")
    ax1.set_ylabel("Count")
    ax1.tick_params(axis="x", rotation=0)
    b64_1 = _save_chart(fig1, "segment_distribution")

    # Histogram: setyear distribution
    b64_2 = ""
    if "setyear" in seg_df.columns:
        setyears = pd.to_numeric(seg_df["setyear"], errors="coerce").dropna()
        setyears = setyears[setyears.between(1950, 2025)]
        if not setyears.empty:
            fig2, ax2 = plt.subplots(figsize=(10, 4))
            ax2.hist(setyears, bins=50, color="#4e79a7", edgecolor="white")
            ax2.set_title("Segment Set Year Distribution")
            ax2.set_xlabel("Set Year")
            ax2.set_ylabel("Count")
            b64_2 = _save_chart(fig2, "segment_setyear_hist")

    # Stacked area: cumulative segment assignments by type
    b64_3 = ""
    if "setyear" in seg_df.columns:
        seg_df_c = seg_df.copy()
        seg_df_c["setyear"] = pd.to_numeric(seg_df_c["setyear"], errors="coerce")
        seg_df_c = seg_df_c[seg_df_c["setyear"].between(1950, 2025)]
        if not seg_df_c.empty:
            pivot = seg_df_c.groupby(["setyear", "segment"]).size().unstack(fill_value=0)
            cumulative = pivot.cumsum()
            fig3, ax3 = plt.subplots(figsize=(12, 5))
            cumulative.plot.area(ax=ax3, alpha=0.7)
            ax3.set_title("Cumulative Segment Assignments Over Time")
            ax3.set_xlabel("Set Year")
            ax3.set_ylabel("Cumulative Count")
            ax3.legend(fontsize=8)
            b64_3 = _save_chart(fig3, "segment_cumulative")

    html_body = _desc_html("segment_consistency")
    html_body += "<h2>Segment Consistency Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    html_body += _html_img(b64_1, "Segment distribution")
    if b64_2:
        html_body += _html_img(b64_2, "Set year histogram")
    if b64_3:
        html_body += _html_img(b64_3, "Cumulative segments")

    md_body = _desc_md("segment_consistency")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    md_body += "\n![Segment distribution](segment_distribution.png)\n"
    if b64_2:
        md_body += "\n![Set year](segment_setyear_hist.png)\n"
    if b64_3:
        md_body += "\n![Cumulative](segment_cumulative.png)\n"

    _write(os.path.join(OUT_DIR, "segment_consistency.html"),
           _build_html("15.7 Segment Consistency", html_body))
    _write(os.path.join(OUT_DIR, "segment_consistency.md"),
           _build_md("15.7 Segment Consistency", md_body))

    result["status"] = "OK"
    return result


# ============================================================================
# 15.8 Equipment quantity sanity
# ============================================================================

def validate_equipment_quantity() -> dict:
    """Check QTY_OF_EQUIPMENT_TYPE values for sanity."""
    from src.loaders.load_equipment_data import load_equipment_data

    _ensure_dir()
    result = {"name": "equipment_quantity", "status": "SKIPPED"}

    equip_df, err = _load_safe(load_equipment_data)
    if equip_df is None:
        return {**result, "error": err}

    # Find QTY column
    qty_col = None
    for c in equip_df.columns:
        if "qty" in c.lower():
            qty_col = c
            break

    if not qty_col:
        return {**result, "error": "No QTY column found"}

    qty = pd.to_numeric(equip_df[qty_col], errors="coerce")
    valid_qty = qty.dropna()

    summary_rows = [
        {"metric": "Total rows", "value": f"{len(equip_df):,}"},
        {"metric": "Min QTY", "value": f"{valid_qty.min()}" if len(valid_qty) else "N/A"},
        {"metric": "Max QTY", "value": f"{valid_qty.max()}" if len(valid_qty) else "N/A"},
        {"metric": "Mean QTY", "value": f"{valid_qty.mean():.2f}" if len(valid_qty) else "N/A"},
        {"metric": "Median QTY", "value": f"{valid_qty.median():.1f}" if len(valid_qty) else "N/A"},
        {"metric": "QTY > 5 (suspicious)", "value": f"{(valid_qty > 5).sum():,}"},
        {"metric": "QTY <= 0 (invalid)", "value": f"{(valid_qty <= 0).sum():,}"},
    ]

    # Export suspicious
    suspicious = equip_df[qty > 5]
    if not suspicious.empty:
        suspicious.to_csv(os.path.join(OUT_DIR, "suspicious_quantities.csv"), index=False)

    # Histogram: QTY distribution
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    bins = [0.5, 1.5, 2.5, 3.5, 4.5, max(valid_qty.max() + 0.5, 5.5)] if len(valid_qty) else [0, 1]
    ax1.hist(valid_qty, bins=bins, color="#4e79a7", edgecolor="white")
    ax1.set_title("Equipment Quantity Distribution")
    ax1.set_xlabel("QTY")
    ax1.set_ylabel("Count")
    b64_1 = _save_chart(fig1, "equipment_qty_hist")

    # Bar chart: avg QTY by equipment_type_code (top 20)
    b64_2 = ""
    if "equipment_type_code" in equip_df.columns:
        equip_df_c = equip_df.copy()
        equip_df_c["_qty"] = qty
        avg_by_code = equip_df_c.groupby("equipment_type_code")["_qty"].mean().sort_values(ascending=False).head(20)
        if not avg_by_code.empty:
            fig2, ax2 = plt.subplots(figsize=(12, 5))
            ax2.bar(range(len(avg_by_code)), avg_by_code.values, color="#f28e2b", edgecolor="white")
            ax2.set_xticks(range(len(avg_by_code)))
            ax2.set_xticklabels(avg_by_code.index, rotation=45, ha="right", fontsize=8)
            ax2.set_title("Average QTY by Equipment Type Code (Top 20)")
            ax2.set_ylabel("Average QTY")
            b64_2 = _save_chart(fig2, "equipment_avg_qty_by_code")

    html_body = _desc_html("equipment_quantity")
    html_body += "<h2>Equipment Quantity Sanity Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    html_body += _html_img(b64_1, "QTY distribution")
    if b64_2:
        html_body += _html_img(b64_2, "Avg QTY by code")

    md_body = _desc_md("equipment_quantity")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    md_body += "\n![QTY distribution](equipment_qty_hist.png)\n"
    if b64_2:
        md_body += "\n![Avg QTY by code](equipment_avg_qty_by_code.png)\n"

    _write(os.path.join(OUT_DIR, "equipment_quantity.html"),
           _build_html("15.8 Equipment Quantity Sanity", html_body))
    _write(os.path.join(OUT_DIR, "equipment_quantity.md"),
           _build_md("15.8 Equipment Quantity Sanity", md_body))

    result["status"] = "OK"
    return result


# ============================================================================
# 15.9 State-district cross-check
# ============================================================================

def validate_state_district() -> dict:
    """Verify service_state is consistent with district_code_IRP."""

    _ensure_dir()
    result = {"name": "state_district_crosscheck", "status": "SKIPPED"}

    prem_df, err = _load_premise_raw()
    if prem_df is None:
        return {**result, "error": err}

    if "service_state" not in prem_df.columns or "district_code_IRP" not in prem_df.columns:
        return {**result, "error": "Missing service_state or district_code_IRP column"}

    # Define expected state for each district
    or_districts = {"MULT", "WASH", "CLAC", "YAMI", "POLK", "MARI", "LINN", "LANE",
                    "DOUG", "COOS", "LINC", "BENT", "CLAT", "COLU"}
    wa_districts = {"CLAR", "SKAM", "KLIC"}

    prem_df = prem_df.copy()

    def expected_state(d):
        if d in or_districts:
            return "OR"
        if d in wa_districts:
            return "WA"
        return "UNKNOWN"

    prem_df["expected_state"] = prem_df["district_code_IRP"].apply(expected_state)
    prem_df["is_mismatch"] = prem_df["service_state"] != prem_df["expected_state"]
    # Don't flag UNKNOWN expected states as mismatches
    prem_df.loc[prem_df["expected_state"] == "UNKNOWN", "is_mismatch"] = False

    total_mismatches = prem_df["is_mismatch"].sum()
    mismatch_pairs = prem_df[prem_df["is_mismatch"]].groupby(
        ["district_code_IRP", "service_state"]).size().reset_index(name="count")

    summary_rows = [
        {"metric": "Total premises checked", "value": f"{len(prem_df):,}"},
        {"metric": "Total mismatches", "value": f"{total_mismatches:,}"},
        {"metric": "Mismatch rate", "value": f"{100 * total_mismatches / max(len(prem_df), 1):.2f}%"},
    ]

    mismatch_rows = []
    for _, row in mismatch_pairs.iterrows():
        mismatch_rows.append({
            "district": row["district_code_IRP"],
            "actual_state": row["service_state"],
            "count": f"{row['count']:,}",
        })

    # Bar chart: premise count by state × district
    cross = prem_df.groupby(["district_code_IRP", "service_state"]).size().unstack(fill_value=0)
    fig1, ax1 = plt.subplots(figsize=(14, 5))
    cross.plot(kind="bar", stacked=True, ax=ax1, edgecolor="white")
    ax1.set_title("Premise Count by District × State")
    ax1.set_xlabel("District")
    ax1.set_ylabel("Premise Count")
    ax1.tick_params(axis="x", rotation=45)
    ax1.legend(title="State")
    b64_1 = _save_chart(fig1, "state_district_crosscheck")

    # Folium map note
    map_note = "<p><em>Coordinate data not available in blinded dataset — map visualization skipped.</em></p>"

    html_body = _desc_html("state_district_crosscheck")
    html_body += "<h2>State-District Cross-Check Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    if mismatch_rows:
        html_body += "<h2>Mismatched Pairs</h2>"
        html_body += _html_table(mismatch_rows, ["district", "actual_state", "count"])
    html_body += _html_img(b64_1, "State-district chart")
    html_body += map_note

    md_body = _desc_md("state_district_crosscheck")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    if mismatch_rows:
        md_body += "\n## Mismatched Pairs\n\n" + _md_table(mismatch_rows, ["district", "actual_state", "count"])
    md_body += "\n![State-district](state_district_crosscheck.png)\n"

    _write(os.path.join(OUT_DIR, "state_district_crosscheck.html"),
           _build_html("15.9 State-District Cross-Check", html_body))
    _write(os.path.join(OUT_DIR, "state_district_crosscheck.md"),
           _build_md("15.9 State-District Cross-Check", md_body))

    result["status"] = "OK"
    result["mismatches"] = int(total_mismatches)
    return result


# ============================================================================
# 15.10 Billing amount reasonableness
# ============================================================================

def validate_billing_reasonableness() -> dict:
    """Flag billing records with suspiciously low or high therm values."""
    from src.loaders.load_billing_data import load_billing_data

    _ensure_dir()
    result = {"name": "billing_reasonableness", "status": "SKIPPED"}

    bill_df, err = _load_safe(load_billing_data)
    if bill_df is None:
        return {**result, "error": err}

    if "utility_usage" not in bill_df.columns:
        return {**result, "error": "utility_usage column not found"}

    bill_df = bill_df.copy()
    bill_df["therms"] = pd.to_numeric(bill_df["utility_usage"], errors="coerce")
    valid = bill_df["therms"].notna()
    total_valid = valid.sum()

    low_flag = bill_df["therms"] < 1
    high_flag = bill_df["therms"] > 500
    flagged = low_flag | high_flag

    summary_rows = [
        {"metric": "Total billing records", "value": f"{len(bill_df):,}"},
        {"metric": "Valid therm values", "value": f"{total_valid:,}"},
        {"metric": "Flagged records (total)", "value": f"{flagged.sum():,}"},
        {"metric": "% flagged", "value": f"{100 * flagged.sum() / max(total_valid, 1):.2f}%"},
        {"metric": "Low (< 1 therm)", "value": f"{low_flag.sum():,}"},
        {"metric": "High (> 500 therms)", "value": f"{high_flag.sum():,}"},
    ]

    # Histogram: therms distribution (log scale)
    b64_1 = ""
    pos_therms = bill_df.loc[bill_df["therms"] > 0, "therms"]
    if not pos_therms.empty:
        fig1, ax1 = plt.subplots(figsize=(10, 5))
        ax1.hist(np.log10(pos_therms), bins=80, color="#4e79a7", edgecolor="white", alpha=0.8)
        ax1.axvline(x=np.log10(1), color="#e15759", linestyle="--", label="1 therm")
        ax1.axvline(x=np.log10(500), color="#e15759", linestyle="--", label="500 therms")
        ax1.set_title("Billing Therms Distribution (log10 scale)")
        ax1.set_xlabel("log10(therms)")
        ax1.set_ylabel("Count")
        ax1.legend()
        b64_1 = _save_chart(fig1, "billing_therms_hist")

    # Time series: monthly average therms
    b64_2 = ""
    if "GL_revenue_date" in bill_df.columns:
        bill_df["GL_revenue_date"] = pd.to_datetime(bill_df["GL_revenue_date"], errors="coerce")
        bill_df["ym"] = bill_df["GL_revenue_date"].dt.to_period("M")
        monthly = bill_df.groupby("ym")["therms"].agg(["mean", "min", "max"]).dropna()
        if not monthly.empty:
            fig2, ax2 = plt.subplots(figsize=(14, 5))
            x = range(len(monthly))
            ax2.fill_between(x, monthly["min"], monthly["max"], alpha=0.2, color="#4e79a7")
            ax2.plot(x, monthly["mean"], color="#4e79a7", linewidth=1)
            ax2.set_title("Monthly Average Billing Therms (with min/max bands)")
            ax2.set_xlabel("Year-Month")
            ax2.set_ylabel("Therms")
            step = max(len(monthly) // 20, 1)
            ax2.set_xticks(range(0, len(monthly), step))
            ax2.set_xticklabels([str(monthly.index[i]) for i in range(0, len(monthly), step)],
                                rotation=45, fontsize=7)
            ax2.grid(True, alpha=0.3)
            b64_2 = _save_chart(fig2, "billing_monthly_therms")

    # Box plot: therms by rate_schedule
    b64_3 = ""
    if "rate_schedule" in bill_df.columns:
        schedules = bill_df["rate_schedule"].dropna().unique()
        if len(schedules) > 0 and len(schedules) <= 20:
            data_by_sched = [bill_df.loc[bill_df["rate_schedule"] == s, "therms"].dropna().values
                             for s in sorted(schedules)]
            data_by_sched = [d for d in data_by_sched if len(d) > 0]
            labels = [s for s in sorted(schedules)
                      if len(bill_df.loc[bill_df["rate_schedule"] == s, "therms"].dropna()) > 0]
            if data_by_sched:
                fig3, ax3 = plt.subplots(figsize=(10, 5))
                ax3.boxplot(data_by_sched, labels=labels, showfliers=False)
                ax3.set_title("Billing Therms by Rate Schedule")
                ax3.set_xlabel("Rate Schedule")
                ax3.set_ylabel("Therms")
                ax3.tick_params(axis="x", rotation=45)
                b64_3 = _save_chart(fig3, "billing_therms_by_schedule")

    html_body = _desc_html("billing_reasonableness")
    html_body += "<h2>Billing Reasonableness Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    if b64_1:
        html_body += _html_img(b64_1, "Therms histogram")
    if b64_2:
        html_body += _html_img(b64_2, "Monthly therms")
    if b64_3:
        html_body += _html_img(b64_3, "Therms by schedule")

    md_body = _desc_md("billing_reasonableness")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    if b64_1:
        md_body += "\n![Therms histogram](billing_therms_hist.png)\n"
    if b64_2:
        md_body += "\n![Monthly therms](billing_monthly_therms.png)\n"
    if b64_3:
        md_body += "\n![Therms by schedule](billing_therms_by_schedule.png)\n"

    _write(os.path.join(OUT_DIR, "billing_reasonableness.html"),
           _build_html("15.10 Billing Amount Reasonableness", html_body))
    _write(os.path.join(OUT_DIR, "billing_reasonableness.md"),
           _build_md("15.10 Billing Amount Reasonableness", md_body))

    result["status"] = "OK"
    result["flagged"] = int(flagged.sum())
    return result


# ============================================================================
# 15.11 Weather temperature bounds
# ============================================================================

def validate_temperature_bounds() -> dict:
    """Check daily TempHA values are within reasonable PNW range (-10°F to 115°F)."""
    from src.loaders.load_weather_data import load_weather_data

    _ensure_dir()
    result = {"name": "temperature_bounds", "status": "SKIPPED"}

    weather_df, err = _load_safe(load_weather_data, config.WEATHER_CALDAY)
    if weather_df is None:
        return {**result, "error": err}

    # Find columns
    date_col = next((c for c in weather_df.columns if "date" in c.lower()), None)
    site_col = next((c for c in weather_df.columns if "site" in c.lower()), None)
    temp_col = next((c for c in weather_df.columns if "tempha" in c.lower()), None)
    if not temp_col:
        temp_col = next((c for c in weather_df.columns if "avgtemp" in c.lower() or "tavg" in c.lower()), None)

    if not temp_col:
        return {**result, "error": "No temperature column found (TempHA, AvgTemp, etc.)"}

    weather_df = weather_df.copy()
    weather_df["_temp"] = pd.to_numeric(weather_df[temp_col], errors="coerce")
    weather_df[date_col] = pd.to_datetime(weather_df[date_col], errors="coerce")
    weather_df["_year"] = weather_df[date_col].dt.year
    weather_df["_month"] = weather_df[date_col].dt.month

    valid_temps = weather_df["_temp"].dropna()
    out_of_range = (valid_temps < -10) | (valid_temps > 115)
    oor_count = out_of_range.sum()

    summary_rows = [
        {"metric": "Total temperature records", "value": f"{len(valid_temps):,}"},
        {"metric": "Out-of-range records", "value": f"{oor_count:,}"},
        {"metric": "Min observed temp (°F)", "value": f"{valid_temps.min():.1f}" if len(valid_temps) else "N/A"},
        {"metric": "Max observed temp (°F)", "value": f"{valid_temps.max():.1f}" if len(valid_temps) else "N/A"},
    ]

    # Stations with outliers
    if site_col and oor_count > 0:
        oor_df = weather_df[weather_df["_temp"].notna() & ((weather_df["_temp"] < -10) | (weather_df["_temp"] > 115))]
        station_outliers = oor_df[site_col].value_counts()
        outlier_rows = [{"station": s, "outlier_count": f"{c:,}"} for s, c in station_outliers.items()]
    else:
        outlier_rows = []

    stations = weather_df[site_col].unique() if site_col else []

    # Time series: daily temp by station
    b64_1 = ""
    if site_col and date_col:
        fig1, ax1 = plt.subplots(figsize=(14, 5))
        for station in sorted(stations):
            sdf = weather_df[weather_df[site_col] == station].sort_values(date_col)
            ax1.plot(sdf[date_col], sdf["_temp"], linewidth=0.3, alpha=0.5, label=station)
        # Highlight out-of-range
        oor_data = weather_df[(weather_df["_temp"] < -10) | (weather_df["_temp"] > 115)]
        if not oor_data.empty:
            ax1.scatter(oor_data[date_col], oor_data["_temp"], color="red", s=10, zorder=5, label="Out of range")
        ax1.axhline(y=-10, color="#e15759", linestyle="--", alpha=0.5)
        ax1.axhline(y=115, color="#e15759", linestyle="--", alpha=0.5)
        ax1.set_title("Daily Temperature by Station (all stations overlaid)")
        ax1.set_xlabel("Date")
        ax1.set_ylabel("Temperature (°F)")
        ax1.legend(fontsize=5, ncol=4)
        ax1.grid(True, alpha=0.3)
        b64_1 = _save_chart(fig1, "temperature_daily")

    # Heatmap: station × month avg temp
    b64_2 = ""
    if site_col:
        avg_temp = weather_df.groupby([site_col, "_month"])["_temp"].mean().unstack(fill_value=np.nan)
        if not avg_temp.empty:
            fig2, ax2 = plt.subplots(figsize=(12, 6))
            im = ax2.imshow(avg_temp.values, aspect="auto", cmap="RdYlBu_r")
            ax2.set_yticks(range(len(avg_temp.index)))
            ax2.set_yticklabels(avg_temp.index, fontsize=8)
            ax2.set_xticks(range(len(avg_temp.columns)))
            month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            ax2.set_xticklabels([month_labels[m - 1] for m in avg_temp.columns], fontsize=8)
            ax2.set_title("Average Temperature by Station × Month (°F)")
            plt.colorbar(im, ax=ax2, label="°F")
            b64_2 = _save_chart(fig2, "temperature_heatmap")

    # Annual avg temp by station
    b64_3 = ""
    if site_col:
        annual_avg = weather_df.groupby([site_col, "_year"])["_temp"].mean().reset_index()
        fig3, ax3 = plt.subplots(figsize=(14, 5))
        for station in sorted(stations):
            sdata = annual_avg[annual_avg[site_col] == station]
            ax3.plot(sdata["_year"], sdata["_temp"], marker=".", markersize=2, label=station, linewidth=0.8)
        ax3.set_title("Annual Average Temperature by Station (1985-2025)")
        ax3.set_xlabel("Year")
        ax3.set_ylabel("Avg Temperature (°F)")
        ax3.legend(fontsize=6, ncol=3)
        ax3.grid(True, alpha=0.3)
        b64_3 = _save_chart(fig3, "temperature_annual_avg")

    # Box plot: monthly temp distribution
    b64_4 = ""
    monthly_data = [weather_df.loc[weather_df["_month"] == m, "_temp"].dropna().values for m in range(1, 13)]
    monthly_data = [d for d in monthly_data if len(d) > 0]
    if monthly_data:
        fig4, ax4 = plt.subplots(figsize=(10, 5))
        ax4.boxplot(monthly_data, tick_labels=["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(monthly_data)],
                    showfliers=False)
        ax4.set_title("Monthly Temperature Distribution (All Stations)")
        ax4.set_xlabel("Month")
        ax4.set_ylabel("Temperature (°F)")
        b64_4 = _save_chart(fig4, "temperature_monthly_box")

    html_body = _desc_html("temperature_bounds")
    html_body += "<h2>Temperature Bounds Summary</h2>"
    html_body += _html_table(summary_rows, ["metric", "value"])
    if outlier_rows:
        html_body += "<h2>Stations with Outliers</h2>"
        html_body += _html_table(outlier_rows, ["station", "outlier_count"])
    if b64_1:
        html_body += _html_img(b64_1, "Daily temperature")
    if b64_2:
        html_body += _html_img(b64_2, "Temperature heatmap")
    if b64_3:
        html_body += _html_img(b64_3, "Annual avg temp")
    if b64_4:
        html_body += _html_img(b64_4, "Monthly box plot")

    md_body = _desc_md("temperature_bounds")
    md_body += "## Summary\n\n" + _md_table(summary_rows, ["metric", "value"])
    if outlier_rows:
        md_body += "\n## Stations with Outliers\n\n" + _md_table(outlier_rows, ["station", "outlier_count"])
    if b64_1:
        md_body += "\n![Daily temp](temperature_daily.png)\n"
    if b64_2:
        md_body += "\n![Heatmap](temperature_heatmap.png)\n"
    if b64_3:
        md_body += "\n![Annual avg](temperature_annual_avg.png)\n"
    if b64_4:
        md_body += "\n![Monthly box](temperature_monthly_box.png)\n"

    _write(os.path.join(OUT_DIR, "temperature_bounds.html"),
           _build_html("15.11 Weather Temperature Bounds", html_body))
    _write(os.path.join(OUT_DIR, "temperature_bounds.md"),
           _build_md("15.11 Weather Temperature Bounds", md_body))

    result["status"] = "OK"
    result["out_of_range"] = int(oor_count)
    return result


# ============================================================================
# 15.12 Temporal alignment audit
# ============================================================================

def validate_temporal_alignment() -> dict:
    """Compare date ranges across all time-series datasets."""
    from src.loaders.load_weather_data import load_weather_data
    from src.loaders.load_billing_data import load_billing_data
    from src.loaders.load_water_temperature import load_water_temperature
    from src.loaders.load_snow_data import load_snow_data

    _ensure_dir()
    result = {"name": "temporal_alignment", "status": "SKIPPED"}

    datasets = {
        "Weather (CalDay)": (load_weather_data, [config.WEATHER_CALDAY], {}),
        "Billing": (load_billing_data, [], {}),
        "Water Temperature": (load_water_temperature, [], {}),
        "Snow": (load_snow_data, [], {}),
    }

    date_ranges = {}
    monthly_counts = {}

    for name, (fn, args, kwargs) in datasets.items():
        df, err = _load_safe(fn, *args, **kwargs)
        if df is None:
            date_ranges[name] = {"min": None, "max": None, "records": 0, "error": err}
            continue

        # Find date column
        date_col = None
        for c in df.columns:
            if "date" in c.lower():
                date_col = c
                break
        if date_col is None and "GL_revenue_date" in df.columns:
            date_col = "GL_revenue_date"

        if date_col and date_col in df.columns:
            dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
            if not dates.empty:
                date_ranges[name] = {
                    "min": dates.min(),
                    "max": dates.max(),
                    "records": len(df),
                }
                # Monthly counts for stacked area
                ym = dates.dt.to_period("M").value_counts().sort_index()
                monthly_counts[name] = ym
            else:
                date_ranges[name] = {"min": None, "max": None, "records": len(df), "error": "No valid dates"}
        else:
            date_ranges[name] = {"min": None, "max": None, "records": len(df), "error": "No date column"}

    # Summary table
    summary_rows = []
    for name, info in date_ranges.items():
        min_d = info["min"].strftime("%Y-%m-%d") if info.get("min") is not None else "N/A"
        max_d = info["max"].strftime("%Y-%m-%d") if info.get("max") is not None else "N/A"
        summary_rows.append({
            "dataset": name,
            "min_date": min_d,
            "max_date": max_d,
            "records": f"{info['records']:,}",
        })

    # Compute overlap
    valid_ranges = {k: v for k, v in date_ranges.items() if v.get("min") is not None}
    if len(valid_ranges) >= 2:
        overlap_start = max(v["min"] for v in valid_ranges.values())
        overlap_end = min(v["max"] for v in valid_ranges.values())
        if overlap_start <= overlap_end:
            overlap_str = f"{overlap_start.strftime('%Y-%m-%d')} to {overlap_end.strftime('%Y-%m-%d')}"
        else:
            overlap_str = "No overlap"
    else:
        overlap_str = "Insufficient datasets"

    # Gantt-style chart
    b64_1 = ""
    if valid_ranges:
        fig1, ax1 = plt.subplots(figsize=(14, 4))
        names = list(valid_ranges.keys())
        for i, name in enumerate(names):
            info = valid_ranges[name]
            start = info["min"]
            end = info["max"]
            ax1.barh(i, (end - start).days, left=start, height=0.5, color=f"C{i}", edgecolor="white")
            ax1.text(start, i, f" {start.strftime('%Y')}", va="center", fontsize=7)
            ax1.text(end, i, f" {end.strftime('%Y')}", va="center", fontsize=7)
        ax1.set_yticks(range(len(names)))
        ax1.set_yticklabels(names, fontsize=9)
        ax1.set_title("Dataset Date Ranges (Gantt-style)")
        ax1.set_xlabel("Date")
        ax1.grid(True, alpha=0.3, axis="x")
        b64_1 = _save_chart(fig1, "temporal_alignment_gantt")

    # Stacked area: monthly record counts
    b64_2 = ""
    if monthly_counts:
        # Build a combined DataFrame
        all_periods = set()
        for ym in monthly_counts.values():
            all_periods.update(ym.index)
        all_periods = sorted(all_periods)
        combined = pd.DataFrame(index=all_periods)
        for name, ym in monthly_counts.items():
            combined[name] = ym
        combined = combined.fillna(0)

        if not combined.empty:
            fig2, ax2 = plt.subplots(figsize=(14, 5))
            combined.plot.area(ax=ax2, alpha=0.7)
            ax2.set_title("Monthly Record Count by Dataset (Stacked Area)")
            ax2.set_xlabel("Year-Month")
            ax2.set_ylabel("Record Count")
            ax2.legend(fontsize=8)
            # Thin x-ticks
            n = len(combined)
            step = max(n // 20, 1)
            ax2.set_xticks(range(0, n, step))
            ax2.set_xticklabels([str(combined.index[i]) for i in range(0, n, step)],
                                rotation=45, fontsize=7)
            ax2.grid(True, alpha=0.3)
            b64_2 = _save_chart(fig2, "temporal_alignment_stacked")

    # Year matrix heatmap
    b64_3 = ""
    if valid_ranges:
        year_matrix = {}
        for name, (fn, args, kwargs) in datasets.items():
            if name not in valid_ranges:
                continue
            df, _ = _load_safe(fn, *args, **kwargs)
            if df is None:
                continue
            date_col = None
            for c in df.columns:
                if "date" in c.lower():
                    date_col = c
                    break
            if date_col is None and "GL_revenue_date" in df.columns:
                date_col = "GL_revenue_date"
            if date_col:
                years = pd.to_datetime(df[date_col], errors="coerce").dt.year.dropna()
                year_matrix[name] = years.value_counts().sort_index()

        if year_matrix:
            all_years = set()
            for yc in year_matrix.values():
                all_years.update(yc.index)
            all_years = sorted(all_years)
            matrix_df = pd.DataFrame(index=all_years)
            for name, yc in year_matrix.items():
                matrix_df[name] = yc
            matrix_df = matrix_df.fillna(0).astype(int)

            if not matrix_df.empty:
                fig3, ax3 = plt.subplots(figsize=(14, max(4, len(matrix_df.columns) * 0.8)))
                im = ax3.imshow(matrix_df.T.values, aspect="auto", cmap="YlOrRd")
                ax3.set_xticks(range(len(matrix_df.index)))
                ax3.set_xticklabels([int(y) for y in matrix_df.index], rotation=45, fontsize=7)
                ax3.set_yticks(range(len(matrix_df.columns)))
                ax3.set_yticklabels(matrix_df.columns, fontsize=8)
                ax3.set_title("Dataset × Year Record Count Matrix")
                plt.colorbar(im, ax=ax3, label="Records")
                b64_3 = _save_chart(fig3, "temporal_alignment_matrix")

    cols = ["dataset", "min_date", "max_date", "records"]
    html_body = _desc_html("temporal_alignment")
    html_body += "<h2>Temporal Alignment Summary</h2>"
    html_body += f"<p>Overlap period: <strong>{overlap_str}</strong></p>"
    html_body += _html_table(summary_rows, cols)
    if b64_1:
        html_body += _html_img(b64_1, "Gantt chart")
    if b64_2:
        html_body += _html_img(b64_2, "Stacked area")
    if b64_3:
        html_body += _html_img(b64_3, "Year matrix")

    md_body = _desc_md("temporal_alignment")
    md_body += f"## Summary\n\nOverlap period: {overlap_str}\n\n"
    md_body += _md_table(summary_rows, cols)
    if b64_1:
        md_body += "\n![Gantt](temporal_alignment_gantt.png)\n"
    if b64_2:
        md_body += "\n![Stacked area](temporal_alignment_stacked.png)\n"
    if b64_3:
        md_body += "\n![Year matrix](temporal_alignment_matrix.png)\n"

    _write(os.path.join(OUT_DIR, "temporal_alignment.html"),
           _build_html("15.12 Temporal Alignment Audit", html_body))
    _write(os.path.join(OUT_DIR, "temporal_alignment.md"),
           _build_md("15.12 Temporal Alignment Audit", md_body))

    result["status"] = "OK"
    return result


# ============================================================================
# 15.13 Customer count over time by segment type
# ============================================================================

def validate_customer_count_over_time() -> dict:
    """Track unique active customers per year by segment type (RESSF, RESMF, MOBILE)."""
    from src.loaders.load_billing_data import load_billing_data
    from src.loaders.load_segment_data import load_segment_data

    _ensure_dir()
    result = {"name": "customer_count_over_time", "status": "SKIPPED"}

    bill_df, err = _load_safe(load_billing_data)
    if bill_df is None:
        return {**result, "error": f"Billing data: {err}"}

    seg_df, err2 = _load_safe(load_segment_data)
    if seg_df is None:
        return {**result, "error": f"Segment data: {err2}"}

    # Parse billing dates to extract year
    if "GL_revenue_date" not in bill_df.columns or "blinded_id" not in bill_df.columns:
        return {**result, "error": "Missing GL_revenue_date or blinded_id in billing data"}

    bill_df = bill_df.copy()
    bill_df["GL_revenue_date"] = pd.to_datetime(bill_df["GL_revenue_date"], errors="coerce")
    bill_df["year"] = bill_df["GL_revenue_date"].dt.year
    bill_df = bill_df.dropna(subset=["year", "blinded_id"])
    bill_df["year"] = bill_df["year"].astype(int)

    if "blinded_id" not in seg_df.columns or "segment" not in seg_df.columns:
        return {**result, "error": "Missing blinded_id or segment in segment data"}

    # Build segment lookup: blinded_id -> segment (take first if duplicates)
    seg_lookup = seg_df.drop_duplicates(subset=["blinded_id"], keep="first")[
        ["blinded_id", "segment"]
    ].set_index("blinded_id")["segment"]

    # Get unique customers per year
    yearly_customers = bill_df.groupby("year")["blinded_id"].nunique().reset_index()
    yearly_customers.columns = ["year", "total_customers"]

    # Get unique customers per year per segment
    bill_df["segment"] = bill_df["blinded_id"].map(seg_lookup)
    # Customers without a segment get "Unknown"
    bill_df["segment"] = bill_df["segment"].fillna("Unknown")

    yearly_by_seg = (
        bill_df.groupby(["year", "segment"])["blinded_id"]
        .nunique()
        .reset_index()
    )
    yearly_by_seg.columns = ["year", "segment", "customers"]

    # Pivot for charts
    pivot = yearly_by_seg.pivot(index="year", columns="segment", values="customers").fillna(0).astype(int)
    # Sort columns: RESSF, RESMF, MOBILE, Unknown, then any others
    preferred_order = ["RESSF", "RESMF", "MOBILE", "Unknown"]
    ordered_cols = [c for c in preferred_order if c in pivot.columns]
    ordered_cols += [c for c in pivot.columns if c not in ordered_cols]
    pivot = pivot[ordered_cols]

    # Filter to reasonable year range
    pivot = pivot[(pivot.index >= 2000) & (pivot.index <= 2025)]

    # Summary table rows
    summary_rows = []
    for year in pivot.index:
        row = {"year": str(year)}
        for seg in pivot.columns:
            row[seg] = f"{int(pivot.loc[year, seg]):,}"
        row["total"] = f"{int(pivot.loc[year].sum()):,}"
        summary_rows.append(row)

    table_cols = ["year"] + list(pivot.columns) + ["total"]

    # Color map for segments
    seg_colors = {
        "RESSF": "#4e79a7",
        "RESMF": "#f28e2b",
        "MOBILE": "#59a14f",
        "Unknown": "#bab0ac",
    }

    # Chart 1: Stacked area — customers over time by segment
    fig1, ax1 = plt.subplots(figsize=(14, 6))
    bottom = np.zeros(len(pivot))
    for seg in pivot.columns:
        color = seg_colors.get(seg, "#76b7b2")
        ax1.fill_between(pivot.index, bottom, bottom + pivot[seg].values,
                         label=seg, color=color, alpha=0.7)
        bottom += pivot[seg].values
    ax1.set_title("Active Customers Over Time by Segment Type (Stacked Area)")
    ax1.set_xlabel("Year")
    ax1.set_ylabel("Unique Customers")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(pivot.index.min(), pivot.index.max())
    b64_1 = _save_chart(fig1, "customer_count_stacked_area")

    # Chart 2: Line chart — each segment as a separate line
    fig2, ax2 = plt.subplots(figsize=(14, 6))
    for seg in pivot.columns:
        color = seg_colors.get(seg, "#76b7b2")
        ax2.plot(pivot.index, pivot[seg].values, marker="o", markersize=4,
                 label=seg, color=color, linewidth=1.5)
    ax2.set_title("Active Customers Over Time by Segment Type (Line)")
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Unique Customers")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(pivot.index.min(), pivot.index.max())
    b64_2 = _save_chart(fig2, "customer_count_lines")

    # Chart 3: Total customers line with YoY growth rate
    totals = pivot.sum(axis=1)
    growth = totals.pct_change() * 100
    fig3, ax3a = plt.subplots(figsize=(14, 5))
    ax3a.bar(totals.index, totals.values, color="#4e79a7", alpha=0.6, label="Total Customers")
    ax3a.set_xlabel("Year")
    ax3a.set_ylabel("Total Customers", color="#4e79a7")
    ax3a.tick_params(axis="y", labelcolor="#4e79a7")
    ax3b = ax3a.twinx()
    ax3b.plot(growth.index, growth.values, color="#e15759", marker="o", markersize=4,
              linewidth=1.5, label="YoY Growth %")
    ax3b.set_ylabel("Year-over-Year Growth (%)", color="#e15759")
    ax3b.tick_params(axis="y", labelcolor="#e15759")
    ax3b.axhline(y=0, color="#e15759", linestyle="--", alpha=0.3)
    ax3a.set_title("Total Active Customers and Year-over-Year Growth Rate")
    lines1, labels1 = ax3a.get_legend_handles_labels()
    lines2, labels2 = ax3b.get_legend_handles_labels()
    ax3a.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax3a.grid(True, alpha=0.3)
    b64_3 = _save_chart(fig3, "customer_count_total_growth")

    # Chart 4: Segment share over time (100% stacked)
    share = pivot.div(pivot.sum(axis=1), axis=0) * 100
    fig4, ax4 = plt.subplots(figsize=(14, 5))
    bottom4 = np.zeros(len(share))
    for seg in share.columns:
        color = seg_colors.get(seg, "#76b7b2")
        ax4.fill_between(share.index, bottom4, bottom4 + share[seg].values,
                         label=seg, color=color, alpha=0.7)
        bottom4 += share[seg].values
    ax4.set_title("Customer Segment Share Over Time (%)")
    ax4.set_xlabel("Year")
    ax4.set_ylabel("Share (%)")
    ax4.set_ylim(0, 100)
    ax4.legend(loc="upper right")
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim(share.index.min(), share.index.max())
    b64_4 = _save_chart(fig4, "customer_segment_share")

    # Build reports
    html_body = _desc_html("customer_count_over_time")
    html_body += "<h2>Customer Count Over Time Summary</h2>"
    html_body += _html_table(summary_rows, table_cols)
    html_body += _html_img(b64_1, "Stacked area")
    html_body += _html_img(b64_2, "Line chart")
    html_body += _html_img(b64_3, "Total and growth")
    html_body += _html_img(b64_4, "Segment share")

    md_body = _desc_md("customer_count_over_time")
    md_body += "## Summary\n\n" + _md_table(summary_rows, table_cols)
    md_body += "\n![Stacked area](customer_count_stacked_area.png)\n"
    md_body += "\n![Line chart](customer_count_lines.png)\n"
    md_body += "\n![Total and growth](customer_count_total_growth.png)\n"
    md_body += "\n![Segment share](customer_segment_share.png)\n"

    _write(os.path.join(OUT_DIR, "customer_count_over_time.html"),
           _build_html("15.13 Customer Count Over Time by Segment Type", html_body))
    _write(os.path.join(OUT_DIR, "customer_count_over_time.md"),
           _build_md("15.13 Customer Count Over Time by Segment Type", md_body))

    result["status"] = "OK"
    result["years"] = len(pivot)
    result["latest_total"] = int(totals.iloc[-1]) if len(totals) > 0 else 0
    return result


# ============================================================================
# Summary dashboard
# ============================================================================

def run_all_validations() -> dict:
    """Run all 12 validation checks and produce a summary dashboard."""
    _ensure_dir()
    logger.info("Starting NW Natural source data validation suite...")

    checks = [
        ("15.1 Referential Integrity", validate_referential_integrity),
        ("15.2 Equipment Code Validity", validate_equipment_codes),
        ("15.3 Duplicate Detection", validate_duplicate_equipment),
        ("15.4 Weather Station Coverage", validate_weather_station_coverage),
        ("15.5 Billing Coverage", validate_billing_coverage),
        ("15.6 Weather Continuity", validate_weather_continuity),
        ("15.7 Segment Consistency", validate_segment_consistency),
        ("15.8 Equipment Quantity", validate_equipment_quantity),
        ("15.9 State-District Cross-Check", validate_state_district),
        ("15.10 Billing Reasonableness", validate_billing_reasonableness),
        ("15.11 Temperature Bounds", validate_temperature_bounds),
        ("15.12 Temporal Alignment", validate_temporal_alignment),
        ("15.13 Customer Count Over Time", validate_customer_count_over_time),
    ]

    results = {}
    for label, fn in checks:
        logger.info(f"Running {label}...")
        try:
            r = fn()
            results[label] = r
            logger.info(f"  {label}: {r.get('status', 'UNKNOWN')}")
        except Exception as e:
            logger.error(f"  {label}: FAILED — {e}")
            results[label] = {"name": label, "status": "ERROR", "error": str(e)}

    # Build dashboard
    _build_dashboard(results)
    return results


def _build_dashboard(results: dict):
    """Build summary dashboard HTML + MD."""
    ts = datetime.now().isoformat()

    rows = []
    for label, r in results.items():
        status = r.get("status", "UNKNOWN")
        error = r.get("error", "")
        report_name = r.get("name", "")
        link = f"{report_name}.html" if report_name else ""

        status_class = "pass" if status == "OK" else ("warn" if status == "SKIPPED" else "fail")
        rows.append({
            "check": label,
            "status": status,
            "status_class": status_class,
            "details": error or "Completed successfully",
            "link": link,
        })

    # HTML dashboard
    table_rows = ""
    for r in rows:
        link_html = f'<a href="{r["link"]}">{r["check"]}</a>' if r["link"] else r["check"]
        table_rows += f'<tr><td>{link_html}</td><td class="{r["status_class"]}">{r["status"]}</td><td>{r["details"]}</td></tr>'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>NW Natural Data Validation Dashboard</title>
<style>{CSS}</style></head><body>
<h1>NW Natural Source Data Validation Dashboard</h1>
<p class="meta">Generated: {ts} | Checks: {len(results)}</p>
<table>
<thead><tr><th>Validation Check</th><th>Status</th><th>Details</th></tr></thead>
<tbody>{table_rows}</tbody>
</table>
<h2>Report Links</h2>
<ul>
"""
    for r in rows:
        if r["link"]:
            html += f'<li><a href="{r["link"]}">{r["check"]}</a></li>\n'
    html += "</ul></body></html>"

    _write(os.path.join(OUT_DIR, "validation_dashboard.html"), html)

    # MD dashboard
    md = f"# NW Natural Source Data Validation Dashboard\nGenerated: {ts}\n\n"
    md += "| Check | Status | Details |\n|-------|--------|--------|\n"
    for r in rows:
        md += f"| {r['check']} | {r['status']} | {r['details']} |\n"
    md += "\n## Report Links\n\n"
    for r in rows:
        if r["link"]:
            md += f"- [{r['check']}]({r['link'].replace('.html', '.md')})\n"

    _write(os.path.join(OUT_DIR, "validation_dashboard.md"), md)


# ============================================================================
# Standalone entry point
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    results = run_all_validations()
    print(f"\nValidation complete. {sum(1 for r in results.values() if r.get('status') == 'OK')}/{len(results)} checks passed.")
    print(f"Reports saved to {OUT_DIR}/")
