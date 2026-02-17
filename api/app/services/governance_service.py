"""Governance service for reviewable change requests and voting."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from app.models.governance import (
    ChangeRequest,
    ChangeRequestCreate,
    ChangeRequestStatus,
    ChangeRequestType,
    ChangeRequestVote,
    ChangeRequestVoteCreate,
    VoteDecision,
)
from app.models.idea import IdeaCreate, IdeaQuestionAnswerUpdate, IdeaQuestionCreate, IdeaUpdate
from app.models.spec_registry import SpecRegistryCreate, SpecRegistryUpdate
from app.services import idea_service, spec_registry_service


class Base(DeclarativeBase):
    pass


class ChangeRequestRecord(Base):
    __tablename__ = "governance_change_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    request_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    proposer_id: Mapped[str] = mapped_column(String, nullable=False)
    proposer_type: Mapped[str] = mapped_column(String, nullable=False)
    required_approvals: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    auto_apply_on_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default=ChangeRequestStatus.OPEN.value)
    approvals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applied_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ChangeRequestVoteRecord(Base):
    __tablename__ = "governance_change_request_votes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    change_request_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    voter_id: Mapped[str] = mapped_column(String, nullable=False)
    voter_type: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}


def _database_url() -> str:
    return spec_registry_service._database_url()  # noqa: SLF001


def _create_engine(url: str):
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = NullPool
    return create_engine(url, **kwargs)


def _engine():
    url = _database_url()
    if _ENGINE_CACHE["engine"] is not None and _ENGINE_CACHE["url"] == url:
        return _ENGINE_CACHE["engine"]
    engine = _create_engine(url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    _ENGINE_CACHE["url"] = url
    _ENGINE_CACHE["engine"] = engine
    _ENGINE_CACHE["sessionmaker"] = SessionLocal
    return engine


def _sessionmaker():
    _engine()
    return _ENGINE_CACHE["sessionmaker"]


@contextmanager
def _session() -> Session:
    SessionLocal = _sessionmaker()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_schema() -> None:
    spec_registry_service.ensure_schema()
    engine = _engine()
    Base.metadata.create_all(bind=engine)


def _default_required_approvals() -> int:
    raw = os.getenv("CHANGE_REQUEST_MIN_APPROVALS", "1").strip()
    try:
        value = int(raw)
    except ValueError:
        return 1
    return max(1, min(value, 10))


def _load_payload(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _parse_applied_result(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return data
    return None


def _to_vote_model(row: ChangeRequestVoteRecord) -> ChangeRequestVote:
    return ChangeRequestVote(
        id=row.id,
        change_request_id=row.change_request_id,
        voter_id=row.voter_id,
        voter_type=row.voter_type,
        decision=row.decision,
        rationale=row.rationale,
        created_at=row.created_at,
    )


def _to_model(
    row: ChangeRequestRecord,
    votes: list[ChangeRequestVoteRecord],
) -> ChangeRequest:
    return ChangeRequest(
        id=row.id,
        request_type=row.request_type,
        title=row.title,
        payload=_load_payload(row.payload_json),
        proposer_id=row.proposer_id,
        proposer_type=row.proposer_type,
        required_approvals=row.required_approvals,
        auto_apply_on_approval=row.auto_apply_on_approval,
        status=row.status,
        approvals=row.approvals,
        rejections=row.rejections,
        applied_result=_parse_applied_result(row.applied_result_json),
        votes=[_to_vote_model(v) for v in sorted(votes, key=lambda item: item.created_at)],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _apply_change_request(change_request: ChangeRequest) -> dict[str, Any]:
    payload = change_request.payload
    request_type = change_request.request_type

    if request_type == ChangeRequestType.IDEA_CREATE:
        created = idea_service.create_idea(
            idea_id=str(payload["id"]),
            name=str(payload["name"]),
            description=str(payload["description"]),
            potential_value=float(payload["potential_value"]),
            estimated_cost=float(payload["estimated_cost"]),
            confidence=float(payload.get("confidence", 0.5)),
            interfaces=[x for x in payload.get("interfaces", []) if isinstance(x, str)],
            open_questions=[
                IdeaQuestionCreate(**item)
                for item in payload.get("open_questions", [])
                if isinstance(item, dict)
            ],
        )
        if created is None:
            existing = idea_service.get_idea(str(payload["id"]))
            if existing is None:
                raise ValueError("idea already exists")
            return {"kind": "idea", "id": existing.id, "action": "already_exists"}
        return {"kind": "idea", "id": created.id, "action": "created"}

    if request_type == ChangeRequestType.IDEA_UPDATE:
        idea_id = str(payload["idea_id"])
        updated = idea_service.update_idea(
            idea_id=idea_id,
            actual_value=(float(payload["actual_value"]) if "actual_value" in payload else None),
            actual_cost=(float(payload["actual_cost"]) if "actual_cost" in payload else None),
            confidence=(float(payload["confidence"]) if "confidence" in payload else None),
            manifestation_status=(
                payload["manifestation_status"] if "manifestation_status" in payload else None
            ),
        )
        if updated is None:
            raise ValueError("idea not found")
        return {"kind": "idea", "id": idea_id, "action": "updated"}

    if request_type == ChangeRequestType.IDEA_ADD_QUESTION:
        idea_id = str(payload["idea_id"])
        updated, added = idea_service.add_question(
            idea_id=idea_id,
            question=str(payload["question"]),
            value_to_whole=float(payload["value_to_whole"]),
            estimated_cost=float(payload["estimated_cost"]),
        )
        if updated is None:
            raise ValueError("idea not found")
        if not added:
            raise ValueError("question already exists")
        return {"kind": "idea_question", "id": idea_id, "action": "added"}

    if request_type == ChangeRequestType.IDEA_ANSWER_QUESTION:
        idea_id = str(payload["idea_id"])
        updated, question_found = idea_service.answer_question(
            idea_id=idea_id,
            question=str(payload["question"]),
            answer=str(payload["answer"]),
            measured_delta=(float(payload["measured_delta"]) if "measured_delta" in payload else None),
        )
        if updated is None:
            raise ValueError("idea not found")
        if not question_found:
            raise ValueError("question not found")
        return {"kind": "idea_question", "id": idea_id, "action": "answered"}

    if request_type == ChangeRequestType.SPEC_CREATE:
        created = spec_registry_service.create_spec(SpecRegistryCreate(**payload))
        if created is None:
            raise ValueError("spec already exists")
        return {"kind": "spec", "id": created.spec_id, "action": "created"}

    if request_type == ChangeRequestType.SPEC_UPDATE:
        spec_id = str(payload["spec_id"])
        data = {k: v for k, v in payload.items() if k != "spec_id"}
        updated = spec_registry_service.update_spec(spec_id, SpecRegistryUpdate(**data))
        if updated is None:
            raise ValueError("spec not found")
        return {"kind": "spec", "id": updated.spec_id, "action": "updated"}

    raise ValueError(f"unsupported request_type: {request_type}")


def list_change_requests(limit: int = 200) -> list[ChangeRequest]:
    ensure_schema()
    with _session() as session:
        rows = (
            session.query(ChangeRequestRecord)
            .order_by(ChangeRequestRecord.updated_at.desc(), ChangeRequestRecord.created_at.desc())
            .limit(max(1, min(limit, 1000)))
            .all()
        )
        out: list[ChangeRequest] = []
        for row in rows:
            votes = (
                session.query(ChangeRequestVoteRecord)
                .filter(ChangeRequestVoteRecord.change_request_id == row.id)
                .all()
            )
            out.append(_to_model(row, votes))
        return out


def get_change_request(change_request_id: str) -> ChangeRequest | None:
    ensure_schema()
    with _session() as session:
        row = session.get(ChangeRequestRecord, change_request_id)
        if row is None:
            return None
        votes = (
            session.query(ChangeRequestVoteRecord)
            .filter(ChangeRequestVoteRecord.change_request_id == row.id)
            .all()
        )
        return _to_model(row, votes)


def create_change_request(data: ChangeRequestCreate) -> ChangeRequest:
    ensure_schema()
    required_approvals = data.required_approvals or _default_required_approvals()
    request = ChangeRequest(
        request_type=data.request_type,
        title=data.title,
        payload=data.payload,
        proposer_id=data.proposer_id,
        proposer_type=data.proposer_type,
        required_approvals=required_approvals,
        auto_apply_on_approval=data.auto_apply_on_approval,
        status=ChangeRequestStatus.OPEN,
        approvals=0,
        rejections=0,
    )
    with _session() as session:
        row = ChangeRequestRecord(
            id=request.id,
            request_type=request.request_type.value,
            title=request.title,
            payload_json=json.dumps(request.payload),
            proposer_id=request.proposer_id,
            proposer_type=request.proposer_type.value,
            required_approvals=request.required_approvals,
            auto_apply_on_approval=request.auto_apply_on_approval,
            status=request.status.value,
            approvals=0,
            rejections=0,
            created_at=request.created_at,
            updated_at=request.updated_at,
        )
        session.add(row)
    return request


def _upsert_vote(session: Session, change_request_id: str, data: ChangeRequestVoteCreate) -> None:
    existing_vote = (
        session.query(ChangeRequestVoteRecord)
        .filter(
            ChangeRequestVoteRecord.change_request_id == change_request_id,
            ChangeRequestVoteRecord.voter_id == data.voter_id,
        )
        .one_or_none()
    )
    now = datetime.utcnow()
    if existing_vote is None:
        session.add(
            ChangeRequestVoteRecord(
                id=str(uuid4()),
                change_request_id=change_request_id,
                voter_id=data.voter_id,
                voter_type=data.voter_type.value,
                decision=data.decision.value,
                rationale=data.rationale,
                created_at=now,
            )
        )
        return
    existing_vote.decision = data.decision.value
    existing_vote.voter_type = data.voter_type.value
    existing_vote.rationale = data.rationale
    existing_vote.created_at = now
    session.add(existing_vote)


def _collect_vote_counts(
    session: Session,
    change_request_id: str,
) -> tuple[list[ChangeRequestVoteRecord], int, int]:
    votes = (
        session.query(ChangeRequestVoteRecord)
        .filter(ChangeRequestVoteRecord.change_request_id == change_request_id)
        .all()
    )
    approvals = sum(1 for vote in votes if vote.decision == VoteDecision.YES.value)
    rejections = sum(1 for vote in votes if vote.decision == VoteDecision.NO.value)
    return votes, approvals, rejections


def _next_status(required_approvals: int, approvals: int, rejections: int) -> ChangeRequestStatus:
    if rejections > 0:
        return ChangeRequestStatus.REJECTED
    if approvals >= required_approvals:
        return ChangeRequestStatus.APPROVED
    return ChangeRequestStatus.OPEN


def _apply_approved_change_request(change_request_id: str, request: ChangeRequest) -> ChangeRequest:
    result = None
    error = None
    try:
        result = _apply_change_request(request)
    except Exception as exc:  # pragma: no cover - surfaced through response payload
        error = str(exc)
    with _session() as session:
        row = session.get(ChangeRequestRecord, change_request_id)
        if row is None:
            return request
        if error is None:
            row.status = ChangeRequestStatus.APPLIED.value
            row.applied_result_json = json.dumps(result)
        else:
            row.applied_result_json = json.dumps({"error": error})
        row.updated_at = datetime.utcnow()
        session.add(row)
        session.flush()
        session.refresh(row)
        votes = (
            session.query(ChangeRequestVoteRecord)
            .filter(ChangeRequestVoteRecord.change_request_id == change_request_id)
            .all()
        )
        return _to_model(row, votes)


def cast_vote(change_request_id: str, data: ChangeRequestVoteCreate) -> ChangeRequest | None:
    ensure_schema()
    with _session() as session:
        row = session.get(ChangeRequestRecord, change_request_id)
        if row is None:
            return None

        _upsert_vote(session, change_request_id, data)
        session.flush()
        votes, approvals, rejections = _collect_vote_counts(session, change_request_id)
        row.approvals = approvals
        row.rejections = rejections
        row.status = _next_status(row.required_approvals, approvals, rejections).value
        row.updated_at = datetime.utcnow()
        session.add(row)
        session.flush()
        session.refresh(row)
        request = _to_model(row, votes)

    if request.status == ChangeRequestStatus.APPROVED and request.auto_apply_on_approval:
        return _apply_approved_change_request(change_request_id, request)

    return get_change_request(change_request_id)
