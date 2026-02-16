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
    
    if not df_report.empty:
        st.subheader("3. 報表資料預覽 (Report Preview)")
        st.dataframe(df_report.head(50), use_container_width=True)
        
    if not df_details.empty:
        st.subheader("4. 明細資料預覽 (Details Preview)")
        st.dataframe(df_details.head(50), use_container_width=True)
