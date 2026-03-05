import pandas as pd
from data_loader import UniversalLoader

loader = UniversalLoader()
df_report, df_details, logs = loader.scan_and_load()
df_report, df_details = loader.enrich_data(df_report, df_details)

# Look at 2/8 main dishes again
mask_det_28 = (df_details['Date_Parsed'].dt.month == 2) & (df_details['Date_Parsed'].dt.year == 2026) & (df_details['Date_Parsed'].dt.day == 8)
det_28 = df_details[mask_det_28].copy()

# A and B only, excluding modifiers
mains = det_28[(det_28['category'].isin(['A 湯麵', 'B 拌麵飯'])) & (~det_28['Is_Modifier'])]
print("A+B Mains Qty:", mains['qty'].sum())

# Let's see what these mains are
print(mains.groupby('item_name')['qty'].sum())

# Wait, were there exactly 3 A/B items that should be excluded?
print(mains[mains['status'] != 'completed']['qty'].sum())

# Look at 'status' in detail?
# What about 'order_type'?
