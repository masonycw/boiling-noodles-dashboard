import pandas as pd
raw = pd.read_csv('data/undefined-2026_02_14.csv', header=1)
raw['日期'] = pd.to_datetime(raw['時間']).dt.date

# Filter only '已完成'
df_completed = raw[raw['狀態'] == '已完成']
daily_completed = df_completed.groupby('日期')['總計'].sum().to_dict()

user_records = {
    pd.to_datetime('2026-01-01').date(): 49455,
    pd.to_datetime('2026-01-02').date(): 26849,
    pd.to_datetime('2026-01-03').date(): 42420,
    pd.to_datetime('2026-01-04').date(): 43859,
    pd.to_datetime('2026-01-05').date(): 25165,
    pd.to_datetime('2026-01-06').date(): 33426,
    pd.to_datetime('2026-01-07').date(): 32562,
    pd.to_datetime('2026-01-08').date(): 23104,
    pd.to_datetime('2026-01-09').date(): 25647,
    pd.to_datetime('2026-01-10').date(): 43332,
    pd.to_datetime('2026-01-11').date(): 44215,
    pd.to_datetime('2026-01-12').date(): 28269,
    pd.to_datetime('2026-01-13').date(): 23725,
    pd.to_datetime('2026-01-14').date(): 25031,
}

print("Comparison for '已完成' orders:")
for d, u_val in user_records.items():
    c_val = daily_completed.get(d, 0)
    print(f"{d}: User={u_val}, Completed={c_val}, Match={u_val == c_val}")

print("\nWhat is '已關閉' about?")
df_closed = raw[raw['狀態'] == '已關閉']
print(df_closed.head(5)[['單號', '時間', '總計', '付款方式', '電子發票號']].to_dict('records'))
