"""Read-only projection helpers for persisted substrate recipes.

This module decodes values already interned by the native Form kernels.  It
does not parse, evaluate, compile, or execute Form; execution authority lives
exclusively in the pinned ``form/`` submodule.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.substrate.kernel import NamedCell, NodeID, lookup_node


def parse_node_id(value: str) -> NodeID:
    package, level, type_, instance = value.split(".")
    return NodeID(int(package), int(level), int(type_), int(instance))


def node_category(session: Session, node_id: NodeID) -> NodeID:
    row = lookup_node(session, node_id)
    if row is None or not row.serialized:
        return node_id
    parts = row.serialized.split("+")
    return node_id if len(parts) <= 1 else parse_node_id(parts[0])


def node_children(session: Session, node_id: NodeID) -> list[NodeID]:
    row = lookup_node(session, node_id)
    if row is None or not row.serialized:
        return []
    parts = row.serialized.split("+")
    return [] if len(parts) <= 1 else [parse_node_id(part) for part in parts[1:]]


def trivial_value(session: Session, node_id: NodeID) -> Any:
    from app.services.substrate.category import Level, RType
    from app.services.substrate.substrate_strings import lookup_string_value

    if node_id.level != Level.TRIVIAL:
        raise ValueError(f"atomic value requires a trivial node, got {node_id}")
    if node_id.type_ == RType.NULL:
        return None
    if node_id.type_ == RType.BOOL:
        return node_id.instance == 1
    if node_id.type_ == RType.INTEGER:
        return node_id.instance - 1 if node_id.instance > 0 else 0
    if node_id.type_ in (RType.STRING, RType.SLUG):
        return lookup_string_value(session, node_id.instance) or ""
    raise ValueError(f"no atomic projection for substrate type {node_id.type_}")


def ctor_field_lookup(session: Session, ctor: Any, field: str) -> Any:
    """Read a named binding from the persisted structured-CTOR shape."""
    from app.services.substrate.category import RBasic

    if ctor is None or not isinstance(ctor, NodeID):
        return None
    category = node_category(session, ctor)
    if category.type_ != RBasic.BLOCK.value:
        return None
    for binding in node_children(session, ctor):
        binding_category = node_category(session, binding)
        if binding_category.type_ != RBasic.BLOCK.value or binding_category.instance != 3:
            continue
        children = node_children(session, binding)
        if len(children) != 2:
            continue
        try:
            key = trivial_value(session, children[0])
        except (ValueError, AttributeError):
            continue
        if key != field:
            continue
        try:
            return trivial_value(session, children[1])
        except (ValueError, AttributeError):
            return children[1]
    return None


def resolve_access(session: Session, target: Any, field: str) -> Any:
    """Project a persisted cell/node field without executing Form."""
    if isinstance(target, dict):
        if field in target:
            return target[field]
        raise AttributeError(field)
    if isinstance(target, NamedCell):
        builtins = {
            "blueprint": target.blueprint,
            "ctor": target.ctor,
            "base": target.base,
            "access": target.access,
            "name": target.name,
            "domain": target.domain,
            "source": target.source_path,
        }
        if field in builtins:
            return builtins[field]
        projected = ctor_field_lookup(session, target.ctor, field)
        if projected is not None:
            return projected
        raise AttributeError(field)
    if isinstance(target, NodeID):
        builtins = {
            "package": target.package,
            "level": target.level,
            "type": target.type_,
            "type_": target.type_,
            "instance": target.instance,
        }
        if field in builtins:
            return builtins[field]
        if field == "category":
            return node_category(session, target)
        if field == "children":
            return node_children(session, target)
        if field == "nchildren":
            return len(node_children(session, target))
        if field == "value":
            return trivial_value(session, target)
        projected = ctor_field_lookup(session, target, field)
        if projected is not None:
            return projected
        raise AttributeError(field)
    raise TypeError(f"cannot project {field!r} from {type(target).__name__}")


# Temporary aliases for callers migrated from the retired Python evaluator.
_ctor_field_lookup = ctor_field_lookup
_node_category = node_category
_node_children = node_children
_resolve_access = resolve_access
_trivial_value = trivial_value
