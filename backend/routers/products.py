from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from database import get_db
from models import User, Product, ScanResult, AIOverviewSnapshot, Recommendation
from auth import get_current_user

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductCreate(BaseModel):
    name: str
    category: str
    use_case: Optional[str] = None
    keywords: List[str] = []
    competitors: List[str] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    use_case: Optional[str] = None
    keywords: Optional[List[str]] = None
    competitors: Optional[List[str]] = None


def get_plan_limits(plan: str) -> dict:
    return {
        "free": {"max_products": 1, "max_keywords": 3},
        "starter": {"max_products": 1, "max_keywords": 5},
        "growth": {"max_products": 3, "max_keywords": 20},
    }.get(plan, {"max_products": 1, "max_keywords": 3})


@router.get("/")
async def list_products(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product).where(Product.user_id == current_user.id, Product.is_active == True)
    )
    products = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "use_case": p.use_case,
            "keywords": p.keywords,
            "competitors": p.competitors,
            "last_scanned_at": p.last_scanned_at,
            "created_at": p.created_at,
        }
        for p in products
    ]


@router.post("/")
async def create_product(
    req: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    limits = get_plan_limits(current_user.plan)

    # Check product limit
    result = await db.execute(
        select(Product).where(Product.user_id == current_user.id, Product.is_active == True)
    )
    existing = result.scalars().all()
    if len(existing) >= limits["max_products"]:
        raise HTTPException(
            status_code=403,
            detail=f"Your plan allows {limits['max_products']} product(s). Upgrade to add more."
        )

    # Check keyword limit
    if len(req.keywords) > limits["max_keywords"]:
        raise HTTPException(
            status_code=403,
            detail=f"Your plan allows {limits['max_keywords']} keyword(s). Upgrade for more."
        )

    product = Product(
        user_id=current_user.id,
        name=req.name,
        category=req.category,
        use_case=req.use_case,
        keywords=req.keywords,
        competitors=req.competitors,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "use_case": product.use_case,
        "keywords": product.keywords,
        "competitors": product.competitors,
        "created_at": product.created_at,
    }


@router.put("/{product_id}")
async def update_product(
    product_id: int,
    req: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.user_id == current_user.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    limits = get_plan_limits(current_user.plan)
    if req.keywords is not None and len(req.keywords) > limits["max_keywords"]:
        raise HTTPException(
            status_code=403,
            detail=f"Your plan allows {limits['max_keywords']} keyword(s)."
        )

    if req.name is not None:
        product.name = req.name
    if req.category is not None:
        product.category = req.category
    if req.use_case is not None:
        product.use_case = req.use_case
    if req.keywords is not None:
        product.keywords = req.keywords
    if req.competitors is not None:
        product.competitors = req.competitors

    await db.commit()
    return {"success": True}


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.user_id == current_user.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.is_active = False
    await db.commit()
    return {"success": True}


@router.post("/{product_id}/scan")
async def trigger_scan(
    product_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger a scan for a product."""
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.user_id == current_user.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    async def do_scan():
        from scheduler import scan_product
        async with __import__('database').AsyncSessionLocal() as scan_db:
            await scan_product(product_id, scan_db)

    background_tasks.add_task(do_scan)
    return {"message": "Scan started in background"}


@router.get("/{product_id}/results")
async def get_results(
    product_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get scan results for a product."""
    # Verify ownership
    prod_result = await db.execute(
        select(Product).where(Product.id == product_id, Product.user_id == current_user.id)
    )
    if not prod_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Product not found")

    result = await db.execute(
        select(ScanResult)
        .where(ScanResult.product_id == product_id)
        .order_by(ScanResult.created_at.desc())
        .limit(limit)
    )
    scans = result.scalars().all()

    return [
        {
            "id": s.id,
            "query": s.query,
            "ai_model": s.ai_model,
            "full_response": s.full_response,
            "product_mentioned": s.product_mentioned,
            "mention_position": s.mention_position,
            "mention_sentiment": s.mention_sentiment,
            "competitors_mentioned": s.competitors_mentioned,
            "created_at": s.created_at,
        }
        for s in scans
    ]


@router.get("/{product_id}/summary")
async def get_summary(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregated summary stats for a product."""
    prod_result = await db.execute(
        select(Product).where(Product.id == product_id, Product.user_id == current_user.id)
    )
    product = prod_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    result = await db.execute(
        select(ScanResult)
        .where(ScanResult.product_id == product_id)
        .order_by(ScanResult.created_at.desc())
        .limit(100)
    )
    scans = result.scalars().all()

    if not scans:
        return {
            "product": {"id": product.id, "name": product.name, "category": product.category},
            "total_queries": 0,
            "mentions": 0,
            "mention_rate": 0,
            "best_position": None,
            "sentiment_breakdown": {},
            "competitors_seen": [],
            "recent_scans": [],
        }

    total = len(scans)
    mentions = sum(1 for s in scans if s.product_mentioned)
    mention_rate = round(mentions / total, 2) if total > 0 else 0

    positions = [s.mention_position for s in scans if s.mention_position]
    best_position = min(positions) if positions else None

    sentiment_breakdown = {}
    for s in scans:
        if s.mention_sentiment:
            sentiment_breakdown[s.mention_sentiment] = sentiment_breakdown.get(s.mention_sentiment, 0) + 1

    all_competitors = []
    for s in scans:
        all_competitors.extend(s.competitors_mentioned or [])
    competitors_seen = list(set(all_competitors))

    return {
        "product": {"id": product.id, "name": product.name, "category": product.category},
        "total_queries": total,
        "mentions": mentions,
        "mention_rate": mention_rate,
        "best_position": best_position,
        "sentiment_breakdown": sentiment_breakdown,
        "competitors_seen": competitors_seen,
        "recent_scans": [
            {
                "query": s.query[:100],
                "mentioned": s.product_mentioned,
                "position": s.mention_position,
                "sentiment": s.mention_sentiment,
                "created_at": s.created_at,
            }
            for s in scans[:10]
        ],
    }


async def _verify_product_ownership(product_id: int, user: User, db: AsyncSession):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.user_id == user.id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/ai-overview")
async def get_ai_overview(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the most recent Google AI Overview snapshot for a product."""
    await _verify_product_ownership(product_id, current_user, db)

    result = await db.execute(
        select(AIOverviewSnapshot)
        .where(AIOverviewSnapshot.product_id == product_id)
        .order_by(AIOverviewSnapshot.created_at.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None
    return {
        "id": snap.id,
        "query": snap.query,
        "was_returned": snap.was_returned,
        "overview_text": snap.overview_text,
        "text_blocks": snap.text_blocks,
        "references": snap.references,
        "created_at": snap.created_at,
    }


@router.get("/{product_id}/recommendations")
async def get_recommendations(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return the most recent Claude-generated recommendations for a product."""
    await _verify_product_ownership(product_id, current_user, db)

    result = await db.execute(
        select(Recommendation)
        .where(Recommendation.product_id == product_id)
        .order_by(Recommendation.created_at.desc())
        .limit(1)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        return None
    return {
        "id": rec.id,
        "executive_summary": rec.executive_summary,
        "strengths": rec.strengths,
        "weaknesses": rec.weaknesses,
        "actions": rec.actions,
        "based_on_scan_count": rec.based_on_scan_count,
        "model_used": rec.model_used,
        "ai_overview_snapshot_id": rec.ai_overview_snapshot_id,
        "created_at": rec.created_at,
    }
