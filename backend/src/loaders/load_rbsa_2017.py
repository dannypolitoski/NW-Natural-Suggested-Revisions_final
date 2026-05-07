"""Load 2017 RBSA-II SiteDetail for temporal comparison."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_rbsa_2017_site_detail(path: str = None) -> pd.DataFrame:
    if path is None: path = os.path.join(config.RBSA_2017_DIR, "SiteDetail.csv")
    if not os.path.exists(path): raise FileNotFoundError(f"2017 RBSA not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} 2017 RBSA records")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try: df = load_rbsa_2017_site_detail(); print(f"  {len(df)} records"); save_diagnostics(df, "rbsa_2017")
    except FileNotFoundError as e: print(f"  Skipped: {e}")
