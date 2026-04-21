from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import User, NotificationSettings
from auth import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


class NotificationUpdate(BaseModel):
    weekly_digest: Optional[bool] = None
    mention_alerts: Optional[bool] = None
    competitor_alerts: Optional[bool] = None
    alert_email: Optional[str] = None


@router.get("/notifications")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == current_user.id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        notif = NotificationSettings(user_id=current_user.id)
        db.add(notif)
        await db.commit()

    return {
        "weekly_digest": notif.weekly_digest,
        "mention_alerts": notif.mention_alerts,
        "competitor_alerts": notif.competitor_alerts,
        "alert_email": notif.alert_email or current_user.email,
    }


@router.put("/notifications")
async def update_notifications(
    req: NotificationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == current_user.id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        notif = NotificationSettings(user_id=current_user.id)
        db.add(notif)

    if req.weekly_digest is not None:
        notif.weekly_digest = req.weekly_digest
    if req.mention_alerts is not None:
        notif.mention_alerts = req.mention_alerts
    if req.competitor_alerts is not None:
        notif.competitor_alerts = req.competitor_alerts
    if req.alert_email is not None:
        notif.alert_email = req.alert_email

    await db.commit()
    return {"success": True}
