import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from .utils import calculate_delta
import db_queries

def render_operational_view():
    st.title("📊 營運總覽")
    
    # --- Local Date Filter ---
    from .utils import render_date_filter
    start_date, end_date = render_date_filter("ops", "近2週 (Last 2 Weeks)")
    
    st.divider()

    # Query Pre-Aggregated PostgreSQL Table
    df_agg = db_queries.fetch_daily_revenue_agg(start_date, end_date)
    
    if df_agg.empty:
        st.warning(f"此區間無營運資料 ({start_date.date()} ~ {end_date.date()})")
        return
        
    # Previous Period Query
    duration = end_date - start_date
    prev_end = start_date - pd.Timedelta(days=1)
    prev_start = prev_end - duration
    df_prev_agg = db_queries.fetch_daily_revenue_agg(prev_start, prev_end)

    # -------------------------------------------------------------
    # 1. Top Level Metrics
    # -------------------------------------------------------------
    curr_rev = df_agg['total_revenue'].sum()
    prev_rev = df_prev_agg['total_revenue'].sum() if not df_prev_agg.empty else 0
    
    curr_vis = df_agg['total_guests'].sum()
    prev_vis = df_prev_agg['total_guests'].sum() if not df_prev_agg.empty else 0

    curr_txs = df_agg['total_orders'].sum()
    prev_txs = df_prev_agg['total_orders'].sum() if not df_prev_agg.empty else 0
    
    curr_avg = curr_rev / curr_vis if curr_vis > 0 else 0
    prev_avg = prev_rev / prev_vis if prev_vis > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰總營業額", f"${curr_rev:,.0f}", f"{calculate_delta(curr_rev, prev_rev):.1%}" if prev_rev else None)
    c2.metric("🍜來客數 (主食數)", f"{curr_vis:,.0f}", f"{calculate_delta(curr_vis, prev_vis):.1%}" if prev_vis else None)
    c3.metric("🧾訂單數", f"{curr_txs:,.0f}", f"{calculate_delta(curr_txs, prev_txs):.1%}" if prev_txs else None)
    c4.metric("👤平均客單價", f"${curr_avg:,.0f}", f"{calculate_delta(curr_avg, prev_avg):.1%}" if prev_avg else None)
    st.divider()

    # -------------------------------------------------------------
    # 2. Charts 
    # -------------------------------------------------------------
    ov_int = st.radio("圖表單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"], horizontal=True, key='ov_int_new')
    ov_freq = 'D'
    if ov_int == "週 (Weekly)": ov_freq = 'W-MON'
    elif ov_int == "4週 (Monthly)": ov_freq = 'ME' # 'M' is deprecated in Pandas for MonthEnd, use 'ME'

    col_L, col_R = st.columns([2, 1])
    
    with col_L:
        st.subheader("📈 營業額趨勢")
        df_trend = db_queries.fetch_daily_revenue_trend(start_date, end_date)
        if not df_trend.empty:
            df_trend['Date_Parsed'] = pd.to_datetime(df_trend['Date_Parsed'])
            resampled = df_trend.groupby(['Order_Category', pd.Grouper(key='Date_Parsed', freq=ov_freq)])['total_amount'].sum().reset_index()
            total_resampled = df_trend.groupby(pd.Grouper(key='Date_Parsed', freq=ov_freq))['total_amount'].sum().reset_index()
            
            fig = px.bar(
                resampled, 
                x='Date_Parsed', 
                y='total_amount', 
                color='Order_Category',
                title=f"營業額 ({ov_int})",
                labels={'total_amount': '金額', 'Date_Parsed': '日期', 'Order_Category': '點餐類型'}
            )
            
            import plotly.graph_objects as go
            fig.add_trace(go.Scatter(
                x=total_resampled['Date_Parsed'],
                y=total_resampled['total_amount'],
                mode='lines+markers+text',
                name='全日總營業額',
                text=total_resampled['total_amount'].apply(lambda x: f"${x:,.0f}" if x > 0 else ""),
                textposition='top center',
                line=dict(color='rgba(0,0,0,0.6)', width=2, dash='dot'),
                marker=dict(size=6, color='black')
            ))
            
            fig.update_layout(xaxis_title=None, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

    with col_R:
        st.subheader("📅 平假日平均 (vs 上期)")
        df_raw = db_queries.fetch_daily_breakdown(start_date, end_date)
        df_raw_prev = db_queries.fetch_daily_breakdown(prev_start, prev_end)
        
        if not df_raw.empty and 'Day_Type' in df_raw.columns:
            daily_rev = df_raw.groupby(['Date_Only', 'Day_Type'])['total_amount'].sum().reset_index()
            curr_type_avg = daily_rev.groupby('Day_Type')['total_amount'].mean()
            
            if not df_raw_prev.empty:
                daily_rev_prev = df_raw_prev.groupby(['Date_Only', 'Day_Type'])['total_amount'].sum().reset_index()
                prev_type_avg = daily_rev_prev.groupby('Day_Type')['total_amount'].mean()
            else:
                prev_type_avg = pd.Series()

            for dtype in ['平日 (Weekday)', '假日 (Holiday)']:
                val = curr_type_avg.get(dtype, 0)
                pval = prev_type_avg.get(dtype, 0)
                st.metric(f"平均 {dtype}", f"${val:,.0f}", f"{calculate_delta(val, pval):.1%}" if pval else None)

    st.divider()

    st.subheader("📊 營運圖表 (Charts)")
    c_chart1, c_chart2 = st.columns([2, 1])
    
    with c_chart1:
        # Reconstruct Period breakdown from df_agg cols
        # df_agg has : lunch_revenue, dinner_revenue, date
        period_data = []
        for _, row in df_agg.iterrows():
            d = row['date']
            period_data.append({'Date_Parsed': d, 'Period': '中午 (Lunch)', 'total_amount': row['lunch_revenue'], 'plot_amount': -row['lunch_revenue']})
            period_data.append({'Date_Parsed': d, 'Period': '晚上 (Dinner)', 'total_amount': row['dinner_revenue'], 'plot_amount': row['dinner_revenue']})
            
        daily_period = pd.DataFrame(period_data)
        daily_period['Date_Parsed'] = pd.to_datetime(daily_period['Date_Parsed'])
        daily_period = daily_period.sort_values('Period', ascending=False)
        
        fig_bar = px.bar(
            daily_period, 
            x='Date_Parsed', 
            y='plot_amount', 
            color='Period', 
            title="每日營業額 (午餐向下 / 晚餐向上)",
            labels={'plot_amount': '金額', 'Date_Parsed': '日期', 'Period': '時段'},
            custom_data=['total_amount']
        )
        fig_bar.update_traces(hovertemplate='時段: %{color}<br>日期: %{x}<br>金額: $%{customdata[0]:,.0f}')
        fig_bar.update_layout(xaxis_title=None, yaxis=dict(tickformat="f"), barmode='relative')
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with c_chart2:
        cat_pie = pd.DataFrame([
            {'Order_Category': '內用 (Dine-in)', 'total_amount': df_agg['dine_in_revenue'].sum()},
            {'Order_Category': '外帶 (Takeout)', 'total_amount': df_agg['takeout_revenue'].sum()},
            {'Order_Category': '外送 (Delivery)', 'total_amount': df_agg['delivery_revenue'].sum()}
        ])
        cat_pie = cat_pie[cat_pie['total_amount'] > 0]
        
        if not cat_pie.empty:
            fig_pie = px.pie(cat_pie, values='total_amount', names='Order_Category', title="營收佔比 (期間加總)", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

    # Line Chart Visitors Dual Axis
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    df_agg['avg_check'] = df_agg['total_revenue'] / df_agg['total_guests'].replace(0, 1)
    
    fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
    fig_dual.add_trace(go.Scatter(x=df_agg['date'], y=df_agg['total_guests'], name="整日來客數", mode='lines+markers'), secondary_y=False)
    fig_dual.add_trace(go.Scatter(x=df_agg['date'], y=df_agg['avg_check'], name="客單價", mode='lines+markers', line=dict(dash='dot')), secondary_y=True)
    fig_dual.update_layout(title_text="每日來客數 & 客單價趨勢", xaxis_title="日期")
    fig_dual.update_yaxes(title_text="來客數 (人)", secondary_y=False)
    fig_dual.update_yaxes(title_text="客單價 ($)", secondary_y=True)
    
    with st.expander("📊 點擊展開：查看詳細來客數與客單價雙軸走勢圖", expanded=False):
        st.plotly_chart(fig_dual, use_container_width=True)

    st.divider()
    
    # -------------------------------------------------------------
    # 3. Data Table
    # -------------------------------------------------------------
    st.subheader("📋 詳細營運數據 (Daily Metrics Table)")
    
    df_agg['Date_Parsed'] = pd.to_datetime(df_agg['date'])
    grouped = df_agg.set_index('Date_Parsed').resample(ov_freq)
    
    base_agg = grouped.agg({
        'total_revenue': 'sum',
        'lunch_revenue': 'sum',
        'dinner_revenue': 'sum',
        'total_guests': 'sum',
        'dine_in_revenue': 'sum',
        'takeout_revenue': 'sum',
        'delivery_revenue': 'sum'
    }).reset_index()
    
    base_agg['客單價'] = base_agg['total_revenue'] / base_agg['total_guests'].replace(0, 1)
    
    date_col = '日期'
    if ov_freq == 'D':
        base_agg[date_col] = base_agg['Date_Parsed'].dt.date.astype(str)
    else:
        base_agg[date_col] = base_agg['Date_Parsed'].dt.strftime('%Y-%m-%d (Start)')
        
    base_agg = base_agg.rename(columns={
        'total_revenue': '總營業額',
        'lunch_revenue': '中午營業額',
        'dinner_revenue': '晚上營業額',
        'total_guests': '整日來客數',
        'dine_in_revenue': '堂食營業額',
        'takeout_revenue': '外帶營業額',
        'delivery_revenue': '外送營業額'
    })
    
    cols_order = [date_col, '中午營業額', '晚上營業額', '總營業額', '整日來客數', '客單價', '外送營業額', '外帶營業額', '堂食營業額']
    final_cols = [c for c in cols_order if c in base_agg.columns]
    
    st.dataframe(
        base_agg[final_cols].sort_values(date_col, ascending=False).style.format({
            '中午營業額': "${:,.0f}", '晚上營業額': "${:,.0f}", '總營業額': "${:,.0f}",
            '整日來客數': "{:,.0f}", '客單價': "${:,.0f}",
            '外送營業額': "${:,.0f}", '外帶營業額': "${:,.0f}", '堂食營業額': "${:,.0f}"
        }), 
        use_container_width=True
    )
