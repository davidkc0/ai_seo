import secrets
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr

from database import get_db
from models import User, NotificationSettings
from auth import verify_password, get_password_hash, create_access_token, get_current_user
from config import settings
from email_service import send_welcome_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/register", response_model=TokenResponse)
async def register(
    req: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Create user on free trial. Generate the unsubscribe_token up front so the
    # first email we send them (welcome) already has a working unsubscribe URL.
    unsub_token = secrets.token_urlsafe(32)
    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        plan="free",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
        unsubscribe_token=unsub_token,
    )
    db.add(user)
    await db.flush()

    # Default notification settings
    notif = NotificationSettings(user_id=user.id, weekly_digest=True)
    db.add(notif)
    await db.commit()

    # Fire welcome email after we've committed. BackgroundTasks runs after the
    # response is returned, so signup latency isn't blocked on Resend's API.
    # Failures are logged inside send_welcome_email and never raise.
    background_tasks.add_task(
        send_welcome_email,
        to_email=user.email,
        unsubscribe_token=unsub_token,
    )

    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "plan": user.plan},
    }


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "plan": user.plan},
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "plan": current_user.plan,
        "trial_ends_at": current_user.trial_ends_at,
        "created_at": current_user.created_at,
    }


@router.get("/admin/users")
async def admin_list_users(key: str, db: AsyncSession = Depends(get_db)):
    """Quick admin endpoint — pass ?key=<SECRET_KEY> to list all users."""
    if key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "plan": u.plan,
            "trial_ends_at": str(u.trial_ends_at) if u.trial_ends_at else None,
            "created_at": str(u.created_at),
        }
        for u in users
    ]

