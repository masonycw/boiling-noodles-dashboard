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
LOCAL_DATA_DIR = "/home/eats365/data"

# Taiwan Holidays (2024-2026)
# Updated to ensure accuracy for 2026 Sept/Oct
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
    "2026-09-25", "2026-09-26", "2026-09-27", "2026-09-28", "2026-10-09", "2026-10-10", "2026-10-11", "2026-10-24", "2026-10-25", "2026-10-26", "2026-12-25"
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

    # --- Feature: Aggregate "Super Value Combos" ---
    if 'Item Name' in df_details.columns:
        mask_combo = df_details['Item Name'].astype(str).str.contains('超值組合', na=False)
        df_details.loc[mask_combo, 'Item Name'] = '超值組合'
    
    # --- Categorization P14 Specific Items ---
    clean_cols = {c: c.strip() for c in df_details.columns}
    df_details.rename(columns=clean_cols, inplace=True)
    
    def infer_category(row):
        sku = str(row.get('Product SKU', '')).strip().upper()
        name = str(row.get('Item Name', '')).strip()
        
        # 0. User Forced Specific Items (P14)
        if name in ['拌水蓮', '燙大陸妹', '燙高麗菜', '燙青江菜']: return 'C 青菜 (Vegetables)'
        if name in ['桂花香豆乾', '涼拌豆干絲', '燒椒尬皮蛋', '紅燒茄子君']: return 'D 小菜 (Sides)'

        # 1. Special Cases C-1
        if name in ['蔥油雞', '芭樂遇見五花']: return 'C-1 特殊單點 (Special)'
        if name == '超值組合': return 'S 套餐 (Set)'

        # 2. Priority: Check SKU First Letter
        if len(sku) > 0:
            prefix = sku[0]
            if prefix == 'A': return 'A 湯麵 (Soup Noodle)'
            if prefix == 'B': return 'B 乾麵/飯 (Dry/Rice)'
            if prefix == 'E': return 'E 湯品 (Soup)' 
            
            # P15 Fix: Cross-Map SKU C->Sides, D->Veg (User Request 1578)
            if prefix == 'C': return 'D 小菜 (Sides)' 
            if prefix == 'D': return 'C 青菜 (Vegetables)' 
            if prefix == 'F': return 'F 飲料 (Drinks)'
            
            if prefix == 'S': return 'S 套餐 (Set)'

        # 3. Fallback (Name based)
        item_type = str(row.get('Item Type', ''))
        if 'Set Meal' in item_type or 'Combo Item' in item_type:
             if 'Single Item' not in item_type: return 'S 套餐 (Set)'
        
        if '湯麵' in name: return 'A 湯麵 (Soup Noodle)'
        if '拌麵' in name or '乾麵' in name or '飯' in name: return 'B 乾麵/飯 (Dry/Rice)'
        
        if any(x in name for x in ['湯', '羹']): return 'E 湯品 (Soup)'
        
        # Consistent with SKU P15
        if any(x in name for x in ['菜', '水蓮']): return 'C 青菜 (Vegetables)'
        if any(x in name for x in ['豆干', '皮蛋', '豆腐', '海帶', '花生', '毛豆', '黃瓜', '蛋']): return 'D 小菜 (Sides)'
        
        if any(x in name for x in ['茶', '飲', '可樂', '雪碧']): return 'F 飲料 (Drinks)'
        
        return 'G 其他 (Others)'
        
    df_details['Category'] = df_details.apply(infer_category, axis=1)

    # --- Day Type ---
    def get_day_type(dt):
        if pd.isnull(dt): return 'Unknown'
        d_str = dt.strftime('%Y-%m-%d')
        if d_str in TW_HOLIDAYS_SET: return '假日 (Holiday)' 
        if dt.weekday() >= 5: return '假日 (Holiday)' 
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

# --- Prediction Logic P13 ---
def predict_revenue_summary(df_report, days_back=14):
    end_date = df_report['Date_Parsed'].max()
    start_date = end_date - timedelta(days=days_back)
    mask = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    recent = df_report[mask].copy()

    def get_simple_type(dt):
        d_str = dt.strftime('%Y-%m-%d')
        if d_str in TW_HOLIDAYS_SET or dt.weekday() >= 5: return 'Holiday'
        return 'Weekday'
    recent['Simple'] = recent['Date_Parsed'].apply(get_simple_type)
    
    daily_sums = recent.groupby(['Date_Parsed', 'Simple'])['總計'].sum().reset_index()
    avgs = daily_sums.groupby('Simple')['總計'].mean()
    
    avg_wd = avgs.get('Weekday', 0)
    avg_hd = avgs.get('Holiday', 0)
    
    if avg_wd == 0 and avg_hd > 0: avg_wd = avg_hd
    if avg_hd == 0 and avg_wd > 0: avg_hd = avg_wd
    
    return avg_wd, avg_hd

def predict_monthly_table_hybrid(avg_wd, avg_hd, df_report, months=12):
    # Hybrid: For current month (if partial data exists), sum Actual + Forecast Remainder
    # For future months, pure Forecast
    
    latest_date = df_report['Date_Parsed'].max()
    start_forecast_date = latest_date + timedelta(days=1)
    end_forecast_date = start_forecast_date + relativedelta(months=months)
    
    dates = []
    curr = start_forecast_date
    while curr < end_forecast_date:
        dates.append(curr)
        curr += timedelta(days=1)
        
    df_future = pd.DataFrame({'Date': dates})
    df_future['Month'] = df_future['Date'].dt.to_period('M')
    
    def get_simple_type(dt):
        d_str = dt.strftime('%Y-%m-%d')
        if d_str in TW_HOLIDAYS_SET or dt.weekday() >= 5: return 'Holiday'
        return 'Weekday'

    df_future['Type'] = df_future['Date'].apply(get_simple_type)
    
    # Group Future by Month
    future_stats = []
    groups = df_future.groupby('Month')
    for m, group in groups:
        n_wd = (group['Type'] == 'Weekday').sum()
        n_hd = (group['Type'] == 'Holiday').sum()
        rev = (n_wd * avg_wd) + (n_hd * avg_hd)
        future_stats.append({
            'Month_Period': m,
            'Date_Label': str(m),
            'Weekday Days': n_wd,
            'Holiday Days': n_hd,
            'Forecast Revenue': rev,
            'Status': 'Forecast'
        })
    df_future_agg = pd.DataFrame(future_stats)
    
    # Get Current Month Actuals
    current_month_period = latest_date.to_period('M')
    
    # Calculate Actuals for Current Month
    current_month_start = latest_date.replace(day=1)
    mask_cur = (df_report['Date_Parsed'] >= current_month_start) & (df_report['Date_Parsed'] <= latest_date)
    actual_rev = df_report.loc[mask_cur, '總計'].sum()
    
    # Update the Current Month row in df_future_agg
    idx = df_future_agg.index[df_future_agg['Month_Period'] == current_month_period].tolist()
    
    if idx:
        future_val = df_future_agg.loc[idx[0], 'Forecast Revenue']
        # Hybrid Total
        hybrid_total = actual_rev + future_val
        df_future_agg.loc[idx[0], 'Forecast Revenue'] = hybrid_total
        df_future_agg.loc[idx[0], 'Status'] = 'Hybrid (Actual+Fcst)'
    else:
        # If today is month end, we might not have a future date for this month.
        pass

    return df_future_agg

# --- 3. Main App ---
try:
    with st.spinner('數據處理中...'):
        df_report_raw, df_details_raw = load_data()
        df_report, df_details = preprocess_data(df_report_raw, df_details_raw)

    if df_report.empty:
        st.warning("尚未載入資料")
        st.stop()

    st.sidebar.title("🍜 滾麵 Dashboard")
    view_mode = st.sidebar.radio("功能切換", ["📊 營運總覽", "🍟 商品分析", "👥 會員查詢", "🆕 新舊客分析", "🔮 智慧預測"])
    st.sidebar.divider()

    st.sidebar.header("📅 日期篩選")
    today = date.today()
    month_options = [ (today - relativedelta(months=i)).strftime("%Y-%m") for i in range(6) ]
    filter_opts = ["今日 (Today)", "昨日 (Yesterday)", "本週 (This Week)", "本月 (This Month)", 
                   "近 28 天", "近 30 天", "近 2 個月 (60 Days)", "近 6 個月 (180 Days)", "自訂範圍"] + month_options
    filter_mode = st.sidebar.selectbox("快速區間", filter_opts, index=3)

    start_date, end_date = today, today 
    if filter_mode == "今日 (Today)": start_date = end_date = pd.Timestamp(today)
    elif filter_mode == "昨日 (Yesterday)": start_date = end_date = pd.Timestamp(today - timedelta(days=1))
    elif filter_mode == "本週 (This Week)": start_date = pd.Timestamp(today - timedelta(days=today.weekday())); end_date = pd.Timestamp(today)
    elif filter_mode == "本月 (This Month)": start_date = pd.Timestamp(today.replace(day=1)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 28 天": start_date = pd.Timestamp(today - timedelta(days=28)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 30 天": start_date = pd.Timestamp(today - timedelta(days=30)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 2 個月 (60 Days)": start_date = pd.Timestamp(today - timedelta(days=60)); end_date = pd.Timestamp(today)
    elif filter_mode == "近 6 個月 (180 Days)": start_date = pd.Timestamp(today - timedelta(days=180)); end_date = pd.Timestamp(today)
    elif filter_mode in month_options: y, m = map(int, filter_mode.split('-')); start_date = pd.Timestamp(date(y, m, 1)); end_date = pd.Timestamp(start_date + relativedelta(months=1, days=-1))
    else: d = st.sidebar.date_input("選擇日期", [today - timedelta(days=7), today]); start_date = pd.to_datetime(d[0]) if len(d) > 0 else pd.Timestamp(today); end_date = pd.to_datetime(d[1]) if len(d) > 1 else start_date

    mask_rep = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    df_rep = df_report.loc[mask_rep].copy()
    mask_det = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
    df_det = df_details.loc[mask_det].copy()

    prev_end = start_date - timedelta(days=1)
    duration = end_date - start_date
    prev_start = prev_end - duration
    mask_rep_prev = (df_report['Date_Parsed'] >= prev_start) & (df_report['Date_Parsed'] <= prev_end)
    df_rep_prev = df_report.loc[mask_rep_prev].copy()
    mask_det_prev = (df_details['Date_Parsed'] >= prev_start) & (df_details['Date_Parsed'] <= prev_end)
    df_det_prev = df_details.loc[mask_det_prev].copy()

    # --- VIEW 1: 營運總覽 ---
    if view_mode == "📊 營運總覽":
        st.title(f"📊 營運總覽 ({start_date.date()} ~ {end_date.date()})")
        
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

        ov_int = st.radio("圖表單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"], horizontal=True, key='ov_int')
        ov_freq = 'D'
        if ov_int == "週 (Weekly)": ov_freq = 'W-MON'
        elif ov_int == "4週 (Monthly)": ov_freq = 'M'

        col_L, col_R = st.columns([2, 1])
        with col_L:
            st.subheader("📈 營業額趨勢 (時段)")
            if not df_rep.empty:
                if ov_freq == 'D':
                    daily_period = df_rep.groupby(['Date_Parsed', 'Period'])['總計'].sum().reset_index()
                    daily_total = df_rep.groupby('Date_Parsed')['總計'].sum().reset_index().rename(columns={'總計': 'Daily_Total'})
                    daily_period = pd.merge(daily_period, daily_total, on='Date_Parsed', how='left')
                    fig = px.bar(daily_period, x='Date_Parsed', y='總計', color='Period', barmode='stack', color_discrete_map={'中午 (Lunch)': '#FFC107', '晚上 (Dinner)': '#3F51B5'}, custom_data=['Daily_Total'])
                    fig.update_traces(hovertemplate="Date: %{x}<br>Rev: $%{y:,.0f}<br>Total: $%{customdata[0]:,.0f}")
                else:
                    resampled = df_rep.set_index('Date_Parsed').resample(ov_freq)['總計'].sum().reset_index()
                    fig = px.bar(resampled, x='Date_Parsed', y='總計', title=f"營業額 ({ov_int})")
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
        st.subheader("🛵 每日營收結構 (通路)")
        col_type = '單類型' if '單類型' in df_rep.columns else 'Order Type'
        if col_type in df_rep.columns:
            if ov_freq == 'D':
                 daily_type = df_rep.groupby(['Date_Parsed', col_type])['總計'].sum().reset_index()
            else:
                 daily_type = df_rep.set_index('Date_Parsed').groupby(col_type).resample(ov_freq)['總計'].sum().reset_index()
            
            fig_type = px.bar(daily_type, x='Date_Parsed', y='總計', color=col_type, barmode='stack')
            st.plotly_chart(fig_type, use_container_width=True)

        st.divider()
        c_vis, c_atv = st.columns(2)
        with c_vis:
            st.subheader("👥 來客數趨勢")
            if not df_rep.empty:
                daily_vis = df_det[df_det['Is_Main_Dish']].set_index('Date_Parsed').resample(ov_freq)['Item Quantity'].sum().reset_index()
                fig_v = px.line(daily_vis, x='Date_Parsed', y='Item Quantity', markers=True, title=f"來客數 ({ov_int})")
                st.plotly_chart(fig_v, use_container_width=True)
        with c_atv:
            st.subheader("💰 客單價趨勢")
            if not df_rep.empty:
                res_rev = df_rep.set_index('Date_Parsed').resample(ov_freq)['總計'].sum()
                res_vis = df_det[df_det['Is_Main_Dish']].set_index('Date_Parsed').resample(ov_freq)['Item Quantity'].sum()
                df_atv = pd.DataFrame({'Rev': res_rev, 'Vis': res_vis})
                df_atv['ATV'] = df_atv['Rev'] / df_atv['Vis']
                df_atv = df_atv.reset_index()
                fig_a = px.line(df_atv, x='Date_Parsed', y='ATV', markers=True, title=f"客單價 ({ov_int})")
                st.plotly_chart(fig_a, use_container_width=True)
        
        st.divider()
        st.subheader("📋 營運報表 (Table)")
        if not df_rep.empty:
            cols_to_agg = {'總計': 'sum'}
            if ov_freq == 'D':
                grouped = df_rep.groupby('Date_Parsed')
                base_agg = grouped['總計'].sum().reset_index().rename(columns={'總計': '總營業額'})
                base_agg['Date_Label'] = base_agg['Date_Parsed'].dt.date.astype(str)
            else:
                grouped = df_rep.set_index('Date_Parsed').resample(ov_freq)
                base_agg = grouped['總計'].sum().reset_index().rename(columns={'總計': '總營業額'})
                base_agg['Date_Label'] = base_agg['Date_Parsed'].dt.strftime('%Y-%m-%d (Start)')

            if ov_freq == 'D':
                period_rev = df_rep.groupby(['Date_Parsed', 'Period'])['總計'].sum().unstack(fill_value=0)
            else:
                p_groups = []
                for p in ['中午 (Lunch)', '晚上 (Dinner)']:
                    mask_p = df_rep['Period'] == p
                    if mask_p.any():
                        res = df_rep[mask_p].set_index('Date_Parsed').resample(ov_freq)['總計'].sum()
                        res.name = p
                        p_groups.append(res)
                if p_groups: period_rev = pd.concat(p_groups, axis=1).fillna(0)
                else: period_rev = pd.DataFrame()

            period_rev = period_rev.reset_index()
            period_rev.rename(columns={'中午 (Lunch)': '午餐營收', '晚上 (Dinner)': '晚餐營收'}, inplace=True)
            for c in ['午餐營收', '晚餐營收']: 
                if c not in period_rev.columns: period_rev[c] = 0

            if ov_freq == 'D':
                 vis_agg = df_det[df_det['Is_Main_Dish']].groupby('Date_Parsed')['Item Quantity'].sum()
            else:
                 vis_agg = df_det[df_det['Is_Main_Dish']].set_index('Date_Parsed').resample(ov_freq)['Item Quantity'].sum()
            vis_agg = vis_agg.reset_index().rename(columns={'Item Quantity': '來客數'})

            if col_type in df_rep.columns:
                types = df_rep[col_type].unique()
                c_groups = []
                for t in types:
                    mask_t = df_rep[col_type] == t
                    if mask_t.any():
                        if ov_freq == 'D': res = df_rep[mask_t].groupby('Date_Parsed')['總計'].sum()
                        else: res = df_rep[mask_t].set_index('Date_Parsed').resample(ov_freq)['總計'].sum()
                        res.name = t
                        c_groups.append(res)
                if c_groups: channel_rev = pd.concat(c_groups, axis=1).fillna(0).reset_index()
                else: channel_rev = pd.DataFrame({'Date_Parsed': base_agg['Date_Parsed']})
            else: channel_rev = pd.DataFrame({'Date_Parsed': base_agg['Date_Parsed']})

            rename_map = {}
            for c in channel_rev.columns:
                if 'Delivery' in str(c) or '外送' in str(c): rename_map[c] = '外送營收'
                if 'Takeout' in str(c) or '外帶' in str(c): rename_map[c] = '外帶營收'
                if 'Dine-in' in str(c) or '內用' in str(c): rename_map[c] = '堂食營收 (內用)'
            channel_rev.rename(columns=rename_map, inplace=True)

            final_df = base_agg.merge(period_rev, on='Date_Parsed', how='left')
            final_df = final_df.merge(vis_agg, on='Date_Parsed', how='left')
            final_df = final_df.merge(channel_rev, on='Date_Parsed', how='left')
            final_df['客單價'] = (final_df['總營業額'] / final_df['來客數']).replace([np.inf, -np.inf], 0).fillna(0).round(0)
            
            cols_show = ['Date_Label', '午餐營收', '晚餐營收', '總營業額', '來客數', '客單價']
            for c in ['外送營收', '外帶營收', '堂食營收 (內用)']:
                if c in final_df.columns: cols_show.append(c)
                
            st.dataframe(final_df[cols_show].sort_values('Date_Label', ascending=False).style.format({
                '午餐營收': '${:,.0f}', '晚餐營收': '${:,.0f}', '總營業額': '${:,.0f}',
                '來客數': '{:,.0f}', '客單價': '${:,.0f}',
                '外送營收': '${:,.0f}', '外帶營收': '${:,.0f}', '堂食營收 (內用)': '${:,.0f}'
            }), use_container_width=True)

    # --- VIEW 2: 商品分析 ---
    elif view_mode == "🍟 商品分析":
        st.title("🍟 商品銷售分析")
        
        if 'Item Name' in df_det.columns:
            df_items = df_det.dropna(subset=['Item Name'])
            
            st.subheader("📈 類別與商品走勢")
            
            cats = sorted(list(df_items['Category'].unique()))
            comp_opt = "📋 [特殊] 乾麵/飯 vs 湯麵 (Dry/Rice vs Soup)"
            cats.insert(0, comp_opt)
            
            sel_cat = st.selectbox("請選擇類別 或 特殊比較", cats, index=0)
            
            interval = st.radio("走勢單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"], index=0, horizontal=True)
            freq_alias = 'D'
            if interval == "週 (Weekly)": freq_alias = 'W-MON'
            elif interval == "4週 (Monthly)": freq_alias = 'M' 

            if sel_cat == comp_opt:
                mask_a = df_items['Category'].str.contains('A 湯麵', na=False)
                mask_b = df_items['Category'].str.contains('B 乾麵', na=False)
                comp_df = df_items[mask_a | mask_b].copy()
                comp_df['Group'] = comp_df['Category'].apply(lambda x: '湯麵 (Soup)' if 'A 湯麵' in x else '乾麵/飯 (Dry/Rice)')
                
                chart_data = comp_df.set_index('Date_Parsed').groupby('Group').resample(freq_alias)['Item Quantity'].sum().reset_index()
                fig_trend = px.line(chart_data, x='Date_Parsed', y='Item Quantity', color='Group', markers=True, title=f"乾麵/飯 vs 湯麵 - {interval} 走勢比較")
                st.plotly_chart(fig_trend, use_container_width=True)
                
                st.write("**比例分析 (Ratio)**")
                pivot_ratio = chart_data.pivot(index='Date_Parsed', columns='Group', values='Item Quantity').fillna(0)
                pivot_ratio['Total'] = pivot_ratio.sum(axis=1)
                for g in pivot_ratio.columns:
                    if g != 'Total': pivot_ratio[g+' %'] = pivot_ratio[g] / pivot_ratio['Total']
                
                fig_ratio = px.bar(pivot_ratio.reset_index(), x='Date_Parsed', y=[c for c in pivot_ratio.columns if '%' in c], barmode='stack', title="銷售比例 (Share %)")
                st.plotly_chart(fig_ratio, use_container_width=True)

            else:
                cat_df = df_items[df_items['Category'] == sel_cat].copy()
                top_items = cat_df.groupby('Item Name')['Item Quantity'].sum().nlargest(5).index.tolist()
                sel_items = st.multiselect("選擇商品繪圖", cat_df['Item Name'].unique(), default=top_items)
                
                if sel_items:
                    chart_data = cat_df[cat_df['Item Name'].isin(sel_items)].copy()
                    chart_data = chart_data.set_index('Date_Parsed').groupby('Item Name').resample(freq_alias)['Item Quantity'].sum().reset_index()
                    fig_trend = px.line(chart_data, x='Date_Parsed', y='Item Quantity', color='Item Name', markers=True, title=f"{sel_cat} {interval} 走勢")
                    st.plotly_chart(fig_trend, use_container_width=True)
                
                # P16: Restore Pie Chart
                st.write("**商品佔比 (Pie Chart)**")
                pie_data = cat_df.groupby('Item Name')['Item Quantity'].sum().reset_index()
                fig_pie = px.pie(pie_data, values='Item Quantity', names='Item Name', title=f"{sel_cat} 銷售佔比")
                st.plotly_chart(fig_pie, use_container_width=True)

    # --- VIEW 3: 會員查詢 ---
    elif view_mode == "👥 會員查詢":
        st.title("👥 會員消費紀錄查詢")
        st.subheader("🔍 1. 搜尋會員")
        search_term = st.text_input("輸入 姓名 或 電話 (模糊搜尋)", "")
        
        col_phone = '客戶電話' if '客戶電話' in df_report.columns else 'Contact'
        col_name = '客戶姓名' if '客戶姓名' in df_report.columns else 'Customer Name'
        
        if search_term:
            s_clean = search_term.strip()
            if col_phone in df_report.columns:
                 phone_series = df_report[col_phone].astype(str).str.replace(r'\D', '', regex=True)
            else: phone_series = pd.Series([])
            if col_name in df_report.columns:
                 name_series = df_report[col_name].astype(str).fillna('')
            else: name_series = pd.Series([])
            
            mask = pd.Series(False, index=df_report.index)
            if not phone_series.empty: mask |= phone_series.str.contains(s_clean, na=False)
            if not name_series.empty: mask |= name_series.str.contains(s_clean, na=False)
            results = df_report[mask].copy()
            unique_members = results[[col_name, col_phone]].drop_duplicates()
            
            if not unique_members.empty:
                st.success(f"找到 {len(unique_members)} 位相關會員")
                unique_members['Label'] = unique_members[col_name].astype(str) + " (" + unique_members[col_phone].astype(str) + ")"
                sel_member_label = st.selectbox("請選擇:", unique_members['Label'].tolist())
                sel_row = unique_members[unique_members['Label'] == sel_member_label].iloc[0]
                sel_name = sel_row[col_name]
                sel_phone = sel_row[col_phone]
                
                if pd.isna(sel_phone): mem_records = df_report[df_report[col_name] == sel_name].copy()
                else: mem_records = df_report[(df_report[col_name] == sel_name) & (df_report[col_phone] == sel_phone)].copy()
                mem_records = mem_records.sort_values('Datetime', ascending=False)
                
                st.divider()
                st.subheader(f"📄 {sel_name} 的消費紀錄")
                
                real_visit_count = mem_records['Date_Parsed'].nunique()
                tx_count = len(mem_records)
                total_spend = mem_records['總計'].sum()
                avg_spend = total_spend / real_visit_count if real_visit_count > 0 else 0
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("總消費", f"${total_spend:,.0f}")
                m2.metric("來店次數 (Days)", f"{real_visit_count} 天")
                m3.metric("總單數 (Txs)", f"{tx_count} 張")
                m4.metric("平均客單 (Per Day)", f"${avg_spend:,.0f}")
                
                st.write("**詳細交易列表** (點擊展開明細)")
                for i, row in mem_records.iterrows():
                    oid = row.get('Order Number')
                    dt_str = row['Datetime'].strftime('%Y-%m-%d %H:%M')
                    amt = row['總計']
                    with st.expander(f"{dt_str} - ${amt:.0f} (單號: {oid})"):
                         if oid and 'Order Number' in df_details.columns:
                             cols = ['Item Name', 'Item Quantity', 'Item Amount(TWD)']
                             if 'Item Discount' in df_details.columns: cols.append('Item Discount')
                             
                             items = df_details[df_details['Order Number'] == oid][cols]
                             st.dataframe(items, use_container_width=True)
                             st.write(f"總項數: {items['Item Quantity'].sum()}")
                         else: st.write("無明細資料")

            else: st.warning("查無資料")

    # --- VIEW 4: 新舊客分析 (Guest Analysis) ---
    elif view_mode == "🆕 新舊客分析":
        st.title("🆕 新舊客消費分析")
        
        df_full = df_report_raw 
        col_phone = '客戶電話' if '客戶電話' in df_full.columns else 'Contact'
        
        if col_phone not in df_full.columns:
            st.warning("無會員電話欄位，無法進行分析")
        else:
            mask_has_phone = df_full[col_phone].notna() & (df_full[col_phone].astype(str).str.len() > 5)
            df_members_only = df_full[mask_has_phone].copy()
            
            if df_members_only.empty:
                st.warning("系統內無有效的會員電話資料")
            else:
                mem_visits = df_members_only.groupby(col_phone)['Date_Parsed'].nunique()
                
                def get_loyalty(n):
                    if n == 1: return 'New (新客)'
                    if n == 2: return 'Returning (舊客)'
                    return 'Regular (常客)'
                    
                loyalty_map = mem_visits.apply(get_loyalty).to_dict()
                
                target_df = df_rep.copy()
                target_df['Has_Data'] = target_df[col_phone].notna() & (target_df[col_phone].astype(str).str.len() > 5)
                target_df['Loyalty'] = target_df[col_phone].map(loyalty_map).fillna('Unknown')
                
                # 2. Stats
                st.subheader("1. 會員資料覆蓋率 (Data vs No Data)")
                d_gb = target_df.groupby('Has_Data').agg({'總計': 'sum', 'Date_Parsed': 'count'}).rename(columns={'Date_Parsed': 'Tx_Count'})
                d_gb.index = d_gb.index.map({True: '有資料 (Members)', False: '無資料 (Guests)'})
                
                c_d1, c_d2 = st.columns(2)
                fig_d1 = px.pie(d_gb, values='Tx_Count', names=d_gb.index, title="交易筆數分佈")
                fig_d2 = px.pie(d_gb, values='總計', names=d_gb.index, title="營業額分佈")
                c_d1.plotly_chart(fig_d1, use_container_width=True)
                c_d2.plotly_chart(fig_d2, use_container_width=True)
                
                st.divider()
                st.subheader("2. 新舊客趨勢分析 (僅含會員)")
                df_loyal = target_df[target_df['Has_Data']].copy()
                
                if df_loyal.empty:
                    st.warning("區間內無會員資料")
                else:
                    an_int = st.radio("統計單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"], horizontal=True, key='an_int')
                    an_freq = 'D'
                    if an_int == "週 (Weekly)": an_freq = 'W-MON'
                    elif an_int == "4週 (Monthly)": an_freq = 'M'
                    
                    res_rev = df_loyal.set_index('Date_Parsed').groupby('Loyalty').resample(an_freq)['總計'].sum().reset_index()
                    fig_l1 = px.bar(res_rev, x='Date_Parsed', y='總計', color='Loyalty', title=f"客群營業額貢獻 ({an_int})", barmode='stack',
                                    category_orders={"Loyalty": ["New (新客)", "Returning (舊客)", "Regular (常客)"]})
                    st.plotly_chart(fig_l1, use_container_width=True)
                    
                    res_tx = df_loyal.set_index('Date_Parsed').groupby('Loyalty').resample(an_freq).size().reset_index(name='Count')
                    fig_l2 = px.bar(res_tx, x='Date_Parsed', y='Count', color='Loyalty', title=f"客群交易頻次 ({an_int})", barmode='stack',
                                    category_orders={"Loyalty": ["New (新客)", "Returning (舊客)", "Regular (常客)"]})
                    st.plotly_chart(fig_l2, use_container_width=True)


    # --- VIEW 5: 智慧預測 ---
    elif view_mode == "🔮 智慧預測":
        st.title("🔮 AI 營收預測")
        
        days_basis = st.radio("預測基礎", ["過去 2 週 (14 Days)", "過去 4 週 (28 Days)"], index=0, horizontal=True)
        days_back = 28 if "4" in days_basis else 14
        
        avg_wd, avg_hd = predict_revenue_summary(df_report, days_back=days_back)
        st.subheader(f"📊 預測參數 ({days_basis} 平均)")
        c1, c2 = st.columns(2)
        c1.metric("平日日均營收", f"${avg_wd:,.0f}")
        c2.metric("假日日均營收", f"${avg_hd:,.0f}")
        
        st.divider()
        st.subheader("📅 未來 12 個月營收預測表")
        st.caption("含本月已知業績 (Hybrid Forecast)")
        
        forecast_df = predict_monthly_table_hybrid(avg_wd, avg_hd, df_report, months=12)
        
        # P16: Show Weekday/Holiday counts in table
        cols_show = ['Date_Label', 'Weekday Days', 'Holiday Days', 'Forecast Revenue', 'Status']
        st.dataframe(forecast_df[cols_show].style.format({
            'Forecast Revenue': '${:,.0f}',
            'Weekday Days': '{:.0f}',
            'Holiday Days': '{:.0f}'
        }), use_container_width=True)
        
        fig_rev = px.bar(forecast_df, x='Date_Label', y='Forecast Revenue', title="未來 12 個月預估營收", color='Status')
        st.plotly_chart(fig_rev, use_container_width=True)

except Exception as e: st.error(f"系統錯誤: {e}")
