"""Decompiler — .fkb back to Python source.

Round trip: Python source → compile → .fkb → decompile → Python source.
Where this diverges from the original, the divergence IS the signal:
either a rule didn't capture enough information, or the inverse action
isn't defined yet.

Status today: first-cut. Joins token values per statement with single
spaces and indents children. Whitespace and operator-spacing nuance
needed for byte-identical roundtrip lands as Phase 2/3 brings the
reverse actions in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .sdk import NodeID, read_fkb


def _by_id(nodes):
    return {str(n["nodeid"]): n for n in nodes}


def _is_open_bracket(t):
    return t in ("(", "[", "{")


def _is_close_bracket(t):
    return t in (")", "]", "}")


_STRING_QUOTE_MAP = {
    "sq": ("'", "'"),
    "dq": ('"', '"'),
    "triple-sq": ("'''", "'''"),
    "triple-dq": ('"""', '"""'),
}

_STRING_PREFIX_MAP = {
    "py-string": "",
    "py-bytes": "b",
    "py-fstring": "f",
    "py-tstring": "t",
}


def _render_string_atom(kind, value):
    """Reassemble a string atom from its kind + body, restoring prefix/quote.

    Suffix encoding:
      `py-<prefix>`              → unquoted (legacy)
      `py-<prefix>-sq|dq`        → single/double quoted
      `py-<prefix>-triple-sq|dq` → triple-quoted
    """
    base = kind
    quote_key = "dq"
    # Check triple FIRST so the chop below doesn't strip the wrong suffix.
    if "-triple-sq" in base:
        quote_key = "triple-sq"
        base = base.replace("-triple-sq", "")
    elif "-triple-dq" in base:
        quote_key = "triple-dq"
        base = base.replace("-triple-dq", "")
    elif base.endswith("-sq"):
        quote_key = "sq"
        base = base[:-3]
    elif base.endswith("-dq"):
        quote_key = "dq"
        base = base[:-3]
    open_q, close_q = _STRING_QUOTE_MAP.get(quote_key, ('"', '"'))
    prefix = _STRING_PREFIX_MAP.get(base, "")
    return f"{prefix}{open_q}{value}{close_q}"


def _render_atom(kind, value):
    """Re-render a token from its kind + raw value."""
    if kind.startswith(("py-string", "py-bytes", "py-fstring", "py-tstring")):
        return _render_string_atom(kind, value)
    # py-keyword, py-name, py-int, py-float, py-op, py-comment — value is the surface text.
    return value


def _normalize_token(entry):
    """Accept either (kind, value) tuple/list or bare value string."""
    if isinstance(entry, (list, tuple)) and len(entry) == 2:
        kind, value = entry
        return _render_atom(kind, value)
    return str(entry)


def _render_tokens(token_entries):
    """Best-effort source text from a token list.

    Spacing follows Python style: tight around brackets/commas/dots,
    @ for decorator, = inside parens for kwargs. Comments get a
    two-space gutter when trailing, flush-left when leading.
    """
    kinds = []
    values = []
    raw_values = []
    for entry in token_entries:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            kinds.append(entry[0])
            raw_values.append(entry[1])
            values.append(_render_atom(entry[0], entry[1]))
        else:
            kinds.append("")
            raw_values.append(str(entry))
            values.append(str(entry))

    def is_op(idx, *symbols):
        """Token at idx is a py-op whose value is one of the symbols."""
        if idx < 0 or idx >= len(kinds):
            return False
        return kinds[idx] == "py-op" and raw_values[idx] in symbols

    # Pre-pass: depths per position so we know when `=` is a kwarg
    # and when `:` is a slice colon.
    paren_depth = []
    square_depth = []
    pd = 0
    sd = 0
    for i in range(len(kinds)):
        paren_depth.append(pd)
        square_depth.append(sd)
        if is_op(i, "("):
            pd += 1
        elif is_op(i, ")"):
            pd = max(0, pd - 1)
        elif is_op(i, "["):
            sd += 1
            pd += 1
        elif is_op(i, "]"):
            sd = max(0, sd - 1)
            pd = max(0, pd - 1)
        elif is_op(i, "{"):
            pd += 1
        elif is_op(i, "}"):
            pd = max(0, pd - 1)

    out = []
    for i, tok in enumerate(values):
        kind = kinds[i]
        raw = raw_values[i]
        if i == 0:
            out.append(tok)
            continue
        prev = values[i - 1]
        prev_kind = kinds[i - 1]
        prev_raw = raw_values[i - 1]

        if kind == "py-comment":
            out.append("  " + tok)
            continue
        # Tight close: comma / colon / semicolon / close-bracket bind tight.
        if is_op(i, ",", ":", ";", ")", "]", "}"):
            out.append(tok)
            continue
        # Inside [] (slice context), the value after `:` binds tight.
        if is_op(i - 1, ":") and square_depth[i - 1] > 0:
            out.append(tok)
            continue
        # Tight after open bracket or after `.` or after `@` decorator.
        if is_op(i - 1, "(", "[", "{", ".", "@"):
            out.append(tok)
            continue
        # Unary +/-/*/** (preceded by an operator that opens an expression)
        # binds tight to its operand. The "opens expression" check covers
        # call/list/tuple/dict/comma/assign/return/`:`/keywords like 'not'/'and'/'or'.
        _UNARY_PARENTS = ("(", "[", "{", ",", "=", ":", "+", "-", "*", "/", "%",
                          "**", "//", "<", ">", "<=", ">=", "==", "!=",
                          "+=", "-=", "*=", "/=", "%=", "**=", "//=",
                          "&", "|", "^", "<<", ">>", "->", ";", "@")
        if is_op(i - 1, "+", "-", "*", "**") and i - 2 >= 0 and (
            is_op(i - 2, *_UNARY_PARENTS) or kinds[i - 2] == "py-keyword"
        ):
            out.append(tok)
            continue
        # `.` binds tight on both sides — but NOT after a keyword like `from`.
        if is_op(i, "."):
            if prev_kind == "py-keyword":
                out.append(" " + tok)
            else:
                out.append(tok)
            continue
        # `(` immediately after a name / close-bracket = call.
        if is_op(i, "(") and (prev_kind == "py-name" or is_op(i - 1, ")", "]")):
            out.append(tok)
            continue
        # `[` after a name / close-bracket = subscript.
        if is_op(i, "[") and (prev_kind == "py-name" or is_op(i - 1, ")", "]")):
            out.append(tok)
            continue
        # `=` inside parens with `name =` shape = kwarg, no spaces.
        if is_op(i, "=") and paren_depth[i] > 0 and prev_kind == "py-name":
            out.append(tok)
            continue
        if is_op(i - 1, "=") and paren_depth[i - 1] > 0:
            if i - 2 >= 0 and kinds[i - 2] == "py-name":
                out.append(tok)
                continue
        out.append(" " + tok)
    return "".join(out)


def _statement_text(node):
    value = node.get("value") or {}
    tokens = value.get("tokens") or []
    # A statement that is only py-blank tokens renders as blank lines.
    only_blanks = (
        tokens
        and all(
            isinstance(t, (list, tuple))
            and len(t) == 2
            and t[0] == "py-blank"
            for t in tokens
        )
    )
    if only_blanks:
        return ""  # the surrounding newline join supplies the blank
    return _render_tokens(tokens)


def _walk(node, by_id, indent=0):
    """Render one statement or statement-block."""
    kind = node.get("kind")
    pad = "    " * indent
    if kind == "statement":
        text = _statement_text(node)
        # Blank-line statements render as "" so they don't carry trailing pad.
        return text if text == "" else f"{pad}{text}"
    if kind == "statement-block":
        children = node.get("children") or []
        if not children:
            return f"{pad}# empty block"
        head_node = by_id.get(str(children[0]))
        head_line = (
            f"{pad}{_statement_text(head_node)}" if head_node else f"{pad}# missing head {children[0]}"
        )
        body_lines = []
        for child_id in children[1:]:
            child_node = by_id.get(str(child_id))
            if child_node is None:
                body_lines.append(f"{pad}    # missing child {child_id}")
                continue
            body_lines.append(_walk(child_node, by_id, indent + 1))
        return head_line + "\n" + "\n".join(body_lines)
    if kind == "module":
        children = node.get("children") or []
        lines = []
        for cid in children:
            cnode = by_id.get(str(cid))
            if cnode is not None:
                lines.append(_walk(cnode, by_id, 0))
        return "\n".join(lines)
    if kind == "package":
        children = node.get("children") or []
        lines = []
        for cid in children:
            cnode = by_id.get(str(cid))
            if cnode is not None:
                lines.append(_walk(cnode, by_id, 0))
        return "\n\n".join(lines)
    # Leaf / unknown — render the kind as a comment for visibility.
    return f"{pad}# unhandled-kind: {kind}"


def decompile_module(nodes, module_id=None):
    """Given the node list read from .fkb, return Python source for one module."""
    by_id = _by_id(nodes)
    if module_id is None:
        modules = [n for n in nodes if n.get("kind") == "module"]
        if not modules:
            return "# no module node found"
        module_id = str(modules[-1]["nodeid"])
    root = by_id.get(str(module_id))
    if root is None:
        return f"# unknown module id {module_id}"
    return _walk(root, by_id, 0)


def decompile_file(fkb_path, out_path=None):
    nodes = read_fkb(fkb_path)
    text = decompile_module(nodes)
    if out_path is not None:
        Path(out_path).write_text(text)
    return text


__all__ = [
    "decompile_module",
    "decompile_file",
]
