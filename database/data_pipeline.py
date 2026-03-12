import os
import sys
import psycopg2
from data_loader import UniversalLoader
from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
import pandas as pd
from psycopg2.extras import execute_values
from datetime import datetime

LOCK_FILE = '/tmp/pipeline.lock'

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        print(f"⚠️ Lock file {LOCK_FILE} exists. Another instance of the pipeline is running.")
        sys.exit(0)
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def connect_to_db():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

def setup_database():
    print("Setting up database schema...")
    conn = connect_to_db()
    with conn.cursor() as cur:
        with open('db_schema.sql', 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        cur.execute(schema_sql)
        # Force add column if table already exists (as IF NOT EXISTS won't alter existing schema)
        cur.execute("ALTER TABLE orders_fact ADD COLUMN IF NOT EXISTS carrier_id VARCHAR(50);")
    conn.commit()
    conn.close()
    print("Database schema created successfully.")

def transform_and_load_orders(df_report, df_details):
    print(f"Loading {len(df_report)} orders into the database...")
    
    # 預處理資料以符合資料表 Schema
    records_to_insert = []
    
    # 計算主餐數量
    main_dish_counts = df_details[df_details['Is_Main_Dish']].groupby('order_id')['qty'].sum().reset_index()
    main_dish_counts = main_dish_counts.rename(columns={'qty': 'main_dish_count'})
    
    df_report = df_report.merge(main_dish_counts, on='order_id', how='left')
    df_report['main_dish_count'] = df_report['main_dish_count'].fillna(0).astype(int)
    
    # 將 NaN 轉為 None
    df_report = df_report.replace({float('nan'): None, '': None})

    for _, row in df_report.iterrows():
        # 處理日期對象
        date_val = row['Date_Parsed'] if pd.notna(row['Date_Parsed']) else row['date']
        if pd.isna(date_val): 
            continue
            
        record = (
            row.get('order_id'),
            date_val,
            row.get('total_amount', 0),
            row.get('status'),
            row.get('order_type'),
            row.get('people_count', 1),
            row.get('payment_method'),
            row.get('member_phone'),
            row.get('customer_name'),
            row.get('invoice_id'),
            row.get('carrier_id'),
            row.get('data_source', 'csv'),
            row.get('Day_Type'),
            row.get('Period'),
            row.get('Member_ID'),
            row.get('Order_Category'),
            row.get('main_dish_count', 0)
        )
        records_to_insert.append(record)
        
    insert_query = """
    INSERT INTO orders_fact (
        order_id, date, total_amount, status, order_type, people_count, 
        payment_method, member_phone, customer_name, invoice_id, carrier_id, data_source, 
        day_type, period, member_id, order_category, main_dish_count
    ) VALUES %s
    ON CONFLICT (order_id) DO UPDATE SET
        date = EXCLUDED.date,
        total_amount = EXCLUDED.total_amount,
        status = EXCLUDED.status,
        order_type = EXCLUDED.order_type,
        people_count = EXCLUDED.people_count,
        payment_method = EXCLUDED.payment_method,
        member_phone = EXCLUDED.member_phone,
        customer_name = EXCLUDED.customer_name,
        invoice_id = EXCLUDED.invoice_id,
        carrier_id = EXCLUDED.carrier_id,
        data_source = EXCLUDED.data_source,
        day_type = EXCLUDED.day_type,
        period = EXCLUDED.period,
        member_id = EXCLUDED.member_id,
        order_category = EXCLUDED.order_category,
        main_dish_count = EXCLUDED.main_dish_count
    WHERE EXCLUDED.data_source = 'json' 
       OR orders_fact.data_source = 'csv'
    """
    
    conn = connect_to_db()
    with conn.cursor() as cur:
        # 執行增量寫入 (UPSERT)
        execute_values(cur, insert_query, records_to_insert, page_size=1000)
    conn.commit()
    conn.close()
    print(f"Successfully loaded {len(records_to_insert)} records into orders_fact.")

def transform_and_load_details(df_details):
    print(f"Loading {len(df_details)} order detail records into the database...")
    if df_details.empty:
        return
        
    # Get order IDs to upsert
    order_ids = df_details['order_id'].dropna().unique().tolist()
    
    # Pre-process data
    records_to_insert = []
    
    # Convert NaN to None
    df_details = df_details.replace({float('nan'): None, '': None})
    
    for _, row in df_details.iterrows():
        # Process date
        date_val = row['Date_Parsed'] if pd.notna(row['Date_Parsed']) else row.get('date')
        if pd.isna(date_val): 
            continue
            
        record = (
            row.get('order_id'),
            date_val,
            row.get('item_name'),
            row.get('category'),
            row.get('sku'),
            row.get('item_type'),
            row.get('item_total', 0),
            row.get('qty', 0),
            row.get('unit_price', 0),
            row.get('options'),
            row.get('Is_Modifier', False),
            row.get('Is_Main_Dish', False),
            row.get('data_source', 'csv')
        )
        records_to_insert.append(record)
        
    insert_query = """
    INSERT INTO order_details_fact (
        order_id, date, item_name, category, sku, item_type, 
        item_total, qty, unit_price, options, is_modifier, is_main_dish, data_source
    ) VALUES %s
    """
    
    conn = connect_to_db()
    with conn.cursor() as cur:
        # Delete existing details for these orders (for incremental loading)
        if order_ids:
            cur.execute("DELETE FROM order_details_fact WHERE order_id = ANY(%s)", (order_ids,))
            
        # Insert new details
        execute_values(cur, insert_query, records_to_insert, page_size=2000)
    conn.commit()
    conn.close()
    print(f"Successfully loaded {len(records_to_insert)} records into order_details_fact.")

def update_data_freshness(latest_dates: dict):
    """Save 4 granular data source freshness dates to the data_freshness table."""
    if not latest_dates:
        return
    
    SOURCE_LABELS = {
        'json':        'Eats365 API (JSON)',
        'csv_report':  '營業日報表 (CSV)',
        'csv_details': '交易明細 (CSV)',
        'invoice':     '發票明細 (CSV)',
    }
    
    conn = connect_to_db()
    with conn.cursor() as cur:
        for key, label in SOURCE_LABELS.items():
            date_val = latest_dates.get(key)
            if date_val and date_val != '無資料':
                cur.execute("""
                    INSERT INTO data_freshness (source_key, source_label, latest_date, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (source_key) DO UPDATE SET
                        source_label = EXCLUDED.source_label,
                        latest_date = GREATEST(data_freshness.latest_date, EXCLUDED.latest_date),
                        updated_at = CURRENT_TIMESTAMP
                """, (key, label, date_val))
    conn.commit()
    conn.close()
    print(f"Data freshness updated: {latest_dates}")


def update_daily_revenue_agg():
    print("Updating daily_revenue_agg table...")
    update_query = """
    INSERT INTO daily_revenue_agg (
        date, total_revenue, total_orders, total_guests, average_ticket_size, 
        average_unit_price, lunch_revenue, dinner_revenue, dine_in_revenue, 
        takeout_revenue, delivery_revenue, new_customer_revenue, 
        returning_customer_revenue, updated_at
    )
    SELECT 
        DATE(date) AS date,
        SUM(total_amount) AS total_revenue,
        COUNT(order_id) AS total_orders,
        SUM(main_dish_count) AS total_guests,
        -- 注意：因為客單價是由前端計算，這裡只存總金額跟數量，或者簡單算個平均
        CASE WHEN COUNT(order_id) > 0 THEN SUM(total_amount) / COUNT(order_id) ELSE 0 END AS average_ticket_size,
        CASE WHEN SUM(main_dish_count) > 0 THEN SUM(total_amount) / SUM(main_dish_count) ELSE 0 END AS average_unit_price,
        
        SUM(CASE WHEN period = '中午 (Lunch)' THEN total_amount ELSE 0 END) AS lunch_revenue,
        SUM(CASE WHEN period = '晚上 (Dinner)' THEN total_amount ELSE 0 END) AS dinner_revenue,
        
        SUM(CASE WHEN order_category = '內用 (Dine-in)' THEN total_amount ELSE 0 END) AS dine_in_revenue,
        SUM(CASE WHEN order_category = '外帶 (Takeout)' THEN total_amount ELSE 0 END) AS takeout_revenue,
        SUM(CASE WHEN order_category = '外送 (Delivery)' THEN total_amount ELSE 0 END) AS delivery_revenue,
        
        -- 新舊客邏輯後續可以使用 window function 計算，這裡我們先寫個大概框架
        0 AS new_customer_revenue, -- 待實作精確邏輯
        0 AS returning_customer_revenue, -- 待實作精確邏輯
        CURRENT_TIMESTAMP AS updated_at
    FROM orders_fact
    GROUP BY DATE(date)
    ON CONFLICT (date) DO UPDATE SET
        total_revenue = EXCLUDED.total_revenue,
        total_orders = EXCLUDED.total_orders,
        total_guests = EXCLUDED.total_guests,
        average_ticket_size = EXCLUDED.average_ticket_size,
        average_unit_price = EXCLUDED.average_unit_price,
        lunch_revenue = EXCLUDED.lunch_revenue,
        dinner_revenue = EXCLUDED.dinner_revenue,
        dine_in_revenue = EXCLUDED.dine_in_revenue,
        takeout_revenue = EXCLUDED.takeout_revenue,
        delivery_revenue = EXCLUDED.delivery_revenue,
        updated_at = CURRENT_TIMESTAMP;
    """
    conn = connect_to_db()
    with conn.cursor() as cur:
        cur.execute(update_query)
    conn.commit()
    conn.close()
    print("Completed updating daily_revenue_agg.")

def main():
    acquire_lock()
    try:
        # 1. 獲取清洗後的資料
        print("Initiating incremental data load via UniversalLoader...")
        loader = UniversalLoader()
        df_report, df_details, logs = loader.scan_and_load()
        
        if df_report is None or df_report.empty:
            print("[Incremental] No new or modified files to process. Exiting cleanly.")
            return
            
        print(f"Data loaded successfully. Report size: {len(df_report)}")
        
        # 3. 下載資料新鮮度
        update_data_freshness(getattr(loader, 'latest_dates', {}))
        
        # 4. 匯入資料庫
        transform_and_load_orders(df_report, df_details)
        transform_and_load_details(df_details)
        update_daily_revenue_agg()
        
        # 5. 確認資料已成功匯入 DB，儲存已處理檔案快取
        loader.commit_processed_files()
        
        print("ETL Pipeline completed.")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
