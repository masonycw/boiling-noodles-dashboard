import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- Content Configuration ---
st.set_page_config(
    page_title="滾麵智慧營運報表",
    page_icon="🍜",
    layout="wide"
)

import os

# --- Constants ---
SHEET_ID = "1hdCvSCZ_4gSSGQxtvW8xCqBNCBAO5H3chCocn2N8qAY"
GID_REPORT = "0"          # 交易報告 (Chinese Headers)
GID_DETAILS = "1988676024" # 交易明細 (English Headers)
LOCAL_DATA_DIR = "/home/eats365/data"

# --- Data Loading ---
@st.cache_data(ttl=300)
def load_data():
    # 1. Try Local Files (fastest, for GCP VM)
    local_report = os.path.join(LOCAL_DATA_DIR, "history_report.csv")
    local_details = os.path.join(LOCAL_DATA_DIR, "history_details.csv")
    
    if os.path.exists(local_report) and os.path.exists(local_details):
        print("Loading from LOCAL VM storage (Fast Mode)...")
        df_report = pd.read_csv(local_report)
        df_details = pd.read_csv(local_details)
    else:
        # 2. Fallback to Google Sheets (slow, for Mac Dev)
        print("Local files not found. Fetching from Google Sheets...")
        base_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        
        # SSL Context hack for Mac local dev
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        
        df_report = pd.read_csv(f"{base_url}&gid={GID_REPORT}")
        df_details = pd.read_csv(f"{base_url}&gid={GID_DETAILS}")
    
    return df_report, df_details

def clean_currency(series):
    """Remove NT$, comma and convert to float"""
    if series.dtype == 'object':
        return pd.to_numeric(series.astype(str).str.replace(r'[NT\$,]', '', regex=True), errors='coerce').fillna(0)
    return pd.to_numeric(series, errors='coerce').fillna(0)

def preprocess_data(df_report, df_details):
    # --- 1. Filter Cancelled Orders ---
    # Report: '狀態' (Chinese)
    # Details: 'Status' (English)
    
    if '狀態' in df_report.columns:
        df_report = df_report[df_report['狀態'] != '已取消'] # Assuming Chinese '已取消' or English 'Cancelled'
        df_report = df_report[df_report['狀態'] != 'Cancelled']

    if 'Status' in df_details.columns:
        df_details = df_details[df_details['Status'] != 'Cancelled']
        df_details = df_details[df_details['Status'] != '已取消']

    # --- 2. Parse Dates & Times ---
    # Report
    if 'date' in df_report.columns:
        df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
    
    # Combine Date + Time for segmentation
    # Report uses '時間' (e.g., 11:03:09)
    if '時間' in df_report.columns and 'date' in df_report.columns:
        df_report['Datetime'] = pd.to_datetime(df_report['date'].astype(str) + ' ' + df_report['時間'].astype(str), errors='coerce')
    
    # Details
    if 'date' in df_details.columns:
        df_details['Date_Parsed'] = pd.to_datetime(df_details['date'], errors='coerce')

    # --- 3. Clean Currency ---
    # Report: '總計'
    if '總計' in df_report.columns:
        df_report['總計'] = clean_currency(df_report['總計'])

    # Details: 'Item Amount(TWD)' or 'Order Total(TWD)'
    if 'Order Total(TWD)' in df_details.columns:
        df_details['Order Total(TWD)'] = clean_currency(df_details['Order Total(TWD)'])

    # --- 4. Logic: Time Segmentation (Lunch < 16:00 <= Dinner) ---
    def get_period(dt):
        if pd.isnull(dt): return 'Unknown'
        return '中午 (Lunch)' if dt.hour < 16 else '晚上 (Dinner)'

    if 'Datetime' in df_report.columns:
        df_report['Period'] = df_report['Datetime'].apply(get_period)
    else:
        df_report['Period'] = 'Unknown'
    
    # --- 5. Logic: Main Dish Identification (Customer Count) ---
    # Details: 'Item Name' (English Header)
    # Rules: Contains "麵" or "飯"
    
    df_details['Is_Main_Dish'] = False
    
    target_col = 'Item Name'
    if target_col in df_details.columns:
        # Filter for Main Dish
        mask = df_details[target_col].astype(str).str.contains('麵|飯', regex=True)
        df_details.loc[mask, 'Is_Main_Dish'] = True
    
    return df_report, df_details

# --- Main App ---
try:
    with st.spinner('正在讀取並處理數據...'):
        df_report_raw, df_details_raw = load_data()
        df_report, df_details = preprocess_data(df_report_raw, df_details_raw)

    st.title("🍜 滾麵 (Gun Mian) 智慧營運報表")
    
    # --- 1. Sidebar: Date & Filter Controls ---
    st.sidebar.header("📅 日期與篩選")
    
    filter_mode = st.sidebar.radio(
        "選擇區間模式",
        ["今日 (Today)", "昨日 (Yesterday)", "本週 (This Week)", "近 7 天", "本月 (This Month)", "近 30 天", "自訂範圍"],
        index=4
    )
    
    today = pd.Timestamp.now().normalize()
    start_date = today
    end_date = today

    if filter_mode == "今日 (Today)":
        start_date = today
        end_date = today
    elif filter_mode == "昨日 (Yesterday)":
        start_date = today - timedelta(days=1)
        end_date = start_date
    elif filter_mode == "本週 (This Week)":
        start_date = today - timedelta(days=today.weekday()) # Monday
        end_date = today
    elif filter_mode == "近 7 天":
        start_date = today - timedelta(days=7)
        end_date = today
    elif filter_mode == "本月 (This Month)":
        start_date = today.replace(day=1)
        end_date = today
    elif filter_mode == "近 30 天":
        start_date = today - timedelta(days=30)
        end_date = today
    else:
        # Custom
        d_range = st.sidebar.date_input("選擇日期", [today - timedelta(days=7), today])
        if len(d_range) == 2:
            start_date = pd.to_datetime(d_range[0])
            end_date = pd.to_datetime(d_range[1])
        else:
            start_date = pd.to_datetime(d_range[0])
            end_date = start_date

    # Apply Date Filter
    mask_report = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    filtered_report = df_report.loc[mask_report]
    
    mask_details = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
    filtered_details = df_details.loc[mask_details]

    # --- 2. Key Metrics Calculation ---
    
    # Revenue (Total from Report)
    total_revenue = filtered_report['總計'].sum()
    
    # Order Count (Transactions)
    total_transactions = len(filtered_report)
    
    # Customer Count (Main Dish Count from Details)
    # Column: 'Item Quantity'
    if 'Item Quantity' in filtered_details.columns:
        filtered_details['Item Quantity'] = pd.to_numeric(filtered_details['Item Quantity'], errors='coerce').fillna(0)
        main_dish_count = filtered_details[filtered_details['Is_Main_Dish']]['Item Quantity'].sum()
    else:
        main_dish_count = 0
        st.error("找不到 'Item Quantity' 欄位")

    # Avg Spend
    avg_spend_per_customer = total_revenue / main_dish_count if main_dish_count > 0 else 0
    
    # Display Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 總營業額", f"${total_revenue:,.0f}")
    col2.metric("🍜 來客數 (主食)", f"{main_dish_count:,.0f} 人")
    col3.metric("🧾 訂單數 (筆)", f"{total_transactions:,.0f}")
    col4.metric("👤 平均客單價", f"${avg_spend_per_customer:,.0f}")
    
    st.divider()

    # --- 3. Charts & Segments ---
    
    # Row 1: Revenue Trend & Period Breakdown
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("📈 營業額趨勢")
        if 'Period' in filtered_report.columns and not filtered_report.empty:
            daily_period_rev = filtered_report.groupby(['Date_Parsed', 'Period'])['總計'].sum().reset_index()
            fig_trend = px.bar(
                daily_period_rev, 
                x='Date_Parsed', 
                y='總計', 
                color='Period',
                title='每日營業額 (分時段)',
                labels={'Date_Parsed': '日期', '總計': '金額', 'Period': '時段'},
                barmode='stack'
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("無資料可顯示趨勢圖")

    with c2:
        st.subheader("☀️🌙 中午 vs 晚上")
        if 'Period' in filtered_report.columns and not filtered_report.empty:
            period_sum = filtered_report.groupby('Period')['總計'].sum().reset_index()
            fig_pie = px.pie(
                period_sum, 
                values='總計', 
                names='Period', 
                hole=0.4,
                color='Period',
                color_discrete_map={'中午 (Lunch)': '#FFC107', '晚上 (Dinner)': '#3F51B5'}
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("無資料可顯示時段分佈")

    # Row 2: Top Items
    st.subheader("🏆 熱銷品項排行 (Top 15)")
    if 'Item Name' in filtered_details.columns and 'Item Quantity' in filtered_details.columns:
        # Filter out "NaN" item names (which are order summary rows)
        item_sales_df = filtered_details.dropna(subset=['Item Name'])
        
        # Group by Item Name
        item_sales = item_sales_df.groupby('Item Name')['Item Quantity'].sum().reset_index()
        item_sales = item_sales.sort_values(by='Item Quantity', ascending=False).head(15)
        
        fig_items = px.bar(
            item_sales, 
            x='Item Quantity', 
            y='Item Name', 
            orientation='h',
            title='銷售數量排行',
            labels={'Item Quantity': '數量', 'Item Name': '品項'},
            text='Item Quantity'
        )
        fig_items.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_items, use_container_width=True)
    else:
        st.warning("無法分析熱銷品項 (找不到 Item Name 或 Item Quantity 欄位)")

    # --- Debug Information (Hidden) ---
    with st.expander("查看原始數據 Source Data"):
        st.write("Report Data:", filtered_report.head())
        st.write("Details Data:", filtered_details.head())

except Exception as e:
    st.error(f"系統發生錯誤: {e}")
