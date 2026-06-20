import csv
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Expense Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)

VLLM_URL = os.getenv("VLLM_URL", "http://vllm:8001")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")


# --- Data helpers ---

def load(filename: str) -> list:
    path = DATA_DIR / filename
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save(filename: str, data: list) -> None:
    path = DATA_DIR / filename
    path.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")


def sync_expenses_csv(expenses: list) -> None:
    if not expenses:
        return
    path = DATA_DIR / "expenses.csv"
    fields = ["id", "date", "amount", "description", "category_id", "wallet_id", "type"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(expenses)


def new_id() -> str:
    return str(uuid.uuid4())


# --- Pydantic models ---

class Wallet(BaseModel):
    name: str
    budget: float
    color: str = "#6366f1"
    icon: str = "💰"


class Category(BaseModel):
    name: str
    wallet_id: str
    type: str = "daily"  # daily | subscription | unexpected


class Expense(BaseModel):
    date: str
    amount: float
    description: str
    category_id: str
    wallet_id: str
    type: str = "planned"  # planned | unexpected


class Subscription(BaseModel):
    name: str
    amount: float
    billing_day: int
    wallet_id: str
    active: bool = True


class ChatMessage(BaseModel):
    message: str


# --- Default seed data ---

def seed_defaults() -> None:
    if not (DATA_DIR / "wallets.json").exists():
        defaults = [
            {"id": new_id(), "name": "Basic Survival", "budget": 10000, "color": "#10b981", "icon": "🏠"},
            {"id": new_id(), "name": "Travelling", "budget": 5000, "color": "#3b82f6", "icon": "✈️"},
            {"id": new_id(), "name": "Relax", "budget": 3000, "color": "#f59e0b", "icon": "☕"},
            {"id": new_id(), "name": "Investment", "budget": 8000, "color": "#8b5cf6", "icon": "📈"},
        ]
        save("wallets.json", defaults)

    if not (DATA_DIR / "categories.json").exists():
        wallets = load("wallets.json")
        wmap = {w["name"]: w["id"] for w in wallets}
        defaults = [
            {"id": new_id(), "name": "Groceries", "wallet_id": wmap.get("Basic Survival", ""), "type": "daily"},
            {"id": new_id(), "name": "Utilities", "wallet_id": wmap.get("Basic Survival", ""), "type": "subscription"},
            {"id": new_id(), "name": "Transport", "wallet_id": wmap.get("Basic Survival", ""), "type": "daily"},
            {"id": new_id(), "name": "Cafe", "wallet_id": wmap.get("Relax", ""), "type": "daily"},
            {"id": new_id(), "name": "Dining Out", "wallet_id": wmap.get("Relax", ""), "type": "daily"},
            {"id": new_id(), "name": "Entertainment", "wallet_id": wmap.get("Relax", ""), "type": "daily"},
            {"id": new_id(), "name": "Flight", "wallet_id": wmap.get("Travelling", ""), "type": "unexpected"},
            {"id": new_id(), "name": "Hotel", "wallet_id": wmap.get("Travelling", ""), "type": "unexpected"},
            {"id": new_id(), "name": "Stocks/ETF", "wallet_id": wmap.get("Investment", ""), "type": "planned"},
        ]
        save("categories.json", defaults)

    for fname in ["expenses.json", "subscriptions.json"]:
        if not (DATA_DIR / fname).exists():
            save(fname, [])


seed_defaults()


# === Wallets ===

@app.get("/api/wallets")
def get_wallets():
    return load("wallets.json")


@app.post("/api/wallets")
def create_wallet(wallet: Wallet):
    wallets = load("wallets.json")
    item = {"id": new_id(), **wallet.model_dump()}
    wallets.append(item)
    save("wallets.json", wallets)
    return item


@app.put("/api/wallets/{wallet_id}")
def update_wallet(wallet_id: str, wallet: Wallet):
    wallets = load("wallets.json")
    for i, w in enumerate(wallets):
        if w["id"] == wallet_id:
            wallets[i] = {"id": wallet_id, **wallet.model_dump()}
            save("wallets.json", wallets)
            return wallets[i]
    raise HTTPException(404, "Wallet not found")


@app.delete("/api/wallets/{wallet_id}")
def delete_wallet(wallet_id: str):
    wallets = [w for w in load("wallets.json") if w["id"] != wallet_id]
    save("wallets.json", wallets)
    return {"ok": True}


# === Categories ===

@app.get("/api/categories")
def get_categories():
    return load("categories.json")


@app.post("/api/categories")
def create_category(cat: Category):
    categories = load("categories.json")
    item = {"id": new_id(), **cat.model_dump()}
    categories.append(item)
    save("categories.json", categories)
    return item


@app.put("/api/categories/{cat_id}")
def update_category(cat_id: str, cat: Category):
    categories = load("categories.json")
    for i, c in enumerate(categories):
        if c["id"] == cat_id:
            categories[i] = {"id": cat_id, **cat.model_dump()}
            save("categories.json", categories)
            return categories[i]
    raise HTTPException(404, "Category not found")


@app.delete("/api/categories/{cat_id}")
def delete_category(cat_id: str):
    categories = [c for c in load("categories.json") if c["id"] != cat_id]
    save("categories.json", categories)
    return {"ok": True}


# === Expenses ===

@app.get("/api/expenses")
def get_expenses(month: Optional[str] = None, wallet_id: Optional[str] = None):
    expenses = load("expenses.json")
    if month:
        expenses = [e for e in expenses if e.get("date", "").startswith(month)]
    if wallet_id:
        expenses = [e for e in expenses if e.get("wallet_id") == wallet_id]
    return expenses


@app.post("/api/expenses")
def create_expense(expense: Expense):
    expenses = load("expenses.json")
    item = {"id": new_id(), **expense.model_dump()}
    expenses.append(item)
    save("expenses.json", expenses)
    sync_expenses_csv(expenses)
    return item


@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: str, expense: Expense):
    expenses = load("expenses.json")
    for i, e in enumerate(expenses):
        if e["id"] == expense_id:
            expenses[i] = {"id": expense_id, **expense.model_dump()}
            save("expenses.json", expenses)
            sync_expenses_csv(expenses)
            return expenses[i]
    raise HTTPException(404, "Expense not found")


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: str):
    expenses = [e for e in load("expenses.json") if e["id"] != expense_id]
    save("expenses.json", expenses)
    sync_expenses_csv(expenses)
    return {"ok": True}


# === Subscriptions ===

@app.get("/api/subscriptions")
def get_subscriptions():
    return load("subscriptions.json")


@app.post("/api/subscriptions")
def create_subscription(sub: Subscription):
    subs = load("subscriptions.json")
    item = {"id": new_id(), **sub.model_dump()}
    subs.append(item)
    save("subscriptions.json", subs)
    return item


@app.put("/api/subscriptions/{sub_id}")
def update_subscription(sub_id: str, sub: Subscription):
    subs = load("subscriptions.json")
    for i, s in enumerate(subs):
        if s["id"] == sub_id:
            subs[i] = {"id": sub_id, **sub.model_dump()}
            save("subscriptions.json", subs)
            return subs[i]
    raise HTTPException(404, "Subscription not found")


@app.delete("/api/subscriptions/{sub_id}")
def delete_subscription(sub_id: str):
    subs = [s for s in load("subscriptions.json") if s["id"] != sub_id]
    save("subscriptions.json", subs)
    return {"ok": True}


# === Dashboard ===

@app.get("/api/dashboard")
def get_dashboard(month: Optional[str] = None):
    if not month:
        month = datetime.now().strftime("%Y-%m")

    wallets = load("wallets.json")
    expenses = load("expenses.json")
    subscriptions = load("subscriptions.json")

    month_expenses = [e for e in expenses if e.get("date", "").startswith(month)]

    wallet_breakdown = []
    for w in wallets:
        spent = sum(e["amount"] for e in month_expenses if e.get("wallet_id") == w["id"])
        wallet_breakdown.append({
            "wallet": w,
            "spent": spent,
            "budget": w["budget"],
            "remaining": w["budget"] - spent,
            "pct": round(spent / w["budget"] * 100, 1) if w["budget"] else 0,
        })

    active_subs = [s for s in subscriptions if s.get("active", True)]
    sub_total = sum(s["amount"] for s in active_subs)

    total_spent = sum(e["amount"] for e in month_expenses)
    total_budget = sum(w["budget"] for w in wallets)
    days_passed = max(datetime.now().day, 1)

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_expenses = [e for e in month_expenses if e.get("date") == today_str]

    # Daily spending by date for chart
    daily: dict = {}
    for e in month_expenses:
        d = e.get("date", "")
        daily[d] = daily.get(d, 0) + e["amount"]

    return {
        "month": month,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_remaining": total_budget - total_spent,
        "daily_average": round(total_spent / days_passed, 2),
        "wallet_breakdown": wallet_breakdown,
        "subscription_total": sub_total,
        "active_subscriptions": active_subs,
        "unexpected_count": len([e for e in month_expenses if e.get("type") == "unexpected"]),
        "today_spent": sum(e["amount"] for e in today_expenses),
        "today_count": len(today_expenses),
        "recent_expenses": sorted(month_expenses, key=lambda x: x.get("date", ""), reverse=True)[:10],
        "daily_chart": sorted([{"date": k, "amount": v} for k, v in daily.items()], key=lambda x: x["date"]),
    }


# === Chat ===

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    wallets = load("wallets.json")
    expenses = load("expenses.json")
    month = datetime.now().strftime("%Y-%m")
    month_expenses = [e for e in expenses if e.get("date", "").startswith(month)]

    wallet_summary = [
        {"name": w["name"], "budget": w["budget"],
         "spent": sum(e["amount"] for e in month_expenses if e.get("wallet_id") == w["id"])}
        for w in wallets
    ]

    system_prompt = f"""You are a personal finance assistant for an expense tracking app.
Today: {datetime.now().strftime('%Y-%m-%d')}. Current month: {month}.

Wallet summary this month:
{json.dumps(wallet_summary, ensure_ascii=False)}

Total transactions this month: {len(month_expenses)}
Total spent: {sum(e['amount'] for e in month_expenses):,.0f} THB

Answer concisely. Use THB currency. Be helpful about budgeting, spending patterns, and financial advice."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{VLLM_URL}/v1/chat/completions",
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": msg.message},
                    ],
                    "max_tokens": 512,
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return {"reply": data["choices"][0]["message"]["content"], "ok": True}
        except httpx.ConnectError:
            return {"reply": "vLLM not reachable. Start with: docker compose --profile ai up", "ok": False}
        except Exception as e:
            return {"reply": f"AI error: {str(e)}", "ok": False}


# === Export ===

@app.get("/api/export/expenses.csv")
def export_csv():
    path = DATA_DIR / "expenses.csv"
    if not path.exists():
        raise HTTPException(404, "No expenses yet")
    return FileResponse(path, media_type="text/csv", filename="expenses.csv")


@app.get("/api/export/data.json")
def export_json():
    return JSONResponse({
        "wallets": load("wallets.json"),
        "categories": load("categories.json"),
        "expenses": load("expenses.json"),
        "subscriptions": load("subscriptions.json"),
        "exported_at": datetime.now().isoformat(),
    })


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "vllm_url": VLLM_URL}
