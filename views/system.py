import streamlit as st
import pandas as pd

def render_system_check(debug_logs, df_report, df_details):
    st.title("🔧 系統檢查 (System Diagnostics)")
    
    st.subheader("1. 資料載入日誌 (Data Loader Logs)")
    if debug_logs:
        log_text = "\n".join(debug_logs)
        st.text_area("Loader Logs", log_text, height=300)
    else:
        st.info("無日誌 (No logs available)")
        
    st.subheader("2. 資料統計 (Data Stats)")
    c1, c2 = st.columns(2)
    c1.metric("Report Rows", len(df_report))
    c2.metric("Details Rows", len(df_details))
    
    if not df_details.empty:
        st.subheader("3. 報表資料預覽 (Report Preview)")
        st.dataframe(df_report.head(50), use_container_width=True)
        
    # --- Main Dish Inspector (v2.3.6 Debug Tool) ---
    st.divider()
    st.subheader("🕵️‍♀️ 主食判定檢查器 (Main Dish Inspector)")
    
    # Date Picker for inspection
    insp_date = st.date_input("選擇檢查日期", pd.to_datetime("2025-02-15"))
    insp_date = pd.to_datetime(insp_date)
    
    if 'Date_Parsed' in df_details.columns:
        # Filter by Date
        # Use Date_Only for comparison
        df_d_day = df_details[df_details['Date_Parsed'].dt.date == insp_date.date()].copy()
        
        st.write(f"📅 **日期:** {insp_date.strftime('%Y-%m-%d')}")
        st.write(f"🔢 **當日總明細行數:** {len(df_d_day)}")
        
        if not df_d_day.empty:
            # 1. Included Main Dishes
            if 'Is_Main_Dish' in df_d_day.columns:
                df_main = df_d_day[df_d_day['Is_Main_Dish']].copy()
                st.metric("🍜 主食總數 (Qty Sum)", f"{df_main['qty'].sum():.0f}", help="所有符合條件品項的數量加總")
                
                with st.expander("✅ 被判定為「主食」的項目 (Included)", expanded=True):
                    if not df_main.empty:
                        # Group for cleaner view
                        disp = df_main.groupby(['item_name', 'sku', 'unit_price', 'status']).agg({'qty': 'sum'}).reset_index()
                        st.dataframe(disp, use_container_width=True)
                    else:
                        st.warning("此日期沒有任何主食被計算到。")
            
            # 2. Excluded Candidates (Debug)
            # Find items that match SKU/Name rules but Is_Main_Dish is False
            # Re-run strict logic parts to see why failed
            
            # Re-construct logic locally for debug display
            # Condition: SKU A/B OR Name 麵/飯
            sku_s = df_d_day['sku'].fillna('').astype(str).str.upper().str.strip()
            name_s = df_d_day['item_name'].fillna('').astype(str)
            
            cond_sku = sku_s.str.startswith(('A', 'B')) & (sku_s != '')
            cond_name = name_s.str.contains('麵|飯', regex=True, na=False)
            is_candidate = np.where(sku_s != '', cond_sku, cond_name) # Same as loader logic
            
            # Filter: Candidate BUT NOT Main Dish
            df_excluded = df_d_day[is_candidate & (~df_d_day['Is_Main_Dish'])].copy()
            
            with st.expander("🚫 被排除的潛在主食 (Excluded Candidates) - 請檢查原因", expanded=True):
                if not df_excluded.empty:
                    st.write("這些項目符合「SKU A/B」或「麵/飯」，但被排除了。原因可能是：")
                    st.write("1. 狀態是 Cancelled/Void (Loader 已過濾，所以這裡可能看不到，除非Loader邏輯有漏)")
                    st.write("2. 是 Combo Item")
                    st.write("3. 程式邏輯錯誤")
                    
                    st.dataframe(df_excluded[['item_name', 'sku', 'qty', 'status', 'item_type', 'order_type', 'Is_Modifier']], use_container_width=True)
                else:
                    st.info("沒有任何「符合特徵但被排除」的項目。 (代表剩下的都是完全不相關的配菜/飲料)")
                    
            # 3. All items breakdown
            with st.expander("📋 當日所有明細 (原始資料)", expanded=False):
                st.dataframe(df_d_day, use_container_width=True)
                
    else:
        st.error("Data missing 'Date_Parsed' column.")

    st.divider()
    st.subheader("5. 伺服器檔案列表 (Server File System)")
    
    import os
    import time
    from config import DATA_DIRS
    
    # Scan all configured paths
    found_files = []
    for d in DATA_DIRS:
        if os.path.exists(d):
            st.write(f"📁 Directory found: `{d}`")
            try:
                for root, dirs, files in os.walk(d):
                    for file in files:
                        if file.lower().endswith(('.csv', '.xls', '.xlsx')):
                            full_path = os.path.join(root, file)
                            stat = os.stat(full_path)
                            size_mb = stat.st_size / (1024 * 1024)
                            mod_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                            found_files.append({
                                "Path": full_path,
                                "File": file,
                                "Size (MB)": f"{size_mb:.2f}",
                                "Modified": mod_time
                            })
            except Exception as e:
                st.error(f"Error scanning {d}: {e}")
        else:
            st.warning(f"❌ Directory not found: `{d}`")
            
    if found_files:
        df_files = pd.DataFrame(found_files)
        st.dataframe(df_files, use_container_width=True)
        
        # File Inspector
        st.subheader("6. 檔案內容檢查 (File Inspector)")
        selected_file = st.selectbox("選擇檔案進行檢查 (Select File to Inspect)", df_files['Path'].unique())
        
        if selected_file:
            if st.button(f"讀取 {os.path.basename(selected_file)} 前 5 行"):
                try:
                    if selected_file.endswith('.csv'):
                        # Try reading raw first to show columns
                        df_preview = pd.read_csv(selected_file, nrows=5)
                        st.write("Columns:", df_preview.columns.tolist())
                        st.dataframe(df_preview)
                    else:
                        st.info("Excel file preview not fully supported in this quick view yet.")
                except Exception as e:
                    st.error(f"Error reading file: {e}")
    else:
        st.warning("No data files found in scan paths.")
