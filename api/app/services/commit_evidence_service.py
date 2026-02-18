"""Persistence service for commit evidence records."""

from __future__ import annotations

import json
import os
import time
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
    __tablename__ = "commit_evidence_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_file: Mapped[str] = mapped_column(String, nullable=False, default="", index=True)
    record_fingerprint: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_INITIALIZED = False
_LIST_RECORDS_CACHE: dict[str, Any] = {
    "expires_at": 0.0,
    "items": [],
}
_LIST_RECORDS_CACHE_TTL_SECONDS = 30.0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_sqlite_path() -> Path:
    return _repo_root() / "api" / "logs" / "commit_evidence_store.db"


def database_url() -> str:
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
    url = database_url()
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
    global _SCHEMA_INITIALIZED
    if _SCHEMA_INITIALIZED:
        return
    engine = _engine()
    Base.metadata.create_all(bind=engine)
    _SCHEMA_INITIALIZED = True


def _invalidate_record_cache() -> None:
    _LIST_RECORDS_CACHE["expires_at"] = 0.0
    _LIST_RECORDS_CACHE["items"] = []


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


def backend_info() -> dict[str, Any]:
    ensure_schema()
    url = database_url()
    backend = "postgresql" if "postgres" in url else "sqlite"
    with _session() as session:
        rows = int(session.query(func.count(CommitEvidenceRecord.id)).scalar() or 0)
    return {
        "backend": backend,
        "database_url": _redact_database_url(url),
        "record_rows": rows,
    }


def _fingerprint_from_payload(payload: dict[str, Any], source_file: str) -> str:
    digest_source = {
        "source_file": source_file,
        "date": payload.get("date"),
        "thread_branch": payload.get("thread_branch"),
        "commit_scope": payload.get("commit_scope"),
        "idea_ids": payload.get("idea_ids"),
        "spec_ids": payload.get("spec_ids"),
        "task_ids": payload.get("task_ids"),
        "change_files": payload.get("change_files"),
    }
    return json.dumps(digest_source, sort_keys=True, default=str)


def upsert_record(payload: dict[str, Any], source_file: str = "") -> None:
    if not isinstance(payload, dict):
        return
    ensure_schema()
    normalized_source = str(source_file or payload.get("_evidence_file") or "").strip()
    fingerprint = _fingerprint_from_payload(payload, normalized_source)
    body = dict(payload)
    body["_evidence_file"] = normalized_source
    serialized = json.dumps(body, default=str, sort_keys=True)
    now = datetime.utcnow()
    with _session() as session:
        row = (
            session.query(CommitEvidenceRecord)
            .filter(CommitEvidenceRecord.record_fingerprint == fingerprint)
            .first()
        )
        if row is None:
            session.add(
                CommitEvidenceRecord(
                    source_file=normalized_source,
                    record_fingerprint=fingerprint,
                    payload_json=serialized,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            row.source_file = normalized_source
            row.payload_json = serialized
            row.updated_at = now
            session.add(row)
    _invalidate_record_cache()


def bulk_upsert(records: list[dict[str, Any]]) -> int:
    imported = 0
    for row in records:
        if not isinstance(row, dict):
            continue
        upsert_record(row, str(row.get("_evidence_file") or ""))
        imported += 1
    _invalidate_record_cache()
    return imported


def list_records(limit: int = 400) -> list[dict[str, Any]]:
    now = time.time()
    requested_limit = max(1, min(int(limit), 5000))
    cached_until = _LIST_RECORDS_CACHE.get("expires_at", 0.0)
    cached_items = _LIST_RECORDS_CACHE.get("items", [])
    if cached_until > now and cached_items:
        return cached_items[:requested_limit]

    ensure_schema()
    with _session() as session:
        rows = (
            session.query(CommitEvidenceRecord)
            .order_by(CommitEvidenceRecord.updated_at.desc(), CommitEvidenceRecord.id.desc())
            .limit(requested_limit)
            .all()
        )
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payload["_evidence_file"] = str(payload.get("_evidence_file") or row.source_file or "")
            out.append(payload)
    _LIST_RECORDS_CACHE["expires_at"] = now + _LIST_RECORDS_CACHE_TTL_SECONDS
    _LIST_RECORDS_CACHE["items"] = out
    return out
