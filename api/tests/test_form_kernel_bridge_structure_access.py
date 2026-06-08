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
    _as_field_dict,
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


class TestModelToRecordNormalization:
    """A model / object normalizes to a record at the marshal boundary.

    The object-OR-dict polymorphism the blocked functions carry
    (``_safe_float(obj, f)`` reads ``obj.f`` from a model OR ``obj[f]`` from a
    dict) is DISSOLVED here: every structured value normalizes to a dict before
    it marshals to a Record, so the recipe only ever sees Records.
    """

    def test_pydantic_model_normalizes_to_field_dict(self):
        from pydantic import BaseModel

        class Spec(BaseModel):
            event_count: int
            actual_value: float

        d = _as_field_dict(Spec(event_count=3, actual_value=1.5))
        assert d == {"event_count": 3, "actual_value": 1.5}

    def test_plain_object_normalizes_to_field_dict(self):
        class Plain:
            def __init__(self, ec: int, av: float) -> None:
                self.event_count = ec
                self.actual_value = av

        d = _as_field_dict(Plain(7, 2.0))
        assert d == {"event_count": 7, "actual_value": 2.0}

    def test_scalar_has_no_field_view(self):
        assert _as_field_dict(5) is None
        assert _as_field_dict("text") is None
        assert _as_field_dict([1, 2]) is None

    def test_model_renders_as_record_new(self):
        from pydantic import BaseModel

        class Spec(BaseModel):
            event_count: int
            actual_value: float

        lit = _fk_literal(Spec(event_count=3, actual_value=1.5))
        assert lit.startswith("(record_new (make_nodeid 1 5 4 1) ")
        assert '"event_count" 3' in lit
        assert '"actual_value" 1.5' in lit


class TestListOfRecordMarshalling:
    """A list[dict|model] marshals to a kernel list-of-records.

    The bridge's recursive marshal: scalar→value, dict/model→record, list→list
    of marshalled. A reduction recipe folds over the resulting list-of-records;
    this is gate #1 ("list-of-record reduction") in API_KERNEL_READINESS.
    """

    def test_list_of_dicts_renders_as_list_of_records(self):
        specs = [
            {"event_count": 3, "actual_value": 1.5},
            {"event_count": 0, "actual_value": 0.0},
        ]
        lit = _fk_literal(specs)
        assert lit.startswith("(list (record_new ")
        assert lit.count("record_new") == 2
        assert '"event_count" 3' in lit
        assert '"event_count" 0' in lit

    def test_list_of_models_marshals_identically_to_dicts(self):
        from pydantic import BaseModel

        class Spec(BaseModel):
            event_count: int
            actual_value: float

        specs_dicts = [{"event_count": 3, "actual_value": 1.5}]
        specs_models = [Spec(event_count=3, actual_value=1.5)]
        assert _fk_literal(specs_models) == _fk_literal(specs_dicts)

    def test_empty_list_renders_as_empty_list_literal(self):
        assert _fk_literal([]) == "(list)"


def _grounding_summary_py(specs: list[dict]) -> list[int]:
    """The four integer grounding signals — value-identical to the recipe."""
    spec_count = len(specs)
    total_event_count = sum(int(s.get("event_count", 0) or 0) for s in specs)
    specs_with_value_count = sum(
        1 for s in specs if (s.get("actual_value", 0) or 0) > 0
    )
    max_event_count = 0
    for s in specs:
        ec = int(s.get("event_count", 0) or 0)
        if ec > max_event_count:
            max_event_count = ec
    return [spec_count, total_event_count, specs_with_value_count, max_event_count]


def _coerce_int_list(value: object) -> list[int]:
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value]
    s = str(value).strip().strip("[]() ")
    if not s:
        return []
    sep = "," if "," in s else None
    parts = s.split(sep) if sep else s.split()
    return [int(float(p.strip().rstrip(","))) for p in parts if p.strip().rstrip(",")]


class TestListOfRecordReductionEndToEnd:
    """A list[record] binding flows into a recipe that folds a field and returns a list."""

    @pytest.mark.skipif(
        not kernel_available() and not os.environ.get("FORM_KERNEL_RUST_BIN"),
        reason="form-kernel-rust binary not available; list-of-record reduction needs the kernel",
    )
    @pytest.mark.parametrize(
        "specs,expected",
        [
            ([], [0, 0, 0, 0]),
            ([{"event_count": 5, "actual_value": 3.0}], [1, 5, 1, 5]),
            (
                [
                    {"event_count": 3, "actual_value": 1.5},
                    {"event_count": 0, "actual_value": 0.0},
                    {"event_count": 7, "actual_value": 2.25},
                ],
                [3, 10, 2, 7],
            ),
            (
                [
                    {"event_count": 0, "actual_value": 0.0},
                    {"event_count": 0, "actual_value": 0.0},
                ],
                [2, 0, 0, 0],
            ),
        ],
    )
    def test_list_of_records_reduction_matches_python(self, specs, expected):
        """list[dict] -> list-of-records binding -> recipe folds fields -> list == python."""
        value, runtime = serve_via_kernel(
            "endpoint_idea_grounding_summary_demo.fk",
            bindings={"specs": specs},
            parse=_coerce_int_list,
        )
        assert runtime in ("inline", "subprocess")
        assert value == expected
        assert value == _grounding_summary_py(specs)

    @pytest.mark.skipif(
        not kernel_available() and not os.environ.get("FORM_KERNEL_RUST_BIN"),
        reason="form-kernel-rust binary not available; list-of-model reduction needs the kernel",
    )
    def test_list_of_models_reduction_matches_dicts(self):
        """A list of Pydantic models reduces to the same result as a list of dicts."""
        from pydantic import BaseModel

        class Spec(BaseModel):
            event_count: int
            actual_value: float

        models = [
            Spec(event_count=3, actual_value=1.5),
            Spec(event_count=7, actual_value=2.25),
        ]
        value, runtime = serve_via_kernel(
            "endpoint_idea_grounding_summary_demo.fk",
            bindings={"specs": models},
            parse=_coerce_int_list,
        )
        assert runtime in ("inline", "subprocess")
        assert value == [2, 10, 2, 7]


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
            parse=float,
        )
        assert runtime in ("inline", "subprocess")
        assert abs(value - _marginal_from_idea_py(idea)) < 1e-12
        assert value == 0.8

    def test_parity_reference_matches_expected_value(self):
        """The Python reference remains only a parity oracle for the recipe."""
        idea = {
            "potential_value": 10.0,
            "actual_value": 2.0,
            "confidence": 0.9,
            "estimated_cost": 6.0,
            "actual_cost": 1.0,
            "resistance_risk": 1.0,
        }
        assert _marginal_from_idea_py(idea) == round((8.0 * 0.81) / (5.0 + 0.5), 6)
