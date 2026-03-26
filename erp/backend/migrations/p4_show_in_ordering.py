"""P4: Add show_in_ordering column to erp_vendors"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text(
            "ALTER TABLE erp_vendors ADD COLUMN IF NOT EXISTS show_in_ordering BOOLEAN DEFAULT FALSE"
        ))
        conn.commit()
        print("✓ show_in_ordering column added to erp_vendors")
    except Exception as e:
        print(f"Error: {e}")
