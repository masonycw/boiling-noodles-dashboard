# 滾麵 ERP — CLAUDE.md

> 快速上手指南。詳細任務規格見 `../dev-tasks/`，部署細節見 `../dev-tasks/部署操作手冊.docx`。

---

## 專案概述

**滾麵 ERP** — 餐廳內部管理系統，分為前台 App（員工用）與後台 Admin（管理用）。

- 前台：行動端 PWA，員工操作叫貨、盤點、金流、耗損
- 後台：管理員/店長用的 SPA，管理資料、查看報表、系統設置

---

## 技術棧

| 層 | 技術 |
|---|---|
| 後端 | Python 3.11 · FastAPI · SQLAlchemy · PostgreSQL · uvicorn |
| 前台 App | Vue 3 · Pinia · Vue Router · Vite · TailwindCSS（port 5173） |
| 後台 Admin | Vue 3 · Pinia · Vue Router · Vite · TailwindCSS（port 5174） |
| 認證 | JWT（python-jose）· bcrypt |

---

## 目錄結構

```
erp/
├── backend/
│   ├── main.py          ← FastAPI 入口，所有 router 在此 include
│   ├── api/             ← 各功能路由（auth / inventory / finance / stocktake / waste / users…）
│   ├── db/
│   │   ├── models.py    ← 所有 SQLAlchemy Model 定義
│   │   └── session.py   ← DB engine / Session
│   ├── core/
│   │   └── security.py  ← JWT 簽發/驗證
│   ├── .env             ← 本地環境變數
│   └── .env.production  ← 正式環境變數（deploy 時覆蓋 .env）
├── frontend/src/        ← 前台 App Vue 代碼
└── admin/src/           ← 後台 Admin Vue 代碼
```

---

## 伺服器

| 項目 | 值 |
|---|---|
| IP | 34.81.51.45 |
| SSH 帳號 | mason_ycw |
| SSH 密碼 | masonpass |
| 認證方式 | 密碼認證（paramiko 需加 `look_for_keys=False, allow_agent=False`） |
| ERP 根目錄 | /home/mason_ycw/boiling-noodles-dashboard/erp |
| 部署指令 | `python deploy_erp.py`（在 智慧報表/ 目錄執行） |

---

## 後台路由結構（B4 重整後）

```
/dashboard                    總覽
/inventory/orders             叫貨收貨
/inventory/stocktakes         盤點紀錄
/inventory/vendors            供應商管理
/cashflow/overview            金流總覽
/cashflow/transactions        金流紀錄
/cashflow/petty-cash          零用金管理
/finance/reports              損益報表
/settings/accounts            帳號管理
/settings/financial-params    財務參數
/settings/display             顯示設置
/settings/features            功能開關
/settings/integrations        串接管理（LINE / 外送平台）
```

---

## 任務卡系統

功能均已拆分為任務卡，存放於 `../dev-tasks/`；完成的任務卡移至 `../dev-tasks/completed/`。

**使用規則：每次只給一張任務卡，嚴格按驗收條件完成後再給下一張。完成後將任務卡移至 completed/ 並更新 README。**

| 狀態 | 系列 | 內容 |
|---|---|---|
| ✅ 完成 | B3、B4、D1、D2 | 架構基礎 |
| ✅ 完成 | A1–A4 | 前台 App 功能強化 |
| ✅ 完成 | B1 | 後台供應商品項重構 |
| ✅ 完成 | C1 | 三角色權限矩陣 |
| ✅ 完成 | E1–E5 | 各類紀錄的編輯/刪除功能 |
| ✅ 完成 | F1 | 操作人顯示規範（共用 UserBadge 元件） |
| ✅ 完成 | P3-0~P3-4 | PWA 強化 + Admin 金流/報表/分類/通知 |

**目前進度：全部任務卡已完成。**

---

## 關鍵業務規則（不可違反）

- 前台：已收貨訂單不可編輯/刪除（後端 403）
- 前台：今天之前的盤點不可編輯/刪除（後端 403）
- 前台：零用金紀錄僅能查看，無編輯/刪除
- E2/E3/E4：硬刪除；E5 人員：軟刪除（`deleted_at`）
- 外部收入匯入以 `(source, external_id)` UNIQUE 防重複

---

## 重要文件

| 文件 | 位置 |
|---|---|
| 任務卡索引 | `../dev-tasks/README.md` |
| Claude Code 移交手冊 | `../dev-tasks/Claude_Code_移交手冊.docx` |
| 部署操作手冊 | `../dev-tasks/部署操作手冊.docx` |
| 系統架構圖 | `../system_architecture_full.html` |

---

> ⚠️ **維護要求：任何重大更新（新功能、架構異動、路由變更、部署方式調整）都必須回來更新這份 CLAUDE.md。**
