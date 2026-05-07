"""Load WA OFM postcensal housing unit estimates."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_ofm_housing(path: str = None) -> pd.DataFrame:
    path = path or config.OFM_HOUSING_XLSX
    if not os.path.exists(path): raise FileNotFoundError(f"OFM file not found: {path}")
    df = pd.read_excel(path, sheet_name='Housing Units')
    if 'Filter' in df.columns: df = df[df['Filter'] == 1].copy()
    cc = next((c for c in ['County','county','Jurisdiction'] if c in df.columns), None)
    if cc: df = df[df[cc].str.strip().isin(['Clark','Skamania','Klickitat'])].copy()
    logger.info(f"Loaded {len(df)} OFM housing rows")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try: df = load_ofm_housing(); print(f"  {len(df)} rows"); save_diagnostics(df, "ofm_housing")
    except FileNotFoundError as e: print(f"  Skipped: {e}")
