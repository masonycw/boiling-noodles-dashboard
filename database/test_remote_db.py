import psycopg2
import pandas as pd

def test_connection():
    try:
        print("Connecting to remote GCP PostgreSQL database (34.81.51.45)...")
        # Connect to the remote database using the external IP
        conn = psycopg2.connect(
            host="34.81.51.45",
            port="5432",
            dbname="boiling_noodles",
            user="dashboard_user",
            password="noodles2026"
        )
        print("✅ Connection successful!\n")
        
        print("Fetching the latest 5 records from 'daily_revenue_agg' (每日營收聚合表):\n")
        query = "SELECT date, total_revenue, total_orders, average_ticket_size, average_unit_price FROM daily_revenue_agg ORDER BY date DESC LIMIT 5;"
        
        # Use pandas to easily format and print the result
        df = pd.read_sql(query, conn)
        print(df.to_string(index=False))
        
        print("\nFetching total record count from 'orders_fact' (明細表):\n")
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM orders_fact;")
        count = cur.fetchone()[0]
        print(f"Total records in orders_fact: {count} rows")
        
        cur.close()
        conn.close()
        print("\n✅ Test completed. The database is fully accessible from your local machine!")
        
    except Exception as e:
        print(f"❌ Error connecting to database:\n{e}")
        print("\nPossible reasons:")
        print("1. GCP Firewall port 5432 is not open to your IP.")
        print("2. postgresql.conf or pg_hba.conf is not correctly configured for external connections.")

if __name__ == "__main__":
    test_connection()
