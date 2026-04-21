# AI Mention Tracker

Track whether AI assistants like Claude and ChatGPT mention your product when users ask category questions. Because more and more buying decisions start with "what's the best X?" asked to an AI — and if your product doesn't show up in that answer, you're invisible.

## What it does

1. You tell it about your product: name, category (e.g. "project management software"), use case, competitors, keywords.
2. It generates realistic buyer queries — "what are the best project management tools?", "alternatives to Asana", etc.
3. It asks those queries to Claude on a schedule (weekly on free, daily on paid).
4. It parses each response and extracts: whether your product was mentioned, what rank, sentiment, and which competitors showed up.
5. It shows the history and trends in a dashboard, and (on paid plans) emails you a weekly digest plus instant alerts when a mention appears.

## Plans

| Plan | Price | Scan frequency | Alerts |
|------|-------|----------------|--------|
| Free (7-day trial) | $0 | Weekly | Weekly digest |
| Starter | $19/mo | Daily | Weekly digest |
| Growth | $39/mo | Daily | Weekly digest + instant mention alerts |

## Stack

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy async, SQLite, APScheduler, JWT auth (bcrypt), Anthropic SDK, Resend, Stripe
- **Frontend:** React 18, Vite, React Router, Lucide icons
- **Deployment target:** Backend on Railway/Render, frontend on Vercel

## Quick start

```bash
# One-liner (after SETUP.md is done)
./start.sh
```

Backend runs on `http://localhost:8000` (API docs at `/docs`). Frontend runs on `http://localhost:5173`.

For first-time setup — creating the venv, installing dependencies, wiring up Anthropic/Resend/Stripe keys — see **[SETUP.md](./SETUP.md)**.

## Repo layout

```
ai-mention-tracker/
├── backend/
│   ├── main.py              # FastAPI app + lifespan init
│   ├── config.py            # Settings loaded from .env
│   ├── database.py          # Async SQLAlchemy engine + session
│   ├── models.py            # User, Product, ScanResult, NotificationSettings
│   ├── auth.py              # JWT + bcrypt helpers
│   ├── monitor.py           # Core: builds queries, calls Claude, parses responses
│   ├── scheduler.py         # APScheduler jobs (daily scans, weekly digests)
│   ├── email_service.py     # Resend integration (digest + instant alerts)
│   ├── routers/
│   │   ├── auth.py          # /register, /login, /me
│   │   ├── products.py      # CRUD + trigger scan + read results
│   │   ├── billing.py       # Stripe checkout, portal, webhook
│   │   └── settings.py      # Notification prefs
│   ├── requirements.txt     # Python deps
│   ├── .env.example         # Env var template
│   └── ai_mention_tracker.db  # SQLite (auto-created)
├── frontend/
│   ├── src/
│   │   ├── App.jsx, main.jsx, AuthContext.jsx, api.js
│   │   ├── pages/           # Landing, Auth, Dashboard, Settings, Pricing
│   │   └── components/      # ProductModal, ScanResults
│   ├── package.json
│   └── vite.config.js
├── start.sh                 # Launches backend + frontend for local dev
├── README.md                # (this file)
└── SETUP.md                 # First-time setup instructions
```

## How the monitoring works

`backend/monitor.py` is the heart of the product:

1. **`build_queries(...)`** — generates 6–8 buyer-intent queries from a product's category, use case, competitors, and keywords.
2. **`query_claude(prompt)`** — sends each query to `claude-haiku-4-5` (fast + cheap; ~\$0.001 per query).
3. **`analyze_response(...)`** — regex/text parsing to detect whether the product appears, estimate list position, classify sentiment from surrounding words, and tag which competitors were mentioned.
4. **`run_product_scan(...)`** — runs all queries for a product and returns a list of `ScanResult` dicts.

The scheduler (`backend/scheduler.py`) runs three cron jobs:
- **Daily 06:00 UTC** — scan every active product belonging to `starter` or `growth` users.
- **Monday 07:00 UTC** — scan every active product belonging to `free` users.
- **Monday 09:00 UTC** — send weekly email digests to all users who haven't disabled them.

## Safety / data

- SQLite DB (`backend/ai_mention_tracker.db`) is the single source of truth for users, products, and scan history. Back it up before any destructive change.
- Passwords are hashed with bcrypt; sessions are JWTs signed with `SECRET_KEY`.
- Never commit `backend/.env` — it has API keys for Anthropic, Resend, and Stripe.

## License

Private / proprietary. Atreides LLC.
