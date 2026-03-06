import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
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
    
    # --- Forecast: This Month + 12 Future Months ---
    st.subheader("🔮 本月 + 未來 12 個月營業額預測")
    st.caption("✨ 本月：已發生實際營收 ＋ 剩餘天數預測（堆疊顯示）。未來各月：全月預測。")
    
    today = date.today()
    this_month_start = today.replace(day=1)
    
    # Actual revenue already recorded in current month
    actual_this_month = daily_rev[
        (daily_rev['Date_Only'] >= this_month_start) &
        (daily_rev['Date_Only'] <= max_date)
    ]['total_amount'].sum()
    
    future_data = []
    
    # Generate 13 entries: this month + 12 future months
    for i in range(13):
        target_month_start = this_month_start + relativedelta(months=i)
        year = target_month_start.year
        month = target_month_start.month
        is_current_month = (i == 0)
        
        if year not in tw_holidays.years:
            tw_holidays.update(holidays.country_holidays('TW', years=year))
            
        full_month_end = target_month_start + relativedelta(months=1) - pd.Timedelta(days=1)
        
        # For this month, only project remaining days after latest data date
        if is_current_month:
            project_start = max_date + pd.Timedelta(days=1)
            dates_to_project = pd.date_range(project_start, full_month_end).date
            month_label = target_month_start.strftime('%Y-%m') + ' ✨本月'
        else:
            dates_to_project = pd.date_range(target_month_start, full_month_end).date
            month_label = target_month_start.strftime('%Y-%m')
        
        wd_count = sum(1 for d in dates_to_project if not is_cny_closed_day(d, tw_holidays) and not is_holiday_tw(d, tw_holidays))
        hol_count = sum(1 for d in dates_to_project if not is_cny_closed_day(d, tw_holidays) and is_holiday_tw(d, tw_holidays))
        
        predicted_remaining = (wd_count * avg_wd_rev) + (hol_count * avg_hol_rev)
        actual = actual_this_month if is_current_month else 0
        
        future_data.append({
            '月份 (Month)': month_label,
            '已發生營收 (Actual)': actual,
            '預測剩餘 (Forecast)': predicted_remaining,
            '合計 (Total)': actual + predicted_remaining,
            '平日天數 (Weekdays)': wd_count,
            '假日天數 (Holidays)': hol_count,
        })
        
    future_df = pd.DataFrame(future_data)
    
    fig_pred = go.Figure()
    fig_pred.add_trace(go.Bar(
        x=future_df['月份 (Month)'],
        y=future_df['已發生營收 (Actual)'],
        name='已發生實際營收',
        marker_color='#636EFA'
    ))
    fig_pred.add_trace(go.Bar(
        x=future_df['月份 (Month)'],
        y=future_df['預測剩餘 (Forecast)'],
        name='預測剩餘天數',
        marker_color='rgba(239,85,59,0.65)'
    ))
    fig_pred.update_layout(
        barmode='stack',
        title='本月 + 未來 12 個月預測營業額',
        xaxis_title=None,
        yaxis_title='營業額 ($)',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    st.plotly_chart(fig_pred, use_container_width=True)
    
    # Table
    st.dataframe(
        future_df[['月份 (Month)', '已發生營收 (Actual)', '預測剩餘 (Forecast)', '合計 (Total)', '平日天數 (Weekdays)', '假日天數 (Holidays)']].style.format({
            '已發生營收 (Actual)': '${:,.0f}',
            '預測剩餘 (Forecast)': '${:,.0f}',
            '合計 (Total)': '${:,.0f}'
        }),
        use_container_width=True
    )
