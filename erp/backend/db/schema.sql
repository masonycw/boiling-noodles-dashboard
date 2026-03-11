-- ERP Phase 1: Authentication & Authorization Schema

-- Roles enum or table. For simplicity, we'll start with a check constraint on erp_users.
-- Roles: 'admin', 'manager', 'staff'

CREATE TABLE IF NOT EXISTS erp_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'staff' CHECK (role IN ('admin', 'manager', 'staff')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Device Tracking / Remember Me
CREATE TABLE IF NOT EXISTS erp_user_devices (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES erp_users(id) ON DELETE CASCADE,
    device_id VARCHAR(255) NOT NULL, -- Unique identifier for the device/browser
    refresh_token VARCHAR(512) NOT NULL, -- Long-lived token for remember me
    device_name VARCHAR(100), -- User friendly name like "Mason's iPhone"
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(user_id, device_id)
);

-- Audit Logs for basic compliance
CREATE TABLE IF NOT EXISTS erp_audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES erp_users(id),
    action VARCHAR(100) NOT NULL, -- e.g., 'login', 'create_order', 'update_inventory'
    resource VARCHAR(100), -- e.g., 'orders', 'users'
    resource_id VARCHAR(50),
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_erp_users_username ON erp_users(username);
CREATE INDEX IF NOT EXISTS idx_erp_user_devices_token ON erp_user_devices(refresh_token);
