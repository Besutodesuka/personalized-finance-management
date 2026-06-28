from __future__ import annotations

import json
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from config import CHAT_THINK, MODEL_NAME, VLLM_URL
from db import get_db, insert, new_id, row_to_dict, update
from models import ChatMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Compact prior conversation once it grows past this many estimated tokens.
CONTEXT_TOKEN_LIMIT = 8000
# After compaction, keep this many recent tokens verbatim; older turns get summarized.
RECENT_TOKEN_BUDGET = 4000


def _est_tokens(text: str) -> int:
    # ~4 chars/token heuristic; no tokenizer dependency needed.
    return max(1, len(text or "") // 4)


def _next_seq(conn) -> int:
    return conn.execute(
        "SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM chat_messages"
    ).fetchone()["n"]


def _save_message(conn, session_id: str, role: str, content: str,
                  actions: list | None = None) -> dict:
    row = {
        "id": new_id(),
        "session_id": session_id,
        "seq": _next_seq(conn),
        "role": role,
        "content": content,
        "actions": json.dumps(actions, ensure_ascii=False) if actions else None,
        "token_est": _est_tokens(content),
        "created_at": datetime.now().isoformat(),
    }
    insert(conn, "chat_messages", row)
    return row


def _load_messages(conn, session_id: str) -> list[dict]:
    return [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM chat_messages WHERE session_id=? ORDER BY seq ASC", (session_id,)
    )]


def _ensure_session(session_id: str | None) -> str:
    """Return a valid session id, creating a fresh session when none is given."""
    with get_db() as conn:
        if session_id:
            r = conn.execute("SELECT id FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
            if r:
                return session_id
        sid = new_id()
        now = datetime.now().isoformat()
        insert(conn, "chat_sessions", {
            "id": sid, "title": "New chat", "created_at": now, "updated_at": now,
        })
        return sid


def _touch_session(conn, session_id: str, first_user_msg: str | None = None) -> None:
    """Bump updated_at; title the session from its first user message."""
    now = datetime.now().isoformat()
    if first_user_msg:
        r = conn.execute("SELECT title FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
        if r and (r["title"] or "") in ("", "New chat"):
            title = " ".join(first_user_msg.split())[:48] or "New chat"
            conn.execute(
                "UPDATE chat_sessions SET title=?, updated_at=? WHERE id=?",
                (title, now, session_id),
            )
            return
    conn.execute("UPDATE chat_sessions SET updated_at=? WHERE id=?", (now, session_id))


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
    {
        "type": "function",
        "function": {
            "name": "set_wallet_budget",
            "description": "Set the monthly budget limit of a single wallet to an exact amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "wallet_name": {"type": "string", "description": "Wallet name (e.g. 'Basic Survival')"},
                    "budget": {"type": "number", "description": "New monthly budget in THB"},
                },
                "required": ["wallet_name", "budget"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_total_budget",
            "description": (
                "Set the TOTAL monthly budget across all wallets to an exact amount. "
                "Use when the user gives one overall number (e.g. 'set my budget to 36000'). "
                "Scales each wallet proportionally to its current share. Budgets are the ongoing "
                "monthly allocation — there is no separate per-month budget."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "total": {"type": "number", "description": "Target total monthly budget in THB"},
                },
                "required": ["total"],
            },
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

    if name == "set_wallet_budget":
        wallet_name = args.get("wallet_name", "")
        new_budget = args["budget"]
        with get_db() as conn:
            wallet = _find_wallet(conn, wallet_name)
            if not wallet:
                return {"ok": False, "error": f"Wallet '{wallet_name}' not found"}
            update(conn, "wallets", wallet["id"], {"budget": new_budget})
        return {"ok": True, "action": "set_wallet_budget", "wallet": wallet["name"],
                "old_budget": wallet["budget"], "budget": new_budget}

    if name == "set_total_budget":
        target = args["total"]
        if target < 0:
            return {"ok": False, "error": "Total budget must be >= 0"}
        with get_db() as conn:
            wallets = [row_to_dict(r) for r in conn.execute("SELECT * FROM wallets")]
            if not wallets:
                return {"ok": False, "error": "No wallets to budget"}
            current_total = sum(w["budget"] for w in wallets)
            # Scale by current share; split evenly if there's nothing to scale from.
            allocations: list[float] = []
            for w in wallets:
                share = (w["budget"] / current_total) if current_total > 0 else (1 / len(wallets))
                allocations.append(round(target * share))
            # Push rounding drift onto the last wallet so the parts sum exactly to target.
            allocations[-1] += round(target) - sum(allocations)
            distributions = []
            for w, amt in zip(wallets, allocations):
                update(conn, "wallets", w["id"], {"budget": amt})
                distributions.append({"wallet": w["name"], "old_budget": w["budget"], "budget": amt})
        return {"ok": True, "action": "set_total_budget", "old_total": current_total,
                "total": round(target), "distributions": distributions}

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

Total monthly budget (sum of wallet budgets): {sum(w['budget'] for w in wallet_lines):,.0f} THB.

You can add/update expenses and subscriptions using the provided tools. When the user says they spent money, call add_expense. When they mention a subscription, call add_subscription. For updates, first call list_expenses or list_subscriptions to get the ID, then update.
To change a single wallet's limit, call set_wallet_budget. When the user gives one overall budget number (e.g. "set my budget to 36000"), call set_total_budget. Budgets are the ongoing monthly allocation — there is no separate per-month budget, so a request like "next month's budget" updates the same monthly budget.
Answer in the same language as the user. Use THB currency."""


async def _summarize(client: httpx.AsyncClient, rows: list[dict]) -> str:
    """Condense old turns into one paragraph of durable context."""
    transcript = "\n".join(f"{r['role']}: {r['content']}" for r in rows)
    resp = await client.post(
        f"{VLLM_URL}/api/chat",
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": (
                    "Summarize this personal-finance assistant conversation concisely. "
                    "Preserve concrete facts: amounts, wallet/category names, dates, IDs, "
                    "decisions made, and any unresolved request. Output a compact paragraph."
                )},
                {"role": "user", "content": transcript},
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 512},
        },
    )
    resp.raise_for_status()
    return resp.json()["message"].get("content", "").strip()


async def _compact_if_needed(conn, client: httpx.AsyncClient, session_id: str) -> None:
    """When stored history exceeds the token limit, fold older turns into a rolling
    summary row, deleting the originals. Idempotent and safe to call every turn."""
    rows = _load_messages(conn, session_id)
    if sum(r["token_est"] for r in rows) <= CONTEXT_TOKEN_LIMIT:
        return

    # Keep the newest turns (>= last 2) within RECENT_TOKEN_BUDGET; summarize the rest.
    recent: list[dict] = []
    acc = 0
    for r in reversed(rows):
        if acc + r["token_est"] > RECENT_TOKEN_BUDGET and len(recent) >= 2:
            break
        recent.append(r)
        acc += r["token_est"]
    old = rows[: len(rows) - len(recent)]
    if not old:
        return

    summary = await _summarize(client, old)
    if not summary:
        return

    ids = ",".join("?" for _ in old)
    conn.execute(f"DELETE FROM chat_messages WHERE id IN ({ids})", tuple(r["id"] for r in old))
    # Re-insert summary at the front (lowest seq) so it leads the rebuilt context.
    min_seq = min(r["seq"] for r in old)
    insert(conn, "chat_messages", {
        "id": new_id(),
        "session_id": session_id,
        "seq": min_seq,
        "role": "system",
        "content": f"[Summary of earlier conversation]\n{summary}",
        "actions": None,
        "token_est": _est_tokens(summary),
        "created_at": old[0]["created_at"],
    })


def _to_model_messages(system_prompt: str, rows: list[dict]) -> list[dict]:
    out = [{"role": "system", "content": system_prompt}]
    for r in rows:
        out.append({"role": r["role"], "content": r["content"]})
    return out


# --- Session management ---

@router.get("/sessions")
def list_sessions():
    """All conversations, newest first, for the history sidebar."""
    with get_db() as conn:
        rows = [row_to_dict(r) for r in conn.execute(
            "SELECT s.id, s.title, s.created_at, s.updated_at, "
            "COUNT(CASE WHEN m.role IN ('user','assistant') THEN 1 END) AS message_count "
            "FROM chat_sessions s LEFT JOIN chat_messages m ON m.session_id = s.id "
            "GROUP BY s.id ORDER BY s.updated_at DESC"
        )]
    return {"sessions": rows}


@router.post("/sessions")
def create_session():
    sid = _ensure_session(None)
    with get_db() as conn:
        s = row_to_dict(conn.execute("SELECT * FROM chat_sessions WHERE id=?", (sid,)).fetchone())
    return s


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    """Stored conversation for display (user/assistant turns only)."""
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM chat_sessions WHERE id=?", (session_id,)).fetchone():
            raise HTTPException(404, "Session not found")
        rows = _load_messages(conn, session_id)
    return {"messages": [
        {
            "role": r["role"],
            "content": r["content"],
            "actions": json.loads(r["actions"]) if r["actions"] else [],
        }
        for r in rows if r["role"] in ("user", "assistant")
    ]}


# --- Turn execution ---

def _parse_tool_args(tc: dict) -> dict:
    fn_args = tc["function"]["arguments"]
    return json.loads(fn_args) if isinstance(fn_args, str) else fn_args


async def _run_turn(client: httpx.AsyncClient, session_id: str, user_message: str):
    """Save the user turn, run the tool-calling loop with token streaming, and
    persist the assistant reply. Yields SSE events for the UI to render live."""
    with get_db() as conn:
        _save_message(conn, session_id, "user", user_message)
        _touch_session(conn, session_id, first_user_msg=user_message)
    with get_db() as conn:
        await _compact_if_needed(conn, client, session_id)
    with get_db() as conn:
        system_prompt = _build_system_prompt(conn)
        messages = _to_model_messages(system_prompt, _load_messages(conn, session_id))

    actions: list[dict] = []
    final_reply = "Reached tool call limit."
    think = CHAT_THINK

    for _ in range(6):  # max tool-call rounds
        content_parts: list[str] = []
        tool_calls: list[dict] = []
        produced = False  # have we emitted any token this round yet?

        while True:  # retries once without `think` if the model rejects it
            payload = {
                "model": MODEL_NAME,
                "messages": messages,
                "tools": CHAT_TOOLS,
                "stream": True,
                "options": {"temperature": 0.7, "num_predict": 1024},
            }
            if think:
                payload["think"] = True
            try:
                async with client.stream("POST", f"{VLLM_URL}/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        m = chunk.get("message", {})
                        if m.get("thinking"):
                            produced = True
                            yield {"type": "thinking", "delta": m["thinking"]}
                        if m.get("content"):
                            produced = True
                            content_parts.append(m["content"])
                            yield {"type": "content", "delta": m["content"]}
                        if m.get("tool_calls"):
                            tool_calls.extend(m["tool_calls"])
                        if chunk.get("done"):
                            break
                break
            except httpx.HTTPStatusError:
                # Model likely doesn't support `think`: drop it and retry the round
                # (safe only because nothing has streamed yet).
                if think and not produced:
                    think = False
                    content_parts, tool_calls = [], []
                    continue
                raise

        content = "".join(content_parts)
        assistant_msg = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            final_reply = content
            break

        for tc in tool_calls:
            result = _execute_tool(tc["function"]["name"], _parse_tool_args(tc))
            actions.append(result)
            yield {"type": "action", "data": result}
            messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})

    with get_db() as conn:
        _save_message(conn, session_id, "assistant", final_reply, actions)
        _touch_session(conn, session_id)
    yield {"type": "done", "reply": final_reply, "actions": actions, "session_id": session_id}


@router.post("/stream")
async def chat_stream(msg: ChatMessage):
    """Streaming chat — emits thinking/content deltas, tool actions, then done."""
    session_id = _ensure_session(msg.session_id)

    async def gen():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        client = httpx.AsyncClient(timeout=120.0)
        try:
            async for event in _run_turn(client, session_id, msg.message):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except httpx.ConnectError:
            err = {"type": "error", "message": "Ollama not reachable. Start with: docker compose --profile ai up"}
            yield f"data: {json.dumps(err)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'AI error: {e}'})}\n\n"
        finally:
            await client.aclose()

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # disable proxy buffering so deltas flush live
    })


@router.post("")
async def chat(msg: ChatMessage):
    """Non-streaming fallback — drains the streamed turn into a single response."""
    session_id = _ensure_session(msg.session_id)
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            reply, actions = "", []
            async for event in _run_turn(client, session_id, msg.message):
                if event["type"] == "done":
                    reply, actions = event["reply"], event["actions"]
            return {"reply": reply, "actions": actions, "session_id": session_id, "ok": True}
        except httpx.ConnectError:
            return {"reply": "Ollama not reachable. Start with: docker compose --profile ai up",
                    "actions": [], "session_id": session_id, "ok": False}
        except Exception as e:
            return {"reply": f"AI error: {str(e)}", "actions": [], "session_id": session_id, "ok": False}
