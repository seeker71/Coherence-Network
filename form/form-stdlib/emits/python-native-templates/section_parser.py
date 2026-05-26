"""Section parser — readable expression of form-source-section-by-dialect.

A Form source file (.fk / .form) can carry multiple dialect sections.
compiler.fk defines form-source + form-source-section-by-dialect as
the dispatcher; this module is the direct Python expression of that
dispatcher, data-driven by a dialect registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .parser import parse_python
from .sdk import NodeID, intern, intern_trivial_string


@dataclass
class FormSection:
    dialect: str
    name: str
    body: str
    nodeid: NodeID | None = None


@dataclass
class FormSource:
    name: str
    sections: list = field(default_factory=list)


DialectHandler = Callable[[FormSection], NodeID]
_DIALECT_REGISTRY = {}


def register_dialect(name, handler):
    _DIALECT_REGISTRY[name] = handler


def get_dialect(name):
    return _DIALECT_REGISTRY.get(name)


def dispatch_dialect(section):
    handler = _DIALECT_REGISTRY.get(section.dialect)
    if handler is None:
        return intern(
            "unknown-section",
            {"dialect": section.dialect, "name": section.name, "body": section.body},
            children=[intern_trivial_string(section.dialect)],
        )
    return handler(section)


def _python_dialect(section):
    module = parse_python(section.body, path=section.name or "<inline-python>")
    return intern(
        "module",
        {
            "category": "py-module",
            "statement_count": len(module.statements),
            "source": section.name,
        },
        children=[],
    )


register_dialect("python", _python_dialect)


def _parse_sections(text):
    """Section headers look like `<dialect> <name> {`; bodies end at matching `}` at depth 0.

    Mirrors fsc-section-end-depth in source-compiler.fk.
    """
    sections = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith(";"):
            continue
        if not line.endswith("{"):
            continue
        header = line[:-1].strip()
        parts = header.split(None, 1)
        if not parts:
            continue
        dialect = parts[0]
        name = parts[1] if len(parts) > 1 else ""
        body_lines = []
        depth = 0
        while i < len(lines):
            cur = lines[i]
            stripped = cur.strip()
            if stripped.endswith("{"):
                depth += 1
            if stripped == "}":
                if depth == 0:
                    i += 1
                    break
                depth -= 1
            body_lines.append(cur)
            i += 1
        sections.append(FormSection(dialect=dialect, name=name, body="\n".join(body_lines)))
    return sections


def parse_form_source(text, name="<source>"):
    return FormSource(name=name, sections=_parse_sections(text))


__all__ = [
    "FormSection",
    "FormSource",
    "register_dialect",
    "get_dialect",
    "dispatch_dialect",
    "parse_form_source",
]
