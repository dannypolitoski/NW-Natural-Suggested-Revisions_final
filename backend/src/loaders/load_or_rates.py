"""Load Oregon current rate schedule."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_or_rates(path: str = None) -> pd.DataFrame:
    path = path or config.OR_RATES
    if not os.path.exists(path):
        raise FileNotFoundError(f"Oregon rates file not found: {path}")
    df = pd.read_csv(path)
    if 'Rate/Value' in df.columns:
        df['Rate/Value'] = pd.to_numeric(df['Rate/Value'], errors='coerce')
    logger.info(f"Loaded {len(df)} Oregon rate records")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_or_rates()
    print(f"  {len(df)} records")
    save_diagnostics(df, "or_rates")
