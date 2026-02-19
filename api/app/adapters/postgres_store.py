"""PostgreSQL-backed GraphStore implementation for contribution tracking."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
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
from app.models.distribution import Distribution, Payout
from app.models.project import Project, ProjectSummary
from app.services.contributor_hygiene import is_test_contributor_email

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


class DistributionModel(Base):
    __tablename__ = "distributions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    asset_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    value_amount = Column(Numeric(precision=20, scale=2), nullable=False)
    payouts = Column(JSON, default=[])
    settlement_status = Column(String, nullable=False, default="pending", index=True)
    settled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)


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
        self._cache_ttl_seconds = 30.0
        self._cache = {
            "contributors": {"expires_at": 0.0, "items_by_limit": {}},
            "assets": {"expires_at": 0.0, "items_by_limit": {}},
            "contributions": {"expires_at": 0.0, "items_by_limit": {}},
            "distributions": {"expires_at": 0.0, "items_by_limit": {}},
        }
        self._ensure_tables()
        self._purge_test_contributors()

    def _cache_now(self) -> float:
        return time.time()

    def _read_cached_rows(
        self,
        kind: str,
        requested_limit: int,
        model_ctor,
    ) -> list | None:
        cache = self._cache.get(kind, {})
        if cache.get("expires_at", 0.0) <= self._cache_now():
            return None

        cached_maps = cache.get("items_by_limit", {})
        best_payload: list | None = None
        best_limit: int | None = None
        for raw_limit, payload in cached_maps.items():
            try:
                cached_limit = int(raw_limit)
            except (TypeError, ValueError):
                continue
            if cached_limit < requested_limit:
                continue
            if not isinstance(payload, list) or len(payload) < requested_limit:
                continue
            if best_limit is None or cached_limit < best_limit:
                best_payload = payload
                best_limit = cached_limit

        if best_payload is None:
            return None
        return [model_ctor(**row) for row in best_payload[:requested_limit]]

    def _write_cache_rows(self, kind: str, requested_limit: int, rows: list) -> None:
        cache = self._cache.setdefault(kind, {})
        serialized = [row.model_dump(mode="json") for row in rows]
        by_limit = cache.setdefault("items_by_limit", {})
        by_limit[requested_limit] = serialized
        cache["expires_at"] = self._cache_now() + self._cache_ttl_seconds

    def _invalidate_list_cache(self) -> None:
        for value in self._cache.values():
            value["expires_at"] = 0.0

    def _normalize_limit(self, kind: str, limit: int, max_limit: int) -> int:
        return max(1, min(int(limit), max_limit))

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)

    def _purge_test_contributors(self) -> int:
        """Remove test contributors and linked contributions from persistent storage."""
        with self._session() as session:
            test_ids = [
                row.id
                for row in session.query(ContributorModel.id, ContributorModel.email).all()
                if is_test_contributor_email(row.email)
            ]
            if not test_ids:
                return 0
            session.query(ContributionModel).filter(ContributionModel.contributor_id.in_(test_ids)).delete(
                synchronize_session=False
            )
            removed = (
                session.query(ContributorModel).filter(ContributorModel.id.in_(test_ids)).delete(synchronize_session=False)
            )
            self._invalidate_list_cache()
            return int(removed or 0)

    @contextmanager
    def _session(self):
        """Get a new database session with proper cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ---- Contribution network API ----

    def get_contributor(self, contributor_id: UUID) -> Contributor | None:
        with self._session() as session:
            model = session.query(ContributorModel).filter_by(id=contributor_id).first()
            if not model:
                return None
            if is_test_contributor_email(model.email):
                return None
            return Contributor(
                id=model.id,
                type=model.type,
                name=model.name,
                email=model.email,
                wallet_address=model.wallet_address,
                hourly_rate=Decimal(str(model.hourly_rate)) if model.hourly_rate else None,
                created_at=model.created_at,
            )

    def find_contributor_by_email(self, email: str) -> Contributor | None:
        """Find contributor by email address."""
        if is_test_contributor_email(email):
            return None
        with self._session() as session:
            model = session.query(ContributorModel).filter_by(email=email).first()
            if not model:
                return None
            if is_test_contributor_email(model.email):
                return None
            return Contributor(
                id=model.id,
                type=model.type,
                name=model.name,
                email=model.email,
                wallet_address=model.wallet_address,
                hourly_rate=Decimal(str(model.hourly_rate)) if model.hourly_rate else None,
                created_at=model.created_at,
            )

    def create_contributor(self, contributor: Contributor) -> Contributor:
        if is_test_contributor_email(str(contributor.email)):
            raise ValueError("test contributor emails are not allowed in persistent store")
        with self._session() as session:
            model = ContributorModel(
                id=contributor.id,
                type=contributor.type.value,
                name=contributor.name,
                email=contributor.email,
                wallet_address=contributor.wallet_address,
                hourly_rate=float(contributor.hourly_rate) if contributor.hourly_rate else None,
                created_at=contributor.created_at,
            )
            session.add(model)
            session.commit()
            self._invalidate_list_cache()
            return contributor

    def list_contributors(self, limit: int = 100) -> list[Contributor]:
        requested_limit = self._normalize_limit("contributors", limit, 1000)
        cached = self._read_cached_rows("contributors", requested_limit, Contributor)
        if cached is not None:
            return cached

        with self._session() as session:
            models = (
                session.query(ContributorModel)
                .order_by(ContributorModel.created_at.desc())
                .limit(requested_limit)
                .all()
            )
            items = [
                Contributor(
                    id=m.id,
                    type=m.type,
                    name=m.name,
                    email=m.email,
                    wallet_address=m.wallet_address,
                    hourly_rate=Decimal(str(m.hourly_rate)) if m.hourly_rate else None,
                    created_at=m.created_at,
                )
                for m in models
            ]
            items = [item for item in items if not is_test_contributor_email(str(item.email))]
            self._write_cache_rows("contributors", requested_limit, items)
            return items

    def get_asset(self, asset_id: UUID) -> Asset | None:
        with self._session() as session:
            model = session.query(AssetModel).filter_by(id=asset_id).first()
            if not model:
                return None
            return Asset(
                id=model.id,
                type=model.type,
                description=model.description,
                total_cost=Decimal(str(model.total_cost)) if model.total_cost else Decimal("0.00"),
                created_at=model.created_at,
            )

    def find_asset_by_name(self, name: str) -> Asset | None:
        """Find asset by canonical repository identity."""
        canonical_name = (name or "").strip()
        if not canonical_name:
            return None

        search_descriptions = [canonical_name]
        if not canonical_name.lower().startswith("github repository:"):
            search_descriptions.append(f"GitHub repository: {canonical_name}")

        with self._session() as session:
            model = (
                session.query(AssetModel)
                .filter(AssetModel.description.in_(search_descriptions))
                .order_by(AssetModel.created_at.asc())
                .first()
            )
            if not model:
                return None
            return Asset(
                id=model.id,
                type=model.type,
                description=model.description,
                total_cost=Decimal(str(model.total_cost)) if model.total_cost else Decimal("0.00"),
                created_at=model.created_at,
            )

    def create_asset(self, asset: Asset) -> Asset:
        with self._session() as session:
            model = AssetModel(
                id=asset.id,
                type=asset.type.value,
                description=asset.description,
                total_cost=float(asset.total_cost) if asset.total_cost else 0.0,
                created_at=asset.created_at,
            )
            session.add(model)
            session.commit()
            self._invalidate_list_cache()
            return asset

    def list_assets(self, limit: int = 100) -> list[Asset]:
        requested_limit = self._normalize_limit("assets", limit, 5000)
        cached = self._read_cached_rows("assets", requested_limit, Asset)
        if cached is not None:
            return cached

        with self._session() as session:
            models = session.query(AssetModel).order_by(AssetModel.created_at.desc()).limit(requested_limit).all()
            items = [
                Asset(
                    id=m.id,
                    type=m.type,
                    description=m.description,
                    total_cost=Decimal(str(m.total_cost)) if m.total_cost else Decimal("0.00"),
                    created_at=m.created_at,
                )
                for m in models
            ]
            self._write_cache_rows("assets", requested_limit, items)
            return items

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
            self._invalidate_list_cache()
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

    def list_contributions(self, limit: int = 100) -> list[Contribution]:
        requested_limit = self._normalize_limit("contributions", limit, 5000)
        cached = self._read_cached_rows("contributions", requested_limit, Contribution)
        if cached is not None:
            return cached

        with self._session() as session:
            models = (
                session.query(ContributionModel)
                .order_by(ContributionModel.timestamp.desc())
                .limit(requested_limit)
                .all()
            )
            out = [
                Contribution(
                    id=m.id,
                    contributor_id=m.contributor_id,
                    asset_id=m.asset_id,
                    cost_amount=Decimal(str(m.cost_amount)),
                    coherence_score=float(m.coherence_score),
                    timestamp=m.timestamp,
                    metadata=m.meta or {},
                )
                for m in models
            ]
            self._write_cache_rows("contributions", requested_limit, out)
            return out

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
                    metadata=m.meta or {},
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
                    metadata=m.meta or {},
                )
                for m in models
            ]

    def create_distribution(self, distribution: Distribution) -> Distribution:
        with self._session() as session:
            model = DistributionModel(
                id=distribution.id,
                asset_id=distribution.asset_id,
                value_amount=float(distribution.value_amount),
                payouts=[row.model_dump(mode="json") for row in distribution.payouts],
                settlement_status=distribution.settlement_status.value,
                settled_at=distribution.settled_at,
                created_at=distribution.created_at,
            )
            session.add(model)
            session.commit()
            self._invalidate_list_cache()
            return distribution

    def get_distribution(self, distribution_id: UUID) -> Distribution | None:
        with self._session() as session:
            model = session.query(DistributionModel).filter_by(id=distribution_id).first()
            if not model:
                return None
            return Distribution(
                id=model.id,
                asset_id=model.asset_id,
                value_amount=Decimal(str(model.value_amount)),
                payouts=[Payout(**row) for row in (model.payouts or [])],
                settlement_status=model.settlement_status,
                settled_at=model.settled_at,
                created_at=model.created_at,
            )

    def list_distributions(self, limit: int = 100) -> list[Distribution]:
        requested_limit = self._normalize_limit("distributions", limit, 5000)
        cached = self._read_cached_rows("distributions", requested_limit, Distribution)
        if cached is not None:
            return cached

        with self._session() as session:
            models = (
                session.query(DistributionModel)
                .order_by(DistributionModel.created_at.desc())
                .limit(requested_limit)
                .all()
            )
            items = [
                Distribution(
                    id=m.id,
                    asset_id=m.asset_id,
                    value_amount=Decimal(str(m.value_amount)),
                    payouts=[Payout(**row) for row in (m.payouts or [])],
                    settlement_status=m.settlement_status,
                    settled_at=m.settled_at,
                    created_at=m.created_at,
                )
                for m in models
            ]
            self._write_cache_rows("distributions", requested_limit, items)
            return items

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
