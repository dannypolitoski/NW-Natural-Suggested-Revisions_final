"""Load WACOG history for OR or WA."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_wacog_history(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"WACOG history file not found: {path}")
    df = pd.read_csv(path)
    if 'Effective Date' in df.columns:
        df['Effective Date'] = pd.to_datetime(df['Effective Date'], errors='coerce')
    if 'Rate per Therm' in df.columns:
        df['Rate per Therm'] = pd.to_numeric(df['Rate per Therm'], errors='coerce')
    logger.info(f"Loaded {len(df)} WACOG records from {path}")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for label, path in [("OR", config.OR_WACOG_HISTORY), ("WA", config.WA_WACOG_HISTORY)]:
        try:
            df = load_wacog_history(path)
            print(f"  {label}: {len(df)} records")
            save_diagnostics(df, f"wacog_{label.lower()}")
        except FileNotFoundError as e:
            print(f"  {label}: skipped ({e})")
