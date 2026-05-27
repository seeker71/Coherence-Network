"""Utility endpoints whose bodies live as Form recipes, not Python functions.

Transmutation as a habit toward the question Urs named: "can we replace
FastAPI with native Form kernel?" Each endpoint here carries the same
shape across three runtimes — CPython, TS evalPython, form-kernel-rust
— and at request-time prefers the native kernel.

FastAPI stays as the HTTP doorway. The body of the endpoint IS a
Recipe: same input → same output across runtimes, guarded by
form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh.

The repeating gesture (every endpoint here uses it):
  1. Land a `.py` demo + compiled `.fk` under seedbank/python-adapter/examples/
  2. Add the demo path to PARITY_FILES in parity_suite.sh
  3. Call `serve_via_kernel(<fk>, bindings={...}, fallback=lambda: ...)`

That's it. ~5 lines of route code; the body lives in the recipe file.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.form_kernel_bridge import (
    kernel_available,
    kernel_bin_path,
    serve_via_kernel,
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
    weight, runtime = serve_via_kernel(
        "endpoint_coherence_weight_demo.fk",
        bindings={"values": parsed, "threshold": threshold},
        fallback=lambda: coherence_weight_py(parsed, threshold),
        parse=int,
    )
    return CoherenceWeightResponse(
        weight=weight,
        values=parsed,
        threshold=threshold,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/nodeid_distance
#
# Pure computation: Manhattan distance between two NodeIDs in the lattice.
# The substrate locates every cell at NodeID(package, level, type, instance);
# distance over those four coordinates is the cheapest structural-proximity
# signal — useful for "what's near this cell?" without a graph traversal.
# ---------------------------------------------------------------------------


def nodeid_distance_py(
    a_pkg: int, a_lvl: int, a_type: int, a_inst: int,
    b_pkg: int, b_lvl: int, b_type: int, b_inst: int,
) -> int:
    """Python fallback — semantically identical to the Form recipe."""
    return (
        abs(a_pkg - b_pkg)
        + abs(a_lvl - b_lvl)
        + abs(a_type - b_type)
        + abs(a_inst - b_inst)
    )


class NodeIdDistanceResponse(BaseModel):
    """GET /api/utils/nodeid_distance response."""

    model_config = ConfigDict(extra="forbid")
    distance: Annotated[int, Field(description="Manhattan distance between the two NodeIDs")]
    a: Annotated[list[int], Field(description="NodeID a as [package, level, type, instance]")]
    b: Annotated[list[int], Field(description="NodeID b as [package, level, type, instance]")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'form-kernel-rust' or 'python-fallback'"),
    ]


@router.get(
    "/nodeid_distance",
    response_model=NodeIdDistanceResponse,
    summary="Manhattan distance between two substrate NodeIDs (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns sum of absolute differences across the four NodeID "
        "coordinates (package, level, type, instance). Same shape as "
        "coherence_weight — kernel-or-fallback served by serve_via_kernel."
    ),
)
async def nodeid_distance(
    a_pkg: Annotated[int, Query(description="NodeID a — package")] = 1,
    a_lvl: Annotated[int, Query(description="NodeID a — level")] = 5,
    a_type: Annotated[int, Query(description="NodeID a — type_")] = 4,
    a_inst: Annotated[int, Query(description="NodeID a — instance")] = 1,
    b_pkg: Annotated[int, Query(description="NodeID b — package")] = 1,
    b_lvl: Annotated[int, Query(description="NodeID b — level")] = 4,
    b_type: Annotated[int, Query(description="NodeID b — type_")] = 4,
    b_inst: Annotated[int, Query(description="NodeID b — instance")] = 7,
) -> NodeIdDistanceResponse:
    distance, runtime = serve_via_kernel(
        "endpoint_nodeid_distance_demo.fk",
        bindings={
            "a_pkg": a_pkg, "a_lvl": a_lvl, "a_type": a_type, "a_inst": a_inst,
            "b_pkg": b_pkg, "b_lvl": b_lvl, "b_type": b_type, "b_inst": b_inst,
        },
        fallback=lambda: nodeid_distance_py(
            a_pkg, a_lvl, a_type, a_inst, b_pkg, b_lvl, b_type, b_inst,
        ),
        parse=int,
    )
    return NodeIdDistanceResponse(
        distance=distance,
        a=[a_pkg, a_lvl, a_type, a_inst],
        b=[b_pkg, b_lvl, b_type, b_inst],
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/weighted_average
#
# Pure computation: weighted average of a list of float scores against a
# list of float weights. The substrate's bread-and-butter combinator —
# every multi-signal coherence aggregation goes through this shape.
# ---------------------------------------------------------------------------


def weighted_average_py(values: list[float], weights: list[float]) -> float:
    """Python fallback — semantically identical to the Form recipe."""
    numerator = sum(v * w for v, w in zip(values, weights))
    denominator = sum(weights)
    return numerator / denominator


class WeightedAverageResponse(BaseModel):
    """GET /api/utils/weighted_average response."""

    model_config = ConfigDict(extra="forbid")
    average: Annotated[float, Field(description="Weighted mean = sum(v*w) / sum(w)")]
    values: Annotated[list[float], Field(description="Input scores, echoed back")]
    weights: Annotated[list[float], Field(description="Input weights, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'form-kernel-rust' or 'python-fallback'"),
    ]


def _parse_floats(raw: str, label: str) -> list[float]:
    """Parse a comma-separated string of floats; HTTPException on bad input."""
    if not raw.strip():
        return []
    out: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"invalid float in {label}: {part!r}",
            ) from e
    return out


@router.get(
    "/weighted_average",
    response_model=WeightedAverageResponse,
    summary="Weighted average of float scores (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns sum(values[i] * weights[i]) / sum(weights). The substrate's "
        "bread-and-butter coherence-score combinator. Kernel-or-fallback served "
        "by serve_via_kernel; three-way parity (CPython, TS, Rust) is the gate."
    ),
)
async def weighted_average(
    values: Annotated[
        str,
        Query(description="Comma-separated floats — e.g. '0.5,0.75,1.0'"),
    ] = "0.5,0.75,1.0",
    weights: Annotated[
        str,
        Query(description="Comma-separated floats — same length as values"),
    ] = "0.25,0.25,0.5",
) -> WeightedAverageResponse:
    parsed_v = _parse_floats(values, "values")
    parsed_w = _parse_floats(weights, "weights")
    if len(parsed_v) != len(parsed_w):
        raise HTTPException(
            status_code=400,
            detail=f"values ({len(parsed_v)}) and weights ({len(parsed_w)}) must have the same length",
        )
    if not parsed_w or sum(parsed_w) == 0.0:
        raise HTTPException(status_code=400, detail="weights must be non-empty with non-zero sum")
    avg, runtime = serve_via_kernel(
        "endpoint_weighted_average_demo.fk",
        bindings={"values": parsed_v, "weights": parsed_w},
        fallback=lambda: weighted_average_py(parsed_v, parsed_w),
        parse=float,
    )
    return WeightedAverageResponse(
        average=avg,
        values=parsed_v,
        weights=parsed_w,
        runtime=runtime,
    )


@router.get(
    "/kernel_status",
    summary="Visibility into whether the Form kernel binary is available",
    description=(
        "Reports whether form-kernel-rust is on disk and executable in this "
        "container. When true, transmuted endpoints (coherence_weight, "
        "nodeid_distance, weighted_average) shell into the kernel; when "
        "false, they fall back to Python."
    ),
)
async def kernel_status() -> dict[str, object]:
    return {
        "available": kernel_available(),
        "binary_path": str(kernel_bin_path()),
    }
