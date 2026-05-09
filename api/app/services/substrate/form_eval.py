"""Data-driven evaluator support — operator-symbol → recipe-category registry.

Closes the gap noted in the operator-self-hosting commit: when a custom
operator was registered (e.g. `%%` at PERCENT), the parser produced a
valid `BinOp(op="%%", ...)` AST, but the evaluator (`_to_recipe_node_id`
in form.py) had a hardcoded switch on op symbols and threw
`SyntaxError: unknown binary op` for anything outside the built-in set.

This module is the registry the evaluator now consults. The hardcoded
switch is replaced by a single dictionary lookup. Built-in operators
register themselves at module load with the same category NodeIDs they
had in the hardcoded version — so existing behavior is preserved
exactly. Custom operators can add their own entries.

Two registries:

  _BINARY_EVAL[op_symbol]       → category NodeID (for BinOp interning)
  _UNARY_EVAL[op_symbol]        → category NodeID (for UnaryOp interning)

`register_eval(op_symbol, category, arity="binary")` adds an entry.
`lookup_eval_category(op_symbol, arity)` reads it.
`reset_eval_registry()` clears both (used by tests).
"""
from __future__ import annotations

from typing import Dict, Optional

from app.services.substrate.category import (
    Level,
    RBasic,
    RLogic,
    RMath,
    RCompare,
)
from app.services.substrate.kernel import NodeID


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------


_BINARY_EVAL: Dict[str, NodeID] = {}
_UNARY_EVAL: Dict[str, NodeID] = {}


def register_eval(op_symbol: str, category: NodeID, *, arity: str = "binary") -> None:
    """Register an operator symbol → recipe-category mapping for the
    evaluator. When the parser produces an AST node with this op, the
    evaluator interns it under this category."""
    if arity == "binary":
        _BINARY_EVAL[op_symbol] = category
    elif arity == "unary":
        _UNARY_EVAL[op_symbol] = category
    else:
        raise ValueError(f"register_eval: arity must be 'binary' or 'unary', got {arity!r}")


def lookup_eval_category(op_symbol: str, arity: str = "binary") -> Optional[NodeID]:
    if arity == "binary":
        return _BINARY_EVAL.get(op_symbol)
    if arity == "unary":
        return _UNARY_EVAL.get(op_symbol)
    return None


def list_eval_mappings(arity: str = "binary") -> Dict[str, NodeID]:
    """Return a copy of the registry for inspection."""
    if arity == "binary":
        return dict(_BINARY_EVAL)
    if arity == "unary":
        return dict(_UNARY_EVAL)
    return {}


def reset_eval_registry() -> None:
    _BINARY_EVAL.clear()
    _UNARY_EVAL.clear()
    _populate_builtins()


# ---------------------------------------------------------------------------
# Built-in registrations (match the categories the hardcoded switch used)
# ---------------------------------------------------------------------------


def _math_id(op: str) -> NodeID:
    instance = {
        "+": RMath.PLUS, "-": RMath.MINUS, "*": RMath.MULTIPLY,
        "/": RMath.DIVIDE, "%": RMath.MODULO, "neg": RMath.NEGATE,
    }[op]
    return NodeID(1, Level.BASIC, RBasic.MATH, instance)


def _compare_id(op: str) -> NodeID:
    instance = {
        "==": RCompare.EQUAL, "!=": RCompare.NOT_EQUAL,
        "<": RCompare.LESS, "<=": RCompare.LESS_EQUAL,
        ">": RCompare.GREATER, ">=": RCompare.GREATER_EQUAL,
    }[op]
    return NodeID(1, Level.BASIC, RBasic.COMPARE, instance)


def _logic_id(op: str) -> NodeID:
    instance = {"&&": RLogic.AND, "||": RLogic.OR, "!": RLogic.NOT}[op]
    return NodeID(1, Level.BASIC, RBasic.LOGIC, instance)


def _populate_builtins() -> None:
    """Default mappings — exactly what the hardcoded switch used to do."""
    for sym in ("+", "-", "*", "/", "%"):
        _BINARY_EVAL[sym] = _math_id(sym)
    for sym in ("==", "!=", "<", "<=", ">", ">="):
        _BINARY_EVAL[sym] = _compare_id(sym)
    for sym in ("&&", "||"):
        _BINARY_EVAL[sym] = _logic_id(sym)
    _UNARY_EVAL["-"] = _math_id("neg")
    _UNARY_EVAL["!"] = _logic_id("!")


# Populate at module load. After this, the hardcoded switch in form.py
# is replaced by `lookup_eval_category(op, arity)`.
_populate_builtins()
