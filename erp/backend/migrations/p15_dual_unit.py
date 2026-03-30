"""
p15: 新增品項雙單位與顯示模式欄位
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

def run():
    with engine.begin() as conn:
        # 新增欄位
        conn.execute(text("""
            ALTER TABLE erp_items
            ADD COLUMN IF NOT EXISTS order_unit_mode VARCHAR DEFAULT 'both'
        """))
        print("✅ erp_items 新增 order_unit_mode")

        conn.execute(text("""
            ALTER TABLE erp_items
            ADD COLUMN IF NOT EXISTS stocktake_unit_mode VARCHAR DEFAULT 'both'
        """))
        print("✅ erp_items 新增 stocktake_unit_mode")

    print("Migration p15 完成")

if __name__ == '__main__':
    run()
