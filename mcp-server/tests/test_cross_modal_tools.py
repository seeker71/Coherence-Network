"""Tests for the cross-modal substrate MCP tools.

The cross-modal substrate (PR #1956, scripts/intern_modality_blueprints.py)
landed seven canonical recipe-shape Blueprints with per-modality twin
families inside the actual lattice. These three tools surface that unity
through the MCP layer so any agent (Claude Desktop, Codex, Cursor, A2A)
can ask "what other modalities carry the shape I am thinking about?"
without composing the Form query by hand.

The tests assert two things:

1. Each tool is registered and routes to the documented REST endpoint —
   dispatch monkeypatches `api_get` and asserts the URL shape. This is
   the unit-level contract that the MCP transport carries.
2. The same underlying substrate kernel that powers `coh substrate form`
   answers these endpoints — exercised by importing the intern script,
   landing the canonical shapes into an in-memory substrate, and calling
   the REST route functions directly. Same `find_equivalent_cells` call,
   same Blueprint NodeID, same family — the cross-modal unity reaches
   the MCP surface without a parallel implementation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPO_ROOT = ROOT.parent
API_DIR = REPO_ROOT / "api"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for extra in (API_DIR, SCRIPTS_DIR):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from coherence_mcp_server import server as mcp_server  # noqa: E402


# ---------------------------------------------------------------------------
# Registration + dispatch contract
# ---------------------------------------------------------------------------


def test_cross_modal_tools_are_registered() -> None:
    """All three cross-modal tools join the MCP surface alongside the substrate cluster."""
    expected = {
        "coherence_cross_modal_twins",
        "coherence_canonical_families",
        "coherence_modality_for",
    }
    assert expected <= set(mcp_server.TOOL_MAP)


def test_cross_modal_twins_routes_to_api(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"path": path}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)

    result = mcp_server.dispatch(
        "coherence_cross_modal_twins", {"canonical_name": "R_Recovery"}
    )
    assert result == {"path": "/api/substrate/cross_modal_twins/R_Recovery"}
    assert calls == [("/api/substrate/cross_modal_twins/R_Recovery", None)]


def test_canonical_families_routes_to_api(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"families": [], "count": 0}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)

    result = mcp_server.dispatch("coherence_canonical_families", {})
    assert result == {"families": [], "count": 0}
    assert calls == [("/api/substrate/canonical_families", None)]


def test_modality_for_routes_to_api(monkeypatch) -> None:
    calls: list[tuple[str, dict | None]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, params))
        return {"path": path}

    monkeypatch.setattr(mcp_server, "api_get", fake_get)

    result = mcp_server.dispatch(
        "coherence_modality_for", {"per_modality_name": "R_Re-coherence"}
    )
    assert result == {"path": "/api/substrate/modality_for/R_Re-coherence"}
    assert calls == [("/api/substrate/modality_for/R_Re-coherence", None)]


def test_cross_modal_twins_rejects_empty_canonical_name() -> None:
    result = mcp_server.dispatch("coherence_cross_modal_twins", {})
    assert "error" in result


def test_modality_for_rejects_empty_per_modality_name() -> None:
    result = mcp_server.dispatch("coherence_modality_for", {})
    assert "error" in result


# ---------------------------------------------------------------------------
# Substrate-kernel-backed integration: tools answer from the same lattice
# that `coh substrate form` queries
# ---------------------------------------------------------------------------


@pytest.fixture
def substrate_session():
    """In-memory SQLite-backed substrate session.

    Same fixture pattern as api/tests/test_modality_blueprints.py — the
    REST endpoints accept a session via session_scope(); here we land the
    canonical shapes into a real substrate and call the router functions
    directly with that session.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.services.substrate.orm import (
        SubstrateNamedCellORM,
        SubstrateNodeORM,
    )
    from app.services.substrate.substrate_strings import SubstrateStringORM

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture
def substrate_with_canonical_shapes(monkeypatch, substrate_session):
    """Substrate session pre-loaded with the seven canonical shapes.

    Patches the router's `session_scope` to a no-arg context manager that
    yields our in-memory session, so the route handlers run against the
    real substrate kernel without touching production data.
    """
    from contextlib import contextmanager

    from intern_modality_blueprints import intern_all

    intern_all(substrate_session)
    substrate_session.flush()

    @contextmanager
    def fake_scope():
        yield substrate_session

    from app.routers import substrate as substrate_router

    monkeypatch.setattr(substrate_router, "session_scope", fake_scope)
    return substrate_session


def test_cross_modal_twins_returns_recovery_family(substrate_with_canonical_shapes) -> None:
    """`R_Recovery` returns the quantum / healing / assemblage twins.

    The lattice carries R_Re-coherence, R_Re-pattern, R_Re-anchor as
    siblings of R_Recovery — they share the canonical Blueprint NodeID.
    """
    from app.routers.substrate import get_cross_modal_twins

    result = get_cross_modal_twins("R_Recovery")
    assert result.found is True
    assert result.canonical_name == "R_Recovery"
    assert result.blueprint is not None
    twin_names = {c.name for c in result.twins}
    assert {"R_Re-coherence", "R_Re-pattern", "R_Re-anchor"} <= twin_names
    # canonical itself is excluded
    assert "R_Recovery" not in twin_names


def test_cross_modal_twins_returns_observer_family(substrate_with_canonical_shapes) -> None:
    """The keystone shape carries quantum measurement, teaching, and assemblage."""
    from app.routers.substrate import get_cross_modal_twins

    result = get_cross_modal_twins("R_ObserverConditionedActualization")
    assert result.found is True
    twin_names = {c.name for c in result.twins}
    # The keystone family carries the three modality tags from
    # scripts/intern_modality_blueprints.py CLAIM-T1 / CLAIM-Q1 / CLAIM-A1.
    # R_Re-anchor only joins the R_Recovery family (not the keystone) —
    # different canonical_name keeps the Blueprint compositions apart.
    assert {"R_Measurement-Collapse", "R_Pointing"} <= twin_names


def test_cross_modal_twins_unknown_canonical_returns_empty(substrate_with_canonical_shapes) -> None:
    """Unknown canonical → empty list with found=False, no error."""
    from app.routers.substrate import get_cross_modal_twins

    result = get_cross_modal_twins("R_NotAShape")
    assert result.found is False
    assert result.twins == []
    assert result.count == 0


def test_canonical_families_lists_every_canonical_shape(substrate_with_canonical_shapes) -> None:
    """Every interned canonical shape appears in the families listing.

    The endpoint pulls its iteration order from
    `app.services.substrate.modality_shapes.CANONICAL_SHAPES` so the
    families grow with the substrate. Asserts the keystone leads, the
    full set is present, and ordering matches declaration order.
    """
    from app.routers.substrate import get_canonical_families
    from app.services.substrate import canonical_shape_names

    expected_names = canonical_shape_names()

    result = get_canonical_families()
    assert result.count == len(expected_names)
    names = [f.canonical_name for f in result.families]
    assert names == expected_names
    # Keystone leads the ordering.
    assert names[0] == "R_ObserverConditionedActualization"
    # Each family carries the canonical itself plus its twins
    recovery_family = next(
        f for f in result.families if f.canonical_name == "R_Recovery"
    )
    member_names = {c.name for c in recovery_family.members}
    assert {"R_Recovery", "R_Re-coherence", "R_Re-pattern", "R_Re-anchor"} <= member_names
    assert recovery_family.member_count == len(recovery_family.members)


def test_modality_for_resolves_per_modality_name(substrate_with_canonical_shapes) -> None:
    """`R_Re-coherence` (quantum) resolves to the R_Recovery canonical family."""
    from app.routers.substrate import get_modality_for

    result = get_modality_for("R_Re-coherence")
    assert result.found is True
    # R_Re-coherence shares Blueprint with R_Recovery (and twins from the
    # observer-actualization family that also matches the composition).
    # The canonical_name is the first family member whose name is in the
    # canonical set — for the recovery family that's R_Recovery.
    assert result.canonical_name in {
        "R_Recovery",
        "R_ObserverConditionedActualization",
    }
    family_names = {c.name for c in result.family}
    assert "R_Re-coherence" in family_names


def test_modality_for_unknown_returns_empty(substrate_with_canonical_shapes) -> None:
    """Unknown per-modality cell → empty result, not an error."""
    from app.routers.substrate import get_modality_for

    result = get_modality_for("R_NotInTheLattice")
    assert result.found is False
    assert result.family == []
    assert result.canonical_name is None
