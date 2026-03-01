import pandas as pd

try:
    df = pd.read_csv('google_sheet_data.csv')
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        min_date = df['date'].min()
        max_date = df['date'].max()
        print(f"Date Range: {min_date} to {max_date}")
        print(f"Row Count: {len(df)}")
    else:
        print("Column 'date' not found. Columns are:", df.columns)
except Exception as e:
    print(f"Error: {e}")
