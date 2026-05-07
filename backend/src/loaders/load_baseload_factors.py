"""Load baseload consumption factors and calculate site baseload."""
import os, logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def load_baseload_factors(path: str = None) -> pd.DataFrame:
    path = path or config.BASELOAD_FACTORS_CSV
    if not os.path.exists(path): raise FileNotFoundError(f"Baseload factors not found: {path}")
    df = pd.read_csv(path)
    logger.info(f"Loaded {len(df)} baseload factor records")
    return df

def _get(factors, cat, sub, param):
    m = factors[(factors['Category']==cat)&(factors['SubCategory']==sub)&(factors['Parameter']==param)]
    return float(m.iloc[0]['Value']) if not m.empty else 0.0

def calculate_site_baseload(vintage: int, is_gorge: bool, has_pipe_insulation: bool, factors: pd.DataFrame = None) -> float:
    if factors is None: factors = load_baseload_factors()
    if factors.empty: return 100.0
    bl = _get(factors,'Baseload','Cooking','Annual_Consumption') + _get(factors,'Baseload','Drying','Annual_Consumption') + _get(factors,'Baseload','Fireplace','Annual_Consumption')
    if vintage < 2015: bl += (_get(factors,'Pilot','Fireplace','Annual_Consumption') + _get(factors,'Pilot','Water_Heater','Annual_Consumption')) / 2
    if vintage < 1990: bl += _get(factors,'Standby','WH_Pre_1990','Base_Loss')
    elif vintage < 2004: bl += _get(factors,'Standby','WH_1991_2003','Base_Loss')
    elif vintage < 2015: bl += _get(factors,'Standby','WH_2004_2014','Base_Loss')
    else: bl += _get(factors,'Standby','WH_2015_Current','Base_Loss')
    if is_gorge: bl *= _get(factors,'Adjustment','Climate','Gorge_Effect_Wind') or 1.15
    if not has_pipe_insulation: bl *= _get(factors,'Adjustment','Plumbing','Thermosiphon_Penalty') or 1.2
    return bl

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    df = load_baseload_factors()
    print(f"  {len(df)} factors")
    save_diagnostics(df, "baseload_factors")
    for v in [1985, 2000, 2012, 2020]:
        bl = calculate_site_baseload(v, False, True, df)
        print(f"  vintage={v}: {bl:.1f} therms/yr")
