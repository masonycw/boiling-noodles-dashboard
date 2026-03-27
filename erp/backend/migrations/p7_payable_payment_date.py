"""
P7: 應付帳款新增 payment_date（實際付款日）欄位
"""
from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("""
        ALTER TABLE erp_accounts_payable
        ADD COLUMN IF NOT EXISTS payment_date TIMESTAMPTZ
    """))
    conn.commit()
    print("Migration p7_payable_payment_date done")
