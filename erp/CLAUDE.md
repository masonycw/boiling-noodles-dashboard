# 滾麵 ERP — Claude Code 開發指南

> 最後更新：2026-03-25
> Git 倉庫：https://github.com/masonycw/boiling-noodles-dashboard
> 維護規則：每次改動邏輯、目錄結構、業務規則，**必須同步更新本文件對應章節**，底部只保留最近進度摘要（舊的刪除）

## ⚠️ 完成任務前的強制驗收規則

**任何涉及前後端對接的任務，標記為「完成」之前，必須依序完成以下步驟：**

### 步驟 1：後端先行驗證
- 前端呼叫的每一個 API 端點，先用 `curl` 或 paramiko **實際打一次**
- 確認：端點存在（不是 404/405）、回傳的 JSON 欄位名稱正確
- 用回傳的 JSON 欄位寫前端，**禁止靠猜**

### 步驟 2：欄位名對照
- 後端回傳的欄位名 → 前端 template 引用的欄位名，逐一比對
- 常見錯誤：`items` vs `discrepancies`、`counted_qty` vs `actual_qty`、`performed_by` vs `created_by`
- 如果後端沒有該欄位，先改後端或改前端，不可留空跳過

### 步驟 3：完整使用者流程測試
- 在前台/後台**實際操作一次完整流程**（不是只看畫面渲染）
- 例：叫貨 → 確認進入待收貨 → 簽收 → 確認進入歷史紀錄
- 例：存草稿 → 離開頁面 → 回來載入草稿 → 確認數量恢復

### 步驟 4：邊界情境
- 空資料時顯示什麼？（空列表、無供應商、無歷史）
- 重複操作會不會爆？（連點兩次送出、重複日結）
- 權限不同的角色能不能正確進入/被擋？

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
│   │   ├── reports.py              ← prefix: /api/v1（損益報表）
│   │   └── webhook.py              ← prefix: /api/v1/webhook（LINE Webhook 驗證 + 事件接收）
│   ├── db/
│   │   ├── models.py               ← 所有 SQLAlchemy ORM Model（24 個表格）
│   │   ├── session.py              ← DB Session / engine
│   │   └── schema.sql              ← 基礎 SQL schema（參考用）
│   ├── core/
│   │   ├── config.py               ← env var 讀取
│   │   └── security.py             ← JWT 簽發/驗證/密碼 hash
│   ├── migrations/                 ← 遷移腳本（p1/p2/p3/o-series）
│   ├── services/
│   │   ├── inventory_service.py    ← 庫存業務邏輯（含 receive_order 自動帶入廠商預設科目）
│   │   ├── finance_service.py      ← 金流業務邏輯（含 date_from/date_to 篩選）
│   │   └── line_service.py         ← LINE Messaging API 發送（send_order_message）
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
│       │   ├── HomeView.vue        ← 待收貨 + 待盤點清單（O5）；低庫存警示
│       │   ├── InventoryView.vue   ← 3-tab：叫貨（草稿/D+N）/ 待收貨 / 歷史紀錄（子tab：已收貨+盤點歷史）
│       │   ├── StocktakeView.vue   ← 盤點（singleMode compact；route.query.group 自動選；O5 次日 Modal）
│       │   ├── FinanceView.vue     ← 零用金 + 日結
│       │   ├── WasteView.vue       ← 2-tab：記錄耗損 / 歷史紀錄（O4）
│       │   ├── MoreView.vue        ← 含 PWA 安裝按鈕 P3-4
│       │   ├── HistoryView.vue     ← 獨立歷史頁（/history）；前台叫貨/盤點歷史已整合進 InventoryView
│       │   └── ManagementView.vue
│       ├── stores/auth.js          ← Pinia auth store（JWT token + user.role）
│       └── router/index.js         ← 路由守衛（login/role 雙重守衛，O7）
└── admin/                          ← Vue Admin（port 5174）
    └── src/
        ├── views/                  ← 24 個 View 元件（見第 5 節）
        │   ├── CashFlowTransactionsView.vue ← O6：日期篩選/科目小計/新增紀錄 Modal
        │   ├── VendorsView.vue              ← O6：廠商預設科目下拉
        │   ├── StocktakeGroupsView.vue      ← O5：週期天數 + 下次盤點日欄位
        │   ├── UsersView.vue                ← O7：cashier / manager 角色選項
        │   └── settings/
        │       └── ApiIntegrationsView.vue  ← LINE Channel Secret/Access Token 設定
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
| PATCH | /inventory/vendors/{id}/default-category | 更新廠商預設金流科目（O6） |

### finance.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /finance/summary | 零用金摘要 |
| GET | /finance/petty-cash | 零用金紀錄列表 |
| POST | /finance/petty-cash | 新增零用金紀錄 |
| GET | /finance/transactions | 金流紀錄列表（支援 date_from/date_to/type/category_id 篩選，O6） |
| POST | /finance/transactions | 新增金流紀錄（O6：手動補帳） |
| PATCH | /finance/transactions/{id} | 更新金流紀錄科目（inline 編輯，O6） |
| GET | /finance/can-settle | 判斷是否可再次日結（O3） |
| GET | /finance/cash-flow/categories | 金流科目列表（給廠商預設科目下拉用） |
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
| GET | /stocktake/groups | 盤點群組列表（含 stocktake_cycle_days / next_stocktake_due） |
| POST | /stocktake/groups | 建立盤點群組 |
| PUT | /stocktake/groups/{id} | 更新盤點群組 |
| DELETE | /stocktake/groups/{id} | 刪除盤點群組 |
| GET | /stocktake/pending-groups | 待盤點群組（O5：today+1 到期過濾，overdue_days 排序） |
| PATCH | /stocktake/groups/{id}/next-due | 手動更新下次預定盤點日（O5） |
| POST | /stocktake/ | 建立盤點 session |
| PUT | /stocktake/{id} | 更新盤點品項 |
| PUT | /stocktake/{id}/submit | 提交盤點（O5：自動推算 next_stocktake_due） |

### waste.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /waste/ | 耗損紀錄（days_limit 篩選） |
| POST | /waste/ | 新增耗損紀錄（支援 photo_url 欄位） |

### uploads.py
| Method | 路徑 | 說明 |
|--------|------|------|
| POST | /uploads/image | 上傳圖片（multipart/form-data），回傳 `{"url": "/uploads/uuid.ext"}`；支援 jpg/png/webp/gif，限 10MB |

> 靜態圖片由 FastAPI `StaticFiles` 掛載 `/uploads` 路徑提供服務，儲存於專案根目錄的 `uploads/` 資料夾

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

### webhook.py
| Method | 路徑 | 說明 |
|--------|------|------|
| GET | /webhook/line | LINE Webhook 驗證（Challenge 回應） |
| POST | /webhook/line | LINE 事件接收（群組訊息/加好友事件，用於取得 group_id） |

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
| Vendor | erp_vendors | id, name, payment_terms, bank_account, free_shipping_threshold, delivery_days_to_arrive, default_category_id FK, line_group_id |
| ItemCategory | erp_item_categories | id, name, display_order |
| StocktakeGroup | erp_stocktake_groups | id, name, display_order, is_active, stocktake_cycle_days, next_stocktake_due（O5） |
| Item | erp_items | id, name, unit, vendor_id FK, category_id FK, current_stock, min_stock, price |
| PurchaseOrder | erp_purchase_orders | id, vendor_id FK, **status**（CHECK: confirmed/received/cancelled）, ordered_at, updated_at, user_id FK（叫貨人）, receive_user_id FK（簽收人） |
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
| DailySettlement | erp_daily_settlements | id, settlement_date（已移除 UNIQUE，O3）, income_total, expense_total, settlement_number, closing_balance, settled_by FK |
| CashTransaction | erp_cash_transactions | id, user_id FK, amount, type, note |
| NotificationSetting | erp_notification_settings | id, user_id FK, notification_type, is_enabled，UNIQUE(user_id, notification_type) |
| ProportionalFeeRule | erp_proportional_fee_rules | id, name, category, percentage, settlement_period, is_active |
| SystemSetting | erp_system_settings | key（UNIQUE），value（TEXT）← LINE credentials / 系統設定（O9） |

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

### 7.6 角色權限（O7）

| 角色 | 說明 | 前台可存取頁面 |
|------|------|----------------|
| `admin` | 店長（全部功能） | 全部 |
| `manager` | 主管 | 全部前台 + 後台唯讀 |
| `staff` | 員工 | 全部前台 |
| `cashier` | 櫃檯 | HomeView + FinanceView + MoreView |

```javascript
// router/index.js — 角色守衛邏輯
const ROLE_LEVELS = { admin: 4, manager: 3, staff: 2, cashier: 1 }
function hasRole(userRole, required) {
  return (ROLE_LEVELS[userRole] ?? 0) >= (ROLE_LEVELS[required] ?? 0)
}
// 各路由 meta.requiredRole：
// /order → 'staff'  /stocktake → 'staff'  /waste → 'staff'
// /history → 'staff'  /finance → 'cashier'（cashier 以上皆可）
```

---

## 8. 前端開發規範

### 8.1 PWA 前台（frontend/）設計系統

- 背景：`bg-slate-50`（頁面）/ `bg-white`（卡片）
- 主色：`#e85d04`（品牌橘）
- 字型：Inter / system-ui
- 圓角：`rounded-xl`（卡片）/ `rounded-2xl`（按鈕）
- 底部 Bottom Sheet：`fixed inset-0 bg-black/50 z-50 flex items-end`；內部 `max-h-[92vh] flex flex-col`，header `flex-shrink-0`，內容 `flex-1 overflow-y-auto`，按鈕 `flex-shrink-0`
- 固定在頁面底部的 action bar：用 `style="bottom: calc(4rem + max(16px, env(safe-area-inset-bottom))); will-change: transform;"` 而非 `fixed bottom-16`（避免 iOS safe-area 遮擋）

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
| **叫貨單 status 只有三種：confirmed / received / cancelled** | DB | 送出即 confirmed，簽收變 received；舊的 pending 已全部 migrate 為 confirmed，CHECK constraint 已更新 |
| 已收貨訂單不可在 App 編輯/刪除 | 前台 | PUT/DELETE /orders/:id → 403 if status=received |
| 今天之前的盤點不可在 App 編輯/刪除 | 前台 | PUT/DELETE /stocktakes/:id → 403 if date < today |
| App 零用金不可編輯/刪除 | 前台 | 前端不提供按鈕 |
| 人員刪除用 Soft Delete | 後台 | deleted_at 欄位，不 DELETE |
| 品項分類有品項時不可刪除 | 後台 | DELETE /categories/:id → 400 if item_count > 0 |
| 通知 target_user_id=NULL 表示廣播 | 全部 | 查詢時 OR target_user_id=current_user.id |
| CashFlowRecurring.category 為 VARCHAR | DB | 不是 FK，直接存字串分類名稱 |
| erp_item_categories 需 display_order | DB | 已 ALTER TABLE 加欄位（2026-03-24） |
| SW 只在 HTTPS 或 localhost 運作 | PWA | 本地開發用 localhost，正式環境需 HTTPS |
| InventoryView 歷史紀錄 tab 分 2 子 tab | 前台 | 已收貨（status=received）/ 盤點歷史；confirmed 只在「待收貨」tab 顯示 |
| 支出類金流紀錄的 category_id 應有值 | DB | 無值則後台列表顯示 ⚠️ 未分科目（O6） |
| 收入/提領類金流不歸科目 | 後台 | category_id 只適用 expense 類型（O6） |
| LINE Channel Secret / Access Token 存 DB | 後端 | 不寫死在程式，從 erp_system_settings 讀取（O9） |
| 日結無每日唯一限制 | DB | unique_settlement_date constraint 已移除（O3） |
| 盤點次日防漂移 | 後端 | next_due = 舊 next_due + cycle_days（非實際完成日），O5 |
| next_stocktake_due NULL + cycle_days 有值 | 前台 | 視為今天到期（提醒首次盤點），O5 |
| cashier 角色前台只能存取 HomeView + FinanceView | 前台 | router guard + App.vue navItems filter（O7） |
| 角色層級：admin > manager > staff > cashier | 前台 | ROLE_LEVELS = { admin:4, manager:3, staff:2, cashier:1 }（O7） |

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

## 11. 功能進度

### O 系列優化任務

| 任務 | 說明 | 狀態 |
|------|------|------|
| O1 | 叫貨送出流程（送出即 confirmed，直進待收貨）+ 草稿/臨時品項 | ✅ |
| O2 | 叫貨歷史操作人（performed_by）+ discrepancy_count 欄位修正 | ✅ |
| O3 | 日結多次/排序/closing_balance/settled_by；移除 UNIQUE constraint | ✅ |
| O4 | WasteView 2-tab + StocktakeView singleMode 緊湊版 | ✅ |
| O5 | 首頁待盤點清單（next_stocktake_due + cycle_days 提醒） | ✅ |
| O6 | 後台金流科目化（日期篩選/手動新增/廠商預設科目/inline 編輯） | ✅ |
| O7 | 權限系統（cashier 角色、路由守衛、nav items 過濾） | ✅ |
| O8 | iOS bottom action bar 固定位置（safe-area-inset-bottom） | ✅ |
| O9 | LINE 訊息推播至廠商群組 | 🔨 Webhook 驗證通過，group_id UI 管理待串 |

### 最近進度（2026-03-25）

- **叫貨單 status 體系重整**：DB CHECK constraint 從 `pending/ordered/received/cancelled` 改為 `confirmed/received/cancelled`；所有舊 pending 資料已 migrate 為 confirmed
- **InventoryView 歷史紀錄 tab**：新增 2 子 tab（已收貨 / 盤點歷史）
- **iOS action bar 定位**：`fixed bottom-16` → `calc(4rem + max(16px, env(safe-area-inset-bottom)))` + `will-change: transform`
- **admin 密碼**：已重設為 `admin123`
- **耗損拍照功能**：新增 `POST /uploads/image` 端點 + `/uploads` 靜態服務；WasteView 表單加拍照按鈕、預覽縮圖，歷史展開顯示照片
- **finance.py import 修正**：`get_current_user` 改從 `auth.py` 引入（原本錯誤指向 security.py）

---

## 12. ngrok（對外 HTTPS 通道）

ngrok 讓 GCP 伺服器有穩定的公開 HTTPS URL，LINE Webhook 需要此 URL。

| 項目 | 說明 |
|------|------|
| 靜態網址 | `https://preoffensive-chasteningly-taunya.ngrok-free.dev` |
| 轉發目標 | `http://localhost:8000`（FastAPI） |
| 服務名稱 | `ngrok`（systemd） |
| 設定檔 | `/etc/systemd/system/ngrok.service` |

```bash
# 查看 ngrok 狀態
sudo systemctl status ngrok

# 重啟 ngrok
sudo systemctl restart ngrok

# ngrok.service 內容
# ExecStart=/usr/local/bin/ngrok http --url=preoffensive-chasteningly-taunya.ngrok-free.dev 8000
```

> ngrok 免費方案限制：1 個靜態 domain、連線數有限。若遇到 ERR_NGROK_8012 錯誤表示連線數超過，重啟即可。

---

## 13. LINE Messaging API 串接（O9）

### 目前狀態

| 項目 | 狀態 |
|------|------|
| LINE Official Account 申請 | ✅ 完成 |
| Webhook URL 設定 | ✅ `https://preoffensive-chasteningly-taunya.ngrok-free.dev/api/v1/webhook/line` |
| Webhook 驗證 | ✅ 通過（200 OK） |
| Channel ID | 2009581286 |
| Channel Secret | 存於 DB `erp_system_settings` key=`line_channel_secret` |
| Access Token | 存於 DB `erp_system_settings` key=`line_access_token` |
| 廠商 line_group_id | 🔨 欄位已加，但 UI 管理 + 實際發送 待完成 |

### 取得廠商群組 Group ID

1. 將 LINE Bot 加入廠商群組
2. Bot 加入群組時會觸發 `join` 事件，webhook 會印出 `group_id`
3. 在後台廠商管理頁填入 `line_group_id`

### line_service.py 使用方式

```python
from erp.backend.services.line_service import send_line_message

# 發送訊息至群組
send_line_message(db, group_id="C...", text="叫貨訊息內容")

# send_line_message 會從 DB 讀取 Access Token：
# SELECT value FROM erp_system_settings WHERE key='line_access_token'
```

### 後台 LINE 憑證設定（ApiIntegrationsView）

```
POST /api/v1/settings/line
Body: { channel_secret: "...", access_token: "..." }
```

---

## 14. 快速 Debug 指令

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
