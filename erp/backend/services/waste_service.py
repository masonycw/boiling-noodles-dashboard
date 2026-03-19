from sqlalchemy.orm import Session
from sqlalchemy import desc, extract
from datetime import datetime, timedelta, date
from typing import List, Optional
from erp.backend.db.models import WasteRecord, Item, User


def get_waste_records(
    db: Session,
    days_limit: Optional[int] = None,
    item_id: Optional[int] = None,
    reason: Optional[str] = None,
    record_date: Optional[str] = None,   # YYYY-MM-DD: filter exact date
    limit: int = 100
) -> List[dict]:
    query = db.query(WasteRecord).order_by(desc(WasteRecord.created_at))

    if record_date:
        d = datetime.strptime(record_date, "%Y-%m-%d")
        query = query.filter(
            WasteRecord.created_at >= d,
            WasteRecord.created_at < d + timedelta(days=1)
        )
    elif days_limit:
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(WasteRecord.created_at >= cutoff)

    if item_id:
        query = query.filter(WasteRecord.item_id == item_id)
    if reason:
        query = query.filter(WasteRecord.reason == reason)

    records = query.limit(limit).all()
    return [_format_waste(r, db) for r in records]


def create_waste_record(db: Session, user_id: int, data: dict) -> dict:
    record = WasteRecord(
        user_id=user_id,
        item_id=data.get("item_id"),
        adhoc_name=data.get("adhoc_name"),
        qty=data["qty"],
        unit=data.get("unit"),
        reason=data.get("reason"),
        estimated_value=data.get("estimated_value"),
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
        reason = r.reason or "其他"
        by_reason[reason] = by_reason.get(reason, 0) + 1

        name = r.adhoc_name
        if r.item_id:
            item = db.query(Item).filter(Item.id == r.item_id).first()
            name = item.name if item else f"item_{r.item_id}"
        if name:
            by_item[name] = by_item.get(name, 0) + float(r.qty)

    return {
        "total_records": len(records),
        "days": days_limit,
        "by_reason": [{"reason": k, "count": v} for k, v in by_reason.items()],
        "by_item": by_item
    }


def get_waste_monthly_kpi(db: Session) -> dict:
    today = date.today()
    records = db.query(WasteRecord).filter(
        extract('year', WasteRecord.created_at) == today.year,
        extract('month', WasteRecord.created_at) == today.month
    ).all()

    total_count = len(records)
    total_value = sum(
        float(getattr(r, 'estimated_value', None) or 0) for r in records
    )
    reasons: dict = {}
    for r in records:
        k = r.reason or "其他"
        reasons[k] = reasons.get(k, 0) + 1

    most_common = max(reasons, key=reasons.get) if reasons else None
    return {
        "total_count": total_count,
        "total_value": round(total_value, 2),
        "most_common_reason": most_common,
        "reason_breakdown": reasons
    }


def get_waste_items_used(db: Session) -> List[dict]:
    """Return distinct items that have waste records"""
    record_item_ids = (
        db.query(WasteRecord.item_id)
        .filter(WasteRecord.item_id.isnot(None))
        .distinct()
        .all()
    )
    ids = [r[0] for r in record_item_ids]
    items = db.query(Item).filter(Item.id.in_(ids)).all()
    return [{"id": i.id, "name": i.name} for i in items]


def _format_waste(record: WasteRecord, db: Session) -> dict:
    item_name = record.adhoc_name
    if record.item_id:
        item = db.query(Item).filter(Item.id == record.item_id).first()
        if item:
            item_name = item.name

    user = db.query(User).filter(User.id == record.user_id).first() if record.user_id else None
    recorded_by_name = None
    if user:
        recorded_by_name = user.full_name or user.username

    estimated_value = getattr(record, 'estimated_value', None)

    return {
        "id": record.id,
        "user_id": record.user_id,
        "recorded_by_name": recorded_by_name,
        "item_id": record.item_id,
        "item_name": item_name,
        "qty": float(record.qty),
        "unit": record.unit,
        "reason": record.reason,
        "estimated_value": float(estimated_value) if estimated_value else None,
        "photo_url": record.photo_url,
        "note": record.note,
        "created_at": record.created_at
    }
