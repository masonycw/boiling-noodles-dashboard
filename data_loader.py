import os
import pandas as pd
import numpy as np
import config

class UniversalLoader:
    def __init__(self):
        self.report_data = [] # Type 1: Transaction Record (undefined) - Master Revenue
        self.invoice_data = [] # Type 2: Invoice Record (發票) - Carrier Info
        self.details_data = [] # Type 3: Transaction Details (Transaction Report) - Item Info
        self.debug_logs = []
        self.seen_files = set()

    def log(self, message):
        self.debug_logs.append(message)
        print(message) 

    def scan_and_load(self):
        """Scans and loads files, classifying them into 3 types."""
        self.report_data = []
        self.invoice_data = []
        self.details_data = []
        self.debug_logs = []
        self.seen_files = set()

        for root_dir in config.DATA_DIRS:
            if not os.path.exists(root_dir):
                self.log(f"Skipping missing directory: {root_dir}")
                continue

            for current_root, dirs, files in os.walk(root_dir):
                if '/.' in current_root: continue 

                for f in sorted(files):
                    if not f.endswith(".csv"): continue
                    
                    full_path = os.path.join(current_root, f)
                    if full_path in self.seen_files: continue
                    self.seen_files.add(full_path)

                    self._process_file(full_path)

        return self._merge_data()

    def _process_file(self, file_path):
        try:
            # Attempt 1: Standard Load with BOM support
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # Smart Header Detection
            if self._is_messy_header(df):
                self.log(f"🔄 Detected messy header in {os.path.basename(file_path)}, retrying with header=1")
                df = pd.read_csv(file_path, header=1, encoding='utf-8-sig') # Retry with correct encoding
            
            # 1. Clean Column Names
            df.columns = df.columns.astype(str).str.strip()
            
            # 2. Apply Synonym Mapping
            df = self._map_columns(df)
            
            # 3. Classify and Store
            # Strategy: Filename Priority -> Column Content Fallback
            filename = os.path.basename(file_path)
            file_type = self._classify_by_filename(filename)
            
            if file_type == 'details':
                df = self._clean_details(df)
                self.details_data.append(df)
                self.log(f"✅ Loaded DETAILS (Type 3 - By Name): {filename} ({len(df)} rows)")
                
            elif file_type == 'report':
                df = self._clean_report(df)
                self.report_data.append(df)
                self.log(f"✅ Loaded REPORT (Type 1 - By Name): {filename} ({len(df)} rows)")
                
            elif file_type == 'invoice':
                df = self._clean_invoice(df)
                self.invoice_data.append(df)
                self.log(f"✅ Loaded INVOICE (Type 2 - By Name): {filename} ({len(df)} rows)")
                
            else:
                # Fallback to Content-Based Classification
                if self._is_details(df, filename): # Pass filename
                    df = self._clean_details(df)
                    self.details_data.append(df)
                    self.log(f"✅ Loaded DETAILS (Type 3 - By Cols): {filename} ({len(df)} rows)")
                    
                elif self._is_report(df):
                    df = self._clean_report(df)
                    self.report_data.append(df)
                    self.log(f"✅ Loaded REPORT (Type 1 - By Cols): {filename} ({len(df)} rows)")
                    
                elif self._is_invoice(df):
                    df = self._clean_invoice(df)
                    self.invoice_data.append(df)
                    self.log(f"✅ Loaded INVOICE (Type 2 - By Cols): {filename} ({len(df)} rows)")
                    
                else:
                    self.log(f"⚠️ Skipped {filename}: Could not classify (Cols: {list(df.columns[:5])}...)")

        except Exception as e:
            self.log(f"❌ Error reading {os.path.basename(file_path)}: {e}")

    def _classify_by_filename(self, filename):
        """Returns 'report', 'details', 'invoice', or None based on naming convention."""
        fn_lower = filename.lower()
        if 'transaction report' in fn_lower: return 'details' # User Definition
        
        if 'history_report' in fn_lower: return 'report'
        if 'undefined' in fn_lower: return None # Let content decide
        
        if '發票' in fn_lower or 'invoice' in fn_lower: return 'invoice'
        return None

    def _is_messy_header(self, df):
        """Heuristic to detect if the first row is metadata."""
        col0 = str(df.columns[0])
        if len(col0) > 20 and any(c.isdigit() for c in col0): return True
        unnamed_count = sum(1 for c in df.columns if 'Unnamed' in str(c))
        if unnamed_count > len(df.columns) / 2: return True
        return False

    def _map_columns(self, df):
        """Renames columns based on config.COLUMN_MAPPING."""
        new_cols = {}
        alias_map = {}
        for std_col, aliases in config.COLUMN_MAPPING.items():
            for alias in aliases:
                alias_map[alias.lower()] = std_col 
        
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in alias_map:
                new_cols[col] = alias_map[col_lower]
        
        if new_cols:
            df.rename(columns=new_cols, inplace=True)
        return df

    def _is_report(self, df):
        """Type 1: Trans Record. Must have Order ID & Total Amount."""
        return 'order_id' in df.columns and 'total_amount' in df.columns

    def _is_details(self, df, filename=""):
        """Type 3: Details. Must have Item Name. (Order ID is usually there too)"""
        if "transaction report" in filename.lower() and "undefined" not in filename.lower():
             return True
             
        if 'item_name' in df.columns: return True
        # Check aliases
        for alias in config.COLUMN_MAPPING.get('item_name', []):
            if alias in df.columns: return True
            
        return False

    def _is_invoice(self, df):
        """Type 2: Invoice Record. Must have Invoice ID. (Order ID usually MISSING in strictly Type 2 files)"""
        # If it has Order ID + Total, it's Type 1.
        # If it LACKS Order ID but HAS Invoice ID, it's Type 2.
        has_invoice = 'invoice_id' in df.columns
        has_order = 'order_id' in df.columns
        return has_invoice and not has_order

    def _clean_report(self, df):
        """Standardizes types for Report data."""
        if 'order_id' in df.columns:
            df['order_id'] = df['order_id'].astype(str).str.strip()
            df = df[df['order_id'] != 'nan']
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        if 'total_amount' in df.columns:
            df['total_amount'] = self._to_numeric(df['total_amount'])
            
        if 'people_count' in df.columns:
            df['people_count'] = pd.to_numeric(df['people_count'], errors='coerce').fillna(0)
            
        # Filter Status (Only Completed)
        if 'status' in df.columns:
            # Normalize status
            df['status'] = df['status'].astype(str).str.strip().str.lower()
            
            # Keep only '已完成' or 'completed'
            valid_statuses = ['已完成', 'completed']
            df = df[df['status'].isin(valid_statuses)]
            
        return df

    def _clean_details(self, df):
        """Standardizes types for Details data."""
        if 'order_id' in df.columns:
            df['order_id'] = df['order_id'].astype(str).str.strip()
            df = df[df['order_id'] != 'nan']

        if 'item_total' in df.columns:
            df['item_total'] = self._to_numeric(df['item_total'])
        if 'unit_price' in df.columns:
            df['unit_price'] = self._to_numeric(df['unit_price'])
            
        if 'qty' in df.columns:
            df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)
            
        return df
        
    def _clean_invoice(self, df):
        """Standardizes Invoice data."""
        if 'invoice_id' in df.columns:
            # Handle potential float/int IDs
            df['invoice_id'] = df['invoice_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            df = df[df['invoice_id'] != 'nan']
            
        if 'carrier_id' in df.columns:
            df['carrier_id'] = df['carrier_id'].astype(str).str.strip()
            
        return df

    def _to_numeric(self, series):
        if series.dtype == 'object':
            return pd.to_numeric(series.astype(str).str.replace(r'[NT\$,]', '', regex=True), errors='coerce').fillna(0)
        return pd.to_numeric(series, errors='coerce').fillna(0)

    def _merge_data(self):
        """Merges 3 sources: Report (Main) + Invoice (Left Join) + Details (Linked)."""
        final_report = pd.DataFrame()
        final_details = pd.DataFrame()
        invoice_lookup = pd.DataFrame()

        # 1. Consolidate Type 2 (Invoice)
        if self.invoice_data:
            invoice_lookup = pd.concat(self.invoice_data, ignore_index=True)
            # Deduplicate Invoice Data (One row per Invoice ID)
            # If duplicates, keep last (or first?)
            if 'invoice_id' in invoice_lookup.columns:
                invoice_lookup.drop_duplicates(subset=['invoice_id'], keep='last', inplace=True)
                self.log(f"Consolidated INVOICE Data: {len(invoice_lookup)} unique records")

        # 2. Consolidate Type 1 (Report - Master)
        if self.report_data:
            final_report = pd.concat(self.report_data, ignore_index=True)
            final_report.drop_duplicates(inplace=True)
            self.log(f"Initial REPORT Rows: {len(final_report)}")
            
            # --- JOIN STRATEGY: Enrich Report with Invoice Info ---
            if not invoice_lookup.empty and 'invoice_id' in final_report.columns and 'invoice_id' in invoice_lookup.columns:
                # Select only useful columns from Invoice Data to merge
                cols_to_merge = ['invoice_id']
                if 'carrier_id' in invoice_lookup.columns: cols_to_merge.append('carrier_id')
                if 'tax_id' in invoice_lookup.columns: cols_to_merge.append('tax_id')
                # Avoid collision if report already has them (but usually report lacks carrier)
                
                # Rename collision
                inv_subset = invoice_lookup[cols_to_merge].copy()
                
                # Perform Merge
                # Update: if Report ALREADY has carrier_id (from some other source), we might overwrite or fillna
                # For now, simplistic Left Join
                final_report = pd.merge(final_report, inv_subset, on='invoice_id', how='left', suffixes=('', '_inv'))
                
                # Coalesce (If Report had column but empty, fill from Invoice)
                if 'carrier_id' in final_report.columns and 'carrier_id_inv' in final_report.columns:
                    final_report['carrier_id'] = final_report['carrier_id'].fillna(final_report['carrier_id_inv'])
                    final_report.drop(columns=['carrier_id_inv'], inplace=True)
                elif 'carrier_id_inv' in final_report.columns:
                    final_report.rename(columns={'carrier_id_inv': 'carrier_id'}, inplace=True)
                    
                self.log(f"Enriched Report with Invoice Data. Final Rows: {len(final_report)}")

        # 3. Consolidate Type 3 (Details)
        if self.details_data:
            final_details = pd.concat(self.details_data, ignore_index=True)
            final_details.drop_duplicates(inplace=True)
            self.log(f"TOTAL DETAILS ROWS: {len(final_details)}")

        return final_report, final_details, self.debug_logs


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

            # Member Identification Logic (Name/Phone OR Carrier)
            # Create a 'Member_ID' column
            # User wants: "Check carrier if name/phone missing"
            
            # Ensure columns exist
            if 'member_phone' not in df_report.columns: df_report['member_phone'] = None
            if 'carrier_id' not in df_report.columns: df_report['carrier_id'] = None
            
            def get_member_id(row):
                p = str(row.get('member_phone', ''))
                c = str(row.get('carrier_id', ''))
                if len(p) > 6 and p != 'nan': return p # Valid Phone
                if len(c) > 4 and c != 'nan': return c # Valid Carrier
                return None # Non-member
                
            df_report['Member_ID'] = df_report.apply(get_member_id, axis=1)
            
            # Order Category Logic (Dine-in / Takeout / Delivery)
            if 'order_type' in df_report.columns:
                def get_order_category(otype):
                    s = str(otype).lower()
                    if 'uber' in s or 'panda' in s or 'delivery' in s or '外送' in s: return '外送 (Delivery)'
                    if 'take' in s or 'tago' in s or '外帶' in s or '自取' in s: return '外帶 (Takeout)'
                    return '內用 (Dine-in)' # Default
                df_report['Order_Category'] = df_report['order_type'].apply(get_order_category)
            else:
                 df_report['Order_Category'] = '內用 (Dine-in)' # Fallback

        # --- 2. Details Enrichment ---
        if not df_details.empty:
            # Parse Date
            if 'date' in df_details.columns:
                 df_details['Date_Parsed'] = pd.to_datetime(df_details['date'], errors='coerce')

            # Main Dish / Modifier Logic
            # User Definition (Strict):
            # 1. Product = Item Name + SKU
            # 2. Exclude rows where Modifier Name (options) is NOT Empty
            
            if 'options' in df_details.columns:
                # If options has content, it's a modifier row
                df_details['Is_Modifier'] = (
                    df_details['options'].notna() & 
                    (df_details['options'].astype(str).str.strip() != '')
                )
            else:
                # Fallback
                if 'unit_price' in df_details.columns:
                    df_details['Is_Modifier'] = (df_details['unit_price'] <= 0)
                else:
                    df_details['Is_Modifier'] = False
            
            # Is_Main_Dish: Not a modifier AND contains '麵' or '飯'
            if 'item_name' in df_details.columns:
                mask_name = df_details['item_name'].astype(str).str.contains('麵|飯', regex=True, na=False)
                df_details['Is_Main_Dish'] = mask_name & (~df_details['Is_Modifier'])
                
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

