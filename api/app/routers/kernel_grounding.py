"""Transmuted /api/utils grounding-summary + cost/value-vector endpoints (bodies run as Form recipes).

Bodies live as Form recipes; the route prefers the native kernel via
``serve_via_kernel`` and falls back to the value-identical Python ``_py``
function. Routes decorate the shared ``/utils`` router from
``app.routers.kernel_shared`` so every path stays ``/api/utils/...``.
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
    _coerce_int_list,
    router,
    serve_via_kernel,
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
