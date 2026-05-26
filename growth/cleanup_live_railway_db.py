#!/usr/bin/env python3
"""Clean fake users/products from the live Railway Postgres database.

Default behavior is a dry run. Use --execute to apply changes.

Policy:
- Keep the first 10 users by id.
- Also keep product-owner user ids 1 and 14 so their products are not orphaned.
- Keep only products where user_id is 1 or 14.
- Delete dependent rows before deleting products/users.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKUP_DIR = ROOT / "growth" / "live-db-cleanup-backups"

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
    parser = argparse.ArgumentParser(description="Cleanup live Railway fake users/products.")
    parser.add_argument("--execute", action="store_true", help="Apply deletes. Omit for dry run.")
    parser.add_argument("--keep-first-users", type=int, default=10)
    parser.add_argument(
        "--keep-product-user-id",
        action="append",
        type=int,
        default=None,
        help="User id whose products should be kept. Repeatable. Defaults to 1 and 14.",
    )
    parser.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    return parser.parse_args()


def json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def db_url() -> str:
    url = (
        os.environ.get("DATABASE_PUBLIC_URL")
        or os.environ.get("POSTGRES_PUBLIC_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
    )
    if not url:
        raise SystemExit("DATABASE_PUBLIC_URL/DATABASE_URL/POSTGRES_URL is not set.")
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url.removeprefix("postgresql+asyncpg://")
    return url


def safe_db_label(url: str) -> str:
    parsed = urlparse(url)
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname or ''}{port}/{parsed.path.lstrip('/')}"


def qi(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return f'"{identifier}"'


def fetch_ids(cur, sql: str, params: tuple = ()) -> list[int]:
    cur.execute(sql, params)
    return [int(row["id"]) for row in cur.fetchall()]


def existing_tables(cur) -> set[str]:
    cur.execute(
        """
        select table_name
        from information_schema.tables
        where table_schema = 'public'
        """
    )
    return {row["table_name"] for row in cur.fetchall()}


def foreign_keys(cur) -> list[dict]:
    cur.execute(
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
        """
    )
    return list(cur.fetchall())


def table_count(cur, table: str) -> int:
    cur.execute(f"select count(*) as count from {qi(table)}")
    return int(cur.fetchone()["count"])


def rows_by_ids(cur, table: str, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    cur.execute(f"select * from {qi(table)} where id = any(%s) order by id", (ids,))
    return list(cur.fetchall())


def delete_by_ids(cur, table: str, ids: list[int]) -> int:
    if not ids:
        return 0
    cur.execute(f"delete from {qi(table)} where id = any(%s)", (ids,))
    return int(cur.rowcount)


def main() -> int:
    args = parse_args()
    keep_product_user_ids = args.keep_product_user_id or [1, 14]
    backup_dir = Path(args.backup_dir)

    url = db_url()
    print(f"Target database: {safe_db_label(url)}")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"Keep first users: {args.keep_first_users}")
    print(f"Keep products for user ids: {keep_product_user_ids}")

    conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            tables = existing_tables(cur)
            missing = {"users", "products"} - tables
            if missing:
                raise SystemExit(f"Missing expected tables: {sorted(missing)}")

            fks = foreign_keys(cur)
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

            first_user_ids = fetch_ids(
                cur,
                "select id from users order by id asc limit %s",
                (args.keep_first_users,),
            )
            keep_user_ids = sorted(set(first_user_ids) | set(keep_product_user_ids))

            user_ids_delete = fetch_ids(
                cur,
                "select id from users where not (id = any(%s)) order by id",
                (keep_user_ids,),
            )
            product_ids_keep = fetch_ids(
                cur,
                "select id from products where user_id = any(%s) order by id",
                (keep_product_user_ids,),
            )
            product_ids_delete = fetch_ids(
                cur,
                "select id from products where not (user_id = any(%s)) order by id",
                (keep_product_user_ids,),
            )

            scan_result_ids_delete = (
                fetch_ids(
                    cur,
                    "select id from scan_results where product_id = any(%s) order by id",
                    (product_ids_delete,),
                )
                if "scan_results" in tables
                else []
            )

            overview_ids_delete = (
                fetch_ids(
                    cur,
                    "select id from ai_overview_snapshots where product_id = any(%s) order by id",
                    (product_ids_delete,),
                )
                if "ai_overview_snapshots" in tables
                else []
            )

            recommendation_ids_delete = (
                fetch_ids(
                    cur,
                    """
                    select id from recommendations
                    where product_id = any(%s)
                       or ai_overview_snapshot_id = any(%s)
                    order by id
                    """,
                    (product_ids_delete, overview_ids_delete),
                )
                if "recommendations" in tables
                else []
            )

            website_audit_ids_delete = (
                fetch_ids(
                    cur,
                    """
                    select id from website_audits
                    where product_id = any(%s)
                       or user_id = any(%s)
                    order by id
                    """,
                    (product_ids_delete, user_ids_delete),
                )
                if "website_audits" in tables
                else []
            )

            notification_setting_ids_delete = (
                fetch_ids(
                    cur,
                    "select id from notification_settings where user_id = any(%s) order by id",
                    (user_ids_delete,),
                )
                if "notification_settings" in tables
                else []
            )

            cdn_connection_ids_delete = (
                fetch_ids(
                    cur,
                    "select id from cdn_connections where user_id = any(%s) order by id",
                    (user_ids_delete,),
                )
                if "cdn_connections" in tables
                else []
            )

            bot_visit_ids_delete = (
                fetch_ids(
                    cur,
                    """
                    select id from bot_visits
                    where user_id = any(%s)
                       or cdn_connection_id = any(%s)
                    order by id
                    """,
                    (user_ids_delete, cdn_connection_ids_delete),
                )
                if "bot_visits" in tables
                else []
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
                print(f"- {table}: {table_count(cur, table)}")

            print("\nKeep users:", keep_user_ids)
            print("Keep product ids:", product_ids_keep)
            print("\nDelete plan:")
            for table in DELETE_ORDER:
                if table in tables:
                    print(f"- {table}: {len(delete_plan[table])} rows")

            backup = {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "target_database": safe_db_label(url),
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
                    backup["deleted_rows"][table] = rows_by_ids(cur, table, delete_plan[table])

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
                conn.rollback()
                return 0

            for table in DELETE_ORDER:
                if table not in tables:
                    continue
                deleted_count = delete_by_ids(cur, table, delete_plan[table])
                if deleted_count:
                    print(f"Deleted {deleted_count} from {table}")

            conn.commit()
            print("\nCleanup committed.")

            print("\nPost-cleanup counts:")
            for table in sorted(HANDLED_TABLES & tables):
                print(f"- {table}: {table_count(cur, table)}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
