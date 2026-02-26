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

def render_crm_analysis(df_report, df_details):
    st.title("🆕 新舊客分析 (New vs Returning)")
    
    with st.expander("ℹ️ 新舊客與非會員定義說明"):
        st.markdown("""
        * **新客 (New)**：在您選擇的區間內，該會員發生了「歷史以來的第 1 次」消費。
        * **舊客 (Returning)**：在您選擇的區間內有消費，但他的「歷史第 1 次」消費發生在這個區間之前。
        * **非會員 (Non-member)**：本次交易未綁定會員電話或載具。
        """)
    
    col_id = 'Member_ID'
    if col_id not in df_report.columns:
        df_report[col_id] = None
        
    df = df_report.copy()
    # Treat NaN as non-member
    df[col_id] = df[col_id].fillna('非會員')
    
    st.divider()
    st.subheader("🗓️ CRM 分析區間")
    from .utils import render_date_filter
    s_date, e_date = render_date_filter("crm")
    
    start_ts = pd.Timestamp(s_date)
    end_ts = pd.Timestamp(e_date)
    
    period_txs = df[(df['Date_Parsed'] >= start_ts) & (df['Date_Parsed'] <= end_ts)].copy()
    
    if period_txs.empty:
        st.warning("此區間無交易資料")
        return
        
    # Process Members
    member_mask = df[col_id] != '非會員'
    df_members = df[member_mask]
    
    # Calculate First Visit for ALL valid members
    member_first_visit = df_members.groupby(col_id)['Date_Parsed'].min().reset_index()
    member_first_visit.columns = [col_id, 'First_Visit_Date']
    
    # Map back to period transactions to determine type
    period_txs = period_txs.merge(member_first_visit, on=col_id, how='left')
    
    period_txs['Date_Only'] = period_txs['Date_Parsed'].dt.date
    
    def determine_type(row):
        if row[col_id] == '非會員':
            return '非會員 (Non-member)'
        if pd.isna(row['First_Visit_Date']):
            # Should not happen given we only merge members that exist, but failsafe
            return '非會員 (Non-member)'
        if row['First_Visit_Date'] >= start_ts:
            return '新客 (New)'
        return '舊客 (Returning)'
        
    period_txs['User_Type'] = period_txs.apply(determine_type, axis=1)
    
    # Create Visit_ID to deduplicate same-day member visits
    def get_visit_id(row):
        if row['User_Type'] == '非會員 (Non-member)':
            return str(row['order_id'])
        else:
            return f"{row[col_id]}_{row['Date_Only']}"
            
    period_txs['Visit_ID'] = period_txs.apply(get_visit_id, axis=1)
    
    # Stats
    type_counts = period_txs.groupby('User_Type')['Visit_ID'].nunique()
    
    rev_by_type = period_txs.groupby('User_Type').agg(
        Total_Revenue=('total_amount', 'sum'),
        Tx_Count=('Visit_ID', 'nunique')
    ).reset_index()
    
    # Map safely
    def get_stat(df, c, v):
        res = df.loc[df['User_Type'] == c, v]
        return res.values[0] if not res.empty else 0
        
    new_rev = get_stat(rev_by_type, '新客 (New)', 'Total_Revenue')
    ret_rev = get_stat(rev_by_type, '舊客 (Returning)', 'Total_Revenue')
    non_rev = get_stat(rev_by_type, '非會員 (Non-member)', 'Total_Revenue')
    
    new_txs = get_stat(rev_by_type, '新客 (New)', 'Tx_Count')
    ret_txs = get_stat(rev_by_type, '舊客 (Returning)', 'Tx_Count')
    non_txs = get_stat(rev_by_type, '非會員 (Non-member)', 'Tx_Count')
    
    total_rev = period_txs['total_amount'].sum()
    total_txs = period_txs['Visit_ID'].nunique()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👥 總來店客組 (Visit_ID)", f"{total_txs:,.0f} 組")
    m2.metric("🆕 新客營收佔比", f"${new_rev:,.0f}", f"{new_rev/total_rev:.1%}" if total_rev else "0%")
    m3.metric("🤝 舊客營收佔比", f"${ret_rev:,.0f}", f"{ret_rev/total_rev:.1%}" if total_rev else "0%")
    m4.metric("❓ 非會員營收佔比", f"${non_rev:,.0f}", f"{non_rev/total_rev:.1%}" if total_rev else "0%")
    
    total_active = new_txs + ret_txs # Approximation or actual if 1 tx per member average? No, let's use actual:
    member_txs = period_txs[period_txs['User_Type'] != '非會員 (Non-member)']
    total_active = member_txs[col_id].nunique() if not member_txs.empty else 0
    new_active = type_counts.get('新客 (New)', 0)
    ret_active = type_counts.get('舊客 (Returning)', 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👤 總活躍會員", f"{total_active:,.0f} 人")
    m2.metric("🆕 新會員數", f"{new_active:,.0f} 人", f"{new_active/total_active:.1%}" if total_active else "0%")
    m3.metric("💸 新客營收貢獻", f"${new_rev:,.0f}", f"{new_rev/(new_rev+ret_rev):.1%}" if (new_rev+ret_rev) else "0%")
    m4.metric("💰 舊客營收貢獻", f"${ret_rev:,.0f}", f"{ret_rev/(new_rev+ret_rev):.1%}" if (new_rev+ret_rev) else "0%")
    
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👥 客群筆數分佈 (同日同名為一筆)")
        fig = px.pie(values=type_counts.values, names=type_counts.index, title="期間來訪佔比 (含非會員)", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("💳 平均客單價 (Avg Check by Type)")
        avg_df = pd.DataFrame([
            {'User_Type': '新客 (New)', 'Avg_Spend': new_rev / new_txs if new_txs else 0},
            {'User_Type': '舊客 (Returning)', 'Avg_Spend': ret_rev / ret_txs if ret_txs else 0},
            {'User_Type': '非會員 (Non-member)', 'Avg_Spend': non_rev / non_txs if non_txs else 0}
        ])
        fig2 = px.bar(avg_df, x='User_Type', y='Avg_Spend', title="平均客單價比較", text_auto='.0f', color='User_Type')
        st.plotly_chart(fig2, use_container_width=True)
        
    st.divider()
    
    # Popular Items Section
    st.subheader("🏆 各類客群熱門餐點分析")
    st.caption("依據主食銷量排序 (顯示 Top 5)")
    
    # Merge User_Type into details
    if not df_details.empty and not period_txs.empty:
        # Get mapping of order_id to User_Type
        order_type_map = period_txs[['order_id', 'User_Type']].drop_duplicates()
        curr_details = df_details[
            (df_details['Date_Parsed'] >= start_ts) & 
            (df_details['Date_Parsed'] <= end_ts) & 
            (df_details['Is_Main_Dish'] == True)
        ].merge(order_type_map, on='order_id', how='inner')
        
        if not curr_details.empty:
            types_to_show = ['新客 (New)', '舊客 (Returning)', '非會員 (Non-member)']
            cols = st.columns(3)
            
            for i, u_type in enumerate(types_to_show):
                with cols[i]:
                    st.markdown(f"**{u_type}**")
                    df_u = curr_details[curr_details['User_Type'] == u_type]
                    if not df_u.empty:
                        top_items = df_u.groupby('item_name')['qty'].sum().reset_index().sort_values('qty', ascending=False).head(5)
                        # Minimalist bar chart
                        st.dataframe(top_items.rename(columns={'item_name': '餐點', 'qty': '數量'}).set_index('餐點'), use_container_width=True)
                    else:
                        st.caption("無資料")
    else:
        st.info("無法載入明細資料進行熱門商品分析。")
        
    st.divider()
    
    # Time Series: New vs Returning over time
    st.subheader("📈 日常客群來店趨勢")
    
    daily_type = period_txs.groupby(['Date_Only', 'User_Type'])['Visit_ID'].nunique().reset_index()
    daily_type.rename(columns={'Visit_ID': 'Visits'}, inplace=True)
    
    fig_time = px.bar(daily_type, x='Date_Only', y='Visits', color='User_Type', title="每日客群來訪數 (同日視為 1 筆)", barmode='stack')
    st.plotly_chart(fig_time, use_container_width=True)

    st.divider()
    
    # Retention / Frequency
    st.subheader("📊 期間回訪頻率 (僅限會員)")
    member_only_txs = period_txs[period_txs['User_Type'] != '非會員 (Non-member)']
    freq = member_only_txs.groupby(col_id)['Visit_ID'].nunique().reset_index()
    freq['Frequency'] = pd.cut(freq['Visit_ID'], bins=[0, 1, 2, 5, 100], labels=['1次', '2次', '3-5次', '6次+'])
    
    # Split frequency by User Type to see if new users ever come back twice in the same period
    user_type_map = member_only_txs[[col_id, 'User_Type']].drop_duplicates()
    freq = freq.merge(user_type_map, on=col_id, how='left')
    freq_summary = freq.groupby(['User_Type', 'Frequency']).size().reset_index(name='Count')
    
    fig_freq = px.bar(freq_summary, x='Frequency', y='Count', color='User_Type', barmode='group', title="期間內消費次數分佈")
    st.plotly_chart(fig_freq, use_container_width=True)

    st.divider()
    
    # RFM Analysis
    st.subheader("🎯 區間內客群細節 (RFM Scatter Plot)")
    st.caption("基於您選擇的日期區間，計算活躍會員的 R (最近一次消費距今)、F (區間內來店次數)、M (區間內累積消費)。")
    
    interval_txs = period_txs[period_txs[col_id] != '非會員'].copy()
    
    if not interval_txs.empty:
        # Calculate R, F, M
        rfm = interval_txs.groupby(col_id).agg(
            Last_Purchase=('Date_Parsed', 'max'),
            Frequency=('Visit_ID', 'nunique'),
            Monetary=('total_amount', 'sum')
        ).reset_index()
        
        # Calculate Recency in days (against the end of the selected period)
        rfm['Recency'] = (pd.Timestamp(end_ts.date()) - pd.to_datetime(rfm['Last_Purchase']).dt.normalize()).dt.days
        rfm['Recency'] = rfm['Recency'].clip(lower=0)
        
        interval_days = max((end_ts.date() - start_ts.date()).days, 1)
        r_thresh = interval_days / 2 if interval_days >= 28 else 14
        
        def segment_rfm(row):
            f = row['Frequency']
            r = row['Recency']
            
            if f >= 3:
                return "Champions (主力常客)" if r <= r_thresh else "At Risk (流失預警)"
            elif f == 2:
                return "Potential (潛力新星)" if r <= r_thresh else "At Risk (流失預警)"
            else:
                return "New (新客)" if r <= r_thresh else "One-time (一次客)"
                
        rfm['Segment'] = rfm.apply(segment_rfm, axis=1)
        
        color_map = {
            "Champions (主力常客)": "#7FCCB5",
            "Potential (潛力新星)": "#FDD1C9",
            "New (新客)": "#FF7B72",
            "At Risk (流失預警)": "#A5D8FF",
            "One-time (一次客)": "#5B96DB"
        }
        cat_order = list(color_map.keys())
        
        fig_scatter = px.scatter(
            rfm, 
            x='Recency', 
            y='Frequency', 
            size='Monetary', 
            color='Segment', 
            hover_name=col_id,
            category_orders={"Segment": cat_order},
            color_discrete_map=color_map,
            title="RFM 分佈 (X=天數未訪, Y=消費次數, 大小=消費額)",
            labels={
                'Recency': 'Recency (天數未訪 - 越小越好)',
                'Frequency': 'Frequency (來店次數)'
            },
            size_max=30
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.divider()
        
        seg_counts = rfm['Segment'].value_counts().reset_index()
        seg_counts.columns = ['會員價值分群', '人數']
        
        # Avg M per segment
        seg_m = rfm.groupby('Segment')['Monetary'].mean().reset_index()
        seg_counts = seg_counts.merge(seg_m, left_on='會員價值分群', right_on='Segment')
        
        col_rfm1, col_rfm2 = st.columns([1, 1])
        with col_rfm1:
            fig_rfm = px.pie(
                seg_counts, names='會員價值分群', values='人數', 
                title="區間 RFM 會員分群佔比", hole=0.3,
                color='會員價值分群', color_discrete_map=color_map,
                category_orders={"會員價值分群": cat_order}
            )
            st.plotly_chart(fig_rfm, use_container_width=True)
            
        with col_rfm2:
            fig_rfm2 = px.bar(
                seg_counts, x='會員價值分群', y='Monetary', 
                title="各群體平均區間貢獻 ($)", text_auto='.0f',
                color='會員價值分群', color_discrete_map=color_map,
                category_orders={"會員價值分群": cat_order}
            )
            fig_rfm2.update_layout(showlegend=False)
            st.plotly_chart(fig_rfm2, use_container_width=True)
