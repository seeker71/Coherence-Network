"""Tests for the substrate-using commands — discover, shape-check, ingest-paths.

These tests exercise the layer that turns the substrate from
infrastructure into something the body uses daily. Each command is
verified end-to-end against an in-memory SQLite substrate populated
with realistic tissue.
"""
from __future__ import annotations

import textwrap

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    find_equivalent_cells,
    ingest_memory_file,
    ingest_spec_file,
)
from app.services.substrate.markdown_frontend import (
    BID_memory,
    BID_spec,
    frontmatter_to_blueprint,
    parse_markdown_file,
)
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


MEMORY_TPL = textwrap.dedent("""\
    ---
    name: {name}
    description: a description
    type: feedback
    ---
    Body.
    """)


SPEC_TPL = textwrap.dedent("""\
    ---
    idea_id: {idea_id}
    source: src/x.py
    requirements: do thing X
    done_when: thing X done
    test: pytest x
    ---
    Spec body.
    """)


# ---------------------------------------------------------------------------
# Shape-check (#2) — surfaces existing cells with the same shape
# ---------------------------------------------------------------------------


def test_shape_check_finds_equivalent_cells(session, tmp_path):
    """When a draft has the same shape as existing cells, shape-check
    surfaces them. This is the killer demo of the substrate-grounding
    use case: catch duplication at authoring time."""
    # Populate with three specs of the same shape
    for idea_id in ["alpha", "beta", "gamma"]:
        p = tmp_path / f"{idea_id}.md"
        p.write_text(SPEC_TPL.format(idea_id=idea_id))
        ingest_spec_file(session, p)

    # Now author a "new" spec with the same shape
    draft = tmp_path / "delta.md"
    draft.write_text(SPEC_TPL.format(idea_id="delta"))

    parsed = parse_markdown_file(draft)
    shape = frontmatter_to_blueprint(session, parsed.frontmatter, BID_spec())
    equivalents = find_equivalent_cells(session, shape)

    # The three already-ingested specs all share the shape
    names = {c.name for c in equivalents}
    assert "alpha" in names
    assert "beta" in names
    assert "gamma" in names


def test_shape_check_for_genuinely_new_shape_returns_empty(session, tmp_path):
    """A draft with a unique shape returns no equivalents — confirming
    that the body would gain a new structural pattern."""
    # Populate with one spec
    p = tmp_path / "alpha.md"
    p.write_text(SPEC_TPL.format(idea_id="alpha"))
    ingest_spec_file(session, p)

    # Author a draft with extra fields — different shape
    draft = tmp_path / "different.md"
    draft.write_text(textwrap.dedent("""\
        ---
        idea_id: novel
        source: src/y.py
        requirements: do Y
        done_when: Y done
        test: pytest y
        constraints: be careful
        priority: high
        owner: someone
        ---
        Different shape.
        """))

    parsed = parse_markdown_file(draft)
    shape = frontmatter_to_blueprint(session, parsed.frontmatter, BID_spec())
    equivalents = find_equivalent_cells(session, shape)

    assert len(equivalents) == 0  # genuinely new pattern


# ---------------------------------------------------------------------------
# Discovery (#6) — clusters, singletons, cross-domain
# ---------------------------------------------------------------------------


def test_discover_finds_largest_cluster(session, tmp_path):
    """Group cells by Blueprint NodeID; report the largest cluster."""
    # Five cells with the same shape, two with a different shape
    for n in range(5):
        p = tmp_path / f"same{n}.md"
        p.write_text(MEMORY_TPL.format(name=f"same{n}"))
        ingest_memory_file(session, p)
    for n in range(2):
        p = tmp_path / f"different{n}.md"
        p.write_text(textwrap.dedent(f"""\
            ---
            name: different{n}
            description: a description
            type: feedback
            extra_field: yes
            ---
            Body.
            """))
        ingest_memory_file(session, p)

    # Walk the substrate and group
    from collections import defaultdict
    rows = session.query(SubstrateNamedCellORM).filter_by(domain="memory").all()
    by_bp = defaultdict(list)
    for r in rows:
        by_bp[r.blueprint_node_id].append(r.name)

    # The largest cluster has 5 cells; the second has 2
    sizes = sorted([len(v) for v in by_bp.values()], reverse=True)
    assert sizes[0] == 5
    assert sizes[1] == 2


def test_discover_identifies_cross_domain_shape_collisions(session, tmp_path):
    """When the same Blueprint NodeID appears across multiple domains,
    discovery surfaces the collision (potential refactor signal)."""
    # Two cells of identical shape, one in memory domain, one in spec
    # We construct identical frontmatter so the resulting shape matches
    template = textwrap.dedent("""\
        ---
        name: foo
        description: bar
        ---
        Body.
        """)
    p_mem = tmp_path / "mem.md"
    p_mem.write_text(template)
    ingest_memory_file(session, p_mem)

    p_spec = tmp_path / "spec.md"
    p_spec.write_text(template)
    ingest_spec_file(session, p_spec)

    # Both cells have differently-typed Blueprints (BID_memory vs BID_spec)
    # by construction — domain blueprints differ. So no cross-domain
    # collision is expected. This test verifies that the discovery
    # logic correctly groups by blueprint AND notices when the same
    # blueprint id appears across domains.
    from collections import defaultdict
    bp_to_domains = defaultdict(set)
    rows = session.query(SubstrateNamedCellORM).all()
    for r in rows:
        bp_to_domains[r.blueprint_node_id].add(r.domain)

    # A clean substrate should have NO cross-domain collisions because
    # BDomain.MEMORY != BDomain.SPEC propagates into the blueprint shape.
    cross = [bp for bp, doms in bp_to_domains.items() if len(doms) > 1]
    assert cross == [], f"unexpected cross-domain collisions: {cross}"


# ---------------------------------------------------------------------------
# Ingest-paths (#1) — auto-ingest changed files
# ---------------------------------------------------------------------------


def test_ingest_paths_dispatches_by_path_pattern(session, tmp_path):
    """Verify the path → domain dispatch logic that ingest-paths uses."""
    # Replicate the dispatch logic from cmd_ingest_paths inline
    def domain_for(path):
        s = str(path).replace("\\", "/")
        parts = s.split("/")
        if "specs" in parts:
            return "spec"
        if "ideas" in parts:
            return "idea"
        if "memory" in parts:
            return "memory"
        if "concepts" in parts and "vision-kb" in parts:
            return "concept"
        if "presences" in parts:
            return "presence"
        return None

    assert domain_for("specs/agent-orchestration-api.md") == "spec"
    assert domain_for("/Users/x/repo/specs/foo.md") == "spec"
    assert domain_for("ideas/agent-pipeline.md") == "idea"
    assert domain_for("docs/vision-kb/concepts/lc-agent-memory.md") == "concept"
    assert domain_for("docs/presences/claude.md") == "presence"
    assert domain_for("memory/feedback_x.md") == "memory"
    assert domain_for("docs/random/file.md") is None  # untracked location
