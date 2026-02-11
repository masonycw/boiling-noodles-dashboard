import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import os

# --- 1. Config ---
st.set_page_config(
    page_title="滾麵智慧營運報表",
    page_icon="🍜",
    layout="wide"
)

# --- 2. Constants & Loading ---
SHEET_ID = "1hdCvSCZ_4gSSGQxtvW8xCqBNCBAO5H3chCocn2N8qAY"
GID_REPORT = "0"
GID_DETAILS = "1988676024"
LOCAL_DATA_DIR = "/home/eats365/data"

# Taiwan Holidays (2024-2025)
# Includes National Holidays and Special Leaves
tw_holidays = [
    # 2024
    "2024-01-01", "2024-02-08", "2024-02-09", "2024-02-10", "2024-02-11", "2024-02-12", "2024-02-13", "2024-02-14",
    "2024-02-28", "2024-04-04", "2024-04-05", "2024-05-01", "2024-06-10", "2024-09-17", "2024-10-10",
    # 2025
    "2025-01-01", "2025-01-25", "2025-01-26", "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", 
    "2025-02-01", "2025-02-02", "2025-02-28", "2025-04-03", "2025-04-04", "2025-04-05", "2025-04-06", 
    "2025-05-01", "2025-05-31", "2025-06-01", "2025-06-02", "2025-10-04", "2025-10-05", "2025-10-06", 
    "2025-05-01", "2025-05-31", "2025-06-01", "2025-06-02", "2025-10-04", "2025-10-05", "2025-10-06", 
    "2025-10-10", "2025-10-11", "2025-10-12",
    # 2026 (Estimated / Partial)
    "2026-01-01", "2026-02-13", "2026-02-14", "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18", # CNY
    "2026-02-28", "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06", "2026-05-01", "2026-06-19", 
    "2026-09-27", "2026-10-10"
]
TW_HOLIDAYS_SET = set(tw_holidays)

@st.cache_data(ttl=300)
def load_data():
    local_report = os.path.join(LOCAL_DATA_DIR, "history_report.csv")
    local_details = os.path.join(LOCAL_DATA_DIR, "history_details.csv")
    
    if os.path.exists(local_report) and os.path.exists(local_details):
        df_report = pd.read_csv(local_report)
        df_details = pd.read_csv(local_details)
    else:
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
    if '狀態' in df_report.columns:
        # Exclude Cancelled AND Closed (per user feedback, Closed seems to be non-revenue)
        # Target: 50563 (Completed only) vs 51581 (Completed + Closed)
        df_report = df_report[~df_report['狀態'].astype(str).str.contains('取消|Cancelled|已關閉|Closed', case=False, na=False)]
    if 'Status' in df_details.columns:
        df_details = df_details[~df_details['Status'].astype(str).str.contains('取消|Cancelled|已關閉|Closed', case=False, na=False)]

    if 'date' in df_report.columns:
        df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
    if 'date' in df_details.columns:
        df_details['Date_Parsed'] = pd.to_datetime(df_details['date'], errors='coerce')

    # Combine DateTime (Robust Fix)
    if '時間' in df_report.columns and 'Date_Parsed' in df_report.columns:
        # 1. Parse '時間' column flexibly (handles '11:00:00' AND '2026-01-24 11:00:00')
        temp_time = pd.to_datetime(df_report['時間'], errors='coerce')
        
        # 2. Extract HH:MM:SS string
        # If temp_time is NaT, fill with 00:00:00
        time_str = temp_time.dt.strftime('%H:%M:%S').fillna('00:00:00')
        
        # 3. Combine with trusted 'Date_Parsed'
        df_report['Datetime'] = pd.to_datetime(
            df_report['Date_Parsed'].dt.strftime('%Y-%m-%d') + ' ' + time_str,
            errors='coerce'
        )

    # Currency
    if '總計' in df_report.columns:
        df_report['總計'] = clean_currency(df_report['總計'])
    if 'Order Total(TWD)' in df_details.columns:
        df_details['Order Total(TWD)'] = clean_currency(df_details['Order Total(TWD)'])
    if 'Item Amount(TWD)' in df_details.columns:
        df_details['Item Amount(TWD)'] = clean_currency(df_details['Item Amount(TWD)'])
    if 'Item Quantity' in df_details.columns:
        df_details['Item Quantity'] = pd.to_numeric(df_details['Item Quantity'], errors='coerce').fillna(0)

    # --- Deduplicate Modifier Rows ---
    if 'Modifier Name' in df_details.columns:
        df_details = df_details[df_details['Modifier Name'].isna() | (df_details['Modifier Name'] == '')]

    # --- Categorization (SKU -> Name) ---
    clean_cols = {c: c.strip() for c in df_details.columns}
    df_details.rename(columns=clean_cols, inplace=True)
    
    def infer_category(row):
        # 1. Try SKU (if valid)
        sku = str(row.get('Product SKU', ''))
        # If user provides mapping later, implement here. 
        # For now, if SKU implies category (e.g., A01), we could use it.
        # Fallback to Name Inference as requested if SKU missing/not useful
        
        name = str(row.get('Item Name', ''))
        if '麵' in name: return '麵類 (Noodle)'
        if '飯' in name: return '飯類 (Rice)'
        if any(x in name for x in ['湯', '羹']): return '湯品 (Soup)'
        if any(x in name for x in ['茶', '飲', '拿鐵', '咖啡', '可樂', '雪碧']): return '飲料 (Drink)'
        if any(x in name for x in ['菜', '豆干', '皮蛋', '肉', '蛋', '豆腐']): return '小菜 (Side Dish)'
        return '其他 (Others)'
        
    df_details['Category'] = df_details.apply(infer_category, axis=1)

    # --- Day Type (Weekday/Holiday) ---
    def get_day_type(dt):
        if pd.isnull(dt): return 'Unknown'
        d_str = dt.strftime('%Y-%m-%d')
        if d_str in TW_HOLIDAYS_SET: return '特別假日 (Holiday)'
        if dt.weekday() >= 5: return '週末 (Weekend)'
        return '平日 (Weekday)'
    
    df_report['Day_Type'] = df_report['Date_Parsed'].apply(get_day_type)
    
    # --- Period (Lunch/Dinner) ---
    def get_period(dt):
        if pd.isnull(dt): return 'Unknown'
        return '中午 (Lunch)' if dt.hour < 16 else '晚上 (Dinner)'
    df_report['Period'] = df_report['Datetime'].apply(get_period) if 'Datetime' in df_report.columns else 'Unknown'

    # --- Main Dish Logic ---
    df_details['Is_Main_Dish'] = False
    mask_name = df_details['Item Name'].astype(str).str.contains('麵|飯', regex=True, na=False)
    mask_exclude_wrapper = pd.Series([True] * len(df_details))
    if 'Item Type' in df_details.columns:
        mask_is_wrapper = df_details['Item Type'].astype(str).str.fullmatch('Combo Item', case=False, na=False)
        mask_exclude_wrapper = ~mask_is_wrapper
    df_details.loc[mask_name & mask_exclude_wrapper, 'Is_Main_Dish'] = True

    return df_report, df_details

def calculate_delta(current, previous):
    if previous == 0: return None
    return (current - previous) / previous

# --- 3. Main App ---
try:
    with st.spinner('數據處理中...'):
        df_report_raw, df_details_raw = load_data()
        df_report, df_details = preprocess_data(df_report_raw, df_details_raw)

    if df_report.empty:
        st.warning("尚未載入資料")
        st.stop()

    st.sidebar.title("🍜 滾麵 Dashboard")
    view_mode = st.sidebar.radio("功能切換", ["📊 營運總覽", "🍟 商品分析", "👥 會員查詢"])
    st.sidebar.divider()

    # --- Dynamic Date Filters ---
    st.sidebar.header("📅 日期篩選")
    
    # Generate Last 6 Months Options
    today = date.today()
    month_options = []
    for i in range(6):
        d = today - relativedelta(months=i)
        month_options.append(d.strftime("%Y-%m"))
    
    filter_opts = ["今日 (Today)", "昨日 (Yesterday)", "本週 (This Week)", "本月 (This Month)", 
                   "近 28 天", "近 30 天", "自訂範圍"] + month_options
                   
    filter_mode = st.sidebar.selectbox("快速區間", filter_opts, index=3)

    # Date Logic
    start_date, end_date = today, today # defaults
    
    if filter_mode == "今日 (Today)":
        start_date = end_date = pd.Timestamp(today)
    elif filter_mode == "昨日 (Yesterday)":
        start_date = end_date = pd.Timestamp(today - timedelta(days=1))
    elif filter_mode == "本週 (This Week)":
        start_date = pd.Timestamp(today - timedelta(days=today.weekday()))
        end_date = pd.Timestamp(today)
    elif filter_mode == "本月 (This Month)":
        start_date = pd.Timestamp(today.replace(day=1))
        end_date = pd.Timestamp(today)
    elif filter_mode == "近 28 天":
        start_date = pd.Timestamp(today - timedelta(days=28))
        end_date = pd.Timestamp(today)
    elif filter_mode == "近 30 天":
        start_date = pd.Timestamp(today - timedelta(days=30))
        end_date = pd.Timestamp(today)
    elif filter_mode in month_options:
        # specific month
        y, m = map(int, filter_mode.split('-'))
        start_date = pd.Timestamp(date(y, m, 1))
        end_date = pd.Timestamp(start_date + relativedelta(months=1, days=-1))
    else:
        d = st.sidebar.date_input("選擇日期", [today - timedelta(days=7), today])
        start_date = pd.to_datetime(d[0]) if len(d) > 0 else pd.Timestamp(today)
        end_date = pd.to_datetime(d[1]) if len(d) > 1 else start_date

    # Prev Period Logic
    duration = end_date - start_date
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - duration
    
    # Filter Data (Current)
    mask_rep = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    df_rep = df_report.loc[mask_rep]
    mask_det = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
    df_det = df_details.loc[mask_det]

    # Filter Data (Previous)
    mask_rep_prev = (df_report['Date_Parsed'] >= prev_start) & (df_report['Date_Parsed'] <= prev_end)
    df_rep_prev = df_report.loc[mask_rep_prev]
    mask_det_prev = (df_details['Date_Parsed'] >= prev_start) & (df_details['Date_Parsed'] <= prev_end)
    df_det_prev = df_details.loc[mask_det_prev]

    # --- VIEW 1: 營運總覽 ---
    if view_mode == "📊 營運總覽":
        st.title(f"📊 營運總覽 ({start_date.date()} ~ {end_date.date()})")
        
        # Metrics Calculation
        curr_rev = df_rep['總計'].sum()
        prev_rev = df_rep_prev['總計'].sum()
        
        curr_vis = df_det[df_det['Is_Main_Dish']]['Item Quantity'].sum()
        prev_vis = df_det_prev[df_det_prev['Is_Main_Dish']]['Item Quantity'].sum()
        
        curr_txs = len(df_rep)
        prev_txs = len(df_rep_prev)
        
        curr_avg = curr_rev / curr_vis if curr_vis > 0 else 0
        prev_avg = prev_rev / prev_vis if prev_vis > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰總營業額", f"${curr_rev:,.0f}", f"{calculate_delta(curr_rev, prev_rev):.1%}" if prev_rev else None)
        c2.metric("🍜來客數", f"{curr_vis:,.0f}", f"{calculate_delta(curr_vis, prev_vis):.1%}" if prev_vis else None)
        c3.metric("🧾訂單數", f"{curr_txs:,.0f}", f"{calculate_delta(curr_txs, prev_txs):.1%}" if prev_txs else None)
        c4.metric("👤平均客單價", f"${curr_avg:,.0f}", f"{calculate_delta(curr_avg, prev_avg):.1%}" if prev_avg else None)
        st.divider()

        # Row 1: Revenue Trend & Table
        col_L, col_R = st.columns([2, 1])
        with col_L:
            st.subheader("📈 營業額趨勢")
            if not df_rep.empty:
                daily = df_rep.groupby(['Date_Parsed', 'Period'])['總計'].sum().reset_index()
                fig = px.bar(daily, x='Date_Parsed', y='總計', color='Period', barmode='stack', title=None,
                             color_discrete_map={'中午 (Lunch)': '#FFC107', '晚上 (Dinner)': '#3F51B5'})
                st.plotly_chart(fig, use_container_width=True)
                
                # Table below chart
                with st.expander("詳細數字 (每日營收表)", expanded=False):
                    pivot_table = daily.pivot(index='Date_Parsed', columns='Period', values='總計').fillna(0)
                    pivot_table['Total'] = pivot_table.sum(axis=1)
                    st.dataframe(pivot_table.style.format("{:,.0f}"), use_container_width=True)
        
        with col_R:
            st.subheader("📅 平假日平均 (數字)")
            if not df_rep.empty:
                daily_rev = df_rep.groupby(['Date_Parsed', 'Day_Type'])['總計'].sum().reset_index()
                type_avg = daily_rev.groupby('Day_Type')['總計'].mean()
                
                # Display Numbers Only
                for dtype in ['平日 (Weekday)', '週末 (Weekend)', '特別假日 (Holiday)']:
                    val = type_avg.get(dtype, 0)
                    st.metric(f"平均 {dtype}", f"${val:,.0f}")

            # List Special Holidays
            st.write("---")
            st.subheader("📌 期間特別假日")
            special = df_rep[df_rep['Day_Type'] == '特別假日 (Holiday)']['Date_Parsed'].dt.date.unique()
            if len(special) > 0:
                for d in sorted(special):
                    st.write(f"- {d}")
            else:
                st.info("無")

    # --- VIEW 2: 商品分析 ---
    elif view_mode == "🍟 商品分析":
        st.title("🍟 商品銷售分析")
        
        if 'Item Name' in df_det.columns:
            df_items = df_det.dropna(subset=['Item Name'])
            
            # --- Auto Comparison (Metrics) ---
            curr_qty = df_items['Item Quantity'].sum()
            prev_qty = df_det_prev['Item Quantity'].sum() if not df_det_prev.empty else 0
            
            c1, c2 = st.columns(2)
            c1.metric("總銷售數量", f"{curr_qty:,.0f}", f"{calculate_delta(curr_qty, prev_qty):.1%}" if prev_qty else None)
            
            # --- Category Share (Base = Category Total) is implied in Pie Chart ---
            st.subheader("📊 類別銷售佔比")
            item_stats = df_items.groupby(['Category', 'Item Name']).agg({
                'Item Quantity': 'sum',
                'Item Amount(TWD)': 'sum'
            }).reset_index()
            
            cat_sum = item_stats.groupby('Category')['Item Amount(TWD)'].sum().reset_index()
            fig_pie = px.pie(cat_sum, values='Item Amount(TWD)', names='Category')
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # --- Detail List ---
            st.subheader("📋 詳細清單")
            cats = ['全部'] + list(item_stats['Category'].unique())
            sel_cat = st.selectbox("篩選類別", cats)
            
            if sel_cat != '全部':
                show_df = item_stats[item_stats['Category'] == sel_cat].copy()
                # Calculate % within category
                cat_total = show_df['Item Amount(TWD)'].sum()
                show_df['Category Share %'] = (show_df['Item Amount(TWD)'] / cat_total * 100).round(1)
            else:
                show_df = item_stats.copy()
                # Calculate % within entire selection
                total = show_df['Item Amount(TWD)'].sum()
                show_df['Share %'] = (show_df['Item Amount(TWD)'] / total * 100).round(1)
                
            st.dataframe(show_df.sort_values('Item Quantity', ascending=False), use_container_width=True)
        else:
            st.error("找不到商品資料")

    # --- VIEW 3: 會員查詢 ---
    elif view_mode == "👥 會員查詢":
        st.title("👥 會員消費紀錄查詢")
        
        col_L, col_R = st.columns([1, 2])
        
        with col_L:
            phone_query = st.text_input("輸入電話或姓名:")
            # Independent Date Filter
            use_date = st.checkbox("限制日期範圍", value=False)
            if use_date:
                d_range = st.date_input("查詢區間", [today - timedelta(days=365), today])
                q_start = pd.to_datetime(d_range[0])
                q_end = pd.to_datetime(d_range[1]) if len(d_range)>1 else q_start
        
        col_phone = None
        col_name = None
        for c in ['Contact', 'Customer Tel', '客戶電話']:
            if c in df_report.columns: col_phone = c; break
        for c in ['Customer Name', '客戶姓名']:
            if c in df_report.columns: col_name = c; break

        if (col_phone or col_name) and phone_query:
            # 1. Base Filter (Name or Phone)
            mask = pd.Series([False]*len(df_report))
            if col_phone: mask |= df_report[col_phone].astype(str).str.contains(phone_query, na=False)
            if col_name: mask |= df_report[col_name].astype(str).str.contains(phone_query, na=False)
            
            member_data = df_report[mask].copy()
            
            # 2. Date Filter (Optional)
            if use_date:
                member_data = member_data[(member_data['Date_Parsed'] >= q_start) & (member_data['Date_Parsed'] <= q_end)]
            
            if not member_data.empty:
                # Basic Info
                name_disp = member_data[col_name].iloc[0] if col_name else "Unknown"
                phone_disp = member_data[col_phone].iloc[0] if col_phone else "Unknown"
                
                # Stats
                m_total = member_data['總計'].sum()
                m_visits = len(member_data)
                
                st.success(f"會員: {name_disp} / 電話: {phone_disp}")
                c1, c2 = st.columns(2)
                c1.metric("累積消費金額", f"${m_total:,.0f}")
                c2.metric("累積來店次數", f"{m_visits} 次")
                
                # 3. Item History (Cross reference with details)
                st.subheader("🍔 歷史購買品項統計")
                if 'Order Number' in member_data.columns and 'Order Number' in df_details.columns:
                    order_ids = member_data['Order Number'].unique()
                    m_details = df_details[df_details['Order Number'].isin(order_ids)]
                    
                    if not m_details.empty:
                        item_hist = m_details.groupby('Item Name')['Item Quantity'].sum().reset_index()
                        item_hist = item_hist.sort_values('Item Quantity', ascending=False)
                        st.dataframe(item_hist, use_container_width=True)
                    else:
                        st.info("無商品明細資料")
                
                # 4. Transaction Log
                st.subheader("📜 交易紀錄")
                st.dataframe(member_data[['date', '時間', '總計', '單類型']].sort_values('date', ascending=False))
                
            else:
                st.warning("查無符合資料")

except Exception as e:
    st.error(f"系統錯誤: {e}")
