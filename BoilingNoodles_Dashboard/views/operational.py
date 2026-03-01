import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from .utils import calculate_delta

def render_operational_view(df_ops):
    st.title("📊 營運總覽")
    
    # --- Local Date Filter ---
    from .utils import render_date_filter
    start_date, end_date = render_date_filter("ops", "近2週 (Last 2 Weeks)")
    
    st.divider()

    # Filter Data
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)
    
    mask_rep = (df_ops['Date_Parsed'] >= start_ts) & (df_ops['Date_Parsed'] <= end_ts)
    df_rep = df_ops.loc[mask_rep].copy()
    
    # Previous Period
    duration = end_date - start_date
    prev_end_ts = start_ts - pd.Timedelta(days=1)
    prev_start_ts = prev_end_ts - duration
    mask_rep_prev = (df_ops['Date_Parsed'] >= prev_start_ts) & (df_ops['Date_Parsed'] <= prev_end_ts)
    df_rep_prev = df_ops.loc[mask_rep_prev].copy()

    # Metrics
    curr_rev = df_rep['total_amount'].sum()
    prev_rev = df_rep_prev['total_amount'].sum()
    
    # Visitors/Txs (Simplified because Data Mart already calculated it)
    curr_vis = df_rep['people_count'].sum()
    prev_vis = df_rep_prev['people_count'].sum()

    curr_txs = df_rep['tx_count'].sum()
    prev_txs = df_rep_prev['tx_count'].sum()
    
    curr_avg = curr_rev / curr_vis if curr_vis > 0 else 0
    prev_avg = prev_rev / prev_vis if prev_vis > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰總營業額", f"${curr_rev:,.0f}", f"{calculate_delta(curr_rev, prev_rev):.1%}" if prev_rev else None)
    c2.metric("🍜來客數 (主食數)", f"{curr_vis:,.0f}", f"{calculate_delta(curr_vis, prev_vis):.1%}" if prev_vis else None)
    c3.metric("🧾訂單數", f"{curr_txs:,.0f}", f"{calculate_delta(curr_txs, prev_txs):.1%}" if prev_txs else None)
    c4.metric("👤平均客單價", f"${curr_avg:,.0f}", f"{calculate_delta(curr_avg, prev_avg):.1%}" if prev_avg else None)
    st.divider()

    # Charts
    ov_int = st.radio("圖表單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"], horizontal=True, key='ov_int_new')
    ov_freq = 'D'
    if ov_int == "週 (Weekly)": ov_freq = 'W-MON'
    elif ov_int == "4週 (Monthly)": ov_freq = 'M'

    col_L, col_R = st.columns([2, 1])
    with col_L:
        st.subheader("📈 營業額趨勢")
        if not df_rep.empty:
            if 'Order_Category' not in df_rep.columns:
                df_rep['Order_Category'] = '內用 (Dine-in)'
                
            # Stacked bars per category
            resampled = df_rep.groupby(['Order_Category', pd.Grouper(key='Date_Parsed', freq=ov_freq)])['total_amount'].sum().reset_index()
            # Total revenue line
            total_resampled = df_rep.groupby(pd.Grouper(key='Date_Parsed', freq=ov_freq))['total_amount'].sum().reset_index()
            
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
        if not df_rep.empty and 'Day_Type' in df_rep.columns:
            # Fix: Group by Date ONLY (strip time) to get Daily Sum
            df_rep['Date_Only'] = df_rep['Date_Parsed'].dt.date
            
            daily_rev = df_rep.groupby(['Date_Only', 'Day_Type'])['total_amount'].sum().reset_index()
            curr_type_avg = daily_rev.groupby('Day_Type')['total_amount'].mean()
            
            # Prev
            if not df_rep_prev.empty:
                df_rep_prev['Date_Only'] = df_rep_prev['Date_Parsed'].dt.date
                daily_rev_prev = df_rep_prev.groupby(['Date_Only', 'Day_Type'])['total_amount'].sum().reset_index()
                prev_type_avg = daily_rev_prev.groupby('Day_Type')['total_amount'].mean()
            else:
                prev_type_avg = pd.Series()

            for dtype in ['平日 (Weekday)', '假日 (Holiday)']:
                val = curr_type_avg.get(dtype, 0)
                pval = prev_type_avg.get(dtype, 0)
                st.metric(f"平均 {dtype}", f"${val:,.0f}", f"{calculate_delta(val, pval):.1%}" if pval else None)

    st.divider()
    
    st.divider()

    # --- Charts Section ---
    st.subheader("📊 營運圖表 (Charts)")
    
    if not df_rep.empty:
        # Data Preparation
        # Ensure Date_Only exists (it might be created in the block above, but safe to redo or check)
        if 'Date_Only' not in df_rep.columns:
            df_rep['Date_Only'] = df_rep['Date_Parsed'].dt.date
            
        # 1. Daily Revenue Breakdown (Lunch/Dinner)
        # Use Date_Only for grouping
        daily_period = df_rep.groupby(['Date_Only', 'Period'])['total_amount'].sum().reset_index()
        # Convert to datetime for Plotly
        daily_period['Date_Parsed'] = pd.to_datetime(daily_period['Date_Only'])
        daily_period.drop(columns=['Date_Only'], inplace=True)
        
        # Modify for bidirectional bar chart: Lunch extends downward (negative), Dinner upward
        def adjust_for_bidirectional(row):
            if row['Period'] == '中午 (Lunch)':
                return -row['total_amount']
            return row['total_amount']
            
        daily_period['plot_amount'] = daily_period.apply(adjust_for_bidirectional, axis=1)
        daily_period['abs_amount'] = daily_period['total_amount'] # For hover display
        
        # 2. Daily Visitor & Avg Check
        # Need to handle visitor count logic per day
        daily_stats = df_rep.groupby('Date_Only').agg({
            'total_amount': 'sum',
            'people_count': 'sum', # Pre-calculated from Data Marts
            'tx_count': 'sum'
        }).reset_index()
        # Convert to datetime IMMEDIATELY after groupby
        daily_stats['Date_Parsed'] = pd.to_datetime(daily_stats['Date_Only'])
        daily_stats.drop(columns=['Date_Only'], inplace=True)
        daily_stats.rename(columns={'people_count': 'final_visitors'}, inplace=True)
        
        # Calculate Avg Check
        daily_stats['avg_check'] = daily_stats['total_amount'] / daily_stats['final_visitors'].replace(0, 1)
        
        # 3. Order Category (Overall for Pie)
        if 'Order_Category' not in df_rep.columns:
            df_rep['Order_Category'] = '內用 (Dine-in)'
            
        cat_pie = df_rep.groupby('Order_Category')['total_amount'].sum().reset_index()

        # --- Visualizations ---
        
        c_chart1, c_chart2 = st.columns([2, 1])
        
        with c_chart1:
            # Bidirectional Bar: Lunch(-) / Dinner(+)
            # Sort so colors and legend map cleanly
            daily_period = daily_period.sort_values('Period', ascending=False)
            
            fig_bar = px.bar(
                daily_period, 
                x='Date_Parsed', 
                y='plot_amount', 
                color='Period', 
                title="每日營業額 (午餐向下 / 晚餐向上)",
                labels={'plot_amount': '金額', 'Date_Parsed': '日期', 'Period': '時段'},
                custom_data=['abs_amount'] # Pass absolute amount to hover
            )
            
            # Customize hover to show positive values regardless of direction
            fig_bar.update_traces(hovertemplate='時段: %{color}<br>日期: %{x}<br>金額: $%{customdata[0]:,.0f}')
            
            # Make Y-axis labels positive only
            fig_bar.update_layout(
                xaxis_title=None,
                yaxis=dict(tickformat="f"), 
                barmode='relative'
            )
            
            # Format tick labels to strip the minus sign using tickvals/ticktext if needed
            # A simpler way in Plotly is using tickformat string: 
            # Note: to hide negative sign in plotly ticks, we can just let it show for now and see, 
            # or fix it explicitly. Let's rely on hover for exact value.
            
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with c_chart2:
            # Pie Chart: Order Category
            fig_pie = px.pie(
                cat_pie, 
                values='total_amount', 
                names='Order_Category', 
                title="營收佔比 (期間加總)",
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
        # Row 2: Line Chart (Visitors & Avg Check) - Dual Axis
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Line 1: Visitors
        fig_dual.add_trace(
            go.Scatter(x=daily_stats['Date_Parsed'], y=daily_stats['final_visitors'], name="整日來客數", mode='lines+markers'),
            secondary_y=False
        )
        
        # Line 2: Avg Check
        fig_dual.add_trace(
            go.Scatter(x=daily_stats['Date_Parsed'], y=daily_stats['avg_check'], name="客單價", mode='lines+markers', line=dict(dash='dot')),
            secondary_y=True
        )
        
        fig_dual.update_layout(
            title_text="每日來客數 & 客單價趨勢",
            xaxis_title="日期"
        )
        fig_dual.update_yaxes(title_text="來客數 (人)", secondary_y=False)
        fig_dual.update_yaxes(title_text="客單價 ($)", secondary_y=True)
        if st.toggle("📊 開啟：來客數與客單價雙軸走勢圖 (耗費運算資源)", value=False):
            st.plotly_chart(fig_dual, use_container_width=True)

    st.divider()
    
    # Table Report (Detailed Daily Data)
    st.subheader("📋 詳細營運數據 (Daily Metrics Table)")
    if not df_rep.empty:
        # Resample Base
        grouped = df_rep.set_index('Date_Parsed').resample(ov_freq)
        base_agg = grouped['total_amount'].sum().reset_index().rename(columns={'total_amount': '總營業額'})
        
        # 1. Lunch / Dinner
        if 'Period' in df_rep.columns:
            for p, col_name in [('中午 (Lunch)', '午餐營業額'), ('晚上 (Dinner)', '晚餐營業額')]:
                mask_p = df_rep['Period'] == p
                # Resample this period even if periods are missing on some days
                # Use pivot or just filter loop
                res = df_rep[mask_p].set_index('Date_Parsed').resample(ov_freq)['total_amount'].sum().reset_index()
                res.rename(columns={'total_amount': col_name}, inplace=True)
                base_agg = base_agg.merge(res, on='Date_Parsed', how='left').fillna(0)

        # 2. Order Category (Dine-in / Takeout / Delivery)
        # Assuming categories: '內用 (Dine-in)', '外帶 (Takeout)', '外送 (Delivery)'
        for cat, col_name in [('內用 (Dine-in)', '堂食營業額'), ('外帶 (Takeout)', '外帶營業額'), ('外送 (Delivery)', '外送營業額')]:
             mask_c = df_rep['Order_Category'] == cat
             res = df_rep[mask_c].set_index('Date_Parsed').resample(ov_freq)['total_amount'].sum().reset_index()
             res.rename(columns={'total_amount': col_name}, inplace=True)
             base_agg = base_agg.merge(res, on='Date_Parsed', how='left').fillna(0)
             
        base_agg = base_agg.merge(ds_resampled, on='Date_Parsed', how='left')
        base_agg.rename(columns={'final_visitors': '整日來客數'}, inplace=True)
        
        # Avg Check
        base_agg['客單價'] = base_agg['總營業額'] / base_agg['整日來客數'].replace(0, 1)

        # Display Formatting
        date_col = '日期'
        if ov_freq == 'D':
            base_agg[date_col] = base_agg['Date_Parsed'].dt.date.astype(str)
        else:
            base_agg[date_col] = base_agg['Date_Parsed'].dt.strftime('%Y-%m-%d (Start)')
            
        # Reorder Columns
        cols_order = [
            date_col, '中午營業額', '晚上營業額', '總營業額', 
            '整日來客數', '客單價', 
            '外送營業額', '外帶營業額', '堂食營業額'
        ]
        # Ensure all cols exist
        final_cols = [c for c in cols_order if c in base_agg.columns]
        
        # Rename for cleaner internal keys if needed, but we already renamed above.
        # Note: '中午營業額' was named '午餐營業額' above? Checking... yes '午餐營業額'.
        # User asked for "中午營業額". I should stick to user's terms.
        # Correction: I named them '午餐營業額' in line 228. I will rename to match user request.
        
        rename_map = {
            '午餐營業額': '中午營業額',
            '晚餐營業額': '晚上營業額'
        }
        base_agg.rename(columns=rename_map, inplace=True)
        
        final_cols = [c for c in cols_order if c in base_agg.columns]
        
        if st.toggle("📋 開啟：詳細每日營運數據報表 (Data Table)", value=False):
            st.dataframe(
                base_agg[final_cols].sort_values(date_col, ascending=False).style.format({
                    '中午營業額': "${:,.0f}", '晚上營業額': "${:,.0f}", '總營業額': "${:,.0f}",
                    '整日來客數': "{:,.0f}", '客單價': "${:,.0f}",
                    '外送營業額': "${:,.0f}", '外帶營業額': "${:,.0f}", '堂食營業額': "${:,.0f}"
                }), 
                use_container_width=False
            )
