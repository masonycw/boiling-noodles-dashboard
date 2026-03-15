from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from erp.backend.db.session import get_db
from erp.backend.services import finance_service

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
