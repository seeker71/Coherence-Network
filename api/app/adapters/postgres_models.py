"""SQLAlchemy ORM models for contribution tracking.

Uses the shared unified_db Base so tables are created alongside all other
models during schema initialization.  Column types are portable across
PostgreSQL and SQLite (String IDs instead of PG_UUID).
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, JSON, Numeric, String
from app.services.unified_db import Base


class ContributorModel(Base):
    __tablename__ = "contributors"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True, index=True)
    wallet_address = Column(String, nullable=True)
    hourly_rate = Column(Numeric(precision=10, scale=2), nullable=True)
    daily_cc_budget = Column(Numeric(precision=20, scale=2), nullable=True)
    monthly_cc_budget = Column(Numeric(precision=20, scale=2), nullable=True)
    created_at = Column(DateTime, nullable=False)


class AssetModel(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    description = Column(String, nullable=False, index=True)
    total_cost = Column(Numeric(precision=20, scale=2), default=0)
    created_at = Column(DateTime, nullable=False)


class ContributionModel(Base):
    __tablename__ = "contributions"

    id = Column(String, primary_key=True)
    contributor_id = Column(String, nullable=False, index=True)
    asset_id = Column(String, nullable=False, index=True)
    cost_amount = Column(Numeric(precision=20, scale=2), nullable=False)
    coherence_score = Column(Numeric(precision=3, scale=2), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    meta = Column(JSON, default={})
