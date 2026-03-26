"""P4c: Add ordering schedule to vendors + stocktake_time to groups"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS is_fixed_order BOOLEAN DEFAULT FALSE"))
        print("✓ is_fixed_order added to erp_vendors")
        conn.execute(text("ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS order_days JSONB DEFAULT NULL"))
        print("✓ order_days added to erp_vendors")
        conn.execute(text("ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS order_time VARCHAR(5) DEFAULT NULL"))
        print("✓ order_time added to erp_vendors")
        conn.execute(text("ALTER TABLE erp_stocktake_groups ADD COLUMN IF NOT EXISTS stocktake_time VARCHAR(5) DEFAULT NULL"))
        print("✓ stocktake_time added to erp_stocktake_groups")
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
