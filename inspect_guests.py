import pandas as pd
from data_loader import UniversalLoader

loader = UniversalLoader()
df_report, df_details, logs = loader.scan_and_load()
df_report, df_details = loader.enrich_data(df_report, df_details)

mask_det = (df_details['Date_Parsed'].dt.month == 2) & (df_details['Date_Parsed'].dt.year == 2026)
df_det_feb = df_details[mask_det]
main_dishes = df_det_feb[df_det_feb['Is_Main_Dish']]

# Check for exact duplicates in main dishes
dupes = main_dishes[main_dishes.duplicated(keep=False)]
print("Total exact duplicate rows in main dishes:", len(main_dishes[main_dishes.duplicated()]))
if len(dupes) > 0:
    print(dupes[['Date_Parsed', 'order_id', 'item_name', 'qty']].sort_values(['order_id', 'item_name']))
