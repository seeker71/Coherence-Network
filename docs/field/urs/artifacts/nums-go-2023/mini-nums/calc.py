"""Calculator frontend for mini-nums.

Surface syntax:
    let x = 5
    let y = x + 3
    let z = y * 2

Drives the kernel via make_global_cell. Each `let` produces a NamedCell
whose CTOR is the recipe-tree of the right-hand-side expression.

The point: this frontend doesn't know anything about NUMS internals beyond
the public API (Module, Blueprint, Recipe, NamedCell, make_global_cell).
The kernel is universal.
"""
from __future__ import annotations
import re
from typing import List, Tuple

from core import (
    Module, Recipe, NamedCell,
    BID_integer,
    RID_integer_lit, RID_math, Math,
    make_global_cell,
)


# ---- Tiny tokenizer / parser --------------------------------------------

TOKEN_RE = re.compile(r"\s*(let|=|[a-zA-Z_][a-zA-Z0-9_]*|\d+|[+\-*/()])")


def tokenize(src: str) -> List[str]:
    out, pos = [], 0
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            if src[pos].isspace():
                pos += 1
                continue
            raise SyntaxError(f"Unknown char at {pos}: {src[pos]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


class Parser:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ""

    def consume(self) -> str:
        t = self.peek()
        self.pos += 1
        return t

    def expect(self, expected: str) -> None:
        t = self.consume()
        if t != expected:
            raise SyntaxError(f"Expected {expected!r}, got {t!r}")


# ---- Build recipes from the parser tree ---------------------------------

def parse_program(module: Module, src: str) -> List[NamedCell]:
    """Parse the source into cells. Returns the list of cells created."""
    p = Parser(tokenize(src))
    cells: List[NamedCell] = []
    while p.peek():
        if p.peek() == "let":
            cells.append(parse_let(module, p))
        else:
            raise SyntaxError(f"Unexpected: {p.peek()!r}")
    return cells


def parse_let(module: Module, p: Parser) -> NamedCell:
    p.expect("let")
    name = p.consume()
    p.expect("=")
    init = parse_expr(module, p)
    return make_global_cell(module, name, init.blueprint, init)


def parse_expr(module: Module, p: Parser) -> Recipe:
    """Pratt-style parsing for + - * /."""
    return parse_term(module, p, 0)


PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2}
OP_TO_MATH = {"+": Math.PLUS, "-": Math.MINUS, "*": Math.MULTIPLY, "/": Math.DIVIDE}


def parse_term(module: Module, p: Parser, min_prec: int) -> Recipe:
    left = parse_atom(module, p)
    while p.peek() in PRECEDENCE and PRECEDENCE[p.peek()] >= min_prec:
        op = p.consume()
        right = parse_term(module, p, PRECEDENCE[op] + 1)
        left = Recipe(
            module=module,
            category=RID_math(OP_TO_MATH[op]),
            blueprint=BID_integer(),
            children=[left, right],
        )
    return left


def parse_atom(module: Module, p: Parser) -> Recipe:
    t = p.consume()
    if t.isdigit():
        inst = module.emplace_integer(t)
        return Recipe(module, RID_integer_lit(inst), BID_integer())
    if re.match(r"[a-zA-Z_]", t):
        # Variable reference — resolve to a global access.
        if t in module.cells_by_name:
            cell = module.cells_by_name[t]
            return cell.access  # share the access-recipe
        raise NameError(f"Undefined: {t}")
    if t == "(":
        inner = parse_expr(module, p)
        p.expect(")")
        return inner
    raise SyntaxError(f"Atom expected, got {t!r}")
