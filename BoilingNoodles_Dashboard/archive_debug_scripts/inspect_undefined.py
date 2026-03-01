import pandas as pd
import sys
import os

df = pd.read_csv('data/undefined-2026_02_14.csv', header=1, low_memory=False)
order_counts = df['單號'].value_counts()
print(f"Top 5 orders with most rows:")
print(order_counts.head())

top_order = order_counts.index[0]
print(f"\n--- Look at order {top_order} ---")
sample = df[df['單號'] == top_order]
print(sample[['單號', '時間', '總計', '狀態', '人數']])
