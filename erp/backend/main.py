from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from erp.backend.api import auth, inventory, finance, stocktake, waste, users

app = FastAPI(
    title="Boiling Noodles ERP",
    version="3.0.0",
    description="滾麵 ERP API — Phase 3"
)

# Setup CORS for Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───
app.include_router(auth.router,       prefix="/api/v1/auth",      tags=["auth"])
app.include_router(inventory.router,  prefix="/api/v1/inventory",  tags=["inventory"])
app.include_router(finance.router,    prefix="/api/v1",            tags=["finance"])
app.include_router(stocktake.router,  prefix="/api/v1",            tags=["stocktake"])
app.include_router(waste.router,      prefix="/api/v1",            tags=["waste"])
app.include_router(users.router,      prefix="/api/v1",            tags=["users"])


@app.get("/")
def read_root():
    return {
        "message": "Boiling Noodles ERP API",
        "version": "3.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}
