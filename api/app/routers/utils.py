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
    active_runtime,
    inline_available,
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
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
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
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
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
# Endpoint: /api/utils/nodeid_compatibility
#
# Pure computation: graded structural compatibility between two NodeIDs, 0..4
# by how many of the four coordinates (package, level, type, instance) match.
# Sibling of nodeid_distance — that measures L1 distance, this measures
# coordinate agreement. It is the kernel of the substrate's view-through-
# blueprint compatibility check: two NodeIDs sharing more coordinates are more
# structurally interchangeable. Body transmuted to a Form recipe.
# ---------------------------------------------------------------------------


def nodeid_compatibility_py(
    a_pkg: int, a_lvl: int, a_type: int, a_inst: int,
    b_pkg: int, b_lvl: int, b_type: int, b_inst: int,
) -> int:
    """Python fallback — semantically identical to the Form recipe."""
    return (
        int(a_pkg == b_pkg)
        + int(a_lvl == b_lvl)
        + int(a_type == b_type)
        + int(a_inst == b_inst)
    )


class NodeIdCompatibilityResponse(BaseModel):
    """GET /api/utils/nodeid_compatibility response."""

    model_config = ConfigDict(extra="forbid")
    compatibility: Annotated[
        int, Field(description="Coordinate-agreement score 0..4 between the two NodeIDs")
    ]
    a: Annotated[list[int], Field(description="NodeID a as [package, level, type, instance]")]
    b: Annotated[list[int], Field(description="NodeID b as [package, level, type, instance]")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/nodeid_compatibility",
    response_model=NodeIdCompatibilityResponse,
    summary="Structural compatibility (0..4 coordinate agreement) between two NodeIDs (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns how many of the four NodeID coordinates (package, level, "
        "type, instance) two cells share — the cheapest structural-"
        "interchangeability signal. Kernel-or-fallback via serve_via_kernel; "
        "three-way parity (CPython, TS, Rust) is the gate."
    ),
)
async def nodeid_compatibility(
    a_pkg: Annotated[int, Query(description="NodeID a — package")] = 1,
    a_lvl: Annotated[int, Query(description="NodeID a — level")] = 5,
    a_type: Annotated[int, Query(description="NodeID a — type_")] = 4,
    a_inst: Annotated[int, Query(description="NodeID a — instance")] = 1,
    b_pkg: Annotated[int, Query(description="NodeID b — package")] = 1,
    b_lvl: Annotated[int, Query(description="NodeID b — level")] = 4,
    b_type: Annotated[int, Query(description="NodeID b — type_")] = 4,
    b_inst: Annotated[int, Query(description="NodeID b — instance")] = 7,
) -> NodeIdCompatibilityResponse:
    compatibility, runtime = serve_via_kernel(
        "endpoint_nodeid_compatibility_demo.fk",
        bindings={
            "a_pkg": a_pkg, "a_lvl": a_lvl, "a_type": a_type, "a_inst": a_inst,
            "b_pkg": b_pkg, "b_lvl": b_lvl, "b_type": b_type, "b_inst": b_inst,
        },
        fallback=lambda: nodeid_compatibility_py(
            a_pkg, a_lvl, a_type, a_inst, b_pkg, b_lvl, b_type, b_inst,
        ),
        parse=int,
    )
    return NodeIdCompatibilityResponse(
        compatibility=compatibility,
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
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
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


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/simpson_diversity
#
# Pure computation: Simpson's diversity index 1 - sum(p_i^2) over a list of
# integer category counts (p_i = count_i / total). The substrate's spread
# signal — how evenly contributors' dominant worldview axes are distributed.
# Shares its body with vitality_service._simpson_diversity (the fallback);
# the Form recipe is its kernel-served twin. Float division is forced via a
# total + 0.0 coercion in the recipe (the kernel's `div` is integer division
# on two ints; Python's `/` is always float), value-identical.
# ---------------------------------------------------------------------------


def _simpson_diversity_py(counts: list[int]) -> float:
    """Python fallback — semantically identical to the Form recipe.

    Mirrors vitality_service._simpson_diversity: 1 - sum((c/total)^2), with a
    total <= 0 guard returning 0.0.
    """
    total = sum(counts)
    if total <= 0:
        return 0.0
    return 1.0 - sum((c / total) ** 2 for c in counts)


class SimpsonDiversityResponse(BaseModel):
    """GET /api/utils/simpson_diversity response."""

    model_config = ConfigDict(extra="forbid")
    diversity: Annotated[float, Field(description="Simpson's index 1 - sum(p_i^2), in [0.0, 1.0]")]
    counts: Annotated[list[int], Field(description="Input category counts, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/simpson_diversity",
    response_model=SimpsonDiversityResponse,
    summary="Simpson's diversity index over category counts (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns 1 - sum((count_i / total)^2) — 0.0 for a single category "
        "(no diversity), approaching 1.0 as the distribution spreads evenly. "
        "The same shape vitality_service uses for contributor-worldview spread. "
        "Kernel-or-fallback via serve_via_kernel; three-way parity is the gate."
    ),
)
async def simpson_diversity(
    counts: Annotated[
        str,
        Query(description="Comma-separated non-negative integers — e.g. '2,1,1'"),
    ] = "2,1,1",
) -> SimpsonDiversityResponse:
    parsed = _parse_values(counts)
    diversity, runtime = serve_via_kernel(
        "endpoint_simpson_diversity_demo.fk",
        bindings={"counts": parsed},
        fallback=lambda: _simpson_diversity_py(parsed),
        parse=float,
    )
    return SimpsonDiversityResponse(
        diversity=diversity,
        counts=parsed,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/idea_score
#
# Pure computation: the free-energy idea score (potential_value * confidence)
# / max(estimated_cost + resistance_risk, 0.5). The substrate's value-per-cost
# prioritization signal — the number select_idea ranks the backlog by. Shares
# its body with idea_scoring._score (the fallback). The two-argument max is
# expressed as a comparison in the recipe (the kernel's `max` native floors
# floats; an `if a > b` branch is float-correct and value-identical).
# ---------------------------------------------------------------------------


def _idea_score_py(
    potential_value: float, confidence: float, estimated_cost: float, resistance_risk: float
) -> float:
    """Python fallback — semantically identical to the Form recipe.

    Mirrors idea_scoring._score: the 0.5 CC floor prevents inflated scores when
    cost and risk are both near zero.
    """
    denom = max(estimated_cost + resistance_risk, 0.5)
    return (potential_value * confidence) / denom


class IdeaScoreResponse(BaseModel):
    """GET /api/utils/idea_score response."""

    model_config = ConfigDict(extra="forbid")
    score: Annotated[float, Field(description="Free-energy score (pv*conf) / max(cost+risk, 0.5)")]
    potential_value: Annotated[float, Field(description="Input potential_value, echoed back")]
    confidence: Annotated[float, Field(description="Input confidence, echoed back")]
    estimated_cost: Annotated[float, Field(description="Input estimated_cost, echoed back")]
    resistance_risk: Annotated[float, Field(description="Input resistance_risk, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/idea_score",
    response_model=IdeaScoreResponse,
    summary="Free-energy idea score with the 0.5 CC floor (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns (potential_value * confidence) / max(estimated_cost + "
        "resistance_risk, 0.5) — the substrate's value-per-cost ranking signal. "
        "The 0.5 CC floor prevents inflated scores when cost and risk are near "
        "zero. Same body as idea_scoring._score. Kernel-or-fallback via "
        "serve_via_kernel; three-way parity is the gate."
    ),
)
async def idea_score(
    potential_value: Annotated[float, Query(description="Potential value in CC")] = 8.0,
    confidence: Annotated[float, Query(description="Confidence in [0.0, 1.0]")] = 0.75,
    estimated_cost: Annotated[float, Query(description="Estimated cost in CC")] = 2.0,
    resistance_risk: Annotated[float, Query(description="Resistance risk in CC")] = 1.0,
) -> IdeaScoreResponse:
    score, runtime = serve_via_kernel(
        "endpoint_idea_score_demo.fk",
        bindings={
            "potential_value": potential_value,
            "confidence": confidence,
            "estimated_cost": estimated_cost,
            "resistance_risk": resistance_risk,
        },
        fallback=lambda: _idea_score_py(
            potential_value, confidence, estimated_cost, resistance_risk
        ),
        parse=float,
    )
    return IdeaScoreResponse(
        score=score,
        potential_value=potential_value,
        confidence=confidence,
        estimated_cost=estimated_cost,
        resistance_risk=resistance_risk,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/marginal_cc_return
#
# Pure computation: Method-B marginal CC return (value_gap * conf^2) /
# (remaining_cost + rr * 0.5), where value_gap = max(pv - av, 0.0) and
# remaining_cost = max(ec - ac, 0.1). Prioritizes uncaptured value per
# remaining CC — confidence enters squared so low-confidence ideas are
# discounted twice. Shares its arithmetic core with idea_scoring.
# _marginal_cc_return (the fallback); that function additionally coalesces
# falsy fields to defaults before the math — host concern, applied here in
# the same way before the recipe runs. The two maxes are comparisons in the
# recipe (float-correct; the `max` native floors floats).
# ---------------------------------------------------------------------------


def _marginal_cc_return_py(
    pv: float, av: float, conf: float, ec: float, ac: float, rr: float
) -> float:
    """Python fallback — the arithmetic core of idea_scoring._marginal_cc_return.

    Inputs are the already-coalesced floats (the service function's
    ``getattr(...) or default`` substitution is the caller's job; this is the
    pure math after it). value_gap floors at 0.0, remaining_cost at 0.1.
    """
    value_gap = max(pv - av, 0.0)
    remaining_cost = max(ec - ac, 0.1)
    return (value_gap * conf * conf) / (remaining_cost + rr * 0.5)


class MarginalCcReturnResponse(BaseModel):
    """GET /api/utils/marginal_cc_return response."""

    model_config = ConfigDict(extra="forbid")
    marginal_return: Annotated[
        float, Field(description="(value_gap * conf^2) / (remaining_cost + rr*0.5)")
    ]
    pv: Annotated[float, Field(description="potential_value, echoed back")]
    av: Annotated[float, Field(description="actual_value, echoed back")]
    conf: Annotated[float, Field(description="confidence, echoed back")]
    ec: Annotated[float, Field(description="estimated_cost, echoed back")]
    ac: Annotated[float, Field(description="actual_cost, echoed back")]
    rr: Annotated[float, Field(description="resistance_risk, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/marginal_cc_return",
    response_model=MarginalCcReturnResponse,
    summary="Method-B marginal CC return (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns (value_gap * conf^2) / (remaining_cost + rr*0.5) where "
        "value_gap = max(pv - av, 0.0) and remaining_cost = max(ec - ac, 0.1) — "
        "uncaptured value per remaining CC, confidence discounted twice. The "
        "arithmetic core of idea_scoring._marginal_cc_return. Kernel-or-fallback "
        "via serve_via_kernel; three-way parity is the gate."
    ),
)
async def marginal_cc_return(
    pv: Annotated[float, Query(description="potential_value in CC")] = 8.0,
    av: Annotated[float, Query(description="actual_value in CC")] = 3.0,
    conf: Annotated[float, Query(description="confidence in [0.0, 1.0]")] = 0.8,
    ec: Annotated[float, Query(description="estimated_cost in CC")] = 4.0,
    ac: Annotated[float, Query(description="actual_cost in CC")] = 1.0,
    rr: Annotated[float, Query(description="resistance_risk in CC")] = 2.0,
) -> MarginalCcReturnResponse:
    marginal_return, runtime = serve_via_kernel(
        "endpoint_marginal_cc_return_demo.fk",
        bindings={"pv": pv, "av": av, "conf": conf, "ec": ec, "ac": ac, "rr": rr},
        fallback=lambda: _marginal_cc_return_py(pv, av, conf, ec, ac, rr),
        parse=float,
    )
    return MarginalCcReturnResponse(
        marginal_return=marginal_return,
        pv=pv, av=av, conf=conf, ec=ec, ac=ac, rr=rr,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/idea_marginal_from_record
#
# The FIRST kernel-served route to exercise STRUCTURE ACCESS — a recipe that
# receives a structured object (the idea, marshalled as a kernel Record from a
# Python dict / model) and pulls named fields out of it, rather than receiving
# the inputs pre-flattened into separate scalar bindings. Same arithmetic as
# marginal_cc_return; the new capability is the field extraction.
#
# How the structure travels into the recipe: the bindings carry one ``idea``
# dict. form_kernel_bridge marshals it to a kernel Record — ``_fk_literal``
# renders ``(record_new <blueprint> "field" value ...)`` on the subprocess path,
# and lib.rs ``py_to_value`` builds a ``Value::Record`` on the inline path. The
# recipe reads each field via the ``_get`` native (the python-bmf SUBSCRIPT
# lowering), which now reads Record fields. This is the gate the
# API_KERNEL_READINESS doc names as blocking ~60% of remaining candidates;
# homogeneous-dict field access is the clean subset built here. (Heterogeneous
# object-OR-dict polymorphism — _safe_float reading .field from a model OR
# ["field"] from a dict across mixed collections — stays CPython; named in the
# doc's structure-access section.)
# ---------------------------------------------------------------------------


class IdeaMarginalFromRecordResponse(BaseModel):
    """GET /api/utils/idea_marginal_from_record response."""

    model_config = ConfigDict(extra="forbid")
    marginal_return: Annotated[
        float,
        Field(description="(value_gap * conf^2) / (remaining_cost + rr*0.5), read from a record"),
    ]
    idea: Annotated[
        dict,
        Field(description="The structured idea object the recipe read its fields from, echoed back"),
    ]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


def _marginal_from_idea_py(idea: dict) -> float:
    """Python fallback — value-identical to endpoint_idea_marginal_from_record_demo.fk.

    Reads the six fields from the structured object and computes the Method-B
    marginal CC return, round(_, 6). The recipe's operation order mirrors this
    so kernel and fallback agree.
    """
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


@router.get(
    "/idea_marginal_from_record",
    response_model=IdeaMarginalFromRecordResponse,
    summary="Method-B marginal CC return read from a structured record (structure-access route)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — the "
        "FIRST to exercise structure access. The six inputs arrive as fields of "
        "one structured object (the idea), marshalled into a kernel Record from "
        "a Python dict, and the recipe reads them by name via the kernel's field "
        "accessor. Same arithmetic as marginal_cc_return; the new capability is "
        "field extraction from a record binding. Kernel-or-fallback via "
        "serve_via_kernel; CPython==Rust value-parity is the gate."
    ),
)
async def idea_marginal_from_record(
    pv: Annotated[float, Query(description="potential_value in CC")] = 8.0,
    av: Annotated[float, Query(description="actual_value in CC")] = 3.0,
    conf: Annotated[float, Query(description="confidence in [0.0, 1.0]")] = 0.8,
    ec: Annotated[float, Query(description="estimated_cost in CC")] = 4.0,
    ac: Annotated[float, Query(description="actual_cost in CC")] = 1.0,
    rr: Annotated[float, Query(description="resistance_risk in CC")] = 2.0,
) -> IdeaMarginalFromRecordResponse:
    idea = {
        "potential_value": pv,
        "actual_value": av,
        "confidence": conf,
        "estimated_cost": ec,
        "actual_cost": ac,
        "resistance_risk": rr,
    }
    marginal_return, runtime = serve_via_kernel(
        "endpoint_idea_marginal_from_record_demo.fk",
        bindings={"idea": idea},
        fallback=lambda: _marginal_from_idea_py(idea),
        parse=float,
    )
    return IdeaMarginalFromRecordResponse(
        marginal_return=marginal_return,
        idea=idea,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/breath_balance
#
# Pure computation: normalized Shannon entropy H / H_max over three phase
# counts (gas / water / ice), H_max = ln(3). The substrate's breath-rhythm
# balance signal — 1.0 for equal thirds, -0.0 (zero) for a single phase.
# Shares its body with vitality_service._breath_balance_py (the fallback);
# the Form recipe is its kernel-served twin. This is the first kernel-served
# route to use a transcendental native — math.log lowers to math_log (ln).
# The p > 0 guard is the log-of-zero guard (ln(0) is never evaluated); the
# single trailing negation matches CPython's `-sum(...)` to the bit,
# including the -0.0 sign on a single-phase distribution.
# ---------------------------------------------------------------------------


class BreathBalanceResponse(BaseModel):
    """GET /api/utils/breath_balance response."""

    model_config = ConfigDict(extra="forbid")
    balance: Annotated[float, Field(description="Normalized entropy H/H_max in [0.0, 1.0]")]
    gas: Annotated[int, Field(description="Input gas-phase count, echoed back")]
    water: Annotated[int, Field(description="Input water-phase count, echoed back")]
    ice: Annotated[int, Field(description="Input ice-phase count, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/breath_balance",
    response_model=BreathBalanceResponse,
    summary="Normalized phase-balance entropy (body runs as Form recipe with ln native)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns normalized Shannon entropy H / H_max over three phase "
        "counts (gas/water/ice), H_max = ln(3) — 1.0 for perfectly balanced "
        "thirds, approaching 0.0 as the distribution collapses into one "
        "phase. The same shape vitality_service uses for breath rhythm. "
        "First kernel-served route to use a transcendental native (ln); the "
        "p>0 guard is the log-of-zero guard. Kernel-or-fallback via "
        "serve_via_kernel; CPython==Rust value-parity is the gate."
    ),
)
async def breath_balance(
    gas: Annotated[int, Query(ge=0, description="Gas-phase count")] = 1,
    water: Annotated[int, Query(ge=0, description="Water-phase count")] = 1,
    ice: Annotated[int, Query(ge=0, description="Ice-phase count")] = 1,
) -> BreathBalanceResponse:
    from app.services.vitality_service import _breath_balance_py

    balance, runtime = serve_via_kernel(
        "endpoint_breath_balance_demo.fk",
        bindings={"gas": gas, "water": water, "ice": ice},
        fallback=lambda: _breath_balance_py(gas, water, ice),
        parse=float,
    )
    return BreathBalanceResponse(
        balance=balance,
        gas=gas,
        water=water,
        ice=ice,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/shannon_entropy
#
# Pure computation: normalized Shannon entropy H / H_max over three phase
# counts (gas / water / ice), H_max = ln(3), rounded to 4 places. The body
# of breath_service._shannon_entropy_normalized. Distinct from breath_balance:
# the per-term accumulator SUBTRACTS (so a single nonzero phase yields +0.0,
# not breath_balance's trailing-negation -0.0), the result is wrapped in
# round(_, 4), and the empty guard is `total == 0`. Folds two natives into one
# recipe — math.log (ln, breath_balance's unlock) and round_ndigits (PR #2320,
# cost_vector's unlock). The p>0 guard is the log-of-zero guard.
# ---------------------------------------------------------------------------


class ShannonEntropyResponse(BaseModel):
    """GET /api/utils/shannon_entropy response."""

    model_config = ConfigDict(extra="forbid")
    entropy: Annotated[
        float, Field(description="Normalized Shannon entropy H/H_max in [0.0, 1.0], round(_, 4)")
    ]
    gas: Annotated[int, Field(description="Input gas-phase count, echoed back")]
    water: Annotated[int, Field(description="Input water-phase count, echoed back")]
    ice: Annotated[int, Field(description="Input ice-phase count, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/shannon_entropy",
    response_model=ShannonEntropyResponse,
    summary="Normalized Shannon entropy over three phase counts (Form recipe, ln + round natives)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns normalized Shannon entropy H / H_max over three phase counts "
        "(gas/water/ice), H_max = ln(3), rounded to 4 places — 1.0 for equal "
        "thirds, 0.0 when only one phase is present. The body of "
        "breath_service._shannon_entropy_normalized. Folds two natives into one "
        "recipe (math.log → ln, round_ndigits → CPython-exact round). The p>0 "
        "guard is the log-of-zero guard. Kernel-or-fallback via serve_via_kernel; "
        "CPython==Rust value-parity is the gate."
    ),
)
async def shannon_entropy(
    gas: Annotated[int, Query(ge=0, description="Gas-phase count")] = 1,
    water: Annotated[int, Query(ge=0, description="Water-phase count")] = 1,
    ice: Annotated[int, Query(ge=0, description="Ice-phase count")] = 1,
) -> ShannonEntropyResponse:
    from app.services.breath_service import _shannon_entropy_normalized

    entropy, runtime = serve_via_kernel(
        "endpoint_shannon_entropy_demo.fk",
        bindings={"gas": gas, "water": water, "ice": ice},
        fallback=lambda: _shannon_entropy_normalized(gas, water, ice),
        parse=float,
    )
    return ShannonEntropyResponse(
        entropy=entropy,
        gas=gas,
        water=water,
        ice=ice,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/softmax_weights
#
# Pure computation: softmax over a list of float scores → a list of
# probability weights summing to 1.0. This is the FIRST list-returning
# kernel-served route — every prior route returns a scalar. It proves the
# value-walk carries list construction end to end: the recipe builds the
# result list via the append-accumulator idiom (form-stdlib's METHOD-CALL
# accumulator arm / the adapter's `_list_append` lowering) and the result
# round-trips through value_to_py's List arm as a real Python list. Shares
# its body with idea_scoring._softmax_weights (the fallback). Uses the
# math.exp transcendental native (math_exp), like breath_balance's ln.
# This opens the whole class of list-returning routes — distributions,
# vectors, normalized weights.
# ---------------------------------------------------------------------------


def _coerce_float_list(value: object) -> list[float]:
    """Coerce a kernel/fallback result into a list[float].

    The inline path hands back a real Python list (value_to_py's List arm);
    the subprocess path hands back the kernel's display string, e.g.
    ``[0.09003057317038046, 0.24472847105479764, 0.6652409557748218]``; the
    python-fallback hands back the list directly. One coercion serves all
    three carriers so the route reads ``runtime`` honestly regardless of path.
    """
    if isinstance(value, (list, tuple)):
        return [float(v) for v in value]
    s = str(value).strip()
    if s in ("", "[]", "(list)"):
        return []
    s = s.strip("[]() ")
    if not s:
        return []
    # Comma- or space-separated floats; `(list a b c)` collapses to space-sep.
    sep = "," if "," in s else None
    parts = s.split(sep) if sep else s.split()
    return [float(p.strip().rstrip(",")) for p in parts if p.strip().rstrip(",")]


class SoftmaxWeightsResponse(BaseModel):
    """GET /api/utils/softmax_weights response."""

    model_config = ConfigDict(extra="forbid")
    weights: Annotated[
        list[float],
        Field(description="Softmax probability weights, same length as scores, summing to 1.0"),
    ]
    scores: Annotated[list[float], Field(description="Input scores, echoed back")]
    temperature: Annotated[float, Field(description="Exploration temperature, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/softmax_weights",
    response_model=SoftmaxWeightsResponse,
    summary="Softmax probability weights over float scores (first LIST-returning Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns softmax(scores / temperature) — a list of probability "
        "weights summing to 1.0. temperature controls exploration: 0.0 is "
        "deterministic (all weight on the max), 1.0 is true softmax, >1.0 "
        "flattens the distribution. The same shape idea selection uses to "
        "sample the backlog. This is the FIRST kernel-served route to return "
        "a LIST — the value-walk carries list construction end to end. "
        "Kernel-or-fallback via serve_via_kernel; CPython==Rust element-wise "
        "value-parity is the gate."
    ),
)
async def softmax_weights(
    scores: Annotated[
        str,
        Query(description="Comma-separated floats — e.g. '1.0,2.0,3.0'"),
    ] = "1.0,2.0,3.0",
    temperature: Annotated[
        float,
        Query(ge=0.0, description="Exploration temperature (0.0 = deterministic)"),
    ] = 1.0,
) -> SoftmaxWeightsResponse:
    from app.services.idea_scoring import _softmax_weights

    parsed = _parse_floats(scores, "scores")
    weights, runtime = serve_via_kernel(
        "endpoint_softmax_weights_demo.fk",
        bindings={"scores": parsed, "temperature": temperature},
        fallback=lambda: _softmax_weights(parsed, temperature),
        parse=_coerce_float_list,
    )
    return SoftmaxWeightsResponse(
        weights=weights,
        scores=parsed,
        temperature=temperature,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/cost_vector
#
# Pure computation: decompose an idea's estimated_cost into CC resource
# types — compute (60%), infrastructure (15%), human_attention (25%),
# opportunity (0), external (0) — each rounded to 4 places, plus the
# rounded total. Shares its body with idea_scoring._build_cost_vector (the
# fallback). The recipe returns a LIST of the six components in struct
# order; this route assembles the named CostVector from the positional
# list (same list-returning shape as softmax_weights).
#
# This is the FIRST kernel-served route to use the round_ndigits native
# (PR #2320): the adapter lowers Python's two-arg round(x, 4) to
# round_ndigits, which replicates CPython's round() for floats EXACTLY
# (half-to-even at n places). The prior round-half-up shim diverged from
# CPython on 71,860 of 4M cost/value components; round_ndigits diverges
# 0/4M. The decimal cases that exposed the divergence — e.g.
# estimated_cost=33.333 → ec*0.25=8.33325 → 8.3332 (NOT 8.3333) — now
# match the bit across CPython, the Form-native walker, and form-kernel-rust.
# ---------------------------------------------------------------------------


def _build_cost_vector_components_py(estimated_cost: float) -> list[float]:
    """Python fallback — the six cost components in struct order.

    Mirrors idea_scoring._build_cost_vector's arithmetic exactly:
    compute 60% / infrastructure 15% / human_attention 25% / opportunity 0 /
    external 0, total — each round(_, 4).
    """
    return [
        round(estimated_cost * 0.60, 4),
        round(estimated_cost * 0.15, 4),
        round(estimated_cost * 0.25, 4),
        0.0,
        0.0,
        round(estimated_cost, 4),
    ]


class CostVectorResponse(BaseModel):
    """GET /api/utils/cost_vector response — the named CC cost breakdown."""

    model_config = ConfigDict(extra="forbid")
    compute_cc: Annotated[float, Field(description="LLM token processing cost = round(ec*0.60, 4)")]
    infrastructure_cc: Annotated[float, Field(description="Server/runtime cost = round(ec*0.15, 4)")]
    human_attention_cc: Annotated[float, Field(description="Human review/decision cost = round(ec*0.25, 4)")]
    opportunity_cc: Annotated[float, Field(description="Delay/blocking cost (reserved — 0.0)")]
    external_cc: Annotated[float, Field(description="Hard currency outflow (reserved — 0.0)")]
    total_cc: Annotated[float, Field(description="Total cost = round(ec, 4)")]
    estimated_cost: Annotated[float, Field(description="Input estimated_cost, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/cost_vector",
    response_model=CostVectorResponse,
    summary="CC cost-vector decomposition (first round_ndigits Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Decomposes estimated_cost into CC resource types — compute (60%), "
        "infrastructure (15%), human_attention (25%), opportunity (0), "
        "external (0) — each round(_, 4), plus the rounded total. Same body "
        "as idea_scoring._build_cost_vector. This is the FIRST kernel-served "
        "route to use the round_ndigits native (CPython-exact round(x, 4), "
        "PR #2320): the decimal cases the old round-half-up shim got wrong "
        "(e.g. ec=33.333 → human_attention 8.3332, not 8.3333) now match the "
        "bit across all runtimes. Kernel-or-fallback via serve_via_kernel; "
        "CPython==Rust per-component value-parity is the gate."
    ),
)
async def cost_vector(
    estimated_cost: Annotated[float, Query(ge=0.0, description="Estimated cost in CC")] = 33.333,
) -> CostVectorResponse:
    components, runtime = serve_via_kernel(
        "endpoint_cost_vector_demo.fk",
        bindings={"estimated_cost": estimated_cost},
        fallback=lambda: _build_cost_vector_components_py(estimated_cost),
        parse=_coerce_float_list,
    )
    return CostVectorResponse(
        compute_cc=components[0],
        infrastructure_cc=components[1],
        human_attention_cc=components[2],
        opportunity_cc=components[3],
        external_cc=components[4],
        total_cc=components[5],
        estimated_cost=estimated_cost,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/value_vector
#
# Pure computation: decompose an idea's potential_value into CC value types
# — adoption (50%), lineage (30%), friction_avoided (20%), revenue (0) —
# each rounded to 4 places, plus the rounded total. Shares its body with
# idea_scoring._build_value_vector (the fallback). Sibling of cost_vector,
# same round_ndigits unlock; the recipe returns a LIST of the five
# components in struct order and this route assembles the named ValueVector.
# ---------------------------------------------------------------------------


def _build_value_vector_components_py(potential_value: float) -> list[float]:
    """Python fallback — the five value components in struct order.

    Mirrors idea_scoring._build_value_vector's arithmetic exactly:
    adoption 50% / lineage 30% / friction_avoided 20% / revenue 0, total —
    each round(_, 4).
    """
    return [
        round(potential_value * 0.50, 4),
        round(potential_value * 0.30, 4),
        round(potential_value * 0.20, 4),
        0.0,
        round(potential_value, 4),
    ]


class ValueVectorResponse(BaseModel):
    """GET /api/utils/value_vector response — the named CC value breakdown."""

    model_config = ConfigDict(extra="forbid")
    adoption_cc: Annotated[float, Field(description="Value from usage/adoption = round(pv*0.50, 4)")]
    lineage_cc: Annotated[float, Field(description="Value from lineage pipeline = round(pv*0.30, 4)")]
    friction_avoided_cc: Annotated[float, Field(description="Value from unblocking work = round(pv*0.20, 4)")]
    revenue_cc: Annotated[float, Field(description="External revenue converted to CC (reserved — 0.0)")]
    total_cc: Annotated[float, Field(description="Total value = round(pv, 4)")]
    potential_value: Annotated[float, Field(description="Input potential_value, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/value_vector",
    response_model=ValueVectorResponse,
    summary="CC value-vector decomposition (round_ndigits Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Decomposes potential_value into CC value types — adoption (50%), "
        "lineage (30%), friction_avoided (20%), revenue (0) — each "
        "round(_, 4), plus the rounded total. Same body as "
        "idea_scoring._build_value_vector. Sibling of cost_vector; the "
        "round_ndigits native (CPython-exact round(x, 4), PR #2320) makes "
        "every component match CPython to the bit. Kernel-or-fallback via "
        "serve_via_kernel; CPython==Rust per-component value-parity is the gate."
    ),
)
async def value_vector(
    potential_value: Annotated[float, Query(ge=0.0, description="Potential value in CC")] = 9.205,
) -> ValueVectorResponse:
    components, runtime = serve_via_kernel(
        "endpoint_value_vector_demo.fk",
        bindings={"potential_value": potential_value},
        fallback=lambda: _build_value_vector_components_py(potential_value),
        parse=_coerce_float_list,
    )
    return ValueVectorResponse(
        adoption_cc=components[0],
        lineage_cc=components[1],
        friction_avoided_cc=components[2],
        revenue_cc=components[3],
        total_cc=components[4],
        potential_value=potential_value,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/grounded_roi
#
# Pure computation: the grounded-ROI scalar trio idea_scoring._with_score
# attaches to every IdeaWithScore —
#   remaining_cost_cc = round(max(estimated_cost - actual_cost, 0.0), 4)
#   value_gap_cc      = round(max(potential_value - actual_value, 0.0), 4)
#   roi_cc            = round(value_gap_cc / remaining_cost_cc, 4)
#                         if remaining_cost_cc > 0 else 0.0
# Shares its body with idea_scoring._grounded_roi_components (the fallback);
# the recipe returns a LIST of the three components in struct order and this
# route assembles the named struct (same list-returning shape as cost_vector
# / value_vector).
#
# This route folds three prior unlocks into one recipe: the two-argument max
# expressed as a comparison (the `max` native floors floats; an `if a > b`
# branch is float-correct and value-identical), the round_ndigits native
# (CPython-exact round(x, 4), PR #2320), and a guarded division — the
# `if remaining_cost_cc > 0 else 0.0` ternary is a conditional in the recipe,
# so the kernel never divides by zero. The falsy-coalescing of
# estimated_cost / actual_cost (`or 0.0` in _with_score) is the host's job,
# applied here before the recipe runs.
# ---------------------------------------------------------------------------


class GroundedRoiResponse(BaseModel):
    """GET /api/utils/grounded_roi response — the grounded-ROI scalar trio."""

    model_config = ConfigDict(extra="forbid")
    remaining_cost_cc: Annotated[
        float, Field(description="Unspent cost = round(max(estimated_cost - actual_cost, 0.0), 4)")
    ]
    value_gap_cc: Annotated[
        float, Field(description="Uncaptured value = round(max(potential_value - actual_value, 0.0), 4)")
    ]
    roi_cc: Annotated[
        float,
        Field(
            description=(
                "Return on remaining cost = round(value_gap_cc / remaining_cost_cc, 4), "
                "or 0.0 when remaining_cost_cc is not positive (guarded division)"
            )
        ),
    ]
    estimated_cost: Annotated[float, Field(description="Input estimated_cost, echoed back")]
    actual_cost: Annotated[float, Field(description="Input actual_cost, echoed back")]
    potential_value: Annotated[float, Field(description="Input potential_value, echoed back")]
    actual_value: Annotated[float, Field(description="Input actual_value, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/grounded_roi",
    response_model=GroundedRoiResponse,
    summary="Grounded-ROI scalar trio with guarded division (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns the three CC scalars idea_scoring._with_score attaches to "
        "every IdeaWithScore: remaining_cost_cc = round(max(estimated_cost - "
        "actual_cost, 0.0), 4), value_gap_cc = round(max(potential_value - "
        "actual_value, 0.0), 4), and roi_cc = round(value_gap_cc / "
        "remaining_cost_cc, 4) — guarded to 0.0 when remaining_cost_cc is not "
        "positive, so the kernel never divides by zero. Same body as "
        "idea_scoring._grounded_roi_components. Folds three unlocks into one "
        "recipe: max-as-comparison, the round_ndigits native (CPython-exact "
        "round(x, 4), PR #2320), and a guarded-division conditional. "
        "Kernel-or-fallback via serve_via_kernel; CPython==Rust per-component "
        "value-parity is the gate."
    ),
)
async def grounded_roi(
    estimated_cost: Annotated[float, Query(ge=0.0, description="Estimated cost in CC")] = 60.0,
    actual_cost: Annotated[float, Query(ge=0.0, description="Actual cost spent in CC")] = 12.0,
    potential_value: Annotated[float, Query(ge=0.0, description="Potential value in CC")] = 33.333,
    actual_value: Annotated[float, Query(ge=0.0, description="Actual value captured in CC")] = 8.0,
) -> GroundedRoiResponse:
    from app.services.idea_scoring import _grounded_roi_components

    components, runtime = serve_via_kernel(
        "endpoint_grounded_roi_demo.fk",
        bindings={
            "estimated_cost": estimated_cost,
            "actual_cost": actual_cost,
            "potential_value": potential_value,
            "actual_value": actual_value,
        },
        fallback=lambda: _grounded_roi_components(
            estimated_cost, actual_cost, potential_value, actual_value
        ),
        parse=_coerce_float_list,
    )
    return GroundedRoiResponse(
        remaining_cost_cc=components[0],
        value_gap_cc=components[1],
        roi_cc=components[2],
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        potential_value=potential_value,
        actual_value=actual_value,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/idea_grounding_summary
#
# The FIRST kernel-served route to REDUCE OVER A LIST OF RECORDS — gate #1 in
# kernels/API_KERNEL_READINESS.md ("heterogeneous polymorphic structure
# access"). Every prior structure-access route read fields from ONE record (the
# marginal-CC core); this one receives a LIST of records (one idea's pre-fetched
# specs) and FOLDS a field across it.
#
# The honest subset of grounded_idea_metrics_service.compute_idea_metrics: its
# confidence/grounding signals reduce over the per-idea collections —
#   spec_count             = len(idea_specs)
#   total_event_count      = sum(s["event_count"] for s in idea_specs)
#   specs_with_value_count = count(s for s in idea_specs if s["actual_value"] > 0)
#   max_event_count        = max(s["event_count"] for s in idea_specs)
# the INTEGER reductions the full function builds has_specs_with_data / runtime
# coverage from. FILTERING by idea_id (`_filter_by_idea_id`) is the host's job —
# the route hands the recipe the already-per-idea list; the kernel does the
# REDUCTION. The float-field fold (spec_actual_cost_sum) and the six-collection
# heterogeneous object-OR-dict join stay CPython — named in the ledger.
#
# How the list travels in: the bindings carry one `specs` list of dicts (or
# models — the bridge normalizes model→dict→record at the marshal boundary, so a
# list[model] marshals identically). form_kernel_bridge marshals it to a kernel
# list-of-records — `_fk_literal` renders each element as a `(record_new ...)`
# literal (subprocess), `py_to_value` builds a `Value::Record` per element
# inline; the list arm recurses element-wise. The recipe iterates via the
# head/tail fold the adapter lowers `for s in specs` into. Returns a LIST of the
# four integer signals; this route assembles the named response from it.
# ---------------------------------------------------------------------------


def _coerce_int_list(value: object) -> list[int]:
    """Coerce a kernel/fallback result into a list[int].

    The inline path hands back a real Python list (value_to_py's List arm); the
    subprocess path hands back the kernel's display string, e.g. ``[3, 10, 2,
    7]``; the python-fallback hands back the list directly. One coercion serves
    all three carriers so the route reads ``runtime`` honestly regardless of path.
    """
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value]
    s = str(value).strip()
    if s in ("", "[]", "(list)"):
        return []
    s = s.strip("[]() ")
    if not s:
        return []
    sep = "," if "," in s else None
    parts = s.split(sep) if sep else s.split()
    return [int(float(p.strip().rstrip(","))) for p in parts if p.strip().rstrip(",")]


def _grounding_summary_py(specs: list[dict]) -> list[int]:
    """Python fallback — value-identical to endpoint_idea_grounding_summary_demo.fk.

    The four integer grounding signals, reduced over the list of spec records:
    spec_count, total_event_count, specs_with_value_count, max_event_count.
    """
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


class IdeaGroundingSummaryResponse(BaseModel):
    """GET /api/utils/idea_grounding_summary response — the integer grounding signals."""

    model_config = ConfigDict(extra="forbid")
    spec_count: Annotated[int, Field(description="Number of spec records for this idea = len(specs)")]
    total_event_count: Annotated[
        int, Field(description="Summed event_count across the specs = sum(s['event_count'])")
    ]
    specs_with_value_count: Annotated[
        int, Field(description="Count of specs with actual_value > 0 (a field predicate)")
    ]
    max_event_count: Annotated[
        int, Field(description="Largest event_count across the specs = max(s['event_count'])")
    ]
    spec_count_in: Annotated[int, Field(description="Number of input spec records, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/idea_grounding_summary",
    response_model=IdeaGroundingSummaryResponse,
    summary="Integer grounding signals reduced over a LIST of spec records (first list-of-record-reduction Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — the "
        "FIRST kernel-served route to REDUCE OVER A LIST OF RECORDS (gate #1 in "
        "API_KERNEL_READINESS). Receives one idea's pre-fetched spec records as "
        "a list and folds four integer grounding signals across it: spec_count, "
        "total_event_count, specs_with_value_count (a field predicate), and "
        "max_event_count. The honest integer subset of compute_idea_metrics' "
        "confidence/coverage reductions; filtering by idea_id and the float-field "
        "fold stay CPython (named in the ledger). The bridge marshals the input "
        "list[dict|model] to a kernel list-of-records (model→dict→record "
        "normalized at the boundary), and the recipe iterates via the head/tail "
        "fold. Kernel-or-fallback via serve_via_kernel; three-way "
        "(CPython/TS/Rust) value-parity is the gate."
    ),
)
async def idea_grounding_summary(
    event_counts: Annotated[
        str,
        Query(description="Comma-separated per-spec event_count ints — e.g. '3,0,7'"),
    ] = "3,0,7",
    actual_values: Annotated[
        str,
        Query(description="Comma-separated per-spec actual_value floats — e.g. '1.5,0.0,2.25'"),
    ] = "1.5,0.0,2.25",
) -> IdeaGroundingSummaryResponse:
    # Build the list of spec records from two parallel query lists. A real call
    # site hands the route already-fetched spec dicts/models for one idea; here
    # the two parallel arrays keep the GET surface simple while exercising the
    # real list-of-record marshalling and reduction.
    ec_list = [int(float(x)) for x in event_counts.split(",") if x.strip()]
    av_list = [float(x) for x in actual_values.split(",") if x.strip()]
    if len(ec_list) != len(av_list):
        raise HTTPException(
            status_code=422,
            detail="event_counts and actual_values must have the same length",
        )
    specs = [
        {"event_count": ec, "actual_value": av}
        for ec, av in zip(ec_list, av_list)
    ]
    signals, runtime = serve_via_kernel(
        "endpoint_idea_grounding_summary_demo.fk",
        bindings={"specs": specs},
        fallback=lambda: _grounding_summary_py(specs),
        parse=_coerce_int_list,
    )
    return IdeaGroundingSummaryResponse(
        spec_count=signals[0],
        total_event_count=signals[1],
        specs_with_value_count=signals[2],
        max_event_count=signals[3],
        spec_count_in=len(specs),
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# idea_grounded_cost_sum — SUMMING A FLOAT FIELD over a LIST OF RECORDS.
#
# The float-field half of the list-of-record reduction the integer
# idea_grounding_summary route named as deferred. compute_idea_metrics folds
# FLOAT cost/value across one idea's specs:
#   spec_actual_cost_sum  = sum(s["actual_cost"]  for s in idea_specs)
#   spec_actual_value_sum = sum(s["actual_value"] for s in idea_specs)
# That fold was blocked on the kernels: TS's `add`/`_plus` were i32-only, so a
# float-field SUM threw on TS while running value-exact on Rust+Go. The
# float-add sibling-parity fix closed that gap — the bare-width MATH arm now
# promotes to f64 at runtime and `_plus` gained the float arms — so the
# float-field fold is sibling-portable: CPython == Rust == TS.
#
# The accumulator seeds at 0.0 (a float), so every `total = total + s[field]`
# walks (float, float). The recipe returns [cost_sum, value_sum]; the route
# names the pair. Sample folds land on non-integer floats (5.25, 3.75) that
# print identically across kernels — the integer-valued-float print divergence
# named in float-natives-band.fk is avoided by construction.
# ---------------------------------------------------------------------------


def _grounded_cost_sum_py(specs: list[dict]) -> list[float]:
    """Python fallback — value-identical to endpoint_idea_grounded_cost_sum_demo.fk.

    The two float grounding sums, folded over the list of spec records:
    total_actual_cost, total_actual_value. Seeds float accumulators so the
    fold stays on the float path (matches the recipe's 0.0 seed exactly).
    """
    total_cost = 0.0
    for s in specs:
        total_cost = total_cost + float(s.get("actual_cost", 0.0) or 0.0)
    total_value = 0.0
    for s in specs:
        total_value = total_value + float(s.get("actual_value", 0.0) or 0.0)
    return [total_cost, total_value]


class IdeaGroundedCostSumResponse(BaseModel):
    """GET /api/utils/idea_grounded_cost_sum response — the float grounding sums."""

    model_config = ConfigDict(extra="forbid")
    spec_actual_cost_sum: Annotated[
        float, Field(description="Summed actual_cost across the specs = sum(s['actual_cost'])")
    ]
    spec_actual_value_sum: Annotated[
        float, Field(description="Summed actual_value across the specs = sum(s['actual_value'])")
    ]
    spec_count_in: Annotated[int, Field(description="Number of input spec records, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/idea_grounded_cost_sum",
    response_model=IdeaGroundedCostSumResponse,
    summary="Float grounding sums folded over a LIST of spec records (float-field list-of-record reduction)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — the "
        "FLOAT-FIELD reduction the integer idea_grounding_summary route named "
        "as deferred. Receives one idea's pre-fetched spec records as a list "
        "and folds two FLOAT grounding sums across it: spec_actual_cost_sum and "
        "spec_actual_value_sum. This was the capability blocked by TS's "
        "i32-only add/_plus; the float-add sibling-parity fix opened it, so the "
        "float-field fold is value-exact across CPython / Rust / TS. The bridge "
        "marshals the input list[dict|model] to a kernel list-of-records and the "
        "recipe iterates via the head/tail fold with a float accumulator. "
        "Kernel-or-fallback via serve_via_kernel."
    ),
)
async def idea_grounded_cost_sum(
    actual_costs: Annotated[
        str,
        Query(description="Comma-separated per-spec actual_cost floats — e.g. '3.5,1.25,0.5'"),
    ] = "3.5,1.25,0.5",
    actual_values: Annotated[
        str,
        Query(description="Comma-separated per-spec actual_value floats — e.g. '1.5,0.0,2.25'"),
    ] = "1.5,0.0,2.25",
) -> IdeaGroundedCostSumResponse:
    # Build the list of spec records from two parallel float lists. A real call
    # site hands the route already-fetched spec dicts/models for one idea; the
    # two parallel arrays keep the GET surface simple while exercising the real
    # list-of-record marshalling and the float-field fold.
    cost_list = [float(x) for x in actual_costs.split(",") if x.strip()]
    val_list = [float(x) for x in actual_values.split(",") if x.strip()]
    if len(cost_list) != len(val_list):
        raise HTTPException(
            status_code=422,
            detail="actual_costs and actual_values must have the same length",
        )
    specs = [
        {"actual_cost": ac, "actual_value": av}
        for ac, av in zip(cost_list, val_list)
    ]
    sums, runtime = serve_via_kernel(
        "endpoint_idea_grounded_cost_sum_demo.fk",
        bindings={"specs": specs},
        fallback=lambda: _grounded_cost_sum_py(specs),
        parse=_coerce_float_list,
    )
    return IdeaGroundedCostSumResponse(
        spec_actual_cost_sum=sums[0],
        spec_actual_value_sum=sums[1],
        spec_count_in=len(specs),
        runtime=runtime,
    )


@router.get(
    "/kernel_status",
    summary="Visibility into which Form-kernel surface is serving this container",
    description=(
        "Reports the kernel paths available in this container. "
        "``active`` names the path the next transmuted endpoint will take: "
        "``inline`` (PyO3 extension), ``subprocess`` (form-kernel-rust "
        "binary), or ``python-fallback`` (no kernel reachable). "
        "``binary_available`` and ``inline_available`` are the underlying "
        "flags; they let an operator see whether a deploy lost one path "
        "while keeping another."
    ),
)
async def kernel_status() -> dict[str, object]:
    bin_ok = kernel_available()
    return {
        "active": active_runtime(),
        "inline_available": inline_available(),
        "binary_available": bin_ok,
        # ``available`` is the original (binary-only) flag — kept as an
        # alias so callers from before the inline path don't break.
        "available": bin_ok,
        "binary_path": str(kernel_bin_path()),
    }
