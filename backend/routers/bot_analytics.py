"""
API endpoints for AI bot log analysis (CDN integration).

Paid plans only — connects to user's Cloudflare account, syncs bot traffic,
and serves analytics data to the dashboard.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import User, CdnConnection, BotVisit
from auth import get_current_user
from config import settings as app_settings
import bot_analytics
import vercel_analytics

router = APIRouter(prefix="/api/bot-analytics", tags=["bot-analytics"])


# ── Request / Response schemas ─────────────────────────────────────────

class ConnectCloudflareRequest(BaseModel):
    api_token: str
    zone_id: str
    zone_name: str


class ConnectVercelRequest(BaseModel):
    api_token: str
    project_id: str
    project_name: str


class SyncRequest(BaseModel):
    days: int = 7  # how far back to sync


# ── Helpers ────────────────────────────────────────────────────────────

def _require_paid(user: User):
    """Raise 403 if user is on the free plan."""
    if user.plan == "free":
        raise HTTPException(
            status_code=403,
            detail="Bot analytics requires a paid plan. Upgrade to Starter or Growth."
        )


# ── Endpoints ──────────────────────────────────────────────────────────

@router.post("/connect")
async def connect_cloudflare(
    body: ConnectCloudflareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Cloudflare zone for bot traffic analysis."""
    _require_paid(current_user)

    # Verify the token works
    check = await asyncio.to_thread(bot_analytics.verify_token, body.api_token)
    if not check["valid"]:
        raise HTTPException(status_code=400, detail=f"Invalid Cloudflare token: {check['error']}")

    # Check for existing connection to same zone
    existing = await db.execute(
        select(CdnConnection).where(
            CdnConnection.user_id == current_user.id,
            CdnConnection.zone_id == body.zone_id,
            CdnConnection.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This zone is already connected.")

    conn = CdnConnection(
        user_id=current_user.id,
        provider="cloudflare",
        zone_id=body.zone_id,
        zone_name=body.zone_name,
        api_token=body.api_token,
        is_active=True,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    return {
        "id": conn.id,
        "provider": conn.provider,
        "zone_name": conn.zone_name,
        "message": "Connected successfully. Syncing bot traffic data now...",
    }


@router.get("/zones")
async def list_zones(
    api_token: str,
    current_user: User = Depends(get_current_user),
):
    """List available Cloudflare zones for a given API token."""
    _require_paid(current_user)
    zones = await asyncio.to_thread(bot_analytics.list_zones, api_token)
    if not zones:
        raise HTTPException(status_code=400, detail="No zones found. Check your API token permissions (Zone:Read required).")
    return zones


@router.get("/vercel-projects")
async def list_vercel_projects(
    api_token: str,
    current_user: User = Depends(get_current_user),
):
    """List available Vercel projects for a given API token.

    Also verifies the token first so the UI can show a meaningful error if
    the token is invalid or the account is missing scope.
    """
    _require_paid(current_user)

    check = await asyncio.to_thread(vercel_analytics.verify_token, api_token)
    if not check["valid"]:
        raise HTTPException(status_code=400, detail=f"Invalid Vercel token: {check['error']}")

    projects = await asyncio.to_thread(vercel_analytics.list_projects, api_token)
    if not projects:
        raise HTTPException(
            status_code=400,
            detail="No projects found for this token. Check that the token has access to your team and that at least one project exists.",
        )
    return projects


@router.post("/connect-vercel")
async def connect_vercel(
    body: ConnectVercelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a Vercel project for bot traffic analysis via Log Drains.

    Flow:
      1. Verify the token.
      2. Check we don't already have an active drain for this project.
      3. Create the CdnConnection row first so we can use its primary key
         in the webhook URL.
      4. Register the Log Drain on Vercel pointing at our public webhook.
      5. Persist the returned drain_id (used later for cleanup on disconnect).

    Note: requires Vercel Pro or Enterprise — Log Drains are unavailable on
    Hobby. Vercel returns a 4xx in that case which we surface to the user.
    """
    _require_paid(current_user)

    # Verify token before doing any DB writes
    check = await asyncio.to_thread(vercel_analytics.verify_token, body.api_token)
    if not check["valid"]:
        raise HTTPException(status_code=400, detail=f"Invalid Vercel token: {check['error']}")

    # Reject duplicate active connection to the same project
    existing = await db.execute(
        select(CdnConnection).where(
            CdnConnection.user_id == current_user.id,
            CdnConnection.provider == "vercel",
            CdnConnection.project_id == body.project_id,
            CdnConnection.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This Vercel project is already connected.")

    # Create the row first so we have an ID for the webhook URL
    webhook_secret = vercel_analytics.generate_webhook_secret()
    conn = CdnConnection(
        user_id=current_user.id,
        provider="vercel",
        project_id=body.project_id,
        zone_name=body.project_name,  # re-use zone_name as human-readable label
        api_token=body.api_token,
        webhook_secret=webhook_secret,
        is_active=True,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)

    # Build the public webhook URL Vercel will POST to
    base = app_settings.backend_url.rstrip("/")
    webhook_url = f"{base}/api/webhooks/vercel-logs/{conn.id}"

    # Register the drain on Vercel
    drain = await asyncio.to_thread(
        vercel_analytics.register_drain,
        api_token=body.api_token,
        project_id=body.project_id,
        webhook_url=webhook_url,
        webhook_secret=webhook_secret,
    )

    if not drain["success"]:
        # Roll back the row so the user can retry cleanly
        await db.delete(conn)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to register Vercel Log Drain: {drain['error']}. "
                   f"Note: Log Drains require a Vercel Pro or Enterprise plan.",
        )

    conn.drain_id = drain["drain_id"]
    await db.commit()

    return {
        "id": conn.id,
        "provider": conn.provider,
        "zone_name": conn.zone_name,
        "drain_id": conn.drain_id,
        "message": "Connected successfully. Bot traffic will start streaming in within a few minutes.",
    }


@router.get("/connections")
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's active CDN connections."""
    result = await db.execute(
        select(CdnConnection).where(
            CdnConnection.user_id == current_user.id,
            CdnConnection.is_active == True,
        )
    )
    connections = result.scalars().all()
    return [
        {
            "id": c.id,
            "provider": c.provider,
            "zone_name": c.zone_name,
            "project_id": c.project_id,
            "last_synced_at": c.last_synced_at,
            "created_at": c.created_at,
        }
        for c in connections
    ]


@router.delete("/connections/{connection_id}")
async def disconnect_cdn(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect a CDN integration.

    For Vercel connections we also delete the Log Drain on Vercel's side so
    we stop receiving webhook traffic and don't leak drains under the user's
    account. We only soft-delete the row (is_active=False) — keeps historical
    bot_visits queryable.
    """
    result = await db.execute(
        select(CdnConnection).where(
            CdnConnection.id == connection_id,
            CdnConnection.user_id == current_user.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    # Best-effort: tear down the Vercel Log Drain so Vercel stops pushing logs.
    # We don't fail the disconnect if the API call fails — the user wants out
    # regardless and the drain can be cleaned up manually from Vercel's UI.
    if conn.provider == "vercel" and conn.drain_id:
        try:
            await asyncio.to_thread(
                vercel_analytics.delete_drain, conn.api_token, conn.drain_id
            )
        except Exception as e:
            print(f"[bot_analytics] Failed to delete Vercel drain {conn.drain_id}: {e}")

    conn.is_active = False
    await db.commit()
    return {"message": "Disconnected successfully."}


@router.post("/sync/{connection_id}")
async def sync_bot_traffic(
    connection_id: int,
    body: SyncRequest = SyncRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual sync of bot traffic data from Cloudflare."""
    _require_paid(current_user)

    result = await db.execute(
        select(CdnConnection).where(
            CdnConnection.id == connection_id,
            CdnConnection.user_id == current_user.id,
            CdnConnection.is_active == True,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    # Vercel is push-based via Log Drains — there's nothing to pull. The
    # webhook handler in routers/vercel_webhook.py inserts visits as Vercel
    # streams them, so a manual sync is a no-op.
    if conn.provider == "vercel":
        return {
            "synced": 0,
            "period_days": body.days,
            "message": "Vercel uses real-time Log Drains — bot traffic streams in automatically.",
        }

    since = datetime.now(timezone.utc) - timedelta(days=body.days)
    until = datetime.now(timezone.utc)

    visits = await asyncio.to_thread(
        bot_analytics.fetch_bot_traffic,
        api_token=conn.api_token,
        zone_id=conn.zone_id,
        since=since,
        until=until,
    )

    # Insert new bot visits
    inserted = 0
    for v in visits:
        db.add(BotVisit(
            cdn_connection_id=conn.id,
            user_id=current_user.id,
            bot_name=v["bot_name"],
            bot_platform=v["bot_platform"],
            bot_category=v["bot_category"],
            path=v["path"],
            status_code=v["status_code"],
            request_count=v["request_count"],
            visited_at=v["visited_at"],
        ))
        inserted += 1

    conn.last_synced_at = datetime.now(timezone.utc)
    await db.commit()

    return {"synced": inserted, "period_days": body.days}


@router.get("/summary")
async def bot_traffic_summary(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate bot traffic summary for the user's connected zones."""
    _require_paid(current_user)

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Total visits by bot platform
    platform_result = await db.execute(
        select(
            BotVisit.bot_platform,
            func.sum(BotVisit.request_count).label("total"),
        )
        .where(
            BotVisit.user_id == current_user.id,
            BotVisit.visited_at >= since,
        )
        .group_by(BotVisit.bot_platform)
        .order_by(desc("total"))
    )
    by_platform = [
        {"platform": row.bot_platform, "requests": row.total}
        for row in platform_result.all()
    ]

    # Total visits by bot category
    category_result = await db.execute(
        select(
            BotVisit.bot_category,
            func.sum(BotVisit.request_count).label("total"),
        )
        .where(
            BotVisit.user_id == current_user.id,
            BotVisit.visited_at >= since,
        )
        .group_by(BotVisit.bot_category)
        .order_by(desc("total"))
    )
    by_category = [
        {"category": row.bot_category, "requests": row.total}
        for row in category_result.all()
    ]

    # Total visits by bot name (most granular)
    bot_result = await db.execute(
        select(
            BotVisit.bot_name,
            BotVisit.bot_platform,
            BotVisit.bot_category,
            func.sum(BotVisit.request_count).label("total"),
        )
        .where(
            BotVisit.user_id == current_user.id,
            BotVisit.visited_at >= since,
        )
        .group_by(BotVisit.bot_name, BotVisit.bot_platform, BotVisit.bot_category)
        .order_by(desc("total"))
    )
    by_bot = [
        {
            "bot_name": row.bot_name,
            "platform": row.bot_platform,
            "category": row.bot_category,
            "requests": row.total,
        }
        for row in bot_result.all()
    ]

    # Top pages visited
    page_result = await db.execute(
        select(
            BotVisit.path,
            func.sum(BotVisit.request_count).label("total"),
        )
        .where(
            BotVisit.user_id == current_user.id,
            BotVisit.visited_at >= since,
        )
        .group_by(BotVisit.path)
        .order_by(desc("total"))
        .limit(25)
    )
    top_pages = [
        {"path": row.path, "requests": row.total}
        for row in page_result.all()
    ]

    # Daily trend (requests per day)
    # Use date truncation that works for both SQLite and Postgres
    daily_result = await db.execute(
        select(
            func.date(BotVisit.visited_at).label("day"),
            func.sum(BotVisit.request_count).label("total"),
        )
        .where(
            BotVisit.user_id == current_user.id,
            BotVisit.visited_at >= since,
        )
        .group_by("day")
        .order_by("day")
    )
    daily_trend = [
        {"date": str(row.day), "requests": row.total}
        for row in daily_result.all()
    ]

    # Grand total
    total_result = await db.execute(
        select(func.sum(BotVisit.request_count)).where(
            BotVisit.user_id == current_user.id,
            BotVisit.visited_at >= since,
        )
    )
    total_requests = total_result.scalar() or 0

    return {
        "period_days": days,
        "total_requests": total_requests,
        "by_platform": by_platform,
        "by_category": by_category,
        "by_bot": by_bot,
        "top_pages": top_pages,
        "daily_trend": daily_trend,
    }
