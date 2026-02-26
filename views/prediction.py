import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from datetime import date
from dateutil.relativedelta import relativedelta
import holidays

def is_holiday_tw(dt, tw_holidays):
    """Returns True if the date is a weekend or a Taiwanese national holiday."""
    if dt.weekday() >= 5: # Saturday = 5, Sunday = 6
        return True
    if dt in tw_holidays:
        return True
    return False

def render_prediction_view(df_report):
    st.title("📈 營業額預測 (Revenue Prediction)")

    if df_report.empty:
        st.info("尚未載入營運資料 (Data missing)")
        return

    # Prepare Data
    df = df_report[df_report['Date_Parsed'].notna()].copy()
    daily_rev = df.set_index('Date_Parsed').resample('D')['total_amount'].sum().reset_index()
    daily_rev['Date_Only'] = daily_rev['Date_Parsed'].dt.date
    daily_rev['total_amount'] = daily_rev['total_amount'].fillna(0)

    # Latest date in data
    max_date = daily_rev['Date_Only'].max()
    if pd.isna(max_date):
        return
        
    # Get holidays for the relevant years (e.g. current year and next year)
    tw_holidays = holidays.country_holidays('TW', years=[max_date.year, max_date.year + 1])

    # Mark past days as holiday or weekday
    daily_rev['Is_Holiday'] = daily_rev['Date_Only'].apply(lambda d: is_holiday_tw(d, tw_holidays))
    
    # UI Controls
    c1, c2 = st.columns([1, 2])
    with c1:
        ref_window = st.selectbox("預測參考基準 (Reference Period)", ["過去2週 (Past 2 Weeks)", "過去4週 (Past 4 Weeks)"])
        days_lookback = 14 if "2週" in ref_window else 28
        
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
            if is_holiday_tw(d, tw_holidays):
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

