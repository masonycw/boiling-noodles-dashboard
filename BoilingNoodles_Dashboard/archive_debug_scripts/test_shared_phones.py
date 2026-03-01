import pandas as pd
import data_loader

loader = data_loader.UniversalLoader()
df_r, df_d, logs = loader.scan_and_load()
df_r, df_d = loader.enrich_data(df_r, df_d)

if df_r.empty:
    print("No data")
    exit()

# Look for phone numbers that appear with many different names
df_r['phone_clean'] = df_r['member_phone'].astype(str).str.strip().str.replace(' ', '')
df_r = df_r[df_r['phone_clean'].str.len() >= 6]
df_r = df_r[~df_r['phone_clean'].str.contains(r'\*')]
df_r = df_r[df_r['phone_clean'] != 'nan']

# Group by phone and count unique names
shared = df_r.groupby('phone_clean')['customer_name'].nunique().reset_index()
shared = shared.sort_values('customer_name', ascending=False)
print("--- Top 10 Phones by Number of Unique Names ---")
print(shared.head(10))

print("\n--- Examples of names for top 3 shared phones ---")
for p in shared.head(3)['phone_clean']:
    names = df_r[df_r['phone_clean'] == p]['customer_name'].unique()
    print(f"Phone {p} has {len(names)} names. Samples: {names[:5]}")

