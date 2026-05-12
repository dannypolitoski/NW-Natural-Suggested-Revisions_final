import pandas as pd

def calculate_site_load(site_data, proxy_df):
    """
    site_data: dict containing 'vintage', 'is_gorge_region', 'pipe_insulation'
    proxy_df: The loaded CSV from above
    """
    # 1. Base Loads
    cooking = proxy_df.query("SubCategory == 'Cooking'")['Value'].values[0]
    
    # 2. Standby Loss based on Vintage
    if site_data['vintage'] < 1991:
        base_standby = proxy_df.query("SubCategory == 'WH_Pre_1990'")['Value'].values[0]
    elif site_data['vintage'] < 2004:
        base_standby = proxy_df.query("SubCategory == 'WH_1991_2003'")['Value'].values[0]
    else:
        base_standby = proxy_df.query("SubCategory == 'WH_2015_Current'")['Value'].values[0]

    # 3. Apply Multipliers
    # Plumbing Penalty (Thermosiphon)
    p_penalty = 1.0
    if not site_data.get('pipe_insulation', True):
        p_penalty = proxy_df.query("Parameter == 'Thermosiphon_Penalty'")['Value'].values[0]
    
    # Gorge Effect (Wind/Cold)
    climate_mult = 1.0
    if site_data.get('is_gorge_region', False):
        climate_mult = proxy_df.query("Parameter == 'Gorge_Effect_Wind'")['Value'].values[0]

    # 4. Final Calculation
    adjusted_standby = base_standby * p_penalty * climate_mult
    
    # Pilot (only if pre-2015)
    pilot = 0
    if site_data['vintage'] < 2015:
        pilot = proxy_df.query("SubCategory == 'Water_Heater' & Category == 'Pilot'")['Value'].values[0]
        
    total_baseload = cooking + adjusted_standby + pilot
    return total_baseload

# Example Site: 1985 home in Troutdale (Gorge) with no pipe insulation
test_site = {'vintage': 1985, 'is_gorge_region': True, 'pipe_insulation': False}
print(f"Total Baseload: {calculate_site_load(test_site, df):.1f} Therms/yr")