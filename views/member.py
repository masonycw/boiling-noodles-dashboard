import streamlit as st
import pandas as pd
import plotly.express as px

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
    
    col_id = 'Member_ID'
    if col_id not in df_report.columns:
        st.error("缺少 Member_ID，無法進行分析")
        return
        
    # Valid Members only
    df = df_report.dropna(subset=[col_id]).copy()
    
    # Date Filter for Analysis Period
    st.sidebar.markdown("---")
    st.sidebar.subheader("CRM 分析區間")
    start_date = st.sidebar.date_input("開始日期", pd.Timestamp.now().date() - timedelta(days=30))
    end_date = st.sidebar.date_input("結束日期", pd.Timestamp.now().date())
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date) + timedelta(days=1) - timedelta(seconds=1) # End of day
    
    # 1. Identify "New Customers" in this period
    # Algorithm:
    # A customer is "New" if their FIRST visit ever is within [start, end].
    # A customer is "Returning" if they visited in [start, end] AND their first visit was BEFORE start.
    
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
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👥 客群分佈")
        fig = px.pie(values=type_counts.values, names=type_counts.index, title="新舊客佔比", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("💰 營收貢獻")
        # Sum revenue by type
        # Merge back to transactions
        period_txs = period_txs.merge(active_status[[col_id, 'User_Type']], on=col_id, how='left')
        rev_by_type = period_txs.groupby('User_Type')['total_amount'].sum().reset_index()
        fig2 = px.bar(rev_by_type, x='User_Type', y='total_amount', title="新舊客營收貢獻", text='total_amount')
        st.plotly_chart(fig2, use_container_width=True)
        
    st.divider()
    
    # Retention / Frequency
    st.subheader("📊 期間回訪頻率 (Period Frequency)")
    freq = period_txs.groupby(col_id)['order_id'].count().reset_index()
    freq['Frequency'] = pd.cut(freq['order_id'], bins=[0, 1, 2, 5, 100], labels=['1次', '2次', '3-5次', '6次+'])
    freq_counts = freq['Frequency'].value_counts().sort_index()
    st.bar_chart(freq_counts)
