from erp.backend.db.session import SessionLocal
from erp.backend.services.inventory_service import create_purchase_order

db = SessionLocal()
try:
    print("Testing order creation...")
    items = [{'item_id': 1, 'qty': 2.0}]
    create_purchase_order(db, 1, 1, items)
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
