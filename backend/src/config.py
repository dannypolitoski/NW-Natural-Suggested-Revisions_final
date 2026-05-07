"""
Configuration module for NW Natural End-Use Forecasting Model.

Defines all static configuration including:
- End-use category mappings
- Equipment efficiency defaults
- Equipment useful life assumptions
- Weather station assignments
- File paths for all data sources
- API constants
- Simulation parameters
"""

import os

# ============================================================================
# END-USE CATEGORY MAPPINGS
# ============================================================================

# Maps equipment_type_code to end-use categories
# Based on equipment_class and equipment_type_code from equipment_codes.csv
END_USE_MAP = {
    # Space Heating (HEAT class) — from equipment_codes.csv
    "HEAT": "space_heating",
    "FURN": "space_heating",
    "BOIL": "space_heating",
    "HPMP": "space_heating",
    "RFAU": "space_heating",      # Forced Air Furnace
    "RFLR": "space_heating",      # Floor Furnace
    "RCHT": "space_heating",      # Circulating Heater <20k BTU
    "RCHTH": "space_heating",     # Circulating Heater >=20K BTU
    "RWLF": "space_heating",      # Wall Furnace <20K BTU
    "RWLFH": "space_heating",     # Wall Furnace >=20K BTU
    "RHWH": "space_heating",      # Residential Heating (Hot Water)
    "RBWA": "space_heating",      # Residential Water Boiler (heating)
    "RVHT": "space_heating",      # Ventless Heating Appliance
    "RCHP": "space_heating",      # Res Combined Heat & Power
    "CONVB": "space_heating",     # Conversion Burner
    "GELP": "space_heating",      # GELP (heating)
    "C6FO": "space_heating",      # Commercial Forced Air Heating
    "C6UN": "space_heating",      # Commercial Unit Heating
    "C6RO": "space_heating",      # Commercial Roof Top Heating
    "C6IN": "space_heating",      # Commercial Radiant Heating
    "C6MA": "space_heating",      # Make Up Air
    "C6BO": "space_heating",      # Boiler Heating (commercial)
    "SPHT": "space_heating",      # Space Heater
    "PTHTR": "space_heating",     # Patio Heater
    
    # Water Heating (WTR class)
    "WTR": "water_heating",
    "WTRH": "water_heating",
    "WTRB": "water_heating",
    "RAWH": "water_heating",      # Residential Water Heating
    "RWHI": "water_heating",      # Residential Tankless Water Heater
    "RVWH": "water_heating",      # Ventless Water Heater
    "CAWH": "water_heating",      # Commercial Water Heating
    "C5WA": "water_heating",      # Commercial Water Heating
    
    # Cooking (RRGE/09CR codes)
    "RRGE": "cooking",            # Residential Range
    "09CR": "cooking",            # Range
    "COOK": "cooking",
    "C4RG": "cooking",            # Commercial Cooking Range
    "C4OV": "cooking",            # Commercial Cooking Oven
    "C4BR": "cooking",            # Commercial Cooking Broiler
    "C4GR": "cooking",            # Commercial Cooking Griddle
    "C4FR": "cooking",            # Commercial Cooking Fryer
    "C4WO": "cooking",            # Commercial Cooking Woks
    "C4MI": "cooking",            # Commercial Cooking Misc
    "CCKG": "cooking",            # Commercial Cooking Gas
    
    # Clothes Drying (RDRY/C9DR codes)
    "RDRY": "clothes_drying",     # Residential Dryer
    "C9DR": "clothes_drying",     # Commercial Dryer
    "DRYR": "clothes_drying",
    "P9DR": "clothes_drying",     # Process Dryers
    
    # Fireplaces/Decorative (FRPL class)
    "FRPL": "fireplace",
    "FIRE": "fireplace",
    "RFPL": "fireplace",          # Fire Place <20K BTU
    "RFPLH": "fireplace",         # Fire Place >=20K BTU
    "RGLG": "fireplace",          # Gas Log
    "RFPIT": "fireplace",         # Fire Pit
    "CFPIT": "fireplace",         # Commercial Fire Pit
    
    # Other/Miscellaneous
    "OTHR": "other",
    "MISC": "other",
    "RMISC": "other",             # Residential Misc
    "RBBQ": "other",              # BBQ
    "RGEN": "other",              # Residential Generator
    "RLTR": "other",              # Residential Log Lighter
    "POOL": "other",              # Pool Heater
    "SPA": "other",               # Spa/Hot Tub
    "HSLN": "other",              # Housepipe
    "ACOND": "other",             # Air Conditioner
    "MGLT": "other",              # Gas Light (Metered)
    "NGLT": "other",              # Gas Light (Non-Metered)
    "RGLT": "other",              # Gas Light
    "NGV": "other",               # NGV Vehicle
    "RWASH": "other",             # Residential Washing Machine
    "RGBHP": "other",             # Gas Backup to Heat Pump
    "CMSC": "other",              # Commercial Misc
    "C8MI": "other",              # Commercial Equip Misc
    "C8GE": "other",              # Standby Generator
    "C8CO": "other",              # Coffee Bean Roaster
    "8CBR": "other",              # Misc Coffee Bean Roaster
    "C8BR": "other",              # Brew Tanks
    "C8TO": "other",              # Torch
    "C8PA": "other",              # Part Cleaners
    "C6PI": "other",              # Oil Boil Pilot
    "C6PA": "other",              # Paint Booths
    "C9GE": "other",              # Engines-Generator
    "P8KI": "other",              # Kilns
    "P8OV": "other",              # Ovens (process)
    "P8MI": "other",              # Process Misc
    "P8BO": "other",              # Process Boiler
    "RVFA": "other",              # Res Vehicle Fuel Appliance CNG
    "CVFA": "other",              # Com Vehicle Fuel Appliance CNG
    "IVFA": "other",              # Ind Vehicle Fuel Appliance CNG
    "4OTO": "other",              # Other
    "6FAF": "other",              # Other
    "06DL": "other",              # Other
    "02FG": "other",              # Other
    "02FS": "other",              # Other
}

# ============================================================================
# EQUIPMENT EFFICIENCY DEFAULTS
# ============================================================================

# Default efficiency by end-use category (as decimal, e.g., 0.85 = 85%)
# Used when equipment-specific efficiency data is unavailable
DEFAULT_EFFICIENCY = {
    "space_heating": 0.80,      # Pre-2010 furnace baseline
    "water_heating": 0.60,      # Pre-2010 water heater baseline
    "cooking": 0.75,            # Gas cooking efficiency
    "clothes_drying": 0.65,     # Gas dryer efficiency
    "fireplace": 0.10,          # Fireplace (mostly heat loss)
    "other": 0.70,              # Generic appliance
}

# ============================================================================
# EQUIPMENT USEFUL LIFE (YEARS)
# ============================================================================

# Default useful life by end-use category (years)
# Used when ASHRAE data is unavailable; replaced by ASHRAE service life when available
USEFUL_LIFE = {
    "space_heating": 20,        # Furnace/boiler typical life
    "water_heating": 13,        # Water heater typical life
    "cooking": 15,              # Gas range typical life
    "clothes_drying": 13,       # Gas dryer typical life
    "fireplace": 30,            # Fireplace (long-lived)
    "other": 15,                # Generic appliance
}

# ============================================================================
# WEIBULL SURVIVAL MODEL PARAMETERS
# ============================================================================

# Shape parameter (beta) for Weibull survival function by end-use
# Controls failure rate distribution: higher beta = sharper peak, lower beta = gradual decline
WEIBULL_BETA = {
    "space_heating": 3.0,       # HVAC: concentrated replacement window
    "water_heating": 3.0,       # Water heater: concentrated replacement window
    "cooking": 2.5,             # Appliances: more gradual replacement
    "clothes_drying": 2.5,      # Appliances: more gradual replacement
    "fireplace": 2.0,           # Long-lived, gradual failure
    "other": 2.5,               # Generic appliance
}

# ============================================================================
# DISTRICT TO WEATHER STATION MAPPING
# ============================================================================

# Maps district_code_IRP to weather station SiteId
# Weather stations: KPDX, KEUG, KSLE, KAST, KDLS, KOTH, KONP, KCVO, KHIO, KTTD, KVUO
DISTRICT_WEATHER_MAP = {
    # Oregon districts
    "MULT": "KPDX",     # Multnomah -> Portland
    "WASH": "KPDX",     # Washington -> Portland
    "CLAC": "KPDX",     # Clackamas -> Portland
    "YAMI": "KPDX",     # Yamhill -> Portland
    "POLK": "KSLE",     # Polk -> Salem
    "MARI": "KSLE",     # Marion -> Salem
    "LINN": "KCVO",     # Linn -> Corvallis
    "LANE": "KEUG",     # Lane -> Eugene
    "DOUG": "KEUG",     # Douglas -> Eugene
    "COOS": "KOTH",     # Coos -> North Bend
    "LINC": "KONP",     # Lincoln -> Newport
    "BENT": "KPDX",     # Benton -> Portland (proxy)
    "CLAT": "KAST",     # Clatsop -> Astoria
    "COLU": "KAST",     # Columbia -> Astoria
    "PORC": "KPDX",     # Portland Commercial -> Portland
    
    # Washington districts
    "CLAR": "KVUO",     # Clark -> Vancouver
    "SKAM": "KDLS",     # Skamania -> The Dalles (proxy)
    "KLIC": "KDLS",     # Klickitat -> The Dalles
}

# ============================================================================
# NW NATURAL-SUPPLIED DATA (PROPRIETARY/BLINDED)
# ============================================================================

NWN_DATA_DIR = "Data/NWNatural Data"
PREMISE_DATA = os.path.join(NWN_DATA_DIR, "premise_data_blinded.csv")
EQUIPMENT_DATA = os.path.join(NWN_DATA_DIR, "equipment_data_blinded.csv")
EQUIPMENT_CODES = os.path.join(NWN_DATA_DIR, "equipment_codes.csv")
SEGMENT_DATA = os.path.join(NWN_DATA_DIR, "segment_data_blinded.csv")
BILLING_DATA = os.path.join(NWN_DATA_DIR, "billing_data_blinded.csv")
BILLING_DATA_SMALL = os.path.join(NWN_DATA_DIR, "small_billing_data_blinded.csv")
WEATHER_CALDAY = os.path.join(NWN_DATA_DIR, "DailyCalDay1985_Mar2025.csv")
WEATHER_GASDAY = os.path.join(NWN_DATA_DIR, "DailyGasDay2008_Mar2025.csv")
WATER_TEMP = os.path.join(NWN_DATA_DIR, "BullRunWaterTemperature.csv")
PORTLAND_SNOW = os.path.join(NWN_DATA_DIR, "Portland_snow.csv")

# ============================================================================
# TARIFF AND RATE DATA (TEAM-CREATED)
# ============================================================================

DATA_DIR = "Data"
OR_RATE_CASE_HISTORY = os.path.join(DATA_DIR, "or_rate_case_history.csv")
OR_RATES = os.path.join(DATA_DIR, "or_rates_oct_2025.csv")
OR_WACOG_HISTORY = os.path.join(DATA_DIR, "or_wacog_history.csv")
WA_RATE_CASE_HISTORY = os.path.join(DATA_DIR, "wa_rate_case_history.csv")
WA_RATES = os.path.join(DATA_DIR, "wa_rates_nov_2025.csv")
WA_WACOG_HISTORY = os.path.join(DATA_DIR, "wa_wacog_history.csv")

# ============================================================================
# RBSA 2022 DATASET (NEEA RESIDENTIAL BUILDING STOCK ASSESSMENT)
# ============================================================================

RBSA_2022_DIR = os.path.join(DATA_DIR, "2022 RBSA Datasets")
RBSA_2022_SITE_DETAIL = os.path.join(RBSA_2022_DIR, "SiteDetail.csv")
RBSA_2022_HVAC = os.path.join(RBSA_2022_DIR, "Mechanical_HeatingAndCooling.csv")
RBSA_2022_WATER_HEATER = os.path.join(RBSA_2022_DIR, "Mechanical_WaterHeater.csv")
RBSA_2022_STOVE_OVEN = os.path.join(RBSA_2022_DIR, "Appliance_Stove_Oven.csv")
RBSA_2022_LAUNDRY = os.path.join(RBSA_2022_DIR, "Appliance_Laundry.csv")
RBSA_2022_BUILDING_SHELL = os.path.join(RBSA_2022_DIR, "Building_Shell_One_Line.csv")

# ============================================================================
# ASHRAE EQUIPMENT DATA (SERVICE LIFE AND MAINTENANCE COST)
# ============================================================================

ASHRAE_DIR = os.path.join(DATA_DIR, "ashrae")
ASHRAE_OR_SERVICE_LIFE = os.path.join(ASHRAE_DIR, "OR-ASHRAE_Service_Life_Data.xls")
ASHRAE_WA_SERVICE_LIFE = os.path.join(ASHRAE_DIR, "WA-ASHRAE_Service_Life_Data.xls")
ASHRAE_OR_MAINTENANCE_COST = os.path.join(ASHRAE_DIR, "OR-ASHRAE_Maintenance_Cost_Data.xls")
ASHRAE_WA_MAINTENANCE_COST = os.path.join(ASHRAE_DIR, "WA-ASHRAE_Maintenance_Cost_Data.xls")

# ============================================================================
# NW NATURAL IRP LOAD DECAY FORECAST AND COMPANION DATA
# ============================================================================

IRP_LOAD_DECAY_FORECAST = os.path.join(DATA_DIR, "10-Year Load Decay Forecast (2025\u20132035).csv")
LOAD_DECAY_DESCRIPTION = os.path.join(DATA_DIR, "prior load decay data description.txt")
LOAD_DECAY_RECONSTRUCTED = os.path.join(DATA_DIR, "prior load decay data reconstructed.txt")
LOAD_DECAY_SIMULATED = os.path.join(DATA_DIR, "prior load decay data simulated.txt")

# ============================================================================
# BASELOAD CONSUMPTION FACTORS
# ============================================================================

BASELOAD_FACTORS_CSV = os.path.join(DATA_DIR, "Baseload Consumption Factors.csv")
BASELOAD_FACTORS_PY = os.path.join(DATA_DIR, "Baseload Consumption factors.py")
BASELOAD_FACTORS_EXPLANATION = os.path.join(DATA_DIR, "Baseload Consumption factors explanation.txt")

# ============================================================================
# NW ENERGY PROXIES (COMPACT PARAMETER SET)
# ============================================================================

NW_ENERGY_PROXIES_CSV = os.path.join(DATA_DIR, "nw_energy_proxies.csv")
NW_ENERGY_PROXIES_PY = os.path.join(DATA_DIR, "nw_energy_proxies.py")
NW_ENERGY_PROXIES_EXPLANATION = os.path.join(DATA_DIR, "nw_energy_proxies explanation.txt")

# ============================================================================
# IRP CONTEXT AND EQUIPMENT LIFE DOCUMENTATION
# ============================================================================

IRP_CONTEXT = os.path.join(DATA_DIR, "Integrated Resource Plan (IRP),.txt")
EQUIPMENT_LIFE_MATH = os.path.join(DATA_DIR, "equipment life math.txt")

# ============================================================================
# BUILDING ENVELOPE AND EQUIPMENT EFFICIENCY REFERENCE DATA
# ============================================================================

ENVELOPE_EFFICIENCY_INDEX = os.path.join(DATA_DIR, "building_envelope_efficiency_index.csv")
SEGMENT_HEATING_MULTIPLIERS_CSV = os.path.join(DATA_DIR, "segment_heating_multipliers.csv")
EQUIPMENT_AFUE_TRAJECTORY = os.path.join(DATA_DIR, "equipment_afue_trajectory.csv")

# ============================================================================
# GREEN BUILDING REGISTRY API
# ============================================================================

GBR_API_BASE_URL = "https://api.greenbuildingregistry.com"
GBR_API_KEY_ENV_VAR = "GBR_API_KEY"

# ============================================================================
# RBSA METERING DATA (SUB-METERED END-USE)
# ============================================================================

RBSAM_Y1_DIR = os.path.join(DATA_DIR, "Future Work", "rbsam_y1")
RBSAM_Y2_DIR = os.path.join(DATA_DIR, "Future Work", "rbsam_y2")
RBSAM_DATA_DICT = os.path.join(DATA_DIR, "Future Work", "rbsa-metering-data-dictionary-2016-2017.xlsx")

# ============================================================================
# 2017 RBSA-II DATASET (EARLIER VINTAGE FOR TEMPORAL COMPARISON)
# ============================================================================

RBSA_2017_DIR = os.path.join(DATA_DIR, "2017-RBSA-II-Combined-Database")
RBSA_2017_USER_MANUAL = os.path.join(DATA_DIR, "2017-RBSA-II-Database-User-Manual.pdf")

# ============================================================================
# CENSUS API CONSTANTS
# ============================================================================

CENSUS_API_BASE = "https://api.census.gov/data"
CENSUS_ACS1_TEMPLATE = "{base}/{year}/acs/acs1"
CENSUS_ACS5_TEMPLATE = "{base}/{year}/acs/acs5"
CENSUS_B25034_GROUP = "B25034"  # Year Structure Built
CENSUS_B25040_GROUP = "B25040"  # House Heating Fuel
CENSUS_B25024_GROUP = "B25024"  # Units in Structure

NWN_SERVICE_TERRITORY_CSV = os.path.join(DATA_DIR, "NW Natural Service Territory Census data.csv")
B25034_BACKUP_DIR = os.path.join(DATA_DIR, "B25034-5y")
B25034_COUNTY_DIR = os.path.join(DATA_DIR, "B25034-5y-county")
B25040_COUNTY_DIR = os.path.join(DATA_DIR, "B25040-5y-county")
B25024_COUNTY_DIR = os.path.join(DATA_DIR, "B25024-5y-county")

# PSU Population Research Center forecasts
PSU_FORECAST_URL = "https://www.pdx.edu/population-research/past-forecasts"
PSU_PROJECTION_DIR = os.path.join(DATA_DIR, "PSU projection data")

# ============================================================================
# WASHINGTON STATE OFM HOUSING ESTIMATES
# ============================================================================

OFM_HOUSING_XLSX = os.path.join(DATA_DIR, "ofm_april1_housing.xlsx")

# ============================================================================
# NOAA CLIMATE NORMALS
# ============================================================================

NOAA_NORMALS_DIR = os.path.join(DATA_DIR, "noaa_normals")
NOAA_CDO_API_BASE = "https://www.ncei.noaa.gov/cdo-web/api/v2"
NOAA_CDO_TOKEN_ENV_VAR = "NOAA_CDO_TOKEN"

# ICAO to GHCND station mapping for NOAA Climate Normals
# 11 weather stations in NW Natural service territory
ICAO_TO_GHCND = {
    "KPDX": "USW00024229",   # Portland International Airport
    "KEUG": "USW00024218",   # Eugene Airport
    "KSLE": "USW00024288",   # Salem-Leckrone Airport
    "KAST": "USW00024218",   # Astoria Regional Airport (proxy: Eugene)
    "KDLS": "USW00024155",   # The Dalles Municipal Airport
    "KOTH": "USW00024288",   # North Bend/Coos Bay Airport (proxy: Salem)
    "KONP": "USW00024288",   # Newport Airport (proxy: Salem)
    "KCVO": "USW00024288",   # Corvallis Airport (proxy: Salem)
    "KHIO": "USW00024229",   # Hillsboro Airport (proxy: Portland)
    "KTTD": "USW00024229",   # Troutdale Airport (proxy: Portland)
    "KVUO": "USW00024289",   # Vancouver-Pearson Field (proxy: Salem)
}

# ============================================================================
# EIA RECS MICRODATA (RESIDENTIAL ENERGY CONSUMPTION SURVEY)
# ============================================================================

RECS_DIR = os.path.join(DATA_DIR, "Residential Energy Consumption Survey")
RECS_2020_CSV = os.path.join(RECS_DIR, "recs2020_public_v7.csv")
RECS_2015_CSV = os.path.join(RECS_DIR, "recs2015_public_v4.csv")
RECS_2009_CSV = os.path.join(RECS_DIR, "2009", "recs2009_public.csv")
RECS_2005_CSV = os.path.join(RECS_DIR, "2005", "RECS05alldata.csv")

RECS_PACIFIC_DIVISION = 9      # Division code for Pacific (OR, WA, CA, NV, HI)
RECS_FUELHEAT_GAS = 1          # Fuel type code for utility gas heating

# ============================================================================
# SIMULATION PARAMETERS
# ============================================================================

BASE_YEAR = 2025                # Base year for model calibration
DEFAULT_BASE_TEMP = 65.0        # Base temperature for HDD/CDD calculation (Fahrenheit)
DEFAULT_HOT_WATER_TEMP = 120.0  # Target hot water temperature (Fahrenheit)
DEFAULT_COLD_WATER_TEMP = 55.0  # Assumed incoming cold water temperature (Fahrenheit)
DEFAULT_DAILY_HOT_WATER_GALLONS = 64.0  # Average daily hot water consumption per household (gallons)

# ============================================================================
# VINTAGE-BASED HEATING FACTOR MULTIPLIERS
# ============================================================================

# Older homes have worse insulation and leak more heat → higher heating factor
# Newer homes are built to stricter energy codes → lower heating factor
# Based on RBSA building shell data and nw_energy_proxies.csv envelope UA values
# Multiplier is relative to the calibrated heating_factor (1.0 = average)
VINTAGE_HEATING_MULTIPLIER = {
    # (min_year, max_year): multiplier
    (0, 1979): 1.35,       # Pre-1980: poor insulation, single-pane windows
    (1980, 1999): 1.15,    # 1980-1999: first energy codes, better insulation
    (2000, 2009): 1.00,    # 2000-2009: baseline (calibration era)
    (2010, 2014): 0.85,    # 2010-2014: improved codes, better windows
    (2015, 2099): 0.70,    # 2015+: current code, condensing furnaces, tight envelope
}

# Segment-based heating factor multipliers
# Multi-family uses less heat per unit (shared walls, smaller units)
SEGMENT_HEATING_MULTIPLIER = {
    'RESSF': 1.05,          # Single-family: slightly above average (larger, more exposed)
    'RESMF': 0.70,          # Multi-family: shared walls reduce heat loss ~30%
    'Unclassified': 1.00,   # Unknown: use average
}

# ============================================================================
# CURRENT RESIDENTIAL TARIFF RATES (REFERENCE)
# ============================================================================

# Current residential rates ($/therm) as of October 2025 / November 2025
# These are used as reference points; historical rates are reconstructed from tariff CSVs
OR_CURRENT_RATE = 1.41220      # Oregon Schedule 2 residential rate ($/therm)
WA_CURRENT_RATE = 1.24164      # Washington Schedule 2 residential rate ($/therm)

# ============================================================================
# LOGGING AND OUTPUT CONFIGURATION
# ============================================================================

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
OUTPUT_DIR = "output"
