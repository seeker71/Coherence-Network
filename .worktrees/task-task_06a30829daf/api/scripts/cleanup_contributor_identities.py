#!/usr/bin/env python3
"""Normalize contributor identities and merge duplicate contributor rows.

Usage:
  cd api
  python scripts/cleanup_contributor_identities.py --dry-run
  python scripts/cleanup_contributor_identities.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text

from app.services.contributor_hygiene import is_internal_contributor_email, normalize_contributor_email


def _database_url() -> str:
    url = str(os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required")
    return url


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return datetime.max
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.max


def _canonical_rank(row: dict[str, Any], normalized_email: str) -> tuple[int, int, datetime, str]:
    type_value = str(row.get("type") or "").strip().upper()
    is_internal = is_internal_contributor_email(normalized_email)
    # Prefer non-internal HUMAN rows, then earliest created_at, then stable id.
    internal_score = 1 if is_internal else 0
    type_score = 0 if type_value == "HUMAN" else 1
    created_at = _parse_datetime(row.get("created_at"))
    return (internal_score, type_score, created_at, str(row.get("id") or ""))


def _load_contributors(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            """
            SELECT id, type, name, email, created_at
            FROM contributors
            ORDER BY created_at ASC
            """
        )
    ).mappings()
    return [dict(row) for row in rows]


def _collect_merge_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_email: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped_no_email = 0
    for row in rows:
        normalized = normalize_contributor_email(str(row.get("email") or ""))
        if not normalized:
            skipped_no_email += 1
            continue
        row_copy = dict(row)
        row_copy["_normalized_email"] = normalized
        by_email[normalized].append(row_copy)

    groups: list[dict[str, Any]] = []
    duplicate_rows = 0
    for normalized_email, group_rows in sorted(by_email.items(), key=lambda item: item[0]):
        ranked = sorted(group_rows, key=lambda row: _canonical_rank(row, normalized_email))
        canonical = ranked[0]
        duplicates = ranked[1:]
        duplicate_rows += len(duplicates)
        groups.append(
            {
                "normalized_email": normalized_email,
                "canonical_id": str(canonical.get("id") or ""),
                "canonical_name": str(canonical.get("name") or ""),
                "canonical_type": str(canonical.get("type") or ""),
                "canonical_target_type": ("SYSTEM" if is_internal_contributor_email(normalized_email) else "HUMAN"),
                "duplicate_ids": [str(row.get("id") or "") for row in duplicates],
                "row_count": len(group_rows),
            }
        )

    return {
        "total_rows": len(rows),
        "groups": groups,
        "unique_emails": len(groups),
        "duplicate_rows": duplicate_rows,
        "skipped_no_email": skipped_no_email,
    }


def _apply_plan(conn: Any, plan: dict[str, Any]) -> dict[str, Any]:
    groups = [row for row in plan.get("groups", []) if isinstance(row, dict)]
    updates = {
        "merged_contributors": 0,
        "moved_contributions": 0,
        "updated_canonical_rows": 0,
    }

    for group in groups:
        normalized_email = str(group.get("normalized_email") or "").strip()
        canonical_id = str(group.get("canonical_id") or "").strip()
        canonical_type = str(group.get("canonical_target_type") or "HUMAN").strip().upper()
        duplicate_ids = [str(item).strip() for item in group.get("duplicate_ids", []) if str(item).strip()]
        if not normalized_email or not canonical_id:
            continue

        for duplicate_id in duplicate_ids:
            moved = conn.execute(
                text(
                    """
                    UPDATE contributions
                    SET contributor_id = :canonical_id
                    WHERE contributor_id = :duplicate_id
                    """
                ),
                {"canonical_id": canonical_id, "duplicate_id": duplicate_id},
            )
            updates["moved_contributions"] += int(moved.rowcount or 0)
            deleted = conn.execute(
                text("DELETE FROM contributors WHERE id = :duplicate_id"),
                {"duplicate_id": duplicate_id},
            )
            if int(deleted.rowcount or 0) > 0:
                updates["merged_contributors"] += int(deleted.rowcount or 0)

        updated = conn.execute(
            text(
                """
                UPDATE contributors
                SET email = :normalized_email, type = :canonical_type
                WHERE id = :canonical_id
                """
            ),
            {
                "normalized_email": normalized_email,
                "canonical_type": canonical_type,
                "canonical_id": canonical_id,
            },
        )
        updates["updated_canonical_rows"] += int(updated.rowcount or 0)

    return updates


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize and merge contributor identity rows.")
    parser.add_argument("--apply", action="store_true", help="Apply updates (default is dry-run).")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run output.")
    args = parser.parse_args()

    apply_changes = bool(args.apply and not args.dry_run)
    engine = create_engine(_database_url(), pool_pre_ping=True)

    with engine.begin() as conn:
        rows = _load_contributors(conn)
        plan = _collect_merge_plan(rows)
        result: dict[str, Any] = {
            "mode": "apply" if apply_changes else "dry-run",
            "plan": plan,
            "applied": {},
        }
        if apply_changes:
            result["applied"] = _apply_plan(conn, plan)
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

