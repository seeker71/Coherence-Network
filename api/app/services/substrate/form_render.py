"""Render Form's grammar back to Form-source text.

`bootstrap_self_host(session)` already proves Form's keyword grammar IS
substrate-resident — each (pattern, template) pair lives as Recipe
NodeIDs in the lattice. This module closes the visible loop: it walks
those recipes and emits Form-flavored source text so a human (or another
agent) can read the body's own grammar in the body's own voice.

The notation produced here is a *target syntax* — what Form would look
like if the bootstrap parser could read its own grammar from text. It
uses primitives Form already speaks (`seq`, `lit`, `cap`, `opt`,
`build`, `ref`, `const`) in a Lisp-shaped composition. The renderer
emits this notation; the bootstrap parser does not yet consume it (that
is the BMF closure, named in form-language.md beyond Step 8).

Two entry points:

  render_pattern(pattern) -> str
  render_template(template) -> str
  render_keyword(name, pattern, template) -> str  # combined

  render_all_registered() -> str  # every keyword currently registered

Output is deterministic — two identical inputs render to identical text,
so the body's grammar can be diffed against itself across processes.
"""
from __future__ import annotations

from typing import Any

from app.services.substrate.form_builders import Build, CaptureRef, Const, MapBuild
from app.services.substrate.form_rules import (
    Capture,
    IdentCapture,
    Literal,
    Opt,
    RepeatedCapture,
    Sequence,
    list_registered_keywords,
    lookup_form_keyword,
)


# ---------------------------------------------------------------------------
# Pattern → Form text
# ---------------------------------------------------------------------------


def render_pattern(pattern: Any, indent: int = 0) -> str:
    """Render a pattern as Form-flavored source text."""
    pad = "    " * indent

    if isinstance(pattern, Literal):
        if pattern.value is None:
            return f'lit "{pattern.kind}"'
        return f'lit "{pattern.kind}" "{pattern.value}"'

    if isinstance(pattern, Capture):
        if pattern.kind == "expr":
            return f'cap "{pattern.name}"'
        return f'cap "{pattern.name}" :{pattern.kind}'

    if isinstance(pattern, IdentCapture):
        return f'ident-cap "{pattern.name}"'

    if isinstance(pattern, Sequence):
        if not pattern.parts:
            return "seq []"
        inner = ",\n".join(
            "    " * (indent + 1) + render_pattern(p, indent + 1)
            for p in pattern.parts
        )
        return f"seq [\n{inner},\n{pad}]"

    if isinstance(pattern, Opt):
        return f"opt {render_pattern(pattern.pattern, indent)}"

    if isinstance(pattern, RepeatedCapture):
        body = render_pattern(pattern.item_pattern, indent + 1)
        sep = (
            f"\n{pad}    sep: {render_pattern(pattern.separator, indent + 1)}"
            if pattern.separator is not None
            else ""
        )
        return f'repeat "{pattern.name}" {{\n{pad}    item: {body}{sep}\n{pad}}}'

    return f"<unrendered {type(pattern).__name__}>"


# ---------------------------------------------------------------------------
# Template → Form text
# ---------------------------------------------------------------------------


def render_template(template: Any, indent: int = 0) -> str:
    """Render a Build/CaptureRef/Const/MapBuild template as Form text."""
    pad = "    " * indent

    if isinstance(template, Const):
        v = template.value
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return f'"{v}"'
        return str(v)

    if isinstance(template, CaptureRef):
        if template.has_default:
            default_val = template.default
            if default_val is None:
                default_str = "null"
            elif isinstance(default_val, bool):
                default_str = "true" if default_val else "false"
            elif isinstance(default_val, str):
                default_str = f'"{default_val}"'
            else:
                default_str = render_template(default_val, indent)
            return f'ref "{template.name}" default {default_str}'
        return f'ref "{template.name}"'

    if isinstance(template, Build):
        if not template.kwargs:
            return f'build "{template.class_name}"'
        fields = ",\n".join(
            "    " * (indent + 1) + f"{key}: {render_template(value, indent + 1)}"
            for key, value in template.kwargs.items()
        )
        return f'build "{template.class_name}" {{\n{fields},\n{pad}}}'

    if isinstance(template, MapBuild):
        items = render_template(template.items, indent + 1)
        each = render_template(template.each, indent + 1)
        return f"map {{\n{pad}    items: {items},\n{pad}    each: {each},\n{pad}}}"

    # Literal Python value passed through
    if template is None:
        return "null"
    if isinstance(template, bool):
        return "true" if template else "false"
    if isinstance(template, (int, float)):
        return str(template)
    if isinstance(template, str):
        return f'"{template}"'

    return f"<unrendered {type(template).__name__}>"


# ---------------------------------------------------------------------------
# Keyword rule → Form text
# ---------------------------------------------------------------------------


def render_keyword(name: str, pattern: Any, template: Any) -> str:
    """Render a complete keyword rule as Form-source text."""
    p = render_pattern(pattern, indent=1)
    t = render_template(template, indent=1)
    return (
        f'keyword "{name}" {{\n'
        f"    pattern: {p}\n"
        f"    template: {t}\n"
        f"}}"
    )


def render_all_registered(templates: dict | None = None) -> str:
    """Render every currently-registered keyword rule as Form text.

    `templates` is an optional `{name: template}` dict — the registry
    stores patterns + compiled-builder callables, so callers that want
    template rendering pass the source-of-truth template map alongside.
    Without it, the template field renders as `<python-builder>`.

    The output reads as the body's own grammar in the body's own voice —
    self-expressing at the keyword layer made visible.
    """
    templates = templates or {}
    parts = []
    for name in sorted(list_registered_keywords()):
        entry = lookup_form_keyword(name)
        if entry is None:
            continue
        pattern, _builder = entry
        template = templates.get(name, "<python-builder>")
        parts.append(render_keyword(name, pattern, template))
    return "\n\n".join(parts)
