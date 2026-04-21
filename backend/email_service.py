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
<body style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;margin:0;padding:40px 20px;">
    <div style="max-width:600px;margin:0 auto;background:#111111;border-radius:14px;overflow:hidden;border:1px solid #1f1f1f;">
        <!-- Header -->
        <div style="padding:36px 32px;text-align:center;background:#0a0a0a;">
            <img src="{settings.app_url}/illusion_logo.png" alt="illusion" style="height:36px;width:auto;margin:0 auto;display:block;" />
            <div style="color:#ccc;margin-top:10px;font-size:13px;font-family:'JetBrains Mono',monospace;">Know where you stand in AI search</div>
        </div>

        <!-- Body -->
        <div style="padding:36px 32px;">
            <h1 style="color:#ededed;font-size:22px;margin:0 0 12px;font-weight:700;">Welcome to Illusion 👋</h1>
            <p style="color:#ccc;font-size:15px;line-height:1.65;margin:0 0 24px;">
                You're on a 7-day free trial — no credit card needed. Here's how to get the most out of it:
            </p>

            <!-- Onboarding steps -->
            <div style="margin:0 0 28px;">
                <div style="display:flex;margin-bottom:16px;">
                    <div style="min-width:28px;height:28px;background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:50%;color:#34d399;font-size:12px;font-weight:700;text-align:center;line-height:26px;font-family:'JetBrains Mono',monospace;">1</div>
                    <div style="margin-left:14px;color:#ededed;font-size:14px;line-height:1.65;"><strong>Add your product.</strong> <span style="color:#ccc;">Give us the name, category, and 2–3 competitors.</span></div>
                </div>
                <div style="display:flex;margin-bottom:16px;">
                    <div style="min-width:28px;height:28px;background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:50%;color:#34d399;font-size:12px;font-weight:700;text-align:center;line-height:26px;font-family:'JetBrains Mono',monospace;">2</div>
                    <div style="margin-left:14px;color:#ededed;font-size:14px;line-height:1.65;"><strong>Run your first scan.</strong> <span style="color:#ccc;">We query Claude, GPT, Gemini and Perplexity with real buyer-intent questions and report who gets mentioned.</span></div>
                </div>
                <div style="display:flex;">
                    <div style="min-width:28px;height:28px;background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:50%;color:#34d399;font-size:12px;font-weight:700;text-align:center;line-height:26px;font-family:'JetBrains Mono',monospace;">3</div>
                    <div style="margin-left:14px;color:#ededed;font-size:14px;line-height:1.65;"><strong>Watch the weekly digest.</strong> <span style="color:#ccc;">Every Monday we'll email a summary of how your AI visibility is trending, plus action items.</span></div>
                </div>
            </div>

            <!-- CTA -->
            <div style="text-align:center;margin:32px 0;">
                <a href="{dashboard_url}"
                   style="display:inline-block;background:#10b981;color:#fff;padding:13px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">
                    Open Your Dashboard →
                </a>
            </div>

            <p style="color:#555;font-size:13px;line-height:1.6;margin:24px 0 0;border-top:1px solid #1f1f1f;padding-top:20px;">
                Replies to this address aren't monitored. If you need help, hit reply-all to any digest email or ping us from the in-app support link.
            </p>
        </div>

        <!-- Footer -->
        <div style="padding:20px 32px;background:#0a0a0a;border-top:1px solid #1f1f1f;text-align:center;">
            <p style="font-size:12px;color:#555;margin:0;line-height:1.6;font-family:'JetBrains Mono',monospace;">
                illusion · You're getting this because you just signed up.<br>
                <a href="{unsubscribe_url}" style="color:#888;text-decoration:underline;">Unsubscribe from all emails</a>
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
        badge_color = "#10b981"
        badge_text = "Strong presence 🚀"
    elif mention_rate >= 0.4:
        badge_color = "#059669"
        badge_text = "Growing visibility 📈"
    elif mention_rate > 0:
        badge_color = "#34d399"
        badge_text = "Emerging mentions 🌱"
    else:
        badge_color = "#555"
        badge_text = "Not yet mentioned 👀"

    sentiment_emoji = {"positive": "😊", "neutral": "😐", "negative": "😟"}.get(sentiment, "😐")
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
        icon = "✅" if mentioned else "❌"
        pos_str = f" (#{pos})" if pos else ""
        sent_str = f" · {sent}" if mentioned else ""
        samples_html += f"""
        <div style="padding:12px 0;border-bottom:1px solid #1f1f1f;">
            <div style="font-size:13px;color:#888;margin-bottom:4px;font-family:'JetBrains Mono',monospace;">{icon} {icon and 'Mentioned' or 'Not mentioned'}{pos_str}{sent_str}</div>
            <div style="font-size:14px;color:#ededed;font-style:italic;">"{q[:120]}{'...' if len(q)>120 else ''}"</div>
        </div>
        """

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;margin:0;padding:40px 20px;">
    <div style="max-width:600px;margin:0 auto;background:#111111;border-radius:14px;overflow:hidden;border:1px solid #1f1f1f;">
        <!-- Header -->
        <div style="padding:28px 32px;text-align:center;background:#0a0a0a;">
            <img src="{settings.app_url}/illusion_logo.png" alt="illusion" style="height:32px;width:auto;margin:0 auto;display:block;" />
            <div style="color:#ccc;margin-top:8px;font-size:13px;font-family:'JetBrains Mono',monospace;">Weekly Digest · {week_label}</div>
        </div>
        
        <!-- Body -->
        <div style="padding:32px;">
            <p style="color:#ededed;font-size:16px;">Hey {user_name or 'there'} 👋</p>
            <p style="color:#ccc;margin-top:0;">Here's what AI said about <strong style="color:#ededed;">{product_name}</strong> this week across {total_queries} queries.</p>
            
            <!-- Badge -->
            <div style="text-align:center;margin:24px 0;">
                <div style="display:inline-block;background:{badge_color};color:white;padding:10px 24px;border-radius:999px;font-size:16px;font-weight:700;">
                    {badge_text}
                </div>
            </div>

            <!-- Stats row -->
            <div style="margin:24px 0;">
                <!--[if mso]><table role="presentation" width="100%"><tr><td width="33%" valign="top"><![endif]-->
                <div style="display:inline-block;width:31%;text-align:center;padding:16px 4px;background:#181818;border-radius:10px;border:1px solid #1f1f1f;vertical-align:top;">
                    <div style="font-size:26px;font-weight:800;color:#10b981;font-family:'JetBrains Mono',monospace;">{mention_count}/{total_queries}</div>
                    <div style="font-size:11px;color:#555;margin-top:4px;font-family:'JetBrains Mono',monospace;">Mentions</div>
                </div>
                <!--[if mso]></td><td width="2%"></td><td width="33%" valign="top"><![endif]-->
                <div style="display:inline-block;width:31%;text-align:center;padding:16px 4px;background:#181818;border-radius:10px;border:1px solid #1f1f1f;vertical-align:top;margin:0 2%;">
                    <div style="font-size:26px;font-weight:800;color:#10b981;font-family:'JetBrains Mono',monospace;">{position_text}</div>
                    <div style="font-size:11px;color:#555;margin-top:4px;font-family:'JetBrains Mono',monospace;">Best rank</div>
                </div>
                <!--[if mso]></td><td width="2%"></td><td width="33%" valign="top"><![endif]-->
                <div style="display:inline-block;width:31%;text-align:center;padding:16px 4px;background:#181818;border-radius:10px;border:1px solid #1f1f1f;vertical-align:top;">
                    <div style="font-size:26px;font-weight:800;color:#10b981;">{sentiment_emoji}</div>
                    <div style="font-size:11px;color:#555;margin-top:4px;font-family:'JetBrains Mono',monospace;">Sentiment</div>
                </div>
                <!--[if mso]></tr></table><![endif]-->
            </div>

            <!-- Query breakdown -->
            {f'<h3 style="color:#ededed;margin:24px 0 12px;font-size:15px;font-weight:700;">Query Breakdown</h3>{samples_html}' if samples_html else ''}

            {competitors_html}

            <!-- CTA -->
            <div style="text-align:center;margin-top:32px;">
                <a href="{settings.app_url}/dashboard" 
                   style="display:inline-block;background:#10b981;color:#fff;padding:13px 28px;border-radius:10px;text-decoration:none;font-weight:700;">
                    View Full Report →
                </a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="padding:20px 32px;background:#0a0a0a;border-top:1px solid #1f1f1f;text-align:center;">
            <p style="font-size:12px;color:#555;margin:0;line-height:1.6;font-family:'JetBrains Mono',monospace;">
                illusion · <a href="{settings.app_url}/settings" style="color:#888;text-decoration:underline;">Manage notifications</a> · <a href="{unsubscribe_url}" style="color:#888;text-decoration:underline;">Unsubscribe</a>
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
<body style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;margin:0;padding:40px 20px;">
    <div style="max-width:500px;margin:0 auto;background:#111111;border-radius:14px;overflow:hidden;border:1px solid #1f1f1f;">
        <!-- Header -->
        <div style="padding:24px 32px;text-align:center;background:#0a0a0a;">
            <img src="{settings.app_url}/illusion_logo.png" alt="illusion" style="height:30px;width:auto;margin:0 auto;display:block;" />
        </div>
        <div style="padding:0 32px 32px;">
            <div style="font-size:32px;text-align:center;">🔔</div>
            <h2 style="text-align:center;color:#ededed;font-size:20px;font-weight:700;">New AI Mention!</h2>
            <p style="color:#ccc;text-align:center;">
                <strong style="color:#ededed;">{product_name}</strong> was mentioned at position <span style="color:#10b981;font-weight:700;">#{position}</span>
            </p>
            <div style="background:#181818;border-radius:10px;border:1px solid #1f1f1f;padding:16px;margin:20px 0;">
                <div style="font-size:11px;color:#555;font-family:'JetBrains Mono',monospace;">Query asked:</div>
                <div style="color:#ededed;margin-top:4px;font-style:italic;font-size:14px;">"{query}"</div>
            </div>
            <div style="text-align:center;margin:8px 0;color:#ccc;">
                {sentiment_emoji} Sentiment: <strong style="color:#ededed;">{sentiment}</strong>
            </div>
            <div style="text-align:center;margin-top:24px;">
                <a href="{settings.app_url}/dashboard"
                   style="display:inline-block;background:#10b981;color:#fff;padding:13px 28px;border-radius:10px;text-decoration:none;font-weight:700;">
                    View Details →
                </a>
            </div>
        </div>
        <!-- Footer -->
        <div style="padding:20px 32px;background:#0a0a0a;border-top:1px solid #1f1f1f;text-align:center;">
            <p style="font-size:12px;color:#555;margin:0;font-family:'JetBrains Mono',monospace;">
                illusion · <a href="{unsubscribe_url}" style="color:#888;text-decoration:underline;">Unsubscribe from alerts</a>
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
