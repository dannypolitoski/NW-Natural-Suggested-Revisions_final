"""Load NW Natural equipment inventory data."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_equipment_data(path: str = None) -> pd.DataFrame:
    path = path or config.EQUIPMENT_DATA
    if not os.path.exists(path):
        raise FileNotFoundError(f"Equipment data file not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} equipment records from {path}")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_equipment_data()
    print(f"  {len(df)} equipment records")
    save_diagnostics(df, "equipment_data")
