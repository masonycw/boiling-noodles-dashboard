"""
Migration p9:
1. erp_petty_cash_records 新增 category_id 欄位（支援單筆修改科目）
2. erp_users 新增 petty_cash_access 欄位（若尚未存在）
"""
import sys
import os
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("""
        ALTER TABLE erp_petty_cash_records
        ADD COLUMN IF NOT EXISTS category_id INTEGER
        REFERENCES erp_cash_flow_categories(id) ON DELETE SET NULL;
    """))
    conn.execute(text("""
        ALTER TABLE erp_users
        ADD COLUMN IF NOT EXISTS petty_cash_access BOOLEAN DEFAULT FALSE;
    """))
    conn.commit()
    print("Migration p9 complete: petty_cash_records.category_id + users.petty_cash_access")
