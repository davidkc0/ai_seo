# Setup

First-time setup instructions for Illusion. Takes ~15 minutes if you already have Python 3.11+ and Node 18+ installed.

---

## 0. Prerequisites

- **Python 3.11 or 3.12** (3.14 works but forces pre-release wheels for `pydantic-core`; stick to 3.11/3.12 in production)
- **Node 18+** and **npm**
- Accounts: [Anthropic](https://console.anthropic.com), [Resend](https://resend.com), [Stripe](https://dashboard.stripe.com)

---

## 1. Backend

```bash
cd backend

# Virtual environment
python3 -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# (edit .env — see section 3 below)
```

The SQLite database (`ai_mention_tracker.db`) is auto-created on first startup — no migration step needed.

Start the backend:

```bash
python main.py
```

API is live at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

App is live at `http://localhost:5173`.

---

## 3. Environment variables

Fill in `backend/.env`. Start with the values you have, come back for the rest.

### Required for basic run (auth + scans)

```env
SECRET_KEY=<generate below>
ANTHROPIC_API_KEY=sk-ant-...
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Get your Anthropic key at <https://console.anthropic.com/settings/keys>. Claude Haiku 4.5 is cheap (~$0.001 per query); budget roughly $0.005–0.01 per product per daily scan.

### Required for email digests (Resend)

```env
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=noreply@contact.illusion.ai
```

1. Sign up at <https://resend.com> (free tier = 3,000 emails/month).
2. **Verify a domain** (required before Resend will send from it). Add the DNS records they show you.
3. Copy the API key from <https://resend.com/api-keys>.
4. Set `RESEND_FROM_EMAIL` to an address on the verified domain.

Without this, the app runs fine but weekly digests and mention alerts won't send.

### Required for payments (Stripe)

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_STARTER_PRICE_ID=price_...
STRIPE_GROWTH_PRICE_ID=price_...
```

1. In the Stripe dashboard, create two **recurring** products:
   - **Starter** — $19 / month
   - **Growth** — $39 / month
   Copy each **price ID** (starts with `price_...`) into the env vars above.
2. Grab your test keys from <https://dashboard.stripe.com/test/apikeys>.
3. For local webhook testing:
   ```bash
   stripe listen --forward-to http://localhost:8000/api/billing/webhook
   ```
   Copy the `whsec_...` signing secret it prints into `STRIPE_WEBHOOK_SECRET`.
4. When you go live: swap every `sk_test_/pk_test_` to `sk_live_/pk_live_`, create live products, re-point the webhook at your prod URL.

### App URLs

```env
APP_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000
DATABASE_URL=sqlite+aiosqlite:///./ai_mention_tracker.db
```

Change `APP_URL` and `BACKEND_URL` to your custom domains when you deploy.

---

## 4. First-run smoke test

1. Open <http://localhost:5173>.
2. Register a new account (7-day free trial activates automatically).
3. Add a product: name, category, 1–2 competitors, 1–2 keywords.
4. Hit **Run scan** — you should see a list of ~6 queries with Claude's responses and mention data within ~10–20 seconds.
5. Check `GET http://localhost:8000/api/health` returns `{"status":"ok"}`.

If all four work, you have a functioning MVP locally.

---

## 5. Deploy

### Backend → Railway or Render
- Point at the `backend/` directory.
- Build: `pip install -r requirements.txt`
- Start: `python main.py` (or `uvicorn main:app --host 0.0.0.0 --port $PORT`)
- Copy all env vars from `backend/.env`.
- **Persist the SQLite DB** on a mounted volume, or migrate to Postgres with `DATABASE_URL=postgresql+asyncpg://...`. SQLite on ephemeral disk will lose data on every deploy.

### Frontend → Vercel
- Point at the `frontend/` directory.
- Build command: `npm run build`
- Output directory: `dist`
- Env var: `VITE_API_URL=https://your-backend.up.railway.app`

### Post-deploy
- Point your custom domain at Vercel.
- Update `APP_URL` and `BACKEND_URL` in the backend env.
- Verify your production domain in Resend.
- Swap Stripe keys to live and re-register the webhook at `https://<backend-domain>/api/billing/webhook`.

---

## Troubleshooting

**`pydantic-core` build errors on `pip install`** — you're on Python 3.14. Either downgrade to 3.11/3.12, or reinstall with `pip install -r requirements.txt --pre`.

**CORS errors in the browser** — make sure `APP_URL` in `backend/.env` matches the origin you're loading the frontend from. The backend's allowed origins list is set in `main.py`.

**`401 Unauthorized` after login** — check that the frontend is sending the JWT as `Authorization: Bearer <token>`. The token lives in `localStorage.token` after login.

**Stripe webhooks not firing locally** — `stripe listen` must be running in a terminal for the duration of your test, and the `whsec_...` it prints must be in your `.env`.

**Scans are slow** — Haiku 4.5 takes ~2–4s per query and there are ~6–8 queries per scan. Totally normal. Run them in the background via the scheduler rather than synchronously in a request when scanning many products.

---

## Next steps (from `memory/ai-mention-tracker-build.md`)

1. Resend + Stripe wired (above).
2. `npm install` in `frontend/` and smoke-test the UI.
3. Register, add a product, run a scan.
4. Push to a private GitHub repo.
5. Deploy backend (Railway/Render) + frontend (Vercel).
6. Custom domain + verified Resend domain.
7. Swap Stripe to live keys.
8. (Optional) Add OpenAI GPT-4 as a second AI to query for fuller coverage.
