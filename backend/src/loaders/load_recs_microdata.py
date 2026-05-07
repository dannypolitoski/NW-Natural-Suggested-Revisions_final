"""Load EIA RECS microdata and build end-use benchmarks."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

_COL_MAP = {'DIVISION':'division','REGIONC':'division','FUELHEAT':'fuelheat','TYPEHUQ':'typehuq',
    'YEARMADERANGE':'yearmaderange','TOTSQFT_EN':'totsqft','TOTSQFT':'totsqft',
    'BTUNG':'btung','BTUNGSPH':'btungsph','BTUNGWTH':'btungwth','BTUNGCOK':'btungcok',
    'BTUNGCDR':'btungcdr','BTUNGNEC':'btungnec','BTUNGOTH':'btungoth','BTUNGAPL':'btungapl',
    'NWEIGHT':'nweight','STATE_FIPS':'state_fips'}

def load_recs_microdata(path: str, year: int) -> pd.DataFrame:
    if not os.path.exists(path): raise FileNotFoundError(f"RECS file not found: {path}")
    df = pd.read_csv(path)
    df = df.rename(columns={k: v for k, v in _COL_MAP.items() if k in df.columns})
    logger.info(f"Loaded {len(df)} RECS {year} records")
    return df

def build_recs_enduse_benchmarks(recs: pd.DataFrame, division: int = 9, fuelheat: int = 1) -> pd.DataFrame:
    if recs.empty: return pd.DataFrame()
    m = pd.Series(True, index=recs.index)
    if 'division' in recs.columns: m &= (recs['division'] == division)
    if 'fuelheat' in recs.columns: m &= (recs['fuelheat'] == fuelheat)
    f = recs[m].copy()
    if f.empty: return pd.DataFrame()
    w = f.get('nweight', pd.Series(1, index=f.index)); tw = w.sum()
    btu = {'btungsph':'space_heating','btungwth':'water_heating','btungcok':'cooking',
           'btungcdr':'clothes_drying','btungnec':'other_nec','btungoth':'other','btungapl':'appliances'}
    rows = []
    for col, eu in btu.items():
        if col not in f.columns: continue
        v = pd.to_numeric(f[col], errors='coerce').fillna(0)
        rows.append({'end_use': eu, 'avg_therms': round((v * w).sum() / tw / 100_000, 1), 'weighted_count': int(tw)})
    df = pd.DataFrame(rows)
    total = df['avg_therms'].sum()
    if total > 0: df['share'] = (df['avg_therms'] / total).round(3)
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for yr, path in [(2020, config.RECS_2020_CSV), (2015, config.RECS_2015_CSV)]:
        try:
            df = load_recs_microdata(path, yr)
            bm = build_recs_enduse_benchmarks(df)
            if not bm.empty:
                print(f"  RECS {yr} benchmarks:")
                for _, r in bm.iterrows(): print(f"    {r['end_use']:20s} {r['avg_therms']:8.1f} therms")
                save_diagnostics(bm, f"recs_{yr}_benchmarks")
        except FileNotFoundError as e: print(f"  RECS {yr}: skipped ({e})")
