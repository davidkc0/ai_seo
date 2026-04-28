import secrets
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

# Railway provides postgresql:// but SQLAlchemy async needs postgresql+asyncpg://
_db_url = settings.database_url
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(_db_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create tables + run lightweight in-place migrations for SQLite.

    SQLAlchemy create_all() only creates missing tables; it won't add columns to
    an existing table. We handle the small number of columns we've added post-v1
    with targeted ADD COLUMN statements + a data backfill pass.
    """
    # Ensure every model is registered with Base.metadata before create_all.
    # Without this import, tables for models only imported elsewhere (e.g.
    # Recommendation, AIOverviewSnapshot) may silently not get created.
    import models as _models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_user_unsubscribe_token_column)
        await conn.run_sync(_ensure_notification_marketing_column)
        await conn.run_sync(_ensure_user_email_verified_column)
        await conn.run_sync(_ensure_cdn_connection_vercel_columns)

    # Backfill any null tokens (new column on existing rows).
    await _backfill_unsubscribe_tokens()


def _ensure_user_unsubscribe_token_column(sync_conn):
    """Add users.unsubscribe_token if it doesn't exist. Idempotent."""
    inspector = inspect(sync_conn)
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "unsubscribe_token" not in cols:
        print("[Migration] Adding users.unsubscribe_token column")
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN unsubscribe_token VARCHAR(64)"))
        # Unique index (nulls are OK — we'll backfill next).
        sync_conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_unsubscribe_token "
            "ON users (unsubscribe_token)"
        ))


def _ensure_notification_marketing_column(sync_conn):
    """Add notification_settings.marketing_emails if missing. Defaults True."""
    inspector = inspect(sync_conn)
    if "notification_settings" not in inspector.get_table_names():
        return  # brand-new install, create_all will build it with the column
    cols = {c["name"] for c in inspector.get_columns("notification_settings")}
    if "marketing_emails" not in cols:
        print("[Migration] Adding notification_settings.marketing_emails column")
        sync_conn.execute(text(
            "ALTER TABLE notification_settings "
            "ADD COLUMN marketing_emails BOOLEAN DEFAULT TRUE"
        ))


def _ensure_user_email_verified_column(sync_conn):
    """Add users.email_verified if missing, then backfill TRUE for every existing
    row so we don't lock current customers out of scans on rollout. Idempotent.

    SQLite stores booleans as INT, Postgres has a real BOOLEAN type — emit the
    appropriate literals for each dialect.
    """
    inspector = inspect(sync_conn)
    if "users" not in inspector.get_table_names():
        return  # brand-new install — create_all will build it with the column
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "email_verified" not in cols:
        print("[Migration] Adding users.email_verified column (+ backfill TRUE)")
        dialect = sync_conn.dialect.name
        default_lit = "0" if dialect == "sqlite" else "FALSE"
        true_lit = "1" if dialect == "sqlite" else "TRUE"
        sync_conn.execute(text(
            f"ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT {default_lit}"
        ))
        # Every row that exists right now is a real customer — flip them all
        # to verified so the new gate doesn't suddenly block paying users.
        sync_conn.execute(text(f"UPDATE users SET email_verified = {true_lit}"))


def _ensure_cdn_connection_vercel_columns(sync_conn):
    """Add Vercel-specific columns to cdn_connections if missing.

    Vercel uses push-based Log Drains, which need three extra fields:
      - project_id     → Vercel project we registered the drain for
      - drain_id       → Vercel's ID for the drain (used to delete on disconnect)
      - webhook_secret → HMAC secret for verifying drain payloads

    All three are nullable so existing Cloudflare rows are unaffected.
    """
    inspector = inspect(sync_conn)
    if "cdn_connections" not in inspector.get_table_names():
        return  # brand-new install, create_all will build it with the columns
    cols = {c["name"] for c in inspector.get_columns("cdn_connections")}
    for col_name, col_type in (
        ("project_id", "VARCHAR"),
        ("drain_id", "VARCHAR"),
        ("webhook_secret", "VARCHAR"),
    ):
        if col_name not in cols:
            print(f"[Migration] Adding cdn_connections.{col_name} column")
            sync_conn.execute(text(
                f"ALTER TABLE cdn_connections ADD COLUMN {col_name} {col_type}"
            ))


async def _backfill_unsubscribe_tokens():
    """Generate tokens for any users missing one. Safe to run every boot."""
    from models import User  # local import to avoid circular
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.id).where(User.unsubscribe_token.is_(None))
        )
        user_ids = [row[0] for row in result.all()]
        if not user_ids:
            return
        print(f"[Migration] Backfilling unsubscribe_token for {len(user_ids)} users")
        for uid in user_ids:
            await session.execute(
                update(User)
                .where(User.id == uid)
                .values(unsubscribe_token=secrets.token_urlsafe(32))
            )
        await session.commit()
