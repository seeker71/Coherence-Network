"""Unified database — single source of truth for all Coherence Network persistence.

Spec 118: Replaces 4 separate SQLite DBs and 5 JSON stores with one DB.
All services import from here instead of managing their own connections.

Configuration:
  - DATABASE_URL env var overrides for production (e.g. PostgreSQL).
  - Otherwise defaults to sqlite:///data/coherence.db (works out of the box).
  - IDEA_PORTFOLIO_PATH is honored for test isolation (derives .db path from it).
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    """Shared declarative base for ALL Coherence Network ORM models."""
    pass


# ---------------------------------------------------------------------------
# Engine / session management (single instance)
# ---------------------------------------------------------------------------

_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_LOCK = threading.Lock()
_SCHEMA_INITIALIZED: dict[str, bool] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_sqlite_path() -> Path:
    return _repo_root() / "data" / "coherence.db"


def database_url() -> str:
    """Single source for the database URL.

    Priority:
      1. api/config/api.json → database.url
      2. DATABASE_URL env var (legacy — Docker/CI override)
      3. IDEA_PORTFOLIO_PATH → derived .db path (test isolation)
      4. sqlite:///data/coherence.db (default)
    """
    # Config file first
    try:
        from app.config_loader import api_config
        config_url = api_config("database", "url")
        if config_url and config_url != "sqlite:///data/coherence.db":
            return str(config_url).strip()
    except ImportError:
        pass

    # Legacy env var (Docker/CI)
    configured = os.getenv("DATABASE_URL")
    if configured:
        return str(configured).strip()
    # Test isolation via IDEA_PORTFOLIO_PATH
    portfolio_path = os.getenv("IDEA_PORTFOLIO_PATH")
    if portfolio_path:
        p = Path(portfolio_path)
        sqlite_path = p.with_suffix(".db") if p.suffix.lower() == ".json" else Path(f"{p}.db")
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+pysqlite:///{sqlite_path}"
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


def engine():
    """Get or create the shared engine."""
    url = database_url()
    if _ENGINE_CACHE["engine"] is not None and _ENGINE_CACHE["url"] == url:
        return _ENGINE_CACHE["engine"]
    eng = _create_engine(url)
    session_factory = sessionmaker(
        bind=eng, autocommit=False, autoflush=False, expire_on_commit=False,
    )
    _ENGINE_CACHE["url"] = url
    _ENGINE_CACHE["engine"] = eng
    _ENGINE_CACHE["sessionmaker"] = session_factory
    # Auto-create tables on new engine (safe: checkfirst=True)
    try:
        from app.services import unified_models  # noqa: F401
        Base.metadata.create_all(bind=eng, checkfirst=True)
        _SCHEMA_INITIALIZED[url] = True
    except Exception:
        pass
    return eng


def get_sessionmaker() -> sessionmaker:
    """Get the shared session factory."""
    engine()
    return _ENGINE_CACHE["sessionmaker"]


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
        Base.metadata.create_all(bind=eng, checkfirst=True)
        _SCHEMA_INITIALIZED[url] = True


def reset_engine() -> None:
    """Reset the engine cache. Useful for tests that switch databases."""
    if _ENGINE_CACHE["engine"] is not None:
        try:
            _ENGINE_CACHE["engine"].dispose()
        except Exception:
            pass
    _ENGINE_CACHE["url"] = ""
    _ENGINE_CACHE["engine"] = None
    _ENGINE_CACHE["sessionmaker"] = None
    _SCHEMA_INITIALIZED.clear()
