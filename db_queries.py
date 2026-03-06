import psycopg2
import pandas as pd
import streamlit as st
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

@st.cache_resource(ttl=3600)
def get_db_connection():
    """Initializes and caches a connection to the PostgreSQL database."""
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

def fetch_data(query, params=None):
    """Helper method to fetch data via Pandas read_sql safely."""
    conn = get_db_connection()
    try:
        if conn.closed:
            st.cache_resource.clear()
            conn = get_db_connection()
        return pd.read_sql(query, conn, params=params)
    except Exception as e:
        st.error(f"Database query failed: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# Daily Revenue Aggregation Queries (Used by Operational/Prediction)
# ---------------------------------------------------------
def fetch_daily_revenue_agg(start_date=None, end_date=None):
    """Fetch daily aggregated revenue metrics for operational views."""
    query = "SELECT * FROM daily_revenue_agg"
    params = []
    
    if start_date and end_date:
        query += " WHERE date >= %s AND date <= %s"
        params.extend([start_date, end_date])
        
    query += " ORDER BY date DESC"
    return fetch_data(query, params)

def fetch_daily_revenue_trend(start_date, end_date):
    """Fetch order category trends, ensuring date formatting corresponds."""
    query = """
    SELECT date AS "Date_Parsed", order_category AS "Order_Category", SUM(total_amount) AS total_amount
    FROM orders_fact
    WHERE date >= %s AND date <= %s
    GROUP BY date, order_category
    ORDER BY date ASC
    """
    return fetch_data(query, [start_date, end_date])
    
def fetch_daily_breakdown(start_date, end_date):
    """Fetch detailed orders fact table to calculate arbitrary breakouts on the frontend."""
    query = """
    SELECT date AS "Date_Parsed", date::DATE AS "Date_Only", total_amount, people_count, order_type, 
           day_type AS "Day_Type", period AS "Period", order_category AS "Order_Category", main_dish_count
    FROM orders_fact
    WHERE date >= %s AND date <= %s
    """
    # Expose necessary columns like how df_rep worked for operational views
    return fetch_data(query, [start_date, end_date])

# ---------------------------------------------------------
# Item Details Queries (Used by Sales analysis)
# ---------------------------------------------------------
def fetch_sales_details(start_date, end_date):
    """Fetch order details for the product sales analysis component."""
    query = """
    SELECT date AS "Date_Parsed", item_name, category, sku, item_type,
           item_total, qty, unit_price, is_modifier AS "Is_Modifier", is_main_dish AS "Is_Main_Dish"
    FROM order_details_fact
    WHERE date >= %s AND date <= %s
    """
    return fetch_data(query, [start_date, end_date])

# ---------------------------------------------------------
# Member Profile & CRM Queries (Used by Member/CRM panels)
# ---------------------------------------------------------
def fetch_member_search(keyword):
    """Returns candidate members matching the name, phone, carrier or ID."""
    query = """
    SELECT 
        customer_name, 
        member_phone, 
        member_id AS "Member_ID", 
        invoice_id AS carrier_id
    FROM orders_fact
    WHERE customer_name ILIKE %s 
       OR member_phone LIKE %s
       OR member_id ILIKE %s
       OR invoice_id ILIKE %s
    GROUP BY customer_name, member_phone, member_id, invoice_id
    LIMIT 100
    """
    term = f"%{keyword}%"
    return fetch_data(query, [term, term, term, term])

def fetch_member_transactions(member_id):
    """Fetch history of orders completely owned by the single member ID."""
    query = """
    SELECT date AS "Date_Parsed", order_id, total_amount, order_type, customer_name
    FROM orders_fact
    WHERE member_id = %s
    ORDER BY date DESC
    """
    return fetch_data(query, [member_id])

def fetch_member_fav_items(member_id):
    """Fetch the top items purchased historically by this member."""
    query = """
    SELECT item_name, SUM(qty) AS qty
    FROM order_details_fact
    WHERE order_id IN (
        SELECT order_id FROM orders_fact WHERE member_id = %s
    ) AND is_modifier = FALSE
    GROUP BY item_name
    ORDER BY SUM(qty) DESC
    LIMIT 5
    """
    return fetch_data(query, [member_id])

def fetch_crm_tx_data(start_date, end_date):
    """Fetch all transaction instances within the period to evaluate CRM."""
    query = """
    SELECT 
        date AS "Date_Parsed",
        date::DATE AS "Date_Only",
        order_id, 
        total_amount, 
        CASE 
            WHEN member_id IS NULL OR member_id = '' OR member_id = '\u975e\u6703\u54e1' THEN '\u975e\u6703\u54e1'
            ELSE member_id
        END AS "Member_ID"
    FROM orders_fact
    WHERE date >= %s AND date <= %s
    """
    return fetch_data(query, [start_date, end_date])
    
def fetch_all_time_active_members():
    """Fetch first-visit dates for all known valid members across the platform lifecycle."""
    query = """
    SELECT member_id AS "Member_ID", MIN(date) AS "First_Visit_Date", COUNT(order_id) AS "Frequency_Global"
    FROM orders_fact
    WHERE member_id IS NOT NULL AND member_id != '' AND member_id != '\u975e\u6703\u54e1'
    GROUP BY member_id
    """
    return fetch_data(query)

def fetch_crm_details_items(start_date, end_date):
    """Fetch only main dishes for active members in the time range to find specific crowd favorites."""
    query = """
    SELECT d.date AS "Date_Parsed", d.order_id, d.item_name, d.qty, COALESCE(o.member_id, '非會員') AS "Member_ID"
    FROM order_details_fact d
    JOIN orders_fact o ON d.order_id = o.order_id
    WHERE d.date >= %s AND d.date <= %s
      AND d.is_main_dish = TRUE
    """
    return fetch_data(query, [start_date, end_date])

def fetch_rolling_member_revenue():
    """Fetches total daily revenue segmented by Member or Non-Member to power the 28-day rolling CRM widget."""
    query = """
    SELECT 
        date::DATE AS "Date_Only",
        COALESCE(member_id, '非會員') AS "Member_ID",
        SUM(total_amount) AS daily_rev
    FROM orders_fact
    GROUP BY date::DATE, COALESCE(member_id, '非會員')
    ORDER BY date::DATE ASC
    """
    return fetch_data(query)

def fetch_data_freshness():
    """Fetch the latest date and order count from orders_fact per data source."""
    query = """
    SELECT 
        data_source AS "data_source",
        MIN(date)::DATE AS "earliest_date",
        MAX(date)::DATE AS "latest_date",
        COUNT(*) AS "order_count"
    FROM orders_fact
    GROUP BY data_source
    ORDER BY data_source
    """
    return fetch_data(query)

def fetch_system_logs():
    """Simple count query to verify DB is reachable."""
    query = """
    SELECT 'orders_fact' as table_name, COUNT(*) as size FROM orders_fact
    UNION ALL
    SELECT 'daily_revenue_agg', COUNT(*) FROM daily_revenue_agg
    UNION ALL
    SELECT 'order_details_fact', COUNT(*) FROM order_details_fact
    """
    return fetch_data(query)
