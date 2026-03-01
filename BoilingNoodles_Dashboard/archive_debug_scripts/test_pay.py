import pandas as pd
raw = pd.read_csv('data/undefined-2026_02_14.csv', header=1)
raw['日期'] = pd.to_datetime(raw['時間']).dt.date
target_date = pd.to_datetime('2026-01-11').date()
raw_jan11 = raw[raw['日期'] == target_date]

print("Revenue by Payment Method (付款方式):")
print(raw_jan11.groupby('付款方式')['總計'].sum())

# Let's check 1/1 as well to see if there's a pattern
target_date_1 = pd.to_datetime('2026-01-01').date()
raw_jan1 = raw[raw['日期'] == target_date_1]
print("\n1/1 Revenue by Payment Method:")
print(raw_jan1.groupby('付款方式')['總計'].sum())

# Also check 1/2
target_date_2 = pd.to_datetime('2026-01-02').date()
raw_jan2 = raw[raw['日期'] == target_date_2]
print("\n1/2 Revenue by Payment Method:")
print(raw_jan2.groupby('付款方式')['總計'].sum())

# Let's print out the exact orders for the diff on 1/11 (1010) and 1/2 (155)
df_diff11 = raw_jan11[raw_jan11['總計'] == 1010]
if not df_diff11.empty:
    print(f"\nExact 1010 order found on 1/11: {df_diff11[['單號', '總計', '人數']].to_dict('records')}")
    
df_diff2 = raw_jan2[raw_jan2['總計'] == 155]
if not df_diff2.empty:
    print(f"\nExact 155 order found on 1/2: {df_diff2[['單號', '總計', '人數']].to_dict('records')}")
    
# Check combinations
# E.g., for 1/2, diff is 155, diff vis is 1. Is there ANY order with 155 and 1 visitor?
print(f"\nOrders with 155 and 1 visitor on 1/2: {raw_jan2[(raw_jan2['總計'] == 155) & (raw_jan2['人數'] == 1)][['單號', '總計', '人數']].to_dict('records')}")

# E.g., for 1/11, diff is 1010, diff vis is 6. Is there a combination? Let's just list sizes of 6
print(f"\nOrders with 6 visitors on 1/11: {raw_jan11[raw_jan11['人數'] == 6][['單號', '總計', '人數']].to_dict('records')}")

