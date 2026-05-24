"""federation_substrate_service — freedom-preserving canonical exchange.

Two coherence instances meeting at the substrate altitude. Each exposes
its interned canonical recipe-shapes (the `recipe-shape` domain from
`modality_shapes.CANONICAL_SHAPES`). Content-addressing — sha256 over the
(canonical_name, role_slots) tuple — lets peers test for structural
alignment without forcing import.

The service has three movements:

  - `local_canonicals()` — what this instance carries. Read-only.
  - `discover_local(name)` — does this instance carry this canonical, and
    what's its content_hash? Cheap single-shape lookup.
  - `exchange_with_peer(payload)` — accept a peer's inventory and write
    per-canonical attestations into `federation_substrate_attestations`.
    Three outcomes per peer-canonical: aligned, diverged, discovered.

What the service does NOT do:
  - Import the peer's canonicals into the local lattice
  - Modify any local recipe-shape cell
  - Decide whether the peer is "right" — both sides stay sovereign

The attestation mirror is each instance's view of its peers — a witness
record, not authority. A later, separate operation (manual or governed)
can choose to ingest a discovered shape; nothing here forces that.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from app.models.federation import (
    ALIGNMENT_STATUSES,
    CanonicalAttestationOut,
    CanonicalDiscoverResponse,
    CanonicalExchangeResponse,
    CanonicalShapeOut,
    CanonicalShapesListResponse,
    PeerCanonicalEntry,
)
from app.services import unified_db as _udb
from app.services.federation_service import FederatedSubstrateAttestationRecord
from app.services.substrate.kernel import (
    NodeID,
    find_equivalent_cells,
    lookup_cell,
)
from app.services.substrate.modality_shapes import (
    CANONICAL_SHAPES,
    DOMAIN_RECIPE_SHAPE,
)


# ---------------------------------------------------------------------------
# Content-addressing — deterministic across instances
# ---------------------------------------------------------------------------


def canonical_content_hash(canonical_name: str, role_slots: Sequence[str]) -> str:
    """sha256 hex of (canonical_name, role_slots) — the over-the-wire fingerprint.

    Deterministic across instances: any two instances that have interned the
    same canonical descriptor will compute the same hash, regardless of
    when they interned it or what NodeID number it ended up with locally.

    Encoding: name + NUL + slots joined by NUL. NUL is reserved out of
    canonical names and role slots, so the boundary is unambiguous.
    """
    parts = [canonical_name, *role_slots]
    payload = "\x00".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _node_id_to_dict(nid: NodeID | None) -> dict | None:
    if nid is None:
        return None
    return {
        "package": nid.package,
        "level": nid.level,
        "type": nid.type_,
        "instance": nid.instance,
    }


# ---------------------------------------------------------------------------
# Local inventory — what THIS instance carries
# ---------------------------------------------------------------------------


def local_canonicals(
    session: Session, *, instance_id: str | None = None
) -> CanonicalShapesListResponse:
    """Build the canonical-shape inventory for this instance.

    Each entry carries its content_hash (always present — content-addressing
    is structural, not dependent on interning). `interned`, `blueprint`,
    and `member_count` reflect THIS instance's lattice state — a peer sees
    them as the peer's own truth.
    """
    out: list[CanonicalShapeOut] = []
    for canonical_name, role_slots, modality_tags in CANONICAL_SHAPES:
        chash = canonical_content_hash(canonical_name, list(role_slots))
        cell = lookup_cell(session, DOMAIN_RECIPE_SHAPE, canonical_name)
        if cell is None:
            out.append(
                CanonicalShapeOut(
                    canonical_name=canonical_name,
                    role_slots=list(role_slots),
                    modality_tags=list(modality_tags),
                    blueprint=None,
                    content_hash=chash,
                    interned=False,
                    member_count=0,
                )
            )
            continue
        members = find_equivalent_cells(session, cell.blueprint)
        out.append(
            CanonicalShapeOut(
                canonical_name=canonical_name,
                role_slots=list(role_slots),
                modality_tags=list(modality_tags),
                blueprint=_node_id_to_dict(cell.blueprint),
                content_hash=chash,
                interned=True,
                member_count=len(members),
            )
        )
    return CanonicalShapesListResponse(
        instance_id=instance_id,
        canonicals=out,
        count=len(out),
    )


def discover_local_canonical(
    session: Session, canonical_name: str
) -> CanonicalDiscoverResponse:
    """Single-shape lookup — does this instance carry `canonical_name`?

    Returns `found=False` if either (a) the canonical isn't in
    `CANONICAL_SHAPES` for this instance's build OR (b) it's declared but
    not yet interned. The content_hash IS returned even when not interned
    (it depends on the declaration, not the cell), so a peer can compare
    structural intent even before either side completes interning.
    """
    for c_name, role_slots, _modality_tags in CANONICAL_SHAPES:
        if c_name != canonical_name:
            continue
        chash = canonical_content_hash(canonical_name, list(role_slots))
        cell = lookup_cell(session, DOMAIN_RECIPE_SHAPE, canonical_name)
        if cell is None:
            return CanonicalDiscoverResponse(
                canonical_name=canonical_name,
                found=False,
                content_hash=chash,
                blueprint=None,
            )
        return CanonicalDiscoverResponse(
            canonical_name=canonical_name,
            found=True,
            content_hash=chash,
            blueprint=_node_id_to_dict(cell.blueprint),
        )
    return CanonicalDiscoverResponse(
        canonical_name=canonical_name,
        found=False,
        content_hash=None,
        blueprint=None,
    )


# ---------------------------------------------------------------------------
# Exchange — accept a peer's inventory and write attestations
# ---------------------------------------------------------------------------


def _local_hash_index() -> dict[str, str]:
    """Build name → local content_hash map from CANONICAL_SHAPES.

    Independent of session state — derived from this instance's build-time
    canonical declarations. Same body running two processes computes the
    same map.
    """
    return {
        name: canonical_content_hash(name, list(role_slots))
        for name, role_slots, _tags in CANONICAL_SHAPES
    }


def _classify_alignment(
    peer_entry: PeerCanonicalEntry, local_hashes: dict[str, str]
) -> tuple[str, str | None]:
    """Return (alignment_status, local_content_hash) for one peer entry.

    Pure function — no session, no DB. The exchange handler writes the
    classification into the attestation mirror.
    """
    local_hash = local_hashes.get(peer_entry.canonical_name)
    if local_hash is None:
        return "discovered", None
    if local_hash == peer_entry.content_hash:
        return "aligned", local_hash
    return "diverged", local_hash


def exchange_with_peer(
    session: Session,
    peer_instance_id: str,
    canonicals: Iterable[PeerCanonicalEntry],
) -> CanonicalExchangeResponse:
    """Record attestations for a peer's canonical inventory.

    For each peer-canonical:
      - Classify (aligned | diverged | discovered) by content_hash
      - Upsert into federation_substrate_attestations keyed by
        (peer_instance_id, canonical_name) so re-running is idempotent
      - Refresh observed_at so the attestation reflects the most recent
        exchange

    Returns the per-canonical outcomes. Does NOT touch local recipe-shape
    cells — sovereignty preserved.
    """
    local_hashes = _local_hash_index()
    now_iso = datetime.now(timezone.utc).isoformat()

    attestations: list[CanonicalAttestationOut] = []
    aligned = diverged = discovered = 0
    received = 0

    for peer_entry in canonicals:
        received += 1
        status, local_hash = _classify_alignment(peer_entry, local_hashes)
        if status == "aligned":
            aligned += 1
        elif status == "diverged":
            diverged += 1
        else:
            discovered += 1

        existing = (
            session.query(FederatedSubstrateAttestationRecord)
            .filter_by(
                peer_instance_id=peer_instance_id,
                canonical_name=peer_entry.canonical_name,
            )
            .one_or_none()
        )
        if existing is None:
            row = FederatedSubstrateAttestationRecord(
                peer_instance_id=peer_instance_id,
                canonical_name=peer_entry.canonical_name,
                peer_content_hash=peer_entry.content_hash,
                local_content_hash=local_hash,
                alignment_status=status,
                observed_at=now_iso,
            )
            session.add(row)
        else:
            existing.peer_content_hash = peer_entry.content_hash
            existing.local_content_hash = local_hash
            existing.alignment_status = status
            existing.observed_at = now_iso

        attestations.append(
            CanonicalAttestationOut(
                peer_instance_id=peer_instance_id,
                canonical_name=peer_entry.canonical_name,
                peer_content_hash=peer_entry.content_hash,
                local_content_hash=local_hash,
                alignment_status=status,
                observed_at=now_iso,
            )
        )

    session.flush()
    return CanonicalExchangeResponse(
        peer_instance_id=peer_instance_id,
        received=received,
        aligned=aligned,
        diverged=diverged,
        discovered=discovered,
        attestations=attestations,
    )


def list_attestations_for_peer(
    session: Session, peer_instance_id: str
) -> list[CanonicalAttestationOut]:
    """Read the attestation mirror for a single peer."""
    rows = (
        session.query(FederatedSubstrateAttestationRecord)
        .filter_by(peer_instance_id=peer_instance_id)
        .order_by(FederatedSubstrateAttestationRecord.canonical_name)
        .all()
    )
    return [
        CanonicalAttestationOut(
            peer_instance_id=row.peer_instance_id,
            canonical_name=row.canonical_name,
            peer_content_hash=row.peer_content_hash,
            local_content_hash=row.local_content_hash,
            alignment_status=row.alignment_status,
            observed_at=row.observed_at,
        )
        for row in rows
    ]


__all__ = [
    "ALIGNMENT_STATUSES",
    "canonical_content_hash",
    "discover_local_canonical",
    "exchange_with_peer",
    "list_attestations_for_peer",
    "local_canonicals",
]
