"""Load PSU Population Research Center county forecasts."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_psu_population_forecasts(directory: str = None) -> pd.DataFrame:
    directory = directory or config.PSU_PROJECTION_DIR
    if not os.path.exists(directory): raise FileNotFoundError(f"PSU dir not found: {directory}")
    dfs = []
    for yd in sorted(os.listdir(directory)):
        yp = os.path.join(directory, yd)
        if not os.path.isdir(yp): continue
        fy = int(yd) if yd.isdigit() else 0
        for f in (f for f in os.listdir(yp) if f.endswith('.csv')):
            try:
                df = pd.read_csv(os.path.join(yp, f))
                cols = [c.upper() for c in df.columns]
                if 'YEAR' in cols and 'POPULATION' in cols:
                    df.columns = cols
                    df['POPULATION'] = pd.to_numeric(df['POPULATION'].astype(str).str.replace(',',''), errors='coerce')
                    df = df.rename(columns={'YEAR': 'year', 'POPULATION': 'population'})
                    df['county'] = f.replace('.csv','').replace('_',' ').title()
                    df['forecast_year'] = fy
                    dfs.append(df[['county','year','population','forecast_year']])
                else:
                    for _, row in df.iterrows():
                        if 'county' in str(row.iloc[0]).lower():
                            ycols = [c for c in df.columns[1:] if str(c).isdigit()]
                            recs = [{'county': f.replace('.csv','').title(), 'year': int(c),
                                     'population': pd.to_numeric(str(row[c]).replace(',',''), errors='coerce'),
                                     'forecast_year': fy} for c in ycols]
                            if recs: dfs.append(pd.DataFrame(recs))
                            break
            except Exception as e: logger.warning(f"Error loading {f}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        df = load_psu_population_forecasts()
        print(f"  {len(df)} records, {df['county'].nunique()} counties")
        save_diagnostics(df, "psu_forecasts")
    except FileNotFoundError as e: print(f"  Skipped: {e}")
