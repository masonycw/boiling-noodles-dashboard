import sys
import os

# Add the project root to sys.path so we can import 'erp'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from erp.backend.db.session import SessionLocal
from erp.backend.services import user_service

def create_admin():
    db = SessionLocal()
    try:
        existing_user = user_service.get_user_by_username(db, "admin")
        if existing_user:
            print("Admin user already exists.")
            return

        user_service.create_user(
            db,
            username="admin",
            password="adminpassword123",
            full_name="System Administrator",
            role="admin"
        )
        print("Admin user created successfully!")
        print("Username: admin")
        print("Password: adminpassword123")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
