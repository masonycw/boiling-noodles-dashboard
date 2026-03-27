"""
P6: 首頁公告系統
- 新增 erp_announcements 表（公告內容、有效期限、發布人）
"""
from erp.backend.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS erp_announcements (
            id SERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_by INTEGER REFERENCES erp_users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ
        )
    """))
    conn.commit()
    print("Migration p6_announcements done")
