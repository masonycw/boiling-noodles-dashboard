"""
Migration p11: 修正金流紀錄日期
- 零用金（source=petty_cash）的 transaction_date 應與對應零用金紀錄的 created_at 同步
- 用金額 + 創建時間接近比對，找到對應的 PettyCashRecord，更新 transaction_date
"""
import sys
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')

from erp.backend.db.session import SessionLocal
from erp.backend.db.models import PettyCashRecord, CashFlowRecord, PettyCashTypeEnum
from datetime import timezone

db = SessionLocal()

def naive(dt):
    if dt is None: return None
    return dt.replace(tzinfo=None) if hasattr(dt, 'tzinfo') and dt.tzinfo else dt

try:
    # 取得所有 petty_cash 來源的金流紀錄
    cf_records = db.query(CashFlowRecord).filter(
        CashFlowRecord.source == 'petty_cash'
    ).all()

    # 取得所有已付零用金支出
    petty_records = db.query(PettyCashRecord).filter(
        PettyCashRecord.type == PettyCashTypeEnum.expense,
        PettyCashRecord.is_paid == True,
    ).all()

    updated = 0
    for cf in cf_records:
        cf_time = naive(cf.transaction_date)
        if not cf_time:
            continue
        # 找金額相同、創建時間相近的零用金紀錄
        match = None
        for pr in petty_records:
            pr_time = naive(pr.created_at)
            if not pr_time:
                continue
            if abs(float(cf.amount) - float(pr.amount)) < 0.01:
                diff = abs((cf_time - pr_time).total_seconds())
                if diff < 5:  # 5秒內視為同一筆
                    match = pr
                    break
        if match:
            pr_time = naive(match.created_at)
            if cf_time != pr_time:
                cf.transaction_date = pr_time
                updated += 1

    db.commit()
    print(f"p11 complete: updated {updated} CashFlowRecord dates to match PettyCashRecord created_at")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    import traceback; traceback.print_exc()
finally:
    db.close()
