import pandas as pd
from data_loader import UniversalLoader

loader = UniversalLoader()
df_report, df_details, logs = loader.scan_and_load()
print(f"Loaded {len(df_report)} report rows and {len(df_details)} details from Parquet.")

print("Report columns dtypes:")
print(df_report[['total_amount', 'people_count']].dtypes)

print("Running enrich_data...")
try:
    df_report, df_details = loader.enrich_data(df_report, df_details)
    print("Enrich data successful!")
except Exception as e:
    print(f"Error during enrich_data: {e}")
