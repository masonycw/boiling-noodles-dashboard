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
    """計算零用金餘額 = 收入 - 支出(已付) - 提領(已付)
    未付款的支出只是記帳，不扣餘額。
    """
    income = db.query(func.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == PettyCashTypeEnum.income
    ).scalar() or 0

    expense = db.query(func.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == PettyCashTypeEnum.expense,
        PettyCashRecord.is_paid == True
    ).scalar() or 0

    withdrawal = db.query(func.sum(PettyCashRecord.amount)).filter(
        PettyCashRecord.type == PettyCashTypeEnum.withdrawal,
        PettyCashRecord.is_paid == True
    ).scalar() or 0

    return float(income - expense - withdrawal)


def get_petty_cash_records(
    db: Session,
    days_limit: Optional[int] = None,
    type_filter: Optional[str] = None,
    date_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_paid: Optional[bool] = None,
    vendor_payment_method: Optional[str] = None,
    include_settled: Optional[bool] = None,
    limit: int = 100
) -> List[dict]:
    query = db.query(PettyCashRecord).order_by(desc(PettyCashRecord.created_at))

    if date_filter:
        # Taiwan is UTC+8; convert local date boundary to UTC for DB query
        day_start = datetime.fromisoformat(date_filter + ' 00:00:00') - timedelta(hours=8)
        day_end = datetime.fromisoformat(date_filter + ' 23:59:59') - timedelta(hours=8)
        query = query.filter(
            PettyCashRecord.created_at >= day_start,
            PettyCashRecord.created_at <= day_end
        )
    elif days_limit:
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(PettyCashRecord.created_at >= cutoff)
    if date_from:
        from_utc = datetime.fromisoformat(date_from + ' 00:00:00') - timedelta(hours=8)
        query = query.filter(PettyCashRecord.created_at >= from_utc)
    if date_to:
        to_utc = datetime.fromisoformat(date_to + ' 23:59:59') - timedelta(hours=8)
        query = query.filter(PettyCashRecord.created_at <= to_utc)
    if type_filter:
        query = query.filter(PettyCashRecord.type == type_filter)
    if is_paid is not None:
        query = query.filter(PettyCashRecord.is_paid == is_paid)
        # 待付款查詢時，排除已結帳的（除非明確要求包含）
        if is_paid is False and not include_settled:
            query = query.filter(PettyCashRecord.settled_at == None)

    # 只顯示已結帳紀錄（最近 7 天）
    if include_settled:
        cutoff_7d = datetime.utcnow() - timedelta(days=7)
        query = query.filter(PettyCashRecord.settled_at != None,
                             PettyCashRecord.settled_at >= cutoff_7d)

    # 按廠商付款方式過濾
    if vendor_payment_method:
        from erp.backend.db.models import Vendor as VendorModel
        query = query.join(VendorModel, PettyCashRecord.vendor_id == VendorModel.id)\
                     .filter(VendorModel.payment_method == vendor_payment_method)

    records = query.limit(limit).all()
    return [_format_petty_cash(r, db) for r in records]


def create_petty_cash_record(db: Session, user_id: int, data: dict) -> dict:
    """
    data: { type, amount, note, photo_url, vendor_id, order_id, is_paid }
    提領（withdrawal）時需要 petty_cash_permission = True
    is_paid=False 表示「待付帳款」，不計入餘額
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
        is_paid=data.get("is_paid", True),
        vendor_id=data.get("vendor_id"),
        order_id=data.get("order_id")
    )
    db.add(record)

    # B-13: 零用金支出（已付）自動寫入金流紀錄
    if data["type"] == "expense" and data.get("is_paid", True):
        from erp.backend.db.models import Vendor as VendorModel
        # 嘗試從廠商取預設科目
        category_id = data.get("category_id")
        if not category_id and data.get("vendor_id"):
            v = db.query(VendorModel).filter(VendorModel.id == data["vendor_id"]).first()
            if v and v.default_category_id:
                category_id = v.default_category_id
        cf = CashFlowRecord(
            user_id=user_id,
            category_id=category_id,
            amount=data["amount"],
            type="expense",
            source="petty_cash",
            description=data.get("note"),
            vendor_id=data.get("vendor_id"),
            is_categorized=category_id is not None,
            transaction_date=datetime.utcnow()
        )
        db.add(cf)

    db.commit()
    db.refresh(record)
    return _format_petty_cash(record, db)


def toggle_petty_cash_payment(db: Session, record_id: int) -> dict:
    """切換零用金紀錄的付款狀態（已付 ↔ 待付）"""
    record = db.query(PettyCashRecord).filter(PettyCashRecord.id == record_id).first()
    if not record:
        raise ValueError("紀錄不存在")
    record.is_paid = not record.is_paid
    db.commit()
    db.refresh(record)
    return _format_petty_cash(record, db)


def batch_settle_payments(db: Session, user_id: int, record_ids: list, photo_url: str = None) -> dict:
    """批次結帳代收款：標記舊紀錄已結帳 + 建立合併付款紀錄 + 同步應付帳款"""
    if not record_ids:
        raise ValueError("未選擇紀錄")

    records = db.query(PettyCashRecord).filter(PettyCashRecord.id.in_(record_ids)).all()
    if len(records) != len(record_ids):
        raise ValueError("部分紀錄不存在")

    # 驗證：都是未付款且未結帳
    for r in records:
        if r.is_paid:
            raise ValueError(f"紀錄 #{r.id} 已付款，無法結帳")
        if r.settled_at is not None:
            raise ValueError(f"紀錄 #{r.id} 已結帳，無法重複結帳")

    # 驗證：同一廠商
    vendor_ids = set(r.vendor_id for r in records if r.vendor_id)
    if len(vendor_ids) > 1:
        raise ValueError("一次只能結帳同一廠商的紀錄")
    vendor_id = vendor_ids.pop() if vendor_ids else None

    # 取得廠商資訊
    from erp.backend.db.models import Vendor as VendorModel
    vendor_name = None
    vendor_cat_id = None
    if vendor_id:
        vdr = db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
        if vdr:
            vendor_name = vdr.name
            if vdr.default_category_id:
                vendor_cat_id = vdr.default_category_id

    # 計算總金額
    total_amount = sum(float(r.amount) for r in records)

    # 收集訂單號
    order_ids = [r.order_id for r in records if r.order_id]
    order_text = ", ".join(f"#{oid}" for oid in order_ids) if order_ids else ""
    note_text = f"付款{' - ' + vendor_name if vendor_name else ''}"
    if order_text:
        note_text += f": 訂單 {order_text}"

    # 1. 標記原始紀錄為已結帳（is_paid 維持 false）
    now = datetime.utcnow()
    for r in records:
        r.settled_at = now

    # 2. 建立合併付款 PettyCashRecord（is_paid=True，計入支出）
    settlement_record = PettyCashRecord(
        user_id=user_id,
        type=PettyCashTypeEnum.expense,
        amount=total_amount,
        note=note_text,
        photo_url=photo_url,
        is_paid=True,
        vendor_id=vendor_id,
    )
    db.add(settlement_record)
    db.flush()  # 取得 settlement_record.id

    # 3. 回寫 settlement_ref_id
    for r in records:
        r.settlement_ref_id = settlement_record.id

    # 4. 建立 CashFlowRecord
    cf = CashFlowRecord(
        user_id=user_id,
        category_id=vendor_cat_id,
        amount=total_amount,
        type="expense",
        source="petty_cash",
        description=note_text,
        vendor_id=vendor_id,
        is_categorized=vendor_cat_id is not None,
        transaction_date=now,
    )
    db.add(cf)

    # 5. 同步 AccountsPayable：標記對應的應付帳款為已付
    for r in records:
        if r.order_id:
            ap = db.query(AccountsPayable).filter(
                AccountsPayable.order_id == r.order_id,
                AccountsPayable.is_paid == False,
            ).first()
            if ap:
                ap.is_paid = True
                ap.paid_at = now
                ap.paid_by_user_id = user_id
                ap.payment_method = "現金"

    db.commit()
    db.refresh(settlement_record)

    return {
        "settlement": _format_petty_cash(settlement_record, db),
        "settled_ids": record_ids,
    }


# ─────────────────────────────────────────────
# 金流管理（Phase 3）
# ─────────────────────────────────────────────

def get_cash_flow_categories(db: Session, include_inactive: bool = False) -> List[dict]:
    query = db.query(CashFlowCategory).order_by(CashFlowCategory.type, CashFlowCategory.display_order)
    if not include_inactive:
        query = query.filter(CashFlowCategory.is_active == True)
    cats = query.all()
    return [{"id": c.id, "name": c.name, "type": c.type, "is_active": c.is_active} for c in cats]


def get_cash_flow_records(
    db: Session,
    days_limit: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    type_filter: Optional[str] = None,
    category_id: Optional[int] = None,
    only_uncategorized: bool = False,
    limit: int = 200
) -> List[dict]:
    query = db.query(CashFlowRecord).order_by(desc(CashFlowRecord.created_at))

    if date_from:
        query = query.filter(CashFlowRecord.created_at >= date_from)
    elif days_limit:
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(CashFlowRecord.created_at >= cutoff)
    if date_to:
        query = query.filter(CashFlowRecord.created_at <= date_to + " 23:59:59")
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


def mark_payable_paid(db: Session, payable_id: int, user_id: int, payment_method: str = None) -> dict:
    record = db.query(AccountsPayable).filter(AccountsPayable.id == payable_id).first()
    if not record:
        raise ValueError(f"AccountsPayable {payable_id} not found")
    record.is_paid = True
    record.paid_at = datetime.utcnow()
    record.paid_by_user_id = user_id
    if payment_method is not None:
        record.payment_method = payment_method
    db.commit()
    db.refresh(record)
    return _format_payable(record, db)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _format_petty_cash(record: PettyCashRecord, db: Session) -> dict:
    from erp.backend.db.models import Vendor, User
    vendor_name = None
    category_id = None
    category_name = None
    if record.vendor_id:
        v = db.query(Vendor).filter(Vendor.id == record.vendor_id).first()
        if v:
            vendor_name = v.name
            if v.default_category_id:
                category_id = v.default_category_id
                cat = db.query(CashFlowCategory).filter(CashFlowCategory.id == v.default_category_id).first()
                category_name = cat.name if cat else None

    recorded_by_name = None
    if record.user_id:
        u = db.query(User).filter(User.id == record.user_id).first()
        if u:
            recorded_by_name = u.full_name or u.username

    return {
        "id": record.id,
        "user_id": record.user_id,
        "recorded_by_name": recorded_by_name,
        "type": record.type.value if record.type else None,
        "amount": float(record.amount),
        "note": record.note,
        "photo_url": record.photo_url,
        "is_paid": record.is_paid if record.is_paid is not None else True,
        "vendor_id": record.vendor_id,
        "vendor_name": vendor_name,
        "category_id": category_id,
        "category_name": category_name,
        "order_id": record.order_id,
        "settled_at": record.settled_at if hasattr(record, 'settled_at') else None,
        "settlement_ref_id": record.settlement_ref_id if hasattr(record, 'settlement_ref_id') else None,
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
    payment_terms = None
    if record.vendor_id:
        v = db.query(Vendor).filter(Vendor.id == record.vendor_id).first()
        if v:
            vendor_name = v.name
            payment_terms = v.payment_terms

    return {
        "id": record.id,
        "vendor_id": record.vendor_id,
        "vendor_name": vendor_name,
        "order_id": record.order_id,
        "amount": float(record.amount),
        "due_date": record.due_date,
        "payment_date": getattr(record, 'payment_date', None),
        "is_paid": record.is_paid,
        "paid_at": record.paid_at,
        "payment_method": record.payment_method,
        "note": record.note,
        "payment_terms": payment_terms,
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
