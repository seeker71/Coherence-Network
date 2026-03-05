"""Database engine, schema, and session for agent run state."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.services.agent_run_state.models import AgentRunStateRecord, Base

_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_INITIALIZED = False
_SCHEMA_INITIALIZED_URL = ""


def _database_url() -> str:
    return (os.getenv("AGENT_RUN_STATE_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()


def _create_engine(url: str):
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = NullPool
    return create_engine(url, **kwargs)


def _table_exists(engine: Any, table_name: str) -> bool:
    try:
        return table_name in inspect(engine).get_table_names()
    except Exception:
        return False


def _engine():
    url = _database_url()
    if not url:
        return None
    if _ENGINE_CACHE["engine"] is not None and _ENGINE_CACHE["url"] == url:
        return _ENGINE_CACHE["engine"]
    global _SCHEMA_INITIALIZED, _SCHEMA_INITIALIZED_URL
    _SCHEMA_INITIALIZED = False
    _SCHEMA_INITIALIZED_URL = ""
    engine = _create_engine(url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    _ENGINE_CACHE["url"] = url
    _ENGINE_CACHE["engine"] = engine
    _ENGINE_CACHE["sessionmaker"] = SessionLocal
    return engine


def _ensure_schema() -> None:
    global _SCHEMA_INITIALIZED, _SCHEMA_INITIALIZED_URL
    url = _database_url()
    if _SCHEMA_INITIALIZED and _SCHEMA_INITIALIZED_URL == url:
        engine = _engine()
        if engine is not None and _table_exists(engine, "agent_run_state"):
            return
        _SCHEMA_INITIALIZED = False
        _SCHEMA_INITIALIZED_URL = ""
    engine = _engine()
    if engine is None or not url:
        return
    if not _table_exists(engine, "agent_run_state"):
        Base.metadata.create_all(bind=engine)
    _SCHEMA_INITIALIZED = True
    _SCHEMA_INITIALIZED_URL = url


@contextmanager
def _session() -> Session:
    SessionLocal = _ENGINE_CACHE.get("sessionmaker")
    if SessionLocal is None:
        _engine()
        SessionLocal = _ENGINE_CACHE.get("sessionmaker")
    if SessionLocal is None:
        raise RuntimeError("agent run state session unavailable")
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_database_url():
    """Return configured database URL (for service layer)."""
    return _database_url()
