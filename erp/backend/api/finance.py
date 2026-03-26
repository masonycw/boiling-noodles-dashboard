from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from erp.backend.db.session import get_db
from erp.backend.services import finance_service
from erp.backend.db.models import DailySettlement, PettyCashRecord, User
from erp.backend.api.auth import get_current_user
from sqlalchemy import extract, desc
from datetime import date, datetime

router = APIRouter(prefix="/finance", tags=["finance"])


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────

class PettyCashCreate(BaseModel):
    type: str                              # income / expense / withdrawal
    amount: float
    note: Optional[str] = None
    photo_url: Optional[str] = None
    vendor_id: Optional[int] = None
    order_id: Optional[int] = None
    is_paid: bool = True                   # False = 待付帳款，不計入零用金餘額


class CashFlowCreate(BaseModel):
    type: str                              # income / expense
    amount: float
    category_id: Optional[int] = None
    description: Optional[str] = None
    vendor_id: Optional[int] = None
    source: str = "manual"


class CashFlowCategoryUpdate(BaseModel):
    category_id: int


# ─────────────────────────────────────────────
# 舊版相容 Endpoints（Phase 2）
# ─────────────────────────────────────────────

@router.get("/transactions")
def list_transactions(days_limit: Optional[int] = None, db: Session = Depends(get_db)):
    return finance_service.get_transactions(db, days_limit=days_limit)


@router.get("/balance")
def get_current_balance(db: Session = Depends(get_db)):
    return {"balance": finance_service.get_balance(db)}


@router.post("/transactions")
def create_transaction(tx: dict, db: Session = Depends(get_db)):
    user_id = 1  # TODO: 從 JWT 取得
    return finance_service.create_transaction(db, user_id, tx)


# ─────────────────────────────────────────────
# 零用金 Endpoints（Phase 3）
# ─────────────────────────────────────────────

@router.get("/petty-cash/balance")
def get_petty_cash_balance(db: Session = Depends(get_db)):
    balance = finance_service.get_petty_cash_balance(db)
    return {"balance": balance}


@router.get("/petty-cash")
def list_petty_cash(
    days_limit: Optional[int] = None,
    type: Optional[str] = None,
    date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_paid: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return finance_service.get_petty_cash_records(
        db, days_limit=days_limit, type_filter=type, date_filter=date,
        date_from=date_from, date_to=date_to, is_paid=is_paid, limit=limit
    )


@router.post("/petty-cash")
def create_petty_cash(data: PettyCashCreate, db: Session = Depends(get_db)):
    user_id = 1  # TODO: 從 JWT 取得
    try:
        return finance_service.create_petty_cash_record(db, user_id, data.dict())
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/petty-cash/{record_id}")
def get_petty_cash_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(PettyCashRecord).filter(PettyCashRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return {
        "id": record.id,
        "type": record.type,
        "amount": float(record.amount or 0),
        "note": record.note,
        "vendor_id": record.vendor_id,
        "is_paid": record.is_paid,
        "created_at": record.created_at,
        "attachments": [],
    }


@router.patch("/petty-cash/{record_id}")
def patch_petty_cash(record_id: int, data: dict, db: Session = Depends(get_db)):
    record = db.query(PettyCashRecord).filter(PettyCashRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    for key in ['type', 'amount', 'note', 'vendor_id', 'is_paid']:
        if key in data:
            setattr(record, key, data[key])
    if 'recorded_at' in data:
        from datetime import datetime as dt
        try:
            record.created_at = dt.fromisoformat(data['recorded_at'])
        except Exception:
            pass
    db.commit()
    return {"success": True}


@router.patch("/petty-cash/{record_id}/toggle-payment")
def toggle_petty_cash_payment(record_id: int, db: Session = Depends(get_db)):
    """切換零用金紀錄的付款狀態（已付 ↔ 待付）"""
    try:
        return finance_service.toggle_petty_cash_payment(db, record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/petty-cash/{record_id}")
def delete_petty_cash(record_id: int, db: Session = Depends(get_db)):
    record = db.query(PettyCashRecord).filter(PettyCashRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    db.commit()
    return {"success": True}


# ─────────────────────────────────────────────
# 金流管理 Endpoints（Phase 3）
# ─────────────────────────────────────────────

@router.get("/cash-flow/categories")
def list_categories(include_inactive: bool = False, db: Session = Depends(get_db)):
    return finance_service.get_cash_flow_categories(db, include_inactive=include_inactive)


class CategoryCreate(BaseModel):
    name: str
    type: str = "expense"
    is_active: bool = True


@router.post("/cash-flow/categories")
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowCategory
    cat = CashFlowCategory(name=data.name, type=data.type, is_active=data.is_active)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "type": cat.type, "is_active": cat.is_active}


@router.put("/cash-flow/categories/{cat_id}")
def update_category(cat_id: int, data: CategoryCreate, db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowCategory
    cat = db.query(CashFlowCategory).filter(CashFlowCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="科目不存在")
    cat.name = data.name
    cat.type = data.type
    cat.is_active = data.is_active
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "type": cat.type, "is_active": cat.is_active}


@router.delete("/cash-flow/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowCategory
    cat = db.query(CashFlowCategory).filter(CashFlowCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="科目不存在")
    db.delete(cat)
    db.commit()
    return {"success": True}


@router.get("/cash-flow")
def list_cash_flow(
    days_limit: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    type: Optional[str] = None,
    category_id: Optional[int] = None,
    only_uncategorized: bool = False,
    limit: int = 200,
    db: Session = Depends(get_db)
):
    return finance_service.get_cash_flow_records(
        db,
        days_limit=days_limit,
        date_from=date_from,
        date_to=date_to,
        type_filter=type,
        category_id=category_id,
        only_uncategorized=only_uncategorized,
        limit=limit
    )


@router.post("/cash-flow")
def create_cash_flow(data: CashFlowCreate, db: Session = Depends(get_db)):
    user_id = 1  # TODO: 從 JWT 取得
    return finance_service.create_cash_flow_record(db, user_id, data.dict())


@router.put("/cash-flow/{record_id}/category")
def update_cash_flow_category(
    record_id: int,
    data: CashFlowCategoryUpdate,
    db: Session = Depends(get_db)
):
    try:
        return finance_service.update_cash_flow_category(db, record_id, data.category_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/cash-flow/summary/{year}/{month}")
def get_monthly_summary(year: int, month: int, db: Session = Depends(get_db)):
    return finance_service.get_cash_flow_monthly_summary(db, year, month)


class CashFlowUpdate(BaseModel):
    amount: Optional[float] = None
    type: Optional[str] = None
    category_id: Optional[int] = None
    description: Optional[str] = None
    transaction_date: Optional[str] = None

@router.put("/cash-flow/{record_id}")
def update_cash_flow(record_id: int, data: CashFlowUpdate, db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowRecord
    record = db.query(CashFlowRecord).filter(CashFlowRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if data.amount is not None:
        record.amount = data.amount
    if data.type is not None:
        record.type = data.type
    if data.category_id is not None:
        record.category_id = data.category_id
        record.is_categorized = True
    if data.description is not None:
        record.description = data.description
    if data.transaction_date is not None:
        try:
            record.transaction_date = datetime.fromisoformat(data.transaction_date)
        except Exception:
            pass
    db.commit()
    db.refresh(record)
    return finance_service._format_cash_flow(record, db)

@router.delete("/cash-flow/{record_id}")
def delete_cash_flow(record_id: int, db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowRecord
    record = db.query(CashFlowRecord).filter(CashFlowRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    db.commit()
    return {"success": True}


# ─────────────────────────────────────────────
# 應付帳款 Endpoints（Phase 3）
# ─────────────────────────────────────────────

@router.get("/accounts-payable")
def list_accounts_payable(
    vendor_id: Optional[int] = None,
    is_paid: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return finance_service.get_accounts_payable(
        db, vendor_id=vendor_id, is_paid=is_paid, limit=limit
    )


class PayablePayBody(BaseModel):
    payment_method: Optional[str] = None

@router.put("/accounts-payable/{payable_id}/pay")
def mark_paid(payable_id: int, body: PayablePayBody = PayablePayBody(), db: Session = Depends(get_db)):
    user_id = 1
    try:
        return finance_service.mark_payable_paid(db, payable_id, user_id, body.payment_method)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/accounts-payable/{payable_id}/unpay")
def mark_unpaid(payable_id: int, db: Session = Depends(get_db)):
    from erp.backend.db.models import AccountsPayable
    p = db.query(AccountsPayable).filter(AccountsPayable.id == payable_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    p.is_paid = False
    p.paid_at = None
    p.paid_by_user_id = None
    p.payment_method = None
    db.commit()
    return {"success": True}

class PayablePatch(BaseModel):
    due_date: Optional[str] = None
    note: Optional[str] = None

@router.patch("/accounts-payable/{payable_id}")
def patch_payable(payable_id: int, data: PayablePatch, db: Session = Depends(get_db)):
    from erp.backend.db.models import AccountsPayable
    from datetime import datetime as dt
    p = db.query(AccountsPayable).filter(AccountsPayable.id == payable_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Not found")
    if data.due_date is not None:
        try:
            p.due_date = dt.fromisoformat(data.due_date)
        except Exception:
            pass
    if data.note is not None:
        p.note = data.note
    db.commit()
    return {"success": True}


# ─────────────────────────────────────────────
# 日結 Endpoints（P2-3）
# ─────────────────────────────────────────────

class DailySettlementCreate(BaseModel):
    income_total: float
    expense_total: float
    closing_balance: Optional[float] = None


def _fmt_settlement(s: DailySettlement, db: Session) -> dict:
    settled_by_name = None
    if s.settled_by_user_id:
        u = db.query(User).filter(User.id == s.settled_by_user_id).first()
        if u:
            settled_by_name = u.full_name or u.username
    return {
        "id": s.id,
        "settled": True,
        "settlement_date": s.settlement_date,
        "settlement_number": s.settlement_number or 1,
        "income_total": float(s.income_total or 0),
        "expense_total": float(s.expense_total or 0),
        "closing_balance": float(s.closing_balance) if s.closing_balance is not None else None,
        "settled_by_name": settled_by_name,
        "settled_at": s.created_at,
        "created_at": s.created_at,
    }


@router.get("/daily-settlement/can-settle")
def can_settle(db: Session = Depends(get_db)):
    """O3: 判斷今日是否可再次日結（有新紀錄才允許）"""
    from erp.backend.db.models import PettyCashRecord
    today = date.today().isoformat()

    last = db.query(DailySettlement).filter(
        DailySettlement.settlement_date == today
    ).order_by(desc(DailySettlement.created_at)).first()

    if not last:
        # 今天未曾日結，只要今天有任何零用金紀錄即可日結
        today_start = datetime.combine(date.today(), datetime.min.time())
        has_records = db.query(PettyCashRecord).filter(
            PettyCashRecord.created_at >= today_start
        ).first() is not None
        return {"can_settle": has_records, "reason": "no_settlement_today"}

    # 有日結記錄，檢查日結後是否有新的零用金紀錄
    new_records = db.query(PettyCashRecord).filter(
        PettyCashRecord.created_at > last.created_at
    ).first()
    return {
        "can_settle": new_records is not None,
        "reason": "new_records_after_last_settlement" if new_records else "no_new_records"
    }


@router.get("/daily-settlement/today")
def get_today_settlement(db: Session = Depends(get_db)):
    """O3: 回傳今日所有日結（陣列），前端可處理多次日結"""
    today = date.today().isoformat()
    settlements = db.query(DailySettlement).filter(
        DailySettlement.settlement_date == today
    ).order_by(DailySettlement.created_at).all()

    if not settlements:
        return {"settled": False, "settlement_date": today}

    return [_fmt_settlement(s, db) for s in settlements]


@router.post("/daily-settlement")
def create_daily_settlement(
    data: DailySettlementCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """O3: 執行日結（允許每天多次，自動計算 settlement_number）"""
    today = date.today().isoformat()

    # 計算今天第幾次日結
    count = db.query(DailySettlement).filter(
        DailySettlement.settlement_date == today
    ).count()
    settlement_number = count + 1

    settlement = DailySettlement(
        settlement_date=today,
        income_total=data.income_total,
        expense_total=data.expense_total,
        settlement_number=settlement_number,
        closing_balance=data.closing_balance,
        settled_by_user_id=current_user.id,
        created_by_user_id=current_user.id,
        settled_by="manual",
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return _fmt_settlement(settlement, db)


@router.delete("/daily-settlement/{settlement_id}")
def delete_daily_settlement(settlement_id: int, db: Session = Depends(get_db)):
    settlement = db.query(DailySettlement).filter(DailySettlement.id == settlement_id).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    db.delete(settlement)
    db.commit()
    return {"success": True}


# ─────────────────────────────────────────────
# P3-1: 金流總覽
# ─────────────────────────────────────────────

@router.get("/overview")
def get_finance_overview(db: Session = Depends(get_db)):
    from erp.backend.db.models import PettyCashRecord, AccountsPayable, CashFlowRecurring, CashFlowRecord
    from sqlalchemy import func as sqlfunc
    import calendar

    today = date.today()
    month_start = today.replace(day=1)

    # 正式金流收入（業務收入，不含零用金帳戶轉移）
    business_income = db.query(sqlfunc.sum(CashFlowRecord.amount)).filter(
        CashFlowRecord.type == 'income',
        CashFlowRecord.transaction_date >= month_start,
    ).scalar() or 0

    # 正式金流支出
    business_expense = db.query(sqlfunc.sum(CashFlowRecord.amount)).filter(
        CashFlowRecord.type == 'expense',
        CashFlowRecord.transaction_date >= month_start,
    ).scalar() or 0

    # 零用金支出（採購等實際支出，已付款）
    petty_expense = db.query(sqlfunc.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == 'expense',
        PettyCashRecord.is_paid == True,
        PettyCashRecord.created_at >= month_start,
    ).scalar() or 0

    # 零用金收入（帳戶轉入，屬帳戶間轉移，不計入業務收入）
    petty_income = db.query(sqlfunc.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == 'income',
        PettyCashRecord.created_at >= month_start,
    ).scalar() or 0

    # 零用金提領（帳戶轉出，屬帳戶間轉移，不計入業務支出）
    petty_withdrawal = db.query(sqlfunc.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == 'withdrawal',
        PettyCashRecord.created_at >= month_start,
    ).scalar() or 0

    income_total = float(business_income)
    expense_total = float(business_expense) + float(petty_expense)

    # 零用金餘額
    from erp.backend.services.finance_service import get_petty_cash_balance
    balance = get_petty_cash_balance(db)

    # 應付帳款（未付）
    payable_count = db.query(AccountsPayable).filter(AccountsPayable.is_paid == False).count()
    payable_amount = db.query(sqlfunc.sum(AccountsPayable.amount)).filter(AccountsPayable.is_paid == False).scalar() or 0

    # 本月有效重複預約
    recurring_active = db.query(CashFlowRecurring).filter(CashFlowRecurring.is_active == True, CashFlowRecurring.type == 'expense').all()
    recurring_total = sum(float(r.amount or 0) for r in recurring_active)
    recurring_count = len(recurring_active)

    return {
        "month_income": income_total,
        "month_expense": expense_total,
        "projected_net": income_total - expense_total,
        "petty_cash_income": float(petty_income),
        "petty_cash_withdrawal": float(petty_withdrawal),
        "petty_cash_balance": float(balance),
        "payable_count": payable_count,
        "payable_amount": float(payable_amount),
        "recurring_expense_total": recurring_total,
        "recurring_expense_count": recurring_count,
    }


# ─────────────────────────────────────────────
# P3-1: 重複預約費用 CRUD
# ─────────────────────────────────────────────

class RecurringCreate(BaseModel):
    name: str
    category: Optional[str] = None
    amount: float
    type: str = "expense"
    day_of_month: Optional[int] = None
    vendor_id: Optional[int] = None
    note: Optional[str] = None


@router.get("/recurring")
def list_recurring(db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowRecurring, Vendor
    items = db.query(CashFlowRecurring).order_by(CashFlowRecurring.id).all()
    result = []
    for r in items:
        vendor = db.query(Vendor).filter(Vendor.id == r.vendor_id).first() if r.vendor_id else None
        result.append({
            "id": r.id,
            "name": r.name,
            "category": r.category,
            "amount": float(r.amount or 0),
            "type": r.type,
            "day_of_month": r.day_of_month,
            "vendor_id": r.vendor_id,
            "vendor_name": vendor.name if vendor else None,
            "note": r.note,
            "is_active": r.is_active,
        })
    return result


@router.post("/recurring")
def create_recurring(data: RecurringCreate, db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowRecurring
    rec = CashFlowRecurring(**data.dict())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "name": rec.name, "is_active": rec.is_active}


@router.put("/recurring/{rec_id}")
def update_recurring(rec_id: int, data: RecurringCreate, db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowRecurring
    rec = db.query(CashFlowRecurring).filter(CashFlowRecurring.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="重複預約不存在")
    for k, v in data.dict().items():
        setattr(rec, k, v)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "name": rec.name}


@router.delete("/recurring/{rec_id}")
def delete_recurring(rec_id: int, db: Session = Depends(get_db)):
    from erp.backend.db.models import CashFlowRecurring
    rec = db.query(CashFlowRecurring).filter(CashFlowRecurring.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="重複預約不存在")
    rec.is_active = False
    db.commit()
    return {"ok": True}


class GeneratePayableBody(BaseModel):
    due_date: Optional[str] = None   # YYYY-MM-DD；留空時自動計算 day_of_month


@router.post("/recurring/{rec_id}/generate-payable")
def generate_recurring_payable(rec_id: int, body: GeneratePayableBody = GeneratePayableBody(), db: Session = Depends(get_db)):
    """B-12: 將重複預約轉為應付帳款"""
    from erp.backend.db.models import CashFlowRecurring, AccountsPayable as AP
    from datetime import datetime as dt
    import calendar

    rec = db.query(CashFlowRecurring).filter(CashFlowRecurring.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="重複預約不存在")

    # 計算到期日
    if body.due_date:
        due = dt.fromisoformat(body.due_date)
    elif rec.day_of_month:
        today = date.today()
        max_day = calendar.monthrange(today.year, today.month)[1]
        due = today.replace(day=min(rec.day_of_month, max_day))
    else:
        due = None

    payable = AP(
        vendor_id=rec.vendor_id,
        amount=rec.amount or 0,
        due_date=due,
        note=rec.name,
        is_paid=False,
    )
    db.add(payable)
    db.commit()
    db.refresh(payable)
    return finance_service._format_payable(payable, db)


# ─────────────────────────────────────────────
# P3-1: 比例費用規則 CRUD
# ─────────────────────────────────────────────

class ProportionalFeeCreate(BaseModel):
    name: str
    category: Optional[str] = None
    calculation_basis: Optional[str] = None
    percentage: float
    settlement_period: str = "monthly"
    note: Optional[str] = None


@router.get("/proportional-fees")
def list_proportional_fees(db: Session = Depends(get_db)):
    from erp.backend.db.models import ProportionalFeeRule
    rules = db.query(ProportionalFeeRule).filter(ProportionalFeeRule.is_active == True).all()
    return [{"id": r.id, "name": r.name, "category": r.category,
             "calculation_basis": r.calculation_basis, "percentage": float(r.percentage),
             "settlement_period": r.settlement_period, "note": r.note} for r in rules]


@router.post("/proportional-fees")
def create_proportional_fee(data: ProportionalFeeCreate, db: Session = Depends(get_db)):
    from erp.backend.db.models import ProportionalFeeRule
    rule = ProportionalFeeRule(**data.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "name": rule.name}


@router.put("/proportional-fees/{rule_id}")
def update_proportional_fee(rule_id: int, data: ProportionalFeeCreate, db: Session = Depends(get_db)):
    from erp.backend.db.models import ProportionalFeeRule
    rule = db.query(ProportionalFeeRule).filter(ProportionalFeeRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="費率規則不存在")
    for k, v in data.dict().items():
        setattr(rule, k, v)
    db.commit()
    return {"id": rule.id, "name": rule.name}


@router.delete("/proportional-fees/{rule_id}")
def delete_proportional_fee(rule_id: int, db: Session = Depends(get_db)):
    from erp.backend.db.models import ProportionalFeeRule
    rule = db.query(ProportionalFeeRule).filter(ProportionalFeeRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="費率規則不存在")
    rule.is_active = False
    db.commit()
    return {"ok": True}
