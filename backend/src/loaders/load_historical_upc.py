"""Load historical UPC from reconstructed and simulated files."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_historical_upc(reconstructed_path: str = None, simulated_path: str = None) -> pd.DataFrame:
    reconstructed_path = reconstructed_path or config.LOAD_DECAY_RECONSTRUCTED
    simulated_path = simulated_path or config.LOAD_DECAY_SIMULATED
    dfs = []
    if os.path.exists(reconstructed_path):
        try:
            df = pd.read_csv(reconstructed_path)
            col_map = {c: 'year' for c in df.columns if 'year' in c.lower()}
            col_map.update({c: 'upc_therms' for c in df.columns if 'therms' in c.lower() or 'upc' in c.lower()})
            df = df.rename(columns=col_map); df['source'] = 'reconstructed'; dfs.append(df)
        except Exception as e: logger.warning(f"Error reading reconstructed: {e}")
    if os.path.exists(simulated_path):
        try:
            df = pd.read_csv(simulated_path, sep='\t')
            col_map = {c: 'year' for c in df.columns if 'year' in c.lower()}
            col_map.update({c: 'upc_therms' for c in df.columns if 'therms' in c.lower()})
            df = df.rename(columns=col_map); df['source'] = 'simulated'; dfs.append(df)
        except Exception as e: logger.warning(f"Error reading simulated: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_historical_upc()
    print(f"  {len(df)} records")
    save_diagnostics(df, "historical_upc")
