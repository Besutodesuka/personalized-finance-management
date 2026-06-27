"""DB connection, query helpers, schema init / migration / seed.

The insert()/update() helpers build column-named SQL from a dict so routes
never depend on column order or count — adding a column can't silently break
an INSERT (which is exactly how the subscriptions/master tables broke before).
Table and column names come from code only, never user input, so the f-string
interpolation here is safe; all values stay parameterized.
"""
import sqlite3
import uuid
from contextlib import contextmanager

from config import DB_PATH


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


def insert(conn, table: str, data: dict) -> dict:
    """INSERT a row from a dict. Returns the dict unchanged (incl. its id)."""
    cols = ", ".join(data)
    placeholders = ", ".join("?" for _ in data)
    conn.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
        tuple(data.values()),
    )
    return data


def update(conn, table: str, id_value: str, data: dict, id_col: str = "id"):
    """UPDATE a row by id from a dict. Returns the updated sqlite3.Row or None."""
    sets = ", ".join(f"{k}=?" for k in data)
    return conn.execute(
        f"UPDATE {table} SET {sets} WHERE {id_col}=? RETURNING *",
        (*data.values(), id_value),
    ).fetchone()


# --- Schema init / migration / seed ---

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
                billing_day INTEGER NOT NULL DEFAULT 1,
                billing_cycle TEXT NOT NULL DEFAULT 'monthly',
                renewal_date TEXT,
                wallet_id TEXT NOT NULL,
                active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS master_wallet (
                id INTEGER PRIMARY KEY,
                balance REAL NOT NULL DEFAULT 0
            );
        """)


def migrate_schema():
    """Add new columns / rows to existing DBs (idempotent)."""
    with get_db() as conn:
        sub_cols = [row[1] for row in conn.execute("PRAGMA table_info(subscriptions)")]
        if "billing_cycle" not in sub_cols:
            conn.execute("ALTER TABLE subscriptions ADD COLUMN billing_cycle TEXT NOT NULL DEFAULT 'monthly'")
        if "renewal_date" not in sub_cols:
            conn.execute("ALTER TABLE subscriptions ADD COLUMN renewal_date TEXT")
        if conn.execute("SELECT COUNT(*) FROM master_wallet").fetchone()[0] == 0:
            conn.execute("INSERT INTO master_wallet (id, balance) VALUES (1, 0)")


def migrate_json():
    """One-time legacy migration: JSON files → SQLite (only if wallets empty)."""
    import json
    from config import DATA_DIR

    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) FROM wallets").fetchone()[0] > 0:
            return

        def load_json(name):
            path = DATA_DIR / name
            return json.loads(path.read_text()) if path.exists() else []

        for w in load_json("wallets.json"):
            insert(conn, "wallets", {
                "id": w["id"], "name": w["name"], "budget": w["budget"],
                "color": w.get("color", "#6366f1"), "icon": w.get("icon", "💰"),
            })
        for c in load_json("categories.json"):
            insert(conn, "categories", {
                "id": c["id"], "name": c["name"],
                "wallet_id": c["wallet_id"], "type": c.get("type", "daily"),
            })
        for e in load_json("expenses.json"):
            insert(conn, "expenses", {
                "id": e["id"], "date": e["date"], "amount": e["amount"],
                "description": e["description"], "category_id": e["category_id"],
                "wallet_id": e["wallet_id"], "type": e.get("type", "planned"),
            })
        for s in load_json("subscriptions.json"):
            insert(conn, "subscriptions", {
                "id": s["id"], "name": s["name"], "amount": s["amount"],
                "billing_day": s.get("billing_day", 1),
                "billing_cycle": s.get("billing_cycle", "monthly"),
                "renewal_date": s.get("renewal_date"),
                "wallet_id": s["wallet_id"],
                "active": 1 if s.get("active", True) else 0,
            })


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
        defaults = [
            (wids["Basic Survival"], "Basic Survival", 10000, "#10b981", "🏠"),
            (wids["Travelling"], "Travelling", 5000, "#3b82f6", "✈️"),
            (wids["Relax"], "Relax", 3000, "#f59e0b", "☕"),
            (wids["Investment"], "Investment", 8000, "#8b5cf6", "📈"),
        ]
        for wid, name, budget, color, icon in defaults:
            insert(conn, "wallets", {
                "id": wid, "name": name, "budget": budget, "color": color, "icon": icon,
            })
        cats = [
            ("Groceries", wids["Basic Survival"], "daily"),
            ("Utilities", wids["Basic Survival"], "subscription"),
            ("Transport", wids["Basic Survival"], "daily"),
            ("Cafe", wids["Relax"], "daily"),
            ("Dining Out", wids["Relax"], "daily"),
            ("Entertainment", wids["Relax"], "daily"),
            ("Flight", wids["Travelling"], "unexpected"),
            ("Hotel", wids["Travelling"], "unexpected"),
            ("Stocks/ETF", wids["Investment"], "planned"),
        ]
        for name, wid, ctype in cats:
            insert(conn, "categories", {
                "id": new_id(), "name": name, "wallet_id": wid, "type": ctype,
            })
