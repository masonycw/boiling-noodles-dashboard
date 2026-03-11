from sqlalchemy.orm import Session
from erp.backend.db.models import Vendor, Item, PurchaseOrder, PurchaseOrderDetail
from datetime import datetime, timedelta

def get_vendors(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Vendor).filter(Vendor.is_active == True).offset(skip).limit(limit).all()

def get_items(db: Session, vendor_id: int = None, skip: int = 0, limit: int = 200):
    query = db.query(Item).filter(Item.is_active == True)
    if vendor_id:
        query = query.filter(Item.vendor_id == vendor_id)
    return query.offset(skip).limit(limit).all()

def create_purchase_order(db: Session, user_id: int, vendor_id: int, items_data: list, expected_delivery_date: datetime = None):
    """
    items_data: list of dicts with {'item_id': int, 'qty': float}
    """
    db_po = PurchaseOrder(
        user_id=user_id,
        vendor_id=vendor_id,
        status="pending",
        total_items=len(items_data),
        expected_delivery_date=expected_delivery_date
    )
    db.add(db_po)
    db.flush() # Get PO ID

    for item in items_data:
        db_detail = PurchaseOrderDetail(
            order_id=db_po.id,
            item_id=item.get('item_id'),
            adhoc_name=item.get('adhoc_name'),
            adhoc_unit=item.get('adhoc_unit'),
            qty=item['qty']
        )
        db.add(db_detail)
    
    db.commit()
    db.refresh(db_po)
    return db_po

def update_purchase_order(db: Session, order_id: int, vendor_id: int, items_data: list, expected_delivery_date: datetime = None):
    db_po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not db_po:
        raise Exception("Order not found")
        
    db_po.vendor_id = vendor_id
    db_po.expected_delivery_date = expected_delivery_date
    db_po.total_items = len(items_data)
    
    # Remove old items
    db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.order_id == order_id).delete()
    
    # Add new items
    for item in items_data:
        db_detail = PurchaseOrderDetail(
            order_id=db_po.id,
            item_id=item.get('item_id'),
            adhoc_name=item.get('adhoc_name'),
            adhoc_unit=item.get('adhoc_unit'),
            qty=item['qty']
        )
        db.add(db_detail)
        
    db.commit()
    db.refresh(db_po)
    return db_po

def get_orders(db: Session, skip: int = 0, limit: int = 50, days_limit: int = None, status: str = None):
    query = db.query(PurchaseOrder)
    if days_limit is not None:
        cutoff_date = datetime.utcnow() - timedelta(days=days_limit)
        query = query.filter(PurchaseOrder.created_at >= cutoff_date)
    if status is not None:
        query = query.filter(PurchaseOrder.status == status)
    return query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit).all()

from erp.backend.services.finance_service import create_transaction

def receive_order(db: Session, order_id: int, user_id: int, amount_paid: float, total_amount: float = 0.0, is_paid: bool = False, note: str = None):
    db_po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not db_po:
        raise Exception("Order not found")
        
    db_po.status = "received"
    db_po.total_amount = total_amount
    db_po.is_paid = is_paid
    db_po.amount_paid = amount_paid if is_paid else 0.0
    if note:
        db_po.note = note
    
    # Generate CashTransaction if amount_paid > 0 and is_paid
    if is_paid and amount_paid > 0:
        tx_in = {
            "amount": amount_paid,
            "type": "expense",
            "category": "進貨付款",
            "note": f"訂單 #{order_id} 貨款: {note or ''}",
            "order_id": order_id
        }
        create_transaction(db, user_id, tx_in)
        
    db.commit()
    db.refresh(db_po)
    return db_po

def update_order_receipt(db: Session, order_id: int, url_path: str):
    db_po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if db_po:
        db_po.receipt_url = url_path
        db.commit()
        db.refresh(db_po)
    return db_po

def delete_purchase_order(db: Session, order_id: int):
    db_po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if db_po:
        db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.order_id == order_id).delete()
        db.delete(db_po)
        db.commit()
    return True

def get_order_details(db: Session, order_id: int):
    return db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.order_id == order_id).all()

# Management Functions
def create_vendor(db: Session, vendor_in: dict):
    db_vendor = Vendor(**vendor_in)
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    return db_vendor

def update_vendor(db: Session, vendor_id: int, vendor_in: dict):
    db_vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if db_vendor:
        for key, value in vendor_in.items():
            setattr(db_vendor, key, value)
        db.commit()
        db.refresh(db_vendor)
    return db_vendor

def delete_vendor(db: Session, vendor_id: int):
    db_vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if db_vendor:
        db_vendor.is_active = False # Soft delete
        db.commit()
    return db_vendor

def create_item(db: Session, item_in: dict):
    db_item = Item(**item_in)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_item(db: Session, item_id: int, item_in: dict):
    db_item = db.query(Item).filter(Item.id == item_id).first()
    if db_item:
        for key, value in item_in.items():
            setattr(db_item, key, value)
        db.commit()
        db.refresh(db_item)
    return db_item

def delete_item(db: Session, item_id: int):
    db_item = db.query(Item).filter(Item.id == item_id).first()
    if db_item:
        db_item.is_active = False # Soft delete
        db.commit()
    return db_item
