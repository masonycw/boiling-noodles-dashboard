import pandas as pd
import sys
import os

sys.path.append(os.getcwd())
from data_loader import UniversalLoader

# Raw Data 
raw_df = pd.read_csv('data/undefined-2026_02_14.csv', header=1, low_memory=False)
if '時間' in raw_df.columns:
    raw_df['Date_Parsed'] = pd.to_datetime(raw_df['時間'], errors='coerce')
    raw_day = raw_df[raw_df['Date_Parsed'].dt.date == pd.to_datetime('2026-02-10').date()]
    print(f"Raw REPORT (undefined) Orders for Feb 10: {len(raw_day)}")
    
loader = UniversalLoader()
df_report, df_details, logs = loader.scan_and_load()

print("\n--- Logs ---")
for log in logs:
    if 'undefined-2026_02_14' in log or 'Initial REPORT' in log:
        print(log)

# Where does the filtering happen? 
# In `_clean_report`:
# invalid_statuses = ['已取消', 'cancelled', 'void', 'delete', 'deleted']
# df = df[~df['status'].isin(invalid_statuses)]
