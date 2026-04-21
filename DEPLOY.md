# Deploy

Target: **Railway** for the FastAPI backend, **Vercel** for the React frontend. Budget: ~$5/month (Railway).

---

## 0. Push to GitHub

Railway and Vercel both deploy from a Git repo.

```bash
cd /path/to/ai-mention-tracker
git init
git add .
git commit -m "initial commit"
gh repo create ai-mention-tracker --private --source=. --push
```

(Or create the repo in the GitHub UI and `git remote add origin ...` + `git push -u origin main`.)

The `.gitignore` at the root excludes `backend/.env`, `*.db`, `venv/`, and `node_modules/` — make sure none of those show up in the first commit.

---

## 1. Backend → Railway

1. Sign in at <https://railway.app> with GitHub.
2. **New Project → Deploy from GitHub repo → ai-mention-tracker.**
3. After the service is created, open its **Settings**:
   - **Root Directory:** `backend`
   - Railway auto-detects Python via Nixpacks; `railway.json` supplies the start command.
4. **Add a Volume** (Settings → Volumes):
   - Mount path: `/data`
   - This is where the SQLite DB will live so it survives deploys. Without a volume, you lose all users on every push.
5. **Variables** tab — add these (copy values from `backend/.env`):

   | Key | Value |
   |---|---|
   | `SECRET_KEY` | generate a new one: `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `OPENROUTER_API_KEY` | your OpenRouter key (routes to Claude + GPT + Gemini + Perplexity for scans) |
   | `ANTHROPIC_API_KEY` | your Anthropic key — used directly for the per-scan SEO recommendations |
   | `ANTHROPIC_MODEL` | `claude-sonnet-4-6` (or omit for the default, or use `claude-haiku-4-5-20251001` to save ~80%) |
   | `SERPAPI_API_KEY` | your SerpAPI key — scrapes Google AI Overview once per scan. Free tier: 100 searches/mo |
   | `RESEND_API_KEY` | your Resend key |
   | `RESEND_FROM_EMAIL` | `noreply@contact.joinroomieapp.com` |
   | `STRIPE_SECRET_KEY` | `sk_live_...` (or test key to start) |
   | `STRIPE_PUBLISHABLE_KEY` | `pk_live_...` |
   | `STRIPE_WEBHOOK_SECRET` | fill in after step 4 below |
   | `STRIPE_STARTER_PRICE_ID` | `price_...` |
   | `STRIPE_GROWTH_PRICE_ID` | `price_...` |
   | `APP_URL` | your Vercel frontend URL (fill in after step 2) |
   | `BACKEND_URL` | your Railway backend URL (shown in Railway after first deploy) |
   | `DATABASE_URL` | `sqlite+aiosqlite:////data/ai_mention_tracker.db` (note four slashes — absolute path on the mounted volume) |
   | `ENV` | `prod` |

6. Hit **Deploy**. First build takes ~2–3 min. When it's up, Railway gives you a URL like `https://ai-mention-tracker-production.up.railway.app`.
7. Test: `curl https://<railway-url>/api/health` → should return `{"status":"ok","version":"1.0.0"}`.

**Budget note:** Railway's Hobby plan is $5/month and includes $5 of usage credit. This app will sit well under the credit — a sleeping FastAPI app uses ~0.1 vCPU, ~100MB RAM. Expect real usage around $2–4/mo unless you get a lot of traffic.

---

## 2. Frontend → Vercel

1. Sign in at <https://vercel.com> with GitHub.
2. **Add New → Project → Import ai-mention-tracker.**
3. Settings:
   - **Root Directory:** `frontend`
   - Framework: **Vite** (auto-detected)
   - Build command: `npm run build` (auto)
   - Output dir: `dist` (auto)
4. **Environment Variables:**

   | Key | Value |
   |---|---|
   | `VITE_API_URL` | your Railway backend URL from step 1.6 (e.g. `https://ai-mention-tracker-production.up.railway.app`) |

5. **Deploy.** First build takes ~1 min. Vercel gives you a URL like `https://ai-mention-tracker.vercel.app`.

---

## 3. Wire them together

Go back to Railway → Variables and update:
- `APP_URL` = your Vercel URL (e.g. `https://ai-mention-tracker.vercel.app`)
- `BACKEND_URL` = your Railway URL

Railway auto-redeploys on env var change.

The backend CORS config already permits any `*.vercel.app` origin, so preview deploys (PR branches) will also work.

---

## 4. Stripe webhook

This has to be done **after** the backend is live on Railway because Stripe needs a public URL to point at.

1. In Stripe Dashboard → Developers → Webhooks → **Add endpoint.**
2. Endpoint URL: `https://<railway-url>/api/billing/webhook`
3. Events to send: at minimum
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. After creation, reveal the **Signing secret** (`whsec_...`). Paste it into Railway's `STRIPE_WEBHOOK_SECRET` variable. Railway will redeploy.
5. Send a test event from Stripe Dashboard → should land at the webhook endpoint with HTTP 200.

---

## 5. Stripe products (if not done)

Still in the Stripe Dashboard:

1. Products → **Add product** → Starter, recurring $19/mo → copy the `price_...` ID into `STRIPE_STARTER_PRICE_ID`.
2. Products → **Add product** → Growth, recurring $39/mo → copy the `price_...` ID into `STRIPE_GROWTH_PRICE_ID`.
3. Settings → Billing → Customer portal → enable, save → this is what `/api/billing/portal` opens.

---

## 6. Custom domain (optional, free subdomain)

You own `joinroomieapp.com`. Point a subdomain like `ai.joinroomieapp.com` at the Vercel frontend:

1. Vercel → Project → Settings → Domains → add `ai.joinroomieapp.com`.
2. Vercel shows a CNAME record to add in your DNS provider. Add it.
3. Update the Stripe webhook URL if you also point a `api.` subdomain at Railway (optional).

---

## Smoke test (end-to-end)

After everything is live:

1. Visit your Vercel URL.
2. Register a new account → should redirect to dashboard.
3. Add a product (e.g. name: "Notion", category: "note-taking apps", competitors: "Obsidian,Evernote").
4. Click **Run scan** → wait 15–30s → scan results should appear.
5. Go to Pricing → pick Starter → Stripe Checkout should open with the $19 recurring price → complete with test card `4242 4242 4242 4242` (if on test keys).
6. Stripe webhook fires → Railway logs should show the event → your account plan flips to `starter` in the DB.

If all six pass, you have a deployed, payment-capable product.

---

## Rollback / debugging

- **Railway logs:** project → service → **Deployments** tab → click a deploy → logs
- **Vercel logs:** project → **Deployments** tab → click a deploy → Function logs (for serverless) or Build logs
- **DB corrupted / reset:** SSH into Railway service (or use their CLI), delete `/data/ai_mention_tracker.db`, redeploy — SQLAlchemy recreates schema on boot.
- **Rollback:** both Railway and Vercel let you redeploy any previous commit with one click.

---

## What's next after shipping

1. Register your first real user (you). Add a product. Watch scans run.
2. Tell ~10 founders in your network — see if anyone bites at $19/mo.
3. If yes → add GPT-4 as a second AI source (bigger moat).
4. If no → iterate on positioning, not features.
