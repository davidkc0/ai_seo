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

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from database import init_db
from scheduler import start_scheduler
from rate_limit import limiter
from routers import auth, products, billing, settings as settings_router, unsubscribe, bot_analytics, vercel_webhook
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

# slowapi rate limiting — protects /register and /resend-verification from
# scripted abuse. The limiter itself is defined in rate_limit.py so routers
# can import it without circular dependencies.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(bot_analytics.router)
# Public webhook receiver for Vercel Log Drains — secured via per-connection
# HMAC signature, NOT auth middleware (Vercel calls this, not our users).
app.include_router(vercel_webhook.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}



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
