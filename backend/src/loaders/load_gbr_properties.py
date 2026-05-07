"""Fetch Green Building Registry properties via API."""
import os, logging, pandas as pd, requests
from typing import List
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def fetch_gbr_properties(zip_codes: List[str], api_key: str = None) -> pd.DataFrame:
    api_key = api_key or os.environ.get(config.GBR_API_KEY_ENV_VAR, '')
    if not api_key: logger.warning("No GBR_API_KEY set"); return pd.DataFrame()
    props = []
    for z in zip_codes:
        try:
            r = requests.get(f"{config.GBR_API_BASE_URL}/properties", params={'zip_code': z, 'api_key': api_key}, timeout=10)
            r.raise_for_status(); props.extend(r.json().get('results', []))
        except requests.RequestException as e: logger.warning(f"GBR error for {z}: {e}")
    return pd.DataFrame(props) if props else pd.DataFrame()

def build_gbr_building_profiles(gbr_data: pd.DataFrame) -> pd.DataFrame:
    return gbr_data.copy() if not gbr_data.empty else pd.DataFrame()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if not os.environ.get(config.GBR_API_KEY_ENV_VAR): print("  No GBR_API_KEY — skipping")
    else:
        df = fetch_gbr_properties(['97201', '97209'])
        if not df.empty: save_diagnostics(df, "gbr_properties")
