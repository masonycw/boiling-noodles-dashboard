import sys
import os

# Add the project root and current dir to the python path
sys.path.append(os.getcwd())
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from erp.backend.db.session import engine, SessionLocal
from erp.backend.db.models import Base, Vendor, Item, User, ItemCategory
from erp.backend.core.security import get_password_hash

def init_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Create Admin User
        if not db.query(User).filter(User.username == "admin").first():
            print("Creating admin user...")
            admin = User(
                username="admin",
                hashed_password=get_password_hash("adminpassword123"),
                full_name="System Admin",
                role="admin"
            )
            db.add(admin)
        
        # 2. Create Vendor
        vendor_name = "菜商（高青）"
        vendor = db.query(Vendor).filter(Vendor.name == vendor_name).first()
        if not vendor:
            print(f"Creating vendor {vendor_name}...")
            from datetime import time
            vendor = Vendor(
                name=vendor_name,
                order_deadline=time(21, 0),
                is_active=True
            )
            db.add(vendor)
            db.commit()
            db.refresh(vendor)
        
        # 3. Create Items
        items_data = [
            ("蔥花", "⽄"), ("蒜泥", "⽄"), ("芹菜", "⽄"), ("辣椒", "⽄"),
            ("紅蔥頭(切片)", "⽄"), ("⼩黃瓜", "⽄"), ("芋頭", "⽄"), ("茄⼦", "⽄"),
            ("紅蘿蔔", "⽄"), ("⽩蘿蔔", "條"), ("檸檬", "顆"), ("洋蔥", "⽄"),
            ("黃⾖芽", "⽄"), ("青江菜", "⽄"), ("⼤陸妹", "⽄"), ("⾼麗菜", "⽄"),
            ("蚵⽩菜", "⽄"), ("⽔蓮", "包"), ("鴻禧菇", "包"), ("⾦針菇", "Kg"),
            ("芭樂", "⽄"), ("⼩番茄", "盒"), ("乾絲", "⽄"), ("⿊⽊耳", "⽄")
        ]
        
        for name, unit in items_data:
            if not db.query(Item).filter(Item.name == name, Item.vendor_id == vendor.id).first():
                print(f"Adding item: {name}")
                item = Item(
                    name=name,
                    unit=unit,
                    vendor_id=vendor.id,
                    is_active=True
                )
                db.add(item)
        
        db.commit()
        print("Local database initialized successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
