from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from erp.backend.db.session import get_db
from erp.backend.services import waste_service

router = APIRouter(prefix="/waste", tags=["waste"])


class WasteCreate(BaseModel):
    item_id: Optional[int] = None
    adhoc_name: Optional[str] = None
    qty: float
    unit: Optional[str] = None
    reason: Optional[str] = None       # 過期 / 破損 / 烹調損耗 / 其他
    photo_url: Optional[str] = None
    note: Optional[str] = None


@router.get("/")
def list_waste_records(
    days_limit: Optional[int] = 30,
    item_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return waste_service.get_waste_records(db, days_limit=days_limit, item_id=item_id, limit=limit)


@router.post("/")
def create_waste_record(data: WasteCreate, db: Session = Depends(get_db)):
    user_id = 1  # TODO: 從 JWT 取得
    if not data.item_id and not data.adhoc_name:
        raise HTTPException(status_code=400, detail="需要提供 item_id 或 adhoc_name")
    return waste_service.create_waste_record(db, user_id, data.dict())


@router.get("/summary")
def get_waste_summary(days_limit: int = 30, db: Session = Depends(get_db)):
    return waste_service.get_waste_summary(db, days_limit=days_limit)
