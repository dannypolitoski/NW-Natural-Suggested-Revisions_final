"""Load and filter NW Natural segment data to residential customers."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def load_segment_data(path: str = None) -> pd.DataFrame:
    path = path or config.SEGMENT_DATA
    if not os.path.exists(path):
        raise FileNotFoundError(f"Segment data file not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} segment records from {path}")
    
    # Include all residential segments: SF, MF, small MF, mobile, and unassigned
    residential_segments = ['RESSF', 'RESMF', 'RSMFF', 'MOBILE', 'UNASS']
    df = df[df['segment'].isin(residential_segments)].copy()
    
    # Normalize: map RSMFF → RESMF (small multi-family is still multi-family)
    df.loc[df['segment'] == 'RSMFF', 'segment'] = 'RESMF'
    # Map UNASS → RESSF (most unassigned are single-family based on subseg analysis)
    df.loc[df['segment'] == 'UNASS', 'segment'] = 'RESSF'
    
    # Flag new construction from mktseg column
    if 'mktseg' in df.columns:
        df['is_new_construction'] = df['mktseg'].isin(['RES-SFNC', 'RES-MFNC'])
        nc_count = df['is_new_construction'].sum()
        logger.info(f"New construction flag: {nc_count:,} of {len(df):,} ({nc_count/len(df)*100:.1f}%)")
    
    logger.info(f"Filtered to {len(df)} residential segment records")
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_segment_data()
    print(f"  {len(df)} records, segments: {df['segment'].value_counts().to_dict()}")
    save_diagnostics(df, "segment_data")
