#!/usr/bin/env python3
"""form_cli.py — Form-native CLI: generate, execute, convert.

The CLI Urs named: kernel + binary library + Language cells, end-to-end.
Uses ONLY the experiments/local-llm-cell-v0/form_native.py recipes and
the .recipelib bundles in docs/coherence-substrate/libraries/. No
substrate session boot, no host stdlib math — every numeric op runs
through the Form-native composition (Newton sqrt, Taylor exp, recursive
list ops) verified by parity_check.py.

Subcommands:

    form_cli list <library>
        Print library meta + per-recipe summary.

    form_cli execute <library> <recipe> [arg ...]
        Invoke a recipe by name. Args are JSON-encoded positional values.
        Result emitted as JSON.

    form_cli convert in  --tongue <name> <input-file>
        Parse raw input (JSON, prose, …) into a Form object tree.
        Emits the Form object as JSON on stdout.

    form_cli convert out --tongue <name> <form-object-file>
        Emit a Form object tree as raw output in the named tongue.

    form_cli generate <form-source-file> [--out <library-path>]
        Extract every `defn name(args) = body` from a .form file and
        bundle into a .recipelib. The Form view is the source text;
        Python/TS views are deferred to the auto-generator follow-up.

Examples:

    form_cli execute libraries/cell-numerics.recipelib.json cosine \\
        '[1.0, 0.0, 0.0]' '[1.0, 0.0, 0.0]'
    # → 1.0

    form_cli convert in --tongue json data.json | \\
        form_cli convert out --tongue json /dev/stdin
    # round-trip JSON → Form object → JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY_DIR = REPO_ROOT / "docs" / "coherence-substrate" / "libraries"
EXPERIMENTS_DIR = REPO_ROOT / "experiments" / "local-llm-cell-v0"

# Allow imports of form_native from experiments/.
sys.path.insert(0, str(EXPERIMENTS_DIR))


def _die(message: str, code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


def _resolve_library_path(arg: str) -> Path:
    """Library can be referenced by absolute path, by basename in
    docs/coherence-substrate/libraries/, or bare name (auto-appends
    `.recipelib.json`).
    """
    p = Path(arg)
    if p.exists():
        return p
    candidate = DEFAULT_LIBRARY_DIR / arg
    if candidate.exists():
        return candidate
    candidate = DEFAULT_LIBRARY_DIR / f"{arg}.recipelib.json"
    if candidate.exists():
        return candidate
    _die(f"library not found: {arg} (looked in {DEFAULT_LIBRARY_DIR})")


def _load_library(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ─── subcommand: list ────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> int:
    path = _resolve_library_path(args.library)
    library = _load_library(path)
    meta = library.get("library_meta", {})
    print(f"library: {meta.get('name')}  v{meta.get('version')}")
    print(f"  path: {path}")
    print(f"  language_cells: {', '.join(library.get('language_cells', []))}")
    deps = library.get("dependencies", [])
    print(f"  dependencies: {', '.join(deps) if deps else '(none)'}")
    print(f"  recipes ({len(library.get('recipes', []))}):")
    name_w = max(
        (len(r.get("name", "")) for r in library.get("recipes", [])),
        default=8,
    )
    for r in library.get("recipes", []):
        bp = r.get("blueprint", {})
        sig = f"({', '.join(bp.get('input_types', []))}) → {bp.get('output_type', '')}"
        node_hint = r.get("node_id_hint", "?")
        print(f"    {r['name']:<{name_w}}  {sig:<48}  @recipe({node_hint})")
    return 0


# ─── subcommand: execute ─────────────────────────────────────────────────


def cmd_execute(args: argparse.Namespace) -> int:
    path = _resolve_library_path(args.library)
    library = _load_library(path)
    recipe = None
    for r in library.get("recipes", []):
        if r.get("name") == args.recipe:
            recipe = r
            break
    if recipe is None:
        names = [r.get("name") for r in library.get("recipes", [])]
        _die(f"recipe '{args.recipe}' not in library (available: {', '.join(names)})")

    try:
        import form_native  # type: ignore
    except ImportError as e:
        _die(f"form_native module not importable: {e}")

    fn = getattr(form_native, args.recipe, None)
    if fn is None:
        _die(
            f"no form_native implementation for '{args.recipe}'. "
            f"Available: {', '.join(sorted(n for n in dir(form_native) if not n.startswith('_')))}"
        )

    parsed_args = []
    for raw in args.args:
        try:
            parsed_args.append(json.loads(raw))
        except json.JSONDecodeError as e:
            _die(f"could not parse argument as JSON: {raw!r} ({e})")

    try:
        result = fn(*parsed_args)
    except Exception as e:  # noqa: BLE001 — surface any execution error honestly
        _die(f"execution failed for '{args.recipe}': {e}")

    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))
    return 0


# ─── subcommand: convert ─────────────────────────────────────────────────
#
# I/O ↔ Form object via the Language cell for the named tongue. JSON is
# the worked example because it's the simplest text-tree grammar; YAML
# / Markdown / PNG follow the same shape once their Language cells are
# loaded. The Form object representation: each node has a `category`
# (B_Object / B_List / B_String / B_Number / B_Bool / B_Null) and either
# `children` (composite) or `value` (leaf).


_CATEGORIES = {
    "B_Object": dict,
    "B_List":   list,
    "B_String": str,
    "B_Number": (int, float),
    "B_Bool":   bool,
    "B_Null":   type(None),
}


def _classify(value) -> str:
    # Order matters — bool is a subclass of int in Python.
    if value is None:
        return "B_Null"
    if isinstance(value, bool):
        return "B_Bool"
    if isinstance(value, (int, float)):
        return "B_Number"
    if isinstance(value, str):
        return "B_String"
    if isinstance(value, list):
        return "B_List"
    if isinstance(value, dict):
        return "B_Object"
    return "B_Unknown"


def _json_to_form_tree(value) -> dict:
    cat = _classify(value)
    if cat in ("B_Object",):
        return {
            "category": cat,
            "children": [
                {"key": k, "value": _json_to_form_tree(v)}
                for k, v in value.items()
            ],
        }
    if cat in ("B_List",):
        return {
            "category": cat,
            "children": [_json_to_form_tree(v) for v in value],
        }
    return {"category": cat, "value": value}


def _form_tree_to_json(tree):
    cat = tree.get("category")
    if cat == "B_Object":
        return {c["key"]: _form_tree_to_json(c["value"]) for c in tree.get("children", [])}
    if cat == "B_List":
        return [_form_tree_to_json(c) for c in tree.get("children", [])]
    if cat in ("B_String", "B_Number", "B_Bool", "B_Null"):
        return tree.get("value")
    if cat is None and "children" in tree:
        # Tolerate untagged composites (e.g. a Form-object file whose
        # top level is a recipe tree, not a JSON tree).
        return [_form_tree_to_json(c) for c in tree["children"]]
    return tree.get("value")


def _convert_in_json(input_path: Path) -> dict:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    return {
        "source_tongue": "json",
        "source_path": str(input_path),
        "tree": _json_to_form_tree(raw),
    }


def _convert_out_json(form_object: dict) -> str:
    tree = form_object.get("tree", form_object)
    return json.dumps(_form_tree_to_json(tree), indent=2)


# ─── markdown tongue ─────────────────────────────────────────────────────
#
# Implements docs/coherence-substrate/markdown-grammar.form.
# Source attribution stamped on every parsed node (per
# lc-the-recipe-remembers-its-source).

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_HR_RE = re.compile(r"^\s{0,3}([\*\-_])\s*\1\s*\1[\s\1]*$")
_FENCE_RE = re.compile(r"^\s{0,3}```\s*([a-zA-Z0-9_+\-]*)\s*$")
_FENCE_CLOSE_RE = re.compile(r"^\s{0,3}```\s*$")
_UL_RE = re.compile(r"^(\s*)([\-*+])\s+(.*)$")
_OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$")
_CROSSREF_RE = re.compile(r"^→\s+([a-z][a-z0-9-]*(?:\s*,\s*[a-z][a-z0-9-]*)*)\s*$")
_FRONTMATTER_DELIM_RE = re.compile(r"^---\s*$")


def _attr(source_path: str, start_line: int, end_line: int,
          start_col: int = 1, end_col: int = 1,
          byte_start: int = 0, byte_end: int = 0,
          language_cell: str = "markdown") -> dict:
    return {
        "source_file":   source_path,
        "start_line":    start_line,
        "start_col":     start_col,
        "end_line":      end_line,
        "end_col":       end_col,
        "byte_start":    byte_start,
        "byte_end":      byte_end,
        "language_cell": language_cell,
    }


def _md_inline(text: str) -> list[dict]:
    """Parse inline markdown into a list of inline-shape nodes.

    Handles **bold**, *italic*, `code`, [text](url), ![alt](url). Leaves
    unmatched text as md_text_inline_shape leaves. Recursive composition
    is honest about the simple-regex limit (GAP-M2 in grammar file).
    """
    if not text:
        return []
    nodes: list[dict] = []
    i = 0
    n = len(text)
    while i < n:
        # image
        if text[i:i+2] == "![":
            end = text.find("]", i + 2)
            if end != -1 and text[end:end+2] == "](":
                close = text.find(")", end + 2)
                if close != -1:
                    nodes.append({
                        "category": "md_image",
                        "alt": text[i+2:end],
                        "url": text[end+2:close],
                    })
                    i = close + 1
                    continue
        # link
        if text[i] == "[":
            end = text.find("]", i + 1)
            if end != -1 and text[end:end+2] == "](":
                close = text.find(")", end + 2)
                if close != -1:
                    inner = text[i+1:end]
                    nodes.append({
                        "category": "md_link",
                        "text": _md_inline(inner),
                        "url": text[end+2:close],
                    })
                    i = close + 1
                    continue
        # bold (**…**)
        if text[i:i+2] == "**":
            end = text.find("**", i + 2)
            if end != -1:
                nodes.append({
                    "category": "md_emphasis_bold",
                    "inlines": _md_inline(text[i+2:end]),
                })
                i = end + 2
                continue
        # italic (*…*) — but not if followed by * (covered above)
        if text[i] == "*" and (i + 1 < n) and text[i+1] != "*":
            end = text.find("*", i + 1)
            if end != -1 and (end + 1 >= n or text[end+1] != "*"):
                nodes.append({
                    "category": "md_emphasis_italic",
                    "inlines": _md_inline(text[i+1:end]),
                })
                i = end + 1
                continue
        # inline code (`…`)
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end != -1:
                nodes.append({
                    "category": "md_code_inline",
                    "text": text[i+1:end],
                })
                i = end + 1
                continue
        # plain text — accumulate until next special char
        start = i
        while i < n and text[i] not in "*`[!":
            i += 1
        if start == i:    # we matched a special-char prefix that didn't pair; consume it as text
            i += 1
        nodes.append({"category": "md_text_inline", "text": text[start:i]})
    return nodes


def _md_parse_blocks(lines: list[str], source_path: str,
                     start_line_offset: int = 0) -> list[dict]:
    """Parse a list of markdown lines into block-level Form nodes."""
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        line_no = i + 1 + start_line_offset

        # Blank line — skip
        if not line.strip():
            i += 1
            continue

        # Heading
        m = _HEADING_RE.match(line)
        if m:
            blocks.append({
                "category": "md_heading",
                "level": len(m.group(1)),
                "text": _md_inline(m.group(2)),
                "source_attribution": _attr(source_path, line_no, line_no),
            })
            i += 1
            continue

        # Horizontal rule
        if _HR_RE.match(line):
            blocks.append({
                "category": "md_horizontal_rule",
                "marker": line.strip(),
                "source_attribution": _attr(source_path, line_no, line_no),
            })
            i += 1
            continue

        # Cross-ref (body convention)
        m = _CROSSREF_RE.match(line)
        if m:
            targets = [t.strip() for t in m.group(1).split(",")]
            blocks.append({
                "category": "md_crossref_block",
                "targets": targets,
                "source_attribution": _attr(source_path, line_no, line_no),
            })
            i += 1
            continue

        # Fenced code block
        m = _FENCE_RE.match(line)
        if m:
            language = m.group(1) or None
            start_line = line_no
            i += 1
            content_lines: list[str] = []
            while i < len(lines) and not _FENCE_CLOSE_RE.match(lines[i]):
                content_lines.append(lines[i])
                i += 1
            end_line = i + 1 + start_line_offset
            if i < len(lines):
                i += 1   # consume closing fence
            blocks.append({
                "category": "md_code_block",
                "fence": "fenced",
                "language": language,
                "content": "\n".join(content_lines),
                "source_attribution": _attr(source_path, start_line, end_line),
            })
            continue

        # Blockquote
        if _BLOCKQUOTE_RE.match(line):
            start_line = line_no
            inner: list[str] = []
            while i < len(lines) and _BLOCKQUOTE_RE.match(lines[i]):
                inner.append(_BLOCKQUOTE_RE.match(lines[i]).group(1))
                i += 1
            end_line = i + start_line_offset
            blocks.append({
                "category": "md_blockquote",
                "blocks": _md_parse_blocks(inner, source_path, start_line - 1),
                "source_attribution": _attr(source_path, start_line, end_line),
            })
            continue

        # Unordered list
        if _UL_RE.match(line):
            start_line = line_no
            items: list[dict] = []
            while i < len(lines):
                m = _UL_RE.match(lines[i])
                if not m:
                    break
                items.append({
                    "category": "md_list_item",
                    "marker": m.group(2),
                    "contents": [{
                        "category": "md_paragraph",
                        "inlines": _md_inline(m.group(3)),
                    }],
                    "source_attribution": _attr(source_path, i + 1 + start_line_offset,
                                                i + 1 + start_line_offset),
                })
                i += 1
            blocks.append({
                "category": "md_list",
                "ordered": False,
                "tight": True,
                "items": items,
                "source_attribution": _attr(source_path, start_line, i + start_line_offset),
            })
            continue

        # Ordered list
        if _OL_RE.match(line):
            start_line = line_no
            items = []
            while i < len(lines):
                m = _OL_RE.match(lines[i])
                if not m:
                    break
                items.append({
                    "category": "md_list_item",
                    "marker": f"{m.group(2)}.",
                    "contents": [{
                        "category": "md_paragraph",
                        "inlines": _md_inline(m.group(3)),
                    }],
                    "source_attribution": _attr(source_path, i + 1 + start_line_offset,
                                                i + 1 + start_line_offset),
                })
                i += 1
            blocks.append({
                "category": "md_list",
                "ordered": True,
                "tight": True,
                "items": items,
                "source_attribution": _attr(source_path, start_line, i + start_line_offset),
            })
            continue

        # Paragraph — consume until blank line or next block-level start
        start_line = line_no
        para_lines = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                break
            if (_HEADING_RE.match(nxt) or _HR_RE.match(nxt)
                    or _FENCE_RE.match(nxt) or _UL_RE.match(nxt)
                    or _OL_RE.match(nxt) or _BLOCKQUOTE_RE.match(nxt)
                    or _CROSSREF_RE.match(nxt)):
                break
            para_lines.append(nxt)
            i += 1
        end_line = i + start_line_offset
        blocks.append({
            "category": "md_paragraph",
            "inlines": _md_inline(" ".join(para_lines)),
            "source_attribution": _attr(source_path, start_line, end_line),
        })

    return blocks


def _convert_in_markdown(input_path: Path) -> dict:
    text = input_path.read_text(encoding="utf-8")
    lines = text.split("\n")
    source_path = str(input_path)

    # Frontmatter detection
    frontmatter = None
    start_idx = 0
    if lines and _FRONTMATTER_DELIM_RE.match(lines[0]):
        for j in range(1, len(lines)):
            if _FRONTMATTER_DELIM_RE.match(lines[j]):
                raw = "\n".join(lines[1:j])
                frontmatter = {
                    "category": "md_frontmatter",
                    "delimiter": "yaml",
                    "raw_text": raw,
                    "source_attribution": _attr(source_path, 1, j + 1),
                }
                start_idx = j + 1
                break

    blocks = _md_parse_blocks(lines[start_idx:], source_path, start_idx)

    return {
        "source_tongue": "markdown",
        "source_path": source_path,
        "tree": {
            "category": "md_document",
            "frontmatter": frontmatter,
            "blocks": blocks,
            "source_attribution": _attr(source_path, 1, len(lines)),
        },
    }


def _md_emit_inlines(inlines: list[dict]) -> str:
    out: list[str] = []
    for n in inlines:
        cat = n.get("category")
        if cat == "md_text_inline":
            out.append(n.get("text", ""))
        elif cat == "md_emphasis_bold":
            out.append("**" + _md_emit_inlines(n.get("inlines", [])) + "**")
        elif cat == "md_emphasis_italic":
            out.append("*" + _md_emit_inlines(n.get("inlines", [])) + "*")
        elif cat == "md_code_inline":
            out.append("`" + n.get("text", "") + "`")
        elif cat == "md_link":
            out.append("[" + _md_emit_inlines(n.get("text", [])) + "](" + n.get("url", "") + ")")
        elif cat == "md_image":
            out.append("![" + n.get("alt", "") + "](" + n.get("url", "") + ")")
    return "".join(out)


def _md_emit_block(block: dict) -> str:
    cat = block.get("category")
    if cat == "md_heading":
        return "#" * block.get("level", 1) + " " + _md_emit_inlines(block.get("text", [])) + "\n"
    if cat == "md_paragraph":
        return _md_emit_inlines(block.get("inlines", [])) + "\n"
    if cat == "md_horizontal_rule":
        return block.get("marker", "---") + "\n"
    if cat == "md_code_block":
        lang = block.get("language") or ""
        return f"```{lang}\n{block.get('content', '')}\n```\n"
    if cat == "md_blockquote":
        inner = "".join(_md_emit_block(b) for b in block.get("blocks", []))
        return "\n".join("> " + ln for ln in inner.rstrip("\n").split("\n")) + "\n"
    if cat == "md_list":
        out: list[str] = []
        for idx, item in enumerate(block.get("items", []), 1):
            marker = item.get("marker", "-")
            if block.get("ordered"):
                marker = f"{idx}."
            body = "".join(_md_emit_block(c) for c in item.get("contents", [])).rstrip("\n")
            out.append(f"{marker} {body}")
        return "\n".join(out) + "\n"
    if cat == "md_crossref_block":
        return "→ " + ", ".join(block.get("targets", [])) + "\n"
    return ""


def _convert_out_markdown(form_object: dict) -> str:
    tree = form_object.get("tree", form_object)
    if tree.get("category") != "md_document":
        return ""
    parts: list[str] = []
    fm = tree.get("frontmatter")
    if fm is not None:
        parts.append("---\n" + fm.get("raw_text", "") + "\n---\n")
    for b in tree.get("blocks", []):
        parts.append(_md_emit_block(b))
    return "\n".join(parts)


# ─── python tongue ───────────────────────────────────────────────────────
#
# Implements docs/coherence-substrate/python-grammar.form. Routes
# through CPython's `ast` module — every AST node carries
# (lineno, col_offset, end_lineno, end_col_offset) natively, so
# source_attribution_shape is stamped from those fields directly
# (per lc-the-recipe-remembers-its-source).
#
# Round-trip uses ast.unparse (Python 3.9+); structural identity
# preserved across (parse → emit) modulo whitespace and comments
# (honest gap noted in python-grammar.form GAP-PY2).


def _py_source_attr(node, source_path: str) -> dict:
    return {
        "source_file":   source_path,
        "start_line":    getattr(node, "lineno", 0),
        "start_col":     getattr(node, "col_offset", 0) + 1,    # 1-indexed for parity with markdown
        "end_line":      getattr(node, "end_lineno", getattr(node, "lineno", 0)),
        "end_col":       getattr(node, "end_col_offset", getattr(node, "col_offset", 0)) + 1,
        "byte_start":    0,    # AST doesn't carry byte offsets; line:col is canonical
        "byte_end":      0,
        "language_cell": "python",
    }


def _py_node_to_form(node, source_path: str):
    """Recursively walk an ast node → Form object tree.

    Each Form node carries:
        category: the ast node class name (e.g. "Module", "FunctionDef")
        source_attribution: from node's lineno/col_offset
        <fields…>: the node's _fields, recursively converted
    """
    import ast

    if node is None:
        return None
    if isinstance(node, list):
        return [_py_node_to_form(item, source_path) for item in node]
    if isinstance(node, (str, int, float, bool, complex, bytes)) or node is None:
        return node
    if not isinstance(node, ast.AST):
        # Tuples, sets, etc. — pass through serialized
        return repr(node)

    out: dict = {"category": f"py_{type(node).__name__}"}
    if hasattr(node, "lineno"):
        out["source_attribution"] = _py_source_attr(node, source_path)
    for field_name in node._fields:
        value = getattr(node, field_name, None)
        out[field_name] = _py_node_to_form(value, source_path)
    # `ctx` is an ast.expr_context subclass; serialize as a slug.
    if "ctx" in node._fields and isinstance(getattr(node, "ctx", None), ast.AST):
        out["ctx"] = type(node.ctx).__name__.lower()
    return out


def _convert_in_python(input_path: Path) -> dict:
    import ast

    source = input_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(input_path), type_comments=True)
    except SyntaxError as e:
        _die(f"Python parse error in {input_path}: {e}")

    form_tree = _py_node_to_form(tree, str(input_path))
    # Promote the module-level docstring if present
    docstring = ast.get_docstring(tree)
    form_tree["docstring"] = docstring
    return {
        "source_tongue":   "python",
        "source_path":     str(input_path),
        "python_version":  f"{sys.version_info.major}.{sys.version_info.minor}",
        "tree":            form_tree,
    }


def _form_to_py_node(form, sentinel_loc=(1, 0)):
    """Reverse of _py_node_to_form: walk a Form object tree → ast nodes.

    Uses ast.fix_missing_locations to re-stamp line/col on synthetic
    nodes that lost their source_attribution sibling; idiomatic AST
    construction otherwise.
    """
    import ast

    if form is None:
        return None
    if isinstance(form, list):
        return [_form_to_py_node(item, sentinel_loc) for item in form]
    if isinstance(form, (str, int, float, bool, complex, bytes)) or form is None:
        return form
    if not isinstance(form, dict):
        return form
    cat = form.get("category", "")
    if not cat.startswith("py_"):
        return form

    cls_name = cat[3:]   # strip "py_"
    cls = getattr(ast, cls_name, None)
    if cls is None:
        _die(f"unknown Python AST node category: {cat}")

    kwargs: dict = {}
    for field_name in cls._fields:
        if field_name in form:
            kwargs[field_name] = _form_to_py_node(form[field_name], sentinel_loc)
    # ctx slug → ast.Load() / Store() / Del()
    if "ctx" in cls._fields and isinstance(kwargs.get("ctx"), str):
        ctx_name = kwargs["ctx"].capitalize()
        ctx_cls = getattr(ast, ctx_name, ast.Load)
        kwargs["ctx"] = ctx_cls()

    node = cls(**kwargs)
    attr = form.get("source_attribution")
    if attr:
        node.lineno = attr.get("start_line", 1)
        node.col_offset = max(attr.get("start_col", 1) - 1, 0)
        node.end_lineno = attr.get("end_line", node.lineno)
        node.end_col_offset = max(attr.get("end_col", 1) - 1, 0)
    return node


def _convert_out_python(form_object: dict) -> str:
    import ast

    tree = form_object.get("tree", form_object)
    if tree.get("category") != "py_Module":
        _die("python emit: top-level form is not a py_Module")
    py_tree = _form_to_py_node(tree)
    ast.fix_missing_locations(py_tree)
    try:
        return ast.unparse(py_tree)
    except AttributeError:
        _die("ast.unparse requires Python 3.9+")


def cmd_convert(args: argparse.Namespace) -> int:
    if args.direction == "in":
        if args.tongue == "json":
            form_obj = _convert_in_json(Path(args.input))
            print(json.dumps(form_obj, indent=2))
            return 0
        if args.tongue in ("md", "markdown"):
            form_obj = _convert_in_markdown(Path(args.input))
            print(json.dumps(form_obj, indent=2))
            return 0
        if args.tongue in ("py", "python"):
            form_obj = _convert_in_python(Path(args.input))
            print(json.dumps(form_obj, indent=2))
            return 0
        _die(
            f"tongue '{args.tongue}' not yet wired for `convert in`. "
            f"Available: json, markdown, python. (Other Language cells "
            f"are named in docs/coherence-substrate/*-grammar.form; wiring follows.)"
        )
    if args.direction == "out":
        with Path(args.input).open(encoding="utf-8") as f:
            form_obj = json.load(f)
        if args.tongue == "json":
            print(_convert_out_json(form_obj))
            return 0
        if args.tongue in ("md", "markdown"):
            print(_convert_out_markdown(form_obj))
            return 0
        if args.tongue in ("py", "python"):
            print(_convert_out_python(form_obj))
            return 0
        _die(f"tongue '{args.tongue}' not yet wired for `convert out`.")
    _die(f"unknown convert direction: {args.direction}")


# ─── subcommand: generate ────────────────────────────────────────────────
#
# Extract `defn name(args) = body;` definitions from a .form file and
# bundle into a .recipelib JSON. The Form source for each recipe is the
# verbatim text between defn and the matching closing brace/semicolon;
# Python/TS views are deferred to the auto-generator follow-up
# (per lc-recipes-as-binary-library "named follow-ups").


_DEFN_RE = re.compile(
    r"^defn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*=\s*",
    re.MULTILINE,
)


def _balanced_block(source: str, start: int) -> int:
    """Return the index just past the matching closing brace for the
    `do { … };` block beginning at `start`, OR past the next `;`
    terminator for a one-line defn. Honest about both shapes.
    """
    n = len(source)
    i = start
    # Skip whitespace
    while i < n and source[i] in " \t\n":
        i += 1
    # Block form?
    if i < n and source[i:i+3] == "do ":
        # Find the opening `{`
        while i < n and source[i] != "{":
            i += 1
        if i >= n:
            return n
        depth = 0
        while i < n:
            c = source[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    # Eat trailing `;`
                    while i < n and source[i] in " \t":
                        i += 1
                    if i < n and source[i] == ";":
                        i += 1
                    return i
            i += 1
        return n
    # One-line form: terminator is `;` not inside parens/brackets.
    paren = brack = 0
    while i < n:
        c = source[i]
        if c == "(":
            paren += 1
        elif c == ")":
            paren -= 1
        elif c == "[":
            brack += 1
        elif c == "]":
            brack -= 1
        elif c == ";" and paren == 0 and brack == 0:
            return i + 1
        i += 1
    return n


def _extract_form_defns(source: str) -> list[dict]:
    recipes = []
    for m in _DEFN_RE.finditer(source):
        name = m.group(1)
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        body_start = m.start()
        body_end = _balanced_block(source, m.end())
        body = source[body_start:body_end]
        recipes.append({
            "name": name,
            "params": params,
            "form_source": body,
        })
    return recipes


def cmd_generate(args: argparse.Namespace) -> int:
    src_path = Path(args.source)
    if not src_path.exists():
        _die(f"source file not found: {args.source}")
    text = src_path.read_text(encoding="utf-8")
    extracted = _extract_form_defns(text)
    if not extracted:
        _die(f"no `defn name(...) = …;` found in {args.source}")

    library_name = args.name or src_path.stem
    out_path = Path(args.out) if args.out else (
        DEFAULT_LIBRARY_DIR / f"{library_name}.recipelib.json"
    )

    library = {
        "library_meta": {
            "name": library_name,
            "version": "0.1.0-generated",
            "generated_at": "auto",
            "generator_tongue": "form-cli generate",
            "package_hint": 1,
            "summary": f"Auto-extracted from {src_path}",
        },
        "dependencies": [],
        "language_cells": ["form"],
        "recipes": [
            {
                "name": r["name"],
                "node_id_hint": f"1.3.{r['name']}.auto",
                "blueprint": {
                    "category": "B_Function",
                    "input_types": [f"~{p}" for p in r["params"]],
                    "output_type": "~Form",
                },
                "tree": {
                    "category": "R_Block.DO",
                    "comment": "tree extraction deferred to auto-generator follow-up",
                },
                "source_provenance": {
                    "tongue": "form",
                    "source_path": str(src_path),
                },
                "tongue_caches": {
                    "form": r["form_source"],
                },
            }
            for r in extracted
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(library, f, indent=2)
    print(f"generated: {out_path}")
    print(f"  recipes: {len(extracted)} ({', '.join(r['name'] for r in extracted)})")
    return 0


# ─── argparser ───────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="form_cli",
        description=__doc__.splitlines()[0],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="print library meta + recipes")
    p_list.add_argument("library", help="library name or path")
    p_list.set_defaults(func=cmd_list)

    p_exec = sub.add_parser("execute", help="invoke a recipe by name")
    p_exec.add_argument("library", help="library name or path")
    p_exec.add_argument("recipe", help="recipe name")
    p_exec.add_argument("args", nargs="*", help="JSON-encoded positional args")
    p_exec.add_argument("--pretty", action="store_true", help="indent JSON output")
    p_exec.set_defaults(func=cmd_execute)

    p_conv = sub.add_parser("convert", help="I/O ↔ Form object via Language cell")
    p_conv.add_argument("direction", choices=["in", "out"])
    p_conv.add_argument("input", help="path to input file (or /dev/stdin)")
    p_conv.add_argument("--tongue", default="json",
                        help="Language cell name (default: json)")
    p_conv.set_defaults(func=cmd_convert)

    p_gen = sub.add_parser("generate", help="extract recipes from .form into .recipelib")
    p_gen.add_argument("source", help="path to a .form source file")
    p_gen.add_argument("--name", help="library name (default: source stem)")
    p_gen.add_argument("--out", help="output .recipelib path")
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
