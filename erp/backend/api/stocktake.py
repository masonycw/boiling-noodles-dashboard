from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from erp.backend.db.session import get_db
from erp.backend.services import stocktake_service

router = APIRouter(prefix="/stocktake", tags=["stocktake"])


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class StocktakeGroupCreate(BaseModel):
    name: str
    display_order: int = 0


class StocktakeGroupUpdate(BaseModel):
    name: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class StocktakeItemInput(BaseModel):
    item_id: Optional[int] = None
    counted_qty: Optional[float] = None
    expected_qty: Optional[float] = None
    order_qty: Optional[float] = None
    note: Optional[str] = None


class StocktakeCreate(BaseModel):
    mode: str = "stocktake"              # stocktake / order / both
    stocktake_group_id: Optional[int] = None
    note: Optional[str] = None
    items: List[StocktakeItemInput] = []


# ─────────────────────────────────────────────
# 盤點群組 Endpoints
# ─────────────────────────────────────────────

@router.get("/groups")
def list_stocktake_groups(db: Session = Depends(get_db)):
    return stocktake_service.get_stocktake_groups(db)


@router.post("/groups")
def create_stocktake_group(data: StocktakeGroupCreate, db: Session = Depends(get_db)):
    return stocktake_service.create_stocktake_group(db, data.dict())


@router.put("/groups/{group_id}")
def update_stocktake_group(group_id: int, data: StocktakeGroupUpdate, db: Session = Depends(get_db)):
    try:
        return stocktake_service.update_stocktake_group(db, group_id, data.dict(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/groups/{group_id}")
def delete_stocktake_group(group_id: int, db: Session = Depends(get_db)):
    try:
        stocktake_service.delete_stocktake_group(db, group_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─────────────────────────────────────────────
# 盤點單 Endpoints
# ─────────────────────────────────────────────

@router.get("/")
def list_stocktakes(
    days_limit: Optional[int] = None,
    group_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    return stocktake_service.get_stocktakes(db, days_limit=days_limit, group_id=group_id, limit=limit)


@router.get("/{stocktake_id}")
def get_stocktake(stocktake_id: int, db: Session = Depends(get_db)):
    try:
        return stocktake_service.get_stocktake(db, stocktake_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/")
def create_stocktake(data: StocktakeCreate, db: Session = Depends(get_db)):
    user_id = 1  # TODO: 從 JWT 取得
    return stocktake_service.create_stocktake(db, user_id, data.dict())


@router.put("/{stocktake_id}/submit")
def submit_stocktake(stocktake_id: int, db: Session = Depends(get_db)):
    try:
        return stocktake_service.submit_stocktake(db, stocktake_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
