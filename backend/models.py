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
