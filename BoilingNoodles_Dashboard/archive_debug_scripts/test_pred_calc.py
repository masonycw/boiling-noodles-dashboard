import pandas as pd
import data_loader
from views import prediction

loader = data_loader.UniversalLoader()
df_r, df_d, logs = loader.scan_and_load()
df_r, df_d = loader.enrich_data(df_r, df_d)

if df_r.empty:
    print("No data")
    exit()

df = df_r[df_r['Date_Parsed'].notna()].copy()
daily_rev = df.set_index('Date_Parsed').resample('D')['total_amount'].sum().reset_index()
daily_rev['Date_Only'] = daily_rev['Date_Parsed'].dt.date
daily_rev['total_amount'] = daily_rev['total_amount'].fillna(0)

max_date = daily_rev['Date_Only'].max()

import holidays
tw_holidays = holidays.country_holidays('TW', years=[max_date.year, max_date.year + 1])
daily_rev['Is_Holiday'] = daily_rev['Date_Only'].apply(lambda d: prediction.is_holiday_tw(d, tw_holidays))

for days_lookback in [14, 28]:
    start_ref_date = max_date - pd.Timedelta(days=days_lookback - 1)
    ref_df = daily_rev[(daily_rev['Date_Only'] >= start_ref_date) & (daily_rev['Date_Only'] <= max_date)]

    past_wd = ref_df[~ref_df['Is_Holiday']]
    past_hol = ref_df[ref_df['Is_Holiday']]

    avg_wd_rev = past_wd['total_amount'].mean() if len(past_wd) > 0 else 0
    avg_hol_rev = past_hol['total_amount'].mean() if len(past_hol) > 0 else 0

    print(f"\n--- Lookback: {days_lookback} days ---")
    print(f"Start: {start_ref_date}, End: {max_date}")
    print(f"Num WD: {len(past_wd)}, Num HOL: {len(past_hol)}")
    print(f"Avg WD: {avg_wd_rev:,.2f}")
    print(f"Avg HOL: {avg_hol_rev:,.2f}")

    if days_lookback == 28:
        print("\n--- Any 0 revenue days in 28 days? ---")
        zero_days = ref_df[ref_df['total_amount'] == 0]
        if not zero_days.empty:
            print(zero_days[['Date_Only', 'Is_Holiday', 'total_amount']])
        else:
            print("No zero revenue days in 28 days.")
