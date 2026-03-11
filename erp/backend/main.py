from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from erp.backend.api import auth, inventory, finance

app = FastAPI(title="Boiling Noodles ERP")

# Setup CORS for Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["inventory"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Boiling Noodles ERP API"}
