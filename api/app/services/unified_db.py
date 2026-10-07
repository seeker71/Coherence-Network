"""Unified database — single source of truth for all Coherence Network persistence.

Spec 118: Replaces 4 separate SQLite DBs and 5 JSON stores with one DB.
All services import from here instead of managing their own connections.

Configuration:
  - api/config/api.json and ~/.coherence-network/config.json provide database.url.
  - Otherwise defaults to sqlite:///data/coherence.db (works out of the box).
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError, TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.db.base import Base


# ---------------------------------------------------------------------------
# Engine / session management (single instance)
# ---------------------------------------------------------------------------

_ENGINE_CACHE: dict[str, Any] = {"url": "", "engine": None, "sessionmaker": None}
_SCHEMA_LOCK = threading.Lock()
_SCHEMA_INITIALIZED: dict[str, bool] = {}

POSTGRES_SUBSTRATE_UNIQUENESS_DDL = (
    "ALTER TABLE substrate_nodes "
    "DROP CONSTRAINT IF EXISTS uq_substrate_serialized",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_substrate_serialized_digest "
    "ON substrate_nodes (package, level, domain, md5(serialized))",
)
POSTGRES_SUBSTRATE_UNIQUENESS_STATE_SQL = """
SELECT
  EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'substrate_nodes'::regclass
      AND conname = 'uq_substrate_serialized'
  ) AS legacy_constraint,
  EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = current_schema()
      AND tablename = 'substrate_nodes'
      AND indexname = 'uq_substrate_serialized_digest'
  ) AS digest_index
"""


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



# Per-session Postgres GUCs (libpq startup `options`) that end the wedge class:
#   lock_timeout=5s                          — a lock-waiter fails, not hangs
#   idle_in_transaction_session_timeout=30s  — reap txns holding locks idle
#   statement_timeout=60s                    — generous runaway backstop
POSTGRES_STARTUP_OPTIONS = (
    "-c lock_timeout=5000"
    " -c idle_in_transaction_session_timeout=30000"
    " -c statement_timeout=60000"
)


def _create_engine(
    url: str,
    *,
    connect_timeout_seconds: int | None = None,
    sqlite_timeout_seconds: float | None = None,
    sqlite_deadline: float | None = None,
    isolated: bool = False,
):
    kwargs: dict[str, Any] = {"pool_pre_ping": not isolated}
    if url.startswith("sqlite"):
        sqlite_connect_args: dict[str, Any] = {"check_same_thread": False}
        if sqlite_timeout_seconds is not None:
            sqlite_connect_args["timeout"] = max(0.001, sqlite_timeout_seconds)
        kwargs["connect_args"] = sqlite_connect_args
        kwargs["poolclass"] = NullPool
    elif url.startswith("postgres"):
        # Stone: bound how long any statement waits on a lock or sits idle in a
        # transaction, so a hot-row write can NEVER wedge the whole write lane
        # for hours (as substrate_nodes.count did, 3x on 2026-07-02, each time
        # needing a manual pg_terminate_backend). A blocked writer now fails
        # fast and the app retries; a stuck-open transaction is reaped.
        connect_args: dict[str, Any] = {"options": POSTGRES_STARTUP_OPTIONS}
        if connect_timeout_seconds is not None:
            connect_args["connect_timeout"] = connect_timeout_seconds
        kwargs["connect_args"] = connect_args
        if isolated:
            # Deadline-scoped receipt writes never wait behind the shared
            # QueuePool. Their only acquisition is a directly bounded connect.
            kwargs["poolclass"] = NullPool
    eng = create_engine(url, **kwargs)
    # Enable WAL mode for SQLite — better concurrent read/write performance
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            try:
                if sqlite_deadline is not None:
                    remaining_ms = int(
                        (sqlite_deadline - time.monotonic()) * 1000
                    )
                    if remaining_ms <= 0:
                        raise SQLAlchemyTimeoutError(
                            "database deadline exhausted during SQLite connect"
                        )
                    # Install the absolute remaining budget before any PRAGMA
                    # that could contend on the database.  A deadline-scoped
                    # one-use connection consumes the existing journal mode;
                    # it never tries to mutate that shared mode while locked.
                    cursor.execute(f"PRAGMA busy_timeout={remaining_ms}")
                else:
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.execute("PRAGMA busy_timeout=5000")
            finally:
                cursor.close()
    return eng


def _create_deadline_engine(url: str, deadline: float):
    """Create an unpooled engine whose connection attempt fits the budget."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SQLAlchemyTimeoutError("database deadline exhausted before connect")
    connect_timeout_seconds: int | None = None
    sqlite_timeout_seconds: float | None = None
    if url.startswith("postgres"):
        # libpq accepts whole seconds, treats 0 as disabled, and enforces a
        # documented two-second minimum. Refuse a shorter window instead of
        # letting the driver silently extend the caller's absolute deadline.
        connect_timeout_seconds = int(remaining)
        if connect_timeout_seconds < 2:
            raise SQLAlchemyTimeoutError(
                "database deadline leaves no bounded PostgreSQL connect window"
            )
    elif url.startswith("sqlite"):
        sqlite_timeout_seconds = remaining
    return _create_engine(
        url,
        connect_timeout_seconds=connect_timeout_seconds,
        sqlite_timeout_seconds=sqlite_timeout_seconds,
        sqlite_deadline=deadline if url.startswith("sqlite") else None,
        isolated=True,
    )


def _apply_cursor_deadline(cursor, dialect_name: str, deadline: float) -> None:
    """Recompute one absolute budget before every ORM-emitted statement."""
    remaining_ms = int((deadline - time.monotonic()) * 1000)
    if remaining_ms <= 0:
        raise SQLAlchemyTimeoutError("database transaction deadline exhausted")
    if dialect_name == "postgresql":
        timeout_value = f"{remaining_ms}ms"
        cursor.execute(
            "SELECT "
            "set_config('statement_timeout', %s, true), "
            "set_config('lock_timeout', %s, true)",
            (timeout_value, timeout_value),
        )
    elif dialect_name == "sqlite":
        cursor.execute(f"PRAGMA busy_timeout = {remaining_ms}")


def _arm_connection_deadline(connection, deadline: float) -> threading.Timer:
    """Cancel the active DBAPI operation when the absolute budget expires."""
    raw_connection = connection.connection.driver_connection
    cancel = (
        getattr(raw_connection, "cancel", None)
        or getattr(raw_connection, "interrupt", None)
    )

    def cancel_active_operation() -> None:
        if cancel is None:
            cancel_completed = False
        else:
            finished = threading.Event()
            failed: list[bool] = []

            def request_cancel() -> None:
                try:
                    cancel()
                except Exception:
                    failed.append(True)
                finally:
                    finished.set()

            cancel_thread = threading.Thread(target=request_cancel, daemon=True)
            cancel_thread.start()
            cancel_completed = finished.wait(0.1) and not failed
        if not cancel_completed:
            # A failed or stalled cancel must not leave the receipt worker
            # attached to a dead socket. Closing the one-use connection forces
            # the active operation to release; the deadline session rolls back.
            try:
                raw_connection.close()
            except Exception:
                pass

    timer = threading.Timer(
        max(0.0, deadline - time.monotonic()),
        cancel_active_operation,
    )
    timer.daemon = True
    timer.start()
    return timer


@contextmanager
def deadline_session(deadline: float) -> Generator[Session, None, None]:
    """A one-transaction session bounded across connect, flush, and commit."""
    eng = _create_deadline_engine(database_url(), deadline)
    cancellation_timers: list[threading.Timer] = []

    @event.listens_for(eng, "before_cursor_execute")
    def _refresh_deadline(conn, cursor, statement, parameters, context, executemany):
        if "absolute_deadline_timer" not in conn.info:
            timer = _arm_connection_deadline(conn, deadline)
            conn.info["absolute_deadline_timer"] = timer
            cancellation_timers.append(timer)
        try:
            _apply_cursor_deadline(cursor, conn.dialect.name, deadline)
        except SQLAlchemyTimeoutError:
            raise
        except Exception as exc:
            raise SQLAlchemyTimeoutError(
                "database deadline could not be installed"
            ) from exc

    factory = sessionmaker(
        bind=eng,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    s = factory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        for timer in cancellation_timers:
            timer.cancel()
        s.close()
        eng.dispose()


def _create_all_idempotent(*, bind, url: str) -> None:
    try:
        Base.metadata.create_all(bind=bind, checkfirst=True)
    except OperationalError as exc:
        message = str(exc).lower()
        if url.startswith("sqlite") and "already exists" in message:
            # SQLite schema setup can race across separate connections during tests.
            return
        raise
    _repair_postgres_substrate_uniqueness(bind=bind, url=url)


def _repair_postgres_substrate_uniqueness(*, bind, url: str) -> None:
    """Lift unbounded serialized trees out of PostgreSQL's btree payload.

    Older deployments used the full serialized text in a UNIQUE constraint.
    PostgreSQL refuses values whose index row exceeds roughly one third of a
    page. A built-in md5 expression keeps the atomic interning backstop bounded;
    kernel lookups additionally compare the complete serialized text.
    """
    if not url.startswith("postgres"):
        return
    with bind.begin() as connection:
        state = connection.execute(
            text(POSTGRES_SUBSTRATE_UNIQUENESS_STATE_SQL)
        ).mappings().one()
        if state["legacy_constraint"]:
            connection.execute(text(POSTGRES_SUBSTRATE_UNIQUENESS_DDL[0]))
        if not state["digest_index"]:
            connection.execute(text(POSTGRES_SUBSTRATE_UNIQUENESS_DDL[1]))


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
        if url.startswith("postgres"):
            # The custom substrate migration is part of schema readiness, not
            # advisory startup work. Returning a cached engine here would let
            # the process serve with the oversized legacy UNIQUE constraint
            # still installed and would make every later engine() call skip
            # the migration. Clear the cache and fail startup so the supervisor
            # retries the complete schema gate.
            cache["url"] = None
            cache["engine"] = None
            cache["sessionmaker"] = None
            eng.dispose()
            raise
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
