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
def load_data(safe_mode=False):
    # Define search paths in priority order
    # New structure: /home/eats365/data/交易資料/
    search_paths = [
        "/home/eats365/data/交易資料", # 0. New primary data folder
        "/home/eats365/upload",        # 1. Fallback Upload
        LOCAL_DATA_DIR,                # 2. Legacy Data
        os.getcwd(),                   # 3. Local CWD
        os.path.join(os.getcwd(), 'data', '交易資料')   # 4. Local New Structure
    ]
    
    all_reports = []
    all_details = []
    debug_logs = []

    # Iterate paths
    for path in search_paths:
        if not os.path.exists(path): continue
        
        try:
            # Sort files for deterministic order (old -> new)
            files = sorted(os.listdir(path))
            for f in files:
                if not f.endswith(".csv"): continue
                
                # If Safe Mode, skip auto-detection and only load legacy names
                if safe_mode:
                    if f not in ["history_report.csv", "history_details.csv"]:
                        continue

                full_p = os.path.join(path, f)
                
                try:
                    # Read header only to classify
                    # Read full file for now since files aren't huge
                    temp_df = pd.read_csv(full_p)
                    temp_df.columns = temp_df.columns.str.strip()
                    cols = temp_df.columns.tolist()
                    
                    # Classifier Logic
                    is_report = '單號' in cols and ('總計' in cols or 'Total' in cols)
                    is_details = 'Item Name' in cols or 'Item Quantity' in cols
                    
                    if is_report:
                        # Process Report
                        temp_df['單號'] = temp_df['單號'].astype(str).str.strip()
                        all_reports.append(temp_df)
                        debug_logs.append(f"Loaded Report: {f} ({len(temp_df)} rows)")
                        
                    elif is_details:
                        # Process Details
                        all_details.append(temp_df)
                        debug_logs.append(f"Loaded Details: {f} ({len(temp_df)} rows)")
                        
                    else:
                        debug_logs.append(f"Skipped {f}: Unknown format (Cols: {cols[:3]}...)")
                        
                except Exception as e:
                    debug_logs.append(f"Error reading {f}: {e}")
                        
        except Exception as e:
             debug_logs.append(f"Error listing {path}: {e}")

    # Merge
    if all_reports:
        df_report = pd.concat(all_reports, ignore_index=True)
        # Simple exact-row deduplication only (safe)
        df_report.drop_duplicates(inplace=True)
        debug_logs.append(f"Merged Report: {len(df_report)} rows")
    else:
        df_report = pd.DataFrame()

    if all_details:
        df_details = pd.concat(all_details, ignore_index=True)
        df_details.drop_duplicates(inplace=True)
    else:
        df_details = pd.DataFrame()
        
    return df_report, df_details, debug_logs

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
    clean_cols_d = {c: c.strip() for c in df_details.columns}
    df_details.rename(columns=clean_cols_d, inplace=True)
    
    clean_cols_r = {c: c.strip() for c in df_report.columns}
    df_report.rename(columns=clean_cols_r, inplace=True)
    
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
            
            # P17.5 Fix: C=Veg/青菜, D=Sides/小菜 (User Request 1527)
            if prefix == 'C': return 'C 青菜 (Vegetables)' 
            if prefix == 'D': return 'D 小菜 (Sides)' 
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

    # --- P18 Fix: Standardize 'Order Number' for Joining ---
    # Ensure both dataframes have 'Order Number' column
    # Report might have '訂單編號' OR '單號' (as seen in debug)
    if '訂單編號' in df_report.columns and 'Order Number' not in df_report.columns:
        df_report['Order Number'] = df_report['訂單編號']
    elif '單號' in df_report.columns and 'Order Number' not in df_report.columns:
        df_report['Order Number'] = df_report['單號']
    
    if '訂單編號' in df_details.columns and 'Order Number' not in df_details.columns:
        df_details['Order Number'] = df_details['訂單編號']
    elif '單號' in df_details.columns and 'Order Number' not in df_details.columns:
        df_details['Order Number'] = df_details['單號']
        
    # Ensure they are transparently string type for merging
    if 'Order Number' in df_report.columns:
        df_report['Order Number'] = df_report['Order Number'].astype(str).str.strip()
        
    if 'Order Number' in df_details.columns:
        df_details['Order Number'] = df_details['Order Number'].astype(str).str.strip()

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

# --- Prediction Logic P13 + P17 Debug ---
def predict_revenue_logic(df_report, days_back=14):
    end_date = df_report['Date_Parsed'].max()
    # Internal Debug
    # st.write(f"DEBUG_INTERNAL: DaysBack={days_back}, EndDate={end_date}")
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
    counts = daily_sums.groupby('Simple')['Date_Parsed'].count()
    
    avg_wd = avgs.get('Weekday', 0)
    avg_hd = avgs.get('Holiday', 0)
    cnt_wd = counts.get('Weekday', 0)
    cnt_hd = counts.get('Holiday', 0)
    
    if avg_wd == 0 and avg_hd > 0: avg_wd = avg_hd
    if avg_hd == 0 and avg_wd > 0: avg_hd = avg_wd
    
    return avg_wd, avg_hd, cnt_wd, cnt_hd, start_date, end_date

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
    st.sidebar.title("🍜 滾麵 Dashboard")
    
    # Safe Mode Toggle (Before Data Load)
    safe_mode = st.sidebar.checkbox("⚠️ 僅讀取舊資料 (Safe Mode)", value=False, help="若資料異常，請勾選此項以排除新上傳的檔案")
    
    with st.spinner('數據處理中...'):
        df_report_raw, df_details_raw, debug_logs = load_data(safe_mode=safe_mode)
        df_report, df_details = preprocess_data(df_report_raw, df_details_raw)

    if df_report.empty:
        st.warning("尚未載入資料")
        if debug_logs:
            with st.expander("除錯日誌 (Debug Logs)"):
                for l in debug_logs: st.write(l)
        st.stop()
        
    # Navigation
    # view_mode = st.sidebar.radio... (Keep existing logic if possible, or re-declare)
    # The original code had st.sidebar.title AFTER load_data. I moved it up.
    # Let's just restate the navigation.
    
    view_mode = st.sidebar.radio("功能切換", ["📊 營運總覽", "🍟 商品分析", "👥 會員查詢", "🆕 新舊客分析", "🔮 智慧預測", "📁 檔案檢查", "🚀 部署測試"])
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
                st.write(f"**{sel_cat} 商品銷售佔比**")
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

    # --- VIEW 4: 新舊客分析 (Advanced Customer Analytics) ---
    elif view_mode == "🆕 新舊客分析":
        st.title("🆕 新舊客深度分析 (Customer CRM)")
        
        df_full = df_report 
        col_phone = '客戶電話' if '客戶電話' in df_full.columns else 'Contact'
        
        if col_phone not in df_full.columns:
            st.warning("無會員電話欄位，無法進行分析")
            st.stop()
            
        # 1. Data Preparation
        
        # --- Feature: Select Analysis Basis (Phone vs Carrier) ---
        analysis_basis = st.radio("分析基準 (Analysis Basis)", ["電話號碼 (Phone)", "載具號碼 (Carrier)"], horizontal=True)
        
        # Define Platform Phone Numbers
        UBER_PHONE = '55941277'
        
        # Helper to find Carrier Column
        possible_carrier_cols = ['載具號碼', 'Carrier Number', 'Carrier No', 'Mobile Carrier', '載具', 'Carrier']
        col_carrier = next((c for c in possible_carrier_cols if c in df_full.columns), None)
        
        # Function to generate unique Member ID
        def get_member_id(row, basis='phone'):
            if basis == 'phone':
                phone = str(row.get(col_phone, '')).strip()
                name = str(row.get('客戶姓名', '')).strip() 
                
                # Normalize Phone (remove spaces, -, +886)
                p_norm = phone.replace(" ", "").replace("-", "").replace("+886", "0")
                if p_norm.startswith("886"): p_norm = "0" + p_norm[3:]
    
                # Exclude Invalid / Foodpanda (Masked)
                if '*' in phone or phone == 'nan' or len(p_norm) < 5:
                    return None
                
                # Exclude Platform Phone (UberEats) and specific excluded names
                if UBER_PHONE in p_norm or '陳美鳳' in name:
                    return None 
    
                # Standard Member (Phone as ID)
                return p_norm 
            
            elif basis == 'carrier':
                if not col_carrier: return None
                carrier = str(row.get(col_carrier, '')).strip()
                
                # Basic validation for Carrier Number (usually / followed by 7 alphanum, or pure alphanum)
                # Exclude empty, nan, or too short
                if carrier == 'nan' or not carrier or len(carrier) < 3:
                    return None
                
                return carrier

        basis_key = 'phone' if "Phone" in analysis_basis else 'carrier'
        
        if basis_key == 'carrier' and not col_carrier:
            st.warning(f"⚠️ 找不到載具號碼欄位。請確認資料包含以下欄位之一: {possible_carrier_cols}")
            st.stop()
            
        df_full['Member_ID'] = df_full.apply(lambda r: get_member_id(r, basis=basis_key), axis=1)
        
        df_members = df_full[df_full['Member_ID'].notna()].copy()
        
        if df_members.empty:
            st.warning(f"分析失敗: 找不到有效的會員資料 (Basis: {analysis_basis})")
            st.stop()
            
        # --- Date Range Filter for CRM ---
        st.markdown(f"### ⚙️ 分析設定 ({analysis_basis})")
        min_date = df_full['Date_Parsed'].min().date()
        max_date = df_full['Date_Parsed'].max().date()
        

        if 'crm_start_date' not in st.session_state:
            st.session_state['crm_start_date'] = min_date
        if 'crm_end_date' not in st.session_state:
            st.session_state['crm_end_date'] = max_date

        col_shortcuts = st.columns(7)
        today = date.today()
        
        if col_shortcuts[0].button("本週 (This Week)"):
            start = today - timedelta(days=today.weekday())
            st.session_state['crm_start_date'] = max(min_date, start)
            st.session_state['crm_end_date'] = min(max_date, today)
            st.rerun()
            
        if col_shortcuts[1].button("上週 (Last Week)"):
            last_week_start = today - timedelta(days=today.weekday() + 7)
            last_week_end = last_week_start + timedelta(days=6)
            st.session_state['crm_start_date'] = max(min_date, last_week_start)
            st.session_state['crm_end_date'] = min(max_date, last_week_end)
            st.rerun()

        if col_shortcuts[2].button("本月 (This Month)"):
            start = today.replace(day=1)
            st.session_state['crm_start_date'] = max(min_date, start)
            st.session_state['crm_end_date'] = min(max_date, today)
            st.rerun()

        if col_shortcuts[3].button("上月 (Last Month)"):
            first_this_month = today.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            st.session_state['crm_start_date'] = max(min_date, last_month_start)
            st.session_state['crm_end_date'] = min(max_date, last_month_end)
            st.rerun()

        if col_shortcuts[4].button("近2月 (Last 60d)"):
            start = today - timedelta(days=60)
            st.session_state['crm_start_date'] = max(min_date, start)
            st.session_state['crm_end_date'] = min(max_date, today)
            st.rerun()
            
        if col_shortcuts[5].button("近6月 (Last 180d)"):
            start = today - timedelta(days=180)
            st.session_state['crm_start_date'] = max(min_date, start)
            st.session_state['crm_end_date'] = min(max_date, today)
            st.rerun()
            
        if col_shortcuts[6].button("全部 (All Time)"):
            st.session_state['crm_start_date'] = min_date
            st.session_state['crm_end_date'] = max_date
            st.rerun()

        date_range = st.date_input(
            "選擇分析區間 (只分析此期間內有消費的會員)",
            value=(st.session_state['crm_start_date'], st.session_state['crm_end_date']),
            min_value=min_date,
            max_value=max_date
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            # Update session state if manually changed
            if start_date != st.session_state['crm_start_date'] or end_date != st.session_state['crm_end_date']:
                st.session_state['crm_start_date'] = start_date
                st.session_state['crm_end_date'] = end_date
        else:
            start_date, end_date = min_date, max_date
        
        
        # Calculate Member Stats (Group by Member_ID instead of Phone)
        # Fix: Count Visits by Unique Date (multiple orders same day = 1 visit)
        df_members['Visit_Date'] = df_members['Date_Parsed'].dt.date
        
        member_stats = df_members.groupby('Member_ID').agg({
            'Date_Parsed': ['min', 'max'],
            'Visit_Date': 'nunique',
            '總計': 'sum',
            col_phone: 'first', 
            '客戶姓名': 'first'
        }).reset_index()
        member_stats.columns = ['Member_ID', 'First_Visit', 'Last_Visit', 'Frequency', 'Monetary', 'Phone', 'Name']
        
        # Global Analysis Date
        today_date = pd.Timestamp(date.today())
        
        # --- RFM Calculation (Based on ALL History Analysis) ---
        # We calculate status based on full history first, then filter for display
        member_stats['Recency'] = (today_date - member_stats['Last_Visit']).dt.days
        
        # Define Segments
        def categorize_rfm(row):
            r, f, m = row['Recency'], row['Frequency'], row['Monetary']
            
            if f == 1:
                return 'One-time (一次客)' # Only 1 visit ever
            
            if r > 90:
                if f > 3: return 'Hibernating (沉睡客)'
                return 'At Risk (流失預警)' # Visited >1 time, but long ago
            
            if r <= 30:
                if f >= 4: return 'Champions (主力常客)' # Frequent & Recent
                if f >= 2: return 'Potential (潛力新星)' # Recent but low freq (2-3)
                return 'New (新客)' # Recent, low freq (likely just switched from 1->2 or just 1? No, f=1 is One-time)
                # Actually if F=1 and R<=30, it is 'One-time' by first rule. 
                # So here F>=2. 
            
            if r <= 60:
                return 'New (新客)' # A bit looser definition for "Recent"
                
            return 'Regular (一般熟客)'

        member_stats['Segment'] = member_stats.apply(categorize_rfm, axis=1)
        
        # --- FILTERING FOR DISPLAY ---
        # Filter Member Population: Only those who visited within [start_date, end_date]
        # We need to know if a member visited in this range. 
        # Since member_stats only has First/Last, we might miss someone who visited in middle but first/last are outside?
        # A safer way: Check df_members for visits in range.
        
        active_members_in_range = df_members[
            (df_members['Date_Parsed'].dt.date >= start_date) & 
            (df_members['Date_Parsed'].dt.date <= end_date)
        ]['Member_ID'].unique()
        
        member_stats_display = member_stats[member_stats['Member_ID'].isin(active_members_in_range)].copy()
        
        # Filter Transactions for Revenue/Preference
        df_full_filtered = df_full[
            (df_full['Date_Parsed'].dt.date >= start_date) & 
            (df_full['Date_Parsed'].dt.date <= end_date)
        ].copy()
        
        st.info(f"ℹ️ **分析母體**: 分析在 `{start_date}` 到 `{end_date}` 期間 **有消費的 {len(member_stats_display)} 位會員** (屬性由歷史行為判定)。")

        tab1, tab2, tab3 = st.tabs(["📊 RFM 客群分群", "📅 留存率分析 (Cohort)", "💰 營收與偏好"])

        with tab1:
            st.subheader("👥 客群分佈 (依歷史行為)")
            
            # Metrics
            seg_counts = member_stats_display['Segment'].value_counts().reset_index()
            seg_counts.columns = ['Segment', 'Count']
            
            c1, c2 = st.columns([1, 2])
            with c1:
                st.write("**客群人數分佈 (此區間有來訪)**")
                st.dataframe(seg_counts, use_container_width=True)
                
                # --- Automated Insights ---
                total_customers = len(member_stats_display)
                n_new = seg_counts[seg_counts['Segment'].str.contains('New')]['Count'].sum()
                n_churn = seg_counts[seg_counts['Segment'].str.contains('One-time')]['Count'].sum()
                n_champ = seg_counts[seg_counts['Segment'].str.contains('Champions')]['Count'].sum()
                
                churn_rate = (n_churn / total_customers * 100) if total_customers > 0 else 0
                new_rate = (n_new / total_customers * 100) if total_customers > 0 else 0
                
                insight_text = ""
                if new_rate > 40:
                    insight_text += "🚀 **新客佔比高**：近期行銷有效，建議設計「二訪優惠券」轉化新客。\n\n"
                if churn_rate > 30:
                    insight_text += "⚠️ **一次客過多**：超過 30% 客人只來一次，需檢視「首次體驗」或「餐點品質」。\n\n"
                if n_champ > 0:
                    insight_text += f"💎 **主力常客**：共有 {n_champ} 位鐵粉在期間內回訪！"
                
                if total_customers > 0:
                    st.info(f"**💡 數據洞察**\n\n{insight_text}")
                else:
                    st.warning("在此期間無會員消費數據。")

            with c2:
                if not seg_counts.empty:
                    fig_rfm = px.bar(seg_counts, x='Segment', y='Count', color='Segment', title="客群分佈圖 (活躍會員)")
                    st.plotly_chart(fig_rfm, use_container_width=True)
            
            st.divider()
            st.subheader("🩺 客群細節 (Scatter Plot)")
            
            if not member_stats_display.empty:
                # Use Member_ID or Name for hover to distinguish Platform users
                member_stats_display['到店次數'] = member_stats_display['Frequency'] # Rename for hover
                member_stats_display['消費金額'] = member_stats_display['Monetary'] # Rename for hover
    
                fig_scat = px.scatter(member_stats_display, x='Recency', y='Frequency', size='Monetary', color='Segment',
                                    hover_data=['Member_ID', 'Name', 'Phone', '消費金額', '到店次數', 'First_Visit'],
                                    title="RFM 分佈 (X=天數未訪, Y=到店次數, 大小=消費金額)")
                fig_scat.update_layout(xaxis_title="Recency (天數未訪 - 越小越好)", yaxis_title="Frequency (到店次數)")
                st.plotly_chart(fig_scat, use_container_width=True)
            else:
                st.info("無數據可顯示散佈圖")

            st.markdown("""
            ### 📌 客群定義說明
            | 客群名稱 | 定義 (條件) | 意義 / 行動建議 |
            | :--- | :--- | :--- |
            | **🏆 Champions (主力常客)** | 近30天有來，且累積 **4次以上** | VIP 客戶，需重點維護。 |
            | **🌱 Potential (潛力新星)** | 近30天有來，且累積 **2~3次** | 剛培養成習慣的熟客，需鼓勵回購。 |
            | **🆕 New (新客)** | 近30天 **第一次來** | 剛認識品牌，首購體驗最關鍵。 |
            | **📉 At Risk (流失預警)** | **30~90天** 沒出現了 | 曾經來過但最近消失，需發送優惠喚回。 |
            | **💤 Hibernating (沉睡客)** | 超過 **90天 (3個月)** 沒來 | 幾乎流失，挽回成本較高。 |
            | **🔵 One-time (一次客)** | 只來過 **1次**，且是 **30天前** | 試一次就沒來的過客。 |
            """)

        # --- TAB 2: Cohort Analysis ---
        with tab2:
            st.subheader("📅 同源留存率 (Cohort Retention)")
            st.caption("觀察每個月的新客，在後續月份的回訪比例")
            
            # 1. Assign Cohort Month (First Visit Month)
            member_stats['CohortMonth'] = member_stats['First_Visit'].dt.to_period('M')
            
            # 2. Merge Cohort back to transaction data
            # Use Member_ID for merge to be consistent
            df_cohort = df_members.merge(member_stats[['Member_ID', 'CohortMonth']], on='Member_ID', how='left')
            df_cohort['VisitMonth'] = df_cohort['Date_Parsed'].dt.to_period('M')
            
            # 3. Group by Cohort/VisitMonth and count unique users (Members)
            cohort_data = df_cohort.groupby(['CohortMonth', 'VisitMonth'])['Member_ID'].nunique().reset_index()
            cohort_data['PeriodNumber'] = (cohort_data['VisitMonth'] - cohort_data['CohortMonth']).apply(lambda x: x.n)
            
            # 4. Pivot for Heatmap
            cohort_pivot = cohort_data.pivot(index='CohortMonth', columns='PeriodNumber', values='Member_ID')
            cohort_size = cohort_pivot.iloc[:, 0]
            retention = cohort_pivot.divide(cohort_size, axis=0) # Percentage
            
            # Display using Plotly Heatmap (No matplotlib needed)
            import plotly.express as px
            
            # Format index for display
            y_labels = [str(x) for x in retention.index]
            x_labels = [f"+{x}月" for x in retention.columns]
            
            fig_cohort = px.imshow(retention, 
                                   labels=dict(x="經過月份", y="首次來訪月份", color="留存率"),
                                   x=x_labels,
                                   y=y_labels,
                                   text_auto='.1%',
                                   color_continuous_scale='Greens',
                                   title="留存率熱力圖 (Retention Rate %)")
            st.plotly_chart(fig_cohort, use_container_width=True)
            
            st.write("**實際回訪人數**")
            st.dataframe(cohort_pivot.fillna(0).style.format("{:.0f}"), use_container_width=True)

        # --- TAB 3: Revenue Contribution ---
        with tab3:
            st.subheader("💰 新舊客營收貢獻")
            
            # Use filtered data for Revenue Calculation to respect date range
            # Logic: If query date == First Visit Date -> New Rev, else Existing Rev
            
            # We need to map every transaction to whether it was that user's first visit
            first_visit_map = member_stats.set_index('Phone')['First_Visit'].to_dict()
            
            # Use df_full_filtered (Transactions in selected range)
            if df_full_filtered.empty:
                st.warning("此區間無營收數據")
            else:
                def classify_transaction(row):
                    phone = row.get(col_phone)
                    if pd.isna(phone): return 'Guest (非會員)'
                    
                    # Check first visit
                    fv = first_visit_map.get(phone)
                    if not fv: return 'Guest (非會員)'
                    
                    # If transaction date is same as first visit date -> New Member Revenue
                    # Actually, "New Customer Revenue" usually means revenue from customers acquired in this period?
                    # Or revenue from "New Segment" customers?
                    # Let's use the Segment definition! 
                    # Much better: Revenue from "New" vs "Regular" segments.
                    
                    # Get Member ID (we need to re-derive or merge)
                    # Optimization: Map Phone -> Segment
                    return 'Unknown'

                # Better Approach: Classify based on Transaction Date vs First Visit Date
                # If Transaction Date == First Visit Date -> New Member (First Purchase)
                # If Transaction Date > First Visit Date -> Returning Member
                
                # 1. Get First Visit Date for each member (from member_stats or df_members)
                # member_stats has 'First_Visit' (datetime64[ns] or similar)
                mem_fv_map = member_stats.set_index('Member_ID')['First_Visit'].dt.date.to_dict()
                
                df_rev_calc = df_full_filtered.copy()
                
                def classify_rev_type(row):
                    mid = row.get('Member_ID')
                    if pd.isna(mid) or mid not in mem_fv_map: return 'Guest (非會員)'
                    
                    tx_date = row['Date_Parsed'].date() # Assuming Date_Parsed is datetime
                    fv_date = mem_fv_map[mid]
                    
                    if tx_date == fv_date: return 'New Member (新會員)'
                    return 'Returning Member (舊會員)'

                df_rev_calc['UserType_Rev'] = df_rev_calc.apply(classify_rev_type, axis=1)
                
                # Stacked Bar: Date vs Revenue by Type
                rev_trend = df_rev_calc.groupby(['Date_Parsed', 'UserType_Rev'])['總計'].sum().reset_index()
                
                fig_rev = px.bar(rev_trend, x='Date_Parsed', y='總計', color='UserType_Rev', 
                                title="營收貢獻趨勢 (依會員身份)",
                                color_discrete_map={'New Member (新會員)': '#FF7043', 'Returning Member (舊會員)': '#42A5F5', 'Guest (非會員)': '#BDBDBD'})
                st.plotly_chart(fig_rev, use_container_width=True)
                
                st.divider()
                st.subheader("🍛 口味偏好比較")
                
                # Use filtered transactions for Preference
                # Filter details for members only to link with segment
                
                col_order_rep = '訂單編號' if '訂單編號' in df_report.columns else 'Order Number'
                col_order_det = 'Order Number' if 'Order Number' in df_details.columns else '訂單編號'

                if col_order_rep in df_full_filtered.columns and col_order_det in df_details.columns:
                    # Map Order -> User Type (New/Return)
                    order_type_map = df_rev_calc.set_index(col_order_rep)['UserType_Rev'].to_dict()
                    
                    # Filter df_details to match filtered orders
                    valid_orders = set(df_rev_calc[col_order_rep])
                    df_det_pref = df_details[df_details[col_order_det].isin(valid_orders)].copy()
                    
                    df_det_pref['UserType'] = df_det_pref[col_order_det].map(order_type_map).fillna('Unknown')
                    
                    mask_new = df_det_pref['UserType'] == 'New Member (新會員)'
                    mask_ret = df_det_pref['UserType'] == 'Returning Member (舊會員)'
                    
                    top_n = 10
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**🟢 新會員最愛 Top {top_n}**")
                        if mask_new.any():
                            new_top = df_det_pref[mask_new].groupby('Item Name')['Item Quantity'].sum().nlargest(top_n).reset_index()
                            fig_n = px.bar(new_top, x='Item Quantity', y='Item Name', orientation='h', title="New Members Favorites")
                            fig_n.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_n, use_container_width=True)
                        else: st.info("此區間無新會員消費")
    
                    with col2:
                        st.write(f"**🔵 舊會員最愛 Top {top_n}**")
                        if mask_ret.any():
                            ret_top = df_det_pref[mask_ret].groupby('Item Name')['Item Quantity'].sum().nlargest(top_n).reset_index()
                            fig_r = px.bar(ret_top, x='Item Quantity', y='Item Name', orientation='h', title="Returning Members Favorites")
                            fig_r.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig_r, use_container_width=True)
                        else: st.info("此區間無舊會員消費")
                    
                else:
                    st.warning("無法連結訂單與商品資料 (缺少 Order Number 欄位)")




    # --- VIEW 5: 智慧預測 ---
    elif view_mode == "🔮 智慧預測":
        st.title("🔮 AI 營收預測")
        
        days_basis = st.radio("預測基礎", ["過去 2 週 (14 Days)", "過去 4 週 (28 Days)"], index=0, horizontal=True, key='pred_basis_radio')
        days_back = 28 if "28" in str(days_basis) else 14
        
        avg_wd, avg_hd, cnt_wd, cnt_hd, p_start, p_end = predict_revenue_logic(df_report, days_back=int(days_back))
        
        st.subheader(f"📊 預測參數 ({days_basis} 平均)")
        st.caption(f"統計區間: {p_start.strftime('%Y-%m-%d')} ~ {p_end.strftime('%Y-%m-%d')}")
        
        c1, c2 = st.columns(2)
        c1.metric(f"平日日均營收 (樣本: {cnt_wd}天)", f"${avg_wd:,.0f}")
        c2.metric(f"假日日均營收 (樣本: {cnt_hd}天)", f"${avg_hd:,.0f}")
        
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


    # --- VIEW 6: 系統檢查 (System Check & Diagnostics) ---
    elif view_mode == "📁 檔案檢查":
        st.title("🔍 伺服器檔案檢查 & 權限診斷")
        
        # --- Data Loading Logs ---
        with st.expander("📄 資料讀取詳細日誌 (Data Loading Logs)", expanded=True):
            if 'debug_logs' in locals() and debug_logs:
                st.write("以下顯示每個被讀取檔案的詳細資訊 (檔名, 列數, 前幾欄名稱):")
                for l in debug_logs:
                    st.text(l)
            else:
                st.info("無資料讀取日誌")

        # --- Daily Revenue Inspector ---
        st.subheader("📅 每日營收檢查 (Daily Revenue Check)")
        
        # Select Month to Inspect
        if not df_report.empty and 'Date_Parsed' in df_report.columns:
            months = df_report['Date_Parsed'].dt.to_period('M').unique().astype(str)
            months = sorted(months, reverse=True) # Newest first
            sel_month = st.selectbox("選擇月份 (Select Month)", months, index=0)
            
            # Filter Data
            mask_m = df_report['Date_Parsed'].dt.to_period('M').astype(str) == sel_month
            df_m = df_report[mask_m].copy()
            
            # Group by Day
            df_daily_chk = df_m.groupby(df_m['Date_Parsed'].dt.date).agg(
                Orders=('總計', 'count'),
                Revenue=('總計', 'sum')
            ).reset_index().rename(columns={'Date_Parsed': 'Date'})
            
            # Show Table
            st.dataframe(df_daily_chk.style.format({'Revenue': '${:,.0f}'}), use_container_width=True)
            
            total_rev = df_daily_chk['Revenue'].sum()
            st.metric(f"{sel_month} 總營收", f"${total_rev:,.0f}")
        else:
            st.warning("無日期資料可供檢查")

        st.divider()

        # --- Diagnostic Tools ---
        st.subheader("🛠️ 系統診斷資訊 (Debug Info)")
        if st.button("執行系統診斷 (Run Diagnostics)"):
            import subprocess
            
            def run_cmd(cmd):
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                    return result.stdout + result.stderr
                except Exception as e:
                    return f"Error: {e}"

            st.code(f"Current User (whoami): {run_cmd('whoami')}", language='bash')
            st.code(f"User Groups (groups): {run_cmd('groups')}", language='bash')
            st.code(f"Folder Permissions (ls -ld /home/eats365/data):\n{run_cmd('ls -ld /home/eats365/data')}", language='bash')
            st.code(f"Parent Permissions (ls -ld /home/eats365):\n{run_cmd('ls -ld /home/eats365')}", language='bash')
            st.code(f"Disk Usage (df -h /home/eats365):\n{run_cmd('df -h /home/eats365')}", language='bash')
            
            # Check sudo capability (might fail if interactive)
            st.code(f"Sudo Check (sudo -n true):\n{run_cmd('sudo -n true && echo Sudo_OK || echo Sudo_Fail')}", language='bash')

        # --- Fix Tool (Root Only) ---
        if st.button("🔧 一鍵修復權限 (Safe Fix)"):
            try:
                log = []
                
                # 1. Fix Home Dir (Must be 755 for SSH to work, NOT 777)
                home_dir = "/home/eats365"
                if not os.path.exists(home_dir):
                    os.makedirs(home_dir, exist_ok=True)
                
                os.chmod(home_dir, 0o755)
                log.append(f"Chmod 755 {home_dir} OK (SSH Safe)")
                
                # 2. Fix .ssh Security (Critical)
                ssh_dir = os.path.join(home_dir, ".ssh")
                if os.path.exists(ssh_dir):
                    os.chmod(ssh_dir, 0o700)
                    log.append(f"Secured {ssh_dir} (700)")
                    
                    auth_keys = os.path.join(ssh_dir, "authorized_keys")
                    if os.path.exists(auth_keys):
                        os.chmod(auth_keys, 0o600)
                        log.append(f"Secured {auth_keys} (600)")
                
                # 3. Open Data/Upload Dirs (777 is fine here)
                open_paths = ["/home/eats365/data", "/home/eats365/upload"]
                for p in open_paths:
                    if not os.path.exists(p):
                        os.makedirs(p, exist_ok=True)
                        log.append(f"Created {p}")
                    
                    # Recursive 777
                    os.chmod(p, 0o777)
                    for root, dirs, files in os.walk(p):
                        for d in dirs:
                            os.chmod(os.path.join(root, d), 0o777)
                        for f in files:
                            os.chmod(os.path.join(root, f), 0o666)
                    log.append(f"Opened {p} (777) OK")

                st.success("安全權限修復完成！日誌如下：\n" + "\n".join(log))
                st.balloons()
                
            except Exception as e:
                st.error(f"修復失敗: {e}")

        st.divider()
        
        # Define directories to check
        dirs_to_check = {
            "🏠 SFTP Home (/home/eats365)": "/home/eats365",
            "📂 Data Dir (/home/eats365/data)": "/home/eats365/data",
            "⬆️ Upload Dir (/home/eats365/upload)": "/home/eats365/upload",
            "📍 Current Dir (.)": os.getcwd()
        }
        
        sel_dir_name = st.selectbox("選擇要檢查的資料夾", list(dirs_to_check.keys()))
        target_path = dirs_to_check[sel_dir_name]
        
        st.write(f"正在檢查路徑: `{target_path}`")
        
        if os.path.exists(target_path):
            try:
                files = []
                for f in os.listdir(target_path):
                    full_path = os.path.join(target_path, f)
                    try:
                        stat = os.stat(full_path)
                        size_kb = round(stat.st_size / 1024, 2)
                        mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        ftype = "Dir" if os.path.isdir(full_path) else "File"
                        
                        # Get Owner/Permissions if possible
                        import pwd, grp
                        try:
                            owner = pwd.getpwuid(stat.st_uid).pw_name
                        except: owner = str(stat.st_uid)
                        try:
                            group = grp.getgrgid(stat.st_gid).gr_name
                        except: group = str(stat.st_gid)
                        perms = oct(stat.st_mode)[-3:]
                        
                    except:
                        size_kb = 0
                        mtime = "Unknown"
                        ftype = "Unknown"
                        owner = "?"
                        group = "?"
                        perms = "?"
                        
                    files.append({
                        "Filename": f,
                        "Type": ftype,
                        "Size (KB)": size_kb,
                        "Modified Time": mtime,
                        "Owner": owner,
                        "Group": group,
                        "Perms": perms
                    })
                
                if files:
                    df_files = pd.DataFrame(files)
                    st.dataframe(df_files.sort_values('Modified Time', ascending=False), use_container_width=True)
                else:
                    st.info("此資料夾為空 (Empty)")
            except Exception as e:
                st.error(f"無法讀取 (Permission Error?): {e}")
        else:
            st.warning(f"找不到此資料夾: {target_path}")
            
        st.caption(f"Current User: {os.environ.get('USER', 'Unknown')}")

except Exception as e:
    st.error(f"系統錯誤: {e}")
