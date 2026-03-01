import pandas as pd
import data_loader

loader = data_loader.UniversalLoader()
df_r, df_d, logs = loader.scan_and_load()
df_r, df_d = loader.enrich_data(df_r, df_d)

if df_r.empty:
    print("No data")
    exit()

print("\n--- Testing UberEats Auto-Detection Logic ---")
ue_members = df_r[df_r['Member_ID'].astype(str).str.startswith('UE_')]
print(f"Total UE_ entries found: {len(ue_members)}")

if not ue_members.empty:
    # Let's display how many unique UE members we found and some sample names/phones
    unique_ue = ue_members.drop_duplicates(subset=['Member_ID'])
    print(f"Total Unique UE_ Member IDs: {len(unique_ue)}")
    print("\nSample UE Member entries (first 10 unique):")
    print(unique_ue[['member_phone', 'customer_name', 'Member_ID']].head(10))

    # Also check if exactly 77519126 and 55941277 were caught
    p1 = df_r[df_r['member_phone'].astype(str).str.contains('77519126')]
    p2 = df_r[df_r['member_phone'].astype(str).str.contains('55941277')]

    print(f"\nEntries with 77519126: {len(p1)}. Sample Member IDs: {p1['Member_ID'].unique()[:5]}")
    print(f"Entries with 55941277: {len(p2)}. Sample Member IDs: {p2['Member_ID'].unique()[:5]}")
