"""Shared helpers for loader diagnostic output."""

import os
import pandas as pd
from datetime import datetime


OUTPUT_DIR = os.path.join("output", "loaders")
QUALITY_DIR = os.path.join("output", "data_quality")


def save_diagnostics(df: pd.DataFrame, name: str, extra_info: str = ""):
    """Save loader diagnostics: summary txt + sample CSV to output/loaders/."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Summary text
    summary_path = os.path.join(OUTPUT_DIR, f"{name}_summary.txt")
    with open(summary_path, "w") as f:
        f.write(f"=== {name} ===\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n\n")
        f.write("Columns:\n")
        for col in df.columns:
            dtype = df[col].dtype
            nulls = df[col].isna().sum()
            f.write(f"  {col:40s}  {str(dtype):12s}  nulls={nulls}\n")
        if extra_info:
            f.write(f"\n{extra_info}\n")
        f.write(f"\nFirst 5 rows:\n{df.head().to_string()}\n")
        f.write(f"\nDescribe (numeric):\n{df.describe().to_string()}\n")
    print(f"  Summary -> {summary_path}")

    # Sample CSV (first 100 rows)
    sample_path = os.path.join(OUTPUT_DIR, f"{name}_sample.csv")
    df.head(100).to_csv(sample_path, index=False)
    print(f"  Sample  -> {sample_path}")


def _col_stats(df: pd.DataFrame, col: str) -> dict:
    """Compute stats for a single column."""
    s = df[col]
    stats = {
        'column': col,
        'dtype': str(s.dtype),
        'count': len(s),
        'nulls': int(s.isna().sum()),
        'null_pct': round(s.isna().mean() * 100, 1),
        'unique': int(s.nunique()),
    }
    if pd.api.types.is_numeric_dtype(s):
        stats['min'] = s.min()
        stats['max'] = s.max()
        stats['mean'] = round(s.mean(), 2) if s.notna().any() else None
        stats['median'] = round(s.median(), 2) if s.notna().any() else None
    else:
        top = s.value_counts().head(5)
        stats['top_values'] = '; '.join(f"{v} ({c})" for v, c in top.items())
    return stats


def write_quality_report_md(df: pd.DataFrame, name: str, extra: str = "") -> str:
    """Generate a Markdown data quality report and return the content."""
    lines = [
        f"# Data Quality Report: {name}",
        f"Generated: {datetime.now().isoformat()}",
        "",
        f"**Shape**: {df.shape[0]:,} rows × {df.shape[1]} columns",
        "",
    ]

    if extra:
        lines += [extra, ""]

    # Column stats table
    lines += ["## Column Summary", ""]
    lines += ["| Column | Type | Nulls | Null% | Unique | Details |"]
    lines += ["|--------|------|-------|-------|--------|---------|"]

    for col in df.columns:
        st = _col_stats(df, col)
        flag = ""
        if st['null_pct'] > 50:
            flag = " ⛔"
        elif st['null_pct'] > 10:
            flag = " ⚠️"

        if pd.api.types.is_numeric_dtype(df[col]):
            detail = f"min={st.get('min')}, max={st.get('max')}, mean={st.get('mean')}"
        else:
            detail = st.get('top_values', '')
            if len(detail) > 80:
                detail = detail[:77] + "..."

        lines.append(
            f"| {col} | {st['dtype']} | {st['nulls']:,} | {st['null_pct']}%{flag} "
            f"| {st['unique']:,} | {detail} |"
        )

    # Numeric describe
    num_cols = df.select_dtypes(include='number')
    if not num_cols.empty:
        lines += ["", "## Numeric Summary", ""]
        lines += ["```"]
        lines += [num_cols.describe().to_string()]
        lines += ["```"]

    # Sample rows
    lines += ["", "## Sample Rows (first 5)", ""]
    lines += [df.head().to_markdown(index=False)]

    return "\n".join(lines)


def write_quality_report_html(df: pd.DataFrame, name: str, extra: str = "") -> str:
    """Generate an HTML data quality report and return the content."""
    stats_rows = []
    for col in df.columns:
        st = _col_stats(df, col)
        flag = ""
        if st['null_pct'] > 50:
            flag = ' style="background:#f8d7da;"'
        elif st['null_pct'] > 10:
            flag = ' style="background:#fff3cd;"'

        if pd.api.types.is_numeric_dtype(df[col]):
            detail = f"min={st.get('min')}, max={st.get('max')}, mean={st.get('mean')}"
        else:
            detail = st.get('top_values', '')
            if len(detail) > 80:
                detail = detail[:77] + "..."

        stats_rows.append(
            f'<tr{flag}><td>{col}</td><td>{st["dtype"]}</td>'
            f'<td>{st["nulls"]:,}</td><td>{st["null_pct"]}%</td>'
            f'<td>{st["unique"]:,}</td><td>{detail}</td></tr>'
        )

    sample_html = df.head(10).to_html(index=False, classes="sample")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Data Quality: {name}</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f8f9fa; }}
h1 {{ font-size: 1.3em; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }}
th {{ background: #343a40; color: #fff; padding: 8px 10px; text-align: left; font-size: 0.85em; }}
td {{ padding: 6px 10px; border-bottom: 1px solid #e9ecef; font-size: 0.84em; }}
tr:hover {{ background: #f1f3f5; }}
.sample td {{ max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.meta {{ color: #666; font-size: 0.9em; }}
</style></head><body>
<h1>Data Quality Report: {name}</h1>
<p class="meta">Generated: {datetime.now().isoformat()} | Shape: {df.shape[0]:,} rows × {df.shape[1]} columns</p>
{"<p>" + extra + "</p>" if extra else ""}
<h2>Column Summary</h2>
<table><thead><tr><th>Column</th><th>Type</th><th>Nulls</th><th>Null%</th><th>Unique</th><th>Details</th></tr></thead>
<tbody>{"".join(stats_rows)}</tbody></table>
<h2>Sample Rows</h2>
{sample_html}
</body></html>"""
    return html


def save_quality_report(df: pd.DataFrame, name: str, extra: str = ""):
    """Save both HTML and MD quality reports to output/data_quality/."""
    os.makedirs(QUALITY_DIR, exist_ok=True)

    md_content = write_quality_report_md(df, name, extra)
    md_path = os.path.join(QUALITY_DIR, f"{name}_quality_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"  Quality MD  -> {md_path}")

    html_content = write_quality_report_html(df, name, extra)
    html_path = os.path.join(QUALITY_DIR, f"{name}_quality_report.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  Quality HTML -> {html_path}")
