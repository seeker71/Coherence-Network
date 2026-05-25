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


def _render_atom(kind, value):
    """Re-render a token from its kind + raw value."""
    if kind == "py-string":
        return '"' + value.replace('"', '\\"') + '"'
    if kind == "py-bytes":
        return 'b"' + value.replace('"', '\\"') + '"'
    if kind == "py-fstring":
        return 'f"' + value.replace('"', '\\"') + '"'
    if kind == "py-tstring":
        return 't"' + value.replace('"', '\\"') + '"'
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

    Tightens around brackets, commas, dots so output reads like Python.
    Token entries may be (kind, value) tuples (preserved across compile)
    or raw value strings (legacy shape). Comments get a two-space gutter
    when trailing (preceded by another token), no padding when leading.
    """
    kinds = []
    values = []
    for entry in token_entries:
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            kinds.append(entry[0])
            values.append(_render_atom(entry[0], entry[1]))
        else:
            kinds.append("")
            values.append(str(entry))

    out = []
    for i, tok in enumerate(values):
        kind = kinds[i]
        if i == 0:
            out.append(tok)
            continue
        prev = values[i - 1]
        if kind == "py-comment":
            out.append("  " + tok)
            continue
        if _is_open_bracket(prev) or tok in (",", ":", ";", ")", "]", "}"):
            out.append(tok)
        elif tok == "(" and (prev.replace("_", "").isalnum() or _is_close_bracket(prev) or prev in (")", "]")):
            out.append(tok)
        elif tok == "." or prev == ".":
            out.append(tok)
        elif tok == "[" and (prev.replace("_", "").isalnum() or _is_close_bracket(prev)):
            out.append(tok)
        else:
            out.append(" " + tok)
    return "".join(out)


def _statement_text(node):
    value = node.get("value") or {}
    tokens = value.get("tokens") or []
    return _render_tokens(tokens)


def _walk(node, by_id, indent=0):
    """Render one statement or statement-block."""
    kind = node.get("kind")
    pad = "    " * indent
    if kind == "statement":
        return f"{pad}{_statement_text(node)}"
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
