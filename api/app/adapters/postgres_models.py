"""SQLAlchemy ORM models and declarative Base for PostgreSQL contribution tracking."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, JSON, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ContributorModel(Base):
    __tablename__ = "contributors"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    type = Column(String, nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True, index=True)
    wallet_address = Column(String, nullable=True)
    hourly_rate = Column(Numeric(precision=10, scale=2), nullable=True)
    created_at = Column(DateTime, nullable=False)


class AssetModel(Base):
    __tablename__ = "assets"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    type = Column(String, nullable=False)
    description = Column(String, nullable=False, index=True)
    total_cost = Column(Numeric(precision=20, scale=2), default=0)
    created_at = Column(DateTime, nullable=False)


class ContributionModel(Base):
    __tablename__ = "contributions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    contributor_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    asset_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    cost_amount = Column(Numeric(precision=20, scale=2), nullable=False)
    coherence_score = Column(Numeric(precision=3, scale=2), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    meta = Column(JSON, default={})
