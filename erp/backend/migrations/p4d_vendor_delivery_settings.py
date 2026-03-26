"""P4d: Add closed_days and closed_on_holidays to erp_vendors"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS closed_days JSONB DEFAULT NULL"))
        print("✓ closed_days added to erp_vendors")
        conn.execute(text("ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS closed_on_holidays BOOLEAN DEFAULT FALSE"))
        print("✓ closed_on_holidays added to erp_vendors")
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
