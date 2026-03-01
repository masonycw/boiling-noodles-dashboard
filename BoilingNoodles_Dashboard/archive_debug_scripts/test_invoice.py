import pandas as pd
import glob
import os

invoice_files = glob.glob('data/*發票*.csv') + glob.glob('data/*invoice*.csv')
if invoice_files:
    latest = max(invoice_files, key=os.path.getctime)
    print(f"Loading {latest}")
    try:
        # Load exactly as is
        df = pd.read_csv(latest, nrows=5)
        print("Columns found (Header 0):", df.columns.tolist())
        
        df2 = pd.read_csv(latest, header=1, nrows=5)
        print("Columns found (Header 1):", df2.columns.tolist())
    except Exception as e:
        print("Error reading:", e)
else:
    print("No invoice files found in data/")
