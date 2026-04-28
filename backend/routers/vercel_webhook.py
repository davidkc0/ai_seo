"""
Webhook endpoint for Vercel Log Drains.

Vercel pushes batched log entries here in real-time. We filter for AI bot
user-agents, classify them, and store matching visits in the BotVisit table.

This endpoint is NOT behind auth middleware — Vercel calls it, not our users.
Security is via HMAC signature verification using the per-connection secret.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import AsyncSessionLocal
from models import CdnConnection, BotVisit
from vercel_analytics import parse_log_entry

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Vercel's HMAC-SHA1 signature on the payload."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha1).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/vercel-logs/{connection_id}")
async def receive_vercel_logs(connection_id: int, request: Request):
    """Receive log drain payloads from Vercel.

    Vercel sends batched log entries as a JSON array. Each entry may contain
    a `proxy` object with user-agent data we can classify.
    """
    body = await request.body()

    # Look up the connection and its webhook secret
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CdnConnection).where(
                CdnConnection.id == connection_id,
                CdnConnection.provider == "vercel",
                CdnConnection.is_active == True,
            )
        )
        conn = result.scalar_one_or_none()

        if not conn:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Verify HMAC signature
        signature = request.headers.get("x-vercel-signature", "")
        if conn.webhook_secret and not _verify_signature(body, signature, conn.webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse the payload — Vercel sends either a single object or an array
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        entries = payload if isinstance(payload, list) else [payload]

        # Classify and insert bot visits
        inserted = 0
        for entry in entries:
            visit_data = parse_log_entry(entry)
            if visit_data:
                db.add(BotVisit(
                    cdn_connection_id=conn.id,
                    user_id=conn.user_id,
                    bot_name=visit_data["bot_name"],
                    bot_platform=visit_data["bot_platform"],
                    bot_category=visit_data["bot_category"],
                    path=visit_data["path"],
                    status_code=visit_data["status_code"],
                    request_count=visit_data["request_count"],
                    visited_at=visit_data["visited_at"],
                ))
                inserted += 1

        if inserted > 0:
            conn.last_synced_at = datetime.now(timezone.utc)
            await db.commit()

    return {"received": len(entries), "bot_visits_inserted": inserted}
