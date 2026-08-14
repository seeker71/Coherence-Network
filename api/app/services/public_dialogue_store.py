"""Durable cells for the unlisted public dialogue lane.

This is a dedicated table in the existing unified database.  Dialogue rows do
not share the internal agent-task namespace, so public reads and worker claims
cannot cross into private orchestration tasks.
"""

from __future__ import annotations

import json
import hashlib
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, case, func, select, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services import unified_db


PUBLIC_DISCLOSURE_ACK = "public-unlisted-v1"
ACTIVE_STATES = ("pending", "running")
TERMINAL_STATES = ("answered", "miss", "failed", "tombstoned")
_ADMISSION_LOCK_KEY = 0x434F484449414C47  # "COHDIALG"
_ADMISSION_LOCK = threading.Lock()


class PublicDialogueRateLimitError(RuntimeError):
    def __init__(self, retry_after: int):
        super().__init__("this network peer has filled its present dialogue interval")
        self.retry_after = retry_after


class PublicDialogueRecord(Base):
    __tablename__ = "public_dialogues"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    state: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    point_of_view: Mapped[str] = mapped_column(Text, nullable=False)
    requested_locale: Mapped[str] = mapped_column(String(80), nullable=False)
    canonical_locale: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_dialogue_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    channel_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    disclosure_ack: Mapped[str] = mapped_column(String(40), nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    network_peer_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    removal_token_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    carrier_pgid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    tombstoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _decode_output(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _row(row: PublicDialogueRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "state": row.state,
        "question": row.question,
        "question_sha256": row.question_sha256,
        "point_of_view": row.point_of_view,
        "requested_locale": row.requested_locale,
        "canonical_locale": row.canonical_locale,
        "parent_dialogue_id": row.parent_dialogue_id,
        "channel_timeout_seconds": row.channel_timeout_seconds,
        "disclosure_ack": row.disclosure_ack,
        "visibility": row.visibility,
        "output": _decode_output(row.output_json),
        "claimed_by": row.claimed_by,
        "carrier_pgid": row.carrier_pgid,
        "attempt": row.attempt,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "expires_at": _iso(row.expires_at),
        "tombstoned_at": _iso(row.tombstoned_at),
    }


def ensure_schema() -> None:
    unified_db.ensure_schema()


def _admission_lock(session: Any) -> None:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _ADMISSION_LOCK_KEY},
        )


def _check_admission(
    session: Any,
    *,
    network_peer_sha256: str,
    parent_dialogue_id: str | None,
    max_active: int,
    starts_per_window: int,
    start_window_seconds: int,
) -> None:
    active = session.scalar(
        select(func.count()).select_from(PublicDialogueRecord).where(
            PublicDialogueRecord.state.in_(ACTIVE_STATES)
        )
    )
    if int(active or 0) >= max_active:
        raise RuntimeError("the public dialogue queue is presently full")
    now = _now()
    recent_starts = session.scalar(
        select(func.count()).select_from(PublicDialogueRecord).where(
            PublicDialogueRecord.network_peer_sha256 == network_peer_sha256,
            PublicDialogueRecord.created_at
            > now - timedelta(seconds=start_window_seconds),
        )
    )
    if int(recent_starts or 0) >= starts_per_window:
        raise PublicDialogueRateLimitError(start_window_seconds)
    if parent_dialogue_id:
        parent = session.get(PublicDialogueRecord, parent_dialogue_id)
        if parent is None or parent.state == "tombstoned":
            raise ValueError(
                "parent_dialogue_id does not name an available public dialogue"
            )


def preflight_dialogue_admission(
    *,
    network_peer_sha256: str,
    parent_dialogue_id: str | None,
    max_active: int,
    starts_per_window: int,
    start_window_seconds: int,
) -> None:
    """Reject an already-full peer or queue before native Form work begins.

    The locked check inside ``create_dialogue`` remains authoritative; this
    first read keeps known refusals from consuming a native admission process.
    """
    ensure_schema()
    with unified_db.session() as session:
        _check_admission(
            session,
            network_peer_sha256=network_peer_sha256,
            parent_dialogue_id=parent_dialogue_id,
            max_active=max_active,
            starts_per_window=starts_per_window,
            start_window_seconds=start_window_seconds,
        )


def create_dialogue(
    *,
    question: str,
    question_sha256: str,
    point_of_view: str,
    requested_locale: str,
    canonical_locale: str,
    parent_dialogue_id: str | None,
    channel_timeout_seconds: int,
    network_peer_sha256: str,
    expires_at: datetime,
    max_active: int,
    starts_per_window: int,
    start_window_seconds: int,
) -> tuple[dict[str, Any], str]:
    ensure_schema()
    with _ADMISSION_LOCK, unified_db.session() as session:
        _admission_lock(session)
        _check_admission(
            session,
            network_peer_sha256=network_peer_sha256,
            parent_dialogue_id=parent_dialogue_id,
            max_active=max_active,
            starts_per_window=starts_per_window,
            start_window_seconds=start_window_seconds,
        )
        now = _now()
        dialogue_id = "dlg_" + secrets.token_urlsafe(18)
        removal_token = secrets.token_urlsafe(32)

        record = PublicDialogueRecord(
            id=dialogue_id,
            state="pending",
            question=question,
            question_sha256=question_sha256,
            point_of_view=point_of_view,
            requested_locale=requested_locale,
            canonical_locale=canonical_locale,
            parent_dialogue_id=parent_dialogue_id,
            channel_timeout_seconds=channel_timeout_seconds,
            disclosure_ack=PUBLIC_DISCLOSURE_ACK,
            visibility="unlisted-public",
            network_peer_sha256=network_peer_sha256,
            removal_token_sha256=hashlib.sha256(removal_token.encode("utf-8")).hexdigest(),
            output_json=None,
            claimed_by=None,
            carrier_pgid=None,
            attempt=0,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            tombstoned_at=None,
        )
        session.add(record)
        session.flush()
        return _row(record), removal_token


def get_dialogue(dialogue_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with unified_db.session() as session:
        row = session.get(PublicDialogueRecord, dialogue_id)
        return _row(row) if row is not None else None


def _locked_dialogue(session: Any, dialogue_id: str) -> PublicDialogueRecord | None:
    return session.scalar(
        select(PublicDialogueRecord)
        .where(PublicDialogueRecord.id == dialogue_id)
        .with_for_update()
    )


def claim_next_dialogue(run_id: str) -> dict[str, Any] | None:
    """Claim one row while the caller holds the organism-wide worker lease.

    A pre-existing ``running`` row is selected first.  Because the advisory
    worker lease is released by PostgreSQL when a process dies, such a row is
    an interrupted read-only attempt and is safe to re-attend.
    """
    ensure_schema()
    with unified_db.session() as session:
        row = session.scalar(
            select(PublicDialogueRecord)
            .where(PublicDialogueRecord.state.in_(ACTIVE_STATES))
            .order_by(
                case((PublicDialogueRecord.state == "running", 0), else_=1),
                PublicDialogueRecord.created_at.asc(),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        row.state = "running"
        row.claimed_by = run_id
        row.attempt = int(row.attempt or 0) + 1
        row.updated_at = _now()
        session.flush()
        return _row(row)


def record_carrier_pgid(dialogue_id: str, run_id: str, pgid: int) -> bool:
    ensure_schema()
    with unified_db.session() as session:
        row = _locked_dialogue(session, dialogue_id)
        if row is None or row.state != "running" or row.claimed_by != run_id:
            return False
        row.carrier_pgid = int(pgid)
        row.updated_at = _now()
        return True


def finish_dialogue(
    dialogue_id: str,
    run_id: str,
    *,
    state: str,
    output: dict[str, Any],
) -> bool:
    if state not in ("answered", "miss", "failed"):
        raise ValueError("invalid terminal dialogue state")
    ensure_schema()
    with unified_db.session() as session:
        row = _locked_dialogue(session, dialogue_id)
        if row is None or row.state != "running" or row.claimed_by != run_id:
            return False
        row.state = state
        row.output_json = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
        row.carrier_pgid = None
        row.updated_at = _now()
        return True


def tombstone_dialogue(dialogue_id: str, removal_token_sha256: str) -> int | bool:
    ensure_schema()
    with unified_db.session() as session:
        row = _locked_dialogue(session, dialogue_id)
        if row is None or not secrets.compare_digest(
            row.removal_token_sha256, removal_token_sha256
        ):
            return False
        carrier_pgid = row.carrier_pgid
        _tombstone(row)
        return carrier_pgid if carrier_pgid is not None else True


def tombstone_expired() -> int:
    ensure_schema()
    now = _now()
    with unified_db.session() as session:
        rows = list(
            session.scalars(
                select(PublicDialogueRecord)
                .where(
                    PublicDialogueRecord.state.notin_(("tombstoned", "running")),
                    PublicDialogueRecord.expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            _tombstone(row, now=now)
        return len(rows)


def _tombstone(row: PublicDialogueRecord, *, now: datetime | None = None) -> None:
    witnessed = now or _now()
    row.state = "tombstoned"
    row.question = "[released]"
    row.question_sha256 = "0" * 64
    row.point_of_view = "[released]"
    row.output_json = json.dumps(
        {"outcome": "tombstoned", "detail": "public content released"},
        separators=(",", ":"),
    )
    row.removal_token_sha256 = ""
    row.claimed_by = None
    row.carrier_pgid = None
    row.updated_at = witnessed
    row.tombstoned_at = witnessed
