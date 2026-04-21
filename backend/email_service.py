"""
Email service using Resend API — transactional (welcome) + bulk (digest, alerts).

All bulk sends include RFC 8058 List-Unsubscribe + One-Click headers so Gmail
and Yahoo count us as a compliant bulk sender (required since Feb 2024).
"""
import resend
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from config import settings
from typing import Optional

resend.api_key = settings.resend_api_key

# Logo hosted in frontend/public/ — served at root by Vite/Vercel.
# Use app_url so it resolves to the live domain in prod.
LOGO_URL = f"{settings.app_url}/illusion_logo.png"


def _is_resend_configured() -> bool:
    return bool(settings.resend_api_key) and settings.resend_api_key != "re_your_key_here"


def build_unsubscribe_url(token: str, list_name: str) -> str:
    """One-click unsubscribe endpoint on the backend. list_name is a short key
    like 'weekly_digest', 'mention_alerts', 'marketing', or 'all'."""
    qs = urlencode({"token": token, "list": list_name})
    return f"{settings.backend_url}/api/unsubscribe?{qs}"


def _bulk_email_headers(unsubscribe_url: str) -> dict:
    """Headers required for Gmail/Yahoo bulk-sender compliance.

    - List-Unsubscribe: URL the mail client links to
    - List-Unsubscribe-Post: tells the client it can POST to that URL to
      unsubscribe in one click (no user confirmation page)
    """
    return {
        "List-Unsubscribe": f"<{unsubscribe_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def send_welcome_email(to_email: str, unsubscribe_token: str) -> bool:
    """Send the onboarding email fired off by POST /api/auth/register.

    Transactional, so technically doesn't need List-Unsubscribe headers — but
    we include a visible footer link anyway so users can disable future bulk
    mail (weekly digest) in one click, which is good hygiene for deliverability.
    """
    if not _is_resend_configured():
        print(f"[EMAIL] Resend not configured. Would send welcome to {to_email}")
        return False

    dashboard_url = f"{settings.app_url}/dashboard"
    # Welcome is transactional, but offer a path to opt out of everything else.
    unsubscribe_url = build_unsubscribe_url(unsubscribe_token, "all")

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;margin:0;padding:40px 20px;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#111111;border-radius:14px;border:1px solid #1f1f1f;overflow:hidden;">
  <tr><td style="padding:32px;text-align:center;background:#0a0a0a;">
    <img src="{LOGO_URL}" alt="illusion" width="160" height="48" style="height:28px;width:auto;margin:0 auto;display:block;" />
    <p style="color:#ccc;margin:10px 0 0;font-size:13px;font-family:'JetBrains Mono',monospace;">Know where you stand in AI search</p>
  </td></tr>
  <tr><td style="padding:36px 32px;">
    <h1 style="color:#ededed;font-size:22px;margin:0 0 12px;font-weight:700;">Welcome to Illusion</h1>
    <p style="color:#ccc;font-size:15px;line-height:1.65;margin:0 0 24px;">You're on a 7-day free trial &mdash; no credit card needed. Here's how to get the most out of it:</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding:0 0 16px;">
        <table cellpadding="0" cellspacing="0"><tr>
          <td style="width:28px;height:28px;background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:50%;color:#34d399;font-size:12px;font-weight:700;text-align:center;line-height:28px;font-family:'JetBrains Mono',monospace;vertical-align:top;" width="28" height="28">1</td>
          <td style="padding-left:14px;color:#ededed;font-size:14px;line-height:1.65;"><strong>Add your product.</strong> <span style="color:#ccc;">Name, category, and 2&ndash;3 competitors.</span></td>
        </tr></table>
      </td></tr>
      <tr><td style="padding:0 0 16px;">
        <table cellpadding="0" cellspacing="0"><tr>
          <td style="width:28px;height:28px;background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:50%;color:#34d399;font-size:12px;font-weight:700;text-align:center;line-height:28px;font-family:'JetBrains Mono',monospace;vertical-align:top;" width="28" height="28">2</td>
          <td style="padding-left:14px;color:#ededed;font-size:14px;line-height:1.65;"><strong>Run your first scan.</strong> <span style="color:#ccc;">We query Claude, GPT, Gemini and Perplexity with real buyer-intent questions.</span></td>
        </tr></table>
      </td></tr>
      <tr><td>
        <table cellpadding="0" cellspacing="0"><tr>
          <td style="width:28px;height:28px;background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:50%;color:#34d399;font-size:12px;font-weight:700;text-align:center;line-height:28px;font-family:'JetBrains Mono',monospace;vertical-align:top;" width="28" height="28">3</td>
          <td style="padding-left:14px;color:#ededed;font-size:14px;line-height:1.65;"><strong>Watch the weekly digest.</strong> <span style="color:#ccc;">Every Monday we email a summary of your AI visibility trending.</span></td>
        </tr></table>
      </td></tr>
    </table>
    <div style="text-align:center;margin:32px 0;">
      <a href="{dashboard_url}" style="display:inline-block;background:#10b981;color:#fff;padding:13px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">Open Your Dashboard &rarr;</a>
    </div>
    <p style="color:#555;font-size:13px;line-height:1.6;margin:24px 0 0;border-top:1px solid #1f1f1f;padding-top:20px;">Replies to this address aren't monitored. If you need help, ping us from the in-app support link.</p>
  </td></tr>
  <tr><td style="padding:20px 32px;background:#0a0a0a;border-top:1px solid #1f1f1f;text-align:center;">
    <p style="font-size:12px;color:#555;margin:0;line-height:1.6;font-family:'JetBrains Mono',monospace;">illusion &middot; You're getting this because you just signed up.<br><a href="{unsubscribe_url}" style="color:#888;text-decoration:underline;">Unsubscribe from all emails</a></p>
  </td></tr>
</table>
</body>
</html>
"""

    try:
        params = {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": "Welcome to Illusion — let's see where you stand in AI search",
            "html": html_body,
            # Even though this is transactional, include the header so Gmail
            # groups us cleanly and the "Unsubscribe" chip appears if the user
            # marks a later mail as spam.
            "headers": _bulk_email_headers(unsubscribe_url),
        }
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send welcome to {to_email}: {e}")
        return False


def send_weekly_digest(
    to_email: str,
    user_name: str,
    product_name: str,
    scan_summary: dict,
    week_start: Optional[datetime] = None,
    unsubscribe_token: Optional[str] = None,
) -> bool:
    """
    Send a weekly digest email showing AI mention results.

    scan_summary = {
        "total_queries": int,
        "mentions": int,
        "mention_rate": float,
        "top_sentiment": str,
        "competitors_seen": list[str],
        "best_position": int | None,
        "sample_responses": list[dict]  # {query, mentioned, position, sentiment}
    }

    unsubscribe_token: the user's User.unsubscribe_token. When provided we wire
    up the List-Unsubscribe / one-click headers Gmail requires for bulk mail.
    Old callers that don't pass one will still work but fall back to the
    settings page (not compliant — fix callers).
    """
    if not _is_resend_configured():
        print(f"[EMAIL] Resend not configured. Would send digest to {to_email}")
        return False

    week_label = (week_start or datetime.now(timezone.utc)).strftime("%B %d, %Y")

    mention_count = scan_summary.get("mentions", 0)
    total_queries = scan_summary.get("total_queries", 0)
    mention_rate = scan_summary.get("mention_rate", 0)
    sentiment = scan_summary.get("top_sentiment", "neutral")
    competitors = scan_summary.get("competitors_seen", [])
    best_position = scan_summary.get("best_position")

    # Build mention badge
    if mention_rate >= 0.7:
        badge_color = "#10b981"
        badge_text = "Strong presence"
    elif mention_rate >= 0.4:
        badge_color = "#059669"
        badge_text = "Growing visibility"
    elif mention_rate > 0:
        badge_color = "#34d399"
        badge_text = "Emerging mentions"
    else:
        badge_color = "#555"
        badge_text = "Not yet mentioned"

    sentiment_label = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}.get(sentiment, "Neutral")
    sentiment_color = {"positive": "#10b981", "neutral": "#888", "negative": "#ef4444"}.get(sentiment, "#888")
    position_text = f"#{best_position}" if best_position else "—"

    # Unsubscribe wiring. Falls back to /settings if no token was passed by the
    # caller — we still emit the email, but without one-click headers.
    unsubscribe_url = (
        build_unsubscribe_url(unsubscribe_token, "weekly_digest")
        if unsubscribe_token
        else f"{settings.app_url}/settings"
    )

    competitors_html = ""
    if competitors:
        comp_items = "".join(f"<li style='margin-bottom:4px;'>{c}</li>" for c in competitors)
        competitors_html = f"""
        <div style="margin-top:20px;padding:16px;background:#181818;border-radius:10px;border:1px solid #1f1f1f;">
            <strong style="color:#ededed;font-size:13px;">Competitors also mentioned this week:</strong>
            <ul style="margin:8px 0 0 0;padding-left:20px;color:#888;font-size:13px;">
                {comp_items}
            </ul>
        </div>
        """

    # Build sample results
    samples_html = ""
    for s in scan_summary.get("sample_responses", [])[:3]:
        q = s.get("query", "")
        mentioned = s.get("mentioned", False)
        pos = s.get("position")
        sent = s.get("sentiment", "neutral")
        dot_color = "#10b981" if mentioned else "#ef4444"
        label = "Mentioned" if mentioned else "Not mentioned"
        pos_str = f" (#{pos})" if pos else ""
        sent_str = f" &middot; {sent}" if mentioned else ""
        samples_html += f"""
        <div style="padding:12px 0;border-bottom:1px solid #1f1f1f;">
            <div style="font-size:13px;color:#888;margin-bottom:4px;font-family:'JetBrains Mono',monospace;"><span style="color:{dot_color};">&#9679;</span> {label}{pos_str}{sent_str}</div>
            <div style="font-size:14px;color:#ededed;font-style:italic;">"{q[:120]}{'...' if len(q)>120 else ''}"</div>
        </div>
        """

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;margin:0;padding:40px 20px;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#111111;border-radius:14px;border:1px solid #1f1f1f;overflow:hidden;">
  <tr><td style="padding:28px 32px;text-align:center;background:#0a0a0a;">
    <img src="{LOGO_URL}" alt="illusion" width="160" height="48" style="height:28px;width:auto;margin:0 auto;display:block;" />
    <p style="color:#ccc;margin:8px 0 0;font-size:13px;font-family:'JetBrains Mono',monospace;">Weekly Digest &middot; {week_label}</p>
  </td></tr>
  <tr><td style="padding:32px;">
    <p style="color:#ededed;font-size:16px;margin:0 0 4px;">Hey {user_name or 'there'},</p>
    <p style="color:#ccc;margin:0 0 20px;">Here's what AI said about <strong style="color:#ededed;">{product_name}</strong> this week across {total_queries} queries.</p>
    <div style="text-align:center;margin:24px 0;">
      <span style="display:inline-block;background:{badge_color};color:#fff;padding:10px 24px;border-radius:999px;font-size:14px;font-weight:700;">{badge_text}</span>
    </div>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;">
      <tr>
        <td width="32%" style="text-align:center;padding:16px 6px;background:#181818;border-radius:10px;border:1px solid #1f1f1f;">
          <div style="font-size:24px;font-weight:800;color:#10b981;font-family:'JetBrains Mono',monospace;">{mention_count}/{total_queries}</div>
          <div style="font-size:11px;color:#555;margin-top:4px;font-family:'JetBrains Mono',monospace;">Mentions</div>
        </td>
        <td width="2%"></td>
        <td width="32%" style="text-align:center;padding:16px 6px;background:#181818;border-radius:10px;border:1px solid #1f1f1f;">
          <div style="font-size:24px;font-weight:800;color:#10b981;font-family:'JetBrains Mono',monospace;">{position_text}</div>
          <div style="font-size:11px;color:#555;margin-top:4px;font-family:'JetBrains Mono',monospace;">Best rank</div>
        </td>
        <td width="2%"></td>
        <td width="32%" style="text-align:center;padding:16px 6px;background:#181818;border-radius:10px;border:1px solid #1f1f1f;">
          <div style="font-size:14px;font-weight:700;color:{sentiment_color};margin-top:4px;">{sentiment_label}</div>
          <div style="font-size:11px;color:#555;margin-top:4px;font-family:'JetBrains Mono',monospace;">Sentiment</div>
        </td>
      </tr>
    </table>
    {f'<h3 style="color:#ededed;margin:24px 0 12px;font-size:15px;font-weight:700;">Query Breakdown</h3>{samples_html}' if samples_html else ''}
    {competitors_html}
    <div style="text-align:center;margin-top:32px;">
      <a href="{settings.app_url}/dashboard" style="display:inline-block;background:#10b981;color:#fff;padding:13px 28px;border-radius:10px;text-decoration:none;font-weight:700;">View Full Report &rarr;</a>
    </div>
  </td></tr>
  <tr><td style="padding:20px 32px;background:#0a0a0a;border-top:1px solid #1f1f1f;text-align:center;">
    <p style="font-size:12px;color:#555;margin:0;line-height:1.6;font-family:'JetBrains Mono',monospace;">illusion &middot; <a href="{settings.app_url}/settings" style="color:#888;text-decoration:underline;">Manage notifications</a> &middot; <a href="{unsubscribe_url}" style="color:#888;text-decoration:underline;">Unsubscribe</a></p>
  </td></tr>
</table>
</body>
</html>
"""

    try:
        params = {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": f"AI Mention Digest: {product_name} — Week of {week_label}",
            "html": html_body,
        }
        # Only attach one-click headers when we have a real token — Gmail
        # requires the URL in List-Unsubscribe to actually work without login.
        if unsubscribe_token:
            params["headers"] = _bulk_email_headers(unsubscribe_url)
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send digest: {e}")
        return False


def send_mention_alert(
    to_email: str,
    product_name: str,
    query: str,
    position: int,
    sentiment: str,
    unsubscribe_token: Optional[str] = None,
) -> bool:
    """Send an immediate alert when product gets a new mention."""
    if not _is_resend_configured():
        print(f"[EMAIL] Resend not configured. Would send alert to {to_email}")
        return False

    sent_color = {"positive": "#10b981", "neutral": "#888", "negative": "#ef4444"}.get(sentiment, "#888")
    sent_label = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}.get(sentiment, "Neutral")

    unsubscribe_url = (
        build_unsubscribe_url(unsubscribe_token, "mention_alerts")
        if unsubscribe_token
        else f"{settings.app_url}/settings"
    )

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;margin:0;padding:40px 20px;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:500px;margin:0 auto;background:#111111;border-radius:14px;border:1px solid #1f1f1f;overflow:hidden;">
  <tr><td style="padding:24px 32px;text-align:center;background:#0a0a0a;">
    <img src="{LOGO_URL}" alt="illusion" width="140" height="42" style="height:26px;width:auto;margin:0 auto;display:block;" />
  </td></tr>
  <tr><td style="padding:0 32px 32px;text-align:center;">
    <h2 style="color:#ededed;font-size:20px;font-weight:700;margin:0 0 8px;">New AI Mention</h2>
    <p style="color:#ccc;margin:0 0 20px;"><strong style="color:#ededed;">{product_name}</strong> was mentioned at position <span style="color:#10b981;font-weight:700;">#{position}</span></p>
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#181818;border-radius:10px;border:1px solid #1f1f1f;">
      <tr><td style="padding:16px;text-align:left;">
        <div style="font-size:11px;color:#555;font-family:'JetBrains Mono',monospace;">Query asked:</div>
        <div style="color:#ededed;margin-top:4px;font-style:italic;font-size:14px;">"{query}"</div>
      </td></tr>
    </table>
    <p style="color:#ccc;margin:16px 0 0;">Sentiment: <strong style="color:{sent_color};">{sent_label}</strong></p>
    <div style="margin-top:24px;">
      <a href="{settings.app_url}/dashboard" style="display:inline-block;background:#10b981;color:#fff;padding:13px 28px;border-radius:10px;text-decoration:none;font-weight:700;">View Details &rarr;</a>
    </div>
  </td></tr>
  <tr><td style="padding:20px 32px;background:#0a0a0a;border-top:1px solid #1f1f1f;text-align:center;">
    <p style="font-size:12px;color:#555;margin:0;font-family:'JetBrains Mono',monospace;">illusion &middot; <a href="{unsubscribe_url}" style="color:#888;text-decoration:underline;">Unsubscribe from alerts</a></p>
  </td></tr>
</table>
</body>
</html>
"""
    try:
        params = {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": f"{product_name} mentioned in AI response (#{position})",
            "html": html_body,
        }
        if unsubscribe_token:
            params["headers"] = _bulk_email_headers(unsubscribe_url)
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send alert: {e}")
        return False
