"""Tests for substrate-resident builders (Build/CaptureRef/Const DSL).

Closes the most-named gap from the substrate-resident-patterns commit.
A keyword's builder can now live as data in the substrate — not just
Python memory. After process restart, the builder is reconstructed from
its template recipe with no Python re-registration needed.

The killer test: register `unless` with a template (NOT a callable),
persist, drop the in-memory registration, reload entirely from
substrate, parse `unless x then y else z`, get the same Recipe NodeID
as the bootstrap `if !x then y else z`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    Build,
    Capture,
    CaptureRef,
    Const,
    Literal,
    MapBuild,
    NodeID,
    Opt,
    Sequence,
    execute_template,
    form_evaluate_text,
    form_parse,
    load_keyword_from_substrate,
    make_builder_from_template,
    pattern_to_recipe,
    recipe_to_pattern,
    recipe_to_template,
    register_form_keyword,
    template_to_recipe,
    unregister_form_keyword,
)
from app.services.substrate.form import IfExpr, UnaryOp
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
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture(autouse=True)
def clean_keyword_registry():
    from app.services.substrate.form_rules import _KEYWORDS, _BUILDERS
    saved_kw = dict(_KEYWORDS)
    saved_b = dict(_BUILDERS)
    yield
    _KEYWORDS.clear()
    _KEYWORDS.update(saved_kw)
    _BUILDERS.clear()
    _BUILDERS.update(saved_b)


# ---------------------------------------------------------------------------
# Template execution
# ---------------------------------------------------------------------------


def test_const_executes_to_value():
    """A Const template returns its value, regardless of captures."""
    from app.services.substrate import form as ast_module
    assert execute_template(Const("hello"), {}, ast_module) == "hello"
    assert execute_template(Const(42), {}, ast_module) == 42
    assert execute_template(Const(None), {}, ast_module) is None


def test_capture_ref_substitutes_from_dict():
    from app.services.substrate import form as ast_module
    captures = {"foo": "the_value"}
    assert execute_template(CaptureRef("foo"), captures, ast_module) == "the_value"


def test_capture_ref_uses_default_when_missing():
    from app.services.substrate import form as ast_module
    assert execute_template(CaptureRef("missing", default=None), {}, ast_module) is None
    assert execute_template(CaptureRef("missing", default="fallback"), {}, ast_module) == "fallback"


def test_capture_ref_raises_when_missing_no_default():
    from app.services.substrate import form as ast_module
    with pytest.raises(KeyError):
        execute_template(CaptureRef("missing"), {}, ast_module)


def test_build_creates_ast_node():
    """Build instantiates an AST class with given kwargs."""
    from app.services.substrate import form as ast_module
    template = Build("UnaryOp", op=Const("!"), operand=Const("dummy"))
    result = execute_template(template, {}, ast_module)
    assert isinstance(result, UnaryOp)
    assert result.op == "!"


def test_nested_build_with_capture_ref():
    """A Build template with nested Build + CaptureRef builds the right AST tree."""
    from app.services.substrate import form as ast_module
    from app.services.substrate.form import Identifier
    template = Build(
        "IfExpr",
        cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("cond")),
        then_branch=CaptureRef("body"),
        else_branch=CaptureRef("other", default=None),
    )
    captures = {"cond": Identifier("x"), "body": Identifier("y")}
    result = execute_template(template, captures, ast_module)
    assert isinstance(result, IfExpr)
    assert isinstance(result.cond, UnaryOp)
    assert isinstance(result.cond.operand, Identifier)
    assert result.cond.operand.name == "x"
    assert isinstance(result.then_branch, Identifier)
    assert result.then_branch.name == "y"
    assert result.else_branch is None


# ---------------------------------------------------------------------------
# Template serialization round-trip
# ---------------------------------------------------------------------------


def test_const_round_trip(session):
    rid = template_to_recipe(session, Const("hello"))
    rebuilt = recipe_to_template(session, rid)
    assert isinstance(rebuilt, Const)
    assert rebuilt.value == "hello"


def test_capture_ref_round_trip_no_default(session):
    rid = template_to_recipe(session, CaptureRef("cond"))
    rebuilt = recipe_to_template(session, rid)
    assert isinstance(rebuilt, CaptureRef)
    assert rebuilt.name == "cond"
    assert not rebuilt.has_default


def test_capture_ref_round_trip_with_default(session):
    rid = template_to_recipe(session, CaptureRef("other", default=None))
    rebuilt = recipe_to_template(session, rid)
    assert isinstance(rebuilt, CaptureRef)
    assert rebuilt.name == "other"
    assert rebuilt.has_default
    assert rebuilt.default is None


def test_build_round_trip(session):
    template = Build(
        "IfExpr",
        cond=CaptureRef("cond"),
        then_branch=CaptureRef("body"),
    )
    rid = template_to_recipe(session, template)
    rebuilt = recipe_to_template(session, rid)
    assert isinstance(rebuilt, Build)
    assert rebuilt.class_name == "IfExpr"
    assert "cond" in rebuilt.kwargs
    assert "then_branch" in rebuilt.kwargs


def test_template_dedup_in_substrate(session):
    """Two structurally-identical templates share Recipe NodeIDs."""
    a = template_to_recipe(session, Build("UnaryOp", op=Const("!"), operand=CaptureRef("x")))
    b = template_to_recipe(session, Build("UnaryOp", op=Const("!"), operand=CaptureRef("x")))
    assert a == b


def test_nested_build_round_trip(session):
    """The full unless-template round-trips structurally."""
    template = Build(
        "IfExpr",
        cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("cond")),
        then_branch=CaptureRef("body"),
        else_branch=CaptureRef("other", default=None),
    )
    rid = template_to_recipe(session, template)
    rebuilt = recipe_to_template(session, rid)
    assert isinstance(rebuilt, Build)
    assert rebuilt.class_name == "IfExpr"
    cond_template = rebuilt.kwargs["cond"]
    assert isinstance(cond_template, Build)
    assert cond_template.class_name == "UnaryOp"


# ---------------------------------------------------------------------------
# Killer test — register with template, reload from substrate, parse
# ---------------------------------------------------------------------------


def _unless_pattern():
    return Sequence([
        Literal("IDENT", "unless"),
        Capture("cond"),
        Literal("IDENT", "then"),
        Capture("body"),
        Opt(Sequence([
            Literal("IDENT", "else"),
            Capture("other"),
        ])),
    ])


def _unless_template():
    return Build(
        "IfExpr",
        cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("cond")),
        then_branch=CaptureRef("body"),
        else_branch=CaptureRef("other", default=None),
    )


def test_register_with_template_parses(session):
    """Register `unless` using a template (not a callable). Parse it."""
    register_form_keyword(
        "unless", _unless_pattern(), template=_unless_template(), session=session,
    )
    ast = form_parse("unless x then y")
    assert isinstance(ast, IfExpr)
    assert isinstance(ast.cond, UnaryOp)


def test_template_evaluates_to_same_recipe_as_bootstrap(session):
    """Template-built `unless` produces the SAME Recipe NodeID as
    the hardcoded `if !x` bootstrap."""
    register_form_keyword(
        "unless", _unless_pattern(), template=_unless_template(), session=session,
    )
    a = form_evaluate_text(session, "unless x then y else z")
    b = form_evaluate_text(session, "if !x then y else z")
    assert a.value == b.value


# ---------------------------------------------------------------------------
# MapBuild — walking lists, applying templates per item
# ---------------------------------------------------------------------------


def test_mapbuild_executes_over_dict_list():
    """When items are dicts, each becomes the captures for the inner template."""
    from app.services.substrate import form as ast_module
    from app.services.substrate.form import MatchArm, Identifier

    template = MapBuild(
        items=CaptureRef("arms"),
        each=Build("MatchArm", pattern=CaptureRef("pattern"), body=CaptureRef("body")),
    )
    captures = {
        "arms": [
            {"pattern": Identifier("a"), "body": Identifier("x")},
            {"pattern": Identifier("b"), "body": Identifier("y")},
        ],
    }
    result = execute_template(template, captures, ast_module)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(arm, MatchArm) for arm in result)
    assert result[0].pattern.name == "a"
    assert result[0].body.name == "x"


def test_mapbuild_executes_over_value_list_via_item_alias():
    """When items are bare values, they're exposed as captures['__item__']."""
    from app.services.substrate import form as ast_module
    template = MapBuild(
        items=CaptureRef("xs"),
        each=Build("UnaryOp", op=Const("!"), operand=CaptureRef("__item__")),
    )
    from app.services.substrate.form import Identifier, UnaryOp
    captures = {"xs": [Identifier("a"), Identifier("b")]}
    result = execute_template(template, captures, ast_module)
    assert all(isinstance(x, UnaryOp) for x in result)
    assert result[0].operand.name == "a"


def test_mapbuild_round_trip(session):
    """A MapBuild template serializes and reconstructs."""
    template = MapBuild(
        items=CaptureRef("arms"),
        each=Build("MatchArm", pattern=CaptureRef("pattern"), body=CaptureRef("body")),
    )
    rid = template_to_recipe(session, template)
    rebuilt = recipe_to_template(session, rid)
    assert isinstance(rebuilt, MapBuild)
    assert isinstance(rebuilt.items, CaptureRef)
    assert rebuilt.items.name == "arms"
    assert isinstance(rebuilt.each, Build)
    assert rebuilt.each.class_name == "MatchArm"


def test_mapbuild_dedup_in_substrate(session):
    """Two structurally-identical MapBuild templates share Recipe NodeIDs."""
    a = template_to_recipe(session, MapBuild(
        items=CaptureRef("xs"),
        each=Build("UnaryOp", op=Const("!"), operand=CaptureRef("__item__")),
    ))
    b = template_to_recipe(session, MapBuild(
        items=CaptureRef("xs"),
        each=Build("UnaryOp", op=Const("!"), operand=CaptureRef("__item__")),
    ))
    assert a == b


def test_load_keyword_from_substrate_uses_template_no_python(session):
    """The killer: register with template, drop in-memory state entirely,
    reload from substrate, parse correctly. NO Python builder registry
    needed — the template itself is the builder.
    """
    register_form_keyword(
        "unless", _unless_pattern(), template=_unless_template(), session=session,
    )
    # Verify it works first
    ast = form_parse("unless x then y")
    assert isinstance(ast, IfExpr)

    # Simulate FULL process restart — drop both registries
    from app.services.substrate.form_rules import _KEYWORDS, _BUILDERS
    _KEYWORDS.clear()
    _BUILDERS.clear()

    # Confirm parser doesn't know `unless` anymore
    ast_again = form_parse("unless")
    from app.services.substrate.form import Identifier
    assert isinstance(ast_again, Identifier)

    # Reload from substrate — template is recovered from the action recipe
    loaded = load_keyword_from_substrate(session, "unless")
    assert loaded is not None

    # Now parse again — works without Python re-registration
    ast_final = form_parse("unless x then y else z")
    assert isinstance(ast_final, IfExpr)
    assert isinstance(ast_final.cond, UnaryOp)
    assert ast_final.else_branch is not None
