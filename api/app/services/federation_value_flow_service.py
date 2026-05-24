"""federation_value_flow_service — freedom-preserving CC distribution across instances.

When an asset on instance A is mirrored to instance B and a reader on B reads
it, value can flow back to A's creator without either side surrendering
authority. The service has three movements:

  - `mirror_asset(manifest)` — record that we are hosting an asset whose
    authority lives on another instance. We hold local_asset_id; the origin
    instance holds the truth about the asset's identity and the creator's
    payment address.

  - `receive_read_attribution(envelope)` — the serving instance sends us a
    signed attribution envelope for one read of one of our assets. We verify
    the signature with the secret we hold for that peer, record the
    attestation, and bridge it into read_tracking so settlement sees it.

  - `compute_federated_shares(period_start, period_end)` — at settlement
    time we walk our received attestations and produce one signed envelope
    per peer (the share owed for serving our content). Envelopes are stored
    in the outgoing log; transport to the peer is the caller's choice
    (sync POST, batched push, or a future on-chain settlement).

  - `receive_settlement_share(envelope)` — symmetric: when a peer settles
    OUR serving fee, we verify and log into the inbox.

What this service does NOT do:
  - Move CC on a chain — that's a separate, downstream breath
  - Decide whether to mirror — that's the human/maintainer choice
  - Coerce a peer into accepting attestations — peers may decline
  - Hold authority over a peer's reader data — `reader_subject` is opaque
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import Boolean, Float, Index, Integer, String, Text, inspect, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.federation import (
    AssetMirrorManifest,
    AssetMirrorRecord,
    ComputeFederatedSharesRequest,
    ComputeFederatedSharesResponse,
    DEFAULT_FEDERATED_CREATOR_SHARE,
    DEFAULT_FEDERATED_SERVING_SHARE,
    FederatedReadAttestationListResponse,
    FederatedReadAttestationOut,
    ReadAttributionAck,
    ReadAttributionEnvelope,
    SettlementInboxEntryOut,
    SettlementInboxListResponse,
    SettlementShareAck,
    SettlementShareEnvelope,
)
from app.services import federation_service, unified_db as _udb
from app.services.unified_db import Base

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class FederatedAssetMirrorRecord(Base):
    """An asset hosted here whose authority lives on another instance.

    Each row says: this local_asset_id is a mirror of origin_asset_id on
    origin_instance_id. We carry origin_url for direct linking and
    origin_payment_address so settlement envelopes know where the creator
    receives CC. Sovereignty: we hold the local row, but the origin
    instance is authoritative for what the asset IS.
    """

    __tablename__ = "federation_asset_mirrors"

    local_asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    origin_instance_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    origin_asset_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    origin_url: Mapped[str] = mapped_column(String, nullable=False)
    origin_payment_address: Mapped[str | None] = mapped_column(String, nullable=True)
    mirrored_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index(
            "idx_fam_origin",
            "origin_instance_id",
            "origin_asset_id",
        ),
    )


class FederatedReadAttestationRecord(Base):
    """A read of one of our assets, attested by the serving instance.

    The serving instance signs the envelope with the secret we share with
    them; we verify on receipt. status taxonomy:

      - received : stored without signature verification (peer secret missing)
      - verified : signature checked and matches
      - settled  : included in an outgoing settlement envelope to the peer
      - rejected : signature failed verification (envelope discarded — kept
                   here only when explicitly stored for audit; the default
                   path returns 401 and stores nothing)
    """

    __tablename__ = "federation_read_attestations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_origin_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    reader_instance_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    reader_subject: Mapped[str | None] = mapped_column(String, nullable=True)
    read_type: Mapped[str] = mapped_column(String, nullable=False, default="free")
    cc_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    concept_resonance_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[str] = mapped_column(String, nullable=False, index=True)
    received_at: Mapped[str] = mapped_column(String, nullable=False)
    signature: Mapped[str] = mapped_column(String, nullable=False)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="received", index=True)

    __table_args__ = (
        Index(
            "idx_fra_reader_observed",
            "reader_instance_id",
            "observed_at",
        ),
    )


class FederatedSettlementInboxRecord(Base):
    """A settlement envelope received from a peer that owes us a serving fee.

    The peer (origin instance for some asset we served) computed our share
    from attestations we sent them and posted this envelope. We verify the
    signature and store; actual CC transfer is downstream — the inbox is a
    durable record of what we are owed.
    """

    __tablename__ = "federation_settlement_inbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    origin_instance_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    serving_instance_id: Mapped[str] = mapped_column(String, nullable=False)
    period_start: Mapped[str] = mapped_column(String, nullable=False, index=True)
    period_end: Mapped[str] = mapped_column(String, nullable=False)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cc_amount_to_serving: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cc_amount_to_creator: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    asset_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    signature: Mapped[str] = mapped_column(String, nullable=False)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_at: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="received", index=True)


class FederatedSettlementOutboxRecord(Base):
    """A settlement envelope we computed and signed, owed to a peer.

    Symmetric with the inbox: when we are origin, the peer is the serving
    side. We log what we sent so we can audit and re-send if the transport
    failed.
    """

    __tablename__ = "federation_settlement_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serving_instance_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    period_start: Mapped[str] = mapped_column(String, nullable=False, index=True)
    period_end: Mapped[str] = mapped_column(String, nullable=False)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cc_amount_to_serving: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cc_amount_to_creator: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    asset_breakdown_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    signature: Mapped[str] = mapped_column(String, nullable=False)
    computed_at: Mapped[str] = mapped_column(String, nullable=False)


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def _ensure_schema() -> None:
    _udb.ensure_schema()


def _session() -> Session:
    return _udb.session()


# ---------------------------------------------------------------------------
# Signing — symmetric HMAC-SHA256
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_attribution_payload(envelope: ReadAttributionEnvelope) -> str:
    """Deterministic JSON for signing/verifying a read-attribution envelope.

    Sorted keys, no whitespace. The signature field is excluded — it cannot
    sign itself.
    """
    dump = envelope.model_dump(mode="json")
    dump.pop("signature", None)
    return json.dumps(dump, sort_keys=True, separators=(",", ":"))


def sign_read_attribution(
    envelope_without_signature: dict,
    secret: str,
) -> str:
    """Compute the HMAC-SHA256 signature for a read-attribution envelope.

    `envelope_without_signature` is the full dict EXCEPT the signature
    field; the caller is the serving instance signing what it is about to
    send. The pair (envelope dict, signature) is what travels.
    """
    if not secret:
        raise ValueError("Cannot sign read attribution: secret is empty")
    payload = json.dumps(
        envelope_without_signature, sort_keys=True, separators=(",", ":")
    )
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_read_attribution(envelope: ReadAttributionEnvelope, secret: str) -> bool:
    """Verify the signature on a read-attribution envelope."""
    if not secret:
        return False
    payload = _canonical_attribution_payload(envelope)
    return federation_service.verify_payload_signature(payload, envelope.signature, secret)


def _canonical_settlement_payload(envelope: SettlementShareEnvelope) -> str:
    dump = envelope.model_dump(mode="json")
    dump.pop("signature", None)
    return json.dumps(dump, sort_keys=True, separators=(",", ":"))


def sign_settlement_share(envelope_without_signature: dict, secret: str) -> str:
    if not secret:
        raise ValueError("Cannot sign settlement share: secret is empty")
    payload = json.dumps(
        envelope_without_signature, sort_keys=True, separators=(",", ":")
    )
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_settlement_share(envelope: SettlementShareEnvelope, secret: str) -> bool:
    if not secret:
        return False
    payload = _canonical_settlement_payload(envelope)
    return federation_service.verify_payload_signature(
        payload, envelope.signature, secret
    )


# ---------------------------------------------------------------------------
# Federated reader id encoding
# ---------------------------------------------------------------------------

FEDERATED_READER_PREFIX = "federated:"


def federated_reader_id(reader_instance_id: str, reader_subject: str | None) -> str:
    """The reader_id under which a federated read is recorded locally.

    Encoding: `federated:<instance_id>:<subject>`. The local read-tracking
    service treats this opaquely — aggregations work, settlement sees the
    read, and the prefix lets us identify federated reads later for the
    settlement-share computation.
    """
    subject = reader_subject or "anonymous"
    return f"{FEDERATED_READER_PREFIX}{reader_instance_id}:{subject}"


def is_federated_reader_id(reader_id: str | None) -> bool:
    return bool(reader_id) and reader_id.startswith(FEDERATED_READER_PREFIX)


def parse_federated_reader_id(reader_id: str) -> tuple[str, str] | None:
    """Return (instance_id, subject) for a federated reader_id, or None."""
    if not is_federated_reader_id(reader_id):
        return None
    rest = reader_id[len(FEDERATED_READER_PREFIX) :]
    if ":" not in rest:
        return rest, "anonymous"
    instance_id, subject = rest.split(":", 1)
    return instance_id, subject


# ---------------------------------------------------------------------------
# Mirror operation — peer asks us to host their asset
# ---------------------------------------------------------------------------


def mirror_asset(manifest: AssetMirrorManifest) -> AssetMirrorRecord:
    """Record a federation mirror for an asset we are hosting.

    Idempotent: a second call with the same local_asset_id updates the
    origin fields. The mirror table is THIS instance's view of which of
    our assets actually live somewhere else's authority; nothing about
    this call touches the origin instance.
    """
    _ensure_schema()
    now_iso = manifest.mirrored_at or _now_iso()
    with _session() as session:
        existing = (
            session.query(FederatedAssetMirrorRecord)
            .filter_by(local_asset_id=manifest.local_asset_id)
            .one_or_none()
        )
        if existing is None:
            row = FederatedAssetMirrorRecord(
                local_asset_id=manifest.local_asset_id,
                origin_instance_id=manifest.origin_instance_id,
                origin_asset_id=manifest.origin_asset_id,
                origin_url=manifest.origin_url,
                origin_payment_address=manifest.origin_payment_address,
                mirrored_at=now_iso,
            )
            session.add(row)
        else:
            existing.origin_instance_id = manifest.origin_instance_id
            existing.origin_asset_id = manifest.origin_asset_id
            existing.origin_url = manifest.origin_url
            existing.origin_payment_address = manifest.origin_payment_address
            existing.mirrored_at = now_iso
        session.flush()
    return AssetMirrorRecord(
        local_asset_id=manifest.local_asset_id,
        origin_instance_id=manifest.origin_instance_id,
        origin_asset_id=manifest.origin_asset_id,
        origin_url=manifest.origin_url,
        origin_payment_address=manifest.origin_payment_address,
        mirrored_at=now_iso,
    )


def get_mirror(local_asset_id: str) -> AssetMirrorRecord | None:
    _ensure_schema()
    with _session() as session:
        row = (
            session.query(FederatedAssetMirrorRecord)
            .filter_by(local_asset_id=local_asset_id)
            .one_or_none()
        )
        if row is None:
            return None
        return AssetMirrorRecord(
            local_asset_id=row.local_asset_id,
            origin_instance_id=row.origin_instance_id,
            origin_asset_id=row.origin_asset_id,
            origin_url=row.origin_url,
            origin_payment_address=row.origin_payment_address,
            mirrored_at=row.mirrored_at,
        )


def list_mirrors(origin_instance_id: str | None = None) -> list[AssetMirrorRecord]:
    _ensure_schema()
    with _session() as session:
        q = session.query(FederatedAssetMirrorRecord)
        if origin_instance_id:
            q = q.filter_by(origin_instance_id=origin_instance_id)
        rows = q.order_by(FederatedAssetMirrorRecord.local_asset_id).all()
        return [
            AssetMirrorRecord(
                local_asset_id=r.local_asset_id,
                origin_instance_id=r.origin_instance_id,
                origin_asset_id=r.origin_asset_id,
                origin_url=r.origin_url,
                origin_payment_address=r.origin_payment_address,
                mirrored_at=r.mirrored_at,
            )
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Read attribution — peer tells us about a read of our asset
# ---------------------------------------------------------------------------


class SignatureRejection(Exception):
    """Raised when a federation envelope's signature cannot be verified."""


def receive_read_attribution(envelope: ReadAttributionEnvelope) -> ReadAttributionAck:
    """Accept a signed read-attribution envelope from a serving instance.

    Verifies the signature against the secret we hold for the serving
    instance. On success, records the attestation, bridges the read into
    read_tracking_service under a federated reader_id, and returns ack.
    On signature failure, raises SignatureRejection — nothing is stored.

    Sovereignty notes:
      - We are authoritative for the asset_origin_id; the envelope's
        reader_instance_id is authoritative for the reader.
      - If the peer is not registered, the secret is missing and we
        reject the envelope. Federation is opt-in on both sides.
    """
    _ensure_schema()
    peer = federation_service.get_instance(envelope.reader_instance_id)
    peer_secret = (peer.public_key if peer else None) or None

    if peer_secret is None:
        raise SignatureRejection(
            f"Cannot verify read attribution: peer {envelope.reader_instance_id!r} "
            f"is not registered or has no signing secret on file."
        )

    if not verify_read_attribution(envelope, peer_secret):
        raise SignatureRejection(
            f"Read attribution signature did not verify for peer "
            f"{envelope.reader_instance_id!r}."
        )

    now_iso = _now_iso()
    reader_id = federated_reader_id(envelope.reader_instance_id, envelope.reader_subject)
    resonance_dict = dict(envelope.concept_resonance) if envelope.concept_resonance else None

    with _session() as session:
        row = FederatedReadAttestationRecord(
            asset_origin_id=envelope.asset_origin_id,
            reader_instance_id=envelope.reader_instance_id,
            reader_subject=envelope.reader_subject,
            read_type=envelope.read_type,
            cc_amount=float(envelope.cc_amount),
            concept_resonance_json=(
                json.dumps(resonance_dict) if resonance_dict else None
            ),
            observed_at=envelope.observed_at,
            received_at=now_iso,
            signature=envelope.signature,
            signature_verified=True,
            status="verified",
        )
        session.add(row)
        session.flush()

    # Bridge into read_tracking so settlement sees this read like any other.
    # Soft-fail: federation accounting still works even if the local
    # read-tracking layer is unreachable during this call.
    try:
        from app.services import read_tracking_service

        read_tracking_service.record_read(
            envelope.asset_origin_id,
            reader_id=reader_id,
            read_type=envelope.read_type,
            cc_amount=float(envelope.cc_amount),
            concept_resonance_snapshot=resonance_dict,
        )
    except Exception as exc:
        logger.warning(
            "federation_value_flow: read_tracking bridge failed for asset=%s reader=%s: %s",
            envelope.asset_origin_id,
            reader_id,
            exc,
        )

    return ReadAttributionAck(
        asset_origin_id=envelope.asset_origin_id,
        reader_instance_id=envelope.reader_instance_id,
        status="verified",
        federated_reader_id=reader_id,
        note="signature verified and read bridged to local read-tracking",
    )


def list_read_attestations(
    asset_origin_id: str | None = None,
    reader_instance_id: str | None = None,
    status: str | None = None,
) -> FederatedReadAttestationListResponse:
    _ensure_schema()
    with _session() as session:
        q = session.query(FederatedReadAttestationRecord)
        if asset_origin_id:
            q = q.filter_by(asset_origin_id=asset_origin_id)
        if reader_instance_id:
            q = q.filter_by(reader_instance_id=reader_instance_id)
        if status:
            q = q.filter_by(status=status)
        rows = q.order_by(FederatedReadAttestationRecord.observed_at).all()
        out = [
            FederatedReadAttestationOut(
                id=r.id,
                asset_origin_id=r.asset_origin_id,
                reader_instance_id=r.reader_instance_id,
                reader_subject=r.reader_subject,
                read_type=r.read_type,
                cc_amount=float(r.cc_amount or 0),
                observed_at=r.observed_at,
                received_at=r.received_at,
                status=r.status,
                signature_verified=bool(r.signature_verified),
            )
            for r in rows
        ]
    return FederatedReadAttestationListResponse(
        asset_origin_id=asset_origin_id,
        reader_instance_id=reader_instance_id,
        attestations=out,
        count=len(out),
    )


# ---------------------------------------------------------------------------
# Settlement share computation — we are origin; peer served our content
# ---------------------------------------------------------------------------


def _in_period(observed_at: str, period_start: str, period_end: str) -> bool:
    """observed_at lies in [period_start, period_end)."""
    return period_start <= observed_at < period_end


def compute_federated_shares(
    request: ComputeFederatedSharesRequest,
) -> ComputeFederatedSharesResponse:
    """Compute per-peer settlement envelopes for federated reads in a window.

    We are the asset's origin; peers served our content and earned a share.
    For each peer with attestations in the window:

      1. Sum total CC across their reads of our assets
      2. Compute their share = total * serving_share
      3. Compute the creator's share = total * creator_share
      4. Sign the envelope with the secret we share with the peer
      5. Store in the outbox; optionally flip attestations to status=settled
      6. Return envelopes — caller transports them
    """
    _ensure_schema()
    serving_share = (
        request.serving_share
        if request.serving_share is not None
        else DEFAULT_FEDERATED_SERVING_SHARE
    )
    creator_share = 1.0 - serving_share

    envelopes: list[SettlementShareEnvelope] = []
    total_to_serving = 0.0
    total_to_creator = 0.0
    settled_count = 0

    with _session() as session:
        q = session.query(FederatedReadAttestationRecord).filter(
            FederatedReadAttestationRecord.observed_at >= request.period_start,
            FederatedReadAttestationRecord.observed_at < request.period_end,
            FederatedReadAttestationRecord.status.in_(("received", "verified")),
        )
        if request.serving_instance_id:
            q = q.filter_by(reader_instance_id=request.serving_instance_id)
        rows = q.all()

        # Group by serving instance, then by asset.
        by_peer: dict[str, list[FederatedReadAttestationRecord]] = {}
        for r in rows:
            by_peer.setdefault(r.reader_instance_id, []).append(r)

        self_instance_id = federation_service._self_instance_id()

        for peer_instance_id, peer_rows in by_peer.items():
            peer = federation_service.get_instance(peer_instance_id)
            peer_secret = (peer.public_key if peer else None) or None
            if not peer_secret:
                logger.warning(
                    "federation_value_flow: skipping settlement for peer %s: no signing secret on file",
                    peer_instance_id,
                )
                continue

            per_asset: dict[str, dict] = {}
            peer_total = 0.0
            for r in peer_rows:
                entry = per_asset.setdefault(
                    r.asset_origin_id,
                    {"asset_origin_id": r.asset_origin_id, "read_count": 0, "cc_amount_total": 0.0},
                )
                entry["read_count"] += 1
                entry["cc_amount_total"] += float(r.cc_amount or 0)
                peer_total += float(r.cc_amount or 0)

            cc_to_serving = round(peer_total * serving_share, 8)
            cc_to_creator = round(peer_total * creator_share, 8)

            breakdown = [
                {
                    "asset_origin_id": entry["asset_origin_id"],
                    "read_count": entry["read_count"],
                    "cc_amount_to_serving": round(
                        entry["cc_amount_total"] * serving_share, 8
                    ),
                }
                for entry in sorted(per_asset.values(), key=lambda e: e["asset_origin_id"])
            ]

            unsigned = {
                "origin_instance_id": self_instance_id,
                "serving_instance_id": peer_instance_id,
                "period_start": request.period_start,
                "period_end": request.period_end,
                "read_count": len(peer_rows),
                "cc_amount_to_serving": cc_to_serving,
                "cc_amount_to_creator": cc_to_creator,
                "serving_share": serving_share,
                "creator_share": creator_share,
                "asset_breakdown": breakdown,
            }
            signature = sign_settlement_share(unsigned, peer_secret)
            envelope = SettlementShareEnvelope(**unsigned, signature=signature)

            session.add(
                FederatedSettlementOutboxRecord(
                    serving_instance_id=peer_instance_id,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    read_count=len(peer_rows),
                    cc_amount_to_serving=cc_to_serving,
                    cc_amount_to_creator=cc_to_creator,
                    asset_breakdown_json=json.dumps(breakdown),
                    signature=signature,
                    computed_at=_now_iso(),
                )
            )

            if request.mark_settled:
                for r in peer_rows:
                    r.status = "settled"
                    settled_count += 1

            envelopes.append(envelope)
            total_to_serving += cc_to_serving
            total_to_creator += cc_to_creator

        session.flush()

    return ComputeFederatedSharesResponse(
        period_start=request.period_start,
        period_end=request.period_end,
        envelopes=envelopes,
        serving_share=serving_share,
        creator_share=creator_share,
        total_cc_to_serving=round(total_to_serving, 8),
        total_cc_to_creator=round(total_to_creator, 8),
        attestations_settled=settled_count,
    )


def list_outbox(
    serving_instance_id: str | None = None,
) -> list[SettlementShareEnvelope]:
    """Walk the settlement outbox — envelopes WE computed and signed."""
    _ensure_schema()
    with _session() as session:
        q = session.query(FederatedSettlementOutboxRecord)
        if serving_instance_id:
            q = q.filter_by(serving_instance_id=serving_instance_id)
        rows = q.order_by(FederatedSettlementOutboxRecord.computed_at).all()
        self_id = federation_service._self_instance_id()
        return [
            SettlementShareEnvelope(
                origin_instance_id=self_id,
                serving_instance_id=r.serving_instance_id,
                period_start=r.period_start,
                period_end=r.period_end,
                read_count=r.read_count,
                cc_amount_to_serving=float(r.cc_amount_to_serving or 0),
                cc_amount_to_creator=float(r.cc_amount_to_creator or 0),
                serving_share=DEFAULT_FEDERATED_SERVING_SHARE,
                creator_share=DEFAULT_FEDERATED_CREATOR_SHARE,
                asset_breakdown=json.loads(r.asset_breakdown_json) if r.asset_breakdown_json else [],
                signature=r.signature,
            )
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Settlement inbox — peer settled OUR serving fee
# ---------------------------------------------------------------------------


def receive_settlement_share(envelope: SettlementShareEnvelope) -> SettlementShareAck:
    """Accept a settlement envelope FROM a peer who owes us a serving fee.

    Verifies the signature against the secret we hold for the origin
    instance. Records into the inbox. CC transfer itself is downstream —
    the inbox is the durable claim that the peer attested this share.
    """
    _ensure_schema()
    origin = federation_service.get_instance(envelope.origin_instance_id)
    origin_secret = (origin.public_key if origin else None) or None
    if origin_secret is None:
        raise SignatureRejection(
            f"Cannot verify settlement share: origin {envelope.origin_instance_id!r} "
            f"is not registered or has no signing secret on file."
        )
    if not verify_settlement_share(envelope, origin_secret):
        raise SignatureRejection(
            f"Settlement share signature did not verify for origin "
            f"{envelope.origin_instance_id!r}."
        )

    now_iso = _now_iso()
    with _session() as session:
        row = FederatedSettlementInboxRecord(
            origin_instance_id=envelope.origin_instance_id,
            serving_instance_id=envelope.serving_instance_id,
            period_start=envelope.period_start,
            period_end=envelope.period_end,
            read_count=envelope.read_count,
            cc_amount_to_serving=float(envelope.cc_amount_to_serving),
            cc_amount_to_creator=float(envelope.cc_amount_to_creator),
            asset_breakdown_json=json.dumps(envelope.asset_breakdown),
            signature=envelope.signature,
            signature_verified=True,
            received_at=now_iso,
            status="verified",
        )
        session.add(row)
        session.flush()
        inbox_id = row.id

    return SettlementShareAck(
        inbox_id=inbox_id,
        origin_instance_id=envelope.origin_instance_id,
        status="verified",
        note="signature verified and envelope logged to inbox",
    )


def list_inbox(
    origin_instance_id: str | None = None,
) -> SettlementInboxListResponse:
    _ensure_schema()
    with _session() as session:
        q = session.query(FederatedSettlementInboxRecord)
        if origin_instance_id:
            q = q.filter_by(origin_instance_id=origin_instance_id)
        rows = q.order_by(FederatedSettlementInboxRecord.received_at).all()
        entries = [
            SettlementInboxEntryOut(
                id=r.id,
                origin_instance_id=r.origin_instance_id,
                period_start=r.period_start,
                period_end=r.period_end,
                read_count=r.read_count,
                cc_amount_to_serving=float(r.cc_amount_to_serving or 0),
                cc_amount_to_creator=float(r.cc_amount_to_creator or 0),
                received_at=r.received_at,
                status=r.status,
                signature_verified=bool(r.signature_verified),
            )
            for r in rows
        ]
    return SettlementInboxListResponse(
        origin_instance_id=origin_instance_id,
        entries=entries,
        count=len(entries),
    )


# ---------------------------------------------------------------------------
# Test reset
# ---------------------------------------------------------------------------


def _reset_for_tests() -> None:
    """Clear all federation value-flow rows. Used by test fixtures."""
    _ensure_schema()
    with _session() as session:
        session.query(FederatedAssetMirrorRecord).delete()
        session.query(FederatedReadAttestationRecord).delete()
        session.query(FederatedSettlementInboxRecord).delete()
        session.query(FederatedSettlementOutboxRecord).delete()


__all__ = [
    "DEFAULT_FEDERATED_CREATOR_SHARE",
    "DEFAULT_FEDERATED_SERVING_SHARE",
    "FEDERATED_READER_PREFIX",
    "FederatedAssetMirrorRecord",
    "FederatedReadAttestationRecord",
    "FederatedSettlementInboxRecord",
    "FederatedSettlementOutboxRecord",
    "SignatureRejection",
    "compute_federated_shares",
    "federated_reader_id",
    "get_mirror",
    "is_federated_reader_id",
    "list_inbox",
    "list_mirrors",
    "list_outbox",
    "list_read_attestations",
    "mirror_asset",
    "parse_federated_reader_id",
    "receive_read_attribution",
    "receive_settlement_share",
    "sign_read_attribution",
    "sign_settlement_share",
    "verify_read_attribution",
    "verify_settlement_share",
]
