"""
Migration p10: 補建金流紀錄
將過去所有 is_paid=True 的零用金支出（expense），
若沒有對應的 CashFlowRecord（source=petty_cash），補建一筆進入金流。
避免重複建立：已有對應金流（source=petty_cash）的不重複建立。
"""
import sys
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')

from erp.backend.db.session import SessionLocal
from erp.backend.db.models import PettyCashRecord, CashFlowRecord, CashFlowCategory, Vendor, PettyCashTypeEnum
from sqlalchemy import text
from datetime import datetime

db = SessionLocal()

try:
    # 找出所有 is_paid=True 的 expense 紀錄
    paid_expenses = db.query(PettyCashRecord).filter(
        PettyCashRecord.type == PettyCashTypeEnum.expense,
        PettyCashRecord.is_paid == True,
    ).order_by(PettyCashRecord.id).all()

    print(f"Found {len(paid_expenses)} paid expense records")

    # 找出已有的 petty_cash 金流紀錄（用 created_at 區間比對不準，改用 description + amount）
    existing_cf = db.query(CashFlowRecord).filter(
        CashFlowRecord.source == 'petty_cash'
    ).all()

    created_count = 0
    skipped_count = 0

    for rec in paid_expenses:
        # 取廠商預設科目
        category_id = getattr(rec, 'category_id', None)
        if not category_id and rec.vendor_id:
            vdr = db.query(Vendor).filter(Vendor.id == rec.vendor_id).first()
            if vdr and vdr.default_category_id:
                category_id = vdr.default_category_id

        # 用 created_at 精確比對：同時間、同金額、同來源的金流紀錄視為已存在
        def naive(dt):
            if dt is None: return None
            return dt.replace(tzinfo=None) if hasattr(dt, 'tzinfo') and dt.tzinfo else dt

        rec_time = naive(rec.created_at)
        dup = next((cf for cf in existing_cf
                    if abs(float(cf.amount) - float(rec.amount)) < 0.01
                    and cf.transaction_date
                    and rec_time
                    and abs((naive(cf.transaction_date) - rec_time).total_seconds()) < 60
                    ), None)

        if dup:
            skipped_count += 1
            continue

        cf = CashFlowRecord(
            user_id=rec.user_id,
            category_id=category_id,
            amount=rec.amount,
            type="expense",
            source="petty_cash",
            description=rec.note,
            vendor_id=rec.vendor_id,
            is_categorized=category_id is not None,
            transaction_date=rec.created_at,
        )
        db.add(cf)
        existing_cf.append(cf)  # 更新已知列表，避免同一批次重複
        created_count += 1

    db.commit()
    print(f"Backfill complete: {created_count} CashFlowRecords created, {skipped_count} skipped (already exist)")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    import traceback; traceback.print_exc()
finally:
    db.close()
