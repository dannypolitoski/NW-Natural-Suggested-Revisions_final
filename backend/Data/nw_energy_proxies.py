import pandas as pd

def get_performance_proxies():
    # Simplified lookup table based on our CSV
    return {
        'pre_1950':   {'u': 0.250, 'ach50': 14.0},
        '1951_1980':  {'u': 0.081, 'ach50': 10.5},
        '1981_2010':  {'u': 0.056, 'ach50': 6.5},
        '2011_2026':  {'u': 0.038, 'ach50': 3.5}
    }

def run_home_scenario(site_data, heating_type='gas', weatherized=False):
    """
    heating_type: 'gas' or 'heat_pump'
    weatherized: bool (if True, applies Retrofit Targets to older homes)
    """
    proxies = get_performance_proxies()
    v = site_data['vintage']
    v_key = 'pre_1950' if v < 1951 else ('1951_1980' if v < 1981 else ('1981_2010' if v < 2011 else '2011_2026'))
    
    # 1. Determine Physics (Apply Weatherization if toggled)
    wall_u = proxies[v_key]['u']
    ach50 = proxies[v_key]['ach50']
    
    if weatherized and v < 2011:
        wall_u = 0.060 # Improved to R-19 equivalent
        ach50 = 5.0    # Professional air sealing target
    
    # 2. Calculate UA
    net_wall_area = site_data['wall_area'] - site_data['window_area']
    inf_ua = site_data['volume'] * (ach50 / 20.0) * 0.018
    total_ua = (net_wall_area * wall_u + site_data['window_area'] * 0.32 + inf_ua)
    
    if site_data.get('is_gorge', False):
        total_ua *= 1.15

    # 3. Efficiency Logic
    if heating_type == 'gas':
        eff_label = "95% AFUE Gas Furnace"
        fuel = "Natural Gas"
    else:
        eff_label = "8.8 HSPF2 Air-Source Heat Pump"
        fuel = "Electricity"

    return {
        'scenario': f"{v_key.replace('_', ' ')} | {heating_type} | Weatherized: {weatherized}",
        'total_ua': round(total_ua, 2),
        'system': eff_label,
        'fuel_type': fuel
    }

# Example: Run two scenarios on the same 1970s house
site = {'vintage': 1972, 'volume': 15000, 'wall_area': 1600, 'window_area': 200, 'is_gorge': False}

gas_baseline = run_home_scenario(site, heating_type='gas', weatherized=False)
hp_retrofit = run_home_scenario(site, heating_type='heat_pump', weatherized=True)

print(f"Baseline (Gas): UA = {gas_baseline['total_ua']}")
print(f"Retrofit (HP):  UA = {hp_retrofit['total_ua']} (Reduction: {round(gas_baseline['total_ua'] - hp_retrofit['total_ua'])} Btu/hr-F)")