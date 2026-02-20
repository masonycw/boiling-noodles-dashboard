import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np

def render_sales_view(df_details, start_date, end_date):
    st.title("🍟 商品銷售分析 (Product Sales)")

    if df_details.empty:
        st.info("尚未載入交易明細 (Transaction Details missing)")
        return

    # 1. Filter Data
    # Convert dates to match
    mask = (df_details['Date_Parsed'].dt.date >= start_date.date()) & (df_details['Date_Parsed'].dt.date <= end_date.date())
    df = df_details.loc[mask].copy()
    
    if df.empty:
        st.warning(f"此區間無銷售資料 ({start_date.date()} ~ {end_date.date()})")
        return

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
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        grouping = st.radio("圖表單位", ["天 (Daily)", "週 (Weekly)", "4週 (Monthly)"])
        freq = 'D'
        if grouping == "週 (Weekly)": freq = 'W-MON'
        elif grouping == "4週 (Monthly)": freq = 'M'
    
    with c2:
        top_n = st.number_input("顯示前 N 名商品走勢", min_value=1, max_value=20, value=5)

    with c3:
        # Multi-select for specific products
        all_items = df_real['item_name'].dropna().unique().tolist()
        selected_items = st.multiselect("特定商品篩選 (留空顯示全部)", options=all_items)
        if selected_items:
            df_real = df_real[df_real['item_name'].isin(selected_items)]

    st.divider()

    # 3. Overall Metrics
    total_qty = df_real['qty'].sum()
    total_sales = df_real['item_total'].sum()
    
    m1, m2 = st.columns(2)
    m1.metric("📦 總銷售數量 (Items)", f"{total_qty:,.0f}")
    m2.metric("💰 總銷售額 (Sales)", f"${total_sales:,.0f}")
    
    # 4. Top Products Ranking (Overall period)
    st.subheader("🏆 熱銷商品排行榜 (Top Items)")
    top_items = df_real.groupby('item_name').agg({'qty': 'sum', 'item_total': 'sum'}).reset_index()
    top_items = top_items.sort_values('qty', ascending=False)
    
    col_chart, col_pie = st.columns([2, 1])
    with col_chart:
        fig_bar = px.bar(top_items.head(15), x='qty', y='item_name', orientation='h', title="Top 15 熱銷數量", text='qty')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
    with col_pie:
        if 'category' in df_real.columns and df_real['category'].notna().any():
            cat_sales = df_real.groupby('category')['qty'].sum().reset_index()
            fig_pie = px.pie(cat_sales, values='qty', names='category', title="商品類別銷量佔比", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # 5. Time Series Trend
    st.subheader(f"📈 歷史走勢 ({grouping})")
    
    # Identify top N items to feature individually, group others
    if not selected_items:
        top_n_names = top_items.head(top_n)['item_name'].tolist()
        df_real['item_group'] = np.where(df_real['item_name'].isin(top_n_names), df_real['item_name'], '其他 (Others)')
    else:
        df_real['item_group'] = df_real['item_name']

    # Resample by date & item_group
    # Need to set Date_Parsed as datetime64 index for resample to work
    df_real['Date_Parsed'] = pd.to_datetime(df_real['Date_Parsed'])
    trend_df = df_real.set_index('Date_Parsed').groupby('item_group').resample(freq)['qty'].sum().reset_index()

    fig_line = px.line(trend_df, x='Date_Parsed', y='qty', color='item_group', markers=True, title="商品銷售趨勢")
    st.plotly_chart(fig_line, use_container_width=True)

    st.divider()

    # 6. Detailed Data Pivot Table
    st.subheader("📋 期間商品銷售矩陣 (Sales Matrix)")
    
    # Resample everything strictly to frequency to create columns
    df_pivot_prep = df_real.set_index('Date_Parsed').groupby(['item_name']).resample(freq)['qty'].sum().reset_index()
    
    if freq == 'D':
        df_pivot_prep['PeriodLabel'] = df_pivot_prep['Date_Parsed'].dt.strftime('%m-%d')
    else:
        df_pivot_prep['PeriodLabel'] = df_pivot_prep['Date_Parsed'].dt.strftime('%m-%d')
        
    pivot_table = pd.pivot_table(df_pivot_prep, values='qty', index='item_name', columns='PeriodLabel', fill_value=0)
    
    # Add Total Column
    pivot_table['Total'] = pivot_table.sum(axis=1)
    pivot_table = pivot_table.sort_values('Total', ascending=False)
    
    # Add Item Total Sales / Avg Price from overall period
    info = df_real.groupby('item_name').agg({'item_total': 'sum', 'unit_price': 'mean'}).rename(columns={'item_total': '總銷售額', 'unit_price': '平均單價'})
    pivot_table = pivot_table.join(info)

    # Reorder columns slightly to put Info at front, then date columns, then Total
    date_cols = [c for c in pivot_table.columns if c not in ['Total', '總銷售額', '平均單價']]
    final_cols = ['平均單價', '總銷售額'] + date_cols + ['Total']

    st.dataframe(
        pivot_table[final_cols].style.format({'平均單價': '${:,.0f}', '總銷售額': '${:,.0f}'}),
        use_container_width=True
    )
