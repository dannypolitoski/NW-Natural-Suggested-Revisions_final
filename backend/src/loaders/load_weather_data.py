"""Load NW Natural daily weather data (CalDay or GasDay)."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_weather_data(path: str = None) -> pd.DataFrame:
    path = path or config.WEATHER_CALDAY
    if not os.path.exists(path):
        raise FileNotFoundError(f"Weather data file not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} weather records from {path}")
    for c in df.columns:
        if 'date' in c.lower():
            try: df[c] = pd.to_datetime(df[c])
            except: pass
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for label, path in [("CalDay", config.WEATHER_CALDAY), ("GasDay", config.WEATHER_GASDAY)]:
        try:
            df = load_weather_data(path)
            print(f"  {label}: {len(df)} records")
            save_diagnostics(df, f"weather_{label.lower()}")
        except FileNotFoundError as e:
            print(f"  {label}: skipped ({e})")
