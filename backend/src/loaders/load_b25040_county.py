"""Load offline ACS B25040 (House Heating Fuel) county CSV files."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_b25040_county_files(directory: str = None) -> pd.DataFrame:
    directory = directory or config.B25040_COUNTY_DIR
    if not os.path.exists(directory): raise FileNotFoundError(f"B25040 dir not found: {directory}")
    csvs = sorted(f for f in os.listdir(directory) if f.endswith('.csv'))
    dfs = []
    for f in csvs:
        try: dfs.append(pd.read_csv(os.path.join(directory, f)))
        except Exception as e: logger.warning(f"Error loading {f}: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try: df = load_b25040_county_files(); print(f"  {len(df)} records"); save_diagnostics(df, "b25040_county")
    except FileNotFoundError as e: print(f"  Skipped: {e}")
