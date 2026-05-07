"""Build historical rate table and convert billing dollars to therms."""
import logging, pandas as pd
from src import config
from src.loaders._helpers import save_diagnostics

logger = logging.getLogger(__name__)

def build_historical_rate_table(rate_cases: pd.DataFrame, wacog: pd.DataFrame,
                                current_rate: float, state: str) -> pd.DataFrame:
    if rate_cases.empty or wacog.empty:
        return pd.DataFrame([{'effective_date': pd.Timestamp('2025-01-01'),
                              'rate_per_therm': current_rate, 'state': state}])
    rc = rate_cases.dropna(subset=['Date Effective', 'Granted Percent']).sort_values('Date Effective', ascending=False)
    wc = wacog.dropna(subset=['Effective Date', 'Rate per Therm']).sort_values('Effective Date', ascending=False)
    current_wacog = wc.iloc[0]['Rate per Therm'] if not wc.empty else 0.0
    base = current_rate - current_wacog
    rows = [{'effective_date': pd.Timestamp('2025-01-01'), 'base_rate': base,
             'wacog': current_wacog, 'rate_per_therm': current_rate, 'state': state}]
    for _, case in rc.iterrows():
        granted = case['Granted Percent']
        if pd.notna(granted) and granted != 0:
            base = base / (1.0 + granted)
        eff_date = case['Date Effective']
        w_rows = wc[wc['Effective Date'] <= eff_date]
        w = w_rows.iloc[0]['Rate per Therm'] if not w_rows.empty else current_wacog
        rows.append({'effective_date': eff_date, 'base_rate': base, 'wacog': w,
                     'rate_per_therm': base + w, 'state': state})
    return pd.DataFrame(rows).sort_values('effective_date').reset_index(drop=True)

def convert_billing_to_therms(billing: pd.DataFrame, rate_table: pd.DataFrame) -> pd.DataFrame:
    if billing.empty:
        return billing
    df = billing.copy()
    if rate_table.empty:
        df['estimated_therms'] = df['utility_usage'] / config.OR_CURRENT_RATE
    else:
        latest = rate_table.sort_values('effective_date').iloc[-1]['rate_per_therm']
        df['estimated_therms'] = df['utility_usage'] / latest
    return df

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    from src.loaders.load_rate_case_history import load_rate_case_history
    from src.loaders.load_wacog_history import load_wacog_history
    try:
        or_rc = load_rate_case_history(config.OR_RATE_CASE_HISTORY)
        or_wacog = load_wacog_history(config.OR_WACOG_HISTORY)
        or_table = build_historical_rate_table(or_rc, or_wacog, config.OR_CURRENT_RATE, 'OR')
        print(f"  OR rate table: {len(or_table)} entries, ${or_table['rate_per_therm'].min():.4f}-${or_table['rate_per_therm'].max():.4f}")
        save_diagnostics(or_table, "historical_rate_table_or")
    except FileNotFoundError as e:
        print(f"  Skipped: {e}")
