import csv
import io
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
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
DB_PATH = DATA_DIR / "expense.db"

VLLM_URL = os.getenv("VLLM_URL", "http://ollama:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def new_id() -> str:
    return str(uuid.uuid4())


def row_to_dict(row) -> dict:
    d = dict(row)
    if "active" in d:
        d["active"] = bool(d["active"])
    return d


# --- Pydantic models ---

class Wallet(BaseModel):
    name: str
    budget: float
    color: str = "#6366f1"
    icon: str = "💰"


class Category(BaseModel):
    name: str
    wallet_id: str
    type: str = "daily"


class Expense(BaseModel):
    date: str
    amount: float
    description: str
    category_id: str
    wallet_id: str
    type: str = "planned"


class Subscription(BaseModel):
    name: str
    amount: float
    billing_day: int
    wallet_id: str
    active: bool = True


class ChatHistoryItem(BaseModel):
    role: str
    content: str


class ChatMessage(BaseModel):
    message: str
    history: list[ChatHistoryItem] = []


# --- Init, migration, seed ---

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS wallets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                budget REAL NOT NULL,
                color TEXT DEFAULT '#6366f1',
                icon TEXT DEFAULT '💰'
            );
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                wallet_id TEXT NOT NULL,
                type TEXT DEFAULT 'daily'
            );
            CREATE TABLE IF NOT EXISTS expenses (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                category_id TEXT NOT NULL,
                wallet_id TEXT NOT NULL,
                type TEXT DEFAULT 'planned'
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                billing_day INTEGER NOT NULL,
                wallet_id TEXT NOT NULL,
                active INTEGER DEFAULT 1
            );
        """)


def migrate_json():
    """One-time migration: JSON files → SQLite (runs only if wallets table is empty)."""
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM wallets").fetchone()[0] > 0:
            return

        def load_json(name):
            path = DATA_DIR / name
            return json.loads(path.read_text()) if path.exists() else []

        for w in load_json("wallets.json"):
            conn.execute(
                "INSERT OR IGNORE INTO wallets VALUES (?,?,?,?,?)",
                (w["id"], w["name"], w["budget"], w.get("color", "#6366f1"), w.get("icon", "💰")),
            )
        for c in load_json("categories.json"):
            conn.execute(
                "INSERT OR IGNORE INTO categories VALUES (?,?,?,?)",
                (c["id"], c["name"], c["wallet_id"], c.get("type", "daily")),
            )
        for e in load_json("expenses.json"):
            conn.execute(
                "INSERT OR IGNORE INTO expenses VALUES (?,?,?,?,?,?,?)",
                (e["id"], e["date"], e["amount"], e["description"], e["category_id"], e["wallet_id"], e.get("type", "planned")),
            )
        for s in load_json("subscriptions.json"):
            conn.execute(
                "INSERT OR IGNORE INTO subscriptions VALUES (?,?,?,?,?,?)",
                (s["id"], s["name"], s["amount"], s["billing_day"], s["wallet_id"], 1 if s.get("active", True) else 0),
            )


def seed_defaults():
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM wallets").fetchone()[0] > 0:
            return
        wids = {
            "Basic Survival": new_id(),
            "Travelling": new_id(),
            "Relax": new_id(),
            "Investment": new_id(),
        }
        conn.executemany(
            "INSERT INTO wallets VALUES (?,?,?,?,?)",
            [
                (wids["Basic Survival"], "Basic Survival", 10000, "#10b981", "🏠"),
                (wids["Travelling"], "Travelling", 5000, "#3b82f6", "✈️"),
                (wids["Relax"], "Relax", 3000, "#f59e0b", "☕"),
                (wids["Investment"], "Investment", 8000, "#8b5cf6", "📈"),
            ],
        )
        conn.executemany(
            "INSERT INTO categories VALUES (?,?,?,?)",
            [
                (new_id(), "Groceries", wids["Basic Survival"], "daily"),
                (new_id(), "Utilities", wids["Basic Survival"], "subscription"),
                (new_id(), "Transport", wids["Basic Survival"], "daily"),
                (new_id(), "Cafe", wids["Relax"], "daily"),
                (new_id(), "Dining Out", wids["Relax"], "daily"),
                (new_id(), "Entertainment", wids["Relax"], "daily"),
                (new_id(), "Flight", wids["Travelling"], "unexpected"),
                (new_id(), "Hotel", wids["Travelling"], "unexpected"),
                (new_id(), "Stocks/ETF", wids["Investment"], "planned"),
            ],
        )


init_db()
migrate_json()
seed_defaults()


# === Wallets ===

@app.get("/api/wallets")
def get_wallets():
    with get_db() as conn:
        return [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]


@app.post("/api/wallets")
def create_wallet(wallet: Wallet):
    item = {"id": new_id(), **wallet.model_dump()}
    with get_db() as conn:
        conn.execute(
            "INSERT INTO wallets VALUES (?,?,?,?,?)",
            (item["id"], item["name"], item["budget"], item["color"], item["icon"]),
        )
    return item


@app.put("/api/wallets/{wallet_id}")
def update_wallet(wallet_id: str, wallet: Wallet):
    with get_db() as conn:
        r = conn.execute(
            "UPDATE wallets SET name=?,budget=?,color=?,icon=? WHERE id=? RETURNING *",
            (wallet.name, wallet.budget, wallet.color, wallet.icon, wallet_id),
        ).fetchone()
    if not r:
        raise HTTPException(404, "Wallet not found")
    return row_to_dict(r)


@app.delete("/api/wallets/{wallet_id}")
def delete_wallet(wallet_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM wallets WHERE id=?", (wallet_id,))
    return {"ok": True}


# === Categories ===

@app.get("/api/categories")
def get_categories():
    with get_db() as conn:
        return [row_to_dict(r) for r in conn.execute("SELECT * FROM categories")]


@app.post("/api/categories")
def create_category(cat: Category):
    item = {"id": new_id(), **cat.model_dump()}
    with get_db() as conn:
        conn.execute(
            "INSERT INTO categories VALUES (?,?,?,?)",
            (item["id"], item["name"], item["wallet_id"], item["type"]),
        )
    return item


@app.put("/api/categories/{cat_id}")
def update_category(cat_id: str, cat: Category):
    with get_db() as conn:
        r = conn.execute(
            "UPDATE categories SET name=?,wallet_id=?,type=? WHERE id=? RETURNING *",
            (cat.name, cat.wallet_id, cat.type, cat_id),
        ).fetchone()
    if not r:
        raise HTTPException(404, "Category not found")
    return row_to_dict(r)


@app.delete("/api/categories/{cat_id}")
def delete_category(cat_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    return {"ok": True}


# === Expenses ===

@app.get("/api/expenses")
def get_expenses(month: Optional[str] = None, wallet_id: Optional[str] = None):
    query = "SELECT * FROM expenses WHERE 1=1"
    params: list = []
    if month:
        query += " AND date LIKE ?"
        params.append(f"{month}%")
    if wallet_id:
        query += " AND wallet_id=?"
        params.append(wallet_id)
    with get_db() as conn:
        return [row_to_dict(r) for r in conn.execute(query, params)]


@app.post("/api/expenses")
def create_expense(expense: Expense):
    item = {"id": new_id(), **expense.model_dump()}
    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses VALUES (?,?,?,?,?,?,?)",
            (item["id"], item["date"], item["amount"], item["description"],
             item["category_id"], item["wallet_id"], item["type"]),
        )
    return item


@app.put("/api/expenses/{expense_id}")
def update_expense(expense_id: str, expense: Expense):
    with get_db() as conn:
        r = conn.execute(
            "UPDATE expenses SET date=?,amount=?,description=?,category_id=?,wallet_id=?,type=? WHERE id=? RETURNING *",
            (expense.date, expense.amount, expense.description, expense.category_id,
             expense.wallet_id, expense.type, expense_id),
        ).fetchone()
    if not r:
        raise HTTPException(404, "Expense not found")
    return row_to_dict(r)


@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    return {"ok": True}


# === Subscriptions ===

@app.get("/api/subscriptions")
def get_subscriptions():
    with get_db() as conn:
        return [row_to_dict(r) for r in conn.execute("SELECT * FROM subscriptions")]


@app.post("/api/subscriptions")
def create_subscription(sub: Subscription):
    item = {"id": new_id(), **sub.model_dump()}
    with get_db() as conn:
        conn.execute(
            "INSERT INTO subscriptions VALUES (?,?,?,?,?,?)",
            (item["id"], item["name"], item["amount"], item["billing_day"],
             item["wallet_id"], 1 if item["active"] else 0),
        )
    return item


@app.put("/api/subscriptions/{sub_id}")
def update_subscription(sub_id: str, sub: Subscription):
    with get_db() as conn:
        r = conn.execute(
            "UPDATE subscriptions SET name=?,amount=?,billing_day=?,wallet_id=?,active=? WHERE id=? RETURNING *",
            (sub.name, sub.amount, sub.billing_day, sub.wallet_id, 1 if sub.active else 0, sub_id),
        ).fetchone()
    if not r:
        raise HTTPException(404, "Subscription not found")
    return row_to_dict(r)


@app.delete("/api/subscriptions/{sub_id}")
def delete_subscription(sub_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
    return {"ok": True}


# === Dashboard ===

@app.get("/api/dashboard")
def get_dashboard(month: Optional[str] = None):
    if not month:
        month = datetime.now().strftime("%Y-%m")

    with get_db() as conn:
        wallets = [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]
        expenses = [row_to_dict(r) for r in conn.execute(
            "SELECT * FROM expenses WHERE date LIKE ?", (f"{month}%",)
        )]
        subscriptions = [row_to_dict(r) for r in conn.execute("SELECT * FROM subscriptions")]

    active_subs = [s for s in subscriptions if s["active"]]
    sub_total = sum(s["amount"] for s in active_subs)
    total_spent = sum(e["amount"] for e in expenses)
    total_budget = sum(w["budget"] for w in wallets)
    days_passed = max(datetime.now().day, 1)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_expenses = [e for e in expenses if e["date"] == today_str]

    wallet_breakdown = []
    for w in wallets:
        spent = sum(e["amount"] for e in expenses if e["wallet_id"] == w["id"])
        wallet_breakdown.append({
            "wallet": w,
            "spent": spent,
            "budget": w["budget"],
            "remaining": w["budget"] - spent,
            "pct": round(spent / w["budget"] * 100, 1) if w["budget"] else 0,
        })

    daily: dict = {}
    for e in expenses:
        d = e["date"]
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
        "unexpected_count": len([e for e in expenses if e["type"] == "unexpected"]),
        "today_spent": sum(e["amount"] for e in today_expenses),
        "today_count": len(today_expenses),
        "recent_expenses": sorted(expenses, key=lambda x: x["date"], reverse=True)[:10],
        "daily_chart": sorted(
            [{"date": k, "amount": v} for k, v in daily.items()], key=lambda x: x["date"]
        ),
    }


# === Chat / Tool Calling ===

CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Add a new expense to the tracker. Use this when the user says they spent money or bought something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Amount in THB"},
                    "description": {"type": "string", "description": "What was purchased or spent on"},
                    "wallet_name": {"type": "string", "description": "Wallet name (e.g. 'Basic Survival', 'Relax')"},
                    "category_name": {"type": "string", "description": "Category name (e.g. 'Groceries', 'Cafe'). Leave empty to auto-match."},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Default: today."},
                    "type": {"type": "string", "enum": ["planned", "unexpected"], "description": "planned or unexpected. Default: planned."},
                },
                "required": ["amount", "description", "wallet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_subscription",
            "description": "Add a new recurring subscription.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Subscription name (e.g. 'Netflix')"},
                    "amount": {"type": "number", "description": "Monthly amount in THB"},
                    "billing_day": {"type": "integer", "description": "Day of month when billed (1-31)"},
                    "wallet_name": {"type": "string", "description": "Wallet name to charge to"},
                },
                "required": ["name", "amount", "billing_day", "wallet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_expense",
            "description": "Update fields on an existing expense (amount, description, date, type).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expense_id": {"type": "string", "description": "ID of the expense to update"},
                    "amount": {"type": "number"},
                    "description": {"type": "string"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD"},
                    "type": {"type": "string", "enum": ["planned", "unexpected"]},
                },
                "required": ["expense_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_subscription",
            "description": "Update a subscription — change amount, name, billing day, or pause/resume (set active).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sub_id": {"type": "string", "description": "ID of the subscription to update"},
                    "name": {"type": "string"},
                    "amount": {"type": "number"},
                    "billing_day": {"type": "integer"},
                    "active": {"type": "boolean", "description": "true = active, false = paused"},
                },
                "required": ["sub_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_expenses",
            "description": "List expenses for a given month to find IDs or check spending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "Month in YYYY-MM format. Default: current month."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_subscriptions",
            "description": "List all subscriptions with their IDs, amounts and status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _find_wallet(conn, name: str) -> dict | None:
    name_lower = name.lower()
    rows = [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]
    for w in rows:
        if w["name"].lower() == name_lower:
            return w
    for w in rows:
        if name_lower in w["name"].lower():
            return w
    return None


def _find_or_create_category(conn, cat_name: str, wallet_id: str) -> str:
    if cat_name:
        cat_name_lower = cat_name.lower()
        rows = [row_to_dict(r) for r in conn.execute(
            "SELECT * FROM categories WHERE wallet_id=?", (wallet_id,)
        )]
        for c in rows:
            if c["name"].lower() == cat_name_lower:
                return c["id"]
        for c in rows:
            if cat_name_lower in c["name"].lower():
                return c["id"]
        cid = new_id()
        conn.execute("INSERT INTO categories VALUES (?,?,?,?)", (cid, cat_name, wallet_id, "daily"))
        return cid
    else:
        r = conn.execute("SELECT id FROM categories WHERE wallet_id=? LIMIT 1", (wallet_id,)).fetchone()
        if r:
            return r["id"]
        cid = new_id()
        conn.execute("INSERT INTO categories VALUES (?,?,?,?)", (cid, "General", wallet_id, "daily"))
        return cid


def _execute_tool(name: str, args: dict) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")

    if name == "add_expense":
        wallet_name = args.get("wallet_name", "")
        with get_db() as conn:
            wallet = _find_wallet(conn, wallet_name)
            if not wallet:
                return {"ok": False, "error": f"Wallet '{wallet_name}' not found"}
            cat_id = _find_or_create_category(conn, args.get("category_name", ""), wallet["id"])
            eid = new_id()
            conn.execute(
                "INSERT INTO expenses VALUES (?,?,?,?,?,?,?)",
                (eid, args.get("date", today), args["amount"], args["description"],
                 cat_id, wallet["id"], args.get("type", "planned")),
            )
        return {
            "ok": True,
            "action": "add_expense",
            "id": eid,
            "description": args["description"],
            "amount": args["amount"],
            "wallet": wallet["name"],
            "date": args.get("date", today),
        }

    if name == "add_subscription":
        wallet_name = args.get("wallet_name", "")
        with get_db() as conn:
            wallet = _find_wallet(conn, wallet_name)
            if not wallet:
                return {"ok": False, "error": f"Wallet '{wallet_name}' not found"}
            sid = new_id()
            conn.execute(
                "INSERT INTO subscriptions VALUES (?,?,?,?,?,?)",
                (sid, args["name"], args["amount"], args["billing_day"], wallet["id"], 1),
            )
        return {
            "ok": True,
            "action": "add_subscription",
            "id": sid,
            "name": args["name"],
            "amount": args["amount"],
            "billing_day": args["billing_day"],
            "wallet": wallet["name"],
        }

    if name == "update_expense":
        eid = args["expense_id"]
        with get_db() as conn:
            current = conn.execute("SELECT * FROM expenses WHERE id=?", (eid,)).fetchone()
            if not current:
                return {"ok": False, "error": f"Expense {eid} not found"}
            cur = row_to_dict(current)
            new_date = args.get("date", cur["date"])
            new_amount = args.get("amount", cur["amount"])
            new_desc = args.get("description", cur["description"])
            new_type = args.get("type", cur["type"])
            conn.execute(
                "UPDATE expenses SET date=?,amount=?,description=?,type=? WHERE id=?",
                (new_date, new_amount, new_desc, new_type, eid),
            )
        return {"ok": True, "action": "update_expense", "id": eid, "amount": new_amount, "description": new_desc}

    if name == "update_subscription":
        sid = args["sub_id"]
        with get_db() as conn:
            current = conn.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone()
            if not current:
                return {"ok": False, "error": f"Subscription {sid} not found"}
            cur = row_to_dict(current)
            new_name = args.get("name", cur["name"])
            new_amount = args.get("amount", cur["amount"])
            new_day = args.get("billing_day", cur["billing_day"])
            new_active = args.get("active", cur["active"])
            conn.execute(
                "UPDATE subscriptions SET name=?,amount=?,billing_day=?,active=? WHERE id=?",
                (new_name, new_amount, new_day, 1 if new_active else 0, sid),
            )
        return {"ok": True, "action": "update_subscription", "id": sid, "name": new_name,
                "active": new_active, "amount": new_amount}

    if name == "list_expenses":
        m = args.get("month", month)
        with get_db() as conn:
            rows = [row_to_dict(r) for r in conn.execute(
                "SELECT e.*, c.name as cat_name, w.name as wallet_name FROM expenses e "
                "LEFT JOIN categories c ON e.category_id=c.id "
                "LEFT JOIN wallets w ON e.wallet_id=w.id "
                "WHERE e.date LIKE ? ORDER BY e.date DESC", (f"{m}%",)
            )]
        return {"ok": True, "action": "list_expenses", "expenses": rows}

    if name == "list_subscriptions":
        with get_db() as conn:
            rows = [row_to_dict(r) for r in conn.execute(
                "SELECT s.*, w.name as wallet_name FROM subscriptions s "
                "LEFT JOIN wallets w ON s.wallet_id=w.id"
            )]
        return {"ok": True, "action": "list_subscriptions", "subscriptions": rows}

    return {"ok": False, "error": f"Unknown tool: {name}"}


@app.post("/api/chat")
async def chat(msg: ChatMessage):
    month = datetime.now().strftime("%Y-%m")
    today = datetime.now().strftime("%Y-%m-%d")

    with get_db() as conn:
        wallets = [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]
        expenses = [row_to_dict(r) for r in conn.execute(
            "SELECT * FROM expenses WHERE date LIKE ?", (f"{month}%",)
        )]
        categories = [row_to_dict(r) for r in conn.execute("SELECT * FROM categories")]

    wallet_summary = [
        {
            "id": w["id"],
            "name": w["name"],
            "budget": w["budget"],
            "spent": sum(e["amount"] for e in expenses if e["wallet_id"] == w["id"]),
        }
        for w in wallets
    ]
    cat_summary = [{"id": c["id"], "name": c["name"], "wallet_id": c["wallet_id"], "type": c["type"]}
                   for c in categories]

    system_prompt = f"""You are a personal finance assistant for an expense tracking app.
Today: {today}. Current month: {month}.

Available wallets (use exact names for tool calls):
{json.dumps([{"name": w["name"], "budget": w["budget"], "spent": next((x["spent"] for x in wallet_summary if x["id"]==w["id"]), 0)} for w in wallets], ensure_ascii=False)}

Available categories:
{json.dumps([{"name": c["name"], "wallet": next((w["name"] for w in wallets if w["id"]==c["wallet_id"]), ""), "type": c["type"]} for c in categories], ensure_ascii=False)}

Total spent this month: {sum(e['amount'] for e in expenses):,.0f} THB across {len(expenses)} transactions.

You can add/update expenses and subscriptions using the provided tools. When the user says they spent money, call add_expense. When they mention a subscription, call add_subscription. For updates, first call list_expenses or list_subscriptions to get the ID, then update.
Answer in the same language as the user. Use THB currency."""

    history_msgs = [{"role": h.role, "content": h.content} for h in msg.history]
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        *history_msgs,
        {"role": "user", "content": msg.message},
    ]

    actions: list[dict] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            for _ in range(6):  # max tool-call rounds
                resp = await client.post(
                    f"{VLLM_URL}/api/chat",
                    json={
                        "model": MODEL_NAME,
                        "messages": messages,
                        "tools": CHAT_TOOLS,
                        "stream": False,
                        "options": {"temperature": 0.7, "num_predict": 1024},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                assistant_msg = data["message"]
                messages.append(assistant_msg)

                tool_calls = assistant_msg.get("tool_calls") or []
                if not tool_calls:
                    return {
                        "reply": assistant_msg.get("content", ""),
                        "actions": actions,
                        "ok": True,
                    }

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = tc["function"]["arguments"]
                    if isinstance(fn_args, str):
                        fn_args = json.loads(fn_args)
                    result = _execute_tool(fn_name, fn_args)
                    actions.append(result)
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            return {"reply": "Reached tool call limit.", "actions": actions, "ok": True}

        except httpx.ConnectError:
            return {"reply": "Ollama not reachable. Start with: docker compose --profile ai up", "actions": [], "ok": False}
        except Exception as e:
            return {"reply": f"AI error: {str(e)}", "actions": [], "ok": False}


# === Export ===

@app.get("/api/export/expenses.csv")
def export_csv():
    with get_db() as conn:
        expenses = [row_to_dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY date")]
    if not expenses:
        raise HTTPException(404, "No expenses yet")
    buf = io.StringIO()
    fields = ["id", "date", "amount", "description", "category_id", "wallet_id", "type"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(expenses)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


@app.get("/api/export/data.json")
def export_json():
    with get_db() as conn:
        return JSONResponse({
            "wallets": [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")],
            "categories": [row_to_dict(r) for r in conn.execute("SELECT * FROM categories")],
            "expenses": [row_to_dict(r) for r in conn.execute("SELECT * FROM expenses")],
            "subscriptions": [row_to_dict(r) for r in conn.execute("SELECT * FROM subscriptions")],
            "exported_at": datetime.now().isoformat(),
        })


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "ollama_url": VLLM_URL}
