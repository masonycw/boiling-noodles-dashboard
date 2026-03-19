"""P1 migration: add missing fields to vendors, items, stocktake_groups"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from erp.backend.db.session import engine
from sqlalchemy import text

MIGRATIONS = [
    # Vendor new fields
    "ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS line_id VARCHAR",
    "ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS bank_account_holder VARCHAR",
    "ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS reminder_days INTEGER DEFAULT 5",
    "ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS order_cycle VARCHAR",
    "ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS payment_method VARCHAR",
    # Item new fields
    "ALTER TABLE erp_items ADD COLUMN IF NOT EXISTS category VARCHAR",
    "ALTER TABLE erp_items ADD COLUMN IF NOT EXISTS price NUMERIC(10,2)",
    # StocktakeGroup new fields
    "ALTER TABLE erp_stocktake_groups ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE erp_stocktake_groups ADD COLUMN IF NOT EXISTS suggested_frequency VARCHAR",
]

if __name__ == '__main__':
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
                print(f"OK: {sql[:60]}...")
            except Exception as e:
                print(f"SKIP: {e}")
        conn.commit()
    print("Migration complete.")
