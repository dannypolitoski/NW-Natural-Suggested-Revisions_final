"""Load NW Natural IRP 10-Year Load Decay Forecast."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_load_decay_forecast(path: str = None) -> pd.DataFrame:
    path = path or config.IRP_LOAD_DECAY_FORECAST
    if not os.path.exists(path): raise FileNotFoundError(f"Load decay forecast not found: {path}")
    df = pd.read_csv(path)
    for col in ['Annual_Decay_Rate', 'Cumulative_Change_vs_2025']:
        if col in df.columns and df[col].dtype == 'object':
            df[col] = df[col].str.replace('%', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce') / 100.0
    logger.info(f"Loaded {len(df)} load decay forecast records")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_load_decay_forecast()
    print(f"  {len(df)} years: {df['Year'].min()}-{df['Year'].max()}, UPC: {df['Avg_Res_UPC_Therms'].min():.1f}-{df['Avg_Res_UPC_Therms'].max():.1f}")
    save_diagnostics(df, "load_decay_forecast")
