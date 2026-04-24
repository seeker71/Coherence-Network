from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.adapters.graph_store import InMemoryGraphStore
from app.db.base import Base
from app.models.asset import Asset, AssetType
from app.models.contributor import Contributor, ContributorType
from app.models.graph import Edge, Node
from app.services import unified_db


# ── helpers ──────────────────────────────────────────────────────────────────

def _contrib(email: str, name: str = "Real User") -> Contributor:
    return Contributor(type=ContributorType.HUMAN, name=name, email=email)


def _asset(desc: str = "test-asset") -> Asset:
    return Asset(type=AssetType.CODE, description=desc)


def test_graph_model_does_not_import_services() -> None:
    model_path = Path(__file__).resolve().parents[1] / "app" / "models" / "graph.py"
    tree = ast.parse(model_path.read_text(encoding="utf-8"))

    service_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.services"):
            service_imports.append(node.module or "")
        elif isinstance(node, ast.Import):
            service_imports.extend(alias.name for alias in node.names if alias.name.startswith("app.services"))

    assert service_imports == []


def test_unified_db_reexports_lower_db_base_for_compatibility() -> None:
    assert unified_db.Base is Base
    assert Node.metadata is Base.metadata
    assert Edge.metadata is Base.metadata
    assert "graph_nodes" in Base.metadata.tables
    assert "graph_edges" in Base.metadata.tables


# ── InMemoryGraphStore persist/isolation boundaries ───────────────────────────


def test_ephemeral_store_allows_test_email_contributor() -> None:
    """Without persist_path any email — including test domains — is accepted."""
    store = InMemoryGraphStore()
    c = store.create_contributor(_contrib("user@example.com"))
    assert store.find_contributor_by_email("user@example.com") is not None
    assert c.id in store._contributors


def test_persistent_store_blocks_test_email_contributor(tmp_path: Path) -> None:
    """persist_path mode rejects test-domain emails at create time."""
    store = InMemoryGraphStore(persist_path=str(tmp_path / "store.json"))
    with pytest.raises(ValueError, match="test contributor emails are not allowed"):
        store.create_contributor(_contrib("ci@example.com"))


def test_persistent_store_hides_injected_test_contributor(tmp_path: Path) -> None:
    """Injected test contributors are filtered from list and find when persist_path is set."""
    store = InMemoryGraphStore(persist_path=str(tmp_path / "store.json"))
    # Inject directly — bypasses the creation guard to simulate stale data
    ghost = _contrib("hidden@example.com", "Ghost")
    store._contributors[ghost.id] = ghost

    listed = store.list_contributors()
    assert not any(str(c.email) == "hidden@example.com" for c in listed)
    assert store.find_contributor_by_email("hidden@example.com") is None


def test_create_contribution_validates_contributor_and_asset_exist() -> None:
    """create_contribution raises ValueError when contributor or asset is absent."""
    store = InMemoryGraphStore()
    real = store.create_contributor(_contrib("alice@coherencenetwork.com", "Alice"))
    asset = store.create_asset(_asset())

    # Missing contributor
    with pytest.raises(ValueError, match="contributor"):
        store.create_contribution(
            contributor_id=uuid4(),
            asset_id=asset.id,
            cost_amount=Decimal("5.00"),
            coherence_score=0.9,
            metadata={},
        )

    # Missing asset
    with pytest.raises(ValueError, match="asset"):
        store.create_contribution(
            contributor_id=real.id,
            asset_id=uuid4(),
            cost_amount=Decimal("5.00"),
            coherence_score=0.9,
            metadata={},
        )

    # Valid pair — must succeed without error
    contrib = store.create_contribution(
        contributor_id=real.id,
        asset_id=asset.id,
        cost_amount=Decimal("5.00"),
        coherence_score=0.9,
        metadata={},
    )
    assert contrib.contributor_id == real.id


def test_persist_round_trip_preserves_real_contributors(tmp_path: Path) -> None:
    """save() + reload preserves real contributors and drops nothing silently."""
    path = str(tmp_path / "store.json")
    store = InMemoryGraphStore(persist_path=path)
    c = store.create_contributor(_contrib("alice@realdomain.com", "Alice"))
    store.save()

    store2 = InMemoryGraphStore(persist_path=path)
    found = store2.find_contributor_by_email("alice@realdomain.com")
    assert found is not None
    assert found.id == c.id
    assert store2.count_projects() == 0  # projects didn't bleed in
