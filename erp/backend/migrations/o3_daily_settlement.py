"""
O3 Migration: 金流日結結構修正
- 移除 settlement_date UNIQUE constraint（允許每天多次日結）
- 新增 settlement_number（第 N 次）
- 新增 closing_balance（結算時餘額）
- 新增 settled_by_user_id（執行人 FK）
"""
import sys
import os
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')
os.environ.setdefault('PYTHONPATH', '/home/mason_ycw/boiling-noodles-dashboard')

from erp.backend.db.session import engine
from sqlalchemy import text

def run():
    with engine.connect() as conn:
        # 1. 移除 UNIQUE constraint
        conn.execute(text("""
            ALTER TABLE erp_daily_settlements
            DROP CONSTRAINT IF EXISTS erp_daily_settlements_settlement_date_key
        """))
        print("✅ Dropped UNIQUE constraint on settlement_date")

        # 2. 新增 settlement_number
        conn.execute(text("""
            ALTER TABLE erp_daily_settlements
            ADD COLUMN IF NOT EXISTS settlement_number INT DEFAULT 1
        """))
        print("✅ Added settlement_number")

        # 3. 新增 closing_balance
        conn.execute(text("""
            ALTER TABLE erp_daily_settlements
            ADD COLUMN IF NOT EXISTS closing_balance DECIMAL(12,2)
        """))
        print("✅ Added closing_balance")

        # 4. 新增 settled_by_user_id
        conn.execute(text("""
            ALTER TABLE erp_daily_settlements
            ADD COLUMN IF NOT EXISTS settled_by_user_id INT REFERENCES erp_users(id)
        """))
        print("✅ Added settled_by_user_id")

        conn.commit()
        print("\n✅ O3 migration complete")

        # 驗證
        r = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='erp_daily_settlements' ORDER BY ordinal_position"
        ))
        print("Columns:", [row[0] for row in r])

if __name__ == '__main__':
    run()
