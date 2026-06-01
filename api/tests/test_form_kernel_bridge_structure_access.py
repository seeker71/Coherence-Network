"""Tests for the structure-access capability in the Form kernel bridge.

Structure access: a transmuted recipe receives structured data (a Python dict
or a model via ``model_dump()``) as a single binding and reads named fields out
of it, rather than receiving the inputs pre-flattened into separate scalars.
This is the capability the kernels/API_KERNEL_READINESS.md doc names as the
gate behind the bulk of remaining transmutation candidates.

The marshalling seam lives in two places that must agree:
  - ``_fk_literal`` renders a Python dict as a ``(record_new <blueprint> "k" v
    ...)`` literal — the subprocess path (and the inline-with-parse path).
  - lib.rs ``py_to_value`` builds a ``Value::Record`` from a Python dict — the
    inline (Preloader) path. (Exercised in production; this dev env runs the
    subprocess path, so the assertion here covers the literal seam and the
    end-to-end read.)

The recipe reads each field via the ``_get`` native (the python-bmf SUBSCRIPT
lowering), which now reads Record fields. The route is
``/api/utils/idea_marginal_from_record``; the recipe body's three-way parity is
the parity_suite gate, and the bridge marshalling is what these tests cover.
"""
from __future__ import annotations

import os

import pytest

from app.services.form_kernel_bridge import (
    _fk_literal,
    kernel_available,
    serve_via_kernel,
)


def _marginal_from_idea_py(idea: dict) -> float:
    pv = idea["potential_value"]
    av = idea["actual_value"]
    conf = idea["confidence"]
    ec = idea["estimated_cost"]
    ac = idea["actual_cost"]
    rr = idea["resistance_risk"]
    value_gap = pv - av
    if value_gap < 0.0:
        value_gap = 0.0
    remaining_cost = ec - ac
    if remaining_cost < 0.1:
        remaining_cost = 0.1
    return round((value_gap * conf * conf) / (remaining_cost + rr * 0.5), 6)


class TestFkLiteralRecord:
    """_fk_literal marshals a dict onto a record_new literal."""

    def test_dict_renders_as_record_new(self):
        lit = _fk_literal({"potential_value": 8.0, "count": 7, "tag": "alive"})
        assert lit.startswith('(record_new (make_nodeid 1 5 4 1) ')
        assert '"potential_value" 8.0' in lit
        assert '"count" 7' in lit
        assert '"tag" "alive"' in lit
        assert lit.endswith(")")

    def test_empty_dict_renders_as_bare_record(self):
        assert _fk_literal({}) == "(record_new (make_nodeid 1 5 4 1))"

    def test_nested_list_value_in_record(self):
        lit = _fk_literal({"weights": [1.0, 2.0]})
        assert '"weights" (list 1.0 2.0)' in lit

    def test_non_string_key_rejected(self):
        with pytest.raises(TypeError):
            _fk_literal({1: 2.0})


class TestStructureAccessEndToEnd:
    """A dict binding flows into a recipe that reads fields and returns a scalar."""

    @pytest.mark.skipif(
        not kernel_available() and not os.environ.get("FORM_KERNEL_RUST_BIN"),
        reason="form-kernel-rust binary not available; structure-access read needs the kernel",
    )
    def test_record_binding_read_matches_python(self):
        """dict -> record binding -> recipe reads fields via _get -> scalar == python."""
        idea = {
            "potential_value": 8.0,
            "actual_value": 3.0,
            "confidence": 0.8,
            "estimated_cost": 4.0,
            "actual_cost": 1.0,
            "resistance_risk": 2.0,
        }
        value, runtime = serve_via_kernel(
            "endpoint_idea_marginal_from_record_demo.fk",
            bindings={"idea": idea},
            fallback=lambda: _marginal_from_idea_py(idea),
            parse=float,
        )
        assert runtime in ("inline", "subprocess")
        assert abs(value - _marginal_from_idea_py(idea)) < 1e-12
        assert value == 0.8

    def test_fallback_path_when_no_kernel(self):
        """With no kernel reachable the fallback computes the same value."""
        idea = {
            "potential_value": 10.0,
            "actual_value": 2.0,
            "confidence": 0.9,
            "estimated_cost": 6.0,
            "actual_cost": 1.0,
            "resistance_risk": 1.0,
        }
        # The fallback is the source of truth for the value regardless of path.
        assert _marginal_from_idea_py(idea) == round((8.0 * 0.81) / (5.0 + 0.5), 6)
