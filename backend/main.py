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


@app.get("/api/debug/scan-test")
async def debug_scan_test(key: str):
    """Run a minimal scan inline and return what happens at each step."""
    if key != app_settings.secret_key:
        return {"error": "forbidden"}
    import traceback, time
    steps = {}
    try:
        import monitor
        steps["openrouter_key_set"] = bool(app_settings.openrouter_api_key)
        steps["openrouter_key_prefix"] = app_settings.openrouter_api_key[:12] + "..." if app_settings.openrouter_api_key else "EMPTY"
        steps["serpapi_key_set"] = bool(app_settings.serpapi_api_key)

        # Test ONE query to ONE provider
        t0 = time.time()
        resp = monitor.query_provider("claude", "What are the best SEO tools?")
        steps["single_query"] = f"OK ({time.time()-t0:.1f}s, {len(resp)} chars)"
    except Exception:
        steps["single_query_error"] = traceback.format_exc()
        return steps

    try:
        t0 = time.time()
        results = monitor.run_product_scan(
            product_name="TestProduct",
            category="SEO",
            use_case=None,
            competitors=[],
            keywords=[],
            providers=["claude"],  # just 1 provider
        )
        steps["mini_scan"] = f"OK ({time.time()-t0:.1f}s, {len(results)} results)"
    except Exception:
        steps["mini_scan_error"] = traceback.format_exc()

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
