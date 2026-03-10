import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
import db_queries

def render_sales_view(start_date, end_date):
    st.title("🍟 商品銷售分析 (Product Sales)")

    df_details = db_queries.fetch_sales_details(start_date, end_date)
    
    if df_details.empty:
        st.warning(f"此區間無銷售資料 ({start_date.date()} ~ {end_date.date()})")
        return

    # 1. Filter Data
    df = df_details.copy()
    
    # Filter out modifiers for "Item Counts"

    if 'Is_Modifier' in df.columns:
        df_real = df[~df['Is_Modifier']].copy()
    else:
        df_real = df.copy()

    if df_real.empty:
        st.warning(f"此區間無主商品銷售資料 (只有配料/備註)")
        return

    # Base date column for grouping
    df_real['Date_Only'] = df_real['Date_Parsed'].dt.date

    # 2. Controls
    c1, c2 = st.columns([1, 2])
    with c1:
        grouping = st.radio("圖表單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"])
        freq = 'D'
        if grouping == "週 (Weekly)": freq = 'W-MON'
        elif grouping == "4週 (Monthly)": freq = 'M'
    
    with c2:
        # Category Select
        categories = []
        if 'category' in df_real.columns:
            categories = df_real['category'].dropna().unique().tolist()
        selected_cats = st.multiselect("選擇比較的商品類別 (Category)", options=categories)
        
        # Multi-select for specific products
        if selected_cats:
            available_items = df_real[df_real['category'].isin(selected_cats)]['item_name'].dropna().unique().tolist()
        else:
            available_items = df_real['item_name'].dropna().unique().tolist()
        selected_items = st.multiselect("特定商品篩選 (留空顯示該類別全部)", options=available_items)

    # Filter by category and items
    if selected_cats:
        df_real = df_real[df_real['category'].isin(selected_cats)]
    if selected_items:
        df_real = df_real[df_real['item_name'].isin(selected_items)]

    if df_real.empty:
        st.warning("篩選後無銷售資料")
        return

    st.divider()

    # 3. Overall Metrics (now reflects filtered items)
    total_qty = df_real['qty'].sum()
    total_sales = df_real['item_total'].sum()
    
    m1, m2 = st.columns(2)
    m1.metric("📦 總銷售數量 (Items)", f"{total_qty:,.0f}")
    m2.metric("💰 總銷售額 (Sales)", f"${total_sales:,.0f}")

    st.divider()

    # 4. Time Series Trend
    st.subheader(f"📈 歷史走勢 ({grouping})")
    
    # Resample by date & item_name
    df_real['Date_Parsed'] = pd.to_datetime(df_real['Date_Parsed'])
    trend_df = df_real.set_index('Date_Parsed').groupby('item_name').resample(freq)['qty'].sum().reset_index()

    fig_line = px.line(trend_df, x='Date_Parsed', y='qty', color='item_name', markers=True, title="商品銷售趨勢")
    st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    # 5. Detailed Data Pivot Table
    st.subheader("📋 期間商品銷售矩陣 (Sales Matrix)")
    
    # Resample everything strictly to frequency to create columns
    # Include 'category' and 'sku' in the grouping to keep it after resampling
    df_pivot_prep = df_real.set_index('Date_Parsed').groupby(['category', 'sku', 'item_name']).resample(freq)['qty'].sum().reset_index()
    
    if freq == 'D':
        df_pivot_prep['PeriodLabel'] = df_pivot_prep['Date_Parsed'].dt.strftime('%m-%d')
    else:
        df_pivot_prep['PeriodLabel'] = df_pivot_prep['Date_Parsed'].dt.strftime('%m-%d')
        
    pivot_table = pd.pivot_table(df_pivot_prep, values='qty', index=['category', 'sku', 'item_name'], columns='PeriodLabel', fill_value=0)
    
    # Add Total Column
    pivot_table['Total'] = pivot_table.sum(axis=1)
    
    # Sort first by SKU (alphanumeric ascending), then by Total descending if SKUs duplicate
    pivot_table = pivot_table.sort_values(by=['sku', 'Total'], ascending=[True, False]).reset_index()
    pivot_table = pivot_table.set_index('item_name') # Remove default range index
    
    # Fix unit_price KeyError by recalculating from totals
    info = df_real.groupby('item_name').agg(
        總銷售額=('item_total', 'sum'),
        QTY=('qty', 'sum')
    )
    info['平均單價'] = (info['總銷售額'] / info['QTY'].replace(0, 1)).round(0)
    info = info.drop(columns=['QTY'])
    
    pivot_table = pivot_table.join(info)

    # Clean up display columns
    pivot_table = pivot_table.rename(columns={'category': '商品類別', 'sku': 'SKU'})

    # Reorder columns slightly to put Category, SKU, Info at front, then date columns, then Total
    date_cols = [c for c in pivot_table.columns if c not in ['Total', '總銷售額', '平均單價', '商品類別', 'SKU']]
    final_cols = ['商品類別', 'SKU', '平均單價', '總銷售額'] + date_cols + ['Total']

    # Set up column formatting mapping
    format_mapping = {'平均單價': '${:,.0f}', '總銷售額': '${:,.0f}'}
    for c in date_cols + ['Total']:
        format_mapping[c] = '{:,.0f}'

    st.dataframe(
        pivot_table[final_cols].style.format(format_mapping),
        use_container_width=True
    )
