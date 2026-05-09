"""Operator registry — precedence-climbing-aware operator rules.

Step 7 of the bootstrap-to-self-hosting path: closing the last keyword-
layer gap. Form's binary and unary operators (+, -, *, /, %, ==, !=,
<, <=, >, >=, &&, ||, !) are now expressible as registered rules with
precedence + associativity. The parser, in `prefer_registered=True`
mode, drives expression parsing via precedence climbing using these
rules — no hardcoded ladder.

Each operator carries:
  - symbol       the operator text ("+")
  - token_kind   the lexer token kind ("PLUS")
  - precedence   integer; higher = tighter binding
  - associativity "left" or "right"
  - arity        "binary" or "unary_prefix"
  - template     a Build template (substrate-resident) that takes
                 __left__ + __right__ captures (for binary) or
                 __operand__ capture (for unary)
  - builder      Python fallback callable; required if template is None
                 or the substrate isn't reachable

Two structurally-identical operator templates dedupe through the
substrate's content-addressed interning. The bootstrap precedence
ladder and the precedence-climbing path produce identical Recipe
NodeIDs for any expression where the operators are registered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# OperatorRule
# ---------------------------------------------------------------------------


@dataclass
class OperatorRule:
    symbol: str
    token_kind: str
    precedence: int
    associativity: str = "left"  # "left" or "right"
    arity: str = "binary"        # "binary" or "unary_prefix"
    template: Any = None
    builder: Optional[Callable] = None

    def __post_init__(self):
        if self.template is None and self.builder is None:
            raise ValueError(
                f"OperatorRule({self.symbol!r}): need template or builder"
            )
        if self.associativity not in ("left", "right"):
            raise ValueError(
                f"OperatorRule({self.symbol!r}): associativity must be left/right"
            )
        if self.arity not in ("binary", "unary_prefix"):
            raise ValueError(
                f"OperatorRule({self.symbol!r}): arity must be binary/unary_prefix"
            )


# ---------------------------------------------------------------------------
# Registry — separate maps for binary vs unary_prefix so the same token
# (e.g. MINUS) can act as both depending on context.
# ---------------------------------------------------------------------------


_BINARY_OPERATORS: Dict[str, OperatorRule] = {}
_UNARY_PREFIX_OPERATORS: Dict[str, OperatorRule] = {}


def _registry_for(arity: str) -> Dict[str, OperatorRule]:
    if arity == "binary":
        return _BINARY_OPERATORS
    if arity == "unary_prefix":
        return _UNARY_PREFIX_OPERATORS
    raise ValueError(f"unknown arity: {arity}")


def register_operator(
    symbol: str,
    token_kind: str,
    precedence: int,
    *,
    associativity: str = "left",
    arity: str = "binary",
    template: Any = None,
    builder: Optional[Callable] = None,
) -> OperatorRule:
    """Add an operator to the registry. Binary and unary_prefix have
    independent slots — registering one doesn't displace the other."""
    rule = OperatorRule(
        symbol=symbol, token_kind=token_kind, precedence=precedence,
        associativity=associativity, arity=arity,
        template=template, builder=builder,
    )
    _registry_for(arity)[token_kind] = rule
    return rule


def lookup_binary_operator(token_kind: str) -> Optional[OperatorRule]:
    return _BINARY_OPERATORS.get(token_kind)


def lookup_unary_prefix_operator(token_kind: str) -> Optional[OperatorRule]:
    return _UNARY_PREFIX_OPERATORS.get(token_kind)


# Backwards-compat alias — checks binary first, then unary_prefix.
def lookup_operator(token_kind: str) -> Optional[OperatorRule]:
    return _BINARY_OPERATORS.get(token_kind) or _UNARY_PREFIX_OPERATORS.get(token_kind)


def list_operators() -> List[OperatorRule]:
    return list(_BINARY_OPERATORS.values()) + list(_UNARY_PREFIX_OPERATORS.values())


def unregister_operator(token_kind: str, arity: str = "binary") -> bool:
    return _registry_for(arity).pop(token_kind, None) is not None


def reset_operator_registry() -> None:
    """Clear both registries. Used by tests + bootstrap_self_host_operators."""
    _BINARY_OPERATORS.clear()
    _UNARY_PREFIX_OPERATORS.clear()


# ---------------------------------------------------------------------------
# Precedence climbing
# ---------------------------------------------------------------------------
#
# Standard precedence-climbing algorithm. The parser parses a primary
# expression (after unary handling), then while the next token is a
# binary operator with precedence >= min_prec, consumes it and recurses
# with adjusted min_prec.
#
# Left-associative: next_min = current_prec + 1
# Right-associative: next_min = current_prec
#
# Unary prefix operators are handled by `parse_unary` upstream; they
# bind tighter than any registered binary operator.


def parse_with_precedence(parser, min_prec: int = 0):
    """Drive expression parsing via precedence climbing using the
    registered operator rules. The parser must already have a working
    `parse_unary()` method that handles unary prefixes + projections +
    primary atoms."""
    left = parser.parse_unary()
    while True:
        t = parser.peek()
        op = _BINARY_OPERATORS.get(t.kind)
        if op is None:
            break
        if op.precedence < min_prec:
            break
        parser.consume(t.kind)
        next_min = (
            op.precedence + 1 if op.associativity == "left" else op.precedence
        )
        right = parse_with_precedence(parser, next_min)
        left = _apply_binary(op, left, right)
    return left


def _apply_binary(op: OperatorRule, left: Any, right: Any) -> Any:
    """Apply a binary operator rule to its operands.

    Prefers the substrate-resident template path (executes the template
    with captures = {__left__, __right__}). Falls back to the Python
    builder if the template is None.
    """
    if op.template is not None:
        from app.services.substrate import form as _form_mod
        from app.services.substrate.form_builders import execute_template
        return execute_template(
            op.template, {"__left__": left, "__right__": right}, _form_mod,
        )
    return op.builder(left, right)


def apply_unary(op: OperatorRule, operand: Any) -> Any:
    """Apply a unary prefix operator rule. Used by parse_unary when the
    parser is in prefer_registered mode."""
    if op.template is not None:
        from app.services.substrate import form as _form_mod
        from app.services.substrate.form_builders import execute_template
        return execute_template(
            op.template, {"__operand__": operand}, _form_mod,
        )
    return op.builder(operand)
