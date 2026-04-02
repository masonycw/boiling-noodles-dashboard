from sqlalchemy.orm import Session
from erp.backend.db.models import Vendor, Item, PurchaseOrder, PurchaseOrderDetail
from datetime import datetime, timedelta

def get_vendors(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Vendor).filter(Vendor.is_active == True).offset(skip).limit(limit).all()

def get_items(db: Session, vendor_id: int = None, stocktake_group_id: int = None, skip: int = 0, limit: int = 200, include_inactive: bool = False):
    query = db.query(Item)
    if not include_inactive:
        query = query.filter(Item.is_active == True)
    if vendor_id:
        query = query.filter(Item.vendor_id == vendor_id)
    if stocktake_group_id:
        query = query.filter(Item.stocktake_group_id == stocktake_group_id)
    return query.order_by(Item.display_order, Item.name).offset(skip).limit(limit).all()

def create_purchase_order(db: Session, user_id: int, vendor_id: int, items_data: list, expected_delivery_date: datetime = None, status: str = "confirmed"):  # confirmed = 待收貨
    """
    items_data: list of dicts with {'item_id': int, 'qty': float}
    """
    db_po = PurchaseOrder(
        user_id=user_id,
        vendor_id=vendor_id,
        status=status,
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
        # Support comma-separated status values e.g. "pending,confirmed"
        status_list = [s.strip() for s in status.split(',') if s.strip()]
        if len(status_list) == 1:
            query = query.filter(PurchaseOrder.status == status_list[0])
        else:
            query = query.filter(PurchaseOrder.status.in_(status_list))
    return query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit).all()

from erp.backend.services.finance_service import create_transaction, create_petty_cash_record

def receive_order(db: Session, order_id: int, user_id: int, amount_paid: float,
                  total_amount: float = 0.0, is_paid: bool = False,
                  note: str = None, receive_photo_url: str = None,
                  payment_mode: str = None):
    """
    payment_mode:
      'cash'     – 現場現金付款（扣零用金）
      'pre_paid' – 已收款（匯款/轉帳，不動零用金）
      'unpaid'   – 未付款，建立應付帳款
    若 payment_mode 未傳，由 is_paid 向後兼容推導。
    """
    # 向後兼容：若未傳 payment_mode，由舊 is_paid 推導
    if payment_mode is None:
        payment_mode = 'cash' if is_paid else 'unpaid'

    actually_paid = payment_mode in ('cash', 'pre_paid')

    db_po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not db_po:
        raise Exception("Order not found")

    db_po.status = "received"
    db_po.receive_user_id = user_id
    db_po.total_amount = total_amount
    db_po.is_paid = actually_paid
    db_po.amount_paid = amount_paid if actually_paid else 0.0
    if note:
        db_po.note = note
    if receive_photo_url:
        db_po.receipt_url = receive_photo_url

    # 取得廠商資訊
    vendor_name = None
    vendor_cat_id = None
    vendor_payment_terms = 'cash'
    vendor_payment_days = 0
    if db_po.vendor_id:
        from erp.backend.db.models import Vendor as VendorModel
        vdr = db.query(VendorModel).filter(VendorModel.id == db_po.vendor_id).first()
        if vdr:
            vendor_name = vdr.name
            if hasattr(vdr, 'default_category_id'):
                vendor_cat_id = vdr.default_category_id
            vendor_payment_terms = vdr.payment_terms or 'cash'
            vendor_payment_days = vdr.payment_days or 0

    bill_amount = total_amount if total_amount > 0 else (amount_paid if amount_paid > 0 else 0.0)
    note_text = f"訂單 #{order_id} 進貨{' - ' + vendor_name if vendor_name else ''}{': ' + note if note else ''}"

    if bill_amount > 0:
        if payment_mode == 'cash':
            # 現金付款：建立零用金支出（已付）＋金流紀錄
            create_petty_cash_record(db, user_id, {
                "type": "expense", "amount": bill_amount,
                "note": note_text, "photo_url": receive_photo_url,
                "vendor_id": db_po.vendor_id, "order_id": order_id, "is_paid": True,
            })
            create_transaction(db, user_id, {
                "amount": bill_amount, "type": "expense",
                "category_id": vendor_cat_id, "category": "進貨付款",
                "note": f"訂單 #{order_id} 貨款: {note or ''}", "order_id": order_id
            })
        elif payment_mode == 'pre_paid':
            # 已收款（匯款等）：不動零用金，只記金流
            create_transaction(db, user_id, {
                "amount": bill_amount, "type": "expense",
                "category_id": vendor_cat_id, "category": "進貨付款",
                "note": f"訂單 #{order_id} 貨款（已收款）: {note or ''}", "order_id": order_id
            })
        elif payment_mode == 'unpaid':
            # 未付款：建立零用金待付記錄
            create_petty_cash_record(db, user_id, {
                "type": "expense", "amount": bill_amount,
                "note": note_text, "photo_url": receive_photo_url,
                "vendor_id": db_po.vendor_id, "order_id": order_id, "is_paid": False,
            })
            # 建立應付帳款，依廠商付款條件計算到期日
            from erp.backend.db.models import AccountsPayable
            from datetime import date as date_cls, timedelta
            today = date_cls.today()
            pt = vendor_payment_terms
            if pt in ('月結', 'monthly'):
                # 下個月5號
                if today.month == 12:
                    due = date_cls(today.year + 1, 1, 5)
                else:
                    due = date_cls(today.year, today.month + 1, 5)
            elif pt in ('週結', 'weekly'):
                # 下個禮拜一（weekday 0=週一，若今天是週一則取下週一）
                days_ahead = (7 - today.weekday()) % 7 or 7
                due = today + timedelta(days=days_ahead)
            elif pt in ('後收款', 'after_delivery'):
                due = today + timedelta(days=max(1, vendor_payment_days or 14))
            else:
                due = today  # 現付但未付 → 今日即到期
            db.add(AccountsPayable(
                vendor_id=db_po.vendor_id,
                order_id=order_id,
                amount=bill_amount,
                due_date=due,
                is_paid=False,
                note=note_text,
            ))

    # 收貨後更新各品項庫存
    details = db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.order_id == order_id).all()
    for detail in details:
        if detail.item_id:
            item = db.query(Item).filter(Item.id == detail.item_id).first()
            if item:
                qty_received = float(detail.actual_qty or detail.qty or 0)
                item.current_stock = float(item.current_stock or 0) + qty_received

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
    from erp.backend.db.models import StocktakeItem, PurchaseOrderDetail, WasteRecord, InventoryTransaction
    db_item = db.query(Item).filter(Item.id == item_id).first()
    if db_item:
        db.query(StocktakeItem).filter(StocktakeItem.item_id == item_id).update({"item_id": None})
        db.query(PurchaseOrderDetail).filter(PurchaseOrderDetail.item_id == item_id).update({"item_id": None})
        db.query(WasteRecord).filter(WasteRecord.item_id == item_id).update({"item_id": None})
        db.query(InventoryTransaction).filter(InventoryTransaction.item_id == item_id).update({"item_id": None})
        db.delete(db_item)
        db.commit()
    return {"deleted": True}
