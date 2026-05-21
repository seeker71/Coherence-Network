"""Tests for the ARTIFACT domain — git-tracked files as substrate cells.

Closes the substrate-side gaps the lc-form-perceptron concept named:
- NodeID-addressed cells for git artifacts
- Cross-process content-addressing
- Harmonic-band placement so artifacts participate in resonance queries

The five perceptron gestures (execute / view / modify / transmute /
query) all reduce to existing substrate surfaces once the ARTIFACT cells
exist; the substrate-native perceptron script demonstrates the gestures
via the live kernel.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    BID_artifact,
    artifact_kind_hz,
    ingest_git_artifact,
    find_cells_compatible_with,
)
from app.services.substrate.category import BBasic, BDomain, Level
from app.services.substrate.kernel import NodeID
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.resonance import (
    find_cells_harmonic_at,
    hz_cell,
)
from app.services.substrate.substrate_strings import SubstrateStringORM

# find_downstream_cells ships in PR #1748; skip the test that uses it
# gracefully when this PR's CI runs before that merge.
try:
    from app.services.substrate.kernel import find_downstream_cells
    _HAS_DOWNSTREAM = True
except ImportError:
    find_downstream_cells = None  # type: ignore
    _HAS_DOWNSTREAM = False


@pytest.fixture
def session():
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


# ---------------------------------------------------------------------------
# BID_artifact & enum wiring
# ---------------------------------------------------------------------------


def test_artifact_blueprint_points_at_bdomain_artifact():
    bp = BID_artifact()
    assert bp == NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.ARTIFACT)
    assert int(BDomain.ARTIFACT) == 16


def test_artifact_kind_hz_carries_band_assignments():
    """The body's kind-to-Hz mapping places each file kind in a band."""
    assert artifact_kind_hz("md") == 741       # consciousness
    assert artifact_kind_hz("form") == 432     # natural harmony
    assert artifact_kind_hz("py") == 528       # transformation
    assert artifact_kind_hz("yaml") == 174     # foundation
    assert artifact_kind_hz("unknown_extension") == 432  # default


# ---------------------------------------------------------------------------
# ingest_git_artifact — idempotent encoder
# ---------------------------------------------------------------------------


def test_ingest_git_artifact_creates_cell_in_artifact_domain(session):
    cell, bp_id, ctor_id = ingest_git_artifact(
        session,
        path="scripts/foo.py",
        content_hash="abc123def456ghij",
        size_bytes=1024,
        mtime=1715200000.0,
    )
    assert cell.domain == "artifact"
    assert cell.name == "scripts/foo.py"
    assert bp_id == BID_artifact()


def test_ingest_git_artifact_is_idempotent(session):
    """Re-ingesting the same file collapses to the same cell."""
    a, _, _ = ingest_git_artifact(
        session, path="scripts/foo.py", content_hash="abc",
        size_bytes=100, mtime=1715200000.0,
    )
    b, _, _ = ingest_git_artifact(
        session, path="scripts/foo.py", content_hash="abc",
        size_bytes=100, mtime=1715200000.0,
    )
    assert a.cell_id == b.cell_id


def test_ingest_git_artifact_authors_harmonic_edge_for_kind(session):
    """A .md file is placed at 741 Hz (consciousness band) in the lattice."""
    md_cell, _, _ = ingest_git_artifact(
        session, path="docs/foo.md", content_hash="hash_md",
        size_bytes=500, mtime=0.0,
    )
    hz741 = hz_cell(session, 741)
    sources = find_cells_harmonic_at(session, hz741.cell_id)
    assert md_cell.cell_id in sources


def test_ingest_two_md_artifacts_share_harmonic_band(session):
    """Two .md files appear together when querying the 741 Hz band."""
    a, _, _ = ingest_git_artifact(
        session, path="docs/a.md", content_hash="h_a",
        size_bytes=100, mtime=0.0,
    )
    b, _, _ = ingest_git_artifact(
        session, path="docs/b.md", content_hash="h_b",
        size_bytes=100, mtime=0.0,
    )
    hz741 = hz_cell(session, 741)
    sources = set(find_cells_harmonic_at(session, hz741.cell_id))
    assert {a.cell_id, b.cell_id}.issubset(sources)


def test_ingest_form_and_md_land_in_different_bands(session):
    """A .form file (432 Hz) and a .md file (741 Hz) don't share a band."""
    form_cell, _, _ = ingest_git_artifact(
        session, path="docs/x.form", content_hash="h_form",
        size_bytes=200, mtime=0.0,
    )
    md_cell, _, _ = ingest_git_artifact(
        session, path="docs/y.md", content_hash="h_md",
        size_bytes=200, mtime=0.0,
    )
    hz432 = hz_cell(session, 432)
    hz741 = hz_cell(session, 741)
    in_432 = set(find_cells_harmonic_at(session, hz432.cell_id))
    in_741 = set(find_cells_harmonic_at(session, hz741.cell_id))
    assert form_cell.cell_id in in_432
    assert form_cell.cell_id not in in_741
    assert md_cell.cell_id in in_741
    assert md_cell.cell_id not in in_432


# ---------------------------------------------------------------------------
# The five perceptron gestures — exercised via existing substrate surfaces
# ---------------------------------------------------------------------------


def test_view_via_find_cells_compatible_with(session):
    """Gesture 2: VIEW — Blueprint compatibility surfaces every artifact."""
    a, _, _ = ingest_git_artifact(session, path="a.py", content_hash="hA",
                                  size_bytes=10, mtime=0.0)
    b, _, _ = ingest_git_artifact(session, path="b.md", content_hash="hB",
                                  size_bytes=20, mtime=0.0)
    views = find_cells_compatible_with(session, BID_artifact(), domain="artifact")
    cell_ids = {v.cell.cell_id for v in views}
    assert a.cell_id in cell_ids
    assert b.cell_id in cell_ids


def test_query_returns_only_artifact_domain(session):
    """Gesture 5: QUERY — domain filter returns only ARTIFACT cells."""
    ingest_git_artifact(session, path="a.py", content_hash="hA",
                        size_bytes=10, mtime=0.0)
    ingest_git_artifact(session, path="b.md", content_hash="hB",
                        size_bytes=20, mtime=0.0)
    rows = session.query(SubstrateNamedCellORM).filter_by(domain="artifact").all()
    assert len(rows) == 2
    assert {r.name for r in rows} == {"a.py", "b.md"}


@pytest.mark.skipif(
    not _HAS_DOWNSTREAM,
    reason="find_downstream_cells ships in PR #1748; will activate after merge",
)
def test_modify_preview_via_downstream_walk(session):
    """Gesture 3: MODIFY preview — find_downstream_cells reaches the Hz cell
    the artifact authored a HARMONIC_AT edge to."""
    cell, _, _ = ingest_git_artifact(
        session, path="docs/x.md", content_hash="hX",
        size_bytes=50, mtime=0.0,
    )
    downstream = find_downstream_cells(session, cell.cell_id)
    domains = {c.domain for c in downstream}
    # HARMONIC_AT @741 puts the spectrum cell downstream.
    assert "spectrum" in domains
