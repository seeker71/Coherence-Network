"""JSON-Schema frontend for mini-nums.

Surface syntax:
    {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "string"}}}

Drives the kernel via make_object_blueprint and make_list_blueprint. The point
is to demonstrate cross-language structural equivalence: a JSON-Schema integer
field reaches the same Blueprint NodeID as a calculator integer literal,
because the Integer Blueprint is shared.
"""
from __future__ import annotations
from typing import Any, Dict

from core import (
    Module, Blueprint, NodeID,
    BID_integer, BID_decimal, BID_string, BID_bool,
    make_object_blueprint, make_list_blueprint,
)


def schema_to_blueprint(module: Module, schema: Dict[str, Any], name: str = "") -> Blueprint:
    """Translate a JSON-Schema object into a NUMS Blueprint."""
    type_ = schema.get("type")
    if type_ == "integer":
        return Blueprint(module, BID_integer(), name=name or "integer")
    if type_ == "number":
        return Blueprint(module, BID_decimal(), name=name or "decimal")
    if type_ == "string":
        return Blueprint(module, BID_string(), name=name or "string")
    if type_ == "boolean":
        return Blueprint(module, BID_bool(), name=name or "bool")
    if type_ == "array":
        items_bp = schema_to_blueprint(module, schema["items"])
        return make_list_blueprint(module, items_bp.id)
    if type_ == "object":
        props = schema.get("properties", {})
        fields = []
        for fname, fschema in props.items():
            fbp = schema_to_blueprint(module, fschema)
            fields.append((fname, fbp.id))
        return make_object_blueprint(module, name or "<anon>", fields)
    raise ValueError(f"Unsupported JSON-Schema type: {type_}")
