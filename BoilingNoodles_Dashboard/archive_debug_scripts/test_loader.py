import data_loader

loader = data_loader.UniversalLoader()
df_r, df_d, logs = loader.scan_and_load()

print("Report Unique Statuses:")
if 'status' in df_r.columns:
    print(df_r['status'].unique())
else:
    print("No status column in Report")

print("\nDetails Unique Statuses:")
if 'status' in df_d.columns:
    print(df_d['status'].unique())
else:
    print("No status column in Details")
