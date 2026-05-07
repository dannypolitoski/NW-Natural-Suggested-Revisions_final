"""Load NW Energy Proxies compact parameter set."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_nw_energy_proxies(path: str = None) -> pd.DataFrame:
    path = path or config.NW_ENERGY_PROXIES_CSV
    if not os.path.exists(path): raise FileNotFoundError(f"NW Energy Proxies not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} proxy records")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_nw_energy_proxies()
    print(f"  {len(df)} records")
    env = df[df['Category']=='Envelope']
    if not env.empty:
        for _, r in env.iterrows(): print(f"    {r['SubCategory']}: U={r['Value']}")
    save_diagnostics(df, "nw_energy_proxies")
