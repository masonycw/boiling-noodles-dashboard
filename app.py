import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# --- 1. Config ---
st.set_page_config(
    page_title="滾麵智慧營運報表", # 修正標題
    page_icon="🍜",
    layout="wide"
)

# --- 2. Constants & Loading ---
SHEET_ID = "1hdCvSCZ_4gSSGQxtvW8xCqBNCBAO5H3chCocn2N8qAY"
GID_REPORT = "0"
GID_DETAILS = "1988676024"
LOCAL_DATA_DIR = "/home/eats365/data"

@st.cache_data(ttl=300)
def load_data():
    local_report = os.path.join(LOCAL_DATA_DIR, "history_report.csv")
    local_details = os.path.join(LOCAL_DATA_DIR, "history_details.csv")
    
    if os.path.exists(local_report) and os.path.exists(local_details):
        df_report = pd.read_csv(local_report)
        df_details = pd.read_csv(local_details)
    else:
        # Fallback for local testing if files missing (or use sheet)
        # For now, assuming environment has files or we gracefully fail
        return pd.DataFrame(), pd.DataFrame()
        
    return df_report, df_details

def clean_currency(series):
    if series.dtype == 'object':
        return pd.to_numeric(series.astype(str).str.replace(r'[NT\$,]', '', regex=True), errors='coerce').fillna(0)
    return pd.to_numeric(series, errors='coerce').fillna(0)

def preprocess_data(df_report, df_details):
    if df_report.empty or df_details.empty:
        return df_report, df_details

    # --- A. Common Cleaning ---
    # 1. Cancelled Orders
    if '狀態' in df_report.columns:
        df_report = df_report[~df_report['狀態'].astype(str).str.contains('取消|Cancelled', case=False, na=False)]
    if 'Status' in df_details.columns:
        df_details = df_details[~df_details['Status'].astype(str).str.contains('取消|Cancelled', case=False, na=False)]

    # 2. Date Parsing
    # Fix 1/24 Unknown issue by ensuring strict parsing
    if 'date' in df_report.columns:
        df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
    
    if 'date' in df_details.columns:
        df_details['Date_Parsed'] = pd.to_datetime(df_details['date'], errors='coerce')

    # 3. Combine DateTime for Logic
    if '時間' in df_report.columns and 'Date_Parsed' in df_report.columns:
        # report['時間'] usually like '11:03:09'
        # Combine Date + Time string
        df_report['Datetime'] = pd.to_datetime(
            df_report['Date_Parsed'].dt.strftime('%Y-%m-%d') + ' ' + df_report['時間'].astype(str),
            errors='coerce'
        )

    # 4. Currency Cleaning
    if '總計' in df_report.columns:
        df_report['總計'] = clean_currency(df_report['總計'])
    if 'Order Total(TWD)' in df_details.columns:
        df_details['Order Total(TWD)'] = clean_currency(df_details['Order Total(TWD)'])
    if 'Item Amount(TWD)' in df_details.columns: # For item analysis
        df_details['Item Amount(TWD)'] = clean_currency(df_details['Item Amount(TWD)'])
    if 'Item Quantity' in df_details.columns:
        df_details['Item Quantity'] = pd.to_numeric(df_details['Item Quantity'], errors='coerce').fillna(0)

    # --- 5. Deduplicate Modifier Rows (CRITICAL FIX) ---
    # Filter out rows where 'Modifier Name' is present to avoid double counting items
    if 'Modifier Name' in df_details.columns:
        # Keep rows where Modifier Name is NaN or Empty
        df_details = df_details[df_details['Modifier Name'].isna() | (df_details['Modifier Name'] == '')]

    # --- B. Specific Logic Updates ---
    
    # Logic 1: Time Split at 16:00
    def get_period(dt):
        if pd.isnull(dt): return 'Unknown'
        return '中午 (Lunch)' if dt.hour < 16 else '晚上 (Dinner)'

    if 'Datetime' in df_report.columns:
        df_report['Period'] = df_report['Datetime'].apply(get_period)
    else:
        df_report['Period'] = 'Unknown'

    # Logic 2: Main Dish Identification (Include Set Meals content, Exclude Wrapper)
    df_details['Is_Main_Dish'] = False
    
    # Ensure column names are clean
    clean_cols = {c: c.strip() for c in df_details.columns}
    df_details.rename(columns=clean_cols, inplace=True)
    
    # 1. Identify "Rice/Noodle" items
    mask_name = df_details['Item Name'].astype(str).str.contains('麵|飯', regex=True, na=False)
    
    # 2. Identify "Set Meal Wrappers" to EXCLUDE
    # We want to count the inner items (Single Item in Combo Item), but NOT the wrapper (Combo Item)
    mask_exclude_wrapper = pd.Series([True] * len(df_details))
    if 'Item Type' in df_details.columns:
        # If it is 'Combo Item' (the set wrapper), we DO NOT count it as a dish
        # We only count 'Single Item' or 'Single Item in Combo Item' that are noodles/rice
        mask_exclude_wrapper = ~df_details['Item Type'].astype(str).str.contains('Combo Item$', case=False, na=False) 
        # Note: 'Single Item in Combo Item' contains 'Combo Item', so we use endswith '$' or strict equality?
        # Let's use strict equality to be safe, or check for "Single Item in Combo Item"
        
        # Better logic:
        # Exclude if Item Type == 'Combo Item'
        # Keep if Item Type == 'Single Item' or 'Single Item in Combo Item'
        mask_is_wrapper = df_details['Item Type'].astype(str).str.fullmatch('Combo Item', case=False, na=False)
        mask_exclude_wrapper = ~mask_is_wrapper
    
    # Final Logic: Is Noodle/Rice AND Is Not Wrapper
    df_details.loc[mask_name & mask_exclude_wrapper, 'Is_Main_Dish'] = True

    return df_report, df_details

# --- 3. Main Application ---
try:
    with st.spinner('數據處理中...'):
        df_report_raw, df_details_raw = load_data()
        df_report, df_details = preprocess_data(df_report_raw, df_details_raw)

    if df_report.empty:
        st.warning("尚未載入資料，請確認後台是否有檔案。")
        st.stop()

    # --- Sidebar Filters ---
    st.sidebar.title("🍜 滾麵 Dashboard")
    
    # 1. View Selection
    view_mode = st.sidebar.radio("功能切換", ["📊 營運總覽", "🍟 商品分析", "👥 會員查詢"])
    st.sidebar.divider()

    # 2. Date Filter
    st.sidebar.header("📅 日期篩選")
    filter_mode = st.sidebar.selectbox(
        "快速區間",
        ["今日 (Today)", "昨日 (Yesterday)", "本週 (This Week)", "本月 (This Month)", "自訂範圍"],
        index=3
    )
    
    today = pd.Timestamp.now().normalize()
    if filter_mode == "今日 (Today)":
        start_date = end_date = today
    elif filter_mode == "昨日 (Yesterday)":
        start_date = end_date = today - timedelta(days=1)
    elif filter_mode == "本週 (This Week)":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif filter_mode == "本月 (This Month)":
        start_date = today.replace(day=1)
        end_date = today
    else:
        d = st.sidebar.date_input("選擇日期", [today - timedelta(days=7), today])
        start_date = pd.to_datetime(d[0]) if len(d) > 0 else today
        end_date = pd.to_datetime(d[1]) if len(d) > 1 else start_date

    # Apply Filter to Data
    mask_rep = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    df_rep_filtered = df_report.loc[mask_rep]
    
    mask_det = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
    df_det_filtered = df_details.loc[mask_det]

    # --- VIEW 1: 營運總覽 ---
    if view_mode == "📊 營運總覽":
        st.title(f"📊 營運總覽 ({start_date.date()} ~ {end_date.date()})")
        
        # KPI Cards
        rev = df_rep_filtered['總計'].sum()
        txs = len(df_rep_filtered)
        # Main Dish Count (including Set Meals now)
        visitors = df_det_filtered[df_det_filtered['Is_Main_Dish']]['Item Quantity'].sum()
        avg_price = rev / visitors if visitors > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰總營業額", f"${rev:,.0f}")
        c2.metric("🍜來客數 (主食+套餐)", f"{visitors:,.0f}")
        c3.metric("🧾訂單數", f"{txs:,.0f}")
        c4.metric("👤平均客單價", f"${avg_price:,.0f}")
        
        st.divider()

        # Charts Row 1
        col_L, col_R = st.columns([2, 1])
        
        with col_L:
            st.subheader("📈 營業額趨勢 (時段)")
            if not df_rep_filtered.empty:
                daily = df_rep_filtered.groupby(['Date_Parsed', 'Period'])['總計'].sum().reset_index()
                fig = px.bar(daily, x='Date_Parsed', y='總計', color='Period', barmode='stack',
                             color_discrete_map={'中午 (Lunch)': '#FFC107', '晚上 (Dinner)': '#3F51B5'})
                st.plotly_chart(fig, use_container_width=True)
        
        with col_R:
            st.subheader("☀️🌙 時段佔比")
            if not df_rep_filtered.empty:
                period_sum = df_rep_filtered.groupby('Period')['總計'].sum().reset_index()
                fig = px.pie(period_sum, values='總計', names='Period', hole=0.4,
                             color='Period', color_discrete_map={'中午 (Lunch)': '#FFC107', '晚上 (Dinner)': '#3F51B5'})
                st.plotly_chart(fig, use_container_width=True)

        # Charts Row 2: Order Type & Payment
        c5, c6 = st.columns(2)
        
        with c5:
            st.subheader("moto 內用/外帶/外送 (Order Type)")
            # 欄位名稱可能是 '單類型' 或 'Order Type'
            col_type = '單類型' if '單類型' in df_rep_filtered.columns else 'Order Type'
            if col_type in df_rep_filtered.columns:
                type_sum = df_rep_filtered.groupby(col_type)['總計'].sum().reset_index()
                fig = px.pie(type_sum, values='總計', names=col_type, hole=0.4, title="各營運模式佔比 (金額)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("無單類型資料")

        with c6:
            st.subheader("💳 結帳方式 (Payment)")
            # 欄位名稱可能是 '付款方式' 或 'Tender'
            col_pay = '付款方式' if '付款方式' in df_rep_filtered.columns else 'Tender'
            if col_pay in df_rep_filtered.columns:
                pay_sum = df_rep_filtered.groupby(col_pay)['總計'].sum().reset_index()
                fig = px.bar(pay_sum, x=col_pay, y='總計', title="各支付方式金額", text='總計')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("無付款方式資料")

    # --- VIEW 2: 商品分析 ---
    elif view_mode == "🍟 商品分析":
        st.title("🍟 商品銷售分析")
        
        # Top Items
        if 'Item Name' in df_det_filtered.columns:
            # Clean data
            df_items = df_det_filtered.dropna(subset=['Item Name'])
            
            # Pivot Table
            item_stats = df_items.groupby('Item Name').agg({
                'Item Quantity': 'sum',
                'Item Amount(TWD)': 'sum'
            }).reset_index()
            
            item_stats = item_stats.sort_values('Item Quantity', ascending=False)
            
            # Chart
            st.subheader("🏆 熱銷排行榜 (數量)")
            fig = px.bar(item_stats.head(20), x='Item Quantity', y='Item Name', orientation='h', 
                         text='Item Quantity', title="Top 20 熱銷品項")
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
            
            # Data Table
            st.subheader("📋 詳細數據")
            st.dataframe(item_stats, use_container_width=True)
        else:
            st.error("找不到商品名稱資料")

    # --- VIEW 3: 會員查詢 ---
    elif view_mode == "👥 會員查詢":
        st.title("👥 會員消費紀錄查詢")
        
        # Input
        phone_query = st.text_input("請輸入電話號碼 (例如 0912345678):")
        
        # Check Column
        # Report usually has 'Contact', 'Customer Tel'
        col_phone = None
        for c in ['Contact', 'Customer Tel', '客戶電話']:
            if c in df_report.columns:
                col_phone = c
                break
        
        if not col_phone:
            st.error("資料中找不到電話欄位，無法查詢。")
        elif phone_query:
            # Filter (Search in FULL report_raw, not filtered by date)
            # member data implies lifetime history
            mask_member = df_report[col_phone].astype(str).str.contains(phone_query, na=False)
            member_history = df_report[mask_member].sort_values('Date_Parsed', ascending=False)
            
            if not member_history.empty:
                # Summary
                m_total_spend = member_history['總計'].sum()
                m_visits = len(member_history)
                m_avg = m_total_spend / m_visits
                m_last = member_history['Date_Parsed'].iloc[0].date()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("歷史總消費", f"${m_total_spend:,.0f}")
                c2.metric("消費次數", f"{m_visits} 次")
                c3.metric("平均客單", f"${m_avg:,.0f}")
                c4.metric("最近來訪", str(m_last))
                
                # History Table
                st.subheader("📜 歷史交易明細")
                display_cols = ['date', '時間', '總計', '單類型', '付款方式']
                st.dataframe(member_history[display_cols], use_container_width=True)
            else:
                st.warning("查無此號碼消費紀錄")
        else:
            st.info("請輸入號碼開始查詢")

except Exception as e:
    st.error(f"系統發生錯誤: {str(e)}")
