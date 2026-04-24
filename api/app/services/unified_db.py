"""Unified database — single source of truth for all Coherence Network persistence.

Spec 118: Replaces 4 separate SQLite DBs and 5 JSON stores with one DB.
All services import from here instead of managing their own connections.

Configuration:
  - api/config/api.json and ~/.coherence-network/config.json provide database.url.
  - Otherwise defaults to sqlite:///data/coherence.db (works out of the box).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.db.base import Base


# ---------------------------------------------------------------------------
# Engine / session management (single instance)
# ---------------------------------------------------------------------------

_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_LOCK = threading.Lock()
_SCHEMA_INITIALIZED: dict[str, bool] = {}


def _normalize_engine_cache() -> dict[str, Any]:
    """Repair the engine cache shape after tests or helpers clear it directly."""
    global _ENGINE_CACHE
    if not isinstance(_ENGINE_CACHE, dict):
        _ENGINE_CACHE = {}
    _ENGINE_CACHE.setdefault("url", "")
    _ENGINE_CACHE.setdefault("engine", None)
    _ENGINE_CACHE.setdefault("sessionmaker", None)
    return _ENGINE_CACHE


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_sqlite_path() -> Path:
    return _repo_root() / "data" / "coherence.db"


def database_url() -> str:
    """Single source for the database URL.

    Priority:
      1. api/config/api.json → database.url
      2. ~/.coherence-network/config.json overlay
      3. sqlite:///data/coherence.db (default)
    """
    try:
        from app.config_loader import database_url as configured_database_url

        return configured_database_url().strip()
    except ImportError:
        sqlite_path = _default_sqlite_path()
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+pysqlite:///{sqlite_path}"



def _create_engine(url: str):
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = NullPool
    eng = create_engine(url, **kwargs)
    # Enable WAL mode for SQLite — better concurrent read/write performance
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    return eng


def _create_all_idempotent(*, bind, url: str) -> None:
    try:
        Base.metadata.create_all(bind=bind, checkfirst=True)
    except OperationalError as exc:
        message = str(exc).lower()
        if url.startswith("sqlite") and "already exists" in message:
            # SQLite schema setup can race across separate connections during tests.
            return
        raise


def engine():
    """Get or create the shared engine."""
    cache = _normalize_engine_cache()
    url = database_url()
    if cache["engine"] is not None and cache["url"] == url:
        return cache["engine"]
    eng = _create_engine(url)
    session_factory = sessionmaker(
        bind=eng, autocommit=False, autoflush=False, expire_on_commit=False,
    )
    cache["url"] = url
    cache["engine"] = eng
    cache["sessionmaker"] = session_factory
    # Auto-create tables on new engine (safe: checkfirst=True)
    try:
        from app.services import unified_models  # noqa: F401
        _create_all_idempotent(bind=eng, url=url)
        _SCHEMA_INITIALIZED[url] = True
    except Exception:
        pass
    return eng


def get_sessionmaker() -> sessionmaker:
    """Get the shared session factory."""
    engine()
    return _normalize_engine_cache()["sessionmaker"]


@contextmanager
def session() -> Generator[Session, None, None]:
    """Context manager for a database session. Auto-commits on success, rolls back on error."""
    factory = get_sessionmaker()
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def ensure_schema() -> None:
    """Create all registered tables if they don't exist."""
    # Import unified_models to ensure all table definitions are registered
    try:
        from app.services import unified_models  # noqa: F401
    except ImportError:
        pass
    eng = engine()
    url = database_url()
    with _SCHEMA_LOCK:
        if _SCHEMA_INITIALIZED.get(url):
            return
        _create_all_idempotent(bind=eng, url=url)
        _SCHEMA_INITIALIZED[url] = True


def reset_engine() -> None:
    """Reset the engine cache. Useful for tests that switch databases."""
    cache = _normalize_engine_cache()
    if cache["engine"] is not None:
        try:
            cache["engine"].dispose()
        except Exception:
            pass
    cache["url"] = ""
    cache["engine"] = None
    cache["sessionmaker"] = None
    _SCHEMA_INITIALIZED.clear()
