# Data Directory — Required Files

This directory contains all input data for the NW Natural End-Use Forecasting Model. Files are organized by source and purpose.

> **Note:** Most files are excluded from version control (`.gitignore`) because they contain proprietary NW Natural data or large public datasets. This README documents what's needed so collaborators can populate the directory.

---

## Status Legend

- ✅ = Present
- 📄 = Documentation only (not used in model logic)

---

## NW Natural Proprietary Data

**Directory:** `NWNatural Data/`

These are blinded extracts from NW Natural's internal systems. Required for the core simulation.

| Status | File | Description |
|--------|------|-------------|
| ✅ | `premise_data_blinded.csv` | Premise-level records (location, vintage, segment) |
| ✅ | `equipment_data_blinded.csv` | Equipment inventory per premise (type, age, fuel) |
| ✅ | `equipment_codes.csv` | Equipment type code → end-use category mapping |
| ✅ | `segment_data_blinded.csv` | Segment classification (RESSF, RESMF, etc.) |
| ✅ | `billing_data_blinded.csv` | Monthly billing data for calibration |
| ✅ | `small_billing_data_blinded.csv` | Smaller billing sample for quick testing |
| ✅ | `DailyCalDay1985_Mar2025.csv` | Daily calendar-day weather (HDD) 1985–2025 |
| ✅ | `DailyGasDay2008_Mar2025.csv` | Daily gas-day weather (HDD) 2008–2025 |
| ✅ | `BullRunWaterTemperature.csv` | Bull Run water temperature (water heating calc) |
| ✅ | `Portland_snow.csv` | Portland snow data (weather normalization) |

---

## IRP Load Decay Forecast

**Directory:** `Data/` (root)

| Status | File | Description |
|--------|------|-------------|
| ✅ | `10-Year Load Decay Forecast (2025–2035).csv` | NW Natural IRP 10-year UPC decay projection (648 therms base, -1.19%/yr) |
| ✅ 📄 | `prior load decay data description.txt` | Documentation of historical load decay methodology |
| ✅ 📄 | `prior load decay data reconstructed.txt` | Reconstructed historical decay rates |
| ✅ 📄 | `prior load decay data simulated.txt` | Simulated decay scenarios |
| ✅ 📄 | `Integrated Resource Plan (IRP),.txt` | IRP context and planning assumptions |

> **Fallback:** If the CSV is missing, the model uses an embedded fallback (648 therms/customer in 2025, -1.19% annual decay).

---

## ASHRAE Equipment Data

**Directory:** `Data/ashrae/`

Service life and maintenance cost data from ASHRAE for equipment replacement modeling.

| Status | File | Description |
|--------|------|-------------|
| ✅ | `OR-ASHRAE_Service_Life_Data.xls` | Oregon equipment service life distributions |
| ✅ | `WA-ASHRAE_Service_Life_Data.xls` | Washington equipment service life distributions |
| ✅ | `OR-ASHRAE_Maintenance_Cost_Data.xls` | Oregon maintenance cost curves |
| ✅ | `WA-ASHRAE_Maintenance_Cost_Data.xls` | Washington maintenance cost curves |

> **Fallback:** Model uses hardcoded `USEFUL_LIFE` defaults (e.g., furnace=20yr, water heater=13yr).

---

## Rate and Tariff Data

**Directory:** `Data/`

Historical and current residential gas rates for cost analysis.

| Status | File | Description |
|--------|------|-------------|
| ✅ | `or_rate_case_history.csv` | Oregon rate case history |
| ✅ | `or_rates_oct_2025.csv` | Oregon Schedule 2 rates (Oct 2025) |
| ✅ | `or_wacog_history.csv` | Oregon WACOG (weighted avg cost of gas) history |
| ✅ | `wa_rate_case_history.csv` | Washington rate case history |
| ✅ | `wa_rates_nov_2025.csv` | Washington Schedule 2 rates (Nov 2025) |
| ✅ | `wa_wacog_history.csv` | Washington WACOG history |

> **Fallback:** Model uses hardcoded current rates ($1.41/therm OR, $1.24/therm WA). Not required for core forecast.

---

## RBSA 2022 (Residential Building Stock Assessment)

**Directory:** `Data/2022 RBSA Datasets/`

NEEA's 2022 Residential Building Stock Assessment for the Pacific Northwest.

| Status | File | Description |
|--------|------|-------------|
| ✅ | `SiteDetail.csv` | Site-level building characteristics |
| ✅ | `Mechanical_HeatingAndCooling.csv` | HVAC equipment inventory |
| ✅ | `Mechanical_WaterHeater.csv` | Water heater equipment data |
| ✅ | `Appliance_Stove_Oven.csv` | Cooking appliance data |
| ✅ | `Appliance_Laundry.csv` | Clothes dryer data |
| ✅ | `Building_Shell_One_Line.csv` | Building envelope characteristics |

> **Fallback:** Model uses default equipment distributions. Affects calibration accuracy but not core simulation.

---

## EIA RECS Microdata (Residential Energy Consumption Survey)

**Directory:** `Data/Residential Energy Consumption Survey/`

Used to compute dynamic non-heating end-use ratios (water heating, cooking, etc.) relative to space heating.

| Status | File | Description |
|--------|------|-------------|
| ✅ | `recs2020_public_v7.csv` | 2020 RECS microdata (primary) |
| ✅ | `recs2015_public_v4.csv` | 2015 RECS microdata |
| ✅ | `2009/recs2009_public.csv` | 2009 RECS microdata |
| ✅ | `2005/RECS05alldata.csv` | 2005 RECS microdata |

> **Fallback:** Model uses hardcoded non-heating ratios: water heating 41%, cooking 8%, clothes drying 5%, fireplace 7%, other 3%.

---

## Census and Housing Projections

**Directory:** `Data/`

Census ACS data and state housing forecasts for demographic enrichment.

| Status | File | Description |
|--------|------|-------------|
| ✅ | `NW Natural Service Territory Census data.csv` | Service territory FIPS codes and Census geography |
| ✅ | `ofm_april1_housing.xlsx` | Washington OFM April 1 housing estimates |

**Subdirectories** (Census ACS 5-year county-level tables):
- `B25034-5y/` — Year Structure Built (vintage distribution)
- `B25034-5y-county/` — County-level vintage data
- `B25040-5y-county/` — House Heating Fuel by county
- `B25024-5y-county/` — Units in Structure by county (SF/MF split)
- `PSU projection data/` — Portland State University population forecasts

> **Fallback:** Model uses config-level segment multipliers and skips census enrichment if `use_census_enrichment=true` but data is missing.

---

## NW Energy Proxies and Envelope Efficiency

**Directory:** `Data/`

Calibration parameters for building envelope thermal performance and equipment efficiency trajectories.

| Status | File | Description |
|--------|------|-------------|
| ✅ | `nw_energy_proxies.csv` | Compact parameter set for NW building stock |
| ✅ | `nw_energy_proxies.py` | Python loader/constants for proxies |
| ✅ | `nw_energy_proxies explanation.txt` | Documentation of proxy derivation |
| ✅ | `building_envelope_efficiency_index.csv` | Envelope UA values by vintage/type |
| ✅ | `equipment_afue_trajectory.csv` | AFUE improvement trajectory over time |
| ✅ | `segment_heating_multipliers.csv` | Segment-based heating factor multipliers |

> **Fallback:** Model uses hardcoded vintage/segment multipliers from `config.py`.

---

## Baseload Consumption Factors

**Directory:** `Data/`

Non-heating baseload consumption by end-use category.

| Status | File | Description |
|--------|------|-------------|
| ✅ | `Baseload Consumption Factors.csv` | Annual baseload therms by end-use |
| ✅ | `Baseload Consumption factors.py` | Python constants for baseload |
| ✅ | `Baseload Consumption factors explanation.txt` | Methodology documentation |

> **Fallback:** Model uses RECS-derived ratios or hardcoded defaults for non-heating end-uses.

---

## RBSA 2017 and Metering Data (Future Work)

**Directory:** `Data/`

Earlier RBSA vintage and sub-metered end-use data for temporal comparison. Not currently used in production model.

| Status | File | Description |
|--------|------|-------------|
| ✅ 📄 | `2017-RBSA-II-Database-User-Manual.pdf` | RBSA-II database documentation |
| ✅ | `2017-RBSA-II-Combined-Database/` | Full 2017 RBSA-II dataset (directory) |
| ✅ | `Future Work/rbsam_y1/` | RBSA metering Year 1 sub-metered data |
| ✅ | `Future Work/rbsam_y2/` | RBSA metering Year 2 sub-metered data |
| ✅ | `Future Work/rbsa-metering-data-dictionary-2016-2017.xlsx` | Metering data dictionary |

> **Fallback:** Not used in current model. Reserved for future end-use disaggregation work.

---

## NOAA Climate Normals

**Directory:** `Data/noaa_normals/`

30-year climate normals for weather normalization. Downloaded via NOAA CDO API.

| Status | File | Description |
|--------|------|-------------|
| — | `*.csv` (per station) | Station-level monthly/annual HDD normals |

> **Fallback:** Model uses actual weather data from NW Natural files. Normals are used for weather normalization adjustments only.

---

## Equipment Documentation

**Directory:** `Data/`

| Status | File | Description |
|--------|------|-------------|
| ✅ 📄 | `equipment life math.txt` | Equipment life calculation methodology |

---

## Summary

| Category | Files | Status |
|----------|-------|--------|
| NW Natural core data | 10 | ✅ All present |
| IRP forecast | 1 | ✅ Present (embedded fallback also available) |
| ASHRAE equipment life | 4 | ✅ All present |
| Rate/tariff data | 6 | ✅ All present |
| RBSA 2022 | 6 | ✅ All present |
| RECS microdata | 4 | ✅ All present |
| Census/housing | 2+ dirs | ✅ All present |
| Energy proxies/envelope | 6 | ✅ All present |
| Baseload factors | 3 | ✅ All present |
| NOAA normals | 22 | ✅ All present |
| PSU projections | dir | ✅ All present |
| Documentation | 5 | ✅ All present |
