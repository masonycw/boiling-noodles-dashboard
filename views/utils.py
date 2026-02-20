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
    shortcuts = [
        "自訂 (Custom)", 
        "這個月 (This Month)", 
        "上個月 (Last Month)", 
        "近4週 (Last 4 Weeks)", 
        "近2個月 (Last 2 Months)", 
        "近6個月 (Last 6 Months)"
    ]
    
    col1, col2 = st.columns([1, 2])
    with col1:
        shortcut = st.selectbox("📅 快速選擇區間", shortcuts, key=f"{key_prefix}_shortcut")
    
    start_shortcut, end_shortcut = get_date_range_shortcut(shortcut)
    
    with col2:
        if start_shortcut and end_shortcut:
            # Use shortcut dates, show them disabled
            d_range = st.date_input("選擇日期", value=(start_shortcut, end_shortcut), key=f"{key_prefix}_date_disabled", disabled=True)
            s_date, e_date = start_shortcut, end_shortcut
        else:
            # Custom date input
            today = date.today()
            default_val = (today.replace(day=1), today)
            d_range = st.date_input("選擇日期", value=default_val, key=f"{key_prefix}_date_custom")
            if len(d_range) == 2:
                s_date, e_date = d_range[0], d_range[1]
            elif len(d_range) == 1:
                s_date, e_date = d_range[0], d_range[0]
            else:
                s_date, e_date = today, today
                
    return pd.to_datetime(s_date), pd.to_datetime(e_date)

