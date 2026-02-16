import streamlit as st
import pandas as pd
from datetime import timedelta, date

def render_member_search(df_report, df_details):
    st.title("👥 會員消費紀錄查詢")
    
    col_phone = 'member_phone'
    col_name = 'customer_name'
    
    if col_phone not in df_report.columns:
        st.error("資料缺少會員電話欄位")
        return

    st.subheader("🔍 搜尋會員")
    search_term = st.text_input("輸入 姓名 或 電話 (模糊搜尋)", "")
    
    if search_term:
        s_clean = search_term.strip()
        
        # Search Matrix
        mask = pd.Series(False, index=df_report.index)
        
        if col_phone in df_report.columns:
             phone_series = df_report[col_phone].astype(str).str.replace(r'\D', '', regex=True)
             mask |= phone_series.str.contains(s_clean, na=False)
             
        if col_name in df_report.columns:
             name_series = df_report[col_name].astype(str).fillna('')
             mask |= name_series.str.contains(s_clean, na=False)
             
        results = df_report[mask].copy()
        
        if not results.empty:
            unique_members = results[[col_name, col_phone]].drop_duplicates()
            # Handle NaN
            unique_members = unique_members.fillna('')
            unique_members['Label'] = unique_members[col_name].astype(str) + " (" + unique_members[col_phone].astype(str) + ")"
            
            sel_label = st.selectbox("請選擇會員:", unique_members['Label'].tolist())
            
            # Filter Records
            # Logic: Match exact Name AND Phone if possible
            sel_row = unique_members[unique_members['Label'] == sel_label].iloc[0]
            sel_n = sel_row[col_name]
            sel_p = sel_row[col_phone]
            
            mem_records = df_report[
                (df_report[col_name].fillna('').astype(str) == str(sel_n)) & 
                (df_report[col_phone].fillna('').astype(str) == str(sel_p))
            ].copy()
            
            mem_records = mem_records.sort_values('Date_Parsed', ascending=False)
            
            # Metrics
            total_spend = mem_records['total_amount'].sum()
            visits = mem_records['Date_Parsed'].nunique()
            txs = len(mem_records)
            avg = total_spend / visits if visits > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("總消費", f"${total_spend:,.0f}")
            c2.metric("來店次數", f"{visits} 天")
            c3.metric("平均客單", f"${avg:,.0f}")
            
            st.divider()
            st.write("詳細紀錄:")
            st.dataframe(mem_records[['Date_Parsed', 'order_id', 'total_amount', 'order_type']].style.format({'total_amount': '${:,.0f}'}), use_container_width=True)
            
        else:
            st.warning("查無資料")

def render_crm_analysis(df_report):
    st.title("🆕 新舊客分析 (CRM)")
    
    analysis_basis = st.radio("分析基準", ["電話 (Phone)", "載具 (Carrier)"], horizontal=True)
    basis_col = 'member_phone' if "Phone" in analysis_basis else 'carrier_id'
    
    if basis_col not in df_report.columns:
        st.warning(f"缺少 {basis_col} 欄位，無法分析")
        return
        
    # Prepare Data
    df = df_report.dropna(subset=[basis_col]).copy()
    # Filter valid IDs (len > 3)
    df = df[df[basis_col].astype(str).str.len() > 3]
    
    if df.empty:
        st.warning("沒有有效的會員數據")
        return
        
    # Stats
    member_stats = df.groupby(basis_col).agg({
        'Date_Parsed': ['min', 'max', 'count', 'nunique'],
        'total_amount': 'sum'
    }).reset_index()
    member_stats.columns = ['ID', 'First_Visit', 'Last_Visit', 'Tx_Count', 'Visit_Days', 'Total_Spend']
    
    # Define "New" as First Visit in selected range
    # But here we stick to simple logic: New = First Visit ever? 
    # Or New in Period? 
    # Let's keep it simple: Distribution of Visit Counts
    
    st.subheader("會員分群 (依來店次數)")
    bins = [0, 1, 2, 5, 10, 1000]
    labels = ['1次 (新客)', '2次 (回頭客)', '3-5次 (熟客)', '6-10次 (忠誠客)', '10次+ (VIP)']
    member_stats['Segment'] = pd.cut(member_stats['Visit_Days'], bins=bins, labels=labels)
    
    seg_counts = member_stats['Segment'].value_counts().sort_index()
    st.bar_chart(seg_counts)
    
    st.write("詳細數據:")
    st.dataframe(pd.DataFrame(seg_counts).T)
