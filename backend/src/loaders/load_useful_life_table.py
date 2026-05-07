"""Build state-specific useful life lookup from ASHRAE data."""
import logging, pandas as pd
from typing import Dict
from src import config
from src.loaders._helpers import save_diagnostics
from src.loaders.load_ashrae_service_life import load_ashrae_service_life
logger = logging.getLogger(__name__)

def build_useful_life_table(ashrae_data: pd.DataFrame = None) -> Dict[str, Dict[str, int]]:
    if ashrae_data is None:
        try: ashrae_data = load_ashrae_service_life()
        except: ashrae_data = pd.DataFrame()
    if ashrae_data.empty:
        return {'OR': dict(config.USEFUL_LIFE), 'WA': dict(config.USEFUL_LIFE)}
    life_col = next((c for c in ['Median Service Life', 'median_service_life', 'Service Life'] if c in ashrae_data.columns), None)
    equip_col = next((c for c in ['Equipment Type', 'equipment_category', 'Category'] if c in ashrae_data.columns), None)
    if not life_col or not equip_col:
        return {'OR': dict(config.USEFUL_LIFE), 'WA': dict(config.USEFUL_LIFE)}
    table = {}
    for state in ['OR', 'WA']:
        sd = ashrae_data[ashrae_data['state'] == state]
        d = dict(config.USEFUL_LIFE)
        for _, r in sd.iterrows():
            if pd.notna(r[equip_col]) and pd.notna(r[life_col]):
                d[str(r[equip_col])] = int(r[life_col])
        table[state] = d
    return table

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    t = build_useful_life_table()
    for s, d in t.items(): print(f"  {s}: {len(d)} entries")
    rows = [{'state': s, 'cat': c, 'life': l} for s, d in t.items() for c, l in d.items()]
    save_diagnostics(pd.DataFrame(rows), "useful_life_table")
