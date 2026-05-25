"""Native Python BMF parser — readable expression of the Form scanner.

Source-of-truth lives at form/form-stdlib/emits/python-native-templates/parser.py
(this file). The Form emitter (emits/python-native.fk) materializes it
to kernels/python_bmf/parser.py via the kernel's write_file_text host
primitive.

Mirrors python-source-scan-text + python-source-layout-objects +
python-parse-module-object in form/form-stdlib/grammars/python-bmf.fk.
Three passes:

1. scan_python_source(text) — char cursor → list of BmfAtom source
   objects (no layout tokens yet).
2. layout_objects(atoms) — insert NEWLINE / INDENT / DEDENT / ENDMARKER
   from source coordinates.
3. parse_module(atoms) — group into BmfStatement / BmfStatementTree.
"""

from __future__ import annotations

from .objects import (
    PYTHON_KEYWORDS,
    PYTHON_OPERATORS,
    BmfAtom,
    py_layout,
)
from .sdk import SourceSpan


class Cursor:
    __slots__ = ("text", "offset", "line", "col", "path")

    def __init__(self, text, path="<source>", offset=0, line=1, col=0):
        self.text = text
        self.offset = offset
        self.line = line
        self.col = col
        self.path = path

    def at_end(self):
        return self.offset >= len(self.text)

    def char(self):
        return "" if self.at_end() else self.text[self.offset]

    def peek(self, n=1):
        pos = self.offset + n
        return "" if pos >= len(self.text) else self.text[pos]

    def starts_with(self, s):
        return self.text.startswith(s, self.offset)

    def advance(self, n=1):
        new = Cursor(self.text, self.path, self.offset, self.line, self.col)
        for _ in range(n):
            if new.offset >= len(self.text):
                break
            if new.text[new.offset] == "\n":
                new.line += 1
                new.col = 0
            else:
                new.col += 1
            new.offset += 1
        return new

    def span_to(self, end):
        return SourceSpan(
            path=self.path,
            start_offset=self.offset,
            end_offset=end.offset,
            start_line=self.line,
            start_col=self.col,
            end_line=end.line,
            end_col=end.col,
        )


def _is_space(ch):
    return ch in (" ", "\t", "\r")


def _is_digit(ch):
    return ch.isdigit()


def _is_name_start(ch):
    return ch.isalpha() or ch == "_"


def _is_name_continue(ch):
    return ch.isalnum() or ch == "_"


def _is_quote(ch):
    return ch in ('"', "'")


def _is_string_prefix(ch):
    return ch in "rRbBfFtTuU"


_OPERATORS_LONGEST_FIRST = tuple(sorted(PYTHON_OPERATORS, key=len, reverse=True))


def _skip_trivia(c):
    while not c.at_end():
        ch = c.char()
        if _is_space(ch):
            c = c.advance()
        elif ch == "#":
            while not c.at_end() and c.char() != "\n":
                c = c.advance()
        else:
            break
    return c


def _scan_string(c, kind="py-string"):
    start = c
    quote = c.char()
    triple = c.peek(1) == quote and c.peek(2) == quote
    if triple:
        c = c.advance(3)
        body = []
        while not c.at_end():
            if c.starts_with(quote * 3):
                c = c.advance(3)
                break
            body.append(c.char())
            c = c.advance()
        return BmfAtom(kind, "".join(body), start.span_to(c)), c
    c = c.advance()
    body = []
    while not c.at_end() and c.char() != quote:
        if c.char() == "\\":
            c = c.advance()
            if not c.at_end():
                body.append(c.char())
                c = c.advance()
            continue
        body.append(c.char())
        c = c.advance()
    if not c.at_end():
        c = c.advance()
    return BmfAtom(kind, "".join(body), start.span_to(c)), c


def _prefix_string_kind(prefix):
    p = prefix.lower()
    if "f" in p:
        return "py-fstring"
    if "t" in p:
        return "py-tstring"
    if "b" in p:
        return "py-bytes"
    return "py-string"


def _scan_prefixed_string(c):
    ch = c.char()
    nx = c.peek(1)
    nxx = c.peek(2)
    if _is_string_prefix(ch) and _is_string_prefix(nx) and _is_quote(nxx):
        prefix = (ch + nx).lower()
        kind = _prefix_string_kind(prefix)
        return _scan_string(c.advance(2), kind)
    if _is_string_prefix(ch) and _is_quote(nx):
        kind = _prefix_string_kind(ch.lower())
        return _scan_string(c.advance(1), kind)
    return None


def _scan_int_or_float(c):
    start = c
    body = []
    while not c.at_end() and (_is_digit(c.char()) or c.char() == "_"):
        body.append(c.char())
        c = c.advance()
    if c.char() == "." and _is_digit(c.peek(1)):
        body.append(c.char())
        c = c.advance()
        while not c.at_end() and (_is_digit(c.char()) or c.char() == "_"):
            body.append(c.char())
            c = c.advance()
        return BmfAtom("py-float", "".join(body), start.span_to(c)), c
    return BmfAtom("py-int", "".join(body), start.span_to(c)), c


def _scan_name(c):
    start = c
    body = []
    while not c.at_end() and _is_name_continue(c.char()):
        body.append(c.char())
        c = c.advance()
    text = "".join(body)
    kind = "py-keyword" if text in PYTHON_KEYWORDS else "py-name"
    return BmfAtom(kind, text, start.span_to(c)), c


def _scan_op(c):
    start = c
    for op in _OPERATORS_LONGEST_FIRST:
        if c.starts_with(op):
            end = c.advance(len(op))
            return BmfAtom("py-op", op, start.span_to(end)), end
    end = c.advance()
    return BmfAtom("py-op", c.char(), start.span_to(end)), end


def _scan_one(c):
    c = _skip_trivia(c)
    if c.at_end():
        return BmfAtom("py-eof", "", c.span_to(c)), c
    ch = c.char()
    if ch == "\n":
        end = c.advance()
        return BmfAtom("py-op", "\n", c.span_to(end)), end
    prefixed = _scan_prefixed_string(c)
    if prefixed is not None:
        return prefixed
    if _is_quote(ch):
        return _scan_string(c)
    if _is_digit(ch):
        return _scan_int_or_float(c)
    if _is_name_start(ch):
        return _scan_name(c)
    return _scan_op(c)


def scan_python_source(text, path="<source>"):
    """Mirror python-source-scan-text in python-bmf.fk."""
    c = Cursor(text, path)
    atoms = []
    while True:
        atom, c = _scan_one(c)
        if atom.kind == "py-eof":
            atoms.append(atom)
            return atoms
        if atom.kind == "py-op" and atom.value == "\n":
            continue
        atoms.append(atom)


def layout_objects(atoms):
    """Insert NEWLINE / INDENT / DEDENT / ENDMARKER. Mirror python-source-layout-objects."""
    out = []
    prev_line = 1
    indent_stack = [0]
    for atom in atoms:
        if atom.kind == "py-eof":
            while len(indent_stack) > 1:
                indent_stack.pop()
                out.append(py_layout("DEDENT"))
            out.append(py_layout("ENDMARKER"))
            continue
        line = atom.span.start_line
        col = atom.span.start_col
        if line > prev_line:
            out.append(py_layout("NEWLINE"))
            while indent_stack and col < indent_stack[-1]:
                indent_stack.pop()
                out.append(py_layout("DEDENT"))
            if col > indent_stack[-1]:
                indent_stack.append(col)
                out.append(py_layout("INDENT"))
        out.append(atom)
        prev_line = line
    return out


def _statement_cpython_rule(tokens):
    """Mirror python-statement-cpython-rule-from-tokens."""
    if not tokens:
        return "empty"
    t0 = tokens[0].value
    t1 = tokens[1].value if len(tokens) > 1 else ""
    if t0 == "from" or t0 == "import":
        return "import_stmt"
    if t0 == "return":
        return "return_stmt"
    if t0 == "raise":
        return "raise_stmt"
    if t0 == "pass":
        return "pass_stmt"
    if t0 == "del":
        return "del_stmt"
    if t0 == "yield":
        return "yield_stmt"
    if t0 == "assert":
        return "assert_stmt"
    if t0 == "break":
        return "break_stmt"
    if t0 == "continue":
        return "continue_stmt"
    if t0 == "global":
        return "global_stmt"
    if t0 == "nonlocal":
        return "nonlocal_stmt"
    if t0 == "class":
        return "class_def"
    if t0 == "def" or (t0 == "async" and t1 == "def"):
        return "function_def"
    if t0 == "if":
        return "if_stmt"
    if t0 == "while":
        return "while_stmt"
    if t0 == "for" or (t0 == "async" and t1 == "for"):
        return "for_stmt"
    if t0 == "with" or (t0 == "async" and t1 == "with"):
        return "with_stmt"
    if t0 == "try":
        return "try_stmt"
    if t0 == "match":
        return "match_stmt"
    if t0 == "type":
        return "type_alias"
    if t1 == "=":
        return "assignment"
    if t1 == ":=":
        return "assignment_expression"
    return "star_expressions"


def parse_module(atoms_with_layout, source_path="<source>"):
    """Group laid-out atoms into a tree of statement trees."""
    from .objects import BmfModule, BmfStatementTree

    flat = []
    cur_tokens = []
    cur_indent = 0
    indent = 0
    for a in atoms_with_layout:
        if a.kind == "py-layout":
            if a.value == "INDENT":
                indent += 1
            elif a.value == "DEDENT":
                indent = max(0, indent - 1)
            elif a.value == "NEWLINE":
                if cur_tokens:
                    flat.append((cur_indent, cur_tokens))
                    cur_tokens = []
                cur_indent = indent
            elif a.value == "ENDMARKER":
                if cur_tokens:
                    flat.append((cur_indent, cur_tokens))
                    cur_tokens = []
            continue
        if not cur_tokens:
            cur_indent = indent
        cur_tokens.append(a)
    if cur_tokens:
        flat.append((cur_indent, cur_tokens))

    def _build(start, parent_indent):
        out = []
        i = start
        while i < len(flat):
            ind, toks = flat[i]
            if ind < parent_indent:
                return out, i
            if ind > parent_indent and out:
                children, i = _build(i, ind)
                out[-1].children = children
                continue
            span = toks[0].span if toks else SourceSpan.empty()
            tree = BmfStatementTree(
                kind="py-statement-tree",
                indent=ind,
                cpython_rule=_statement_cpython_rule(toks),
                tokens=toks,
                children=[],
                span=span,
            )
            out.append(tree)
            i += 1
        return out, i

    statements, _ = _build(0, 0)
    return BmfModule(statements=statements, source_path=source_path)


def parse_python(text, path="<source>"):
    return parse_module(layout_objects(scan_python_source(text, path)), path)


__all__ = [
    "Cursor",
    "scan_python_source",
    "layout_objects",
    "parse_module",
    "parse_python",
]
