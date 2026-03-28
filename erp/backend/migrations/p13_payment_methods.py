"""
p13: 建立 erp_payment_methods 表格，並植入預設付款方式
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from erp.backend.db.session import engine, SessionLocal
from sqlalchemy import text

def run():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS erp_payment_methods (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                display_order INTEGER NOT NULL DEFAULT 999
            )
        """))
        conn.commit()
        print("✅ erp_payment_methods 表格建立完成")

    db = SessionLocal()
    try:
        from erp.backend.db.models import PaymentMethod
        defaults = [
            ("轉帳", 1),
            ("現金", 2),
            ("支票", 3),
            ("其他", 4),
        ]
        for name, order in defaults:
            if not db.query(PaymentMethod).filter(PaymentMethod.name == name).first():
                db.add(PaymentMethod(name=name, is_active=True, display_order=order))
        db.commit()
        total = db.query(PaymentMethod).count()
        print(f"✅ 預設付款方式植入完成，共 {total} 筆")
    finally:
        db.close()

if __name__ == "__main__":
    run()
