"""Build weighted distributions from RBSA site detail + HVAC + water heater."""
import logging, pandas as pd, numpy as np
from typing import Dict
from src.loaders._helpers import save_diagnostics
logger = logging.getLogger(__name__)

def build_rbsa_distributions(site_detail: pd.DataFrame, hvac: pd.DataFrame, water_heater: pd.DataFrame) -> Dict:
    d: Dict = {}
    w = 'Site_Case_Weight'
    if 'Building_Type' in site_detail.columns and 'Conditioned_Area' in site_detail.columns:
        sqft = {}
        for bt, g in site_detail.groupby('Building_Type'):
            wt = g[w].fillna(1) if w in g.columns else pd.Series(1, index=g.index)
            sqft[bt] = np.average(g['Conditioned_Area'].fillna(0), weights=wt)
        d['sqft_by_type'] = sqft
    if 'Fuel' in hvac.columns:
        d['hvac_fuel_mix'] = hvac['Fuel'].value_counts(normalize=True).to_dict()
    if 'Fuel' in hvac.columns and 'COP_or_AFUE' in hvac.columns:
        d['hvac_eff_by_fuel'] = hvac.groupby('Fuel')['COP_or_AFUE'].mean().to_dict()
    if 'Fuel_Type' in water_heater.columns and 'Water_Heater_Efficiency' in water_heater.columns:
        d['wh_eff_by_fuel'] = water_heater.groupby('Fuel_Type')['Water_Heater_Efficiency'].mean().to_dict()
    return d

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from src.loaders.load_rbsa_site_detail import load_rbsa_site_detail
    from src.loaders.load_rbsa_hvac import load_rbsa_hvac
    from src.loaders.load_rbsa_water_heater import load_rbsa_water_heater
    try:
        dist = build_rbsa_distributions(load_rbsa_site_detail(), load_rbsa_hvac(), load_rbsa_water_heater())
        for k, v in dist.items(): print(f"  {k}: {v}")
        rows = [{'metric': k, 'cat': c, 'val': v} for k, d in dist.items() if isinstance(d, dict) for c, v in d.items()]
        if rows: save_diagnostics(pd.DataFrame(rows), "rbsa_distributions")
    except FileNotFoundError as e: print(f"  Skipped: {e}")
