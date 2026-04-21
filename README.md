# AI Mention Tracker

Track whether AI assistants like Claude and ChatGPT mention your product when users ask category questions. Because more and more buying decisions start with "what's the best X?" asked to an AI — and if your product doesn't show up in that answer, you're invisible.

## What it does

1. You tell it about your product: name, category (e.g. "project management software"), use case, competitors, keywords.
2. It generates realistic buyer queries — "what are the best project management tools?", "alternatives to Asana", etc.
3. It asks those queries to **Claude, GPT, Gemini, and Perplexity** on a schedule (weekly on free, daily on paid) — all routed through a single OpenRouter key so you only deal with one vendor.
4. It parses each response and extracts: whether your product was mentioned, what rank, sentiment, and which competitors showed up — tagged by provider so you can see where you're winning vs losing.
5. It scrapes **Google's AI Overview** for the primary category query (via SerpAPI) so you see which sources Google itself cites in its AI answers.
6. It feeds all of that — LLM mention data + competitors + AI Overview citations — into Claude directly, which returns a prioritized action list of concrete SEO / content moves to improve rankings across AI search.
7. It shows history, trends, and recommendations in a dashboard, and (on paid plans) emails a weekly digest plus instant alerts when a mention appears.

## Plans

| Plan | Price | Scan frequency | Alerts |
|------|-------|----------------|--------|
| Free (7-day trial) | $0 | Weekly | Weekly digest |
| Starter | $19/mo | Daily | Weekly digest |
| Growth | $39/mo | Daily | Weekly digest + instant mention alerts |

## Stack

- **Backend:** FastAPI (Python 3.11+), SQLAlchemy async, SQLite, APScheduler, JWT auth (bcrypt), OpenRouter (Claude + GPT + Gemini + Perplexity for scans), Anthropic SDK (direct Claude for recommendations), SerpAPI (Google AI Overview), Resend, Stripe
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

The scan pipeline lives across three modules:

**`backend/monitor.py`** — LLM scanning
1. **`build_queries(...)`** — generates 6–8 buyer-intent queries from a product's category, use case, competitors, and keywords.
2. **`query_provider(provider_tag, prompt)`** — routes to the specified provider via OpenRouter's OpenAI-compatible API. The `PROVIDERS` dict maps short tags (`claude`, `gpt`, `gemini`, `perplexity`) to model ids.
3. **`analyze_response(...)`** — regex/text parsing to detect whether the product appears, estimate list position, classify sentiment from surrounding words, and tag which competitors were mentioned.
4. **`run_product_scan(...)`** — runs every query against every provider. ~24–32 queries per scan → ~$0.02–0.04 in OpenRouter cost.

**`backend/serp.py`** — Google AI Overview scraping
- **`fetch_ai_overview(query)`** — hits SerpAPI's `engine=google` search, looks for an inline `ai_overview` block, and falls back to the `page_token` → `engine=google_ai_overview` flow when Google defers the result. Returns normalized `{overview_text, text_blocks, references, was_returned}`.
- Only the primary category query is sent (1 SerpAPI credit per scan). ~36% of queries return actual AI Overview content; the rest are recorded as `was_returned=False`.

**`backend/recommendations.py`** — Claude-generated SEO plan
- **`build_prompt(product, scan_results, ai_overview)`** — assembles product metadata + per-provider mention stats + representative response samples + AI Overview text and citations.
- **`generate_recommendations(...)`** — calls Anthropic directly (using `ANTHROPIC_API_KEY`, separate from OpenRouter) and expects structured JSON back: `{executive_summary, strengths, weaknesses, actions: [{priority, title, rationale}]}`. ~$0.02 per summary with Sonnet 4.5.

**`backend/scheduler.py`** ties it together: after the LLM scan saves `ScanResult` rows it runs SerpAPI (saved as `AIOverviewSnapshot`) then Claude (saved as `Recommendation`). Both steps are wrapped in try/except so a SerpAPI or Claude failure never fails the scan.

The scheduler runs three cron jobs:
- **Daily 06:00 UTC** — scan every active product belonging to `starter` or `growth` users.
- **Monday 07:00 UTC** — scan every active product belonging to `free` users.
- **Monday 09:00 UTC** — send weekly email digests to all users who haven't disabled them.

## Safety / data

- SQLite DB (`backend/ai_mention_tracker.db`) is the single source of truth for users, products, and scan history. Back it up before any destructive change.
- Passwords are hashed with bcrypt; sessions are JWTs signed with `SECRET_KEY`.
- Never commit `backend/.env` — it has API keys for Anthropic, Resend, and Stripe.

## License

Private / proprietary. Atreides LLC.
