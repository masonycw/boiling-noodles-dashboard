"""
Migration: Add is_paid to erp_petty_cash_records
- is_paid BOOLEAN DEFAULT TRUE (existing records = already paid)
"""
import sys
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')

from erp.backend.db.session import engine
from sqlalchemy import text

def run():
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='erp_petty_cash_records' AND column_name='is_paid'
        """))
        if result.fetchone():
            print("Column is_paid already exists, skipping.")
            return

        conn.execute(text("""
            ALTER TABLE erp_petty_cash_records
            ADD COLUMN is_paid BOOLEAN NOT NULL DEFAULT TRUE
        """))
        conn.commit()
        print("Added is_paid column to erp_petty_cash_records (default TRUE for existing records)")

if __name__ == '__main__':
    run()
