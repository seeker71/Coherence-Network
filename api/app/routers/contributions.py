from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.adapters.graph_store import GraphStore
from app.models.asset import Asset, AssetType
from app.models.contribution import Contribution, ContributionCreate
from app.models.contributor import Contributor, ContributorType
from app.models.error import ErrorDetail

router = APIRouter()


class GitHubContribution(BaseModel):
    """GitHub webhook contribution payload."""

    contributor_email: str
    repository: str
    commit_hash: str
    cost_amount: Decimal
    metadata: dict = {}


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


@router.post(
    "/contributions",
    response_model=Contribution,
    status_code=201,
    summary="Record contribution with automatic coherence scoring",
    description="""
**Purpose**: Track contributor impact with automatic quality assessment for fair value distribution.

**Spec**: [048-contributions-api.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/048-contributions-api.md)
**Idea**: `coherence-network-value-attribution` - Enable transparent, quality-weighted contributor rewards
**Tests**: `api/tests/test_contributions.py::test_create_get_contribution_and_asset_rollup_cost`

**Coherence Scoring**:
- Baseline: 0.5
- +0.2 if `has_tests=true`
- +0.2 if `has_docs=true`
- +0.1 if `complexity="low"`
- Capped at 1.0

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (if changing rationale/value)
2. **Spec**: Update `/specs/048-contributions-api.md` (if changing API contract)
3. **Tests**: Update `/api/tests/test_contributions.py` (add/modify tests)
4. **Implementation**: Update `/api/app/routers/contributions.py` (this file)
5. **Validation**: Run `pytest api/tests/test_contributions.py -v`
    """,
    responses={
        201: {
            "description": "Contribution recorded with coherence score",
            "content": {
                "application/json": {
                    "example": {
                        "id": "770e8400-e29b-41d4-a716-446655440000",
                        "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
                        "asset_id": "660e8400-e29b-41d4-a716-446655440000",
                        "cost_amount": 150.00,
                        "coherence_score": 1.0,
                        "metadata": {
                            "has_tests": True,
                            "has_docs": True,
                            "complexity": "low"
                        },
                        "timestamp": "2026-02-15T10:30:00Z"
                    }
                }
            }
        },
        404: {"description": "Contributor or Asset not found"},
        422: {"description": "Validation error (missing required fields)"}
    },
    openapi_extra={
        "x-spec-file": "specs/048-contributions-api.md",
        "x-idea-id": "coherence-network-value-attribution",
        "x-test-file": "api/tests/test_contributions.py",
        "x-implementation-file": "api/app/routers/contributions.py",
        "x-coherence-formula": "0.5 + (0.2 * has_tests) + (0.2 * has_docs) + (0.1 * low_complexity)"
    }
)
async def create_contribution(contribution: ContributionCreate, store: GraphStore = Depends(get_store)) -> Contribution:
    """Record a new contribution with automatic coherence scoring."""
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
    summary="Retrieve contribution by ID",
    description="""
**Purpose**: Fetch a specific contribution record with coherence score and metadata.

**Spec**: [048-contributions-api.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/048-contributions-api.md)
**Idea**: `coherence-network-value-attribution`
**Tests**: `api/tests/test_contributions.py::test_create_get_contribution_and_asset_rollup_cost`

**Change Process**: See POST /contributions for full change process.
    """,
    responses={
        200: {
            "description": "Contribution found",
            "content": {
                "application/json": {
                    "example": {
                        "id": "770e8400-e29b-41d4-a716-446655440000",
                        "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
                        "asset_id": "660e8400-e29b-41d4-a716-446655440000",
                        "cost_amount": 150.00,
                        "coherence_score": 1.0,
                        "metadata": {},
                        "timestamp": "2026-02-15T10:30:00Z"
                    }
                }
            }
        },
        404: {"model": ErrorDetail, "description": "Contribution not found"}
    },
    openapi_extra={
        "x-spec-file": "specs/048-contributions-api.md",
        "x-idea-id": "coherence-network-value-attribution",
        "x-test-file": "api/tests/test_contributions.py"
    }
)
async def get_contribution(contribution_id: UUID, store: GraphStore = Depends(get_store)) -> Contribution:
    """Retrieve contribution by ID."""
    contrib = store.get_contribution(contribution_id)
    if not contrib:
        raise HTTPException(status_code=404, detail="Contribution not found")
    return contrib


@router.get(
    "/assets/{asset_id}/contributions",
    response_model=list[Contribution],
    summary="List all contributions to an asset",
    description="""
**Purpose**: Retrieve contribution history for an asset (used for rollup calculations and distribution).

**Spec**: [048-contributions-api.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/048-contributions-api.md)
**Idea**: `coherence-network-value-attribution`
**Tests**: `api/tests/test_contributions.py::test_get_asset_and_contributor_contributions`

**Use Case**: Calculate total weighted cost for distribution: sum(cost × (0.5 + coherence))

**Change Process**: See POST /contributions for full change process.
    """,
    responses={
        200: {
            "description": "List of contributions to asset (may be empty)",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "770e8400-e29b-41d4-a716-446655440000",
                            "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
                            "asset_id": "660e8400-e29b-41d4-a716-446655440000",
                            "cost_amount": 150.00,
                            "coherence_score": 1.0,
                            "metadata": {},
                            "timestamp": "2026-02-15T10:30:00Z"
                        }
                    ]
                }
            }
        },
        404: {"description": "Asset not found"}
    },
    openapi_extra={
        "x-spec-file": "specs/048-contributions-api.md",
        "x-idea-id": "coherence-network-value-attribution",
        "x-test-file": "api/tests/test_contributions.py"
    }
)
async def get_asset_contributions(asset_id: UUID, store: GraphStore = Depends(get_store)) -> list[Contribution]:
    """List all contributions to an asset."""
    if not store.get_asset(asset_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return store.get_asset_contributions(asset_id)


@router.get(
    "/contributors/{contributor_id}/contributions",
    response_model=list[Contribution],
    summary="List all contributions by a contributor",
    description="""
**Purpose**: Retrieve contribution history for a contributor (used for analytics and payout calculations).

**Spec**: [048-contributions-api.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/048-contributions-api.md)
**Idea**: `coherence-network-value-attribution`
**Tests**: `api/tests/test_contributions.py::test_get_asset_and_contributor_contributions`

**Use Case**: Show contributor impact across all assets, calculate average coherence score.

**Change Process**: See POST /contributions for full change process.
    """,
    responses={
        200: {
            "description": "List of contributions by contributor (may be empty)",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "770e8400-e29b-41d4-a716-446655440000",
                            "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
                            "asset_id": "660e8400-e29b-41d4-a716-446655440000",
                            "cost_amount": 150.00,
                            "coherence_score": 1.0,
                            "metadata": {},
                            "timestamp": "2026-02-15T10:30:00Z"
                        }
                    ]
                }
            }
        },
        404: {"description": "Contributor not found"}
    },
    openapi_extra={
        "x-spec-file": "specs/048-contributions-api.md",
        "x-idea-id": "coherence-network-value-attribution",
        "x-test-file": "api/tests/test_contributions.py"
    }
)
async def get_contributor_contributions(
    contributor_id: UUID, store: GraphStore = Depends(get_store)
) -> list[Contribution]:
    """List all contributions by a contributor."""
    if not store.get_contributor(contributor_id):
        raise HTTPException(status_code=404, detail="Contributor not found")
    return store.get_contributor_contributions(contributor_id)


@router.post(
    "/contributions/github",
    response_model=Contribution,
    status_code=201,
    summary="Track GitHub contribution via webhook",
    description="""
**Purpose**: Automatically track contributions from GitHub webhooks with auto-creation of contributors/assets.

**Spec**: [048-contributions-api.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/048-contributions-api.md)
**Idea**: `coherence-network-value-attribution`
**Tests**: `api/tests/test_contributions.py`

**Auto-Creation**:
- Creates Contributor if `contributor_email` not found
- Creates Asset if `repository` not found

**GitHub Coherence Formula**:
- Baseline: 0.5
- +0.1 if `files_changed > 0`
- +0.2 if `0 < lines_added < 100` (well-scoped)
- +0.1 if `lines_added >= 100` (large changes)
- Capped at 1.0

**Change Process**: See POST /contributions for full change process.
    """,
    responses={
        201: {
            "description": "Contribution tracked from GitHub webhook",
            "content": {
                "application/json": {
                    "example": {
                        "id": "770e8400-e29b-41d4-a716-446655440000",
                        "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
                        "asset_id": "660e8400-e29b-41d4-a716-446655440000",
                        "cost_amount": 100.00,
                        "coherence_score": 0.8,
                        "metadata": {
                            "files_changed": 3,
                            "lines_added": 50,
                            "lines_deleted": 10,
                            "commit_hash": "abc123def456",
                            "repository": "org/repo",
                            "contributor_email": "alice@example.com"
                        },
                        "timestamp": "2026-02-15T12:00:00Z"
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-spec-file": "specs/048-contributions-api.md",
        "x-idea-id": "coherence-network-value-attribution",
        "x-test-file": "api/tests/test_contributions.py",
        "x-webhook-type": "github"
    }
)
async def track_github_contribution(payload: GitHubContribution, store: GraphStore = Depends(get_store)) -> Contribution:
    """Track contribution from GitHub webhook. Auto-creates contributor and asset if they don't exist."""
    # Find or create contributor by email
    contributor = None
    if hasattr(store, "find_contributor_by_email"):
        contributor = store.find_contributor_by_email(payload.contributor_email)

    if not contributor:
        # Create new contributor
        contributor_name = payload.contributor_email.split("@")[0]
        contributor = Contributor(
            type=ContributorType.HUMAN,
            name=contributor_name,
            email=payload.contributor_email
        )
        contributor = store.create_contributor(contributor)

    # Find or create asset for repository
    asset = None
    if hasattr(store, "find_asset_by_name"):
        asset = store.find_asset_by_name(payload.repository)

    if not asset:
        # Create new asset
        asset = Asset(
            type=AssetType.CODE,
            description=f"GitHub repository: {payload.repository}"
        )
        asset = store.create_asset(asset)

    # Calculate coherence score from metadata
    coherence = calculate_coherence_from_github_metadata(payload.metadata)

    # Create contribution
    return store.create_contribution(
        contributor_id=contributor.id,
        asset_id=asset.id,
        cost_amount=payload.cost_amount,
        coherence_score=coherence,
        metadata={
            **payload.metadata,
            "commit_hash": payload.commit_hash,
            "repository": payload.repository,
            "contributor_email": payload.contributor_email,
        },
    )


def calculate_coherence_from_github_metadata(metadata: dict) -> float:
    """Calculate coherence score from GitHub commit metadata."""
    score = 0.5  # Baseline

    # Check for test files
    files_changed = metadata.get("files_changed", 0)
    if files_changed > 0:
        score += 0.1

    # Check for documentation
    lines_added = metadata.get("lines_added", 0)
    if lines_added > 0 and lines_added < 100:
        score += 0.2  # Well-scoped changes
    elif lines_added >= 100:
        score += 0.1  # Large changes

    return min(score, 1.0)


@router.post(
    "/contributions/github/debug",
    response_model=dict,
    status_code=200,
    summary="Debug GitHub webhook integration",
    description="""
**Purpose**: Test GitHub webhook integration with detailed error reporting (doesn't raise exceptions).

**Spec**: [048-contributions-api.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/048-contributions-api.md)
**Idea**: `coherence-network-value-attribution`
**Tests**: `api/tests/test_contributions.py`

**Returns**:
- On success: `{"success": true, "contribution_id": "...", "contributor_id": "...", "asset_id": "..."}`
- On error: `{"success": false, "error": "...", "error_type": "...", "traceback": "..."}`

**Use Case**: Debugging webhook configuration without 500 errors.

**Change Process**: See POST /contributions for full change process.
    """,
    responses={
        200: {
            "description": "Debug response (success or error details)",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "value": {
                                "success": True,
                                "contribution_id": "770e8400-e29b-41d4-a716-446655440000",
                                "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
                                "asset_id": "660e8400-e29b-41d4-a716-446655440000"
                            }
                        },
                        "error": {
                            "value": {
                                "success": False,
                                "error": "Database connection failed",
                                "error_type": "ConnectionError",
                                "traceback": "..."
                            }
                        }
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-spec-file": "specs/048-contributions-api.md",
        "x-idea-id": "coherence-network-value-attribution",
        "x-test-file": "api/tests/test_contributions.py",
        "x-webhook-type": "github",
        "x-debug-endpoint": True
    }
)
async def debug_github_contribution(payload: GitHubContribution, store: GraphStore = Depends(get_store)) -> dict:
    """Debug version that returns detailed error info instead of raising exceptions."""
    import traceback
    try:
        # Find or create contributor by email
        contributor = None
        if hasattr(store, "find_contributor_by_email"):
            contributor = store.find_contributor_by_email(payload.contributor_email)

        if not contributor:
            contributor_name = payload.contributor_email.split("@")[0]
            contributor = Contributor(
                type=ContributorType.HUMAN,
                name=contributor_name,
                email=payload.contributor_email
            )
            contributor = store.create_contributor(contributor)

        # Find or create asset
        asset = None
        if hasattr(store, "find_asset_by_name"):
            asset = store.find_asset_by_name(payload.repository)

        if not asset:
            asset = Asset(
                type=AssetType.CODE,
                description=f"GitHub repository: {payload.repository}"
            )
            asset = store.create_asset(asset)

        # Calculate coherence
        coherence = calculate_coherence_from_github_metadata(payload.metadata)

        # Create contribution
        contrib = store.create_contribution(
            contributor_id=contributor.id,
            asset_id=asset.id,
            cost_amount=payload.cost_amount,
            coherence_score=coherence,
            metadata={
                **payload.metadata,
                "commit_hash": payload.commit_hash,
                "repository": payload.repository,
                "contributor_email": payload.contributor_email,
            }
        )

        return {
            "success": True,
            "contribution_id": str(contrib.id),
            "contributor_id": str(contributor.id),
            "asset_id": str(asset.id)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
