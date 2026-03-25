"""
Migration B-14: Add category varchar column to erp_cash_flow_recurring
The model previously only had category_id FK but the API sends category as a string.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text(
        "ALTER TABLE erp_cash_flow_recurring ADD COLUMN IF NOT EXISTS category VARCHAR;"
    ))
    conn.commit()
    print("Migration b14: added category VARCHAR column to erp_cash_flow_recurring ✓")
