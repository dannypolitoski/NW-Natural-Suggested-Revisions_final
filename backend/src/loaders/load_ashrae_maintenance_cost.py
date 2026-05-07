"""Load ASHRAE maintenance cost data for OR and WA."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_ashrae_maintenance_cost(or_path: str = None, wa_path: str = None) -> pd.DataFrame:
    or_path = or_path or config.ASHRAE_OR_MAINTENANCE_COST
    wa_path = wa_path or config.ASHRAE_WA_MAINTENANCE_COST
    dfs = []
    for label, path in [("OR", or_path), ("WA", wa_path)]:
        if os.path.exists(path):
            try:
                df = pd.read_excel(path); df['state'] = label; dfs.append(df)
            except Exception as e: logger.warning(f"Error reading {label}: {e}")
        else: logger.warning(f"{label} file not found: {path}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try: df = load_ashrae_maintenance_cost(); print(f"  {len(df)} records"); save_diagnostics(df, "ashrae_maintenance_cost")
    except Exception as e: print(f"  Error: {e}")
