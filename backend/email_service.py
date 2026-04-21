"""
Email digest service using Resend API.
"""
import resend
from datetime import datetime, timedelta, timezone
from config import settings
from typing import Optional

resend.api_key = settings.resend_api_key


def send_weekly_digest(
    to_email: str,
    user_name: str,
    product_name: str,
    scan_summary: dict,
    week_start: Optional[datetime] = None,
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
    """
    if not settings.resend_api_key or settings.resend_api_key == "re_your_key_here":
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
            <div style="font-size:22px;font-weight:700;color:white;">AI Mention Tracker</div>
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
            <p style="font-size:12px;color:#9ca3af;margin:0;">
                AI Mention Tracker · <a href="{settings.app_url}/settings" style="color:#6366f1;">Manage notifications</a>
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
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send digest: {e}")
        return False


def send_mention_alert(to_email: str, product_name: str, query: str, position: int, sentiment: str) -> bool:
    """Send an immediate alert when product gets a new mention."""
    if not settings.resend_api_key or settings.resend_api_key == "re_your_key_here":
        print(f"[EMAIL] Resend not configured. Would send alert to {to_email}")
        return False

    sentiment_emoji = {"positive": "🟢", "neutral": "🟡", "negative": "🔴"}.get(sentiment, "🟡")
    
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
        resend.Emails.send(params)
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send alert: {e}")
        return False
