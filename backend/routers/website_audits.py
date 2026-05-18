import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import website_audits
from auth import get_current_user
from config import settings
from database import AsyncSessionLocal, get_db
from models import Product, User, WebsiteAudit
from rate_limit import limiter

router = APIRouter(prefix="/api/website-audits", tags=["website-audits"])

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class PublicAuditRequest(BaseModel):
    url: str
    turnstile_token: Optional[str] = None


class ClaimAuditRequest(BaseModel):
    public_token: Optional[str] = None
    product_id: Optional[int] = None
    create_product: bool = False
    product_name: Optional[str] = None
    category: Optional[str] = None
    use_case: Optional[str] = None


class RerunAuditRequest(BaseModel):
    product_id: Optional[int] = None
    url: Optional[str] = None


def _plan_limits(plan: str) -> dict:
    return {
        "free": {"max_products": 1, "max_keywords": 3},
        "starter": {"max_products": 1, "max_keywords": 5},
        "growth": {"max_products": 3, "max_keywords": 20},
    }.get(plan, {"max_products": 1, "max_keywords": 3})


async def _verify_turnstile(token: Optional[str], remote_ip: Optional[str]) -> bool:
    if not settings.turnstile_secret_key:
        return True
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": settings.turnstile_secret_key,
                    "response": token,
                    "remoteip": remote_ip or "",
                },
            )
            return resp.json().get("success") is True
    except Exception as e:
        print(f"[website_audits] Turnstile verify failed: {e}")
        return False


def _serialize_audit(audit: WebsiteAudit, include_token: bool = False) -> dict:
    payload = {
        "id": audit.id,
        "user_id": audit.user_id,
        "product_id": audit.product_id,
        "original_url": audit.original_url,
        "normalized_url": audit.normalized_url,
        "domain": audit.domain,
        "status": audit.status,
        "scores": {
            "overall": audit.overall_score,
            "ux": audit.ux_score,
            "seo": audit.seo_score,
            "ai": audit.ai_score,
        },
        "executive_summary": audit.executive_summary,
        "findings": audit.findings or [],
        "crawled_pages": audit.crawled_pages or [],
        "extracted_signals": audit.extracted_signals or {},
        "model_used": audit.model_used,
        "error": audit.error,
        "created_at": audit.created_at,
        "updated_at": audit.updated_at,
        "completed_at": audit.completed_at,
    }
    if include_token:
        payload["public_token"] = audit.public_token
    return payload


async def _run_audit_job(audit_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WebsiteAudit).where(WebsiteAudit.id == audit_id))
        audit = result.scalar_one_or_none()
        if not audit:
            return

        audit.status = "running"
        audit.updated_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            report = await asyncio.to_thread(website_audits.run_website_audit, audit.normalized_url)
            scores = report["scores"]
            audit.normalized_url = report["normalized_url"]
            audit.domain = report["domain"]
            audit.status = "completed"
            audit.overall_score = scores.get("overall")
            audit.ux_score = scores.get("ux")
            audit.seo_score = scores.get("seo")
            audit.ai_score = scores.get("ai")
            audit.executive_summary = report["executive_summary"]
            audit.findings = report["findings"]
            audit.crawled_pages = report["crawled_pages"]
            audit.extracted_signals = report["extracted_signals"]
            audit.model_used = report["model_used"]
            audit.error = None
            audit.completed_at = datetime.now(timezone.utc)
            audit.updated_at = audit.completed_at
        except Exception as e:
            audit.status = "failed"
            audit.error = str(e)
            audit.updated_at = datetime.now(timezone.utc)
            print(f"[website_audits] Audit {audit_id} failed: {type(e).__name__}: {e}")

        await db.commit()


@router.post("/public")
@limiter.limit("6/hour")
async def start_public_audit(
    request: Request,
    body: PublicAuditRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start an anonymous website audit and return polling credentials."""
    remote_ip = request.client.host if request.client else None
    if not await _verify_turnstile(body.turnstile_token, remote_ip):
        raise HTTPException(status_code=400, detail="Captcha verification failed. Please try again.")

    try:
        normalized_url = await asyncio.to_thread(website_audits.normalize_url, body.url)
    except website_audits.AuditError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit = WebsiteAudit(
        public_token=secrets.token_urlsafe(32),
        original_url=body.url,
        normalized_url=normalized_url,
        domain=website_audits.domain_for_url(normalized_url),
        status="queued",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    background_tasks.add_task(_run_audit_job, audit.id)
    return {"audit_id": audit.id, "public_token": audit.public_token, "status": audit.status}


@router.get("/public/{audit_id}")
async def get_public_audit(
    audit_id: int,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(WebsiteAudit).where(WebsiteAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit or not secrets.compare_digest(audit.public_token, token):
        raise HTTPException(status_code=404, detail="Audit not found")
    return _serialize_audit(audit, include_token=True)


async def _owned_product(product_id: int, user: User, db: AsyncSession) -> Product:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.user_id == user.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/{audit_id}/claim")
async def claim_audit(
    audit_id: int,
    body: ClaimAuditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(WebsiteAudit).where(WebsiteAudit.id == audit_id))
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    if audit.user_id and audit.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This audit belongs to another account.")
    if audit.user_id is None:
        if not body.public_token or not secrets.compare_digest(audit.public_token, body.public_token):
            raise HTTPException(status_code=404, detail="Audit not found")

    product = None
    if body.product_id:
        product = await _owned_product(body.product_id, current_user, db)
        product.website_url = audit.normalized_url
    elif body.create_product:
        limits = _plan_limits(current_user.plan)
        existing_result = await db.execute(
            select(Product).where(Product.user_id == current_user.id, Product.is_active == True)
        )
        existing = existing_result.scalars().all()
        if len(existing) >= limits["max_products"]:
            raise HTTPException(
                status_code=403,
                detail=f"Your plan allows {limits['max_products']} product(s). Upgrade to add more.",
            )
        product = Product(
            user_id=current_user.id,
            name=(body.product_name or audit.domain or "My website").strip(),
            category=(body.category or "local service business").strip(),
            use_case=(body.use_case or None),
            website_url=audit.normalized_url,
            keywords=[],
            competitors=[],
        )
        db.add(product)
        await db.flush()

    audit.user_id = current_user.id
    if product:
        audit.product_id = product.id
    audit.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(audit)

    return {
        "audit": _serialize_audit(audit),
        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "website_url": product.website_url,
        } if product else None,
    }


@router.get("/")
async def list_audits(
    product_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(WebsiteAudit).where(WebsiteAudit.user_id == current_user.id)
    if product_id is not None:
        await _owned_product(product_id, current_user, db)
        query = query.where(WebsiteAudit.product_id == product_id)
    result = await db.execute(query.order_by(WebsiteAudit.created_at.desc()).limit(50))
    return [_serialize_audit(a) for a in result.scalars().all()]


@router.get("/{audit_id}")
async def get_audit(
    audit_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebsiteAudit).where(WebsiteAudit.id == audit_id, WebsiteAudit.user_id == current_user.id)
    )
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    return _serialize_audit(audit)


async def _enforce_rerun_cooldown(user: User, product_id: Optional[int], normalized_url: str, db: AsyncSession):
    cooldown = timedelta(days=7) if user.plan == "free" else timedelta(hours=24)
    since = datetime.now(timezone.utc) - cooldown
    query = select(WebsiteAudit).where(
        WebsiteAudit.user_id == user.id,
        WebsiteAudit.created_at >= since,
        WebsiteAudit.status.in_(["queued", "running", "completed"]),
    )
    if product_id:
        query = query.where(WebsiteAudit.product_id == product_id)
    else:
        query = query.where(WebsiteAudit.normalized_url == normalized_url)
    result = await db.execute(query.order_by(WebsiteAudit.created_at.desc()).limit(1))
    if result.scalar_one_or_none():
        label = "weekly" if user.plan == "free" else "daily"
        raise HTTPException(status_code=403, detail=f"Your {user.plan} plan allows {label} website audit reruns.")


@router.post("/rerun")
async def rerun_audit(
    body: RerunAuditRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    product = None
    raw_url = body.url
    if body.product_id:
        product = await _owned_product(body.product_id, current_user, db)
        raw_url = raw_url or product.website_url
    if not raw_url:
        raise HTTPException(status_code=400, detail="Add a website URL before running an audit.")

    try:
        normalized_url = await asyncio.to_thread(website_audits.normalize_url, raw_url)
    except website_audits.AuditError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await _enforce_rerun_cooldown(current_user, product.id if product else None, normalized_url, db)

    if product and product.website_url != normalized_url:
        product.website_url = normalized_url

    audit = WebsiteAudit(
        user_id=current_user.id,
        product_id=product.id if product else None,
        public_token=secrets.token_urlsafe(32),
        original_url=raw_url,
        normalized_url=normalized_url,
        domain=website_audits.domain_for_url(normalized_url),
        status="queued",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)

    background_tasks.add_task(_run_audit_job, audit.id)
    return _serialize_audit(audit)
