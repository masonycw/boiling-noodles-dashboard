from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from erp.backend.db.session import get_db
from erp.backend.db.models import Announcement
from erp.backend.api.auth import get_current_user

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementCreate(BaseModel):
    content: str
    expires_at: Optional[datetime] = None


class AnnouncementUpdate(BaseModel):
    content: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


def _fmt(a: Announcement):
    return {
        "id": a.id,
        "content": a.content,
        "is_active": a.is_active,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "expires_at": a.expires_at.isoformat() if a.expires_at else None,
    }


@router.get("")
def list_announcements(all: bool = False, db: Session = Depends(get_db)):
    """回傳公告列表；all=true 時回傳全部（含停用），供後台使用"""
    now = datetime.utcnow()
    q = db.query(Announcement)
    if not all:
        q = q.filter(
            Announcement.is_active == True,
            (Announcement.expires_at == None) | (Announcement.expires_at > now)
        )
    rows = q.order_by(Announcement.created_at.desc()).all()
    return [_fmt(r) for r in rows]


@router.post("")
def create_announcement(body: AnnouncementCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(403, "需要管理員權限")
    a = Announcement(
        content=body.content,
        expires_at=body.expires_at,
        created_by=current_user.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _fmt(a)


@router.patch("/{ann_id}")
def update_announcement(ann_id: int, body: AnnouncementUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(403, "需要管理員權限")
    a = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not a:
        raise HTTPException(404, "公告不存在")
    if body.content is not None:
        a.content = body.content
    if body.is_active is not None:
        a.is_active = body.is_active
    if body.expires_at is not None:
        a.expires_at = body.expires_at
    db.commit()
    return _fmt(a)


@router.delete("/{ann_id}")
def delete_announcement(ann_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(403, "需要管理員權限")
    a = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not a:
        raise HTTPException(404, "公告不存在")
    db.delete(a)
    db.commit()
    return {"ok": True}
