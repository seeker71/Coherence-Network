"""Flow-centric tests for the coherence-substrate.

Validates the kernel + markdown frontend end-to-end against an isolated
in-memory SQLite database.

The architectural commitments tested here:
- NodeID 4-tuples uniquely identify positions in the lattice
- Two structurally-identical shapes share the same NodeID (content addressing)
- A NamedCell carries (Recipe access + Base + Name + CTOR)
- The equivalence query returns cells with matching Blueprint NodeIDs
- Recipe trees compose bottom-up with level promotion
- Cells with different frontmatter shapes get distinct Blueprint NodeIDs
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.substrate import (
    NodeID,
    Recipe,
    find_equivalent_cells,
    ingest_memory_file,
    intern_node,
    lattice_stats,
    lookup_cell,
    make_cell,
    parse_markdown,
)
from app.services.substrate.category import (
    BBasic,
    BContainer,
    BType,
    Level,
    RBasic,
    RType,
)
from app.services.substrate.kernel import DOMAIN_BLUEPRINT, DOMAIN_RECIPE
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


@pytest.fixture
def session():
    """In-memory SQLite session with substrate tables only."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Kernel invariants
# ---------------------------------------------------------------------------


def test_intern_node_dedup_returns_same_id(session):
    """Two intern calls with the same (category, children) collapse."""
    cat = NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.OBJECT)
    child = NodeID(1, Level.TRIVIAL, BType.NUMERIC, 2)  # Integer
    a = intern_node(session, DOMAIN_BLUEPRINT, cat, [child])
    b = intern_node(session, DOMAIN_BLUEPRINT, cat, [child])
    assert a == b
    # Count incremented on dedup
    row = session.query(SubstrateNodeORM).filter_by(
        package=a.package, level=a.level, type_=a.type_, instance=a.instance
    ).one()
    assert row.count == 2


def test_different_shapes_get_different_ids(session):
    """Different children → different NodeIDs."""
    cat = NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.OBJECT)
    int_t = NodeID(1, Level.TRIVIAL, BType.NUMERIC, 2)
    str_t = NodeID(1, Level.TRIVIAL, BType.NUMERIC, 4)
    a = intern_node(session, DOMAIN_BLUEPRINT, cat, [int_t])
    b = intern_node(session, DOMAIN_BLUEPRINT, cat, [str_t])
    assert a != b


def test_recipe_tree_composition(session):
    """A Recipe with children interns recursively, level-promoted bottom-up."""
    int_lit_a = Recipe(
        category=NodeID(1, Level.TRIVIAL, RType.INTEGER, 1),
        blueprint=NodeID(1, Level.TRIVIAL, BType.NUMERIC, 2),
    )
    int_lit_b = Recipe(
        category=NodeID(1, Level.TRIVIAL, RType.INTEGER, 2),
        blueprint=NodeID(1, Level.TRIVIAL, BType.NUMERIC, 2),
    )
    plus = Recipe(
        category=NodeID(1, Level.BASIC, RBasic.BLOCK, 1),
        blueprint=NodeID(1, Level.TRIVIAL, BType.NUMERIC, 2),
        children=[int_lit_a, int_lit_b],
    )
    rid = plus.make_self_id(session)
    # Level promoted above BASIC because it has children.
    assert rid.level >= Level.COMPLEX_1


def test_recipe_dedup_via_makeself(session):
    """Two structurally-identical recipes share the same SelfID."""
    def build():
        a = Recipe(
            category=NodeID(1, Level.TRIVIAL, RType.INTEGER, 1),
            blueprint=NodeID(1, Level.TRIVIAL, BType.NUMERIC, 2),
        )
        b = Recipe(
            category=NodeID(1, Level.TRIVIAL, RType.INTEGER, 2),
            blueprint=NodeID(1, Level.TRIVIAL, BType.NUMERIC, 2),
        )
        return Recipe(
            category=NodeID(1, Level.BASIC, RBasic.BLOCK, 1),
            blueprint=NodeID(1, Level.TRIVIAL, BType.NUMERIC, 2),
            children=[a, b],
        )

    r1_id = build().make_self_id(session)
    r2_id = build().make_self_id(session)
    assert r1_id == r2_id


# ---------------------------------------------------------------------------
# Cell lifecycle
# ---------------------------------------------------------------------------


def test_make_cell_persists_and_lookup_finds(session):
    """Creating a cell, then looking it up, returns the same shape."""
    bp = NodeID(1, Level.BASIC, BBasic.DOMAIN, 4)  # MEMORY
    cell = make_cell(session, "test-memory", "memory", bp, source_path="/tmp/x.md")
    assert cell.cell_id is not None

    found = lookup_cell(session, "memory", "test-memory")
    assert found is not None
    assert found.name == "test-memory"
    assert found.blueprint == bp
    assert found.source_path == "/tmp/x.md"


def test_make_cell_idempotent_on_domain_name(session):
    """Re-creating the same (domain, name) updates instead of duplicating."""
    bp1 = NodeID(1, Level.BASIC, BBasic.DOMAIN, 4)
    bp2 = NodeID(1, Level.BASIC, BBasic.DOMAIN, 1)  # IDEA
    c1 = make_cell(session, "x", "memory", bp1)
    c2 = make_cell(session, "x", "memory", bp2)
    assert c1.cell_id == c2.cell_id
    # The blueprint binding updated
    found = lookup_cell(session, "memory", "x")
    assert found.blueprint == bp2


# ---------------------------------------------------------------------------
# Markdown frontend — the killer demo
# ---------------------------------------------------------------------------


MEMORY_TEMPLATE_A = textwrap.dedent("""\
    ---
    name: {name}
    description: a one-line description
    type: feedback
    ---
    The body of this memory.
    """)

MEMORY_TEMPLATE_DIFFERENT = textwrap.dedent("""\
    ---
    name: {name}
    description: a description
    type: project
    extra_field: yes
    another_field: more
    ---
    A longer body to make it look different.
    """)


def test_two_memories_with_same_shape_share_blueprint(session, tmp_path):
    """Two memory files with identical frontmatter shape (same keys, same
    value-types) hash to the same Blueprint NodeID. This is the killer
    architectural payoff: structural equivalence at the substrate level.
    """
    p1 = tmp_path / "alpha.md"
    p1.write_text(MEMORY_TEMPLATE_A.format(name="Alpha"))
    p2 = tmp_path / "beta.md"
    p2.write_text(MEMORY_TEMPLATE_A.format(name="Beta"))

    cell1, bp1, _ = ingest_memory_file(session, p1)
    cell2, bp2, _ = ingest_memory_file(session, p2)

    assert bp1 == bp2, "structurally identical memories should share Blueprint NodeID"


def test_different_frontmatter_shape_different_blueprint(session, tmp_path):
    """A memory with extra frontmatter keys gets a different Blueprint."""
    p1 = tmp_path / "alpha.md"
    p1.write_text(MEMORY_TEMPLATE_A.format(name="Alpha"))
    p2 = tmp_path / "gamma.md"
    p2.write_text(MEMORY_TEMPLATE_DIFFERENT.format(name="Gamma"))

    cell1, bp1, _ = ingest_memory_file(session, p1)
    cell2, bp2, _ = ingest_memory_file(session, p2)

    assert bp1 != bp2, "different frontmatter shapes should get different Blueprint NodeIDs"


def test_find_equivalent_cells_returns_structurally_equal(session, tmp_path):
    """The equivalence query returns all cells with matching Blueprint NodeIDs."""
    p1 = tmp_path / "alpha.md"
    p1.write_text(MEMORY_TEMPLATE_A.format(name="Alpha"))
    p2 = tmp_path / "beta.md"
    p2.write_text(MEMORY_TEMPLATE_A.format(name="Beta"))
    p3 = tmp_path / "gamma.md"
    p3.write_text(MEMORY_TEMPLATE_DIFFERENT.format(name="Gamma"))

    cell1, bp1, _ = ingest_memory_file(session, p1)
    cell2, bp2, _ = ingest_memory_file(session, p2)
    cell3, bp3, _ = ingest_memory_file(session, p3)

    equivalents = find_equivalent_cells(session, bp1)
    names = {c.name for c in equivalents}
    assert "Alpha" in names
    assert "Beta" in names
    # Gamma has a different shape — should NOT be in the equivalent set
    assert "Gamma" not in names


def test_lattice_stats_reflects_ingestion(session, tmp_path):
    """Stats grow as we ingest."""
    initial = lattice_stats(session)
    assert initial["cells_total"] == 0

    p = tmp_path / "x.md"
    p.write_text(MEMORY_TEMPLATE_A.format(name="X"))
    ingest_memory_file(session, p)

    after = lattice_stats(session)
    assert after["cells_total"] == 1
    assert after["blueprints_total"] >= 1


# ---------------------------------------------------------------------------
# Tolerant frontmatter parsing — colons-in-descriptions don't break us
# ---------------------------------------------------------------------------


FRONTMATTER_WITH_COLONS = textwrap.dedent("""\
    ---
    name: Memory with colons
    description: This description has: a colon. And: another. Reach for: structural reasoning.
    type: feedback
    ---
    Body.
    """)


def test_tolerant_frontmatter_handles_colons_in_descriptions(session):
    """Memory files in this body use unquoted descriptions with colons —
    strict YAML rejects them; the tolerant fallback parses them."""
    parsed = parse_markdown(FRONTMATTER_WITH_COLONS)
    assert parsed.frontmatter.get("name") == "Memory with colons"
    assert parsed.frontmatter.get("type") == "feedback"
    # The description is a string (with colons preserved), not a nested mapping
    desc = parsed.frontmatter.get("description")
    assert isinstance(desc, str)
    assert "colon" in desc
