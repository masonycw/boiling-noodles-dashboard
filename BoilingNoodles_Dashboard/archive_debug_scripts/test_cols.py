import pandas as pd
try:
    df = pd.read_csv('data/undefined-2026_02_14.csv', header=1)
    print("Columns:", df.columns.tolist())
    print("Row 0:", df.iloc[0].to_dict())
except Exception as e:
    print("Error:", e)
