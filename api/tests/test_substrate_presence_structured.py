"""Presence domain — structural composition discipline.

Presence files in this body have a baseline frontmatter shape (name /
canonical_url / type / contributor_type / create_if_missing). Some
presence cells also carry an `edges` block:

    edges:
      transmits: [<concept-or-presence-slug>, ...]
      tends:     [<slug>, ...]
      witnesses: [<slug>, ...]

The structured encoder produces a fully-expressed CTOR (named-pair LET
children with substrate-resident values) AND, when present, authors the
substrate edges via R_Transmit.TRANSMIT_TO / R_Tend.TEND / R_Witness.

Discipline lives in docs/coherence-substrate/structural-composition.md.

Lineage as a substrate domain is a future breath — current lineage
files (docs/lineage/*.md) are prose-only without YAML frontmatter, so
there is no `ingest_lineage_file` yet. That's named in the migration
doc; this breath ships the presence half.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    ingest_concept_file,
    ingest_presence_file,
    lookup_cell,
)
from app.services.substrate.category import (
    Level,
    RBasic,
    RBlock,
    RTend,
    RTransmit,
    RType,
)
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


def _make_file(content: str, prefix: str = "") -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, prefix=prefix,
    )
    f.write(content)
    f.close()
    return Path(f.name)


def _ingest_presence(session, slug: str, content: str) -> None:
    path = _make_file(content, prefix=f"{slug}_")
    target = path.parent / f"{slug}.md"
    path.rename(target)
    try:
        ingest_presence_file(session, target, structured=True)
        session.flush()
    finally:
        target.unlink()


def _ingest_concept_target(session, slug: str) -> None:
    """Seed a concept cell so edges can resolve to it."""
    content = f"---\nid: {slug}\n---\n\nBody.\n"
    path = _make_file(content)
    try:
        ingest_concept_file(session, path, structured=True)
        session.flush()
    finally:
        path.unlink()


# ---------------------------------------------------------------------------
# Baseline structured CTOR
# ---------------------------------------------------------------------------


def test_presence_structured_ctor_named_pairs(session):
    content = """---
name: test-presence
canonical_url: https://example.org/
type: contributor
contributor_type: HUMAN
---

Body of the presence.
"""
    _ingest_presence(session, "test-presence", content)
    cell = lookup_cell(session, "presence", "test-presence")
    assert cell is not None
    assert cell.ctor is not None

    # CTOR is R_Block.DO with named-pair LET children
    ctor_ref = f'@{cell.ctor.package}.{cell.ctor.level}.{cell.ctor.type_}.{cell.ctor.instance}'
    from app.services.substrate import form_execute_text
    cat = form_execute_text(session, f'{ctor_ref}.category')
    assert cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.DO)
    # All children are LET pairs
    n = form_execute_text(session, f'{ctor_ref}.nchildren')
    assert n >= 4
    for i in range(n):
        child_cat = form_execute_text(session, f'{ctor_ref}.child({i}).category')
        assert child_cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.LET)


# ---------------------------------------------------------------------------
# edges block — TRANSMIT_TO / TEND / WITNESS recipes
# ---------------------------------------------------------------------------


def test_transmits_edge_authored(session):
    """`edges.transmits` entries become TRANSMIT_TO cell-ref recipes
    pointing at the target concept cells."""
    _ingest_concept_target(session, "lc-target-of-transmission")

    content = """---
name: transmitting-presence
canonical_url: https://example.org/
type: contributor
contributor_type: HUMAN
edges:
  transmits:
    - lc-target-of-transmission
---

Body.
"""
    _ingest_presence(session, "transmitting-presence", content)

    presence = lookup_cell(session, "presence", "transmitting-presence")
    target = lookup_cell(session, "concept", "lc-target-of-transmission")
    assert presence.cell_id and target.cell_id

    transmit_cat = NodeID(1, Level.BASIC, RBasic.TRANSMIT, RTransmit.TRANSMIT_TO)
    serialized = (
        f"{transmit_cat}+1.1.{RType.REF}.{presence.cell_id}+1.1.{RType.REF}.{target.cell_id}"
    )
    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is not None


def test_tends_edge_authored(session):
    _ingest_concept_target(session, "lc-tended-cluster")

    content = """---
name: tending-presence
type: contributor
contributor_type: HUMAN
edges:
  tends:
    - lc-tended-cluster
---

Body.
"""
    _ingest_presence(session, "tending-presence", content)

    presence = lookup_cell(session, "presence", "tending-presence")
    target = lookup_cell(session, "concept", "lc-tended-cluster")
    tend_cat = NodeID(1, Level.BASIC, RBasic.TEND, RTend.TEND)
    serialized = (
        f"{tend_cat}+1.1.{RType.REF}.{presence.cell_id}+1.1.{RType.REF}.{target.cell_id}"
    )
    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is not None


def test_witnesses_edge_authored(session):
    _ingest_concept_target(session, "lc-witnessed-event")

    content = """---
name: witnessing-presence
type: contributor
contributor_type: HUMAN
edges:
  witnesses:
    - lc-witnessed-event
---

Body.
"""
    _ingest_presence(session, "witnessing-presence", content)

    presence = lookup_cell(session, "presence", "witnessing-presence")
    target = lookup_cell(session, "concept", "lc-witnessed-event")
    witness_cat = NodeID(1, Level.BASIC, RBasic.WITNESS, 1)
    serialized = (
        f"{witness_cat}+1.1.{RType.REF}.{presence.cell_id}+1.1.{RType.REF}.{target.cell_id}"
    )
    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is not None


def test_multiple_edge_kinds_in_one_ingest(session):
    _ingest_concept_target(session, "lc-multi-target-a")
    _ingest_concept_target(session, "lc-multi-target-b")

    content = """---
name: multi-edge-presence
type: contributor
contributor_type: HUMAN
edges:
  transmits:
    - lc-multi-target-a
  tends:
    - lc-multi-target-b
---

Body.
"""
    _ingest_presence(session, "multi-edge-presence", content)

    presence = lookup_cell(session, "presence", "multi-edge-presence")
    target_a = lookup_cell(session, "concept", "lc-multi-target-a")
    target_b = lookup_cell(session, "concept", "lc-multi-target-b")

    transmit_cat = NodeID(1, Level.BASIC, RBasic.TRANSMIT, RTransmit.TRANSMIT_TO)
    tend_cat = NodeID(1, Level.BASIC, RBasic.TEND, RTend.TEND)

    assert (
        session.query(SubstrateNodeORM)
        .filter_by(
            serialized=(
                f"{transmit_cat}+1.1.{RType.REF}.{presence.cell_id}+1.1.{RType.REF}.{target_a.cell_id}"
            )
        )
        .one_or_none()
        is not None
    )
    assert (
        session.query(SubstrateNodeORM)
        .filter_by(
            serialized=(
                f"{tend_cat}+1.1.{RType.REF}.{presence.cell_id}+1.1.{RType.REF}.{target_b.cell_id}"
            )
        )
        .one_or_none()
        is not None
    )


def test_edges_to_unresolved_targets_skip_silently(session):
    """Targets not yet ingested don't break ingest — they just don't author edges.
    A second-pass re-ingest after targets land closes the loop."""
    content = """---
name: orphan-edges-presence
type: contributor
contributor_type: HUMAN
edges:
  transmits:
    - does-not-exist
---

Body.
"""
    _ingest_presence(session, "orphan-edges-presence", content)
    cell = lookup_cell(session, "presence", "orphan-edges-presence")
    assert cell is not None  # ingest still completes


# ---------------------------------------------------------------------------
# Legacy path unchanged
# ---------------------------------------------------------------------------


def test_legacy_path_authors_no_edges(session):
    _ingest_concept_target(session, "lc-legacy-target")

    content = """---
name: legacy-presence
type: contributor
contributor_type: HUMAN
edges:
  transmits:
    - lc-legacy-target
---

Body.
"""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    f.write(content)
    f.close()
    path = Path(f.name)
    target_path = path.parent / "legacy-presence.md"
    path.rename(target_path)
    try:
        ingest_presence_file(session, target_path, structured=False)
        session.flush()
    finally:
        target_path.unlink()

    presence = lookup_cell(session, "presence", "legacy-presence")
    target = lookup_cell(session, "concept", "lc-legacy-target")
    transmit_cat = NodeID(1, Level.BASIC, RBasic.TRANSMIT, RTransmit.TRANSMIT_TO)
    serialized = (
        f"{transmit_cat}+1.1.{RType.REF}.{presence.cell_id}+1.1.{RType.REF}.{target.cell_id}"
    )
    found = (
        session.query(SubstrateNodeORM)
        .filter_by(serialized=serialized)
        .one_or_none()
    )
    assert found is None
