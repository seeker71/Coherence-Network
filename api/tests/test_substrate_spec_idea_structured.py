"""Spec + Idea domains — structural composition discipline.

The paired migration: spec.idea_id → R_Realize.REALIZE cell-ref recipe
to the @idea cell; idea.specs[] → list of R_Realize.REALIZE recipes in
the reverse direction. Bidirectional structural integrity via content-
addressed interning: (spec, idea, REALIZE) collapses to one NodeID
regardless of which side authored it.

Discipline lives in docs/coherence-substrate/structural-composition.md.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    ingest_idea_file,
    ingest_spec_file,
    lookup_cell,
)
from app.services.substrate.category import Level, RBasic, RRealize, RType
from app.services.substrate.kernel import NodeID
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.substrate_strings import SubstrateStringORM


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


def _make_file(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def _author_idea(session, slug: str, **fields) -> None:
    lines = ["---", f"idea_id: {slug}"]
    for k, v in fields.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.extend(["---", "", "Body.", ""])
    path = _make_file("\n".join(lines))
    try:
        ingest_idea_file(session, path, structured=True)
        session.flush()
    finally:
        path.unlink()


def _author_spec(session, slug: str, **fields) -> None:
    # spec name comes from the filename stem; write a deterministic path
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, prefix=f"{slug}_")
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.extend(["---", "", "Body.", ""])
    f.write("\n".join(lines))
    f.close()
    path = Path(f.name)
    # Rename so the filename stem is the spec slug (spec ingest uses stem as name).
    target = path.parent / f"{slug}.md"
    path.rename(target)
    try:
        ingest_spec_file(session, target, structured=True)
        session.flush()
    finally:
        target.unlink()


# ---------------------------------------------------------------------------
# spec.idea_id → REALIZE cell-ref recipe
# ---------------------------------------------------------------------------


def test_spec_authors_realize_edge_to_idea(session):
    _author_idea(session, "agent-pipeline")
    _author_spec(session, "agent-pipeline-mvp", idea_id="agent-pipeline")

    spec = lookup_cell(session, "spec", "agent-pipeline-mvp")
    idea = lookup_cell(session, "idea", "agent-pipeline")
    assert spec is not None and idea is not None

    realize_cat = NodeID(1, Level.BASIC, RBasic.REALIZE, RRealize.REALIZE)
    source_ref = f"1.1.{RType.REF}.{spec.cell_id}"
    target_ref = f"1.1.{RType.REF}.{idea.cell_id}"
    serialized = f"{realize_cat}+{source_ref}+{target_ref}"

    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is not None, "REALIZE edge from spec to idea not authored"


def test_spec_skipped_when_idea_not_yet_ingested(session):
    """When `idea_id` references an idea not in the substrate, ingest
    completes without the edge; a second-pass re-ingest closes the loop."""
    _author_spec(session, "orphan-spec", idea_id="does-not-exist")
    spec = lookup_cell(session, "spec", "orphan-spec")
    assert spec is not None  # cell ingested, just no edge


# ---------------------------------------------------------------------------
# idea.specs[] → reverse REALIZE recipes (one per spec)
# ---------------------------------------------------------------------------


def test_idea_authors_realize_edges_from_each_spec(session):
    # Ingest specs first so they exist when the idea references them
    _author_spec(session, "agent-pipeline-mvp", idea_id="agent-pipeline")
    _author_spec(session, "agent-pipeline-v2", idea_id="agent-pipeline")
    # Now ingest the idea pointing back
    _author_idea(
        session, "agent-pipeline",
        specs=["agent-pipeline-mvp", "agent-pipeline-v2"],
    )

    idea = lookup_cell(session, "idea", "agent-pipeline")
    spec1 = lookup_cell(session, "spec", "agent-pipeline-mvp")
    spec2 = lookup_cell(session, "spec", "agent-pipeline-v2")
    assert idea.cell_id and spec1.cell_id and spec2.cell_id

    realize_cat = NodeID(1, Level.BASIC, RBasic.REALIZE, RRealize.REALIZE)
    idea_ref = f"1.1.{RType.REF}.{idea.cell_id}"
    rows = (
        session.query(SubstrateNodeORM)
        .filter(SubstrateNodeORM.serialized.like(f"{realize_cat}+%+{idea_ref}"))
        .all()
    )
    # Both spec→idea edges should exist (authored by both sides)
    assert len(rows) >= 2


def test_idea_specs_markdown_link_form(session):
    """Idea files sometimes encode `specs:` as markdown links — the slug
    is the basename of the link target. The encoder normalizes both forms.

    Real idea files use bare markdown-link YAML which YAML can't parse;
    here we test the encoder's ability to extract a slug given a quoted
    entry. A future breath could add a markdown-link-aware frontmatter
    parser; the encoder is already ready for it."""
    _author_spec(session, "agent-pipeline-mvp", idea_id="agent-pipeline")
    _author_idea(
        session, "agent-pipeline",
        specs=['"[Agent Pipeline MVP](../specs/agent-pipeline-mvp.md)"'],
    )

    idea = lookup_cell(session, "idea", "agent-pipeline")
    spec = lookup_cell(session, "spec", "agent-pipeline-mvp")
    assert idea.cell_id and spec.cell_id

    realize_cat = NodeID(1, Level.BASIC, RBasic.REALIZE, RRealize.REALIZE)
    serialized = (
        f"{realize_cat}+1.1.{RType.REF}.{spec.cell_id}+1.1.{RType.REF}.{idea.cell_id}"
    )
    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is not None


# ---------------------------------------------------------------------------
# Bidirectional integrity: both sides author → one shared edge NodeID
# ---------------------------------------------------------------------------


def test_bidirectional_realize_collapses_to_one_node_id(session):
    """When BOTH spec.idea_id AND idea.specs[] are authored with structured=True,
    the same (spec, idea, REALIZE) recipe shape interns once — content-addressing
    makes the two paths converge on a single NodeID."""
    _author_idea(
        session, "agent-pipeline",
        specs=["agent-pipeline-mvp"],
    )
    _author_spec(session, "agent-pipeline-mvp", idea_id="agent-pipeline")
    # Second-pass: re-ingest the idea now that the spec exists, so the
    # reverse edge can be authored
    _author_idea(
        session, "agent-pipeline",
        specs=["agent-pipeline-mvp"],
    )

    spec = lookup_cell(session, "spec", "agent-pipeline-mvp")
    idea = lookup_cell(session, "idea", "agent-pipeline")
    realize_cat = NodeID(1, Level.BASIC, RBasic.REALIZE, RRealize.REALIZE)
    serialized = (
        f"{realize_cat}+1.1.{RType.REF}.{spec.cell_id}+1.1.{RType.REF}.{idea.cell_id}"
    )
    rows = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .all()
    )
    # Content-addressing → exactly one row, regardless of who authored
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# absorbed_ideas[] → ABSORB recipes
# ---------------------------------------------------------------------------


def test_absorbed_ideas_author_absorb_recipes(session):
    _author_idea(session, "earlier-sketch")
    _author_idea(
        session, "successor-idea",
        absorbed_ideas=["earlier-sketch"],
    )

    successor = lookup_cell(session, "idea", "successor-idea")
    earlier = lookup_cell(session, "idea", "earlier-sketch")
    assert successor.cell_id and earlier.cell_id

    absorb_cat = NodeID(1, Level.BASIC, RBasic.ABSORB, 1)
    serialized = (
        f"{absorb_cat}+1.1.{RType.REF}.{earlier.cell_id}+1.1.{RType.REF}.{successor.cell_id}"
    )
    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is not None


# ---------------------------------------------------------------------------
# Legacy path unchanged
# ---------------------------------------------------------------------------


def test_legacy_path_authors_no_edges(session):
    _author_idea(session, "legacy-idea-target")
    # Legacy ingest — structured=False
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, prefix="legacy-spec_")
    f.write("---\nidea_id: legacy-idea-target\n---\nBody.\n")
    f.close()
    path = Path(f.name)
    target = path.parent / "legacy-spec.md"
    path.rename(target)
    try:
        ingest_spec_file(session, target, structured=False)
        session.flush()
    finally:
        target.unlink()

    spec = lookup_cell(session, "spec", "legacy-spec")
    idea = lookup_cell(session, "idea", "legacy-idea-target")
    assert spec is not None
    realize_cat = NodeID(1, Level.BASIC, RBasic.REALIZE, RRealize.REALIZE)
    serialized = (
        f"{realize_cat}+1.1.{RType.REF}.{spec.cell_id}+1.1.{RType.REF}.{idea.cell_id}"
    )
    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is None  # no edge authored without structured=True
