# Part 2 — Welcome Email + Unsubscribe: Test Plan

What shipped: welcome email on signup, one-click unsubscribe (Gmail/Yahoo-compliant), `unsubscribe_token` on every user, `marketing_emails` flag on notification settings.

---

## 1. Env checklist (before testing)

These must be set — locally in `backend/.env` for dev, and in Railway **Variables** for prod:

| Key | Value | Why |
|---|---|---|
| `RESEND_API_KEY` | `re_…` from https://resend.com/api-keys | Required — without it, emails silently no-op (you'll see `[EMAIL] Resend not configured` in logs) |
| `RESEND_FROM_EMAIL` | `noreply@contact.illusion.ai` | Must match a verified sending identity. `contact.illusion.ai` is verified on Resend per your setup. |
| `APP_URL` | dev: `http://localhost:5173` · prod: `https://illusion.ai` (or your Vercel URL) | Used in CTA links inside the welcome + digest emails |
| `BACKEND_URL` | dev: `http://localhost:8000` · prod: your Railway URL (or `https://api.illusion.ai`) | Used to build the one-click unsubscribe URL in email headers |

Gotcha: if `BACKEND_URL` points at localhost but you send the email to your real inbox, Gmail can't actually hit the one-click endpoint to unsubscribe you. For real inbox testing you want the backend reachable from the public internet (ngrok locally, or just test in staging/prod).

---

## 2. Migration sanity (first boot after deploying)

Watch the backend logs on first startup after pushing. You should see one or both of these lines **once** (on pre-existing DBs only):

```
[Migration] Adding users.unsubscribe_token column
[Migration] Adding notification_settings.marketing_emails column
[Migration] Backfilling unsubscribe_token for N users
```

On subsequent boots those lines stay silent — the migration helpers are idempotent.

If Railway's volume is fresh (no `/data/ai_mention_tracker.db` yet), you won't see migration lines — `create_all()` builds the tables with the columns already in place.

Sanity SQL (via Railway shell or a local `sqlite3 /data/ai_mention_tracker.db`):

```sql
SELECT id, email, unsubscribe_token FROM users LIMIT 3;
-- every row should have a 43-char random token, none NULL.

PRAGMA table_info(notification_settings);
-- should list a marketing_emails column with default 1.
```

---

## 3. End-to-end signup flow

1. Go to your Vercel URL → click **Sign Up**.
2. Register a brand new email you control (use `+test1@gmail.com` style aliases so you can test multiple times).
3. Expect: redirect to dashboard, no UI lag (welcome email fires in a BackgroundTask, doesn't block the 200 response).
4. Check that inbox within ~10s. Welcome email should arrive:
   - From: `noreply@contact.illusion.ai`
   - Subject: **Welcome to Illusion — let's see where you stand in AI search**
   - Renders a purple gradient header, 3 onboarding steps, "Open Your Dashboard" CTA
5. Click **Open Your Dashboard** → should land on your Vercel URL's dashboard page while logged in (the JWT is still live from the signup call).

If the email doesn't show up:
- Check the backend logs for `[EMAIL] Failed to send welcome to …` — usually means `RESEND_API_KEY` is wrong or the from-address isn't on a verified domain.
- Check Resend dashboard → **Emails** tab — does the send appear at all? If yes, it's a deliverability problem (spam folder, DKIM record). If no, it's an API/config problem.

---

## 4. Gmail compliance check (the whole reason we did this)

Open the welcome email in Gmail's web UI. Look for the inbox-level **Unsubscribe** chip next to the sender name.
- If it's there → `List-Unsubscribe` + `List-Unsubscribe-Post` headers are being read correctly.
- If it's missing → open **Show original** and confirm both headers appear. Common causes: from-domain not DKIM-aligned, or the `List-Unsubscribe` URL isn't HTTPS (it must be, in prod).

Click the chip → Gmail fires a background POST to `{BACKEND_URL}/api/unsubscribe?token=…&list=all`. In backend logs you should see a 200 response. In the DB:

```sql
SELECT weekly_digest, mention_alerts, marketing_emails
  FROM notification_settings WHERE user_id = <your id>;
-- should now read  0 | 0 | 0
```

---

## 5. Manual unsubscribe link

Scroll to the welcome email footer, click **Unsubscribe from all emails**. You should land on:
- `{BACKEND_URL}/api/unsubscribe?token=…&list=all`
- Page renders a white card: "✓ You're unsubscribed" with a "Back to Illusion" button.
- DB check: same three flags = 0.

Click the link a second time → still loads the same confirmation page (idempotent).

Tamper with the token in the URL (add a character) → page returns 404 with "This unsubscribe link is invalid or expired". No DB change.

---

## 6. Per-list unsubscribe (weekly digest, mention alerts)

The weekly digest and mention alerts now also carry the List-Unsubscribe headers, scoped to their specific list:

- Weekly digest footer link points at `?list=weekly_digest` → only flips `weekly_digest` off.
- Mention alert footer link points at `?list=mention_alerts` → only flips that one off.

To test without waiting for Monday 9am UTC: from a Python shell in the backend —

```python
import asyncio
from email_service import send_weekly_digest
asyncio.run(send_weekly_digest(
    to_email="you@gmail.com",
    user_name="you",
    product_name="Notion",
    scan_summary={"total_queries":6,"mentions":2,"mention_rate":0.33,"top_sentiment":"positive","competitors_seen":["Obsidian"],"best_position":3,"sample_responses":[]},
    unsubscribe_token="<paste real token from DB>",
))
```

Click the footer Unsubscribe → only `weekly_digest` flips to 0, the other two stay.

---

## 7. Gotchas + follow-ups

- **Existing users**: the backfill runs once on boot and gives every pre-existing user a token. If you register yourself today, you're covered. If someone was in the DB before this deploy, they also get a token on first boot after the push.
- **Default for `marketing_emails`**: True. Opt-out only, per CAN-SPAM. Part 4 (marketing agent) will read this flag before sending.
- **Reply handling**: `noreply@contact.illusion.ai` currently goes nowhere. If someone replies, they're yelling into the void. Acceptable for now; add a support address in Part 3 (optional).
- **BACKEND_URL**: make sure this is the **public** URL when you go live. Emails always link to whatever `BACKEND_URL` was at the moment they were generated — wrong value here = broken one-click unsubscribe.
- **Part 2 is done when** all of Sections 3, 4, and 5 pass with real emails in your real Gmail inbox.
