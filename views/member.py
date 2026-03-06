import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta
import db_queries

def render_member_search(latest_dates=None):
    st.title("👥 會員消費紀錄查詢")
    
    st.info("⚡ 此頁面已連線 PostgreSQL，資料皆為即時查詢。")
    
    st.subheader("🔍 搜尋會員")
    st.caption("輸入資料 (姓名 / 電話 / 載具號碼)")
    search_term = st.text_input("關鍵字 (Keyword)", "")
    
    if search_term:
        s_clean = search_term.strip()
        candidates = db_queries.fetch_member_search(s_clean)
        
        if not candidates.empty:
            def make_label(row):
                n = str(row.get('customer_name', '')) if row.get('customer_name') else '-'
                p = str(row.get('member_phone', '')) if row.get('member_phone') else '-'
                c = str(row.get('carrier_id', '')) if row.get('carrier_id') else '-'
                mid = str(row.get('Member_ID', ''))
                
                label = f"{n} / {p} / {c}"
                return f"{label} (ID: {mid})"

            unique_members = candidates.drop_duplicates(subset=['Member_ID']).copy()
            unique_members['Label'] = unique_members.apply(make_label, axis=1)
            
            sel_label = st.selectbox(f"找到 {len(unique_members)} 位相關會員:", unique_members['Label'].tolist())
            
            sel_mid_row = unique_members[unique_members['Label'] == sel_label].iloc[0]
            sel_mid = sel_mid_row['Member_ID']
            
            mem_records = db_queries.fetch_member_transactions(sel_mid)
            
            st.divider()
            st.subheader(f"👤 會員檔案: {sel_label}")
            
            if not mem_records.empty:
                mem_records['Date_Parsed'] = pd.to_datetime(mem_records['Date_Parsed'])
                total_spend = mem_records['total_amount'].sum()
                visits = mem_records['Date_Parsed'].dt.date.nunique()
                first_visit = mem_records['Date_Parsed'].min().date()
                last_visit = mem_records['Date_Parsed'].max().date()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("總消費", f"${total_spend:,.0f}")
                c2.metric("來店次數", f"{visits} 次")
                c3.metric("初次來店", str(first_visit))
                c4.metric("最近來店", str(last_visit))
                
                st.subheader("🧾 消費歷程")
                hist_df = mem_records[['Date_Parsed', 'order_id', 'total_amount', 'order_type', 'customer_name']].copy()
                st.dataframe(hist_df.style.format({'total_amount': '${:,.0f}', 'Date_Parsed': '{:%Y-%m-%d %H:%M}'}), use_container_width=True)
                
                fav_items = db_queries.fetch_member_fav_items(sel_mid)
                if not fav_items.empty:
                    st.subheader("❤️ 喜好商品")
                    st.bar_chart(fav_items.set_index('item_name'))
            
        else:
            st.warning("查無資料")

def render_crm_analysis(latest_dates=None):
    st.title("🆕 新舊客分析 (New vs Returning)")
    
    # --- Data Freshness Banner ---
    freshness = db_queries.fetch_data_freshness()
    if not freshness.empty:
        dates_map = {}
        for _, row in freshness.iterrows():
            dates_map[row['source_key']] = str(row['latest_date'])
            
        json_date = dates_map.get('json', 'N/A')
        rep_date = dates_map.get('csv_report', 'N/A')
        det_date = dates_map.get('csv_details', 'N/A')
        inv_date = dates_map.get('invoice', 'N/A')
        
        st.info(f"**最新系統資料範圍提示**\n\n"
                f"📡 **Eats365 API (JSON)**: `{json_date}` \u3000|\u3000 📊 **營業日報表 (CSV)**: `{rep_date}`\n\n"
                f"🛒 **交易明細 (CSV)**: `{det_date}` \u3000|\u3000 🧾 **發票明細 (CSV)**: `{inv_date}`\n\n"
                f"*(新舊客與會員判定極度依賴歷史紀錄，請確認上面所有手動 CSV 檔案都已上傳更新至最新日期)*")
    else:
        st.info("⚡ 此頁面已升級為 PostgreSQL 即時連線。")

    with st.expander("ℹ️ 新舊客與非會員定義說明"):
        st.markdown("""
        * **新客 (New)**：在您選擇的區間內，該會員發生了「歷史以來的第 1 次」消費。
        * **舊客 (Returning)**：在您選擇的區間內有消費，但他的「歷史第 1 次」消費發生在這個區間之前。
        * **非會員 (Non-member)**：本次交易未綁定會員電話或載具。
        """)
    
    st.divider()
    
    st.subheader("🗓️ 單期綜合分析區間")
    from .utils import render_date_filter
    s_date, e_date = render_date_filter("crm_tab1", "這個月 (This Month)")
    
    period_txs = db_queries.fetch_crm_tx_data(s_date, e_date)
    
    if period_txs.empty:
        st.warning("此區間無交易資料")
        return
        
    global_first_visits = db_queries.fetch_all_time_active_members()
    global_first_visits = global_first_visits[['Member_ID', 'First_Visit_Date']]
    
    period_txs = period_txs.merge(global_first_visits, on='Member_ID', how='left')
    
    period_txs['Date_Parsed'] = pd.to_datetime(period_txs['Date_Parsed'])
    period_txs['First_Visit_Date'] = pd.to_datetime(period_txs['First_Visit_Date'])
    period_txs['Date_Only'] = period_txs['Date_Parsed'].dt.date
    
    start_ts = pd.Timestamp(s_date)
    end_ts = pd.Timestamp(e_date)
    
    def determine_type(row):
        if row['Member_ID'] == '非會員':
            return '非會員 (Non-member)'
        if pd.isna(row['First_Visit_Date']):
            return '非會員 (Non-member)'
        if row['First_Visit_Date'].date() >= start_ts.date():
            return '新客 (New)'
        return '舊客 (Returning)'
        
    period_txs['User_Type'] = period_txs.apply(determine_type, axis=1)
    
    def get_visit_id(row):
        if row['User_Type'] == '非會員 (Non-member)':
            return str(row['order_id'])
        else:
            return f"{row['Member_ID']}_{row['Date_Only']}"
            
    period_txs['Visit_ID'] = period_txs.apply(get_visit_id, axis=1)
    
    type_counts = period_txs.groupby('User_Type')['Visit_ID'].nunique()
    
    rev_by_type = period_txs.groupby('User_Type').agg(
        Total_Revenue=('total_amount', 'sum'),
        Tx_Count=('Visit_ID', 'nunique')
    ).reset_index()
    
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
    m1.metric("👥 總來店客組", f"{total_txs:,.0f} 組", help="根據訂單ID或會員每日計算的不重複來訪數")
    m2.metric("🆕 新客營收佔比", f"${new_rev:,.0f}", delta=f"佔比 {new_rev/total_rev:.1%}" if total_rev else "佔比 0%", delta_color="off")
    m3.metric("🤝 舊客營收佔比", f"${ret_rev:,.0f}", delta=f"佔比 {ret_rev/total_rev:.1%}" if total_rev else "佔比 0%", delta_color="off")
    m4.metric("❓ 非會員營收佔", f"${non_rev:,.0f}", delta=f"佔比 {non_rev/total_rev:.1%}" if total_rev else "佔比 0%", delta_color="off")
    
    member_txs = period_txs[period_txs['User_Type'] != '非會員 (Non-member)']
    total_active = member_txs['Member_ID'].nunique() if not member_txs.empty else 0
    new_active = type_counts.get('新客 (New)', 0)
    ret_active = type_counts.get('舊客 (Returning)', 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("👤 總活躍會員", f"{total_active:,.0f} 人")
    m2.metric("🆕 新會員數", f"{new_active:,.0f} 人", delta=f"佔比 {new_active/total_active:.1%}" if total_active else "佔比 0%", delta_color="off")
    m3.metric("💸 新客會員貢獻", f"${new_rev:,.0f}", delta=f"佔比 {new_rev/(new_rev+ret_rev):.1%}" if (new_rev+ret_rev) else "佔比 0%", delta_color="off")
    m4.metric("💰 舊客會員貢獻", f"${ret_rev:,.0f}", delta=f"佔比 {ret_rev/(new_rev+ret_rev):.1%}" if (new_rev+ret_rev) else "佔比 0%", delta_color="off")
    
    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👥 客群筆數分佈")
        fig = px.pie(values=type_counts.values, names=type_counts.index, title="期間來訪佔比 (含非會員)", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("💳 平均客單價")
        avg_df = pd.DataFrame([
            {'User_Type': '新客 (New)', 'Avg_Spend': new_rev / new_txs if new_txs else 0},
            {'User_Type': '舊客 (Returning)', 'Avg_Spend': ret_rev / ret_txs if ret_txs else 0},
            {'User_Type': '非會員 (Non-member)', 'Avg_Spend': non_rev / non_txs if non_txs else 0}
        ])
        fig2 = px.bar(avg_df, x='User_Type', y='Avg_Spend', title="平均客單價比較", text_auto='.0f', color='User_Type')
        st.plotly_chart(fig2, use_container_width=True)
        
    st.divider()
    
    st.subheader("🏆 各類客群熱門餐點分析")
    st.caption("依據主食銷量排序 (顯示 Top 5)")
    
    curr_details = db_queries.fetch_crm_details_items(s_date, e_date)
    
    if not curr_details.empty and not period_txs.empty:
        order_type_map = period_txs[['order_id', 'User_Type']].drop_duplicates()
        curr_details = curr_details.merge(order_type_map, on='order_id', how='inner')
        
        types_to_show = ['新客 (New)', '舊客 (Returning)', '非會員 (Non-member)']
        cols = st.columns(3)
        
        for i, u_type in enumerate(types_to_show):
            with cols[i]:
                st.markdown(f"**{u_type}**")
                df_u = curr_details[curr_details['User_Type'] == u_type]
                if not df_u.empty:
                    top_items = df_u.groupby('item_name')['qty'].sum().reset_index().sort_values('qty', ascending=False).head(5)
                    st.dataframe(top_items.rename(columns={'item_name': '餐點', 'qty': '數量'}).set_index('餐點'), use_container_width=True)
                else:
                    st.caption("無資料")
    else:
        st.info("無法載入明細資料進行熱門商品分析。")
        
    st.divider()
    
    st.subheader("📈 日常客群來店趨勢")
    daily_type = period_txs.groupby(['Date_Only', 'User_Type'])['Visit_ID'].nunique().reset_index()
    daily_type.rename(columns={'Visit_ID': 'Visits'}, inplace=True)
    
    fig_time = px.bar(daily_type, x='Date_Only', y='Visits', color='User_Type', title="每日客群來訪數", barmode='stack')
    st.plotly_chart(fig_time, use_container_width=True)
        
    st.divider()
    
    st.subheader("📊 期間回訪頻率 (會員)")
    freq = member_txs.groupby('Member_ID')['Visit_ID'].nunique().reset_index()
    freq['Frequency'] = pd.cut(freq['Visit_ID'], bins=[0, 1, 2, 5, 100], labels=['1次', '2次', '3-5次', '6次+'])
    
    user_type_map = member_txs[['Member_ID', 'User_Type']].drop_duplicates()
    freq = freq.merge(user_type_map, on='Member_ID', how='left')
    freq_summary = freq.groupby(['User_Type', 'Frequency']).size().reset_index(name='Count')
    
    fig_freq = px.bar(freq_summary, x='Frequency', y='Count', color='User_Type', barmode='group', title="期間消費次數分佈")
    st.plotly_chart(fig_freq, use_container_width=True)

    st.divider()
    
    st.subheader("🎯 區間內 RFM Scatter")
    st.caption("基於您選擇的日期區間，計算活躍會員的 R (最近一次消費距今)、F (區間來店)、M (區間消費)。")
    
    interval_txs = member_txs.copy()
    
    if not interval_txs.empty:
        rfm = interval_txs.groupby('Member_ID').agg(
            Last_Purchase=('Date_Parsed', 'max'),
            Frequency=('Visit_ID', 'nunique'),
            Monetary=('total_amount', 'sum')
        ).reset_index()
        
        rfm = rfm.merge(global_first_visits, on='Member_ID', how='left')
        rfm['Days_Since_First_Visit'] = (pd.Timestamp(end_ts.date()) - pd.to_datetime(rfm['First_Visit_Date']).dt.normalize()).dt.days
        rfm['First_Visit_Str'] = pd.to_datetime(rfm['First_Visit_Date']).dt.strftime('%Y-%m-%d')
        
        global_all_freq = db_queries.fetch_all_time_active_members()
        rfm = rfm.merge(global_all_freq[['Member_ID', 'Frequency_Global']], on='Member_ID', how='left')
        
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
            x='Recency', y='Frequency', size='Monetary', color='Segment', 
            hover_name='Member_ID',
            category_orders={"Segment": cat_order},
            color_discrete_map=color_map,
            title="RFM 分佈"
        )
        with st.expander("📊 查看 RFM 散佈圖"):
            st.plotly_chart(fig_scatter, use_container_width=True)
            
        seg_counts = rfm['Segment'].value_counts().reset_index()
        seg_counts.columns = ['會員價值分群', '人數']
        
        seg_m = rfm.groupby('Segment')['Monetary'].mean().reset_index()
        seg_counts = seg_counts.merge(seg_m, left_on='會員價值分群', right_on='Segment')
        
        col_rfm1, col_rfm2 = st.columns([1, 1])
        with col_rfm1:
            fig_rfm = px.pie(seg_counts, names='會員價值分群', values='人數', title="RFM 佔比", hole=0.3, color='會員價值分群', color_discrete_map=color_map, category_orders={"會員價值分群": cat_order})
            st.plotly_chart(fig_rfm, use_container_width=True)
        with col_rfm2:
            fig_rfm2 = px.bar(seg_counts, x='會員價值分群', y='Monetary', title="各群體平均貢獻", color='會員價值分群', color_discrete_map=color_map, category_orders={"會員價值分群": cat_order})
            fig_rfm2.update_layout(showlegend=False)
            st.plotly_chart(fig_rfm2, use_container_width=True)

    st.divider()
    
    st.subheader("🗓️ 歷史走勢觀察區間")
    from .utils import render_date_filter
    s_date_t2, e_date_t2 = render_date_filter("crm_trend", "這個月 (This Month)")
    start_ts_t2 = pd.Timestamp(s_date_t2)
    end_ts_t2 = pd.Timestamp(e_date_t2)
    
    st.subheader("📊 歷史客群營收走勢 (28日移動總和)")
    
    all_daily_rev = db_queries.fetch_rolling_member_revenue()
    
    if not all_daily_rev.empty:
        all_daily_rev['Date_Only'] = pd.to_datetime(all_daily_rev['Date_Only']).dt.date
        all_daily_rev = all_daily_rev.merge(global_first_visits, on='Member_ID', how='left')
        
        def assign_global_type(row):
            if row['Member_ID'] == '非會員': return '非會員 (Non-member)'
            if pd.isna(row['First_Visit_Date']): return '非會員 (Non-member)'
            if row['Date_Only'] == pd.to_datetime(row['First_Visit_Date']).date(): return '新客 (New)'
            return '舊客 (Returning)'
            
        all_daily_rev['Global_Type'] = all_daily_rev.apply(assign_global_type, axis=1)
        
        daily_rev = all_daily_rev.groupby(['Date_Only', 'Global_Type'])['daily_rev'].sum().unstack(fill_value=0).reset_index()
        for c in ['新客 (New)', '舊客 (Returning)', '非會員 (Non-member)']:
            if c not in daily_rev.columns: daily_rev[c] = 0
            
        daily_rev = daily_rev.sort_values('Date_Only')
        active_days = daily_rev['Date_Only'].values
        
        rolling_df = daily_rev.copy()
        rolling_df['新客營收總和 (28日)'] = rolling_df['新客 (New)'].rolling(window=28, min_periods=1).sum()
        rolling_df['舊客營收總和 (28日)'] = rolling_df['舊客 (Returning)'].rolling(window=28, min_periods=1).sum()
        rolling_df['非會員營收總和 (28日)'] = rolling_df['非會員 (Non-member)'].rolling(window=28, min_periods=1).sum()
        
        rolling_df['純會員總和 (28日)'] = rolling_df['新客營收總和 (28日)'] + rolling_df['舊客營收總和 (28日)']
        rolling_df['會員總和_Safe'] = rolling_df['純會員總和 (28日)'].replace(0, np.nan)
        
        rolling_df['舊客會員內貢獻 (28日)'] = rolling_df['舊客營收總和 (28日)'] / rolling_df['會員總和_Safe']
        
        mask_period = (pd.to_datetime(rolling_df['Date_Only']) >= start_ts_t2) & (pd.to_datetime(rolling_df['Date_Only']) <= end_ts_t2)
        plot_df = rolling_df.loc[mask_period].copy()
        
        if not plot_df.empty:
            recent_stats = rolling_df[pd.to_datetime(rolling_df['Date_Only']) <= end_ts_t2]
            
            if not recent_stats.empty:
                latest_row = recent_stats.iloc[-1]
                
                n_rev28 = latest_row['新客營收總和 (28日)']
                r_rev28 = latest_row['舊客營收總和 (28日)']
                nm_rev28 = latest_row['非會員營收總和 (28日)']
                total_rev28 = n_rev28 + r_rev28 + nm_rev28
                
                idx = np.where(active_days == latest_row['Date_Only'])[0]
                if len(idx) > 0:
                    end_idx = idx[0]
                    start_idx = max(0, end_idx - 27)
                    window_days = active_days[start_idx : end_idx + 1]
                    
                    window_df = all_daily_rev[(all_daily_rev['Date_Only'].isin(window_days)) & (all_daily_rev['Member_ID'] != '非會員')]
                    unique_members_28d = window_df['Member_ID'].nunique()
                else:
                    unique_members_28d = 0
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("28營業日總活躍會員", f"{unique_members_28d:,.0f} 人")
                m2.metric("新客營收貢獻(28日)", f"${n_rev28:,.0f}", f"佔比 {n_rev28/total_rev28:.1%}" if total_rev28 else "0%", delta_color="off")
                m3.metric("舊客營收貢獻(28日)", f"${r_rev28:,.0f}", f"佔比 {r_rev28/total_rev28:.1%}" if total_rev28 else "0%", delta_color="off")
                m4.metric("非會員營收(28日)", f"${nm_rev28:,.0f}", f"佔比 {nm_rev28/total_rev28:.1%}" if total_rev28 else "0%", delta_color="off")
                
            fig_rolling = make_subplots(specs=[[{"secondary_y": True}]])
            
            color_map = {
                '新客營收總和 (28日)': '#FF7B72',
                '舊客營收總和 (28日)': '#7FCCB5',
                '非會員營收總和 (28日)': '#C9D1D9'
            }
            
            for col in ['新客營收總和 (28日)', '舊客營收總和 (28日)', '非會員營收總和 (28日)']:
                fig_rolling.add_trace(
                    go.Scatter(x=plot_df['Date_Only'], y=plot_df[col], name=col, line=dict(color=color_map[col], width=3)),
                    secondary_y=False,
                )
                
            fig_rolling.add_trace(
                go.Scatter(
                    x=plot_df['Date_Only'], y=plot_df['舊客會員內貢獻 (28日)'], name='舊客會員內貢獻佔比',
                    line=dict(color='#F2C94C', width=3, dash='dot')
                ),
                secondary_y=True,
            )
            
            fig_rolling.update_layout(title="客群 28 營業日滾動總營收趨勢")
            fig_rolling.update_yaxes(title_text="營收", secondary_y=False)
            fig_rolling.update_yaxes(title_text="佔比", tickformat='.1%', secondary_y=True, range=[0, 1.05])
            
            st.plotly_chart(fig_rolling, use_container_width=True)
        else:
            st.info("該區間並無足夠的營業日可以顯示趨勢。")
    else:
        st.info("資料庫中無紀錄。")
