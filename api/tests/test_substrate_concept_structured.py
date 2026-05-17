"""Concept domain — structured composition discipline.

A concept cell's frontmatter is richer than memory: it carries `parent`
(cell-ref), `cross_refs` (list of cell-refs), `hz` (Spectrum band),
`geometry: {arity, form, topology, polarity, ...}` (typed-token refs to
dimensional vocabulary cells). The structured encoder makes all of these
become substrate-resident recipe edges rather than slug strings.

Per `docs/coherence-substrate/structural-composition.md`.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    form_execute_text,
    ingest_concept_file,
    lookup_cell,
)
from app.services.substrate.category import (
    Level,
    RBasic,
    RBlock,
    RCompose,
    RResonance,
    RType,
)
from app.services.substrate.kernel import NodeID
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.substrate_strings import (
    SubstrateStringORM,
    lookup_string_value,
)


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


def _make_concept_file(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def _author_concept(session, slug: str, **extra) -> None:
    """Ingest a concept cell with minimal frontmatter — for cross-ref targets."""
    lines = ["---", f"id: {slug}"]
    for k, v in extra.items():
        if isinstance(v, dict):
            lines.append(f"{k}:")
            for kk, vv in v.items():
                lines.append(f"  {kk}: {vv}")
        elif isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{k}: {v}")
    lines.extend(["---", "", "Body.", ""])
    path = _make_concept_file("\n".join(lines))
    try:
        ingest_concept_file(session, path, structured=True)
        session.flush()
    finally:
        path.unlink()


# ---------------------------------------------------------------------------
# CTOR structure — values recoverable, named-pair tree
# ---------------------------------------------------------------------------


def test_concept_ctor_uses_structured_encoder(session):
    """The concept structured CTOR has named-pair LET children whose values
    are recoverable via the substrate string-table."""
    _author_concept(session, "lc-test-concept", hz=174, status="seed")

    cell = lookup_cell(session, "concept", "lc-test-concept")
    assert cell is not None
    assert cell.ctor is not None

    ctor_ref = f'@{cell.ctor.package}.{cell.ctor.level}.{cell.ctor.type_}.{cell.ctor.instance}'
    cat = form_execute_text(session, f'{ctor_ref}.category')
    assert cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.DO)

    # Walk one of the children to confirm it's a LET pair with recoverable values
    n = form_execute_text(session, f'{ctor_ref}.nchildren')
    assert n >= 2  # at least `id` and `hz` and `status`

    # Each child should be R_Block.LET
    for i in range(n):
        child_cat = form_execute_text(session, f'{ctor_ref}.child({i}).category')
        assert child_cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.LET)


# ---------------------------------------------------------------------------
# parent → PARENT_OF compose recipe (cell-ref, not slug-string)
# ---------------------------------------------------------------------------


def test_parent_authors_parent_of_recipe(session):
    """`parent: lc-x` becomes a PARENT_OF compose recipe pointing at the
    parent concept cell — visible as an interned substrate node."""
    # Seed the parent first
    _author_concept(session, "lc-parent-of-test")
    # Now ingest the child with `parent: lc-parent-of-test`
    _author_concept(session, "lc-child-of-test", parent="lc-parent-of-test")

    child = lookup_cell(session, "concept", "lc-child-of-test")
    parent = lookup_cell(session, "concept", "lc-parent-of-test")
    assert child.cell_id is not None and parent.cell_id is not None

    # The PARENT_OF recipe should exist in substrate_nodes — look it up by
    # category + serialized children.
    parent_of_cat = NodeID(1, Level.BASIC, RBasic.COMPOSE, RCompose.PARENT_OF)
    source_ref = f"1.1.{RType.REF}.{child.cell_id}"
    target_ref = f"1.1.{RType.REF}.{parent.cell_id}"
    serialized = f"{parent_of_cat}+{source_ref}+{target_ref}"

    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is not None, (
        f"PARENT_OF recipe not authored — expected serialized={serialized}"
    )


def test_parent_skipped_when_target_not_yet_ingested(session):
    """When `parent:` references a concept that isn't in the substrate yet,
    the encoder skips silently rather than aborting ingest. A second-pass
    re-ingest closes the loop once all cells exist."""
    _author_concept(session, "lc-orphan-child", parent="lc-does-not-exist")
    child = lookup_cell(session, "concept", "lc-orphan-child")
    assert child is not None  # cell still ingested, just without the edge


# ---------------------------------------------------------------------------
# cross_refs → list of CROSS_REF recipes
# ---------------------------------------------------------------------------


def test_cross_refs_author_cross_ref_recipes(session):
    """Each `cross_refs` entry becomes a CROSS_REF compose recipe."""
    _author_concept(session, "lc-target-a")
    _author_concept(session, "lc-target-b")
    _author_concept(session, "lc-target-c")
    _author_concept(
        session, "lc-with-refs",
        cross_refs=["lc-target-a", "lc-target-b", "lc-target-c"],
    )

    src = lookup_cell(session, "concept", "lc-with-refs")
    assert src.cell_id is not None

    cross_ref_cat = NodeID(1, Level.BASIC, RBasic.COMPOSE, RCompose.CROSS_REF)
    rows = (
        session.query(SubstrateNodeORM)
        .filter(SubstrateNodeORM.serialized.like(f"{cross_ref_cat}+%"))
        .all()
    )
    # Three CROSS_REF recipes should have been authored, each pointing
    # from `lc-with-refs` to one of the targets.
    source_seg = f"1.1.{RType.REF}.{src.cell_id}"
    matching = [r for r in rows if f"+{source_seg}+" in r.serialized]
    assert len(matching) >= 3


# ---------------------------------------------------------------------------
# hz + geometry → resonance edges via author_geometry_signature
# ---------------------------------------------------------------------------


def test_hz_authors_harmonic_at_edge(session):
    """`hz: 174` becomes a HARMONIC_AT resonance edge to @spectrum(Hz-174)."""
    _author_concept(session, "lc-hz-test", hz=174)

    cell = lookup_cell(session, "concept", "lc-hz-test")
    hz_spectrum_cell = lookup_cell(session, "spectrum", "Hz-174")
    assert hz_spectrum_cell is not None, "Hz(174) spectrum cell should be authored"

    harmonic_at_cat = NodeID(1, Level.BASIC, RBasic.RESONANCE, RResonance.HARMONIC_AT)
    source_ref = f"1.1.{RType.REF}.{cell.cell_id}"
    target_ref = f"1.1.{RType.REF}.{hz_spectrum_cell.cell_id}"
    serialized = f"{harmonic_at_cat}+{source_ref}+{target_ref}"
    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is not None, "HARMONIC_AT resonance edge not authored"


def test_geometry_authors_shape_edges(session):
    """`geometry.{form, topology, polarity}` authors SHAPES recipe edges to
    cells in the geometric-form / topology / polarity domains."""
    content = """---
id: lc-geometry-test
hz: 174
geometry:
  arity: 3
  form: triad
  topology: parallel
  polarity: parallel-facets
---

Body.
"""
    path = _make_concept_file(content)
    try:
        ingest_concept_file(session, path, structured=True)
        session.flush()
    finally:
        path.unlink()

    cell = lookup_cell(session, "concept", "lc-geometry-test")
    assert cell.cell_id is not None

    triad_cell = lookup_cell(session, "geometric_form", "triad")
    parallel_cell = lookup_cell(session, "topology", "parallel")
    parallel_facets_cell = lookup_cell(session, "polarity", "parallel-facets")

    assert triad_cell is not None
    assert parallel_cell is not None
    assert parallel_facets_cell is not None

    # Each is reached via a SHAPES recipe edge
    shapes_cat = NodeID(1, Level.BASIC, RBasic.RESONANCE, RResonance.SHAPES)
    source_seg = f"1.1.{RType.REF}.{cell.cell_id}"
    for target in (triad_cell, parallel_cell, parallel_facets_cell):
        target_seg = f"1.1.{RType.REF}.{target.cell_id}"
        serialized = f"{shapes_cat}+{source_seg}+{target_seg}"
        found = (
            session.query(SubstrateNodeORM)
            .filter_by(serialized=serialized)
            .one_or_none()
        )
        assert found is not None, (
            f"SHAPES edge to {target.domain}({target.name}) not authored"
        )


def test_geometry_idempotent(session):
    """Re-ingesting the same concept produces the same edge NodeIDs
    (content-addressed)."""
    content = """---
id: lc-idempotent-test
hz: 174
geometry:
  form: triad
---

Body.
"""
    path = _make_concept_file(content)
    try:
        ingest_concept_file(session, path, structured=True)
        session.flush()
        cell1 = lookup_cell(session, "concept", "lc-idempotent-test")
        # Re-ingest
        ingest_concept_file(session, path, structured=True)
        session.flush()
        cell2 = lookup_cell(session, "concept", "lc-idempotent-test")
        # Same cell, same cell_id
        assert cell1.cell_id == cell2.cell_id
    finally:
        path.unlink()


# ---------------------------------------------------------------------------
# Legacy path unchanged — backward compatibility during migration
# ---------------------------------------------------------------------------


def test_legacy_path_unchanged(session):
    """Without structured=True, the legacy encoder runs — no resonance edges
    authored. Migration is opt-in per-call."""
    content = """---
id: lc-legacy-test
hz: 174
geometry:
  form: triad
---

Body.
"""
    path = _make_concept_file(content)
    try:
        ingest_concept_file(session, path, structured=False)
        session.flush()
        cell = lookup_cell(session, "concept", "lc-legacy-test")
        assert cell is not None
        # No SHAPES edge should exist for this cell
        shapes_cat = NodeID(1, Level.BASIC, RBasic.RESONANCE, RResonance.SHAPES)
        rows = (
            session.query(SubstrateNodeORM)
            .filter(SubstrateNodeORM.serialized.like(f"{shapes_cat}+%"))
            .all()
        )
        source_seg = f"1.1.{RType.REF}.{cell.cell_id}"
        matching = [r for r in rows if f"+{source_seg}+" in r.serialized]
        assert len(matching) == 0
    finally:
        path.unlink()
