import pandas as pd
raw = pd.read_csv('data/undefined-2026_02_14.csv', header=1)
raw['日期'] = pd.to_datetime(raw['時間']).dt.date

# Check 1/2 orders 1141, 1142
t2 = pd.to_datetime('2026-01-02').date()
raw2 = raw[raw['日期'] == t2]
print("1/2 Orders 1141, 1142:")
print(raw2[(raw2['單號'] == 1141) | (raw2['單號'] == 1142)].to_dict('records'))

# Check 1/11 orders that might sum to 1010 and 6 visitors
t11 = pd.to_datetime('2026-01-11').date()
raw11 = raw[raw['日期'] == t11]
# Let's print all remarks or unusual employees
print("\n1/11 Remarks:")
print(raw11[raw11['訂單備註'].notna()][['單號', '總計', '人數', '訂單備註']].to_dict('records'))

print("\n1/11 Employees:")
print(raw11.groupby('員工')['總計'].sum())

# Let's see if any order has 100% discount, or "test" in notes
test_orders = raw[raw['訂單備註'].astype(str).str.contains('測試|test|員工|招待', na=False, case=False)]
print("\nTest/Employee/Comp Orders:")
print(test_orders[['日期', '單號', '總計', '人數', '訂單備註']].to_dict('records'))

# Let's check 1/11 discrepancy again: 1010, 6 visitors.
# Could it be an order that was canceled but still recorded here?
# Let's look at raw11['狀態']
print("\n1/11 Statuses:")
print(raw11.groupby('狀態')['總計'].sum())
