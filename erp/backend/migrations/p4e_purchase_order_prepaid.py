"""P4e: Add is_prepaid to erp_purchase_orders"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE erp_purchase_orders ADD COLUMN IF NOT EXISTS is_prepaid BOOLEAN DEFAULT FALSE"))
        print("✓ is_prepaid added to erp_purchase_orders")
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
