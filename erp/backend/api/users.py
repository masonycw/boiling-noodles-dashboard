from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
from erp.backend.db.session import get_db
from erp.backend.db.models import User
from erp.backend.core.security import get_password_hash
from erp.backend.api.auth import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    role: str = "staff"
    petty_cash_permission: bool = False
    petty_cash_access: bool = False
    remittance_permission: bool = False


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    petty_cash_permission: Optional[bool] = None
    petty_cash_access: Optional[bool] = None
    remittance_permission: Optional[bool] = None
    password: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@router.get("/import-template")
def users_import_template():
    """動態產生帳號匯入 Excel 範本（含角色/零用金下拉）"""
    from erp.backend.utils.excel_template import build_accounts_template
    from fastapi.responses import StreamingResponse
    import io

    data = build_accounts_template()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''%E5%B8%B3%E8%99%9F%E5%8C%AF%E5%85%A5%E7%AF%84%E6%9C%AC.xlsx"}
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return _format_user(current_user)


@router.get("/")
def list_users(db: Session = Depends(get_db)) -> List[dict]:
    users = db.query(User).filter(User.deleted_at == None).order_by(User.id).all()
    return [_format_user(u) for u in users]


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _format_user(user)


@router.post("/")
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=data.username,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=data.role,
        petty_cash_permission=data.petty_cash_permission,
        petty_cash_access=data.petty_cash_access,
        remittance_permission=data.remittance_permission,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _format_user(user)


@router.put("/{user_id}")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = data.dict(exclude_none=True)
    password = update_data.pop('password', None)
    if update_data.get('username') and update_data['username'] != user.username:
        existing = db.query(User).filter(User.username == update_data['username'], User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="帳號名稱已被使用")
    for key, value in update_data.items():
        setattr(user, key, value)
    if password:
        user.hashed_password = get_password_hash(password)
    db.commit()
    db.refresh(user)
    return _format_user(user)


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from datetime import datetime as dt
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="SELF_DELETE: 無法刪除自己的帳號")
    user = db.query(User).filter(User.id == user_id, User.deleted_at == None).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Check if this is the last admin
    if user.role == 'admin':
        admin_count = db.query(User).filter(User.role == 'admin', User.deleted_at == None).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="LAST_ADMIN: 系統至少需保留一個管理者帳號")
    user.deleted_at = dt.utcnow()
    user.is_active = False
    db.commit()
    return {"success": True}


@router.put("/{user_id}/password")
def change_password(
    user_id: int,
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Admin 可以直接重設他人密碼，不需驗證舊密碼
    is_admin_reset = current_user.role == "admin" and current_user.id != user_id
    if not is_admin_reset:
        if not pwd_context.verify(data.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return {"ok": True, "message": "Password updated"}


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def _format_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "petty_cash_permission": user.petty_cash_permission,
        "petty_cash_access": getattr(user, 'petty_cash_access', False) or False,
        "remittance_permission": getattr(user, 'remittance_permission', False) or False,
        "created_at": user.created_at,
        "last_login": user.last_login
    }
