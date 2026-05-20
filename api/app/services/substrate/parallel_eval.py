"""Parallel execution — run every Form expression through both kernels.

The substrate carries two execution paths for the same expression:

- **Python kernel** — `form_execute_text(session, expr)` walks the recipe
  through Python's evaluator (`form_runtime.py` + `form_eval.py`).

- **Form kernel** — the meta-circular evaluator written in Form itself,
  loaded from `docs/coherence-substrate/form-engine.form`. The Python
  kernel hosts it, but the dispatch logic lives in Form source code.

These two have been kept in agreement by `test_substrate_form_self_hosted.py`
and the conformance harness since PR #1730 ("two kernels keeping each
other honest"). What was missing: a way to *run* them in parallel from
production call sites and surface any divergence as a first-class
signal, not a buried test failure.

This module adds that:

    from app.services.substrate.parallel_eval import parallel_execute_text

    result = parallel_execute_text(session, "1 + 2 * 3")
    # ParallelResult(
    #     python_value=7,
    #     form_value=7,
    #     agreed=True,
    #     recipe_node_id=NodeID(...),
    #     python_ms=0.4,
    #     form_ms=2.1,
    # )

The parallel mode is the bridge between "Python kernel is canonical"
and "Form kernel is canonical." While both run, every operation is
double-checked, every divergence is observable. When the Form kernel
has demonstrated it agrees on a wide-enough corpus over time, the
Python kernel can be retired arm by arm.

This is what the body's *cross-validate form siblings* commit history
has been preparing — the conformance vectors verify behavior at test
time; this module makes the same verification available at runtime.

## Coverage today

The meta-circular engine (form-engine.form) covers the BASIC dispatch
layer end-to-end: arithmetic, comparison, logic, conditional, blocks
(via last-value), choice, trivial leaves. The wellness check confirms
*Form arms cover 15/15 Python dispatch branches*.

Expressions outside that coverage (function calls into runtime registries,
mutation, async question-effects, substrate writes) fall through to the
Python kernel only — `parallel_execute_text` will record `form_value=None`
and `agreed=None` (rather than False) for those, distinguishing
*no comparison yet* from *comparison failed*.

## Traceability

Each `ParallelResult` carries the Recipe NodeID the expression interned
to. Combined with `form_decompile.recipe_to_form`, this gives the
caller a substrate-canonical view of what was actually executed — not
the source text the caller wrote, but the lattice coordinate the
substrate received. That coordinate is the truth of *what part of the
recipe was being run* when affecting any downstream cell.

This is the runtime piece beneath the witness-trace teaching that
landed at [`lc-traces-teach-the-recipe`](../../../docs/vision-kb/concepts/lc-traces-teach-the-recipe.md)
(#1749) and [`traces-teach-the-recipe.form`](../../../docs/coherence-substrate/traces-teach-the-recipe.form).
That concept names a four-pole loop — cell / recipe / witness-trace /
substrate-aggregation — turning each firing into a substrate-level
trace tagged with (cell, recipe, sense-before, sense-after, moment).
Mean delta across all firings of one Blueprint is the strategy's
efficacy-signature.

This module gives the *recipe* dimension of that trace its canonical
identity: every parallel-executed expression has a `recipe_node_id`
that names exactly which sub-recipe ran. When the witness-trace
publication layer lands (the GAP in `traces-teach-the-recipe.form`),
the trace's `recipe` field can point at the NodeID this module surfaces.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.substrate import form_evaluate_text
from app.services.substrate.form_runtime import form_execute_text
from app.services.substrate.kernel import NodeID


_ENGINE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "docs" / "coherence-substrate" / "form-engine.form"
)
_ENGINE_CACHE: dict[str, str] = {}


def _load_engine() -> str:
    """Read the meta-circular evaluator from form-engine.form.

    The evaluator source is bracketed by `# >>> BEGIN engine` /
    `# >>> END engine` markers in `form-engine.form`. Cached after
    first read because the file rarely changes mid-process.
    """
    cached = _ENGINE_CACHE.get("src")
    if cached is not None:
        return cached
    if not _ENGINE_PATH.exists():
        raise RuntimeError(
            f"parallel_eval: form-engine.form not found at {_ENGINE_PATH}. "
            f"The meta-circular evaluator's source is required for "
            f"running the Form kernel alongside Python."
        )
    src = _ENGINE_PATH.read_text()
    m = re.search(r"# >>> BEGIN engine\n(.*?)\n# >>> END engine", src, re.DOTALL)
    if not m:
        raise RuntimeError(
            f"parallel_eval: BEGIN engine / END engine markers not found "
            f"in {_ENGINE_PATH}. The Form kernel evaluator's source needs "
            f"those markers to be extractable."
        )
    engine = m.group(1)
    _ENGINE_CACHE["src"] = engine
    return engine


@dataclass
class ParallelResult:
    """Outcome of running an expression through both kernels.

    Attributes:
        python_value: The value the Python kernel computed.
        form_value: The value the Form kernel computed. `None` if the
            expression's category isn't yet covered by form-engine.form's
            dispatch arms.
        agreed: True if both kernels produced equal values; False if they
            disagreed; None if the Form kernel didn't run (out of coverage).
        recipe_node_id: The Recipe NodeID the expression interned to.
            Substrate-canonical identity for the executed expression.
            `None` if the expression has no Recipe representation yet
            (e.g. `defn` and other runtime-only constructs).
        python_ms: Wall-clock time the Python kernel spent.
        form_ms: Wall-clock time the Form kernel spent.
        form_error: If the Form kernel raised, the exception class name.
        coverage_gap: Reason the comparison didn't happen, when agreed
            is None. One of: `None` (compared), "no_recipe_representation",
            "form_kernel_error", "engine_load_error".
    """

    python_value: Any
    form_value: Any
    agreed: Optional[bool]
    recipe_node_id: Optional[NodeID]
    python_ms: float
    form_ms: float
    form_error: Optional[str] = None
    coverage_gap: Optional[str] = None


def parallel_execute_text(session: Session, expr: str) -> ParallelResult:
    """Execute an expression through both the Python and Form kernels.

    The Python kernel is always run (and its value returned even if the
    Form kernel fails) so callers can use this as a drop-in for
    `form_execute_text` and never silently lose execution semantics. The
    Form kernel runs alongside and its outcome is surfaced for
    comparison.

    Example:
        with Session() as s:
            r = parallel_execute_text(s, "1 + 2 * 3")
            assert r.python_value == r.form_value == 7
            assert r.agreed is True
    """
    # Run the Python kernel first — it's the canonical path today and
    # we always want a value back even if the Form kernel is uncovered.
    t0 = time.perf_counter()
    python_value = form_execute_text(session, expr)
    python_ms = (time.perf_counter() - t0) * 1000.0

    # Try to intern the expression as a Recipe NodeID. Some runtime-only
    # constructs (defn, mutation, await) don't yet have Recipe
    # representations; that's a coverage gap distinct from the Form
    # kernel's dispatch coverage.
    recipe_nid: Optional[NodeID] = None
    coverage_gap: Optional[str] = None
    try:
        recipe_nid = form_evaluate_text(session, expr).value
    except Exception:
        coverage_gap = "no_recipe_representation"

    # Run the Form kernel — wrap to catch coverage gaps so the caller
    # learns "out of coverage" rather than "the world is broken."
    form_value: Any = None
    form_error: Optional[str] = None
    agreed: Optional[bool] = None
    t1 = time.perf_counter()
    if recipe_nid is not None:
        try:
            engine = _load_engine()
            # The pattern matches test_substrate_form_self_hosted._form_eval:
            # load the engine source, then evaluate `ev(@<nid>)` in scope.
            form_value = form_execute_text(
                session,
                f"do {{\n{engine}\n; ev(@{recipe_nid})\n}}",
            )
        except FileNotFoundError as exc:
            form_error = type(exc).__name__
            coverage_gap = "engine_load_error"
        except Exception as exc:
            form_error = type(exc).__name__
            coverage_gap = "form_kernel_error"
    form_ms = (time.perf_counter() - t1) * 1000.0

    if form_error is None and recipe_nid is not None:
        agreed = (python_value == form_value)

    return ParallelResult(
        python_value=python_value,
        form_value=form_value,
        agreed=agreed,
        recipe_node_id=recipe_nid,
        python_ms=python_ms,
        form_ms=form_ms,
        form_error=form_error,
        coverage_gap=coverage_gap,
    )
