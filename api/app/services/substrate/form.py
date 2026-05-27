"""Form — the substrate-native language. Parser + evaluator.

A small recursive-descent parser implementing the grammar in
docs/coherence-substrate/form-language.md. Compiles Form text to an AST,
evaluates AST against the substrate kernel, returns NodeIDs / CellViews /
cell sets.

Grammar (informal BNF):

    program     := stmt*
    stmt        := query | bind | view_expr | atom

    query       := '?' query_body
    query_body  := 'equivalent' atom
                 | 'cells' ('where' filter)?
                 | 'cells' projection ('where' filter)?
                 | 'compatible' projection
    filter      := 'domain' '==' STRING
                 | 'name' 'matches' STRING

    bind        := ':' DOMAIN '.' NAME '=' compose
    compose     := atom | object_comp
    object_comp := '{' member (',' member)* ','? '}'
    member      := IDENT ':' atom

    view_expr   := atom '|>' atom

    atom        := nodeid_lit | trivial_ref | cell_ref | view_expr
    nodeid_lit  := '@' INT '.' INT '.' INT '.' INT
    trivial_ref := '~' IDENT                  # ~Memory, ~Integer, ~String, etc.
    cell_ref    := '@' DOMAIN '(' NAME ')'    # @memory(arrival_relational_ground)
                 | '@' DOMAIN                  # bare @memory → trivial domain blueprint

The evaluator returns a small union: NodeID, CellView, list[NamedCell],
list[CellView], or a Python str/None.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from app.services.substrate.category import (
    BAtomic,
    BBasic,
    BContainer,
    BDomain,
    BNumeric,
    BType,
    Level,
    RBasic,
    RBlock,
    RChoice,
    RCommon,
    RCompare,
    RCond,
    RDelegate,
    RException,
    RJump,
    RLogic,
    RMatch,
    RMath,
    RMethod,
    RProjection,
    RReactive,
    RReverse,
    RState,
    RTry,
)
from app.services.substrate.kernel import (
    CellView,
    NamedCell,
    NodeID,
    find_cells_compatible_with,
    find_equivalent_cells,
    lookup_cell,
    make_composite_blueprint,
    view_cell_through_blueprint,
)


# ---------------------------------------------------------------------------
# Trivial constructor table — agent-friendly names → NodeID
# ---------------------------------------------------------------------------


TRIVIAL_REFS: Dict[str, NodeID] = {
    # Numeric trivial blueprints
    "Bool": NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.BOOL),
    "Integer": NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.INTEGER),
    "Decimal": NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.DECIMAL),
    "String": NodeID(1, Level.TRIVIAL, BType.NUMERIC, BNumeric.STRING),
    # Atomic trivial blueprints
    "Slug": NodeID(1, Level.TRIVIAL, BType.ATOMIC, BAtomic.SLUG),
    "UUID": NodeID(1, Level.TRIVIAL, BType.ATOMIC, BAtomic.UUID),
    "Date": NodeID(1, Level.TRIVIAL, BType.ATOMIC, BAtomic.DATE),
    "Score": NodeID(1, Level.TRIVIAL, BType.ATOMIC, BAtomic.SCORE),
    "Path": NodeID(1, Level.TRIVIAL, BType.ATOMIC, BAtomic.PATH),
    "URL": NodeID(1, Level.TRIVIAL, BType.ATOMIC, BAtomic.URL),
    # Domain trivial blueprints
    "Idea": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.IDEA),
    "Spec": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.SPEC),
    "Concept": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.CONCEPT),
    "Memory": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.MEMORY),
    "Presence": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.PRESENCE),
    "Task": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.TASK),
    "Lineage": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.LINEAGE),
    "Witness": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.WITNESS),
    "Transmission": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.TRANSMISSION),
    "Resource": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.RESOURCE),
    "Guide": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.GUIDE),
    "LanguageView": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.LANGUAGE_VIEW),
    "KBPage": NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.KB_PAGE),
    # Container trivial blueprints
    "List": NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.LIST),
    "Object": NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.OBJECT),
    "Dictionary": NodeID(1, Level.BASIC, BBasic.CONTAINER, BContainer.DICTIONARY),
}


# Domain name (lowercase) → which TRIVIAL_REFS entry to use for `@<domain>`
DOMAIN_TO_REF: Dict[str, str] = {
    "memory": "Memory",
    "spec": "Spec",
    "idea": "Idea",
    "concept": "Concept",
    "presence": "Presence",
    "task": "Task",
    "lineage": "Lineage",
    "witness": "Witness",
    "transmission": "Transmission",
    "resource": "Resource",
    "guide": "Guide",
    "language_view": "LanguageView",
    "kb_page": "KBPage",
}


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------


@dataclass
class Token:
    kind: str
    value: str
    pos: int


# Token patterns live in the runtime-extensible registry
# `form_lexer._TOKEN_PATTERNS`. The tokenizer reads its compiled regex
# from there via `get_token_regex()`, so adding a new token kind no
# longer requires editing this file:
#
#     from app.services.substrate.form_lexer import register_token_pattern
#     register_token_pattern("DOLLAR", r"\$", before="PLUS")
#
# The compiled regex is cached and re-built on registry mutation.


def _token_re():
    """Return the registry's currently-compiled master token regex.

    Indirection lets the tokenizer pick up registry mutations without
    holding a stale compiled regex. The registry caches the compiled
    regex internally and invalidates it on `register_token_pattern` /
    `unregister_token_pattern`."""
    from app.services.substrate.form_lexer import get_token_regex
    return get_token_regex()


def tokenize(text: str) -> List[Token]:
    """Eager tokenization — returns all tokens at once. Use `tokenize_iter` or
    `tokenize_chunks` for lazy / streaming input."""
    tokens: List[Token] = []
    pos = 0
    while pos < len(text):
        m = _token_re().match(text, pos)
        if not m:
            raise SyntaxError(f"Form: unexpected char at pos {pos}: {text[pos]!r}")
        kind = m.lastgroup or ""
        value = m.group()
        if kind not in ("WS", "COMMENT"):
            tokens.append(Token(kind, value, pos))
        pos = m.end()
    tokens.append(Token("EOF", "", pos))
    return tokens


def tokenize_iter(text: str):
    """Lazy single-string tokenization — yields tokens one at a time.

    Equivalent to `tokenize(text)` but doesn't materialize the whole list
    upfront; useful when the parser only needs a few tokens of lookahead
    and the source string is held entirely in memory but the parse is
    short-lived.
    """
    pos = 0
    while pos < len(text):
        m = _token_re().match(text, pos)
        if not m:
            raise SyntaxError(f"Form: unexpected char at pos {pos}: {text[pos]!r}")
        kind = m.lastgroup or ""
        value = m.group()
        if kind not in ("WS", "COMMENT"):
            yield Token(kind, value, pos)
        pos = m.end()
    yield Token("EOF", "", pos)


def tokenize_chunks(chunks):
    """Streaming tokenization from an iterator of text chunks.

    `chunks` yields strings (any size). Output is a generator of Tokens
    terminated with EOF. Handles tokens that span chunk boundaries by
    holding a partial-buffer until a full match is confirmed.

    A match is only emitted when either (a) it ends with at least one
    character following (so we know we have the full extent), or (b) the
    input stream has ended. The first STRING in the chunk-boundary case
    is the canonical example: `"hello"` split as `["he`, `llo"]` parses
    correctly because we wait for the closing quote before yielding.
    """
    buf = ""
    pos = 0  # absolute position over the original stream (for error messages)
    chunks_done = False
    chunks_iter = iter(chunks)

    def try_match():
        """Return (token_or_None, advance_chars). None if can't safely match yet."""
        if not buf:
            return None, 0
        m = _token_re().match(buf, 0)
        if not m:
            # No match. If chunks may still arrive, the unmatched prefix
            # might be the start of a multi-char token (e.g. opening quote
            # of a string whose body lives in the next chunk). Wait.
            if not chunks_done:
                return None, 0
            raise SyntaxError(
                f"Form: unexpected char at pos {pos}: {buf[0]!r}"
            )
        # If match ends at end-of-buffer AND more chunks may be coming,
        # the match might extend — wait for more input.
        if m.end() == len(buf) and not chunks_done:
            return None, 0
        kind = m.lastgroup or ""
        value = m.group()
        token = None if kind in ("WS", "COMMENT") else Token(kind, value, pos)
        return token, m.end()

    while True:
        # Try to emit a token from the current buffer.
        token, advance = try_match()
        while advance:
            if token is not None:
                yield token
            buf = buf[advance:]
            pos += advance
            token, advance = try_match()

        if chunks_done:
            if buf:
                # Should never happen — try_match would have raised or matched.
                raise SyntaxError(f"Form: leftover buffer at pos {pos}: {buf!r}")
            yield Token("EOF", "", pos)
            return

        # Need more input.
        try:
            buf += next(chunks_iter)
        except StopIteration:
            chunks_done = True


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass
class NodeIDLit:
    package: int
    level: int
    type_: int
    instance: int


@dataclass
class TrivialRef:
    name: str  # "Memory", "Integer", etc.


@dataclass
class CellRef:
    domain: str
    name: Optional[str] = None  # if None, means @<domain> = the trivial domain blueprint


@dataclass
class Projection:
    cell: "AtomNode"
    blueprint: "AtomNode"


@dataclass
class ObjectComp:
    members: List[tuple]  # [(key_str, type_atom), ...]


@dataclass
class Filter:
    field: str  # "domain" | "name" | "shape" | "harmonic" | ...
    op: str    # "==" | "matches"
    value: Any  # str for literal compares; CellRef/NodeIDLit for atom-ref compares


@dataclass
class Query:
    kind: str            # "equivalent" | "cells" | "compatible"
    arg: Optional[Any] = None      # AtomNode for equivalent/compatible/projection
    filters: List[Filter] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Recipe AST nodes — code expressions that intern as Recipes
# ---------------------------------------------------------------------------


@dataclass
class IntLit:
    value: int


@dataclass
class BoolLit:
    value: bool


@dataclass
class StringLit:
    value: str


@dataclass
class Identifier:
    """A bare name — either a local binding or a built-in (true/false/fail/stop)."""
    name: str


@dataclass
class BinOp:
    op: str  # one of: + - * / %  ==  !=  <  <=  >  >=  &&  ||
    left: Any
    right: Any


@dataclass
class UnaryOp:
    op: str  # one of:  -  !
    operand: Any


@dataclass
class IfExpr:
    cond: Any
    then_branch: Any
    else_branch: Optional[Any] = None  # None for if-without-else


@dataclass
class WithExpr:
    """`with subject { body }` — BML's scoped-reference block.

    Binds `subject` as the implicit receiver of the block. `.self` inside the
    block resolves to the subject; `.field` (when method-access lands) resolves
    against the subject too. Structurally distinct from `do { let s = X; ... }`
    because the binding is implicit and the block IS the scope.

    Recipe shape: `(RBlock.WITH, [subject_recipe, body_recipe])`. Two with-blocks
    with identical (subject, body) interns share a Recipe NodeID through the
    kernel's content-addressing — the same equivalence guarantee `do` blocks
    already get.
    """
    subject: Any
    body: Any


@dataclass
class SelfRef:
    """`.self` — references the implicit subject of the enclosing `with` block.

    Interns as a trivial Recipe (RType.LOCAL_ACCESS with the SELF sentinel
    instance). Static analysis can later check that `.self` only appears inside
    a `with` block; for now we intern the recipe regardless and let runtime
    eval (when it lands) check scope.
    """
    pass


@dataclass
class DoBlock:
    statements: List[Any]  # last statement is the value of the block


@dataclass
class Let:
    name: str
    value: Any


@dataclass
class MatchArm:
    pattern: Any  # an expression to match against (or Identifier("_") for default)
    body: Any


@dataclass
class MatchExpr:
    scrutinee: Any
    arms: List[MatchArm]


@dataclass
class ChooseExpr:
    candidates: List[Any]  # choose [a, b, c]


@dataclass
class FailExpr:
    """`fail` keyword — signals failure, triggers backtracking."""


@dataclass
class StopExpr:
    """`stop` keyword — commits speculation, no more backtracking."""


@dataclass
class SaveExpr:
    """`save` — push current state onto the BML state-stack."""


@dataclass
class RestoreExpr:
    """`restore` — pop state from the BML state-stack."""


@dataclass
class DiscardExpr:
    """`discard` — drop the top of the BML state-stack without restoring."""


@dataclass
class RaiseExpr:
    """`raise` or `raise <value>` — raise an exception with an optional payload.

    When the payload is provided, the catch handler sees it as `.self` —
    the raised value becomes the implicit subject of the catch block.
    """
    value: Any = None


@dataclass
class ResumeExpr:
    """`resume` — resume from a raised exception."""


@dataclass
class DelegateExpr:
    """`delegate @X to @Y` — BML delegation inheritance.

    Dispatch against the source cell falls through to the target cell when the
    source doesn't carry the requested method. Interns as Recipe
    `(RBasic.DELEGATE, [source_ref, target_ref])`.
    """
    source: Any  # an atom-ref expression (CellRef / NodeIDLit)
    target: Any


@dataclass
class UndoExpr:
    """`undo <recipe>` — execute the inverse of the wrapped recipe.

    The recipe-execution engine pairs each recipe with its reverse; `undo`
    invokes the reverse pass. Interns as `(RBasic.REVERSE, [child_recipe])`.
    """
    child: Any


@dataclass
class InverseExpr:
    """`inverse(<recipe>)` — yield the inverse-recipe NodeID without running it.

    Interns as `(RBasic.REVERSE, [child_recipe])` distinguished by instance
    from `undo` (UNDO=1, INVERSE=2).
    """
    child: Any


@dataclass
class CommonExpr:
    """`common @X @Y` — BML Common Objects: X and Y share a base.

    Data-level shared-tissue declaration (different from `|>` view projection).
    Interns as `(RBasic.COMMON, [x_ref, y_ref])`.
    """
    a: Any
    b: Any


@dataclass
class MethodDefExpr:
    """`method NAME(p1, p2, ...) on @X { body }` — define a method on a cell.

    Params bind in the call frame when `invoke NAME on @X with [a, b]` fires.
    Empty params list when no parens are given (`method NAME on @X { body }`).
    Interns as `(RBasic.METHOD/DEFINE, [name_str, target_ref, params_seq, body])`.
    """
    name: str
    target: Any
    body: Any
    params: List[str] = field(default_factory=list)


@dataclass
class FnDef:
    """`defn name(p1, p2, ...) = body` — bind a callable in the enclosing frame.

    The body is captured as an AST and evaluated lazily on each call. The
    function's name is visible inside its own body so recursion works
    without a separate `rec` form. Frames are lexically scoped — a call
    pushes a child frame whose parent is the frame the function was
    defined in (closure semantics).
    """
    name: str
    params: List[str]
    body: Any


@dataclass
class MethodInvokeExpr:
    """`invoke NAME on @X` or `invoke NAME on @X with [a, b, c]`.

    Dispatch walks the delegation chain. Args evaluate in the caller's frame,
    then bind to the method's params in the call frame.
    Interns as `(RBasic.METHOD/INVOKE, [name_str, target_ref, *arg_recipes])`.
    """
    name: str
    target: Any
    args: List[Any] = field(default_factory=list)


@dataclass
class TryCatchExpr:
    """`try { body } catch { handler }` — catching frame for raised exceptions.

    The body runs in a sub-frame; if a RaiseSignal escapes, control falls to
    the handler (also a sub-frame). Without a raise, handler is unreached.
    Interns as `(RBasic.TRY/TRY_CATCH, [body_recipe, handler_recipe])`.
    """
    body: Any
    handler: Any


@dataclass
class OnChangeExpr:
    """`?on_change <query> { body }` — reactive lens: fire body on result change.

    Interns as `(RBasic.REACTIVE, [query_recipe, body_recipe])`. The
    subscription engine (when it lands) wires the query result to the body.
    """
    query: Any
    body: Any


@dataclass
class ProjectExpr:
    """`?project @cell @coord_fn` — spatial-projection lens: render through coords.

    Interns as `(RBasic.PROJECTION, [cell_ref, coord_fn_ref])`. The renderer
    (GPU-visualizer, memory-framebuffer) consumes the recipe and emits a frame.
    """
    cell: Any
    coord_fn: Any


@dataclass
class FnCall:
    """`name(arg1, arg2, ...)` — invoke a callable bound by FnDef."""
    name: str
    args: List[Any]


@dataclass
class IndexExpr:
    """`xs[i]` — index into a list, string, or dict.

    Runtime returns `xs[i]` for the target value and resolved index. Chains
    via the postfix loop in `parse_primary`: `xs[0][1]` becomes nested
    IndexExprs.
    """
    target: Any
    index: Any


@dataclass
class TernaryExpr:
    """`cond ? then : else` — three-arm conditional in expression position.

    Lower-precedence form of `if cond then a else b`; lives at the top
    of the precedence ladder.
    """
    cond: Any
    then_branch: Any
    else_branch: Any


@dataclass
class SetExpr:
    """`set name = value` — update an existing binding in the nearest enclosing
    frame that holds it. Distinct from `let` which always introduces a new
    binding in the current frame. Loops use `set` for accumulation.
    """
    name: str
    value: Any


@dataclass
class ForExpr:
    """`for x in xs { body }` — iterate xs, bind each to x in a sub-frame,
    evaluate body. Returns the list of body-results (like map but imperative).
    """
    var: str
    iter: Any
    body: Any


@dataclass
class WhileExpr:
    """`while cond { body }` — evaluate body while cond is truthy.
    Returns the last body-result, or null if the loop never entered.
    """
    cond: Any
    body: Any


@dataclass
class DictExpr:
    """`{a: 1, b: 2}` — composed record. Honors the structural composition
    discipline (CLAUDE.md): keys participate in identity; positions don't.

    Interns as `R_Block.SEQUENCE` with one `R_Block.LET` child per (key, value)
    pair — the same shape frontmatter fields take. At runtime, evaluates to
    a Python dict for ergonomics; field access `d.a` resolves via `_resolve_access`.
    """
    pairs: List[Any]  # list of (key_str, value_ast) tuples


@dataclass
class Access:
    """`target.field` — fractal-tree navigation.

    Lets Form walk into the holographic composition of a Cell, Blueprint,
    or Recipe: `@memory(x).blueprint.category` reaches the type the cell
    IS; `@memory(x).blueprint.children` reaches the ordered child
    Blueprints; `@memory(x).ctor.children[0]` reaches the first composed
    value. The dot is the seam between levels.

    The point of this primitive is the same point the substrate's
    content-addressing makes structurally: *we don't stuff structure
    into slugs or flat objects, we keep the tree.* The slug is a query
    key; the tree is the body.
    """
    target: Any
    field: str


@dataclass
class MethodCall:
    """`target.method(arg1, arg2, ...)` — for `.child(n)` and similar
    indexed/parameterized accesses on a Cell, Blueprint, or Recipe."""
    target: Any
    method: str
    args: List[Any]


AtomNode = Union[NodeIDLit, TrivialRef, CellRef, Projection]
ExprNode = Any  # any AST node — too many to enumerate


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


# Bootstrap-keyword dispatch — replaces a ~30-way if/elif chain that ran
# per IDENT token. Each entry maps the keyword to the Parser method name
# that handles it; `parse_keyword_or_ident` does one `.get(kw)` and
# `getattr(self, name)()`.
_KEYWORD_DISPATCH: Dict[str, str] = {
    "true":     "_parse_true",
    "false":    "_parse_false",
    "if":       "parse_if",
    "do":       "parse_do_block",
    "with":     "parse_with",
    "let":      "parse_let",
    "match":    "parse_match",
    "choose":   "parse_choose",
    "fail":     "_parse_fail",
    "stop":     "_parse_stop",
    "save":     "_parse_save",
    "restore":  "_parse_restore",
    "discard":  "_parse_discard",
    "raise":    "parse_raise",
    "resume":   "_parse_resume",
    "delegate": "parse_delegate",
    "undo":     "parse_undo",
    "inverse":  "parse_inverse",
    "common":   "parse_common",
    "method":   "parse_method_def",
    "invoke":   "parse_method_invoke",
    "try":      "parse_try_catch",
    "for":      "parse_for",
    "while":    "parse_while",
    "set":      "parse_set",
    "defn":     "parse_defn",
}


class Parser:
    def __init__(self, tokens, *, prefer_registered: bool = False):
        """Tokens may be:
        - a List[Token] — eager, classic mode
        - any iterator of Token — streaming mode, lazily extending `_buf`
          as `peek(n)` reaches forward; speculation rewinds `pos` within
          the buffered prefix so backtracking still works.
        """
        if isinstance(tokens, list):
            self._buf: List[Token] = tokens
            self._stream = None
        else:
            self._buf = []
            self._stream = iter(tokens)
        self.pos = 0
        # When True, the parser consults the user-registered keyword
        # registry BEFORE falling through to bootstrap hardcoded handlers.
        # Used by `bootstrap_self_host` and the self-hosting demonstration —
        # see docs/coherence-substrate/form-language.md ("Self-hosting,
        # partial").
        self.prefer_registered = prefer_registered

    # The legacy attribute name — kept so older code that reads
    # `parser.tokens` directly still works (it returns the buffered prefix
    # when streaming).
    @property
    def tokens(self) -> List[Token]:
        return self._buf

    def _ensure(self, n: int) -> None:
        """Make sure `_buf` has at least `self.pos + n + 1` tokens.

        Pulls from the lazy stream until the buffer reaches that depth or
        the stream is exhausted (the final EOF token is naturally yielded
        by tokenize_iter / tokenize_chunks, so the buffer terminates).
        """
        if self._stream is None:
            return
        needed = self.pos + n + 1
        while len(self._buf) < needed:
            try:
                self._buf.append(next(self._stream))
            except StopIteration:
                self._stream = None
                return

    def peek(self, n: int = 0) -> Token:
        self._ensure(n)
        if self.pos + n >= len(self._buf):
            # Past EOF (defensive — shouldn't normally happen because tokenize
            # emits a trailing EOF). Return a synthetic EOF token.
            return Token("EOF", "", self._buf[-1].pos if self._buf else 0)
        return self._buf[self.pos + n]

    def consume(self, kind: Optional[str] = None) -> Token:
        t = self.peek()
        if kind is not None and t.kind != kind:
            raise SyntaxError(f"Form: expected {kind}, got {t.kind}({t.value!r}) at pos {t.pos}")
        self.pos += 1
        return t

    def parse(self):
        if self.peek().kind == "QMARK":
            return self.parse_query()
        if self.peek().kind == "COLON":
            return self.parse_bind()
        return self.parse_expr()

    # ----- Expression grammar with precedence -----------------------------

    # Lowest precedence: ||
    def parse_expr(self) -> ExprNode:
        if self.prefer_registered:
            # Use precedence-climbing if any binary operators are registered.
            # Otherwise fall through to the bootstrap ladder so expressions
            # like `x + 1` keep working when only keywords are self-hosted.
            from app.services.substrate.form_operators import _BINARY_OPERATORS
            if _BINARY_OPERATORS:
                from app.services.substrate.form_operators import parse_with_precedence
                base = parse_with_precedence(self, 0)
                return self._maybe_ternary(base)
        base = self.parse_or()
        return self._maybe_ternary(base)

    def _maybe_ternary(self, cond: ExprNode) -> ExprNode:
        """If a `?` follows, consume `then ? else`. Otherwise return cond as-is."""
        if self.peek().kind == "QMARK":
            # Only treat as ternary when `?` is followed by an expression — the
            # query form `?cells` etc. parses inside parse_primary, never here.
            # By the time we see a QMARK at expression-end position, it's a ternary.
            self.consume("QMARK")
            then_branch = self.parse_or()
            if self.peek().kind != "COLON":
                raise SyntaxError("Form: expected ':' after ternary `?` branch")
            self.consume("COLON")
            else_branch = self.parse_or()
            return TernaryExpr(cond=cond, then_branch=then_branch, else_branch=else_branch)
        return cond

    def parse_or(self) -> ExprNode:
        left = self.parse_and()
        while self.peek().kind == "OR":
            self.consume("OR")
            right = self.parse_and()
            left = BinOp("||", left, right)
        return left

    def parse_and(self) -> ExprNode:
        left = self.parse_compare()
        while self.peek().kind == "AND":
            self.consume("AND")
            right = self.parse_compare()
            left = BinOp("&&", left, right)
        return left

    def parse_compare(self) -> ExprNode:
        left = self.parse_add()
        op_kind = self.peek().kind
        op_map = {"EQ": "==", "NEQ": "!=", "LT": "<", "LE": "<=", "GT": ">", "GE": ">="}
        if op_kind in op_map:
            self.consume(op_kind)
            right = self.parse_add()
            return BinOp(op_map[op_kind], left, right)
        return left

    def parse_add(self) -> ExprNode:
        left = self.parse_mul()
        while self.peek().kind in ("PLUS", "MINUS"):
            t = self.consume()
            right = self.parse_mul()
            left = BinOp("+" if t.kind == "PLUS" else "-", left, right)
        return left

    def parse_mul(self) -> ExprNode:
        left = self.parse_unary()
        while self.peek().kind in ("STAR", "SLASH", "PERCENT"):
            t = self.consume()
            op = {"STAR": "*", "SLASH": "/", "PERCENT": "%"}[t.kind]
            right = self.parse_unary()
            left = BinOp(op, left, right)
        return left

    def parse_unary(self) -> ExprNode:
        # In prefer_registered mode, check the unary-prefix operator
        # registry first. If a rule matches, use it. Otherwise fall
        # through to the bootstrap unary handling — the registry doesn't
        # have to be populated for prefer mode to keep working.
        if self.prefer_registered:
            from app.services.substrate.form_operators import (
                apply_unary, lookup_unary_prefix_operator,
            )
            t = self.peek()
            op = lookup_unary_prefix_operator(t.kind)
            if op is not None:
                self.consume(t.kind)
                operand = self.parse_unary()
                return apply_unary(op, operand)
            # Fall through to bootstrap below.

        # Bootstrap path: hardcoded unary prefixes.
        if self.peek().kind == "BANG":
            self.consume("BANG")
            return UnaryOp("!", self.parse_unary())
        if self.peek().kind == "MINUS":
            self.consume("MINUS")
            return UnaryOp("-", self.parse_unary())
        return self.parse_projection()

    def parse_projection(self) -> ExprNode:
        a = self.parse_primary()
        # Postfix loop: handles |> projection AND .field / .method(args)
        # tree-navigation. The dot is the seam between holographic levels —
        # the substrate's fractal composition becomes navigable syntax.
        while True:
            t = self.peek()
            if t.kind == "PROJECT":
                self.consume("PROJECT")
                b = self.parse_primary()
                a = Projection(cell=a, blueprint=b)
                continue
            if t.kind == "DOT":
                # `.field` access — but only when followed by an IDENT that
                # isn't `self` (the latter is a primary `.self` expression).
                # If we already have a target on the left (we do, since
                # parse_primary returned `a`), then `a.field` is access.
                # Bare `.self` was handled in parse_primary when no left
                # target existed.
                next_tok = self.peek(1)
                if next_tok.kind != "IDENT":
                    break
                if next_tok.value == "self":
                    # Don't consume — `.self` after an expression isn't
                    # valid; let downstream parsers handle the error.
                    break
                self.consume("DOT")
                field_tok = self.consume("IDENT")
                field = field_tok.value
                # Optional method-call: `.field(args)` becomes MethodCall.
                if self.peek().kind == "LPAREN":
                    self.consume("LPAREN")
                    args: List[Any] = []
                    while self.peek().kind != "RPAREN":
                        args.append(self.parse_expr())
                        if self.peek().kind == "COMMA":
                            self.consume("COMMA")
                    self.consume("RPAREN")
                    a = MethodCall(target=a, method=field, args=args)
                else:
                    a = Access(target=a, field=field)
                continue
            if t.kind == "LBRACK":
                # Postfix indexing: `target[index]`. Distinguish from a list
                # literal in atom position by checking the LEFT context: at
                # this point in parse_projection's postfix loop we always have
                # a target on the left, so `[` must be indexing.
                self.consume("LBRACK")
                index = self.parse_expr()
                self.consume("RBRACK")
                a = IndexExpr(target=a, index=index)
                continue
            break
        return a

    def parse_primary(self) -> ExprNode:
        """Dispatch primary-atom parsing through the runtime-extensible
        registry. Each token kind ("INT", "STRING", "AT", "TILDE", "DOT",
        "LPAREN", "LBRACK", "LBRACE", "IDENT", "QMARK") has a registered
        handler in `form_atoms.py`. New atom shapes can be added at
        runtime by `register_atom(token_kind, handler)`.

        Closes the form-language.md gap: "Primary-atom parsing ... still
        hardcoded" — no longer hardcoded.
        """
        from app.services.substrate.form_atoms import dispatch_atom
        t = self.peek()
        return dispatch_atom(self, t.kind)

    def parse_keyword_or_ident(self) -> ExprNode:
        t = self.peek()
        kw = t.value

        # Self-hosting mode — try the user-registered registry FIRST.
        # If a registered rule matches, use its template-built AST.
        # Otherwise fall through to bootstrap handlers.
        if self.prefer_registered:
            from app.services.substrate.form_rules import try_apply_keyword_rule
            node = try_apply_keyword_rule(self, kw)
            if node is not None:
                return node

        # Built-in keywords (the bootstrap grammar) — dispatched via a
        # class-level dict so the hot path is a single `.get(kw)` instead
        # of walking ~30 string-equality comparisons per IDENT token.
        handler_name = _KEYWORD_DISPATCH.get(kw)
        if handler_name is not None:
            return getattr(self, handler_name)()

        # User-registered keywords (the rule-driven extension point —
        # this is where the grammar becomes alive at runtime).
        if not self.prefer_registered:
            from app.services.substrate.form_rules import try_apply_keyword_rule
            node = try_apply_keyword_rule(self, kw)
            if node is not None:
                return node

        # Otherwise it's an Identifier (local name reference) — or a
        # function call if followed by `(`. The call syntax lives here so
        # any bare name in expression position can become a call.
        self.consume("IDENT")
        if self.peek().kind == "LPAREN":
            self.consume("LPAREN")
            args: List[Any] = []
            while self.peek().kind != "RPAREN":
                args.append(self.parse_expr())
                if self.peek().kind == "COMMA":
                    self.consume("COMMA")
            self.consume("RPAREN")
            return FnCall(name=kw, args=args)
        return Identifier(name=kw)

    def parse_defn(self) -> "FnDef":
        """`defn name(p1, p2, ...) = body` — function definition.

        The function name and parameters are plain identifiers. Body is
        any expression. Closure semantics are handled at runtime: the
        FnDef binds in the current frame; calling it pushes a child
        frame whose parent is the defining frame.
        """
        self.consume("IDENT")  # 'defn'
        name = self.consume("IDENT").value
        self.consume("LPAREN")
        params: List[str] = []
        while self.peek().kind != "RPAREN":
            params.append(self.consume("IDENT").value)
            if self.peek().kind == "COMMA":
                self.consume("COMMA")
        self.consume("RPAREN")
        self.consume("ASSIGN")
        body = self.parse_expr()
        return FnDef(name=name, params=params, body=body)

    # ------- Bare-keyword leaves — small helpers for the dispatch dict.
    def _parse_true(self) -> BoolLit:
        self.consume("IDENT")
        return BoolLit(True)

    def _parse_false(self) -> BoolLit:
        self.consume("IDENT")
        return BoolLit(False)

    def _parse_fail(self) -> FailExpr:
        self.consume("IDENT")
        return FailExpr()

    def _parse_stop(self) -> StopExpr:
        self.consume("IDENT")
        return StopExpr()

    def _parse_save(self) -> SaveExpr:
        self.consume("IDENT")
        return SaveExpr()

    def _parse_restore(self) -> RestoreExpr:
        self.consume("IDENT")
        return RestoreExpr()

    def _parse_discard(self) -> DiscardExpr:
        self.consume("IDENT")
        return DiscardExpr()

    def _parse_resume(self) -> ResumeExpr:
        self.consume("IDENT")
        return ResumeExpr()

    def parse_raise(self) -> RaiseExpr:
        self.consume("IDENT")  # 'raise'
        # Optional value after raise; if the next token starts an
        # expression (atom, paren, ident, etc.) parse it as payload.
        nxt = self.peek().kind
        if nxt in ("INT", "STRING", "AT", "TILDE", "LPAREN", "LBRACK", "IDENT", "DOT"):
            # Some IDENTs ARE statement terminators in catch/end context;
            # be permissive and parse-attempt — fall back to no value on
            # certain reserved follow-ups.
            if nxt == "IDENT" and self.peek().value in ("catch", "then", "else", "end"):
                return RaiseExpr()
            return RaiseExpr(value=self.parse_expr())
        return RaiseExpr()

    def parse_if(self) -> IfExpr:
        self.consume("IDENT")  # 'if'
        cond = self.parse_expr()
        if self.peek().kind != "IDENT" or self.peek().value != "then":
            raise SyntaxError("Form: expected 'then' after if-condition")
        self.consume("IDENT")  # 'then'
        then_branch = self.parse_expr()
        else_branch = None
        if self.peek().kind == "IDENT" and self.peek().value == "else":
            self.consume("IDENT")  # 'else'
            else_branch = self.parse_expr()
        return IfExpr(cond=cond, then_branch=then_branch, else_branch=else_branch)

    def parse_do_block(self) -> DoBlock:
        self.consume("IDENT")  # 'do'
        self.consume("LBRACE")
        stmts = []
        while self.peek().kind != "RBRACE":
            stmts.append(self.parse_expr())
            if self.peek().kind == "SEMI":
                self.consume("SEMI")
            elif self.peek().kind == "RBRACE":
                break
            else:
                # allow whitespace-separated statements
                pass
        self.consume("RBRACE")
        return DoBlock(statements=stmts)

    def parse_with(self) -> WithExpr:
        """`with subject { body }` — BML's scoped-reference block.

        The subject can be any expression (atom-ref, identifier, recipe).
        The body is a brace-delimited block of statements, like `do { ... }`.
        """
        self.consume("IDENT")  # 'with'
        subject = self.parse_expr()
        self.consume("LBRACE")
        stmts = []
        while self.peek().kind != "RBRACE":
            stmts.append(self.parse_expr())
            if self.peek().kind == "SEMI":
                self.consume("SEMI")
            elif self.peek().kind == "RBRACE":
                break
        self.consume("RBRACE")
        # Body is a do-block wrapper around the statements (gives us free
        # sequence semantics + content-addressed equality).
        body = DoBlock(statements=stmts)
        return WithExpr(subject=subject, body=body)

    def parse_let(self) -> Let:
        self.consume("IDENT")  # 'let'
        name = self.consume("IDENT").value
        self.consume("ASSIGN")
        value = self.parse_expr()
        return Let(name=name, value=value)

    def parse_match(self) -> MatchExpr:
        self.consume("IDENT")  # 'match'
        scrutinee = self.parse_expr()
        self.consume("LBRACE")
        arms = []
        while self.peek().kind != "RBRACE":
            pattern = self.parse_expr()
            self.consume("ARROW")
            body = self.parse_expr()
            arms.append(MatchArm(pattern=pattern, body=body))
            if self.peek().kind == "COMMA":
                self.consume("COMMA")
        self.consume("RBRACE")
        return MatchExpr(scrutinee=scrutinee, arms=arms)

    def parse_choose(self) -> ChooseExpr:
        self.consume("IDENT")  # 'choose'
        self.consume("LBRACK")
        candidates = []
        while self.peek().kind != "RBRACK":
            candidates.append(self.parse_expr())
            if self.peek().kind == "COMMA":
                self.consume("COMMA")
        self.consume("RBRACK")
        return ChooseExpr(candidates=candidates)

    def parse_delegate(self) -> DelegateExpr:
        """`delegate @X to @Y`"""
        self.consume("IDENT")  # 'delegate'
        source = self.parse_expr()
        if self.peek().kind != "IDENT" or self.peek().value != "to":
            raise SyntaxError("Form: expected 'to' after delegate source")
        self.consume("IDENT")  # 'to'
        target = self.parse_expr()
        return DelegateExpr(source=source, target=target)

    def parse_undo(self) -> UndoExpr:
        """`undo <expr>`"""
        self.consume("IDENT")  # 'undo'
        child = self.parse_expr()
        return UndoExpr(child=child)

    def parse_inverse(self) -> InverseExpr:
        """`inverse(<expr>)`"""
        self.consume("IDENT")  # 'inverse'
        self.consume("LPAREN")
        child = self.parse_expr()
        self.consume("RPAREN")
        return InverseExpr(child=child)

    def parse_common(self) -> CommonExpr:
        """`common @X @Y`"""
        self.consume("IDENT")  # 'common'
        a = self.parse_expr()
        b = self.parse_expr()
        return CommonExpr(a=a, b=b)

    def parse_method_def(self) -> MethodDefExpr:
        """`method NAME(p1, p2, ...) on @X { body }` — params optional."""
        self.consume("IDENT")  # 'method'
        name = self.consume("IDENT").value
        params: List[str] = []
        if self.peek().kind == "LPAREN":
            self.consume("LPAREN")
            while self.peek().kind != "RPAREN":
                params.append(self.consume("IDENT").value)
                if self.peek().kind == "COMMA":
                    self.consume("COMMA")
            self.consume("RPAREN")
        if self.peek().kind != "IDENT" or self.peek().value != "on":
            raise SyntaxError("Form: expected 'on' after method name")
        self.consume("IDENT")  # 'on'
        target = self.parse_expr()
        self.consume("LBRACE")
        stmts = []
        while self.peek().kind != "RBRACE":
            stmts.append(self.parse_expr())
            if self.peek().kind == "SEMI":
                self.consume("SEMI")
            elif self.peek().kind == "RBRACE":
                break
        self.consume("RBRACE")
        body = DoBlock(statements=stmts)
        return MethodDefExpr(name=name, target=target, body=body, params=params)

    def parse_method_invoke(self) -> MethodInvokeExpr:
        """`invoke NAME on @X` or `invoke NAME on @X with [a, b]`."""
        self.consume("IDENT")  # 'invoke'
        name = self.consume("IDENT").value
        if self.peek().kind != "IDENT" or self.peek().value != "on":
            raise SyntaxError("Form: expected 'on' after invoke name")
        self.consume("IDENT")  # 'on'
        target = self.parse_expr()
        args: List[Any] = []
        if self.peek().kind == "IDENT" and self.peek().value == "with":
            self.consume("IDENT")  # 'with'
            self.consume("LBRACK")
            while self.peek().kind != "RBRACK":
                args.append(self.parse_expr())
                if self.peek().kind == "COMMA":
                    self.consume("COMMA")
            self.consume("RBRACK")
        return MethodInvokeExpr(name=name, target=target, args=args)

    def parse_try_catch(self) -> "TryCatchExpr":
        """`try { body } catch { handler }`."""
        self.consume("IDENT")  # 'try'
        self.consume("LBRACE")
        body_stmts = []
        while self.peek().kind != "RBRACE":
            body_stmts.append(self.parse_expr())
            if self.peek().kind == "SEMI":
                self.consume("SEMI")
            elif self.peek().kind == "RBRACE":
                break
        self.consume("RBRACE")
        if self.peek().kind != "IDENT" or self.peek().value != "catch":
            raise SyntaxError("Form: expected 'catch' after try-body")
        self.consume("IDENT")  # 'catch'
        self.consume("LBRACE")
        handler_stmts = []
        while self.peek().kind != "RBRACE":
            handler_stmts.append(self.parse_expr())
            if self.peek().kind == "SEMI":
                self.consume("SEMI")
            elif self.peek().kind == "RBRACE":
                break
        self.consume("RBRACE")
        return TryCatchExpr(
            body=DoBlock(statements=body_stmts),
            handler=DoBlock(statements=handler_stmts),
        )

    def parse_for(self) -> "ForExpr":
        """`for x in <iter> { body }` — iterate, bind, evaluate body."""
        self.consume("IDENT")  # 'for'
        var = self.consume("IDENT").value
        if self.peek().kind != "IDENT" or self.peek().value != "in":
            raise SyntaxError("Form: expected 'in' after for-variable")
        self.consume("IDENT")  # 'in'
        iter_expr = self.parse_expr()
        self.consume("LBRACE")
        stmts = []
        while self.peek().kind != "RBRACE":
            stmts.append(self.parse_expr())
            if self.peek().kind == "SEMI":
                self.consume("SEMI")
            elif self.peek().kind == "RBRACE":
                break
        self.consume("RBRACE")
        return ForExpr(var=var, iter=iter_expr, body=DoBlock(statements=stmts))

    def parse_while(self) -> "WhileExpr":
        """`while <cond> { body }` — evaluate body while cond is truthy."""
        self.consume("IDENT")  # 'while'
        cond = self.parse_expr()
        self.consume("LBRACE")
        stmts = []
        while self.peek().kind != "RBRACE":
            stmts.append(self.parse_expr())
            if self.peek().kind == "SEMI":
                self.consume("SEMI")
            elif self.peek().kind == "RBRACE":
                break
        self.consume("RBRACE")
        return WhileExpr(cond=cond, body=DoBlock(statements=stmts))

    def parse_set(self) -> "SetExpr":
        """`set name = value` — mutate an existing binding in the nearest
        enclosing frame holding it."""
        self.consume("IDENT")  # 'set'
        name = self.consume("IDENT").value
        if self.peek().kind != "ASSIGN":
            raise SyntaxError("Form: expected '=' after `set` name")
        self.consume("ASSIGN")
        value = self.parse_expr()
        return SetExpr(name=name, value=value)

    def parse_on_change(self) -> OnChangeExpr:
        """`?on_change <query> { body }` — entered via parse_query branch."""
        query = self.parse_expr()
        self.consume("LBRACE")
        stmts = []
        while self.peek().kind != "RBRACE":
            stmts.append(self.parse_expr())
            if self.peek().kind == "SEMI":
                self.consume("SEMI")
            elif self.peek().kind == "RBRACE":
                break
        self.consume("RBRACE")
        return OnChangeExpr(query=query, body=DoBlock(statements=stmts))

    def parse_project(self) -> ProjectExpr:
        """`?project @cell @coord_fn` — entered via parse_query branch."""
        cell = self.parse_expr()
        coord_fn = self.parse_expr()
        return ProjectExpr(cell=cell, coord_fn=coord_fn)

    def parse_list_literal(self) -> List[ExprNode]:
        self.consume("LBRACK")
        items = []
        while self.peek().kind != "RBRACK":
            items.append(self.parse_expr())
            if self.peek().kind == "COMMA":
                self.consume("COMMA")
        self.consume("RBRACK")
        return items

    def parse_dict_literal(self) -> "DictExpr":
        """`{key: value, key: value, ...}` — key is an IDENT or STRING."""
        self.consume("LBRACE")
        pairs: List[tuple] = []
        while self.peek().kind != "RBRACE":
            key_tok = self.peek()
            if key_tok.kind == "IDENT":
                self.consume("IDENT")
                key = key_tok.value
            elif key_tok.kind == "STRING":
                self.consume("STRING")
                key = _unquote(key_tok.value)
            else:
                raise SyntaxError(
                    f"Form: dict key must be IDENT or STRING at pos {key_tok.pos}"
                )
            if self.peek().kind != "COLON":
                raise SyntaxError("Form: expected ':' after dict key")
            self.consume("COLON")
            value = self.parse_expr()
            pairs.append((key, value))
            if self.peek().kind == "COMMA":
                self.consume("COMMA")
        self.consume("RBRACE")
        return DictExpr(pairs=pairs)

    # ----- Backwards-compat wrapper for query-style atoms -----------------

    def parse_query(self) -> Query:
        self.consume("QMARK")
        kw = self.consume("IDENT").value
        if kw == "equivalent":
            arg = self.parse_atom_or_view()
            filters = []
            if self.peek().kind == "IDENT" and self.peek().value == "where":
                self.consume("IDENT")
                filters.append(self.parse_filter())
            return Query(kind="equivalent", arg=arg, filters=filters)
        if kw == "compatible":
            self.consume("PROJECT")
            arg = self.parse_atom_or_view()
            return Query(kind="compatible", arg=arg)
        if kw == "shaped_by":
            # `?shaped_by @<cell>` — cells whose SHAPES resonance edge points at <cell>.
            # The cross-discipline bridge query: gives back every cell sharing
            # the target's geometric form, regardless of source domain.
            arg = self.parse_atom_or_view()
            return Query(kind="shaped_by", arg=arg)
        if kw == "harmonic_at":
            # `?harmonic_at @<cell>` — cells whose HARMONIC_AT edge points at <cell>.
            arg = self.parse_atom_or_view()
            return Query(kind="harmonic_at", arg=arg)
        if kw == "downstream":
            # `?downstream @<cell>` — cells this cell points at via any cell-ref recipe.
            # The forward direction of `?shaped_by` / `?harmonic_at`. Closes GAP-T1.
            arg = self.parse_atom_or_view()
            return Query(kind="downstream", arg=arg)
        if kw == "lattice":
            # `?lattice` — substrate-snapshot lens. Returns counts of blueprints /
            # recipes / cells without touching them. The framebuffer-analog: read
            # the substrate's current shape as a single observation.
            return Query(kind="lattice")
        if kw == "keywords":
            # `?keywords` — grammar-introspection lens. Returns the names of every
            # runtime-registered Form keyword. Lets the grammar see itself; BMF
            # property — the parser knows its own rules.
            return Query(kind="keywords")
        if kw == "vocabulary":
            # `?vocabulary` — verb-cluster lens. Returns the histogram of recipe
            # types (RBasic categories) and blueprint types currently interned.
            # Reveals which regions of the numeric verb-space the body's
            # circulation occupies. A body with only one verb's count > 0 is a
            # body without circulation across language layers.
            return Query(kind="vocabulary")
        if kw == "on_change":
            # `?on_change <query> { body }` — reactive lens (form layer).
            # Interns the subscription intent; subscription engine fires the
            # body when query result changes.
            return Query(kind="on_change", arg=self.parse_on_change())
        if kw == "project":
            # `?project @cell @coord_fn` — spatial-projection lens (form layer).
            # Interns the render intent; renderer (GPU-visualizer, memory-
            # framebuffer) consumes when it lands.
            return Query(kind="project", arg=self.parse_project())
        if kw == "cells":
            arg = None
            if self.peek().kind == "PROJECT":
                self.consume("PROJECT")
                arg = self.parse_atom_or_view()
            filters = []
            if self.peek().kind == "IDENT" and self.peek().value == "where":
                self.consume("IDENT")
                filters.append(self.parse_filter())
            return Query(kind="cells", arg=arg, filters=filters)
        # Generic registry-driven dispatch — any registered query verb that
        # doesn't need a custom argument-parser (e.g. `?queries`, plus any
        # runtime-registered verb via `register_form_query`) parses as a
        # bare `?<verb>`. The evaluator dispatches via the registry; if no
        # handler is registered it raises NameError at evaluate-time.
        from app.services.substrate.form_queries import lookup_form_query
        if lookup_form_query(kw) is not None:
            return Query(kind=kw)
        # Unknown verb — still parse as a bare query so the evaluator's
        # registry-driven NameError is what surfaces (consistent error
        # shape regardless of whether the verb is parser-known or not).
        return Query(kind=kw)

    def parse_filter(self) -> Filter:
        field_tok = self.consume("IDENT")
        op_tok = self.peek()
        if op_tok.kind == "EQ":
            self.consume("EQ")
            rhs_tok = self.peek()
            # `==` accepts either a STRING literal (compare against a plain value)
            # or an @atom-ref (compare against a cell/blueprint NodeID).
            if rhs_tok.kind == "STRING":
                val = self.consume("STRING").value
                return Filter(field=field_tok.value, op="==", value=_unquote(val))
            if rhs_tok.kind == "AT":
                ref = self.parse_at()  # CellRef or NodeIDLit
                return Filter(field=field_tok.value, op="==", value=ref)
            raise SyntaxError(
                f"Form: expected STRING or @atom-ref after '==' at pos {rhs_tok.pos}"
            )
        if op_tok.kind == "IDENT" and op_tok.value == "matches":
            self.consume("IDENT")
            val = self.consume("STRING").value
            return Filter(field=field_tok.value, op="matches", value=_unquote(val))
        raise SyntaxError(f"Form: expected '==' or 'matches' at pos {op_tok.pos}")

    def parse_bind(self):
        # Phase-4 stub — bind isn't evaluated yet (would create/update cells).
        # Skip through the rest as an expression for round-trip; raise on eval.
        raise NotImplementedError("Form bind (':<domain>.<name> = ...') not yet evaluable")

    def parse_atom_or_view(self) -> AtomNode:
        # Backwards-compat — used by queries. Use parse_projection for new code.
        return self.parse_projection()

    def parse_atom(self) -> AtomNode:
        # Backwards-compat — used by queries.
        return self.parse_primary()

    def parse_at(self) -> Union[NodeIDLit, CellRef]:
        self.consume("AT")
        first = self.peek()
        if first.kind == "INT":
            # NodeID literal: @p.l.t.i
            p = int(self.consume("INT").value)
            self.consume("DOT")
            l = int(self.consume("INT").value)
            self.consume("DOT")
            t = int(self.consume("INT").value)
            self.consume("DOT")
            i = int(self.consume("INT").value)
            return NodeIDLit(p, l, t, i)
        if first.kind == "IDENT":
            domain = self.consume("IDENT").value
            if self.peek().kind == "LPAREN":
                self.consume("LPAREN")
                # Name can be IDENT, STRING, or composed of IDENT-DOT-IDENT
                name = self._consume_name()
                self.consume("RPAREN")
                return CellRef(domain=domain, name=name)
            return CellRef(domain=domain, name=None)
        raise SyntaxError(f"Form: expected INT or IDENT after @, got {first.kind}")

    def _consume_name(self) -> str:
        t = self.peek()
        if t.kind == "STRING":
            self.consume("STRING")
            return _unquote(t.value)
        if t.kind == "IDENT":
            parts = [self.consume("IDENT").value]
            while self.peek().kind == "DOT":
                self.consume("DOT")
                parts.append(self.consume("IDENT").value)
            return ".".join(parts)
        raise SyntaxError(f"Form: expected name (ident or string), got {t.kind}")

    def parse_trivial_ref(self) -> TrivialRef:
        self.consume("TILDE")
        name = self.consume("IDENT").value
        return TrivialRef(name=name)


def _unquote(s: str) -> str:
    # Triple-quoted strings strip both ends together.
    if s.startswith('"""') and s.endswith('"""'):
        return s[3:-3]
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


def _parse_interpolated(text: str):
    """Parse a string body for `${...}` interpolation markers.

    Returns a list alternating literal-string and expression-AST. When there
    are no markers, returns `[text]` (a single string).

    Each `${...}` is parsed as a Form expression using a nested parser.
    The result composes into a chain of `BinOp("+", ...)` with `str(expr)`
    coercion around each expression — surfaces the natural concatenation.
    """
    parts: list = []
    i = 0
    while i < len(text):
        # Find next `${`
        start = text.find("${", i)
        if start < 0:
            if i < len(text):
                parts.append(text[i:])
            break
        if start > i:
            parts.append(text[i:start])
        # Walk to matching `}` (balanced)
        depth = 1
        j = start + 2
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            raise SyntaxError(f"Form: unterminated `${{...}}` in string literal")
        expr_src = text[start + 2 : j]
        # Recursively parse the embedded expression.
        parts.append(parse(expr_src))
        i = j + 1
    return parts


def _interpolated_to_ast(text: str):
    """Build the AST for an interpolated string body.

    No markers -> StringLit(text).
    Markers -> chain of `str(expr) + "..." + str(expr) + ...` via BinOp("+").
    """
    parts = _parse_interpolated(text)
    if len(parts) == 1 and isinstance(parts[0], str):
        return StringLit(value=parts[0])
    # Build the concat chain. Each non-string part is coerced via FnCall("str", [expr]).
    def make(part):
        if isinstance(part, str):
            return StringLit(value=part)
        return FnCall(name="str", args=[part])
    nodes = [make(p) for p in parts]
    acc = nodes[0]
    for n in nodes[1:]:
        acc = BinOp(op="+", left=acc, right=n)
    return acc


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


@dataclass
class FormResult:
    """Discriminated union of possible evaluation outcomes."""
    kind: str   # "node_id" | "cell" | "view" | "cells" | "views"
    value: Any  # NodeID | NamedCell | CellView | list[NamedCell] | list[CellView]


# ---------------------------------------------------------------------------
# Recipe-category constructors — produce Recipe NodeIDs for interning
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


def _cond_id(kind: str) -> NodeID:
    instance = {
        "if_then": RCond.IF_THEN, "if_then_else": RCond.IF_THEN_ELSE,
    }[kind]
    return NodeID(1, Level.BASIC, RBasic.COND, instance)


def _block_id(kind: str) -> NodeID:
    instance = {
        "do": RBlock.DO,
        "let": RBlock.LET,
        "seq": RBlock.SEQUENCE,
        "with": RBlock.WITH,
    }[kind]
    return NodeID(1, Level.BASIC, RBasic.BLOCK, instance)


# Sentinel instance for `.self` — a LOCAL_ACCESS recipe that runtime eval (when
# it lands) resolves against the enclosing `with` block's subject. Picked from
# the high end of the instance space so it doesn't collide with hashed-name
# placeholders that occupy the low ~10^9 range.
_SELF_REF_INSTANCE = 999_999_999


def _match_id() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.MATCH, RMatch.SWITCH)


def _choice_id(kind: str) -> NodeID:
    instance = {"choose": RChoice.CHOOSE, "fail": RChoice.FAIL, "stop": RChoice.STOP}[kind]
    return NodeID(1, Level.BASIC, RBasic.CHOICE, instance)


def _state_id(kind: str) -> NodeID:
    instance = {"save": RState.SAVE, "restore": RState.RESTORE, "discard": RState.DISCARD}[kind]
    return NodeID(1, Level.BASIC, RBasic.STATE, instance)


def _exception_id(kind: str) -> NodeID:
    instance = {"raise": RException.RAISE, "resume": RException.RESUME}[kind]
    return NodeID(1, Level.BASIC, RBasic.EXCEPTION, instance)


def _delegate_id() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.DELEGATE, RDelegate.DELEGATE_TO)


def _reverse_id(kind: str) -> NodeID:
    instance = {"undo": RReverse.UNDO, "inverse": RReverse.INVERSE}[kind]
    return NodeID(1, Level.BASIC, RBasic.REVERSE, instance)


def _common_id() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.COMMON, RCommon.SHARED_BASE)


def _method_id(kind: str) -> NodeID:
    instance = {"define": RMethod.DEFINE, "invoke": RMethod.INVOKE}[kind]
    return NodeID(1, Level.BASIC, RBasic.METHOD, instance)


def _reactive_id() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.REACTIVE, RReactive.ON_CHANGE)


def _projection_id() -> NodeID:
    return NodeID(1, Level.BASIC, RBasic.PROJECTION, RProjection.PROJECT)


def _intern_recipe(session: Session, category: NodeID, children: List[NodeID]) -> NodeID:
    """Intern a Recipe shape and return its NodeID."""
    from app.services.substrate.kernel import DOMAIN_RECIPE, intern_node
    return intern_node(session, DOMAIN_RECIPE, category, children)


def _to_recipe_node_id(session: Session, ast: Any) -> NodeID:
    """Compile an AST node to a Recipe NodeID (interning as it goes)."""
    if isinstance(ast, IntLit):
        return NodeID(1, Level.TRIVIAL, 3, ast.value + 1 if ast.value >= 0 else 0)
        # RType.INTEGER = 3; instance encodes a small literal index
    if isinstance(ast, BoolLit):
        return NodeID(1, Level.TRIVIAL, 2, 1 if ast.value else 0)  # RType.BOOL = 2
    if isinstance(ast, StringLit):
        # Intern via the substrate string-table so `recipe_eval` can recover
        # the value at runtime. The previous hash-derived encoding was lossy:
        # `recipe_eval_text(s, '"hello"')` returned a NodeID instead of "hello".
        # `intern_string_instance` allocates a sequential, cross-process-stable
        # instance that `lookup_string_value` reverses.
        from app.services.substrate.substrate_strings import intern_string_instance
        inst = intern_string_instance(session, ast.value)
        return NodeID(1, Level.TRIVIAL, 5, inst)  # RType.STRING = 5
    if isinstance(ast, Identifier):
        # Bare name — intern as a SLUG (identity-role token). This makes
        # the name recoverable via _trivial_value/lookup_string_value, so
        # `let x = 42` round-trips through decompile + reparse to the
        # same Recipe NodeID. The previous encoding hashed the name into
        # type=7, which collided with RType.DATE and was one-way.
        from app.services.substrate.substrate_strings import intern_string_instance
        inst = intern_string_instance(session, ast.name)
        return NodeID(1, Level.TRIVIAL, 6, inst)  # RType.SLUG = 6
    if isinstance(ast, NodeIDLit):
        return NodeID(ast.package, ast.level, ast.type_, ast.instance)
    if isinstance(ast, TrivialRef):
        nid = TRIVIAL_REFS.get(ast.name)
        if nid is None:
            raise NameError(f"Form: unknown trivial ~{ast.name}")
        return nid
    if isinstance(ast, CellRef):
        if ast.name is None:
            ref_name = DOMAIN_TO_REF.get(ast.domain)
            if ref_name is None:
                raise NameError(f"Form: unknown domain @{ast.domain}")
            return TRIVIAL_REFS[ref_name]
        cell = lookup_cell(session, ast.domain, ast.name)
        if cell is None:
            raise LookupError(f"Form: cell ({ast.domain}, {ast.name}) not found")
        # Reference the cell as a global recipe — instance = its cell_id
        return NodeID(1, Level.TRIVIAL, 8, cell.cell_id or 0)  # RType.GLOBAL = 8
    if isinstance(ast, BinOp):
        l = _to_recipe_node_id(session, ast.left)
        r = _to_recipe_node_id(session, ast.right)
        # Data-driven: look up the op→category mapping from the registry.
        # Built-ins are pre-registered to match the previous hardcoded
        # behavior; custom operators can register their own categories.
        from app.services.substrate.form_eval import lookup_eval_category
        category = lookup_eval_category(ast.op, "binary")
        if category is not None:
            return _intern_recipe(session, category, [l, r])
        raise SyntaxError(f"Form: unknown binary op {ast.op!r} (no eval mapping)")
    if isinstance(ast, UnaryOp):
        operand = _to_recipe_node_id(session, ast.operand)
        from app.services.substrate.form_eval import lookup_eval_category
        category = lookup_eval_category(ast.op, "unary")
        if category is not None:
            return _intern_recipe(session, category, [operand])
        raise SyntaxError(f"Form: unknown unary op {ast.op!r} (no eval mapping)")
    if isinstance(ast, IfExpr):
        cond = _to_recipe_node_id(session, ast.cond)
        then_id = _to_recipe_node_id(session, ast.then_branch)
        if ast.else_branch is None:
            return _intern_recipe(session, _cond_id("if_then"), [cond, then_id])
        else_id = _to_recipe_node_id(session, ast.else_branch)
        return _intern_recipe(session, _cond_id("if_then_else"), [cond, then_id, else_id])
    if isinstance(ast, DoBlock):
        kids = [_to_recipe_node_id(session, s) for s in ast.statements]
        return _intern_recipe(session, _block_id("do"), kids)
    if isinstance(ast, Let):
        # A Let is a Block(let) holding an Identifier-shaped placeholder + value.
        name_id = _to_recipe_node_id(session, Identifier(name=ast.name))
        value_id = _to_recipe_node_id(session, ast.value)
        return _intern_recipe(session, _block_id("let"), [name_id, value_id])
    if isinstance(ast, MatchExpr):
        scrut = _to_recipe_node_id(session, ast.scrutinee)
        kids = [scrut]
        for arm in ast.arms:
            pat = _to_recipe_node_id(session, arm.pattern)
            body = _to_recipe_node_id(session, arm.body)
            kids.append(pat)
            kids.append(body)
        return _intern_recipe(session, _match_id(), kids)
    if isinstance(ast, ChooseExpr):
        kids = [_to_recipe_node_id(session, c) for c in ast.candidates]
        return _intern_recipe(session, _choice_id("choose"), kids)
    if isinstance(ast, FailExpr):
        return _choice_id("fail")  # leaf — no children
    if isinstance(ast, StopExpr):
        return _choice_id("stop")  # leaf — no children
    if isinstance(ast, SaveExpr):
        return _state_id("save")
    if isinstance(ast, RestoreExpr):
        return _state_id("restore")
    if isinstance(ast, DiscardExpr):
        return _state_id("discard")
    if isinstance(ast, RaiseExpr):
        return _exception_id("raise")
    if isinstance(ast, ResumeExpr):
        return _exception_id("resume")
    if isinstance(ast, DelegateExpr):
        src = _to_recipe_node_id(session, ast.source)
        tgt = _to_recipe_node_id(session, ast.target)
        return _intern_recipe(session, _delegate_id(), [src, tgt])
    if isinstance(ast, UndoExpr):
        child = _to_recipe_node_id(session, ast.child)
        return _intern_recipe(session, _reverse_id("undo"), [child])
    if isinstance(ast, InverseExpr):
        child = _to_recipe_node_id(session, ast.child)
        return _intern_recipe(session, _reverse_id("inverse"), [child])
    if isinstance(ast, CommonExpr):
        a = _to_recipe_node_id(session, ast.a)
        b = _to_recipe_node_id(session, ast.b)
        return _intern_recipe(session, _common_id(), [a, b])
    if isinstance(ast, MethodDefExpr):
        name_id = _to_recipe_node_id(session, StringLit(ast.name))
        target_id = _to_recipe_node_id(session, ast.target)
        body_id = _to_recipe_node_id(session, ast.body)
        params_id = _to_recipe_node_id(
            session, DoBlock(statements=[StringLit(p) for p in ast.params])
        )
        return _intern_recipe(
            session, _method_id("define"), [name_id, target_id, params_id, body_id]
        )
    if isinstance(ast, MethodInvokeExpr):
        name_id = _to_recipe_node_id(session, StringLit(ast.name))
        target_id = _to_recipe_node_id(session, ast.target)
        children = [name_id, target_id]
        for arg in ast.args:
            children.append(_to_recipe_node_id(session, arg))
        return _intern_recipe(session, _method_id("invoke"), children)
    if isinstance(ast, TryCatchExpr):
        body_id = _to_recipe_node_id(session, ast.body)
        handler_id = _to_recipe_node_id(session, ast.handler)
        return _intern_recipe(
            session,
            NodeID(1, Level.BASIC, RBasic.TRY, RTry.TRY_CATCH),
            [body_id, handler_id],
        )
    if isinstance(ast, OnChangeExpr):
        q_id = _to_recipe_node_id(session, ast.query)
        b_id = _to_recipe_node_id(session, ast.body)
        return _intern_recipe(session, _reactive_id(), [q_id, b_id])
    if isinstance(ast, ProjectExpr):
        c_id = _to_recipe_node_id(session, ast.cell)
        f_id = _to_recipe_node_id(session, ast.coord_fn)
        return _intern_recipe(session, _projection_id(), [c_id, f_id])
    if isinstance(ast, Projection):
        # In Recipe context, projection is a "view-as" recipe with two children.
        cell_id = _to_recipe_node_id(session, ast.cell)
        bp_id = _to_recipe_node_id(session, ast.blueprint)
        return _intern_recipe(session, _block_id("seq"), [cell_id, bp_id])
    if isinstance(ast, WithExpr):
        subject_id = _to_recipe_node_id(session, ast.subject)
        body_id = _to_recipe_node_id(session, ast.body)
        return _intern_recipe(session, _block_id("with"), [subject_id, body_id])
    if isinstance(ast, SelfRef):
        # Leaf — interns as a stable LOCAL_ACCESS NodeID with the SELF sentinel.
        return NodeID(1, Level.TRIVIAL, 7, _SELF_REF_INSTANCE)
    raise TypeError(f"Form: cannot compile {type(ast).__name__} to Recipe")


def evaluate(session: Session, ast: Any) -> FormResult:
    if isinstance(ast, NodeIDLit):
        return FormResult("node_id", NodeID(ast.package, ast.level, ast.type_, ast.instance))

    if isinstance(ast, TrivialRef):
        nid = TRIVIAL_REFS.get(ast.name)
        if nid is None:
            raise NameError(f"Form: unknown trivial ~{ast.name}")
        return FormResult("node_id", nid)

    if isinstance(ast, CellRef):
        if ast.name is None:
            # @<domain> bare — return the trivial domain blueprint
            ref_name = DOMAIN_TO_REF.get(ast.domain)
            if ref_name is None:
                raise NameError(f"Form: unknown domain @{ast.domain}")
            return FormResult("node_id", TRIVIAL_REFS[ref_name])
        # @<domain>(name) — look up the cell
        cell = lookup_cell(session, ast.domain, ast.name)
        if cell is None:
            raise LookupError(f"Form: cell ({ast.domain}, {ast.name}) not found")
        return FormResult("cell", cell)

    if isinstance(ast, Projection):
        cell_result = evaluate(session, ast.cell)
        bp_result = evaluate(session, ast.blueprint)
        if cell_result.kind != "cell":
            raise TypeError(f"Form: |> requires a cell on left, got {cell_result.kind}")
        if bp_result.kind != "node_id":
            raise TypeError(f"Form: |> requires a NodeID on right, got {bp_result.kind}")
        view = view_cell_through_blueprint(session, cell_result.value, bp_result.value)
        return FormResult("view", view)

    if isinstance(ast, Query):
        return _evaluate_query(session, ast)

    # Tree navigation — `.field` / `.method(args)`.
    #
    # The runtime in form_runtime.py already resolves these against cells,
    # NodeIDs, dicts, and structured CTORs. The structural evaluator
    # delegates and wraps the raw value back into a FormResult so the REST
    # surface and the playground render through the same code paths they
    # already use for direct structural results.
    #
    # BOOTSTRAP-RESIDUE: this branch is scheduled for compost together
    # with form.py's evaluate() function as a whole when G6 lands and the
    # Form-native runtime (form-kernel-rust walking python-bmf.fk recipes
    # via kernel-bmf-run) takes over. Named in:
    # - kernels/BOOTSTRAP_COMPOST_MANIFEST.md (Phase C)
    # - kernels/PHASE_A_FIRING_QUESTIONS.md (the parser+emitter+test triple
    #   that this evaluator is downstream of)
    # - kernels/PYTHON_BMF_CONTRACT.md (G6 — binary entry-point orchestration)
    #
    # The pulse witness organ substrate_form (#2054) detected this exact
    # path's silence in production at 2026-05-27T07:48Z. Healing the
    # silence now keeps the playground breathing while the Form-native
    # path completes.
    if isinstance(ast, (Access, MethodCall)):
        from app.services.substrate.form_runtime import Frame as _RuntimeFrame
        from app.services.substrate.form_runtime import execute as _runtime_execute
        value = _runtime_execute(session, ast, _RuntimeFrame())
        return _wrap_runtime_value(value)

    # Recipe-AST nodes: compile to a Recipe NodeID (intern as we go)
    if isinstance(ast, (
        IntLit, BoolLit, StringLit, Identifier,
        BinOp, UnaryOp, IfExpr, DoBlock, Let,
        MatchExpr, ChooseExpr, FailExpr, StopExpr,
        SaveExpr, RestoreExpr, DiscardExpr, RaiseExpr, ResumeExpr,
        WithExpr, SelfRef,
        DelegateExpr, UndoExpr, InverseExpr, CommonExpr,
        MethodDefExpr, MethodInvokeExpr,
        OnChangeExpr, ProjectExpr,
        TryCatchExpr,
    )):
        rid = _to_recipe_node_id(session, ast)
        return FormResult("recipe", rid)

    raise TypeError(f"Form: cannot evaluate {type(ast).__name__}")


def _wrap_runtime_value(value: Any) -> FormResult:
    """Wrap a raw runtime value back into a FormResult for the AST evaluator.

    Walks the type ladder the runtime returns (NodeID, NamedCell,
    CellView, homogeneous lists, primitives) and picks the matching kind
    so the REST surface and the playground UI render under the same code
    paths they already use for direct structural results.

    BOOTSTRAP-RESIDUE: composts with `evaluate()` when G6 closes — see
    kernels/PYTHON_BMF_CONTRACT.md.
    """
    if isinstance(value, NodeID):
        return FormResult("node_id", value)
    if isinstance(value, NamedCell):
        return FormResult("cell", value)
    if isinstance(value, CellView):
        return FormResult("view", value)
    if isinstance(value, list):
        if value and all(isinstance(v, NamedCell) for v in value):
            return FormResult("cells", value)
        if value and all(isinstance(v, CellView) for v in value):
            return FormResult("views", value)
    return FormResult("value", value)


def _evaluate_query(session: Session, q: Query) -> FormResult:
    """Dispatch a `?<verb>` query through the runtime-extensible registry.

    Each verb's handler lives in `form_queries.py` and can be replaced
    or extended at runtime via `register_form_query`. The dispatch
    table is no longer hardcoded here — closing the gap named in
    `form-language.md` → "Query operators ... are still hardcoded
    in _evaluate_query`."
    """
    from app.services.substrate.form_queries import dispatch_query
    return dispatch_query(session, q)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


# Bounded parse cache for the prefer_registered=False (bootstrap-grammar)
# path. Skipped for prefer_registered=True because the user-registered
# keyword registry can mutate at runtime — the same text could parse to a
# different AST after a register_form_keyword call. The bootstrap grammar
# is frozen at module load, so its parse is a pure function of text and
# safe to memoize. AST nodes are dataclasses read by evaluators without
# mutation, so the shared object is also safe to return.
_PARSE_CACHE: "OrderedDict[str, Any]" = OrderedDict()
_PARSE_CACHE_MAX = 256


def parse(text: str, *, prefer_registered: bool = False) -> Any:
    """Parse a single Form expression.

    `prefer_registered` flips the lookup order so the user-registered
    keyword registry takes priority over bootstrap hardcoded handlers.
    Used for partial self-hosting demonstrations — see
    `docs/coherence-substrate/form-language.md` ("Self-hosting").
    """
    key = text.strip() if not prefer_registered else None
    if key is not None and key in _PARSE_CACHE:
        _PARSE_CACHE.move_to_end(key)
        return _PARSE_CACHE[key]

    tokens = tokenize(text.strip())
    parser = Parser(tokens, prefer_registered=prefer_registered)
    result = parser.parse()
    if parser.peek().kind != "EOF":
        raise SyntaxError(
            f"Form: trailing input at pos {parser.peek().pos}: {parser.peek().value!r}"
        )

    if key is not None:
        _PARSE_CACHE[key] = result
        if len(_PARSE_CACHE) > _PARSE_CACHE_MAX:
            _PARSE_CACHE.popitem(last=False)
    return result


def parse_chunks(chunks, *, prefer_registered: bool = False) -> Any:
    """Parse a single Form expression from a streaming iterator of text chunks.

    Unlike `parse(text)`, this never materializes the whole input — the
    tokenizer lazily consumes chunks, the parser lazily fills its buffer
    from the tokenizer, and speculation rewinds within the already-buffered
    prefix. Useful for sockets, stdin, log tails, or any other unbounded
    source.

    Example:
        parse_chunks(["1 + ", "2 * ", "3"])  # parses "1 + 2 * 3"
    """
    parser = Parser(tokenize_chunks(chunks), prefer_registered=prefer_registered)
    result = parser.parse()
    if parser.peek().kind != "EOF":
        raise SyntaxError(
            f"Form: trailing input at pos {parser.peek().pos}: {parser.peek().value!r}"
        )
    return result


def evaluate_text(
    session: Session, text: str, *, prefer_registered: bool = False,
) -> FormResult:
    """Parse and evaluate a Form expression in one step."""
    return evaluate(session, parse(text, prefer_registered=prefer_registered))


# ---------------------------------------------------------------------------
# Serialization (NodeID → Form text)
# ---------------------------------------------------------------------------


def serialize_node_id(nid: NodeID) -> str:
    return f"@{nid.package}.{nid.level}.{nid.type_}.{nid.instance}"


def serialize_cell(cell: NamedCell) -> str:
    return f"@{cell.domain}({cell.name!r})"
