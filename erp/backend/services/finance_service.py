from sqlalchemy.orm import Session
from erp.backend.db.models import CashTransaction, AuditLog
from datetime import datetime, timedelta

def get_transactions(db: Session, skip: int = 0, limit: int = 100, days_limit: int = None):
    query = db.query(CashTransaction)
    if days_limit is not None:
        cutoff_date = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(CashTransaction.created_at >= cutoff_date)
    return query.order_by(CashTransaction.created_at.desc()).offset(skip).limit(limit).all()

from sqlalchemy.sql import func
def get_balance(db: Session):
    incomes = db.query(func.sum(CashTransaction.amount)).filter(CashTransaction.type == 'income').scalar() or 0
    expenses = db.query(func.sum(CashTransaction.amount)).filter(CashTransaction.type == 'expense').scalar() or 0
    withdrawals = db.query(func.sum(CashTransaction.amount)).filter(CashTransaction.type == 'withdrawal').scalar() or 0
    return float(incomes - expenses - withdrawals)

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
    
    # Also log to AuditLog for security tracking
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

def verify_pin(pin: str) -> bool:
    # In a real app, this would be a user-specific setting in the DB
    # For this local demo/MVP, we use '1234' as requested/suggested
    return pin == "1234"
