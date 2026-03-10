import streamlit as st
import pandas as pd
from datetime import datetime
from config import APP_VERSION
from views import operational, member, system, sales, prediction
import db_queries

# --- 1. Config ---
st.set_page_config(
    page_title=f"滾麵智慧營運報表 v{APP_VERSION}",
    page_icon="🍜",
    layout="wide"
)

# Force Reload Trigger: v2.4 (Version bump)

# --- 2. Data Loading (SQL Check) ---
@st.cache_data(ttl=300)
def check_db_health():
    # Attempt a quick health check to fail fast if DB is down
    logs = db_queries.fetch_system_logs()
    
    latest_dates = {}
    try:
        # Get Max Date representing the freshness
        max_date_df = db_queries.fetch_data("SELECT MAX(date) as max_date FROM orders_fact")
        if not max_date_df.empty and max_date_df.iloc[0]['max_date'] is not None:
            max_d = pd.to_datetime(max_date_df.iloc[0]['max_date'])
            latest_dates['latest_db_record'] = max_d.strftime('%Y-%m-%d %H:%M:%S')
    except:
        pass
        
    return logs, latest_dates

# --- 3. Main App ---
def main():
    st.sidebar.title(f"🍜 滾麵 Dashboard v{APP_VERSION}")
    
    if st.sidebar.button("🔄 強制重新連線資料庫"):
        st.cache_resource.clear()
        check_db_health.clear()
        st.rerun()
    
    with st.spinner('連線遠端 PostgreSQL 資料庫中...'):
        health_logs, latest_dates = check_db_health()

    if health_logs.empty:
        st.warning("⚠️ 無法連線至資料庫或資料庫為空")
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
        operational.render_operational_view()
        
    elif view_mode == "🍟 商品銷售分析":
        st.subheader("📅 銷售分析區間")
        from views.utils import render_date_filter
        s_date, e_date = render_date_filter("sales", "近2週 (Last 2 Weeks)")
        sales.render_sales_view(s_date, e_date)
            
    elif view_mode == "📈 營業額預測":
        prediction.render_prediction_view()
        
    elif view_mode == "👥 會員查詢":
        member.render_member_search(latest_dates)
        
    elif view_mode == "🆕 新舊客分析":
        member.render_crm_analysis(latest_dates)
        
    elif view_mode == "🔧 系統檢查":
        system.render_system_check(health_logs)

if __name__ == "__main__":
    main()
