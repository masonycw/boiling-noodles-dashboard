import pandas as pd
import sys
import os

sys.path.append(os.getcwd())
from data_loader import UniversalLoader

loader = UniversalLoader()
df_report, df_details, logs = loader.scan_and_load()
df_report, df_details = loader.enrich_data(df_report, df_details)

df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
df_15 = df_report[df_report['Date_Parsed'].dt.date == pd.to_datetime('2026-02-15').date()]
order_ids = df_15['order_id'].unique()
df_det_15 = df_details[df_details['order_id'].isin(order_ids)]

main_dishes = df_det_15[df_det_15['Is_Main_Dish'] == True]
print(f"Calculated Visitors: {main_dishes['qty'].sum()}, Should be: 143")

not_main = df_det_15[df_det_15['Is_Main_Dish'] == False]

# Look for items with A or B SKU, no options, but combo item?
rejected_ab = not_main[not_main['sku'].astype(str).str.startswith(('A', 'B'))]
combo_ab = rejected_ab[rejected_ab['item_type'].astype(str).str.contains('Combo Item', case=False, na=False)]
print("\n--- Combo Items with SKU A or B ---")
combo_summary = combo_ab.groupby(['sku', 'item_name', 'item_type'])['qty'].sum().reset_index()
print(combo_summary)

# Are there any other A/B items that were rejected?
print("\n--- Other A/B items rejected (No options) ---")
no_opt_ab = rejected_ab[
    (rejected_ab['options'].isna() | (rejected_ab['options'].astype(str).str.strip() == '')) &
    (~rejected_ab['item_type'].astype(str).str.contains('Combo Item', case=False, na=False))
]
print(no_opt_ab[['sku', 'item_name', 'item_type', 'qty']])

# Check the user conversation summary:
# "Item Type如果是Combo Item則是套餐名稱，不計算在主食" => Wait.
# Ah! "Item Type如果是Combo Item則是套餐名稱，不計算在主食". 
# But wait, what if the main dish is INSIDE the combo? Then its item type is "Single Item in Combo Item", NOT "Combo Item"!
# "Single Item in Combo Item" DOES NOT contain "Combo Item"? Yes it does! "Single Item in Combo Item" CONTAINS "Combo Item"!!!
print("\n--- Single Item in Combo Item that WERE included ---")
included_combo_items = main_dishes[main_dishes['item_type'].str.contains('Combo Item', na=False)]
summary_included = included_combo_items.groupby(['sku', 'item_name', 'item_type'])['qty'].sum().reset_index()
print(summary_included)
