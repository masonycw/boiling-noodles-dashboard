"""
P2 migration: add estimated_value to waste_records, is_locked to cash_flow_records,
create erp_daily_settlements table
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from sqlalchemy import text
from erp.backend.db.session import engine

MIGRATIONS = [
    "ALTER TABLE erp_waste_records ADD COLUMN IF NOT EXISTS estimated_value DECIMAL(10,2)",
    "ALTER TABLE erp_cash_flow_records ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE",
    """CREATE TABLE IF NOT EXISTS erp_daily_settlements (
        id SERIAL PRIMARY KEY,
        settlement_date VARCHAR(10) NOT NULL UNIQUE,
        income_total DECIMAL(12,2) DEFAULT 0,
        expense_total DECIMAL(12,2) DEFAULT 0,
        created_by_user_id INTEGER REFERENCES erp_users(id),
        settled_by VARCHAR(20) DEFAULT 'manual',
        notes TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )""",
]

if __name__ == '__main__':
    with engine.connect() as conn:
        for sql in MIGRATIONS:
            try:
                conn.execute(text(sql))
                print(f"OK: {sql[:60].strip()}...")
            except Exception as e:
                print(f"SKIP: {e}")
        conn.commit()
    print("Migration complete.")
