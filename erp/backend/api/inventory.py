from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from erp.backend.db.session import get_db
from erp.backend.services import inventory_service

router = APIRouter()

@router.get("/vendors")
def list_vendors(db: Session = Depends(get_db)):
    return inventory_service.get_vendors(db)

@router.post("/vendors")
def create_vendor(vendor: dict, db: Session = Depends(get_db)):
    return inventory_service.create_vendor(db, vendor)

@router.put("/vendors/{vendor_id}")
def update_vendor(vendor_id: int, vendor: dict, db: Session = Depends(get_db)):
    return inventory_service.update_vendor(db, vendor_id, vendor)

@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    return inventory_service.delete_vendor(db, vendor_id)

@router.get("/items")
def list_items(vendor_id: int = None, db: Session = Depends(get_db)):
    return inventory_service.get_items(db, vendor_id=vendor_id)

@router.post("/items")
def create_item(item: dict, db: Session = Depends(get_db)):
    return inventory_service.create_item(db, item)

@router.put("/items/{item_id}")
def update_item(item_id: int, item: dict, db: Session = Depends(get_db)):
    return inventory_service.update_item(db, item_id, item)

@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    return inventory_service.delete_item(db, item_id)

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class OrderItemCreate(BaseModel):
    item_id: Optional[int] = None
    adhoc_name: Optional[str] = None
    adhoc_unit: Optional[str] = None
    qty: float

class OrderCreate(BaseModel):
    vendor_id: int
    expected_delivery_date: Optional[datetime] = None
    items: List[OrderItemCreate]

@router.post("/orders")
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    user_id = 1 # Temporary placeholder
    # Convert pydantic models to dicts for service layer
    items_dicts = [item.dict() for item in order_data.items]
    return inventory_service.create_purchase_order(
        db, user_id, order_data.vendor_id, items_dicts, order_data.expected_delivery_date
    )

@router.get("/orders")
def list_orders(days_limit: int = None, status: str = None, db: Session = Depends(get_db)):
    orders = inventory_service.get_orders(db, days_limit=days_limit, status=status)
    result = []
    for order in orders:
        vendor = db.query(inventory_service.Vendor).filter(inventory_service.Vendor.id == order.vendor_id).first()
        result.append({
            "id": order.id,
            "vendor_name": vendor.name if vendor else "Unknown",
            "created_at": order.created_at,
            "status": order.status,
            "total_items": order.total_items,
            "expected_delivery_date": order.expected_delivery_date,
            "amount_paid": order.amount_paid
        })
    return result

class OrderReceive(BaseModel):
    amount_paid: float
    note: Optional[str] = None

@router.post("/orders/{order_id}/receive")
def receive_order(order_id: int, receive_data: OrderReceive, db: Session = Depends(get_db)):
    user_id = 1
    return inventory_service.receive_order(db, order_id, user_id, receive_data.amount_paid, receive_data.note)

@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    details = inventory_service.get_order_details(db, order_id)
    result = []
    for d in details:
        name = d.adhoc_name
        unit = d.adhoc_unit
        if d.item_id:
            item = db.query(inventory_service.Item).filter(inventory_service.Item.id == d.item_id).first()
            if item:
                name = item.name
                unit = item.unit
        
        result.append({
            "name": name,
            "qty": d.qty,
            "unit": unit
        })
    return result
