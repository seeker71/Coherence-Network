"""Substrate-resident builders — Build/CaptureRef/Const template DSL.

Closes the most-named gap from the substrate-resident-patterns commit.
Builders no longer have to live as Python callables — they can be data:
a small template DSL that serializes to Recipe NodeIDs.

The DSL has three primitives:

  Build(class_name, **kwargs)
      Instantiate an AST class with these keyword arguments. Each kwarg
      value can be another template (Build / CaptureRef / Const) or a
      bare Python value.

  CaptureRef(name, default=...)
      Substitute the captured group `name` from the parser's captures
      dict. If the capture is missing and `default` is provided, use it.

  Const(value)
      A literal value to embed (string, int, bool, None, etc.).

Example — the `unless` builder as a template:

    unless_template = Build(
        "IfExpr",
        cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("cond")),
        then_branch=CaptureRef("body"),
        else_branch=CaptureRef("other", default=None),
    )

`execute_template(template, captures, ast_module)` walks the template
and produces an AST node.

`template_to_recipe(session, template)` serializes a template to a
Recipe NodeID. Two structurally-identical templates share NodeIDs.

`recipe_to_template(session, recipe_id)` reverses serialization.

`make_builder_from_template(template, ast_module)` returns a Python
callable suitable for `register_form_keyword`'s `builder=` parameter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session


# Sentinel to distinguish "no default provided" from "default is None"
_NO_DEFAULT = object()


# ---------------------------------------------------------------------------
# Template primitives
# ---------------------------------------------------------------------------


@dataclass
class Build:
    """Instantiate an AST class with these kwargs.

    Each kwarg value may be another template, a CaptureRef, a Const, or
    a bare Python value (treated as a Const).
    """
    class_name: str
    kwargs: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, class_name: str, **kwargs):
        self.class_name = class_name
        self.kwargs = kwargs


@dataclass
class CaptureRef:
    """Reference a captured sub-expression by name."""
    name: str
    default: Any = _NO_DEFAULT

    @property
    def has_default(self) -> bool:
        return self.default is not _NO_DEFAULT


@dataclass
class Const:
    """A literal value to embed in the build."""
    value: Any


@dataclass
class MapBuild:
    """Walk a list and apply a template per item, producing a new list.

    `items` is a template that resolves to a list (typically a
    `CaptureRef` pointing at a `RepeatedCapture`'s result).

    `each` is a template applied per item. If an item is a `dict`, its
    keys become the captures for the inner execution; if an item is a
    bare value, it's exposed as `captures["__item__"]`.

    Used to wrap structured RepeatedCapture results — for example,
    converting a list of `{pattern, body}` dicts into a list of
    `MatchArm` AST instances:

        MapBuild(
            items=CaptureRef("arms"),
            each=Build("MatchArm",
                pattern=CaptureRef("pattern"),
                body=CaptureRef("body"),
            ),
        )
    """
    items: Any
    each: Any


# ---------------------------------------------------------------------------
# Interpreter — execute a template against captures
# ---------------------------------------------------------------------------


def execute_template(template: Any, captures: Dict[str, Any], ast_module: Any) -> Any:
    """Walk the template and produce a value (typically an AST node).

    `ast_module` is the module where AST classes live (e.g.,
    `app.services.substrate.form`). Class names from Build instructions
    are resolved with `getattr(ast_module, class_name)`.
    """
    if isinstance(template, Build):
        cls = getattr(ast_module, template.class_name, None)
        if cls is None:
            raise NameError(
                f"Form template: AST class {template.class_name!r} "
                f"not found in {ast_module.__name__}"
            )
        kwargs = {
            key: execute_template(val, captures, ast_module)
            for key, val in template.kwargs.items()
        }
        return cls(**kwargs)

    if isinstance(template, CaptureRef):
        if template.name in captures:
            return captures[template.name]
        if template.has_default:
            return template.default
        raise KeyError(
            f"Form template: missing capture {template.name!r} and no default"
        )

    if isinstance(template, Const):
        return template.value

    if isinstance(template, MapBuild):
        items = execute_template(template.items, captures, ast_module)
        if not isinstance(items, list):
            raise TypeError(
                f"Form template: MapBuild items resolved to non-list "
                f"({type(items).__name__})"
            )
        out = []
        for item in items:
            if isinstance(item, dict):
                inner_captures = item
            else:
                inner_captures = {"__item__": item}
            out.append(execute_template(template.each, inner_captures, ast_module))
        return out

    # Bare value — treat as Const
    return template


def make_builder_from_template(template: Any, ast_module: Any) -> Callable[[Dict[str, Any]], Any]:
    """Wrap a template into a Python callable suitable for register_form_keyword."""
    def _builder(captures: Dict[str, Any]) -> Any:
        return execute_template(template, captures, ast_module)
    return _builder


# ---------------------------------------------------------------------------
# Serialization — templates ↔ Recipe NodeIDs
# ---------------------------------------------------------------------------
#
# Encoding:
#
#   Build(class_name, kwargs)
#     → Block.SEQUENCE [str("__build__"), str(class_name),
#                        Block.LET[str(key1), value1_recipe],
#                        Block.LET[str(key2), value2_recipe], ...]
#
#   CaptureRef(name, default=NO)
#     → Block.LET [str("__capture__"), str(name)]
#
#   CaptureRef(name, default=value)
#     → Block.LET [str("__capture__"), str(name),
#                    str("__default__"), value_recipe]
#
#   Const(value: str)
#     → str-recipe (RType.STRING)
#   Const(value: int)
#     → int-recipe (RType.INTEGER), instance encodes the value
#   Const(value: bool)
#     → bool-recipe (RType.BOOL)
#   Const(value: None)
#     → null-recipe (RType.NULL)


def _category_from_form_rules():
    """Lazy imports to avoid circular deps."""
    from app.services.substrate.category import Level, RBasic, RBlock, RCond, RType
    return Level, RBasic, RBlock, RCond, RType


def _string_id(value: str):
    """Encode a string as a trivial String recipe NodeID. Caches for round-trip."""
    from app.services.substrate.form_rules import _STRING_CACHE, _node_id_key
    from app.services.substrate.kernel import NodeID
    Level, _, _, _, RType = _category_from_form_rules()
    inst = abs(hash(value)) % (10**9) + 1
    nid = NodeID(1, Level.TRIVIAL, RType.STRING, inst)
    _STRING_CACHE[_node_id_key(nid)] = value
    return nid


def _int_id(value: int):
    from app.services.substrate.kernel import NodeID
    Level, _, _, _, RType = _category_from_form_rules()
    return NodeID(1, Level.TRIVIAL, RType.INTEGER, value + 1 if value >= 0 else 0)


def _bool_id(value: bool):
    from app.services.substrate.kernel import NodeID
    Level, _, _, _, RType = _category_from_form_rules()
    return NodeID(1, Level.TRIVIAL, RType.BOOL, 1 if value else 0)


def _null_id():
    from app.services.substrate.kernel import NodeID
    Level, _, _, _, RType = _category_from_form_rules()
    return NodeID(1, Level.TRIVIAL, RType.NULL, 0)


def _block_seq_id():
    from app.services.substrate.kernel import NodeID
    Level, RBasic, RBlock, _, _ = _category_from_form_rules()
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.SEQUENCE)


def _block_let_id():
    from app.services.substrate.kernel import NodeID
    Level, RBasic, RBlock, _, _ = _category_from_form_rules()
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.LET)


def template_to_recipe(session: Session, template: Any):
    """Serialize a template to a Recipe NodeID. Two structurally-identical
    templates share NodeIDs via the kernel's content-addressed interning."""
    from app.services.substrate.kernel import DOMAIN_RECIPE, intern_node

    if isinstance(template, Const):
        return _const_to_recipe(template.value)

    if isinstance(template, CaptureRef):
        capture_marker = _string_id("__capture__")
        name_id = _string_id(template.name)
        if not template.has_default:
            return intern_node(
                session, DOMAIN_RECIPE, _block_let_id(),
                [capture_marker, name_id],
            )
        default_marker = _string_id("__default__")
        default_id = template_to_recipe(session, _wrap_value(template.default))
        return intern_node(
            session, DOMAIN_RECIPE, _block_let_id(),
            [capture_marker, name_id, default_marker, default_id],
        )

    if isinstance(template, Build):
        build_marker = _string_id("__build__")
        class_id = _string_id(template.class_name)
        children = [build_marker, class_id]
        for key in sorted(template.kwargs.keys()):
            value = template.kwargs[key]
            key_id = _string_id(key)
            value_id = template_to_recipe(session, _wrap_value(value))
            kvpair = intern_node(
                session, DOMAIN_RECIPE, _block_let_id(),
                [key_id, value_id],
            )
            children.append(kvpair)
        return intern_node(
            session, DOMAIN_RECIPE, _block_seq_id(), children,
        )

    if isinstance(template, MapBuild):
        # Encoding: Block.SEQUENCE [str("__map__"), items_recipe, each_recipe]
        map_marker = _string_id("__map__")
        items_id = template_to_recipe(session, _wrap_value(template.items))
        each_id = template_to_recipe(session, _wrap_value(template.each))
        return intern_node(
            session, DOMAIN_RECIPE, _block_seq_id(),
            [map_marker, items_id, each_id],
        )

    # Bare value — wrap as Const
    return _const_to_recipe(template)


def _wrap_value(value: Any) -> Any:
    """Wrap a bare Python value as a Const if it isn't already a template."""
    if isinstance(value, (Build, CaptureRef, Const, MapBuild)):
        return value
    return Const(value)


def _const_to_recipe(value: Any):
    if isinstance(value, str):
        return _string_id(value)
    if isinstance(value, bool):
        return _bool_id(value)
    if isinstance(value, int):
        return _int_id(value)
    if value is None:
        return _null_id()
    raise TypeError(f"Form template: cannot serialize Const({value!r}) of type {type(value).__name__}")


def recipe_to_template(session: Session, recipe_id) -> Any:
    """Reverse of template_to_recipe. Returns a Build / CaptureRef / Const.

    Dispatches on the row's parsed *category* (parts[0]), NOT on the
    NodeID's type/instance — those are allocation counters within a
    (level, type) shard, not category instance markers.
    """
    from app.services.substrate.form_rules import _string_from_recipe, _parse_node_id_str
    from app.services.substrate.orm import SubstrateNodeORM

    Level, RBasic, RBlock, _, RType = _category_from_form_rules()

    # Trivial leaves are Consts
    if recipe_id.level == Level.TRIVIAL:
        if recipe_id.type_ == RType.STRING:
            return Const(value=_string_from_recipe(session, recipe_id))
        if recipe_id.type_ == RType.INTEGER:
            return Const(value=recipe_id.instance - 1 if recipe_id.instance > 0 else 0)
        if recipe_id.type_ == RType.BOOL:
            return Const(value=bool(recipe_id.instance))
        if recipe_id.type_ == RType.NULL:
            return Const(value=None)
        return Const(value=None)

    # Composite — read the row
    row = (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=recipe_id.package, level=recipe_id.level,
            type_=recipe_id.type_, instance=recipe_id.instance,
        )
        .one_or_none()
    )
    if row is None:
        raise LookupError(f"Form template: recipe {recipe_id} not found")

    parts = row.serialized.split("+")
    category = _parse_node_id_str(parts[0])
    children_ids = [_parse_node_id_str(p) for p in parts[1:]]

    # Dispatch on the *category* (the original recipe shape marker), not
    # on the result-NodeID's allocated instance.
    is_block_let = (
        category.type_ == RBasic.BLOCK and category.instance == RBlock.LET
    )
    is_block_seq = (
        category.type_ == RBasic.BLOCK and category.instance == RBlock.SEQUENCE
    )

    # Block.LET shape — CaptureRef
    if is_block_let and len(children_ids) >= 2:
        first_str = _string_from_recipe(session, children_ids[0])
        if first_str == "__capture__":
            name = _string_from_recipe(session, children_ids[1])
            if len(children_ids) >= 4:
                # name + __default__ + default-value
                default_template = recipe_to_template(session, children_ids[3])
                default_value = (
                    default_template.value
                    if isinstance(default_template, Const)
                    else default_template
                )
                return CaptureRef(name=name, default=default_value)
            return CaptureRef(name=name)

    # Block.SEQUENCE shape — could be Build, MapBuild, or other markers
    if is_block_seq and len(children_ids) >= 2:
        first_str = _string_from_recipe(session, children_ids[0])

        if first_str == "__build__":
            class_name = _string_from_recipe(session, children_ids[1])
            kwargs: Dict[str, Any] = {}
            for kvpair_id in children_ids[2:]:
                # Each kvpair is a Block.LET with [key-string, value-recipe]
                kvpair_row = (
                    session.query(SubstrateNodeORM)
                    .filter_by(
                        package=kvpair_id.package, level=kvpair_id.level,
                        type_=kvpair_id.type_, instance=kvpair_id.instance,
                    )
                    .one_or_none()
                )
                if kvpair_row is None:
                    continue
                kvparts = kvpair_row.serialized.split("+")
                if len(kvparts) < 3:
                    continue
                kv_children = [_parse_node_id_str(p) for p in kvparts[1:]]
                key_str = _string_from_recipe(session, kv_children[0])
                value_template = recipe_to_template(session, kv_children[1])
                kwargs[key_str] = value_template
            build = Build(class_name)
            build.kwargs = kwargs
            return build

        if first_str == "__map__" and len(children_ids) == 3:
            items = recipe_to_template(session, children_ids[1])
            each = recipe_to_template(session, children_ids[2])
            return MapBuild(items=items, each=each)

    raise ValueError(
        f"Form template: unrecognized shape at {recipe_id} "
        f"(category={category}, children={len(children_ids)})"
    )
