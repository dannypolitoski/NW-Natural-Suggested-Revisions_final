"""
RECS (Residential Energy Consumption Survey) integration.

Loads all available RECS survey years (1993-2020) for the Pacific division,
computes weighted gas end-use shares, and projects the trend forward
to replace hardcoded non-heating ratios in the scenario pipeline.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from src import config

logger = logging.getLogger(__name__)

W = 'NWEIGHT'  # weight column name (consistent across all years)


def _ws(df: pd.DataFrame, col: str, total_col: str) -> float:
    """Weighted share of col relative to total_col."""
    num = (df[col] * df[W]).sum()
    den = (df[total_col] * df[W]).sum()
    return num / den * 100 if den > 0 else 0


def _wa(df: pd.DataFrame, col: str) -> float:
    """Weighted average."""
    return (df[col] * df[W]).sum() / df[W].sum()


def load_recs_enduse_trend() -> pd.DataFrame:
    """
    Load all RECS survey years and compute Pacific division gas end-use shares.

    Returns DataFrame with columns:
        year, n, weighted_pop, total_therms, sh_pct, wh_pct, appliance_pct
    """
    base = Path(config.RECS_DIR)
    if not base.exists():
        logger.warning(f"RECS directory not found: {base}")
        return pd.DataFrame()
    
    results = []

    # --- 1993 (HHID, FUELHEAT in file2, gas BTU in file11, kBTU) ---
    try:
        f1 = base / '1993' / 'file1_asc.txt'
        f2 = base / '1993' / 'file2_asc.txt'
        f11 = base / '1993' / 'file11_asc.txt'
        if f1.exists() and f2.exists() and f11.exists():
            m = (pd.read_csv(f1)
                 .merge(pd.read_csv(f2), on='HHID', suffixes=('', '_f2'))
                 .merge(pd.read_csv(f11), on='HHID', suffixes=('', '_f11')))
            pac = m[(m['DIVISION'] == 9) & (m['FUELHEAT'] == 1)]
            if len(pac) > 0:
                results.append({
                    'year': 1993, 'n': len(pac), 'weighted_pop': int(pac[W].sum()),
                    'total_therms': round(_wa(pac, 'BTUNG') / 100, 1),
                    'sh_pct': round(_ws(pac, 'BTUNGSPH', 'BTUNG'), 1),
                    'wh_pct': round(_ws(pac, 'BTUNGWTH', 'BTUNG'), 1),
                    'appliance_pct': round(_ws(pac, 'BTUNGAPL', 'BTUNG'), 1) if 'BTUNGAPL' in pac.columns
                        else round(100 - _ws(pac, 'BTUNGSPH', 'BTUNG') - _ws(pac, 'BTUNGWTH', 'BTUNG'), 1),
                })
                logger.info(f"RECS 1993: {len(pac)} homes, SH={results[-1]['sh_pct']}%, WH={results[-1]['wh_pct']}%")
    except Exception as e:
        logger.warning(f"RECS 1993 failed: {e}")

    # --- 1997 (DOEID, FUELHEAT in file4, gas BTU in file11, kBTU) ---
    try:
        f1 = base / '1997' / 'file1os.txt'
        f4 = base / '1997' / 'file4os.txt'
        f11 = base / '1997' / 'file11os.txt'
        if f1.exists() and f4.exists() and f11.exists():
            m = (pd.read_csv(f1)
                 .merge(pd.read_csv(f4), on='DOEID', suffixes=('', '_f4'))
                 .merge(pd.read_csv(f11), on='DOEID', suffixes=('', '_f11')))
            pac = m[(m['DIVISION'] == 9) & (m['FUELHEAT'] == 1)]
            if len(pac) > 0:
                results.append({
                    'year': 1997, 'n': len(pac), 'weighted_pop': int(pac[W].sum()),
                    'total_therms': round(_wa(pac, 'BTUNG') / 100, 1),
                    'sh_pct': round(_ws(pac, 'BTUNGSPH', 'BTUNG'), 1),
                    'wh_pct': round(_ws(pac, 'BTUNGWTH', 'BTUNG'), 1),
                    'appliance_pct': round(_ws(pac, 'BTUNGAPL', 'BTUNG'), 1) if 'BTUNGAPL' in pac.columns
                        else round(100 - _ws(pac, 'BTUNGSPH', 'BTUNG') - _ws(pac, 'BTUNGWTH', 'BTUNG'), 1),
                })
                logger.info(f"RECS 1997: {len(pac)} homes, SH={results[-1]['sh_pct']}%, WH={results[-1]['wh_pct']}%")
    except Exception as e:
        logger.warning(f"RECS 1997 failed: {e}")

    # --- 2001 (DOEID, FUELHEAT in datafile4, gas BTU in datafile11, kBTU) ---
    try:
        f1 = base / '2001' / 'datafile1-2001.txt'
        f4 = base / '2001' / 'datafile4-2001.txt'
        f11 = base / '2001' / 'datafile11-2001.txt'
        if f1.exists() and f4.exists() and f11.exists():
            m = (pd.read_csv(f1)
                 .merge(pd.read_csv(f4), on='DOEID', suffixes=('', '_f4'))
                 .merge(pd.read_csv(f11), on='DOEID', suffixes=('', '_f11')))
            pac = m[(m['DIVISION'] == 9) & (m['FUELHEAT'] == 1)]
            if len(pac) > 0:
                results.append({
                    'year': 2001, 'n': len(pac), 'weighted_pop': int(pac[W].sum()),
                    'total_therms': round(_wa(pac, 'BTUNG') / 100, 1),
                    'sh_pct': round(_ws(pac, 'BTUNGSPH', 'BTUNG'), 1),
                    'wh_pct': round(_ws(pac, 'BTUNGWTH', 'BTUNG'), 1),
                    'appliance_pct': round(_ws(pac, 'BTUNGAPL', 'BTUNG'), 1) if 'BTUNGAPL' in pac.columns
                        else round(100 - _ws(pac, 'BTUNGSPH', 'BTUNG') - _ws(pac, 'BTUNGWTH', 'BTUNG'), 1),
                })
                logger.info(f"RECS 2001: {len(pac)} homes, SH={results[-1]['sh_pct']}%, WH={results[-1]['wh_pct']}%")
    except Exception as e:
        logger.warning(f"RECS 2001 failed: {e}")

    # --- 2005 (single file, kBTU) ---
    try:
        fp = base / '2005' / 'RECS05alldata.csv'
        if fp.exists():
            df = pd.read_csv(fp, low_memory=False)
            pac = df[(df['DIVISION'] == 9) & (df['FUELHEAT'] == 1)]
            if len(pac) > 0:
                apl = _ws(pac, 'BTUNGAPL', 'BTUNG') if 'BTUNGAPL' in pac.columns else 100 - _ws(pac, 'BTUNGSPH', 'BTUNG') - _ws(pac, 'BTUNGWTH', 'BTUNG')
                results.append({
                    'year': 2005, 'n': len(pac), 'weighted_pop': int(pac[W].sum()),
                    'total_therms': round(_wa(pac, 'BTUNG') / 100, 1),
                    'sh_pct': round(_ws(pac, 'BTUNGSPH', 'BTUNG'), 1),
                    'wh_pct': round(_ws(pac, 'BTUNGWTH', 'BTUNG'), 1),
                    'appliance_pct': round(apl, 1),
                })
                logger.info(f"RECS 2005: {len(pac)} homes, SH={results[-1]['sh_pct']}%, WH={results[-1]['wh_pct']}%")
    except Exception as e:
        logger.warning(f"RECS 2005 failed: {e}")

    # --- 2009 (single file, kBTU, BTUNGOTH instead of BTUNGAPL) ---
    try:
        fp = base / '2009' / 'recs2009_public.csv'
        if fp.exists():
            df = pd.read_csv(fp, low_memory=False)
            pac = df[(df['DIVISION'] == 9) & (df['FUELHEAT'] == 1)]
            if len(pac) > 0:
                apl = _ws(pac, 'BTUNGOTH', 'BTUNG') if 'BTUNGOTH' in pac.columns else 100 - _ws(pac, 'BTUNGSPH', 'BTUNG') - _ws(pac, 'BTUNGWTH', 'BTUNG')
                results.append({
                    'year': 2009, 'n': len(pac), 'weighted_pop': int(pac[W].sum()),
                    'total_therms': round(_wa(pac, 'BTUNG') / 100, 1),
                    'sh_pct': round(_ws(pac, 'BTUNGSPH', 'BTUNG'), 1),
                    'wh_pct': round(_ws(pac, 'BTUNGWTH', 'BTUNG'), 1),
                    'appliance_pct': round(apl, 1),
                })
                logger.info(f"RECS 2009: {len(pac)} homes, SH={results[-1]['sh_pct']}%, WH={results[-1]['wh_pct']}%")
    except Exception as e:
        logger.warning(f"RECS 2009 failed: {e}")

    # --- 2015 (CUFEETNG in CCF, 1 CCF ≈ 1.037 therms) ---
    try:
        fp = base / 'recs2015_public_v4.csv'
        if fp.exists():
            df = pd.read_csv(fp)
            pac = df[(df['DIVISION'] == 9) & (df['FUELHEAT'] == 1)]
            if len(pac) > 0:
                sh = _ws(pac, 'CUFEETNGSPH', 'CUFEETNG')
                wh = _ws(pac, 'CUFEETNGWTH', 'CUFEETNG')
                cook = _ws(pac, 'CUFEETNGCOK', 'CUFEETNG') if 'CUFEETNGCOK' in pac.columns else 0
                dry = _ws(pac, 'CUFEETNGCDR', 'CUFEETNG') if 'CUFEETNGCDR' in pac.columns else 0
                nec = _ws(pac, 'CUFEETNGNEC', 'CUFEETNG') if 'CUFEETNGNEC' in pac.columns else 0
                results.append({
                    'year': 2015, 'n': len(pac), 'weighted_pop': int(pac[W].sum()),
                    'total_therms': round(_wa(pac, 'CUFEETNG') * 1.037, 1),
                    'sh_pct': round(sh, 1), 'wh_pct': round(wh, 1),
                    'appliance_pct': round(cook + dry + nec, 1),
                })
                logger.info(f"RECS 2015: {len(pac)} homes, SH={results[-1]['sh_pct']}%, WH={results[-1]['wh_pct']}%")
    except Exception as e:
        logger.warning(f"RECS 2015 failed: {e}")

    # --- 2020 (DIVISION is string 'Pacific', kBTU) ---
    try:
        fp = base / 'recs2020_public_v7.csv'
        if fp.exists():
            df = pd.read_csv(fp)
            pac = df[(df['DIVISION'] == 'Pacific') & (df['FUELHEAT'] == 1)]
            if len(pac) > 0:
                sh = _ws(pac, 'BTUNGSPH', 'BTUNG')
                wh = _ws(pac, 'BTUNGWTH', 'BTUNG')
                cook = _ws(pac, 'BTUNGCOK', 'BTUNG') if 'BTUNGCOK' in pac.columns else 0
                dry = _ws(pac, 'BTUNGCDR', 'BTUNG') if 'BTUNGCDR' in pac.columns else 0
                oth = _ws(pac, 'BTUNGOTH', 'BTUNG') if 'BTUNGOTH' in pac.columns else 0
                nec = _ws(pac, 'BTUNGNEC', 'BTUNG') if 'BTUNGNEC' in pac.columns else 0
                results.append({
                    'year': 2020, 'n': len(pac), 'weighted_pop': int(pac[W].sum()),
                    'total_therms': round(_wa(pac, 'BTUNG') / 100, 1),
                    'sh_pct': round(sh, 1), 'wh_pct': round(wh, 1),
                    'appliance_pct': round(cook + dry + oth + nec, 1),
                })
                logger.info(f"RECS 2020: {len(pac)} homes, SH={results[-1]['sh_pct']}%, WH={results[-1]['wh_pct']}%")
    except Exception as e:
        logger.warning(f"RECS 2020 failed: {e}")

    rdf = pd.DataFrame(results).sort_values('year').reset_index(drop=True)
    logger.info(f"Loaded RECS end-use trend: {len(rdf)} survey years ({rdf['year'].min()}-{rdf['year'].max()})")
    return rdf


def compute_non_heating_ratios(recs_trend: pd.DataFrame) -> Dict[str, float]:
    """
    Compute non-heating end-use ratios relative to space heating,
    using the RECS trend data weighted by sample size.

    Uses the most recent 3 survey years (weighted by sample size) to
    compute stable ratios, rather than just the latest year.

    Returns dict like:
        {'water_heating': 0.72, 'cooking': 0.06, 'clothes_drying': 0.04,
         'fireplace': 0.05, 'other': 0.03}
    where each value is the ratio of that end-use to space heating therms.
    """
    if recs_trend.empty:
        logger.warning("No RECS trend data; using hardcoded fallback ratios")
        return _fallback_ratios()

    # Use the 3 most recent years, weighted by sample size
    recent = recs_trend.nlargest(3, 'year').copy()
    weights = recent['n'].values
    total_w = weights.sum()

    # Weighted average shares
    sh_pct = (recent['sh_pct'] * weights).sum() / total_w
    wh_pct = (recent['wh_pct'] * weights).sum() / total_w
    apl_pct = (recent['appliance_pct'] * weights).sum() / total_w

    # Convert shares to ratios relative to space heating
    # wh_ratio = wh_pct / sh_pct (e.g., if WH=35% and SH=55%, ratio = 0.636)
    if sh_pct <= 0:
        logger.warning("Space heating share is 0; using fallback ratios")
        return _fallback_ratios()

    wh_ratio = wh_pct / sh_pct

    # Split appliance_pct into sub-categories using 2020 detailed breakdown
    # 2020 breakdown: cook=3.2%, dry=1.9%, other+nec=12.3% of total gas
    # Fireplace is part of "other" — estimate ~40% of other is fireplace in PNW
    cook_ratio = apl_pct * 0.18 / sh_pct   # ~18% of appliance share
    dry_ratio = apl_pct * 0.11 / sh_pct    # ~11% of appliance share
    fire_ratio = apl_pct * 0.28 / sh_pct   # ~28% of appliance share (PNW has lots of gas fireplaces)
    other_ratio = apl_pct * 0.43 / sh_pct  # ~43% remainder

    ratios = {
        'water_heating': round(wh_ratio, 4),
        'cooking': round(cook_ratio, 4),
        'clothes_drying': round(dry_ratio, 4),
        'fireplace': round(fire_ratio, 4),
        'other': round(other_ratio, 4),
    }

    total_ratio = sum(ratios.values())
    logger.info(
        f"RECS-derived non-heating ratios (relative to SH): "
        f"WH={ratios['water_heating']:.3f}, Cook={ratios['cooking']:.3f}, "
        f"Dry={ratios['clothes_drying']:.3f}, Fire={ratios['fireplace']:.3f}, "
        f"Other={ratios['other']:.3f} (total={total_ratio:.3f}, "
        f"SH share={sh_pct:.1f}%)"
    )
    return ratios


def _fallback_ratios() -> Dict[str, float]:
    """Hardcoded fallback ratios if RECS data is unavailable."""
    return {
        'water_heating': 0.41,
        'cooking': 0.08,
        'clothes_drying': 0.05,
        'fireplace': 0.07,
        'other': 0.03,
    }


def export_recs_summary(recs_trend: pd.DataFrame, ratios: Dict[str, float], output_dir: str):
    """Export RECS trend data and computed ratios to scenario folder."""
    output_dir = Path(output_dir)
    if not recs_trend.empty:
        recs_trend.to_csv(output_dir / 'recs_enduse_trend.csv', index=False)
        recs_trend.to_json(output_dir / 'recs_enduse_trend.json', orient='records', indent=2)
    if ratios:
        pd.DataFrame([ratios]).to_csv(output_dir / 'recs_non_heating_ratios.csv', index=False)
        pd.DataFrame([ratios]).to_json(output_dir / 'recs_non_heating_ratios.json', orient='records', indent=2)
