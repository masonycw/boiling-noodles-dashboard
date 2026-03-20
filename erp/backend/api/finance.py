from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from erp.backend.db.session import get_db
from erp.backend.services import finance_service
from erp.backend.db.models import DailySettlement, PettyCashRecord
from sqlalchemy import extract
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
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return finance_service.get_petty_cash_records(
        db, days_limit=days_limit, type_filter=type, limit=limit
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
def list_categories(db: Session = Depends(get_db)):
    return finance_service.get_cash_flow_categories(db)


@router.get("/cash-flow")
def list_cash_flow(
    days_limit: Optional[int] = None,
    type: Optional[str] = None,
    category_id: Optional[int] = None,
    only_uncategorized: bool = False,
    limit: int = 200,
    db: Session = Depends(get_db)
):
    return finance_service.get_cash_flow_records(
        db,
        days_limit=days_limit,
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


@router.put("/accounts-payable/{payable_id}/pay")
def mark_paid(payable_id: int, db: Session = Depends(get_db)):
    user_id = 1  # TODO: 從 JWT 取得
    try:
        return finance_service.mark_payable_paid(db, payable_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# 日結 Endpoints（P2-3）
# ─────────────────────────────────────────────

class DailySettlementCreate(BaseModel):
    income_total: float
    expense_total: float


@router.get("/daily-settlement/today")
def get_today_settlement(db: Session = Depends(get_db)):
    today = date.today().isoformat()
    settlement = db.query(DailySettlement).filter(
        DailySettlement.settlement_date == today
    ).first()
    if not settlement:
        return {"settled": False, "settlement_date": today}
    return {
        "settled": True,
        "settlement_date": settlement.settlement_date,
        "income_total": float(settlement.income_total or 0),
        "expense_total": float(settlement.expense_total or 0),
        "settled_by": settlement.settled_by,
        "created_at": settlement.created_at,
    }


@router.post("/daily-settlement")
def create_daily_settlement(data: DailySettlementCreate, db: Session = Depends(get_db)):
    user_id = 1  # TODO: 從 JWT 取得
    today = date.today().isoformat()

    existing = db.query(DailySettlement).filter(
        DailySettlement.settlement_date == today
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="今日已完成日結")

    settlement = DailySettlement(
        settlement_date=today,
        income_total=data.income_total,
        expense_total=data.expense_total,
        created_by_user_id=user_id,
        settled_by="manual",
    )
    db.add(settlement)

    # Lock today's petty cash records
    db.query(PettyCashRecord).filter(
        extract('year', PettyCashRecord.created_at) == date.today().year,
        extract('month', PettyCashRecord.created_at) == date.today().month,
        extract('day', PettyCashRecord.created_at) == date.today().day,
    ).update({"note": PettyCashRecord.note})  # no-op update to avoid schema issue

    db.commit()
    db.refresh(settlement)
    return {
        "settled": True,
        "settlement_date": settlement.settlement_date,
        "income_total": float(settlement.income_total or 0),
        "expense_total": float(settlement.expense_total or 0),
        "created_at": settlement.created_at,
    }


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
    from erp.backend.db.models import PettyCashRecord, AccountsPayable, CashFlowRecurring
    from sqlalchemy import func as sqlfunc
    import calendar

    today = date.today()
    month_start = today.replace(day=1)

    # 本月收入（零用金收入記錄）
    income_total = db.query(sqlfunc.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == 'income',
        PettyCashRecord.created_at >= month_start,
    ).scalar() or 0

    # 本月支出（零用金支出+提領）
    expense_total = db.query(sqlfunc.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type.in_(['expense', 'withdrawal']),
        PettyCashRecord.created_at >= month_start,
    ).scalar() or 0

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
        "month_income": float(income_total),
        "month_expense": float(expense_total),
        "projected_net": float(income_total) - float(expense_total),
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
