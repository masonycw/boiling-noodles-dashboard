from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Numeric, ARRAY, Time
from sqlalchemy.sql import func
from erp.backend.db.session import Base

class User(Base):
    __tablename__ = "erp_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, nullable=False, default="staff")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))

class UserDevice(Base):
    __tablename__ = "erp_user_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id", ondelete="CASCADE"))
    device_id = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False, index=True)
    device_name = Column(String)
    last_seen = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

class AuditLog(Base):
    __tablename__ = "erp_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    action = Column(String, nullable=False)
    resource = Column(String)
    resource_id = Column(String)
    details = Column(JSON)
    ip_address = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Vendor(Base):
    __tablename__ = "erp_vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact_person = Column(String)
    phone = Column(String)
    delivery_days = Column(JSON)
    order_deadline = Column(Time)
    message_template = Column(String, server_default='{item_name} {qty} {unit}')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Item(Base):
    __tablename__ = "erp_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("erp_item_categories.id"))
    vendor_id = Column(Integer, ForeignKey("erp_vendors.id"))
    min_stock = Column(Numeric(10, 2), default=0)
    current_stock = Column(Numeric(10, 2), default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ItemCategory(Base):
    __tablename__ = "erp_item_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)

class PurchaseOrder(Base):
    __tablename__ = "erp_purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    vendor_id = Column(Integer, ForeignKey("erp_vendors.id"))
    status = Column(String, default="pending")
    total_items = Column(Integer, default=0)
    note = Column(String)
    expected_delivery_date = Column(DateTime(timezone=True))
    amount_paid = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), default=0)
    is_paid = Column(Boolean, default=False)
    receipt_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PurchaseOrderDetail(Base):
    __tablename__ = "erp_purchase_order_details"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("erp_purchase_orders.id", ondelete="CASCADE"))
    item_id = Column(Integer, ForeignKey("erp_items.id"), nullable=True)
    adhoc_name = Column(String)
    adhoc_unit = Column(String)
    qty = Column(Numeric(10, 2), nullable=False)
    actual_qty = Column(Numeric(10, 2))
    price_at_order = Column(Numeric(10, 2))

class InventoryTransaction(Base):
    __tablename__ = "erp_inventory_transactions"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("erp_items.id"))
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    type = Column(String, nullable=False)
    qty = Column(Numeric(10, 2), nullable=False)
    reason = Column(String)
    reference_id = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CashTransaction(Base):
    __tablename__ = "erp_cash_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(String, nullable=False) # 'withdrawal', 'expense', 'income'
    category = Column(String)
    note = Column(String)
    order_id = Column(Integer, ForeignKey("erp_purchase_orders.id"), nullable=True) # For reconciliation
    is_reconciled = Column(Boolean, default=False)
    has_receipt = Column(Boolean, default=False)
    receipt_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
