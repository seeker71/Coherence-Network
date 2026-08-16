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
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import DateTime, Integer, String, Text, case, func, select, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services import form_kernel_bridge, unified_db


PUBLIC_SINGLE_TURN_DISCLOSURE_ACK = "public-unlisted-v1"
PUBLIC_DISCLOSURE_ACK = "public-unlisted-thread-v2"
PUBLIC_DISCLOSURE_ACKS = frozenset(
    (PUBLIC_SINGLE_TURN_DISCLOSURE_ACK, PUBLIC_DISCLOSURE_ACK)
)
MAX_THREAD_TURNS = 128
ACTIVE_STATES = ("pending", "running", "releasing")
TERMINAL_STATES = ("answered", "miss", "failed", "tombstoned")
_ADMISSION_LOCK_KEY = 0x434F484449414C47  # "COHDIALG"
_ADMISSION_LOCK = threading.RLock()
_THREAD_PLANNER_LOCK_KEY = 0x434F484454485250  # "COHDTHRP"
_THREAD_PLANNER_SLOT = threading.Lock()
_THREAD_WINDOW_RECIPE = (
    Path(__file__).resolve().parent.parent
    / "form_recipes"
    / "public_dialogue_thread_window.fk"
)
_THREAD_WINDOW_BAND_ENTRY = "  (dialogue-thread-window-band))"


class PublicDialogueRateLimitError(RuntimeError):
    def __init__(self, retry_after: int):
        super().__init__("this network peer has filled its present dialogue interval")
        self.retry_after = retry_after


class PublicDialogueAdmissionBusyError(RuntimeError):
    def __init__(self):
        super().__init__("the public dialogue admission lane is presently attending another offer")


class PublicDialogueThreadDisclosureError(ValueError):
    def __init__(self):
        super().__init__("this turn grants single-turn access only")


class PublicDialogueThreadPlannerBusyError(RuntimeError):
    def __init__(self):
        super().__init__("the native dialogue thread planner is presently attending another read")


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


@contextmanager
def _admission_slot() -> Iterator[None]:
    if not _ADMISSION_LOCK.acquire(blocking=False):
        raise PublicDialogueAdmissionBusyError()
    try:
        yield
    finally:
        _ADMISSION_LOCK.release()


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
    if session.bind is None:
        return
    if session.bind.dialect.name == "postgresql":
        acquired = session.scalar(
            text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
            {"lock_key": _ADMISSION_LOCK_KEY},
        )
        if not acquired:
            raise PublicDialogueAdmissionBusyError()
    elif session.bind.dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))


@contextmanager
def _thread_planning_slot() -> Iterator[Any]:
    """Bound fkwu planning once per process and, on production, once per DB."""
    if not _THREAD_PLANNER_SLOT.acquire(blocking=False):
        raise PublicDialogueThreadPlannerBusyError()
    try:
        with unified_db.session() as session:
            if session.bind is not None and session.bind.dialect.name == "postgresql":
                acquired = session.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                    {"lock_key": _THREAD_PLANNER_LOCK_KEY},
                )
                if not acquired:
                    raise PublicDialogueThreadPlannerBusyError()
            yield session
    finally:
        _THREAD_PLANNER_SLOT.release()


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
        parent = session.scalar(
            select(PublicDialogueRecord)
            .where(PublicDialogueRecord.id == parent_dialogue_id)
            .with_for_update()
        )
        if parent is None or parent.state in ("tombstoned", "releasing"):
            raise ValueError(
                "parent_dialogue_id does not name an available public dialogue"
            )
        if parent.disclosure_ack != PUBLIC_DISCLOSURE_ACK:
            raise ValueError(
                "parent_dialogue_id names a single-turn-only public dialogue"
            )
        expires_at = parent.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            raise ValueError(
                "parent_dialogue_id does not name an available public dialogue"
            )


@contextmanager
def serialized_dialogue_admission(
    *,
    network_peer_sha256: str,
    parent_dialogue_id: str | None,
    max_active: int,
    starts_per_window: int,
    start_window_seconds: int,
) -> Any:
    """Hold the cross-process capacity gate through Form and persistence."""
    ensure_schema()
    with _admission_slot():
        with unified_db.session() as session:
            _admission_lock(session)
            _check_admission(
                session,
                network_peer_sha256=network_peer_sha256,
                parent_dialogue_id=parent_dialogue_id,
                max_active=max_active,
                starts_per_window=starts_per_window,
                start_window_seconds=start_window_seconds,
            )
            yield session


def create_dialogue(
    *,
    question: str,
    question_sha256: str,
    point_of_view: str,
    requested_locale: str,
    canonical_locale: str,
    parent_dialogue_id: str | None,
    public_disclosure_ack: str = PUBLIC_DISCLOSURE_ACK,
    channel_timeout_seconds: int,
    network_peer_sha256: str,
    expires_at: datetime,
    max_active: int,
    starts_per_window: int,
    start_window_seconds: int,
    admission_session: Any | None = None,
) -> tuple[dict[str, Any], str]:
    ensure_schema()
    if admission_session is None:
        with serialized_dialogue_admission(
            network_peer_sha256=network_peer_sha256,
            parent_dialogue_id=parent_dialogue_id,
            max_active=max_active,
            starts_per_window=starts_per_window,
            start_window_seconds=start_window_seconds,
        ) as session:
            return create_dialogue(
                question=question,
                question_sha256=question_sha256,
                point_of_view=point_of_view,
                requested_locale=requested_locale,
                canonical_locale=canonical_locale,
                parent_dialogue_id=parent_dialogue_id,
                public_disclosure_ack=public_disclosure_ack,
                channel_timeout_seconds=channel_timeout_seconds,
                network_peer_sha256=network_peer_sha256,
                expires_at=expires_at,
                max_active=max_active,
                starts_per_window=starts_per_window,
                start_window_seconds=start_window_seconds,
                admission_session=session,
            )

    if public_disclosure_ack not in PUBLIC_DISCLOSURE_ACKS:
        raise ValueError("unknown public dialogue disclosure acknowledgement")
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
        disclosure_ack=public_disclosure_ack,
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
    admission_session.add(record)
    admission_session.flush()
    return _row(record), removal_token


def get_dialogue(dialogue_id: str) -> dict[str, Any] | None:
    ensure_schema()
    with unified_db.session() as session:
        row = session.scalar(
            select(PublicDialogueRecord)
            .where(PublicDialogueRecord.id == dialogue_id)
            .with_for_update()
        )
        if row is None:
            return None
        if row.state == "releasing":
            return _released_owned_view(row)
        now = _now()
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if row.state != "tombstoned" and expires_at <= now:
            if row.state == "running":
                return _expired_running_view(row)
            _tombstone(row, now=now)
        return _row(row)


def _thread_child_candidates(
    session: Any,
    frontier: list[str],
    seen_ids: set[str],
    limit: int,
) -> list[PublicDialogueRecord]:
    return list(
        session.scalars(
            select(PublicDialogueRecord)
            .where(
                PublicDialogueRecord.parent_dialogue_id.in_(frontier),
                PublicDialogueRecord.id.notin_(seen_ids),
            )
            .order_by(
                PublicDialogueRecord.created_at.asc(),
                PublicDialogueRecord.id.asc(),
            )
            .limit(limit)
        )
    )


def _thread_candidates(
    session: Any,
    anchor: PublicDialogueRecord,
    max_turns: int,
) -> list[PublicDialogueRecord]:
    root = anchor
    ancestry = [anchor]
    ancestor_ids = {anchor.id}
    while root.parent_dialogue_id and len(ancestry) < max_turns:
        parent = session.scalar(
            select(PublicDialogueRecord).where(
                PublicDialogueRecord.id == root.parent_dialogue_id
            )
        )
        if parent is None or parent.id in ancestor_ids:
            break
        ancestor_ids.add(parent.id)
        ancestry.append(parent)
        root = parent

    rows = list(reversed(ancestry))
    seen_ids = {row.id for row in rows}
    frontier = list(seen_ids)
    while frontier and len(rows) < max_turns + 1:
        remaining = max_turns + 1 - len(rows)
        fresh = _thread_child_candidates(session, frontier, seen_ids, remaining)
        if not fresh:
            break
        rows.extend(fresh)
        frontier = [child.id for child in fresh]
        seen_ids.update(frontier)
    return rows


def _native_thread_window(
    candidates: list[PublicDialogueRecord],
    anchor_id: str,
    max_turns: int,
) -> dict[str, Any]:
    """Let Form choose topology and truncation over persistence-carried rows."""
    source = _THREAD_WINDOW_RECIPE.read_text(encoding="utf-8")
    if source.count(_THREAD_WINDOW_BAND_ENTRY) != 1:
        raise RuntimeError("native Form dialogue thread entry is unavailable")
    identifiers: dict[str, str] = {}
    nodes = []
    for row in candidates:
        node_id = row.id.encode("utf-8").hex()
        parent_id = (row.parent_dialogue_id or "").encode("utf-8").hex()
        identifiers[node_id] = row.id
        identifiers[parent_id] = row.parent_dialogue_id or ""
        nodes.append(f'(list "{node_id}" "{parent_id}")')
    anchor_hex = anchor_id.encode("utf-8").hex()
    invocation = (
        "(dialogue-thread-window-receipt (list "
        + " ".join(nodes)
        + f') "{anchor_hex}" {max_turns})'
    )
    receipt = form_kernel_bridge.run_recipe(
        source.replace(_THREAD_WINDOW_BAND_ENTRY, f"  {invocation})"),
        timeout=10,
    )
    pieces = receipt.split("|")
    if len(pieces) != 6 or pieces[5] not in ("0", "1"):
        raise RuntimeError("native Form dialogue thread returned an invalid verdict")
    selected_hex = pieces[4].split(",") if pieces[4] else []
    if (
        not selected_hex
        or len(selected_hex) > max_turns
        or len(selected_hex) != len(set(selected_hex))
        or anchor_hex not in selected_hex
        or any(value not in identifiers for value in selected_hex)
    ):
        raise RuntimeError("native Form dialogue thread returned an invalid window")

    def identity(value: str) -> str | None:
        if not value:
            return None
        if value not in identifiers:
            raise RuntimeError("native Form dialogue thread returned an unknown identity")
        return identifiers[value]

    selected = [identifiers[value] for value in selected_hex]
    root_id = identity(pieces[0])
    oldest_id = identity(pieces[1])
    continuation_id = identity(pieces[2])
    if identity(pieces[3]) != anchor_id or oldest_id != selected[0]:
        raise RuntimeError("native Form dialogue thread returned an unbound window")
    if (root_id is None) == (continuation_id is None):
        raise RuntimeError("native Form dialogue thread returned an ambiguous root")
    return {
        "root_dialogue_id": root_id,
        "oldest_observed_dialogue_id": oldest_id,
        "continuation_parent_dialogue_id": continuation_id,
        "anchor_dialogue_id": anchor_id,
        "selected_ids": selected,
        "truncated": pieces[5] == "1",
    }


def _observe_thread_rows(
    rows: list[PublicDialogueRecord],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    for row in rows:
        if row.state == "releasing":
            observed.append(_released_owned_view(row))
            continue
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if row.state != "tombstoned" and expires_at <= now:
            if row.state == "running":
                observed.append(_expired_running_view(row))
                continue
            _tombstone(row, now=now)
        observed.append(_row(row))
    return observed


def get_dialogue_thread(
    dialogue_id: str,
    *,
    max_turns: int = MAX_THREAD_TURNS,
) -> dict[str, Any] | None:
    """Read one bounded unlisted dialogue tree from any turn capability."""
    if isinstance(max_turns, bool) or not 1 <= max_turns <= MAX_THREAD_TURNS:
        raise ValueError(f"max_turns must be between 1 and {MAX_THREAD_TURNS}")
    ensure_schema()
    with _thread_planning_slot() as session:
        anchor = session.scalar(
            select(PublicDialogueRecord).where(PublicDialogueRecord.id == dialogue_id)
        )
        if anchor is None:
            return None
        if anchor.disclosure_ack != PUBLIC_DISCLOSURE_ACK:
            raise PublicDialogueThreadDisclosureError()
        candidates = _thread_candidates(session, anchor, max_turns)
        if any(row.disclosure_ack != PUBLIC_DISCLOSURE_ACK for row in candidates):
            raise PublicDialogueThreadDisclosureError()
        plan = _native_thread_window(candidates, dialogue_id, max_turns)
    with unified_db.session() as session:
        lock_order = case(
            {
                row_id: position
                for position, row_id in enumerate(plan["selected_ids"])
            },
            value=PublicDialogueRecord.id,
            else_=len(plan["selected_ids"]),
        )
        locked = list(
            session.scalars(
                select(PublicDialogueRecord)
                .where(PublicDialogueRecord.id.in_(plan["selected_ids"]))
                .order_by(lock_order)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        locked_by_id = {row.id: row for row in locked}
        if set(locked_by_id) != set(plan["selected_ids"]):
            raise RuntimeError("dialogue thread changed before its native window locked")
        rows = [locked_by_id[row_id] for row_id in plan["selected_ids"]]
        observed = _observe_thread_rows(rows, now=_now())
        return {
            "root_dialogue_id": plan["root_dialogue_id"],
            "oldest_observed_dialogue_id": plan["oldest_observed_dialogue_id"],
            "continuation_parent_dialogue_id": plan[
                "continuation_parent_dialogue_id"
            ],
            "anchor_dialogue_id": plan["anchor_dialogue_id"],
            "turns": observed,
            "turn_count": len(observed),
            "truncated": plan["truncated"],
        }


def _expired_running_view(row: PublicDialogueRecord) -> dict[str, Any]:
    """Hide expired public content without abandoning its native carrier."""
    observed = _row(row)
    observed.update(
        state="tombstoned",
        question="[released]",
        question_sha256="0" * 64,
        point_of_view="[released]",
        output={
            "outcome": "tombstoned",
            "detail": "public content expired; native cleanup remains owned",
        },
    )
    return observed


def _released_owned_view(row: PublicDialogueRecord) -> dict[str, Any]:
    """Expose a releasing row as removed while its carrier remains owned."""
    observed = _row(row)
    observed["state"] = "tombstoned"
    return observed


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
                case(
                    (PublicDialogueRecord.state == "releasing", 0),
                    (PublicDialogueRecord.state == "running", 1),
                    else_=2,
                ),
                PublicDialogueRecord.created_at.asc(),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        if row.state == "releasing":
            return _row(row)
        recovered = row.state == "running"
        row.state = "running"
        row.claimed_by = run_id
        if not recovered:
            row.attempt = int(row.attempt or 0) + 1
        row.updated_at = _now()
        session.flush()
        claimed = _row(row)
        claimed["recovered"] = recovered
        return claimed


def begin_recovered_dialogue_attempt(dialogue_id: str, run_id: str) -> int | None:
    """Spend one execution attempt only after prior carrier cleanup succeeded."""
    ensure_schema()
    with unified_db.session() as session:
        row = _locked_dialogue(session, dialogue_id)
        if row is None or row.state != "running" or row.claimed_by != run_id:
            return None
        row.carrier_pgid = None
        row.attempt = int(row.attempt or 0) + 1
        row.updated_at = _now()
        return row.attempt


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
        now = _now()
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            _tombstone(row, now=now)
            return True
        row.state = state
        row.output_json = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
        row.carrier_pgid = None
        row.updated_at = now
        return True


def tombstone_dialogue(dialogue_id: str, removal_token_sha256: str) -> int | bool:
    ensure_schema()
    with unified_db.session() as session:
        row = _locked_dialogue(session, dialogue_id)
        if row is None or not secrets.compare_digest(
            row.removal_token_sha256, removal_token_sha256
        ):
            return False
        if row.state == "tombstoned":
            return True
        if row.state == "releasing":
            return row.carrier_pgid if row.carrier_pgid is not None else True
        carrier_pgid = row.carrier_pgid
        if row.state == "running" and carrier_pgid is not None:
            _begin_release(row)
            return carrier_pgid
        _tombstone(row)
        return True


def finish_releasing_dialogue(dialogue_id: str, carrier_pgid: int) -> bool:
    """Clear durable carrier ownership only after its release was acknowledged."""
    ensure_schema()
    with unified_db.session() as session:
        row = _locked_dialogue(session, dialogue_id)
        if (
            row is None
            or row.state != "releasing"
            or row.carrier_pgid != carrier_pgid
        ):
            return False
        row.state = "tombstoned"
        row.claimed_by = None
        row.carrier_pgid = None
        return True


def tombstone_expired() -> int:
    ensure_schema()
    now = _now()
    with unified_db.session() as session:
        rows = list(
            session.scalars(
                select(PublicDialogueRecord)
                .where(
                    PublicDialogueRecord.state.notin_(
                        ("tombstoned", "running", "releasing")
                    ),
                    PublicDialogueRecord.expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            _tombstone(row, now=now)
        return len(rows)


def _begin_release(row: PublicDialogueRecord, *, now: datetime | None = None) -> None:
    witnessed = now or _now()
    row.state = "releasing"
    row.question = "[released]"
    row.question_sha256 = "0" * 64
    row.point_of_view = "[released]"
    row.output_json = json.dumps(
        {"outcome": "tombstoned", "detail": "public content released"},
        separators=(",", ":"),
    )
    row.updated_at = witnessed
    row.tombstoned_at = witnessed


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
    row.claimed_by = None
    row.carrier_pgid = None
    row.updated_at = witnessed
    row.tombstoned_at = witnessed
