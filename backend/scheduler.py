"""
Background scheduler for running product scans on a cadence.
- Free plan: weekly scans
- Starter ($19/mo): daily scans
- Growth ($39/mo): daily scans + alerts
"""
import asyncio
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import User, Product, ScanResult, NotificationSettings, AIOverviewSnapshot, Recommendation, CdnConnection, BotVisit
import monitor
import serp
import recommendations
import email_service
import bot_analytics


scheduler = AsyncIOScheduler(timezone="UTC")


async def scan_product(product_id: int, db: AsyncSession):
    """Run a scan for a single product and save results."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product or not product.is_active:
        return

    print(f"[Scheduler] Scanning product: {product.name} (id={product_id})")

    # Run blocking LLM calls in a thread so the event loop stays responsive
    scan_results = await asyncio.to_thread(
        monitor.run_product_scan,
        product_name=product.name,
        category=product.category,
        use_case=product.use_case,
        competitors=product.competitors or [],
        keywords=product.keywords or [],
    )

    new_results = []
    for sr in scan_results:
        db_result = ScanResult(
            product_id=product.id,
            query=sr["query"],
            ai_model=sr["ai_model"],
            full_response=sr["full_response"],
            product_mentioned=sr["product_mentioned"],
            mention_position=sr["mention_position"],
            mention_sentiment=sr["mention_sentiment"],
            competitors_mentioned=sr["competitors_mentioned"],
        )
        db.add(db_result)
        new_results.append(sr)

    product.last_scanned_at = datetime.now(timezone.utc)
    await db.commit()

    # Look up user plan to gate premium features
    user_result = await db.execute(select(User).where(User.id == product.user_id))
    user = user_result.scalar_one_or_none()
    user_plan = user.plan if user else "free"

    # Skip AI Overview + Recommendations for free-tier users
    if user_plan == "free":
        print(f"[Scheduler] Done scanning {product.name}: {len(new_results)} queries (free plan — skipping recs)")
        return

    # ────────────────────────────────────────────────────────────────
    # AI Overview + Recommendations (paid plans only, best-effort)
    # ────────────────────────────────────────────────────────────────
    ai_overview_snapshot = None
    try:
        queries = monitor.build_queries(
            product_name=product.name,
            category=product.category,
            use_case=product.use_case,
            competitors=product.competitors or [],
            keywords=product.keywords or [],
        )
        primary_query = serp.pick_primary_query(queries)
        if primary_query:
            overview = await asyncio.to_thread(serp.fetch_ai_overview, primary_query)
            ai_overview_snapshot = AIOverviewSnapshot(
                product_id=product.id,
                query=primary_query,
                overview_text=overview.get("overview_text", ""),
                text_blocks=overview.get("text_blocks", []),
                references=overview.get("references", []),
                raw_response=overview.get("raw_response", {}),
                was_returned=overview.get("was_returned", False),
            )
            db.add(ai_overview_snapshot)
            await db.commit()
            await db.refresh(ai_overview_snapshot)
            print(f"[Scheduler] AI Overview fetched (returned={ai_overview_snapshot.was_returned})")
    except Exception as e:
        print(f"[Scheduler] AI Overview step failed: {type(e).__name__}: {e}")

    try:
        ai_overview_payload = None
        if ai_overview_snapshot and ai_overview_snapshot.was_returned:
            ai_overview_payload = {
                "was_returned": True,
                "overview_text": ai_overview_snapshot.overview_text,
                "references": ai_overview_snapshot.references,
            }

        rec = await asyncio.to_thread(
            recommendations.generate_recommendations,
            product={
                "name": product.name,
                "category": product.category,
                "use_case": product.use_case,
                "competitors": product.competitors or [],
                "keywords": product.keywords or [],
            },
            scan_results=new_results,
            ai_overview=ai_overview_payload,
        )
        db_rec = Recommendation(
            product_id=product.id,
            ai_overview_snapshot_id=ai_overview_snapshot.id if ai_overview_snapshot else None,
            executive_summary=rec["executive_summary"],
            strengths=rec["strengths"],
            weaknesses=rec["weaknesses"],
            actions=rec["actions"],
            based_on_scan_count=len(new_results),
            model_used=rec["model_used"],
        )
        db.add(db_rec)
        await db.commit()
        print(f"[Scheduler] Recommendations saved ({len(rec['actions'])} actions)")
    except Exception as e:
        print(f"[Scheduler] Recommendations step failed: {type(e).__name__}: {e}")

    # Check if we should send instant alerts (Growth plan)
    user_result = await db.execute(select(User).where(User.id == product.user_id))
    user = user_result.scalar_one_or_none()

    if user and user.plan == "growth":
        notif_result = await db.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user.id)
        )
        notif = notif_result.scalar_one_or_none()
        if notif and notif.mention_alerts:
            alert_email = notif.alert_email or user.email
            for sr in new_results:
                if sr["product_mentioned"] and sr["mention_position"]:
                    email_service.send_mention_alert(
                        to_email=alert_email,
                        product_name=product.name,
                        query=sr["query"],
                        position=sr["mention_position"],
                        sentiment=sr["mention_sentiment"] or "neutral",
                        unsubscribe_token=user.unsubscribe_token,
                    )

    print(f"[Scheduler] Done scanning {product.name}: {len(new_results)} queries run")


async def run_daily_scans():
    """Run scans for all active paid products (daily cadence)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Product)
            .join(User, Product.user_id == User.id)
            .where(
                Product.is_active == True,
                User.plan.in_(["starter", "growth"]),
                User.is_active == True,
            )
        )
        products = result.scalars().all()
        for product in products:
            try:
                await scan_product(product.id, db)
                await asyncio.sleep(2)  # Polite delay between products
            except Exception as e:
                print(f"[Scheduler] Error scanning product {product.id}: {e}")


async def run_weekly_scans():
    """Run scans for free-tier products (weekly cadence)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Product)
            .join(User, Product.user_id == User.id)
            .where(
                Product.is_active == True,
                User.plan == "free",
                User.is_active == True,
            )
        )
        products = result.scalars().all()
        for product in products:
            try:
                await scan_product(product.id, db)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[Scheduler] Error scanning product {product.id}: {e}")


async def send_weekly_digests():
    """Send weekly email digest to all users."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import func
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        result = await db.execute(select(User).where(User.is_active == True))
        users = result.scalars().all()

        for user in users:
            # Check notification preferences
            notif_result = await db.execute(
                select(NotificationSettings).where(NotificationSettings.user_id == user.id)
            )
            notif = notif_result.scalar_one_or_none()
            if notif and not notif.weekly_digest:
                continue

            # Get products for this user
            prod_result = await db.execute(
                select(Product).where(Product.user_id == user.id, Product.is_active == True)
            )
            products = prod_result.scalars().all()

            for product in products:
                # Gather scan results from the past week
                scan_result = await db.execute(
                    select(ScanResult)
                    .where(
                        ScanResult.product_id == product.id,
                        ScanResult.created_at >= week_ago
                    )
                    .order_by(ScanResult.created_at.desc())
                )
                scans = scan_result.scalars().all()

                if not scans:
                    continue

                total = len(scans)
                mentions = sum(1 for s in scans if s.product_mentioned)
                mention_rate = mentions / total if total > 0 else 0

                sentiments = [s.mention_sentiment for s in scans if s.mention_sentiment]
                top_sentiment = max(set(sentiments), key=sentiments.count) if sentiments else "neutral"

                positions = [s.mention_position for s in scans if s.mention_position]
                best_position = min(positions) if positions else None

                all_competitors = []
                for s in scans:
                    all_competitors.extend(s.competitors_mentioned or [])
                competitors_seen = list(set(all_competitors))

                sample_responses = [
                    {
                        "query": s.query,
                        "mentioned": s.product_mentioned,
                        "position": s.mention_position,
                        "sentiment": s.mention_sentiment,
                    }
                    for s in scans[:5]
                ]

                scan_summary = {
                    "total_queries": total,
                    "mentions": mentions,
                    "mention_rate": mention_rate,
                    "top_sentiment": top_sentiment,
                    "competitors_seen": competitors_seen,
                    "best_position": best_position,
                    "sample_responses": sample_responses,
                }

                email_service.send_weekly_digest(
                    to_email=user.email,
                    user_name=user.email.split("@")[0],
                    product_name=product.name,
                    scan_summary=scan_summary,
                    unsubscribe_token=user.unsubscribe_token,
                )


async def sync_bot_traffic():
    """Daily sync of AI bot traffic from connected CDN accounts (paid users only)."""
    print("[Scheduler] Starting daily bot traffic sync...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CdnConnection).where(CdnConnection.is_active == True)
        )
        connections = result.scalars().all()

        for conn in connections:
            try:
                since = datetime.now(timezone.utc) - timedelta(days=1)
                until = datetime.now(timezone.utc)

                visits = await asyncio.to_thread(
                    bot_analytics.fetch_bot_traffic,
                    api_token=conn.api_token,
                    zone_id=conn.zone_id,
                    since=since,
                    until=until,
                )

                for v in visits:
                    db.add(BotVisit(
                        cdn_connection_id=conn.id,
                        user_id=conn.user_id,
                        bot_name=v["bot_name"],
                        bot_platform=v["bot_platform"],
                        bot_category=v["bot_category"],
                        path=v["path"],
                        status_code=v["status_code"],
                        request_count=v["request_count"],
                        visited_at=v["visited_at"],
                    ))

                conn.last_synced_at = datetime.now(timezone.utc)
                await db.commit()
                print(f"[Scheduler] Bot sync for {conn.zone_name}: {len(visits)} visit groups")
            except Exception as e:
                print(f"[Scheduler] Bot sync failed for {conn.zone_name}: {type(e).__name__}: {e}")


def start_scheduler():
    """Start the background scheduler."""
    # Daily bot traffic sync at 5am UTC
    scheduler.add_job(sync_bot_traffic, "cron", hour=5, minute=0, id="bot_traffic_sync")
    # Daily scans at 6am UTC for paid users
    scheduler.add_job(run_daily_scans, "cron", hour=6, minute=0, id="daily_scans")
    # Weekly scans on Monday at 7am UTC for free users
    scheduler.add_job(run_weekly_scans, "cron", day_of_week="mon", hour=7, minute=0, id="weekly_scans")
    # Weekly digests every Monday at 9am UTC
    scheduler.add_job(send_weekly_digests, "cron", day_of_week="mon", hour=9, minute=0, id="weekly_digests")
    scheduler.start()
    print("[Scheduler] Started: bot sync 5am, daily scans 6am, weekly digests Mon 9am UTC")
