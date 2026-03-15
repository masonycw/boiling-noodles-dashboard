-- ════════════════════════════════════════════════════════════════════
-- ERP Phase 3 Migration Script
-- 執行日期：2026-03-15
-- 說明：補充 Phase 3 所需的欄位與新資料表
-- ════════════════════════════════════════════════════════════════════

-- 安全模式：僅在欄位/表格不存在時才建立
BEGIN;

-- ─────────────────────────────────────────────
-- 1. 現有資料表欄位補充
-- ─────────────────────────────────────────────

-- 1A. erp_users：新增零用金提領授權
ALTER TABLE erp_users
    ADD COLUMN IF NOT EXISTS petty_cash_permission BOOLEAN DEFAULT FALSE;

-- 1B. erp_vendors：新增財務 / 物流相關欄位
ALTER TABLE erp_vendors
    ADD COLUMN IF NOT EXISTS expense_category VARCHAR(100),
    ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(30) DEFAULT 'cash',
    ADD COLUMN IF NOT EXISTS payment_days INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bank_account VARCHAR(100),
    ADD COLUMN IF NOT EXISTS bank_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS free_shipping_threshold NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS delivery_days_to_arrive INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS note TEXT;

-- 1C. erp_items：新增盤點群組 / 顯示順序 / 第二單位
ALTER TABLE erp_items
    ADD COLUMN IF NOT EXISTS stocktake_group_id INTEGER REFERENCES erp_stocktake_groups(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS secondary_unit VARCHAR(20),
    ADD COLUMN IF NOT EXISTS secondary_unit_ratio NUMERIC(10, 4);

-- 1D. erp_purchase_orders：新增廠商確認狀態
ALTER TABLE erp_purchase_orders
    ADD COLUMN IF NOT EXISTS confirmation_status VARCHAR(20) DEFAULT 'unconfirmed';

-- 1E. erp_purchase_order_details：新增差異記錄欄位
ALTER TABLE erp_purchase_order_details
    ADD COLUMN IF NOT EXISTS discrepancy NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS discrepancy_reason VARCHAR(200);

-- ─────────────────────────────────────────────
-- 2. ENUM Types（PostgreSQL 需先建立 type）
-- ─────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE stocktake_mode_enum AS ENUM ('stocktake', 'order', 'both');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE petty_cash_type_enum AS ENUM ('income', 'expense', 'withdrawal');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ─────────────────────────────────────────────
-- 3. 新增資料表
-- ─────────────────────────────────────────────

-- 3A. 盤點群組
CREATE TABLE IF NOT EXISTS erp_stocktake_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3B. 盤點單
CREATE TABLE IF NOT EXISTS erp_stocktakes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES erp_users(id),
    stocktake_group_id INTEGER REFERENCES erp_stocktake_groups(id) ON DELETE SET NULL,
    mode stocktake_mode_enum NOT NULL DEFAULT 'stocktake',
    status VARCHAR(20) DEFAULT 'draft',          -- draft / submitted
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE
);

-- 3C. 盤點品項
CREATE TABLE IF NOT EXISTS erp_stocktake_items (
    id SERIAL PRIMARY KEY,
    stocktake_id INTEGER REFERENCES erp_stocktakes(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES erp_items(id),
    counted_qty NUMERIC(10, 2),
    expected_qty NUMERIC(10, 2),
    order_qty NUMERIC(10, 2),                    -- 盤點+叫貨模式時使用
    note VARCHAR(200)
);

-- 3D. 損耗紀錄
CREATE TABLE IF NOT EXISTS erp_waste_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES erp_users(id),
    item_id INTEGER REFERENCES erp_items(id) ON DELETE SET NULL,
    adhoc_name VARCHAR(100),
    qty NUMERIC(10, 2) NOT NULL,
    unit VARCHAR(20),
    reason VARCHAR(100),                         -- 過期 / 破損 / 烹調損耗 / 其他
    photo_url TEXT,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3E. 零用金記錄
CREATE TABLE IF NOT EXISTS erp_petty_cash_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES erp_users(id),
    type petty_cash_type_enum NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    note TEXT,
    photo_url TEXT,                              -- 提領時需拍照
    vendor_id INTEGER REFERENCES erp_vendors(id) ON DELETE SET NULL,
    order_id INTEGER REFERENCES erp_purchase_orders(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3F. 金流科目分類
CREATE TABLE IF NOT EXISTS erp_cash_flow_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL,                   -- income / expense
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

-- 3G. 金流明細
CREATE TABLE IF NOT EXISTS erp_cash_flow_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES erp_users(id),
    category_id INTEGER REFERENCES erp_cash_flow_categories(id) ON DELETE SET NULL,
    amount NUMERIC(10, 2) NOT NULL,
    type VARCHAR(20) NOT NULL,                   -- income / expense
    source VARCHAR(50) DEFAULT 'manual',         -- manual / pos_sync / petty_cash / purchase
    description TEXT,
    vendor_id INTEGER REFERENCES erp_vendors(id) ON DELETE SET NULL,
    is_categorized BOOLEAN DEFAULT TRUE,
    transaction_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3H. 重複預約費用
CREATE TABLE IF NOT EXISTS erp_cash_flow_recurring (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category_id INTEGER REFERENCES erp_cash_flow_categories(id) ON DELETE SET NULL,
    amount NUMERIC(10, 2),
    type VARCHAR(20) NOT NULL,                   -- income / expense
    day_of_month INTEGER,                        -- 每月幾號
    vendor_id INTEGER REFERENCES erp_vendors(id) ON DELETE SET NULL,
    note TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3I. 應付帳款
CREATE TABLE IF NOT EXISTS erp_accounts_payable (
    id SERIAL PRIMARY KEY,
    vendor_id INTEGER REFERENCES erp_vendors(id) NOT NULL,
    order_id INTEGER REFERENCES erp_purchase_orders(id) ON DELETE SET NULL,
    amount NUMERIC(10, 2) NOT NULL,
    due_date TIMESTAMP WITH TIME ZONE,
    is_paid BOOLEAN DEFAULT FALSE,
    paid_at TIMESTAMP WITH TIME ZONE,
    paid_by_user_id INTEGER REFERENCES erp_users(id) ON DELETE SET NULL,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3J. 通知
CREATE TABLE IF NOT EXISTS erp_notifications (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,                   -- payable_due / uncategorized_expense / custom
    title VARCHAR(200) NOT NULL,
    body TEXT,
    target_user_id INTEGER REFERENCES erp_users(id) ON DELETE CASCADE,
    is_read BOOLEAN DEFAULT FALSE,
    reference_id INTEGER,
    reference_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- 4. Indexes
-- ─────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_stocktake_items_stocktake ON erp_stocktake_items(stocktake_id);
CREATE INDEX IF NOT EXISTS idx_waste_records_created ON erp_waste_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_petty_cash_created ON erp_petty_cash_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cash_flow_created ON erp_cash_flow_records(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cash_flow_type ON erp_cash_flow_records(type);
CREATE INDEX IF NOT EXISTS idx_accounts_payable_due ON erp_accounts_payable(due_date);
CREATE INDEX IF NOT EXISTS idx_accounts_payable_vendor ON erp_accounts_payable(vendor_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON erp_notifications(target_user_id);

-- ─────────────────────────────────────────────
-- 5. 初始資料（金流科目預設值）
-- ─────────────────────────────────────────────

INSERT INTO erp_cash_flow_categories (name, type, display_order)
VALUES
    ('食材成本', 'expense', 1),
    ('人事費用', 'expense', 2),
    ('租金', 'expense', 3),
    ('水電費', 'expense', 4),
    ('外送平台費', 'expense', 5),
    ('刷卡手續費', 'expense', 6),
    ('行銷費用', 'expense', 7),
    ('設備維修', 'expense', 8),
    ('雜支', 'expense', 9),
    ('現金收入', 'income', 1),
    ('外送平台撥款', 'income', 2),
    ('其他收入', 'income', 3)
ON CONFLICT DO NOTHING;

INSERT INTO erp_stocktake_groups (name, display_order)
VALUES
    ('冷藏', 1),
    ('冷凍', 2),
    ('常溫', 3),
    ('醬料調味', 4)
ON CONFLICT DO NOTHING;

COMMIT;

-- ════════════════════════════════════════════════════════════════════
-- 執行方式：psql -h <host> -U <user> -d boiling_noodles -f migrate_phase3.sql
-- ════════════════════════════════════════════════════════════════════
