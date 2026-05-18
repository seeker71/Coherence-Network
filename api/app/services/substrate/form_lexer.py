"""Runtime-extensible token pattern registry for Form's tokenizer.

Until now, `_TOKEN_PATTERNS` in `form.py` was a hardcoded list — adding
a new token kind (a new operator, a new delimiter, a new literal shape)
meant editing form.py. This module lifts the pattern list into an
ordered registry so any module can register a new pattern at runtime,
and the tokenizer rebuilds its master regex from the registry.

The closing of the gap form-language.md → "The lexer ... is still
hand-written regex code": no longer hardcoded. Token patterns are now
substrate-runtime-resident; the tokenizer reads them from a registry
that can grow at runtime.

Order discipline: the registry is an ordered list, not a dict. Regex
alternation matches longest-first only when patterns are listed in the
right order (`==` before `=`, `<=` before `<`, `&&` before `|`).
Insertion points are explicit:

    register_token_pattern("MY_OP", r"\\$\\$")                  # appended
    register_token_pattern("MY_OP", r"\\$\\$", before="PLUS")   # before PLUS
    register_token_pattern("MY_OP", r"\\$\\$", after="EQ")      # after EQ

The tokenizer caches its compiled regex; mutation of the registry
invalidates the cache so the next tokenize call rebuilds.

See also:
- `form_rules.py` — compound keyword registry
- `form_queries.py` — query-verb registry
- `form_atoms.py` — primary-atom registry
- `form_eval.py` — operator-category registry
- This module — token-pattern registry (the bottom of the parser stack)

Together they form the runtime-extensible registries the parser
consults end-to-end. `form.py`'s hardcoded paths now consist of the
parser flow itself (recursive descent through precedence ladders);
every leaf, atom, keyword, operator, query, and now token shape is
registry-resident.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple


# Each pattern entry is `(kind, regex_source)`. Kept as a list so order
# is preserved — longest-match regex alternation requires `==` to come
# before `=`, `<=` before `<`, etc.
_TOKEN_PATTERNS: List[Tuple[str, str]] = []

# Cached compiled regex; invalidated when the registry mutates.
_COMPILED_RE: Optional[re.Pattern] = None


def register_token_pattern(
    kind: str,
    regex: str,
    *,
    before: Optional[str] = None,
    after: Optional[str] = None,
) -> None:
    """Register a token pattern. Kind must be ident-shaped; regex is a
    Python regular expression string (no flags — the master regex uses
    none). Use `before=<kind>` or `after=<kind>` to control position;
    omit both to append at the end."""
    if not kind or not kind.replace("_", "").isalnum():
        raise ValueError(f"form_lexer: kind must be ident-shaped, got {kind!r}")
    # Replace any existing entry of the same kind so the registry stays
    # a function — one regex per kind.
    unregister_token_pattern(kind)
    if before is not None and after is not None:
        raise ValueError("form_lexer: pass before OR after, not both")
    if before is not None:
        idx = _index_of(before)
        if idx < 0:
            raise KeyError(f"form_lexer: no pattern named {before!r}")
        _TOKEN_PATTERNS.insert(idx, (kind, regex))
    elif after is not None:
        idx = _index_of(after)
        if idx < 0:
            raise KeyError(f"form_lexer: no pattern named {after!r}")
        _TOKEN_PATTERNS.insert(idx + 1, (kind, regex))
    else:
        _TOKEN_PATTERNS.append((kind, regex))
    _invalidate()


def unregister_token_pattern(kind: str) -> bool:
    """Remove the pattern of the given kind. Returns True if removed."""
    global _TOKEN_PATTERNS
    new_list = [p for p in _TOKEN_PATTERNS if p[0] != kind]
    if len(new_list) == len(_TOKEN_PATTERNS):
        return False
    _TOKEN_PATTERNS = new_list
    _invalidate()
    return True


def list_token_patterns() -> List[Tuple[str, str]]:
    """Return the ordered list of (kind, regex_source) pairs."""
    return list(_TOKEN_PATTERNS)


def get_token_regex() -> re.Pattern:
    """Return the cached compiled regex, rebuilding if invalidated."""
    global _COMPILED_RE
    if _COMPILED_RE is None:
        _COMPILED_RE = re.compile(
            "|".join(f"(?P<{name}>{pat})" for name, pat in _TOKEN_PATTERNS)
        )
    return _COMPILED_RE


def _index_of(kind: str) -> int:
    for i, (k, _) in enumerate(_TOKEN_PATTERNS):
        if k == kind:
            return i
    return -1


def _invalidate() -> None:
    global _COMPILED_RE
    _COMPILED_RE = None


# ---------------------------------------------------------------------------
# Built-in token patterns — the seed set
# ---------------------------------------------------------------------------
#
# Order matters. Multi-char operators MUST come before their single-char
# components (==, !=, <=, >= before <, >, =; &&, || before & and |;
# triple-quote string before single-quote). Whitespace/comments first
# so they short-circuit on common input. IDENT last so it doesn't
# accidentally match keyword shapes that other rules might want.


def _register_builtins() -> None:
    _patterns: List[Tuple[str, str]] = [
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
        # Triple-quoted multiline strings come FIRST so the alternation
        # matches them before the single-quote rule. Non-greedy.
        ("STRING", r'"""[\s\S]*?"""|"([^"\\]|\\.)*"'),
        ("INT", r"\d+"),
        ("IDENT", r"[A-Za-z_][A-Za-z_0-9\-]*"),
    ]
    for kind, regex in _patterns:
        _TOKEN_PATTERNS.append((kind, regex))
    _invalidate()


_register_builtins()


__all__ = [
    "register_token_pattern",
    "unregister_token_pattern",
    "list_token_patterns",
    "get_token_regex",
]
