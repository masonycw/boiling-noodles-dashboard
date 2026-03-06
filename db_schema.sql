-- 滾麵 智慧報表 PostgreSQL 核心資料表 Schema

-- ==========================================
-- 1. 明細單層級 (Transaction Fact Table)
-- ==========================================
-- 儲存每一筆訂單的明細，包含各種商品、金額、客人等資訊
CREATE TABLE IF NOT EXISTS orders_fact (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL UNIQUE, -- 可能包含前綴 (例如：YYYYMMDD-oid-HHMM)
    date TIMESTAMP NOT NULL,
    total_amount NUMERIC(10, 2) DEFAULT 0,
    status VARCHAR(50),
    order_type VARCHAR(20), -- 內用, 外帶, 外送, 自取
    people_count INTEGER DEFAULT 1,
    payment_method VARCHAR(50),
    member_phone VARCHAR(50),
    customer_name VARCHAR(100),
    invoice_id VARCHAR(50),
    data_source VARCHAR(20) DEFAULT 'csv', -- 'csv' 或 'json'
    day_type VARCHAR(20), -- '平日 (Weekday)' 或 '假日 (Holiday)'
    period VARCHAR(20), -- '中午 (Lunch)' 或 '晚上 (Dinner)'
    member_id VARCHAR(50), -- 識別後的唯一會員 ID (如 CRM_0912..., Carrier_123...)
    order_category VARCHAR(50), -- '內用 (Dine-in)', '外帶 (Takeout)', '外送 (Delivery)'
    
    -- 記錄此筆訂單包含的主要商品數量 (Main Dishes)
    main_dish_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 建立索引加速查詢
CREATE INDEX IF NOT EXISTS idx_orders_fact_date ON orders_fact(date);
CREATE INDEX IF NOT EXISTS idx_orders_fact_member_id ON orders_fact(member_id);
CREATE INDEX IF NOT EXISTS idx_orders_fact_order_id ON orders_fact(order_id);

-- ==========================================
-- 2. 每日營收聚合 (Daily Revenue Aggregation)
-- ==========================================
-- 以「天」為單位先算好各項指標，Dashbaord 讀取這裡可以快 10 倍以上
CREATE TABLE IF NOT EXISTS daily_revenue_agg (
    date DATE PRIMARY KEY,
    total_revenue NUMERIC(12, 2) DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    total_guests INTEGER DEFAULT 0, -- 依據主餐數量計算的客流量
    average_ticket_size NUMERIC(10, 2) DEFAULT 0, -- total_revenue / total_orders
    average_unit_price NUMERIC(10, 2) DEFAULT 0, -- total_revenue / total_guest
    
    -- 餐期拆分
    lunch_revenue NUMERIC(12, 2) DEFAULT 0,
    dinner_revenue NUMERIC(12, 2) DEFAULT 0,
    
    -- 內用/外帶外送拆分
    dine_in_revenue NUMERIC(12, 2) DEFAULT 0,
    takeout_revenue NUMERIC(12, 2) DEFAULT 0,
    delivery_revenue NUMERIC(12, 2) DEFAULT 0,
    
    -- 客群拆分 (根據會員識別)
    new_customer_revenue NUMERIC(12, 2) DEFAULT 0,
    returning_customer_revenue NUMERIC(12, 2) DEFAULT 0,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ==========================================
-- 3. 會員輪廓視圖/聚合表 (Member Profile Aggregation)
-- ==========================================
-- 每個會員的 RFM 指標與基本資料，加速 CRM 查詢
CREATE TABLE IF NOT EXISTS member_profile_agg (
    member_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(100),
    member_phone VARCHAR(50),
    
    -- RFM 指標
    first_visit_date DATE,
    last_visit_date DATE,
    total_visits INTEGER DEFAULT 0,
    total_spent NUMERIC(12, 2) DEFAULT 0,
    average_spent_per_visit NUMERIC(10, 2) DEFAULT 0,
    
    -- 偏好
    favorite_order_category VARCHAR(50), -- 最常使用的點餐方式
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_member_profile_last_visit ON member_profile_agg(last_visit_date);

-- ==========================================
-- Table: order_details_fact
-- Description: Stores individual line items for each order
-- ==========================================
CREATE TABLE IF NOT EXISTS order_details_fact (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    date TIMESTAMP NOT NULL,
    item_name VARCHAR(100),
    category VARCHAR(50),
    sku VARCHAR(50),
    item_type VARCHAR(50),
    item_total NUMERIC(10, 2) DEFAULT 0,
    qty NUMERIC(10, 2) DEFAULT 0,
    unit_price NUMERIC(10, 2) DEFAULT 0,
    options TEXT,
    is_modifier BOOLEAN DEFAULT FALSE,
    is_main_dish BOOLEAN DEFAULT FALSE,
    data_source VARCHAR(20) DEFAULT 'csv',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_order_details_order_id ON order_details_fact(order_id);
CREATE INDEX IF NOT EXISTS idx_order_details_date ON order_details_fact(date);
CREATE INDEX IF NOT EXISTS idx_order_details_category ON order_details_fact(category);
CREATE INDEX IF NOT EXISTS idx_order_details_sku ON order_details_fact(sku);
