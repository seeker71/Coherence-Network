"""Runtime-extensible primary-atom dispatch for Form.

A "primary atom" is the parser's bottom of the expression grammar — the
shapes that don't decompose further: literals, NodeID literals, trivial
refs, cell refs, parenthesized expressions, list/dict literals,
identifiers, dot-prefixed forms, and queries-in-expression-position.

Until now, `Parser.parse_primary` dispatched on token kind via a
hardcoded if/elif chain — adding a new atom shape (or overriding an
existing one) meant editing form.py. This module lifts the dispatch
into a registry so any module can register a new atom handler for a
given token kind at runtime.

Each handler has signature:

    (parser: Parser) -> AST node

The handler consumes tokens from the parser and returns the AST node.
The parser dispatches by looking up the handler for the current token's
kind; if no handler is registered, parse_primary raises SyntaxError.

The closing of the gap form-language.md → "Primary-atom parsing ...
the leaves the structured keywords compose over": no longer hardcoded.

See also:
- `form_rules.py` — keyword registry (compound keyword constructs)
- `form_queries.py` — query handler registry (?-verbs)
- `form_eval.py` — operator-category registry (op recipes)
- This module — atom registry (leaf token kinds)

Together they form the runtime-extensible registries the parser
consults; form.py's hand-written paths shrink with each registry.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List


# Handler signature: (parser) -> AST node.
# `parser` is `form.Parser`; the handler is free to call any of its
# methods (peek, consume, parse_expr, parse_at, etc.).
AtomHandler = Callable[["Parser"], Any]  # noqa: F821


# Keyed by TOKEN kind (e.g. "INT", "STRING", "AT", "TILDE", ...).
# Token kinds come from form._TOKEN_RE's named groups.
_ATOM_HANDLERS: Dict[str, AtomHandler] = {}


def register_atom(token_kind: str, handler: AtomHandler) -> None:
    """Register a handler for a given primary-atom token kind."""
    if not token_kind or not token_kind.replace("_", "").isalnum():
        raise ValueError(
            f"form_atoms: token kind must be ident-shaped, got {token_kind!r}"
        )
    _ATOM_HANDLERS[token_kind] = handler


def unregister_atom(token_kind: str) -> bool:
    return _ATOM_HANDLERS.pop(token_kind, None) is not None


def lookup_atom(token_kind: str) -> AtomHandler | None:
    return _ATOM_HANDLERS.get(token_kind)


def list_atoms() -> List[str]:
    """Names of every registered atom token kind. Used by introspection
    — `?atoms` (a future verb) can read this surface."""
    return sorted(_ATOM_HANDLERS.keys())


def dispatch_atom(parser, token_kind: str):
    """Dispatch a primary atom through the registry. Returns the AST node
    on success, raises SyntaxError if no handler is registered."""
    handler = _ATOM_HANDLERS.get(token_kind)
    if handler is None:
        t = parser.peek()
        raise SyntaxError(
            f"Form: no atom handler registered for token kind {token_kind!r} "
            f"at pos {t.pos} ({t.value!r})"
        )
    return handler(parser)


# ---------------------------------------------------------------------------
# Built-in atom handlers — the seed set
# ---------------------------------------------------------------------------
#
# Each handler is the same shape that used to live in `parse_primary`'s
# if/elif chain. Lifting them here makes them replaceable: a sibling
# module could `register_atom("INT", ...)` to override integer-literal
# semantics (e.g., for a fixed-point language dialect).


def _atom_at(parser):
    """`@<...>` — NodeID literal or cell ref."""
    return parser.parse_at()


def _atom_tilde(parser):
    """`~<Name>` — trivial blueprint reference."""
    return parser.parse_trivial_ref()


def _atom_int(parser):
    """Integer literal."""
    from app.services.substrate.form import IntLit
    return IntLit(int(parser.consume("INT").value))


def _atom_string(parser):
    """String literal. Handles `${...}` interpolation when present."""
    from app.services.substrate.form import (
        StringLit,
        _interpolated_to_ast,
        _unquote,
    )

    raw = parser.consume("STRING").value
    body = _unquote(raw)
    if "${" in body:
        return _interpolated_to_ast(body)
    return StringLit(value=body)


def _atom_lparen(parser):
    """Parenthesized expression."""
    parser.consume("LPAREN")
    inner = parser.parse_expr()
    parser.consume("RPAREN")
    return inner


def _atom_lbrack(parser):
    """List literal `[a, b, c]`."""
    return parser.parse_list_literal()


def _atom_lbrace(parser):
    """Dict literal `{key: value, ...}`."""
    return parser.parse_dict_literal()


def _atom_ident(parser):
    """Identifier — also matches keywords (dispatched in parse_keyword_or_ident)."""
    return parser.parse_keyword_or_ident()


def _atom_dot(parser):
    """`.self` — implicit subject of an enclosing `with` block."""
    from app.services.substrate.form import SelfRef

    t = parser.peek()
    parser.consume("DOT")
    ident = parser.peek()
    if ident.kind == "IDENT" and ident.value == "self":
        parser.consume("IDENT")
        return SelfRef()
    raise SyntaxError(
        f"Form: only `.self` is supported in dot-prefix position at pos {t.pos} "
        f"(got `.{ident.value}`)"
    )


def _atom_qmark(parser):
    """`?<query>` in expression position — queries are composable atoms."""
    return parser.parse_query()


def _register_builtins() -> None:
    """Register the 10 built-in primary-atom handlers."""
    register_atom("AT", _atom_at)
    register_atom("TILDE", _atom_tilde)
    register_atom("INT", _atom_int)
    register_atom("STRING", _atom_string)
    register_atom("LPAREN", _atom_lparen)
    register_atom("LBRACK", _atom_lbrack)
    register_atom("LBRACE", _atom_lbrace)
    register_atom("IDENT", _atom_ident)
    register_atom("DOT", _atom_dot)
    register_atom("QMARK", _atom_qmark)


_register_builtins()


__all__ = [
    "AtomHandler",
    "register_atom",
    "unregister_atom",
    "lookup_atom",
    "list_atoms",
    "dispatch_atom",
]
