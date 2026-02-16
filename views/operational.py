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

    st.title("📊 營運總覽 (Operational Overview)")
    
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
            daily_rev = df_rep.groupby(['Date_Parsed', 'Day_Type'])['total_amount'].sum().reset_index()
            curr_type_avg = daily_rev.groupby('Day_Type')['total_amount'].mean()
            
            # Prev
            if not df_rep_prev.empty:
                daily_rev_prev = df_rep_prev.groupby(['Date_Parsed', 'Day_Type'])['total_amount'].sum().reset_index()
                prev_type_avg = daily_rev_prev.groupby('Day_Type')['total_amount'].mean()
            else:
                prev_type_avg = pd.Series()

            for dtype in ['平日 (Weekday)', '假日 (Holiday)']:
                val = curr_type_avg.get(dtype, 0)
                pval = prev_type_avg.get(dtype, 0)
                st.metric(f"平均 {dtype}", f"${val:,.0f}", f"{calculate_delta(val, pval):.1%}" if pval else None)

    st.divider()
    
    # Detailed Metrics Section
    st.subheader("🔢 詳細營運數據 (Detailed Breakdown)")
    
    # Calculate detailed metrics
    rev_lunch = df_rep[df_rep['Period'] == '中午 (Lunch)']['total_amount'].sum() if 'Period' in df_rep.columns else 0
    rev_dinner = df_rep[df_rep['Period'] == '晚上 (Dinner)']['total_amount'].sum() if 'Period' in df_rep.columns else 0
    
    # Order Category Logic (Ensure column exists)
    if 'Order_Category' not in df_rep.columns:
        df_rep['Order_Category'] = '內用 (Dine-in)' # Fallback if not enriched yet
        
    rev_dine_in = df_rep[df_rep['Order_Category'] == '內用 (Dine-in)']['total_amount'].sum()
    rev_takeout = df_rep[df_rep['Order_Category'] == '外帶 (Takeout)']['total_amount'].sum()
    rev_delivery = df_rep[df_rep['Order_Category'] == '外送 (Delivery)']['total_amount'].sum()

    dm1, dm2, dm3, dm4 = st.columns(4)
    dm1.metric("🌞 中午營業額", f"${rev_lunch:,.0f}")
    dm2.metric("🌙 晚上營業額", f"${rev_dinner:,.0f}")
    dm3.metric("🍽️ 堂食營業額", f"${rev_dine_in:,.0f}")
    dm4.metric("🥡 外帶營業額", f"${rev_takeout:,.0f}")
    
    dm5, dm6, dm7, dm8 = st.columns(4)
    dm5.metric("🛵 外送營業額", f"${rev_delivery:,.0f}")
    dm6.metric("👥 整日來客數", f"{curr_vis:,.0f}")
    dm7.metric("💰 客單價", f"${curr_avg:,.0f}")
    
    st.divider()
    
    # Table Report
    st.subheader("📋 營運報表")
    if not df_rep.empty:
        grouped = df_rep.set_index('Date_Parsed').resample(ov_freq)
        base_agg = grouped['total_amount'].sum().reset_index().rename(columns={'total_amount': '總營業額'})
        
        # Period Breakdown
        if 'Period' in df_rep.columns:
            p_groups = []
            for p in ['中午 (Lunch)', '晚上 (Dinner)']:
                mask_p = df_rep['Period'] == p
                if mask_p.any():
                    res = df_rep[mask_p].set_index('Date_Parsed').resample(ov_freq)['total_amount'].sum()
                    res.name = p
                    p_groups.append(res)
            if p_groups: 
                period_rev = pd.concat(p_groups, axis=1).fillna(0).reset_index()
                base_agg = base_agg.merge(period_rev, on='Date_Parsed', how='left')
        
        # Display
        date_col = 'Date_Label'
        if ov_freq == 'D':
            base_agg[date_col] = base_agg['Date_Parsed'].dt.date.astype(str)
        else:
            base_agg[date_col] = base_agg['Date_Parsed'].dt.strftime('%Y-%m-%d (Start)')
            
        base_agg.rename(columns={'中午 (Lunch)': '午餐', '晚上 (Dinner)': '晚餐'}, inplace=True)
        st.dataframe(base_agg.sort_values(date_col, ascending=False).style.format("${:,.0f}", subset=['總營業額']), use_container_width=True)
