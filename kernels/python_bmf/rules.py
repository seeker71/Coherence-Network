"""Python BMF rule registry — readable expression of python-bmf.fk's rule book.

Source-of-truth lives at form/form-stdlib/emits/python-native-templates/rules.py
(this file). The Form emitter materializes it to kernels/python_bmf/rules.py.

The Form-resident grammar defines BMF rules as ::= pattern + forward
action + reverse action. This module expresses the same rules as Python
Rule dataclasses in a list, with forward and reverse actions as plain
Python functions.

Phase 0 ships a first slice of rules (pass, break, continue, import,
return, assign, int, string, ident). Coverage expands as Phases 2-3 land.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .objects import BmfAtom, BmfStatementTree, PyBmfCategory
from .sdk import NodeID, intern, intern_trivial_int, intern_trivial_string


@dataclass
class Match:
    kind: str  # "literal" | "capture"
    expected_kind: str = ""
    literal: str = ""
    name: str = ""


def lit(value):
    return Match(kind="literal", literal=value)


def cap(name, expected_kind):
    return Match(kind="capture", name=name, expected_kind=expected_kind)


def _atom_satisfies(atom, m):
    if m.kind == "literal":
        return atom.value == m.literal
    expected = m.expected_kind
    if expected == "name":
        return atom.kind == "py-name"
    if expected == "int":
        return atom.kind == "py-int"
    if expected == "float":
        return atom.kind == "py-float"
    if expected == "string":
        return atom.kind == "py-string"
    if expected == "bytes":
        return atom.kind == "py-bytes"
    if expected == "fstring":
        return atom.kind == "py-fstring"
    if expected == "keyword":
        return atom.kind == "py-keyword"
    if expected == "op":
        return atom.kind == "py-op"
    return False


def match_pattern(pattern, tokens):
    if len(tokens) < len(pattern):
        return None
    caps = {}
    for m, atom in zip(pattern, tokens[: len(pattern)]):
        if not _atom_satisfies(atom, m):
            return None
        if m.kind == "capture" and m.name:
            caps[m.name] = atom
    return caps


@dataclass
class Rule:
    name: str
    pattern: list
    category: PyBmfCategory
    forward: Callable
    reverse: Callable | None = None
    description: str = ""

    def try_apply(self, tokens):
        caps = match_pattern(self.pattern, tokens)
        if caps is None:
            return None
        return self.forward(caps, tokens)


def _emit_ident(caps, tokens):
    name = caps.get("value", tokens[0]).value
    return intern(
        "ident",
        {"category": int(PyBmfCategory.IDENT), "name": name},
        children=[intern_trivial_string(name)],
    )


def _emit_int(caps, tokens):
    value = caps.get("value", tokens[0]).value
    return intern(
        "int",
        {"category": int(PyBmfCategory.INT), "literal": value},
        children=[intern_trivial_int(int(value.replace("_", "")))],
    )


def _emit_string(caps, tokens):
    value = caps.get("value", tokens[0]).value
    return intern(
        "string",
        {"category": int(PyBmfCategory.STRING), "literal": value},
        children=[intern_trivial_string(value)],
    )


def _emit_pass(caps, tokens):
    return intern("pass", {"category": int(PyBmfCategory.PASS)}, children=[])


def _emit_break(caps, tokens):
    return intern("break", {"category": int(PyBmfCategory.BREAK)}, children=[])


def _emit_continue(caps, tokens):
    return intern("continue", {"category": int(PyBmfCategory.CONTINUE)}, children=[])


def _emit_import(caps, tokens):
    module = caps.get("module")
    name = module.value if module else ""
    return intern(
        "import",
        {"category": int(PyBmfCategory.IMPORT), "module": name},
        children=[intern_trivial_string(name)],
    )


def _emit_return_value(caps, tokens):
    val = caps.get("value")
    val_text = val.value if val else ""
    return intern(
        "return",
        {"category": int(PyBmfCategory.RETURN), "value": val_text},
        children=[intern_trivial_string(val_text)],
    )


def _emit_return_bare(caps, tokens):
    return intern("return", {"category": int(PyBmfCategory.RETURN), "value": None}, children=[])


def _emit_assign_simple(caps, tokens):
    target = caps.get("target")
    value = caps.get("value")
    return intern(
        "assign",
        {
            "category": int(PyBmfCategory.ASSIGN),
            "target": target.value if target else "",
            "value": value.value if value else "",
        },
        children=[
            intern_trivial_string(target.value if target else ""),
            intern_trivial_string(value.value if value else ""),
        ],
    )


python_bmf_rules = [
    Rule("pass", [lit("pass")], PyBmfCategory.PASS, _emit_pass, description="pass"),
    Rule("break", [lit("break")], PyBmfCategory.BREAK, _emit_break, description="break"),
    Rule("continue", [lit("continue")], PyBmfCategory.CONTINUE, _emit_continue, description="continue"),
    Rule("import-simple", [lit("import"), cap("module", "name")], PyBmfCategory.IMPORT, _emit_import, description="import <module>"),
    Rule("return-value-name", [lit("return"), cap("value", "name")], PyBmfCategory.RETURN, _emit_return_value, description="return <name>"),
    Rule("return-value-int", [lit("return"), cap("value", "int")], PyBmfCategory.RETURN, _emit_return_value, description="return <int>"),
    Rule("return-bare", [lit("return")], PyBmfCategory.RETURN, _emit_return_bare, description="return"),
    Rule("assign-simple-int", [cap("target", "name"), lit("="), cap("value", "int")], PyBmfCategory.ASSIGN, _emit_assign_simple, description="<name> = <int>"),
    Rule("assign-simple-name", [cap("target", "name"), lit("="), cap("value", "name")], PyBmfCategory.ASSIGN, _emit_assign_simple, description="<name> = <name>"),
    Rule("int", [cap("value", "int")], PyBmfCategory.INT, _emit_int, description="<int>"),
    Rule("string", [cap("value", "string")], PyBmfCategory.STRING, _emit_string, description="<string>"),
    Rule("ident", [cap("value", "name")], PyBmfCategory.IDENT, _emit_ident, description="<name>"),
]


def find_rule(name):
    for r in python_bmf_rules:
        if r.name == name:
            return r
    return None


def apply_rule(name, tokens):
    rule = find_rule(name)
    if rule is None:
        return None
    return rule.try_apply(tokens)


def apply_any_rule(tokens):
    """Walk rules longest-first; return first that matches its full pattern."""
    candidates = sorted(python_bmf_rules, key=lambda r: -len(r.pattern))
    for rule in candidates:
        nid = rule.try_apply(tokens)
        if nid is not None:
            return rule, nid
    return None


def compile_statement(tree):
    """Translate a parsed statement-tree into a Recipe NodeID.

    Span is included in the interned content so two occurrences of an
    otherwise-identical statement at different source positions stay
    distinct. Without this, content-addressing collapses them and the
    decompiler renders one body where the other belongs.
    """
    span = tree.span
    occurrence = [span.start_line, span.start_col, span.end_line, span.end_col]
    hit = apply_any_rule(tree.tokens)
    if hit is not None:
        _rule, nid = hit
        # Re-intern with span so occurrences stay distinct even when the
        # rule's forward action interned by content alone.
        return intern(
            "statement-occurrence",
            {
                "cpython_rule": tree.cpython_rule,
                "head": str(nid),
                "tokens": [(t.kind, t.value) for t in tree.tokens],
                "span": occurrence,
            },
            children=[nid],
        )
    return intern(
        "statement",
        {
            "cpython_rule": tree.cpython_rule,
            "tokens": [(t.kind, t.value) for t in tree.tokens],
            "span": occurrence,
        },
        children=[],
    )


__all__ = [
    "Match",
    "lit",
    "cap",
    "Rule",
    "match_pattern",
    "python_bmf_rules",
    "find_rule",
    "apply_rule",
    "apply_any_rule",
    "compile_statement",
]
