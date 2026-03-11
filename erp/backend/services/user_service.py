from sqlalchemy.orm import Session
from erp.backend.db.models import User
from erp.backend.core.security import get_password_hash

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, username: str, password: str, full_name: str = None, role: str = "staff"):
    hashed_password = get_password_hash(password)
    db_user = User(
        username=username,
        hashed_password=hashed_password,
        full_name=full_name,
        role=role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_password(db: Session, user_id: int, new_password: str):
    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user:
        db_user.hashed_password = get_password_hash(new_password)
        db.commit()
        db.refresh(db_user)
    return db_user
