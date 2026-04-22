from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import stripe

from database import get_db
from models import User
from auth import get_current_user
from config import settings

router = APIRouter(prefix="/api/billing", tags=["billing"])
stripe.api_key = settings.stripe_secret_key


@router.get("/plans")
async def get_plans():
    """Return pricing plans (public endpoint)."""
    return {
        "plans": [
            {
                "id": "free",
                "name": "Free Trial",
                "price": 0,
                "period": "7 days",
                "features": [
                    "1 product",
                    "3 keywords",
                    "Weekly AI scan",
                    "Basic dashboard",
                ],
                "limits": {"products": 1, "keywords": 3},
            },
            {
                "id": "starter",
                "name": "Starter",
                "price": 19,
                "period": "month",
                "stripe_price_id": settings.stripe_starter_price_id,
                "features": [
                    "1 product",
                    "5 keywords",
                    "Daily AI scan",
                    "AI-generated recommendations",
                    "Google AI Overview tracking",
                    "Weekly email digest",
                    "Competitor tracking",
                ],
                "limits": {"products": 1, "keywords": 5},
                "popular": True,
            },
            {
                "id": "growth",
                "name": "Growth",
                "price": 39,
                "period": "month",
                "stripe_price_id": settings.stripe_growth_price_id,
                "features": [
                    "3 products",
                    "20 keywords",
                    "Daily AI scan",
                    "AI-generated recommendations",
                    "Google AI Overview tracking",
                    "Weekly email digest",
                    "Instant mention alerts",
                    "Competitor comparison",
                ],
                "limits": {"products": 3, "keywords": 20},
            },
        ]
    }


@router.post("/create-checkout")
async def create_checkout(
    plan: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a Stripe checkout session."""
    if not settings.stripe_secret_key or settings.stripe_secret_key.startswith("sk_test_your"):
        raise HTTPException(status_code=503, detail="Stripe not configured. See SETUP.md.")

    price_id = {
        "starter": settings.stripe_starter_price_id,
        "growth": settings.stripe_growth_price_id,
    }.get(plan)

    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid plan")

    # Get or create Stripe customer
    customer_id = current_user.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(email=current_user.email)
        customer_id = customer.id
        current_user.stripe_customer_id = customer_id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.app_url}/dashboard?upgraded=true",
        cancel_url=f"{settings.app_url}/pricing",
        metadata={"user_id": str(current_user.id), "plan": plan},
    )

    return {"checkout_url": session.url}


@router.post("/portal")
async def create_portal(
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe billing portal session."""
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=f"{settings.app_url}/settings",
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhooks to update subscription status."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["metadata"].get("user_id", 0))
        plan = session["metadata"].get("plan", "starter")

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.plan = plan
            user.stripe_subscription_id = session.get("subscription")
            await db.commit()

    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]

        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.plan = "free"
            user.stripe_subscription_id = None
            await db.commit()

    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]
        status = subscription["status"]

        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user and status not in ("active", "trialing"):
            user.plan = "free"
            await db.commit()

    return {"received": True}
