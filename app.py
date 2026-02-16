import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

# Import new modules
from data_loader import UniversalLoader
from views import operational, member, system
# from views import product # Omitted for now until data available

# --- 1. Config ---
st.set_page_config(
    page_title="滾麵智慧營運報表 v2.0",
    page_icon="🍜",
    layout="wide"
)

# --- 2. Data Loading (Cached) ---
@st.cache_data(ttl=300)
def get_data():
    loader = UniversalLoader()
    df_report, df_details, logs = loader.scan_and_load()
    
    # Enrich Data (Business Logic)
    df_report, df_details = loader.enrich_data(df_report, df_details)
    
    return df_report, df_details, logs

# --- 3. Main App ---
def main():
    st.sidebar.title("🍜 滾麵 Dashboard v2.0")
    
    with st.spinner('數據處理中 (Rebuilding V2)...'):
        df_report, df_details, debug_logs = get_data()

    if df_report.empty:
        st.warning("尚未載入資料")
        if debug_logs:
            with st.expander("除錯日誌 (Debug Logs)"):
                st.text("\n".join(debug_logs))
        st.stop()

    # --- Sidebar Navigation ---
    view_mode = st.sidebar.radio(
        "功能切換", 
        ["📊 營運總覽", "👥 會員查詢", "🆕 新舊客分析", "🔧 系統檢查"]
        # "🍟 商品分析" -> Removed until details available
    )
    st.sidebar.divider()

    # --- Date Filter (Global) ---
    st.sidebar.header("📅 日期篩選")
    today = date.today()
    month_options = [ (today - relativedelta(months=i)).strftime("%Y-%m") for i in range(6) ]
    filter_opts = ["今日 (Today)", "昨日 (Yesterday)", "本週 (This Week)", "本月 (This Month)", 
                   "近 28 天", "近 30 天", "近 2 個月 (60 Days)", "近 6 個月 (180 Days)", "自訂範圍"] + month_options
    filter_mode = st.sidebar.selectbox("快速區間", filter_opts, index=3)

    start_date, end_date = today, today 
    
    # Date Logic
    if filter_mode == "今日 (Today)": start_date = end_date = pd.Timestamp(today)
    elif filter_mode == "昨日 (Yesterday)": start_date = end_date = pd.Timestamp(today - timedelta(days=1))
    elif filter_mode == "本週 (This Week)": start_date = pd.Timestamp(today - timedelta(days=today.weekday())); end_date = pd.Timestamp(today)
    elif filter_mode == "本月 (This Month)": start_date = pd.Timestamp(today.replace(day=1)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 28 天": start_date = pd.Timestamp(today - timedelta(days=28)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 30 天": start_date = pd.Timestamp(today - timedelta(days=30)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 2 個月 (60 Days)": start_date = pd.Timestamp(today - timedelta(days=60)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 6 個月 (180 Days)": start_date = pd.Timestamp(today - timedelta(days=180)); end_date = pd.Timestamp(today)
    elif filter_mode in month_options: 
        y, m = map(int, filter_mode.split('-'))
        start_date = pd.Timestamp(date(y, m, 1))
        end_date = pd.Timestamp(start_date + relativedelta(months=1, days=-1))
    else: 
        d = st.sidebar.date_input("選擇日期", [today - timedelta(days=7), today])
        if len(d) > 0: start_date = pd.to_datetime(d[0])
        if len(d) > 1: end_date = pd.to_datetime(d[1])
        else: end_date = start_date

    # --- Routing ---
    if view_mode == "📊 營運總覽":
        operational.render_operational_view(df_report, df_details, start_date, end_date)
        
    elif view_mode == "👥 會員查詢":
        member.render_member_search(df_report, df_details)
        
    elif view_mode == "🆕 新舊客分析":
        member.render_crm_analysis(df_report)
        
    elif view_mode == "🔧 系統檢查":
        system.render_system_check(debug_logs, df_report, df_details)

if __name__ == "__main__":
    main()
