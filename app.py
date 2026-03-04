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
def get_data():
    loader = UniversalLoader()
    # scan_and_load now includes enrich_data internally and caches the fully-enriched result.
    # No need to call loader.enrich_data() separately.
    df_report, df_details, logs = loader.scan_and_load()
    
    latest_dates = getattr(loader, 'latest_dates', {})
    return df_report, df_details, logs, latest_dates

# --- 3. Main App ---
def main():
    st.sidebar.title(f"🍜 滾麵 Dashboard v{APP_VERSION}")
    
    if st.sidebar.button("🔄 強制重新整理資料"):
        get_data.clear()
        st.rerun()
    
    with st.spinner('載入資料中... (若有新資料則重新處理)'):

        df_report, df_details, debug_logs, latest_dates = get_data()

    if df_report.empty:
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
        operational.render_operational_view(df_report, df_details)
        
    elif view_mode == "🍟 商品銷售分析":
        # Needs date range, likely local to view or share same logic?
        # For now, let's implement local date filter in sales view too or pass None
        # User requested Sales Analysis.
        # I created render_sales_view taking start/end.
        # Let's simple create a date picker here if we want consistency?
        # Or let the view handle it. 
        # I haven't put a date picker IN render_sales_view yet? 
        # Wait, I did: "# 1. Date Filter (Local to View)" in my thought, but did I write it?
        # Let me check my previous write_to_file for sales.py...
        # I wrote: "# 1. Date Filter (Local to View)... if start_date is None..."
        # No, I wrote: "def render_sales_view(df_details, start_date, end_date):"
        # and "if df.empty...". It EXPECTS arguments.
        # So I need to provide dates here or wrap it.
        # Ideally, each view handles its own controls if global is removed.
        # Let's add a helper for date picker here or inside the view?
        # Better: Add date picker in this block for Sales View.
        
        st.subheader("📅 銷售分析區間")
        from views.utils import render_date_filter
        s_date, e_date = render_date_filter("sales", "近2週 (Last 2 Weeks)")
        sales.render_sales_view(df_details, s_date, e_date)
            
    elif view_mode == "📈 營業額預測":
        prediction.render_prediction_view(df_report)
        
    elif view_mode == "👥 會員查詢":
        member.render_member_search(df_report, df_details, latest_dates)
        
    elif view_mode == "🆕 新舊客分析":
        member.render_crm_analysis(df_report, df_details, latest_dates)
        
    elif view_mode == "🔧 系統檢查":
        system.render_system_check(debug_logs, df_report, df_details)

if __name__ == "__main__":
    main()
