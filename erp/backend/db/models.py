from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey,
    JSON, Numeric, ARRAY, Time, Text, Enum as SAEnum
)
from sqlalchemy.sql import func
from erp.backend.db.session import Base
import enum


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class StocktakeModeEnum(str, enum.Enum):
    stocktake = "stocktake"          # 純盤點
    order = "order"                  # 純叫貨
    both = "both"                    # 盤點＋叫貨

class PettyCashTypeEnum(str, enum.Enum):
    income = "income"                # 現金撥入
    expense = "expense"              # 現場費用支出
    withdrawal = "withdrawal"        # 提領（取出存銀行）

class PaymentTermsEnum(str, enum.Enum):
    cash = "cash"                    # 現付
    monthly = "monthly"              # 月結
    after_delivery = "after_delivery"  # 後結（貨到後N天）


# ─────────────────────────────────────────────
# Phase 1：使用者 / 設備 / 稽核
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "erp_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, nullable=False, default="staff")  # admin / manager / staff
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))
    # Phase 3 新增
    petty_cash_permission = Column(Boolean, default=False)  # 零用金提領授權


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


# ─────────────────────────────────────────────
# Phase 2：供應商 / 品項 / 叫貨 / 收貨
# ─────────────────────────────────────────────

class Vendor(Base):
    __tablename__ = "erp_vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    contact_person = Column(String)
    phone = Column(String)
    delivery_days = Column(JSON)           # 送貨日 e.g. [1,3,5]
    order_deadline = Column(Time)          # 截單時間
    message_template = Column(String, server_default='{item_name} {qty} {unit}')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Phase 3 新增
    expense_category = Column(String)                        # 預設支出科目
    payment_terms = Column(String, default="cash")           # cash / monthly / after_delivery
    payment_days = Column(Integer, default=0)                # 後結天數（after_delivery 時用）
    bank_account = Column(String)                            # 匯款帳號
    bank_name = Column(String)                               # 銀行名稱
    free_shipping_threshold = Column(Numeric(10, 2))         # 免運門檻金額
    delivery_days_to_arrive = Column(Integer, default=1)     # D+N 到貨天數
    note = Column(Text)                                      # 備注
    # P1-0 新增
    line_id = Column(String)                                 # LINE ID
    bank_account_holder = Column(String)                     # 銀行戶名
    reminder_days = Column(Integer, default=5)               # 到期前提醒天數
    order_cycle = Column(String)                             # 叫貨週期文字
    payment_method = Column(String)                          # 付款方式（現金/轉帳/支票）


class ItemCategory(Base):
    __tablename__ = "erp_item_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    display_order = Column(Integer, default=0)


class StocktakeGroup(Base):
    """盤點群組（例如：冷藏、冷凍、常溫）"""
    __tablename__ = "erp_stocktake_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # P1-3 新增
    description = Column(Text)                               # 群組說明
    suggested_frequency = Column(String)                     # 建議盤點頻率


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
    # Phase 3 新增
    stocktake_group_id = Column(Integer, ForeignKey("erp_stocktake_groups.id"), nullable=True)
    display_order = Column(Integer, default=0)               # 叫貨/盤點顯示順序
    secondary_unit = Column(String)                          # 第二單位（例：箱）
    secondary_unit_ratio = Column(Numeric(10, 4))            # 換算比例（1箱=N個）
    # P1-1 新增
    category = Column(String)                                # 品項分類（文字）
    price = Column(Numeric(10, 2))                           # 參考單價


class PurchaseOrder(Base):
    __tablename__ = "erp_purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    vendor_id = Column(Integer, ForeignKey("erp_vendors.id"))
    status = Column(String, default="pending")               # pending / confirmed / received / cancelled
    total_items = Column(Integer, default=0)
    note = Column(String)
    expected_delivery_date = Column(DateTime(timezone=True))
    amount_paid = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), default=0)
    is_paid = Column(Boolean, default=False)
    receipt_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Phase 3 新增
    confirmation_status = Column(String, default="unconfirmed")  # unconfirmed / confirmed（廠商確認）


class PurchaseOrderDetail(Base):
    __tablename__ = "erp_purchase_order_details"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("erp_purchase_orders.id", ondelete="CASCADE"))
    item_id = Column(Integer, ForeignKey("erp_items.id"), nullable=True)
    adhoc_name = Column(String)                              # 臨時品項名稱
    adhoc_unit = Column(String)                              # 臨時品項單位
    qty = Column(Numeric(10, 2), nullable=False)             # 叫貨數量
    actual_qty = Column(Numeric(10, 2))                      # 實收數量
    price_at_order = Column(Numeric(10, 2))
    # Phase 3 新增
    discrepancy = Column(Numeric(10, 2))                     # 差異數量（actual_qty - qty）
    discrepancy_reason = Column(String)                      # 差異原因


class InventoryTransaction(Base):
    __tablename__ = "erp_inventory_transactions"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("erp_items.id"))
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    type = Column(String, nullable=False)                    # receive / waste / adjust / stocktake
    qty = Column(Numeric(10, 2), nullable=False)
    reason = Column(String)
    reference_id = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Phase 3：盤點
# ─────────────────────────────────────────────

class Stocktake(Base):
    """盤點單"""
    __tablename__ = "erp_stocktakes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    stocktake_group_id = Column(Integer, ForeignKey("erp_stocktake_groups.id"), nullable=True)
    mode = Column(
        SAEnum(StocktakeModeEnum, name="stocktake_mode_enum", create_type=False),
        nullable=False,
        default=StocktakeModeEnum.stocktake
    )
    status = Column(String, default="draft")                 # draft / submitted
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True))


class StocktakeItem(Base):
    """盤點品項"""
    __tablename__ = "erp_stocktake_items"

    id = Column(Integer, primary_key=True, index=True)
    stocktake_id = Column(Integer, ForeignKey("erp_stocktakes.id", ondelete="CASCADE"))
    item_id = Column(Integer, ForeignKey("erp_items.id"))
    counted_qty = Column(Numeric(10, 2))                     # 實際盤點數量
    expected_qty = Column(Numeric(10, 2))                    # 系統預期數量
    order_qty = Column(Numeric(10, 2))                       # 叫貨建議數量（mode=both 時填入）
    note = Column(String)


# ─────────────────────────────────────────────
# Phase 3：損耗
# ─────────────────────────────────────────────

class WasteRecord(Base):
    """損耗紀錄"""
    __tablename__ = "erp_waste_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    item_id = Column(Integer, ForeignKey("erp_items.id"), nullable=True)
    adhoc_name = Column(String)                              # 非品項的臨時名稱
    qty = Column(Numeric(10, 2), nullable=False)
    unit = Column(String)
    reason = Column(String)                                  # 過期 / 損壞 / 試菜 / 其他 / 破損 / 烹調損耗
    estimated_value = Column(Numeric(10, 2))                 # 損耗估值 P2-0
    photo_url = Column(String)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Phase 3：零用金
# ─────────────────────────────────────────────

class PettyCashRecord(Base):
    """零用金記錄（收入 / 支出 / 提領）"""
    __tablename__ = "erp_petty_cash_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    type = Column(
        SAEnum(PettyCashTypeEnum, name="petty_cash_type_enum", create_type=False),
        nullable=False
    )
    amount = Column(Numeric(10, 2), nullable=False)
    note = Column(Text)
    photo_url = Column(String)                               # 提領時拍照
    vendor_id = Column(Integer, ForeignKey("erp_vendors.id"), nullable=True)  # 支出時關聯廠商
    order_id = Column(Integer, ForeignKey("erp_purchase_orders.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Phase 3：金流管理（帳款 / 科目 / 定期）
# ─────────────────────────────────────────────

class CashFlowCategory(Base):
    """金流科目分類"""
    __tablename__ = "erp_cash_flow_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)                    # income / expense
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class CashFlowRecord(Base):
    """金流明細記錄"""
    __tablename__ = "erp_cash_flow_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    category_id = Column(Integer, ForeignKey("erp_cash_flow_categories.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(String, nullable=False)                    # income / expense
    source = Column(String)                                  # manual / pos_sync / petty_cash / purchase
    description = Column(Text)
    vendor_id = Column(Integer, ForeignKey("erp_vendors.id"), nullable=True)
    is_categorized = Column(Boolean, default=True)           # False = 未分類（臨時支出）
    transaction_date = Column(DateTime(timezone=True))       # 實際發生日期
    is_locked = Column(Boolean, default=False)               # P2-3 日結後鎖定
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CashFlowRecurring(Base):
    """重複預約費用（固定月費等）"""
    __tablename__ = "erp_cash_flow_recurring"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)                    # 例：網路費、租金
    category_id = Column(Integer, ForeignKey("erp_cash_flow_categories.id"), nullable=True)
    amount = Column(Numeric(10, 2))                          # 金額已知才填
    type = Column(String, nullable=False)                    # income / expense
    day_of_month = Column(Integer)                           # 每月幾號
    vendor_id = Column(Integer, ForeignKey("erp_vendors.id"), nullable=True)
    note = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Phase 3：應付帳款
# ─────────────────────────────────────────────

class AccountsPayable(Base):
    """應付帳款（月結 / 後結廠商帳款）"""
    __tablename__ = "erp_accounts_payable"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("erp_vendors.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("erp_purchase_orders.id"), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    due_date = Column(DateTime(timezone=True))               # 應付日期
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime(timezone=True))
    paid_by_user_id = Column(Integer, ForeignKey("erp_users.id"), nullable=True)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Phase 3：通知
# ─────────────────────────────────────────────

class Notification(Base):
    """系統通知"""
    __tablename__ = "erp_notifications"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)                    # payable_due / uncategorized_expense / custom
    title = Column(String, nullable=False)
    body = Column(Text)
    target_user_id = Column(Integer, ForeignKey("erp_users.id"), nullable=True)  # NULL = 廣播全員
    is_read = Column(Boolean, default=False)
    reference_id = Column(Integer)                           # 關聯的資源 ID
    reference_type = Column(String)                          # 關聯的資源類型
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Phase 2 Legacy（保留）
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# P2-3：日結機制
# ─────────────────────────────────────────────

class DailySettlement(Base):
    """日結記錄"""
    __tablename__ = "erp_daily_settlements"

    id = Column(Integer, primary_key=True, index=True)
    settlement_date = Column(String, nullable=False, unique=True)  # YYYY-MM-DD
    income_total = Column(Numeric(12, 2), default=0)
    expense_total = Column(Numeric(12, 2), default=0)
    created_by_user_id = Column(Integer, ForeignKey("erp_users.id"), nullable=True)
    settled_by = Column(String, default="manual")            # manual / auto
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# Phase 2 Legacy（保留）
# ─────────────────────────────────────────────

class CashTransaction(Base):
    """舊版零用金記錄（保留向後相容）"""
    __tablename__ = "erp_cash_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"))
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(String, nullable=False)                    # withdrawal / expense / income
    category = Column(String)
    note = Column(String)
    order_id = Column(Integer, ForeignKey("erp_purchase_orders.id"), nullable=True)
    is_reconciled = Column(Boolean, default=False)
    has_receipt = Column(Boolean, default=False)
    receipt_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────
# P3-0: 通知設定
# ─────────────────────────────────────────────

class NotificationSetting(Base):
    """通知規則開關（每位使用者獨立設定）"""
    __tablename__ = "erp_notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("erp_users.id"), nullable=False)
    notification_type = Column(String, nullable=False)  # order, low_stock, delivery, settlement, payment, stocktake, waste, system
    is_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ─────────────────────────────────────────────
# P3-1: 比例費用規則
# ─────────────────────────────────────────────

class ProportionalFeeRule(Base):
    """比例費用規則（外送平台抽成、信用卡手續費等）"""
    __tablename__ = "erp_proportional_fee_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String)            # platform_fee, processing_fee, tax, other
    calculation_basis = Column(String)   # order_total, transaction_amount, taxable_sales, other
    percentage = Column(Numeric(5, 2), nullable=False)
    settlement_period = Column(String, default="monthly")  # monthly, quarterly, yearly
    is_active = Column(Boolean, default=True)
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
