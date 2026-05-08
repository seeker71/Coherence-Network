"""Cold-tier archival for ``asset_view_events``.

The hot tier (Postgres ``asset_view_events``) keeps full per-event
detail for the last N days. Older events are dumped to a free,
durable, public substrate (GitHub releases) with byte-perfect
fidelity, and replaced in the DB by a single tombstone row per day
that knows where the original lives and how to verify it.

The pattern preserves three invariants:

  1. **Full traceability** — any archived day can be retrieved
     bit-for-bit. The tombstone carries the SHA-256 of the gzipped
     JSONL, so we know an answer matches what was archived.
  2. **Compact in-DB footprint** — one tombstone (~150 bytes) per
     archived day replaces ~2 MB of per-event rows. The hot table
     stops growing without bound.
  3. **Known retrieval cost** — the tombstone records compressed
     bytes + an estimated retrieval seconds, so a caller knows
     before they ask whether the trip is cheap or expensive.

Surface:
  · ``ViewEventsArchive`` — the tombstone ORM model (``view_events_archive``)
  · ``serialise_day(day)`` — pull a day's events into JSONL bytes
  · ``upload_to_github_releases(...)`` — push to the cold tier
  · ``record_tombstone(...)`` — write the DB tombstone
  · ``retrieve_day(day)`` — fetch from cold tier, verify, decompress
  · ``stats()`` — totals + provider breakdown for the health endpoint

Re-key on ``day`` (UTC date). Each archive is one calendar day's
events, ordered by ``created_at`` ascending, one JSON object per line.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import os
import subprocess
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import mapped_column

log = logging.getLogger(__name__)


# Estimated network throughput on the VPS for retrieval-cost
# guesses. Conservative ~10 MB/s sustained; gh.io serves quickly.
_RETRIEVAL_BYTES_PER_SECOND = 10 * 1024 * 1024

# Local cache for retrieved archives — re-fetching the same day from
# GitHub is free (no egress fee) but still ~1-2s; caching makes
# repeated retrievals instant.
_CACHE_DIR = Path(
    os.environ.get(
        "COHERENCE_ARCHIVE_CACHE",
        "/tmp/coherence-archive-cache",
    )
)


# ---------------------------------------------------------------------------
# ORM
# ---------------------------------------------------------------------------

from app.services.unified_db import Base


class ViewEventsArchive(Base):
    """Tombstone — one row per archived day. Replaces O(events) hot
    rows with O(days) tombstones in the DB while keeping full
    fidelity in the cold tier.
    """

    __tablename__ = "view_events_archive"

    day = mapped_column(Date, primary_key=True)
    event_count = mapped_column(Integer, nullable=False)
    bytes_compressed = mapped_column(Integer, nullable=False)
    bytes_original = mapped_column(Integer, nullable=False)
    sha256 = mapped_column(String(64), nullable=False)
    archive_url = mapped_column(String(512), nullable=False)
    archive_provider = mapped_column(String(64), nullable=False)
    archive_tag = mapped_column(String(128), nullable=True)
    archived_at = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    estimated_retrieval_seconds = mapped_column(Float, nullable=True)


def _session():
    from app.services.unified_db import session
    return session()


def _ensure_ready() -> None:
    from app.services.unified_db import ensure_schema
    ensure_schema()


# ---------------------------------------------------------------------------
# Serialisation — pull a day's events into gzipped JSONL bytes.
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "asset_id": row.asset_id,
        "concept_id": row.concept_id,
        "contributor_id": row.contributor_id,
        "session_fingerprint": row.session_fingerprint,
        "source_page": row.source_page,
        "referrer_contributor_id": row.referrer_contributor_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialise_day(target_day: date) -> tuple[bytes, dict[str, Any]]:
    """Return (gzipped JSONL, manifest) for a single UTC day's events.

    The JSONL is one event per line, ordered by created_at ascending.
    The manifest carries totals so the caller can record a tombstone.
    """
    _ensure_ready()
    from app.services.read_tracking_service import AssetViewEvent

    start = datetime.combine(target_day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    with _session() as s:
        rows = (
            s.query(AssetViewEvent)
            .filter(AssetViewEvent.created_at >= start)
            .filter(AssetViewEvent.created_at < end)
            .order_by(AssetViewEvent.created_at.asc(), AssetViewEvent.id.asc())
            .all()
        )

    raw = io.BytesIO()
    count = 0
    for row in rows:
        raw.write((json.dumps(_row_to_dict(row), separators=(",", ":")) + "\n").encode("utf-8"))
        count += 1
    raw_bytes = raw.getvalue()

    compressed = gzip.compress(raw_bytes, compresslevel=9)
    digest = hashlib.sha256(compressed).hexdigest()

    return compressed, {
        "day": target_day.isoformat(),
        "event_count": count,
        "bytes_original": len(raw_bytes),
        "bytes_compressed": len(compressed),
        "sha256": digest,
    }


# ---------------------------------------------------------------------------
# Cold-tier upload — GitHub releases on the existing repo.
#
# We use a deterministic tag pattern `archive/view-events/YYYY-MM-DD`
# so retrievers can construct the URL without round-tripping the API.
# Asset filename is `events-YYYY-MM-DD.jsonl.gz`. Both upload and
# tag-create are idempotent (re-running on a re-archived day will
# fail or warn loudly — the caller should check tombstone first).
# ---------------------------------------------------------------------------

DEFAULT_REPO = os.environ.get("COHERENCE_ARCHIVE_REPO", "seeker71/Coherence-Network")
# Hyphenated, slash-free tag prefix. GitHub release download URLs are
# path-based and ambiguous when tags contain "/", so we keep the tag
# flat: e.g. ``archive-view-events-2026-05-08``.
DEFAULT_TAG_PREFIX = "archive-view-events"
DEFAULT_PROVIDER = "github-releases"


def _gh_tag_for(target_day: date) -> str:
    return f"{DEFAULT_TAG_PREFIX}-{target_day.isoformat()}"


def _gh_asset_name(target_day: date) -> str:
    return f"events-{target_day.isoformat()}.jsonl.gz"


def github_release_url(target_day: date, repo: str = DEFAULT_REPO) -> str:
    """Deterministic public download URL for a day's archive."""
    return (
        f"https://github.com/{repo}/releases/download/"
        f"{_gh_tag_for(target_day)}/{_gh_asset_name(target_day)}"
    )


def upload_to_github_releases(
    target_day: date,
    payload: bytes,
    *,
    repo: str = DEFAULT_REPO,
    notes: str = "",
) -> str:
    """Push the gzipped JSONL to a GitHub release. Returns the URL.

    Requires ``gh`` CLI available and authenticated on the host
    running this. Idempotent on tag creation (uses ``gh release create
    --notes``; if the tag already exists this falls through to upload
    using ``--clobber``).

    Raises CalledProcessError on failure so the caller does not
    record a tombstone for an upload that didn't land.
    """
    tag = _gh_tag_for(target_day)
    asset = _gh_asset_name(target_day)

    # Stage payload to a temp file for `gh release upload`.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as f:
        f.write(payload)
        tmp_path = f.name

    try:
        # Best-effort tag create; if it already exists, that's fine.
        # `gh release create` returns non-zero when the tag exists,
        # so swallow that specific failure.
        try:
            subprocess.run(
                ["gh", "release", "create", tag, "--repo", repo,
                 "--title", f"view-events archive · {target_day.isoformat()}",
                 "--notes", notes or "Cold-tier archive of one day of view events."],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            if "already exists" in (e.stderr or ""):
                log.info("archive: tag %s already exists, re-uploading asset", tag)
            else:
                raise

        # Upload (or clobber) the asset.
        subprocess.run(
            ["gh", "release", "upload", tag, f"{tmp_path}#{asset}",
             "--repo", repo, "--clobber"],
            check=True, capture_output=True, text=True,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return github_release_url(target_day, repo=repo)


# ---------------------------------------------------------------------------
# Tombstone
# ---------------------------------------------------------------------------

def record_tombstone(
    target_day: date,
    *,
    manifest: dict[str, Any],
    archive_url: str,
    archive_provider: str = DEFAULT_PROVIDER,
    archive_tag: str | None = None,
) -> ViewEventsArchive:
    """Write/upsert the tombstone row. Idempotent on day primary key."""
    _ensure_ready()
    eta_seconds = round(manifest["bytes_compressed"] / _RETRIEVAL_BYTES_PER_SECOND, 3)

    with _session() as s:
        existing = s.query(ViewEventsArchive).filter_by(day=target_day).first()
        if existing:
            existing.event_count = manifest["event_count"]
            existing.bytes_compressed = manifest["bytes_compressed"]
            existing.bytes_original = manifest["bytes_original"]
            existing.sha256 = manifest["sha256"]
            existing.archive_url = archive_url
            existing.archive_provider = archive_provider
            existing.archive_tag = archive_tag
            existing.archived_at = datetime.now(timezone.utc)
            existing.estimated_retrieval_seconds = eta_seconds
            row = existing
        else:
            row = ViewEventsArchive(
                day=target_day,
                event_count=manifest["event_count"],
                bytes_compressed=manifest["bytes_compressed"],
                bytes_original=manifest["bytes_original"],
                sha256=manifest["sha256"],
                archive_url=archive_url,
                archive_provider=archive_provider,
                archive_tag=archive_tag,
                estimated_retrieval_seconds=eta_seconds,
            )
            s.add(row)
        s.commit()
        # Refresh primary key fields after commit.
        s.refresh(row)
        return row


def delete_hot_rows_for_day(target_day: date) -> int:
    """Delete the per-event rows for a day after the tombstone lands.

    The caller should verify the tombstone exists for ``target_day``
    before calling this. Returns the number of rows removed.
    """
    _ensure_ready()
    from app.services.read_tracking_service import AssetViewEvent

    start = datetime.combine(target_day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    with _session() as s:
        n = (
            s.query(AssetViewEvent)
            .filter(AssetViewEvent.created_at >= start)
            .filter(AssetViewEvent.created_at < end)
            .delete(synchronize_session=False)
        )
        s.commit()
        return n or 0


# ---------------------------------------------------------------------------
# Retrieval — fetch + verify + decompress.
# ---------------------------------------------------------------------------

def _cache_path(target_day: date) -> Path:
    return _CACHE_DIR / f"events-{target_day.isoformat()}.jsonl.gz"


def get_tombstone(target_day: date) -> ViewEventsArchive | None:
    _ensure_ready()
    with _session() as s:
        row = s.query(ViewEventsArchive).filter_by(day=target_day).first()
        if not row:
            return None
        # Detach from session so caller can read after session closes.
        s.expunge(row)
        return row


def retrieve_day(target_day: date) -> dict[str, Any]:
    """Retrieve a day's archived events. Verifies SHA-256, caches
    locally for repeat reads. Returns a manifest with the event list.
    """
    tomb = get_tombstone(target_day)
    if not tomb:
        return {"day": target_day.isoformat(), "events": [], "found": False, "reason": "not archived"}

    cache = _cache_path(target_day)
    payload: bytes
    fetched_from_cache = False

    if cache.exists():
        payload = cache.read_bytes()
        if hashlib.sha256(payload).hexdigest() == tomb.sha256:
            fetched_from_cache = True
        else:
            log.warning("archive: cached payload sha256 mismatch — re-fetching")
            cache.unlink(missing_ok=True)
            payload = b""

    fetch_seconds: float | None = None
    if not fetched_from_cache:
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(
                tomb.archive_url,
                headers={"User-Agent": "coherence-network-archive/1.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            return {
                "day": target_day.isoformat(),
                "events": [],
                "found": True,
                "fetched": False,
                "error": f"fetch failed: {e}",
                "tombstone": _tombstone_to_dict(tomb),
            }
        fetch_seconds = round(time.perf_counter() - t0, 3)

        actual_sha = hashlib.sha256(payload).hexdigest()
        if actual_sha != tomb.sha256:
            return {
                "day": target_day.isoformat(),
                "events": [],
                "found": True,
                "fetched": False,
                "error": (
                    f"integrity check failed: tombstone sha256={tomb.sha256} "
                    f"actual={actual_sha}"
                ),
                "tombstone": _tombstone_to_dict(tomb),
            }
        # Persist to cache for the next reader.
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(payload)
        except OSError as e:
            log.warning("archive: could not write cache %s: %s", cache, e)

    # Decompress + parse JSONL.
    try:
        raw = gzip.decompress(payload)
    except gzip.BadGzipFile as e:
        return {
            "day": target_day.isoformat(),
            "events": [],
            "found": True,
            "fetched": True,
            "error": f"gunzip failed: {e}",
            "tombstone": _tombstone_to_dict(tomb),
        }

    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    return {
        "day": target_day.isoformat(),
        "events": events,
        "found": True,
        "fetched": True,
        "verified_sha256": tomb.sha256,
        "fetched_from_cache": fetched_from_cache,
        "fetch_seconds": fetch_seconds,
        "tombstone": _tombstone_to_dict(tomb),
    }


def _tombstone_to_dict(tomb: ViewEventsArchive) -> dict[str, Any]:
    return {
        "day": tomb.day.isoformat() if tomb.day else None,
        "event_count": tomb.event_count,
        "bytes_compressed": tomb.bytes_compressed,
        "bytes_original": tomb.bytes_original,
        "sha256": tomb.sha256,
        "archive_url": tomb.archive_url,
        "archive_provider": tomb.archive_provider,
        "archive_tag": tomb.archive_tag,
        "archived_at": tomb.archived_at.isoformat() if tomb.archived_at else None,
        "estimated_retrieval_seconds": tomb.estimated_retrieval_seconds,
    }


# ---------------------------------------------------------------------------
# Stats — for the health endpoint.
# ---------------------------------------------------------------------------

def stats() -> dict[str, Any]:
    """Aggregate stats on archived days. Cheap; one query."""
    _ensure_ready()
    with _session() as s:
        rows = s.query(ViewEventsArchive).all()
        total_archived_days = len(rows)
        total_archived_events = sum(r.event_count or 0 for r in rows)
        total_compressed_bytes = sum(r.bytes_compressed or 0 for r in rows)
        total_original_bytes = sum(r.bytes_original or 0 for r in rows)
        oldest = min((r.day for r in rows), default=None)
        newest = max((r.day for r in rows), default=None)
        providers: dict[str, int] = {}
        for r in rows:
            providers[r.archive_provider] = providers.get(r.archive_provider, 0) + 1

    compression_ratio = (
        round(total_original_bytes / total_compressed_bytes, 1)
        if total_compressed_bytes > 0
        else None
    )
    return {
        "total_archived_days": total_archived_days,
        "total_archived_events": total_archived_events,
        "total_compressed_bytes": total_compressed_bytes,
        "total_original_bytes": total_original_bytes,
        "compression_ratio": compression_ratio,
        "oldest_archived_day": oldest.isoformat() if oldest else None,
        "newest_archived_day": newest.isoformat() if newest else None,
        "providers": providers,
    }
