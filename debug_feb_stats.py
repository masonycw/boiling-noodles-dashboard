import pandas as pd
from data_loader import UniversalLoader

def check_feb_visitors():
    print("--- Checking Feb 2026 Visitor Count ---")
    loader = UniversalLoader()
    df_report, _, _ = loader.scan_and_load()
    df_report, _ = loader.enrich_data(df_report, pd.DataFrame())
    
    # Filter Feb 2026
    mask = (df_report['Date_Parsed'] >= "2026-02-01") & (df_report['Date_Parsed'] <= "2026-02-28 23:59:59")
    df_feb = df_report[mask].copy()
    
    print(f"Feb Rows: {len(df_feb)}")
    
    if 'people_count' in df_feb.columns:
        val = df_feb['people_count'].sum()
        print(f"Feb People Count Sum: {val}")
    else:
        print("Column 'people_count' NOT FOUND in Feb data.")
        print("Columns:", df_feb.columns.tolist())

if __name__ == "__main__":
    check_feb_visitors()
