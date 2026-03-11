-- ERP Phase 2: Inventory & Ordering Schema

-- Vendors Table
CREATE TABLE IF NOT EXISTS erp_vendors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    -- Delivery days: 0=Sun, 1=Mon, ..., 6=Sat. Stored as integer array.
    delivery_days INTEGER[] DEFAULT '{1,2,3,4,5,6}', 
    order_deadline TIME, -- e.g., '21:00:00'
    message_template TEXT DEFAULT '{item_name} {qty} {unit}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Item Categories (Optional but good for organization)
CREATE TABLE IF NOT EXISTS erp_item_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

-- Items Table
CREATE TABLE IF NOT EXISTS erp_items (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    category_id INTEGER REFERENCES erp_item_categories(id),
    vendor_id INTEGER REFERENCES erp_vendors(id),
    min_stock DECIMAL(10, 2) DEFAULT 0,
    current_stock DECIMAL(10, 2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Purchase Orders (叫貨單)
CREATE TABLE IF NOT EXISTS erp_purchase_orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES erp_users(id),
    vendor_id INTEGER REFERENCES erp_vendors(id),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'ordered', 'received', 'cancelled')),
    total_items INTEGER DEFAULT 0,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Purchase Order Details
CREATE TABLE IF NOT EXISTS erp_purchase_order_details (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES erp_purchase_orders(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES erp_items(id),
    qty DECIMAL(10, 2) NOT NULL,
    actual_qty DECIMAL(10, 2), -- Fill this during verification/receiving
    price_at_order DECIMAL(10, 2) -- To track price changes
);

-- Inventory Transactions (Log for every change)
CREATE TABLE IF NOT EXISTS erp_inventory_transactions (
    id SERIAL PRIMARY KEY,
    item_id INTEGER REFERENCES erp_items(id),
    user_id INTEGER REFERENCES erp_users(id),
    type VARCHAR(20) NOT NULL CHECK (type IN ('in', 'out', 'adjustment')),
    qty DECIMAL(10, 2) NOT NULL,
    reason VARCHAR(255),
    reference_id VARCHAR(50), -- e.g., PO number or manual adj ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create some indexes
CREATE INDEX IF NOT EXISTS idx_erp_items_vendor ON erp_items(vendor_id);
CREATE INDEX IF NOT EXISTS idx_erp_po_status ON erp_purchase_orders(status);
