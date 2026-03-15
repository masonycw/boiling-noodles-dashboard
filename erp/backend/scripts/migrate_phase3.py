"""
Phase 3 Migration Script
執行：python -m erp.backend.scripts.migrate_phase3
或：  cd 智慧報表 && python -m erp.backend.scripts.migrate_phase3
"""
import os
import sys
import psycopg2

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from erp.backend.core.config import settings

SQL_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "migrate_phase3.sql")


def run_migration():
    print("🚀 Starting Phase 3 DB Migration...")
    print(f"   DB: {settings.DATABASE_URL}")

    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.autocommit = False
        cur = conn.cursor()

        with open(SQL_PATH, "r", encoding="utf-8") as f:
            sql = f.read()

        cur.execute(sql)
        conn.commit()
        print("✅ Phase 3 Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
