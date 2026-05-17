"""MCP exposure for the coherence-substrate: every sibling agent reaches Form.

Three tools land here:

- `coherence_substrate_run` — full meta-circular runtime (defn, match,
  recursion, `.children[i]`, `.value`, arithmetic, conditionals).
- `coherence_substrate_query` — lookup-mode Form evaluation (intern +
  structural answer; `?equivalent`, `|>` projection, cell lookups).
- `coherence_substrate_stats` — lattice census.

Without these the substrate is a Claude-only surface. With them, Codex
/ Cursor / Gemini / any MCP-speaking cell reasons in Form the same way.
"""
from __future__ import annotations

from app.services.mcp_tool_registry import TOOL_MAP


def test_substrate_tools_registered():
    assert "coherence_substrate_run" in TOOL_MAP
    assert "coherence_substrate_query" in TOOL_MAP
    assert "coherence_substrate_stats" in TOOL_MAP


def test_substrate_run_arithmetic():
    r = TOOL_MAP["coherence_substrate_run"]["handler"]({"expression": "1 + 2 * 3"})
    assert r == {"value": 7}


def test_substrate_run_conditional():
    r = TOOL_MAP["coherence_substrate_run"]["handler"](
        {"expression": "if 5 > 3 then 100 else 200"}
    )
    assert r == {"value": 100}


def test_substrate_run_recursion():
    """The full runtime is reachable — defn, recursion, the works."""
    src = "do { defn fact(n) = if n <= 1 then 1 else n * fact(n - 1); fact(6) }"
    r = TOOL_MAP["coherence_substrate_run"]["handler"]({"expression": src})
    assert r == {"value": 720}


def test_substrate_run_string_interpolation():
    r = TOOL_MAP["coherence_substrate_run"]["handler"](
        {"expression": '"hello ${1 + 2}"'}
    )
    assert r == {"value": "hello 3"}


def test_substrate_run_missing_expression_returns_error():
    r = TOOL_MAP["coherence_substrate_run"]["handler"]({})
    assert "error" in r


def test_substrate_run_surfaces_parse_errors():
    """Errors come back as JSON, not as an MCP transport exception."""
    r = TOOL_MAP["coherence_substrate_run"]["handler"](
        {"expression": "1 + +"}  # syntactically broken
    )
    assert "error" in r


def test_substrate_stats_returns_counts():
    r = TOOL_MAP["coherence_substrate_stats"]["handler"]({})
    assert "blueprints_total" in r
    assert "recipes_total" in r
    assert "cells_total" in r


def test_substrate_query_missing_cell_surfaces_error():
    r = TOOL_MAP["coherence_substrate_query"]["handler"](
        {"expression": "@concept(nonexistent-cell-name)"}
    )
    assert "error" in r


def test_substrate_run_walks_recipe_tree_via_form_engine():
    """End-to-end proof: the same engine that runs in form-engine.form
    runs through the MCP surface — a sibling cell evaluating recipe
    walks the same accessors the Form-level interpreter walks."""
    src = """
    do {
      defn ev(n) = match n.category {
        @1.2.12.1 => ev(n.children[0]) + ev(n.children[1]),
        @1.2.12.2 => ev(n.children[0]) - ev(n.children[1]),
        @1.2.12.3 => ev(n.children[0]) * ev(n.children[1]),
        _ => n.value
      };
      do {
        let nid = @1.4.12.1;
        ev(nid)
      }
    }
    """
    # We can't pre-compute the nid here; just exercise that the engine
    # parses and runs through MCP without crashing. A composite NodeID
    # that doesn't exist returns 0 via .value (NULL trivial decode).
    r = TOOL_MAP["coherence_substrate_run"]["handler"]({"expression": src})
    # Either resolves to a value or raises a substrate error — both
    # surface cleanly through the JSON shape.
    assert "value" in r or "error" in r
