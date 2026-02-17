import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
from .utils import calculate_delta

def render_operational_view(df_report, df_details, start_date=None, end_date=None):
    # If dates passed from global, use them as defaults? 
    # User said: "Left side date filter, only for operational overview, move it to top"
    # So we ignore passed defaults for interactive control here? 
    # Let's Implement Local Control.

    st.title("📊 營運總覽 v2.3.1 (Datetime Fix)")
    
    # --- Local Date Filter ---
    # Default to This Month if not passed
    if start_date is None:
        today = pd.Timestamp.now().date()
        start_date = pd.Timestamp(today.replace(day=1))
        end_date = pd.Timestamp(today)
    
    c_d1, c_d2 = st.columns([1, 3])
    with c_d1:
        date_range = st.date_input("選擇日期區間", [start_date, end_date])
        if len(date_range) > 0: start_date = pd.to_datetime(date_range[0])
        if len(date_range) > 1: end_date = pd.to_datetime(date_range[1])
        else: end_date = start_date
        
    st.divider()

    # Filter Data
    mask_rep = (df_report['Date_Parsed'] >= start_date) & (df_report['Date_Parsed'] <= end_date)
    df_rep = df_report.loc[mask_rep].copy()
    
    # Previous Period
    duration = end_date - start_date
    prev_end = start_date - pd.Timedelta(days=1)
    prev_start = prev_end - duration
    mask_rep_prev = (df_report['Date_Parsed'] >= prev_start) & (df_report['Date_Parsed'] <= prev_end)
    df_rep_prev = df_report.loc[mask_rep_prev].copy()

    # Metrics
    curr_rev = df_rep['total_amount'].sum()
    prev_rev = df_rep_prev['total_amount'].sum()
    
    # Visitors/Details (If available)
    # Priority 1: Visitor Count from Item Details (Main Dishes)
    # Priority 2: Visitor Count from Report (People Count)
    # Priority 3: Quantity from Details
    # Priority 4: Transaction Count
    
    has_details = not df_details.empty
    
    # Current Period Visitors
    curr_vis = 0
    if has_details and 'Is_Main_Dish' in df_details.columns:
        mask_det = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
        df_det = df_details.loc[mask_det]
        # Method 1
        curr_vis = df_det[df_det['Is_Main_Dish']]['qty'].sum()
        
    if curr_vis == 0 and 'people_count' in df_rep.columns:
        # Method 2
        curr_vis = df_rep['people_count'].sum()
        
    if curr_vis == 0 and has_details:
        # Method 3
        curr_vis = df_det['qty'].sum()
        
    # Previous Period Visitors
    prev_vis = 0
    if has_details and 'Is_Main_Dish' in df_details.columns:
        mask_det_prev = (df_details['Date_Parsed'] >= prev_start) & (df_details['Date_Parsed'] <= prev_end)
        df_det_prev = df_details.loc[mask_det_prev]
        prev_vis = df_det_prev[df_det_prev['Is_Main_Dish']]['qty'].sum()
        
    if prev_vis == 0 and 'people_count' in df_rep_prev.columns:
        prev_vis = df_rep_prev['people_count'].sum()
        
    if prev_vis == 0 and has_details:
        prev_vis = df_det_prev['qty'].sum()

    curr_txs = len(df_rep)
    prev_txs = len(df_rep_prev)
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
            resampled = df_rep.set_index('Date_Parsed').resample(ov_freq)['total_amount'].sum().reset_index()
            fig = px.bar(resampled, x='Date_Parsed', y='total_amount', title=f"營業額 ({ov_int})")
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
        
        # 2. Daily Visitor & Avg Check
        # Need to handle visitor count logic per day
        daily_stats = df_rep.groupby('Date_Only').agg({
            'total_amount': 'sum',
            'people_count': 'sum', # Default report count
            'order_id': 'count'
        }).reset_index()
        # Convert to datetime IMMEDIATELY after groupby
        daily_stats['Date_Parsed'] = pd.to_datetime(daily_stats['Date_Only'])
        daily_stats.drop(columns=['Date_Only'], inplace=True)
        
        # If details exist, try to improve visitor count accuracy per day
        if has_details and 'Is_Main_Dish' in df_details.columns:
            # Create Date_Only for details too
            df_details['Date_Only'] = df_details['Date_Parsed'].dt.date
            
            daily_vis_det = df_details[df_details['Is_Main_Dish']].groupby('Date_Only')['qty'].sum().reset_index()
            # Convert to datetime BEFORE merge
            daily_vis_det['Date_Parsed'] = pd.to_datetime(daily_vis_det['Date_Only'])
            daily_vis_det.drop(columns=['Date_Only'], inplace=True)
            daily_vis_det.rename(columns={'qty': 'det_qty'}, inplace=True)
            
            # Merge (both are now datetime64[ns])
            daily_stats = daily_stats.merge(daily_vis_det, on='Date_Parsed', how='left')
            daily_stats['det_qty'] = daily_stats['det_qty'].fillna(0)
            
            # Logic: Use detailsqty, if 0 fallback to people_count
            daily_stats['final_visitors'] = np.where(daily_stats['det_qty'] > 0, daily_stats['det_qty'], daily_stats['people_count'])
        else:
             daily_stats['final_visitors'] = daily_stats['people_count']
             
        # Calculate Avg Check
        daily_stats['avg_check'] = daily_stats['total_amount'] / daily_stats['final_visitors'].replace(0, 1)
        
        # 3. Order Category (Overall for Pie)
        if 'Order_Category' not in df_rep.columns:
            df_rep['Order_Category'] = '內用 (Dine-in)'
            
        cat_pie = df_rep.groupby('Order_Category')['total_amount'].sum().reset_index()

        # --- Visualizations ---
        
        c_chart1, c_chart2 = st.columns([2, 1])
        
        with c_chart1:
            # Stacked Bar: Lunch/Dinner
            fig_bar = px.bar(
                daily_period, 
                x='Date_Parsed', 
                y='total_amount', 
                color='Period', 
                title="每日營業額 (午餐/晚餐)",
                labels={'total_amount': '金額', 'Date_Parsed': '日期', 'Period': '時段'},
                # text_auto='.2s' # Too cluttered for daily?
            )
            fig_bar.update_layout(xaxis_title=None)
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
             
        # 3. Visitor & Avg Check (From daily_stats logic above if ov_freq is Daily, else re-agg)
        # Note: ov_freq might be Weekly/Monthly. 
        # If freq != 'D', we need to sum visitors.
        # Let's reuse 'people_count' col from report as base, add details logic if possible?
        # Aggregating complex visitor logic over weeks is tricky.
        # Fallback: Sum 'people_count' for now to be safe and consistent with previous logic?
        # Or re-implement the strict Main Dish logic for the whole resample bin?
        
        # Re-calc visitors for the BIN (Day/Week/Month)
        # Efficient way: Filter details by date bin.
        # But we simply need to sum 'people_count' (Report) OR 'qty' (Details Main Dish)
        
        # Create a helper df with Date, Rev, Visitor
        # We can just sum the calculated daily_stats if ov_freq is 'D'
        # If ov_freq is W/M, we need to resample daily_stats.
        
        # Let's use daily_stats from above (it is Daily).
        ds_indexed = daily_stats.set_index('Date_Parsed')
        ds_resampled = ds_indexed.resample(ov_freq).agg({
            'final_visitors': 'sum'
        }).reset_index()
        
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
        
        st.dataframe(
            base_agg[final_cols].sort_values(date_col, ascending=False).style.format({
                '中午營業額': "${:,.0f}", '晚上營業額': "${:,.0f}", '總營業額': "${:,.0f}",
                '整日來客數': "{:,.0f}", '客單價': "${:,.0f}",
                '外送營業額': "${:,.0f}", '外帶營業額': "${:,.0f}", '堂食營業額': "${:,.0f}"
            }), 
            use_container_width=True
        )
