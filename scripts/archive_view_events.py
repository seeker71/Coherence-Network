#!/usr/bin/env python3
"""Move days of asset_view_events into cold-tier storage.

Pattern:

  hot tier (Postgres asset_view_events)
    └─ archive day D:
       1. SELECT * FROM asset_view_events WHERE created_at on D
       2. JSONL → gzip → SHA-256
       3. ``gh release upload archive/view-events/D events-D.jsonl.gz``
       4. INSERT INTO view_events_archive (tombstone with URL + SHA)
       5. DELETE hot rows for D
       6. VACUUM (sqlite only)

The tombstone (~150 bytes) replaces ~2 MB of hot rows per day with
full retrievability via SHA-256-verified GitHub-release fetch.

Usage:

    # Dry-run — see what would be archived
    python3 scripts/archive_view_events.py --keep-days 30 --dry-run

    # Archive everything older than 30 days, in chronological order
    python3 scripts/archive_view_events.py --keep-days 30 --apply

    # Archive a single specific day (re-archive / repair)
    python3 scripts/archive_view_events.py --day 2026-04-20 --apply

    # Different repo (default: $COHERENCE_ARCHIVE_REPO or seeker71/Coherence-Network)
    python3 scripts/archive_view_events.py --keep-days 30 --apply \\
        --repo seeker71/coherence-network-archive

Requires ``gh`` CLI authenticated on the host. Idempotent: re-running
on an already-archived day verifies the existing tombstone and
re-uploads only if the SHA changed (e.g. after a hot-tier repair).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_ROOT = os.path.join(REPO_ROOT, "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from app.services import view_events_archive_service as vea  # noqa: E402
from app.services.unified_db import session, ensure_schema  # noqa: E402
from sqlalchemy import func  # noqa: E402

log = logging.getLogger("archive_view_events")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def _human(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def days_with_hot_events_older_than(keep_days: int) -> list[date]:
    """Return UTC dates that have at least one row older than the
    keep window. Sorted ascending so we archive oldest-first."""
    ensure_schema()
    from app.services.read_tracking_service import AssetViewEvent

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    with session() as s:
        # Pull distinct days; func.date works on both sqlite and postgres.
        rows = (
            s.query(func.date(AssetViewEvent.created_at).label("d"))
            .filter(AssetViewEvent.created_at < cutoff)
            .distinct()
            .all()
        )
    days: list[date] = []
    for (d,) in rows:
        if isinstance(d, date) and not isinstance(d, datetime):
            days.append(d)
        elif isinstance(d, datetime):
            days.append(d.date())
        elif isinstance(d, str):
            days.append(date.fromisoformat(d))
    return sorted(days)


def archive_one_day(target_day: date, *, repo: str, apply: bool) -> dict:
    """Archive a single day. Returns a summary dict."""
    log.info("==> day %s", target_day.isoformat())

    payload, manifest = vea.serialise_day(target_day)
    log.info(
        "    %s events · original %s · compressed %s · sha256=%s…",
        manifest["event_count"],
        _human(manifest["bytes_original"]),
        _human(manifest["bytes_compressed"]),
        manifest["sha256"][:12],
    )

    if manifest["event_count"] == 0:
        log.info("    no events for this day — skipping (no upload, no tombstone)")
        return {"day": target_day.isoformat(), "skipped": "no events"}

    # Idempotency: if a tombstone exists with the same sha256, the
    # archive is already current — skip the upload but ensure hot
    # rows are gone.
    existing = vea.get_tombstone(target_day)
    if existing and existing.sha256 == manifest["sha256"]:
        log.info("    tombstone already current (sha256 matches)")
        if apply:
            removed = vea.delete_hot_rows_for_day(target_day)
            log.info("    deleted %s hot rows for day", removed)
            return {"day": target_day.isoformat(), "skipped_upload": True, "deleted": removed}
        return {"day": target_day.isoformat(), "skipped_upload": True, "deleted": 0}

    if not apply:
        log.info("    (dry-run) — would upload %s and write tombstone",
                 vea._gh_asset_name(target_day))
        return {"day": target_day.isoformat(), "would_upload": True}

    # Upload to cold tier.
    archive_url = vea.upload_to_github_releases(
        target_day,
        payload,
        repo=repo,
        notes=(
            f"Daily cold-tier archive of asset_view_events for "
            f"{target_day.isoformat()}.\n\n"
            f"Event count: {manifest['event_count']}\n"
            f"Original size: {_human(manifest['bytes_original'])}\n"
            f"Compressed size: {_human(manifest['bytes_compressed'])}\n"
            f"SHA-256: {manifest['sha256']}\n\n"
            f"Format: gzipped JSON Lines, one event per line, ordered "
            f"by created_at ascending. Verify integrity by computing "
            f"SHA-256 of the gzipped asset and comparing to this note."
        ),
    )
    log.info("    uploaded → %s", archive_url)

    # Tombstone.
    tomb = vea.record_tombstone(
        target_day,
        manifest=manifest,
        archive_url=archive_url,
        archive_provider=vea.DEFAULT_PROVIDER,
        archive_tag=vea._gh_tag_for(target_day),
    )
    log.info("    tombstone recorded · ETA retrieval %.2fs", tomb.estimated_retrieval_seconds or 0)

    # Delete hot rows.
    removed = vea.delete_hot_rows_for_day(target_day)
    log.info("    deleted %s hot rows for day", removed)

    return {
        "day": target_day.isoformat(),
        "event_count": manifest["event_count"],
        "bytes_compressed": manifest["bytes_compressed"],
        "bytes_original": manifest["bytes_original"],
        "sha256": manifest["sha256"],
        "archive_url": archive_url,
        "deleted": removed,
    }


def vacuum_if_sqlite() -> None:
    try:
        from app.services.unified_db import _engine  # type: ignore
        if "sqlite" in str(getattr(_engine, "url", "")):
            with session() as s:
                s.execute("VACUUM")
                log.info("(sqlite) VACUUM — pages reclaimed")
    except Exception as e:  # pragma: no cover
        log.warning("vacuum step skipped: %s", e)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--keep-days", type=int, default=30,
        help="Archive days older than N days (default: 30). Ignored if --day given.",
    )
    p.add_argument(
        "--day", type=str, default=None,
        help="Archive a single specific UTC day (YYYY-MM-DD). Overrides --keep-days.",
    )
    p.add_argument(
        "--repo", type=str,
        default=os.environ.get("COHERENCE_ARCHIVE_REPO", vea.DEFAULT_REPO),
        help="GitHub repo for cold-tier releases (default: $COHERENCE_ARCHIVE_REPO).",
    )
    p.add_argument(
        "--apply", action="store_true",
        help="Commit upload + tombstone + hot-row delete. Without this flag, run is read-only.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Report only — explicit alias for the default behaviour.",
    )
    p.add_argument(
        "--limit", type=int, default=0,
        help="Maximum number of days to archive in this run (0 = no limit).",
    )
    args = p.parse_args(argv)

    apply = args.apply and not args.dry_run

    if args.day:
        target = date.fromisoformat(args.day)
        days = [target]
    else:
        days = days_with_hot_events_older_than(args.keep_days)
        if args.limit > 0:
            days = days[: args.limit]

    log.info("=== archive_view_events ===")
    log.info("repo:       %s", args.repo)
    log.info("mode:       %s", "APPLY (uploads + commits)" if apply else "DRY-RUN")
    log.info("days_found: %s%s",
             len(days), f" (limited to first {args.limit})" if args.limit > 0 else "")
    if not days:
        log.info("nothing to archive. body breathes.")
        return 0

    summaries: list[dict] = []
    for d in days:
        try:
            summaries.append(archive_one_day(d, repo=args.repo, apply=apply))
        except Exception as e:
            log.error("    FAILED for %s: %s", d.isoformat(), e)
            summaries.append({"day": d.isoformat(), "error": str(e)})

    if apply:
        vacuum_if_sqlite()

    log.info("\n=== summary ===")
    total_events = sum(s.get("event_count", 0) for s in summaries)
    total_bytes = sum(s.get("bytes_compressed", 0) for s in summaries)
    total_deleted = sum(s.get("deleted", 0) for s in summaries)
    log.info("days handled:  %s", len(summaries))
    log.info("events archived: %s", total_events)
    log.info("compressed cold-tier bytes: %s", _human(total_bytes))
    log.info("hot rows deleted: %s", total_deleted)

    return 0


if __name__ == "__main__":
    sys.exit(main())
