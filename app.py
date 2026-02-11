import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- Content Configuration ---
st.set_page_config(
    page_title="滾麵 (Gun Mian) 營運儀表板",
    page_icon="🍜",
    layout="wide"
)

# --- Constants ---
SHEET_ID = "1hdCvSCZ_4gSSGQxtvW8xCqBNCBAO5H3chCocn2N8qAY"
GID_REPORT = "0"          # 交易報告
GID_DETAILS = "1988676024" # 交易明細

# --- Data Loading ---
@st.cache_data(ttl=300) # Cache data for 5 minutes
def load_data():
    base_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
    
    # SSL Context hack for Mac local dev
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # Load Transaction Report
    url_report = f"{base_url}&gid={GID_REPORT}"
    df_report = pd.read_csv(url_report)
    
    # Load Transaction Details (Optional for now, but good to have)
    url_details = f"{base_url}&gid={GID_DETAILS}"
    df_details = pd.read_csv(url_details)
    
    return df_report, df_details

def preprocess_data(df):
    # Rename columns for easier access if needed, or just use Chinese directly
    # 'date', '總計', '支付工具', '來源訂單編號' (UXIFS/Invoice related?), '電子發票號碼'
    
    # Ensure Date format
    if 'date' in df.columns:
        df['Date_Parsed'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Clean Currency Columns (Remove 'NT$' and ',')
    currency_cols = ['總計', '小計', '折扣', '服務費']
    for col in currency_cols:
        if col in df.columns:
            df[col] = df[col].replace({r'[NT\$,]': ''}, regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    return df

# --- Main App ---
try:
    with st.spinner('正在從 Google Sheet 讀取最新資料...'):
        df_report, df_details = load_data()
        df_report = preprocess_data(df_report)
        df_details = preprocess_data(df_details)
        
    st.title("🍜 滾麵 (Gun Mian) 營運監測中心")
    st.markdown(f"**資料來源**: Google Sheets (自動同步) | **最後更新**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # --- Sidebar Filters ---
    st.sidebar.header("篩選條件")
    
    # Date Range Filter
    min_date = df_report['Date_Parsed'].min()
    max_date = df_report['Date_Parsed'].max()
    
    date_range = st.sidebar.date_input(
        "選擇日期範圍",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # Filter Data
    if len(date_range) == 2:
        start_date, end_date = date_range
        mask = (df_report['Date_Parsed'].dt.date >= start_date) & (df_report['Date_Parsed'].dt.date <= end_date)
        df_filtered = df_report[mask]
    else:
        df_filtered = df_report

    # --- KPI Cards ---
    total_revenue = df_filtered['總計'].sum()
    total_orders = len(df_filtered)
    avg_ticket = total_revenue / total_orders if total_orders > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("總營業額 (Revenue)", f"NT$ {total_revenue:,.0f}")
    col2.metric("總訂單數 (Orders)", f"{total_orders:,} 單")
    col3.metric("平均客單價 (AOV)", f"NT$ {avg_ticket:,.0f}")

    st.divider()

    # --- Charts ---
    
    # 1. Daily Revenue Trend
    st.subheader("📈 每日營業額趨勢")
    daily_revenue = df_filtered.groupby('Date_Parsed')['總計'].sum().reset_index()
    fig_line = px.line(daily_revenue, x='Date_Parsed', y='總計', title='每日營業額', markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

    # 2. Payment Method Distribution
    st.subheader("💳 支付方式分佈")
    if '支付工具' in df_filtered.columns:
        payment_stats = df_filtered.groupby('支付工具')['總計'].sum().reset_index()
        fig_pie = px.pie(payment_stats, values='總計', names='支付工具', title='各支付方式佔比')
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.warning("找不到此期間的支付工具資料")

    # 3. Invoice / Member Check
    st.subheader("🔍 數據核對")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("##### 電子發票開立狀況")
        if '電子發票號碼' in df_filtered.columns:
            has_invoice = df_filtered['電子發票號碼'].notna() & (df_filtered['電子發票號碼'] != '')
            invoice_count = has_invoice.sum()
            no_invoice_count = len(df_filtered) - invoice_count
            
            fig_invoice = px.bar(
                x=['已開立', '未開立'], 
                y=[invoice_count, no_invoice_count], 
                title=f"電子發票 (共 {len(df_filtered)} 筆)"
            )
            st.plotly_chart(fig_invoice, use_container_width=True)
        else:
            st.info("無電子發票欄位")

    with col_b:
        st.markdown("##### 會員消費佔比")
        if '客戶名稱' in df_filtered.columns:
            has_member = df_filtered['客戶名稱'].notna() & (df_filtered['客戶名稱'] != '')
            member_rev = df_filtered[has_member]['總計'].sum()
            guest_rev = total_revenue - member_rev
            
            fig_member = px.pie(
                names=['會員', '非會員'], 
                values=[member_rev, guest_rev], 
                hole=0.4,
                title="會員 vs 非會員 貢獻度"
            )
            st.plotly_chart(fig_member, use_container_width=True)

    # --- Raw Data View ---
    with st.expander("查看原始資料表"):
        st.dataframe(df_filtered)

except Exception as e:
    st.error(f"發生錯誤：{e}")
    st.write("請確認 Google Sheet 連結權限是否正常，或與開發者聯繫。")
