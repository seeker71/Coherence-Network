"""User-extensible Form keywords — step 3 of the bootstrap-to-self-hosting path.

The bootstrap parser in `form.py` has a hand-written grammar. This module
makes ONE part of that grammar live: when an agent encounters an unknown
keyword, the parser consults a registry of user-registered keywords. If
a rule matches, the parser captures sub-expressions using the rule's
pattern and hands them to the rule's builder to construct the AST.

This proves the grammar-as-data architecture is alive (not just stored).
A new keyword can be added at runtime — `unless`, `when`, `until`, etc. —
without editing form.py.

What this module is NOT yet:
- Pattern matching is structural-token-level, not character-level. Lexing
  remains static.
- Builders are Python callables, not substrate-resident Recipe actions.
- Backtracking is implicit (try-and-rewind via parser.pos save/restore),
  not Choice.FAIL-driven speculation.

Each of those gaps is a future breath. What ships here is the seed:
the parser truly extends at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Pattern primitives
# ---------------------------------------------------------------------------


@dataclass
class Literal:
    """Match a single token by kind + optional value."""
    kind: str                       # token kind (e.g. "IDENT", "PROJECT")
    value: Optional[str] = None     # exact value to match (or None for any)


@dataclass
class Capture:
    """Capture a sub-expression under a name.

    `kind` is the parser-rule to invoke for this capture:
      - "expr" — any expression (calls parse_expr)
      - "primary" — a primary atom only
    """
    name: str
    kind: str = "expr"


@dataclass
class Sequence:
    """Match a sequence of patterns in order."""
    parts: List[Any]


@dataclass
class Optional_:
    """Match a sub-pattern if it's there; succeed with no captures otherwise."""
    pattern: Any


# Public alias — `Optional_` would shadow typing.Optional otherwise
Opt = Optional_


# ---------------------------------------------------------------------------
# Match engine
# ---------------------------------------------------------------------------


@dataclass
class MatchResult:
    success: bool
    captures: Dict[str, Any] = field(default_factory=dict)


def try_match(parser, pattern: Any) -> MatchResult:
    """Try to match a pattern against the parser's current position.

    On success, returns MatchResult(success=True, captures=...).
    On fail, restores parser.pos and returns MatchResult(success=False).

    This is the "implicit backtracking" — we save pos before the try,
    restore on failure. Future work: integrate with Choice.FAIL so the
    parser's speculation is itself a substrate-recorded operation.
    """
    saved = parser.pos
    captures: Dict[str, Any] = {}
    if _do_match(parser, pattern, captures):
        return MatchResult(True, captures)
    parser.pos = saved
    return MatchResult(False)


def _do_match(parser, pattern: Any, captures: Dict[str, Any]) -> bool:
    if isinstance(pattern, Literal):
        t = parser.peek()
        if t.kind != pattern.kind:
            return False
        if pattern.value is not None and t.value != pattern.value:
            return False
        parser.consume(pattern.kind)
        return True

    if isinstance(pattern, Capture):
        try:
            if pattern.kind == "expr":
                node = parser.parse_expr()
            elif pattern.kind == "primary":
                node = parser.parse_primary()
            else:
                return False
        except SyntaxError:
            return False
        captures[pattern.name] = node
        return True

    if isinstance(pattern, Sequence):
        for part in pattern.parts:
            if not _do_match(parser, part, captures):
                return False
        return True

    if isinstance(pattern, Optional_):
        saved = parser.pos
        sub_captures: Dict[str, Any] = {}
        if _do_match(parser, pattern.pattern, sub_captures):
            captures.update(sub_captures)
            return True
        parser.pos = saved
        return True  # optional: not matching is success

    return False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


# `keyword_name` → (pattern, builder)
# Pattern is a RulePattern; builder takes captures dict and returns an AST node.
_KEYWORDS: Dict[str, tuple] = {}


def register_form_keyword(
    name: str,
    pattern: Any,
    builder: Callable[[Dict[str, Any]], Any],
    *,
    session=None,
    substrate_pattern_id=None,
    substrate_action_id=None,
) -> None:
    """Register a user-defined Form keyword.

    `name` is the trigger token (e.g. "unless"). When the parser hits an
    IDENT with this value at the start of an expression, it consults this
    registry before falling through to the bootstrap grammar.

    `pattern` is a RulePattern — a Sequence of Literals and Captures —
    that defines the keyword's syntax.

    `builder` is a callable that receives a `captures` dict and returns
    an AST node from `form.py`'s vocabulary (IfExpr, BinOp, etc.).

    If `session` is provided, also registers the rule as a substrate Cell
    in the grammar domain (using register_form_rule). Pattern + action
    NodeIDs default to placeholder leaves; richer substrate-level
    representation is future work.
    """
    _KEYWORDS[name] = (pattern, builder)
    if session is not None and substrate_pattern_id is not None and substrate_action_id is not None:
        from app.services.substrate.grammar import register_form_rule
        register_form_rule(session, name, substrate_pattern_id, substrate_action_id)


def unregister_form_keyword(name: str) -> bool:
    """Remove a keyword from the registry. Useful in tests."""
    return _KEYWORDS.pop(name, None) is not None


def lookup_form_keyword(name: str) -> Optional[tuple]:
    """Return (pattern, builder) or None."""
    return _KEYWORDS.get(name)


def list_registered_keywords() -> List[str]:
    """All currently-registered keyword names."""
    return list(_KEYWORDS.keys())


def try_apply_keyword_rule(parser, name: str) -> Optional[Any]:
    """If `name` is a registered keyword, try its rule against the parser.

    Returns the built AST node on success, None on miss-or-fail.
    Note: parser.pos is NOT consumed past 'name' on entry — the rule's
    pattern itself must match the keyword token (typically as the first
    Literal in the Sequence).
    """
    entry = _KEYWORDS.get(name)
    if entry is None:
        return None
    pattern, builder = entry
    result = try_match(parser, pattern)
    if not result.success:
        return None
    return builder(result.captures)
