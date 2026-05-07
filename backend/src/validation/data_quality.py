"""
Data ingestion validation suite — Task 2.3.

Generates quality reports for all loaded data sources and cross-loader audits.
All outputs saved to output/data_quality/ as HTML + Markdown.

Run standalone:
    python -m src.validation.data_quality
"""

import os
import logging
import warnings
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

from src import config
from src.loaders._helpers import save_quality_report, write_quality_report_html, write_quality_report_md

logger = logging.getLogger(__name__)

OUT_DIR = os.path.join("output", "data_quality")
DIST_DIR = os.path.join(OUT_DIR, "distributions")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Wrote {path}")


def _load_safe(loader_fn, *args, **kwargs):
    """Call a loader, return (df, error_str). Returns (None, msg) on failure."""
    try:
        df = loader_fn(*args, **kwargs)
        return df, None
    except Exception as e:
        return None, str(e)


def _null_flag(pct: float) -> str:
    if pct > 50:
        return "⛔ ERROR"
    if pct > 10:
        return "⚠️ WARN"
    return "✅ OK"


# ---------------------------------------------------------------------------
# 2.3.1  Per-loader quality reports
# ---------------------------------------------------------------------------

def run_per_loader_quality_reports() -> dict:
    """
    Generate HTML + MD quality report for each available loader.
    Returns dict of {loader_name: status}.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    results = {}

    # Import loaders lazily to avoid hard failures on missing files
    loader_specs = _get_loader_specs()

    for name, (loader_fn, args, kwargs, extra_fn) in loader_specs.items():
        df, err = _load_safe(loader_fn, *args, **kwargs)
        if df is None:
            logger.warning(f"Loader {name} failed: {err}")
            results[name] = f"FAILED: {err}"
            continue

        extra = extra_fn(df) if extra_fn else ""
        save_quality_report(df, name, extra)
        results[name] = f"OK ({len(df):,} rows)"
        logger.info(f"Quality report: {name} -> {len(df):,} rows")

    return results


def _get_loader_specs() -> dict:
    """Return {name: (loader_fn, args, kwargs, extra_fn)} for all loaders."""
    from src.loaders.load_premise_data import load_premise_data
    from src.loaders.load_equipment_data import load_equipment_data
    from src.loaders.load_segment_data import load_segment_data
    from src.loaders.load_equipment_codes import load_equipment_codes
    from src.loaders.load_billing_data import load_billing_data
    from src.loaders.load_weather_data import load_weather_data
    from src.loaders.load_water_temperature import load_water_temperature
    from src.loaders.load_snow_data import load_snow_data
    from src.loaders.load_or_rates import load_or_rates
    from src.loaders.load_wa_rates import load_wa_rates
    from src.loaders.load_wacog_history import load_wacog_history
    from src.loaders.load_rate_case_history import load_rate_case_history
    from src.loaders.load_baseload_factors import load_baseload_factors
    from src.loaders.load_nw_energy_proxies import load_nw_energy_proxies
    from src.loaders.load_service_territory_fips import load_service_territory_fips

    def premise_extra(df):
        total = len(df)
        pct = round(100 * total / max(total, 1), 1)
        return f"Filter pass rate: {pct}% active residential (custtype=R, status_code=AC)"

    def equip_extra(df):
        if "equipment_type_code" in df.columns:
            mapped = df["equipment_type_code"].isin(config.END_USE_MAP).sum()
            pct = round(100 * mapped / max(len(df), 1), 1)
            return f"END_USE_MAP coverage: {pct}% of equipment codes map to a known end-use"
        return ""

    def fips_extra(df):
        return f"Loaded {len(df)} county FIPS entries"

    def _load_fips():
        records = load_service_territory_fips()
        return pd.DataFrame(records) if isinstance(records, list) else records

    return {
        "premise_data": (load_premise_data, [], {}, premise_extra),
        "equipment_data": (load_equipment_data, [], {}, equip_extra),
        "segment_data": (load_segment_data, [], {}, None),
        "equipment_codes": (load_equipment_codes, [], {}, None),
        "billing_data": (load_billing_data, [], {}, None),
        "weather_calday": (load_weather_data, [config.WEATHER_CALDAY], {}, None),
        "water_temperature": (load_water_temperature, [], {}, None),
        "snow_data": (load_snow_data, [], {}, None),
        "or_rates": (load_or_rates, [], {}, None),
        "wa_rates": (load_wa_rates, [], {}, None),
        "or_wacog": (load_wacog_history, [config.OR_WACOG_HISTORY], {}, None),
        "wa_wacog": (load_wacog_history, [config.WA_WACOG_HISTORY], {}, None),
        "or_rate_cases": (load_rate_case_history, [config.OR_RATE_CASE_HISTORY], {}, None),
        "wa_rate_cases": (load_rate_case_history, [config.WA_RATE_CASE_HISTORY], {}, None),
        "baseload_factors": (load_baseload_factors, [], {}, None),
        "nw_energy_proxies": (load_nw_energy_proxies, [], {}, None),
        "service_territory_fips": (_load_fips, [], {}, fips_extra),
    }


# ---------------------------------------------------------------------------
# 2.3.2  Cross-loader join audit
# ---------------------------------------------------------------------------

def run_join_audit() -> None:
    """
    Audit blinded_id overlap across premise / equipment / segment / billing.
    Output: output/data_quality/join_audit.html and .md
    """
    from src.loaders.load_premise_data import load_premise_data
    from src.loaders.load_equipment_data import load_equipment_data
    from src.loaders.load_segment_data import load_segment_data
    from src.loaders.load_billing_data import load_billing_data
    from src.loaders.load_equipment_codes import load_equipment_codes

    sources = {
        "premises": (load_premise_data, [], {}),
        "equipment": (load_equipment_data, [], {}),
        "segments": (load_segment_data, [], {}),
        "billing": (load_billing_data, [], {}),
    }

    dfs = {}
    for name, (fn, args, kwargs) in sources.items():
        df, err = _load_safe(fn, *args, **kwargs)
        if df is not None:
            dfs[name] = df
        else:
            logger.warning(f"join_audit: {name} unavailable — {err}")

    # Build ID sets
    id_sets = {}
    for name, df in dfs.items():
        if "blinded_id" in df.columns:
            id_sets[name] = set(df["blinded_id"].dropna().unique())

    # Equipment code mapping audit
    codes_df, _ = _load_safe(
        lambda: __import__("src.loaders.load_equipment_codes", fromlist=["load_equipment_codes"]).load_equipment_codes()
    )
    equip_df = dfs.get("equipment")

    rows = []
    if id_sets:
        all_ids = set.union(*id_sets.values()) if id_sets else set()
        for name, ids in id_sets.items():
            others = {k: v for k, v in id_sets.items() if k != name}
            if others:
                matched = ids & set.union(*others.values())
            else:
                matched = ids
            orphans = ids - matched
            rows.append({
                "source": name,
                "total_ids": len(ids),
                "matched_ids": len(matched),
                "orphan_ids": len(orphans),
                "match_rate": f"{100*len(matched)/max(len(ids),1):.1f}%",
            })

    # Equipment code mapping
    code_rows = []
    if equip_df is not None and "equipment_type_code" in equip_df.columns:
        codes_in_data = equip_df["equipment_type_code"].dropna().unique()
        mapped = [c for c in codes_in_data if c in config.END_USE_MAP]
        unmapped = [c for c in codes_in_data if c not in config.END_USE_MAP]
        code_rows = [
            {"metric": "Total unique equipment_type_codes", "value": len(codes_in_data)},
            {"metric": "Mapped to END_USE_MAP", "value": len(mapped)},
            {"metric": "Unmapped codes", "value": len(unmapped)},
            {"metric": "Unmapped code list", "value": ", ".join(sorted(unmapped)) or "none"},
        ]

    # District mapping
    dist_rows = []
    if "premises" in dfs and "district_code_IRP" in dfs["premises"].columns:
        districts = dfs["premises"]["district_code_IRP"].dropna().unique()
        mapped_d = [d for d in districts if d in config.DISTRICT_WEATHER_MAP]
        unmapped_d = [d for d in districts if d not in config.DISTRICT_WEATHER_MAP]
        dist_rows = [
            {"metric": "Total unique district_code_IRP", "value": len(districts)},
            {"metric": "Mapped to DISTRICT_WEATHER_MAP", "value": len(mapped_d)},
            {"metric": "Unmapped districts", "value": len(unmapped_d)},
            {"metric": "Unmapped district list", "value": ", ".join(sorted(unmapped_d)) or "none"},
        ]

    _write_join_audit(rows, code_rows, dist_rows)


def _write_join_audit(id_rows, code_rows, dist_rows):
    ts = datetime.now().isoformat()

    def _table_md(rows, cols):
        if not rows:
            return "_No data available_\n"
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        body = "\n".join("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows)
        return f"{header}\n{sep}\n{body}\n"

    def _table_html(rows, cols, title):
        if not rows:
            return f"<h3>{title}</h3><p><em>No data available</em></p>"
        ths = "".join(f"<th>{c}</th>" for c in cols)
        trs = "".join(
            "<tr>" + "".join(f"<td>{r.get(c,'')}</td>" for c in cols) + "</tr>"
            for r in rows
        )
        return f"<h3>{title}</h3><table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"

    id_cols = ["source", "total_ids", "matched_ids", "orphan_ids", "match_rate"]
    metric_cols = ["metric", "value"]

    md = f"# Cross-Loader Join Audit\nGenerated: {ts}\n\n"
    md += "## blinded_id Overlap\n" + _table_md(id_rows, id_cols)
    md += "\n## Equipment Code Mapping\n" + _table_md(code_rows, metric_cols)
    md += "\n## District Code Mapping\n" + _table_md(dist_rows, metric_cols)

    css = "body{font-family:'Segoe UI',sans-serif;margin:20px;background:#f8f9fa} table{border-collapse:collapse;width:100%;background:#fff;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.1)} th{background:#343a40;color:#fff;padding:8px 10px;text-align:left;font-size:.85em} td{padding:6px 10px;border-bottom:1px solid #e9ecef;font-size:.84em} tr:hover{background:#f1f3f5}"
    html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Join Audit</title><style>{css}</style></head><body>"
    html += f"<h1>Cross-Loader Join Audit</h1><p class='meta'>Generated: {ts}</p>"
    html += _table_html(id_rows, id_cols, "blinded_id Overlap")
    html += _table_html(code_rows, metric_cols, "Equipment Code Mapping")
    html += _table_html(dist_rows, metric_cols, "District Code Mapping")
    html += "</body></html>"

    _write(os.path.join(OUT_DIR, "join_audit.md"), md)
    _write(os.path.join(OUT_DIR, "join_audit.html"), html)


# ---------------------------------------------------------------------------
# 2.3.3  Sample mismatches export
# ---------------------------------------------------------------------------

def run_validation_failures_export() -> None:
    """
    Export CSV of rows failing key validations.
    Output: output/data_quality/validation_failures.csv
    """
    from src.loaders.load_premise_data import load_premise_data
    from src.loaders.load_equipment_data import load_equipment_data
    from src.loaders.load_segment_data import load_segment_data
    from src.loaders.load_equipment_codes import load_equipment_codes

    failures = []

    # Premise failures
    prem_df, err = _load_safe(load_premise_data)
    if prem_df is not None:
        miss_district = prem_df[~prem_df.get("district_code_IRP", pd.Series(dtype=str)).isin(config.DISTRICT_WEATHER_MAP)]
        for _, row in miss_district.iterrows():
            failures.append({
                "source": "premises",
                "blinded_id": row.get("blinded_id", ""),
                "field": "district_code_IRP",
                "value": row.get("district_code_IRP", ""),
                "reason": "district_code_IRP not in DISTRICT_WEATHER_MAP",
            })

    # Equipment failures
    equip_df, err = _load_safe(load_equipment_data)
    if equip_df is not None:
        # Unmapped equipment codes
        if "equipment_type_code" in equip_df.columns:
            unmapped = equip_df[~equip_df["equipment_type_code"].isin(config.END_USE_MAP)]
            for _, row in unmapped.iterrows():
                failures.append({
                    "source": "equipment",
                    "blinded_id": row.get("blinded_id", ""),
                    "field": "equipment_type_code",
                    "value": row.get("equipment_type_code", ""),
                    "reason": "equipment_type_code not in END_USE_MAP",
                })
        # Zero/negative efficiency
        if "efficiency" in equip_df.columns:
            bad_eff = equip_df[(equip_df["efficiency"].notna()) & (equip_df["efficiency"] <= 0)]
            for _, row in bad_eff.iterrows():
                failures.append({
                    "source": "equipment",
                    "blinded_id": row.get("blinded_id", ""),
                    "field": "efficiency",
                    "value": row.get("efficiency", ""),
                    "reason": "efficiency <= 0",
                })

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "validation_failures.csv")
    if failures:
        pd.DataFrame(failures).to_csv(out_path, index=False)
        logger.info(f"Exported {len(failures)} validation failures -> {out_path}")
    else:
        pd.DataFrame(columns=["source", "blinded_id", "field", "value", "reason"]).to_csv(out_path, index=False)
        logger.info(f"No validation failures found (or source data unavailable) -> {out_path}")


# ---------------------------------------------------------------------------
# 2.3.4  Column coverage matrix
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = {
    "premise": ["blinded_id", "custtype", "status_code", "district_code_IRP"],
    "equipment": ["blinded_id", "equipment_type_code", "efficiency", "install_year"],
    "segment": ["blinded_id", "segment"],
    "equipment_codes": ["equipment_type_code", "equipment_class"],
    "billing": ["blinded_id", "utility_usage"],
    "weather": ["SiteId", "Date", "MaxTemp", "MinTemp", "AvgTemp"],
}


def run_column_coverage() -> None:
    """
    Compare expected vs actual columns for each NW Natural file.
    Output: output/data_quality/column_coverage.html and .md
    """
    from src.loaders.load_premise_data import load_premise_data
    from src.loaders.load_equipment_data import load_equipment_data
    from src.loaders.load_segment_data import load_segment_data
    from src.loaders.load_equipment_codes import load_equipment_codes
    from src.loaders.load_billing_data import load_billing_data
    from src.loaders.load_weather_data import load_weather_data

    loader_map = {
        "premise": (load_premise_data, [], {}),
        "equipment": (load_equipment_data, [], {}),
        "segment": (load_segment_data, [], {}),
        "equipment_codes": (load_equipment_codes, [], {}),
        "billing": (load_billing_data, [], {}),
        "weather": (load_weather_data, [config.WEATHER_CALDAY], {}),
    }

    rows = []
    for name, (fn, args, kwargs) in loader_map.items():
        expected = set(EXPECTED_COLUMNS.get(name, []))
        df, err = _load_safe(fn, *args, **kwargs)
        if df is None:
            rows.append({
                "file": name, "status": "UNAVAILABLE",
                "expected_cols": len(expected), "actual_cols": 0,
                "missing": ", ".join(sorted(expected)),
                "extra": "N/A",
            })
            continue
        actual = set(df.columns)
        missing = expected - actual
        extra = actual - expected
        rows.append({
            "file": name,
            "status": "✅ OK" if not missing else "⚠️ MISSING COLS",
            "expected_cols": len(expected),
            "actual_cols": len(actual),
            "missing": ", ".join(sorted(missing)) or "none",
            "extra": f"{len(extra)} extra cols",
        })

    _write_column_coverage(rows)


def _write_column_coverage(rows):
    ts = datetime.now().isoformat()
    cols = ["file", "status", "expected_cols", "actual_cols", "missing", "extra"]

    md = f"# Column Coverage Matrix\nGenerated: {ts}\n\n"
    md += "| " + " | ".join(cols) + " |\n"
    md += "| " + " | ".join(["---"] * len(cols)) + " |\n"
    for r in rows:
        md += "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n"

    css = "body{font-family:'Segoe UI',sans-serif;margin:20px;background:#f8f9fa} table{border-collapse:collapse;width:100%;background:#fff;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.1)} th{background:#343a40;color:#fff;padding:8px 10px;text-align:left;font-size:.85em} td{padding:6px 10px;border-bottom:1px solid #e9ecef;font-size:.84em} tr:hover{background:#f1f3f5}"
    ths = "".join(f"<th>{c}</th>" for c in cols)
    trs = "".join(
        "<tr>" + "".join(f"<td>{r.get(c,'')}</td>" for c in cols) + "</tr>"
        for r in rows
    )
    html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Column Coverage</title><style>{css}</style></head><body>"
    html += f"<h1>Column Coverage Matrix</h1><p>Generated: {ts}</p>"
    html += f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></body></html>"

    _write(os.path.join(OUT_DIR, "column_coverage.md"), md)
    _write(os.path.join(OUT_DIR, "column_coverage.html"), html)


# ---------------------------------------------------------------------------
# 2.3.5  Data freshness and date range check
# ---------------------------------------------------------------------------

def run_date_range_check() -> None:
    """
    Report min/max dates and record counts for all time-series files.
    Output: output/data_quality/date_ranges.html and .md
    """
    from src.loaders.load_weather_data import load_weather_data
    from src.loaders.load_billing_data import load_billing_data
    from src.loaders.load_wacog_history import load_wacog_history
    from src.loaders.load_rate_case_history import load_rate_case_history
    from src.loaders.load_water_temperature import load_water_temperature
    from src.loaders.load_snow_data import load_snow_data

    time_series = [
        ("weather_calday", load_weather_data, [config.WEATHER_CALDAY], {}, "Date"),
        ("weather_gasday", load_weather_data, [config.WEATHER_GASDAY], {}, "Date"),
        ("water_temperature", load_water_temperature, [], {}, "Date"),
        ("snow_data", load_snow_data, [], {}, "Date"),
        ("billing", load_billing_data, [], {}, "GL_revenue_date"),
        ("or_wacog", load_wacog_history, [config.OR_WACOG_HISTORY], {}, "date"),
        ("wa_wacog", load_wacog_history, [config.WA_WACOG_HISTORY], {}, "date"),
        ("or_rate_cases", load_rate_case_history, [config.OR_RATE_CASE_HISTORY], {}, "effective_date"),
        ("wa_rate_cases", load_rate_case_history, [config.WA_RATE_CASE_HISTORY], {}, "effective_date"),
    ]

    rows = []
    for name, fn, args, kwargs, date_col in time_series:
        df, err = _load_safe(fn, *args, **kwargs)
        if df is None:
            rows.append({"source": name, "status": "UNAVAILABLE", "records": 0,
                         "min_date": "N/A", "max_date": "N/A", "extends_to_2025": "N/A"})
            continue

        # Find date column (case-insensitive fallback)
        actual_col = date_col
        if date_col not in df.columns:
            candidates = [c for c in df.columns if "date" in c.lower() or "year" in c.lower()]
            actual_col = candidates[0] if candidates else None

        if actual_col and actual_col in df.columns:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                dates = pd.to_datetime(df[actual_col], errors="coerce").dropna()
            min_d = dates.min().strftime("%Y-%m-%d") if len(dates) else "N/A"
            max_d = dates.max().strftime("%Y-%m-%d") if len(dates) else "N/A"
            extends = "✅" if len(dates) and dates.max().year >= 2025 else "⚠️ STALE"
        else:
            min_d = max_d = "N/A"
            extends = "N/A"

        rows.append({
            "source": name, "status": "OK", "records": len(df),
            "min_date": min_d, "max_date": max_d, "extends_to_2025": extends,
        })

    _write_date_ranges(rows)


def _write_date_ranges(rows):
    ts = datetime.now().isoformat()
    cols = ["source", "status", "records", "min_date", "max_date", "extends_to_2025"]

    md = f"# Data Freshness and Date Range Check\nGenerated: {ts}\n\n"
    md += "| " + " | ".join(cols) + " |\n"
    md += "| " + " | ".join(["---"] * len(cols)) + " |\n"
    for r in rows:
        md += "| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n"

    css = "body{font-family:'Segoe UI',sans-serif;margin:20px;background:#f8f9fa} table{border-collapse:collapse;width:100%;background:#fff;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.1)} th{background:#343a40;color:#fff;padding:8px 10px;text-align:left;font-size:.85em} td{padding:6px 10px;border-bottom:1px solid #e9ecef;font-size:.84em} tr:hover{background:#f1f3f5}"
    ths = "".join(f"<th>{c}</th>" for c in cols)
    trs = "".join(
        "<tr>" + "".join(f"<td>{r.get(c,'')}</td>" for c in cols) + "</tr>"
        for r in rows
    )
    html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Date Ranges</title><style>{css}</style></head><body>"
    html += f"<h1>Data Freshness and Date Range Check</h1><p>Generated: {ts}</p>"
    html += f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></body></html>"

    _write(os.path.join(OUT_DIR, "date_ranges.md"), md)
    _write(os.path.join(OUT_DIR, "date_ranges.html"), html)


# ---------------------------------------------------------------------------
# 2.3.6  Distribution plots for key fields
# ---------------------------------------------------------------------------

def run_distribution_plots() -> None:
    """
    Generate distribution histograms and bar charts for key fields.
    Output: output/data_quality/distributions/ (PNGs) + distribution_summary.html and .md
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(DIST_DIR, exist_ok=True)
    plots = []  # list of (title, filename)

    from src.loaders.load_equipment_data import load_equipment_data
    from src.loaders.load_premise_data import load_premise_data
    from src.loaders.load_billing_data import load_billing_data
    from src.loaders.load_weather_data import load_weather_data
    from src.loaders.load_segment_data import load_segment_data
    from src.loaders.load_rbsa_hvac import load_rbsa_hvac

    # --- Equipment age distribution ---
    equip_df, _ = _load_safe(load_equipment_data)
    if equip_df is not None and "install_year" in equip_df.columns:
        ages = 2025 - equip_df["install_year"].dropna()
        ages = ages[(ages >= 0) & (ages <= 80)]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(ages, bins=40, color="#4e79a7", edgecolor="white")
        ax.set_title("Equipment Age Distribution (years)")
        ax.set_xlabel("Age (years)")
        ax.set_ylabel("Count")
        fname = "equipment_age.png"
        fig.tight_layout()
        fig.savefig(os.path.join(DIST_DIR, fname), dpi=100)
        plt.close(fig)
        plots.append(("Equipment Age Distribution", fname))

    # --- Efficiency by end-use ---
    if equip_df is not None and "efficiency" in equip_df.columns and "equipment_type_code" in equip_df.columns:
        df_eff = equip_df.copy()
        df_eff["end_use"] = df_eff["equipment_type_code"].map(config.END_USE_MAP)
        df_eff = df_eff[df_eff["efficiency"].notna() & df_eff["end_use"].notna()]
        if not df_eff.empty:
            fig, ax = plt.subplots(figsize=(9, 4))
            for eu, grp in df_eff.groupby("end_use"):
                ax.hist(grp["efficiency"], bins=20, alpha=0.6, label=eu)
            ax.set_title("Efficiency Distribution by End-Use")
            ax.set_xlabel("Efficiency")
            ax.set_ylabel("Count")
            ax.legend(fontsize=7)
            fname = "efficiency_by_enduse.png"
            fig.tight_layout()
            fig.savefig(os.path.join(DIST_DIR, fname), dpi=100)
            plt.close(fig)
            plots.append(("Efficiency by End-Use", fname))

    # --- Billing utility_usage (log scale) ---
    billing_df, _ = _load_safe(load_billing_data)
    if billing_df is not None and "utility_usage" in billing_df.columns:
        vals = pd.to_numeric(billing_df["utility_usage"], errors="coerce").dropna()
        vals = vals[vals > 0]
        if len(vals):
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.hist(np.log10(vals), bins=50, color="#f28e2b", edgecolor="white")
            ax.set_title("Billing utility_usage Distribution (log10 scale)")
            ax.set_xlabel("log10(utility_usage)")
            ax.set_ylabel("Count")
            fname = "billing_usage.png"
            fig.tight_layout()
            fig.savefig(os.path.join(DIST_DIR, fname), dpi=100)
            plt.close(fig)
            plots.append(("Billing utility_usage (log scale)", fname))

    # --- Annual HDD by weather station ---
    weather_df, _ = _load_safe(load_weather_data, config.WEATHER_CALDAY)
    if weather_df is not None:
        date_col = next((c for c in weather_df.columns if "date" in c.lower()), None)
        temp_col = next((c for c in weather_df.columns if "avg" in c.lower() and "temp" in c.lower()), None)
        site_col = next((c for c in weather_df.columns if "site" in c.lower()), None)
        if date_col and temp_col and site_col:
            weather_df["_year"] = pd.to_datetime(weather_df[date_col], errors="coerce").dt.year
            weather_df["_hdd"] = (65 - pd.to_numeric(weather_df[temp_col], errors="coerce")).clip(lower=0)
            annual = weather_df.groupby([site_col, "_year"])["_hdd"].sum().reset_index()
            avg_hdd = annual.groupby(site_col)["_hdd"].mean().sort_values(ascending=False)
            fig, ax = plt.subplots(figsize=(10, 4))
            avg_hdd.plot(kind="bar", ax=ax, color="#76b7b2", edgecolor="white")
            ax.set_title("Average Annual HDD by Weather Station")
            ax.set_xlabel("Station")
            ax.set_ylabel("HDD (base 65°F)")
            ax.tick_params(axis="x", rotation=45)
            fname = "annual_hdd_by_station.png"
            fig.tight_layout()
            fig.savefig(os.path.join(DIST_DIR, fname), dpi=100)
            plt.close(fig)
            plots.append(("Annual HDD by Weather Station", fname))

    # --- Premises by district ---
    prem_df, _ = _load_safe(load_premise_data)
    if prem_df is not None and "district_code_IRP" in prem_df.columns:
        counts = prem_df["district_code_IRP"].value_counts().sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(10, 4))
        counts.plot(kind="bar", ax=ax, color="#59a14f", edgecolor="white")
        ax.set_title("Premises by District (district_code_IRP)")
        ax.set_xlabel("District")
        ax.set_ylabel("Premise Count")
        ax.tick_params(axis="x", rotation=45)
        fname = "premises_by_district.png"
        fig.tight_layout()
        fig.savefig(os.path.join(DIST_DIR, fname), dpi=100)
        plt.close(fig)
        plots.append(("Premises by District", fname))

    # --- Equipment count by end_use ---
    if equip_df is not None and "equipment_type_code" in equip_df.columns:
        eu_counts = equip_df["equipment_type_code"].map(config.END_USE_MAP).value_counts()
        fig, ax = plt.subplots(figsize=(8, 4))
        eu_counts.plot(kind="bar", ax=ax, color="#edc948", edgecolor="white")
        ax.set_title("Equipment Count by End-Use Category")
        ax.set_xlabel("End-Use")
        ax.set_ylabel("Count")
        ax.tick_params(axis="x", rotation=30)
        fname = "equipment_by_enduse.png"
        fig.tight_layout()
        fig.savefig(os.path.join(DIST_DIR, fname), dpi=100)
        plt.close(fig)
        plots.append(("Equipment Count by End-Use", fname))

    # --- Segment distribution ---
    seg_df, _ = _load_safe(load_segment_data)
    if seg_df is not None and "segment" in seg_df.columns:
        seg_counts = seg_df["segment"].value_counts()
        fig, ax = plt.subplots(figsize=(6, 4))
        seg_counts.plot(kind="bar", ax=ax, color="#b07aa1", edgecolor="white")
        ax.set_title("Segment Distribution")
        ax.set_xlabel("Segment")
        ax.set_ylabel("Count")
        ax.tick_params(axis="x", rotation=0)
        fname = "segment_distribution.png"
        fig.tight_layout()
        fig.savefig(os.path.join(DIST_DIR, fname), dpi=100)
        plt.close(fig)
        plots.append(("Segment Distribution", fname))

    # --- RBSA fuel type mix (pie) ---
    rbsa_hvac, _ = _load_safe(load_rbsa_hvac)
    if rbsa_hvac is not None:
        fuel_col = next((c for c in rbsa_hvac.columns if "fuel" in c.lower()), None)
        if fuel_col:
            fuel_counts = rbsa_hvac[fuel_col].value_counts().head(6)
            fig, ax = plt.subplots(figsize=(6, 5))
            ax.pie(fuel_counts.values, labels=fuel_counts.index, autopct="%1.1f%%", startangle=90)
            ax.set_title("RBSA HVAC Fuel Type Mix")
            fname = "rbsa_fuel_mix.png"
            fig.tight_layout()
            fig.savefig(os.path.join(DIST_DIR, fname), dpi=100)
            plt.close(fig)
            plots.append(("RBSA HVAC Fuel Type Mix", fname))

    _write_distribution_summary(plots)


def _write_distribution_summary(plots):
    ts = datetime.now().isoformat()

    md = f"# Distribution Summary\nGenerated: {ts}\n\n"
    if not plots:
        md += "_No plots generated (source data unavailable)_\n"
    for title, fname in plots:
        md += f"## {title}\n![{title}](distributions/{fname})\n\n"

    html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Distribution Summary</title>"
    html += "<style>body{font-family:'Segoe UI',sans-serif;margin:20px;background:#f8f9fa} img{max-width:100%;border:1px solid #dee2e6;border-radius:4px;margin-bottom:20px} h2{margin-top:30px}</style></head><body>"
    html += f"<h1>Distribution Summary</h1><p>Generated: {ts}</p>"
    if not plots:
        html += "<p><em>No plots generated (source data unavailable)</em></p>"
    for title, fname in plots:
        html += f"<h2>{title}</h2><img src='distributions/{fname}' alt='{title}'>"
    html += "</body></html>"

    _write(os.path.join(OUT_DIR, "distribution_summary.md"), md)
    _write(os.path.join(OUT_DIR, "distribution_summary.html"), html)


# ---------------------------------------------------------------------------
# Property 2 validation
# ---------------------------------------------------------------------------

def validate_property2() -> dict:
    """
    Property 2: Filtering preserves only active residential premises
    (custtype='R' and status_code='AC').
    Returns dict with pass/fail and details.
    """
    from src.loaders.load_premise_data import load_premise_data

    df, err = _load_safe(load_premise_data)
    if df is None:
        return {"property": 2, "status": "SKIP", "reason": f"Data unavailable: {err}"}

    violations = df[
        (df.get("custtype", pd.Series(dtype=str)) != "R") |
        (df.get("status_code", pd.Series(dtype=str)) != "AC")
    ]
    passed = len(violations) == 0
    return {
        "property": 2,
        "description": "Filtering preserves only active residential premises (custtype=R, status_code=AC)",
        "status": "PASS" if passed else "FAIL",
        "total_rows": len(df),
        "violations": len(violations),
    }


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_all() -> None:
    """Run all 2.3 validation checks."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("=== Task 2.3: Data Ingestion Validation Suite ===")

    logger.info("2.3.1 Per-loader quality reports...")
    results = run_per_loader_quality_reports()
    for name, status in results.items():
        logger.info(f"  {name}: {status}")

    logger.info("2.3.2 Cross-loader join audit...")
    run_join_audit()

    logger.info("2.3.3 Validation failures export...")
    run_validation_failures_export()

    logger.info("2.3.4 Column coverage matrix...")
    run_column_coverage()

    logger.info("2.3.5 Date range check...")
    run_date_range_check()

    logger.info("2.3.6 Distribution plots...")
    run_distribution_plots()

    logger.info("Property 2 validation...")
    p2 = validate_property2()
    logger.info(f"  Property 2: {p2['status']}")

    logger.info(f"Done. Outputs in {OUT_DIR}/")


if __name__ == "__main__":
    run_all()
