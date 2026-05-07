"""Load NW Natural billing data, parse dollar strings and dates."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_billing_data(path: str = None) -> pd.DataFrame:
    path = path or config.BILLING_DATA
    if not os.path.exists(path):
        raise FileNotFoundError(f"Billing data file not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} billing records from {path}")
    if 'utility_usage' in df.columns and df['utility_usage'].dtype == 'object':
        df['utility_usage'] = df['utility_usage'].str.replace('$', '', regex=False).str.replace(',', '', regex=False)
        df['utility_usage'] = pd.to_numeric(df['utility_usage'], errors='coerce')
    if 'GL_revenue_date' in df.columns:
        try:
            df['GL_revenue_date'] = pd.to_datetime(df['GL_revenue_date'], format='%Y%m', errors='coerce')
            df['revenue_year'] = df['GL_revenue_date'].dt.year
            df['revenue_month'] = df['GL_revenue_date'].dt.month
        except: pass
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for label, path in [("small", config.BILLING_DATA_SMALL), ("full", config.BILLING_DATA)]:
        try:
            df = load_billing_data(path)
            print(f"  {label}: {len(df)} records")
            save_diagnostics(df, f"billing_data_{label}")
            break
        except FileNotFoundError as e:
            print(f"  {label}: skipped ({e})")
