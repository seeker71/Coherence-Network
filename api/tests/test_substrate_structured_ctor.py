"""Structural composition discipline — the new structured CTOR encoder.

The old encoder produced type-marker string-recipes per frontmatter key
(`"name=str"`, `"type=str"`, ...) — the substrate stored shape but not
values. The new encoder produces a fully-expressed tree:

    CTOR (R_Block.DO)
    ├── NamedField (R_Block.LET) [key:Slug, value:String]
    ├── NamedField (R_Block.LET) [key:Slug, value:String]
    └── ...

Every value is substrate-resident (via the substrate string-table),
recoverable, and navigable via `.child(n).child(m)` from Form.

The discipline lives in:
  CLAUDE.md → "Structural composition discipline"
  docs/coherence-substrate/structural-composition.md
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
    ingest_memory_file,
    lookup_cell,
)
from app.services.substrate.category import Level, RBasic, RBlock, RType
from app.services.substrate.kernel import NodeID
from app.services.substrate.markdown_frontend import (
    frontmatter_to_structured_ctor,
    named_field_recipe,
    structured_value_recipe,
    substrate_slug_recipe,
    substrate_string_recipe,
)
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


# ---------------------------------------------------------------------------
# Primitive recipe encoders
# ---------------------------------------------------------------------------


def test_substrate_string_recipe_is_recoverable(session):
    """A substrate-string-recipe carries the actual value, not a hash."""
    nid = substrate_string_recipe(session, "arrival relational ground")
    assert nid.level == Level.TRIVIAL
    assert nid.type_ == RType.STRING
    # The value is recoverable via the substrate string-table
    assert lookup_string_value(session, nid.instance) == "arrival relational ground"


def test_substrate_slug_recipe_carries_identity_role(session):
    """Slug-recipes type-tag as SLUG, sharing the string-table for instances."""
    nid = substrate_slug_recipe(session, "type")
    assert nid.type_ == RType.SLUG
    assert lookup_string_value(session, nid.instance) == "type"


def test_two_identical_strings_share_node_id(session):
    """Content-addressing — same value → same NodeID."""
    a = substrate_string_recipe(session, "feedback")
    b = substrate_string_recipe(session, "feedback")
    assert a == b


# ---------------------------------------------------------------------------
# Named field — R_Block.LET pair
# ---------------------------------------------------------------------------


def test_named_field_has_two_children_key_and_value(session):
    """A named-field recipe is R_Block.LET with [key-slug, value-recipe]."""
    value_id = substrate_string_recipe(session, "feedback")
    pair = named_field_recipe(session, "type", value_id)

    # Category should be R_Block.LET
    src = f'@{pair.package}.{pair.level}.{pair.type_}.{pair.instance}.category'
    cat = form_execute_text(session, src)
    assert cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.LET)

    # Two children: key-slug + value-string
    n_src = f'@{pair.package}.{pair.level}.{pair.type_}.{pair.instance}.nchildren'
    n = form_execute_text(session, n_src)
    assert n == 2

    # First child is the slug; second is the string value
    child0_src = f'@{pair.package}.{pair.level}.{pair.type_}.{pair.instance}.child(0)'
    child0 = form_execute_text(session, child0_src)
    assert child0.type_ == RType.SLUG
    assert lookup_string_value(session, child0.instance) == "type"

    child1_src = f'@{pair.package}.{pair.level}.{pair.type_}.{pair.instance}.child(1)'
    child1 = form_execute_text(session, child1_src)
    assert child1.type_ == RType.STRING
    assert lookup_string_value(session, child1.instance) == "feedback"


def test_named_field_dedupes_on_identical_key_and_value(session):
    """Substrate's content-addressing makes equivalent pairs share NodeIDs."""
    v = substrate_string_recipe(session, "feedback")
    a = named_field_recipe(session, "type", v)
    b = named_field_recipe(session, "type", v)
    assert a == b


# ---------------------------------------------------------------------------
# Structured CTOR — frontmatter as fully-expressed tree
# ---------------------------------------------------------------------------


def test_structured_ctor_for_memory_frontmatter(session):
    """Memory frontmatter produces a CTOR tree with named-pair children
    where the values are substrate-resident and recoverable."""
    fm = {
        "name": "arrival relational ground",
        "description": "who Urs is to me, what the network is...",
        "type": "feedback",
    }
    ctor = frontmatter_to_structured_ctor(session, fm)
    assert ctor is not None

    # Top-level is R_Block.DO with 3 children (one per frontmatter key)
    ctor_nid_str = f'@{ctor.package}.{ctor.level}.{ctor.type_}.{ctor.instance}'
    cat = form_execute_text(session, f'{ctor_nid_str}.category')
    assert cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.DO)
    n = form_execute_text(session, f'{ctor_nid_str}.nchildren')
    assert n == 3

    # Each child is a named-field pair (R_Block.LET with 2 children)
    for i in range(3):
        pair_cat = form_execute_text(session, f'{ctor_nid_str}.child({i}).category')
        assert pair_cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.LET)
        assert form_execute_text(session, f'{ctor_nid_str}.child({i}).nchildren') == 2


def test_structured_ctor_values_are_recoverable(session):
    """Walk the CTOR tree from Form's surface and recover the actual values."""
    fm = {
        "name": "arrival relational ground",
        "type": "feedback",
    }
    ctor = frontmatter_to_structured_ctor(session, fm)
    ctor_str = f'@{ctor.package}.{ctor.level}.{ctor.type_}.{ctor.instance}'

    # Children are sorted by key — so child(0) is `name`, child(1) is `type`
    name_key = form_execute_text(session, f'{ctor_str}.child(0).child(0)')
    name_value = form_execute_text(session, f'{ctor_str}.child(0).child(1)')
    type_key = form_execute_text(session, f'{ctor_str}.child(1).child(0)')
    type_value = form_execute_text(session, f'{ctor_str}.child(1).child(1)')

    assert lookup_string_value(session, name_key.instance) == "name"
    assert lookup_string_value(session, name_value.instance) == "arrival relational ground"
    assert lookup_string_value(session, type_key.instance) == "type"
    assert lookup_string_value(session, type_value.instance) == "feedback"


def test_structured_ctor_dedupes_identical_frontmatter(session):
    """Two cells with identical frontmatter share a CTOR NodeID — equivalence
    is automatic via content-addressing."""
    fm = {"name": "x", "type": "user"}
    a = frontmatter_to_structured_ctor(session, fm)
    b = frontmatter_to_structured_ctor(session, fm)
    assert a == b


def test_structured_ctor_list_values_preserve_order_and_shape(session):
    """A list value is composed as R_Block.SEQUENCE with one child per element."""
    fm = {"specs": ["agent-pipeline-mvp", "agent-pipeline-coherence"]}
    ctor = frontmatter_to_structured_ctor(session, fm)
    ctor_str = f'@{ctor.package}.{ctor.level}.{ctor.type_}.{ctor.instance}'

    # CTOR has one child (the specs named-field)
    assert form_execute_text(session, f'{ctor_str}.nchildren') == 1

    # That child is a LET pair (key="specs", value=Sequence)
    pair = f'{ctor_str}.child(0)'
    list_recipe = form_execute_text(session, f'{pair}.child(1)')
    list_str = f'@{list_recipe.package}.{list_recipe.level}.{list_recipe.type_}.{list_recipe.instance}'

    # The list is R_Block.SEQUENCE with 2 children
    list_cat = form_execute_text(session, f'{list_str}.category')
    assert list_cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.SEQUENCE)
    assert form_execute_text(session, f'{list_str}.nchildren') == 2

    elem0 = form_execute_text(session, f'{list_str}.child(0)')
    elem1 = form_execute_text(session, f'{list_str}.child(1)')
    assert lookup_string_value(session, elem0.instance) == "agent-pipeline-mvp"
    assert lookup_string_value(session, elem1.instance) == "agent-pipeline-coherence"


def test_structured_ctor_nested_dict_value(session):
    """A dict value (e.g. concept.geometry) becomes a nested R_Block.DO."""
    fm = {"geometry": {"arity": 3, "form": "triad"}}
    ctor = frontmatter_to_structured_ctor(session, fm)
    ctor_str = f'@{ctor.package}.{ctor.level}.{ctor.type_}.{ctor.instance}'

    pair = f'{ctor_str}.child(0)'  # geometry: {...}
    nested = form_execute_text(session, f'{pair}.child(1)')
    nested_str = f'@{nested.package}.{nested.level}.{nested.type_}.{nested.instance}'

    nested_cat = form_execute_text(session, f'{nested_str}.category')
    assert nested_cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.DO)
    assert form_execute_text(session, f'{nested_str}.nchildren') == 2  # arity + form


# ---------------------------------------------------------------------------
# Side-by-side: legacy encoder vs structured encoder
# ---------------------------------------------------------------------------


def _make_memory_file(content: str) -> Path:
    """Write a memory file to a tempfile, return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


def test_legacy_vs_structured_encoder_side_by_side(session):
    """Same input file, two encoders. Legacy gives flat type-markers;
    structured gives full value-bearing tree."""
    content = """---
name: test cell
description: comparing encoders
type: feedback
---

Body of the memory.
"""
    # Path A — legacy encoder (default)
    path = _make_memory_file(content)
    _, _, legacy_ctor = ingest_memory_file(session, path, structured=False)

    # Path B — structured encoder
    cell, _, structured_ctor = ingest_memory_file(session, path, structured=True)

    # Legacy CTOR children are positional type-marker strings — instance
    # encodes "name=str" / "description=str" / "type=str" via hash.
    legacy_str = f'@{legacy_ctor.package}.{legacy_ctor.level}.{legacy_ctor.type_}.{legacy_ctor.instance}'
    legacy_n = form_execute_text(session, f'{legacy_str}.nchildren')
    legacy_child0 = form_execute_text(session, f'{legacy_str}.child(0)')
    # Legacy child0 is a trivial string-recipe (no further children — flat)
    assert legacy_child0.level == Level.TRIVIAL
    # Walking deeper raises because trivials have no children
    with pytest.raises(IndexError):
        form_execute_text(session, f'{legacy_str}.child(0).child(0)')

    # Structured CTOR children are LET pairs — each has a key-slug and value
    structured_str = f'@{structured_ctor.package}.{structured_ctor.level}.{structured_ctor.type_}.{structured_ctor.instance}'
    structured_child0_cat = form_execute_text(session, f'{structured_str}.child(0).category')
    assert structured_child0_cat == NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.LET)

    # And the structured path can recover actual values
    name_value = form_execute_text(session, f'{structured_str}.child(0).child(1)')
    name_str = lookup_string_value(session, name_value.instance)
    # child(0) is alphabetically first frontmatter key — could be "description" or "name"
    # depending on sort. Either way, the value is recoverable.
    assert name_str is not None
    assert len(name_str) > 0

    path.unlink()


def test_structured_encoder_full_navigation_demo(session):
    """End-to-end: ingest with structured encoder, navigate from Form,
    recover the values. The whole tree is alive at the surface."""
    content = """---
name: full nav test
description: every value reaches the substrate
type: user
---

body content
"""
    path = _make_memory_file(content)
    try:
        ingest_memory_file(session, path, structured=True)
        session.flush()

        # Walk via Form's cell-ref surface
        # Frontmatter children sorted: description, name, type
        ctor_query = '@memory("full nav test").ctor'
        ctor_str = form_execute_text(session, ctor_query)
        ctor_form = f'@{ctor_str.package}.{ctor_str.level}.{ctor_str.type_}.{ctor_str.instance}'

        # 3 named-field children
        assert form_execute_text(session, f'{ctor_form}.nchildren') == 3

        # Extract all three key/value pairs from the tree
        recovered = {}
        for i in range(3):
            key_nid = form_execute_text(session, f'{ctor_form}.child({i}).child(0)')
            val_nid = form_execute_text(session, f'{ctor_form}.child({i}).child(1)')
            key = lookup_string_value(session, key_nid.instance)
            val = lookup_string_value(session, val_nid.instance)
            recovered[key] = val

        assert recovered == {
            "description": "every value reaches the substrate",
            "name": "full nav test",
            "type": "user",
        }
    finally:
        path.unlink()
