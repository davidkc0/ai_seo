# Email + Analytics Plan

Working plan for email (transactional, digest, marketing) and website analytics
for Illusion. Source of truth for me and any agent that picks this up later.

Last updated: 2026-04-21

---

## Status at a glance

| # | Workstream | Status |
|---|---|---|
| 1 | Welcome email on signup | ✅ shipped |
| 2a | Resend domain verification (`contact.illusion.ai`) | ✅ verified in Resend |
| 2b | One-click unsubscribe + `List-Unsubscribe` headers | ✅ shipped |
| 2c | Weekly digest end-to-end smoke test | ☐ ops task — run once with real inbox |
| 4a | Vercel Web Analytics | ✅ shipped |
| 4b | PostHog + event helpers | ✅ shipped |
| 3 | **Marketing email agent** (this is what's left) | 🚧 pending |

Everything below the `Part 3 — Marketing email agent` section still matters.
Parts 1, 2, and 4 are kept for posterity / so the next agent can see what
already exists before duplicating it.

---

## Part 3 — Marketing email agent (remaining work)

This is the only workstream still open. All infrastructure it depends on
(verified sending domain, unsubscribe tokens, `marketing_emails` opt-out flag,
PostHog for measuring results) is already in place — see Parts 1/2/4 below.

### Goals
- Weekly "AI Search Insights" email to existing users (and eventually waitlist
  signups from the landing page).
- Driven by Claude with tool use.
- Mixes Illusion's own aggregated stats with outside news to feel in-the-moment.
- Human-in-the-loop review for the first 4–6 weeks, then consider auto-send.

### What's already in place the agent can rely on
- `User.unsubscribe_token` — unique per user, already backfilled.
- `NotificationSettings.marketing_emails` — boolean flag, default `True`.
  **The agent MUST filter the recipient list by this flag.**
- `email_service.build_unsubscribe_url(token, "marketing")` → returns
  `{BACKEND_URL}/api/unsubscribe?token=…&list=marketing`.
- `email_service._bulk_email_headers(url)` → returns the
  `List-Unsubscribe` + `List-Unsubscribe-Post: One-Click` header pair.
- `/api/unsubscribe` already handles `list=marketing` (sets
  `NotificationSettings.marketing_emails = False`).
- PostHog frontend event `unsubscribeClicked` exists (wire the email link
  to a `?utm_source=marketing_weekly` param so PostHog can join the dots).

### Architecture

```
┌─ APScheduler ───────────────────────────────────────┐
│  cron: Tuesday 10:00 UTC (digest ships Monday 9:00) │
└─────────────────┬───────────────────────────────────┘
                  ↓
     build_context() gathers:
       • segment = 'free' | 'paid' | 'waitlist'
       • aggregate_stats_for_segment()   (internal tool)
       • news_for_this_week()            (Tavily tool)
     ↓
     claude_generate(context) → { subject, html, text, rationale }
     ↓
     if MARKETING_AUTO_SEND:  resend.batch_send(segment, rendered)
     else:                    post_to_review_queue(draft)  ← default for first month
                                 ↳ Slack webhook or email to David
     ↓
     on approval:  resend.batch_send(...)
     ↓
     track_opens_clicks()  (Resend webhooks → email_events table)
```

### Agent tools to implement

1. **`aggregate_stats(segment, window='7d')`** — internal function that returns:
   - avg mention rate across users in the segment
   - top competitor names seen in scans
   - fastest-climbing product (anonymized) for a "success story" hook
   - total scans run, total recommendations generated
2. **`tavily_search(query, max_results=5)`** — wraps Tavily Search API
   - 1,000 free searches/month is plenty (~5–10 per weekly email)
   - returns title, URL, snippet, published date, score
   - preloaded agent queries: "AI search SEO news this week", "Google AI
     Overview changes", "ChatGPT SaaS recommendations trends", "generative
     engine optimization"
3. **`get_product_update()`** — optional manual input from David. Single row
   in a `marketing_input` table he updates whenever he wants. Empty → agent skips.

### Content template
Agent outputs JSON:
```json
{
  "subject": "max 50 chars, no 'newsletter', one curiosity hook",
  "preheader": "short second-line preview text",
  "sections": {
    "hero_stat": "one sentence + one number from aggregate_stats()",
    "news": [
      { "headline": "...", "so_what": "one line on why it matters", "url": "..." }
    ],
    "product_tip": "one actionable thing to try in Illusion this week",
    "product_update": "optional, only if get_product_update() returned non-empty"
  },
  "rationale": "one paragraph: why this angle, this week, for this segment"
}
```

Render step converts JSON → HTML using a Jinja template in
`backend/templates/marketing_weekly.html`.

### CAN-SPAM / deliverability requirements
- Clear from address: `noreply@contact.illusion.ai` (already verified).
- Physical mailing address in the footer — required by 15 USC §7704 for any
  commercial email (the marketing broadcast qualifies; the welcome email and
  weekly digest are transactional/relationship mail under §7702(17) and don't
  strictly need it). Acceptable forms under 16 CFR §316.5: a street address,
  USPS-registered PO box, or CMRA virtual mailbox (iPostal1 / Anytime Mailbox
  / etc ~$10/mo). If David has an LLC, use its registered address.
- Visible unsubscribe link in the body (use the existing token system).
- `List-Unsubscribe` headers (use `_bulk_email_headers()` helper).
- Don't send more than 1 marketing email per segment per week.

### Open questions (need David's call before building)
- **Who gets marketing emails?** Default proposal: active users (free + paid)
  + waitlist signups from landing page. Unsubscribed users (where
  `marketing_emails = False`) → excluded.
- **Separate opt-in for marketing vs. digest at signup?** GDPR + good taste
  say yes. Recommended: add a checkbox at signup ("Send me product news and
  tips" — default checked, honored via `marketing_emails` column which
  already exists).
- **Physical mailing address for the marketing broadcast footer** — LLC
  registered address, home address, virtual mailbox, or PO box. Any works.
  Needed before the first send, not to build the agent.
- **Outbound cold email?** Different rabbit hole (warmup, list hygiene, reply
  handling). Defer. If pursued, needs its own doc.

### New files / touchpoints
| What | Where |
|---|---|
| Agent core | `backend/marketing_agent.py` *(new)* |
| Review queue endpoint | `backend/routers/marketing_review.py` *(new)* |
| Email template | `backend/templates/marketing_weekly.html` *(new)* |
| Scheduled job | `backend/scheduler.py` (add Tuesday 10:00 UTC job) |
| Config keys | `backend/config.py` (add Tavily + auto-send + Slack webhook) |
| Waitlist table (if we add landing-page capture) | `backend/models.py` |
| DB: email tracking | `backend/models.py` (`email_events` table fed by Resend webhook) |

### New env vars
| Key | Notes |
|---|---|
| `TAVILY_API_KEY` | Free tier 1,000 searches/mo, sign up at tavily.com |
| `MARKETING_AUTO_SEND` | `false` until we trust the agent, then `true` |
| `MARKETING_REVIEW_SLACK_WEBHOOK` | Optional — if we want Slack pings for drafts |

### Acceptance
- [ ] First 4 weekly drafts are reviewed by David before send
- [ ] Unsubscribe rate stays under 2% per send
- [ ] Open rate ≥ 25% for existing-user segment, ≥ 15% for waitlist
- [ ] Zero Gmail spam complaints before auto-send is enabled

---

## Remaining ops item (outside Part 3)

### 2c. Weekly digest end-to-end smoke test
Code path is live and wired up with one-click unsubscribe. What's left is to
validate delivery against a real inbox once — see `PART2_TESTPLAN.md` Section
6 for a one-shot script (`asyncio.run(send_weekly_digest(...))`) that fires a
digest from a Python REPL without waiting for the Monday 9am UTC cron.

---

---

# Shipped work — reference only

The sections below describe work that's already done. Kept so the next agent
can quickly locate existing code before re-implementing.

## ✅ Part 1 — Welcome email (shipped)

- `email_service.send_welcome_email(to_email, unsubscribe_token)` renders a
  purple-gradient onboarding email with 3 next-step bullets and a Dashboard
  CTA. Lives in `backend/email_service.py`.
- Fired from `POST /api/auth/register` via FastAPI `BackgroundTasks` — signup
  response isn't blocked on Resend. See `backend/routers/auth.py`.
- Reply-to isn't monitored (`noreply@contact.illusion.ai`); footer notes this
  and offers unsubscribe-all.

## ✅ Part 2a — Resend domain verification (shipped)

`contact.illusion.ai` is verified in Resend with SPF + DKIM + DMARC green.
`RESEND_FROM_EMAIL=noreply@contact.illusion.ai` in both `.env.example` and
Railway. If we ever want to send from the bare apex, verify `illusion.ai`
separately (distinct verification).

## ✅ Part 2b — One-click unsubscribe (shipped)

### Data model
- `User.unsubscribe_token` — `VARCHAR(64)`, unique + indexed, populated via
  `secrets.token_urlsafe(32)`. Generated at signup for new users;
  `database.py::_backfill_unsubscribe_tokens` fills existing rows on boot.
- `NotificationSettings.marketing_emails` — `Boolean`, default `True`. Added
  via `database.py::_ensure_notification_marketing_column` in-place migration.

### Endpoints
`backend/routers/unsubscribe.py`:
- `GET /api/unsubscribe?token=…&list=…` — renders "✓ You're unsubscribed"
  HTML page.
- `POST /api/unsubscribe?token=…&list=…` — RFC 8058 one-click endpoint Gmail
  hits behind the scenes. Returns 200 text/plain.
- Valid `list` values: `weekly_digest`, `mention_alerts`, `marketing`, `all`.
  Unknown → falls back to `all` (safer opt-out).
- Invalid tokens return generic 404 (GET) / 200 (POST) — doesn't leak existence.

### Email-side wiring
`email_service.py`:
- `build_unsubscribe_url(token, list_name)` — builds the URL.
- `_bulk_email_headers(url)` — returns the `List-Unsubscribe` +
  `List-Unsubscribe-Post: One-Click` header pair.
- Welcome + weekly digest + mention alert all attach the headers and include
  a visible footer "Unsubscribe" link.
- `scheduler.py::send_weekly_digests` + the instant-alert call site both
  pass `user.unsubscribe_token` to the email functions.

## ✅ Part 4 — Analytics stack (shipped)

### Vercel Web Analytics
- `@vercel/analytics` installed in `frontend/package.json`.
- `<Analytics />` rendered once in `frontend/src/App.jsx`.
- Free on Vercel Hobby. Covers pageviews, referrers, top pages, device
  breakdown. Privacy-friendly — no cookie banner required.

### PostHog
- `posthog-js` installed in `frontend/package.json`.
- Initialized in `frontend/src/main.jsx` in cookieless mode
  (`persistence: 'memory'`), `api_host: https://us.i.posthog.com`. Auto
  pageview + pageleave capture enabled.
- API key lives inline in `main.jsx` (client-side key is meant to be public).
- Event helper library at `frontend/src/analytics.js` exposes a typed
  `track.*` API. All defined events:
  `landingViewed`, `pricingViewed`, `registerStarted`, `registerCompleted`,
  `loginCompleted`, `firstProductAdded`, `firstScanRun`, `scanRun`,
  `scanCompleted`, `recommendationViewed`, `checkoutStarted`,
  `checkoutCompleted`, `unsubscribeClicked`.

### Not using
- **Google Analytics 4**: slow, samples data, multiple EU DPAs have ruled
  against specific GA4 configs. Product-analytics angle matters more.
- **Plausible**: duplicates Vercel Analytics, paid, no reason to run both.

---

## Research sources

- [Vercel Analytics pricing docs](https://vercel.com/docs/analytics/limits-and-pricing)
- [PostHog pricing](https://posthog.com/pricing)
- [PostHog: GA4 alternatives comparison](https://posthog.com/blog/ga4-alternatives)
- [Tavily vs Perplexity vs Exa 2026](https://www.humai.blog/perplexity-vs-tavily-vs-exa-vs-you-com-the-complete-ai-search-engine-comparison-2026/)
- [Deep research APIs for agentic workflows 2026](https://www.firecrawl.dev/blog/best-deep-research-apis)
- Gmail bulk sender rules (Feb 2024): one-click unsubscribe + SPF/DKIM/DMARC required
