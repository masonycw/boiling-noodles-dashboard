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
    elif shortcut_name == "近2週 (Last 2 Weeks)":
        end = today
        start = end - timedelta(days=14)
    elif shortcut_name == "近4週 (Last 4 Weeks)":
        end = today
        start = end - timedelta(days=28)
    elif shortcut_name == "近3個月 (Last 3 Months)":
        end = today
        start = end - relativedelta(months=3)
    elif shortcut_name == "近6個月 (Last 6 Months)":
        end = today
        start = end - relativedelta(months=6)
    elif shortcut_name == "近12個月 (Last 12 Months)":
        end = today
        start = end - relativedelta(months=12)
    elif shortcut_name == "所有歷史資料 (All Time)":
        end = today
        start = date(2000, 1, 1) # Will be clipped by dataframe
    elif "年" in shortcut_name and "月" in shortcut_name:
        # e.g., "2026年01月"
        try:
            year = int(shortcut_name[:4])
            month = int(shortcut_name[5:7])
            start = date(year, month, 1)
            end = start + relativedelta(months=1) - timedelta(days=1)
        except ValueError:
            return None, None
    else: # 自訂 (Custom)
        return None, None
        
    return start, end

def render_date_filter(key_prefix, default_shortcut="這個月 (This Month)"):
    """Renders a date filter with shortcuts and returns (start_date, end_date) as datetime objects."""
    
    # Generate past 6 months dynamically (e.g. 2026年01月)
    today = date.today()
    past_months = []
    for i in range(1, 7):
        target_month = today.replace(day=1) - relativedelta(months=i)
        past_months.append(target_month.strftime("%Y年%m月"))

    shortcuts = [
        "近3個月 (Last 3 Months)", 
        "自訂 (Custom)", 
        "這個月 (This Month)", 
        "上個月 (Last Month)", 
        "近2週 (Last 2 Weeks)",
        "近4週 (Last 4 Weeks)", 
        "近6個月 (Last 6 Months)",
        "近12個月 (Last 12 Months)",
        "所有歷史資料 (All Time)"
    ] + past_months
    
    col1, col2 = st.columns([1, 2])
    with col1:
        default_idx = shortcuts.index(default_shortcut) if default_shortcut in shortcuts else 0
        shortcut = st.selectbox("📅 快速選擇區間", shortcuts, index=default_idx, key=f"{key_prefix}_shortcut")
    
    start_shortcut, end_shortcut = get_date_range_shortcut(shortcut)
    
    with col2:
        if start_shortcut and end_shortcut:
            # Use shortcut dates, show them disabled
            d_range = st.date_input("選擇日期", value=(start_shortcut, end_shortcut), key=f"{key_prefix}_date_disabled", disabled=True)
            s_date, e_date = start_shortcut, end_shortcut
        else:
            # Custom date input
            default_start = today - relativedelta(months=3)
            default_val = (default_start, today)
            d_range = st.date_input("選擇日期", value=default_val, key=f"{key_prefix}_date_custom")
            if len(d_range) == 2:
                s_date, e_date = d_range[0], d_range[1]
            elif len(d_range) == 1:
                s_date, e_date = d_range[0], d_range[0]
            else:
                s_date, e_date = today, today
                
    return pd.to_datetime(s_date), pd.to_datetime(e_date) + pd.Timedelta(days=1, seconds=-1)

