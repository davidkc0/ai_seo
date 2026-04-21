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
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f3f4f6;margin:0;padding:40px 20px;">
    <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:40px 32px;text-align:center;">
            <div style="font-size:26px;font-weight:700;color:white;letter-spacing:-0.5px;">Illusion</div>
            <div style="color:#c7d2fe;margin-top:6px;font-size:14px;">Know where you stand in AI search</div>
        </div>

        <!-- Body -->
        <div style="padding:36px 32px;">
            <h1 style="color:#111827;font-size:22px;margin:0 0 12px;">Welcome to Illusion 👋</h1>
            <p style="color:#374151;font-size:16px;line-height:1.6;margin:0 0 20px;">
                You're on a 7-day free trial — no credit card needed. Here's how to get the most out of it:
            </p>

            <!-- Onboarding steps -->
            <ol style="color:#374151;font-size:15px;line-height:1.7;padding-left:20px;margin:0 0 28px;">
                <li style="margin-bottom:10px;">
                    <strong>Add your product.</strong> Give us the name, category, and 2–3 competitors.
                </li>
                <li style="margin-bottom:10px;">
                    <strong>Run your first scan.</strong> We query Claude, GPT, Gemini and Perplexity with real buyer-intent questions and report who gets mentioned — you or your competitors.
                </li>
                <li style="margin-bottom:10px;">
                    <strong>Watch the weekly digest.</strong> Every Monday we'll email a summary of how your AI visibility is trending, plus action items from Claude.
                </li>
            </ol>

            <!-- CTA -->
            <div style="text-align:center;margin:32px 0;">
                <a href="{dashboard_url}"
                   style="display:inline-block;background:#6366f1;color:white;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">
                    Open Your Dashboard →
                </a>
            </div>

            <p style="color:#6b7280;font-size:13px;line-height:1.6;margin:24px 0 0;border-top:1px solid #e5e7eb;padding-top:20px;">
                Replies to this address aren't monitored. If you need help, hit reply-all to any digest email or ping us from the in-app support link.
            </p>
        </div>

        <!-- Footer -->
        <div style="padding:20px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;text-align:center;">
            <p style="font-size:12px;color:#9ca3af;margin:0;line-height:1.6;">
                Illusion · You're getting this because you just signed up.<br>
                <a href="{unsubscribe_url}" style="color:#6b7280;text-decoration:underline;">Unsubscribe from all emails</a>
            </p>
        </div>
    </div>
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
        badge_color = "#22c55e"
        badge_text = "Strong presence 🚀"
    elif mention_rate >= 0.4:
        badge_color = "#f59e0b"
        badge_text = "Growing visibility 📈"
    elif mention_rate > 0:
        badge_color = "#3b82f6"
        badge_text = "Emerging mentions 🌱"
    else:
        badge_color = "#6b7280"
        badge_text = "Not yet mentioned 👀"

    sentiment_emoji = {"positive": "😊", "neutral": "😐", "negative": "😟"}.get(sentiment, "😐")
    position_text = f"#{best_position}" if best_position else "Not ranked"

    # Unsubscribe wiring. Falls back to /settings if no token was passed by the
    # caller — we still emit the email, but without one-click headers.
    unsubscribe_url = (
        build_unsubscribe_url(unsubscribe_token, "weekly_digest")
        if unsubscribe_token
        else f"{settings.app_url}/settings"
    )

    competitors_html = ""
    if competitors:
        comp_items = "".join(f"<li>{c}</li>" for c in competitors)
        competitors_html = f"""
        <div style="margin-top:20px;padding:16px;background:#f9fafb;border-radius:8px;">
            <strong>Competitors also mentioned this week:</strong>
            <ul style="margin:8px 0 0 0;padding-left:20px;color:#374151;">
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
        icon = "✅" if mentioned else "❌"
        pos_str = f" (#{pos})" if pos else ""
        sent_str = f" · {sent}" if mentioned else ""
        samples_html += f"""
        <div style="padding:12px 0;border-bottom:1px solid #e5e7eb;">
            <div style="font-size:13px;color:#6b7280;margin-bottom:4px;">{icon} {icon and 'Mentioned' or 'Not mentioned'}{pos_str}{sent_str}</div>
            <div style="font-size:14px;color:#374151;font-style:italic;">"{q[:120]}{'...' if len(q)>120 else ''}"</div>
        </div>
        """

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f3f4f6;margin:0;padding:40px 20px;">
    <div style="max-width:600px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:32px;text-align:center;">
            <div style="font-size:22px;font-weight:700;color:white;">Illusion</div>
            <div style="color:#c7d2fe;margin-top:4px;font-size:14px;">Weekly Digest · {week_label}</div>
        </div>
        
        <!-- Body -->
        <div style="padding:32px;">
            <p style="color:#374151;font-size:16px;">Hey {user_name or 'there'} 👋</p>
            <p style="color:#6b7280;margin-top:0;">Here's what AI said about <strong>{product_name}</strong> this week across {total_queries} queries.</p>
            
            <!-- Badge -->
            <div style="text-align:center;margin:24px 0;">
                <div style="display:inline-block;background:{badge_color};color:white;padding:12px 28px;border-radius:999px;font-size:18px;font-weight:600;">
                    {badge_text}
                </div>
            </div>

            <!-- Stats row -->
            <div style="display:flex;gap:16px;margin:24px 0;" class="stats">
                <div style="flex:1;text-align:center;padding:16px;background:#f9fafb;border-radius:8px;">
                    <div style="font-size:28px;font-weight:700;color:#6366f1;">{mention_count}/{total_queries}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">Queries with mention</div>
                </div>
                <div style="flex:1;text-align:center;padding:16px;background:#f9fafb;border-radius:8px;">
                    <div style="font-size:28px;font-weight:700;color:#6366f1;">{position_text}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">Best ranking</div>
                </div>
                <div style="flex:1;text-align:center;padding:16px;background:#f9fafb;border-radius:8px;">
                    <div style="font-size:28px;font-weight:700;color:#6366f1;">{sentiment_emoji}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">Avg sentiment</div>
                </div>
            </div>

            <!-- Query breakdown -->
            {f'<h3 style="color:#111827;margin:24px 0 12px;">Query Breakdown</h3>{samples_html}' if samples_html else ''}

            {competitors_html}

            <!-- CTA -->
            <div style="text-align:center;margin-top:32px;">
                <a href="{settings.app_url}/dashboard" 
                   style="display:inline-block;background:#6366f1;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;">
                    View Full Report →
                </a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="padding:20px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;text-align:center;">
            <p style="font-size:12px;color:#9ca3af;margin:0;line-height:1.6;">
                Illusion · <a href="{settings.app_url}/settings" style="color:#6b7280;text-decoration:underline;">Manage notifications</a> · <a href="{unsubscribe_url}" style="color:#6b7280;text-decoration:underline;">Unsubscribe</a>
            </p>
        </div>
    </div>
</body>
</html>
"""

    try:
        params = {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": f"🔍 AI Mention Digest: {product_name} — Week of {week_label}",
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

    sentiment_emoji = {"positive": "🟢", "neutral": "🟡", "negative": "🔴"}.get(sentiment, "🟡")

    unsubscribe_url = (
        build_unsubscribe_url(unsubscribe_token, "mention_alerts")
        if unsubscribe_token
        else f"{settings.app_url}/settings"
    )

    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,sans-serif;background:#f3f4f6;margin:0;padding:40px 20px;">
    <div style="max-width:500px;margin:0 auto;background:white;border-radius:12px;padding:32px;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <div style="font-size:32px;text-align:center;">🔔</div>
        <h2 style="text-align:center;color:#111827;">New AI Mention!</h2>
        <p style="color:#6b7280;text-align:center;">
            <strong>{product_name}</strong> was mentioned at position #{position}
        </p>
        <div style="background:#f9fafb;border-radius:8px;padding:16px;margin:20px 0;">
            <div style="font-size:12px;color:#6b7280;">Query asked:</div>
            <div style="color:#374151;margin-top:4px;font-style:italic;">"{query}"</div>
        </div>
        <div style="text-align:center;margin:8px 0;">
            {sentiment_emoji} Sentiment: <strong>{sentiment}</strong>
        </div>
        <div style="text-align:center;margin-top:24px;">
            <a href="{settings.app_url}/dashboard"
               style="background:#6366f1;color:white;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;">
                View Details →
            </a>
        </div>
        <p style="font-size:12px;color:#9ca3af;text-align:center;margin:24px 0 0;border-top:1px solid #e5e7eb;padding-top:16px;">
            Illusion · <a href="{unsubscribe_url}" style="color:#6b7280;text-decoration:underline;">Unsubscribe from alerts</a>
        </p>
    </div>
</body>
</html>
"""
    try:
        params = {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": f"🔔 {product_name} mentioned in AI response (#{position})",
            "html": html_body,
        }
        if unsubscribe_token:
            params["headers"] = _bulk_email_headers(unsubscribe_url)
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send alert: {e}")
        return False
