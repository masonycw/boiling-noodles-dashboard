import pandas as pd
import streamlit as st
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

def calculate_delta(current, previous):
    if previous == 0: return None
    return (current - previous) / previous

def get_date_range_shortcut(shortcut_name):
    """Returns (start_date, end_date) based on shortcut name using today's date."""
    today = date.today()
    if shortcut_name == "這個月 (This Month)":
        start = today.replace(day=1)
        end = today
    elif shortcut_name == "上個月 (Last Month)":
        first_day_this_month = today.replace(day=1)
        end = first_day_this_month - timedelta(days=1)
        start = end.replace(day=1)
    elif shortcut_name == "近4週 (Last 4 Weeks)":
        end = today
        start = end - timedelta(days=28)
    elif shortcut_name == "近2個月 (Last 2 Months)":
        end = today
        start = end - relativedelta(months=2)
    elif shortcut_name == "近6個月 (Last 6 Months)":
        end = today
        start = end - relativedelta(months=6)
    else: # 自訂 (Custom)
        return None, None
        
    return start, end

def render_date_filter(key_prefix):
    """Renders a date filter with shortcuts and returns (start_date, end_date) as datetime objects."""
    
    start_key = f"{key_prefix}_start"
    end_key = f"{key_prefix}_end"
    
    if start_key not in st.session_state:
        today = date.today()
        st.session_state[start_key] = today.replace(day=1)
        st.session_state[end_key] = today

    def set_shortcut(shortcut):
        s, e = get_date_range_shortcut(shortcut)
        if s and e:
            st.session_state[start_key] = s
            st.session_state[end_key] = e
            
    shortcuts = [
        "這個月 (This Month)", 
        "上個月 (Last Month)", 
        "近4週 (Last 4 Weeks)", 
        "近2個月 (Last 2 Months)", 
        "近6個月 (Last 6 Months)"
    ]
    
    d_range = st.date_input(
        "選擇日期區間", 
        value=(st.session_state[start_key], st.session_state[end_key]), 
        key=f"{key_prefix}_date_input"
    )
    
    if len(d_range) == 2:
        st.session_state[start_key] = d_range[0]
        st.session_state[end_key] = d_range[1]
    elif len(d_range) == 1:
        st.session_state[start_key] = d_range[0]
        st.session_state[end_key] = d_range[0]
        
    st.caption("快速選擇區間")
    cols = st.columns(len(shortcuts))
    for i, sc in enumerate(shortcuts):
        label = sc.split(" ")[0]
        cols[i].button(label, on_click=set_shortcut, args=(sc,), key=f"{key_prefix}_btn_{i}")
        
    return pd.to_datetime(st.session_state[start_key]), pd.to_datetime(st.session_state[end_key])

