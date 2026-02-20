import pandas as pd
import sys
import os

sys.path.append(os.getcwd())
from data_loader import UniversalLoader

loader = UniversalLoader()
df_report, df_details, logs = loader.scan_and_load()
df_report, df_details = loader.enrich_data(df_report, df_details)

df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
df_details['Date_Parsed'] = pd.to_datetime(df_details['date'], errors='coerce')

for d_str in ['2026-02-10', '2026-02-11']:
    target_date = pd.to_datetime(d_str).date()
    
    # Processed Data
    df_rep_day = df_report[df_report['Date_Parsed'].dt.date == target_date]
    order_ids = df_rep_day['order_id'].unique()
    df_det_day = df_details[df_details['order_id'].isin(order_ids)]
    
    # Processed Guest Count
    main_dishes = df_det_day[df_det_day['Is_Main_Dish'] == True]
    calc_visitors = main_dishes['qty'].sum()
    expected_vis = 114 if d_str == '2026-02-11' else 92
    
    # Processed Revenue
    curr_rev = df_rep_day['total_amount'].sum()
    total_orders = len(df_rep_day)
    
    print(f"\n===== Date: {d_str} =====")
    print(f"Calculated Visitors: {calc_visitors} (User Expected: {expected_vis})")
    print(f"Total Revenue: {curr_rev}")
    print(f"Valid Orders (Report): {total_orders}")
    
    # Raw Data Checks
    raw_df = pd.read_csv('data/Transaction Report 2026-01-01 00_00 2026-02-14 23_59.csv', low_memory=False)
    raw_df['Date_Parsed'] = pd.to_datetime(raw_df['Time'], errors='coerce')
    raw_day = raw_df[raw_df['Date_Parsed'].dt.date == target_date]
    
    print(f"--- Raw CSV Stats ---")
    raw_main = raw_day[raw_day['Product SKU'].astype(str).str.startswith(('A', 'B'), na=False)]
    raw_main = raw_main[raw_main['Modifier Name'].isna() | (raw_main['Modifier Name'].astype(str).str.strip() == '')]
    raw_main = raw_main[raw_main['Overall Status'].astype(str).str.lower() == 'completed']
    print(f"Raw Completed Main Dishes (qty sum): {raw_main['Item Quantity'].astype(float).sum()}")
    
    raw_orders = raw_day[raw_day['Item Name'].isna() | (raw_day['Item Name'] == '')] 
    # Because Report rows typically have empty Item Name in this specific POS format
    # Wait, lets check if Order Total exists
    raw_completed_orders = raw_day[(raw_day['Overall Status'].astype(str).str.lower() == 'completed') & (raw_day['Order Total(TWD)'].notna())]
    raw_completed_orders = raw_completed_orders.drop_duplicates(subset=['Order Number'])
    
    print(f"Raw Completed Revenue: {raw_completed_orders['Order Total(TWD)'].astype(float).sum()}")
    print(f"Raw Completed Orders: {len(raw_completed_orders)}")

