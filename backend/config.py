from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # OpenRouter — routes to Claude, GPT, Gemini, Perplexity (for scans)
    openrouter_api_key: str = ""

    # Anthropic — used directly by recommendations.py to generate the
    # per-scan SEO summary (fed with LLM scan data + Google AI Overview).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # SerpAPI — scrapes Google AI Overview for the primary query each scan.
    serpapi_api_key: str = ""

    # Resend
    resend_api_key: str = ""
    resend_from_email: str = "noreply@contact.illusion.ai"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_starter_price_id: str = ""
    stripe_growth_price_id: str = ""

    # App
    app_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    database_url: str = "sqlite+aiosqlite:///./ai_mention_tracker.db"

    # Cloudflare Turnstile (anti-bot on /register). When unset, verification is
    # skipped — safe for local dev, and harmless if Railway hasn't been wired yet.
    turnstile_secret_key: str = ""
    turnstile_site_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
