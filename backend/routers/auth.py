import secrets
from typing import Optional

import httpx
import resend
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt

from database import get_db
from models import User, NotificationSettings
from auth import verify_password, get_password_hash, create_access_token, get_current_user
from config import settings
from disposable_domains import is_disposable
from email_service import send_welcome_email
from rate_limit import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    # Cloudflare Turnstile token from the frontend widget. Optional so the
    # backend stays usable in dev without a configured site key.
    turnstile_token: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


async def _verify_turnstile(token: Optional[str], remote_ip: Optional[str]) -> bool:
    """Verify a Cloudflare Turnstile challenge token via siteverify.

    Returns True if the captcha is valid OR if Turnstile isn't configured
    (dev-mode escape hatch — mirrors `_is_resend_configured` so local dev
    keeps working without Cloudflare creds). Network/parse errors fail
    closed in prod (returns False) so a flaky Cloudflare doesn't open the
    floodgates.
    """
    if not settings.turnstile_secret_key:
        return True  # not configured → skip
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": settings.turnstile_secret_key,
                    "response": token,
                    "remoteip": remote_ip or "",
                },
            )
            return r.json().get("success") is True
    except Exception as e:
        print(f"[Turnstile] siteverify failed: {e}")
        return False


@router.post("/register", response_model=TokenResponse)
@limiter.limit("3/hour")
async def register(
    request: Request,
    req: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Cheap filters first — block obvious throwaway providers and bot
    # traffic before we touch the database. Turnstile is the heavier
    # check (HTTPS round-trip to Cloudflare) so it goes second.
    if is_disposable(req.email):
        raise HTTPException(
            status_code=400,
            detail="Please use a permanent email address.",
        )

    remote_ip = request.client.host if request.client else None
    if not await _verify_turnstile(req.turnstile_token, remote_ip):
        raise HTTPException(
            status_code=400,
            detail="Captcha verification failed. Please try again.",
        )

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

    # Send the email-verification link. Until they click it, scans refuse to
    # run for this account — the dashboard itself stays open so honest users
    # have a friendly first impression.
    background_tasks.add_task(
        _send_verification_email,
        to_email=user.email,
        verify_url=_build_verify_url(user.email),
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
        "email_verified": current_user.email_verified,
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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


@router.post("/forgot-password")
async def forgot_password(
    req: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset email. Always returns 200 to prevent email enumeration."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if user:
        # Generate a short-lived reset token (30 min)
        reset_token = create_access_token(
            {"sub": user.email, "purpose": "reset"},
            expires_delta=timedelta(minutes=30),
        )
        reset_url = f"{settings.app_url}/reset-password?token={reset_token}"
        background_tasks.add_task(
            _send_reset_email, user.email, reset_url
        )

    # Always return success to prevent email enumeration
    return {"message": "If that email exists, we sent a reset link."}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password using the token from the email."""
    try:
        payload = jwt.decode(req.token, settings.secret_key, algorithms=[settings.algorithm])
        email = payload.get("sub")
        purpose = payload.get("purpose")
        if not email or purpose != "reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user.hashed_password = get_password_hash(req.password)
    await db.commit()

    return {"message": "Password updated. You can now log in."}


# ── Email verification ─────────────────────────────────────────────────
# Bots and tourists don't have inboxes. Gating scans on "did the user click
# the link in the email we just sent" is the highest-leverage anti-fraud
# move available — see plan at .claude/plans/mossy-coalescing-engelbart.md.

class VerifyEmailRequest(BaseModel):
    token: str


def _build_verify_url(email: str) -> str:
    """Mint a 24h JWT and embed it in the frontend verify URL.

    Mirrors the `purpose: "reset"` token pattern used by forgot-password so
    we don't need a new DB column for the token itself.
    """
    token = create_access_token(
        {"sub": email, "purpose": "email_verify"},
        expires_delta=timedelta(hours=24),
    )
    return f"{settings.app_url}/verify-email?token={token}"


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """Consume an email-verification token and flip user.email_verified = True.

    Idempotent — re-clicking the link just succeeds again.
    """
    try:
        payload = jwt.decode(req.token, settings.secret_key, algorithms=[settings.algorithm])
        email = payload.get("sub")
        purpose = payload.get("purpose")
        if not email or purpose != "email_verify":
            raise HTTPException(status_code=400, detail="Invalid verification token")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user.email_verified = True
    await db.commit()
    return {"message": "Email verified"}


@router.post("/resend-verification")
@limiter.limit("5/hour")
async def resend_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Resend the verification email to the currently-logged-in user.

    Auth-gated to prevent enumeration / spamming arbitrary inboxes. If the
    account is already verified we no-op with 200 so the UI can show a
    friendly confirmation either way.
    """
    if current_user.email_verified:
        return {"message": "Already verified"}

    background_tasks.add_task(
        _send_verification_email,
        to_email=current_user.email,
        verify_url=_build_verify_url(current_user.email),
    )
    return {"message": "Verification email sent"}


def _send_reset_email(to_email: str, reset_url: str):
    """Send password reset email using the same template style as other emails."""
    from email_service import _is_resend_configured, LOGO_URL

    if not _is_resend_configured():
        print(f"[EMAIL] Resend not configured. Reset URL for {to_email}: {reset_url}")
        return

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
    <h1 style="color:#ededed;font-size:22px;margin:0 0 12px;font-weight:700;">Reset your password</h1>
    <p style="color:#ccc;font-size:15px;line-height:1.65;margin:0 0 24px;">We received a request to reset the password for your Illusion account. Click the button below to choose a new password.</p>
    <div style="text-align:center;margin:32px 0;">
      <a href="{reset_url}" style="display:inline-block;background:#10b981;color:#fff;padding:13px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">Reset Password &rarr;</a>
    </div>
    <p style="color:#888;font-size:13px;line-height:1.6;margin:0;">This link expires in 30 minutes. If you didn't request a password reset, you can safely ignore this email.</p>
    <p style="color:#555;font-size:13px;line-height:1.6;margin:24px 0 0;border-top:1px solid #1f1f1f;padding-top:20px;">Replies to this address aren't monitored. If you need help, email us at hello@illusion.ai.</p>
  </td></tr>
  <tr><td style="padding:20px 32px;background:#0a0a0a;border-top:1px solid #1f1f1f;text-align:center;">
    <p style="font-size:12px;color:#555;margin:0;line-height:1.6;font-family:'JetBrains Mono',monospace;">illusion &middot; You're getting this because a password reset was requested for this email.</p>
  </td></tr>
</table>
</body>
</html>
"""
    try:
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": "Reset your Illusion password",
            "html": html_body,
        })
        print(f"[EMAIL] Reset email sent to {to_email}")
    except Exception as e:
        print(f"[EMAIL] Failed to send reset email to {to_email}: {e}")


def _send_verification_email(to_email: str, verify_url: str):
    """Send the email-verification link. Style mirrors the password-reset
    template so the brand is consistent across transactional mail.

    Failures are swallowed — if Resend is misconfigured we don't want to
    take down /register, just log it.
    """
    from email_service import _is_resend_configured, LOGO_URL

    if not _is_resend_configured():
        print(f"[EMAIL] Resend not configured. Verify URL for {to_email}: {verify_url}")
        return

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
    <h1 style="color:#ededed;font-size:22px;margin:0 0 12px;font-weight:700;">Verify your email</h1>
    <p style="color:#ccc;font-size:15px;line-height:1.65;margin:0 0 24px;">Click below to verify your email and unlock AI scans for your products. This link expires in 24 hours.</p>
    <div style="text-align:center;margin:32px 0;">
      <a href="{verify_url}" style="display:inline-block;background:#10b981;color:#fff;padding:13px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:15px;">Verify Email &rarr;</a>
    </div>
    <p style="color:#888;font-size:13px;line-height:1.6;margin:0;">If you didn't create an Illusion account, you can safely ignore this email.</p>
    <p style="color:#555;font-size:13px;line-height:1.6;margin:24px 0 0;border-top:1px solid #1f1f1f;padding-top:20px;">Replies to this address aren't monitored. If you need help, email us at hello@illusion.ai.</p>
  </td></tr>
  <tr><td style="padding:20px 32px;background:#0a0a0a;border-top:1px solid #1f1f1f;text-align:center;">
    <p style="font-size:12px;color:#555;margin:0;line-height:1.6;font-family:'JetBrains Mono',monospace;">illusion &middot; You're getting this because you just signed up.</p>
  </td></tr>
</table>
</body>
</html>
"""
    try:
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": "Verify your Illusion email",
            "html": html_body,
        })
        print(f"[EMAIL] Verification email sent to {to_email}")
    except Exception as e:
        print(f"[EMAIL] Failed to send verification email to {to_email}: {e}")


