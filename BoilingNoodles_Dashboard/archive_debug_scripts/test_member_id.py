import pandas as pd
import data_loader

loader = data_loader.UniversalLoader()
df_r, df_d, logs = loader.scan_and_load()
df_r, df_d = loader.enrich_data(df_r, df_d)

print("--- Testing Hidden Phones ---")
hidden = df_r[df_r['member_phone'].astype(str).str.contains(r'\*')]
print(f"Total hidden phones found: {len(hidden)}")
if not hidden.empty:
    print("Sample Member IDs for hidden phones:")
    print(hidden[['member_phone', 'carrier_id', 'customer_name', 'Member_ID']].head(5))

print("\n--- Testing UberEats Phone ---")
ue = df_r[df_r['member_phone'].astype(str).str.contains('5594')]
print(f"Total UberEats phones found: {len(ue)}")
if not ue.empty:
    print("Sample Member IDs for UberEats phones:")
    print(ue[['member_phone', 'carrier_id', 'customer_name', 'Member_ID']].head(5))

print("\n--- Testing Carrier IDs ---")
carrier = df_r[df_r['carrier_id'].astype(str).str.len() > 4]
print(f"Total Carrier IDs found: {len(carrier)}")
if not carrier.empty:
    # Filter out ones with valid phone to see if fallback works
    carrier_only = carrier[carrier['member_phone'].astype(str).str.replace('*','').str.strip() == '']
    print(f"Carrier ONLY (No valid phone): {len(carrier_only)}")
    if not carrier_only.empty:
        print(carrier_only[['member_phone', 'carrier_id', 'customer_name', 'Member_ID']].head(5))

