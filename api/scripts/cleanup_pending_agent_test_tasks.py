#!/usr/bin/env python3
"""Maintenance helper for cleaning rows from `agent_tasks`.

Defaults to deleting pending test tasks only.
Use `--all` for a full table purge, guarded by an explicit confirmation flag.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(API_DIR)
CONFIRM_TOKEN = "DELETE_ALL_AGENT_TASKS"

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(API_DIR, ".env"), override=False)
except ImportError:
    pass


def _mask_database_url(url: str) -> str:
    """Return a DB URL with credentials redacted."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<invalid-url>"
    netloc = parts.netloc
    if "@" in netloc:
        auth, host = netloc.rsplit("@", 1)
        username = auth.split(":", 1)[0]
        netloc = f"{username}:***@{host}" if username else f"***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _database_url_from_env() -> str:
    return (os.getenv("AGENT_TASKS_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()


def _database_url_from_fallback_env() -> str:
    return (
        os.getenv("AGENT_TASKS_DATABASE_URL_FALLBACK")
        or os.getenv("DATABASE_URL_FALLBACK")
        or ""
    ).strip()


def _table_exists(conn, table_name: str) -> bool:
    query = text(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema = 'public'
            AND table_name = :table_name
        )
        """
    )
    return bool(conn.execute(query, {"table_name": table_name}).scalar())


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete rows from agent_tasks table safely.")
    parser.add_argument("--dry-run", action="store_true", help="Report counts only, no delete.")
    parser.add_argument("--all", action="store_true", dest="delete_all", help="Delete all rows.")
    parser.add_argument("--batch-size", type=int, default=2000, help="Batch size for --all.")
    parser.add_argument("--status", type=str, default="pending", help="Status filter for targeted delete.")
    parser.add_argument("--task-type", type=str, default="test", help="Task type filter for targeted delete.")
    parser.add_argument("--database-url", type=str, default="", help="Explicit DB URL override.")
    parser.add_argument(
        "--use-fallback-url",
        action="store_true",
        help="Resolve DB URL via AGENT_TASKS_DATABASE_URL_FALLBACK or DATABASE_URL_FALLBACK.",
    )
    parser.add_argument(
        "--confirm-delete-all",
        type=str,
        default="",
        help=f"Required with --all (unless --dry-run): {CONFIRM_TOKEN}",
    )
    args = parser.parse_args()

    if args.database_url and args.use_fallback_url:
        print("Choose only one URL source: --database-url or --use-fallback-url.")
        return 2

    try:
        if args.database_url:
            database_url = args.database_url.strip()
        elif args.use_fallback_url:
            database_url = _database_url_from_fallback_env()
        else:
            database_url = _database_url_from_env()
    except subprocess.CalledProcessError as exc:
        print(f"Failed to resolve fallback DB URL: {exc}")
        return 2

    if not database_url:
        print("No DB URL found (tried AGENT_TASKS_DATABASE_URL/DATABASE_URL).")
        return 2

    print(f"Target DB: {_mask_database_url(database_url)}")

    if args.delete_all and not args.dry_run and args.confirm_delete_all != CONFIRM_TOKEN:
        print(
            "Refusing full delete without explicit confirmation. "
            f"Add --confirm-delete-all {CONFIRM_TOKEN}"
        )
        return 2

    batch_size = max(100, min(50000, args.batch_size))
    engine = create_engine(database_url, pool_pre_ping=True)

    with engine.connect() as conn:
        if not _table_exists(conn, "agent_tasks"):
            print("Table `agent_tasks` does not exist in target DB.")
            return 2

        if args.delete_all:
            total = int(conn.execute(text("SELECT COUNT(*) FROM agent_tasks")).scalar() or 0)
            if args.dry_run:
                print(f"Would delete all {total} task(s).")
                return 0

            deleted = 0
            while True:
                if database_url.startswith("postgresql"):
                    result = conn.execute(
                        text(
                            """
                            DELETE FROM agent_tasks
                            WHERE id IN (
                                SELECT id
                                FROM agent_tasks
                                ORDER BY id
                                LIMIT :lim
                            )
                            """
                        ),
                        {"lim": batch_size},
                    )
                else:
                    result = conn.execute(
                        text("DELETE FROM agent_tasks WHERE rowid IN (SELECT rowid FROM agent_tasks LIMIT :lim)"),
                        {"lim": batch_size},
                    )
                conn.commit()
                batch_deleted = int(result.rowcount or 0)
                deleted += batch_deleted
                if batch_deleted > 0:
                    print(f"Deleted batch: {batch_deleted} (total so far: {deleted})")
                if batch_deleted < batch_size:
                    break
            print(f"Deleted {deleted} task(s) total.")
            return 0

        params = {"status": args.status, "task_type": args.task_type}
        matching = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM agent_tasks
                    WHERE status = :status
                      AND task_type = :task_type
                    """
                ),
                params,
            ).scalar()
            or 0
        )

        if args.dry_run:
            print(
                f"Would delete {matching} task(s) where status='{args.status}' "
                f"and task_type='{args.task_type}'."
            )
            return 0

        result = conn.execute(
            text(
                """
                DELETE FROM agent_tasks
                WHERE status = :status
                  AND task_type = :task_type
                """
            ),
            params,
        )
        conn.commit()
        deleted = int(result.rowcount or 0)
        print(
            f"Deleted {deleted} task(s) where status='{args.status}' "
            f"and task_type='{args.task_type}'."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
