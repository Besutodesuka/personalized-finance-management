# 💸 Expense Tracker

A **self-hosted, privacy-first personal finance app** built around *envelope budgeting* with a
**local AI assistant**. You log spending into themed wallets, the dashboard shows where the money
goes, and a chat assistant (running entirely on your own machine via [Ollama](https://ollama.com))
can add expenses, manage subscriptions, and adjust budgets in plain language.

Your data lives in a local SQLite file. Nothing is sent to any cloud — including the AI.

Currency: **THB (฿)**.

---

## ✨ Features

| Area | What you get |
|------|--------------|
| **Wallets** | Envelope-style budgets (e.g. *Basic Survival, Travelling, Relax, Investment*), each with a monthly budget, color & icon |
| **Master Wallet** | A central balance you top up, then **refill** all wallet budgets from in one click |
| **Expenses** | Log `planned` / `unexpected` spending, filter by month & wallet |
| **Subscriptions** | Recurring `monthly` / `yearly` bills with billing day / renewal date |
| **Categories** | Typed (`daily` / `subscription` / `unexpected`) and tied to a wallet |
| **Dashboard** | Budget vs spent, daily average, per-wallet breakdown, today's spend, recent activity, daily chart |
| **AI Chat** | Local LLM with **tool-calling** — "I spent ฿250 on lunch" → expense added. Streaming replies + reasoning, multi-session history, auto context compaction |
| **Export** | One-click CSV (expenses) and JSON (full data) |

> Looking for what's *next*? See the **[Feature Roadmap & Backlog → FEATURES.md](./FEATURES.md)**
> (insurance vault, Thai tax optimizer, multi-currency trips, portfolio tracking, and more).

---

## 🧱 Tech Stack

| Layer | Tech |
|-------|------|
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS 3, Chart.js |
| **Backend** | FastAPI, Pydantic v2, Uvicorn, httpx |
| **Database** | SQLite (WAL mode) — zero-config, file-based |
| **AI** | Ollama (default model `qwen2.5:3b`), OpenAI-style tool calling, SSE streaming |
| **Orchestration** | Docker Compose |

---

## 🗺️ Architecture

```
┌──────────────┐  HTTP   ┌──────────────┐  HTTP   ┌──────────────┐
│   Frontend   │────────▶│   Backend    │────────▶│    Ollama    │
│  Next.js 15  │  + SSE  │   FastAPI    │         │  local LLM   │
│    :3000     │◀────────│    :8000     │◀────────│   :11434     │
└──────────────┘         └──────┬───────┘         └──────────────┘
                                │
                          ┌─────▼──────┐
                          │   SQLite   │
                          │ data/*.db  │
                          └────────────┘
```

The backend is **assembly-only** in `main.py`; all logic lives in `routers/` and `db.py`.
DB helpers build column-named SQL from dicts, so adding a column can't silently break an INSERT.
Startup runs four **idempotent** steps: `init_db → migrate_schema → migrate_json → seed_defaults`.

---

## 📁 Project Structure

```
expense/
├── docker-compose.yml        # backend + frontend + ollama (ai profile)
├── .env.example              # copy to .env and edit
├── fix_manual.md             # operational fixes (Ollama pulls, Docker networking)
├── FEATURES.md               # roadmap & nice-to-have backlog
├── data/                     # SQLite db (gitignored) — your data lives here
├── backend/
│   ├── main.py               # app assembly + CORS + startup + /api/health
│   ├── config.py             # env vars & paths
│   ├── db.py                 # connection, query helpers, schema/migration/seed
│   ├── models.py             # Pydantic request/response schemas
│   ├── routers/              # wallets, categories, expenses, subscriptions,
│   │                         #   master_wallet, dashboard, chat, export
│   └── tests/                # pytest suite
└── frontend/
    └── src/
        ├── app/              # pages: dashboard, expenses, wallets,
        │                     #   subscriptions, categories, chat
        ├── components/       # Sidebar, Modal, WalletTag
        └── lib/              # api client, types, utils
```

---

## 🚀 Quick Start (Docker — recommended)

**Prerequisites:** Docker + Docker Compose.

```bash
cd expense
cp .env.example .env        # adjust if you like (model, ports)
```

**Without AI** (tracker only — chat will show a friendly "Ollama not reachable" message):

```bash
docker compose up -d
```

**With AI** (also starts Ollama and auto-pulls the model on first run):

```bash
docker compose --profile ai up -d
```

Then open:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/health |

> First AI start downloads the model (~2 GB for the default `qwen2.5:3b`) — give it a minute.

---

## 🛠️ Local Development

### Backend

```bash
cd backend
pip install -r requirements-dev.txt        # app deps + pytest
DATA_DIR=./data uvicorn main:app --reload --port 8000
```

> `DATA_DIR=./data` is required locally — the default (`/app/data`) is the Docker path and isn't
> writable on your host. For AI chat, run Ollama natively and set
> `VLLM_URL=http://localhost:11434`.

### Frontend

```bash
cd frontend
npm install
npm run dev                                 # http://localhost:3000
```

> The frontend talks to `http://localhost:8000/api` by default. Override with
> `NEXT_PUBLIC_API_URL` if your backend runs elsewhere.

---

## ⚙️ Configuration

Set via `.env` (Docker) or your shell (local). All are optional with sane defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `qwen2.5:3b` | Ollama model for chat (must support tool calling) |
| `CHAT_THINK` | `true` | Stream the model's reasoning to the UI (thinking-capable models only) |
| `VLLM_URL` | `http://ollama:11434` | Ollama endpoint (use `http://host.docker.internal:11434` for native Ollama) |
| `DATA_DIR` | `/app/data` | Where the SQLite file lives (set `./data` for local dev) |
| `OLLAMA_MODELS_DIR` | `~/.ollama` | Host dir for Ollama model storage |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | Frontend → backend base URL |

**CPU-friendly model options** (all support tool calling):
`qwen2.5:3b` (2 GB, fastest) · `llama3.2:3b` (2 GB) · `qwen2.5:7b` (5 GB, higher quality).

---

## 🗃️ Data Model

| Table | Purpose |
|-------|---------|
| `wallets` | Budget envelopes — `name, budget, color, icon` |
| `categories` | `name, wallet_id, type` (`daily` / `subscription` / `unexpected`) |
| `expenses` | `date, amount, description, category_id, wallet_id, type` (`planned` / `unexpected`) |
| `subscriptions` | `name, amount, billing_day, billing_cycle, renewal_date, wallet_id, active` |
| `master_wallet` | Single-row central balance used to refill wallets |
| `chat_sessions` | Conversation list for the AI history sidebar |
| `chat_messages` | Per-session turns + tool actions, with token estimates for compaction |

---

## 🔌 API Reference

Base path: `/api`. Full interactive docs at `/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Status + active model |
| `GET/POST` | `/wallets` · `PUT/DELETE /wallets/{id}` | Manage wallets |
| `GET/POST` | `/categories` · `PUT/DELETE /categories/{id}` | Manage categories |
| `GET` | `/expenses?month=YYYY-MM&wallet_id=` | List expenses (filterable) |
| `POST` | `/expenses` · `PUT/DELETE /expenses/{id}` | Manage expenses |
| `GET/POST` | `/subscriptions` · `PUT/DELETE /subscriptions/{id}` | Manage subscriptions |
| `GET` | `/master-wallet` | Current central balance |
| `POST` | `/master-wallet/adjust` | Add / subtract balance |
| `POST` | `/master-wallet/refill` | Deduct total budgets, refill all wallets |
| `GET` | `/dashboard?month=YYYY-MM` | Aggregated monthly stats + chart data |
| `GET` | `/export/expenses.csv` · `/export/data.json` | Export |
| `POST` | `/chat` · `/chat/stream` | Chat (JSON / SSE streaming) |
| `GET/POST` | `/chat/sessions` · `DELETE /chat/sessions/{id}` | Conversation management |
| `GET` | `/chat/sessions/{id}/messages` | Load a conversation |

---

## 🤖 AI Assistant

The chat runs against a **local** Ollama model with tool calling. It sees your current wallets,
categories and month-to-date spend as context, then can act on these tools:

| Tool | Does |
|------|------|
| `add_expense` | Log spending ("spent ฿250 on lunch") |
| `add_subscription` | Add a recurring bill |
| `update_expense` / `update_subscription` | Edit or pause/resume existing items |
| `list_expenses` / `list_subscriptions` | Look up items & IDs |
| `set_wallet_budget` | Set one wallet's monthly limit |
| `set_total_budget` | Set overall budget; splits across wallets proportionally |

**Notable behavior**

- **Streaming** — reply tokens *and* model reasoning stream live over SSE.
- **Multi-session** — conversations are titled from the first message and listed in a sidebar.
- **Context compaction** — once history passes a token threshold, older turns are folded into a
  rolling summary so long chats stay cheap and in-context.
- **Graceful degradation** — if the model rejects the `think` flag, the turn retries without it;
  if Ollama is down, you get a clear hint instead of a crash.

Answers follow the user's language and use THB.

---

## 🌱 Default Seed Data

On first run (empty DB), the app seeds four wallets so you start with something usable:

| Wallet | Budget | Icon |
|--------|--------|------|
| 🏠 Basic Survival | ฿10,000 | groceries, utilities, transport |
| ✈️ Travelling | ฿5,000 | flights, hotels |
| ☕ Relax | ฿3,000 | cafe, dining, entertainment |
| 📈 Investment | ฿8,000 | stocks / ETF |

---

## 🧪 Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Each test runs against a fresh, isolated, seeded SQLite DB (see `tests/conftest.py`).

---

## 💾 Data & Backups

- All data is a single SQLite file at `data/expense.db` (plus WAL/SHM files), mounted into the
  backend container via the `./data` volume.
- **Back up** by copying the `data/` directory, or use `GET /api/export/data.json` for a portable
  snapshot.
- `data/*.db` is gitignored — your finances never get committed.

---

## 🩺 Troubleshooting

See **[fix_manual.md](./fix_manual.md)** for known operational fixes, including:

- Pulling a custom GGUF model into Ollama.
- Resolving Docker `network ... not found` errors (`docker compose down --remove-orphans && up`).

Quick checks:

```bash
docker compose ps                 # backend + frontend should be Up
curl localhost:8000/api/health    # {"status":"ok", ...}
docker compose logs -f backend    # tail backend logs
```

---

## 🛣️ Roadmap

Planned and proposed features — insurance vault, Thai tax optimizer, multi-currency trip budgets,
investment/DCA tracking, credit-card rewards optimizer, and proactive LINE/Telegram alerts — are
documented in **[FEATURES.md](./FEATURES.md)**.
