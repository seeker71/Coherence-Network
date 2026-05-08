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
    ("EQ", r"=="),
    ("ASSIGN", r"="),
    ("AT", r"@"),
    ("TILDE", r"~"),
    ("QMARK", r"\?"),
    ("COLON", r":"),
    ("COMMA", r","),
    ("DOT", r"\."),
    ("LBRACE", r"\{"),
    ("RBRACE", r"\}"),
    ("LBRACK", r"\["),
    ("RBRACK", r"\]"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("STRING", r'"([^"\\]|\\.)*"'),
    ("INT", r"-?\d+"),
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
    field: str  # "domain" | "name"
    op: str    # "==" | "matches"
    value: str


@dataclass
class Query:
    kind: str            # "equivalent" | "cells" | "compatible"
    arg: Optional[Any] = None      # AtomNode for equivalent/compatible/projection
    filters: List[Filter] = field(default_factory=list)


AtomNode = Union[NodeIDLit, TrivialRef, CellRef, Projection]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

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
        return self.parse_atom_or_view()

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
            val = self.consume("STRING").value
            return Filter(field=field_tok.value, op="==", value=_unquote(val))
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
        a = self.parse_atom()
        while self.peek().kind == "PROJECT":
            self.consume("PROJECT")
            b = self.parse_atom()
            a = Projection(cell=a, blueprint=b)
        return a

    def parse_atom(self) -> AtomNode:
        t = self.peek()
        if t.kind == "AT":
            return self.parse_at()
        if t.kind == "TILDE":
            return self.parse_trivial_ref()
        raise SyntaxError(f"Form: expected atom (@ or ~), got {t.kind}({t.value!r}) at pos {t.pos}")

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
        for f in q.filters:
            if f.field == "domain" and f.op == "==":
                rows = rows.filter_by(domain=f.value)
            elif f.field == "name" and f.op == "matches":
                rows = rows.filter(SubstrateNamedCellORM.name.like(f.value.replace("*", "%")))
        cells = [_orm_to_cell(session, r) for r in rows.all()]
        return FormResult("cells", cells)

    raise NameError(f"Form: unknown query kind {q.kind!r}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse(text: str) -> Any:
    """Parse a single Form expression."""
    tokens = tokenize(text.strip())
    parser = Parser(tokens)
    result = parser.parse()
    if parser.peek().kind != "EOF":
        raise SyntaxError(
            f"Form: trailing input at pos {parser.peek().pos}: {parser.peek().value!r}"
        )
    return result


def evaluate_text(session: Session, text: str) -> FormResult:
    """Parse and evaluate a Form expression in one step."""
    return evaluate(session, parse(text))


# ---------------------------------------------------------------------------
# Serialization (NodeID → Form text)
# ---------------------------------------------------------------------------


def serialize_node_id(nid: NodeID) -> str:
    return f"@{nid.package}.{nid.level}.{nid.type_}.{nid.instance}"


def serialize_cell(cell: NamedCell) -> str:
    return f"@{cell.domain}({cell.name!r})"
