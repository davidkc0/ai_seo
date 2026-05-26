#!/usr/bin/env python3
"""Safely remove fake users/products from the production database.

Default behavior is a dry run. Use --execute to apply changes.

Cleanup policy:
- Keep the first 10 users by id.
- Also keep product-owner user ids 1 and 14 so kept products are not orphaned.
- Keep only products where user_id is 1 or 14.
- Delete known dependent rows before deleting products/users.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import create_async_engine


HANDLED_TABLES = {
    "users",
    "products",
    "scan_results",
    "ai_overview_snapshots",
    "recommendations",
    "website_audits",
    "notification_settings",
    "cdn_connections",
    "bot_visits",
}

TARGET_PARENT_TABLES = {
    "users",
    "products",
    "cdn_connections",
    "ai_overview_snapshots",
}

DELETE_ORDER = [
    "bot_visits",
    "recommendations",
    "ai_overview_snapshots",
    "scan_results",
    "website_audits",
    "cdn_connections",
    "notification_settings",
    "products",
    "users",
]

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup live fake users/products.")
    parser.add_argument("--execute", action="store_true", help="Apply deletes. Omit for dry run.")
    parser.add_argument("--keep-first-users", type=int, default=10)
    parser.add_argument(
        "--keep-product-user-id",
        action="append",
        type=int,
        default=None,
        help="User id whose products should be kept. Repeatable. Defaults to 1 and 14.",
    )
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="Directory for the JSON backup/preview. Defaults beside SQLite DB or ./cleanup-backups.",
    )
    return parser.parse_args()


def json_default(value: Any) -> str | float:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def database_url() -> str:
    url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("DATABASE_PUBLIC_URL")
        or os.environ.get("POSTGRES_URL")
    )
    if not url:
        raise SystemExit("DATABASE_URL/DATABASE_PUBLIC_URL/POSTGRES_URL is not set.")

    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


def safe_db_label(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.startswith("sqlite"):
        return f"{parsed.scheme}:{unquote(parsed.path)}"
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{host}{port}/{parsed.path.lstrip('/')}"


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def default_backup_dir(url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme.startswith("sqlite") and parsed.path:
        db_path = Path(unquote(parsed.path))
        if db_path.is_absolute():
            return db_path.parent / "live-db-cleanup-backups"
    return Path.cwd() / "cleanup-backups"


def qi(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return f'"{identifier}"'


def row_dict(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


async def fetch_dicts(conn, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = await conn.execute(text(sql), params or {})
    return [row_dict(row) for row in result.fetchall()]


async def fetch_ids(
    conn,
    sql: str,
    params: dict[str, Any] | None = None,
    expanding: tuple[str, ...] = (),
) -> list[int]:
    stmt = text(sql)
    for name in expanding:
        stmt = stmt.bindparams(bindparam(name, expanding=True))
    result = await conn.execute(stmt, params or {})
    return [int(row._mapping["id"]) for row in result.fetchall()]


async def existing_tables(conn, sqlite_mode: bool) -> set[str]:
    if sqlite_mode:
        rows = await fetch_dicts(
            conn,
            """
            select name as table_name
            from sqlite_master
            where type = 'table'
              and name not like 'sqlite_%'
            """,
        )
    else:
        rows = await fetch_dicts(
            conn,
            """
            select table_name
            from information_schema.tables
            where table_schema = 'public'
            """,
        )
    return {str(row["table_name"]) for row in rows}


async def foreign_keys(conn, tables: set[str], sqlite_mode: bool) -> list[dict[str, str]]:
    if sqlite_mode:
        keys: list[dict[str, str]] = []
        for table in sorted(tables):
            result = await conn.execute(text(f"pragma foreign_key_list({qi(table)})"))
            for row in result.fetchall():
                mapping = row._mapping
                keys.append(
                    {
                        "table_name": table,
                        "column_name": str(mapping["from"]),
                        "foreign_table_name": str(mapping["table"]),
                        "foreign_column_name": str(mapping["to"]),
                    }
                )
        return keys

    return await fetch_dicts(
        conn,
        """
        select
            tc.table_name,
            kcu.column_name,
            ccu.table_name as foreign_table_name,
            ccu.column_name as foreign_column_name
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu
            on tc.constraint_name = kcu.constraint_name
           and tc.table_schema = kcu.table_schema
        join information_schema.constraint_column_usage ccu
            on ccu.constraint_name = tc.constraint_name
           and ccu.table_schema = tc.table_schema
        where tc.constraint_type = 'FOREIGN KEY'
          and tc.table_schema = 'public'
          and ccu.table_name in (
              'users',
              'products',
              'cdn_connections',
              'ai_overview_snapshots'
          )
        order by ccu.table_name, tc.table_name, kcu.column_name
        """,
    )


async def table_count(conn, table: str) -> int:
    result = await conn.execute(text(f"select count(*) as count from {qi(table)}"))
    return int(result.fetchone()._mapping["count"])


async def rows_by_ids(conn, table: str, ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    stmt = text(f"select * from {qi(table)} where id in :ids order by id").bindparams(
        bindparam("ids", expanding=True)
    )
    result = await conn.execute(stmt, {"ids": ids})
    return [row_dict(row) for row in result.fetchall()]


async def delete_by_ids(conn, table: str, ids: list[int]) -> int:
    if not ids:
        return 0
    stmt = text(f"delete from {qi(table)} where id in :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    result = await conn.execute(stmt, {"ids": ids})
    return int(result.rowcount or 0)


async def run() -> int:
    args = parse_args()
    keep_product_user_ids = args.keep_product_user_id or [1, 14]
    url = database_url()
    sqlite_mode = is_sqlite(url)
    backup_dir = Path(args.backup_dir) if args.backup_dir else default_backup_dir(url)

    print(f"Target database: {safe_db_label(url)}")
    print(f"Driver: {'SQLite' if sqlite_mode else 'Postgres'}")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"Keep first users: {args.keep_first_users}")
    print(f"Keep products for user ids: {keep_product_user_ids}")

    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            tables = await existing_tables(conn, sqlite_mode)
            missing = {"users", "products"} - tables
            if missing:
                raise SystemExit(f"Missing expected tables: {sorted(missing)}")

            fks = await foreign_keys(conn, tables, sqlite_mode)
            unknown_fk_tables = sorted(
                {
                    row["table_name"]
                    for row in fks
                    if row["foreign_table_name"] in TARGET_PARENT_TABLES
                    and row["table_name"] not in HANDLED_TABLES
                }
            )
            if unknown_fk_tables:
                raise SystemExit(
                    "Refusing to run because unknown tables reference cleanup targets: "
                    + ", ".join(unknown_fk_tables)
                )

            first_user_ids = await fetch_ids(
                conn,
                "select id from users order by id asc limit :limit",
                {"limit": args.keep_first_users},
            )
            keep_user_ids = sorted(set(first_user_ids) | set(keep_product_user_ids))

            user_ids_delete = await fetch_ids(
                conn,
                "select id from users where id not in :ids order by id",
                {"ids": keep_user_ids},
                ("ids",),
            )
            product_ids_keep = await fetch_ids(
                conn,
                "select id from products where user_id in :ids order by id",
                {"ids": keep_product_user_ids},
                ("ids",),
            )
            product_ids_delete = await fetch_ids(
                conn,
                "select id from products where user_id not in :ids order by id",
                {"ids": keep_product_user_ids},
                ("ids",),
            )

            scan_result_ids_delete = (
                await fetch_ids(
                    conn,
                    "select id from scan_results where product_id in :ids order by id",
                    {"ids": product_ids_delete},
                    ("ids",),
                )
                if "scan_results" in tables and product_ids_delete
                else []
            )

            overview_ids_delete = (
                await fetch_ids(
                    conn,
                    "select id from ai_overview_snapshots where product_id in :ids order by id",
                    {"ids": product_ids_delete},
                    ("ids",),
                )
                if "ai_overview_snapshots" in tables and product_ids_delete
                else []
            )

            recommendation_ids_delete = []
            if "recommendations" in tables:
                if product_ids_delete and overview_ids_delete:
                    recommendation_ids_delete = await fetch_ids(
                        conn,
                        """
                        select id from recommendations
                        where product_id in :product_ids
                           or ai_overview_snapshot_id in :overview_ids
                        order by id
                        """,
                        {"product_ids": product_ids_delete, "overview_ids": overview_ids_delete},
                        ("product_ids", "overview_ids"),
                    )
                elif product_ids_delete:
                    recommendation_ids_delete = await fetch_ids(
                        conn,
                        "select id from recommendations where product_id in :ids order by id",
                        {"ids": product_ids_delete},
                        ("ids",),
                    )
                elif overview_ids_delete:
                    recommendation_ids_delete = await fetch_ids(
                        conn,
                        "select id from recommendations where ai_overview_snapshot_id in :ids order by id",
                        {"ids": overview_ids_delete},
                        ("ids",),
                    )

            website_audit_ids_delete = []
            if "website_audits" in tables:
                if product_ids_delete and user_ids_delete:
                    website_audit_ids_delete = await fetch_ids(
                        conn,
                        """
                        select id from website_audits
                        where product_id in :product_ids
                           or user_id in :user_ids
                        order by id
                        """,
                        {"product_ids": product_ids_delete, "user_ids": user_ids_delete},
                        ("product_ids", "user_ids"),
                    )
                elif product_ids_delete:
                    website_audit_ids_delete = await fetch_ids(
                        conn,
                        "select id from website_audits where product_id in :ids order by id",
                        {"ids": product_ids_delete},
                        ("ids",),
                    )
                elif user_ids_delete:
                    website_audit_ids_delete = await fetch_ids(
                        conn,
                        "select id from website_audits where user_id in :ids order by id",
                        {"ids": user_ids_delete},
                        ("ids",),
                    )

            notification_setting_ids_delete = (
                await fetch_ids(
                    conn,
                    "select id from notification_settings where user_id in :ids order by id",
                    {"ids": user_ids_delete},
                    ("ids",),
                )
                if "notification_settings" in tables and user_ids_delete
                else []
            )

            cdn_connection_ids_delete = (
                await fetch_ids(
                    conn,
                    "select id from cdn_connections where user_id in :ids order by id",
                    {"ids": user_ids_delete},
                    ("ids",),
                )
                if "cdn_connections" in tables and user_ids_delete
                else []
            )

            bot_visit_ids_delete = []
            if "bot_visits" in tables:
                if user_ids_delete and cdn_connection_ids_delete:
                    bot_visit_ids_delete = await fetch_ids(
                        conn,
                        """
                        select id from bot_visits
                        where user_id in :user_ids
                           or cdn_connection_id in :connection_ids
                        order by id
                        """,
                        {"user_ids": user_ids_delete, "connection_ids": cdn_connection_ids_delete},
                        ("user_ids", "connection_ids"),
                    )
                elif user_ids_delete:
                    bot_visit_ids_delete = await fetch_ids(
                        conn,
                        "select id from bot_visits where user_id in :ids order by id",
                        {"ids": user_ids_delete},
                        ("ids",),
                    )
                elif cdn_connection_ids_delete:
                    bot_visit_ids_delete = await fetch_ids(
                        conn,
                        "select id from bot_visits where cdn_connection_id in :ids order by id",
                        {"ids": cdn_connection_ids_delete},
                        ("ids",),
                    )

            delete_plan = {
                "bot_visits": bot_visit_ids_delete,
                "recommendations": recommendation_ids_delete,
                "ai_overview_snapshots": overview_ids_delete,
                "scan_results": scan_result_ids_delete,
                "website_audits": website_audit_ids_delete,
                "cdn_connections": cdn_connection_ids_delete,
                "notification_settings": notification_setting_ids_delete,
                "products": product_ids_delete,
                "users": user_ids_delete,
            }

            print("\nCurrent counts:")
            for table in sorted(HANDLED_TABLES & tables):
                print(f"- {table}: {await table_count(conn, table)}")

            print("\nKeep users:", keep_user_ids)
            print("Keep product ids:", product_ids_keep)
            print("\nDelete plan:")
            for table in DELETE_ORDER:
                if table in tables:
                    print(f"- {table}: {len(delete_plan[table])} rows")

            backup = {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "target_database": safe_db_label(url),
                "driver": "sqlite" if sqlite_mode else "postgres",
                "mode": "execute" if args.execute else "dry-run",
                "keep_first_user_ids": first_user_ids,
                "keep_user_ids": keep_user_ids,
                "keep_product_user_ids": keep_product_user_ids,
                "keep_product_ids": product_ids_keep,
                "delete_plan_counts": {table: len(ids) for table, ids in delete_plan.items()},
                "deleted_rows": {},
            }
            for table in DELETE_ORDER:
                if table in tables:
                    backup["deleted_rows"][table] = await rows_by_ids(conn, table, delete_plan[table])

            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / (
                "cleanup-backup-"
                + datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                + ("-execute" if args.execute else "-dry-run")
                + ".json"
            )
            backup_path.write_text(json.dumps(backup, indent=2, default=json_default), encoding="utf-8")
            print(f"\nWrote backup/preview: {backup_path}")

            if not args.execute:
                print("\nDry run only. Re-run with --execute to delete these rows.")
                await conn.rollback()
                return 0

            for table in DELETE_ORDER:
                if table not in tables:
                    continue
                deleted_count = await delete_by_ids(conn, table, delete_plan[table])
                if deleted_count:
                    print(f"Deleted {deleted_count} from {table}")

            print("\nCleanup committed.")

            print("\nPost-cleanup counts:")
            for table in sorted(HANDLED_TABLES & tables):
                print(f"- {table}: {await table_count(conn, table)}")
    finally:
        await engine.dispose()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(run()))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
