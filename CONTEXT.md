# Project Context: Boiling Noodles (滾麵專案)

## 🎯 Project Overview
This project is an **ERP + Intelligent Reporting System** for "Boiling Noodles" (滾麵). It aims to transition from post-analysis reporting to a daily operational core.

## 🛠 Technical Stack
- **Backend API**: FastAPI (Role-based access, business logic, JWT)
- **Dashboard**: Streamlit (Data visualization, internal reporting)
- **Database**: PostgreSQL (`boiling_noodles` DB)
- **Frontend (Planned)**: Vue 3 + Vite + Tailwind CSS (Mobile-first PWA)
- **Storage**: Google Cloud Storage (GCS) for receipt and inspection photos
- **Cache Layer**: SFTP + Parquet files for high-performance data loading
- **Infrastructure**: GCP (e2-medium recommended), Docker, Systemd

## 📂 Key Directory Structure
- `erp/backend`: Core FastAPI application and business logic
- `streamlit`: Streamlit-based data dashboards
- `database`: Database schemas and migration scripts
- `scripts`: Performance optimization, deployment, and maintenance tools
- `_agents/workflows`: AI-specific SOPs and automation workflows

## 💡 Key Architectural Decisions
1. **Data Performance**: Use Parquet files cached on SFTP for near-instant loading (~0.1-0.5s).
2. **Storage Strategy**: Strictly use GCS for commercial receipts/photos to ensure data persistence and scalability.
3. **Phased Development**:
   - Phase 1: Authentication & DB Foundation
   - Phase 2: Inventory MVP (Ordering, Stock-taking)
   - Phase 3: Cashflow & Accounting
   - Phase 4: BOM & Advanced Inventory
   - Phase 5: Line Automation (Messaging API)
   - Phase 6: AI Document Recognition (Vision API)

## 🤖 Preferred AI Interaction
- Use **Task Mode** for complex coding or architecture changes.
- Use **Discussion Mode** for brainstorming or framework evaluation.
- Follow `.agent/workflows/debug.md` for error analysis.
- Refer to `CONTEXT.md` (this file) and `ERP開發企劃書_Draft.md` before starting new tasks.
