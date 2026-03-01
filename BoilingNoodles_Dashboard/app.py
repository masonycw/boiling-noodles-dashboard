import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

# Import new modules
# Import new modules
from data_loader import UniversalLoader
from config import APP_VERSION
from views import operational, member, system, sales, prediction

# --- 1. Config ---
st.set_page_config(
    page_title=f"滾麵智慧營運報表 v{APP_VERSION}",
    page_icon="🍜",
    layout="wide"
)

# Force Reload Trigger: v2.4 (Version bump)

# --- 2. Data Loading (Cached) ---
@st.cache_data(ttl=300)
def get_marts_data():
    loader = UniversalLoader()
    df_ops, df_sales, df_crm, logs = loader.load_marts()
    
    # If marts don't exist yet, we must trigger a full rebuild
    if df_ops.empty:
        loader.scan_and_load()
        df_ops, df_sales, df_crm, logs = loader.load_marts()
        
    latest_dates = getattr(loader, 'latest_dates', {})
    return df_ops, df_sales, df_crm, logs, latest_dates

@st.cache_data(ttl=300)
def get_raw_data():
    loader = UniversalLoader()
    df_report, df_details, logs = loader.scan_and_load()
    return df_report, df_details

# --- 3. Main App ---
def main():
    st.sidebar.title(f"🍜 滾麵 Dashboard v{APP_VERSION}")
    
    with st.spinner('載入輕量化資料超市...'):
        df_ops, df_sales, df_crm, debug_logs, latest_dates = get_marts_data()

    if df_ops.empty:
        st.warning("尚未載入資料")
        if debug_logs:
            with st.expander("除錯日誌 (Debug Logs)"):
                st.text("\n".join(debug_logs))
        st.stop()

    # --- Sidebar Navigation ---
    view_mode = st.sidebar.radio(
        "功能切換", 
        [
            "📊 營運總覽", 
            "🍟 商品銷售分析", 
            "📈 營業額預測",
            "👥 會員查詢", 
            "🆕 新舊客分析", 
            "🔧 系統檢查"
        ]
    )
    st.sidebar.divider()
    st.sidebar.caption(f"資料更新時間: {datetime.now().strftime('%H:%M:%S')}")

    # --- Routing ---
    if view_mode == "📊 營運總覽":
        # operational view handles its own dates now
        operational.render_operational_view(df_ops)
        
    elif view_mode == "🍟 商品銷售分析":
        # Needs date range, likely local to view or share same logic?
        # For now, let's implement local date filter in sales view too or pass None
        # User requested Sales Analysis.
        # I created render_sales_view taking start/end.
        # Let's simple create a date picker here if we want consistency?
        # Or let the view handle it. 
        # I haven't put a date picker IN render_sales_view yet? 
        # Wait, I did: "# 1. Date Filter (Local to View)" in my thought, but did I write it?
        st.subheader("📅 銷售分析區間")
        from views.utils import render_date_filter
        s_date, e_date = render_date_filter("sales", "近2週 (Last 2 Weeks)")
        sales.render_sales_view(df_sales, s_date, e_date)
            
    elif view_mode == "📈 營業額預測":
        prediction.render_prediction_view(df_ops)
        
    elif view_mode == "👥 會員查詢":
        with st.spinner("載入完整歷史明細 (第一筆可能需等待約一秒)..."):
            df_report, df_details = get_raw_data()
        member.render_member_search(df_report, df_details, latest_dates)
        
    elif view_mode == "🆕 新舊客分析":
        with st.spinner("載入完整歷史明細以繪製 RFM 模型..."):
            df_report, df_details = get_raw_data()
        member.render_crm_analysis(df_report, df_details, df_crm, latest_dates)
        
    elif view_mode == "🔧 系統檢查":
        with st.spinner("載入完整歷史明細以進行系統檢查..."):
            df_report, df_details = get_raw_data()
        system.render_system_check(debug_logs, df_report, df_details)

if __name__ == "__main__":
    main()
