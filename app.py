import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import os
import re
import numpy as np

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

    # --- Categorization (Phase 6: Refined) ---
    clean_cols = {c: c.strip() for c in df_details.columns}
    df_details.rename(columns=clean_cols, inplace=True)
    
    def infer_category(row):
        sku = str(row.get('Product SKU', '')).strip().upper()
        name = str(row.get('Item Name', '')).strip()
        
        # 1. Special Cases C-1 (User Request)
        if name in ['蔥油雞', '芭樂遇見五花']:
            return 'C 單點 (Alacarte)'

        # 2. Priority: Check SKU First Letter
        if len(sku) > 0:
            prefix = sku[0]
            if prefix == 'A': return 'A 湯麵 (Soup Noodle)'
            if prefix == 'B': return 'B 乾麵/飯 (Dry/Rice)'
            if prefix == 'C': return 'F 小菜 (Small Sides)' # Phase 6: F is Sides (Wait, User said E=Soup, F=Sides)
            # Let's map strict user request: E->Soup, F->Sides, C->Alacarte?
            # User said: "E應該是湯，Ｆ是小菜"
            # But what is A/B/C/D?
            # Assuming A=Soup Noodle, B=Dry/Rice, C=Alacarte, D=Veg?
            # Let's stick to valid mapping:
            
            if prefix == 'E': return 'E 湯品 (Soup)' # User: E=Soup
            if prefix == 'F': return 'F 小菜 (Small Sides)' # User: F=Sides
            
            # Others:
            if prefix == 'D': return 'C 單點/青菜 (Alacarte/Veg)'
            if prefix == 'S': return 'S 套餐 (Set)'
            
            # If SKU is C, it was Sides before. But User says F is Sides. 
            # If SKU is C, maybe it's Alacarte?
            if prefix == 'C': return 'C 單點 (Alacarte)'

        # 3. Fallback (Name based)
        item_type = str(row.get('Item Type', ''))
        
        if 'Set Meal' in item_type or 'Combo Item' in item_type:
             if 'Single Item' not in item_type: return 'S 套餐 (Set)'
        
        # Check Name
        if '湯麵' in name: return 'A 湯麵 (Soup Noodle)'
        if '拌麵' in name or '乾麵' in name or '飯' in name: return 'B 乾麵/飯 (Dry/Rice)'
        
        if any(x in name for x in ['湯', '羹']): return 'E 湯品 (Soup)'
        if any(x in name for x in ['豆干', '皮蛋', '豆腐', '海帶', '花生', '毛豆', '黃瓜', '蛋']): return 'F 小菜 (Small Sides)'
        
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
    view_mode = st.sidebar.radio("功能切換", ["📊 營運總覽", "🍟 商品分析", "👥 會員查詢", "🔮 智慧預測"])
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
            st.subheader("📅 平假日平均 (vs 上期)")
            if not df_rep.empty:
                daily_rev = df_rep.groupby(['Date_Parsed', 'Day_Type'])['總計'].sum().reset_index()
                curr_type_avg = daily_rev.groupby('Day_Type')['總計'].mean()
                daily_rev_prev = df_rep_prev.groupby(['Date_Parsed', 'Day_Type'])['總計'].sum().reset_index() if not df_rep_prev.empty else pd.DataFrame()
                prev_type_avg = daily_rev_prev.groupby('Day_Type')['總計'].mean() if not daily_rev_prev.empty else pd.Series()
                
                for dtype in ['平日 (Weekday)', '週末 (Weekend)', '特別假日 (Holiday)']:
                    val = curr_type_avg.get(dtype, 0)
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
        
        # Graphs: Visitor & ATV (Bottom)
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
            
            st.metric("總銷售數量", f"{curr_qty:,.0f}", f"{calculate_delta(curr_qty, prev_qty):.1%}" if prev_qty else None)
            
            st.divider()
            
            # 1. Detail Analysis flow
            st.subheader("📈 類別與商品走勢")
            cats = sorted(list(df_items['Category'].unique()))
            sel_cat = st.selectbox("請先選擇類別 (查看細項)", cats, index=0)
            
            # Interval Selector (User Req)
            interval = st.radio("走勢單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"], index=0, horizontal=True)
            interval_map = {"天 (Daily)": "D", "週 (Weekly)": "W-MON", "4週 (Monthly)": "4W-MON"}
            freq = interval_map[interval]

            # Filter by Category
            cat_df = df_items[df_items['Category'] == sel_cat].copy()
            
            # Trend Chart (Left: Chart, Right: Table was old. User wants Rank BELOW Chart)
            
            # Trend Data
            cat_df['PeriodData'] = cat_df['Date_Parsed'].dt.to_period(freq[0] if freq != "4W-MON" else "M") # Simple approx
            # Better resampling
            trend_df = cat_df.set_index('Date_Parsed')
            
            # Select Top Items for Visual Complexity
            top_items = cat_df.groupby('Item Name')['Item Quantity'].sum().nlargest(5).index.tolist()
            sel_items = st.multiselect("選擇商品繪圖", cat_df['Item Name'].unique(), default=top_items)
            
            if sel_items:
                # Resample logic
                chart_data = cat_df[cat_df['Item Name'].isin(sel_items)].copy()
                chart_data = chart_data.set_index('Date_Parsed').groupby('Item Name').resample(freq)['Item Quantity'].sum().reset_index()
                
                # Plot
                fig_trend = px.line(chart_data, x='Date_Parsed', y='Item Quantity', color='Item Name', markers=True, 
                                    title=f"{sel_cat} 商品銷售走勢 ({interval})")
                st.plotly_chart(fig_trend, use_container_width=True)

            # Ranking Table (Below Chart)
            st.divider()
            st.subheader(f"📊 {sel_cat} - 商品銷售佔比")
            
            cat_total_qty = cat_df['Item Quantity'].sum()
            
            c_pie, c_rank = st.columns([1, 1])
            
            with c_pie:
                # Share Pie Chart
                item_pie = cat_df.groupby('Item Name')['Item Quantity'].sum().reset_index()
                fig_pie = px.pie(item_pie, values='Item Quantity', names='Item Name', title=f"{sel_cat} 銷量佔比")
                st.plotly_chart(fig_pie, use_container_width=True)

            with c_rank:
                 cat_total_rev = cat_df['Item Amount(TWD)'].sum()
                 summary = cat_df.groupby('Item Name').agg({
                    'Item Quantity': 'sum', 
                    'Item Amount(TWD)': 'sum'
                 }).reset_index().sort_values('Item Quantity', ascending=False)
                 
                 summary['Rev %'] = (summary['Item Amount(TWD)'] / cat_total_rev * 100).map('{:.1f}%'.format)
                 summary['Qty %'] = (summary['Item Quantity'] / cat_total_qty * 100).map('{:.1f}%'.format)
                 
                 st.write(f"**{sel_cat} 銷售排行**")
                 st.dataframe(summary[['Item Name', 'Item Quantity', 'Item Amount(TWD)', 'Qty %', 'Rev %']], use_container_width=True)

            st.divider()
            st.subheader("📋 原始商品數據 (每日數量)")
            # Pivot table: Date x Item match
            raw_pivot = df_items.groupby(['Date_Parsed', 'Item Name'])['Item Quantity'].sum().reset_index()
            raw_pivot['Date'] = raw_pivot['Date_Parsed'].dt.date
            raw_wide = raw_pivot.pivot(index='Date', columns='Item Name', values='Item Quantity').fillna(0)
            st.dataframe(raw_wide, use_container_width=True)

    # --- VIEW 3: 會員查詢 ---
    elif view_mode == "👥 會員查詢":
        st.title("👥 會員消費紀錄查詢")
        
        col_L, col_R = st.columns([1, 2])
        with col_L:
            phone_query = st.text_input("輸入電話或姓名:")
            use_date = st.checkbox("限制日期範圍", value=False)
            q_start, q_end = today, today
            
        col_phone = '客戶電話' if '客戶電話' in df_report.columns else 'Contact'
        col_name = '客戶姓名' if '客戶姓名' in df_report.columns else 'Customer Name'

        if phone_query:
            try:
                # Robust Clean
                query_str = str(phone_query).strip()
                query_clean = re.sub(r'\D', '', query_str)
                mask = pd.Series([False]*len(df_report))
                
                if col_phone in df_report.columns and query_clean: 
                    phone_col_clean = df_report[col_phone].astype(str).str.replace(r'\D', '', regex=True)
                    mask |= phone_col_clean.str.contains(query_clean, na=False)
                
                if col_name in df_report.columns: 
                    mask |= df_report[col_name].astype(str).str.contains(query_str, na=False)
                
                member_data = df_report[mask].copy()
                
                if not member_data.empty:
                    name_disp = member_data[col_name].iloc[0] if col_name in member_data.columns else "Unknown"
                    phone_disp = member_data[col_phone].iloc[0] if col_phone in member_data.columns else "Unknown"
                    st.success(f"會員: {name_disp} / 電話: {phone_disp}")
                    c1, c2 = st.columns(2)
                    c1.metric("累積消費金額", f"${member_data['總計'].sum():,.0f}")
                    c2.metric("累積來店次數", f"{len(member_data)} 次")
                    
                    st.subheader("Hamburger 歷史購買品項")
                    if 'Order Number' in member_data.columns and 'Order Number' in df_details.columns:
                        target_orders = member_data['Order Number'].unique()
                        m_details = df_details[df_details['Order Number'].isin(target_orders)]
                        if not m_details.empty:
                            item_hist = m_details.groupby('Item Name')['Item Quantity'].sum().reset_index().sort_values('Item Quantity', ascending=False)
                            st.dataframe(item_hist, use_container_width=True)
                    st.dataframe(member_data[['date', '時間', '總計']], use_container_width=True)
                else: st.warning("查無符合資料")
            except Exception as e:
                st.error(f"查詢發生錯誤: {e}")

    # --- VIEW 4: 智慧預測 ---
    elif view_mode == "🔮 智慧預測":
        st.title("🔮 AI 營收與銷量預測")
        st.info("此功能使用簡單移動平均 (SMA) 進行趨勢預估，僅供參考。")

        if df_rep.empty:
            st.warning("無足夠數據進行預測")
        else:
            # 1. Revenue Forecast
            st.subheader("📈 未來 7 天營收預估")
            daily_rev = df_report.groupby('Date_Parsed')['總計'].sum().reset_index()
            daily_rev = daily_rev.sort_values('Date_Parsed')
            
            if len(daily_rev) > 7:
                daily_rev['MA_7'] = daily_rev['總計'].rolling(window=7).mean()
                last_ma = daily_rev['MA_7'].iloc[-1]
                
                # Generate Future Dates
                last_date = daily_rev['Date_Parsed'].max()
                future_dates = [last_date + timedelta(days=i) for i in range(1, 8)]
                future_rev = [last_ma] * 7 # Simple persistence forecast
                
                future_df = pd.DataFrame({'Date_Parsed': future_dates, 'Forecast': future_rev})
                
                fig_f = px.line(daily_rev, x='Date_Parsed', y='總計', title="歷史營收 vs 預測趨勢")
                fig_f.add_scatter(x=future_df['Date_Parsed'], y=future_df['Forecast'], mode='lines+markers', name='預測 (Forecast)', line=dict(dash='dash', color='red'))
                st.plotly_chart(fig_f, use_container_width=True)
            else:
                st.warning("數據不足 7 天，無法產生趨勢")

            st.divider()
            
            # 2. Item Forecast
            st.subheader("🍟 熱銷商品銷量預估")
            if 'Item Name' in df_details.columns:
                top_items = df_details.groupby('Item Name')['Item Quantity'].sum().nlargest(5).index
                sel_item = st.selectbox("選擇商品", top_items)
                
                item_daily = df_details[df_details['Item Name'] == sel_item].groupby('Date_Parsed')['Item Quantity'].sum().reset_index()
                if len(item_daily) > 7:
                    item_daily['MA_7'] = item_daily['Item Quantity'].rolling(window=7).mean()
                    last_val = item_daily['MA_7'].iloc[-1]
                    st.metric(f"{sel_item} - 預估日銷量", f"{last_val:.1f} 份")
                    st.line_chart(item_daily.set_index('Date_Parsed')['Item Quantity'])
                else:
                    st.warning("該商品數據不足")

except Exception as e: st.error(f"系統錯誤: {e}")
