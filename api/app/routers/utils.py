"""Utility endpoints whose bodies live as Form recipes, not Python functions.

The first transmutation gesture toward the question Urs named:
"can we replace FastAPI with native Form kernel?" Each endpoint here
carries the same shape across three runtimes — CPython, TS evalPython,
form-kernel-rust — and at request-time prefers the native kernel.

FastAPI stays as the HTTP doorway. The body of the endpoint IS a
Recipe: same input → same output across runtimes, guarded by
form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.form_kernel_bridge import (
    kernel_available,
    kernel_bin_path,
    run_with_fallback,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/utils", tags=["utils"])


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/coherence_weight
#
# Pure computation: given a list of integer values and a threshold,
# compute a weighted coherence score. Above-threshold values contribute
# with position-based decay (100×, 50×, 25×, then 10×) and add a 100×
# bonus per above-threshold count.
#
# This Python function is the *fallback*; the *primary* runtime is the
# Form recipe compiled from
# form/form-kernel-ts/seedbank/python-adapter/examples/
# endpoint_coherence_weight_demo.py. The parity_suite guarantees they
# return the same integer for the same inputs.
# ---------------------------------------------------------------------------


def _weighted_score_py(value: int, position: int) -> int:
    if position == 0:
        return value * 100
    if position == 1:
        return value * 50
    if position == 2:
        return value * 25
    return value * 10


def _coherence_score_py(values: list[int], threshold: int) -> int:
    total = 0
    position = 0
    for v in values:
        if v >= threshold:
            total = total + _weighted_score_py(v, position)
            position = position + 1
    return total


def _count_above_py(values: list[int], threshold: int) -> int:
    return sum(1 for v in values if v >= threshold)


def coherence_weight_py(values: list[int], threshold: int) -> int:
    """Python fallback — semantically identical to the Form recipe."""
    above = _count_above_py(values, threshold)
    coherence = _coherence_score_py(values, threshold)
    return above * 100 + coherence


def _coherence_weight_fk_source(values: list[int], threshold: int) -> str:
    """Build the .fk recipe for these inputs.

    Same shape as endpoint_coherence_weight_demo.fk — only the input
    literals change. The recipe body itself is fixed, and the parity_suite
    proves its semantics against CPython on the canonical inputs.
    """
    values_lit = "(list " + " ".join(str(v) for v in values) + ")"
    threshold_lit = str(threshold)
    return (
        "(do "
        "(defn weighted_score (value position) "
        "(if (eq position 0) (mul value 100) "
        "(if (eq position 1) (mul value 50) "
        "(if (eq position 2) (mul value 25) (mul value 10))))) "
        "(defn coherence_score (values threshold) "
        "(do (let total 0) (do (let position 0) (do (do "
        "(defn _for_0 (_remaining total position) "
        "(if (eq (len _remaining) 0) (list total position) "
        "(do (let v (head _remaining)) "
        "(if (ge v threshold) "
        "(do (let total (_plus total (weighted_score v position))) "
        "(let position (_plus position 1))) false) "
        "(_for_0 (tail _remaining) total position)))) "
        "(let _for_1_result (_for_0 values total position)) "
        "(let total (nth _for_1_result 0)) "
        "(let position (nth _for_1_result 1))) total)))) "
        "(defn count_above (values threshold) "
        "(do (let n 0) (do (do "
        "(defn _for_1 (_remaining n) "
        "(if (eq (len _remaining) 0) n "
        "(do (let v (head _remaining)) "
        "(if (ge v threshold) (let n (_plus n 1)) false) "
        "(_for_1 (tail _remaining) n)))) "
        "(let n (_for_1 values n))) n))) "
        "(defn coherence_weight (values threshold) "
        "(do (let above (count_above values threshold)) "
        "(do (let coherence (coherence_score values threshold)) "
        "(_plus (mul above 100) coherence)))) "
        f"(let values {values_lit}) "
        f"(let threshold {threshold_lit}) "
        "(coherence_weight values threshold))"
    )


class CoherenceWeightResponse(BaseModel):
    """GET /api/utils/coherence_weight response."""

    model_config = ConfigDict(extra="forbid")
    weight: Annotated[int, Field(description="Computed weighted coherence score")]
    values: Annotated[list[int], Field(description="Input values, echoed back")]
    threshold: Annotated[int, Field(description="Input threshold, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'form-kernel-rust' or 'python-fallback'"),
    ]


def _parse_values(values: str) -> list[int]:
    """Parse the comma-separated query param into a list of ints."""
    if not values.strip():
        return []
    out: list[int] = []
    for part in values.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"invalid integer in values: {part!r}",
            ) from e
    return out


@router.get(
    "/coherence_weight",
    response_model=CoherenceWeightResponse,
    summary="Compute weighted coherence score (body runs as Form recipe)",
    description=(
        "First transmutation gesture: the body of this endpoint is a Form "
        "recipe compiled from "
        "form/form-kernel-ts/seedbank/python-adapter/examples/"
        "endpoint_coherence_weight_demo.py. When form-kernel-rust is "
        "available the request shells into the native binary; otherwise "
        "the semantically-identical Python fallback runs. Three-way "
        "parity (CPython, TS, Rust) is the regression gate."
    ),
)
async def coherence_weight(
    values: Annotated[
        str,
        Query(description="Comma-separated integers — e.g. '72,38,91,55,28'"),
    ] = "72,38,91,55,28,67,84,45,95,12",
    threshold: Annotated[int, Query(description="Cutoff — only values >= this contribute")] = 50,
) -> CoherenceWeightResponse:
    parsed = _parse_values(values)
    fk_source = _coherence_weight_fk_source(parsed, threshold)
    weight, runtime = run_with_fallback(
        fk_source,
        fallback=lambda: coherence_weight_py(parsed, threshold),
        parse=int,
    )
    return CoherenceWeightResponse(
        weight=weight,
        values=parsed,
        threshold=threshold,
        runtime=runtime,
    )


@router.get(
    "/kernel_status",
    summary="Visibility into whether the Form kernel binary is available",
    description=(
        "Reports whether form-kernel-rust is on disk and executable in this "
        "container. When true, transmuted endpoints (coherence_weight, ...) "
        "shell into the kernel; when false, they fall back to Python."
    ),
)
async def kernel_status() -> dict[str, object]:
    return {
        "available": kernel_available(),
        "binary_path": str(kernel_bin_path()),
    }
