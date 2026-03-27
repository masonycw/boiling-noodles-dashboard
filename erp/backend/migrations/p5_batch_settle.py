"""
P5: 零用金代收款批次結帳
- erp_petty_cash_records 新增 settled_at (結帳時間) 和 settlement_ref_id (合併付款紀錄 FK)
"""
from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text(
        "ALTER TABLE erp_petty_cash_records "
        "ADD COLUMN IF NOT EXISTS settled_at TIMESTAMPTZ"
    ))
    conn.execute(text(
        "ALTER TABLE erp_petty_cash_records "
        "ADD COLUMN IF NOT EXISTS settlement_ref_id INTEGER "
        "REFERENCES erp_petty_cash_records(id)"
    ))
    conn.commit()
    print("Migration p5_batch_settle done")
