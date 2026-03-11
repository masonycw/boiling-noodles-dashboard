import sys
import os

sys.path.append(os.getcwd())
try:
    from erp.backend.db.session import engine
except Exception as e:
    print("Could not import engine", e)
    sys.exit(1)

from sqlalchemy import text

def run_migration():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE erp_purchase_orders ADD COLUMN expected_delivery_date TIMESTAMP WITH TIME ZONE;"))
            print("Added expected_delivery_date")
        except Exception as e:
            print("Skip expected_delivery_date:", e)
            
        try:
            conn.execute(text("ALTER TABLE erp_purchase_orders ADD COLUMN amount_paid NUMERIC(10, 2) DEFAULT 0;"))
            print("Added amount_paid")
        except Exception as e:
            print("Skip amount_paid:", e)

        try:
            conn.execute(text("ALTER TABLE erp_cash_transactions ADD COLUMN has_receipt BOOLEAN DEFAULT FALSE;"))
            print("Added has_receipt")
        except Exception as e:
            print("Skip has_receipt:", e)
            
        try:
            conn.execute(text("ALTER TABLE erp_cash_transactions ADD COLUMN receipt_url VARCHAR;"))
            print("Added receipt_url")
        except Exception as e:
            print("Skip receipt_url:", e)
            
        conn.commit()

if __name__ == "__main__":
    run_migration()
