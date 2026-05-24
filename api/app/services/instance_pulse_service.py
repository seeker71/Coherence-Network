"""Instance pulse service — each coherence instance shows its own breath.

Federation honors sovereignty: each instance exposes its breath to whoever
chooses to look, but no central monitor controls it. The pulse endpoint is a
window, not a hook. Other instances and external observers can sense an
instance's aliveness without becoming its controller.

This service runs lightweight, bounded organ checks (api, postgres, neo4j,
substrate, schema) and synthesizes the overall state. Each check has a hard
timeout so the pulse keeps breathing even when other organs don't.

Companion to ``community_pulse_service`` (which senses the felt experience of
the organism) and the production ``pulse.coherencycoin.com`` witness (which
watches the production instance from outside). This is the per-instance
self-attestation surface that makes federation possible.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import Index, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.services import unified_db
from app.services.unified_db import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Identity + lifecycle
# ---------------------------------------------------------------------------

INSTANCE_STARTED_AT = datetime.now(timezone.utc)

# Per-check timeout: each organ check must return within this window or be
# marked silent. Keeps the pulse endpoint fast even under stress.
ORGAN_TIMEOUT_S = 0.05


def instance_id() -> str:
    """Identifier for this coherence instance.

    Defaults to "local" for development/test; production sets
    FEDERATION_INSTANCE_ID. Sovereignty: the instance names itself.
    """
    return os.getenv("FEDERATION_INSTANCE_ID", "local")


def uptime_seconds(now: datetime | None = None) -> int:
    """Seconds since this instance process started."""
    now = now or datetime.now(timezone.utc)
    return max(0, int((now - INSTANCE_STARTED_AT).total_seconds()))


def pulse_enabled() -> bool:
    """An instance may disable its public pulse window for privacy.

    Set ``FEDERATION_PULSE_DISABLED=1`` to refuse the visibility. The default
    is to share: showing your breath is generosity, not surrender.
    """
    raw = os.getenv("FEDERATION_PULSE_DISABLED", "").strip().lower()
    return raw not in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Peer pulse persistence — what we have observed from peers we chose to watch
# ---------------------------------------------------------------------------

class PeerPulseRecord(Base):
    """Most-recent pulse observed from a peer instance.

    Each instance decides which peers to watch via existing federation flows;
    this table holds whatever the (separate) peer-poll job has captured. The
    GET /api/pulse/peers endpoint reads from here without making any outbound
    calls — readers see what the body has chosen to see, nothing forced.
    """

    __tablename__ = "peer_pulse_records"

    peer_instance_id: Mapped[str] = mapped_column(String, primary_key=True)
    last_pulse_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("idx_ppr_observed_at", "observed_at"),)


# ---------------------------------------------------------------------------
# Organ checks — each returns (status, score, detail)
# ---------------------------------------------------------------------------

# Allow tests to inject custom check callables. None = use defaults.
_check_overrides: dict[str, Callable[[], tuple[str, float, str | None]] | None] = {}
_overrides_lock = threading.Lock()


def set_organ_check(name: str, fn: Callable[[], tuple[str, float, str | None]] | None) -> None:
    """Test hook: override a single organ's check function."""
    with _overrides_lock:
        if fn is None:
            _check_overrides.pop(name, None)
        else:
            _check_overrides[name] = fn


def reset_organ_checks() -> None:
    """Test hook: clear all overrides."""
    with _overrides_lock:
        _check_overrides.clear()


def _check_api() -> tuple[str, float, str | None]:
    # If this function executes, the API process is responsive enough to
    # answer its own pulse. That is the api organ's breathing.
    return ("breathing", 1.0, None)


def _check_postgres() -> tuple[str, float, str | None]:
    try:
        from sqlalchemy import text as _text
        with unified_db.session() as sess:
            sess.execute(_text("SELECT 1"))
        return ("breathing", 1.0, None)
    except Exception as exc:  # pragma: no cover - covered by mocked test
        return ("silent", 0.0, f"postgres unreachable: {type(exc).__name__}")


def _check_neo4j() -> tuple[str, float, str | None]:
    try:
        # Lazy import — the graph store is optional in some test environments.
        from app.services import graph_store_service
        store = graph_store_service.get_store()
        if store is None:
            return ("silent", 0.0, "graph store unavailable")
        # A simple read; the count itself is incidental.
        store.run_query("MATCH (n) RETURN count(n) AS c LIMIT 1")
        return ("breathing", 1.0, None)
    except Exception as exc:
        return ("silent", 0.0, f"neo4j unreachable: {type(exc).__name__}")


def _check_substrate() -> tuple[str, float, str | None]:
    try:
        from app.services.substrate import lattice_stats
        with unified_db.session() as sess:
            stats = lattice_stats(sess)
        # If the substrate responds at all, it is breathing — emptiness is
        # not silence.
        if isinstance(stats, dict):
            return ("breathing", 1.0, None)
        return ("strained", 0.5, "substrate returned unexpected shape")
    except Exception as exc:
        return ("silent", 0.0, f"substrate unreadable: {type(exc).__name__}")


def _check_schema() -> tuple[str, float, str | None]:
    try:
        from sqlalchemy import text as _text
        with unified_db.session() as sess:
            for table in ("contributions", "contributors", "assets"):
                sess.execute(_text(f"SELECT 1 FROM {table} LIMIT 1"))
        return ("breathing", 1.0, None)
    except Exception as exc:
        return ("silent", 0.0, f"core tables missing: {type(exc).__name__}")


DEFAULT_CHECKS: dict[str, Callable[[], tuple[str, float, str | None]]] = {
    "api": _check_api,
    "postgres": _check_postgres,
    "neo4j": _check_neo4j,
    "substrate": _check_substrate,
    "schema": _check_schema,
}

# Organs whose silence indicates a structural problem rather than an
# auxiliary outage. If any of these go silent, overall drops below
# "breathing" even if everything else is fine.
CORE_ORGANS = frozenset({"api", "postgres"})


# Shared executor so a single slow organ's still-running thread doesn't block
# the response — we return on timeout and let the worker finish in the
# background. Bounded pool size keeps a stuck check from spawning unbounded
# threads under load.
_check_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="pulse-check")


def _run_with_timeout(fn: Callable[[], tuple[str, float, str | None]]) -> tuple[str, float, str | None]:
    """Run a check with a bounded timeout; treat overrun as silence.

    On timeout the worker thread keeps running (Python has no safe way to
    interrupt arbitrary code), but the response returns immediately. The
    shared pool absorbs the orphan until it completes.
    """
    future = _check_pool.submit(fn)
    try:
        return future.result(timeout=ORGAN_TIMEOUT_S)
    except FutureTimeout:
        return ("silent", 0.0, f"check exceeded {int(ORGAN_TIMEOUT_S * 1000)}ms")
    except Exception as exc:  # pragma: no cover - safety net
        return ("silent", 0.0, f"check raised: {type(exc).__name__}")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sample_organs() -> list[dict[str, Any]]:
    """Run all organ checks (with timeout) and return their breath state."""
    sampled_at = datetime.now(timezone.utc)
    now_iso = _iso(sampled_at)

    with _overrides_lock:
        active = {name: _check_overrides.get(name) or default for name, default in DEFAULT_CHECKS.items()}

    organs: list[dict[str, Any]] = []
    for name, fn in active.items():
        status, score, detail = _run_with_timeout(fn)
        organs.append({
            "name": name,
            "status": status,
            "last_breath_at": now_iso,
            "score": round(float(score), 3),
            "detail": detail,
        })
    return organs


def synthesize_overall(organs: list[dict[str, Any]]) -> tuple[str, int]:
    """Combine organ states into one overall breath.

    Rules:
      - All breathing → "breathing"
      - Any core organ silent → "silent"
      - Any organ silent or strained, core still healthy → "strained"
    """
    silences = sum(1 for o in organs if o["status"] != "breathing")
    core_silent = any(
        o["status"] == "silent" and o["name"] in CORE_ORGANS for o in organs
    )
    if core_silent:
        return ("silent", silences)
    if silences == 0:
        return ("breathing", 0)
    return ("strained", silences)


def self_pulse() -> dict[str, Any]:
    """Sample this instance's current breath state."""
    started = time.perf_counter()
    sampled_at = datetime.now(timezone.utc)
    organs = sample_organs()
    overall, silences = synthesize_overall(organs)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return {
        "instance_id": instance_id(),
        "overall": overall,
        "organs": organs,
        "silences": silences,
        "uptime_seconds": uptime_seconds(sampled_at),
        "as_of": _iso(sampled_at),
        "sample_duration_ms": elapsed_ms,
    }


# ---------------------------------------------------------------------------
# Peer pulse reads + writes
# ---------------------------------------------------------------------------

def record_peer_pulse(peer_id: str, pulse: dict[str, Any]) -> None:
    """Store an observed pulse from a peer.

    Used by the (out-of-scope) peer-poll job and by tests. Upserts a single
    row per peer — only the most-recent observation is kept.
    """
    import json

    payload = json.dumps(pulse, default=str)
    now = datetime.now(timezone.utc)
    with unified_db.session() as sess:
        existing = sess.get(PeerPulseRecord, peer_id)
        if existing is None:
            sess.add(PeerPulseRecord(
                peer_instance_id=peer_id,
                last_pulse_json=payload,
                observed_at=now,
            ))
        else:
            existing.last_pulse_json = payload
            existing.observed_at = now
        sess.commit()


def list_peer_pulses() -> list[dict[str, Any]]:
    """Return the most-recent observed pulse from each watched peer."""
    import json

    out: list[dict[str, Any]] = []
    try:
        with unified_db.session() as sess:
            rows = sess.query(PeerPulseRecord).order_by(
                PeerPulseRecord.observed_at.desc()
            ).all()
            for row in rows:
                try:
                    pulse = json.loads(row.last_pulse_json or "{}")
                except Exception:
                    pulse = {}
                out.append({
                    "peer_instance_id": row.peer_instance_id,
                    "observed_at": _iso(row.observed_at) if row.observed_at else None,
                    "pulse": pulse,
                })
    except Exception as exc:
        logger.warning("Failed to read peer pulses: %s", exc)
    return out
