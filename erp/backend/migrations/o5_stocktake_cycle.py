import sys
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')
from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("""
        ALTER TABLE erp_stocktake_groups
        ADD COLUMN IF NOT EXISTS stocktake_cycle_days INT DEFAULT NULL,
        ADD COLUMN IF NOT EXISTS next_stocktake_due DATE DEFAULT NULL
    """))
    conn.commit()
    print("O5 migration complete: added stocktake_cycle_days + next_stocktake_due to erp_stocktake_groups")
