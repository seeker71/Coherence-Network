#!/usr/bin/env python3
"""Trim the witness-trace table when it grows past comfortable.

The body's tracing layer writes one row to ``asset_view_events`` per
visit. The aggregate ``asset_reads_daily`` table stays bounded
(O(assets × days)); the per-event table grows linearly with traffic.
This script is the lever the wellness check / maintainer can pull
when /api/views/health flags ``size_high`` or ``growth_high``.

Two modes, composable:

  · **Roll-up + delete** (``--older-than 30``) — for events older
    than N days, ensure the daily aggregate already carries those
    counts (it does, by construction; the ping path writes both),
    then delete the per-event rows. Per-day breakdown stays
    queryable forever via ``asset_reads_daily``; per-event detail
    (referrer, session fingerprint, source page) only stays for
    the last N days.

  · **Down-sample anonymous** (``--sample-anonymous 0.1``) — keep
    only 10% of anonymous (no contributor_id) events older than the
    keep window. Anonymous events drive the trending counter +
    daily aggregate but rarely matter individually; sampling keeps
    the shape, drops the bulk.

Defaults are conservative — read-only ``--dry-run`` is the default
behaviour. Pass ``--apply`` to commit deletes.

Usage:

    python3 scripts/trim_view_events.py --dry-run
    python3 scripts/trim_view_events.py --older-than 30 --apply
    python3 scripts/trim_view_events.py --older-than 30 \\
        --sample-anonymous 0.1 --apply

Run after a /api/views/health flag, or schedule weekly when traffic
warrants. Idempotent — re-running is safe.
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import datetime, timedelta, timezone

# Allow `python3 scripts/...` from the repo root.
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_ROOT = os.path.join(REPO_ROOT, "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from app.services.unified_db import session, ensure_schema  # noqa: E402
from app.services.read_tracking_service import AssetViewEvent  # noqa: E402
from sqlalchemy import func  # noqa: E402

log = logging.getLogger("trim_view_events")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def _human_count(n: int) -> str:
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


def _human_bytes(n: int) -> str:
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def _summarise(s, label: str) -> dict:
    total = s.query(func.count(AssetViewEvent.id)).scalar() or 0
    oldest = s.query(func.min(AssetViewEvent.created_at)).scalar()
    newest = s.query(func.max(AssetViewEvent.created_at)).scalar()
    log.info(
        "  [%s] %s rows · oldest=%s · newest=%s",
        label,
        _human_count(total),
        oldest.isoformat() if oldest else "—",
        newest.isoformat() if newest else "—",
    )
    return {"rows": total, "oldest": oldest, "newest": newest}


def trim(
    older_than_days: int,
    sample_anonymous: float | None,
    apply: bool,
) -> int:
    """Returns the number of rows actually (or would-be) deleted."""
    ensure_schema()
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    log.info("=== views-trace trim ===")
    log.info("cutoff   = %s (%d days ago)", cutoff.isoformat(), older_than_days)
    if sample_anonymous is not None:
        log.info("anon-keep = %.0f%% (drop %.0f%% of anonymous events)",
                 sample_anonymous * 100, (1 - sample_anonymous) * 100)
    log.info("mode     = %s", "APPLY (deletes will commit)" if apply else "DRY-RUN (no commits)")

    with session() as s:
        before = _summarise(s, "before")

        # Eligible deletes: events older than cutoff. Within those,
        # named (contributor_id is not null) events get rolled up via
        # the daily aggregate (which already has them by the time the
        # ping path commits) — so we delete them outright.
        # Anonymous events can be sampled if --sample-anonymous given;
        # otherwise they are deleted with the named ones.

        eligible = s.query(AssetViewEvent).filter(
            AssetViewEvent.created_at < cutoff,
        )
        eligible_count = eligible.count()
        log.info("  [eligible] %s rows older than cutoff", _human_count(eligible_count))

        if eligible_count == 0:
            log.info("nothing to trim. body breathes.")
            return 0

        # If sampling: keep a percentage of anonymous-only events.
        # Hash on event id for deterministic sampling — same id
        # produces the same kept/dropped decision across re-runs.
        if sample_anonymous is not None:
            anon_eligible = eligible.filter(AssetViewEvent.contributor_id.is_(None))
            anon_count = anon_eligible.count()
            named_count = eligible_count - anon_count
            keep_anon = int(round(anon_count * sample_anonymous))
            drop_anon = anon_count - keep_anon
            to_delete = named_count + drop_anon
            log.info(
                "  named-to-delete=%s · anon-keep=%s · anon-delete=%s · total-to-delete=%s",
                _human_count(named_count),
                _human_count(keep_anon),
                _human_count(drop_anon),
                _human_count(to_delete),
            )
        else:
            to_delete = eligible_count
            log.info("  total-to-delete = %s", _human_count(to_delete))

        if not apply:
            log.info("(dry-run) — re-run with --apply to commit. body waits.")
            return to_delete

        # Apply path: commit the deletes.
        deleted = 0
        if sample_anonymous is not None:
            # Delete all named eligible events outright.
            deleted_named = (
                s.query(AssetViewEvent)
                .filter(
                    AssetViewEvent.created_at < cutoff,
                    AssetViewEvent.contributor_id.isnot(None),
                )
                .delete(synchronize_session=False)
            )
            deleted += deleted_named or 0
            # For anonymous: walk in pages and skip a deterministic share.
            anon_rows = (
                s.query(AssetViewEvent.id)
                .filter(
                    AssetViewEvent.created_at < cutoff,
                    AssetViewEvent.contributor_id.is_(None),
                )
                .all()
            )
            keep_threshold = sample_anonymous
            ids_to_delete: list[str] = []
            for (row_id,) in anon_rows:
                # Deterministic sampling — hash the id mod 1e9 / 1e9.
                seed_value = sum(ord(c) for c in row_id) % 10_000 / 10_000.0
                if seed_value >= keep_threshold:
                    ids_to_delete.append(row_id)
            if ids_to_delete:
                # Chunked delete to avoid pathological IN-list size.
                CHUNK = 1000
                for i in range(0, len(ids_to_delete), CHUNK):
                    chunk = ids_to_delete[i : i + CHUNK]
                    n = (
                        s.query(AssetViewEvent)
                        .filter(AssetViewEvent.id.in_(chunk))
                        .delete(synchronize_session=False)
                    )
                    deleted += n or 0
        else:
            # No sampling — delete everything older than cutoff.
            deleted = (
                s.query(AssetViewEvent)
                .filter(AssetViewEvent.created_at < cutoff)
                .delete(synchronize_session=False)
            ) or 0

        s.commit()
        log.info("  [deleted] %s rows committed", _human_count(deleted))

        # If the dialect is sqlite, run VACUUM so freed pages are
        # actually returned to disk. Postgres reclaims via autovacuum.
        try:
            from app.services.unified_db import _engine  # type: ignore[attr-defined]
            url = str(_engine.url) if hasattr(_engine, "url") else ""
            if "sqlite" in url:
                s.execute("VACUUM")
                log.info("  [vacuum] sqlite pages reclaimed")
        except Exception as e:  # pragma: no cover
            log.warning("  vacuum step skipped: %s", e)

        _summarise(s, "after")
        return deleted

    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--older-than", type=int, default=30,
        help="Delete events older than N days (default: 30).",
    )
    p.add_argument(
        "--sample-anonymous", type=float, default=None,
        help=(
            "Keep only this fraction of anonymous events (0.0–1.0). "
            "E.g. 0.1 keeps 10%%. If omitted, anonymous events are "
            "deleted alongside named ones."
        ),
    )
    p.add_argument(
        "--apply", action="store_true",
        help="Commit the deletes. Without this flag, run is read-only.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Report only — explicit alias for the default behaviour.",
    )
    args = p.parse_args(argv)

    if args.sample_anonymous is not None:
        if not (0.0 <= args.sample_anonymous <= 1.0):
            log.error("--sample-anonymous must be between 0.0 and 1.0")
            return 2

    apply = args.apply and not args.dry_run
    deleted = trim(
        older_than_days=args.older_than,
        sample_anonymous=args.sample_anonymous,
        apply=apply,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
