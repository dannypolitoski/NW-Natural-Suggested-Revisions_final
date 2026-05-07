"""Fetch Census ACS B25034 via API and build vintage distributions."""
import logging, pandas as pd, requests
from typing import List
from src import config
from src.loaders._helpers import save_diagnostics
from src.loaders.load_service_territory_fips import load_service_territory_fips
logger = logging.getLogger(__name__)

def fetch_census_b25034(fips_codes: List[str], year: int = 2023, acs_type: str = "acs5") -> pd.DataFrame:
    url = f"{config.CENSUS_API_BASE}/{year}/acs/{acs_type}"
    ucgids = ','.join(f"0500000US{f}" for f in fips_codes)
    try:
        r = requests.get(url, params={'get': f'NAME,group({config.CENSUS_B25034_GROUP})', 'ucgid': ucgids}, timeout=30)
        r.raise_for_status(); data = r.json()
        if isinstance(data, list) and len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0])
    except requests.RequestException as e: logger.error(f"Census API error: {e}"); raise
    return pd.DataFrame()

def build_vintage_distribution(b25034: pd.DataFrame) -> pd.DataFrame:
    if b25034.empty: return pd.DataFrame()
    est = [c for c in b25034.columns if c.endswith('E') and c.startswith('B25034_')]
    total = 'B25034_001E'
    if total not in b25034.columns: return b25034
    df = b25034.copy()
    for c in est: df[c] = pd.to_numeric(df[c], errors='coerce')
    for c in est:
        if c != total: df[c.replace('E', '_pct')] = df[c] / df[total].replace(0, float('nan'))
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        fips = [c['fips'] for c in load_service_territory_fips()]
        df = fetch_census_b25034(fips); print(f"  {len(df)} counties")
        save_diagnostics(build_vintage_distribution(df), "census_b25034_api")
    except Exception as e: print(f"  Error: {e}")
