"""P4g: Make vendor_id nullable in erp_accounts_payable"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE erp_accounts_payable ALTER COLUMN vendor_id DROP NOT NULL"))
        print("✓ vendor_id is now nullable in erp_accounts_payable")
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
