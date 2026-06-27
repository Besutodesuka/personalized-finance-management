from __future__ import annotations

import json
from datetime import datetime

import httpx
from fastapi import APIRouter

from config import MODEL_NAME, VLLM_URL
from db import get_db, insert, new_id, row_to_dict, update
from models import ChatMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])


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
            "description": "Add a new recurring subscription (monthly or yearly).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Subscription name (e.g. 'Netflix')"},
                    "amount": {"type": "number", "description": "Amount in THB per billing cycle"},
                    "billing_day": {"type": "integer", "description": "Day of month when billed (1-31). Used for monthly."},
                    "billing_cycle": {"type": "string", "enum": ["monthly", "yearly"], "description": "Default monthly."},
                    "renewal_date": {"type": "string", "description": "YYYY-MM-DD renewal date. Used for yearly."},
                    "wallet_name": {"type": "string", "description": "Wallet name to charge to"},
                },
                "required": ["name", "amount", "wallet_name"],
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
            "description": "Update a subscription — change amount, name, billing day/cycle, renewal date, or pause/resume (set active).",
            "parameters": {
                "type": "object",
                "properties": {
                    "sub_id": {"type": "string", "description": "ID of the subscription to update"},
                    "name": {"type": "string"},
                    "amount": {"type": "number"},
                    "billing_day": {"type": "integer"},
                    "billing_cycle": {"type": "string", "enum": ["monthly", "yearly"]},
                    "renewal_date": {"type": "string", "description": "YYYY-MM-DD"},
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
        insert(conn, "categories", {"id": cid, "name": cat_name, "wallet_id": wallet_id, "type": "daily"})
        return cid
    r = conn.execute("SELECT id FROM categories WHERE wallet_id=? LIMIT 1", (wallet_id,)).fetchone()
    if r:
        return r["id"]
    cid = new_id()
    insert(conn, "categories", {"id": cid, "name": "General", "wallet_id": wallet_id, "type": "daily"})
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
            insert(conn, "expenses", {
                "id": eid, "date": args.get("date", today), "amount": args["amount"],
                "description": args["description"], "category_id": cat_id,
                "wallet_id": wallet["id"], "type": args.get("type", "planned"),
            })
        return {
            "ok": True, "action": "add_expense", "id": eid,
            "description": args["description"], "amount": args["amount"],
            "wallet": wallet["name"], "date": args.get("date", today),
        }

    if name == "add_subscription":
        wallet_name = args.get("wallet_name", "")
        with get_db() as conn:
            wallet = _find_wallet(conn, wallet_name)
            if not wallet:
                return {"ok": False, "error": f"Wallet '{wallet_name}' not found"}
            sid = new_id()
            cycle = args.get("billing_cycle", "monthly")
            insert(conn, "subscriptions", {
                "id": sid, "name": args["name"], "amount": args["amount"],
                "billing_day": args.get("billing_day", 1), "billing_cycle": cycle,
                "renewal_date": args.get("renewal_date"), "wallet_id": wallet["id"], "active": 1,
            })
        return {
            "ok": True, "action": "add_subscription", "id": sid, "name": args["name"],
            "amount": args["amount"], "billing_cycle": cycle, "wallet": wallet["name"],
        }

    if name == "update_expense":
        eid = args["expense_id"]
        with get_db() as conn:
            current = conn.execute("SELECT * FROM expenses WHERE id=?", (eid,)).fetchone()
            if not current:
                return {"ok": False, "error": f"Expense {eid} not found"}
            cur = row_to_dict(current)
            changes = {
                "date": args.get("date", cur["date"]),
                "amount": args.get("amount", cur["amount"]),
                "description": args.get("description", cur["description"]),
                "type": args.get("type", cur["type"]),
            }
            update(conn, "expenses", eid, changes)
        return {"ok": True, "action": "update_expense", "id": eid,
                "amount": changes["amount"], "description": changes["description"]}

    if name == "update_subscription":
        sid = args["sub_id"]
        with get_db() as conn:
            current = conn.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone()
            if not current:
                return {"ok": False, "error": f"Subscription {sid} not found"}
            cur = row_to_dict(current)
            changes = {
                "name": args.get("name", cur["name"]),
                "amount": args.get("amount", cur["amount"]),
                "billing_day": args.get("billing_day", cur["billing_day"]),
                "billing_cycle": args.get("billing_cycle", cur.get("billing_cycle", "monthly")),
                "renewal_date": args.get("renewal_date", cur.get("renewal_date")),
                "active": 1 if args.get("active", cur["active"]) else 0,
            }
            update(conn, "subscriptions", sid, changes)
        return {"ok": True, "action": "update_subscription", "id": sid, "name": changes["name"],
                "active": bool(changes["active"]), "amount": changes["amount"]}

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


def _build_system_prompt(conn) -> str:
    month = datetime.now().strftime("%Y-%m")
    today = datetime.now().strftime("%Y-%m-%d")
    wallets = [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]
    expenses = [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM expenses WHERE date LIKE ?", (f"{month}%",)
    )]
    categories = [row_to_dict(r) for r in conn.execute("SELECT * FROM categories")]

    wallet_lines = [
        {"name": w["name"], "budget": w["budget"],
         "spent": sum(e["amount"] for e in expenses if e["wallet_id"] == w["id"])}
        for w in wallets
    ]
    cat_lines = [
        {"name": c["name"],
         "wallet": next((w["name"] for w in wallets if w["id"] == c["wallet_id"]), ""),
         "type": c["type"]}
        for c in categories
    ]

    return f"""You are a personal finance assistant for an expense tracking app.
Today: {today}. Current month: {month}.

Available wallets (use exact names for tool calls):
{json.dumps(wallet_lines, ensure_ascii=False)}

Available categories:
{json.dumps(cat_lines, ensure_ascii=False)}

Total spent this month: {sum(e['amount'] for e in expenses):,.0f} THB across {len(expenses)} transactions.

You can add/update expenses and subscriptions using the provided tools. When the user says they spent money, call add_expense. When they mention a subscription, call add_subscription. For updates, first call list_expenses or list_subscriptions to get the ID, then update.
Answer in the same language as the user. Use THB currency."""


@router.post("")
async def chat(msg: ChatMessage):
    with get_db() as conn:
        system_prompt = _build_system_prompt(conn)

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
                assistant_msg = resp.json()["message"]
                messages.append(assistant_msg)

                tool_calls = assistant_msg.get("tool_calls") or []
                if not tool_calls:
                    return {"reply": assistant_msg.get("content", ""), "actions": actions, "ok": True}

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = tc["function"]["arguments"]
                    if isinstance(fn_args, str):
                        fn_args = json.loads(fn_args)
                    result = _execute_tool(fn_name, fn_args)
                    actions.append(result)
                    messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})

            return {"reply": "Reached tool call limit.", "actions": actions, "ok": True}

        except httpx.ConnectError:
            return {"reply": "Ollama not reachable. Start with: docker compose --profile ai up", "actions": [], "ok": False}
        except Exception as e:
            return {"reply": f"AI error: {str(e)}", "actions": [], "ok": False}
