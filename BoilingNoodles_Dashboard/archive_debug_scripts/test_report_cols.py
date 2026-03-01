import pandas as pd
import data_loader

loader = data_loader.UniversalLoader()
df_r, df_d, logs = loader.scan_and_load()
df_r, df_d = loader.enrich_data(df_r, df_d)

print("Report Columns:", df_r.columns.tolist())
