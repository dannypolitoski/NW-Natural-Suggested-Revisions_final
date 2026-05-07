"""Load Bull Run water temperature data."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_water_temperature(path: str = None) -> pd.DataFrame:
    path = path or config.WATER_TEMP
    if not os.path.exists(path):
        raise FileNotFoundError(f"Water temperature file not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} water temperature records from {path}")
    for c in df.columns:
        if 'date' in c.lower():
            try: df[c] = pd.to_datetime(df[c])
            except: pass
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_water_temperature()
    print(f"  {len(df)} records")
    save_diagnostics(df, "water_temperature")
