"""Load NW Natural service territory county FIPS codes."""
import os, logging, pandas as pd
from typing import List, Dict
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_service_territory_fips(path: str = None) -> List[Dict]:
    path = path or config.NWN_SERVICE_TERRITORY_CSV
    if not os.path.exists(path): raise FileNotFoundError(f"FIPS file not found: {path}")
    df = pd.read_csv(path, header=None, names=['state', 'county', 'fips'])
    df['fips'] = df['fips'].astype(str).str.zfill(5)
    logger.info(f"Loaded {len(df)} service territory counties")
    return df.to_dict('records')

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    counties = load_service_territory_fips()
    print(f"  {len(counties)} counties")
    for c in counties: print(f"    {c['state']:10s} {c['county']:15s} {c['fips']}")
    save_diagnostics(pd.DataFrame(counties), "service_territory_fips")
