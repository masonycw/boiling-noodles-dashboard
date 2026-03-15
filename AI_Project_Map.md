# Boiling Noodles ERP - 專案架構地圖 (Project Architecture Map)

這份文件是由 AI 專案架構導師根據「低 Token 消耗、高邏輯性」原則所產出的全局架構指南。旨在協助未來參與開發的 AI 或工程師能迅速確認「所處在位置」，理解資料流向與開發標準。

---

## 🏗️ 1. 系統架構圖 (System Architecture)

```mermaid
graph TD
    %% 外部輸入層
    SFTP_Server[SFTP Server / Uploads<br>CSV / Excel Reports] -->|File Watcher Tracker| Data_Pipeline
    
    subgraph Database_Layer [Database & ETL Layer]
        Data_Pipeline(database/data_pipeline.py<br>ETL & Increment Load)
        Data_Pipeline -->|Process & Clean| PostgreSQL[(PostgreSQL DB<br>boiling_noodles)]
        File_Watcher(database/file_watcher.py<br>Directory Monitoring) -.->|Trigger| Data_Pipeline
    end

    subgraph Backend_Layer [FastAPI Backend]
        API_Routes(erp/backend/api/<br>Controllers)
        Services(erp/backend/services/<br>Business Logic)
        DB_Models(erp/backend/db/<br>SQLAlchemy/Drivers)
        
        API_Routes --> Services
        Services --> DB_Models
        DB_Models <--> PostgreSQL
    end
    
    subgraph Frontend_Layer [Frontend Clients]
        Streamlit[Streamlit Dashboards<br>Data Visualization (Port 8501)]
        VueApp[Vue 3 PWA App<br>Mobile Store App (Planned)]
    end

    %% 連線
    Streamlit <-->|Direct DB SQL (Read-Only)| PostgreSQL
    VueApp <-->|REST API (JWT)| API_Routes
    
    %% 輔助服務
    GCS[GCP Cloud Storage<br>Receipts & Images]
    Services -.->|Upload/Signed URLs| GCS
```

---

## 📂 2. 全局目錄結構與功能索引 (Directory Index)

### 📌 核心目錄
*   **/erp/backend**: ERP 核心大腦 (FastAPI).
    *   `api/`: Controller 層。定義 HTTP 路由 (如 [auth.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/api/auth.py), [inventory.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/api/inventory.py), [finance.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/api/finance.py))。
    *   `services/`: 商業邏輯層。所有報表計算、權限判斷、資料轉換都在此處 (如 [inventory_service.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/services/inventory_service.py))。
    *   [db/](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp.db): 資料庫連線與 ORM/Schema (如 [models.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/db/models.py), [session.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/db/session.py))。
    *   `core/`: 核心設定 (如 [config.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/config.py) 管理環境變數與 JWT 設定).
*   **/database**: ETL 數據抽取與資料庫本體區。
    *   [data_pipeline.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/database/data_pipeline.py): 將 CSV/JSON 轉換入庫的 ETL 腳本。包含 Lock 機制防衝突。
    *   [file_watcher.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/database/file_watcher.py): 監聽 SFTP 目錄的檔案變動，自動觸發 Pipeline。
    *   [data_loader.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/database/data_loader.py): 處理各種格式資料載入與欄位對應 (`COLUMN_MAPPING`)。
*   **/streamlit**: 數據儀表板 (Dashboard) 專區。
    *   負責讀取 DB 資料並產生圖表，**不應**在此處寫入資料，以防 Database Lock。
*   **/scripts**: 維運與部署腳本區。
    *   包含 [deploy_erp.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/deploy_erp.py), [check_server.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/check_server.py), [restart_app.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/restart_app.py)。
*   **/_agents/workflows**: AI SOP 工作流 (如 [architecture_mentor.md](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/_agents/workflows/architecture_mentor.md), [debug.md](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/_agents/workflows/debug.md))。

---

## 🔄 3. 核心資料流說明 (Core Data Flows)

### A. 日常報表匯入流 (ETL Flow)
1. POS 機產出 CSV / Excel 報表。
2. 透過 SFTP 傳輸至 Server (`/home/eats365/data`)。
3. [database/file_watcher.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/database/file_watcher.py) 偵測到新檔案或重命名。
4. 觸發 [database/data_pipeline.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/database/data_pipeline.py)。
5. Pipeline 透過 `UniversalLoader` 讀取快取 (Parquet) 或原始檔，執行 UPSERT (增量更新) 寫入 PostgreSQL 的 `orders_fact` 與 `order_details_fact`。

### B. 前端 API 請求流 (API Request Flow)
1. Vue 前端發送附帶 JWT Token 的 HTTP Request 至 `/api/v1/inventory/...`。
2. [erp/backend/api/inventory.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/api/inventory.py) 攔截請求，驗證 Token (Dependency Injection)。
3. Controller 呼叫 [erp/backend/services/inventory_service.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/services/inventory_service.py) 進行邏輯運算 (例如計算建議叫貨量)。
4. Service 層呼叫 [db/models.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/db/models.py) 或直接下 SQL Command，從 PostgreSQL 取得資料。
5. Service 將資料格式化後回傳給 Controller，Controller 再以 JSON 格式回應給前端。

### C. 圖片上傳流 (Image Upload Flow - 點貨/零用金)
1. 前端呼叫 API 請求上傳圖片。
2. Backend 驗證權限。
3. Backend 將圖片串流上傳至 GCP Cloud Storage (GCS)。
4. Backend 將 GCS 的圖片網址 (或關聯 ID) 寫入 PostgreSQL 紀錄。
5. 前端讀取時，Backend 動態產生 Signed URL 供前端取得圖片。

---

## 📏 4. 專案開發標準 (Development Standards)

1. **三層式架構嚴格分離**:
   *   `api/` 絕對不寫 SQL 語法或複雜商業邏輯，僅負責 Request 解析與 Response 封裝。
   *   所有邏輯運算必須封裝在 `services/` 中，以確保程式碼可測試性與降低耦合。
2. **Database Lock 防禦**:
   *   [data_pipeline.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/database/data_pipeline.py) 等背景 ETL 寫入作業，應避免執行耗時過長的 `ALTER TABLE` 或全表鎖定。
   *   寫入時應盡量使用 Batch UPSERT (`execute_values` + `ON CONFLICT DO UPDATE`)。
3. **路徑引用與環境變數**:
   *   專案內引用模組一律使用絕對路徑 (如 `from erp.backend.core.config import settings`)。
   *   機密資訊 (如 DB 密碼、Secret Key) 絕不 Hardcode，必須從 [core/config.py](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/erp/backend/core/config.py) 或 `.env` 讀取。
4. **命名慣例**:
   *   **資料表 / 欄位**: `snake_case` (如 `order_details_fact`)。
   *   **API 路徑**: `/api/v1/資源名稱/動作` (如 `/api/v1/inventory/orders`)，使用名詞複數與 `kebab-case`。
   *   **Service 類別**: `PascalCase` (如 `InventoryService`)。
   *   **Python 變數**: `snake_case`。
5. **AI 協作規範**:
   *   每次開啟新任務前，務必詳讀 [CONTEXT.md](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/CONTEXT.md)。
   *   複雜功能開發必須啟動 Task Mode ([task.md](file:///Users/mason/.gemini/antigravity/brain/1743730c-91fd-4b18-a1b4-71d6e01bbda6/task.md))。
   *   除錯時優先參照 [_agents/workflows/debug.md](file:///Users/mason/%E6%BB%BE%E9%BA%B5%E5%B0%88%E6%A1%88/%E6%99%BA%E6%85%A7%E5%A0%B1%E8%A1%A8/_agents/workflows/debug.md)。
