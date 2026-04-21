"""
One-click unsubscribe endpoint — RFC 8058 compliant.

Handles both:
- GET  /api/unsubscribe?token=X&list=Y → renders an HTML confirmation page
  (what users see when they click the "Unsubscribe" link in an email footer).
- POST /api/unsubscribe?token=X&list=Y → silent, returns 200 text/plain
  (what Gmail / Yahoo clients hit behind the scenes when the user taps the
  "Unsubscribe" chip in their inbox, because of List-Unsubscribe-Post: One-Click).

Both paths are idempotent — calling twice is harmless.

Valid `list` values:
- weekly_digest  → NotificationSettings.weekly_digest = False
- mention_alerts → NotificationSettings.mention_alerts = False
- marketing     → NotificationSettings.marketing_emails = False
- all           → all three above = False

Invalid token returns a generic 404 page so we don't leak whether a token
exists. Invalid `list` falls back to `all` (safer: if the mail client is
ambiguous, opt the user out of everything).
"""
from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User, NotificationSettings
from config import settings

router = APIRouter(prefix="/api/unsubscribe", tags=["unsubscribe"])


_VALID_LISTS = {"weekly_digest", "mention_alerts", "marketing", "all"}


async def _apply_unsubscribe(
    db: AsyncSession, token: str, list_name: str
) -> tuple[bool, str]:
    """Flip the relevant flag(s) off. Returns (ok, normalized_list_name).

    ok=False means the token didn't match a user — caller should render 404.
    """
    if list_name not in _VALID_LISTS:
        list_name = "all"

    user_row = await db.execute(
        select(User).where(User.unsubscribe_token == token)
    )
    user = user_row.scalar_one_or_none()
    if not user:
        return False, list_name

    settings_row = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == user.id)
    )
    notif = settings_row.scalar_one_or_none()
    if not notif:
        # No row yet (shouldn't normally happen — register creates one) —
        # create one in the opted-out state.
        notif = NotificationSettings(
            user_id=user.id,
            weekly_digest=True,
            mention_alerts=False,
            marketing_emails=True,
        )
        db.add(notif)

    if list_name == "weekly_digest":
        notif.weekly_digest = False
    elif list_name == "mention_alerts":
        notif.mention_alerts = False
    elif list_name == "marketing":
        notif.marketing_emails = False
    else:  # all
        notif.weekly_digest = False
        notif.mention_alerts = False
        notif.marketing_emails = False

    await db.commit()
    return True, list_name


_FRIENDLY_LIST_NAMES = {
    "weekly_digest": "weekly digest emails",
    "mention_alerts": "mention alert emails",
    "marketing": "product and marketing emails",
    "all": "all Illusion emails",
}


def _confirmation_page(list_name: str) -> str:
    friendly = _FRIENDLY_LIST_NAMES.get(list_name, "Illusion emails")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Unsubscribed · Illusion</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #f3f4f6; margin: 0; padding: 60px 20px; color: #111827; }}
        .card {{ max-width: 480px; margin: 0 auto; background: white; border-radius: 12px;
                padding: 40px 32px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .check {{ font-size: 40px; margin-bottom: 16px; }}
        h1 {{ font-size: 22px; margin: 0 0 12px; }}
        p  {{ color: #6b7280; line-height: 1.6; margin: 0 0 20px; }}
        a.btn {{ display: inline-block; background: #6366f1; color: white; padding: 10px 22px;
                border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; }}
        .muted {{ font-size: 12px; color: #9ca3af; margin-top: 28px; }}
        .muted a {{ color: #6b7280; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="check">✓</div>
        <h1>You're unsubscribed</h1>
        <p>You won't receive {friendly} from Illusion anymore.</p>
        <a class="btn" href="{settings.app_url}">Back to Illusion</a>
        <p class="muted">
            Changed your mind? <a href="{settings.app_url}/settings">Log in and re-enable notifications</a>.
        </p>
    </div>
</body>
</html>"""


_NOT_FOUND_PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Link expired · Illusion</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: #f3f4f6;
               padding: 60px 20px; color: #111827; }}
        .card {{ max-width: 480px; margin: 0 auto; background: white; border-radius: 12px;
                padding: 40px 32px; text-align: center; }}
        a {{ color: #6366f1; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>This unsubscribe link is invalid or expired</h1>
        <p>If you're still getting mail from us, log in and adjust your
        <a href="{settings.app_url}/settings">notification settings</a> directly.</p>
    </div>
</body>
</html>"""


@router.get("", response_class=HTMLResponse)
async def unsubscribe_get(
    token: str,
    list: str = "all",
    db: AsyncSession = Depends(get_db),
):
    """User-facing unsubscribe link (clicked from email footer)."""
    ok, normalized = await _apply_unsubscribe(db, token, list)
    if not ok:
        return HTMLResponse(content=_NOT_FOUND_PAGE, status_code=404)
    return HTMLResponse(content=_confirmation_page(normalized), status_code=200)


@router.post("", response_class=PlainTextResponse)
async def unsubscribe_post(
    token: str,
    list: str = "all",
    db: AsyncSession = Depends(get_db),
):
    """RFC 8058 one-click endpoint — hit by Gmail/Yahoo when the user clicks
    the inbox-level "Unsubscribe" chip. Must respond quickly with 200."""
    ok, _ = await _apply_unsubscribe(db, token, list)
    if not ok:
        # Return 200 even on token miss — we don't want mail clients to retry
        # or flag the list, and we've already avoided leaking existence.
        return PlainTextResponse("ok", status_code=200)
    return PlainTextResponse("unsubscribed", status_code=200)
