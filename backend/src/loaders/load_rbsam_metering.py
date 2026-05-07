"""Load RBSA sub-metered end-use data from chunked TXT files."""
import os, json, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_rbsam_metering(directory: str = None, year: int = 1, max_rows: int = 10000) -> pd.DataFrame:
    if directory is None:
        directory = config.RBSAM_Y1_DIR if year == 1 else config.RBSAM_Y2_DIR
    if not os.path.exists(directory):
        raise FileNotFoundError(f"RBSAM directory not found: {directory}")
    manifests = sorted([f for f in os.listdir(directory) if f.endswith('.manifest.json')])
    if manifests:
        with open(os.path.join(directory, manifests[0])) as f:
            chunks = [c['chunk_path'] for c in json.load(f)['chunks']]
        if chunks and os.path.exists(chunks[0]):
            df = pd.read_csv(chunks[0], sep='\t', nrows=max_rows)
            if 'time' in df.columns:
                try: df['time'] = pd.to_datetime(df['time'], format='%d%b%y:%H:%M:%S', errors='coerce')
                except: pass
            logger.info(f"Loaded {len(df)} sample rows from {chunks[0]}")
            return df
    chunks = sorted([f for f in os.listdir(directory) if '.chunk.' in f])
    if chunks:
        df = pd.read_csv(os.path.join(directory, chunks[0]), sep='\t', nrows=max_rows)
        return df
    raise FileNotFoundError(f"No data files in {directory}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for yr in [1, 2]:
        try:
            df = load_rbsam_metering(year=yr, max_rows=5000)
            print(f"  Y{yr}: {len(df)} rows, {len(df.columns)} cols")
            save_diagnostics(df, f"rbsam_y{yr}")
        except FileNotFoundError as e: print(f"  Y{yr}: skipped ({e})")
