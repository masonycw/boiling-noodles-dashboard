import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta
import holidays
import db_queries

def is_holiday_tw(dt, tw_holidays):
    """Returns True if the date is a weekend or a Taiwanese national holiday."""
    if dt.weekday() >= 5: # Saturday = 5, Sunday = 6
        return True
    if dt in tw_holidays:
        return True
    return False

def is_cny_closed_day(dt, tw_holidays):
    """Returns True if the date is Chinese New Year's Eve through Day 3, handling multiple holiday naming conventions."""
    name = tw_holidays.get(dt)
    if not name:
        return False
        
    if isinstance(name, list):
        name = ", ".join(name)
        
    name = name.lower()
    
    # Ignore makeup days / observed days
    if "observed" in name or "adjusted" in name or "補假" in name or "補行" in name:
        return False
        
    cny_keywords = [
        "chinese new year", "spring festival", "lunar new year",
        "農曆除夕", "春節", "除夕", "初一", "初二", "初三"
    ]
    
    return any(keyword in name for keyword in cny_keywords)

def render_prediction_view():
    st.title("📈 營業額預測 (Revenue Prediction)")

    df_agg = db_queries.fetch_daily_revenue_agg()
    
    if df_agg.empty:
        st.info("尚未載入營運資料 (Data missing)")
        return

    # Prepare Data
    daily_rev = df_agg[['date', 'total_revenue']].rename(columns={'date': 'Date_Parsed', 'total_revenue': 'total_amount'}).copy()
    daily_rev['Date_Parsed'] = pd.to_datetime(daily_rev['Date_Parsed'])
    daily_rev['Date_Only'] = daily_rev['Date_Parsed'].dt.date
    daily_rev['total_amount'] = daily_rev['total_amount'].fillna(0)

    # Latest date in data
    max_date = daily_rev['Date_Only'].max()
    min_date = daily_rev['Date_Only'].min()
    if pd.isna(max_date) or pd.isna(min_date):
        return
        
    # Get holidays for the relevant years (all history to next year)
    years_needed = list(range(min_date.year, max_date.year + 2))
    tw_holidays = holidays.country_holidays('TW', years=years_needed)

    # Mark past days as holiday or weekday
    daily_rev['Is_Holiday'] = daily_rev['Date_Only'].apply(lambda d: is_holiday_tw(d, tw_holidays))
    
    # UI Controls
    c1, c2 = st.columns([1, 2])
    with c1:
        ref_window = st.selectbox("預測參考基準 (Reference Period)", ["過去2週 (Past 2 Weeks)", "過去4週 (Past 4 Weeks)", "過去1個月 (Past 1 Month)"])
        if "2週" in ref_window:
            days_lookback = 14
        elif "4週" in ref_window:
            days_lookback = 28
        else:
            days_lookback = 30
        
    # Calculate Past Averages
    start_ref_date = max_date - pd.Timedelta(days=days_lookback - 1)
    ref_df = daily_rev[(daily_rev['Date_Only'] >= start_ref_date) & (daily_rev['Date_Only'] <= max_date)]
    
    past_wd = ref_df[(~ref_df['Is_Holiday']) & (ref_df['total_amount'] > 0)]
    past_hol = ref_df[(ref_df['Is_Holiday']) & (ref_df['total_amount'] > 0)]
    
    avg_wd_rev = past_wd['total_amount'].mean() if len(past_wd) > 0 else 0
    avg_hol_rev = past_hol['total_amount'].mean() if len(past_hol) > 0 else 0
    
    st.divider()
    
    col_w, col_h = st.columns(2)
    col_w.metric(f"📉 平日平均營業額 ({ref_window})", f"${avg_wd_rev:,.0f}")
    col_h.metric(f"🎌 假日平均營業額 ({ref_window})", f"${avg_hol_rev:,.0f}")
    
    st.caption("* 假日定義：包含週末 (六、日) 以及國定假日")
    st.caption("* 注意：預測邏輯已自動扣除每年除夕至初三之春節店休日，該四日預測營業額將視為 $0。")
    st.divider()
    
    # --- Historical Trend Chart ---
    st.subheader("📊 歷史平均營業額走勢 (Historical Averages Trend)")
    st.caption("觀察過去不同時間點的「滾動平均營業額」。長短期趨勢可由最上方的「參考基準」控制調整。")
    
    from .utils import render_date_filter
    s_date, e_date = render_date_filter("pred_hist")
    
    # Create complete date range bridging any gaps, to allow proper rolling across days without data
    full_date_range = pd.date_range(start=min_date, end=max_date).date
    dense_df = pd.DataFrame({'Date_Only': full_date_range})
    dense_df = dense_df.merge(daily_rev, on='Date_Only', how='left')
    
    dense_df['Is_Holiday'] = dense_df['Date_Only'].apply(lambda d: is_holiday_tw(d, tw_holidays))
    dense_df['total_amount'] = dense_df['total_amount'].fillna(0)
    
    # Only average days that have > 0 revenue
    dense_df['valid_wd_rev'] = dense_df['total_amount'].where((~dense_df['Is_Holiday']) & (dense_df['total_amount'] > 0), np.nan)
    dense_df['valid_hol_rev'] = dense_df['total_amount'].where((dense_df['Is_Holiday']) & (dense_df['total_amount'] > 0), np.nan)
    
    # Rolling averages
    dense_df['平日平均 (Weekday Avg)'] = dense_df['valid_wd_rev'].rolling(window=days_lookback, min_periods=1).mean()
    dense_df['假日平均 (Holiday Avg)'] = dense_df['valid_hol_rev'].rolling(window=days_lookback, min_periods=1).mean()
    
    # Filter for the plotting interval
    mask = (dense_df['Date_Only'] >= s_date.date()) & (dense_df['Date_Only'] <= e_date.date())
    chart_df = dense_df[mask].copy()
    
    if not chart_df.empty:
        melted = chart_df.melt(id_vars=['Date_Only'], value_vars=['平日平均 (Weekday Avg)', '假日平均 (Holiday Avg)'], 
                               var_name='Type', value_name='Average_Revenue')
        
        fig_trend = px.line(melted, x='Date_Only', y='Average_Revenue', color='Type', 
                            title=f"過去 {days_lookback} 天為基準的滾動平均走勢",
                            labels={'Date_Only': '日期', 'Average_Revenue': '平均營業額 ($)'},
                            color_discrete_map={'平日平均 (Weekday Avg)': '#636EFA', '假日平均 (Holiday Avg)': '#EF553B'})
        fig_trend.update_yaxes(rangemode="tozero")
        fig_trend.update_layout(legend_title_text='', hovermode="x unified")
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("所選區間內無歷史資料可供顯示。")
        
    st.divider()
    
    # Prepare Future 12 Months Projection
    st.subheader("🔮 未來 12 個月營業額預測")
    
    # Start from next month
    today = date.today()
    next_month = today.replace(day=1) + relativedelta(months=1)
    
    future_data = []
    
    # Generate 12 months
    for i in range(12):
        target_month = next_month + relativedelta(months=i)
        year = target_month.year
        month = target_month.month
        
        # Make sure holidays for that year are loaded
        if year not in tw_holidays.years:
            tw_holidays.update(holidays.country_holidays('TW', years=year))
            
        # Get all dates in that month
        start_dt = date(year, month, 1)
        end_dt = start_dt + relativedelta(months=1) - pd.Timedelta(days=1)
        
        dates_in_month = pd.date_range(start_dt, end_dt).date
        
        wd_count = 0
        hol_count = 0
        
        for d in dates_in_month:
            if is_cny_closed_day(d, tw_holidays):
                continue # Store is closed, exclude from multiplier completely
            elif is_holiday_tw(d, tw_holidays):
                hol_count += 1
            else:
                wd_count += 1
                
        pred_rev = (wd_count * avg_wd_rev) + (hol_count * avg_hol_rev)
        
        future_data.append({
            '月份 (Month)': target_month.strftime('%Y-%m'),
            '平日天數 (Weekdays)': wd_count,
            '假日天數 (Holidays)': hol_count,
            '預測營業額 (Predicted)': pred_rev
        })
        
    future_df = pd.DataFrame(future_data)
    
    # Visual Chart
    fig_pred = px.bar(future_df, x='月份 (Month)', y='預測營業額 (Predicted)', title="未來 12 個月預測營業額", text_auto='.2s')
    st.plotly_chart(fig_pred, use_container_width=True)
    
    # Table View
    st.dataframe(
        future_df.style.format({
            '預測營業額 (Predicted)': '${:,.0f}'
        }),
        use_container_width=True
    )

