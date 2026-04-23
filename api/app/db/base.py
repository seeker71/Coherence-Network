"""Shared SQLAlchemy declarative base for persistence models."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for Coherence Network ORM models."""

