"""Structured persistence for idea portfolio tracking."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text, create_engine, func
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    selectinload,
    sessionmaker,
)
from sqlalchemy.pool import NullPool

from app.models.idea import Idea, IdeaQuestion, IdeaStage, IdeaType, ManifestationStatus
from app.services.unified_db import Base


class IdeaRecord(Base):
    __tablename__ = "idea_registry_ideas"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    potential_value: Mapped[float] = mapped_column(Float, nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False)
    actual_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    resistance_risk: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    manifestation_status: Mapped[str] = mapped_column(String, nullable=False, default=ManifestationStatus.NONE.value)
    interfaces_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    idea_type: Mapped[str] = mapped_column(String, nullable=False, default="standalone")
    parent_idea_id: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    child_idea_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    stage: Mapped[str] = mapped_column(String, nullable=False, default="none", server_default="none")
    value_basis_json: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    questions: Mapped[list["IdeaQuestionRecord"]] = relationship(
        "IdeaQuestionRecord",
        back_populates="idea",
        cascade="all, delete-orphan",
    )


class IdeaQuestionRecord(Base):
    __tablename__ = "idea_registry_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idea_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("idea_registry_ideas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    value_to_whole: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_delta: Mapped[float | None] = mapped_column(Float, nullable=True)

    idea: Mapped[IdeaRecord] = relationship("IdeaRecord", back_populates="questions")


class RegistryMetaRecord(Base):
    __tablename__ = "idea_registry_meta"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")


from app.services import unified_db as _udb

_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_legacy_portfolio_path() -> Path:
    return _repo_root() / "api" / "logs" / "idea_portfolio.json"


def _legacy_portfolio_path() -> Path:
    configured = os.getenv("IDEA_PORTFOLIO_PATH")
    if configured:
        return Path(configured)
    return _default_legacy_portfolio_path()


def _database_url() -> str:
    return _udb.database_url()


def _engine():
    return _udb.engine()


def _sessionmaker():
    return _udb.get_sessionmaker()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


_STAGE_COLUMN_MIGRATED: dict[str, bool] = {}


def _migrate_add_stage_column() -> None:
    """Add the 'stage' column to idea_registry_ideas if it doesn't exist yet."""
    url = _udb.database_url()
    if _STAGE_COLUMN_MIGRATED.get(url):
        return
    try:
        with _session() as session:
            from sqlalchemy import text as _text, inspect as _inspect
            insp = _inspect(session.bind)
            columns = {c["name"] for c in insp.get_columns("idea_registry_ideas")}
            if "stage" not in columns:
                session.execute(_text(
                    "ALTER TABLE idea_registry_ideas ADD COLUMN stage VARCHAR NOT NULL DEFAULT 'none'"
                ))
    except Exception:
        pass  # Table may not exist yet; create_all will handle it
    _STAGE_COLUMN_MIGRATED[url] = True


def ensure_schema() -> None:
    _udb.ensure_schema()
    _migrate_add_stage_column()


def _load_interfaces(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, str) and x.strip()]


def load_ideas() -> list[Idea]:
    ensure_schema()
    with _session() as session:
        rows = (
            session.query(IdeaRecord)
            .options(selectinload(IdeaRecord.questions))
            .order_by(IdeaRecord.position.asc(), IdeaRecord.id.asc())
            .all()
        )
        out: list[Idea] = []
        for row in rows:
            questions = sorted(row.questions, key=lambda q: (q.position, q.id))
            # Parse idea_type safely
            try:
                idea_type = IdeaType(row.idea_type) if row.idea_type else IdeaType.STANDALONE
            except (ValueError, AttributeError):
                idea_type = IdeaType.STANDALONE

            # Parse child_idea_ids from JSON
            child_idea_ids: list[str] = []
            try:
                raw_children = json.loads(row.child_idea_ids_json or "[]")
                if isinstance(raw_children, list):
                    child_idea_ids = [x for x in raw_children if isinstance(x, str)]
            except (json.JSONDecodeError, AttributeError):
                pass

            # Parse value_basis from JSON
            value_basis: dict[str, str] | None = None
            try:
                if row.value_basis_json:
                    raw_vb = json.loads(row.value_basis_json)
                    if isinstance(raw_vb, dict):
                        value_basis = raw_vb
            except (json.JSONDecodeError, AttributeError):
                pass

            # Parse stage safely
            try:
                idea_stage = IdeaStage(getattr(row, "stage", "none") or "none")
            except (ValueError, AttributeError):
                idea_stage = IdeaStage.NONE

            out.append(
                Idea(
                    id=row.id,
                    name=row.name,
                    description=row.description,
                    potential_value=float(row.potential_value),
                    actual_value=float(row.actual_value),
                    estimated_cost=float(row.estimated_cost),
                    actual_cost=float(row.actual_cost),
                    resistance_risk=float(row.resistance_risk),
                    confidence=float(row.confidence),
                    manifestation_status=ManifestationStatus(row.manifestation_status),
                    stage=idea_stage,
                    interfaces=_load_interfaces(row.interfaces_json),
                    idea_type=idea_type,
                    parent_idea_id=getattr(row, "parent_idea_id", None),
                    child_idea_ids=child_idea_ids,
                    value_basis=value_basis,
                    open_questions=[
                        IdeaQuestion(
                            question=q.question,
                            value_to_whole=float(q.value_to_whole),
                            estimated_cost=float(q.estimated_cost),
                            answer=q.answer,
                            measured_delta=float(q.measured_delta) if q.measured_delta is not None else None,
                        )
                        for q in questions
                    ],
                )
            )
        return out


def _upsert_idea_in_session(session: Session, idea: Idea, position: int) -> None:
    """Upsert a single idea and its questions within an existing session."""
    existing = session.get(IdeaRecord, idea.id)
    if existing is not None:
        existing.position = position
        existing.name = idea.name
        existing.description = idea.description
        existing.potential_value = float(idea.potential_value)
        existing.actual_value = float(idea.actual_value)
        existing.estimated_cost = float(idea.estimated_cost)
        existing.actual_cost = float(idea.actual_cost)
        existing.resistance_risk = float(idea.resistance_risk)
        existing.confidence = float(idea.confidence)
        existing.manifestation_status = idea.manifestation_status.value
        existing.interfaces_json = json.dumps(idea.interfaces)
        existing.idea_type = idea.idea_type.value if idea.idea_type else "standalone"
        existing.parent_idea_id = idea.parent_idea_id
        existing.child_idea_ids_json = json.dumps(idea.child_idea_ids or [])
        existing.stage = idea.stage.value if idea.stage else "none"
        existing.value_basis_json = json.dumps(idea.value_basis) if idea.value_basis else None
    else:
        session.add(
            IdeaRecord(
                id=idea.id,
                position=position,
                name=idea.name,
                description=idea.description,
                potential_value=float(idea.potential_value),
                actual_value=float(idea.actual_value),
                estimated_cost=float(idea.estimated_cost),
                actual_cost=float(idea.actual_cost),
                resistance_risk=float(idea.resistance_risk),
                confidence=float(idea.confidence),
                manifestation_status=idea.manifestation_status.value,
                stage=idea.stage.value if idea.stage else "none",
                interfaces_json=json.dumps(idea.interfaces),
                idea_type=idea.idea_type.value if idea.idea_type else "standalone",
                parent_idea_id=idea.parent_idea_id,
                child_idea_ids_json=json.dumps(idea.child_idea_ids or []),
                value_basis_json=json.dumps(idea.value_basis) if idea.value_basis else None,
            )
        )

    # Upsert questions: delete existing, re-insert deduped list
    session.query(IdeaQuestionRecord).filter(
        IdeaQuestionRecord.idea_id == idea.id
    ).delete()

    seen_questions: set[str] = set()
    for q_position, question in enumerate(idea.open_questions):
        key = question.question.strip().lower()
        if not key or key in seen_questions:
            continue
        seen_questions.add(key)
        session.add(
            IdeaQuestionRecord(
                idea_id=idea.id,
                position=q_position,
                question=question.question,
                value_to_whole=float(question.value_to_whole),
                estimated_cost=float(question.estimated_cost),
                answer=question.answer,
                measured_delta=(
                    float(question.measured_delta)
                    if question.measured_delta is not None
                    else None
                ),
            )
        )


def save_single_idea(idea: Idea, position: int = 0) -> None:
    """Upsert a single idea and its questions."""
    ensure_schema()
    with _session() as session:
        _upsert_idea_in_session(session, idea, position)


def save_ideas(ideas: list[Idea], bootstrap_source: str | None = None) -> None:
    ensure_schema()
    with _session() as session:
        incoming_ids = {idea.id for idea in ideas}

        # Delete ideas no longer in the list
        existing_ids_rows = session.query(IdeaRecord.id).all()
        stale_ids = {row[0] for row in existing_ids_rows} - incoming_ids
        if stale_ids:
            session.query(IdeaQuestionRecord).filter(
                IdeaQuestionRecord.idea_id.in_(stale_ids)
            ).delete(synchronize_session=False)
            session.query(IdeaRecord).filter(
                IdeaRecord.id.in_(stale_ids)
            ).delete(synchronize_session=False)

        # Upsert each idea
        for position, idea in enumerate(ideas):
            _upsert_idea_in_session(session, idea, position)

        if bootstrap_source is not None:
            row = session.get(RegistryMetaRecord, "bootstrap_source")
            if row is None:
                session.add(RegistryMetaRecord(key="bootstrap_source", value=bootstrap_source))
            else:
                row.value = bootstrap_source


def _meta_value(session: Session, key: str, default: str = "") -> str:
    row = session.get(RegistryMetaRecord, key)
    if row is None or not row.value:
        return default
    return row.value


def storage_info() -> dict[str, Any]:
    ensure_schema()
    url = _database_url()
    with _session() as session:
        idea_count = int(session.query(func.count(IdeaRecord.id)).scalar() or 0)
        question_count = int(session.query(func.count(IdeaQuestionRecord.id)).scalar() or 0)
        bootstrap_source = _meta_value(session, "bootstrap_source", default="unknown")

    backend = "postgresql" if "postgres" in url else "sqlite"
    return {
        "backend": backend,
        "database_url": _redact_database_url(url),
        "idea_count": idea_count,
        "question_count": question_count,
        "bootstrap_source": bootstrap_source,
    }


def _redact_database_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, remainder = url.split("://", 1)
    if "@" not in remainder:
        return url
    credentials, host = remainder.split("@", 1)
    if ":" in credentials:
        user = credentials.split(":", 1)[0]
        credentials = f"{user}:***"
    else:
        credentials = "***"
    return f"{scheme}://{credentials}@{host}"
