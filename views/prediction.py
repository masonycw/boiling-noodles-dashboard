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
    if dt.weekday() >= 5:
        return True
    if dt in tw_holidays:
        return True
    return False

def is_cny_closed_day(dt, tw_holidays):
    """Returns True if the date is Chinese New Year's Eve through Day 3."""
    name = tw_holidays.get(dt)
    if not name:
        return False
    if isinstance(name, list):
        name = ", ".join(name)
    name = name.lower()
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

    max_date = daily_rev['Date_Only'].max()
    min_date = daily_rev['Date_Only'].min()
    if pd.isna(max_date) or pd.isna(min_date):
        return
        
    years_needed = list(range(min_date.year, max_date.year + 2))
    tw_holidays_obj = holidays.country_holidays('TW', years=years_needed)

    daily_rev['Is_Holiday'] = daily_rev['Date_Only'].apply(lambda d: is_holiday_tw(d, tw_holidays_obj))
    
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
    
    # Historical Trend
    st.subheader("📊 歷史平均營業額走勢 (Historical Averages Trend)")
    
    from .utils import render_date_filter
    s_date, e_date = render_date_filter("pred_hist")
    
    full_date_range = pd.date_range(start=min_date, end=max_date).date
    dense_df = pd.DataFrame({'Date_Only': full_date_range})
    dense_df = dense_df.merge(daily_rev, on='Date_Only', how='left')
    dense_df['Is_Holiday'] = dense_df['Date_Only'].apply(lambda d: is_holiday_tw(d, tw_holidays_obj))
    dense_df['total_amount'] = dense_df['total_amount'].fillna(0)
    dense_df['valid_wd_rev'] = dense_df['total_amount'].where((~dense_df['Is_Holiday']) & (dense_df['total_amount'] > 0), np.nan)
    dense_df['valid_hol_rev'] = dense_df['total_amount'].where((dense_df['Is_Holiday']) & (dense_df['total_amount'] > 0), np.nan)
    dense_df['平日平均 (Weekday Avg)'] = dense_df['valid_wd_rev'].rolling(window=days_lookback, min_periods=1).mean()
    dense_df['假日平均 (Holiday Avg)'] = dense_df['valid_hol_rev'].rolling(window=days_lookback, min_periods=1).mean()
    
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
    
    # --- Forecast ---
    st.subheader("🔮 本月 + 未來 12 個月營業額預測")
    st.caption("✨ 本月第一欄：左半段 = 已記錄實際營收，右半段（斜紋）= 剩餘天預測。後面 12 欄為完整月份預測。")
    
    today = date.today()
    this_month_start = today.replace(day=1)
    
    # Actual revenue already in DB for current month (max_date may be in previous month = 0)
    actual_this_month = float(daily_rev[
        (daily_rev['Date_Only'] >= this_month_start) &
        (daily_rev['Date_Only'] <= max_date)
    ]['total_amount'].sum())
    
    rows = []
    
    for i in range(13):
        target_start = this_month_start + relativedelta(months=i)
        y = target_start.year
        m = target_start.month
        is_curr = (i == 0)
        
        if y not in tw_holidays_obj.years:
            tw_holidays_obj.update(holidays.country_holidays('TW', years=y))
            
        month_end = target_start + relativedelta(months=1) - pd.Timedelta(days=1)
        
        if is_curr:
            # Project only remaining days (after max_date in DB)
            proj_start = max_date + pd.Timedelta(days=1)
            dates_proj = pd.date_range(proj_start, month_end).date if proj_start.date() <= month_end.date() else []
            label = target_start.strftime('%Y-%m') + ' ✨'
        else:
            dates_proj = pd.date_range(target_start, month_end).date
            label = target_start.strftime('%Y-%m')
        
        wd = sum(1 for d in dates_proj if not is_cny_closed_day(d, tw_holidays_obj) and not is_holiday_tw(d, tw_holidays_obj))
        hd = sum(1 for d in dates_proj if not is_cny_closed_day(d, tw_holidays_obj) and is_holiday_tw(d, tw_holidays_obj))
        
        forecast = (wd * avg_wd_rev) + (hd * avg_hol_rev)
        actual = actual_this_month if is_curr else 0.0
        
        rows.append({
            '月份': label,
            '已發生營收': actual,
            '預測剩餘': forecast,
            '合計': actual + forecast,
            '平日天數': wd,
            '假日天數': hd,
            'is_curr': is_curr,
        })
        
    df_fc = pd.DataFrame(rows)
    
    # Build chart
    curr = df_fc[df_fc['is_curr']].iloc[0]
    future = df_fc[~df_fc['is_curr']]
    
    fig = go.Figure()
    
    # Current month actual (solid blue)
    if curr['已發生營收'] > 0:
        fig.add_trace(go.Bar(
            x=[curr['月份']], y=[curr['已發生營收']],
            name='本月已發生',
            marker_color='#636EFA'
        ))
    
    # Current month forecast remainder (hatched blue)
    if curr['預測剩餘'] > 0:
        fig.add_trace(go.Bar(
            x=[curr['月份']], y=[curr['預測剩餘']],
            name='本月預測剩餘',
            marker_color='rgba(99,110,250,0.45)',
            marker_pattern_shape='/'
        ))
    
    # Future months (red)
    fig.add_trace(go.Bar(
        x=future['月份'], y=future['預測剩餘'],
        name='未來月份預測',
        marker_color='#EF553B'
    ))
    
    fig.update_layout(
        barmode='stack',
        title='本月 + 未來 12 個月預測營業額',
        xaxis_title=None,
        yaxis_title='營業額 ($)',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Current month summary metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("本月已發生營收", f"${curr['已發生營收']:,.0f}", help=f"資料截止 {max_date}")
    m2.metric("本月剩餘預測", f"${curr['預測剩餘']:,.0f}")
    m3.metric("本月預計合計", f"${curr['合計']:,.0f}")
    
    # Table
    st.dataframe(
        df_fc[['月份', '已發生營收', '預測剩餘', '合計', '平日天數', '假日天數']].style.format({
            '已發生營收': '${:,.0f}',
            '預測剩餘': '${:,.0f}',
            '合計': '${:,.0f}'
        }),
        use_container_width=True
    )
