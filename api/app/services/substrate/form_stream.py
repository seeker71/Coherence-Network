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
from typing import Callable, Iterator, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.substrate.category import (
    Level,
    RBasic,
    RBlock,
    RChoice,
    RCommon,
    RCompare,
    RCond,
    RDelegate,
    RException,
    RLogic,
    RMatch,
    RMath,
    RMethod,
    RReverse,
    RState,
    RTry,
    RType,
)
from app.services.substrate.kernel import (
    DOMAIN_RECIPE,
    NodeID,
    intern_node,
    lookup_cell,
)
# Reuse the canonical trivial-ref table and self-ref instance so streaming
# and AST paths encode identical leaves by construction. The substrate is
# the destination; constants that determine leaf coordinates are shared.
from app.services.substrate.form import (
    TRIVIAL_REFS,
    DOMAIN_TO_REF,
    _SELF_REF_INSTANCE,
)
from app.services.substrate.substrate_strings import intern_string_instance


# ---------------------------------------------------------------------------
# Tokenizer — shared shape with form.py but local to keep this file standalone
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(
    r"""
    (?P<WS>\s+) |
    (?P<COMMENT>\#[^\n]*) |
    (?P<STRING>"(?:[^"\\]|\\.)*") |
    (?P<INT>\d+) |
    (?P<ARROW>=>) |
    (?P<EQ>==) | (?P<NEQ>!=) | (?P<LEQ><=) | (?P<GEQ>>=) |
    (?P<AND>&&) | (?P<OR>\|\|) |
    (?P<ASSIGN>=) |
    (?P<LT><) | (?P<GT>>) |
    (?P<PLUS>\+) | (?P<MINUS>-) | (?P<STAR>\*) | (?P<SLASH>/) | (?P<PCT>%) |
    (?P<NOT>!) |
    (?P<LPAREN>\() | (?P<RPAREN>\)) |
    (?P<LBRACE>\{) | (?P<RBRACE>\}) |
    (?P<LBRACK>\[) | (?P<RBRACK>\]) |
    (?P<AT>@) |
    (?P<TILDE>~) |
    (?P<DOT>\.) |
    (?P<COLON>:) |
    (?P<SEMI>;) |
    (?P<COMMA>,) |
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


def _block_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.BLOCK, op)


def _match_cat() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.MATCH, RMatch.SWITCH)


def _choice_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.CHOICE, op)


def _state_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.STATE, op)


def _exception_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.EXCEPTION, op)


def _try_cat() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.TRY, RTry.TRY_CATCH)


def _delegate_cat() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.DELEGATE, RDelegate.DELEGATE_TO)


def _reverse_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.REVERSE, op)


def _common_cat() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.COMMON, RCommon.SHARED_BASE)


def _method_cat(op: int) -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.METHOD, op)


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


def _string_leaf(session: Session, value: str) -> NodeID:
    """A string literal interns through the substrate string-table — same as
    `form._to_recipe_node_id` does for StringLit. Cross-process-stable
    instance allocation makes the resulting NodeID round-trip-recoverable."""
    inst = intern_string_instance(session, value)
    return NodeID(1, Level.TRIVIAL, RType.STRING, inst)


def _identifier_leaf(name: str) -> NodeID:
    """Bare identifier — placeholder LOCAL_ACCESS encoded by hashing the name
    into a small instance number. Matches form.py's IntLit-adjacent path."""
    inst = abs(hash(name)) % (10**9) + 1
    return NodeID(1, Level.TRIVIAL, 7, inst)


def _self_leaf() -> NodeID:
    """`.self` — interns as a stable LOCAL_ACCESS NodeID with the SELF sentinel."""
    return NodeID(1, Level.TRIVIAL, 7, _SELF_REF_INSTANCE)


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
    # ---- trivial leaves --------------------------------------------------
    if t.kind == "INT":
        p.consume("INT")
        p.stack.append(_int_leaf(int(t.value)))
        return
    if t.kind == "STRING":
        p.consume("STRING")
        # Strip surrounding quotes; decode common escapes \n, \t, \", \\
        raw = t.value[1:-1]
        decoded = raw.encode("utf-8").decode("unicode_escape")
        p.stack.append(_string_leaf(session, decoded))
        return
    if t.kind == "AT":
        _parse_at_form(session, p)
        return
    if t.kind == "TILDE":
        _parse_trivial_ref(session, p)
        return
    if t.kind == "DOT":
        _parse_dot_form(session, p)
        return
    # ---- keyword-named constructs ---------------------------------------
    if t.kind == "IDENT":
        kw = t.value
        if kw == "true":
            p.consume("IDENT")
            p.stack.append(_bool_leaf(True))
            return
        if kw == "false":
            p.consume("IDENT")
            p.stack.append(_bool_leaf(False))
            return
        if kw in _KEYWORD_HANDLERS:
            _KEYWORD_HANDLERS[kw](session, p)
            return
        # bare identifier — placeholder leaf
        p.consume("IDENT")
        p.stack.append(_identifier_leaf(kw))
        return
    # ---- parenthesized expression ---------------------------------------
    if t.kind == "LPAREN":
        p.consume("LPAREN")
        _parse_expr(session, p)
        p.consume("RPAREN")
        return
    raise SyntaxError(
        f"form_stream: unexpected token {t.kind} ({t.value!r}) at pos {t.pos}"
    )


# ---- @-forms: NodeID literal, cell ref, bare domain ----------------------


def _parse_at_form(session: Session, p: _ParserState) -> None:
    """Three @-shapes:
        @p.l.t.i         — NodeID literal (4 ints separated by DOT)
        @domain          — bare domain blueprint (e.g. @memory)
        @domain(name)    — cell reference (lookup_cell + GLOBAL trivial)
    """
    p.consume("AT")
    # NodeID literal vs domain-name
    if p.peek().kind == "INT":
        parts = [int(p.consume("INT").value)]
        while p.peek().kind == "DOT" and p.tokens[p.pos + 1].kind == "INT":
            p.consume("DOT")
            parts.append(int(p.consume("INT").value))
        if len(parts) != 4:
            raise SyntaxError(
                f"form_stream: NodeID literal needs 4 parts, got {len(parts)}"
            )
        p.stack.append(NodeID(parts[0], parts[1], parts[2], parts[3]))
        return
    # @<domain> or @<domain>(name)
    if p.peek().kind != "IDENT":
        t = p.peek()
        raise SyntaxError(
            f"form_stream: expected domain name after @ at pos {t.pos}, got {t.kind}"
        )
    domain = p.consume("IDENT").value
    if p.peek().kind == "LPAREN":
        p.consume("LPAREN")
        # cell name — may be a slug (IDENT, optionally with hyphens parsed as
        # MINUS + IDENT). Collect contiguous IDENT/MINUS tokens.
        name_parts: list[str] = []
        while p.peek().kind in ("IDENT", "MINUS", "INT"):
            name_parts.append(p.consume(p.peek().kind).value)
        p.consume("RPAREN")
        name = "".join(name_parts)
        cell = lookup_cell(session, domain, name)
        if cell is None:
            raise LookupError(
                f"form_stream: cell ({domain}, {name}) not found"
            )
        # GLOBAL trivial — instance = cell_id. Matches form.py's CellRef encoding.
        p.stack.append(NodeID(1, Level.TRIVIAL, 8, cell.cell_id or 0))
        return
    # bare @<domain>
    ref_name = DOMAIN_TO_REF.get(domain)
    if ref_name is None:
        raise NameError(f"form_stream: unknown domain @{domain}")
    p.stack.append(TRIVIAL_REFS[ref_name])


def _parse_trivial_ref(session: Session, p: _ParserState) -> None:
    """~Name — resolves to the canonical trivial Blueprint NodeID."""
    p.consume("TILDE")
    name = p.consume("IDENT").value
    nid = TRIVIAL_REFS.get(name)
    if nid is None:
        raise NameError(f"form_stream: unknown trivial ~{name}")
    p.stack.append(nid)


def _parse_dot_form(session: Session, p: _ParserState) -> None:
    """`.self` — the BML scoped-reference primitive. Other dotted access
    (`.blueprint`, `.category`, `.child(n)`) is in the AST path but is a
    query-shape, not a recipe — out of streaming-emit scope for now."""
    p.consume("DOT")
    if p.peek().kind == "IDENT" and p.peek().value == "self":
        p.consume("IDENT")
        p.stack.append(_self_leaf())
        return
    t = p.peek()
    raise SyntaxError(
        f"form_stream: only `.self` supported in recipe context at pos {t.pos}"
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
# Block / let / with — the RBlock family
# ---------------------------------------------------------------------------


def _parse_do(session: Session, p: _ParserState) -> None:
    """do { stmt; stmt; ...; expr } — emit Block.DO with N statement children.

    Each statement (let-binding or expression) leaves exactly one NodeID on
    the stack. The closing brace pops them all under Block.DO. SEMIs are
    statement separators; trailing SEMI is allowed."""
    p.consume("IDENT")  # 'do'
    p.consume("LBRACE")
    count = 0
    while p.peek().kind != "RBRACE":
        if p.peek().kind == "IDENT" and p.peek().value == "let":
            _parse_let(session, p)
        else:
            _parse_expr(session, p)
        count += 1
        if p.peek().kind == "SEMI":
            p.consume("SEMI")
        elif p.peek().kind != "RBRACE":
            t = p.peek()
            raise SyntaxError(
                f"form_stream: expected ';' or '}}' at pos {t.pos}, got {t.kind}"
            )
    p.consume("RBRACE")
    p.emit(session, _block_cat(RBlock.DO), arity=count)


def _parse_let(session: Session, p: _ParserState) -> None:
    """let name = expr — emit Block.LET with (name-as-identifier, value).
    Matches form.py: name is encoded as an Identifier-style placeholder leaf."""
    p.consume("IDENT")  # 'let'
    name = p.consume("IDENT").value
    p.consume("ASSIGN")
    _parse_expr(session, p)
    # Push the name-leaf, then emit LET with arity 2 (name, value).
    name_id = _identifier_leaf(name)
    # Stack currently has [value]. We need [name, value] before emit. Insert.
    value_id = p.stack.pop()
    p.stack.append(name_id)
    p.stack.append(value_id)
    p.emit(session, _block_cat(RBlock.LET), arity=2)


def _parse_with(session: Session, p: _ParserState) -> None:
    """with subject { body } — BML scoped-reference. The body always wraps
    in a DO block (matches form.py: `body = DoBlock(statements=stmts)`)
    regardless of statement count. That gives content-addressed equality
    with the AST path."""
    p.consume("IDENT")  # 'with'
    _parse_expr(session, p)  # subject
    _parse_brace_block_always_wrap(session, p)
    # Stack has [subject, body-as-DO]; emit WITH with arity 2.
    p.emit(session, _block_cat(RBlock.WITH), arity=2)


# ---------------------------------------------------------------------------
# Match — RMatch.SWITCH
# ---------------------------------------------------------------------------


def _parse_match(session: Session, p: _ParserState) -> None:
    """match scrutinee { pat => body, pat => body, _ => body } — emit
    Match.SWITCH with [scrutinee, pat1, body1, pat2, body2, ...]. The
    underscore default is encoded as an identifier-leaf named "_"."""
    p.consume("IDENT")  # 'match'
    _parse_expr(session, p)  # scrutinee
    p.consume("LBRACE")
    arms = 0
    while p.peek().kind != "RBRACE":
        # pattern — could be an underscore literal or a regular expression
        if p.peek().kind == "IDENT" and p.peek().value == "_":
            p.consume("IDENT")
            p.stack.append(_identifier_leaf("_"))
        else:
            _parse_expr(session, p)
        p.consume("ARROW")
        _parse_expr(session, p)  # body
        arms += 1
        if p.peek().kind == "COMMA":
            p.consume("COMMA")
    p.consume("RBRACE")
    # Stack has [scrutinee, pat1, body1, pat2, body2, ...]. Total = 1 + 2*arms.
    p.emit(session, _match_cat(), arity=1 + 2 * arms)


# ---------------------------------------------------------------------------
# Choice — RChoice (choose / fail / stop)
# ---------------------------------------------------------------------------


def _parse_choose(session: Session, p: _ParserState) -> None:
    """choose [a, b, c] — angelic speculation primitive."""
    p.consume("IDENT")  # 'choose'
    p.consume("LBRACK")
    count = 0
    while p.peek().kind != "RBRACK":
        _parse_expr(session, p)
        count += 1
        if p.peek().kind == "COMMA":
            p.consume("COMMA")
    p.consume("RBRACK")
    p.emit(session, _choice_cat(RChoice.CHOOSE), arity=count)


def _parse_fail(session: Session, p: _ParserState) -> None:
    p.consume("IDENT")  # 'fail'
    # Bare leaf — no children, no DB roundtrip (kernel skips trivial-leaf intern).
    p.stack.append(_choice_cat(RChoice.FAIL))


def _parse_stop(session: Session, p: _ParserState) -> None:
    p.consume("IDENT")  # 'stop'
    p.stack.append(_choice_cat(RChoice.STOP))


# ---------------------------------------------------------------------------
# State — RState (save / restore / discard)
# ---------------------------------------------------------------------------


def _parse_save(session: Session, p: _ParserState) -> None:
    p.consume("IDENT")
    p.stack.append(_state_cat(RState.SAVE))


def _parse_restore(session: Session, p: _ParserState) -> None:
    p.consume("IDENT")
    p.stack.append(_state_cat(RState.RESTORE))


def _parse_discard(session: Session, p: _ParserState) -> None:
    p.consume("IDENT")
    p.stack.append(_state_cat(RState.DISCARD))


# ---------------------------------------------------------------------------
# Exception — RException (raise / resume)
# ---------------------------------------------------------------------------


def _parse_raise(session: Session, p: _ParserState) -> None:
    p.consume("IDENT")  # 'raise'
    # The current form.py path interns raise as a bare leaf regardless of
    # whether a payload follows; the payload is captured in the AST but the
    # recipe encoding strips it. Match that behavior here.
    p.stack.append(_exception_cat(RException.RAISE))


def _parse_resume(session: Session, p: _ParserState) -> None:
    p.consume("IDENT")
    p.stack.append(_exception_cat(RException.RESUME))


# ---------------------------------------------------------------------------
# Try / catch — RTry.TRY_CATCH
# ---------------------------------------------------------------------------


def _parse_try(session: Session, p: _ParserState) -> None:
    """try { body } catch { handler } — both arms always wrapped as DO
    blocks (matches form.py). Equivalence with the AST path requires the
    DO wrapping even for single-statement arms."""
    p.consume("IDENT")  # 'try'
    _parse_brace_block_always_wrap(session, p)  # body
    catch_tok = p.peek()
    if catch_tok.kind != "IDENT" or catch_tok.value != "catch":
        raise SyntaxError(
            f"form_stream: expected 'catch' at pos {catch_tok.pos}, got {catch_tok.value!r}"
        )
    p.consume("IDENT")  # 'catch'
    _parse_brace_block_always_wrap(session, p)  # handler
    p.emit(session, _try_cat(), arity=2)


def _parse_brace_block_always_wrap(session: Session, p: _ParserState) -> None:
    """Parse `{ stmts }` and ALWAYS wrap the result in Block.DO — matches
    form.py's `body = DoBlock(statements=stmts)` for with / try / method.
    Net effect: one NodeID (a DO recipe) on the stack."""
    p.consume("LBRACE")
    count = 0
    while p.peek().kind != "RBRACE":
        if p.peek().kind == "IDENT" and p.peek().value == "let":
            _parse_let(session, p)
        else:
            _parse_expr(session, p)
        count += 1
        if p.peek().kind == "SEMI":
            p.consume("SEMI")
        elif p.peek().kind != "RBRACE":
            t = p.peek()
            raise SyntaxError(
                f"form_stream: expected ';' or '}}' at pos {t.pos}, got {t.kind}"
            )
    p.consume("RBRACE")
    p.emit(session, _block_cat(RBlock.DO), arity=count)


# ---------------------------------------------------------------------------
# Delegate — RDelegate.DELEGATE_TO
# ---------------------------------------------------------------------------


def _parse_delegate(session: Session, p: _ParserState) -> None:
    """delegate @X to @Y — emit Delegate.DELEGATE_TO with [source, target]."""
    p.consume("IDENT")  # 'delegate'
    _parse_expr(session, p)  # source
    to_tok = p.peek()
    if to_tok.kind != "IDENT" or to_tok.value != "to":
        raise SyntaxError(
            f"form_stream: expected 'to' at pos {to_tok.pos}, got {to_tok.value!r}"
        )
    p.consume("IDENT")  # 'to'
    _parse_expr(session, p)  # target
    p.emit(session, _delegate_cat(), arity=2)


# ---------------------------------------------------------------------------
# Reverse — RReverse (undo / inverse)
# ---------------------------------------------------------------------------


def _parse_undo(session: Session, p: _ParserState) -> None:
    """undo (expr) — emit Reverse.UNDO with one child."""
    p.consume("IDENT")  # 'undo'
    _parse_primary(session, p)
    p.emit(session, _reverse_cat(RReverse.UNDO), arity=1)


def _parse_inverse(session: Session, p: _ParserState) -> None:
    """inverse(expr) — emit Reverse.INVERSE with one child. The parens are
    required by form.py's path; mirror that."""
    p.consume("IDENT")  # 'inverse'
    p.consume("LPAREN")
    _parse_expr(session, p)
    p.consume("RPAREN")
    p.emit(session, _reverse_cat(RReverse.INVERSE), arity=1)


# ---------------------------------------------------------------------------
# Common — RCommon.SHARED_BASE
# ---------------------------------------------------------------------------


def _parse_common(session: Session, p: _ParserState) -> None:
    """common @X @Y — two cells share a base for method dispatch."""
    p.consume("IDENT")  # 'common'
    _parse_primary(session, p)  # @X
    _parse_primary(session, p)  # @Y
    p.emit(session, _common_cat(), arity=2)


# ---------------------------------------------------------------------------
# Method — RMethod (define / invoke)
# ---------------------------------------------------------------------------


def _parse_method_def(session: Session, p: _ParserState) -> None:
    """method NAME on @X { body } — emit Method.DEFINE with
    [name-string, target, params-do-block, body]. Mirrors form.py's
    MethodDefExpr encoding. For this streaming subset we don't support
    parameter syntax (`(p1, p2)`) yet — params is an empty DO."""
    p.consume("IDENT")  # 'method'
    name = p.consume("IDENT").value
    on_tok = p.peek()
    if on_tok.kind != "IDENT" or on_tok.value != "on":
        raise SyntaxError(
            f"form_stream: expected 'on' at pos {on_tok.pos}, got {on_tok.value!r}"
        )
    p.consume("IDENT")  # 'on'
    _parse_expr(session, p)  # target
    _parse_brace_block_always_wrap(session, p)  # body — always wrapped in DO
    # Push [name-string, target, params-empty-do, body]
    body_id = p.stack.pop()
    target_id = p.stack.pop()
    name_id = _string_leaf(session, name)
    # Empty params: a DO block with 0 statements is an intern of (BLOCK.DO, []).
    params_id = intern_node(session, DOMAIN_RECIPE, _block_cat(RBlock.DO), [])
    p.stack.append(name_id)
    p.stack.append(target_id)
    p.stack.append(params_id)
    p.stack.append(body_id)
    p.emit(session, _method_cat(RMethod.DEFINE), arity=4)


def _parse_invoke(session: Session, p: _ParserState) -> None:
    """invoke NAME on @X [arg1, arg2, ...] — emit Method.INVOKE with
    [name-string, target, args...]. Mirrors form.py."""
    p.consume("IDENT")  # 'invoke'
    name = p.consume("IDENT").value
    on_tok = p.peek()
    if on_tok.kind != "IDENT" or on_tok.value != "on":
        raise SyntaxError(
            f"form_stream: expected 'on' at pos {on_tok.pos}, got {on_tok.value!r}"
        )
    p.consume("IDENT")  # 'on'
    _parse_expr(session, p)  # target — leaves one NodeID on stack
    # Args (optional, bracketed)
    arg_count = 0
    if p.peek().kind == "LBRACK":
        p.consume("LBRACK")
        while p.peek().kind != "RBRACK":
            _parse_expr(session, p)
            arg_count += 1
            if p.peek().kind == "COMMA":
                p.consume("COMMA")
        p.consume("RBRACK")
    # Stack currently has [target, arg1, ..., argN]. Prepend name-string by
    # popping all, inserting name at the front, pushing back.
    children: list[NodeID] = []
    for _ in range(1 + arg_count):
        children.append(p.stack.pop())
    children.reverse()  # restore order: [target, arg1, ..., argN]
    name_id = _string_leaf(session, name)
    p.stack.append(name_id)
    for c in children:
        p.stack.append(c)
    p.emit(session, _method_cat(RMethod.INVOKE), arity=2 + arg_count)


# ---------------------------------------------------------------------------
# Keyword dispatch — class-level dict mapping keyword → handler.
# Single `.get(kw)` instead of a long if/elif chain.
# ---------------------------------------------------------------------------


_KEYWORD_HANDLERS: dict[str, "Callable[[Session, _ParserState], None]"] = {
    "if":       _parse_if,
    "do":       _parse_do,
    "with":     _parse_with,
    "match":    _parse_match,
    "choose":   _parse_choose,
    "fail":     _parse_fail,
    "stop":     _parse_stop,
    "save":     _parse_save,
    "restore":  _parse_restore,
    "discard":  _parse_discard,
    "raise":    _parse_raise,
    "resume":   _parse_resume,
    "try":      _parse_try,
    "delegate": _parse_delegate,
    "undo":     _parse_undo,
    "inverse":  _parse_inverse,
    "common":   _parse_common,
    "method":   _parse_method_def,
    "invoke":   _parse_invoke,
}


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
