"""Load RBSA 2022 HVAC data."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_rbsa_hvac(path: str = None) -> pd.DataFrame:
    path = path or config.RBSA_2022_HVAC
    if not os.path.exists(path): raise FileNotFoundError(f"RBSA HVAC not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} HVAC records")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try: df = load_rbsa_hvac(); print(f"  {len(df)} records"); save_diagnostics(df, "rbsa_hvac")
    except FileNotFoundError as e: print(f"  Skipped: {e}")
