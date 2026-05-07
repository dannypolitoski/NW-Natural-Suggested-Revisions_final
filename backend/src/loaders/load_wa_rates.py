"""Load Washington current rate schedule."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_wa_rates(path: str = None) -> pd.DataFrame:
    path = path or config.WA_RATES
    if not os.path.exists(path):
        raise FileNotFoundError(f"Washington rates file not found: {path}")
    df = pd.read_csv(path)
    if 'Value' in df.columns and df['Value'].dtype == 'object':
        df['Value'] = df['Value'].str.replace(r'\s*\[cite:.*?\]', '', regex=True)
        df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
    logger.info(f"Loaded {len(df)} Washington rate records")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_wa_rates()
    print(f"  {len(df)} records")
    save_diagnostics(df, "wa_rates")
