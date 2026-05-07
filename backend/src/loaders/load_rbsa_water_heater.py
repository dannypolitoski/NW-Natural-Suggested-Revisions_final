"""Load RBSA 2022 water heater data."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_rbsa_water_heater(path: str = None) -> pd.DataFrame:
    path = path or config.RBSA_2022_WATER_HEATER
    if not os.path.exists(path): raise FileNotFoundError(f"RBSA WH not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} water heater records")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try: df = load_rbsa_water_heater(); print(f"  {len(df)} records"); save_diagnostics(df, "rbsa_water_heater")
    except FileNotFoundError as e: print(f"  Skipped: {e}")
