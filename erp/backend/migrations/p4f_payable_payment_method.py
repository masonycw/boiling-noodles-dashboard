"""P4f: Add payment_method to erp_accounts_payable"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE erp_accounts_payable ADD COLUMN IF NOT EXISTS payment_method VARCHAR DEFAULT NULL"))
        print("✓ payment_method added to erp_accounts_payable")
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
