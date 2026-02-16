#!/usr/bin/env bash
# generate_ccn_backend.sh
# Generates the Coherence Contribution Network FastAPI backend files + tests,
# then verifies by compiling and running pytest.
set -euo pipefail

ROOT_DIR="$(pwd)"
API_DIR="${ROOT_DIR}/api"
APP_DIR="${API_DIR}/app"
MODELS_DIR="${APP_DIR}/models"
ROUTERS_DIR="${APP_DIR}/routers"
SERVICES_DIR="${APP_DIR}/services"
TESTS_DIR="${API_DIR}/tests"

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[INFO] $*"; }
ok() { echo "[OK] $*"; }

# --- Basic repo sanity checks ---
[ -d "${API_DIR}" ] || die "Expected ./api directory. Run this from your repo root."
[ -d "${APP_DIR}" ] || die "Expected ./api/app directory."
[ -f "${APP_DIR}/models/project.py" ] || die "Expected ./api/app/models/project.py to exist (existing project models)."

# --- Ensure package init files exist ---
mkdir -p "${MODELS_DIR}" "${ROUTERS_DIR}" "${SERVICES_DIR}" "${TESTS_DIR}"
touch "${APP_DIR}/__init__.py" "${MODELS_DIR}/__init__.py" "${ROUTERS_DIR}/__init__.py" "${SERVICES_DIR}/__init__.py"

# Helper to write a file atomically
write_file() {
  local path="$1"
  local tmp="${path}.tmp.$$"
  cat > "${tmp}"
  mkdir -p "$(dirname "${path}")"
  mv "${tmp}" "${path}"
}

# ------------------------------------------------------------------------------
# 1) Models
# ------------------------------------------------------------------------------

info "Writing models..."

write_file "${MODELS_DIR}/contributor.py" <<'PY'
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class ContributorType(str, Enum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"


class ContributorBase(BaseModel):
    type: ContributorType
    name: str
    email: EmailStr
    wallet_address: str | None = None
    hourly_rate: Decimal | None = None


class ContributorCreate(ContributorBase):
    pass


class Contributor(ContributorBase):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
PY

write_file "${MODELS_DIR}/asset.py" <<'PY'
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    CODE = "CODE"
    MODEL = "MODEL"
    CONTENT = "CONTENT"
    DATA = "DATA"


class AssetBase(BaseModel):
    type: AssetType
    description: str


class AssetCreate(AssetBase):
    pass


class Asset(AssetBase):
    id: UUID = Field(default_factory=uuid4)
    total_cost: Decimal = Decimal("0.00")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
PY

write_file "${MODELS_DIR}/contribution.py" <<'PY'
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ContributionBase(BaseModel):
    contributor_id: UUID
    asset_id: UUID
    cost_amount: Decimal
    metadata: dict = Field(default_factory=dict)


class ContributionCreate(ContributionBase):
    pass


class Contribution(ContributionBase):
    id: UUID = Field(default_factory=uuid4)
    coherence_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
PY

write_file "${MODELS_DIR}/distribution.py" <<'PY'
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Payout(BaseModel):
    contributor_id: UUID
    amount: Decimal


class DistributionCreate(BaseModel):
    asset_id: UUID
    value_amount: Decimal


class Distribution(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    asset_id: UUID
    value_amount: Decimal
    payouts: list[Payout]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
PY

write_file "${MODELS_DIR}/error.py" <<'PY'
from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    detail: str
PY

# ------------------------------------------------------------------------------
# 2) GraphStore update (overwrites api/app/adapters/graph_store.py)
#    NOTE: This replaces the file with a version that preserves your existing
#    project methods and adds the contribution-network methods.
# ------------------------------------------------------------------------------

info "Writing adapters/graph_store.py (adds contribution network methods)..."

write_file "${APP_DIR}/adapters/graph_store.py" <<'PY'
"""GraphStore abstraction + in-memory backend — extended for Coherence Contribution Network.

This version preserves the existing project/dependency API and adds:
- Contributors
- Assets
- Contributions

All money uses Decimal. Store is in-memory with optional JSON persistence.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Optional, Protocol
from uuid import UUID

from app.models.asset import Asset
from app.models.contribution import Contribution
from app.models.contributor import Contributor
from app.models.project import Project, ProjectSummary


def _key(ecosystem: str, name: str) -> tuple[str, str]:
    return (ecosystem.lower(), name.lower())


class GraphStore(Protocol):
    """Protocol for graph storage. Implementations: InMemoryGraphStore, future Neo4j."""

    # ---- existing project API ----
    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        ...

    def search(self, query: str, limit: int = 20) -> list[ProjectSummary]:
        ...

    def upsert_project(self, project: Project) -> None:
        ...

    def add_dependency(self, from_eco: str, from_name: str, to_eco: str, to_name: str) -> None:
        ...

    def count_projects(self) -> int:
        ...

    def count_dependents(self, ecosystem: str, name: str) -> int:
        """Count projects that depend on this one (reverse edges)."""
        ...

    # ---- contribution network API ----
    def get_contributor(self, contributor_id: UUID) -> Contributor | None:
        """Get contributor by ID."""
        ...

    def create_contributor(self, contributor: Contributor) -> Contributor:
        """Create new contributor."""
        ...

    def list_contributors(self, limit: int = 100) -> list[Contributor]:
        """List all contributors."""
        ...

    def get_asset(self, asset_id: UUID) -> Asset | None:
        """Get asset by ID."""
        ...

    def create_asset(self, asset: Asset) -> Asset:
        """Create new asset."""
        ...

    def list_assets(self, limit: int = 100) -> list[Asset]:
        """List all assets."""
        ...

    def create_contribution(
        self,
        contributor_id: UUID,
        asset_id: UUID,
        cost_amount: Decimal,
        coherence_score: float,
        metadata: dict,
    ) -> Contribution:
        """Record a contribution."""
        ...

    def get_contribution(self, contribution_id: UUID) -> Contribution | None:
        """Get contribution by ID."""
        ...

    def get_asset_contributions(self, asset_id: UUID) -> list[Contribution]:
        """Get all contributions to an asset."""
        ...

    def get_contributor_contributions(self, contributor_id: UUID) -> list[Contribution]:
        """Get all contributions by a contributor."""
        ...


class InMemoryGraphStore:
    """In-memory GraphStore. Optional JSON persistence for restart."""

    def __init__(self, persist_path: Optional[str] = None) -> None:
        # existing graph data
        self._projects: dict[tuple[str, str], Project] = {}
        self._edges: list[tuple[tuple[str, str], tuple[str, str]]] = []

        # contribution network data
        self._contributors: dict[UUID, Contributor] = {}
        self._assets: dict[UUID, Asset] = {}
        self._contributions: dict[UUID, Contribution] = {}

        self._persist_path = persist_path
        if persist_path and os.path.isfile(persist_path):
            self._load()

    def _load(self) -> None:
        if not self._persist_path:
            return
        try:
            with open(self._persist_path, encoding="utf-8") as f:
                data = json.load(f)

            # projects
            for p in data.get("projects", []):
                proj = Project(**p)
                self._projects[_key(proj.ecosystem, proj.name)] = proj
            for e in data.get("edges", []):
                if len(e) >= 2 and len(e[0]) >= 2 and len(e[1]) >= 2:
                    self._edges.append(((e[0][0], e[0][1]), (e[1][0], e[1][1])))
            self._recompute_dependency_counts()

            # contribution network
            for c in data.get("contributors", []):
                contrib = Contributor(**c)
                self._contributors[contrib.id] = contrib
            for a in data.get("assets", []):
                asset = Asset(**a)
                self._assets[asset.id] = asset
            for cn in data.get("contributions", []):
                contribn = Contribution(**cn)
                self._contributions[contribn.id] = contribn

        except (json.JSONDecodeError, IOError, KeyError, ValueError):
            pass

    def _recompute_dependency_counts(self) -> None:
        counts: dict[tuple[str, str], int] = {k: 0 for k in self._projects}
        for from_k, _to_k in self._edges:
            if from_k in counts:
                counts[from_k] += 1
        for k, proj in self._projects.items():
            proj.dependency_count = counts.get(k, 0)

    def save(self) -> None:
        """Persist to JSON if path set."""
        if not self._persist_path:
            return
        os.makedirs(os.path.dirname(self._persist_path) or ".", exist_ok=True)
        data = {
            "projects": [p.model_dump() for p in self._projects.values()],
            "edges": [[list(from_k), list(to_k)] for from_k, to_k in self._edges],
            "contributors": [c.model_dump() for c in self._contributors.values()],
            "assets": [a.model_dump() for a in self._assets.values()],
            "contributions": [c.model_dump() for c in self._contributions.values()],
        }
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=0)

    # ----------------------------
    # Existing project API
    # ----------------------------
    def get_project(self, ecosystem: str, name: str) -> Optional[Project]:
        return self._projects.get(_key(ecosystem, name))

    def search(self, query: str, limit: int = 20) -> list[ProjectSummary]:
        q = (query or "").strip().lower()
        if not q:
            return []
        out: list[ProjectSummary] = []
        for proj in self._projects.values():
            if q in proj.name.lower() or q in (proj.description or "").lower():
                out.append(
                    ProjectSummary(
                        name=proj.name,
                        ecosystem=proj.ecosystem,
                        description=proj.description or "",
                    )
                )
                if len(out) >= limit:
                    break
        return out

    def upsert_project(self, project: Project) -> None:
        self._projects[_key(project.ecosystem, project.name)] = project
        self._recompute_dependency_counts()

    def add_dependency(self, from_eco: str, from_name: str, to_eco: str, to_name: str) -> None:
        from_k = _key(from_eco, from_name)
        to_k = _key(to_eco, to_name)
        edge = (from_k, to_k)
        if edge not in self._edges:
            self._edges.append(edge)
            self._recompute_dependency_counts()

    def count_projects(self) -> int:
        return len(self._projects)

    def count_dependents(self, ecosystem: str, name: str) -> int:
        target = _key(ecosystem, name)
        return sum(1 for _from_k, to_k in self._edges if to_k == target)

    # ----------------------------
    # Contribution network API
    # ----------------------------
    def get_contributor(self, contributor_id: UUID) -> Contributor | None:
        return self._contributors.get(contributor_id)

    def create_contributor(self, contributor: Contributor) -> Contributor:
        self._contributors[contributor.id] = contributor
        return contributor

    def list_contributors(self, limit: int = 100) -> list[Contributor]:
        items = sorted(self._contributors.values(), key=lambda c: c.created_at, reverse=True)
        return items[: max(0, int(limit))]

    def get_asset(self, asset_id: UUID) -> Asset | None:
        return self._assets.get(asset_id)

    def create_asset(self, asset: Asset) -> Asset:
        self._assets[asset.id] = asset
        return asset

    def list_assets(self, limit: int = 100) -> list[Asset]:
        items = sorted(self._assets.values(), key=lambda a: a.created_at, reverse=True)
        return items[: max(0, int(limit))]

    def create_contribution(
        self,
        contributor_id: UUID,
        asset_id: UUID,
        cost_amount: Decimal,
        coherence_score: float,
        metadata: dict,
    ) -> Contribution:
        contrib = Contribution(
            contributor_id=contributor_id,
            asset_id=asset_id,
            cost_amount=cost_amount,
            coherence_score=coherence_score,
            metadata=metadata or {},
        )
        self._contributions[contrib.id] = contrib

        asset = self._assets.get(asset_id)
        if asset:
            asset.total_cost = (asset.total_cost or Decimal("0.00")) + cost_amount

        return contrib

    def get_contribution(self, contribution_id: UUID) -> Contribution | None:
        return self._contributions.get(contribution_id)

    def get_asset_contributions(self, asset_id: UUID) -> list[Contribution]:
        out = [c for c in self._contributions.values() if c.asset_id == asset_id]
        out.sort(key=lambda c: c.timestamp)
        return out

    def get_contributor_contributions(self, contributor_id: UUID) -> list[Contribution]:
        out = [c for c in self._contributions.values() if c.contributor_id == contributor_id]
        out.sort(key=lambda c: c.timestamp)
        return out
PY

# ------------------------------------------------------------------------------
# 3) Routers
# ------------------------------------------------------------------------------

info "Writing routers..."

write_file "${ROUTERS_DIR}/contributors.py" <<'PY'
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.contributor import Contributor, ContributorCreate
from app.models.error import ErrorDetail

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post("/contributors", response_model=Contributor, status_code=201)
async def create_contributor(contributor: ContributorCreate, store: GraphStore = Depends(get_store)) -> Contributor:
    """Create a new contributor."""
    contrib = Contributor(**contributor.dict())
    return store.create_contributor(contrib)


@router.get(
    "/contributors/{contributor_id}",
    response_model=Contributor,
    responses={404: {"model": ErrorDetail}},
)
async def get_contributor(contributor_id: UUID, store: GraphStore = Depends(get_store)) -> Contributor:
    """Get contributor by ID."""
    contrib = store.get_contributor(contributor_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contributor not found")
    return contrib


@router.get("/contributors", response_model=list[Contributor])
async def list_contributors(limit: int = 100, store: GraphStore = Depends(get_store)) -> list[Contributor]:
    """List all contributors."""
    return store.list_contributors(limit=limit)
PY

write_file "${ROUTERS_DIR}/assets.py" <<'PY'
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.asset import Asset, AssetCreate
from app.models.error import ErrorDetail

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post("/assets", response_model=Asset, status_code=201)
async def create_asset(asset: AssetCreate, store: GraphStore = Depends(get_store)) -> Asset:
    """Create a new asset."""
    asset_obj = Asset(**asset.dict())
    return store.create_asset(asset_obj)


@router.get(
    "/assets/{asset_id}",
    response_model=Asset,
    responses={404: {"model": ErrorDetail}},
)
async def get_asset(asset_id: UUID, store: GraphStore = Depends(get_store)) -> Asset:
    """Get asset by ID."""
    asset = store.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/assets", response_model=list[Asset])
async def list_assets(limit: int = 100, store: GraphStore = Depends(get_store)) -> list[Asset]:
    """List all assets."""
    return store.list_assets(limit=limit)
PY

write_file "${ROUTERS_DIR}/contributions.py" <<'PY'
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.contribution import Contribution, ContributionCreate
from app.models.error import ErrorDetail

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


def calculate_coherence(contribution: ContributionCreate, store: GraphStore) -> float:
    """Calculate basic coherence score."""
    score = 0.5  # Baseline

    if contribution.metadata.get("has_tests"):
        score += 0.2

    if contribution.metadata.get("has_docs"):
        score += 0.2

    if contribution.metadata.get("complexity", "medium") == "low":
        score += 0.1

    return min(score, 1.0)


@router.post("/contributions", response_model=Contribution, status_code=201)
async def create_contribution(contribution: ContributionCreate, store: GraphStore = Depends(get_store)) -> Contribution:
    """Record a new contribution."""
    if not store.get_contributor(contribution.contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")

    if not store.get_asset(contribution.asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")

    coherence = calculate_coherence(contribution, store)

    return store.create_contribution(
        contributor_id=contribution.contributor_id,
        asset_id=contribution.asset_id,
        cost_amount=contribution.cost_amount,
        coherence_score=coherence,
        metadata=contribution.metadata,
    )


@router.get(
    "/contributions/{contribution_id}",
    response_model=Contribution,
    responses={404: {"model": ErrorDetail}},
)
async def get_contribution(contribution_id: UUID, store: GraphStore = Depends(get_store)) -> Contribution:
    """Get contribution by ID."""
    contrib = store.get_contribution(contribution_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return contrib


@router.get("/assets/{asset_id}/contributions", response_model=list[Contribution])
async def get_asset_contributions(asset_id: UUID, store: GraphStore = Depends(get_store)) -> list[Contribution]:
    """Get all contributions to an asset."""
    if not store.get_asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return store.get_asset_contributions(asset_id)


@router.get("/contributors/{contributor_id}/contributions", response_model=list[Contribution])
async def get_contributor_contributions(
    contributor_id: UUID, store: GraphStore = Depends(get_store)
) -> list[Contribution]:
    """Get all contributions by a contributor."""
    if not store.get_contributor(contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")
    return store.get_contributor_contributions(contributor_id)
PY

write_file "${ROUTERS_DIR}/distributions.py" <<'PY'
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.distribution import Distribution, DistributionCreate
from app.models.error import ErrorDetail
from app.services.distribution_engine import DistributionEngine

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.post(
    "/distributions",
    response_model=Distribution,
    status_code=201,
    responses={404: {"model": ErrorDetail}},
)
async def create_distribution(distribution: DistributionCreate, store: GraphStore = Depends(get_store)) -> Distribution:
    """Trigger value distribution for an asset."""
    if not store.get_asset(distribution.asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")

    engine = DistributionEngine(store)
    return await engine.distribute(asset_id=distribution.asset_id, value_amount=distribution.value_amount)
PY

# ------------------------------------------------------------------------------
# 4) Distribution Engine
# ------------------------------------------------------------------------------

info "Writing services/distribution_engine.py..."

write_file "${SERVICES_DIR}/distribution_engine.py" <<'PY'
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.adapters.graph_store import GraphStore
from app.models.distribution import Distribution, Payout


class DistributionEngine:
    def __init__(self, store: GraphStore):
        self.store = store

    async def distribute(self, asset_id: UUID, value_amount: Decimal) -> Distribution:
        """Distribute value proportionally to contributors weighted by coherence."""
        contributions = self.store.get_asset_contributions(asset_id)

        if not contributions:
            return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=[])

        weighted_costs: dict[UUID, Decimal] = {}
        for contrib in contributions:
            weight = Decimal("0.5") + Decimal(str(contrib.coherence_score))
            weighted_cost = contrib.cost_amount * weight
            weighted_costs[contrib.contributor_id] = weighted_costs.get(contrib.contributor_id, Decimal("0.00")) + weighted_cost

        total_weighted = sum(weighted_costs.values(), Decimal("0.00"))
        if total_weighted == 0:
            return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=[])

        payouts: list[Payout] = []
        for contributor_id, weighted in weighted_costs.items():
            raw = (weighted / total_weighted) * value_amount
            amount = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            payouts.append(Payout(contributor_id=contributor_id, amount=amount))

        return Distribution(asset_id=asset_id, value_amount=value_amount, payouts=payouts)
PY

# ------------------------------------------------------------------------------
# 5) main.py (overwrites api/app/main.py)
# ------------------------------------------------------------------------------

info "Writing main.py (includes new routers)..."

write_file "${APP_DIR}/main.py" <<'PY'
from __future__ import annotations

from fastapi import FastAPI

from app.adapters.graph_store import InMemoryGraphStore
from app.routers import assets, contributions, contributors, distributions

app = FastAPI(title="Coherence Contribution Network API", version="1.0.0")

# Default in-memory store (tests can override app.state.graph_store per test)
app.state.graph_store = InMemoryGraphStore()

app.include_router(contributors.router, prefix="/api", tags=["contributors"])
app.include_router(assets.router, prefix="/api", tags=["assets"])
app.include_router(contributions.router, prefix="/api", tags=["contributions"])
app.include_router(distributions.router, prefix="/api", tags=["distributions"])
PY

# ------------------------------------------------------------------------------
# 6) Tests
# ------------------------------------------------------------------------------

info "Writing tests..."

write_file "${TESTS_DIR}/test_contributors.py" <<'PY'
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_create_get_list_contributors() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"},
        )
        assert resp.status_code == 201
        created = resp.json()
        cid = created["id"]

        resp2 = await client.get(f"/api/contributors/{cid}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == cid

        resp3 = await client.get("/api/contributors?limit=10")
        assert resp3.status_code == 200
        assert any(x["id"] == cid for x in resp3.json())


@pytest.mark.asyncio
async def test_get_contributor_404() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/contributors/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Contributor not found"


@pytest.mark.asyncio
async def test_create_contributor_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/contributors", json={"type": "HUMAN", "name": "NoEmail"})
        assert resp.status_code == 422
PY

write_file "${TESTS_DIR}/test_assets.py" <<'PY'
from __future__ import annotations

import pytest
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_create_get_list_assets() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/assets", json={"type": "CODE", "description": "Test asset"})
        assert resp.status_code == 201
        created = resp.json()
        aid = created["id"]

        resp2 = await client.get(f"/api/assets/{aid}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == aid

        resp3 = await client.get("/api/assets?limit=10")
        assert resp3.status_code == 200
        assert any(x["id"] == aid for x in resp3.json())

        # total_cost default
        got = await client.get(f"/api/assets/{aid}")
        assert Decimal(got.json()["total_cost"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_get_asset_404() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/assets/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Asset not found"


@pytest.mark.asyncio
async def test_create_asset_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/assets", json={"type": "CODE"})
        assert resp.status_code == 422
PY

write_file "${TESTS_DIR}/test_contributions.py" <<'PY'
from __future__ import annotations

import pytest
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_create_get_contribution_and_asset_rollup_cost() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_id = c.json()["id"]

        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        r = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "100.00",
                "metadata": {"has_tests": True, "has_docs": True},
            },
        )
        assert r.status_code == 201
        created = r.json()
        assert Decimal(created["cost_amount"]) == Decimal("100.00")
        assert abs(float(created["coherence_score"]) - 0.9) < 1e-9

        contrib_id = created["id"]

        g = await client.get(f"/api/contributions/{contrib_id}")
        assert g.status_code == 200
        assert g.json()["id"] == contrib_id

        asset = await client.get(f"/api/assets/{asset_id}")
        assert Decimal(asset.json()["total_cost"]) == Decimal("100.00")


@pytest.mark.asyncio
async def test_create_contribution_404s() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        r = await client.post(
            "/api/contributions",
            json={
                "contributor_id": "00000000-0000-0000-0000-000000000000",
                "asset_id": asset_id,
                "cost_amount": "10.00",
                "metadata": {},
            },
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Contributor not found"

        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_id = c.json()["id"]

        r2 = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": "00000000-0000-0000-0000-000000000000",
                "cost_amount": "10.00",
                "metadata": {},
            },
        )
        assert r2.status_code == 404
        assert r2.json()["detail"] == "Asset not found"


@pytest.mark.asyncio
async def test_get_asset_and_contributor_contributions() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_id = c.json()["id"]

        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "5.00",
                "metadata": {"complexity": "low"},
            },
        )

        ac = await client.get(f"/api/assets/{asset_id}/contributions")
        assert ac.status_code == 200
        assert len(ac.json()) == 1

        cc = await client.get(f"/api/contributors/{contributor_id}/contributions")
        assert cc.status_code == 200
        assert len(cc.json()) == 1


@pytest.mark.asyncio
async def test_create_contribution_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_id = c.json()["id"]
        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        r = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "not-a-number",
                "metadata": {},
            },
        )
        assert r.status_code == 422
PY

write_file "${TESTS_DIR}/test_distributions.py" <<'PY'
from __future__ import annotations

import pytest
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_distribution_weighted_by_coherence() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp1 = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        alice_id = resp1.json()["id"]

        resp2 = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Bob", "email": "bob@example.com"})
        bob_id = resp2.json()["id"]

        resp3 = await client.post("/api/assets", json={"type": "CODE", "description": "Test asset"})
        asset_id = resp3.json()["id"]

        await client.post(
            "/api/contributions",
            json={"contributor_id": alice_id, "asset_id": asset_id, "cost_amount": "100.00", "metadata": {"has_tests": True, "has_docs": True}},
        )
        await client.post(
            "/api/contributions",
            json={"contributor_id": bob_id, "asset_id": asset_id, "cost_amount": "100.00", "metadata": {}},
        )

        resp = await client.post("/api/distributions", json={"asset_id": asset_id, "value_amount": "1000.00"})
        assert resp.status_code == 201
        data = resp.json()

        payouts = {p["contributor_id"]: Decimal(p["amount"]) for p in data["payouts"]}
        assert abs(payouts[alice_id] - Decimal("583.33")) < Decimal("0.01")
        assert abs(payouts[bob_id] - Decimal("416.67")) < Decimal("0.01")


@pytest.mark.asyncio
async def test_distribution_asset_not_found_404() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/distributions", json={"asset_id": "00000000-0000-0000-0000-000000000000", "value_amount": "1.00"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Asset not found"


@pytest.mark.asyncio
async def test_distribution_no_contributions_returns_empty_payouts() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        a = await client.post("/api/assets", json={"type": "CODE", "description": "Empty asset"})
        asset_id = a.json()["id"]

        resp = await client.post("/api/distributions", json={"asset_id": asset_id, "value_amount": "10.00"})
        assert resp.status_code == 201
        assert resp.json()["payouts"] == []


@pytest.mark.asyncio
async def test_distribution_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/distributions", json={"asset_id": "00000000-0000-0000-0000-000000000000", "value_amount": "x"})
        assert resp.status_code == 422
PY

# ------------------------------------------------------------------------------
# Verification
# ------------------------------------------------------------------------------

info "Verifying files exist..."
required_files=(
  "${MODELS_DIR}/contributor.py"
  "${MODELS_DIR}/asset.py"
  "${MODELS_DIR}/contribution.py"
  "${MODELS_DIR}/distribution.py"
  "${MODELS_DIR}/error.py"
  "${APP_DIR}/adapters/graph_store.py"
  "${ROUTERS_DIR}/contributors.py"
  "${ROUTERS_DIR}/assets.py"
  "${ROUTERS_DIR}/contributions.py"
  "${ROUTERS_DIR}/distributions.py"
  "${SERVICES_DIR}/distribution_engine.py"
  "${APP_DIR}/main.py"
  "${TESTS_DIR}/test_contributors.py"
  "${TESTS_DIR}/test_assets.py"
  "${TESTS_DIR}/test_contributions.py"
  "${TESTS_DIR}/test_distributions.py"
)

for f in "${required_files[@]}"; do
  [ -f "$f" ] || die "Missing expected file: $f"
done
ok "All expected files are present."

info "Python import/compile check..."
(
  cd "${API_DIR}"
  python -m compileall -q app
)
ok "Compile check passed."

info "Running pytest..."
(
  cd "${API_DIR}"
  python -m pytest -q
)
ok "All tests passed."

echo
ok "Done. Generated CCN backend + verified successfully."
