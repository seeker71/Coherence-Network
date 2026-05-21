"""bmf.py — real BMF tokenizer + pattern matcher (no ast.parse delegation).

Urs's call: "why BMF tomorrow, what are we waiting for, if there is
a dependency reason, yes, if it is just avoiding work, then let's
get to it."

There was no dependency reason. This module is the smallest concrete
proof that BMF-style grammar can land *today* in the body's substrate
discipline. The path it walks:

  source text → tokenize (char-by-char, no regex over ast tokens)
              → token stream with line/col/byte spans
              → match_pattern (Literal / Capture / Sequence / Opt /
                               Choice with FAIL-unwind)
              → semantic action fires (builds the Form object)
              → Form object with source_attribution stamped natively

The carrier is still Python (which is what Urs noticed: "still seeing
python executions, interesting"). That's the second move, the next
breath — routing execution through the TS or Rust kernels instead of
CPython. This module addresses the FIRST move: BMF rules executed
through BMF semantics, not delegated to ast.parse.

Honest scope: this is a working BMF parser for a small slice of
Python — `import` and `from-import` statements. The rules are
register_form_rule-shape (pattern + action), the matcher honors
FAIL-unwind cleanly, the actions produce Form objects parity-
equivalent to ast.parse for the same inputs. The rest of Python
(class, def, expressions) lands as more rules in future breaths —
one construct per breath, exactly the path lc-parsers-as-recipes
named.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ─── 1. tokens ──────────────────────────────────────────────────────────


@dataclass
class Token:
    kind: str            # "KW" | "IDENT" | "OP" | "STRING" | "INT" | "NEWLINE" | "EOF"
    value: str
    line: int            # 1-indexed
    col: int             # 1-indexed
    byte_start: int      # 0-indexed
    byte_end: int


@dataclass
class TokenStream:
    """Lazy-shaped stream: head/tail/empty without committing to read
    the whole source up front. For now we tokenize eagerly because
    Python's grammar is small enough; the streaming-discipline shape
    is what matters for BMF.
    """
    tokens: list[Token]
    pos: int = 0
    source_path: str = "<input>"

    def head(self) -> Token:
        if self.pos >= len(self.tokens):
            return Token("EOF", "", 0, 0, 0, 0)
        return self.tokens[self.pos]

    def tail(self) -> "TokenStream":
        return TokenStream(self.tokens, self.pos + 1, self.source_path)

    def empty(self) -> bool:
        return self.head().kind == "EOF"


# ─── 2. tokenizer (Python keywords + operators, no ast delegation) ──────


PY_KEYWORDS = {
    "def", "class", "import", "from", "as", "if", "elif", "else", "for",
    "while", "return", "raise", "try", "except", "finally", "with",
    "in", "is", "and", "or", "not", "lambda", "yield", "async", "await",
    "pass", "break", "continue", "global", "nonlocal", "del", "True",
    "False", "None", "match", "case",
}


# Hand-rolled tokenizer that walks the source character-by-character.
# No regex over the whole source; the matcher consults this stream.

def tokenize(source: str, source_path: str = "<input>") -> TokenStream:
    tokens: list[Token] = []
    i = 0
    n = len(source)
    line = 1
    col = 1

    def make(kind: str, value: str, start: int, start_line: int, start_col: int) -> Token:
        return Token(kind, value, start_line, start_col, start, start + len(value))

    while i < n:
        ch = source[i]
        start_line = line
        start_col = col

        # Newline
        if ch == "\n":
            tokens.append(make("NEWLINE", "\n", i, start_line, start_col))
            i += 1
            line += 1
            col = 1
            continue

        # Whitespace (consume but skip)
        if ch in " \t":
            i += 1
            col += 1
            continue

        # Comment — # to end of line
        if ch == "#":
            j = i
            while j < n and source[j] != "\n":
                j += 1
            # skip without emitting (could emit COMMENT if needed)
            col += j - i
            i = j
            continue

        # String literal — simple double-quoted strings for the slice
        # we care about today (import statements don't carry strings,
        # but the tokenizer is shared infrastructure)
        if ch in '"\'':
            quote = ch
            j = i + 1
            while j < n and source[j] != quote:
                if source[j] == "\\":
                    j += 2
                else:
                    j += 1
            j += 1  # consume closing quote
            tokens.append(make("STRING", source[i:j], i, start_line, start_col))
            col += j - i
            i = j
            continue

        # Number — INT only (FLOAT can be added)
        if ch.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            tokens.append(make("INT", source[i:j], i, start_line, start_col))
            col += j - i
            i = j
            continue

        # Identifier or keyword
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            word = source[i:j]
            kind = "KW" if word in PY_KEYWORDS else "IDENT"
            tokens.append(make(kind, word, i, start_line, start_col))
            col += j - i
            i = j
            continue

        # Operator / punctuation
        # Multi-char operators first
        two = source[i:i+2] if i + 1 < n else ""
        if two in ("==", "!=", "<=", ">=", "->", ":=", "**", "//", "+=", "-=", "*=", "/="):
            tokens.append(make("OP", two, i, start_line, start_col))
            i += 2
            col += 2
            continue
        if ch in "+-*/%<>=()[],:;.@{}":
            tokens.append(make("OP", ch, i, start_line, start_col))
            i += 1
            col += 1
            continue

        # Anything else — emit as UNKNOWN and advance
        tokens.append(make("UNKNOWN", ch, i, start_line, start_col))
        i += 1
        col += 1

    tokens.append(Token("EOF", "", line, col, n, n))
    return TokenStream(tokens, 0, source_path)


# ─── 3. pattern primitives ──────────────────────────────────────────────
#
# Same shapes as form-language.md names for the runtime keyword
# registration: Literal / Capture / Sequence / Opt / Choice.
# Each carries a single match(stream) -> Result | FAIL contract.


# FAIL sentinel — BMF's backtracking primitive. A pattern that
# returns FAIL signals the matcher to unwind to the nearest Choice
# and try the next alternative.
class _Fail:
    def __repr__(self) -> str:
        return "FAIL"
FAIL = _Fail()


@dataclass
class MatchResult:
    captures: dict[str, Any]
    rest: TokenStream
    span_start: Token             # first token of the match
    span_end: Token               # last token of the match


@dataclass
class Literal:
    kind: str                     # "KW" | "IDENT" | "OP" | "INT" | "STRING"
    value: Optional[str] = None   # exact value to match; None = any of this kind

    def match(self, stream: TokenStream):
        tok = stream.head()
        if tok.kind != self.kind:
            return FAIL
        if self.value is not None and tok.value != self.value:
            return FAIL
        return MatchResult(captures={}, rest=stream.tail(),
                           span_start=tok, span_end=tok)


@dataclass
class Capture:
    name: str
    inner: Any                    # another pattern (Literal, Sequence, …)

    def match(self, stream: TokenStream):
        m = self.inner.match(stream)
        if m is FAIL:
            return FAIL
        # Capture the matched span as a list of tokens (for IDENT/KW
        # captures, this is just the value; for sequences, the full span).
        captured = _collect_captured_value(self.inner, stream, m)
        return MatchResult(
            captures={**m.captures, self.name: captured},
            rest=m.rest,
            span_start=m.span_start,
            span_end=m.span_end,
        )


def _collect_captured_value(pattern, stream: TokenStream, result: MatchResult):
    """For a Literal capture, the value is the token's text. For more
    complex patterns, return the (captures, span) as a dict so the
    semantic action can reach into structured captures.
    """
    if isinstance(pattern, Literal):
        return stream.head().value
    return {
        "captures": result.captures,
        "span_start": result.span_start,
        "span_end": result.span_end,
    }


@dataclass
class Sequence:
    parts: list[Any]              # ordered patterns; all must match

    def match(self, stream: TokenStream):
        captures: dict[str, Any] = {}
        s = stream
        first_token = s.head()
        last_token = first_token
        for part in self.parts:
            m = part.match(s)
            if m is FAIL:
                return FAIL       # FAIL unwinds; captures discarded cleanly
            captures.update(m.captures)
            last_token = m.span_end
            s = m.rest
        return MatchResult(captures, s, first_token, last_token)


@dataclass
class Opt:
    inner: Any                    # matches if present; succeeds either way

    def match(self, stream: TokenStream):
        m = self.inner.match(stream)
        if m is FAIL:
            # Opt success-with-empty: zero-width match, no captures.
            tok = stream.head()
            return MatchResult({}, stream, tok, tok)
        return m


@dataclass
class Choice:
    alts: list[Any]               # first matching alternative wins

    def match(self, stream: TokenStream):
        for alt in self.alts:
            m = alt.match(stream)
            if m is not FAIL:
                return m
        return FAIL                # no alternative matched


@dataclass
class Star:
    """Zero-or-more. Repeats `inner` until it fails; captures each
    match's captures into a list under `name`.
    """
    name: str
    inner: Any

    def match(self, stream: TokenStream):
        items: list[Any] = []
        s = stream
        first_token = s.head()
        last_token = first_token
        while True:
            m = self.inner.match(s)
            if m is FAIL:
                break
            items.append(m.captures)
            last_token = m.span_end
            s = m.rest
        return MatchResult({self.name: items}, s, first_token, last_token)


# ─── 4. Rule + register_form_rule (in-process registry) ─────────────────
#
# Sibling to api/app/services/substrate/grammar.py's register_form_rule.
# In-process for now; the substrate session form is the persistent
# version (closes by routing through the same registry).


@dataclass
class Rule:
    name: str
    pattern: Any
    action: Callable[[dict, dict], dict]   # (captures, span) -> Form object


_RULES: dict[str, Rule] = {}


def register_form_rule(name: str, pattern: Any, action: Callable) -> Rule:
    """Intern a (pattern, action) pair. Sibling to grammar.py's
    register_form_rule(session, ...) — same name, in-process registry."""
    rule = Rule(name=name, pattern=pattern, action=action)
    _RULES[name] = rule
    return rule


def list_form_rules() -> list[Rule]:
    return list(_RULES.values())


def lookup_form_rule(name: str) -> Optional[Rule]:
    return _RULES.get(name)


# ─── 5. the dispatch loop — try each rule against the stream ────────────


def parse(stream: TokenStream, rule_names: Optional[list[str]] = None) -> list[dict]:
    """Walk the stream, trying each registered rule in order until
    one matches. Fire the action; append the Form object to the
    output. Repeat until EOF.

    `rule_names` lets the caller restrict which rules are tried (e.g.
    only the import-statement rules for the demo). Default tries all.
    """
    rules = [_RULES[n] for n in (rule_names or list(_RULES.keys()))]
    out: list[dict] = []
    while not stream.empty():
        # Skip NEWLINE tokens between statements
        if stream.head().kind == "NEWLINE":
            stream = stream.tail()
            continue
        # Try each rule; first match wins
        matched = False
        for rule in rules:
            m = rule.pattern.match(stream)
            if m is FAIL:
                continue
            span = {
                "source_file": stream.source_path,
                "start_line":  m.span_start.line,
                "start_col":   m.span_start.col,
                "end_line":    m.span_end.line,
                "end_col":     m.span_end.col + len(m.span_end.value),
                "byte_start":  m.span_start.byte_start,
                "byte_end":    m.span_end.byte_end,
                "language_cell": "python",
            }
            form_obj = rule.action(m.captures, span)
            # Stamp source_attribution natively (the parser's track!
            # macro — same gesture as the framebuffer's provenance plane,
            # per lc-the-recipe-remembers-its-source).
            form_obj["source_attribution"] = span
            out.append(form_obj)
            stream = m.rest
            matched = True
            break
        if not matched:
            # Honest BMF: no rule matched. Future: invoke error-recovery
            # (Choice.FAIL at the parse-loop layer). Today: raise.
            tok = stream.head()
            raise SyntaxError(
                f"BMF: no rule matches token {tok.kind}({tok.value!r}) "
                f"at line {tok.line} col {tok.col} in {stream.source_path}"
            )
    return out


# ─── 6. Python `import` rules — the first real BMF closure ──────────────
#
# Each rule is a (pattern, action) pair. The pattern composes the
# primitives above; the action receives the captures and produces a
# Form object whose shape matches what ast.parse + _py_node_to_form
# would produce (see form_cli.py).
#
# Coverage today:
#   - `import x`
#   - `import x.y.z`
#   - `import x as y`
#   - `import x, y, z`             (multiple aliases on one statement)
#   - `from x import y`
#   - `from x.y import z`
#   - `from x import y as z`
#   - `from x import y, z`
#   - `from . import x`            (relative)
#   - `from .. import x`           (relative, deeper)
#
# Each is an honest BMF closure of one Python construct. No ast.parse
# in the path.


# Helper: match a dotted name (a.b.c) into a string.
# A dotted name is IDENT ('.' IDENT)*
def _dotted_name_pattern():
    return Sequence([
        Capture("head", Literal("IDENT")),
        Star("tail", Sequence([
            Literal("OP", "."),
            Capture("part", Literal("IDENT")),
        ])),
    ])


def _dotted_name_to_string(captures: dict) -> str:
    head = captures["head"]
    parts = [head]
    for item in captures.get("tail", []):
        parts.append(item["part"])
    return ".".join(parts)


# Helper: match leading dots for relative imports (`from .. import x`)
def _relative_dots_pattern():
    # Zero or more "." OPs.
    return Star("dots", Capture("dot", Literal("OP", ".")))


def _count_relative_dots(captures: dict) -> int:
    """Count the leading "." OPs of a relative import.

    The Capture wrapping around the Star spreads the Star's captures
    upward via `{**m.captures, ...}`, so the "dots" key from the
    Star("dots", Capture("dot", Literal("OP", "."))) lands at the
    outer captures level. Each match contributes one entry to the list.
    """
    return len(captures.get("dots", []))


# ──────────────────────────── Rule: `import x[.y.z][, ...]` ─────────────


_import_alias_pattern = Sequence([
    Capture("name", _dotted_name_pattern()),
    Opt(Sequence([
        Literal("KW", "as"),
        Capture("alias", Literal("IDENT")),
    ])),
])


def _build_import_node(captures: dict, span: dict) -> dict:
    """Build a py_Import Form object matching the shape ast.parse
    produces (per python-grammar.form's py_import_shape)."""
    names = []
    # `aliases` is the Star's collected captures
    for item in captures.get("aliases", []):
        # item carries: name (dict captures), and optionally alias
        name_captures = item["name"]["captures"]
        name_str = _dotted_name_to_string(name_captures)
        alias = item.get("alias")
        names.append({"name": name_str, "asname": alias})
    return {
        "category": "py_Import",
        "names": names,
    }


_import_stmt_pattern = Sequence([
    Literal("KW", "import"),
    Capture("aliases", Sequence([
        Capture("first", _import_alias_pattern),
        Star("rest", Sequence([
            Literal("OP", ","),
            Capture("entry", _import_alias_pattern),
        ])),
    ])),
])


# The pattern above is layered; let me flatten the aliases collection
# more directly. Replace with a Star-based approach that's cleaner:


def _make_import_aliases_pattern():
    """Match `alias (, alias)*` returning a list of alias dicts."""
    return Sequence([
        Capture("first", _import_alias_pattern),
        Star("rest", Sequence([
            Literal("OP", ","),
            Capture("entry", _import_alias_pattern),
        ])),
    ])


def _collect_import_aliases(captures: dict) -> list[dict]:
    """Extract the list of (name, alias) pairs from import-statement captures."""
    aliases = []
    first = captures.get("first")
    if first:
        # first is the dict returned by Capture("first", _import_alias_pattern)
        # which contains {"captures": {...}, ...}
        f_caps = first.get("captures", first)
        name = _dotted_name_to_string(f_caps["name"]["captures"])
        aliases.append({"name": name, "asname": f_caps.get("alias")})
    for item in captures.get("rest", []):
        entry = item.get("entry", {})
        e_caps = entry.get("captures", entry)
        name = _dotted_name_to_string(e_caps["name"]["captures"])
        aliases.append({"name": name, "asname": e_caps.get("alias")})
    return aliases


def _build_import_node_v2(captures: dict, span: dict) -> dict:
    return {
        "category": "py_Import",
        "names": _collect_import_aliases(captures),
    }


register_form_rule(
    "py_import",
    pattern=Sequence([
        Literal("KW", "import"),
        _make_import_aliases_pattern(),
    ]),
    action=_build_import_node_v2,
)


# ─────────────────── Rule: `from x[.y] import name[, name]` ─────────────


_from_import_name_pattern = Sequence([
    Capture("name", Literal("IDENT")),
    Opt(Sequence([
        Literal("KW", "as"),
        Capture("alias", Literal("IDENT")),
    ])),
])


def _collect_from_names(captures: dict) -> list[dict]:
    names = []
    first = captures.get("first_name")
    if first:
        f = first.get("captures", first)
        names.append({"name": f["name"], "asname": f.get("alias")})
    for item in captures.get("more_names", []):
        entry = item.get("more_entry", {})
        e = entry.get("captures", entry)
        names.append({"name": e["name"], "asname": e.get("alias")})
    return names


def _build_import_from_node(captures: dict, span: dict) -> dict:
    """Build a py_ImportFrom Form object."""
    level = _count_relative_dots(captures)
    # module is optional for `from . import x`
    module = None
    mod_captures = captures.get("module")
    if mod_captures and mod_captures.get("captures"):
        module = _dotted_name_to_string(mod_captures["captures"])
    return {
        "category": "py_ImportFrom",
        "module": module,
        "level":  level,
        "names":  _collect_from_names(captures),
    }


register_form_rule(
    "py_import_from",
    pattern=Sequence([
        Literal("KW", "from"),
        Capture("rel_dots", _relative_dots_pattern()),
        Opt(Capture("module", _dotted_name_pattern())),
        Literal("KW", "import"),
        Capture("first_name", _from_import_name_pattern),
        Star("more_names", Sequence([
            Literal("OP", ","),
            Capture("more_entry", _from_import_name_pattern),
        ])),
    ]),
    action=_build_import_from_node,
)


# ─── 7. convenience: parse a single statement ───────────────────────────


def parse_python_imports(source: str, source_path: str = "<input>") -> list[dict]:
    """Parse a source string containing only import / from-import
    statements through the BMF rules registered above. Returns Form
    objects shaped like ast.parse + _py_node_to_form would produce.
    """
    stream = tokenize(source, source_path)
    return parse(stream, rule_names=["py_import_from", "py_import"])
    # Order matters: try py_import_from first because "from" is
    # unambiguous; "import" alone is the catch-all. This is the
    # precedence layer BMF rules carry implicitly via registration
    # order — a future register_form_rule(precedence=N) call lets
    # the body name it explicitly.
