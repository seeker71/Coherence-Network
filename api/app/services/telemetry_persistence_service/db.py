"""Database engine, session, and schema for telemetry persistence."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from .models import Base


_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_CACHE: dict[str, Any] = {"url": "", "initialized": False}
_SCHEMA_LOCK = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_sqlite_path() -> Path:
    return _repo_root() / "api" / "logs" / "telemetry_store.db"


def database_url() -> str:
    configured = os.getenv("TELEMETRY_DATABASE_URL") or os.getenv("DATABASE_URL")
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
    engine = _engine()
    url = database_url()
    with _SCHEMA_LOCK:
        if bool(_SCHEMA_CACHE.get("initialized")) and _SCHEMA_CACHE.get("url") == url:
            return
        Base.metadata.create_all(bind=engine, checkfirst=True)
        _SCHEMA_CACHE["url"] = url
        _SCHEMA_CACHE["initialized"] = True
