import os

# System Version
APP_VERSION = "2.3.3"

# --- Paths ---
# Define ROOT paths to scan recursively
DATA_DIRS = [
    "/home/eats365/data",          # Primary Data Root
    "/home/eats365/upload",        # Fallback Upload
    "/data",                       # Absolute Data Path (User's SFTP Root?)
    "/data/交易資料",               # Specific Directory (If not recursive from /data?)
    os.path.join(os.getcwd(), 'data'), # Local Data
    os.getcwd()                    # Local Root
]

# --- Column Synonym Dictionary (The "Universal Mapper") ---
# Format: 'Standard_Internal_Name': ['Alias1', 'Alias2', ...]

COLUMN_MAPPING = {
    # Report Columns
    'order_id': ['單號', '訂單編號', 'Order Number', 'Order No', 'No.'],
    'date': ['日期', 'Date', 'Time', '時間', '交易時間', '付款時間', '發票日期'], # Invoice date also valid
    'total_amount': ['總計', 'Total', 'Order Total', '金額', 'Order Total(TWD)'],
    'tax_id': ['統一編號', 'Tax ID', 'Buyer Tax ID', '買受人統編'],
    'source_id': ['來源訂單編號', 'Source ID', 'Source Order ID'],
    'member_phone': ['會員電話', 'Phone', 'Customer Phone', '客戶電話', 'Contact'],
    'customer_name': ['客戶姓名', 'Customer Name', 'Name', '買受人名稱'],
    'people_count': ['人數', 'People', 'Guest', 'Pax', '來客'],
    
    # Invoice Specific
    'invoice_id': ['電子發票號', '發票號碼', 'Invoice No', 'Invoice Number'],
    'carrier_id': ['載具號碼', 'Carrier Number', 'Carrier No', 'Mobile Carrier', '載具', 'Carrier'],
    
    'status': ['狀態', 'Status', 'Order Status', '發票狀態', 'Overall Status'],
    'order_type': ['單類型', 'Order Type', 'Type'],

    # Details Columns
    'item_name': ['Item Name', '商品名稱', 'Product Name'],
    'category': ['Category', '商品類別', 'Product Category'],
    'qty': ['Item Quantity', '數量', 'Qty', 'Quantity'],
    'unit_price': ['Unit Price', '單價', 'Price'],
    'item_total': ['Item Total', '小計', 'Subtotal', 'Item Amount(TWD)'],
    'options': ['Item Option', '選項', 'Options', 'Modifier Name', 'Product Note'], 
    'sku': ['Product SKU', 'SKU', '料號'],
    'item_type': ['Item Type', '商品型態', 'ItemType']
}

# --- Holidays ---
# 2024-2026 Taiwan Holidays
TW_HOLIDAYS = [
    # 2024
    "2024-01-01", "2024-02-08", "2024-02-09", "2024-02-10", "2024-02-11", "2024-02-12", "2024-02-13", "2024-02-14",
    "2024-02-28", "2024-04-04", "2024-04-05", "2024-05-01", "2024-06-10", "2024-09-17", "2024-10-10", "2024-12-25",
    # 2025
    "2025-01-01", "2025-01-25", "2025-01-26", "2025-01-27", "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31", 
    "2025-02-01", "2025-02-02", "2025-02-28", "2025-04-03", "2025-04-04", "2025-04-05", "2025-04-06", 
    "2025-05-01", "2025-05-31", "2025-06-01", "2025-06-02", "2025-10-04", "2025-10-05", "2025-10-06", 
    "2025-10-10", "2025-10-11", "2025-10-12", "2025-12-25",
    # 2026
    "2026-01-01", "2026-02-14", "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18",
    "2026-02-28", "2026-04-03", "2026-04-04", "2026-04-05", "2026-04-06", "2026-05-01", "2026-06-19", 
    "2026-09-25", "2026-09-26", "2026-09-27", "2026-09-28", "2026-10-09", "2026-10-10", "2026-10-11", "2026-10-24", "2026-10-25", "2026-10-26", "2026-12-25"
]
TW_HOLIDAYS_SET = set(TW_HOLIDAYS)
