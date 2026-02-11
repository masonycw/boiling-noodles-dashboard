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

    # --- Categorization ---
    clean_cols = {c: c.strip() for c in df_details.columns}
    df_details.rename(columns=clean_cols, inplace=True)
    
    def infer_category(row):
        sku = str(row.get('Product SKU', '')).strip().upper()
        name = str(row.get('Item Name', '')).strip()
        
        # 1. Special Cases C-1
        if name in ['蔥油雞', '芭樂遇見五花']: return 'C-1 特殊單點 (Special)'

        # 2. Priority: Check SKU First Letter
        if len(sku) > 0:
            prefix = sku[0]
            if prefix == 'A': return 'A 湯麵 (Soup Noodle)'
            if prefix == 'B': return 'B 乾麵/飯 (Dry/Rice)'
            if prefix == 'E': return 'E 湯品 (Soup)' 
            if prefix == 'F': return 'F 小菜 (Small Sides)' 
            if prefix == 'D': return 'D 青菜 (Vegetables)'
            if prefix == 'S': return 'S 套餐 (Set)'
            if prefix == 'C': return 'C 單點 (Alacarte)'

        # 3. Fallback (Name based)
        item_type = str(row.get('Item Type', ''))
        if 'Set Meal' in item_type or 'Combo Item' in item_type:
             if 'Single Item' not in item_type: return 'S 套餐 (Set)'
        
        if '湯麵' in name: return 'A 湯麵 (Soup Noodle)'
        if '拌麵' in name or '乾麵' in name or '飯' in name: return 'B 乾麵/飯 (Dry/Rice)'
        if any(x in name for x in ['湯', '羹']): return 'E 湯品 (Soup)'
        if any(x in name for x in ['豆干', '皮蛋', '豆腐', '海帶', '花生', '毛豆', '黃瓜', '蛋']): return 'F 小菜 (Small Sides)'
        
        return 'G 其他 (Others)'
        
    df_details['Category'] = df_details.apply(infer_category, axis=1)

    # --- Day Type (Helper) ---
    def get_day_type(dt):
        if pd.isnull(dt): return 'Unknown'
        d_str = dt.strftime('%Y-%m-%d')
        if d_str in TW_HOLIDAYS_SET: return '假日 (Holiday)' # Use simplified Label
        if dt.weekday() >= 5: return '假日 (Holiday)' # Weekend is Holiday
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

# --- Prediction Logic ---
def predict_revenue(df_report, days=365):
    # 1. Get Past 2 Weeks Data
    end_date = df_report['Date_Parsed'].max()
    start_date = end_date - timedelta(days=14)
    mask = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    recent_df = df_report[mask].copy()
    
    if recent_df.empty: return pd.DataFrame()

    # 2. Calculate Averages
    daily_rev = recent_df.groupby(['Date_Parsed', 'Day_Type'])['總計'].sum().reset_index()
    avg_weekday = daily_rev[daily_rev['Day_Type'] == '平日 (Weekday)']['總計'].mean()
    avg_holiday = daily_rev[daily_rev['Day_Type'] == '假日 (Holiday)']['總計'].mean()
    
    # Fill NaN (e.g. if no holiday in last 2 weeks, use weekday avg)
    if pd.isna(avg_weekday): avg_weekday = avg_holiday if not pd.isna(avg_holiday) else 0
    if pd.isna(avg_holiday): avg_holiday = avg_weekday

    # 3. Predict Future
    future_dates = [end_date + timedelta(days=i) for i in range(1, days+1)]
    forecast = []
    
    for d in future_dates:
        d_str = d.strftime('%Y-%m-%d')
        is_holiday = (d.weekday() >= 5) or (d_str in TW_HOLIDAYS_SET)
        val = avg_holiday if is_holiday else avg_weekday
        forecast.append({'Date': d, 'Forecast Revenue': val})
        
    return pd.DataFrame(forecast)

def predict_item_sales(df_details, item_name, days=14, mode='Daily'):
    # 1. Get Past Data
    end_date = df_details['Date_Parsed'].max()
    # Use ALL history for item average to be safe? User said "Past Weekday/Holiday Average". 
    # Let's use last 30 days to capture recent trend, or full history?
    # User said "according to past weekday/holiday sales average". 
    # Usually recent is better. Let's stick to recent 28 days for items to capture seasonality.
    start_date = end_date - timedelta(days=28)
    mask = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
    
    # Check if item exists in recent history
    recent_df = df_details[mask & (df_details['Item Name'] == item_name)].copy()
    
    # We need "Day Type" in details. Map from Date.
    def is_holiday(dt):
        if pd.isnull(dt): return False
        d_str = dt.strftime('%Y-%m-%d')
        if d_str in TW_HOLIDAYS_SET: return True
        if dt.weekday() >= 5: return True
        return False

    # Group by Date first to get Daily Qty
    daily_qty = recent_df.groupby('Date_Parsed')['Item Quantity'].sum().reset_index()
    daily_qty['Is_Holiday'] = daily_qty['Date_Parsed'].apply(is_holiday)
    
    avg_weekday = daily_qty[~daily_qty['Is_Holiday']]['Item Quantity'].mean()
    avg_holiday = daily_qty[daily_qty['Is_Holiday']]['Item Quantity'].mean()
    
    if pd.isna(avg_weekday): avg_weekday = 0
    if pd.isna(avg_holiday): avg_holiday = 0 # If never sold on holiday
    
    # 2. Forecast
    future_dates = [end_date + timedelta(days=i) for i in range(1, days+1)]
    forecast = []
    
    for d in future_dates:
        holiday = is_holiday(d)
        val = avg_holiday if holiday else avg_weekday
        forecast.append({'Date': d, 'Forecast Qty': val})
        
    res_df = pd.DataFrame(forecast)
    
    if mode == 'Weekly':
        res_df['Week'] = res_df['Date'].dt.to_period('W-MON').dt.start_time
        res_df = res_df.groupby('Week')['Forecast Qty'].sum().reset_index().rename(columns={'Week': 'Date'})
        
    return res_df

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
    
    # Prev Data for Charts (Shifted Logic)
    mask_rep_prev = (df_report['Date_Parsed'] >= prev_start) & (df_report['Date_Parsed'] <= prev_end)
    df_rep_prev = df_report.loc[mask_rep_prev].copy()
    mask_det_prev = (df_details['Date_Parsed'] >= prev_start) & (df_details['Date_Parsed'] <= prev_end)
    df_det_prev = df_details.loc[mask_det_prev].copy()

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

        # Graphs: Revenue
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
                
                for dtype in ['平日 (Weekday)', '假日 (Holiday)']:
                    val = curr_type_avg.get(dtype, 0)
                    pval = prev_type_avg.get(dtype, 0)
                    st.metric(f"平均 {dtype}", f"${val:,.0f}", f"{calculate_delta(val, pval):.1%}" if pval else None)

        st.divider()
        st.subheader("🛵 每日營收結構")
        col_type = '單類型' if '單類型' in df_rep.columns else 'Order Type'
        if col_type in df_rep.columns:
            daily_type = df_rep.groupby(['Date_Parsed', col_type])['總計'].sum().reset_index()
            fig_type = px.bar(daily_type, x='Date_Parsed', y='總計', color=col_type, barmode='stack')
            st.plotly_chart(fig_type, use_container_width=True)

        st.divider()
        
        # Graphs: Visitor & ATV (User Req: Compare with Prev Period)
        c_vis, c_atv = st.columns(2)
        with c_vis:
            st.subheader("👥 來客數趨勢")
            if not df_rep.empty:
                daily_vis = df_det[df_det['Is_Main_Dish']].groupby('Date_Parsed')['Item Quantity'].sum().reset_index()
                
                # Plot
                fig_v = px.line(daily_vis, x='Date_Parsed', y='Item Quantity', markers=True, title="本期來客數")
                
                # Add Prev Period Line (Approx layout)
                if not df_det_prev.empty:
                    daily_vis_prev = df_det_prev[df_det_prev['Is_Main_Dish']].groupby('Date_Parsed')['Item Quantity'].sum().reset_index()
                    # Shift x-axis to align? Or just plot on secondary?
                    # Easiest is to add traces. But dates are different.
                    # We can map prev dates to current dates by adding 'duration'
                    daily_vis_prev['Date_Shifted'] = daily_vis_prev['Date_Parsed'] + (duration + timedelta(days=1))
                    fig_v.add_scatter(x=daily_vis_prev['Date_Shifted'], y=daily_vis_prev['Item Quantity'], mode='lines', name='上期 (Prev)', line=dict(dash='dot', color='gray'))
                    
                st.plotly_chart(fig_v, use_container_width=True)
        
        with c_atv:
            st.subheader("💰 客單價趨勢")
            if not df_rep.empty and not daily_vis.empty:
                daily_rev_chart = df_rep.groupby('Date_Parsed')['總計'].sum().reset_index()
                daily_atv = pd.merge(daily_rev_chart, daily_vis, on='Date_Parsed', how='inner')
                daily_atv['ATV'] = daily_atv['總計'] / daily_atv['Item Quantity']
                fig_a = px.line(daily_atv, x='Date_Parsed', y='ATV', markers=True, title="本期客單價")
                
                # Add Prev Line
                if not df_rep_prev.empty:
                     vis_prev = df_det_prev[df_det_prev['Is_Main_Dish']].groupby('Date_Parsed')['Item Quantity'].sum().reset_index()
                     rev_prev = df_rep_prev.groupby('Date_Parsed')['總計'].sum().reset_index()
                     atv_prev = pd.merge(rev_prev, vis_prev, on='Date_Parsed', how='inner')
                     atv_prev['ATV'] = atv_prev['總計'] / atv_prev['Item Quantity']
                     atv_prev['Date_Shifted'] = atv_prev['Date_Parsed'] + (duration + timedelta(days=1))
                     fig_a.add_scatter(x=atv_prev['Date_Shifted'], y=atv_prev['ATV'], mode='lines', name='上期 (Prev)', line=dict(dash='dot', color='gray'))

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
            
            st.subheader("📈 類別與商品走勢")
            cats = sorted(list(df_items['Category'].unique()))
            sel_cat = st.selectbox("請先選擇類別 (查看細項)", cats, index=0)
            
            interval = st.radio("走勢單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"], index=0, horizontal=True)
            freq_alias = 'D'
            if interval == "週 (Weekly)": freq_alias = 'W-MON'
            elif interval == "4週 (Monthly)": freq_alias = 'M' 

            cat_df = df_items[df_items['Category'] == sel_cat].copy()
            
            # Trend Chart
            top_items = cat_df.groupby('Item Name')['Item Quantity'].sum().nlargest(5).index.tolist()
            sel_items = st.multiselect("選擇商品繪圖", cat_df['Item Name'].unique(), default=top_items)
            
            if sel_items:
                chart_data = cat_df[cat_df['Item Name'].isin(sel_items)].copy()
                chart_data = chart_data.set_index('Date_Parsed').groupby('Item Name').resample(freq_alias)['Item Quantity'].sum().reset_index()
                fig_trend = px.line(chart_data, x='Date_Parsed', y='Item Quantity', color='Item Name', markers=True, title=f"{sel_cat} {interval} 走勢")
                st.plotly_chart(fig_trend, use_container_width=True)

            st.divider()
            st.subheader(f"📊 {sel_cat} - 銷售佔比與排行")
            cat_total_qty = cat_df['Item Quantity'].sum()
            
            c_pie, c_rank = st.columns([1, 1])
            with c_pie:
                item_pie = cat_df.groupby('Item Name')['Item Quantity'].sum().reset_index()
                fig_pie = px.pie(item_pie, values='Item Quantity', names='Item Name', title=f"{sel_cat} 銷量佔比 (Qty %)")
                st.plotly_chart(fig_pie, use_container_width=True)

            with c_rank:
                 cat_total_rev = cat_df['Item Amount(TWD)'].sum()
                 summary = cat_df.groupby('Item Name').agg({'Item Quantity': 'sum', 'Item Amount(TWD)': 'sum'}).reset_index().sort_values('Item Quantity', ascending=False)
                 summary['Rev %'] = (summary['Item Amount(TWD)'] / cat_total_rev * 100).map('{:.1f}%'.format)
                 summary['Qty %'] = (summary['Item Quantity'] / cat_total_qty * 100).map('{:.1f}%'.format)
                 st.write(f"**{sel_cat} 銷售排行**")
                 st.dataframe(summary[['Item Name', 'Item Quantity', 'Item Amount(TWD)', 'Qty %', 'Rev %']], use_container_width=True)

            st.divider()
            st.subheader("📋 原始商品數據 (每日銷量)")
            raw_pivot = df_items.groupby(['Date_Parsed', 'Item Name'])['Item Quantity'].sum().reset_index()
            raw_pivot['Date'] = raw_pivot['Date_Parsed'].dt.strftime('%Y-%m-%d')
            raw_wide = raw_pivot.pivot(index='Date', columns='Item Name', values='Item Quantity').fillna(0)
            st.dataframe(raw_wide, use_container_width=True)

    # --- VIEW 3: 會員查詢 (OVERHAUL) ---
    elif view_mode == "👥 會員查詢":
        st.title("👥 會員消費紀錄查詢")
        
        # User Flow: Search -> List -> Select -> Detail
        st.subheader("🔍 1. 搜尋會員")
        search_term = st.text_input("輸入 姓名 或 電話 (模糊搜尋)", "")
        
        col_phone = '客戶電話' if '客戶電話' in df_report.columns else 'Contact'
        col_name = '客戶姓名' if '客戶姓名' in df_report.columns else 'Customer Name'
        
        if search_term:
            # Clean Input
            s_clean = search_term.strip()
            # Clean Phone Col for search
            phone_series = df_report[col_phone].astype(str).str.replace(r'\D', '', regex=True)
            name_series = df_report[col_name].astype(str).fillna('')
            
            # Mask
            mask = phone_series.str.contains(s_clean, na=False) | name_series.str.contains(s_clean, na=False)
            results = df_report[mask].copy()
            
            # Deduplicate by Name+Phone for Selection List
            unique_members = results[[col_name, col_phone]].drop_duplicates()
            
            if not unique_members.empty:
                st.success(f"找到 {len(unique_members)} 位相關會員")
                
                # Create Select Options
                unique_members['Label'] = unique_members[col_name].astype(str) + " (" + unique_members[col_phone].astype(str) + ")"
                
                st.subheader("👇 2. 選擇會員查看詳情")
                sel_member_label = st.selectbox("請選擇:", unique_members['Label'].tolist())
                
                # Extract Selected Info
                sel_row = unique_members[unique_members['Label'] == sel_member_label].iloc[0]
                sel_name = sel_row[col_name]
                sel_phone = sel_row[col_phone]
                
                # Filter ALL records for this member
                mem_records = df_report[
                    (df_report[col_name] == sel_name) & 
                    (df_report[col_phone] == sel_phone)
                ].copy().sort_values('Datetime', ascending=False)
                
                st.divider()
                st.subheader(f"📄 {sel_name} 的消費紀錄")
                
                # Metrics
                total_spend = mem_records['總計'].sum()
                visit_count = len(mem_records)
                avg_spend = total_spend / visit_count if visit_count > 0 else 0
                
                m1, m2, m3 = st.columns(3)
                m1.metric("總消費", f"${total_spend:,.0f}")
                m2.metric("來店次數", f"{visit_count} 次")
                m3.metric("平均客單", f"${avg_spend:,.0f}")
                
                # Item History
                if 'Order Number' in mem_records.columns and 'Order Number' in df_details.columns:
                    target_orders = mem_records['Order Number'].unique()
                    m_details = df_details[df_details['Order Number'].isin(target_orders)]
                    if not m_details.empty:
                         st.write("**偏好商品統計**")
                         item_hist = m_details.groupby('Item Name')['Item Quantity'].sum().reset_index().sort_values('Item Quantity', ascending=False)
                         st.dataframe(item_hist.head(10), use_container_width=True)
                
                st.write("**詳細交易列表**")
                st.dataframe(mem_records[['Datetime', '總計', '單類型']], use_container_width=True)
                
            else:
                st.warning("查無資料")

    # --- VIEW 4: 智慧預測 (Revamp - User Req #2, #3, #4) ---
    elif view_mode == "🔮 智慧預測":
        st.title("🔮 AI 營收與銷量預測")
        # Logic: Past 2 Weeks Weekday/Holiday Avg
        
        if df_rep.empty:
            st.warning("無資料")
        else:
            # 1. Revenue Forecast (12 Months)
            st.subheader("📈 未來 12 個月營收預測")
            st.caption("邏輯：根據過去 2 週的平/假日平均日營收，推估未來 1 年趨勢。")
            
            rev_fc_df = predict_revenue(df_report, days=365)
            if not rev_fc_df.empty:
                # Group by Month for clearer view
                rev_fc_df['Month'] = rev_fc_df['Date'].dt.to_period('M').astype(str)
                monthly_fc = rev_fc_df.groupby('Month')['Forecast Revenue'].sum().reset_index()
                
                fig_rev = px.bar(monthly_fc, x='Month', y='Forecast Revenue', title="未來 12 個月預估營收")
                st.plotly_chart(fig_rev, use_container_width=True)
                st.dataframe(monthly_fc, use_container_width=True)
            else:
                st.warning("數據不足")
                
            st.divider()
            
            # 2. Item Forecast (1-2 Weeks)
            st.subheader("🍟 商品銷量預測")
            st.caption("邏輯：根據過去 28 天的平/假日平均銷量，推估未來銷量。")
            
            if 'Item Name' in df_details.columns:
                top_items = df_details.groupby('Item Name')['Item Quantity'].sum().nlargest(20).index
                sel_item = st.selectbox("選擇商品", top_items)
                
                mode = st.radio("預測單位", ["日 (Daily)", "週 (Weekly)"], index=0, horizontal=True)
                mode_key = 'Weekly' if '週' in mode else 'Daily'
                days_fc = 14 # 2 Weeks
                
                item_fc_df = predict_item_sales(df_details, sel_item, days=days_fc, mode=mode_key)
                
                if not item_fc_df.empty:
                    val_col = 'Forecast Qty'
                    total_fc = item_fc_df[val_col].sum()
                    st.metric(f"未來 2 週預估總銷量", f"{total_fc:.1f} 份")
                    
                    fig_i = px.bar(item_fc_df, x='Date', y=val_col, title=f"{sel_item} 未來預測 ({mode_key})")
                    st.plotly_chart(fig_i, use_container_width=True)
                    st.dataframe(item_fc_df, use_container_width=True)

except Exception as e: st.error(f"系統錯誤: {e}")
