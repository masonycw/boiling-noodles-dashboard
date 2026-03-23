# 滾麵 ERP — Claude Code 開發指南

> 最後更新：2026-03-24（P3 實作完成後）
> Git 倉庫：https://github.com/masonycw/boiling-noodles-dashboard
> 最新 commit：257c7e7（P3-0 ~ P3-4 全部完成）

---

## 1. 技術棧速覽

| 項目 | 說明 |
|------|------|
| 後端語言 | Python 3.11 · FastAPI · SQLAlchemy ORM · uvicorn |
| 前端框架 | Vue 3 · Vue Router 4 · Pinia · Vite · TailwindCSS |
| 資料庫 | PostgreSQL（遠端 GCP 伺服器） |
| 認證 | JWT（python-jose）· bcrypt 密碼雜湊 |
| 遠端伺服器 | 34.81.51.45 |
| 後端 Port | 8000（systemd: erp-backend） |
| 前台 PWA Port | 5173（systemd: erp-frontend） |
| 後台 Admin Port | 5174（systemd: erp-admin） |
| SSH 帳密 | mason_ycw / masonpass |
| API Base URL | http://34.81.51.45:8000/api/v1 |
| Swagger UI | http://34.81.51.45:8000/docs |

---

## 2. 目錄結構

```
erp/                                ← 本 CLAUDE.md 所在位置
├── CLAUDE.md                       ← 本文件
├── backend/
│   ├── main.py                     ← FastAPI app 入口，所有 router 在此 include
│   ├── api/
│   │   ├── auth.py                 ← prefix: /api/v1/auth
│   │   ├── inventory.py            ← prefix: /api/v1/inventory（叫貨/收貨/廠商/品項/分類/差異分析）
│   │   ├── finance.py              ← prefix: /api/v1（金流/零用金/日結/重複費用/比例費用/金流總覽）
│   │   ├── stocktake.py            ← prefix: /api/v1（盤點）
│   │   ├── waste.py                ← prefix: /api/v1（耗損）
│   │   ├── users.py                ← prefix: /api/v1（人員管理）
│   │   ├── notifications.py        ← prefix: /api/v1（通知 + 通知設定）
│   │   └── reports.py              ← prefix: /api/v1（損益報表）
│   ├── db/
│   │   ├── models.py               ← 所有 SQLAlchemy ORM Model（23 個表格）
│   │   ├── session.py              ← DB Session / engine
│   │   └── schema.sql              ← 基礎 SQL schema（參考用）
│   ├── core/
│   │   ├── config.py               ← env var 讀取
│   │   └── security.py             ← JWT 簽發/驗證/密碼 hash
│   ├── migrations/                 ← 遷移腳本（p1/p2/p3）
│   ├── services/
│   │   └── inventory_service.py    ← 庫存業務邏輯
│   ├── .env                        ← 本地開發環境變數
│   └── requirements.txt
├── frontend/                       ← Vue PWA App（port 5173）
│   ├── index.html                  ← PWA meta tags + manifest link
│   ├── public/
│   │   ├── manifest.json           ← PWA manifest（P3-4）
│   │   └── sw.js                   ← Service Worker（P3-4）
│   └── src/
│       ├── main.js                 ← SW 註冊 + install prompt capture
│       ├── views/
│       │   ├── LoginView.vue
│       │   ├── HomeView.vue
│       │   ├── InventoryView.vue   ← 叫貨（含草稿自動儲存 P3-3、D+N 倒數）
│       │   ├── StocktakeView.vue   ← 盤點（含草稿儲存 P3-3、差異分析 P3-3）
│       │   ├── FinanceView.vue     ← 零用金 + 日結
│       │   ├── WasteView.vue
│       │   ├── MoreView.vue        ← 含 PWA 安裝按鈕 P3-4
│       │   ├── HistoryView.vue
│       │   └── ManagementView.vue
│       ├── stores/auth.js          ← Pinia auth store（JWT token 管理）
│       └── router/index.js
└── admin/                          ← Vue Admin（port 5174）
    └── src/
        ├── views/                  ← 24 個 View 元件（見第 5 節）
        ├── stores/auth.js
        └── router/index.js         ← 23 條路由 + 11 條舊路由 redirect
```

---

## 3. 後端 API 端點清單

### auth.py
| Method | 路徑 | 說明 |
|--------|------|------|
| POST | /auth/login | 登入，回傳 JWT |
| GET | /auth/me | 目前登入用戶資訊 |

### inventory.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /inventory/vendors | 供應商列表 |
| POST/PUT/DELETE | /inventory/vendors/{id} | 供應商 CRUD |
| GET | /inventory/items | 品項列表（支援 vendor_id、stocktake_group_id 篩選） |
| GET | /inventory/orders | 叫貨單列表（status、days_limit 篩選） |
| POST | /inventory/orders | 建立叫貨單 |
| GET | /inventory/orders/{id} | 叫貨單詳情（含品項） |
| DELETE | /inventory/orders/{id} | 刪除叫貨單（已收貨 → 403） |
| POST | /inventory/orders/{id}/receive | 簽收叫貨單 |
| GET | /inventory/categories | 品項分類列表（含品項數、範例品項） |
| POST | /inventory/categories | 建立分類 |
| PUT | /inventory/categories/{id} | 更新分類 |
| DELETE | /inventory/categories/{id} | 刪除分類（有品項 → 400） |
| GET | /inventory/items/{id}/discrepancy-analysis | 品項差異分析（近 N 天到貨、損耗、理論剩餘） |

### finance.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /finance/summary | 零用金摘要 |
| GET | /finance/petty-cash | 零用金紀錄列表 |
| POST | /finance/petty-cash | 新增零用金紀錄 |
| GET | /finance/transactions | 金流紀錄列表 |
| POST | /finance/transactions | 新增金流紀錄 |
| POST | /finance/daily-settlement | 執行日結 |
| GET | /finance/overview | 金流總覽 KPI（本月收入/支出/淨額/零用金餘額） |
| GET | /finance/recurring | 重複費用列表 |
| POST | /finance/recurring | 建立重複費用 |
| PUT | /finance/recurring/{id} | 更新重複費用 |
| DELETE | /finance/recurring/{id} | 刪除重複費用 |
| GET | /finance/proportional-fees | 比例費用規則列表 |
| POST | /finance/proportional-fees | 建立比例費用規則 |
| PUT | /finance/proportional-fees/{id} | 更新比例費用規則 |
| DELETE | /finance/proportional-fees/{id} | 刪除比例費用規則 |

### stocktake.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /stocktake/groups | 盤點群組列表 |
| POST | /stocktake/ | 建立盤點 session |
| PUT | /stocktake/{id} | 更新盤點品項 |
| PUT | /stocktake/{id}/submit | 提交盤點 |

### waste.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /waste/ | 耗損紀錄（days_limit 篩選） |
| POST | /waste/ | 新增耗損紀錄 |

### users.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /users | 用戶列表 |
| POST | /users | 建立用戶 |
| PUT | /users/{id} | 更新用戶 |
| PUT | /users/{id}/password | 修改密碼 |

### notifications.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /notifications/settings | 所有通知類型 + 開關狀態 |
| PUT | /notifications/settings/{type} | 切換通知開關 |
| GET | /notifications | 通知列表（分頁） |
| PUT | /notifications/{id}/read | 標記已讀/未讀 |

### reports.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /reports/pl?period=month\|quarter\|year | 損益報表 KPI + 明細 |
| GET | /reports/pl/trend?months=6\|12 | 6/12 個月趨勢資料（Canvas 圖表用） |

---

## 4. 前台 PWA 路由

```
/login          → LoginView.vue（public）
/               → HomeView.vue（首頁儀表板）
/order          → InventoryView.vue（叫貨 + 待收貨 + 歷史）
/stocktake      → StocktakeView.vue（盤點 + 叫貨雙模式）
/finance        → FinanceView.vue（零用金 + 日結）
/waste          → WasteView.vue（耗損紀錄）
/more           → MoreView.vue（個人設定 + PWA 安裝）
```

**底部 Nav Bar 順序：** 首頁 | 訂單 | 金流 | 更多

---

## 5. 後台 Admin 路由與導覽

### 5 大 navGroup 與側邊欄

```
總覽
  /dashboard                      → DashboardView.vue

庫存管理
  /inventory/orders               → OrdersView.vue（叫貨/收貨）
  /inventory/stocktakes           → StocktakeView.vue（盤點紀錄）
  /inventory/groups               → StocktakeGroupsView.vue（盤點群組）
  /inventory/waste                → WasteView.vue（耗損紀錄）
  /inventory/vendors              → VendorsView.vue（供應商管理）
  /inventory/items                → ItemsView.vue（品項管理）

金流管理
  /cashflow/overview              → CashFlowOverviewView.vue（金流總覽 KPI）
  /cashflow/transactions          → CashFlowTransactionsView.vue（金流紀錄）
  /cashflow/petty-cash            → PettyCashView.vue（零用金管理）
  /cashflow/payables              → PayablesView.vue（應付帳款）
  /cashflow/recurring             → RecurringChargesView.vue（重複費用設定）
  /cashflow/ratio-costs           → ProportionalFeesView.vue（比例費用設定）

財務管理
  /financial/pl                   → ReportsView.vue（損益報表）

系統管理
  /settings/accounts              → AccountsView.vue（帳號管理）
  /settings/finance               → FinanceParamsView.vue（財務參數）
  /settings/display               → DisplaySettingsView.vue（顯示設置）
  /settings/features              → FeaturesToggleView.vue（功能開關）
  /settings/api                   → ApiIntegrationsView.vue（串接管理）
```

### 舊路由 → 新路由 redirect（router/index.js 已設好）

| 舊路徑 | 新路徑 |
|--------|--------|
| /orders | /inventory/orders |
| /stocktake | /inventory/stocktakes |
| /stocktake-groups | /inventory/groups |
| /waste | /inventory/waste |
| /vendors | /inventory/vendors |
| /items | /inventory/items |
| /finance | /cashflow/transactions |
| /cash-flow-overview | /cashflow/overview |
| /recurring-charges | /cashflow/recurring |
| /proportional-fees | /cashflow/ratio-costs |
| /users | /settings/accounts |

---

## 6. 資料庫表格總覽（23 個 Model）

| Model 類名 | 表格名稱 | 關鍵欄位 |
|-----------|----------|----------|
| User | erp_users | id, username, hashed_password, role, is_active, petty_cash_permission |
| UserDevice | erp_user_devices | user_id FK, device_id, refresh_token, expires_at |
| AuditLog | erp_audit_logs | user_id FK, action, resource, resource_id, details JSONB |
| Vendor | erp_vendors | id, name, payment_terms, bank_account, free_shipping_threshold, delivery_days_to_arrive |
| ItemCategory | erp_item_categories | id, name, display_order |
| StocktakeGroup | erp_stocktake_groups | id, name, display_order, is_active |
| Item | erp_items | id, name, unit, vendor_id FK, category_id FK, current_stock, min_stock, price |
| PurchaseOrder | erp_purchase_orders | id, vendor_id FK, status, ordered_at, updated_at |
| PurchaseOrderDetail | erp_purchase_order_details | order_id FK, item_id FK, qty, actual_qty |
| InventoryTransaction | erp_inventory_transactions | item_id FK, qty, type |
| Stocktake | erp_stocktakes | id, group_id FK, mode, status |
| StocktakeItem | erp_stocktake_items | stocktake_id FK, item_id FK, counted_qty |
| WasteRecord | erp_waste_records | id, item_id FK, qty, unit, reason, estimated_value |
| PettyCashRecord | erp_petty_cash_records | id, user_id FK, type, amount, note, vendor_id FK |
| CashFlowCategory | erp_cash_flow_categories | id, name, type |
| CashFlowRecord | erp_cash_flow_records | id, category_id FK, amount, type, note |
| CashFlowRecurring | erp_cash_flow_recurring | id, name, category, amount, day_of_month, is_active |
| AccountsPayable | erp_accounts_payable | id, vendor_id FK, amount, due_date, is_paid |
| Notification | erp_notifications | id, type, title, body, target_user_id FK(nullable=broadcast), is_read |
| DailySettlement | erp_daily_settlements | id, settlement_date UNIQUE, income_total, expense_total |
| CashTransaction | erp_cash_transactions | id, user_id FK, amount, type, note |
| NotificationSetting | erp_notification_settings | id, user_id FK, notification_type, is_enabled，UNIQUE(user_id, notification_type) |
| ProportionalFeeRule | erp_proportional_fee_rules | id, name, category, percentage, settlement_period, is_active |

**注意：** 若要新增表格，在 `models.py` 加 Model + `migrations/` 寫遷移腳本 + 遠端執行，勿在此表重複建立。

---

## 7. 開發工作流程

### 7.1 SSH 進入遠端伺服器

```bash
ssh mason_ycw@34.81.51.45   # password: masonpass
cd /home/mason_ycw/boiling-noodles-dashboard
```

### 7.2 後端啟動 / 重啟

```bash
# 殺掉舊 process
pkill -f uvicorn
sleep 2

# 啟動
cd /home/mason_ycw/boiling-noodles-dashboard
source erp/backend/venv/bin/activate
nohup uvicorn erp.backend.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &

# 確認
tail -5 /tmp/uvicorn.log
curl -s http://localhost:8000/api/v1/auth/me
```

### 7.3 DB Migration（Python 腳本方式）

```bash
# 本機用 paramiko 上傳 + 執行（參考 run_remote.py）
python3 - << 'EOF'
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('34.81.51.45', username='mason_ycw', password='masonpass')

sftp = ssh.open_sftp()
sftp.put('erp/backend/migrations/pX_xxx.py',
         '/home/mason_ycw/boiling-noodles-dashboard/erp/backend/migrations/pX_xxx.py')
sftp.close()

cmd = 'cd /home/mason_ycw/boiling-noodles-dashboard && source erp/backend/venv/bin/activate && PYTHONPATH=/home/mason_ycw/boiling-noodles-dashboard python3 erp/backend/migrations/pX_xxx.py'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
ssh.close()
EOF
```

### 7.4 新增後端 API 的標準流程

1. `backend/api/` 建立 `.py`，定義 `APIRouter`
2. `backend/db/models.py` 加 SQLAlchemy Model
3. `backend/main.py` 的 `# ─── Routers ───` 區塊 `include_router`
4. `backend/migrations/` 寫遷移腳本並在遠端執行

### 7.5 認證 Header

```javascript
// 前台 / 後台通用
headers: { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
```

```python
# 後端取目前登入用戶
from erp.backend.core.security import get_current_user
from fastapi import Depends

@router.get("/resource")
def get_resource(current_user = Depends(get_current_user)):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(403, "Insufficient permissions")
```

---

## 8. 前端開發規範

### 8.1 PWA 前台（frontend/）設計系統

- 背景：`bg-slate-50`（頁面）/ `bg-white`（卡片）
- 主色：`#e85d04`（品牌橘）
- 字型：Inter / system-ui
- 圓角：`rounded-xl`（卡片）/ `rounded-2xl`（按鈕）
- 底部 Bottom Sheet：`fixed inset-0 bg-black/50 z-50 flex items-end`

### 8.2 Admin 後台設計系統

- 深色主題：背景 `bg-[#0f1117]`，卡片 `bg-[#1a202c]`，邊框 `border-[#2d3748]`
- 主色：`#e85d04`（橘）
- iOS 風格 Toggle：pure CSS，啟用時橘色

### 8.3 草稿自動儲存（P3-3，localStorage）

```javascript
// Key 格式
`draft:order:${auth.user?.id}`    // 叫貨草稿（InventoryView.vue）
`draft:stocktake:${auth.user?.id}` // 盤點草稿（StocktakeView.vue）

// TTL：48 小時（48 * 60 * 60 * 1000 ms）
// 自動儲存間隔：30 秒
// 頁面載入時：偵測草稿 → 顯示恢復 banner（繼續編輯 / 丟棄）
```

### 8.4 Soft Delete（人員管理）

```python
# E5 人員管理用，其餘資源用硬刪除
user.deleted_at = datetime.utcnow()
db.commit()

# 查詢時排除已刪除
db.query(User).filter(User.deleted_at == None).all()
```

---

## 9. 不可違反的業務規則

| 規則 | 適用範圍 | 後端要求 |
|------|----------|----------|
| 已收貨訂單不可在 App 編輯/刪除 | 前台 | PUT/DELETE /orders/:id → 403 if status=received |
| 今天之前的盤點不可在 App 編輯/刪除 | 前台 | PUT/DELETE /stocktakes/:id → 403 if date < today |
| App 零用金不可編輯/刪除 | 前台 | 前端不提供按鈕 |
| 人員刪除用 Soft Delete | 後台 | deleted_at 欄位，不 DELETE |
| 品項分類有品項時不可刪除 | 後台 | DELETE /categories/:id → 400 if item_count > 0 |
| 通知 target_user_id=NULL 表示廣播 | 全部 | 查詢時 OR target_user_id=current_user.id |
| CashFlowRecurring.category 為 VARCHAR | DB | 不是 FK，直接存字串分類名稱 |
| erp_item_categories 需 display_order | DB | 已 ALTER TABLE 加欄位（2026-03-24） |
| SW 只在 HTTPS 或 localhost 運作 | PWA | 本地開發用 localhost，正式環境需 HTTPS |

---

## 10. 環境變數

### backend/.env
```
DATABASE_URL=postgresql://...
JWT_SECRET_KEY=...
ALGORITHM=HS256
```

### frontend/.env / admin/.env
```
VITE_API_BASE_URL=http://34.81.51.45:8000/api/v1
```

---

## 11. 功能完成狀態（截至 P3）

### ✅ 已完成

| 批次 | 功能 |
|------|------|
| P0 | 後端基礎架構（認證/廠商/品項/叫貨/盤點/耗損/零用金） |
| P1 | 前台 PWA 全頁面（叫貨/盤點/金流/耗損/更多） |
| P2 | Admin 後台全頁面 + 日結 modal |
| B4 | 後台路由重整（5 大 navGroup，/inventory/cashflow/financial/settings） |
| D1 | 系統管理中心（FinanceParams / DisplaySettings / FeaturesToggle） |
| D2 | 串接管理（ApiIntegrations） |
| P3-0 | Admin 分類管理（CategoryView）+ 通知管理（NotificationView） |
| P3-1 | Admin 金流總覽（CashFlowOverview）+ 重複費用 + 比例費用 |
| P3-2 | 損益報表（Canvas 趨勢圖，月/季/年分頁） |
| P3-3 | PWA 草稿自動儲存 + D+N 到貨倒數 + 差異分析 Sheet |
| P3-4 | PWA manifest + Service Worker + 安裝提示 |

### ⏳ 尚未實作（參考原規劃）

| 任務 | 說明 |
|------|------|
| A2 | 後端草稿 API（/drafts CRUD）—目前僅 localStorage 版本 |
| A3 | 金流附件上傳（POST /transactions/:id/attachments） |
| B1 | 供應商品項 Drag & Drop 排序（erp_vendor_items junction table） |
| C1 | 權限矩陣（36 項權限，RolePermission Model） |
| E1 | App 零用金點擊詳情 Bottom Sheet |
| E2 | 後台叫貨收貨編輯/刪除 + Lightbox |
| E3 | 後台盤點紀錄編輯/刪除 |
| E4 | 後台零用金/金流編輯/刪除 |
| E5 | 後台人員管理完整 CRUD（含 Soft Delete） |
| F1 | 操作人 UserBadge 元件（API JOIN erp_users） |

---

## 12. 快速 Debug 指令

```bash
# 查看後端 log
tail -f /tmp/uvicorn.log

# 測試 API（需先登入取 token）
curl -s http://localhost:8000/api/v1/finance/overview
curl -s http://localhost:8000/api/v1/inventory/categories

# 查看 DB 表格欄位
PYTHONPATH=/home/mason_ycw/boiling-noodles-dashboard python3 -c "
from erp.backend.db.session import engine
from sqlalchemy import text
with engine.connect() as conn:
    r = conn.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='TABLE_NAME'\"))
    print([row[0] for row in r])
"

# 查 process
ps aux | grep uvicorn
```
