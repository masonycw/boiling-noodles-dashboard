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
        """Scans raw files or loads from instant Parquet cache if available and valid."""
        # --- Cache Validation Logic ---
        cache_dir = os.path.join(os.getcwd(), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        report_cache = os.path.join(cache_dir, 'df_report.parquet')
        details_cache = os.path.join(cache_dir, 'df_details.parquet')
        
        # 1. Find the newest raw data file modification time
        newest_raw_mtime = 0
        raw_files_to_process = []
        
        for root_dir in config.DATA_DIRS:
            if not os.path.exists(root_dir):
                self.log(f"Skipping missing directory: {root_dir}")
                continue
                
            for current_root, dirs, files in os.walk(root_dir):
                if '/.' in current_root: continue
                for f in files:
                    if not (f.endswith(".csv") or f.endswith(".json") or f.endswith(".txt")): continue
                    
                    full_path = os.path.join(current_root, f)
                    mtime = os.path.getmtime(full_path)
                    if mtime > newest_raw_mtime:
                        newest_raw_mtime = mtime
                    raw_files_to_process.append(full_path)
                    
        # 2. Check Parquet Cache validity
        if os.path.exists(report_cache) and os.path.exists(details_cache):
            cache_mtime = min(os.path.getmtime(report_cache), os.path.getmtime(details_cache))
            
            if cache_mtime >= newest_raw_mtime:
                self.log("⚡ [Parquet Cache Hit] Raw files unchanged. Loading binary cache instantly...")
                try:
                    df_report = pd.read_parquet(report_cache)
                    df_details = pd.read_parquet(details_cache)
                    self.log(f"⚡ Successfully loaded {len(df_report)} report rows and {len(df_details)} details from Parquet.")
                    return df_report, df_details, self.debug_logs
                except Exception as e:
                    self.log(f"⚠️ Failed to load Parquet cache: {e}. Reverting to raw scan.")
        
        self.log("🔄 [Cache Miss or Invalid] Processing raw files from scratch...")
        
        # --- Raw Parsing Logic (Fallback / Cache Rebuild) ---
        self.report_data = []
        self.invoice_data = []
        self.details_data = []
        self.seen_files = set()

        for full_path in raw_files_to_process:
            if full_path in self.seen_files: continue
            self.seen_files.add(full_path)
            self._process_file(full_path)

        # Merge raw data
        df_report, df_details, logs = self._merge_data()
        
        # --- Save Cache ---
        try:
            # Parquet requires uniform column types (no mixed int/str). Cast all to string to be safe.
            df_report_pq = df_report.astype(str)
            df_details_pq = df_details.astype(str)
            
            df_report_pq.to_parquet(report_cache, engine='pyarrow', index=False)
            df_details_pq.to_parquet(details_cache, engine='pyarrow', index=False)
            self.log("💾 [Cache Saved] Parquet cache rebuilt successfully.")
        except Exception as e:
            self.log(f"⚠️ Failed to save Parquet cache: {e}")
            
        return df_report, df_details, logs

    def _process_file(self, file_path):
        try:
            # Handle JSON files separately
            if file_path.endswith('.json') or ('OperationReport' in file_path and file_path.endswith('.txt')):
                self._process_json_file(file_path)
                return

            # Attempt 1: Standard Load with BOM support for CSV
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
            # Remove duplicated columns (keep first) to prevent DataFrame string accessor errors
            df = df.loc[:, ~df.columns.duplicated()].copy()
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
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
        if 'order_id' in df.columns:
            df['order_id'] = df['order_id'].astype(str).str.strip()
            df = df[df['order_id'] != 'nan']
            
            # Fix for POS daily reset order numbers (e.g. '111', '121' repeating every day in undefined report)
            # If date exists, and order_id is short/purely numeric, prefix it with the date to make it unique across days.
            if 'date' in df.columns:
                def make_unique_id(row):
                    oid = str(row['order_id'])
                    dt = row['date']
                    if pd.notna(dt) and oid.isdigit() and len(oid) <= 4:
                        # Append hour and minute to prevent collision on same day (e.g., POS mid-day reset)
                        return f"{dt.strftime('%Y%m%d')}-{oid}-{dt.strftime('%H%M')}"
                    return oid
                
                df['order_id'] = df.apply(make_unique_id, axis=1)
        
        if 'total_amount' in df.columns:
            df['total_amount'] = self._to_numeric(df['total_amount'])
            
        if 'people_count' in df.columns:
            df['people_count'] = pd.to_numeric(df['people_count'], errors='coerce').fillna(0)
            
        # Filter Status (Only Completed)
        if 'status' in df.columns:
            # Normalize status
            df['status'] = df['status'].astype(str).str.strip().str.lower()
            
            # Relaxed Filter (v2.3.8): Exclude Cancelled instead of strict Include
            # This avoids dropping valid orders with statuses like 'Paid', 'Delivered', etc.
            invalid_statuses = ['已取消', 'cancelled', 'void', 'delete', 'deleted', '已關閉', 'closed']
            df = df[~df['status'].isin(invalid_statuses)]
            
        return df

    def _clean_details(self, df):
        """Standardizes types for Details data."""
        if 'date' in df.columns:
             df['date'] = pd.to_datetime(df['date'], errors='coerce')

        if 'order_id' in df.columns:
            df['order_id'] = df['order_id'].astype(str).str.strip()
            df = df[df['order_id'] != 'nan']

            # Match report composite key logic
            if 'date' in df.columns:
                def make_unique_id(row):
                    oid = str(row['order_id'])
                    dt = row['date']
                    if pd.notna(dt) and oid.isdigit() and len(oid) <= 4:
                        # Append hour and minute to prevent collision on same day (e.g., POS mid-day reset)
                        return f"{dt.strftime('%Y%m%d')}-{oid}-{dt.strftime('%H%M')}"
                    return oid
                
                df['order_id'] = df.apply(make_unique_id, axis=1)

        if 'item_total' in df.columns:
            df['item_total'] = self._to_numeric(df['item_total'])
        if 'unit_price' in df.columns:
            df['unit_price'] = self._to_numeric(df['unit_price'])
            
        if 'qty' in df.columns:
            df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0)
            
        # Filter Item Status (Void/Cancelled items in valid orders)
        if 'status' in df.columns:
            # Normalize
            df['status'] = df['status'].astype(str).str.strip().str.lower()
            # Defines invalid statuses
            invalid_statuses = ['已取消', 'cancelled', 'void', '已退菜', '退菜', '已關閉', 'closed']
            # Drop rows with invalid status
            df = df[~df['status'].isin(invalid_statuses)]
            
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
        self.latest_dates = {
            'json': '無資料',
            'csv_report': '無資料',
            'csv_details': '無資料',
            'invoice': '無資料'
        }

        # 1. Consolidate Type 2 (Invoice)
        if self.invoice_data:
            invoice_lookup = pd.concat(self.invoice_data, ignore_index=True)
            if 'date' in invoice_lookup.columns:
                invoice_lookup['date'] = pd.to_datetime(invoice_lookup['date'], errors='coerce')
                max_dt = invoice_lookup['date'].max()
                if pd.notna(max_dt):
                    self.latest_dates['invoice'] = max_dt.strftime('%Y-%m-%d')
                    
            # Deduplicate Invoice Data (One row per Invoice ID)
            # If duplicates, keep last (or first?)
            if 'invoice_id' in invoice_lookup.columns:
                invoice_lookup.drop_duplicates(subset=['invoice_id'], keep='last', inplace=True)
                self.log(f"Consolidated INVOICE Data: {len(invoice_lookup)} unique records")

        # 2. Consolidate Type 1 (Report - Master)
        if self.report_data:
            final_report = pd.concat(self.report_data, ignore_index=True)
            if 'data_source' not in final_report.columns:
                 final_report['data_source'] = 'csv'
            else:
                 final_report['data_source'] = final_report['data_source'].fillna('csv')
                 
            # Compute max dates BEFORE deduplication
            if 'date' in final_report.columns:
                temp_date = pd.to_datetime(final_report['date'], errors='coerce')
                final_report['_temp_date'] = temp_date
                
                j_df = final_report[final_report['data_source'] == 'json']
                if not j_df.empty:
                    m = j_df['_temp_date'].max()
                    if pd.notna(m): self.latest_dates['json'] = m.strftime('%Y-%m-%d')
                    
                c_df = final_report[final_report['data_source'] == 'csv']
                if not c_df.empty:
                    m = c_df['_temp_date'].max()
                    if pd.notna(m): self.latest_dates['csv_report'] = m.strftime('%Y-%m-%d')
                    
                final_report.drop(columns=['_temp_date'], inplace=True)
                 
            if 'order_id' in final_report.columns:
                # Deduplicate Report Data: JSON has priority.
                # Sort so 'data_source' == 'json' comes first
                final_report.sort_values(by=['order_id', 'data_source'], ascending=[True, False], inplace=True)
                
                # --- PRESERVE CSV MEMBER DATA ---
                # Before dropping the CSV row, we need to save the manual member info (phone, name).
                # JSON data often lacks these if they were manually keyed into the POS note or CRM later.
                cols_to_preserve = ['order_id']
                if 'member_phone' in final_report.columns: cols_to_preserve.append('member_phone')
                if 'customer_name' in final_report.columns: cols_to_preserve.append('customer_name')
                
                csv_members = pd.DataFrame()
                if len(cols_to_preserve) > 1:
                    csv_members = final_report[final_report['data_source'] == 'csv'][cols_to_preserve].copy()
                    # Drop empty/nan rows to create a clean lookup table
                    csv_members = csv_members.replace({'': pd.NA, 'nan': pd.NA}).dropna(subset=[c for c in cols_to_preserve if c != 'order_id'], how='all')
                    csv_members.drop_duplicates(subset=['order_id'], keep='first', inplace=True)
                
                # Perform Deduplication
                final_report.drop_duplicates(subset=['order_id'], keep='first', inplace=True)
                
                # --- APPLY CSV MEMBER DATA ---
                # Back-fill the surviving JSON row with the preserved CSV member data
                if not csv_members.empty:
                    final_report = pd.merge(final_report, csv_members, on='order_id', how='left', suffixes=('', '_csv'))
                    if 'member_phone' in final_report.columns and 'member_phone_csv' in final_report.columns:
                        final_report['member_phone'] = final_report['member_phone'].replace({'': pd.NA, 'nan': pd.NA}).fillna(final_report['member_phone_csv'])
                        final_report.drop(columns=['member_phone_csv'], inplace=True)
                    if 'customer_name' in final_report.columns and 'customer_name_csv' in final_report.columns:
                        final_report['customer_name'] = final_report['customer_name'].replace({'': pd.NA, 'nan': pd.NA}).fillna(final_report['customer_name_csv'])
                        final_report.drop(columns=['customer_name_csv'], inplace=True)
                        
            else:
                final_report.drop_duplicates(inplace=True)
            self.log(f"Initial REPORT Rows (Deduplicated with JSON priority & CRM Preserved): {len(final_report)}")
            
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
            
            if 'data_source' not in final_details.columns:
                 final_details['data_source'] = 'csv'
            else:
                 final_details['data_source'] = final_details['data_source'].fillna('csv')
                 
            # Extract Max Date before dropping CSV rows
            if 'date' in final_details.columns:
                c_df = final_details[final_details['data_source'] == 'csv'].copy()
                if not c_df.empty:
                    c_df['temp_date'] = pd.to_datetime(c_df['date'], errors='coerce')
                    m = c_df['temp_date'].max()
                    if pd.notna(m):
                        self.latest_dates['csv_details'] = m.strftime('%Y-%m-%d')
            
            # DO NOT drop_duplicates on details! Valid receipts can have identical item lines 
            # (e.g., ordering the same dish twice but POS outputs two lines).
            
            # Filter Details: Only keep details for valid Report Orders (Completed)
            if not final_report.empty and 'order_id' in final_report.columns and 'order_id' in final_details.columns:
                valid_orders = set(final_report['order_id'].astype(str))
                initial_count = len(final_details)
                final_details = final_details[final_details['order_id'].astype(str).isin(valid_orders)]
                
                # To deduplicate details effectively, we must deduplicate the "CSV" lines if JSON lines are present for the same order_id
                # So we drop ALL CSV rows where order_id exists in JSON details.
                json_order_ids = set(final_details[final_details['data_source'] == 'json']['order_id'].astype(str))
                # Keep row if it's JSON, OR if it's CSV and the order is NOT in json_order_ids
                mask = (final_details['data_source'] == 'json') | (~final_details['order_id'].astype(str).isin(json_order_ids))
                final_details = final_details[mask]

                filtered_count = len(final_details)
                self.log(f"Filtered Details by Status & JSON Deduplication: {initial_count} -> {filtered_count} rows (Removed {initial_count - filtered_count} rows)")
            
            self.log(f"TOTAL DETAILS ROWS: {len(final_details)}")

        return final_report, final_details, self.debug_logs

    def _process_json_file(self, file_path):
        import json
        from datetime import datetime
        import pytz

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            orders = data.get('pay_load', {}).get('data', [])
            if not orders:
                self.log(f"⚠️ JSON {os.path.basename(file_path)} has no orders.")
                return

            report_list = []
            details_list = []
            tz = pytz.timezone('Asia/Taipei')

            for order in orders:
                # Only process COMPLETED orders to match CSV behavior
                # This filters out 'PROCESSING' (incomplete) or other states
                if order.get('status') != 'COMPLETED':
                    continue
                    
                # 1. REPORT DATA
                order_id = order.get('short_code', '')
                if not order_id:
                    order_id = order.get('id', '')[-6:]
                    
                timestamp_ms = order.get('created_at')
                date_str = pd.NaT
                if timestamp_ms:
                    dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Apply composite logic to match CSV: YYYYMMDD-oid-HHMM
                    if str(order_id).isdigit() and len(str(order_id)) <= 4:
                        order_id = f"{dt.strftime('%Y%m%d')}-{order_id}-{dt.strftime('%H%M')}"

                total_price = order.get('total_price', 0)
                status = order.get('status', '')

                # order type mapping
                o_type_raw = order.get('type', '')
                if o_type_raw == 'dine_in': o_type = '內用'
                elif o_type_raw == 'takeout': o_type = '外帶'
                elif o_type_raw == 'delivery': o_type = '外送'
                elif o_type_raw == 'pick_up': o_type = '自取' # Assuming pick up is takeout
                else: o_type = o_type_raw
                    
                people_count = order.get('party_size', 0)

                # Payment Info
                payments = order.get('payments', [])
                payment_method = payments[0].get('name', '') if payments else ''

                # Membership / Customer Info
                ship_info = order.get('shipping_information', {})
                receiver = ship_info.get('receiver', {}) if isinstance(ship_info, dict) else {}
                member_phone = receiver.get('phone_number', '')  # Could be empty
                customer_name = receiver.get('first_name', '')   # Could be empty
                
                # Invoice info
                invoice_list = order.get('invoice_list', [])
                invoice_number = invoice_list[0].get('invoice_number', '') if invoice_list else ''
                
                report_row = {
                    'order_id': order_id,
                    'date': date_str,
                    'total_amount': total_price,
                    'status': status,
                    'order_type': o_type,
                    'people_count': people_count,
                    'payment_method': payment_method,
                    'member_phone': member_phone,
                    'customer_name': customer_name,
                    'invoice_id': invoice_number,
                    'data_source': 'json'
                }
                report_list.append(report_row)
                
                # 2. DETAILS DATA
                items = order.get('line_items', [])
                for item in items:
                    item_name = item.get('product_name', {}).get('default', '')
                    sku = item.get('product_code', '')
                    qty = item.get('quantity', 0)
                    unit_price = item.get('price', 0)
                    item_total = item.get('price_total', 0)
                    
                    mods = item.get('modifiers', [])
                    options = ', '.join([m.get('value_name', {}).get('zh_TW', '') for m in mods if isinstance(m, dict)])
                    
                    is_combo = item.get('is_combo', False)
                    item_type_str = 'Combo Item' if is_combo else 'Normal'
                    
                    details_row = {
                        'order_id': order_id,
                        'date': date_str,
                        'status': status,
                        'item_name': item_name,
                        'sku': sku,
                        'qty': qty,
                        'unit_price': unit_price,
                        'item_total': item_total,
                        'options': options,
                        'item_type': item_type_str,
                        'data_source': 'json'
                    }
                    details_list.append(details_row)
                    
                    # Also extract bundled sub-items (for combos)
                    for b_item in item.get('bundled', []):
                        b_name = b_item.get('product_name', {}).get('default', '') or b_item.get('product_name', {}).get('zh_TW', '')
                        b_sku = b_item.get('product_code', '')
                        b_qty = b_item.get('quantity', 0)
                        
                        b_mods = b_item.get('modifiers', [])
                        b_opts = ', '.join([m.get('value_name', {}).get('zh_TW', '') for m in b_mods if isinstance(m, dict)])
                        
                        b_details_row = {
                            'order_id': order_id,
                            'date': date_str,
                            'status': status,
                            'item_name': b_name,
                            'sku': b_sku,
                            'qty': b_qty * qty,  # Multiply by parent combo quantity
                            'unit_price': b_item.get('price', 0),
                            'item_total': b_item.get('price_total', 0),
                            'options': b_opts,
                            'item_type': 'Combo Item', # Sub-items are part of the combo
                            'data_source': 'json'
                        }
                        details_list.append(b_details_row)

            if report_list:
                df_r = pd.DataFrame(report_list)
                self.report_data.append(df_r)
                self.log(f"✅ Loaded REPORT (JSON API): {os.path.basename(file_path)} ({len(df_r)} rows)")
                
            if details_list:
                df_d = pd.DataFrame(details_list)
                self.details_data.append(df_d)
                self.log(f"✅ Loaded DETAILS (JSON API): {os.path.basename(file_path)} ({len(df_d)} rows)")

        except Exception as e:
            self.log(f"❌ Error processing JSON {os.path.basename(file_path)}: {e}")


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
            if 'customer_name' not in df_report.columns: df_report['customer_name'] = None
            
            # 1. Identify Highly-Shared Phones (Platform Phones)
            # Clean phones temporarily for counting
            temp_phones = df_report['member_phone'].astype(str).str.strip().str.replace(' ', '')
            valid_mask = (temp_phones.str.len() >= 6) & (~temp_phones.str.contains(r'\*')) & (temp_phones != 'nan')
            
            # Count distinct customer names per phone
            name_counts = df_report[valid_mask].groupby(temp_phones[valid_mask])['customer_name'].nunique()
            shared_phones_auto = set(name_counts[name_counts >= 10].index)
            
            # Add known hardcoded platforms
            known_platforms = {'55941277', '77519126'}
            platform_phones = shared_phones_auto.union(known_platforms)
            
            # --- Carrier ID to Phone Mapping (Strategy B) ---
            # 1. Extract valid, non-platform, non-hidden phones with carrier IDs
            valid_phone_mask = (
                (temp_phones.str.len() > 6) & 
                (~temp_phones.str.contains(r'\*')) & 
                (temp_phones != 'nan') &
                (~temp_phones.isin(platform_phones)) &
                (~temp_phones.apply(lambda p: any(k in p for k in known_platforms)))
            )
            
            valid_carrier_mask = (
                df_report['carrier_id'].astype(str).str.len() > 4
            ) & (df_report['carrier_id'].astype(str) != 'nan')
            
            carrier_df = df_report[valid_phone_mask & valid_carrier_mask].copy()
            
            if not carrier_df.empty:
                # 2. Calculate Frequency (distinct dates), Recency (max date), Monetary (sum amount)
                carrier_df['date_only'] = carrier_df['Date_Parsed'].dt.date
                carrier_stats = carrier_df.groupby(['carrier_id', 'member_phone', 'customer_name']).agg(
                    Frequency=('date_only', 'nunique'),
                    Recency=('Date_Parsed', 'max'),
                    Monetary=('total_amount', 'sum')
                ).reset_index()
                
                # Sort descending: Highest freq -> Most recent -> Highest amount
                carrier_stats = carrier_stats.sort_values(
                    by=['carrier_id', 'Frequency', 'Recency', 'Monetary'],
                    ascending=[True, False, False, False]
                )
                
                # Drop duplicates to keep the #1 Ranked phone per carrier
                best_carriers = carrier_stats.drop_duplicates(subset=['carrier_id'], keep='first')
                
                # 3. Create mapping dictionaries
                carrier_to_phone = dict(zip(best_carriers['carrier_id'], best_carriers['member_phone']))
                carrier_to_name = dict(zip(best_carriers['carrier_id'], best_carriers['customer_name']))
                
                # 4. Apply mapping to rows with carrier but NO valid phone
                # Identify rows needing backfill (missing, empty, nan, or hidden)
                needs_backfill = (
                    (~valid_phone_mask) & valid_carrier_mask & 
                    (~temp_phones.isin(platform_phones)) & 
                    (~temp_phones.apply(lambda p: any(k in p for k in known_platforms)))
                )
                
                # Map values
                mapped_phones = df_report.loc[needs_backfill, 'carrier_id'].map(carrier_to_phone)
                mapped_names = df_report.loc[needs_backfill, 'carrier_id'].map(carrier_to_name)
                
                # Replace explicitly, ignore existing invalid values if map exists
                df_report.loc[needs_backfill & mapped_phones.notna(), 'member_phone'] = mapped_phones
                df_report.loc[needs_backfill & mapped_names.notna(), 'customer_name'] = mapped_names
                
            # --- End Carrier Mapping ---
            
            def get_member_id(row):
                p = str(row.get('member_phone', '')).strip().replace(' ', '')
                c = str(row.get('carrier_id', '')).strip()
                n = str(row.get('customer_name', '')).strip()
                
                # Hidden Phone Exception (e.g., ******)
                if '*' in p:
                    p = ''
                    
                # Platform Phone Exception (e.g., UberEats)
                is_platform = (p in platform_phones) or any(k in p for k in known_platforms)
                
                if is_platform:
                    if len(n) > 0 and n != 'nan': return f"UE_{n}"
                    p = ''
                
                if len(p) > 6 and p != 'nan': return f"CRM_{p}" # Valid Phone
                if len(c) > 4 and c != 'nan': return f"Carrier_{c}" # Valid Carrier
                return None # Non-member
                
            df_report['Member_ID'] = df_report.apply(get_member_id, axis=1)
            
            # Order Category Logic (Dine-in / Takeout / Delivery)
            if 'order_type' not in df_report.columns:
                df_report['order_type'] = ''
            if 'payment_method' not in df_report.columns:
                df_report['payment_method'] = ''
                
            def get_order_category(row):
                otype = str(row.get('order_type', '')).lower()
                pmethod = str(row.get('payment_method', '')).lower()
                
                # Check Platform / Payment Method first
                if 'foodomo' in pmethod or 'foodomo' in otype:
                    return '外送 (Delivery)'
                    
                if 'uber' in otype or 'panda' in otype or 'delivery' in otype or '外送' in otype: 
                    return '外送 (Delivery)'
                if 'take' in otype or 'tago' in otype or '外帶' in otype or '自取' in otype: 
                    return '外帶 (Takeout)'
                return '內用 (Dine-in)' # Default
                
            df_report['Order_Category'] = df_report.apply(get_order_category, axis=1)

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
                # If options has content, it's a modifier row (for CSV).
                # For JSON, options are nested within the actual items, so having options doesn't make it a modifier row.
                mask_csv = (df_details.get('data_source', '') != 'json')
                df_details['Is_Modifier'] = (
                    mask_csv &
                    df_details['options'].notna() & 
                    (df_details['options'].astype(str).str.strip() != '')
                )
            else:
                # Fallback
                if 'unit_price' in df_details.columns:
                    df_details['Is_Modifier'] = (df_details['unit_price'] <= 0)
                else:
                    df_details['Is_Modifier'] = False
            
            # Is_Main_Dish & Category Logic:
            if 'item_name' in df_details.columns:
                # Prepare SKU column
                if 'sku' not in df_details.columns:
                    df_details['sku'] = ''
                
                sku_series = df_details['sku'].fillna('').astype(str).str.upper().str.strip()
                
                # Category Assignment
                def get_sku_category(sku):
                    if sku.startswith('A'): return 'A 湯麵'
                    if sku.startswith('B'): return 'B 拌麵飯'
                    if sku.startswith('C'): return 'C 小菜'
                    if sku.startswith('D1'): return 'D1 單點'
                    if sku.startswith('D2'): return 'D2 青菜'
                    if sku.startswith('D'): return 'D 單點/青菜'
                    if sku.startswith('E'): return 'E 湯'
                    if sku.startswith('F'): return 'F 飲料'
                    if sku.startswith('S'): return 'S 套餐'
                    return '其他'
                    
                df_details['category'] = sku_series.apply(get_sku_category)
                
                # Is_Main_Dish Definition
                # Rule: SKU starts with A or B (Combos 'S' are not main dishes themselves to avoid double counting)
                cond_sku_match = sku_series.str.startswith(('A', 'B'))
                
                # Fallback if no SKU (legacy data support): contains 麵 or 飯 but is not a combo item
                name_series = df_details['item_name'].fillna('').astype(str)
                cond_name_match = name_series.str.contains('麵|飯', regex=True, na=False)
                
                combo_indicators = []
                if 'item_type' in df_details.columns:
                    combo_indicators.append(df_details['item_type'])
                if 'order_type' in df_details.columns:
                    combo_indicators.append(df_details['order_type'])
                    
                if combo_indicators:
                    combined_type = pd.concat(combo_indicators, axis=1).fillna('').astype(str)
                    is_combo = combined_type.apply(lambda row: row.str.contains('Combo Item', case=False).any(), axis=1)
                    mask_not_combo = ~is_combo
                else:
                    mask_not_combo = True
                
                cond_no_sku_fallback = (sku_series == '') & cond_name_match & mask_not_combo
                
                # Must NOT be a Modifier
                # For CSV, modifier rows often have 'options' filled. For JSON, 'options' are just attributes of the main dish.
                mask_json = (df_details.get('data_source', '') == 'json')
                mask_no_mod = (
                    mask_json |
                    df_details['options'].isna() | 
                    (df_details['options'].astype(str).str.strip() == '')
                )
                
                # Global Filter
                df_details['Is_Main_Dish'] = (cond_sku_match | cond_no_sku_fallback) & mask_no_mod

            # --- 3. Post-Enrichment Cross-Updates ---
            # Update people_count in df_report based on actual Main Dishes in df_details
            # Especially crucial for JSON orders and Delivery/Takeout where party_size is hardcoded to 1
            if 'Is_Main_Dish' in df_details.columns and 'order_id' in df_report.columns:
                # Count main dishes per order
                main_dish_counts = df_details[df_details['Is_Main_Dish']].groupby('order_id')['qty'].sum().reset_index()
                main_dish_counts = main_dish_counts.rename(columns={'qty': 'calculated_people'})
                
                # Merge into report
                df_report = df_report.merge(main_dish_counts, on='order_id', how='left')
                df_report['calculated_people'] = df_report['calculated_people'].fillna(0)
                
                # Logic: If calculated people > current people_count OR it's a JSON order, use calculated
                # (except if calculated is 0, keep at least 1 if original was >= 1)
                def fix_people_count(row):
                    orig = pd.to_numeric(row.get('people_count', 0), errors='coerce')
                    if pd.isna(orig): orig = 0
                    calc = row.get('calculated_people', 0)
                    
                    # For JSON or Takeout/Delivery, mostly trust the main dish count
                    if row.get('data_source') == 'json' or row.get('order_type') in ['外送', '外帶', '自取']:
                        return max(calc, 1) if calc > 0 else max(orig, 1)
                    
                    # For normal Dine-in CSVs, if calculated > orig, trust calculated
                    return max(orig, calc)
                    
                df_report['people_count'] = df_report.apply(fix_people_count, axis=1)
                df_report.drop(columns=['calculated_people'], inplace=True)

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

