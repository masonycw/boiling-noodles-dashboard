from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import List, Optional
from erp.backend.db.models import (
    StocktakeGroup, Stocktake, StocktakeItem, Item, StocktakeModeEnum
)


# ─────────────────────────────────────────────
# 盤點群組
# ─────────────────────────────────────────────

def get_stocktake_groups(db: Session) -> List[StocktakeGroup]:
    return (
        db.query(StocktakeGroup)
        .filter(StocktakeGroup.is_active == True)
        .order_by(StocktakeGroup.display_order)
        .all()
    )


def create_stocktake_group(db: Session, data: dict) -> StocktakeGroup:
    group = StocktakeGroup(**data)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def update_stocktake_group(db: Session, group_id: int, data: dict) -> StocktakeGroup:
    group = db.query(StocktakeGroup).filter(StocktakeGroup.id == group_id).first()
    if not group:
        raise ValueError(f"StocktakeGroup {group_id} not found")
    for key, value in data.items():
        setattr(group, key, value)
    db.commit()
    db.refresh(group)
    return group


def delete_stocktake_group(db: Session, group_id: int) -> bool:
    group = db.query(StocktakeGroup).filter(StocktakeGroup.id == group_id).first()
    if not group:
        raise ValueError(f"StocktakeGroup {group_id} not found")
    group.is_active = False  # Soft delete
    db.commit()
    return True


# ─────────────────────────────────────────────
# 盤點單
# ─────────────────────────────────────────────

def get_stocktakes(
    db: Session,
    days_limit: Optional[int] = None,
    group_id: Optional[int] = None,
    limit: int = 50
) -> List[dict]:
    from datetime import timedelta
    query = db.query(Stocktake).order_by(desc(Stocktake.created_at))

    if days_limit:
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(Stocktake.created_at >= cutoff)
    if group_id:
        query = query.filter(Stocktake.stocktake_group_id == group_id)

    stocktakes = query.limit(limit).all()
    result = []
    for s in stocktakes:
        items = db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == s.id).all()
        result.append(_format_stocktake(s, items))
    return result


def get_stocktake(db: Session, stocktake_id: int) -> dict:
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise ValueError(f"Stocktake {stocktake_id} not found")
    items = db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == s.id).all()
    return _format_stocktake(s, items)


def create_stocktake(db: Session, user_id: int, data: dict) -> dict:
    """
    data: {
        mode: 'stocktake' | 'order' | 'both',
        stocktake_group_id: int | None,
        note: str | None,
        items: [{ item_id, counted_qty, expected_qty, order_qty, note }]
    }
    """
    items_data = data.pop("items", [])

    stocktake = Stocktake(
        user_id=user_id,
        mode=data.get("mode", StocktakeModeEnum.stocktake),
        stocktake_group_id=data.get("stocktake_group_id"),
        note=data.get("note"),
        status="draft"
    )
    db.add(stocktake)
    db.flush()

    for item_data in items_data:
        si = StocktakeItem(
            stocktake_id=stocktake.id,
            item_id=item_data.get("item_id"),
            counted_qty=item_data.get("counted_qty"),
            expected_qty=item_data.get("expected_qty"),
            order_qty=item_data.get("order_qty"),
            note=item_data.get("note")
        )
        db.add(si)

    db.commit()
    db.refresh(stocktake)
    items = db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == stocktake.id).all()
    return _format_stocktake(stocktake, items)


def submit_stocktake(db: Session, stocktake_id: int) -> dict:
    """送出盤點，更新庫存 current_stock"""
    stocktake = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not stocktake:
        raise ValueError(f"Stocktake {stocktake_id} not found")
    if stocktake.status == "submitted":
        raise ValueError("Stocktake already submitted")

    stocktake.status = "submitted"
    stocktake.submitted_at = datetime.utcnow()

    # 更新庫存（僅盤點模式才更新）
    if stocktake.mode in (StocktakeModeEnum.stocktake, StocktakeModeEnum.both):
        items = db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == stocktake_id).all()
        for si in items:
            if si.item_id and si.counted_qty is not None:
                item = db.query(Item).filter(Item.id == si.item_id).first()
                if item:
                    item.current_stock = si.counted_qty

    db.commit()
    db.refresh(stocktake)
    items = db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == stocktake.id).all()
    return _format_stocktake(stocktake, items)


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def _format_stocktake(stocktake: Stocktake, items: List[StocktakeItem]) -> dict:
    return {
        "id": stocktake.id,
        "user_id": stocktake.user_id,
        "stocktake_group_id": stocktake.stocktake_group_id,
        "mode": stocktake.mode.value if stocktake.mode else "stocktake",
        "status": stocktake.status,
        "note": stocktake.note,
        "created_at": stocktake.created_at,
        "submitted_at": stocktake.submitted_at,
        "items": [
            {
                "id": si.id,
                "item_id": si.item_id,
                "counted_qty": float(si.counted_qty) if si.counted_qty is not None else None,
                "expected_qty": float(si.expected_qty) if si.expected_qty is not None else None,
                "order_qty": float(si.order_qty) if si.order_qty is not None else None,
                "note": si.note
            }
            for si in items
        ]
    }
