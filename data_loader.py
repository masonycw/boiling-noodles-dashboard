import os
import pandas as pd
import numpy as np
import config

class UniversalLoader:
    def __init__(self):
        self.report_data = [] # List of DataFrames
        self.details_data = [] # List of DataFrames
        self.debug_logs = []
        self.seen_files = set()

    def log(self, message):
        self.debug_logs.append(message)
        print(message) # Also print to console for dev

    def scan_and_load(self):
        """Scans all configured directories and loads valid CSV files."""
        self.report_data = []
        self.details_data = []
        self.debug_logs = []
        self.seen_files = set()

        for root_dir in config.DATA_DIRS:
            if not os.path.exists(root_dir):
                self.log(f"Skipping missing directory: {root_dir}")
                continue

            for current_root, dirs, files in os.walk(root_dir):
                if '/.' in current_root: continue # Skip hidden dirs

                for f in sorted(files):
                    if not f.endswith(".csv"): continue
                    
                    full_path = os.path.join(current_root, f)
                    if full_path in self.seen_files: continue
                    self.seen_files.add(full_path)

                    self._process_file(full_path)

        return self._merge_data()

    def _process_file(self, file_path):
        try:
            # Attempt 1: Standard Load
            df = pd.read_csv(file_path)
            
            # Smart Header Detection
            # If the first row looks like metadata (e.g., date range, many 'Unnamed'), try next row
            if self._is_messy_header(df):
                self.log(f"🔄 Detected messy header in {os.path.basename(file_path)}, retrying with header=1")
                df = pd.read_csv(file_path, header=1)
            
            # 1. Clean Column Names (Strip whitespace)
            df.columns = df.columns.astype(str).str.strip()
            
            # 2. Apply Synonym Mapping
            df = self._map_columns(df)
            
            # 3. Classify and Store
            if self._is_report(df):
                df = self._clean_report(df)
                self.report_data.append(df)
                self.log(f"✅ Loaded REPORT: {os.path.basename(file_path)} ({len(df)} rows)")
            elif self._is_details(df):
                df = self._clean_details(df)
                self.details_data.append(df)
                self.log(f"✅ Loaded DETAILS: {os.path.basename(file_path)} ({len(df)} rows)")
            else:
                self.log(f"⚠️ Skipped {os.path.basename(file_path)}: Could not classify (Cols: {list(df.columns[:5])}...)")

        except Exception as e:
            self.log(f"❌ Error reading {os.path.basename(file_path)}: {e}")

    def _is_messy_header(self, df):
        """Heuristic to detect if the first row is metadata (e.g. 2024-01-01 - 2024-12-31)."""
        # Criteria 1: First column name is a long string containing numbers (like a date range)
        col0 = str(df.columns[0])
        if len(col0) > 20 and any(c.isdigit() for c in col0):
            return True
        
        # Criteria 2: Many 'Unnamed' columns
        unnamed_count = sum(1 for c in df.columns if 'Unnamed' in str(c))
        if unnamed_count > len(df.columns) / 2:
            return True
            
        return False

    def _map_columns(self, df):
        """Renames columns based on config.COLUMN_MAPPING."""
        new_cols = {}
        # Reverse mapping: Alias -> Standard Name
        alias_map = {}
        for std_col, aliases in config.COLUMN_MAPPING.items():
            for alias in aliases:
                alias_map[alias.lower()] = std_col  # Case insensitive matching
        
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in alias_map:
                new_cols[col] = alias_map[col_lower]
        
        if new_cols:
            df.rename(columns=new_cols, inplace=True)
        return df

    def _is_report(self, df):
        """Checks if DF has essential Report columns."""
        required = ['order_id', 'total_amount']
        # Also typically needs 'date' but sometimes date is missing in source? 
        # Let's be strict on ID and Total.
        return all(col in df.columns for col in required)

    def _is_details(self, df):
        """Checks if DF has essential Details columns."""
        required = ['order_id', 'item_name'] # Minimum for details
        return all(col in df.columns for col in required)

    def _clean_report(self, df):
        """Standardizes types for Report data."""
        # Clean ID
        if 'order_id' in df.columns:
            df['order_id'] = df['order_id'].astype(str).str.strip()
            # Remove empty IDs
            df = df[df['order_id'] != 'nan']
        
        # Clean Date
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Clean Numeric
        if 'total_amount' in df.columns:
            df['total_amount'] = self._to_numeric(df['total_amount'])
            
        return df

    def _clean_details(self, df):
        """Standardizes types for Details data."""
        # Clean ID
        if 'order_id' in df.columns:
            df['order_id'] = df['order_id'].astype(str).str.strip()
            df = df[df['order_id'] != 'nan']

        # Clean Numeric
        if 'item_total' in df.columns:
            df['item_total'] = self._to_numeric(df['item_total'])
        if 'qty' in df.columns:
            df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)
            
        return df

    def _to_numeric(self, series):
        """Helper to clean currency strings."""
        if series.dtype == 'object':
            return pd.to_numeric(series.astype(str).str.replace(r'[NT\$,]', '', regex=True), errors='coerce').fillna(0)
        return pd.to_numeric(series, errors='coerce').fillna(0)

    def _merge_data(self):
        """Concatenates all loaded chunks and performs final deduplication."""
        final_report = pd.DataFrame()
        final_details = pd.DataFrame()

        if self.report_data:
            final_report = pd.concat(self.report_data, ignore_index=True)
            # Strict Deduplication: Exact Row Match
            final_report.drop_duplicates(inplace=True)
            self.log(f"TOTAL REPORT ROWS: {len(final_report)}")

        if self.details_data:
            final_details = pd.concat(self.details_data, ignore_index=True)
            final_details.drop_duplicates(inplace=True)
            self.log(f"TOTAL DETAILS ROWS: {len(final_details)}")

    def enrich_data(self, df_report, df_details):
        """Applies business logic: Day Type, Period, Categories, etc."""
        
        # --- 1. Report Enrichment ---
        if not df_report.empty:
            # Parse Date & Time
            # Assuming 'date' is already datetime from _clean_report, but let's ensure
            if 'date' in df_report.columns:
                df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
                
                # Day Type
                df_report['Day_Type'] = df_report['Date_Parsed'].apply(self._get_day_type)
                
                # Period (Lunch/Dinner)
                # If date has time component? 
                # In app.py, it combined 'Date_Parsed' + '時間' string.
                # My loader maps 'date' from '日期'/'Time'.
                # Let's check if 'date' has time. 
                # If not, we might need a separate 'time' column mapping if it exists.
                # Config has 'date': ['日期', 'Date', 'Time', ...]. 
                # If 'Time' is a separate column in source, it gets mapped to 'date'? No, mapped to 'date'.
                # If source has BOTH Date and Time columns, they both get mapped to 'date'?
                # That would overwrite.
                # Quick fix: The source usually has a combined datetime or separate.
                # For now, simplistic period check from Date_Parsed if it has time.
                df_report['Period'] = df_report['Date_Parsed'].apply(self._get_period)

        # --- 2. Details Enrichment ---
        if not df_details.empty:
            # Parse Date
            if 'date' in df_details.columns:
                 df_details['Date_Parsed'] = pd.to_datetime(df_details['date'], errors='coerce')

            # Main Dish Logic
            if 'item_name' in df_details.columns:
                # Simple logic: '麵' or '飯' implies Main Dish
                # And exclude 'Combo Item' wrapper if identifiable
                mask_name = df_details['item_name'].astype(str).str.contains('麵|飯', regex=True, na=False)
                df_details['Is_Main_Dish'] = mask_name
                
            # Category Inference could go here (omitted for brevity as we lack details data now)
            
        return df_report, df_details

    def _get_day_type(self, dt):
        if pd.isnull(dt): return 'Unknown'
        d_str = dt.strftime('%Y-%m-%d')
        if d_str in config.TW_HOLIDAYS_SET: return '假日 (Holiday)' 
        if dt.weekday() >= 5: return '假日 (Holiday)' 
        return '平日 (Weekday)'

    def _get_period(self, dt):
        if pd.isnull(dt): return 'Unknown'
        if dt.hour == 0 and dt.minute == 0: return 'Unknown' # Midnight usually means no time info
        
        return '中午 (Lunch)' if dt.hour < 16 else '晚上 (Dinner)'


if __name__ == "__main__":
    loader = UniversalLoader()
    print("--- Starting Data Load Test ---")
    df_r, df_d, logs = loader.scan_and_load()
    
    print("\n--- Summary ---")
    print(f"Report Rows: {len(df_r)}")
    print(f"Details Rows: {len(df_d)}")
    
    if not df_r.empty:
        print("\nReport Columns:", df_r.columns.tolist())
        print("Report Head:\n", df_r.head(2))
    
    if not df_d.empty:
        print("\nDetails Columns:", df_d.columns.tolist())
        print("Details Head:\n", df_d.head(2))
        
    print("\n--- Logs ---")
    for l in logs: print(l)

