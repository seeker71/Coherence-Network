"""Read-only projection helpers for persisted substrate recipes.

This module decodes values already interned by the native Form kernels.  It
does not parse, evaluate, compile, or execute Form; execution authority lives
exclusively in the pinned ``form/`` submodule.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import tuple_
from sqlalchemy.orm import Session

from app.services.substrate.kernel import NamedCell, NodeID, lookup_node
from app.services.substrate.orm import SubstrateNodeORM
from app.services.substrate.substrate_strings import SubstrateStringORM


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
        if (
            binding_category.type_ != RBasic.BLOCK.value
            or binding_category.instance != 3
        ):
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


def _node_coordinates(node: NodeID) -> tuple[int, int, int, int]:
    return node.package, node.level, node.type_, node.instance


def _binding_rows(
    session: Session,
    binding_ids: list[NodeID],
) -> dict[tuple[int, int, int, int], SubstrateNodeORM]:
    coordinates = [_node_coordinates(node) for node in binding_ids]
    rows = (
        session.query(SubstrateNodeORM)
        .filter(
            tuple_(
                SubstrateNodeORM.package,
                SubstrateNodeORM.level,
                SubstrateNodeORM.type_,
                SubstrateNodeORM.instance,
            ).in_(coordinates)
        )
        .all()
    )
    return {_node_coordinates(NodeID(row.package, row.level, row.type_, row.instance)): row for row in rows}


def _structured_bindings(
    binding_ids: list[NodeID],
    rows_by_node: dict[tuple[int, int, int, int], SubstrateNodeORM],
) -> list[tuple[NodeID, NodeID]]:
    from app.services.substrate.category import RBasic

    bindings: list[tuple[NodeID, NodeID]] = []
    for binding in binding_ids:
        row = rows_by_node.get(_node_coordinates(binding))
        if row is None or not row.serialized:
            continue
        parts = row.serialized.split("+")
        category = parse_node_id(parts[0])
        if category.type_ != RBasic.BLOCK.value or category.instance != 3:
            continue
        if len(parts) == 3:
            bindings.append((parse_node_id(parts[1]), parse_node_id(parts[2])))
    return bindings


def _binding_strings(
    session: Session,
    bindings: list[tuple[NodeID, NodeID]],
) -> dict[int, str]:
    from app.services.substrate.category import Level, RType

    instances = {
        node.instance
        for binding in bindings
        for node in binding
        if node.level == Level.TRIVIAL and node.type_ in (RType.STRING, RType.SLUG)
    }
    if not instances:
        return {}
    return {
        row.instance: row.value
        for row in session.query(SubstrateStringORM)
        .filter(SubstrateStringORM.instance.in_(instances))
        .all()
    }


def _project_batched_trivial(node: NodeID, strings: dict[int, str]) -> Any:
    from app.services.substrate.category import Level, RType

    if node.level != Level.TRIVIAL:
        raise ValueError
    if node.type_ == RType.NULL:
        return None
    if node.type_ == RType.BOOL:
        return node.instance == 1
    if node.type_ == RType.INTEGER:
        return node.instance - 1 if node.instance > 0 else 0
    if node.type_ in (RType.STRING, RType.SLUG):
        return strings.get(node.instance, "")
    raise ValueError


def ctor_fields(
    session: Session,
    ctor: Any,
    fields: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Project a structured CTOR in a constant number of database reads.

    ``ctor_field_lookup`` is the convenient single-field lens. Calling it for
    every field in a record repeatedly walks the complete binding tree and
    turns an N-field projection into O(N²) node lookups. Runtime records such
    as deployment witnesses are whole values, so read their CTOR, bindings,
    and string leaves as three set-based queries instead.
    """
    from app.services.substrate.category import RBasic

    if ctor is None or not isinstance(ctor, NodeID):
        return {}
    ctor_row = lookup_node(session, ctor)
    if ctor_row is None or not ctor_row.serialized:
        return {}
    ctor_parts = ctor_row.serialized.split("+")
    category = parse_node_id(ctor_parts[0])
    if category.type_ != RBasic.BLOCK.value:
        return {}

    binding_ids = [parse_node_id(part) for part in ctor_parts[1:]]
    if not binding_ids:
        return {}
    bindings = _structured_bindings(binding_ids, _binding_rows(session, binding_ids))
    strings = _binding_strings(session, bindings)
    requested = set(fields) if fields is not None else None
    projected: dict[str, Any] = {}
    for key_node, value_node in bindings:
        try:
            key = _project_batched_trivial(key_node, strings)
        except ValueError:
            continue
        if not isinstance(key, str) or (requested is not None and key not in requested):
            continue
        try:
            projected[key] = _project_batched_trivial(value_node, strings)
        except ValueError:
            projected[key] = value_node
    return projected


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
