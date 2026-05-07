"""Load NOAA 30-year climate normals and compute weather adjustment."""
import os, logging, numpy as np, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_noaa_daily_normals(directory: str = None, station: str = "KPDX") -> pd.DataFrame:
    directory = directory or config.NOAA_NORMALS_DIR
    fp = os.path.join(directory, f"{station}_daily_normals.csv")
    if not os.path.exists(fp): raise FileNotFoundError(f"NOAA daily normals not found: {fp}")
    df = pd.read_csv(fp).replace(-7777, np.nan)
    logger.info(f"Loaded {len(df)} daily normals for {station}")
    return df

def load_noaa_monthly_normals(directory: str = None, station: str = "KPDX") -> pd.DataFrame:
    directory = directory or config.NOAA_NORMALS_DIR
    fp = os.path.join(directory, f"{station}_monthly_normals.csv")
    if not os.path.exists(fp): raise FileNotFoundError(f"NOAA monthly normals not found: {fp}")
    df = pd.read_csv(fp).replace(-7777, np.nan)
    logger.info(f"Loaded {len(df)} monthly normals for {station}")
    return df

def compute_weather_adjustment(actual_hdd: float, normal_hdd: float) -> float:
    if pd.isna(normal_hdd) or normal_hdd == 0: return 1.0
    return actual_hdd / normal_hdd

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for s in list(config.ICAO_TO_GHCND.keys()):
        try:
            d = load_noaa_daily_normals(station=s); m = load_noaa_monthly_normals(station=s)
            print(f"  {s}: {len(d)} daily, {len(m)} monthly")
            if s == 'KPDX': save_diagnostics(d, f"noaa_daily_{s}"); save_diagnostics(m, f"noaa_monthly_{s}")
        except FileNotFoundError: print(f"  {s}: not found")
