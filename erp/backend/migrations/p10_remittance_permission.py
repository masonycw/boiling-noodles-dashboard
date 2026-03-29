"""
p10: 新增 remittance 零用金類型 + User.remittance_permission 欄位
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

def run():
    with engine.begin() as conn:
        # 1. 在 PostgreSQL ENUM 加 remittance 值
        conn.execute(text("ALTER TYPE petty_cash_type_enum ADD VALUE IF NOT EXISTS 'remittance'"))
        print("✅ petty_cash_type_enum 新增 remittance")

        # 2. User 表加 remittance_permission 欄位
        conn.execute(text("""
            ALTER TABLE erp_users
            ADD COLUMN IF NOT EXISTS remittance_permission BOOLEAN DEFAULT FALSE
        """))
        print("✅ erp_users 新增 remittance_permission 欄位")

    print("Migration p10 完成")

if __name__ == '__main__':
    run()
