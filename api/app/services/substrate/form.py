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
    RCompare,
    RCond,
    RJump,
    RLogic,
    RMatch,
    RMath,
)
from app.services.substrate.kernel import (
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
}


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------


@dataclass
class Token:
    kind: str
    value: str
    pos: int


_TOKEN_PATTERNS = [
    ("WS", r"[ \t\n\r]+"),
    ("COMMENT", r"#[^\n]*"),
    ("PROJECT", r"\|>"),
    ("ARROW", r"=>"),
    ("EQ", r"=="),
    ("NEQ", r"!="),
    ("LE", r"<="),
    ("GE", r">="),
    ("AND", r"&&"),
    ("OR", r"\|\|"),
    ("ASSIGN", r"="),
    ("LT", r"<"),
    ("GT", r">"),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("STAR", r"\*"),
    ("SLASH", r"/"),
    ("PERCENT", r"%"),
    ("BANG", r"!"),
    ("AT", r"@"),
    ("TILDE", r"~"),
    ("QMARK", r"\?"),
    ("COLON", r":"),
    ("SEMI", r";"),
    ("COMMA", r","),
    ("DOT", r"\."),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LBRACK", r"\["),
    ("RBRACK", r"\]"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("STRING", r'"([^"\\]|\\.)*"'),
    ("INT", r"\d+"),
    ("IDENT", r"[A-Za-z_][A-Za-z_0-9\-]*"),
]
_TOKEN_RE = re.compile(
    "|".join(f"(?P<{name}>{pat})" for name, pat in _TOKEN_PATTERNS)
)


def tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise SyntaxError(f"Form: unexpected char at pos {pos}: {text[pos]!r}")
        kind = m.lastgroup or ""
        value = m.group()
        if kind not in ("WS", "COMMENT"):
            tokens.append(Token(kind, value, pos))
        pos = m.end()
    tokens.append(Token("EOF", "", pos))
    return tokens


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


AtomNode = Union[NodeIDLit, TrivialRef, CellRef, Projection]
ExprNode = Any  # any AST node — too many to enumerate


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class Parser:
    def __init__(self, tokens: List[Token], *, prefer_registered: bool = False):
        self.tokens = tokens
        self.pos = 0
        # When True, the parser consults the user-registered keyword
        # registry BEFORE falling through to bootstrap hardcoded handlers.
        # Used by `bootstrap_self_host` and the self-hosting demonstration —
        # see docs/coherence-substrate/form-language.md ("Self-hosting,
        # partial").
        self.prefer_registered = prefer_registered

    def peek(self, n: int = 0) -> Token:
        return self.tokens[self.pos + n]

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
                return parse_with_precedence(self, 0)
        return self.parse_or()

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
        while self.peek().kind == "PROJECT":
            self.consume("PROJECT")
            b = self.parse_primary()
            a = Projection(cell=a, blueprint=b)
        return a

    def parse_primary(self) -> ExprNode:
        t = self.peek()
        if t.kind == "AT":
            return self.parse_at()
        if t.kind == "TILDE":
            return self.parse_trivial_ref()
        if t.kind == "INT":
            return IntLit(int(self.consume("INT").value))
        if t.kind == "STRING":
            return StringLit(_unquote(self.consume("STRING").value))
        if t.kind == "LPAREN":
            self.consume("LPAREN")
            inner = self.parse_expr()
            self.consume("RPAREN")
            return inner
        if t.kind == "LBRACK":
            return self.parse_list_literal()
        if t.kind == "IDENT":
            return self.parse_keyword_or_ident()
        if t.kind == "DOT":
            # `.self` — references the implicit subject of an enclosing `with`.
            # Other dot-access forms (`.field`, `.method`) aren't shipped yet.
            self.consume("DOT")
            ident = self.peek()
            if ident.kind == "IDENT" and ident.value == "self":
                self.consume("IDENT")
                return SelfRef()
            raise SyntaxError(
                f"Form: only `.self` is supported in dot-prefix position at pos {t.pos} "
                f"(got `.{ident.value}`)"
            )
        raise SyntaxError(f"Form: unexpected {t.kind}({t.value!r}) at pos {t.pos}")

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

        # Built-in keywords (the bootstrap grammar)
        if kw == "true":
            self.consume("IDENT")
            return BoolLit(True)
        if kw == "false":
            self.consume("IDENT")
            return BoolLit(False)
        if kw == "if":
            return self.parse_if()
        if kw == "do":
            return self.parse_do_block()
        if kw == "with":
            return self.parse_with()
        if kw == "let":
            return self.parse_let()
        if kw == "match":
            return self.parse_match()
        if kw == "choose":
            return self.parse_choose()
        if kw == "fail":
            self.consume("IDENT")
            return FailExpr()
        if kw == "stop":
            self.consume("IDENT")
            return StopExpr()

        # User-registered keywords (the rule-driven extension point —
        # this is where the grammar becomes alive at runtime).
        if not self.prefer_registered:
            from app.services.substrate.form_rules import try_apply_keyword_rule
            node = try_apply_keyword_rule(self, kw)
            if node is not None:
                return node

        # Otherwise it's an Identifier (local name reference)
        self.consume("IDENT")
        return Identifier(name=kw)

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

    def parse_list_literal(self) -> List[ExprNode]:
        self.consume("LBRACK")
        items = []
        while self.peek().kind != "RBRACK":
            items.append(self.parse_expr())
            if self.peek().kind == "COMMA":
                self.consume("COMMA")
        self.consume("RBRACK")
        return items

    # ----- Backwards-compat wrapper for query-style atoms -----------------

    def parse_query(self) -> Query:
        self.consume("QMARK")
        kw = self.consume("IDENT").value
        if kw == "equivalent":
            arg = self.parse_atom_or_view()
            return Query(kind="equivalent", arg=arg)
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
        raise SyntaxError(f"Form: unknown query keyword: {kw!r}")

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
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s


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
        # Map literal string to an instance — same hash trick used elsewhere
        inst = abs(hash(ast.value)) % (10**9) + 1
        return NodeID(1, Level.TRIVIAL, 5, inst)  # RType.STRING = 5
    if isinstance(ast, Identifier):
        # Bare name — encode as a placeholder LOCAL_ACCESS instance.
        # Real binding-resolution belongs in a future symbol-table phase.
        inst = abs(hash(ast.name)) % (10**9) + 1
        return NodeID(1, Level.TRIVIAL, 7, inst)  # RType.LOCAL_ACCESS = 7
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

    # Recipe-AST nodes: compile to a Recipe NodeID (intern as we go)
    if isinstance(ast, (
        IntLit, BoolLit, StringLit, Identifier,
        BinOp, UnaryOp, IfExpr, DoBlock, Let,
        MatchExpr, ChooseExpr, FailExpr, StopExpr,
        WithExpr, SelfRef,
    )):
        rid = _to_recipe_node_id(session, ast)
        return FormResult("recipe", rid)

    raise TypeError(f"Form: cannot evaluate {type(ast).__name__}")


def _evaluate_query(session: Session, q: Query) -> FormResult:
    if q.kind == "equivalent":
        target = evaluate(session, q.arg)
        if target.kind == "cell":
            cells = find_equivalent_cells(session, target.value.blueprint, exclude_name=target.value.name)
            return FormResult("cells", cells)
        if target.kind == "node_id":
            cells = find_equivalent_cells(session, target.value)
            return FormResult("cells", cells)
        raise TypeError(f"Form: ?equivalent expects cell or node_id")

    if q.kind == "compatible":
        bp_result = evaluate(session, q.arg)
        if bp_result.kind != "node_id":
            raise TypeError(f"Form: ?compatible |> expects a NodeID")
        views = find_cells_compatible_with(session, bp_result.value)
        return FormResult("views", views)

    if q.kind in ("shaped_by", "harmonic_at"):
        # Resonance-walk query: given a target cell, return cells whose
        # resonance edge of the named verb points at it.
        from app.services.substrate.orm import SubstrateNamedCellORM
        from app.services.substrate.kernel import _orm_to_cell
        from app.services.substrate.resonance import (
            find_cells_shaping,
            find_cells_harmonic_at,
        )

        rhs = evaluate(session, q.arg)
        if rhs.kind != "cell":
            raise TypeError(
                f"Form: ?{q.kind} expects a cell ref on the right, got {rhs.kind}"
            )
        target_db_id = rhs.value.cell_id
        if target_db_id is None:
            raise LookupError(f"Form: target cell has no db id (was it persisted?)")

        if q.kind == "shaped_by":
            source_db_ids = find_cells_shaping(session, target_db_id)
        else:
            source_db_ids = find_cells_harmonic_at(session, target_db_id)

        cells = []
        for sid in source_db_ids:
            row = (
                session.query(SubstrateNamedCellORM)
                .filter_by(cell_id=sid)
                .one_or_none()
            )
            if row:
                cells.append(_orm_to_cell(session, row))
        return FormResult("cells", cells)

    if q.kind == "cells":
        from app.services.substrate.orm import SubstrateNamedCellORM
        from app.services.substrate.kernel import _orm_to_cell

        if q.arg is not None:
            # ?cells |> @blueprint — return CellViews
            bp_result = evaluate(session, q.arg)
            if bp_result.kind != "node_id":
                raise TypeError(f"Form: ?cells |> expects a NodeID")
            domain_filter = None
            for f in q.filters:
                if f.field == "domain" and f.op == "==":
                    domain_filter = f.value
            views = find_cells_compatible_with(session, bp_result.value, domain=domain_filter)
            return FormResult("views", views)

        # ?cells [where ...] — return raw cells
        rows = session.query(SubstrateNamedCellORM)
        shape_filter_cell: Optional[NamedCell] = None
        for f in q.filters:
            if f.field == "domain" and f.op == "==" and isinstance(f.value, str):
                rows = rows.filter_by(domain=f.value)
            elif f.field == "name" and f.op == "matches" and isinstance(f.value, str):
                rows = rows.filter(SubstrateNamedCellORM.name.like(f.value.replace("*", "%")))
            elif f.field == "shape" and f.op == "==":
                # `where shape == @<atom-ref>` — resolve the atom-ref, then filter by
                # blueprint equality OR (when the rhs is itself a cell) by structural
                # equivalence with that cell's blueprint.
                rhs = evaluate(session, f.value)
                if rhs.kind == "node_id":
                    target_bp = rhs.value
                elif rhs.kind == "cell":
                    target_bp = rhs.value.blueprint
                else:
                    raise TypeError(
                        f"Form: ?cells where shape == ... expects a NodeID or cell rhs, got {rhs.kind}"
                    )
                # Match cells whose blueprint NodeID equals the target.
                from app.services.substrate.kernel import _node_to_db_id
                target_bp_db = _node_to_db_id(session, target_bp)
                rows = rows.filter(SubstrateNamedCellORM.blueprint_node_id == target_bp_db)
            else:
                raise SyntaxError(
                    f"Form: unsupported filter ({f.field!r} {f.op!r} {type(f.value).__name__})"
                )
        cells = [_orm_to_cell(session, r) for r in rows.all()]
        return FormResult("cells", cells)

    raise NameError(f"Form: unknown query kind {q.kind!r}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse(text: str, *, prefer_registered: bool = False) -> Any:
    """Parse a single Form expression.

    `prefer_registered` flips the lookup order so the user-registered
    keyword registry takes priority over bootstrap hardcoded handlers.
    Used for partial self-hosting demonstrations — see
    `docs/coherence-substrate/form-language.md` ("Self-hosting").
    """
    tokens = tokenize(text.strip())
    parser = Parser(tokens, prefer_registered=prefer_registered)
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
