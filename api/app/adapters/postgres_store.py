"""PostgreSQL-backed GraphStore implementation for contribution tracking."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import create_engine, Column, String, Numeric, DateTime, JSON, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime

from app.models.asset import Asset
from app.models.contribution import Contribution
from app.models.contributor import Contributor
from app.models.project import Project, ProjectSummary

Base = declarative_base()


class ContributorModel(Base):
    __tablename__ = "contributors"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False)
    meta = Column(JSON, default={})


class AssetModel(Base):
    __tablename__ = "assets"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    name = Column(String, nullable=False, index=True)
    asset_type = Column(String, nullable=False)
    total_cost = Column(Numeric(precision=20, scale=2), default=0)
    created_at = Column(DateTime, nullable=False)
    meta = Column(JSON, default={})


class ContributionModel(Base):
    __tablename__ = "contributions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    contributor_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    asset_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    cost_amount = Column(Numeric(precision=20, scale=2), nullable=False)
    coherence_score = Column(Numeric(precision=3, scale=2), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    meta = Column(JSON, default={})


class PostgresGraphStore:
    """PostgreSQL-backed GraphStore for contribution tracking.

    Note: This is a simplified implementation focused on contribution tracking.
    The project/dependency graph features are not yet implemented for PostgreSQL.
    """

    def __init__(self, database_url: str | None = None) -> None:
        if not database_url:
            database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL is required for PostgresGraphStore")

        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)

    def _session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    # ---- Contribution network API ----

    def get_contributor(self, contributor_id: UUID) -> Contributor | None:
        with self._session() as session:
            model = session.query(ContributorModel).filter_by(id=contributor_id).first()
            if not model:
                return None
            return Contributor(
                id=model.id,
                name=model.name,
                email=model.email,
                created_at=model.created_at,
                metadata=model.meta or {},
            )

    def find_contributor_by_email(self, email: str) -> Contributor | None:
        """Find contributor by email address."""
        with self._session() as session:
            model = session.query(ContributorModel).filter_by(email=email).first()
            if not model:
                return None
            return Contributor(
                id=model.id,
                name=model.name,
                email=model.email,
                created_at=model.created_at,
                metadata=model.meta or {},
            )

    def create_contributor(self, contributor: Contributor) -> Contributor:
        with self._session() as session:
            model = ContributorModel(
                id=contributor.id,
                name=contributor.name,
                email=contributor.email,
                created_at=contributor.created_at,
                meta=contributor.metadata or {},
            )
            session.add(model)
            session.commit()
            return contributor

    def list_contributors(self, limit: int = 100) -> list[Contributor]:
        with self._session() as session:
            models = (
                session.query(ContributorModel)
                .order_by(ContributorModel.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                Contributor(
                    id=m.id,
                    name=m.name,
                    email=m.email,
                    created_at=m.created_at,
                    metadata=m.metadata or {},
                )
                for m in models
            ]

    def get_asset(self, asset_id: UUID) -> Asset | None:
        with self._session() as session:
            model = session.query(AssetModel).filter_by(id=asset_id).first()
            if not model:
                return None
            return Asset(
                id=model.id,
                name=model.name,
                asset_type=model.asset_type,
                total_cost=Decimal(str(model.total_cost)) if model.total_cost else Decimal("0.00"),
                created_at=model.created_at,
                metadata=model.meta or {},
            )

    def find_asset_by_name(self, name: str) -> Asset | None:
        """Find asset by name."""
        with self._session() as session:
            model = session.query(AssetModel).filter_by(name=name).first()
            if not model:
                return None
            return Asset(
                id=model.id,
                name=model.name,
                asset_type=model.asset_type,
                total_cost=Decimal(str(model.total_cost)) if model.total_cost else Decimal("0.00"),
                created_at=model.created_at,
                metadata=model.meta or {},
            )

    def create_asset(self, asset: Asset) -> Asset:
        with self._session() as session:
            model = AssetModel(
                id=asset.id,
                name=asset.name,
                asset_type=asset.asset_type,
                total_cost=float(asset.total_cost) if asset.total_cost else 0.0,
                created_at=asset.created_at,
                meta=asset.metadata or {},
            )
            session.add(model)
            session.commit()
            return asset

    def list_assets(self, limit: int = 100) -> list[Asset]:
        with self._session() as session:
            models = session.query(AssetModel).order_by(AssetModel.created_at.desc()).limit(limit).all()
            return [
                Asset(
                    id=m.id,
                    name=m.name,
                    asset_type=m.asset_type,
                    total_cost=Decimal(str(m.total_cost)) if m.total_cost else Decimal("0.00"),
                    created_at=m.created_at,
                    metadata=m.metadata or {},
                )
                for m in models
            ]

    def create_contribution(
        self,
        contributor_id: UUID,
        asset_id: UUID,
        cost_amount: Decimal,
        coherence_score: float,
        metadata: dict,
    ) -> Contribution:
        with self._session() as session:
            contrib = Contribution(
                contributor_id=contributor_id,
                asset_id=asset_id,
                cost_amount=cost_amount,
                coherence_score=coherence_score,
                metadata=metadata or {},
            )

            model = ContributionModel(
                id=contrib.id,
                contributor_id=contrib.contributor_id,
                asset_id=contrib.asset_id,
                cost_amount=float(contrib.cost_amount),
                coherence_score=float(contrib.coherence_score),
                timestamp=contrib.timestamp,
                meta=contrib.metadata,
            )
            session.add(model)

            # Update asset total cost
            asset_model = session.query(AssetModel).filter_by(id=asset_id).first()
            if asset_model:
                current_cost = Decimal(str(asset_model.total_cost)) if asset_model.total_cost else Decimal("0.00")
                asset_model.total_cost = float(current_cost + cost_amount)

            session.commit()
            return contrib

    def get_contribution(self, contribution_id: UUID) -> Contribution | None:
        with self._session() as session:
            model = session.query(ContributionModel).filter_by(id=contribution_id).first()
            if not model:
                return None
            return Contribution(
                id=model.id,
                contributor_id=model.contributor_id,
                asset_id=model.asset_id,
                cost_amount=Decimal(str(model.cost_amount)),
                coherence_score=float(model.coherence_score),
                timestamp=model.timestamp,
                metadata=model.meta or {},
            )

    def get_asset_contributions(self, asset_id: UUID) -> list[Contribution]:
        with self._session() as session:
            models = (
                session.query(ContributionModel)
                .filter_by(asset_id=asset_id)
                .order_by(ContributionModel.timestamp)
                .all()
            )
            return [
                Contribution(
                    id=m.id,
                    contributor_id=m.contributor_id,
                    asset_id=m.asset_id,
                    cost_amount=Decimal(str(m.cost_amount)),
                    coherence_score=float(m.coherence_score),
                    timestamp=m.timestamp,
                    metadata=m.metadata or {},
                )
                for m in models
            ]

    def get_contributor_contributions(self, contributor_id: UUID) -> list[Contribution]:
        with self._session() as session:
            models = (
                session.query(ContributionModel)
                .filter_by(contributor_id=contributor_id)
                .order_by(ContributionModel.timestamp)
                .all()
            )
            return [
                Contribution(
                    id=m.id,
                    contributor_id=m.contributor_id,
                    asset_id=m.asset_id,
                    cost_amount=Decimal(str(m.cost_amount)),
                    coherence_score=float(m.coherence_score),
                    timestamp=m.timestamp,
                    metadata=m.metadata or {},
                )
                for m in models
            ]

    # ---- Project/dependency API (not yet implemented for PostgreSQL) ----

    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        """Not yet implemented for PostgreSQL."""
        return None

    def search(self, query: str, limit: int = 20) -> list[ProjectSummary]:
        """Not yet implemented for PostgreSQL."""
        return []

    def upsert_project(self, project: Project) -> None:
        """Not yet implemented for PostgreSQL."""
        pass

    def add_dependency(self, from_eco: str, from_name: str, to_eco: str, to_name: str) -> None:
        """Not yet implemented for PostgreSQL."""
        pass

    def count_projects(self) -> int:
        """Not yet implemented for PostgreSQL."""
        return 0

    def count_dependents(self, ecosystem: str, name: str) -> int:
        """Not yet implemented for PostgreSQL."""
        return 0
