import streamlit as st
import pandas as pd
import db_queries

def render_system_check(health_logs):
    st.title("🔧 系統檢查 (System Diagnostics)")
    
    st.subheader("1. 資料庫連線狀態 (Database Health)")
    if not health_logs.empty:
        st.success("✅ 資料庫連線正常")
        
        # Display table sizes
        st.dataframe(health_logs, use_container_width=True)
    else:
        st.error("❌ 資料庫無回應或為空")

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
