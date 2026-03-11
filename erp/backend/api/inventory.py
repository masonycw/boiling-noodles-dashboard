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

@router.post("/orders")
def create_order(vendor_id: int, items: List[dict], db: Session = Depends(get_db)):
    # In a real app, we'd get user_id from the JWT token
    user_id = 1 # Temporary placeholder
    return inventory_service.create_purchase_order(db, user_id, vendor_id, items)
@router.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    orders = inventory_service.get_orders(db)
    # Enhance orders with vendor name for the frontend
    result = []
    for order in orders:
        vendor = db.query(inventory_service.Vendor).filter(inventory_service.Vendor.id == order.vendor_id).first()
        result.append({
            "id": order.id,
            "vendor_name": vendor.name if vendor else "Unknown",
            "created_at": order.created_at,
            "status": order.status,
            "total_items": order.total_items
        })
    return result

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
