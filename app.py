import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import os
import re

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

# Taiwan Holidays (2024-2026)
tw_holidays = [
    # 2024
    "2024-01-01", "2024-02-08", "2024-02-09", "2024-02-10", "2024-02-11", "2024-02-12", "2024-02-13", "2024-02-14",
    "2024-02-28", "2024-04-04", "2024-04-05", "2024-05-01", "2024-06-10", "2024-09-17", "2024-10-10", "2024-12-25",
    # 2025
    "2025-01-01", "2025-01-25", "2025-01-26", "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", 
    "2025-02-01", "2025-02-02", "2025-02-28", "2025-04-03", "2025-04-04", "2025-04-05", "2025-04-06", 
    "2025-05-01", "2025-05-31", "2025-06-01", "2025-06-02", "2025-10-04", "2025-10-05", "2025-10-06", 
    "2025-10-10", "2025-10-11", "2025-10-12", "2025-12-25",
    # 2026
    "2026-01-01", "2026-02-13", "2026-02-14", "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-02-28", "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06", "2026-05-01", "2026-06-19", 
    "2026-09-27", "2026-10-10", "2026-12-25"
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
        # Exclude Cancelled, Closed, AND Void (作廢)
        # Matches user's manual count of 975 visitors for Feb 2026
        df_report = df_report[~df_report['狀態'].astype(str).str.contains('取消|Cancelled|已關閉|Closed|Void|作廢', case=False, na=False)]
    if 'Status' in df_details.columns:
        df_details = df_details[~df_details['Status'].astype(str).str.contains('取消|Cancelled|已關閉|Closed|Void|作廢', case=False, na=False)]

    if 'date' in df_report.columns:
        df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
    if 'date' in df_details.columns:
        df_details['Date_Parsed'] = pd.to_datetime(df_details['date'], errors='coerce')

    # Combine DateTime
    if '時間' in df_report.columns and 'Date_Parsed' in df_report.columns:
        temp_time = pd.to_datetime(df_report['時間'], errors='coerce')
        time_str = temp_time.dt.strftime('%H:%M:%S').fillna('00:00:00')
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

    # --- Categorization (Phase 5: SKU Based) ---
    clean_cols = {c: c.strip() for c in df_details.columns}
    df_details.rename(columns=clean_cols, inplace=True)
    
    def infer_category(row):
        sku = str(row.get('Product SKU', '')).strip().upper()
        
        # Priority: Check SKU First Letter
        if len(sku) > 0:
            prefix = sku[0]
            if prefix == 'A': return 'A 湯麵 (Soup Noodle)'
            if prefix == 'B': return 'B 乾麵/飯 (Dry/Rice)'
            if prefix == 'C': return 'D 小菜 (Sides)' # SKU C is small sides
            if prefix == 'D': return 'C 單點/青菜 (Alacarte/Veg)' # SKU D contains Veg/Meat
            if prefix == 'E': return 'C 單點/青菜 (Alacarte/Veg)' # SKU E is Soup, treat as Alacarte
            if prefix == 'F': return 'E 飲料 (Drink)'
            if prefix == 'S': return 'S 套餐 (Set)'
            if prefix == 'M': return 'D 小菜 (Sides)' # 40元小菜

        # Fallback (Name based) if SKU missing
        name = str(row.get('Item Name', ''))
        item_type = str(row.get('Item Type', ''))
        
        if 'Set Meal' in item_type or 'Combo Item' in item_type:
             if 'Single Item' not in item_type: return 'S 套餐 (Set)'
        
        if '麵' in name and '湯' in name: return 'A 湯麵 (Soup Noodle)'
        if ('麵' in name and '湯' not in name) or '飯' in name: return 'B 乾麵/飯 (Dry Noodle/Rice)'
        if any(x in name for x in ['茶', '飲', '拿鐵', '咖啡', '可樂', '雪碧']): return 'E 飲料 (Drink)'
        if any(x in name for x in ['豆干', '皮蛋', '肉', '蛋', '高麗菜', '水蓮']): return 'C 單點/青菜 (Alacarte/Veg)'
        return 'G 其他 (Others)'
        
    df_details['Category'] = df_details.apply(infer_category, axis=1)

    # --- Day Type ---
    def get_day_type(dt):
        if pd.isnull(dt): return 'Unknown'
        d_str = dt.strftime('%Y-%m-%d')
        if d_str in TW_HOLIDAYS_SET: return '特別假日 (Holiday)'
        if dt.weekday() >= 5: return '週末 (Weekend)'
        return '平日 (Weekday)'
    df_report['Day_Type'] = df_report['Date_Parsed'].apply(get_day_type)
    
    # --- Period ---
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

    # --- Date Filters ---
    st.sidebar.header("📅 日期篩選")
    today = date.today()
    month_options = [ (today - relativedelta(months=i)).strftime("%Y-%m") for i in range(6) ]
    filter_opts = ["今日 (Today)", "昨日 (Yesterday)", "本週 (This Week)", "本月 (This Month)", 
                   "近 28 天", "近 30 天", "自訂範圍"] + month_options
    filter_mode = st.sidebar.selectbox("快速區間", filter_opts, index=3)

    start_date, end_date = today, today 
    if filter_mode == "今日 (Today)": start_date = end_date = pd.Timestamp(today)
    elif filter_mode == "昨日 (Yesterday)": start_date = end_date = pd.Timestamp(today - timedelta(days=1))
    elif filter_mode == "本週 (This Week)": start_date = pd.Timestamp(today - timedelta(days=today.weekday())); end_date = pd.Timestamp(today)
    elif filter_mode == "本月 (This Month)": start_date = pd.Timestamp(today.replace(day=1)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 28 天": start_date = pd.Timestamp(today - timedelta(days=28)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 30 天": start_date = pd.Timestamp(today - timedelta(days=30)); end_date = pd.Timestamp(today)
    elif filter_mode in month_options: y, m = map(int, filter_mode.split('-')); start_date = pd.Timestamp(date(y, m, 1)); end_date = pd.Timestamp(start_date + relativedelta(months=1, days=-1))
    else: d = st.sidebar.date_input("選擇日期", [today - timedelta(days=7), today]); start_date = pd.to_datetime(d[0]) if len(d) > 0 else pd.Timestamp(today); end_date = pd.to_datetime(d[1]) if len(d) > 1 else start_date

    # Prev Period
    duration = end_date - start_date
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - duration
    
    # Filter
    mask_rep = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    df_rep = df_report.loc[mask_rep].copy()
    mask_det = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
    df_det = df_details.loc[mask_det].copy()
    mask_rep_prev = (df_report['Date_Parsed'] >= prev_start) & (df_report['Date_Parsed'] <= prev_end)
    df_rep_prev = df_report.loc[mask_rep_prev]
    mask_det_prev = (df_details['Date_Parsed'] >= prev_start) & (df_details['Date_Parsed'] <= prev_end)
    df_det_prev = df_details.loc[mask_det_prev]

    # --- VIEW 1: 營運總覽 ---
    if view_mode == "📊 營運總覽":
        st.title(f"📊 營運總覽 ({start_date.date()} ~ {end_date.date()})")
        
        # Metrics
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

        # Graphs: Revenue (Top)
        col_L, col_R = st.columns([2, 1])
        with col_L:
            st.subheader("📈 營業額趨勢 (時段)")
            if not df_rep.empty:
                daily_period = df_rep.groupby(['Date_Parsed', 'Period'])['總計'].sum().reset_index()
                daily_total = df_rep.groupby('Date_Parsed')['總計'].sum().reset_index().rename(columns={'總計': 'Daily_Total'})
                daily_period = pd.merge(daily_period, daily_total, on='Date_Parsed', how='left')
                fig = px.bar(
                    daily_period, x='Date_Parsed', y='總計', color='Period', 
                    barmode='stack', color_discrete_map={'中午 (Lunch)': '#FFC107', '晚上 (Dinner)': '#3F51B5'},
                    custom_data=['Daily_Total']
                )
                fig.update_traces(hovertemplate="Date: %{x}<br>Rev: $%{y:,.0f}<br>Total: $%{customdata[0]:,.0f}")
                st.plotly_chart(fig, use_container_width=True)
        
        with col_R:
            st.subheader("📅 平假日平均")
            if not df_rep.empty:
                daily_rev = df_rep.groupby(['Date_Parsed', 'Day_Type'])['總計'].sum().reset_index()
                type_avg = daily_rev.groupby('Day_Type')['總計'].mean()
                daily_rev_prev = df_rep_prev.groupby(['Date_Parsed', 'Day_Type'])['總計'].sum().reset_index() if not df_rep_prev.empty else pd.DataFrame()
                prev_type_avg = daily_rev_prev.groupby('Day_Type')['總計'].mean() if not daily_rev_prev.empty else pd.Series()

                for dtype in ['平日 (Weekday)', '週末 (Weekend)', '特別假日 (Holiday)']:
                    val = type_avg.get(dtype, 0)
                    pval = prev_type_avg.get(dtype, 0)
                    st.metric(f"平均 {dtype}", f"${val:,.0f}", f"{calculate_delta(val, pval):.1%}" if pval else None)
            
            st.write("---")
            st.subheader("📌 特別假日")
            special = df_rep[df_rep['Day_Type'] == '特別假日 (Holiday)']['Date_Parsed'].dt.date.unique()
            if len(special) > 0:
                for d in sorted(special): st.write(f"- {d}")

        st.divider()
        st.subheader("🛵 每日營收結構")
        col_type = '單類型' if '單類型' in df_rep.columns else 'Order Type'
        if col_type in df_rep.columns:
            daily_type = df_rep.groupby(['Date_Parsed', col_type])['總計'].sum().reset_index()
            fig_type = px.bar(daily_type, x='Date_Parsed', y='總計', color=col_type, barmode='stack')
            st.plotly_chart(fig_type, use_container_width=True)

        st.divider()
        
        # Graphs: Visitor & ATV (Moved to Bottom)
        c_vis, c_atv = st.columns(2)
        with c_vis:
            st.subheader("👥 來客數趨勢")
            if not df_rep.empty:
                daily_vis = df_det[df_det['Is_Main_Dish']].groupby('Date_Parsed')['Item Quantity'].sum().reset_index()
                fig_v = px.line(daily_vis, x='Date_Parsed', y='Item Quantity', markers=True)
                st.plotly_chart(fig_v, use_container_width=True)
        
        with c_atv:
            st.subheader("💰 客單價趨勢")
            if not df_rep.empty and not daily_vis.empty:
                daily_rev_chart = df_rep.groupby('Date_Parsed')['總計'].sum().reset_index()
                daily_atv = pd.merge(daily_rev_chart, daily_vis, on='Date_Parsed', how='inner')
                daily_atv['ATV'] = daily_atv['總計'] / daily_atv['Item Quantity']
                fig_a = px.line(daily_atv, x='Date_Parsed', y='ATV', markers=True)
                st.plotly_chart(fig_a, use_container_width=True)
        
        st.divider()
        st.subheader("📋 原始報表數據")
        st.dataframe(df_rep, use_container_width=True)

    # --- VIEW 2: 商品分析 ---
    elif view_mode == "🍟 商品分析":
        st.title("🍟 商品銷售分析")
        
        if 'Item Name' in df_det.columns:
            df_items = df_det.dropna(subset=['Item Name'])
            
            curr_qty = df_items['Item Quantity'].sum()
            prev_qty = df_det_prev['Item Quantity'].sum() if not df_det_prev.empty else 0
            
            c1, c2 = st.columns(2)
            c1.metric("總銷售數量", f"{curr_qty:,.0f}", f"{calculate_delta(curr_qty, prev_qty):.1%}" if prev_qty else None)
            
            # 1. Category Breakdown
            st.subheader("📊 類別銷售表現")
            cat_stats_curr = df_items.groupby('Category').agg({'Item Quantity': 'sum', 'Item Amount(TWD)': 'sum'}).reset_index()
            cat_stats_prev = df_det_prev.groupby('Category').agg({'Item Quantity': 'sum', 'Item Amount(TWD)': 'sum'}).reset_index() if not df_det_prev.empty else pd.DataFrame(columns=['Category', 'Item Quantity'])
            cat_comp = pd.merge(cat_stats_curr, cat_stats_prev, on='Category', how='left', suffixes=('', '_prev'))
            
            cols = st.columns(min(len(cat_stats_curr), 4))
            for i, row in cat_comp.iterrows():
                with cols[i % 4]:
                    val = row['Item Quantity']
                    pval = row['Item Quantity_prev']
                    st.metric(f"{row['Category'].split(' ')[0]}", f"{val:,.0f}", f"{calculate_delta(val, pval):.1%}" if pd.notnull(pval) else None)
            
            st.divider()
            
            # 2. Detail Analysis flow
            st.subheader("📈 類別與商品走勢")
            cats = sorted(list(df_items['Category'].unique()))
            sel_cat = st.selectbox("請先選擇類別 (查看細項)", cats, index=0)
            
            # Filter by Category
            cat_df = df_items[df_items['Category'] == sel_cat].copy()
            
            # Summary Table for Category
            cat_total_rev = cat_df['Item Amount(TWD)'].sum()
            cat_total_qty = cat_df['Item Quantity'].sum()
            
            summary = cat_df.groupby('Item Name').agg({
                'Item Quantity': 'sum', 
                'Item Amount(TWD)': 'sum'
            }).reset_index().sort_values('Item Quantity', ascending=False)
            
            summary['Rev %'] = (summary['Item Amount(TWD)'] / cat_total_rev * 100).map('{:.1f}%'.format)
            summary['Qty %'] = (summary['Item Quantity'] / cat_total_qty * 100).map('{:.1f}%'.format)
            
            c_table, c_trend = st.columns([1, 2])
            
            with c_table:
                st.write(f"**{sel_cat} 銷售排行**")
                st.dataframe(summary[['Item Name', 'Item Quantity', 'Item Amount(TWD)', 'Qty %', 'Rev %']], use_container_width=True)

            with c_trend:
                st.write(f"**{sel_cat} 商品過往走勢 (近 6 個月)**")
                # 6 Months logic
                end_m = date.today().replace(day=1) + relativedelta(months=1) - timedelta(days=1)
                start_m = (end_m - relativedelta(months=5)).replace(day=1)
                mask_6m = (df_details['Date_Parsed'] >= pd.Timestamp(start_m)) & (df_details['Date_Parsed'] <= pd.Timestamp(end_m))
                df_6m = df_details[mask_6m].copy()
                df_6m_cat = df_6m[df_6m['Category'] == sel_cat]
                
                # Default Text
                top5_items = summary['Item Name'].head(5).tolist()
                sel_items = st.multiselect("選擇商品繪圖", df_6m_cat['Item Name'].unique(), default=top5_items)
                
                if sel_items:
                    df_6m_cat['Month'] = df_6m_cat['Date_Parsed'].dt.strftime('%Y-%m')
                    trend_data = df_6m_cat[df_6m_cat['Item Name'].isin(sel_items)].groupby(['Month', 'Item Name'])['Item Quantity'].sum().reset_index()
                    fig_trend = px.line(trend_data, x='Month', y='Item Quantity', color='Item Name', markers=True)
                    st.plotly_chart(fig_trend, use_container_width=True)
            
            st.divider()
            st.subheader("📋 原始商品數據")
            st.dataframe(df_items, use_container_width=True)

    # --- VIEW 3: 會員查詢 ---
    elif view_mode == "👥 會員查詢":
        st.title("👥 會員消費紀錄查詢")
        
        col_L, col_R = st.columns([1, 2])
        with col_L:
            phone_query = st.text_input("輸入電話或姓名:")
            use_date = st.checkbox("限制日期範圍", value=False)
            q_start, q_end = today, today
            if use_date:
                d_range = st.date_input("查詢區間", [today - timedelta(days=365), today])
                q_start = pd.to_datetime(d_range[0]); q_end = pd.to_datetime(d_range[1]) if len(d_range)>1 else q_start
        
        # Fixed Column Names
        col_phone = '客戶電話' if '客戶電話' in df_report.columns else 'Contact'
        col_name = '客戶姓名' if '客戶姓名' in df_report.columns else 'Customer Name'

        if phone_query:
            query_clean = re.sub(r'\D', '', phone_query)
            mask = pd.Series([False]*len(df_report))
            
            if col_phone in df_report.columns and query_clean: 
                phone_col_clean = df_report[col_phone].astype(str).str.replace(r'\D', '', regex=True)
                mask |= phone_col_clean.str.contains(query_clean, na=False)
            
            if col_name in df_report.columns: 
                mask |= df_report[col_name].astype(str).str.contains(phone_query, na=False)
            
            member_data = df_report[mask].copy()
            if use_date: member_data = member_data[(member_data['Date_Parsed'] >= q_start) & (member_data['Date_Parsed'] <= q_end)]
            
            if not member_data.empty:
                name_disp = member_data[col_name].iloc[0] if col_name in member_data.columns else "Unknown"
                phone_disp = member_data[col_phone].iloc[0] if col_phone in member_data.columns else "Unknown"
                st.success(f"會員: {name_disp} / 電話: {phone_disp}")
                c1, c2 = st.columns(2)
                c1.metric("累積消費金額", f"${member_data['總計'].sum():,.0f}")
                c2.metric("累積來店次數", f"{len(member_data)} 次")
                
                st.subheader("🍔 歷史購買品項")
                if 'Order Number' in member_data.columns and 'Order Number' in df_details.columns:
                    target_orders = member_data['Order Number'].unique()
                    m_details = df_details[df_details['Order Number'].isin(target_orders)]
                    if not m_details.empty:
                        item_hist = m_details.groupby('Item Name')['Item Quantity'].sum().reset_index().sort_values('Item Quantity', ascending=False)
                        st.dataframe(item_hist, use_container_width=True)
                st.subheader("📜 交易紀錄")
                st.dataframe(member_data, use_container_width=True)
            else: st.warning("查無符合資料")
except Exception as e: st.error(f"系統錯誤: {e}")
