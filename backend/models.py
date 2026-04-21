from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float,
    ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    plan = Column(String, default="free")  # free, starter, growth
    trial_ends_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    products = relationship("Product", back_populates="owner", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    use_case = Column(String, nullable=True)
    keywords = Column(JSON, default=list)  # list of keyword strings
    competitors = Column(JSON, default=list)  # list of competitor names
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    last_scanned_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="products")
    scan_results = relationship("ScanResult", back_populates="product", cascade="all, delete-orphan")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    query = Column(Text, nullable=False)
    ai_model = Column(String, default="claude")
    full_response = Column(Text, nullable=False)
    product_mentioned = Column(Boolean, default=False)
    mention_position = Column(Integer, nullable=True)  # 1=first, 2=second, etc.
    mention_sentiment = Column(String, nullable=True)  # positive, neutral, negative
    competitors_mentioned = Column(JSON, default=list)  # list of competitor names found
    created_at = Column(DateTime, default=utcnow)

    product = relationship("Product", back_populates="scan_results")


class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    weekly_digest = Column(Boolean, default=True)
    mention_alerts = Column(Boolean, default=False)
    competitor_alerts = Column(Boolean, default=False)
    alert_email = Column(String, nullable=True)


class AIOverviewSnapshot(Base):
    """Cached Google AI Overview result for a product's primary query."""
    __tablename__ = "ai_overview_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    # Flattened plain-text version of the overview, convenient for prompts and UI.
    overview_text = Column(Text, nullable=True)
    # Structured data from SerpAPI: list of {type, snippet/list/...}.
    text_blocks = Column(JSON, default=list)
    # Cited sources: [{url, title, source}].
    references = Column(JSON, default=list)
    # Raw SerpAPI response for debugging / future reprocessing.
    raw_response = Column(JSON, default=dict)
    # True if SerpAPI returned a non-empty AI Overview (only ~36% of queries do).
    was_returned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)


class Recommendation(Base):
    """Claude-generated SEO / positioning recommendations for a product."""
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    ai_overview_snapshot_id = Column(Integer, ForeignKey("ai_overview_snapshots.id"), nullable=True)
    # 2-3 sentence high-level diagnosis.
    executive_summary = Column(Text, nullable=False)
    # Lists of short strings.
    strengths = Column(JSON, default=list)
    weaknesses = Column(JSON, default=list)
    # Prioritized actions: [{priority: "high"|"medium"|"low", title, rationale}].
    actions = Column(JSON, default=list)
    # How many scan results the rec is based on — lets frontend show "based on N queries".
    based_on_scan_count = Column(Integer, default=0)
    model_used = Column(String, default="claude")  # e.g. "claude-sonnet-4-5"
    created_at = Column(DateTime, default=utcnow)
