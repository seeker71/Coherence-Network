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

from app.models.idea import Idea, IdeaQuestion, ManifestationStatus


class Base(DeclarativeBase):
    pass


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


def _default_sqlite_path() -> Path:
    legacy_path = _legacy_portfolio_path()
    if legacy_path.suffix.lower() == ".json":
        return legacy_path.with_suffix(".db")
    return Path(f"{legacy_path}.db")


def _database_url() -> str:
    configured = (
        os.getenv("IDEA_REGISTRY_DATABASE_URL")
        or os.getenv("IDEA_REGISTRY_DB_URL")
        or os.getenv("DATABASE_URL")
    )
    if configured:
        return configured
    sqlite_path = _default_sqlite_path()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{sqlite_path}"


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
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
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
    engine = _engine()
    Base.metadata.create_all(bind=engine)


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
                    interfaces=_load_interfaces(row.interfaces_json),
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


def save_ideas(ideas: list[Idea], bootstrap_source: str | None = None) -> None:
    ensure_schema()
    with _session() as session:
        session.query(IdeaQuestionRecord).delete()
        session.query(IdeaRecord).delete()

        for position, idea in enumerate(ideas):
            idea_row = IdeaRecord(
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
                interfaces_json=json.dumps(idea.interfaces),
            )
            session.add(idea_row)

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
