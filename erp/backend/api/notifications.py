from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
from pydantic import BaseModel
from erp.backend.db.session import get_db
from erp.backend.db.models import Notification, NotificationSetting

router = APIRouter(prefix="/notifications", tags=["notifications"])

NOTIFICATION_TYPES = [
    {"key": "order", "label": "訂單通知"},
    {"key": "low_stock", "label": "低庫存通知"},
    {"key": "delivery", "label": "進貨到達通知"},
    {"key": "settlement", "label": "日結提醒"},
    {"key": "payment", "label": "付款提醒"},
    {"key": "stocktake", "label": "盤點提醒"},
    {"key": "waste", "label": "損耗異常通知"},
    {"key": "system", "label": "系統通知"},
]

USER_ID = 1  # TODO: from JWT


@router.get("/settings")
def get_notification_settings(db: Session = Depends(get_db)):
    settings = {s.notification_type: s.is_enabled
                for s in db.query(NotificationSetting).filter(NotificationSetting.user_id == USER_ID).all()}
    return [
        {
            "key": t["key"],
            "label": t["label"],
            "is_enabled": settings.get(t["key"], True),
        }
        for t in NOTIFICATION_TYPES
    ]


@router.put("/settings/{rule_type}")
def toggle_notification_setting(rule_type: str, db: Session = Depends(get_db)):
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == USER_ID,
        NotificationSetting.notification_type == rule_type,
    ).first()
    if setting:
        setting.is_enabled = not setting.is_enabled
    else:
        setting = NotificationSetting(user_id=USER_ID, notification_type=rule_type, is_enabled=False)
        db.add(setting)
    db.commit()
    return {"key": rule_type, "is_enabled": setting.is_enabled}


@router.get("")
def list_notifications(limit: int = 30, db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter(
        (Notification.target_user_id == USER_ID) | (Notification.target_user_id == None)
    ).order_by(desc(Notification.created_at)).limit(limit).all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in notifs
    ]


@router.put("/{notif_id}/read")
def mark_notification_read(notif_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="通知不存在")
    notif.is_read = not notif.is_read
    db.commit()
    return {"id": notif.id, "is_read": notif.is_read}
