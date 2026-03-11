from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from erp.backend.db.session import get_db
from erp.backend.services import finance_service
from typing import List

router = APIRouter(prefix="/finance", tags=["finance"])

@router.get("/transactions")
def list_transactions(days_limit: int = None, db: Session = Depends(get_db)):
    return finance_service.get_transactions(db, days_limit=days_limit)

@router.get("/balance")
def get_current_balance(db: Session = Depends(get_db)):
    return {"balance": finance_service.get_balance(db)}

@router.post("/transactions")
def create_transaction(tx: dict, db: Session = Depends(get_db)):
    # In a real app, we'd get user_id from the JWT token
    user_id = 1 
    return finance_service.create_transaction(db, user_id, tx)

@router.post("/verify-pin")
def verify_pin(data: dict):
    pin = data.get("pin")
    if finance_service.verify_pin(pin):
        return {"status": "ok"}
    else:
        raise HTTPException(status_code=403, detail="PIN 錯誤")
