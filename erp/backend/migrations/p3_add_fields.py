"""P3 migration: add notification_settings and proportional_fee_rules tables"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from sqlalchemy import text
from erp.backend.db.session import engine

MIGRATIONS = [
    """CREATE TABLE IF NOT EXISTS erp_notification_settings (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES erp_users(id),
        notification_type VARCHAR(30) NOT NULL,
        is_enabled BOOLEAN DEFAULT TRUE,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        UNIQUE(user_id, notification_type)
    )""",
    """CREATE TABLE IF NOT EXISTS erp_proportional_fee_rules (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        category VARCHAR(30),
        calculation_basis VARCHAR(30),
        percentage DECIMAL(5,2) NOT NULL,
        settlement_period VARCHAR(30) DEFAULT 'monthly',
        is_active BOOLEAN DEFAULT TRUE,
        note TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    )""",
    # Fix: CashFlowRecurring model uses string category but table has category_id FK only
    "ALTER TABLE erp_cash_flow_recurring ADD COLUMN IF NOT EXISTS category VARCHAR(50)",
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
    print("P3 migration complete.")
