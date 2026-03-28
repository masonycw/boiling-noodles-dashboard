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
    description: Optional[str] = None
    suggested_frequency: Optional[str] = None
    is_active: bool = True
    stocktake_cycle_days: Optional[int] = None   # O5
    next_stocktake_due: Optional[str] = None      # O5


class StocktakeGroupUpdate(BaseModel):
    name: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    suggested_frequency: Optional[str] = None
    stocktake_cycle_days: Optional[int] = None   # O5
    next_stocktake_due: Optional[str] = None      # O5


class NextDueUpdate(BaseModel):
    next_due: str


class StocktakeItemInput(BaseModel):
    item_id: Optional[int] = None
    counted_qty: Optional[float] = None
    expected_qty: Optional[float] = None
    order_qty: Optional[float] = None
    note: Optional[str] = None


class StocktakeCreate(BaseModel):
    mode: str = "stocktake"
    stocktake_group_id: Optional[int] = None
    note: Optional[str] = None
    items: List[StocktakeItemInput] = []


# ─────────────────────────────────────────────
# 盤點群組 Endpoints
# ─────────────────────────────────────────────

@router.get("/groups")
def list_stocktake_groups(db: Session = Depends(get_db)):
    return stocktake_service.get_stocktake_groups(db)


@router.get("/pending-groups")
def get_pending_groups(db: Session = Depends(get_db)):
    """O5: 回傳今天或逾期或明天到期的待盤點群組（HomeView 用）"""
    return stocktake_service.get_pending_groups(db)


@router.patch("/groups/{group_id}/next-due")
def update_group_next_due(group_id: int, data: NextDueUpdate, db: Session = Depends(get_db)):
    """O5: 手動更新群組下次預定盤點日"""
    try:
        return stocktake_service.update_group_next_due(db, group_id, data.next_due)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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

@router.get("/history")
def list_stocktakes_history(
    days_limit: Optional[int] = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    return stocktake_service.get_stocktakes(db, days_limit=days_limit, limit=limit)


@router.get("/monthly-kpi")
def get_monthly_kpi(db: Session = Depends(get_db)):
    return stocktake_service.get_stocktake_monthly_kpi(db)


@router.get("/executors")
def get_executors(db: Session = Depends(get_db)):
    return stocktake_service.get_executors(db)


@router.get("/")
def list_stocktakes(
    days_limit: Optional[int] = None,
    group_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    executor_id: Optional[int] = None,
    has_discrepancy: Optional[bool] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    return stocktake_service.get_stocktakes(
        db,
        days_limit=days_limit,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
        executor_id=executor_id,
        has_discrepancy=has_discrepancy,
        limit=limit
    )


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


class StocktakeItemPatch(BaseModel):
    item_id: int
    counted_qty: float


class StocktakePatch(BaseModel):
    stocktake_date: Optional[str] = None
    performed_by: Optional[int] = None
    note: Optional[str] = None
    items: Optional[List[StocktakeItemPatch]] = None


@router.patch("/{stocktake_id}")
def patch_stocktake(stocktake_id: int, data: StocktakePatch, db: Session = Depends(get_db)):
    from erp.backend.db.models import Stocktake, StocktakeItem
    from datetime import datetime as dt
    record = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Stocktake not found")
    if data.stocktake_date:
        try:
            record.created_at = dt.fromisoformat(data.stocktake_date)
        except Exception:
            pass
    if data.performed_by is not None:
        record.user_id = data.performed_by
    if data.note is not None:
        record.note = data.note
    if data.items is not None:
        for item_patch in data.items:
            si = db.query(StocktakeItem).filter(
                StocktakeItem.stocktake_id == stocktake_id,
                StocktakeItem.item_id == item_patch.item_id
            ).first()
            if si:
                si.counted_qty = item_patch.counted_qty
            else:
                # 新增未被盤點的品項（補盤）
                from erp.backend.db.models import Item as ItemModel
                item = db.query(ItemModel).filter(ItemModel.id == item_patch.item_id).first()
                expected_qty = float(item.current_stock) if item and item.current_stock else 0
                new_si = StocktakeItem(
                    stocktake_id=stocktake_id,
                    item_id=item_patch.item_id,
                    counted_qty=item_patch.counted_qty,
                    expected_qty=expected_qty,
                )
                db.add(new_si)
    db.commit()
    return {"success": True}


@router.delete("/{stocktake_id}")
def delete_stocktake(stocktake_id: int, db: Session = Depends(get_db)):
    from erp.backend.db.models import Stocktake, StocktakeItem
    record = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Stocktake not found")
    db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == stocktake_id).delete()
    db.delete(record)
    db.commit()
    return {"success": True}
