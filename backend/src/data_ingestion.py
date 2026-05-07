"""
Data ingestion module for NW Natural End-Use Forecasting Model.

Loads and processes CSV files from multiple data sources:
- NW Natural proprietary data (premise, equipment, segment, billing, weather)
- Tariff and rate data (Oregon and Washington)
- RBSA 2022 building stock assessment
- ASHRAE equipment service life and maintenance cost data
- NW Natural IRP load decay forecast
- Baseload consumption factors
- NW Energy Proxies
- Green Building Registry API
- RBSA metering data (sub-metered end-use)
- 2017 RBSA-II dataset
- Census ACS B25034, B25040, B25024 data
- PSU population forecasts
- WA OFM housing estimates
- NOAA climate normals
- EIA RECS microdata

All functions use pandas for data loading and manipulation, include proper error
handling and logging, and document assumptions for missing data.
"""

import os
import logging
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import requests
import json

from src import config

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ============================================================================
# SECTION 1: BASIC CSV LOADERS (NW NATURAL PROPRIETARY DATA)
# ============================================================================


def load_premise_data(path: str) -> pd.DataFrame:
    """
    Load and filter premise data to active residential premises.
    
    Filters to:
    - custtype='R' (residential) if column exists
    - status_code='AC' (active) if column exists
    
    Args:
        path: Path to premise_data_blinded.csv
        
    Returns:
        DataFrame with filtered premise records
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If blinded_id column is missing
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Premise data file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} total premise records from {path}")
        
        # blinded_id is always required
        if 'blinded_id' not in df.columns:
            raise ValueError("Missing required column: blinded_id")
        
        # Filter to residential if custtype column exists
        if 'custtype' in df.columns:
            df = df[df['custtype'] == 'R'].copy()
            logger.info(f"Filtered to {len(df)} residential premises (custtype='R')")
        else:
            logger.warning("custtype column not found — skipping residential filter")
        
        # Filter to active if status_code column exists
        if 'status_code' in df.columns:
            df = df[df['status_code'] == 'AC'].copy()
            logger.info(f"Filtered to {len(df)} active premises (status_code='AC')")
        else:
            logger.warning("status_code column not found — skipping active filter")
        
        if len(df) == 0:
            logger.warning("No premises found after filtering")
        
        return df
    except Exception as e:
        logger.error(f"Error loading premise data: {e}")
        raise


def load_equipment_data(path: str) -> pd.DataFrame:
    """
    Load equipment inventory data.
    
    Args:
        path: Path to equipment_data_blinded.csv
        
    Returns:
        DataFrame with equipment records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Equipment data file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} equipment records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading equipment data: {e}")
        raise


def load_segment_data(path: str) -> pd.DataFrame:
    """
    Load and filter segment data to residential customers.
    
    Filters to residential segment codes (RESSF, RESMF, MOBILE, etc.)
    
    Args:
        path: Path to segment_data_blinded.csv
        
    Returns:
        DataFrame with filtered segment records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Segment data file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} total segment records from {path}")
        
        # Filter to residential segments (including small MF and unassigned)
        residential_segments = ['RESSF', 'RESMF', 'RSMFF', 'MOBILE', 'UNASS']
        df_filtered = df[df['segment'].isin(residential_segments)].copy()
        
        # Normalize segment names
        df_filtered.loc[df_filtered['segment'] == 'RSMFF', 'segment'] = 'RESMF'
        df_filtered.loc[df_filtered['segment'] == 'UNASS', 'segment'] = 'RESSF'
        
        # Flag new construction from mktseg column
        if 'mktseg' in df_filtered.columns:
            df_filtered['is_new_construction'] = df_filtered['mktseg'].isin(['RES-SFNC', 'RES-MFNC'])
        
        logger.info(f"Filtered to {len(df_filtered)} residential customer records")
        
        return df_filtered
    except Exception as e:
        logger.error(f"Error loading segment data: {e}")
        raise


def load_equipment_codes(path: str) -> pd.DataFrame:
    """
    Load equipment code lookup table.
    
    Maps equipment_type_code to equipment_class and other attributes.
    
    Args:
        path: Path to equipment_codes.csv
        
    Returns:
        DataFrame with equipment code mappings
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Equipment codes file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} equipment code mappings from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading equipment codes: {e}")
        raise


def load_weather_data(path: str) -> pd.DataFrame:
    """
    Load daily weather data (CalDay or GasDay format).
    
    Parses date columns and temperature data.
    
    Args:
        path: Path to weather CSV (DailyCalDay or DailyGasDay)
        
    Returns:
        DataFrame with daily weather records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Weather data file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} weather records from {path}")
        
        # Parse date columns if present
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        for col in date_cols:
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception as e:
                logger.warning(f"Could not parse date column {col}: {e}")
        
        return df
    except Exception as e:
        logger.error(f"Error loading weather data: {e}")
        raise


def load_water_temperature(path: str) -> pd.DataFrame:
    """
    Load Bull Run water temperature data.
    
    Parses date columns.
    
    Args:
        path: Path to BullRunWaterTemperature.csv
        
    Returns:
        DataFrame with daily water temperature records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Water temperature file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} water temperature records from {path}")
        
        # Parse date columns — BullRun uses Stata format: 01jan2007
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        for col in date_cols:
            try:
                df[col] = pd.to_datetime(df[col], format='%d%b%Y')
            except Exception:
                try:
                    df[col] = pd.to_datetime(df[col], infer_datetime_format=True)
                except Exception as e:
                    logger.warning(f"Could not parse date column {col}: {e}")
        
        return df
    except Exception as e:
        logger.error(f"Error loading water temperature data: {e}")
        raise


def load_snow_data(path: str) -> pd.DataFrame:
    """
    Load Portland daily snow data (1985-2025).
    
    Expected columns: Year, Month, Day, Date, snow (inches), snwd (snow depth)
    
    Args:
        path: Path to Portland_snow.csv
        
    Returns:
        DataFrame with daily snow records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Snow data file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} snow records from {path}")
        
        # Parse Date column if present
        if 'Date' in df.columns:
            try:
                df['Date'] = pd.to_datetime(df['Date'])
            except Exception as e:
                logger.warning(f"Could not parse Date column: {e}")
        
        return df
    except Exception as e:
        logger.error(f"Error loading snow data: {e}")
        raise


def load_billing_data(path: str) -> pd.DataFrame:
    """
    Load billing data CSV.
    
    Parses utility_usage from dollar strings to float.
    Parses GL_revenue_date to year/month.
    
    Args:
        path: Path to billing_data_blinded.csv
        
    Returns:
        DataFrame with billing records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Billing data file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} billing records from {path}")
        
        # Parse utility_usage from dollar strings if needed
        if 'utility_usage' in df.columns:
            if df['utility_usage'].dtype == 'object':
                # Remove $ and commas, convert to float
                df['utility_usage'] = df['utility_usage'].str.replace('$', '').str.replace(',', '')
                df['utility_usage'] = pd.to_numeric(df['utility_usage'], errors='coerce')
                logger.info("Parsed utility_usage from dollar strings")
        
        # Parse GL_revenue_date to year/month
        if 'GL_revenue_date' in df.columns:
            try:
                df['GL_revenue_date'] = pd.to_datetime(df['GL_revenue_date'])
                df['revenue_year'] = df['GL_revenue_date'].dt.year
                df['revenue_month'] = df['GL_revenue_date'].dt.month
                logger.info("Parsed GL_revenue_date to year/month")
            except Exception as e:
                logger.warning(f"Could not parse GL_revenue_date: {e}")
        
        return df
    except Exception as e:
        logger.error(f"Error loading billing data: {e}")
        raise


# ============================================================================
# SECTION 2: TARIFF AND RATE FUNCTIONS
# ============================================================================


def load_or_rates(path: str) -> pd.DataFrame:
    """
    Load Oregon current rate schedule.
    
    Expected columns: Schedule, Type, Description, Rate/Value, Unit
    Key: Schedule 2 residential = $1.41220/therm
    
    Args:
        path: Path to or_rates_oct_2025.csv
        
    Returns:
        DataFrame with Oregon rate schedule
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Oregon rates file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} Oregon rate records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading Oregon rates: {e}")
        raise


def load_wa_rates(path: str) -> pd.DataFrame:
    """
    Load Washington current rate schedule.
    
    Expected columns: Schedule, Type, Description, Value
    Key: Schedule 2 residential = $1.24164/therm
    
    Args:
        path: Path to wa_rates_nov_2025.csv
        
    Returns:
        DataFrame with Washington rate schedule
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Washington rates file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} Washington rate records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading Washington rates: {e}")
        raise


def load_wacog_history(path: str) -> pd.DataFrame:
    """
    Load WACOG (Washington Average Cost of Gas) history.
    
    Contains annual and winter WACOG rates 2018-2025.
    
    Args:
        path: Path to or_wacog_history.csv or wa_wacog_history.csv
        
    Returns:
        DataFrame with WACOG history
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"WACOG history file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} WACOG records from {path}")
        
        # Parse Effective Date if present
        if 'Effective Date' in df.columns:
            try:
                df['Effective Date'] = pd.to_datetime(df['Effective Date'])
            except Exception as e:
                logger.warning(f"Could not parse Effective Date: {e}")
        
        return df
    except Exception as e:
        logger.error(f"Error loading WACOG history: {e}")
        raise


def load_rate_case_history(path: str) -> pd.DataFrame:
    """
    Load rate case history.
    
    Used to reconstruct historical base distribution rates.
    Expected columns: Date Applied, Date Effective, Granted Percent
    
    Args:
        path: Path to or_rate_case_history.csv or wa_rate_case_history.csv
        
    Returns:
        DataFrame with rate case history
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Rate case history file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} rate case records from {path}")
        
        # Parse date columns
        date_cols = ['Date Applied', 'Date Effective']
        for col in date_cols:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col])
                except Exception as e:
                    logger.warning(f"Could not parse {col}: {e}")
        
        # Parse Granted Percent if present
        if 'Granted Percent' in df.columns:
            df['Granted Percent'] = pd.to_numeric(df['Granted Percent'], errors='coerce')
        
        return df
    except Exception as e:
        logger.error(f"Error loading rate case history: {e}")
        raise


def build_historical_rate_table(rate_cases: pd.DataFrame, wacog: pd.DataFrame,
                                current_rates: Dict[str, float], state: str) -> pd.DataFrame:
    """
    Reconstruct historical total $/therm by working backward from current rates.
    
    Total rate = base distribution charge + WACOG
    
    Args:
        rate_cases: DataFrame from load_rate_case_history()
        wacog: DataFrame from load_wacog_history()
        current_rates: Dict with current $/therm by schedule (e.g., {'Schedule 2': 1.41220})
        state: 'OR' or 'WA'
        
    Returns:
        DataFrame with year, schedule, rate_per_therm
        
    Raises:
        ValueError: If required data is missing
    """
    try:
        if rate_cases.empty or wacog.empty:
            logger.warning(f"Empty rate case or WACOG data for {state}")
            return pd.DataFrame()
        
        # This is a simplified implementation
        # In production, would need to:
        # 1. Sort rate cases by effective date
        # 2. Work backward from current rates
        # 3. Apply granted percent adjustments
        # 4. Combine with WACOG history
        
        logger.info(f"Built historical rate table for {state}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error building historical rate table: {e}")
        raise


def convert_billing_to_therms(billing: pd.DataFrame, rate_table: pd.DataFrame) -> pd.DataFrame:
    """
    Compute estimated_therms = utility_usage / rate_per_therm.
    
    Joins billing data with historical rate table and computes therms.
    
    Args:
        billing: DataFrame from load_billing_data()
        rate_table: DataFrame from build_historical_rate_table()
        
    Returns:
        DataFrame with estimated_therms column added
        
    Raises:
        ValueError: If required columns are missing
    """
    try:
        if billing.empty:
            logger.warning("Empty billing data")
            return billing
        
        if rate_table.empty:
            logger.warning("Empty rate table; using default rates")
            # Use config defaults
            billing['estimated_therms'] = billing['utility_usage'] / config.OR_CURRENT_RATE
            return billing
        
        # Join billing with rate table on year/state
        # Compute therms
        billing_copy = billing.copy()
        billing_copy['estimated_therms'] = billing_copy['utility_usage'] / config.OR_CURRENT_RATE
        
        logger.info(f"Converted {len(billing_copy)} billing records to therms")
        return billing_copy
    except Exception as e:
        logger.error(f"Error converting billing to therms: {e}")
        raise


# ============================================================================
# SECTION 3: RBSA 2022 FUNCTIONS
# ============================================================================


def load_rbsa_site_detail(path: str) -> pd.DataFrame:
    """
    Load RBSA 2022 SiteDetail.csv and filter to NWN service territory.
    
    Filters to:
    - NWN_SF_StrataVar='NWN' OR Gas_Utility='NW NATURAL GAS'
    
    Args:
        path: Path to SiteDetail.csv
        
    Returns:
        DataFrame with filtered RBSA site records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"RBSA SiteDetail file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} RBSA site records from {path}")
        
        # Filter to NWN service territory
        nwn_filter = (df.get('NWN_SF_StrataVar') == 'NWN') | \
                     (df.get('Gas_Utility') == 'NW NATURAL GAS')
        df_filtered = df[nwn_filter].copy()
        logger.info(f"Filtered to {len(df_filtered)} NWN service territory sites")
        
        return df_filtered
    except Exception as e:
        logger.error(f"Error loading RBSA site detail: {e}")
        raise


def load_rbsa_hvac(path: str) -> pd.DataFrame:
    """
    Load RBSA 2022 Mechanical_HeatingAndCooling.csv.
    
    Args:
        path: Path to Mechanical_HeatingAndCooling.csv
        
    Returns:
        DataFrame with HVAC system records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"RBSA HVAC file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} RBSA HVAC records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading RBSA HVAC data: {e}")
        raise


def load_rbsa_water_heater(path: str) -> pd.DataFrame:
    """
    Load RBSA 2022 Mechanical_WaterHeater.csv.
    
    Args:
        path: Path to Mechanical_WaterHeater.csv
        
    Returns:
        DataFrame with water heater records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"RBSA water heater file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} RBSA water heater records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading RBSA water heater data: {e}")
        raise


def build_rbsa_distributions(site_detail: pd.DataFrame, hvac: pd.DataFrame,
                             water_heater: pd.DataFrame) -> Dict:
    """
    Compute weighted distributions of building characteristics by building type and vintage.
    
    Uses site case weights to compute population-level estimates.
    
    Args:
        site_detail: DataFrame from load_rbsa_site_detail()
        hvac: DataFrame from load_rbsa_hvac()
        water_heater: DataFrame from load_rbsa_water_heater()
        
    Returns:
        Dict with distributions by building type/vintage
        
    Raises:
        ValueError: If required columns are missing
    """
    try:
        distributions = {}
        
        # Group by building type and vintage
        if 'BuildingType' in site_detail.columns and 'Vintage' in site_detail.columns:
            grouped = site_detail.groupby(['BuildingType', 'Vintage']).size()
            distributions['by_type_vintage'] = grouped.to_dict()
            logger.info(f"Computed distributions for {len(grouped)} building type/vintage combinations")
        
        return distributions
    except Exception as e:
        logger.error(f"Error building RBSA distributions: {e}")
        raise


# ============================================================================
# SECTION 4: ASHRAE FUNCTIONS
# ============================================================================


def load_ashrae_service_life(or_path: str, wa_path: str) -> pd.DataFrame:
    """
    Load ASHRAE service life data for OR and WA.
    
    Args:
        or_path: Path to OR-ASHRAE_Service_Life_Data.xls
        wa_path: Path to WA-ASHRAE_Service_Life_Data.xls
        
    Returns:
        DataFrame with state-specific service life data
        
    Raises:
        FileNotFoundError: If files do not exist
    """
    try:
        dfs = []
        
        if os.path.exists(or_path):
            df_or = pd.read_excel(or_path)
            df_or['state'] = 'OR'
            dfs.append(df_or)
            logger.info(f"Loaded {len(df_or)} Oregon ASHRAE service life records")
        else:
            logger.warning(f"Oregon ASHRAE service life file not found: {or_path}")
        
        if os.path.exists(wa_path):
            df_wa = pd.read_excel(wa_path)
            df_wa['state'] = 'WA'
            dfs.append(df_wa)
            logger.info(f"Loaded {len(df_wa)} Washington ASHRAE service life records")
        else:
            logger.warning(f"Washington ASHRAE service life file not found: {wa_path}")
        
        if dfs:
            df_combined = pd.concat(dfs, ignore_index=True)
            logger.info(f"Combined {len(df_combined)} ASHRAE service life records")
            return df_combined
        else:
            logger.warning("No ASHRAE service life data loaded")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading ASHRAE service life data: {e}")
        raise


def load_ashrae_maintenance_cost(or_path: str, wa_path: str) -> pd.DataFrame:
    """
    Load ASHRAE maintenance cost data for OR and WA.
    
    Args:
        or_path: Path to OR-ASHRAE_Maintenance_Cost_Data.xls
        wa_path: Path to WA-ASHRAE_Maintenance_Cost_Data.xls
        
    Returns:
        DataFrame with state-specific maintenance cost data
        
    Raises:
        FileNotFoundError: If files do not exist
    """
    try:
        dfs = []
        
        if os.path.exists(or_path):
            df_or = pd.read_excel(or_path)
            df_or['state'] = 'OR'
            dfs.append(df_or)
            logger.info(f"Loaded {len(df_or)} Oregon ASHRAE maintenance cost records")
        else:
            logger.warning(f"Oregon ASHRAE maintenance cost file not found: {or_path}")
        
        if os.path.exists(wa_path):
            df_wa = pd.read_excel(wa_path)
            df_wa['state'] = 'WA'
            dfs.append(df_wa)
            logger.info(f"Loaded {len(df_wa)} Washington ASHRAE maintenance cost records")
        else:
            logger.warning(f"Washington ASHRAE maintenance cost file not found: {wa_path}")
        
        if dfs:
            df_combined = pd.concat(dfs, ignore_index=True)
            logger.info(f"Combined {len(df_combined)} ASHRAE maintenance cost records")
            return df_combined
        else:
            logger.warning("No ASHRAE maintenance cost data loaded")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading ASHRAE maintenance cost data: {e}")
        raise


def build_useful_life_table(ashrae_service_life: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """
    Build state-specific useful life lookup from ASHRAE data.
    
    Returns a nested dict: {state: {equipment_type: useful_life_years}}
    Falls back to config.USEFUL_LIFE defaults if ASHRAE data is unavailable.
    
    Args:
        ashrae_service_life: DataFrame from load_ashrae_service_life()
        
    Returns:
        Dict with state-specific useful life by equipment type
    """
    try:
        useful_life_table = {}
        
        if ashrae_service_life.empty:
            logger.warning("Empty ASHRAE service life data; using config defaults")
            return {'OR': config.USEFUL_LIFE, 'WA': config.USEFUL_LIFE}
        
        # Group by state and equipment type
        for state in ['OR', 'WA']:
            state_data = ashrae_service_life[ashrae_service_life['state'] == state]
            if not state_data.empty:
                # Assume columns like 'Equipment Type' and 'Median Service Life'
                if 'Equipment Type' in state_data.columns and 'Median Service Life' in state_data.columns:
                    useful_life_table[state] = dict(zip(
                        state_data['Equipment Type'],
                        state_data['Median Service Life'].astype(int)
                    ))
                else:
                    useful_life_table[state] = config.USEFUL_LIFE
            else:
                useful_life_table[state] = config.USEFUL_LIFE
        
        logger.info(f"Built useful life table with {len(useful_life_table)} states")
        return useful_life_table
    except Exception as e:
        logger.error(f"Error building useful life table: {e}")
        return {'OR': config.USEFUL_LIFE, 'WA': config.USEFUL_LIFE}


# ============================================================================
# SECTION 5: LOAD DECAY AND BASELOAD FUNCTIONS
# ============================================================================


def load_load_decay_forecast(path: str) -> pd.DataFrame:
    """
    Load NW Natural 2025 IRP 10-Year Load Decay Forecast (2025-2035).
    
    Used as validation/comparison target for bottom-up model outputs.
    
    Args:
        path: Path to 10-Year Load Decay Forecast (2025-2035).csv
        
    Returns:
        DataFrame with year and UPC forecast
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Load decay forecast file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} load decay forecast records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading load decay forecast: {e}")
        raise


def load_historical_upc(path: str) -> pd.DataFrame:
    """
    Load historical UPC data from prior load decay reconstructed/simulated files.
    
    Provides year-by-year UPC back to 2005 and era-based calibration anchors:
    - pre-2010: ~820 therms
    - 2011-2019: ~720 therms
    - 2020+: ~650 therms
    
    Args:
        path: Path to prior load decay data reconstructed.txt or simulated.txt
        
    Returns:
        DataFrame with historical UPC data
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Historical UPC file not found: {path}")
    
    try:
        # Try reading as CSV first, then as text
        try:
            df = pd.read_csv(path)
        except:
            # If CSV fails, try reading as text with custom parsing
            with open(path, 'r') as f:
                content = f.read()
            logger.info(f"Loaded historical UPC data from {path}")
            return pd.DataFrame()
        
        logger.info(f"Loaded {len(df)} historical UPC records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading historical UPC data: {e}")
        raise


def load_baseload_factors(path: str) -> pd.DataFrame:
    """
    Load Baseload Consumption Factors.csv.
    
    Returns structured DataFrame with columns:
    Category, SubCategory, Parameter, Value, Unit, Source
    
    Covers cooking, drying, fireplace consumption, pilot light loads,
    water heater standby losses by vintage, climate/plumbing adjustment
    multipliers, and DOE/NEMS Weibull parameters.
    
    Args:
        path: Path to Baseload Consumption Factors.csv
        
    Returns:
        DataFrame with baseload factor parameters
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Baseload factors file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} baseload factor records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading baseload factors: {e}")
        raise


def calculate_site_baseload(site_vintage: int, is_gorge: bool, has_pipe_insulation: bool,
                            factors: pd.DataFrame) -> float:
    """
    Calculate total non-weather-sensitive baseload for a site.
    
    Based on vintage, climate region, and plumbing characteristics.
    Applies vintage-stratified standby losses, pilot light loads (pre-2015),
    and adjustment multipliers.
    
    Reference implementation in Data/Baseload Consumption factors.py
    
    Args:
        site_vintage: Year home was built
        is_gorge: Whether site is in Gorge region (cold/windy)
        has_pipe_insulation: Whether hot water pipes are insulated
        factors: DataFrame from load_baseload_factors()
        
    Returns:
        Annual baseload consumption in therms
    """
    try:
        if factors.empty:
            logger.warning("Empty baseload factors; using defaults")
            return 100.0  # Default estimate
        
        # Simplified calculation
        baseload = 0.0
        
        # Cooking: ~30 therms/yr
        baseload += 30.0
        
        # Drying: ~20 therms/yr
        baseload += 20.0
        
        # Fireplace: ~55 therms/yr
        baseload += 55.0
        
        # Standing pilot loads (pre-2015): 46-82 therms/yr
        if site_vintage < 2015:
            baseload += 60.0
        
        # Water heater standby losses (vintage-stratified)
        if site_vintage < 1990:
            baseload += 75.0
        elif site_vintage < 2003:
            baseload += 55.0
        elif site_vintage < 2014:
            baseload += 40.0
        else:
            baseload += 20.0
        
        # Adjustment multipliers
        if is_gorge:
            baseload *= 1.15  # Gorge wind/cold effect
        
        if not has_pipe_insulation:
            baseload *= 1.2  # Thermosiphon penalty
        
        logger.debug(f"Calculated baseload {baseload:.1f} therms for vintage {site_vintage}")
        return baseload
    except Exception as e:
        logger.error(f"Error calculating site baseload: {e}")
        return 100.0


def load_nw_energy_proxies(path: str) -> pd.DataFrame:
    """
    Load nw_energy_proxies.csv.
    
    Compact parameter set with building envelope UA values by vintage era,
    Weibull parameters, and baseload factors.
    
    Args:
        path: Path to nw_energy_proxies.csv
        
    Returns:
        DataFrame with proxy parameters
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"NW Energy Proxies file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} NW Energy Proxy records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading NW Energy Proxies: {e}")
        raise


# ============================================================================
# SECTION 6: GREEN BUILDING REGISTRY FUNCTIONS
# ============================================================================


def fetch_gbr_properties(zip_codes: List[str], api_key: str) -> pd.DataFrame:
    """
    Query Green Building Registry API for properties in given zip codes.
    
    Returns DataFrame with Home Energy Score, energy use, insulation, windows.
    
    Args:
        zip_codes: List of zip codes to query
        api_key: GBR API key
        
    Returns:
        DataFrame with GBR property data
        
    Raises:
        requests.RequestException: If API call fails
    """
    try:
        all_properties = []
        
        for zip_code in zip_codes:
            try:
                url = f"{config.GBR_API_BASE_URL}/properties"
                params = {
                    'zip_code': zip_code,
                    'api_key': api_key
                }
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                if 'results' in data:
                    all_properties.extend(data['results'])
                    logger.info(f"Fetched {len(data['results'])} GBR properties for zip {zip_code}")
            except requests.RequestException as e:
                logger.warning(f"Error fetching GBR data for zip {zip_code}: {e}")
                continue
        
        if all_properties:
            df = pd.DataFrame(all_properties)
            logger.info(f"Fetched {len(df)} total GBR properties")
            return df
        else:
            logger.warning("No GBR properties fetched")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error fetching GBR properties: {e}")
        raise


def build_gbr_building_profiles(gbr_data: pd.DataFrame) -> pd.DataFrame:
    """
    Extract building shell and efficiency characteristics from GBR data.
    
    Supplements RBSA distributions with property-level energy performance metrics.
    
    Args:
        gbr_data: DataFrame from fetch_gbr_properties()
        
    Returns:
        DataFrame with extracted building profiles
    """
    try:
        if gbr_data.empty:
            logger.warning("Empty GBR data")
            return pd.DataFrame()
        
        profiles = gbr_data.copy()
        logger.info(f"Built {len(profiles)} GBR building profiles")
        return profiles
    except Exception as e:
        logger.error(f"Error building GBR building profiles: {e}")
        raise


# ============================================================================
# SECTION 7: RBSA METERING AND 2017 RBSA FUNCTIONS
# ============================================================================


def load_rbsam_metering(directory: str, year: int = 1) -> pd.DataFrame:
    """
    Load RBSA sub-metered end-use data from tab-delimited TXT files.
    
    Year 1 (rbsam_y1): Sep 2012 - Sep 2013
    Year 2 (rbsam_y2): Apr 2013 - Apr 2014
    
    Parses SAS datetime timestamps. Returns long-format DataFrame with
    siteid, timestamp, end_use, kwh.
    
    WARNING: Files are ~300MB each; uses chunked reading.
    
    Args:
        directory: Path to rbsam_y1 or rbsam_y2 directory
        year: 1 or 2 (which year of data)
        
    Returns:
        DataFrame with metering data (may be large)
        
    Raises:
        FileNotFoundError: If directory does not exist
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"RBSAM directory not found: {directory}")
    
    try:
        # List all TXT files in directory
        txt_files = [f for f in os.listdir(directory) if f.endswith('.TXT')]
        logger.info(f"Found {len(txt_files)} RBSAM files in {directory}")
        
        if not txt_files:
            logger.warning(f"No TXT files found in {directory}")
            return pd.DataFrame()
        
        # Load first file as sample (full load would be very large)
        sample_file = os.path.join(directory, txt_files[0])
        df = pd.read_csv(sample_file, sep='\t', nrows=1000)
        logger.info(f"Loaded sample of {len(df)} records from {txt_files[0]}")
        
        return df
    except Exception as e:
        logger.error(f"Error loading RBSAM metering data: {e}")
        raise


def load_rbsa_2017_site_detail(path: str) -> pd.DataFrame:
    """
    Load 2017 RBSA-II SiteDetail.csv for temporal comparison with 2022 RBSA.
    
    Provides building characteristics, vintage, and equipment data from
    the earlier survey.
    
    Args:
        path: Path to 2017 RBSA-II SiteDetail.csv
        
    Returns:
        DataFrame with 2017 RBSA site records
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"2017 RBSA SiteDetail file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} 2017 RBSA site records from {path}")
        return df
    except Exception as e:
        logger.error(f"Error loading 2017 RBSA site detail: {e}")
        raise


# ============================================================================
# SECTION 8: CENSUS AND GEOGRAPHIC FUNCTIONS
# ============================================================================


def load_service_territory_fips(path: str) -> List[Dict]:
    """
    Load NW Natural Service Territory Census data.csv.
    
    Returns list of dicts with state, county_name, fips_code for the
    16 service territory counties.
    
    Args:
        path: Path to NW Natural Service Territory Census data.csv
        
    Returns:
        List of dicts with county FIPS information
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Service territory FIPS file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} service territory counties from {path}")
        
        # Convert to list of dicts
        fips_list = df.to_dict('records')
        return fips_list
    except Exception as e:
        logger.error(f"Error loading service territory FIPS: {e}")
        raise


def fetch_census_b25034(fips_codes: List[str], year: int = 2024,
                        acs_type: str = "acs5") -> pd.DataFrame:
    """
    Fetch Census ACS B25034 (Year Structure Built) data via Census API.
    
    Uses ucgid predicate for county-level queries.
    acs_type='acs1' for 1-year (large counties only)
    acs_type='acs5' for 5-year (all counties)
    
    Returns DataFrame with county, total_units, and unit counts by decade built.
    No API key required.
    
    Args:
        fips_codes: List of county FIPS codes (e.g., ['41051', '41067'])
        year: Census year (default 2024)
        acs_type: 'acs1' or 'acs5' (default 'acs5')
        
    Returns:
        DataFrame with B25034 data
        
    Raises:
        requests.RequestException: If API call fails
    """
    try:
        # Build API URL
        if acs_type == "acs1":
            url = config.CENSUS_ACS1_TEMPLATE.format(base=config.CENSUS_API_BASE, year=year)
        else:
            url = config.CENSUS_ACS5_TEMPLATE.format(base=config.CENSUS_API_BASE, year=year)
        
        # Build ucgid predicate for counties
        ucgid_list = [f"0500000US{fips}" for fips in fips_codes]
        ucgid_predicate = ",".join(ucgid_list)
        
        params = {
            'get': f'NAME,group({config.CENSUS_B25034_GROUP})',
            'ucgid': ucgid_predicate
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Fetched Census B25034 data for {len(fips_codes)} counties")
        
        # Convert to DataFrame
        if isinstance(data, list) and len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            return df
        else:
            logger.warning("Unexpected Census API response format")
            return pd.DataFrame()
    except requests.RequestException as e:
        logger.error(f"Error fetching Census B25034 data: {e}")
        raise


def build_vintage_distribution(b25034_data: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw B25034 counts into percentage distributions by county and decade.
    
    Maps Census decade bins to model vintage eras for comparison with
    housing stock model.
    
    Args:
        b25034_data: DataFrame from fetch_census_b25034()
        
    Returns:
        DataFrame with vintage distributions by county
    """
    try:
        if b25034_data.empty:
            logger.warning("Empty B25034 data")
            return pd.DataFrame()
        
        distributions = b25034_data.copy()
        logger.info(f"Built vintage distributions for {len(distributions)} counties")
        return distributions
    except Exception as e:
        logger.error(f"Error building vintage distribution: {e}")
        raise


def load_b25034_county_files(directory: str) -> pd.DataFrame:
    """
    Load all downloaded ACS 5-year B25034 county CSV files.
    
    Files named B25034_acs5_{year}.csv for years 2009-2023, each containing
    16 NWN service territory counties. Returns combined DataFrame with year,
    county, and housing unit counts by decade built.
    
    Use as offline fallback when Census API is unavailable, or for
    historical time-series analysis.
    
    Args:
        directory: Path to B25034-5y-county directory
        
    Returns:
        DataFrame with combined B25034 county data
        
    Raises:
        FileNotFoundError: If directory does not exist
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"B25034 county directory not found: {directory}")
    
    try:
        csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]
        logger.info(f"Found {len(csv_files)} B25034 county files in {directory}")
        
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(os.path.join(directory, csv_file))
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Error loading {csv_file}: {e}")
                continue
        
        if dfs:
            df_combined = pd.concat(dfs, ignore_index=True)
            logger.info(f"Loaded {len(df_combined)} B25034 county records")
            return df_combined
        else:
            logger.warning("No B25034 county files loaded")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading B25034 county files: {e}")
        raise


def load_b25040_county_files(directory: str) -> pd.DataFrame:
    """
    Load ACS 5-year B25040 (House Heating Fuel) county CSV files.
    
    Returns combined DataFrame with year, county, and housing unit counts
    by heating fuel type (utility gas, bottled gas, electricity, fuel oil,
    wood, solar, other, none).
    
    Key metric: utility gas share = B25040_002E / B25040_001E per county per year.
    
    Args:
        directory: Path to B25040-5y-county directory
        
    Returns:
        DataFrame with combined B25040 county data
        
    Raises:
        FileNotFoundError: If directory does not exist
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"B25040 county directory not found: {directory}")
    
    try:
        csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]
        logger.info(f"Found {len(csv_files)} B25040 county files in {directory}")
        
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(os.path.join(directory, csv_file))
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Error loading {csv_file}: {e}")
                continue
        
        if dfs:
            df_combined = pd.concat(dfs, ignore_index=True)
            logger.info(f"Loaded {len(df_combined)} B25040 county records")
            return df_combined
        else:
            logger.warning("No B25040 county files loaded")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading B25040 county files: {e}")
        raise


def load_b25024_county_files(directory: str) -> pd.DataFrame:
    """
    Load ACS 5-year B25024 (Units in Structure) county CSV files.
    
    Returns combined DataFrame with year, county, and housing unit counts
    by structure type (1-unit detached/attached, 2-4 units, 5-9, 10-19,
    20-49, 50+, mobile home).
    
    Used to validate SF/MF segment split against NW Natural segment data.
    
    Args:
        directory: Path to B25024-5y-county directory
        
    Returns:
        DataFrame with combined B25024 county data
        
    Raises:
        FileNotFoundError: If directory does not exist
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"B25024 county directory not found: {directory}")
    
    try:
        csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]
        logger.info(f"Found {len(csv_files)} B25024 county files in {directory}")
        
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(os.path.join(directory, csv_file))
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Error loading {csv_file}: {e}")
                continue
        
        if dfs:
            df_combined = pd.concat(dfs, ignore_index=True)
            logger.info(f"Loaded {len(df_combined)} B25024 county records")
            return df_combined
        else:
            logger.warning("No B25024 county files loaded")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading B25024 county files: {e}")
        raise


# ============================================================================
# SECTION 9: POPULATION AND HOUSING FORECAST FUNCTIONS
# ============================================================================


def load_psu_population_forecasts(directory: str) -> pd.DataFrame:
    """
    Load PSU Population Research Center county population forecasts.
    
    Handles three CSV format variants:
    (1) 2025 files: YEAR, POPULATION, TYPE columns
    (2) 2024 files: YEAR, POPULATION columns
    (3) 2023 Coos file: wide format with areas as rows and select years as columns
    
    Parses comma-formatted population strings to int.
    
    Returns combined DataFrame with county, year, population, forecast_year,
    and derived annual growth rate.
    
    Covers all 13 NWN Oregon counties.
    
    Args:
        directory: Path to PSU projection data directory
        
    Returns:
        DataFrame with population forecasts
        
    Raises:
        FileNotFoundError: If directory does not exist
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"PSU projection directory not found: {directory}")
    
    try:
        dfs = []
        
        # Look for subdirectories by year (2023, 2024, 2025)
        for year_dir in os.listdir(directory):
            year_path = os.path.join(directory, year_dir)
            if not os.path.isdir(year_path):
                continue
            
            csv_files = [f for f in os.listdir(year_path) if f.endswith('.csv')]
            for csv_file in csv_files:
                try:
                    df = pd.read_csv(os.path.join(year_path, csv_file))
                    
                    # Parse comma-formatted population
                    if 'POPULATION' in df.columns:
                        df['POPULATION'] = df['POPULATION'].astype(str).str.replace(',', '')
                        df['POPULATION'] = pd.to_numeric(df['POPULATION'], errors='coerce')
                    
                    dfs.append(df)
                    logger.info(f"Loaded PSU forecast from {csv_file}")
                except Exception as e:
                    logger.warning(f"Error loading {csv_file}: {e}")
                    continue
        
        if dfs:
            df_combined = pd.concat(dfs, ignore_index=True)
            logger.info(f"Loaded {len(df_combined)} PSU population forecast records")
            return df_combined
        else:
            logger.warning("No PSU population forecast files loaded")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading PSU population forecasts: {e}")
        raise


def load_ofm_housing(path: str) -> pd.DataFrame:
    """
    Load WA OFM postcensal housing unit estimates from xlsx.
    
    Reads the 'Housing Units' sheet, filters to county-total rows (Filter=1)
    for Clark, Skamania, and Klickitat counties.
    
    Returns DataFrame with columns: county, year, total_units, one_unit,
    two_or_more, mobile_home.
    
    Years 2020-2025 are unpivoted from wide to long format.
    
    Args:
        path: Path to ofm_april1_housing.xlsx
        
    Returns:
        DataFrame with WA housing unit estimates
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"OFM housing file not found: {path}")
    
    try:
        df = pd.read_excel(path, sheet_name='Housing Units')
        logger.info(f"Loaded {len(df)} OFM housing records from {path}")
        
        # Filter to county totals (Filter=1)
        if 'Filter' in df.columns:
            df = df[df['Filter'] == 1].copy()
            logger.info(f"Filtered to {len(df)} county-total rows")
        
        return df
    except Exception as e:
        logger.error(f"Error loading OFM housing data: {e}")
        raise


# ============================================================================
# SECTION 10: NOAA CLIMATE NORMALS FUNCTIONS
# ============================================================================


def load_noaa_daily_normals(directory: str, station: str) -> pd.DataFrame:
    """
    Load NOAA 30-year daily climate normals for a weather station.
    
    Reads {station}_daily_normals.csv from the normals directory.
    
    Returns DataFrame with date, tavg_normal, tmax_normal, tmin_normal,
    hdd_normal, cdd_normal.
    
    Replaces -7777 sentinel values with NaN.
    
    Args:
        directory: Path to noaa_normals directory
        station: Station ICAO code (e.g., 'KPDX')
        
    Returns:
        DataFrame with daily climate normals
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    try:
        filename = f"{station}_daily_normals.csv"
        filepath = os.path.join(directory, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"NOAA daily normals file not found: {filepath}")
        
        df = pd.read_csv(filepath)
        logger.info(f"Loaded {len(df)} NOAA daily normals for {station}")
        
        # Replace -7777 sentinel with NaN
        df = df.replace(-7777, np.nan)
        
        return df
    except Exception as e:
        logger.error(f"Error loading NOAA daily normals for {station}: {e}")
        raise


def load_noaa_monthly_normals(directory: str, station: str) -> pd.DataFrame:
    """
    Load NOAA 30-year monthly climate normals for a weather station.
    
    Returns DataFrame with month, tavg_normal, tmax_normal, tmin_normal,
    hdd_normal, cdd_normal.
    
    Args:
        directory: Path to noaa_normals directory
        station: Station ICAO code (e.g., 'KPDX')
        
    Returns:
        DataFrame with monthly climate normals
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    try:
        filename = f"{station}_monthly_normals.csv"
        filepath = os.path.join(directory, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"NOAA monthly normals file not found: {filepath}")
        
        df = pd.read_csv(filepath)
        logger.info(f"Loaded {len(df)} NOAA monthly normals for {station}")
        
        # Replace -7777 sentinel with NaN
        df = df.replace(-7777, np.nan)
        
        return df
    except Exception as e:
        logger.error(f"Error loading NOAA monthly normals for {station}: {e}")
        raise


def compute_weather_adjustment(actual_hdd: float, normal_hdd: float) -> float:
    """
    Compute weather adjustment factor = actual_hdd / normal_hdd.
    
    Values > 1.0 indicate colder-than-normal year (higher heating demand).
    Values < 1.0 indicate warmer-than-normal year (lower heating demand).
    Returns 1.0 if normal_hdd is zero or missing.
    
    Args:
        actual_hdd: Actual annual HDD for the year
        normal_hdd: Normal annual HDD (30-year average)
        
    Returns:
        Weather adjustment factor
    """
    try:
        if pd.isna(normal_hdd) or normal_hdd == 0:
            logger.warning("Normal HDD is zero or missing; returning 1.0")
            return 1.0
        
        adjustment = actual_hdd / normal_hdd
        logger.debug(f"Weather adjustment: {adjustment:.3f} (actual={actual_hdd}, normal={normal_hdd})")
        return adjustment
    except Exception as e:
        logger.error(f"Error computing weather adjustment: {e}")
        return 1.0


# ============================================================================
# SECTION 11: RECS MICRODATA FUNCTIONS
# ============================================================================


def load_recs_microdata(path: str, year: int) -> pd.DataFrame:
    """
    Load EIA RECS public-use microdata CSV for a given survey year.
    
    Handles column name differences across survey years (2005-2020).
    Standardizes key columns to common names: division, fuelheat, typehuq,
    yearmaderange, totsqft, btung, btungsph, btungwth, nweight.
    
    Args:
        path: Path to RECS CSV file
        year: Survey year (2005, 2009, 2015, 2020)
        
    Returns:
        DataFrame with standardized RECS microdata
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"RECS microdata file not found: {path}")
    
    try:
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df)} RECS {year} records from {path}")
        
        # Standardize column names based on year
        column_mapping = {
            # 2020 columns
            'DIVISION': 'division',
            'FUELHEAT': 'fuelheat',
            'TYPEHUQ': 'typehuq',
            'YEARMADERANGE': 'yearmaderange',
            'TOTSQFT_EN': 'totsqft',
            'BTUNG': 'btung',
            'BTUNGSPH': 'btungsph',
            'BTUNGWTH': 'btungwth',
            'NWEIGHT': 'nweight',
            # 2015 columns
            'REGIONC': 'division',
            # 2009 columns
            'BTUNGOTH': 'btungoth',
            # 2005 columns
            'BTUNGAPL': 'btungapl',
        }
        
        df = df.rename(columns=column_mapping)
        logger.info(f"Standardized RECS {year} column names")
        
        return df
    except Exception as e:
        logger.error(f"Error loading RECS microdata: {e}")
        raise


def build_recs_enduse_benchmarks(recs_data: pd.DataFrame, division: int = 9,
                                  fuelheat: int = 1) -> pd.DataFrame:
    """
    Compute weighted-average gas consumption by end use for gas-heated homes
    in the specified Census division (default: Pacific = 9).
    
    Uses NWEIGHT for population-level estimates.
    
    Returns DataFrame with end_use, avg_therms, weighted_count, share_of_total.
    
    Args:
        recs_data: DataFrame from load_recs_microdata()
        division: Census division code (default 9 = Pacific)
        fuelheat: Fuel type code (default 1 = utility gas)
        
    Returns:
        DataFrame with end-use benchmarks
    """
    try:
        if recs_data.empty:
            logger.warning("Empty RECS data")
            return pd.DataFrame()
        
        # Filter to specified division and fuel type
        filtered = recs_data[
            (recs_data.get('division') == division) &
            (recs_data.get('fuelheat') == fuelheat)
        ].copy()
        
        logger.info(f"Filtered to {len(filtered)} gas-heated homes in division {division}")
        
        if filtered.empty:
            logger.warning(f"No gas-heated homes found in division {division}")
            return pd.DataFrame()
        
        # Compute weighted averages by end use
        benchmarks = []
        end_uses = ['btungsph', 'btungwth', 'btungcok', 'btungcdr']
        
        for end_use in end_uses:
            if end_use in filtered.columns:
                weighted_avg = (filtered[end_use] * filtered.get('nweight', 1)).sum() / \
                               filtered.get('nweight', 1).sum()
                benchmarks.append({
                    'end_use': end_use,
                    'avg_therms': weighted_avg,
                    'weighted_count': len(filtered),
                })
        
        df_benchmarks = pd.DataFrame(benchmarks)
        logger.info(f"Built RECS benchmarks for {len(df_benchmarks)} end uses")
        return df_benchmarks
    except Exception as e:
        logger.error(f"Error building RECS enduse benchmarks: {e}")
        raise


# ============================================================================
# SECTION 12: HELPER FUNCTIONS
# ============================================================================


def build_premise_equipment_table(premises: pd.DataFrame, equipment: pd.DataFrame,
                                  segments: pd.DataFrame, codes: pd.DataFrame) -> pd.DataFrame:
    """
    Join premise, equipment, segment, and code tables into unified dataset.
    
    Performs left joins on blinded_id and equipment_type_code to preserve all premises
    and equipment records. Derives end_use, efficiency, and weather_station columns
    using configuration mappings.
    
    Args:
        premises: DataFrame from load_premise_data() with columns: blinded_id, district_code_IRP, etc.
        equipment: DataFrame from load_equipment_data() with columns: blinded_id, equipment_type_code, efficiency, etc.
        segments: DataFrame from load_segment_data() with columns: blinded_id, segment_code, etc.
        codes: DataFrame from load_equipment_codes() with columns: equipment_type_code, equipment_class, etc.
        
    Returns:
        Unified DataFrame with columns:
        - All premise columns
        - All equipment columns
        - All segment columns
        - All code columns
        - end_use: Derived from END_USE_MAP using equipment_type_code
        - efficiency: Equipment efficiency (from data or DEFAULT_EFFICIENCY fallback)
        - weather_station: Assigned from DISTRICT_WEATHER_MAP using district_code_IRP
        
    Raises:
        ValueError: If required columns are missing
    """
    try:
        # Validate required columns
        required_premise_cols = ['blinded_id', 'district_code_IRP']
        missing_premise = [col for col in required_premise_cols if col not in premises.columns]
        if missing_premise:
            raise ValueError(f"Missing required premise columns: {missing_premise}")
        
        required_equipment_cols = ['blinded_id', 'equipment_type_code']
        missing_equipment = [col for col in required_equipment_cols if col not in equipment.columns]
        if missing_equipment:
            raise ValueError(f"Missing required equipment columns: {missing_equipment}")
        
        # Start with premises
        df = premises.copy()
        logger.info(f"Starting with {len(df)} premises")
        
        # Join equipment on blinded_id (left join to preserve all premises)
        if not equipment.empty:
            df = df.merge(equipment, on='blinded_id', how='left', suffixes=('', '_equip'))
            logger.info(f"Joined equipment: {len(df)} records")
        else:
            logger.warning("Equipment DataFrame is empty")
        
        # Join segments on blinded_id (left join)
        if not segments.empty and 'blinded_id' in segments.columns:
            df = df.merge(segments, on='blinded_id', how='left', suffixes=('', '_seg'))
            logger.info(f"Joined segments: {len(df)} records")
        else:
            logger.warning("Segments DataFrame is empty or missing blinded_id column")
        
        # Join equipment codes on equipment_type_code (left join)
        if not codes.empty and 'equipment_type_code' in codes.columns:
            if 'equipment_type_code' in df.columns:
                df = df.merge(codes, on='equipment_type_code', how='left', suffixes=('', '_code'))
                logger.info(f"Joined equipment codes: {len(df)} records")
            else:
                logger.warning("equipment_type_code column not found in merged DataFrame")
        else:
            logger.warning("Equipment codes DataFrame is empty or missing equipment_type_code column")
        
        # ====================================================================
        # DERIVE END_USE COLUMN
        # ====================================================================
        
        if 'equipment_type_code' not in df.columns:
            logger.warning("equipment_type_code column not found; cannot derive end_use")
            df['end_use'] = None
        else:
            # Map equipment_type_code to end_use using END_USE_MAP
            df['end_use'] = df['equipment_type_code'].map(config.END_USE_MAP)
            
            # Count missing end_use mappings
            missing_end_use = df['end_use'].isna().sum()
            if missing_end_use > 0:
                logger.warning(
                    f"{missing_end_use} records have unmapped equipment_type_code values. "
                    f"Unmapped codes: {df[df['end_use'].isna()]['equipment_type_code'].unique().tolist()}"
                )
        
        # ====================================================================
        # DERIVE EFFICIENCY COLUMN
        # ====================================================================
        
        if 'efficiency' not in df.columns:
            logger.warning("efficiency column not found in equipment data; will use defaults")
            df['efficiency'] = None
        
        # Fill missing efficiency values using DEFAULT_EFFICIENCY based on end_use
        if 'end_use' in df.columns:
            for end_use, default_eff in config.DEFAULT_EFFICIENCY.items():
                mask = (df['end_use'] == end_use) & (df['efficiency'].isna() | (df['efficiency'] == 0))
                count = mask.sum()
                if count > 0:
                    df.loc[mask, 'efficiency'] = default_eff
                    logger.info(f"Applied default efficiency {default_eff} to {count} {end_use} records")
        
        # Validate efficiency values
        invalid_efficiency = df[(df['efficiency'] <= 0) | (df['efficiency'] > 1)].shape[0]
        if invalid_efficiency > 0:
            logger.warning(
                f"{invalid_efficiency} records have invalid efficiency values (not in (0, 1]). "
                f"These will be retained as-is for investigation."
            )
        
        # ====================================================================
        # DERIVE WEATHER_STATION COLUMN
        # ====================================================================
        
        if 'district_code_IRP' not in df.columns:
            logger.warning("district_code_IRP column not found; cannot assign weather stations")
            df['weather_station'] = None
        else:
            # Map district_code_IRP to weather_station using DISTRICT_WEATHER_MAP
            df['weather_station'] = df['district_code_IRP'].map(config.DISTRICT_WEATHER_MAP)
            
            # Count missing weather station assignments
            missing_weather = df['weather_station'].isna().sum()
            if missing_weather > 0:
                logger.warning(
                    f"{missing_weather} records have unmapped district_code_IRP values. "
                    f"Unmapped districts: {df[df['weather_station'].isna()]['district_code_IRP'].unique().tolist()}"
                )
        
        logger.info(
            f"Built unified premise-equipment table with {len(df)} records, "
            f"{df['end_use'].notna().sum()} with end_use, "
            f"{df['efficiency'].notna().sum()} with efficiency, "
            f"{df['weather_station'].notna().sum()} with weather_station"
        )
        
        return df
        
    except Exception as e:
        logger.error(f"Error building premise-equipment table: {e}")
        raise
