from sqlalchemy.orm import Session
from sqlalchemy import desc, extract
from datetime import datetime, date
from typing import List, Optional
from erp.backend.db.models import (
    StocktakeGroup, Stocktake, StocktakeItem, Item, StocktakeModeEnum, User
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
    group.is_active = False
    db.commit()
    return True


# ─────────────────────────────────────────────
# 盤點單
# ─────────────────────────────────────────────

def get_stocktakes(
    db: Session,
    days_limit: Optional[int] = None,
    group_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    executor_id: Optional[int] = None,
    has_discrepancy: Optional[bool] = None,
    limit: int = 50
) -> List[dict]:
    from datetime import timedelta
    query = db.query(Stocktake).order_by(desc(Stocktake.created_at))

    if date_from:
        query = query.filter(Stocktake.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
    elif days_limit:
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(Stocktake.created_at >= cutoff)

    if date_to:
        from datetime import timedelta as td
        dt = datetime.strptime(date_to, "%Y-%m-%d") + td(days=1)
        query = query.filter(Stocktake.created_at < dt)

    if group_id:
        query = query.filter(Stocktake.stocktake_group_id == group_id)
    if executor_id:
        query = query.filter(Stocktake.user_id == executor_id)

    stocktakes = query.limit(limit).all()
    result = []
    for s in stocktakes:
        items = db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == s.id).all()
        formatted = _format_stocktake(s, items, db)
        if has_discrepancy is True and formatted["discrepancy_count"] == 0:
            continue
        if has_discrepancy is False and formatted["discrepancy_count"] > 0:
            continue
        result.append(formatted)
    return result


def get_stocktake(db: Session, stocktake_id: int) -> dict:
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise ValueError(f"Stocktake {stocktake_id} not found")
    items = db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == s.id).all()
    return _format_stocktake(s, items, db)


def create_stocktake(db: Session, user_id: int, data: dict) -> dict:
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
    return _format_stocktake(stocktake, items, db)


def submit_stocktake(db: Session, stocktake_id: int) -> dict:
    stocktake = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not stocktake:
        raise ValueError(f"Stocktake {stocktake_id} not found")
    if stocktake.status == "submitted":
        raise ValueError("Stocktake already submitted")

    stocktake.status = "submitted"
    stocktake.submitted_at = datetime.utcnow()

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
    return _format_stocktake(stocktake, items, db)


def get_stocktake_monthly_kpi(db: Session) -> dict:
    today = date.today()
    stocktakes = db.query(Stocktake).filter(
        extract('year', Stocktake.created_at) == today.year,
        extract('month', Stocktake.created_at) == today.month
    ).all()

    count = len(stocktakes)
    total_discrepancy = 0
    for s in stocktakes:
        items = db.query(StocktakeItem).filter(StocktakeItem.stocktake_id == s.id).all()
        disc = sum(
            1 for i in items
            if i.counted_qty is not None and i.expected_qty is not None
            and float(i.counted_qty) != float(i.expected_qty)
        )
        total_discrepancy += disc

    avg_discrepancy = round(total_discrepancy / count, 1) if count > 0 else 0
    return {
        "month_count": count,
        "average_discrepancy_count": avg_discrepancy,
        "total_discrepancy_items": total_discrepancy
    }


def get_executors(db: Session) -> List[dict]:
    """Return users who have performed stocktakes"""
    user_ids = (
        db.query(Stocktake.user_id)
        .filter(Stocktake.user_id.isnot(None))
        .distinct()
        .all()
    )
    ids = [r[0] for r in user_ids]
    users = db.query(User).filter(User.id.in_(ids)).all()
    return [{"id": u.id, "name": u.full_name or u.username} for u in users]


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def _format_stocktake(stocktake: Stocktake, items: List[StocktakeItem], db: Session = None) -> dict:
    group_name = None
    executor_name = None

    performed_by = None
    if db:
        if stocktake.stocktake_group_id:
            group = db.query(StocktakeGroup).filter(
                StocktakeGroup.id == stocktake.stocktake_group_id
            ).first()
            group_name = group.name if group else None
        if stocktake.user_id:
            user = db.query(User).filter(User.id == stocktake.user_id).first()
            if user:
                executor_name = user.full_name or user.username
                performed_by = {
                    "id": user.id,
                    "username": "(已刪除)" if user.deleted_at else user.username,
                    "name": user.full_name or user.username
                }

    formatted_items = []
    for si in items:
        item_name = f"item_{si.item_id}" if si.item_id else "臨時品項"
        if db and si.item_id:
            item = db.query(Item).filter(Item.id == si.item_id).first()
            if item:
                item_name = item.name

        variance = None
        if si.counted_qty is not None and si.expected_qty is not None:
            variance = round(float(si.counted_qty) - float(si.expected_qty), 2)

        formatted_items.append({
            "id": si.id,
            "item_id": si.item_id,
            "item_name": item_name,
            "counted_qty": float(si.counted_qty) if si.counted_qty is not None else None,
            "expected_qty": float(si.expected_qty) if si.expected_qty is not None else None,
            "previous_stock": float(si.expected_qty) if si.expected_qty is not None else None,
            "order_qty": float(si.order_qty) if si.order_qty is not None else None,
            "variance": variance,
            "note": si.note
        })

    discrepancy_count = sum(
        1 for i in formatted_items
        if i.get("variance") is not None and i["variance"] != 0
    )

    return {
        "id": stocktake.id,
        "user_id": stocktake.user_id,
        "executor_name": executor_name,
        "performed_by": performed_by,
        "stocktake_group_id": stocktake.stocktake_group_id,
        "group_name": group_name,
        "mode": stocktake.mode.value if stocktake.mode else "stocktake",
        "status": stocktake.status,
        "discrepancy_count": discrepancy_count,
        "note": stocktake.note,
        "created_at": stocktake.created_at,
        "submitted_at": stocktake.submitted_at,
        "items": formatted_items
    }
