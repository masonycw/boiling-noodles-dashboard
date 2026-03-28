from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from erp.backend.db.session import get_db
from erp.backend.db.models import SystemSetting, LinePendingGroup

router = APIRouter(prefix="/settings", tags=["settings"])

class SettingUpdate(BaseModel):
    value: str

class PendingGroupMatchUpdate(BaseModel):
    matched: bool

@router.get("/")
def get_settings(db: Session = Depends(get_db)):
    settings = db.query(SystemSetting).all()
    return {s.key: s.value for s in settings}

@router.put("/{key}")
def update_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if setting:
        setting.value = body.value
    else:
        setting = SystemSetting(key=key, value=body.value)
        db.add(setting)
    db.commit()
    return {"key": key, "value": body.value}

@router.get("/line-pending-groups")
def get_line_pending_groups(matched: Optional[bool] = None, db: Session = Depends(get_db)):
    query = db.query(LinePendingGroup)
    if matched is not None:
        query = query.filter(LinePendingGroup.matched == matched)
    groups = query.order_by(LinePendingGroup.first_seen.desc()).all()
    return [
        {
            "id": g.id,
            "group_id": g.group_id,
            "matched": g.matched,
            "first_seen": g.first_seen.isoformat() if g.first_seen else None,
        }
        for g in groups
    ]

@router.patch("/line-pending-groups/{pending_id}/match")
def update_pending_group_match(pending_id: int, body: PendingGroupMatchUpdate, db: Session = Depends(get_db)):
    group = db.query(LinePendingGroup).filter(LinePendingGroup.id == pending_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Pending group not found")
    group.matched = body.matched
    db.commit()
    return {"id": group.id, "group_id": group.group_id, "matched": group.matched}
