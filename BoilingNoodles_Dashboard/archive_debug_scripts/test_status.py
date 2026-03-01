import pandas as pd
df = pd.read_csv('data/undefined-2026_02_14.csv')
print("Columns:", df.columns.tolist())
if '狀態' in df.columns: print("狀態 unique:", df['狀態'].unique())
if '狀態' not in df.columns and 'Status' in df.columns: print("Status unique:", df['Status'].unique())
