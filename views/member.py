import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

def render_member_search(df_report, df_details):
    st.title("👥 會員消費紀錄查詢")
    
    col_id = 'Member_ID'
    col_name = 'customer_name'
    col_phone = 'member_phone'
    col_carrier = 'carrier_id'
    
    if col_id not in df_report.columns:
        st.error("資料缺少 Member_ID 欄位 (請確認 Data Loader)")
        return

    # --- Search Interface ---
    st.subheader("🔍 搜尋會員")
    st.caption("輸入資料 (姓名 / 電話 / 載具號碼)")
    search_term = st.text_input("關鍵字 (Keyword)", "")
    
    if search_term:
        s_clean = search_term.strip()
        
        # Search Matrix
        mask = pd.Series(False, index=df_report.index)
        
        # Search in Name
        if col_name in df_report.columns:
            mask |= df_report[col_name].astype(str).str.contains(s_clean, na=False, case=False)
        # Search in Phone
        if col_phone in df_report.columns:
            mask |= df_report[col_phone].astype(str).str.contains(s_clean, na=False)
        # Search in Carrier
        if col_carrier in df_report.columns:
            mask |= df_report[col_carrier].astype(str).str.contains(s_clean, na=False, case=False)
        # Search in Member ID
        mask |= df_report[col_id].astype(str).str.contains(s_clean, na=False, case=False)
             
        results = df_report[mask].copy()
        
        if not results.empty:
            # Display Candidates
            # Create a label for selection
            def make_label(row):
                n = str(row.get(col_name, ''))
                p = str(row.get(col_phone, ''))
                c = str(row.get(col_carrier, ''))
                mid = str(row.get(col_id, ''))
                
                label = f"{n if n!='nan' else '-'} / {p if p!='nan' else '-'} / {c if c!='nan' else '-'}"
                return f"{label} (ID: {mid})"

            # Deduplicate by Member ID
            unique_members = results.drop_duplicates(subset=[col_id]).copy()
            unique_members['Label'] = unique_members.apply(make_label, axis=1)
            
            sel_label = st.selectbox(f"找到 {len(unique_members)} 位相關會員:", unique_members['Label'].tolist())
            
            # Retrieve Selected Member Data
            sel_mid_row = unique_members[unique_members['Label'] == sel_label].iloc[0]
            sel_mid = sel_mid_row[col_id]
            
            # Fetch all records for this Member ID
            mem_records = df_report[df_report[col_id] == sel_mid].copy()
            mem_records = mem_records.sort_values('Date_Parsed', ascending=False)
            
            # --- Personal Dashboard ---
            st.divider()
            st.subheader(f"👤 會員檔案: {sel_label}")
            
            # Metrics
            total_spend = mem_records['total_amount'].sum()
            visits = mem_records['Date_Parsed'].dt.date.nunique()
            first_visit = mem_records['Date_Parsed'].min().date()
            last_visit = mem_records['Date_Parsed'].max().date()
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("總消費", f"${total_spend:,.0f}")
            c2.metric("來店次數", f"{visits} 次")
            c3.metric("初次來店", str(first_visit))
            c4.metric("最近來店", str(last_visit))
            
            # Purchase History
            st.subheader("🧾 消費歷程")
            hist_df = mem_records[['Date_Parsed', 'order_id', 'total_amount', 'order_type', 'customer_name']].copy()
            st.dataframe(hist_df.style.format({'total_amount': '${:,.0f}', 'Date_Parsed': '{:%Y-%m-%d %H:%M}'}), use_container_width=True)
            
            # Favorite Items (if details available)
            if not df_details.empty:
                # Need to link details via order_id
                mem_orders = mem_records['order_id'].unique()
                mem_details = df_details[df_details['order_id'].isin(mem_orders)].copy()
                
                if not mem_details.empty:
                    st.subheader("❤️ 喜好商品")
                    # Filter modifiers
                    if 'Is_Modifier' in mem_details.columns:
                        mem_details = mem_details[~mem_details['Is_Modifier']]
                        
                    fav_items = mem_details.groupby('item_name')['qty'].sum().reset_index().sort_values('qty', ascending=False).head(5)
                    st.bar_chart(fav_items.set_index('item_name'))
            
        else:
            st.warning("查無資料")

def render_crm_analysis(df_report):
    st.title("🆕 新舊客分析 (New vs Returning)")
    
    with st.expander("ℹ️ 新客與舊客定義說明"):
        st.markdown("""
        * **新客 (New)**：在您選擇的區間內，該會員發生了「歷史以來的第 1 次」消費。
        * **舊客 (Returning)**：在您選擇的區間內有消費，但他的「歷史第 1 次」消費發生在這個區間之前。
        * *(本分析只會將這段時間有買過東西的活躍會員進行拆解。)*
        """)
    
    col_id = 'Member_ID'
    if col_id not in df_report.columns:
        st.error("缺少 Member_ID，無法進行分析")
        return
        
    # Valid Members only
    df = df_report.dropna(subset=[col_id]).copy()
    
    st.divider()
    st.subheader("🗓️ CRM 分析區間")
    from .utils import render_date_filter
    s_date, e_date = render_date_filter("crm")
    
    start_ts = pd.Timestamp(s_date)
    end_ts = pd.Timestamp(e_date) + timedelta(days=1) - timedelta(seconds=1) # End of day
    
    # 1. Identify "New Customers" in this period
    # Algorithm:
    # A customer is "New" if their FIRST visit ever is within [start_ts, end_ts].
    # A customer is "Returning" if they visited in [start_ts, end_ts] AND their first visit was BEFORE start_ts.
    
    # Calculate First Visit for ALL members
    member_first_visit = df.groupby(col_id)['Date_Parsed'].min().reset_index()
    member_first_visit.columns = [col_id, 'First_Visit_Date']
    
    # Filter transactions within period
    period_txs = df[(df['Date_Parsed'] >= start_ts) & (df['Date_Parsed'] <= end_ts)].copy()
    
    if period_txs.empty:
        st.warning("此區間無交易資料")
        return
        
    # Get active members in period
    active_mids = period_txs[col_id].unique()
    
    # Join with First Visit
    active_status = member_first_visit[member_first_visit[col_id].isin(active_mids)].copy()
    
    # Determine Type
    active_status['User_Type'] = active_status['First_Visit_Date'].apply(
        lambda x: '新客 (New)' if x >= start_ts else '舊客 (Returning)'
    )
    
    # Stats
    type_counts = active_status['User_Type'].value_counts()
    
    # Merge back to transactions for revenue
    period_txs = period_txs.merge(active_status[[col_id, 'User_Type']], on=col_id, how='left')
    
    rev_by_type = period_txs.groupby('User_Type').agg(
        Total_Revenue=('total_amount', 'sum'),
        Tx_Count=('order_id', 'nunique')
    ).reset_index()
    
    # Metrics Strip
    total_active = len(active_status)
    new_active = type_counts.get('新客 (New)', 0)
    ret_active = type_counts.get('舊客 (Returning)', 0)
    
    new_rev = rev_by_type.loc[rev_by_type['User_Type'] == '新客 (New)', 'Total_Revenue'].sum()
    ret_rev = rev_by_type.loc[rev_by_type['User_Type'] == '舊客 (Returning)', 'Total_Revenue'].sum()
    
    new_txs = rev_by_type.loc[rev_by_type['User_Type'] == '新客 (New)', 'Tx_Count'].sum()
    ret_txs = rev_by_type.loc[rev_by_type['User_Type'] == '舊客 (Returning)', 'Tx_Count'].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👥 總活躍會員", f"{total_active:,.0f} 人")
    m2.metric("🆕 新會員數", f"{new_active:,.0f} 人", f"{new_active/total_active:.1%}" if total_active else "0%")
    m3.metric("💸 新客營收貢獻", f"${new_rev:,.0f}", f"{new_rev/(new_rev+ret_rev):.1%}" if (new_rev+ret_rev) else "0%")
    m4.metric("💰 舊客營收貢獻", f"${ret_rev:,.0f}", f"{ret_rev/(new_rev+ret_rev):.1%}" if (new_rev+ret_rev) else "0%")
    
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👥 客群人數分佈")
        fig = px.pie(values=type_counts.values, names=type_counts.index, title="期間來訪人數佔比", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("💳 平均客單價 (Avg Check by Type)")
        avg_df = pd.DataFrame([
            {'User_Type': '新客 (New)', 'Avg_Spend': new_rev / new_txs if new_txs else 0},
            {'User_Type': '舊客 (Returning)', 'Avg_Spend': ret_rev / ret_txs if ret_txs else 0}
        ])
        fig2 = px.bar(avg_df, x='User_Type', y='Avg_Spend', title="平均客單價比較", text_auto='.0f', color='User_Type')
        st.plotly_chart(fig2, use_container_width=True)
        
    st.divider()
    
    # Time Series: New vs Returning over time
    st.subheader("📈 新舊客每日來店趨勢")
    
    period_txs['Date_Only'] = period_txs['Date_Parsed'].dt.date
    daily_type = period_txs.groupby(['Date_Only', 'User_Type'])['order_id'].nunique().reset_index()
    daily_type.rename(columns={'order_id': 'Visits'}, inplace=True)
    
    fig_time = px.bar(daily_type, x='Date_Only', y='Visits', color='User_Type', title="每日客群來訪數 (交易筆數)", barmode='stack')
    st.plotly_chart(fig_time, use_container_width=True)

    st.divider()
    
    # Retention / Frequency
    st.subheader("📊 期間回訪頻率 (Period Frequency)")
    freq = period_txs.groupby(col_id)['order_id'].count().reset_index()
    freq['Frequency'] = pd.cut(freq['order_id'], bins=[0, 1, 2, 5, 100], labels=['1次', '2次', '3-5次', '6次+'])
    
    # Split frequency by User Type to see if new users ever come back twice in the same period
    freq = freq.merge(active_status[[col_id, 'User_Type']], on=col_id, how='left')
    freq_summary = freq.groupby(['User_Type', 'Frequency']).size().reset_index(name='Count')
    
    fig_freq = px.bar(freq_summary, x='Frequency', y='Count', color='User_Type', barmode='group', title="期間內消費次數分佈")
    st.plotly_chart(fig_freq, use_container_width=True)

    st.divider()
    
    # RFM Analysis
    st.subheader("🎯 RFM 會員價值分析 (全歷史資料)")
    st.caption("基於系統內截至目前的歷史交易資料，計算活躍會員的 R (最近一次消費)、F (消費頻率)、M (累積消費總額)。")
    
    # RFM uses data up to end_ts
    historical_txs = df[df['Date_Parsed'] <= end_ts].copy()
    
    if not historical_txs.empty:
        # Calculate R, F, M
        last_date = historical_txs['Date_Parsed'].max()
        rfm = historical_txs.groupby(col_id).agg(
            Last_Purchase=('Date_Parsed', 'max'),
            Frequency=('order_id', 'nunique'),
            Monetary=('total_amount', 'sum')
        ).reset_index()
        
        # Calculate Recency in days
        rfm['Recency'] = (last_date - rfm['Last_Purchase']).dt.days
        
        # Simple Segmentation based on Frequency & Recency
        def segment_rfm(row):
            if row['Frequency'] >= 5 and row['Recency'] <= 30:
                return "🌟 VVIP (高頻活躍)"
            elif row['Frequency'] >= 2 and row['Recency'] <= 60:
                return "⭐ 忠誠客 (穩定回訪)"
            elif row['Frequency'] == 1 and row['Recency'] <= 30:
                return "👋 近期新客"
            elif row['Frequency'] >= 2 and row['Recency'] > 60:
                return "💤 沉睡客 (曾回訪但很久沒來)"
            else:
                return "📉 流失單次客 (只來一次且很久沒來)"
                
        rfm['Segment'] = rfm.apply(segment_rfm, axis=1)
        
        seg_counts = rfm['Segment'].value_counts().reset_index()
        seg_counts.columns = ['會員價值分群', '人數']
        
        # Avg M per segment
        seg_m = rfm.groupby('Segment')['Monetary'].mean().reset_index()
        seg_counts = seg_counts.merge(seg_m, left_on='會員價值分群', right_on='Segment')
        
        col_rfm1, col_rfm2 = st.columns([1, 1])
        with col_rfm1:
            fig_rfm = px.pie(seg_counts, names='會員價值分群', values='人數', title=" RFM 會員分群佔比", hole=0.3)
            st.plotly_chart(fig_rfm, use_container_width=True)
            
        with col_rfm2:
            fig_rfm2 = px.bar(seg_counts, x='會員價值分群', y='Monetary', title="各群體平均終身貢獻 (LTV)", text_auto='.0f')
            st.plotly_chart(fig_rfm2, use_container_width=True)
