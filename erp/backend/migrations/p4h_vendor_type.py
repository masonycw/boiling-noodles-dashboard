"""P4h: Add vendor_type to erp_vendors"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS vendor_type VARCHAR DEFAULT 'supplier'"))
        print("✓ vendor_type added to erp_vendors")
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
