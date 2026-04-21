from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Anthropic
    anthropic_api_key: str = ""

    # Resend
    resend_api_key: str = ""
    resend_from_email: str = "noreply@aimentiontacker.com"

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

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
