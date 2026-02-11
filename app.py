import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
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

# Taiwan Holidays (2024-2025) - Manual List for simplicity
tw_holidays = [
    # 2024
    "2024-01-01", "2024-02-08", "2024-02-09", "2024-02-10", "2024-02-11", "2024-02-12", "2024-02-13", "2024-02-14",
    "2024-02-28", "2024-04-04", "2024-04-05", "2024-05-01", "2024-06-10", "2024-09-17", "2024-10-10",
    # 2025
    "2025-01-01", "2025-01-25", "2025-01-26", "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", "2025-02-01", "2025-02-02",
    "2025-02-28", "2025-04-03", "2025-04-04", "2025-04-05", "2025-04-06", "2025-05-01", "2025-05-31", "2025-06-01", "2025-06-02",
    "2025-10-04", "2025-10-05", "2025-10-06", "2025-10-10", "2025-10-11", "2025-10-12"
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
        df_report = df_report[~df_report['狀態'].astype(str).str.contains('取消|Cancelled', case=False, na=False)]
    if 'Status' in df_details.columns:
        df_details = df_details[~df_details['Status'].astype(str).str.contains('取消|Cancelled', case=False, na=False)]

    if 'date' in df_report.columns:
        df_report['Date_Parsed'] = pd.to_datetime(df_report['date'], errors='coerce')
    if 'date' in df_details.columns:
        df_details['Date_Parsed'] = pd.to_datetime(df_details['date'], errors='coerce')

    # Combine DateTime
    if '時間' in df_report.columns and 'Date_Parsed' in df_report.columns:
        df_report['Datetime'] = pd.to_datetime(
            df_report['Date_Parsed'].dt.strftime('%Y-%m-%d') + ' ' + df_report['時間'].astype(str),
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

    # --- 5. Deduplicate Modifier Rows ---
    if 'Modifier Name' in df_details.columns:
        df_details = df_details[df_details['Modifier Name'].isna() | (df_details['Modifier Name'] == '')]

    # --- B. Specific Logic Updates ---
    
    # 1. Period (Lunch/Dinner)
    def get_period(dt):
        if pd.isnull(dt): return 'Unknown'
        return '中午 (Lunch)' if dt.hour < 16 else '晚上 (Dinner)'
    df_report['Period'] = df_report['Datetime'].apply(get_period) if 'Datetime' in df_report.columns else 'Unknown'

    # 2. Day Type (Weekday / Weekend / Holiday)
    def get_day_type(dt):
        if pd.isnull(dt): return 'Unknown'
        d_str = dt.strftime('%Y-%m-%d')
        # Check Special Holiday -> Weekend -> Weekday
        if d_str in TW_HOLIDAYS_SET:
            return '特別假日 (Holiday)'
        if dt.weekday() >= 5: # 5=Sat, 6=Sun
            return '週末 (Weekend)'
        return '平日 (Weekday)'
    
    df_report['Day_Type'] = df_report['Date_Parsed'].apply(get_day_type)

    # 3. Category Inference (Noodle/Rice/Soup/Drink)
    clean_cols = {c: c.strip() for c in df_details.columns}
    df_details.rename(columns=clean_cols, inplace=True)
    
    def infer_category(name):
        name = str(name)
        if '麵' in name: return '麵類 (Noodle)'
        if '飯' in name: return '飯類 (Rice)'
        if any(x in name for x in ['湯', '羹']): return '湯品 (Soup)'
        if any(x in name for x in ['茶', '飲', '拿鐵', '咖啡', '可樂', '雪碧']): return '飲料 (Drink)'
        if any(x in name for x in ['菜', '豆干', '皮蛋', '肉', '蛋', '豆腐']): return '小菜 (Side Dish)'
        return '其他 (Others)'
        
    df_details['Category'] = df_details['Item Name'].apply(infer_category)

    # 4. Main Dish Identification
    df_details['Is_Main_Dish'] = False
    mask_name = df_details['Item Name'].astype(str).str.contains('麵|飯', regex=True, na=False)
    
    mask_exclude_wrapper = pd.Series([True] * len(df_details))
    if 'Item Type' in df_details.columns:
        # Exclude 'Combo Item' wrapper, keep 'Single Item in Combo Item'
        mask_is_wrapper = df_details['Item Type'].astype(str).str.fullmatch('Combo Item', case=False, na=False)
        mask_exclude_wrapper = ~mask_is_wrapper
    
    df_details.loc[mask_name & mask_exclude_wrapper, 'Is_Main_Dish'] = True

    return df_report, df_details

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

    st.sidebar.header("📅 日期篩選")
    filter_mode = st.sidebar.selectbox(
        "快速區間", 
        ["今日 (Today)", "昨日 (Yesterday)", "本週 (This Week)", "本月 (This Month)", "近 30 天", "自訂範圍"],
        index=3
    ) # Added "近 30 天"
    
    today = pd.Timestamp.now().normalize()
    if filter_mode == "今日 (Today)": start_date = end_date = today
    elif filter_mode == "昨日 (Yesterday)": start_date = end_date = today - timedelta(days=1)
    elif filter_mode == "本週 (This Week)": start_date = today - timedelta(days=today.weekday()); end_date = today
    elif filter_mode == "本月 (This Month)": start_date = today.replace(day=1); end_date = today
    elif filter_mode == "近 30 天": start_date = today - timedelta(days=30); end_date = today
    else:
        d = st.sidebar.date_input("選擇日期", [today - timedelta(days=7), today])
        start_date = pd.to_datetime(d[0]) if len(d) > 0 else today
        end_date = pd.to_datetime(d[1]) if len(d) > 1 else start_date

    mask_rep = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    df_rep_filtered = df_report.loc[mask_rep]
    mask_det = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
    df_det_filtered = df_details.loc[mask_det]

    if view_mode == "📊 營運總覽":
        st.title(f"📊 營運總覽 ({start_date.date()} ~ {end_date.date()})")
        
        # KPI
        rev = df_rep_filtered['總計'].sum()
        txs = len(df_rep_filtered)
        visitors = df_det_filtered[df_det_filtered['Is_Main_Dish']]['Item Quantity'].sum()
        avg_price = rev / visitors if visitors > 0 else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰總營業額", f"${rev:,.0f}")
        c2.metric("🍜來客數", f"{visitors:,.0f}")
        c3.metric("🧾訂單數", f"{txs:,.0f}")
        c4.metric("👤平均客單價", f"${avg_price:,.0f}")
        st.divider()
        
        # New Feature: Weekday vs Holiday Analysis
        st.subheader("📅 平日 vs 假日/國定假日 (平均日營業額)")
        if not df_rep_filtered.empty:
            # Group by Date first to get Daily Revenue
            daily_rev = df_rep_filtered.groupby(['Date_Parsed', 'Day_Type'])['總計'].sum().reset_index()
            # Then avg by Day_Type
            type_avg = daily_rev.groupby('Day_Type')['總計'].mean().reset_index()
            
            c_wk, c_hol = st.columns(2)
            
            val_wk = type_avg[type_avg['Day_Type']=='平日 (Weekday)']['總計'].values
            val_wk = val_wk[0] if len(val_wk)>0 else 0
            
            # Combine Weekend & Special Holiday for simplicity or show all?
            # Let's show Bar Chart for clear comparison
            fig_daytype = px.bar(type_avg, x='Day_Type', y='總計', color='Day_Type', 
                                 title="平均日營業額比較", text_auto='.0f',
                                 color_discrete_map={'平日 (Weekday)': '#9E9E9E', '週末 (Weekend)': '#FF9800', '特別假日 (Holiday)': '#F44336'})
            st.plotly_chart(fig_daytype, use_container_width=True)
            
            # List Special Holidays
            with st.expander("📅 查看期間內的「詳細與特別假日」清單"):
                # Filter rows where Day_Type is Special Holiday or Weekend
                special_days = daily_rev[daily_rev['Day_Type'].isin(['特別假日 (Holiday)', '週末 (Weekend)'])]
                if not special_days.empty:
                    st.dataframe(special_days.sort_values('Date_Parsed'), use_container_width=True)
                else:
                    st.info("此區間無特別假日或週末")
        
        st.divider()

        # Graphs
        col_L, col_R = st.columns([2, 1])
        with col_L:
            st.subheader("📈 營業額趨勢")
            if not df_rep_filtered.empty:
                daily = df_rep_filtered.groupby(['Date_Parsed', 'Period'])['總計'].sum().reset_index()
                fig = px.bar(daily, x='Date_Parsed', y='總計', color='Period', barmode='stack', color_discrete_map={'中午 (Lunch)': '#FFC107', '晚上 (Dinner)': '#3F51B5'})
                st.plotly_chart(fig, use_container_width=True)
        with col_R:
            st.subheader("Order Type")
            col_type = '單類型' if '單類型' in df_rep_filtered.columns else 'Order Type'
            if col_type in df_rep_filtered.columns:
                type_sum = df_rep_filtered.groupby(col_type)['總計'].sum().reset_index()
                fig = px.pie(type_sum, values='總計', names=col_type, hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
                
    elif view_mode == "🍟 商品分析":
        st.title("🍟 商品銷售分析")
        
        if 'Item Name' in df_det_filtered.columns:
            # Clean
            df_items = df_det_filtered.dropna(subset=['Item Name'])
            
            # Group by Category + Item Name
            item_stats = df_items.groupby(['Category', 'Item Name']).agg({
                'Item Quantity': 'sum',
                'Item Amount(TWD)': 'sum'
            }).reset_index()
            
            # Sort
            item_stats = item_stats.sort_values(['Category', 'Item Quantity'], ascending=[True, False])
            
            # Treemap or Bar Chart by Category
            st.subheader("📊 類別銷售佔比")
            cat_sum = item_stats.groupby('Category')['Item Amount(TWD)'].sum().reset_index()
            fig_pie = px.pie(cat_sum, values='Item Amount(TWD)', names='Category', title="各類別營收佔比")
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Detail List
            st.subheader("📋 詳細清單 (依類別)")
            
            # Selector for Category
            cats = ['全部'] + list(item_stats['Category'].unique())
            sel_cat = st.selectbox("篩選類別", cats)
            
            if sel_cat != '全部':
                show_df = item_stats[item_stats['Category'] == sel_cat]
            else:
                show_df = item_stats
                
            st.dataframe(show_df, use_container_width=True)
            
        else:
            st.error("No Item Name found")

    elif view_mode == "👥 會員查詢":
        st.title("👥 會員消費紀錄查詢")
        phone_query = st.text_input("輸入電話:")
        col_phone = None
        for c in ['Contact', 'Customer Tel', '客戶電話']:
            if c in df_report.columns: col_phone = c; break
            
        if col_phone and phone_query:
            mask = df_report[col_phone].astype(str).str.contains(phone_query, na=False)
            hist = df_report[mask].sort_values('Date_Parsed', ascending=False)
            if not hist.empty:
                st.metric("歷史總消費", f"${hist['總計'].sum():,.0f}")
                st.dataframe(hist[['date', '時間', '總計', '單類型']])
            else:
                st.warning("查無紀錄")

except Exception as e:
    st.error(f"Error: {e}")
