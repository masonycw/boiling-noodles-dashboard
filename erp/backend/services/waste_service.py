from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import List, Optional
from erp.backend.db.models import WasteRecord, Item


def get_waste_records(
    db: Session,
    days_limit: Optional[int] = None,
    item_id: Optional[int] = None,
    limit: int = 100
) -> List[dict]:
    query = db.query(WasteRecord).order_by(desc(WasteRecord.created_at))

    if days_limit:
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(WasteRecord.created_at >= cutoff)
    if item_id:
        query = query.filter(WasteRecord.item_id == item_id)

    records = query.limit(limit).all()
    return [_format_waste(r, db) for r in records]


def create_waste_record(db: Session, user_id: int, data: dict) -> dict:
    """
    data: { item_id, adhoc_name, qty, unit, reason, photo_url, note }
    """
    record = WasteRecord(
        user_id=user_id,
        item_id=data.get("item_id"),
        adhoc_name=data.get("adhoc_name"),
        qty=data["qty"],
        unit=data.get("unit"),
        reason=data.get("reason"),
        photo_url=data.get("photo_url"),
        note=data.get("note")
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _format_waste(record, db)


def get_waste_summary(db: Session, days_limit: int = 30) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days_limit)
    records = (
        db.query(WasteRecord)
        .filter(WasteRecord.created_at >= cutoff)
        .all()
    )

    by_reason: dict = {}
    by_item: dict = {}

    for r in records:
        # 按原因彙整
        reason = r.reason or "其他"
        by_reason[reason] = by_reason.get(reason, 0) + 1

        # 按品項彙整
        name = r.adhoc_name
        if r.item_id:
            item = db.query(Item).filter(Item.id == r.item_id).first()
            name = item.name if item else f"item_{r.item_id}"
        if name:
            by_item[name] = by_item.get(name, 0) + float(r.qty)

    return {
        "total_records": len(records),
        "days": days_limit,
        "by_reason": by_reason,
        "by_item": by_item
    }


def _format_waste(record: WasteRecord, db: Session) -> dict:
    item_name = record.adhoc_name
    if record.item_id:
        item = db.query(Item).filter(Item.id == record.item_id).first()
        item_name = item.name if item else None

    return {
        "id": record.id,
        "user_id": record.user_id,
        "item_id": record.item_id,
        "item_name": item_name,
        "qty": float(record.qty),
        "unit": record.unit,
        "reason": record.reason,
        "photo_url": record.photo_url,
        "note": record.note,
        "created_at": record.created_at
    }
