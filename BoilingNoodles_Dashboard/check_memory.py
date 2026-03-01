import sys
import pandas as pd
from data_loader import UniversalLoader

loader = UniversalLoader()
df_report, df_details, _ = loader.scan_and_load()

print(f"Report Memory: {df_report.memory_usage(deep=True).sum() / 1e6:.2f} MB")
print(f"Details Memory: {df_details.memory_usage(deep=True).sum() / 1e6:.2f} MB")

df_report, df_details = loader.enrich_data(df_report, df_details)

print(f"Enriched Report Memory: {df_report.memory_usage(deep=True).sum() / 1e6:.2f} MB")
print(f"Enriched Details Memory: {df_details.memory_usage(deep=True).sum() / 1e6:.2f} MB")
