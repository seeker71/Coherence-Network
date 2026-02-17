"""DB-backed commit evidence registry and file import utilities."""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


class CommitEvidenceRecord(Base):
    __tablename__ = "commit_evidence_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    sha256: Mapped[str] = mapped_column(String, nullable=False, index=True)
    commit_scope: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date_value: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_sqlite_path() -> Path:
    return _repo_root() / "api" / "logs" / "commit_evidence_registry.db"


def _database_url() -> str:
    configured = os.getenv("COMMIT_EVIDENCE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if configured:
        return str(configured).strip()
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
    engine = _engine()
    Base.metadata.create_all(bind=engine)


def backend_info() -> dict[str, Any]:
    ensure_schema()
    url = _database_url()
    backend = "postgresql" if "postgres" in url.lower() else "sqlite"
    with _session() as session:
        rows = int(session.query(func.count(CommitEvidenceRecord.id)).scalar() or 0)
    return {
        "backend": backend,
        "database_url": _redact_database_url(url),
        "rows": rows,
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


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.pop("_evidence_file", None)
    return out


def upsert_record(payload: dict[str, Any], *, source_file: str) -> bool:
    """Upsert one record. Returns True when insert/update happened."""
    ensure_schema()
    normalized = _normalize_payload(payload)
    serialized = json.dumps(normalized, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    commit_scope = str(normalized.get("commit_scope") or "")
    date_value = str(normalized.get("date") or "") or None
    source_key = str(source_file).strip()
    if not source_key:
        source_key = f"sha256:{digest}"

    with _session() as session:
        row = session.query(CommitEvidenceRecord).filter_by(source_file=source_key).first()
        if row is not None and row.sha256 == digest:
            return False
        if row is None:
            row = CommitEvidenceRecord(
                source_file=source_key,
                sha256=digest,
                commit_scope=commit_scope,
                date_value=date_value,
                payload_json=serialized,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(row)
            return True
        row.sha256 = digest
        row.commit_scope = commit_scope
        row.date_value = date_value
        row.payload_json = serialized
        row.updated_at = datetime.utcnow()
        session.add(row)
        return True


def import_from_dir(evidence_dir: Path, limit: int = 3000) -> dict[str, int]:
    ensure_schema()
    if not evidence_dir.exists():
        return {"imported": 0, "skipped": 0}

    files = sorted(evidence_dir.glob("commit_evidence_*.json"))[: max(1, min(limit, 10000))]
    imported = 0
    skipped = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            skipped += 1
            continue
        if not isinstance(payload, dict):
            skipped += 1
            continue
        changed = upsert_record(payload, source_file=str(path))
        if changed:
            imported += 1
    return {"imported": imported, "skipped": skipped}


def list_records(limit: int = 400) -> list[dict[str, Any]]:
    ensure_schema()
    with _session() as session:
        rows = (
            session.query(CommitEvidenceRecord)
            .order_by(CommitEvidenceRecord.updated_at.desc(), CommitEvidenceRecord.id.desc())
            .limit(max(1, min(limit, 5000)))
            .all()
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json)
        except ValueError:
            continue
        if isinstance(payload, dict):
            payload["_evidence_file"] = row.source_file
            out.append(payload)
    return out


def tracked_idea_ids(limit: int = 1200) -> list[str]:
    ids: set[str] = set()
    for row in list_records(limit=limit):
        raw = row.get("idea_ids")
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, str) and item.strip():
                ids.add(item.strip())
    return sorted(ids)
