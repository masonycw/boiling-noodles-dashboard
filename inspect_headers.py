import pandas as pd
import os
import config

print("--- Data Directory Scan & Header Inspection ---")
for root_dir in config.DATA_DIRS:
    if not os.path.exists(root_dir):
        print(f"[SKIP] Missing: {root_dir}")
        continue
        
    print(f"[SCAN] {root_dir}")
    for current_root, dirs, files in os.walk(root_dir):
        for f in sorted(files):
            if not f.endswith(".csv"): continue
            
            full_path = os.path.join(current_root, f)
            print(f"\n📄 File: {f}")
            try:
                # Try reading with default utf-8
                df = pd.read_csv(full_path, nrows=1)
                print(f"   Encoding: utf-8")
                print(f"   Raw Columns: {list(df.columns)}")

                # Check for messy header
                col0 = str(df.columns[0])
                if len(col0) > 20 and any(c.isdigit() for c in col0):
                    print("   ⚠️  Messy Header detected (Row 0 looks like metadata)")
                    df_h1 = pd.read_csv(full_path, header=1, encoding='utf-8-sig') # Try header=1
                    print(f"   ➡️  Columns with header=1: {list(df_h1.columns)}")
                
                # Check for BOM/Encoding issues by re-reading with utf-8-sig
                df_sig = pd.read_csv(full_path, nrows=1, encoding='utf-8-sig')
                if list(df.columns) != list(df_sig.columns):
                    print(f"   ⚠️  Difference with utf-8-sig: {list(df_sig.columns)}")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
