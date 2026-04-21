"""
Illusion - Backend API
FastAPI server with SQLite, scheduled monitoring, and Stripe billing.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from database import init_db
from scheduler import start_scheduler
from routers import auth, products, billing, settings as settings_router, unsubscribe
from config import settings as app_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB and scheduler. Shutdown: nothing special."""
    print("[Boot] Initializing database...")
    await init_db()
    print("[Boot] Database ready.")
    start_scheduler()
    yield
    print("[Shutdown] Goodbye.")


app = FastAPI(
    title="Illusion",
    description="Track what AI says about your product",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server and production
# In prod on Railway, set ALLOWED_ORIGINS env var (comma-separated) OR just set APP_URL.
_extra_origins = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({
        "http://localhost:5173",
        "http://localhost:3000",
        app_settings.app_url,
        *_extra_origins,
    }),
    allow_origin_regex=r"https://.*\.vercel\.app",  # allow Vercel preview deploys
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(billing.router)
app.include_router(settings_router.router)
app.include_router(unsubscribe.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/debug/register-test")
async def debug_register_test():
    """Temporary debug endpoint — tests each step of register to find the 500."""
    import traceback, secrets
    from datetime import timedelta
    steps = {}
    try:
        from auth import get_password_hash
        h = get_password_hash("testpassword123")
        steps["1_bcrypt"] = "OK"
    except Exception:
        steps["1_bcrypt"] = traceback.format_exc()
        return steps
    try:
        from database import AsyncSessionLocal
        from models import User, NotificationSettings
        from sqlalchemy import select, text
        from datetime import datetime, timezone
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            steps["2_db_connect"] = "OK"

            unsub = secrets.token_urlsafe(32)
            user = User(
                email=f"debugtest_{secrets.token_hex(4)}@test.com",
                hashed_password=h,
                plan="free",
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7),
                unsubscribe_token=unsub,
            )
            db.add(user)
            await db.flush()
            steps["3_user_insert"] = f"OK (id={user.id})"

            notif = NotificationSettings(user_id=user.id, weekly_digest=True)
            db.add(notif)
            await db.commit()
            steps["4_notif_insert"] = "OK"

            # Clean up test user
            await db.delete(notif)
            await db.delete(user)
            await db.commit()
            steps["5_cleanup"] = "OK"
    except Exception:
        steps["error"] = traceback.format_exc()
    return steps



# Serve frontend build if it exists
frontend_build = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.exists(frontend_build):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_build, "assets")))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = os.path.join(frontend_build, "index.html")
        return FileResponse(index)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    is_dev = os.environ.get("ENV", "dev").lower() == "dev"
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=is_dev,
        log_level="info",
    )
