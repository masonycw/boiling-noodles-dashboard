# Boiling Noodles (滾麵) 專案交接手冊 🍜

這份手冊旨在協助接手的 AI 快速理解「滾麵專案」現況、架構、技術設定以及使用者的運作習慣。

---

## 🎯 1. 專案概觀 (Project Overview)
本專案為「滾麵」品牌開發的 **ERP + 智慧報表系統**。
- **核心目標**：將事後分析報表轉型為每日營運的核心工具，涵蓋進銷存管理、財務現金流、以及自動化數據分析。
- **目前版本**：`2.5.2` (基於 `config.py`)

## 📂 2. 目錄架構 (Directory Structure)
專案根目錄為 `/Users/mason/滾麵專案/智慧報表`，主要結構如下：
- `/erp`: 
  - `backend/`: FastAPI 核心，處理 B2B 業務邏輯、權限 (JWT)、資料庫操作。
  - `frontend/`: Vue 3 + Vite + Tailwind CSS 開發的行動優先 PWA。
- `/streamlit`: 基於 Streamlit 的數據儀表板，提供直觀的數據視覺化。
- `/database`: 包含資料庫 Schema、ETL Pipeline (`data_pipeline.py`) 及檔案監控器 (`file_watcher.py`)。
- `/scripts`: 部署、遷移、維護工具腳本。
- `/_agents/workflows`: AI 專用的 SOP 流程圖與調試手冊。

## ⚙️ 3. 技術規格與設定 (Technical Specs)
- **後端**: Python (FastAPI), Python 3.10+
- **前端**: Vue 3 / Streamlit (Port 8501 產線, 8502 測試)
- **資料庫**: PostgreSQL (Local: localhost, Remote: 34.81.51.45)
- **快取**: SFTP + Parquet 檔案（用於報表加速，達成 ~0.5s 讀取）。
- **基礎設施**: GCP (e2-medium), Systemd 管理服務。

## 📈 4. 目前進度與關鍵問題 (Current Progress & Issues)
### 最近修正 (2026-03-11/12):
1. **File Watcher 優化**：已支援 SFTP 上傳完成後的「重新命名 (Moved)」事件監聽。
2. **數據管道強健性**：修復了空資料時日期格式錯誤導致 ETL 崩潰的問題。
3. **路徑修正**：確保腳本在重構後的目錄結構中能正確呼叫 `.venv`。

### 🚨 待處理問題 (Pending):
- **Database Lock**: `data_pipeline.py` 在執行 `ALTER TABLE` 時可能與正在讀取的 Streamlit 連線產生衝突，導致超時。目前正在將結構更新移出頻繁執行的 ETL 流程中。

## 👤 5. 使用習慣與注意事項 (User Habits & Precautions)
- **協作模式**：
  - 複雜任務請務必進入 **Task Mode** (建立 `task.md`, `implementation_plan.md`)。
  - 頻繁參考 `CONTEXT.md` 與 `ERP開發企劃書_Draft.md` 以確保決策一致。
- **部署習慣**：
  - 使用者通常會透過自動化腳本 (`deploy_erp.py`, `upload_watcher.py`) 進行部署。
  - 部署前需檢查 SSH Key 狀態 (僅保留單一特定 SSH Key)。
- **資料處理行為**：
  - 使用者習慣透過 SFTP 上傳 CSV 或 Excel 檔案。系統需即時偵測並更新數據。
  - 若數據未更新，優先檢查 `database/file_watcher.py` 的日誌。

## 🛠 6. 常用快速指令 (Quick Start Commands)
- **檢查服務狀態**: `python3 check_server.py`
- **手動觸發 ETL**: `python3 trigger_pipeline.py`
- **查看後端日誌**: `tail -f erp/backend/backend.log`
- **重啟服務**: `python3 restart_app.py`

---

> [!TIP]
> 接手 AI 請優先閱讀 `CONTEXT.md` 作為所有決策的基礎，並在修改前更新 `task.md`。
