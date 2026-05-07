"""Load Portland daily snow data."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_snow_data(path: str = None) -> pd.DataFrame:
    path = path or config.PORTLAND_SNOW
    if not os.path.exists(path):
        raise FileNotFoundError(f"Snow data file not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} snow records from {path}")
    if 'Date' in df.columns:
        try: df['Date'] = pd.to_datetime(df['Date'])
        except: pass
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_snow_data()
    print(f"  {len(df)} records")
    if 'snow' in df.columns:
        print(f"  Snow days: {(df['snow'] > 0).sum()}")
    save_diagnostics(df, "snow_data")
