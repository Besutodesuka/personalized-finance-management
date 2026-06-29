# 🛣️ Feature Roadmap & Nice-to-Have Backlog

Planned and proposed features for the [Expense Tracker](./README.md).

**Who this is built for:** a 🇹🇭 **Thai citizen** and **software engineer** who **travels**, loves to
**eat**, plays **sport** / does **activities**, moves around on **transport**, and wants to
**maximize financial gain** — squeeze tax back, dodge waste, and grow the *Investment* wallet.

**Design principles**

1. **Reuse what exists.** Every feature below builds on the current primitives — `wallets`,
   `subscriptions`, `categories`, the `dashboard` aggregator, and the AI `CHAT_TOOLS` pattern — so
   most are *additive*, not rewrites.
2. **Privacy-first.** Stays self-hosted. External calls (FX, stock prices, OCR) are opt-in, cached,
   and degrade gracefully when offline — exactly like the current Ollama integration.
3. **Thai-first.** THB native; tax, banks, and rewards modeled for Thailand.
4. **AI-native.** If a human can do it in the UI, the assistant should have a tool for it too.

> ⚠️ **Thai tax/insurance figures below are illustrative.** Limits change yearly (Revenue
> Department announcements). Every number must be a configurable, year-versioned setting — never
> hard-coded — and verified against the current tax year before relying on it.

---

## 🎯 Priority — the features that actually move the needle

Ranked by real-life impact **for this user**. Effort: **S** ≈ days · **M** ≈ 1–2 weeks · **L** ≈ multi-week.

| # | Feature | Why it matters to *you* | Impact | Effort | Tier |
|---|---------|-------------------------|:------:|:------:|:----:|
| 1 | **Insurance & Protection Vault** | One bad accident/illness wipes out years of saving. Premiums are also tax-deductible. | 🔥🔥🔥🔥🔥 | M | 1 |
| 2 | **Thai Tax Optimizer & Deduction Tracker** | Biggest guaranteed THB win — legally claw back 10–35% via RMF/SSF/ThaiESG/insurance. | 🔥🔥🔥🔥🔥 | L | 1 |
| 3 | **Investment & DCA Tracker** | "Maximize gain" — make the *Investment* wallet real (cost basis, P/L, rebalance). | 🔥🔥🔥🔥🔥 | L | 1 |
| 4 | **Multi-Currency & Per-Trip Budgets** | You travel — log in any currency, settle a whole trip in THB. | 🔥🔥🔥🔥 | M | 1 |
| 5 | **Credit-Card Rewards Optimizer** | Free money on spend you *already* do (dining, transport, travel, online). | 🔥🔥🔥🔥 | M | 1 |
| 6 | **Proactive Alerts (LINE / Telegram)** | Engineer automation — the app warns *you* before you overspend or a bill renews. | 🔥🔥🔥🔥 | M | 1 |
| 7 | **Membership & Gear Cost-Per-Use** | Sport/activity ROI — is the ฿1,590/mo gym worth it this month? | 🔥🔥🔥 | S | 1 |

That's **7 high-impact features** (the brief asked for ≥5). Tier 2 and Tier 3 below round out the
"exhaustive" wishlist.

---

# 🥇 Tier 1 — High-impact (build these first)

---

## 1. 🛡️ Insurance & Protection Vault

**Why it matters to you.** You travel, play sport, and ride Thai roads — the highest-variance risks
in your life aren't your daily lattes, they're the events insurance exists for. This is also the
*only* expense category that pays you back at tax time (life + health premiums are deductible).
Today the app tracks where money *goes*; this tracks what protects you when it goes *wrong*.

**What it does**

- A vault of policies: **health, life, accident (PA), travel, auto/motorbike, mobile/gadget, condo/home**.
- Per policy: insurer, policy no., **premium + cycle**, **coverage / sum insured**, **renewal date**,
  beneficiary, deductible, and attached **documents** (PDF/photo).
- Premiums auto-create a linked **subscription** (reuses the existing engine) → they show up in the
  dashboard and budget like any recurring bill.
- **Renewal reminders** (30/7/1 days out) via the alerts feature (#6).
- **Coverage-gap nudges:** "You travel often but have no travel/PA policy," or "Health cover ฿X is
  below your annual medical spend trend."
- **Tax flag:** marks life/health premiums as deductible and feeds the Tax Optimizer (#2).

**Data model** (new)

```sql
CREATE TABLE insurance_policies (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,            -- health | life | accident | travel | auto | gadget | home
  insurer TEXT NOT NULL,
  policy_number TEXT,
  premium REAL NOT NULL,
  billing_cycle TEXT DEFAULT 'yearly',
  renewal_date TEXT,            -- YYYY-MM-DD
  coverage_amount REAL,
  beneficiary TEXT,
  tax_deductible INTEGER DEFAULT 0,
  subscription_id TEXT,         -- link to auto-created subscription
  document_path TEXT,           -- stored file (see Cross-cutting: file storage)
  notes TEXT,
  active INTEGER DEFAULT 1
);
CREATE TABLE insurance_claims (
  id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL,
  date TEXT NOT NULL,
  amount_claimed REAL,
  amount_paid REAL,
  status TEXT DEFAULT 'submitted',  -- submitted | approved | paid | rejected
  notes TEXT
);
```

**API:** `GET/POST /api/insurance` · `PUT/DELETE /api/insurance/{id}` · `GET/POST /api/insurance/{id}/claims`.

**AI tools:** `add_insurance_policy`, `list_insurance`, `log_insurance_claim`, `next_renewals`.

**UI:** new **🛡️ Insurance** sidebar page — card grid by type, renewal timeline, coverage-vs-spend chart.

**Dependencies:** file storage (Cross-cutting), alerts (#6). **Integrates with:** subscriptions, tax (#2).

---

## 2. 🇹🇭 Thai Tax Optimizer & Deduction Tracker

**Why it matters to you.** This is the single highest-ROI feature. As a salaried engineer you're
likely in the **15–25%+ marginal** bracket. Every ฿1 you route into **RMF / SSF / ThaiESG** or
deductible **insurance** before year-end is ฿0.15–0.35 back. The app already knows your income
(refills) and spending — it can tell you the *exact* top-up to minimize tax.

**What it does**

- **Year dashboard:** estimated taxable income → progressive PIT (0–35%) → tax due, updated as you log.
- **Deduction tracker** with live caps and progress bars (all year-versioned settings):
  - Personal / spouse / child / parent allowances, SSO contributions.
  - **Retirement bucket:** SSF, RMF, **ThaiESG** — with the combined retirement ceiling.
  - **Insurance:** life + health (self), health (parents) — auto-pulled from the Insurance Vault (#1).
  - **Stimulus:** *Easy E-Receipt* / shop-stimulus spend, captured from tagged expenses.
  - Donations (incl. 2× categories), mortgage interest.
- **Optimizer:** "Invest **฿X more in SSF/ThaiESG** before Dec 31 to drop a bracket and save **฿Y**."
- **Filing pack export:** a tidy PDF/CSV of deductions for PND.90/91 season.

**Data model**

```sql
CREATE TABLE tax_profile (
  year INTEGER PRIMARY KEY,
  annual_income REAL,
  marital_status TEXT,
  children INTEGER DEFAULT 0,
  parents_supported INTEGER DEFAULT 0,
  sso_paid REAL DEFAULT 0
);
CREATE TABLE tax_deductions (
  id TEXT PRIMARY KEY,
  year INTEGER NOT NULL,
  category TEXT NOT NULL,   -- ssf | rmf | thaiesg | life_ins | health_ins | donation | e_receipt ...
  amount REAL NOT NULL,
  source TEXT,              -- manual | insurance_policy:<id> | expense:<id> | investment:<id>
  date TEXT
);
-- Brackets, allowances & caps live in a versioned config table, NOT in code:
CREATE TABLE tax_rules (year INTEGER, key TEXT, value REAL, PRIMARY KEY (year, key));
```

**API:** `GET /api/tax/{year}/summary` · `GET /api/tax/{year}/optimize` · `GET/POST /api/tax/{year}/deductions` · `GET /api/tax/{year}/export`.

**AI tools:** `tax_summary`, `tax_optimize` ("how do I pay less tax?"), `add_deduction`.

**UI:** **🇹🇭 Tax** page — bracket bar, deduction progress rings, the optimizer call-to-action.

**Dependencies:** Insurance (#1) and Investment (#3) for auto-sourced deductions. **Effort: L** (tax logic + verification).

---

## 3. 📈 Investment & DCA Tracker

**Why it matters to you.** The *Investment* wallet exists but is just a budget bucket. You already
run a real DCA thesis (see `../portfolio.md` — NVDA, IRBO, ICLN, XBI…). This turns intent into a
tracked portfolio: cost basis, live value, P/L, dividends, and **rebalance alerts** against your
target weights — the core of "maximize gain."

**What it does**

- **Holdings** per ticker: units, average cost, current price (opt-in price API, cached), unrealized P/L.
- **DCA schedules:** recurring buys (reuses subscription cadence) with reminders; logs the buy as a transaction.
- **Target allocation** (from `portfolio.md`) vs **actual** → drift % → "**Rebalance: trim NVDA 3%,
  add ICLN 2%**."
- **Dividend log** + simple yield-on-cost.
- **Net worth roll-up:** investments + cash wallets − liabilities, charted over time.
- **Thai tax bridge:** RMF/SSF/ThaiESG holdings feed the Tax Optimizer (#2) deduction totals.

**Data model**

```sql
CREATE TABLE holdings (
  id TEXT PRIMARY KEY, ticker TEXT, name TEXT, asset_class TEXT,   -- stock | etf | rmf | ssf | thaiesg | crypto
  units REAL DEFAULT 0, avg_cost REAL DEFAULT 0, currency TEXT DEFAULT 'USD',
  target_pct REAL, tax_vehicle TEXT                                 -- null | rmf | ssf | thaiesg
);
CREATE TABLE trades (
  id TEXT PRIMARY KEY, holding_id TEXT, date TEXT, side TEXT,        -- buy | sell | dividend
  units REAL, price REAL, fee REAL DEFAULT 0
);
CREATE TABLE price_cache (ticker TEXT PRIMARY KEY, price REAL, currency TEXT, fetched_at TEXT);
```

**API:** `GET/POST /api/portfolio/holdings` · `POST /api/portfolio/trades` · `GET /api/portfolio/summary` · `GET /api/portfolio/rebalance` · `GET /api/networth`.

**AI tools:** `add_trade`, `portfolio_summary`, `rebalance_check`, `set_target_allocation`.

**UI:** **📈 Portfolio** page — allocation donut (target vs actual), holdings table w/ P/L, net-worth line chart.

**Dependencies:** price fetcher + FX (Cross-cutting). **Integrates with:** Investment wallet, Tax (#2), DCA reminders (#6).

---

## 4. 🌍 Multi-Currency & Per-Trip Budgets

**Why it matters to you.** You travel. Right now a ¥12,000 dinner in Tokyo and a ฿250 lunch in
Bangkok are logged the same way — no FX, no trip view. This adds foreign-currency entry and a
**trip wallet** so you can budget, track daily burn, and settle a whole trip back to THB.

**What it does**

- Log an expense in **any currency**; auto-convert to THB at the day's rate (cached FX, manual override).
- A **Trip** = a temporary wallet with start/end dates, a budget, and a home base.
  - Daily burn rate, "days of runway left," and a per-trip category breakdown.
  - End-of-trip **settlement**: total THB, FX gain/loss, over/under budget.
- Pairs with **travel insurance** (#1) and **card-per-country** suggestions (#5, avoid FX fees).

**Data model**

```sql
ALTER TABLE expenses ADD COLUMN currency TEXT DEFAULT 'THB';
ALTER TABLE expenses ADD COLUMN fx_rate REAL DEFAULT 1;      -- to THB at time of entry
ALTER TABLE expenses ADD COLUMN trip_id TEXT;
CREATE TABLE trips (
  id TEXT PRIMARY KEY, name TEXT, destination TEXT,
  start_date TEXT, end_date TEXT, budget REAL, home_currency TEXT DEFAULT 'THB'
);
CREATE TABLE fx_rates (date TEXT, base TEXT, quote TEXT, rate REAL, PRIMARY KEY (date, base, quote));
```

**API:** `GET/POST /api/trips` · `GET /api/trips/{id}/summary` · `GET /api/fx?from=JPY&to=THB&date=`.

**AI tools:** `start_trip`, `add_expense` extended with `currency`, `trip_summary`.

**UI:** **✈️ Trips** page — active-trip banner with burn gauge; currency selector in the expense modal.

**Dependencies:** FX fetcher (Cross-cutting). **Effort: M.**

---

## 5. 💳 Credit-Card Rewards Optimizer

**Why it matters to you.** Dining, transport, travel, and online shopping are your bread and butter
— exactly the categories Thai cards reward most. The app already classifies every expense by
category, so it can tell you **which card to swipe** and how much cashback you're leaving on the table.

**What it does**

- Register cards: network, **annual fee**, statement/due day, and **reward rules** (category →
  cashback % or points, with monthly caps).
- On expense entry (or via chat): **"Use Card X — 5% dining cashback"**.
- Monthly **"missed rewards"** report: what optimal-card routing would have earned vs what you did.
- **Annual-fee break-even** tracker; **points/miles balance** with expiry; **statement due-date** reminders (#6).
- Pairs with Trips (#4): flags the best **no-FX-fee** card abroad.

**Data model**

```sql
CREATE TABLE cards (
  id TEXT PRIMARY KEY, name TEXT, network TEXT, annual_fee REAL DEFAULT 0,
  statement_day INTEGER, due_day INTEGER, points_balance REAL DEFAULT 0, active INTEGER DEFAULT 1
);
CREATE TABLE card_rewards (
  id TEXT PRIMARY KEY, card_id TEXT, category TEXT,
  rate REAL,                 -- 0.05 = 5% cashback, or points-per-THB
  reward_type TEXT,          -- cashback | points | miles
  monthly_cap REAL
);
ALTER TABLE expenses ADD COLUMN card_id TEXT;
```

**API:** `GET/POST /api/cards` · `GET /api/cards/best?category=&amount=` · `GET /api/cards/rewards-report?month=`.

**AI tools:** `best_card` ("which card for ฿2,000 dining?"), `add_card`, `rewards_report`.

**UI:** **💳 Cards** page — card wallet, "best card" hint in the expense modal, monthly missed-rewards banner.

**Effort: M.** **Integrates with:** expenses, trips (#4), alerts (#6).

---

## 6. 🔔 Proactive Alerts (LINE / Telegram)

**Why it matters to you.** You're an engineer — you want the system to *push*, not for you to *pull*.
A passive tracker is forgotten by week two. Push the right nudge to your phone and it stays useful:
budget breaches, bill/insurance renewals, subscription price hikes, DCA buy days, card due dates.

**What it does**

- A small **scheduler** (cron-style job) evaluates rules daily and on threshold crossings.
- **Channels:** **Telegram bot** (trivial to self-host) or **LINE Messaging API** push.
  > ⚠️ **LINE Notify was discontinued (Mar 2025)** — do **not** build on it. Use a LINE **Messaging
  > API** bot or, simplest, a **Telegram** bot.
- **Two-way (optional):** reply *"spent 250 lunch"* in Telegram → it calls the same chat tools to log it.
- Rule types: budget % thresholds, daily-spend spikes, upcoming renewals (#1), due dates (#5),
  DCA reminders (#3), end-of-month "you'll overspend by ฿X" forecast.

**Data model**

```sql
CREATE TABLE notification_channels (id TEXT PRIMARY KEY, kind TEXT, token TEXT, chat_id TEXT, active INTEGER DEFAULT 1);
CREATE TABLE alert_rules (id TEXT PRIMARY KEY, type TEXT, threshold REAL, channel_id TEXT, active INTEGER DEFAULT 1);
CREATE TABLE alert_log (id TEXT PRIMARY KEY, rule_id TEXT, sent_at TEXT, message TEXT);
```

**API:** `GET/POST /api/alerts/rules` · `POST /api/alerts/test` · `POST /api/alerts/channels`.

**Infra:** background scheduler (APScheduler in-process, or a `cron` compose service hitting an internal endpoint).

**UI:** **🔔 Alerts** page — channel setup + rule toggles. **Effort: M** (scheduler + bot wiring).

---

## 7. 🏋️ Membership & Gear Cost-Per-Use

**Why it matters to you.** Sport and activities are recurring spend whose *value* depends on
**usage**, not price. A ฿1,590/mo gym is great at 20 visits and a ripoff at 2. This makes that ROI
visible and tells you to use it more — or cancel.

**What it does**

- Tag a subscription (or one-off gear buy) as **usage-tracked**; log check-ins (button or chat: *"went climbing"*).
- **Cost per use** = period cost ÷ uses; compare to the **drop-in / pay-per-visit** price.
- Verdict badge: **"Worth it"** (below drop-in) vs **"Underused — ฿199/visit vs ฿120 drop-in."**
- Gear amortization: ฿9,000 climbing shoes ÷ 60 sessions = ฿150/session.

**Data model**

```sql
ALTER TABLE subscriptions ADD COLUMN usage_tracked INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN dropin_price REAL;        -- pay-per-visit benchmark
CREATE TABLE usage_log (id TEXT PRIMARY KEY, ref_type TEXT, ref_id TEXT, date TEXT, note TEXT);
```

**API:** `POST /api/usage` · `GET /api/usage/roi`.

**AI tools:** `log_activity` ("went to the gym"), `membership_roi`.

**UI:** ROI cards on the Subscriptions page + a quick "✅ Used today" button. **Effort: S.**

---

# 🥈 Tier 2 — Strong nice-to-haves

| Feature | What & why | Effort |
|---------|------------|:------:|
| **📷 Receipt OCR + e-Receipt capture** | Snap a receipt → auto-fill amount/merchant/date; store e-Tax invoices for the Easy-E-Receipt deduction (#2). Cuts entry friction to ~zero. | M |
| **🏦 Bank / PromptPay statement import** | Import SCB / K-Bank / KTB / BBL CSV (or email/SMS parse) → auto-categorized transactions. The biggest data-entry time-saver for a Thai user. | L |
| **💰 Net Worth & Cashflow Forecast** | Assets − liabilities over time + month-end projection ("at this burn you'll be ฿3,200 over"). Turns the tracker forward-looking. | M |
| **🎯 Financial Goals & Emergency Fund** | "6 months expenses = ฿180k, you're 64% there." Auto-allocate a slice of each refill toward goals. | M |
| **🔍 Subscription Audit** | Detect unused / duplicate subs and **price-hike** changes ("Netflix +฿70"). Recovers silent money leaks. | S |
| **🏧 Debt & Loan Tracker** | Amortization for car/condo/personal loans; **snowball vs avalanche** payoff planner; interest paid to date. | M |
| **📅 Bill Calendar** | All recurring outflows (subs, insurance, cards, loans) on one calendar with due-date reminders. | S |
| **👥 Shared / Household Budget + Bill Split** | Split rent/dining/trips with partner or friends; settle-up balances. Needs multi-user. | L |
| **📱 PWA / Mobile + Offline** | Installable phone app, quick-add widget, offline queue. Where on-the-go logging actually happens. | M |
| **🪙 Recurring Income & Payday Auto-Refill** | Model salary/side income; on payday, auto-run the master-wallet refill and goal allocations. | S |
| **🧾 Warranty & Big-Purchase Tracker** | Track electronics/appliance warranties + receipts; reminders before expiry. | S |

---

# 🥉 Tier 3 — Exhaustive backlog (someday / maybe)

Grouped wishlist — capture everything; pull up as appetite allows.

**Insights & intelligence**
- Anomaly detection (unusual charge alerts) · spend heatmap (day/hour) · merchant-level analytics ·
  category auto-classification rules · "what-if" simulator (cut X, save Y/yr) · year-in-review report ·
  AI monthly financial coach summary.

**Maximize gain**
- Dividend calendar · tax-loss-harvesting hints · FX-fee leaderboard per card · interest-rate
  watch for Thai savings/MMF · cashback/coupon wallet · loyalty-points & airline-miles hub ·
  gift-card / voucher tracker · "round-up to invest" micro-investing.

**Thai-specific**
- SSO (มาตรา 33/39/40) benefit & contribution tracker · provident fund (PVD) tracker ·
  gov stimulus-scheme assistant (เงินดิจิทัล / คนละครึ่ง-style) · Thai SET stock data source ·
  withholding-tax (ภ.ง.ด.) reconciliation.

**Lifestyle (eat / sport / transport)**
- Restaurant/dish spend log + "favorite cheap eats" · transport mode breakdown (BTS/MRT vs Grab vs
  fuel) + cost-per-km · fuel-economy log · race/event-registration budget · health/medical spend
  ledger.

**Engineering & data**
- Multi-user auth + roles · encrypted backups & restore · Google Sheets / Notion sync ·
  webhook/REST integrations · import (CSV/JSON/OFX) · audit log · API keys · dark mode · i18n
  (TH/EN) · tags + full-text search · split transactions · inter-wallet transfers · budget
  templates · data-retention/export-all (PDPA-friendly).

---

# 🧩 Cross-cutting foundations

Several Tier-1 features share infrastructure — build these once:

| Foundation | Needed by | Notes |
|------------|-----------|-------|
| **Background scheduler** | Alerts, DCA, renewals, payday refill | APScheduler in-process, or a `cron` compose service calling internal endpoints. |
| **File storage** | Insurance docs, receipts (OCR) | Local `data/files/` volume + path column; keep it self-hosted. |
| **Price + FX fetcher** | Portfolio, Trips, multi-currency | One cached fetcher service; opt-in, offline-safe (last-known-rate fallback). |
| **Versioned settings store** | Tax rules, reward rules, caps | `(year, key) → value` tables so yearly rule changes never touch code. |
| **Notification service** | All reminders | Channel abstraction (Telegram / LINE Messaging API / email). |
| **Auth (optional)** | Multi-user, mobile, sharing | Only when leaving single-user localhost. |

---

# 🗓️ Suggested build order

A phased path that front-loads impact and shares foundations:

1. **Phase 1 — Protect & save (Tier 1 core).**
   Insurance Vault (#1) → Tax Optimizer (#2). Highest guaranteed THB return; #1 feeds #2.
2. **Phase 2 — Grow & travel.**
   Investment/DCA (#3) + Multi-Currency/Trips (#4). Shares the **price/FX fetcher** foundation.
3. **Phase 3 — Optimize the everyday.**
   Card Rewards (#5) + Membership ROI (#7). Pure upside on existing spend.
4. **Phase 4 — Close the loop.**
   Proactive Alerts (#6) on top of the scheduler — makes every prior feature *proactive*.
5. **Phase 5+ — Tier 2 by appetite.**
   Statement import & Receipt OCR (kill data entry) → Net worth/forecast → Goals → the rest.

---

*Living document — reprioritize freely as life and the Thai tax code change.*
