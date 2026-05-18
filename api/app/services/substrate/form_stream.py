"""Streaming-emit Form parser — BMF-style proof-of-shape.

The bootstrap parser (`form.py`) builds Python dataclass AST nodes, then
`_to_recipe_node_id` walks the AST to intern Recipe NodeIDs into the
substrate. The AST is a staging area that gets thrown away after intern.

BMF (Backtracking Model Form, 2000) named the deeper instinct:

    "Evaluating the parse attributes during parsing will cut down the
    running parse tree in a way, that even infinitive input streams can
    be supported."

The substrate is already the destination. The AST is duplication. This
module proves the BMF-faithful shape on this body: each parse rule's
success **directly emits a Recipe NodeID** to a working stack. No AST
node classes parallel to recipe categories; no intermediate tree;
no garbage to collect between parse and intern.

Status: **alpha — a shape proof, not a replacement.** Covers a
deliberately small grammar subset that demonstrates the architecture:

- integer literals (trivial leaves; no DB roundtrip)
- binary arithmetic (`+ - * / %`) with precedence
- comparison (`== != < <= > >=`)
- logic (`&& || !`) with precedence
- parenthesized grouping
- `if/then/else`

The equivalence property is the proof: for every expression in the subset,
`form_stream.parse_and_emit(s, text)` returns the **same Recipe NodeID**
as `form_evaluate_text(s, text)` would. The substrate is the shared
destination; the kernel's content-addressing enforces equivalence
regardless of which path emits the recipe.

What this prototype shows that the AST-based path cannot:

1. **Streaming-native.** Each completed rule emits its NodeID immediately;
   the parser never holds a full tree in memory. Long expressions, log
   tails, stream-based inputs become natural.

2. **No AST vocabulary parallel to recipe vocabulary.** Adding a new
   construct means registering a new (pattern, emit-action) rule cell
   in the substrate's `grammar` domain — no new Python class to define.
   Truly first-class runtime grammar extension.

3. **Single-stack uniformity.** Parser, runtime `choose`/`fail`/`stop`,
   and version control's `tend`/`compost`/`release` all become reflections
   of the same primitive — a working stack with structured undo. (See
   docs/coherence-substrate/form-language.md → "The path from bootstrap
   to self-hosting" → steps 5-9.)

Path forward beyond this proof:

- Cover the full Form grammar (do/let/with/match/choose/method/...)
- Surface the rules as substrate-resident cells in the `grammar` domain
  (the registry infrastructure already exists in `form_rules.py`)
- Port the hot loop to a Rust kernel via PyO3 — Bjorg's BMA had
  forward/reverse semantics for every instruction; Rust enum-dispatch
  expresses that cleanly. The substrate stays the universal data plane.

See:
- `docs/field/urs/artifacts/master-thesis-2000/` — BMF lineage
- `docs/coherence-substrate/form-language.md` — Form language design
- `api/app/services/substrate/form.py` — the AST-based bootstrap parser
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.substrate.category import (
    Level,
    RBasic,
    RCompare,
    RCond,
    RLogic,
    RMath,
    RType,
)
from app.services.substrate.kernel import (
    DOMAIN_RECIPE,
    NodeID,
    intern_node,
)


# ---------------------------------------------------------------------------
# Tokenizer — shared shape with form.py but local to keep this file standalone
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(
    r"""
    (?P<WS>\s+) |
    (?P<COMMENT>\#[^\n]*) |
    (?P<INT>\d+) |
    (?P<EQ>==) | (?P<NEQ>!=) | (?P<LEQ><=) | (?P<GEQ>>=) |
    (?P<AND>&&) | (?P<OR>\|\|) |
    (?P<LT><) | (?P<GT>>) |
    (?P<PLUS>\+) | (?P<MINUS>-) | (?P<STAR>\*) | (?P<SLASH>/) | (?P<PCT>%) |
    (?P<NOT>!) |
    (?P<LPAREN>\() | (?P<RPAREN>\)) |
    (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    pos: int


def tokenize(text: str) -> List[Token]:
    """Eager tokenize the input. Streaming variants belong in a later breath
    once the per-rule emit pattern is proven end-to-end."""
    tokens: List[Token] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise SyntaxError(
                f"form_stream: unexpected char at pos {pos}: {text[pos]!r}"
            )
        kind = m.lastgroup or ""
        if kind not in ("WS", "COMMENT"):
            tokens.append(Token(kind, m.group(), pos))
        pos = m.end()
    tokens.append(Token("EOF", "", pos))
    return tokens


# ---------------------------------------------------------------------------
# Category coordinates for the rules this prototype emits
# ---------------------------------------------------------------------------


def _math_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.MATH, op)


def _compare_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.COMPARE, op)


def _logic_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.LOGIC, op)


def _cond_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.COND, op)


_BINARY_MATH: dict[str, NodeID] = {
    "+": _math_cat(RMath.PLUS),
    "-": _math_cat(RMath.MINUS),
    "*": _math_cat(RMath.MULTIPLY),
    "/": _math_cat(RMath.DIVIDE),
    "%": _math_cat(RMath.MODULO),
}

_COMPARE: dict[str, NodeID] = {
    "==": _compare_cat(RCompare.EQUAL),
    "!=": _compare_cat(RCompare.NOT_EQUAL),
    "<":  _compare_cat(RCompare.LESS),
    "<=": _compare_cat(RCompare.LESS_EQUAL),
    ">":  _compare_cat(RCompare.GREATER),
    ">=": _compare_cat(RCompare.GREATER_EQUAL),
}

_LOGIC_BINARY: dict[str, NodeID] = {
    "&&": _logic_cat(RLogic.AND),
    "||": _logic_cat(RLogic.OR),
}


def _int_leaf(value: int) -> NodeID:
    """An integer literal interns as a trivial NodeID by coordinate — no row
    in `substrate_nodes`, no DB roundtrip. The kernel skips re-interning
    trivial leaves; their coordinate IS their identity.

    Encoding matches `form._to_recipe_node_id` for IntLit so both parsers
    produce the same NodeID for the same integer."""
    return NodeID(1, Level.TRIVIAL, RType.INTEGER, value + 1 if value >= 0 else 0)


def _bool_leaf(value: bool) -> NodeID:
    return NodeID(1, Level.TRIVIAL, RType.BOOL, 1 if value else 0)


# ---------------------------------------------------------------------------
# The streaming-emit parser
# ---------------------------------------------------------------------------


@dataclass
class _ParserState:
    """The whole parser is a token cursor + a NodeID emit-stack.

    On rule success: pop the rule's children from the stack, intern the
    rule's category-with-children, push the resulting NodeID back.
    On rule failure (not used in this minimal subset; reserved for the
    full grammar): restore (pos, stack-depth) — BMF's
    backtracking-without-sediment at the parser level.
    """
    tokens: List[Token]
    pos: int = 0
    stack: List[NodeID] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.stack is None:
            self.stack = []

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[self.pos + offset]

    def consume(self, kind: str) -> Token:
        t = self.peek()
        if t.kind != kind:
            raise SyntaxError(
                f"form_stream: expected {kind} at pos {t.pos}, got {t.kind} ({t.value!r})"
            )
        self.pos += 1
        return t

    def emit(self, session: Session, category: NodeID, arity: int) -> None:
        """Pop `arity` children from the stack; push the interned recipe.

        This IS the BMF semantic-action — the moment a rule completes,
        the rule's NodeID lands on the working stack. No AST node is ever
        materialized. The substrate is the destination, and the path from
        token-stream to substrate has one staging surface (the stack), not
        two (the stack AND a separate AST tree)."""
        if arity > len(self.stack):
            raise RuntimeError(
                f"form_stream: stack underflow — want {arity} children, have {len(self.stack)}"
            )
        children = self.stack[-arity:] if arity > 0 else []
        del self.stack[len(self.stack) - arity:]
        node_id = intern_node(session, DOMAIN_RECIPE, category, children)
        self.stack.append(node_id)


# ---------- recursive descent with streaming emit ---------------------------


def _parse_expr(session: Session, p: _ParserState) -> None:
    """Top of the precedence ladder: logical-or."""
    _parse_logic_or(session, p)


def _parse_logic_or(session: Session, p: _ParserState) -> None:
    _parse_logic_and(session, p)
    while p.peek().kind == "OR":
        p.consume("OR")
        _parse_logic_and(session, p)
        p.emit(session, _LOGIC_BINARY["||"], arity=2)


def _parse_logic_and(session: Session, p: _ParserState) -> None:
    _parse_compare(session, p)
    while p.peek().kind == "AND":
        p.consume("AND")
        _parse_compare(session, p)
        p.emit(session, _LOGIC_BINARY["&&"], arity=2)


def _parse_compare(session: Session, p: _ParserState) -> None:
    _parse_additive(session, p)
    kind = p.peek().kind
    sym_for_kind = {
        "EQ": "==", "NEQ": "!=", "LT": "<", "LEQ": "<=", "GT": ">", "GEQ": ">=",
    }
    if kind in sym_for_kind:
        sym = sym_for_kind[kind]
        p.consume(kind)
        _parse_additive(session, p)
        p.emit(session, _COMPARE[sym], arity=2)


def _parse_additive(session: Session, p: _ParserState) -> None:
    _parse_multiplicative(session, p)
    while p.peek().kind in ("PLUS", "MINUS"):
        op = "+" if p.peek().kind == "PLUS" else "-"
        p.consume(p.peek().kind)
        _parse_multiplicative(session, p)
        p.emit(session, _BINARY_MATH[op], arity=2)


def _parse_multiplicative(session: Session, p: _ParserState) -> None:
    _parse_unary(session, p)
    while p.peek().kind in ("STAR", "SLASH", "PCT"):
        op = {"STAR": "*", "SLASH": "/", "PCT": "%"}[p.peek().kind]
        p.consume(p.peek().kind)
        _parse_unary(session, p)
        p.emit(session, _BINARY_MATH[op], arity=2)


def _parse_unary(session: Session, p: _ParserState) -> None:
    if p.peek().kind == "NOT":
        p.consume("NOT")
        _parse_unary(session, p)
        p.emit(session, _logic_cat(RLogic.NOT), arity=1)
        return
    if p.peek().kind == "MINUS":
        p.consume("MINUS")
        _parse_unary(session, p)
        p.emit(session, _math_cat(RMath.NEGATE), arity=1)
        return
    _parse_primary(session, p)


def _parse_primary(session: Session, p: _ParserState) -> None:
    t = p.peek()
    if t.kind == "INT":
        p.consume("INT")
        p.stack.append(_int_leaf(int(t.value)))
        return
    if t.kind == "IDENT" and t.value == "true":
        p.consume("IDENT")
        p.stack.append(_bool_leaf(True))
        return
    if t.kind == "IDENT" and t.value == "false":
        p.consume("IDENT")
        p.stack.append(_bool_leaf(False))
        return
    if t.kind == "IDENT" and t.value == "if":
        _parse_if(session, p)
        return
    if t.kind == "LPAREN":
        p.consume("LPAREN")
        _parse_expr(session, p)
        p.consume("RPAREN")
        return
    raise SyntaxError(
        f"form_stream: unexpected token {t.kind} ({t.value!r}) at pos {t.pos}"
    )


def _parse_if(session: Session, p: _ParserState) -> None:
    """if cond then body [else else_body] — emit IF_THEN or IF_THEN_ELSE.

    Each sub-expression's parse leaves exactly one NodeID on the stack.
    The emit pops the right arity and lands the conditional recipe."""
    p.consume("IDENT")  # 'if'
    _parse_expr(session, p)
    then_tok = p.peek()
    if then_tok.kind != "IDENT" or then_tok.value != "then":
        raise SyntaxError(
            f"form_stream: expected 'then' at pos {then_tok.pos}, got {then_tok.value!r}"
        )
    p.consume("IDENT")  # 'then'
    _parse_expr(session, p)
    has_else = p.peek().kind == "IDENT" and p.peek().value == "else"
    if has_else:
        p.consume("IDENT")  # 'else'
        _parse_expr(session, p)
        p.emit(session, _cond_cat(RCond.IF_THEN_ELSE), arity=3)
    else:
        p.emit(session, _cond_cat(RCond.IF_THEN), arity=2)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def parse_and_emit(session: Session, text: str) -> NodeID:
    """Parse `text` in the subset this prototype covers, emitting Recipe
    NodeIDs to the substrate as rules complete. Returns the final stacked
    NodeID — what would be the root of an AST in the bootstrap parser, but
    here it's just the last thing left on the working stack.

    Equivalence property: for every text in this subset,
        parse_and_emit(s, text) == form_evaluate_text(s, text).value
    """
    tokens = tokenize(text.strip())
    p = _ParserState(tokens=tokens, pos=0, stack=[])
    _parse_expr(session, p)
    if p.peek().kind != "EOF":
        t = p.peek()
        raise SyntaxError(
            f"form_stream: trailing input at pos {t.pos}: {t.value!r}"
        )
    if len(p.stack) != 1:
        raise RuntimeError(
            f"form_stream: stack didn't reduce to one — depth={len(p.stack)}"
        )
    return p.stack[0]


__all__ = [
    "parse_and_emit",
    "tokenize",
    "Token",
]
