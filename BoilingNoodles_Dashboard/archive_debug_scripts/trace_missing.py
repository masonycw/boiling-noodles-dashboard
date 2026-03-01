import pandas as pd
import sys
import os

sys.path.append(os.getcwd())
from data_loader import UniversalLoader

# Raw details sum
df = pd.read_csv('data/Transaction Report 2026-02-15 00_00 2026-02-15 23_59.csv')
main = df[df['Product SKU'].astype(str).str.startswith(('A', 'B'))]
raw_main = main[main['Modifier Name'].isna() | (main['Modifier Name'] == '')]

print(f"Raw main dishes: {raw_main['Item Quantity'].astype(float).sum()}")

# Load via data_loader
loader = UniversalLoader()
df_report, df_details, logs = loader.scan_and_load()
df_report, df_details = loader.enrich_data(df_report, df_details)

df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
df_15 = df_report[df_report['Date_Parsed'].dt.date == pd.to_datetime('2026-02-15').date()]
order_ids = df_15['order_id'].unique()
df_det_15 = df_details[df_details['order_id'].isin(order_ids)]
loaded_main = df_det_15[df_det_15['Is_Main_Dish'] == True]

# Find the difference
raw_indices = set(raw_main.index)
# df_det_15 does not preserve original row index after concat/filter, 
# but we can match them by order_id and line item if needed, 
# or just compare order_ids that have main dishes.

raw_orders = raw_main['Order Number'].astype(str).str.strip().tolist()
loaded_orders = loaded_main['order_id'].astype(str).str.strip().tolist()

from collections import Counter
raw_counts = Counter(raw_orders)
loaded_counts = Counter(loaded_orders)

missing_orders = []
for order in raw_counts:
    if raw_counts[order] > loaded_counts.get(order, 0):
        missing_orders.append((order, raw_counts[order] - loaded_counts.get(order, 0)))

print(f"Missing orders: {missing_orders}")

for order, diff in missing_orders:
    print(f"\n--- Order: {order} ---")
    print(df[df['Order Number'].astype(str).str.strip() == order][['Order Number', 'Status', 'Overall Status', 'Product SKU', 'Item Name', 'Modifier Name', 'Item Quantity']])

