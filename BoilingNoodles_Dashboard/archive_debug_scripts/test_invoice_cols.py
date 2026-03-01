import pandas as pd
import glob
import os

invoice_files = glob.glob('data/電子發票/*.csv')
if not invoice_files:
    # Try looking for other filenames containing 發票
    invoice_files = glob.glob('data/*發票*.csv')

if invoice_files:
    latest = max(invoice_files, key=os.path.getctime)
    print(f"Loading {latest}")
    try:
        # Might need a different header row
        df = pd.read_csv(latest, nrows=5)
        print("Columns found (Header 0):", df.columns.tolist())
        
        # Sometimes header is 1 or 2
        df2 = pd.read_csv(latest, header=1, nrows=5)
        print("Columns found (Header 1):", df2.columns.tolist())
        
        df3 = pd.read_csv(latest, header=2, nrows=5)
        print("Columns found (Header 2):", df3.columns.tolist())
    except Exception as e:
        print("Error reading:", e)
else:
    print("No invoice files found in data/")
