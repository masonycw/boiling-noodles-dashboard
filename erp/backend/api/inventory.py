from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from erp.backend.db.session import get_db
from erp.backend.services import inventory_service
from erp.backend.services.line_service import send_line_message, get_setting
from erp.backend.db.models import Vendor, Item

router = APIRouter()

@router.get("/vendors")
def list_vendors(show_in_ordering: bool = None, vendor_type: str = None, db: Session = Depends(get_db)):
    vendors = inventory_service.get_vendors(db)
    if show_in_ordering is not None:
        vendors = [v for v in vendors if bool(v.show_in_ordering) == show_in_ordering]
    if vendor_type is not None:
        vendors = [v for v in vendors if (v.vendor_type or 'supplier') == vendor_type]
    result = []
    for v in vendors:
        d = v.__dict__.copy() if hasattr(v, '__dict__') else dict(v)
        d.pop('_sa_instance_state', None)
        result.append(d)
    return result

@router.post("/vendors")
def create_vendor(vendor: dict, db: Session = Depends(get_db)):
    return inventory_service.create_vendor(db, vendor)

@router.put("/vendors/{vendor_id}")
def update_vendor(vendor_id: int, vendor: dict, db: Session = Depends(get_db)):
    return inventory_service.update_vendor(db, vendor_id, vendor)

@router.patch("/vendors/{vendor_id}/default-category")
def set_vendor_default_category(vendor_id: int, data: dict, db: Session = Depends(get_db)):
    from erp.backend.db.models import Vendor
    v = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not v:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Vendor not found")
    v.default_category_id = data.get("default_category_id")
    db.commit()
    return {"ok": True}

@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    return inventory_service.delete_vendor(db, vendor_id)

@router.get("/items")
def list_items(vendor_id: int = None, stocktake_group_id: int = None, db: Session = Depends(get_db)):
    return inventory_service.get_items(db, vendor_id=vendor_id, stocktake_group_id=stocktake_group_id)

@router.post("/items")
def create_item(item: dict, db: Session = Depends(get_db)):
    return inventory_service.create_item(db, item)

@router.patch("/items/reorder")
def reorder_items(data: dict, db: Session = Depends(get_db)):
    from erp.backend.db.models import Item as ItemModel
    for entry in data.get('items', []):
        item = db.query(ItemModel).filter(ItemModel.id == entry['id']).first()
        if item:
            item.display_order = entry.get('sort_order', 999)
    db.commit()
    return {"success": True}

@router.put("/items/{item_id}")
def update_item(item_id: int, item: dict, db: Session = Depends(get_db)):
    return inventory_service.update_item(db, item_id, item)

@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    return inventory_service.delete_item(db, item_id)

@router.post("/items/bulk-delete")
def bulk_delete_items(data: dict, db: Session = Depends(get_db)):
    from erp.backend.db.models import Item as ItemModel
    ids = data.get("ids", [])
    deleted = 0
    for item_id in ids:
        item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
        if item:
            db.delete(item)
            deleted += 1
    db.commit()
    return {"deleted": deleted}

# ─── Excel 匯入範本端點 ──────────────────────────────────────────────────────

@router.get("/items/import-template")
def items_import_template(db: Session = Depends(get_db)):
    """動態產生品項匯入 Excel 範本（含供應商/盤點群組下拉）"""
    from erp.backend.db.models import Vendor as VendorModel, StocktakeGroup
    from erp.backend.utils.excel_template import build_items_template
    from fastapi.responses import StreamingResponse
    import io

    vendors = [{"name": v.name} for v in db.query(VendorModel).order_by(VendorModel.name).all()]
    groups  = [{"name": g.name} for g in db.query(StocktakeGroup).all()]
    data = build_items_template(vendors, groups)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''%E5%93%81%E9%A0%85%E5%8C%AF%E5%85%A5%E7%AF%84%E6%9C%AC.xlsx"}
    )


@router.get("/vendors/import-template")
def vendors_import_template(db: Session = Depends(get_db)):
    """動態產生供應商匯入 Excel 範本（含付款方式/金流科目下拉）"""
    from erp.backend.db.models import PaymentMethod, CashFlowCategory
    from erp.backend.utils.excel_template import build_vendors_template
    from fastapi.responses import StreamingResponse
    import io

    methods = [{"name": m.name} for m in
               db.query(PaymentMethod).filter(PaymentMethod.is_active == True)
               .order_by(PaymentMethod.display_order).all()]
    cats = [{"name": c.name} for c in
            db.query(CashFlowCategory).filter(CashFlowCategory.type == "expense").all()]
    data = build_vendors_template(methods, cats)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename*=UTF-8''%E4%BE%9B%E6%87%89%E5%95%86%E5%8C%AF%E5%85%A5%E7%AF%84%E6%9C%AC.xlsx"}
    )


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
    status: Optional[str] = "confirmed"

@router.post("/orders")
async def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    user_id = 1 # Temporary placeholder
    items_dicts = [item.dict() for item in order_data.items]
    order = inventory_service.create_purchase_order(
        db, user_id, order_data.vendor_id, items_dicts, order_data.expected_delivery_date,
        status=order_data.status or "confirmed"
    )

    # 送出後推播 LINE 訊息至廠商群組
    try:
        vendor = db.query(Vendor).filter(Vendor.id == order_data.vendor_id).first()
        if vendor and vendor.line_id:
            access_token = get_setting(db, "line_access_token")
            if access_token:
                from datetime import datetime as dt
                today = dt.now().strftime('%Y/%m/%d')
                msg = f"【叫貨單】{vendor.name}\n日期：{today}\n──────────\n"
                for item_data in items_dicts:
                    if item_data.get('item_id'):
                        item = db.query(Item).filter(Item.id == item_data['item_id']).first()
                        if item:
                            msg += f"{item.name} × {item_data['qty']} {item.unit or ''}\n"
                    elif item_data.get('adhoc_name'):
                        msg += f"{item_data['adhoc_name']} × {item_data['qty']} {item_data.get('adhoc_unit', '')}\n"
                msg += "──────────"
                if order_data.expected_delivery_date:
                    d = order_data.expected_delivery_date
                    msg += f"\n預計到貨：{d.year}/{d.month}/{d.day}"
                await send_line_message(vendor.line_id, msg, access_token)
    except Exception as e:
        print(f"LINE send error: {e}")

    return order

@router.put("/orders/{order_id}")
def update_order(order_id: int, order_data: OrderCreate, db: Session = Depends(get_db)):
    items_dicts = [item.dict() for item in order_data.items]
    try:
        return inventory_service.update_purchase_order(
            db, order_id, order_data.vendor_id, items_dicts, order_data.expected_delivery_date
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/orders")
def list_orders(days_limit: int = None, status: str = None, limit: int = 500, db: Session = Depends(get_db)):
    from erp.backend.db.models import User, PurchaseOrderDetail
    orders = inventory_service.get_orders(db, days_limit=days_limit, status=status)
    # Preload items for reference_amount calculation
    all_items = {i.id: i for i in db.query(inventory_service.Item).all()}
    all_details = db.query(PurchaseOrderDetail).all()
    details_by_order = {}
    for d in all_details:
        details_by_order.setdefault(d.order_id, []).append(d)
    result = []
    for order in orders:
        vendor = db.query(inventory_service.Vendor).filter(inventory_service.Vendor.id == order.vendor_id).first()
        ordered_by = None
        if order.user_id:
            user = db.query(User).filter(User.id == order.user_id).first()
            if user:
                ordered_by = {
                    "id": user.id,
                    "name": "(已刪除帳號)" if user.deleted_at else (user.full_name or user.username)
                }
        received_by = None
        if hasattr(order, 'receive_user_id') and order.receive_user_id:
            recv_user = db.query(User).filter(User.id == order.receive_user_id).first()
            if recv_user:
                received_by = {
                    "id": recv_user.id,
                    "name": "(已刪除帳號)" if recv_user.deleted_at else (recv_user.full_name or recv_user.username)
                }
        ref_amount = sum(
            float(d.qty or 0) * float(all_items[d.item_id].price or 0)
            for d in details_by_order.get(order.id, [])
            if d.item_id and d.item_id in all_items and all_items[d.item_id].price
        )
        result.append({
            "id": order.id,
            "vendor_id": order.vendor_id,
            "vendor_name": vendor.name if vendor else "Unknown",
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "status": order.status,
            "total_items": order.total_items,
            "expected_delivery_date": order.expected_delivery_date,
            "total_amount": order.total_amount,
            "amount_paid": order.amount_paid,
            "reference_amount": ref_amount,
            "is_paid": order.is_paid,
            "is_prepaid": order.is_prepaid or False,
            "receipt_url": order.receipt_url,
            "note": order.note,
            "ordered_by": ordered_by,
            "received_by": received_by,
            "created_by": ordered_by
        })
    return result

class OrderReceive(BaseModel):
    amount_paid: float
    total_amount: float = 0.0
    is_paid: bool = False
    note: Optional[str] = None
    receive_photo_url: Optional[str] = None
    payment_mode: Optional[str] = None  # 'cash' | 'pre_paid' | 'unpaid'

@router.post("/orders/{order_id}/receive")
def receive_order(order_id: int, receive_data: OrderReceive, db: Session = Depends(get_db)):
    from erp.backend.db.models import PurchaseOrder as PO
    user_id = 1
    # 若叫貨時已標記「已收款」，自動套用 pre_paid
    payment_mode = receive_data.payment_mode
    if not payment_mode:
        order_obj = db.query(PO).filter(PO.id == order_id).first()
        if order_obj and order_obj.is_prepaid:
            payment_mode = 'pre_paid'
    return inventory_service.receive_order(
        db, order_id, user_id,
        receive_data.amount_paid, receive_data.total_amount,
        receive_data.is_paid, receive_data.note,
        receive_data.receive_photo_url,
        payment_mode
    )

import os
from fastapi import UploadFile, File
from fastapi.responses import FileResponse
import shutil

UPLOAD_DIR = "/home/mason_ycw/boiling-noodles-dashboard/erp/backend/uploads"

@router.post("/orders/{order_id}/receipt")
def upload_receipt(order_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
        
    file_extension = file.filename.split(".")[-1]
    filename = f"receipt_order_{order_id}_{datetime.now().strftime('%Y%md%H%M%S')}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    url_path = f"/api/v1/inventory/uploads/{filename}"
    inventory_service.update_order_receipt(db, order_id, url_path)
    return {"receipt_url": url_path}

@router.get("/uploads/{filename}")
def get_upload_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

class OrderPatch(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None
    ordered_at: Optional[str] = None
    expected_delivery_date: Optional[str] = None
    total_amount: Optional[float] = None
    is_prepaid: Optional[bool] = None
    items: Optional[List[OrderItemCreate]] = None

@router.patch("/orders/{order_id}")
def patch_order(order_id: int, data: OrderPatch, db: Session = Depends(get_db)):
    from erp.backend.db.models import PurchaseOrder, PurchaseOrderDetail
    from datetime import datetime as dt
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if data.status is not None:
        order.status = data.status
    if data.note is not None:
        order.note = data.note
    if data.ordered_at is not None:
        try:
            order.created_at = dt.fromisoformat(data.ordered_at)
        except Exception:
            pass
    if data.expected_delivery_date is not None:
        try:
            order.expected_delivery_date = dt.fromisoformat(data.expected_delivery_date)
        except Exception:
            pass
    if data.total_amount is not None:
        order.total_amount = data.total_amount
    if data.is_prepaid is not None:
        order.is_prepaid = data.is_prepaid
    if data.items is not None:
        db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.order_id == order_id).delete()
        for item in data.items:
            db.add(PurchaseOrderDetail(
                order_id=order_id,
                item_id=item.item_id,
                adhoc_name=item.adhoc_name,
                adhoc_unit=item.adhoc_unit,
                qty=item.qty
            ))
        order.total_items = len(data.items)
    db.commit()
    return {"success": True}

@router.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    inventory_service.delete_purchase_order(db, order_id)
    return {"message": "Order deleted"}

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
            "unit": unit,
            "item_id": d.item_id,
            "adhoc_name": d.adhoc_name,
            "adhoc_unit": d.adhoc_unit
        })
    return result


# ─────────────────────────────────────────────
# P3-0: 品項分類 CRUD
# ─────────────────────────────────────────────
from erp.backend.db.models import ItemCategory, Item as ItemModel

@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    cats = db.query(ItemCategory).order_by(ItemCategory.display_order, ItemCategory.name).all()
    result = []
    for c in cats:
        item_count = db.query(ItemModel).filter(ItemModel.category_id == c.id, ItemModel.is_active == True).count()
        examples = db.query(ItemModel.name).filter(ItemModel.category_id == c.id, ItemModel.is_active == True).limit(3).all()
        result.append({
            "id": c.id,
            "name": c.name,
            "display_order": c.display_order,
            "item_count": item_count,
            "example_items": [e[0] for e in examples],
        })
    return result

class CategoryCreate(BaseModel):
    name: str
    display_order: int = 0

@router.post("/categories")
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    existing = db.query(ItemCategory).filter(ItemCategory.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="分類名稱已存在")
    cat = ItemCategory(name=data.name.strip(), display_order=data.display_order)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "item_count": 0, "example_items": []}

@router.put("/categories/{cat_id}")
def update_category(cat_id: int, data: CategoryCreate, db: Session = Depends(get_db)):
    cat = db.query(ItemCategory).filter(ItemCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="分類不存在")
    dup = db.query(ItemCategory).filter(ItemCategory.name == data.name, ItemCategory.id != cat_id).first()
    if dup:
        raise HTTPException(status_code=400, detail="分類名稱已存在")
    cat.name = data.name.strip()
    cat.display_order = data.display_order
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name}

@router.delete("/categories/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db)):
    cat = db.query(ItemCategory).filter(ItemCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="分類不存在")
    item_count = db.query(ItemModel).filter(ItemModel.category_id == cat_id, ItemModel.is_active == True).count()
    if item_count > 0:
        raise HTTPException(status_code=400, detail=f"此分類有 {item_count} 個品項，請先移除品項")
    db.delete(cat)
    db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────
# P3-3: 盤點差異分析
# ─────────────────────────────────────────────
from erp.backend.db.models import PurchaseOrder, PurchaseOrderDetail, WasteRecord
from datetime import timedelta

@router.get("/items/{item_id}/discrepancy-analysis")
def discrepancy_analysis(item_id: int, days: int = 7, db: Session = Depends(get_db)):
    item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="品項不存在")

    from sqlalchemy import func as sqlfunc
    cutoff = datetime.utcnow() - timedelta(days=days)

    # 近 N 天到貨紀錄（status=received 的訂單）
    received_orders = (
        db.query(PurchaseOrder, PurchaseOrderDetail)
        .join(PurchaseOrderDetail, PurchaseOrder.id == PurchaseOrderDetail.order_id)
        .filter(
            PurchaseOrderDetail.item_id == item_id,
            PurchaseOrder.status == "received",
            PurchaseOrder.updated_at >= cutoff
        )
        .order_by(PurchaseOrder.updated_at.desc())
        .all()
    )
    deliveries = []
    total_received = 0.0
    for order, detail in received_orders:
        qty = float(detail.actual_qty or detail.qty or 0)
        total_received += qty
        deliveries.append({
            "date": order.updated_at.strftime("%m/%d") if order.updated_at else "",
            "vendor_id": order.vendor_id,
            "qty": qty,
            "unit": item.unit or "",
            "status": "簽收"
        })

    # 近 N 天損耗紀錄
    waste_records = (
        db.query(WasteRecord)
        .filter(
            WasteRecord.item_id == item_id,
            WasteRecord.created_at >= cutoff
        )
        .order_by(WasteRecord.created_at.desc())
        .all()
    )
    wastes = []
    total_waste = 0.0
    for w in waste_records:
        qty = float(w.qty or 0)
        total_waste += qty
        wastes.append({
            "date": w.created_at.strftime("%m/%d") if w.created_at else "",
            "reason": w.reason or "損耗",
            "qty": qty,
            "unit": w.unit or item.unit or ""
        })

    # 計算理論剩餘
    current_stock = float(item.current_stock or 0)
    theoretical = current_stock + total_waste  # 如果實盤=current_stock，理論=盤點值+損耗
    # 差異分析
    diff_text = ""
    if abs(theoretical - current_stock) <= 0.5:
        diff_text = f"理論剩餘約 {theoretical:.1f} {item.unit or ''}，差異在合理範圍內 ✓"
    else:
        diff_text = f"理論剩餘約 {theoretical:.1f} {item.unit or ''}，與系統庫存差異 {theoretical - current_stock:+.1f}，建議核查"

    return {
        "item_id": item_id,
        "item_name": item.name,
        "current_stock": current_stock,
        "unit": item.unit or "",
        "days": days,
        "deliveries": deliveries,
        "total_received": total_received,
        "wastes": wastes,
        "total_waste": total_waste,
        "analysis_summary": diff_text
    }
