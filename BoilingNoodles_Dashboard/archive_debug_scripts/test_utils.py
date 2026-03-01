import pandas as pd
from views.utils import render_date_filter
import data_loader

loader = data_loader.UniversalLoader()
df_r, df_d, logs = loader.scan_and_load()
df_r, df_d = loader.enrich_data(df_r, df_d)

# Mock passing '上個月 (Last Month)' to utils.py manually
# Actually just use hardcoded dates to see if filtering dataframe matches
# The issue is in app.py or operational.py when doing:
# mask_rep = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)

start_date = pd.to_datetime('2026-01-01')
end_date = pd.to_datetime('2026-01-31') + pd.Timedelta(days=1, seconds=-1)

mask_rep = (df_r['Date_Parsed'] >= start_date) & (df_r['Date_Parsed'] <= end_date)
df_rep = df_r.loc[mask_rep]

print("Test Total Revenue with modified boundary:", df_rep['total_amount'].sum())
