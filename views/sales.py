import streamlit as st
import plotly.express as px
import pandas as pd

def render_sales_view(df_details, start_date, end_date):
    st.title("🍟 商品銷售分析 (Product Sales)")

    if df_details.empty:
        st.info("尚未載入交易明細 (Transaction Details missing)")
        return

    # 1. Date Filter (Local to View)
    # The user asked to move date filter to top. 
    # Since we are modularizing, let's allow this view to accept dates 
    # OR render its own if needed. For consistency with Operational View's request,
    # we might want to standardize.
    # But for now, let's assume dates are passed in or we act on the passed range.
    
    # Filter Data
    mask = (df_details['Date_Parsed'] >= start_date) & (df_details['Date_Parsed'] <= end_date)
    df = df_details.loc[mask].copy()
    
    if df.empty:
        st.warning(f"此區間無銷售資料 ({start_date.date()} ~ {end_date.date()})")
        return

    # 2. Key Metrics
    # Filter out modifiers for "Item Counts"
    if 'Is_Modifier' in df.columns:
        df_real = df[~df['Is_Modifier']].copy()
        df_mod = df[df['Is_Modifier']].copy()
    else:
        df_real = df
        df_mod = pd.DataFrame()

    total_qty = df_real['qty'].sum()
    total_sales = df['item_total'].sum() # Sales include modifiers (usually they create value?) or not?
    # Usually modifiers (like Extra Cheese) have price, so they contribute to Sales.
    # But User said "Taste adjustment notes are duplicate items" -> imply zero price notes?
    # If zero price, they don't affect sales.
    # If they are just "Less Ice", they explicitly don't should count as a "Sold Item".
    
    c1, c2 = st.columns(2)
    c1.metric("📦 總銷售數量 (Items)", f"{total_qty:,.0f}")
    c2.metric("💰 總銷售額 (Sales)", f"${total_sales:,.0f}")
    
    st.divider()

    # 3. Top Products Chart
    col_L, col_R = st.columns([2, 1])
    
    with col_L:
        st.subheader("🏆 熱銷商品排行榜 (Top Items)")
        # Group by Item Name
        if 'item_name' in df_real.columns:
            top_items = df_real.groupby('item_name')['qty'].sum().reset_index().sort_values('qty', ascending=False).head(20)
            fig = px.bar(top_items, x='qty', y='item_name', orientation='h', title="Top 20 熱銷商品", text='qty')
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
            
    with col_R:
        st.subheader("🥧 類別佔比")
        # If category exists
        if 'category' in df_real.columns:
            cat_sales = df_real.groupby('category')['item_total'].sum().reset_index()
            fig_pie = px.pie(cat_sales, values='item_total', names='category', title="銷售額佔比 (By Category)")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("尚無類別資料 (Category data missing)")

    st.divider()

    # 4. Detailed Table
    st.subheader("📋 銷售明細表")
    if 'item_name' in df.columns:
        # Pivot or Group
        # Show: Name, Qty, Sales, Avg Price
        item_stats = df_real.groupby('item_name').agg({
            'qty': 'sum',
            'item_total': 'sum',
            'unit_price': 'mean'
        }).reset_index()
        
        item_stats.rename(columns={
            'item_name': '商品名稱',
            'qty': '銷售數量',
            'item_total': '銷售總額',
            'unit_price': '平均單價'
        }, inplace=True)
        
        st.dataframe(
            item_stats.sort_values('銷售數量', ascending=False).style.format({
                '銷售總額': "${:,.0f}", 
                '平均單價': "${:,.0f}"
            }), 
            use_container_width=True
        )
