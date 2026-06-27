"""Expense Tracker API — app assembly only. Logic lives in routers/ and db.py."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import MODEL_NAME, VLLM_URL
from db import init_db, migrate_json, migrate_schema, seed_defaults
from routers import (
    categories,
    chat,
    dashboard,
    expenses,
    export,
    master_wallet,
    subscriptions,
    wallets,
)

app = FastAPI(title="Expense Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup: schema + migrations + seed (all idempotent)
init_db()
migrate_schema()
migrate_json()
seed_defaults()

for module in (wallets, categories, expenses, subscriptions, master_wallet, dashboard, chat, export):
    app.include_router(module.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "ollama_url": VLLM_URL}
