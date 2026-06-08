"""Transmuted /api/utils idea/score combinator endpoints (bodies run as Form recipes).

Bodies live as Form recipes; the route requires the native kernel via
``serve_via_kernel``. This module owns request binding and response shaping;
the endpoint arithmetic lives in the committed Form recipes. Routes decorate
the shared ``/utils`` router from ``app.routers.kernel_shared`` so every path
stays ``/api/utils/...``.
"""
from __future__ import annotations

from app.routers.kernel_shared import (
    Annotated,
    BaseModel,
    ConfigDict,
    Field,
    HTTPException,
    Query,
    _coerce_float_list,
    _parse_floats,
    _parse_values,
    router,
    serve_via_kernel,
)

# ---------------------------------------------------------------------------
# Endpoint: /api/utils/weighted_average
#
# Pure computation: weighted average of a list of float scores against a
# list of float weights. The substrate's bread-and-butter combinator —
# every multi-signal coherence aggregation goes through this shape.
# ---------------------------------------------------------------------------


class WeightedAverageResponse(BaseModel):
    """GET /api/utils/weighted_average response."""

    model_config = ConfigDict(extra="forbid")
    average: Annotated[float, Field(description="Weighted mean = sum(v*w) / sum(w)")]
    values: Annotated[list[float], Field(description="Input scores, echoed back")]
    weights: Annotated[list[float], Field(description="Input weights, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
    ]


@router.get(
    "/weighted_average",
    response_model=WeightedAverageResponse,
    summary="Weighted average of float scores (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns sum(values[i] * weights[i]) / sum(weights). The substrate's "
        "bread-and-butter coherence-score combinator. Kernel-only served "
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
# Shares the arithmetic shape vitality_service._simpson_diversity uses.
# Float division is forced via a
# total + 0.0 coercion in the recipe (the kernel's `div` is integer division
# on two ints; Python's `/` is always float), value-identical.
# ---------------------------------------------------------------------------


class SimpsonDiversityResponse(BaseModel):
    """GET /api/utils/simpson_diversity response."""

    model_config = ConfigDict(extra="forbid")
    diversity: Annotated[float, Field(description="Simpson's index 1 - sum(p_i^2), in [0.0, 1.0]")]
    counts: Annotated[list[int], Field(description="Input category counts, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
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
        "Kernel-only via serve_via_kernel; three-way parity is the gate."
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
# prioritization signal — the number select_idea ranks the backlog by. It mirrors
# idea_scoring._score's arithmetic. The two-argument max is
# expressed as a comparison in the recipe (the kernel's `max` native floors
# floats; an `if a > b` branch is float-correct and value-identical).
# ---------------------------------------------------------------------------


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
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
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
        "zero. Same body as idea_scoring._score. Kernel-only via "
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
# _marginal_cc_return; that function additionally coalesces
# falsy fields to defaults before the math — host concern, applied here in
# the same way before the recipe runs. The two maxes are comparisons in the
# recipe (float-correct; the `max` native floors floats).
# ---------------------------------------------------------------------------


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
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
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
        "arithmetic core of idea_scoring._marginal_cc_return. Kernel-only "
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
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
    ]

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
        "field extraction from a record binding. Kernel-only via "
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
        parse=float,
    )
    return IdeaMarginalFromRecordResponse(
        marginal_return=marginal_return,
        idea=idea,
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
# its body mirrors idea_scoring._softmax_weights. Uses the
# math.exp transcendental native (math_exp), like breath_balance's ln.
# This opens the whole class of list-returning routes — distributions,
# vectors, normalized weights.
# ---------------------------------------------------------------------------


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
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
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
        "Kernel-only via serve_via_kernel; CPython==Rust element-wise "
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
    parsed = _parse_floats(scores, "scores")
    weights, runtime = serve_via_kernel(
        "endpoint_softmax_weights_demo.fk",
        bindings={"scores": parsed, "temperature": temperature},
        parse=_coerce_float_list,
    )
    return SoftmaxWeightsResponse(
        weights=weights,
        scores=parsed,
        temperature=temperature,
        runtime=runtime,
    )
