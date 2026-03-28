"""
Migration p12: 重建 source=petty_cash 的金流紀錄
- 刪除所有 source='petty_cash' 的 CashFlowRecord
- 從所有 is_paid=True, type=expense 的 PettyCashRecord 重新建立
- transaction_date 使用 rec.created_at（零用金本身日期），修正舊資料全顯示 3/27 的問題
- 同時補上透過 PATCH 改為已付但沒有金流紀錄的情況
"""
import sys
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')

from erp.backend.db.session import SessionLocal
from erp.backend.db.models import PettyCashRecord, CashFlowRecord, Vendor, PettyCashTypeEnum
from datetime import timezone

db = SessionLocal()

def naive(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if hasattr(dt, 'tzinfo') and dt.tzinfo else dt

try:
    # 刪除所有 source=petty_cash 的金流紀錄
    deleted = db.query(CashFlowRecord).filter(CashFlowRecord.source == 'petty_cash').delete()
    print(f"Deleted {deleted} existing petty_cash CashFlowRecords")

    # 取得所有已付零用金支出
    paid_expenses = db.query(PettyCashRecord).filter(
        PettyCashRecord.type == PettyCashTypeEnum.expense,
        PettyCashRecord.is_paid == True,
    ).order_by(PettyCashRecord.id).all()

    print(f"Found {len(paid_expenses)} paid expense records to rebuild")

    created_count = 0
    for rec in paid_expenses:
        # 取科目：優先用紀錄本身 category_id，fallback 廠商預設
        category_id = getattr(rec, 'category_id', None)
        if not category_id and rec.vendor_id:
            vdr = db.query(Vendor).filter(Vendor.id == rec.vendor_id).first()
            if vdr and vdr.default_category_id:
                category_id = vdr.default_category_id

        cf = CashFlowRecord(
            user_id=rec.user_id,
            category_id=category_id,
            amount=rec.amount,
            type="expense",
            source="petty_cash",
            description=rec.note,
            vendor_id=rec.vendor_id,
            is_categorized=category_id is not None,
            transaction_date=naive(rec.created_at),  # 零用金本身日期
        )
        db.add(cf)
        created_count += 1

    db.commit()
    print(f"p12 complete: created {created_count} CashFlowRecords with correct dates")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    import traceback; traceback.print_exc()
finally:
    db.close()
