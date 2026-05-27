"""Pin Access + MethodCall in the structural Form evaluator.

The substrate playground sends `mode="ast"` (the default) — the
structural evaluator in `form.py`. Before this test existed, the first
quest on the playground (`@concept(x).blueprint`) returned
`TypeError: Form: cannot evaluate Access` because the AST evaluator
had no branch for tree-navigation nodes. The runtime in
`form_runtime.py` knew how to resolve them; the structural evaluator
now delegates there and wraps the value back into a FormResult so the
REST surface and the UI render it through the existing code paths.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import form_evaluate_text, ingest_memory_file
from app.services.substrate.kernel import NodeID
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    from app.services.substrate.substrate_strings import SubstrateStringORM
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


def _seed_memory_cell(session):
    body = """---
name: test memory
description: a test cell for tree navigation
type: feedback
---

Body of the memory.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(body)
        path = f.name
    try:
        ingest_memory_file(session, Path(path))
        session.flush()
    finally:
        os.unlink(path)


def test_blueprint_access_returns_node_id_result(session):
    _seed_memory_cell(session)
    result = form_evaluate_text(session, '@memory("test memory").blueprint')
    assert result.kind == "node_id"
    assert isinstance(result.value, NodeID)


def test_ctor_access_returns_recipe_node_id(session):
    _seed_memory_cell(session)
    result = form_evaluate_text(session, '@memory("test memory").ctor')
    # The ctor is also a NodeID — kind is "node_id" since our wrap
    # cannot distinguish blueprint from recipe NodeIDs at this layer.
    assert result.kind == "node_id"
    assert isinstance(result.value, NodeID)


def test_nested_access_blueprint_category(session):
    _seed_memory_cell(session)
    result = form_evaluate_text(session, '@memory("test memory").blueprint.category')
    assert result.kind == "node_id"
    assert isinstance(result.value, NodeID)


def test_method_call_child_returns_node_id_result(session):
    _seed_memory_cell(session)
    result = form_evaluate_text(session, '@memory("test memory").blueprint.child(0)')
    assert result.kind == "node_id"
    assert isinstance(result.value, NodeID)


def test_primitive_field_returns_value_result(session):
    """`.nchildren` is an int — wraps as a `value` kind so the API can
    return it without forcing an artificial NodeID shape."""
    _seed_memory_cell(session)
    result = form_evaluate_text(session, '@memory("test memory").blueprint.nchildren')
    assert result.kind == "value"
    assert isinstance(result.value, int)
    assert result.value >= 3
