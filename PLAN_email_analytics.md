# Email + Analytics Plan

This is the working plan for email (transactional, digest, marketing) and website
analytics for Illusion. It's a source of truth for me and any agent that picks this
up later — keep it up to date as work happens.

Last updated: 2026-04-21

---

## TL;DR build order

1. Analytics (Vercel Web Analytics + PostHog) — ~1 hour
2. Welcome email + Resend domain verification + unsubscribe token — ~½ day
3. Weekly digest smoke test end-to-end — ~1 hour
4. Marketing email agent with human-in-the-loop review — ~1–2 days

---

## Current state (audited 2026-04-21)

### Auth / signup
- `POST /register` creates a user with a valid JWT, no email verification, no welcome email.
- No `is_verified` / `verification_token` columns on the User model.
- On register we create the User + NotificationSettings rows and return a token. That's it.

### Resend integration (`backend/email_service.py`)
- Global client init via `resend.api_key = settings.resend_api_key` at import time.
- Two functions exist:
  - `send_weekly_digest(...)` — per-product weekly email
  - `send_mention_alert(...)` — triggered when a new mention appears
- Both use inline f-string HTML templates — fine for now, will get unwieldy at 5+ templates.
- Env: `RESEND_API_KEY`, `RESEND_FROM_EMAIL` (defaults to `contact@illusion.ai`).
- Error handling: try/except with console log on failure. No retry, no dead-letter.

### Scheduled jobs (`backend/scheduler.py`)
- APScheduler, in-process.
- Daily scans: 6am UTC (paid users only).
- Weekly scans: Monday 7am UTC (free users only).
- Weekly digest: **Monday 9am UTC** — iterates active users, checks
  `NotificationSettings.weekly_digest` opt-in, sends one email per product per user.
- No unsubscribe token in the email; footer just links to `/settings` (requires login).

### Marketing emails
- None exist. No broadcast list, no contact segmentation, nothing.

### Known bugs to fix en route
- `config.py` default `RESEND_FROM_EMAIL` was `noreply@aimentiontacker.com`
  (missing "r" in tracker). **Fixed 2026-04-21** to `contact@illusion.ai`.
- `DEPLOY.md` referenced `joinroomieapp.com`. **Fixed 2026-04-21** to `illusion.ai`.

---

## Part 1 — Signup welcome email

**Decision**: send a welcome email, do NOT require verification before login.
Optimize for lowest possible friction on first signup.

**Work**:
1. Add `send_welcome_email(user_email, user_name)` to `email_service.py`. New inline
   template keyed off the same Resend config.
2. In `routers/auth.py::register`, after the user is persisted and token issued,
   fire the welcome email via FastAPI `BackgroundTasks` so the HTTP response doesn't
   wait on Resend.
3. Template content: "Welcome to Illusion, here's what to do in 60 seconds" —
   (1) add your product, (2) run your first scan, (3) read the recommendations.
   Link to `/dashboard`. Reply-to = `contact@illusion.ai`.

**Acceptance**:
- [ ] Register a test user against a real inbox and receive the email within 10s
- [ ] Email lands in Gmail primary tab, not Promotions or Spam
- [ ] Email renders correctly in Gmail, Outlook, Apple Mail
- [ ] Signup latency unchanged (< 200ms p95)

---

## Part 2 — Finish the weekly digest

The scheduler already runs. The ops work is what's missing.

### 2a. Resend domain verification
Required before any meaningful email volume. Gmail/Outlook will 100% spam-route
unverified senders.

**Work**:
1. In Resend dashboard → Domains → Add `illusion.ai`.
2. Copy the three DNS records Resend provides (SPF TXT, DKIM CNAME, DMARC TXT).
3. Add them at the `illusion.ai` DNS provider.
4. Wait for propagation + green checkmark in Resend UI (~10–60 min).

**Acceptance**: Resend UI shows `illusion.ai` as "Verified" with DKIM + SPF + DMARC all green.

### 2b. One-click unsubscribe
Gmail's bulk sender rules (enforced Feb 2024) and Yahoo's equivalent effectively
require a one-click unsub that works without login.

**Work**:
1. Add `unsubscribe_token` column to User model (generated at user creation,
   stored as a URL-safe random string).
2. Add `GET /api/unsubscribe?token=...&list=weekly_digest` endpoint:
   - Look up user by token
   - Flip `NotificationSettings.weekly_digest = false` (or whichever list)
   - Render a simple "You're unsubscribed" HTML page
3. Add `List-Unsubscribe` header to every bulk email in `email_service.py`:
   ```
   List-Unsubscribe: <https://illusion.ai/api/unsubscribe?token={t}&list=weekly_digest>
   List-Unsubscribe-Post: List-Unsubscribe=One-Click
   ```
4. Replace the "Manage notifications" footer link with a visible "Unsubscribe" link
   pointing to the same URL.

**Acceptance**:
- [ ] Clicking the Gmail "Unsubscribe" link (next to the from-address) flips the flag
- [ ] Clicking the footer unsub link flips the flag and shows a confirmation page
- [ ] User can re-enable from `/settings`

### 2c. End-to-end smoke test
Before any marketing email work, validate the digest pipeline once with real data.

**Work**: register a test account, add a product, run a few scans, manually
trigger `send_weekly_digests()` (expose as an admin-only endpoint or run from a
REPL), confirm delivery + render across Gmail/Outlook/Apple Mail.

---

## Part 3 — Marketing email agent

### Goals
- Weekly "AI Search Insights" email to existing users (and eventually waitlist
  signups from the landing page)
- Driven by Claude with tool use
- Mixes Illusion's own aggregated stats with outside news to feel in-the-moment
- Human-in-the-loop review for the first 4–6 weeks, then consider auto-send

### Architecture

```
┌─ APScheduler ───────────────────────────────────────┐
│  cron: Tuesday 10:00 UTC (digest ships Monday 9:00) │
└─────────────────┬───────────────────────────────────┘
                  ↓
     build_context() gathers:
       • segment = 'free' | 'paid' | 'waitlist'
       • aggregate_stats_for_segment()  (internal tool)
       • news_for_this_week()           (Tavily tool)
     ↓
     claude_generate(context) → { subject, html, text, rationale }
     ↓
     if AUTO_SEND:  resend.batch_send(segment, rendered)
     else:          post_to_review_queue(draft)   ← default for first month
                       ↳ Slack webhook or email to David
     ↓
     on approval:  resend.batch_send(...)
     ↓
     track_opens_clicks()  (Resend webhooks → email_events table)
```

### Agent tools

1. **`aggregate_stats(segment, window='7d')`** — internal function that returns:
   - avg mention rate across users in the segment
   - top competitor names seen in scans
   - fastest-climbing product (anonymized) for a "success story" hook
   - total scans run, total recommendations generated
2. **`tavily_search(query, max_results=5)`** — wraps Tavily Search API
   - 1,000 free searches/month is plenty (we run ~5–10 per weekly email)
   - returns title, URL, snippet, published date, score
   - preloaded agent queries: "AI search SEO news this week", "Google AI Overview
     changes", "ChatGPT SaaS recommendations trends", "generative engine optimization"
3. **`get_product_update()`** — optional manual input from David's side (a
   short note about what shipped this week). Pulled from a single row in a
   `marketing_input` table that David updates whenever he wants. Empty → agent skips.

### Content template
Agent outputs JSON:
```json
{
  "subject": "max 50 chars, no 'newsletter', one curiosity hook",
  "preheader": "short second-line preview text",
  "sections": {
    "hero_stat": "one sentence + one number from aggregate_stats()",
    "news": [
      { "headline": "...", "so_what": "one line on why it matters", "url": "..." },
      ...up to 3
    ],
    "product_tip": "one actionable thing to try in Illusion this week",
    "product_update": "optional, only if get_product_update() returned non-empty"
  },
  "rationale": "one paragraph: why this angle, this week, for this segment"
}
```

Render step converts JSON → HTML using a Jinja template in `backend/templates/marketing_weekly.html`.

### CAN-SPAM / deliverability requirements
- Clear from address: `contact@illusion.ai` (same verified domain)
- Physical mailing address in the footer (requirement — even a PO box)
- Visible unsubscribe link in the body (same token system as Part 2b)
- `List-Unsubscribe` headers
- Don't send more than 1 marketing email per segment per week

### Open questions (need David's call before building)
- **Who gets marketing emails?**
  - Default proposal: active users (free + paid) + waitlist signups from landing page.
  - Unsubscribed users → excluded, obviously.
  - Do we want a separate opt-in step for marketing vs. digest? GDPR and good taste
    say yes — treat them as separate lists. Recommended: add a checkbox at signup
    ("Send me product news and tips" — default checked, but honored).
- **Outbound cold email?** Different rabbit hole (warmup, list hygiene, reply handling).
  I'd defer. If you want to pursue, it needs its own doc.

### Acceptance
- [ ] First 4 weekly drafts are reviewed by David before send
- [ ] Unsubscribe rate stays under 2% per send
- [ ] Open rate ≥ 25% for existing-user segment, ≥ 15% for waitlist
- [ ] Zero Gmail spam complaints before auto-send is enabled

---

## Part 4 — Analytics stack

**Chosen stack**: Vercel Web Analytics + PostHog. Both free tiers, complementary.

### Vercel Web Analytics
- One-line install: `npm i @vercel/analytics`, add `<Analytics />` in `App.jsx`
- Privacy-friendly by default, no cookie banner needed
- Free on Hobby plan (covers our volume for the foreseeable future)
- Gives: pageviews, unique visitors, referrers, top pages, device breakdown

### PostHog
- Free tier: 1M events/month, 5k session replays/month, 1M feature flag requests/month
- Gives us what Vercel Analytics doesn't:
  - Funnels (landing → register → first scan → paid)
  - Retention cohorts (are day-7 users still running scans?)
  - Session replays (watch confused users)
  - Feature flags (gate new features to % of users)
  - A/B testing
- Configure in cookieless mode → still no cookie banner
- Install: `npm i posthog-js`, init in `main.jsx`

### Key events to track in PostHog (day 1)
- `landing_viewed`
- `register_started` / `register_completed` (with segment)
- `first_product_added`
- `first_scan_run`
- `first_scan_completed` (with mention_rate)
- `recommendation_viewed`
- `pricing_viewed`
- `checkout_started` / `checkout_completed` (with plan)
- `scan_run` (ongoing engagement)
- `unsubscribe_clicked` (from emails — ties email → retention)

### Not using
- **Google Analytics 4**: slow, samples data, requires a PhD to configure events,
  multiple EU DPAs have ruled against specific GA4 configs. For a product-led
  SaaS the product-analytics angle (funnels, retention) matters more than raw
  traffic numbers, which is exactly where GA4 is weakest.
- **Plausible**: simpler than Vercel Analytics but duplicates the same basic
  metrics. Paid. Not worth the overlap.

---

## File / code touchpoints

When someone picks up each part, here's where the work lands:

| Part | Files to edit | New files |
|---|---|---|
| 1. Welcome email | `backend/email_service.py`, `backend/routers/auth.py` | — |
| 2a. Domain verify | — (DNS + Resend dashboard) | — |
| 2b. Unsubscribe | `backend/models.py` (add column), `backend/email_service.py`, `backend/routers/__init__.py` | `backend/routers/unsubscribe.py` |
| 3. Marketing agent | `backend/scheduler.py` (add job), `backend/config.py` (Tavily key) | `backend/marketing_agent.py`, `backend/routers/marketing_review.py`, `backend/templates/marketing_weekly.html` |
| 4a. Vercel Analytics | `frontend/src/App.jsx`, `frontend/package.json` | — |
| 4b. PostHog | `frontend/src/main.jsx`, `frontend/package.json`, `.env` (`VITE_POSTHOG_KEY`) | `frontend/src/analytics.js` (event helpers) |

---

## New env vars this plan introduces

Add to Railway when each part ships:

| Key | When | Notes |
|---|---|---|
| `TAVILY_API_KEY` | Part 3 | Free tier 1,000 searches/mo, sign up at tavily.com |
| `MARKETING_AUTO_SEND` | Part 3 | `false` until we trust the agent, then `true` |
| `MARKETING_REVIEW_SLACK_WEBHOOK` | Part 3 (optional) | if we want Slack pings for drafts |
| `VITE_POSTHOG_KEY` | Part 4b | frontend env var, not backend |
| `VITE_POSTHOG_HOST` | Part 4b | `https://us.i.posthog.com` for US cloud |

---

## Research sources

- [Vercel Analytics pricing docs](https://vercel.com/docs/analytics/limits-and-pricing)
- [PostHog pricing](https://posthog.com/pricing)
- [PostHog: GA4 alternatives comparison](https://posthog.com/blog/ga4-alternatives)
- [Tavily vs Perplexity vs Exa 2026](https://www.humai.blog/perplexity-vs-tavily-vs-exa-vs-you-com-the-complete-ai-search-engine-comparison-2026/)
- [Deep research APIs for agentic workflows 2026](https://www.firecrawl.dev/blog/best-deep-research-apis)
- Gmail bulk sender rules (Feb 2024): one-click unsubscribe + SPF/DKIM/DMARC required
