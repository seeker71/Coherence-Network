"""federation_peer_poll_service — the federation's heartbeat.

Each instance decides which peers to know, polls them on its own schedule,
records what they willingly share. No instance is polled without its
consent (the peer remains free to refuse / throttle / 404), no peer is
forced to reciprocate (this service never writes to peers — it only reads
what peers willingly share via their public read-only endpoints).

Three things land in local tissue from a successful poll:

  - PeerPulseRecord (shipped in instance_pulse_service) — peer's
    `/api/pulse/now` response, upserted by peer_instance_id.
  - PeerCapabilityRecord (this module) — peer's
    `/api/federation/capabilities/self`, the manifest the peer self-declares.
  - federation_substrate_attestations (via federation_substrate_service) —
    peer's `/api/federation/substrate/canonicals`, classified per-canonical
    as aligned / diverged / discovered.

What the service does NOT do:
  - POST/PUT/DELETE to peers — every outbound is a GET
  - Retry aggressively when a peer refuses — 401/403/404 is the peer
    naming a boundary; we honor it the same as a timeout
  - Import peer canonicals into the local lattice — the exchange records
    attestations only; sovereignty is preserved on both sides
  - Couple peers together — one failing peer's exception is caught and
    bounded; the rest of the loop continues
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.federation import PeerCanonicalEntry
from app.services import federation_service
from app.services import federation_substrate_service
from app.services import instance_pulse_service
from app.services import unified_db as _udb
from app.services.unified_db import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ORM — what we record from a successful capability poll
# ---------------------------------------------------------------------------

class PeerCapabilityRecord(Base):
    """Most-recent capability manifest observed from a peer.

    One row per peer_instance_id — the manifest evolves as the peer's own
    truth changes, and this is the latest snapshot the network has seen.
    Stored as opaque JSON so unknown extension fields round-trip without
    loss; readers can decode whatever shape the peer chose to share.
    """

    __tablename__ = "peer_capability_records"

    peer_instance_id: Mapped[str] = mapped_column(String, primary_key=True)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (Index("idx_pcr_observed_at", "observed_at"),)


# ---------------------------------------------------------------------------
# Result shape — one row per peer per poll
# ---------------------------------------------------------------------------


@dataclass
class PeerPollResult:
    """Outcome of one poll cycle for one peer.

    Each endpoint is independent — a peer may share pulse but refuse
    capabilities, or share both but lack canonicals. Each `*_status` is one
    of:
      - "ok"            : the GET returned 2xx and was recorded
      - "not_sharing"   : the peer returned 401/403/404 — sovereign refusal
      - "unreachable"   : timeout, connection error, DNS failure
      - "error"         : the peer returned 5xx or the response didn't parse
      - "skipped"       : we did not attempt (e.g. peer has no endpoint_url)
    """

    peer_instance_id: str
    endpoint_url: str | None = None
    polled_at: str = ""
    pulse_status: str = "skipped"
    capabilities_status: str = "skipped"
    substrate_status: str = "skipped"
    aligned: int = 0
    diverged: int = 0
    discovered: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "peer_instance_id": self.peer_instance_id,
            "endpoint_url": self.endpoint_url,
            "polled_at": self.polled_at,
            "pulse_status": self.pulse_status,
            "capabilities_status": self.capabilities_status,
            "substrate_status": self.substrate_status,
            "aligned": self.aligned,
            "diverged": self.diverged,
            "discovered": self.discovered,
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Tuning knobs
# ---------------------------------------------------------------------------

# Per-endpoint timeout. Short enough that one slow peer doesn't stall the
# whole loop; long enough that a healthy peer on a slow link still answers.
DEFAULT_TIMEOUT_S = 5.0


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def _ensure_schema() -> None:
    """Ensure peer_capability_records and dependent tables exist.

    federation_service._ensure_schema() also runs the federation tables;
    instance_pulse_service uses Base.metadata.create_all via unified_db so
    the PeerPulseRecord table is present too.
    """
    federation_service._ensure_schema()
    _udb.ensure_schema()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


# ---------------------------------------------------------------------------
# Status classification — keep it small and explicit
# ---------------------------------------------------------------------------


def _classify_http_response(response: httpx.Response) -> str:
    """Map an HTTP status code to one of our outcome buckets.

    401/403/404 are honored as sovereign refusal, not failure. 5xx is
    flagged as error so a healthy peer's bad day stays visible. 2xx is ok;
    anything else also lands in error so we don't silently classify
    unexpected codes as success.
    """
    if 200 <= response.status_code < 300:
        return "ok"
    if response.status_code in (401, 403, 404):
        return "not_sharing"
    return "error"


# ---------------------------------------------------------------------------
# Per-endpoint pollers — each returns a (status, parsed_body_or_none)
# ---------------------------------------------------------------------------


async def _poll_pulse(
    client: httpx.AsyncClient, base_url: str, result: PeerPollResult
) -> dict[str, Any] | None:
    url = f"{base_url}/api/pulse/now"
    try:
        response = await client.get(url)
    except httpx.TimeoutException:
        result.pulse_status = "unreachable"
        result.notes.append("pulse: timeout")
        return None
    except httpx.RequestError as exc:
        result.pulse_status = "unreachable"
        result.notes.append(f"pulse: {type(exc).__name__}")
        return None

    status = _classify_http_response(response)
    result.pulse_status = status
    if status != "ok":
        result.notes.append(f"pulse: HTTP {response.status_code}")
        return None
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        result.pulse_status = "error"
        result.notes.append("pulse: response was not JSON")
        return None
    if not isinstance(body, dict):
        result.pulse_status = "error"
        result.notes.append("pulse: response was not a JSON object")
        return None
    return body


async def _poll_capabilities(
    client: httpx.AsyncClient, base_url: str, result: PeerPollResult
) -> dict[str, Any] | None:
    url = f"{base_url}/api/federation/capabilities/self"
    try:
        response = await client.get(url)
    except httpx.TimeoutException:
        result.capabilities_status = "unreachable"
        result.notes.append("capabilities: timeout")
        return None
    except httpx.RequestError as exc:
        result.capabilities_status = "unreachable"
        result.notes.append(f"capabilities: {type(exc).__name__}")
        return None

    status = _classify_http_response(response)
    result.capabilities_status = status
    if status != "ok":
        result.notes.append(f"capabilities: HTTP {response.status_code}")
        return None
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        result.capabilities_status = "error"
        result.notes.append("capabilities: response was not JSON")
        return None
    if not isinstance(body, dict):
        result.capabilities_status = "error"
        result.notes.append("capabilities: response was not a JSON object")
        return None
    return body


async def _poll_canonicals(
    client: httpx.AsyncClient, base_url: str, result: PeerPollResult
) -> list[dict[str, Any]] | None:
    url = f"{base_url}/api/federation/substrate/canonicals"
    try:
        response = await client.get(url)
    except httpx.TimeoutException:
        result.substrate_status = "unreachable"
        result.notes.append("substrate: timeout")
        return None
    except httpx.RequestError as exc:
        result.substrate_status = "unreachable"
        result.notes.append(f"substrate: {type(exc).__name__}")
        return None

    status = _classify_http_response(response)
    result.substrate_status = status
    if status != "ok":
        result.notes.append(f"substrate: HTTP {response.status_code}")
        return None
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        result.substrate_status = "error"
        result.notes.append("substrate: response was not JSON")
        return None
    if not isinstance(body, dict):
        result.substrate_status = "error"
        result.notes.append("substrate: response was not a JSON object")
        return None
    canonicals = body.get("canonicals")
    if not isinstance(canonicals, list):
        result.substrate_status = "error"
        result.notes.append("substrate: 'canonicals' missing or not a list")
        return None
    return canonicals


# ---------------------------------------------------------------------------
# Local recording — keep each write isolated from the next
# ---------------------------------------------------------------------------


def _record_capability_manifest(peer_instance_id: str, manifest: dict[str, Any]) -> None:
    """Upsert one row per peer with the freshest manifest payload."""
    payload = json.dumps(manifest, default=str)
    now = datetime.now(timezone.utc)
    with _session() as session:
        existing = session.get(PeerCapabilityRecord, peer_instance_id)
        if existing is None:
            session.add(
                PeerCapabilityRecord(
                    peer_instance_id=peer_instance_id,
                    manifest_json=payload,
                    observed_at=now,
                )
            )
        else:
            existing.manifest_json = payload
            existing.observed_at = now


def _entries_from_canonicals(raw_canonicals: list[dict[str, Any]]) -> list[PeerCanonicalEntry]:
    """Coerce loose JSON canonicals into PeerCanonicalEntry models.

    Malformed entries are dropped rather than failing the whole exchange —
    a single bad row from a peer shouldn't break the alignment record for
    the canonicals that DID round-trip cleanly.
    """
    entries: list[PeerCanonicalEntry] = []
    for raw in raw_canonicals:
        if not isinstance(raw, dict):
            continue
        name = raw.get("canonical_name")
        chash = raw.get("content_hash")
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(chash, str) or not chash:
            continue
        role_slots = raw.get("role_slots") or []
        modality_tags = raw.get("modality_tags") or []
        if not isinstance(role_slots, list):
            role_slots = []
        if not isinstance(modality_tags, list):
            modality_tags = []
        try:
            entries.append(
                PeerCanonicalEntry(
                    canonical_name=name,
                    role_slots=[str(s) for s in role_slots],
                    modality_tags=[str(t) for t in modality_tags],
                    content_hash=chash,
                )
            )
        except Exception:
            # Validation rejected this row — skip rather than fail the batch.
            continue
    return entries


def _record_substrate_alignment(
    peer_instance_id: str,
    raw_canonicals: list[dict[str, Any]],
    result: PeerPollResult,
) -> None:
    entries = _entries_from_canonicals(raw_canonicals)
    if not entries:
        result.notes.append("substrate: peer shared no usable canonicals")
        return
    with _session() as session:
        response = federation_substrate_service.exchange_with_peer(
            session,
            peer_instance_id=peer_instance_id,
            canonicals=entries,
        )
    result.aligned = response.aligned
    result.diverged = response.diverged
    result.discovered = response.discovered


# ---------------------------------------------------------------------------
# Public surface — poll one peer, poll all peers
# ---------------------------------------------------------------------------


def _normalize_base_url(endpoint_url: str | None) -> str | None:
    if not endpoint_url:
        return None
    return endpoint_url.rstrip("/")


async def poll_peer(
    instance_id: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> PeerPollResult:
    """Poll one peer's three read-only endpoints; record what they share.

    The `client` argument is optional — tests inject a mock transport; in
    production the service opens its own AsyncClient with the configured
    timeout. Either way, every outbound is a GET; the service never writes
    to the peer.
    """
    _ensure_schema()
    peer = federation_service.get_instance(instance_id)
    polled_at = datetime.now(timezone.utc).isoformat()
    result = PeerPollResult(
        peer_instance_id=instance_id,
        endpoint_url=None,
        polled_at=polled_at,
    )
    if peer is None:
        result.notes.append("peer not registered locally")
        return result

    base_url = _normalize_base_url(peer.endpoint_url)
    result.endpoint_url = base_url
    if base_url is None:
        result.notes.append("peer has no endpoint_url")
        return result

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=timeout_s)

    try:
        pulse_body = await _poll_pulse(client, base_url, result)
        if pulse_body is not None:
            try:
                instance_pulse_service.record_peer_pulse(instance_id, pulse_body)
            except Exception as exc:
                result.pulse_status = "error"
                result.notes.append(f"pulse: local write failed ({type(exc).__name__})")

        cap_body = await _poll_capabilities(client, base_url, result)
        if cap_body is not None:
            try:
                _record_capability_manifest(instance_id, cap_body)
            except Exception as exc:
                result.capabilities_status = "error"
                result.notes.append(
                    f"capabilities: local write failed ({type(exc).__name__})"
                )

        canonicals = await _poll_canonicals(client, base_url, result)
        if canonicals is not None:
            try:
                _record_substrate_alignment(instance_id, canonicals, result)
            except Exception as exc:
                result.substrate_status = "error"
                result.notes.append(
                    f"substrate: local write failed ({type(exc).__name__})"
                )
    finally:
        if owns_client:
            await client.aclose()

    return result


async def poll_all_peers(
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    instance_ids: Iterable[str] | None = None,
) -> dict[str, PeerPollResult]:
    """Iterate over registered peers; return per-peer results.

    Each peer's poll is wrapped in its own try/except so one failing peer
    cannot break the rest of the loop. `instance_ids` lets a caller (or
    test) narrow the loop to a specific subset; default is "every
    registered instance."
    """
    _ensure_schema()
    if instance_ids is None:
        targets = [inst.instance_id for inst in federation_service.list_instances()]
    else:
        targets = list(instance_ids)

    results: dict[str, PeerPollResult] = {}
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for peer_id in targets:
            try:
                results[peer_id] = await poll_peer(peer_id, client=client)
            except Exception as exc:
                logger.warning(
                    "poll_peer raised for %s: %s", peer_id, exc, exc_info=True
                )
                fallback = PeerPollResult(
                    peer_instance_id=peer_id,
                    polled_at=datetime.now(timezone.utc).isoformat(),
                )
                fallback.notes.append(f"poll: {type(exc).__name__}")
                results[peer_id] = fallback
    return results


# ---------------------------------------------------------------------------
# Read surface — last-polled timestamp per peer
# ---------------------------------------------------------------------------


def get_last_capability_observation(peer_instance_id: str) -> str | None:
    """ISO timestamp of the most recent successful capability poll, or None."""
    _ensure_schema()
    with _session() as session:
        row = session.get(PeerCapabilityRecord, peer_instance_id)
        if row is None or row.observed_at is None:
            return None
        return row.observed_at.astimezone(timezone.utc).isoformat()


def list_last_polled() -> dict[str, str | None]:
    """Map peer_instance_id → freshest observation across pulse + capabilities.

    The web /federation page uses this to show one "last polled" timestamp
    per peer card without re-fetching every record. The freshest of the
    three sources wins; if a peer has never been successfully polled, the
    value is None.
    """
    _ensure_schema()
    out: dict[str, datetime] = {}
    with _session() as session:
        # Capability observations
        for row in session.query(PeerCapabilityRecord).all():
            if row.observed_at is None:
                continue
            ts = row.observed_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            existing = out.get(row.peer_instance_id)
            if existing is None or ts > existing:
                out[row.peer_instance_id] = ts
        # Pulse observations
        from app.services.instance_pulse_service import PeerPulseRecord

        for row in session.query(PeerPulseRecord).all():
            if row.observed_at is None:
                continue
            ts = row.observed_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            existing = out.get(row.peer_instance_id)
            if existing is None or ts > existing:
                out[row.peer_instance_id] = ts
    return {pid: ts.isoformat() for pid, ts in out.items()}


# ---------------------------------------------------------------------------
# Test reset
# ---------------------------------------------------------------------------


def _reset_for_tests() -> None:
    """Clear peer-poll local tissue so each test starts from clean ground."""
    _ensure_schema()
    with _session() as session:
        session.query(PeerCapabilityRecord).delete()
        from app.services.instance_pulse_service import PeerPulseRecord

        session.query(PeerPulseRecord).delete()
        from app.services.federation_service import (
            FederatedSubstrateAttestationRecord,
        )

        session.query(FederatedSubstrateAttestationRecord).delete()


__all__ = [
    "DEFAULT_TIMEOUT_S",
    "PeerCapabilityRecord",
    "PeerPollResult",
    "get_last_capability_observation",
    "list_last_polled",
    "poll_all_peers",
    "poll_peer",
]
