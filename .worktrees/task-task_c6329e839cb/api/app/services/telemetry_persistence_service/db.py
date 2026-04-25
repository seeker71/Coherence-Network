"""Database engine, session, and schema for telemetry persistence.

Delegates to unified_db for engine/session management.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.services import unified_db as _udb


def database_url() -> str:
    return _udb.database_url()


def _engine():
    return _udb.engine()


def _sessionmaker():
    return _udb.get_sessionmaker()


@contextmanager
def _session() -> Session:
    with _udb.session() as session:
        yield session


def ensure_schema() -> None:
    _udb.ensure_schema()
