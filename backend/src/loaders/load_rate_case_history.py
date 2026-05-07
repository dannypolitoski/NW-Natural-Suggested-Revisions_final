"""Load rate case history for OR or WA."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_rate_case_history(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Rate case history file not found: {path}")
    df = pd.read_csv(path)
    for col in ['Date Applied', 'Date Effective']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    for col in ['Change Percent', 'Granted Percent']:
        if col in df.columns and df[col].dtype == 'object':
            df[col] = df[col].str.replace('%', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce') / 100.0
    logger.info(f"Loaded {len(df)} rate case records from {path}")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for label, path in [("OR", config.OR_RATE_CASE_HISTORY), ("WA", config.WA_RATE_CASE_HISTORY)]:
        try:
            df = load_rate_case_history(path)
            print(f"  {label}: {len(df)} rate cases")
            save_diagnostics(df, f"rate_cases_{label.lower()}")
        except FileNotFoundError as e:
            print(f"  {label}: skipped ({e})")
