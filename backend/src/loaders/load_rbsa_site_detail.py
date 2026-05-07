"""Load RBSA 2022 SiteDetail, filter to NW Natural service territory."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_rbsa_site_detail(path: str = None) -> pd.DataFrame:
    path = path or config.RBSA_2022_SITE_DETAIL
    if not os.path.exists(path):
        raise FileNotFoundError(f"RBSA SiteDetail not found: {path}")
    df = pd.read_csv(path)
    mask = pd.Series(False, index=df.index)
    if 'NWN_SF_StrataVar' in df.columns: mask |= (df['NWN_SF_StrataVar'] == 'NWN')
    if 'Gas_Utility' in df.columns: mask |= (df['Gas_Utility'] == 'NW NATURAL GAS')
    df = df[mask].copy()
    logger.info(f"Filtered to {len(df)} NWN sites")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        df = load_rbsa_site_detail()
        print(f"  {len(df)} NWN sites")
        save_diagnostics(df, "rbsa_site_detail")
    except FileNotFoundError as e: print(f"  Skipped: {e}")
