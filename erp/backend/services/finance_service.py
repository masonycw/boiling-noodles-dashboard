from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import Optional, List
from erp.backend.db.models import (
    CashTransaction, AuditLog,
    PettyCashRecord, PettyCashTypeEnum,
    CashFlowRecord, CashFlowCategory, CashFlowRecurring,
    AccountsPayable, User
)


# ─────────────────────────────────────────────
# 舊版 CashTransaction（Phase 2 相容）
# ─────────────────────────────────────────────

def get_transactions(db: Session, skip: int = 0, limit: int = 100, days_limit: int = None):
    query = db.query(CashTransaction)
    if days_limit is not None:
        cutoff_date = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(CashTransaction.created_at >= cutoff_date)
    return query.order_by(desc(CashTransaction.created_at)).offset(skip).limit(limit).all()


def create_transaction(db: Session, user_id: int, tx_in: dict):
    db_tx = CashTransaction(
        user_id=user_id,
        amount=tx_in['amount'],
        type=tx_in['type'],
        category=tx_in.get('category'),
        note=tx_in.get('note'),
        order_id=tx_in.get('order_id')
    )
    db.add(db_tx)
    audit = AuditLog(
        user_id=user_id,
        action=f"CASH_{tx_in['type'].upper()}",
        resource="cash_transaction",
        details={"amount": tx_in['amount'], "category": tx_in.get('category')}
    )
    db.add(audit)
    db.commit()
    db.refresh(db_tx)
    return db_tx


# ─────────────────────────────────────────────
# 零用金（Phase 3）
# ─────────────────────────────────────────────

def get_petty_cash_balance(db: Session) -> float:
    """計算零用金餘額 = 收入 - 支出 - 提領"""
    income = db.query(func.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == PettyCashTypeEnum.income
    ).scalar() or 0

    expense = db.query(func.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == PettyCashTypeEnum.expense
    ).scalar() or 0

    withdrawal = db.query(func.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == PettyCashTypeEnum.withdrawal
    ).scalar() or 0

    return float(income - expense - withdrawal)


def get_petty_cash_records(
    db: Session,
    days_limit: Optional[int] = None,
    type_filter: Optional[str] = None,
    limit: int = 100
) -> List[dict]:
    query = db.query(PettyCashRecord).order_by(desc(PettyCashRecord.created_at))

    if days_limit:
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(PettyCashRecord.created_at >= cutoff)
    if type_filter:
        query = query.filter(PettyCashRecord.type == type_filter)

    records = query.limit(limit).all()
    return [_format_petty_cash(r, db) for r in records]


def create_petty_cash_record(db: Session, user_id: int, data: dict) -> dict:
    """
    data: { type, amount, note, photo_url, vendor_id, order_id }
    提領（withdrawal）時需要 petty_cash_permission = True
    """
    # 驗證提領權限
    if data.get("type") == "withdrawal":
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.petty_cash_permission:
            raise PermissionError("此帳號無提領授權")

    record = PettyCashRecord(
        user_id=user_id,
        type=data["type"],
        amount=data["amount"],
        note=data.get("note"),
        photo_url=data.get("photo_url"),
        vendor_id=data.get("vendor_id"),
        order_id=data.get("order_id")
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _format_petty_cash(record, db)


# ─────────────────────────────────────────────
# 金流管理（Phase 3）
# ─────────────────────────────────────────────

def get_cash_flow_categories(db: Session) -> List[dict]:
    cats = db.query(CashFlowCategory).filter(
        CashFlowCategory.is_active == True
    ).order_by(CashFlowCategory.type, CashFlowCategory.display_order).all()
    return [{"id": c.id, "name": c.name, "type": c.type} for c in cats]


def get_cash_flow_records(
    db: Session,
    days_limit: Optional[int] = None,
    type_filter: Optional[str] = None,
    category_id: Optional[int] = None,
    only_uncategorized: bool = False,
    limit: int = 200
) -> List[dict]:
    query = db.query(CashFlowRecord).order_by(desc(CashFlowRecord.created_at))

    if days_limit:
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(CashFlowRecord.created_at >= cutoff)
    if type_filter:
        query = query.filter(CashFlowRecord.type == type_filter)
    if category_id:
        query = query.filter(CashFlowRecord.category_id == category_id)
    if only_uncategorized:
        query = query.filter(CashFlowRecord.is_categorized == False)

    records = query.limit(limit).all()
    return [_format_cash_flow(r, db) for r in records]


def create_cash_flow_record(db: Session, user_id: int, data: dict) -> dict:
    record = CashFlowRecord(
        user_id=user_id,
        category_id=data.get("category_id"),
        amount=data["amount"],
        type=data["type"],
        source=data.get("source", "manual"),
        description=data.get("description"),
        vendor_id=data.get("vendor_id"),
        is_categorized=data.get("category_id") is not None,
        transaction_date=data.get("transaction_date") or datetime.utcnow()
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _format_cash_flow(record, db)


def update_cash_flow_category(db: Session, record_id: int, category_id: int) -> dict:
    """後台補填臨時支出的科目"""
    record = db.query(CashFlowRecord).filter(CashFlowRecord.id == record_id).first()
    if not record:
        raise ValueError(f"CashFlowRecord {record_id} not found")
    record.category_id = category_id
    record.is_categorized = True
    db.commit()
    db.refresh(record)
    return _format_cash_flow(record, db)


def get_cash_flow_monthly_summary(db: Session, year: int, month: int) -> dict:
    """月度金流彙整，用於後台損益顯示"""
    from sqlalchemy import extract
    income = db.query(func.sum(CashFlowRecord.amount)).filter(
        CashFlowRecord.type == "income",
        extract("year", CashFlowRecord.transaction_date) == year,
        extract("month", CashFlowRecord.transaction_date) == month
    ).scalar() or 0

    expense = db.query(func.sum(CashFlowRecord.amount)).filter(
        CashFlowRecord.type == "expense",
        extract("year", CashFlowRecord.transaction_date) == year,
        extract("month", CashFlowRecord.transaction_date) == month
    ).scalar() or 0

    return {
        "year": year,
        "month": month,
        "total_income": float(income),
        "total_expense": float(expense),
        "net": float(income - expense)
    }


# ─────────────────────────────────────────────
# 應付帳款（Phase 3）
# ─────────────────────────────────────────────

def get_accounts_payable(
    db: Session,
    vendor_id: Optional[int] = None,
    is_paid: Optional[bool] = None,
    limit: int = 100
) -> List[dict]:
    query = db.query(AccountsPayable).order_by(AccountsPayable.due_date)
    if vendor_id:
        query = query.filter(AccountsPayable.vendor_id == vendor_id)
    if is_paid is not None:
        query = query.filter(AccountsPayable.is_paid == is_paid)
    records = query.limit(limit).all()
    return [_format_payable(r, db) for r in records]


def mark_payable_paid(db: Session, payable_id: int, user_id: int) -> dict:
    record = db.query(AccountsPayable).filter(AccountsPayable.id == payable_id).first()
    if not record:
        raise ValueError(f"AccountsPayable {payable_id} not found")
    record.is_paid = True
    record.paid_at = datetime.utcnow()
    record.paid_by_user_id = user_id
    db.commit()
    db.refresh(record)
    return _format_payable(record, db)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _format_petty_cash(record: PettyCashRecord, db: Session) -> dict:
    from erp.backend.db.models import Vendor
    vendor_name = None
    if record.vendor_id:
        v = db.query(Vendor).filter(Vendor.id == record.vendor_id).first()
        vendor_name = v.name if v else None

    return {
        "id": record.id,
        "user_id": record.user_id,
        "type": record.type.value if record.type else None,
        "amount": float(record.amount),
        "note": record.note,
        "photo_url": record.photo_url,
        "vendor_id": record.vendor_id,
        "vendor_name": vendor_name,
        "order_id": record.order_id,
        "created_at": record.created_at
    }


def _format_cash_flow(record: CashFlowRecord, db: Session) -> dict:
    category_name = None
    if record.category_id:
        cat = db.query(CashFlowCategory).filter(CashFlowCategory.id == record.category_id).first()
        category_name = cat.name if cat else None

    return {
        "id": record.id,
        "user_id": record.user_id,
        "category_id": record.category_id,
        "category_name": category_name,
        "amount": float(record.amount),
        "type": record.type,
        "source": record.source,
        "description": record.description,
        "vendor_id": record.vendor_id,
        "is_categorized": record.is_categorized,
        "transaction_date": record.transaction_date,
        "created_at": record.created_at
    }


def _format_payable(record: AccountsPayable, db: Session) -> dict:
    from erp.backend.db.models import Vendor
    vendor_name = None
    if record.vendor_id:
        v = db.query(Vendor).filter(Vendor.id == record.vendor_id).first()
        vendor_name = v.name if v else None

    return {
        "id": record.id,
        "vendor_id": record.vendor_id,
        "vendor_name": vendor_name,
        "order_id": record.order_id,
        "amount": float(record.amount),
        "due_date": record.due_date,
        "is_paid": record.is_paid,
        "paid_at": record.paid_at,
        "created_at": record.created_at
    }


# ─────────────────────────────────────────────
# 保留（向後相容）
# ─────────────────────────────────────────────

def get_balance(db: Session) -> float:
    """舊版零用金餘額（保留 Phase 2 相容）"""
    incomes = db.query(func.sum(CashTransaction.amount)).filter(CashTransaction.type == 'income').scalar() or 0
    expenses = db.query(func.sum(CashTransaction.amount)).filter(CashTransaction.type == 'expense').scalar() or 0
    withdrawals = db.query(func.sum(CashTransaction.amount)).filter(CashTransaction.type == 'withdrawal').scalar() or 0
    return float(incomes - expenses - withdrawals)
