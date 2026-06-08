"""Transmuted /api/utils grounded-cost and grounded-value endpoints (bodies run as Form recipes).

Bodies live as Form recipes; the route requires the native kernel via
``serve_via_kernel``. This module owns request binding and response shaping;
the endpoint reductions live in the committed Form recipes. Routes decorate
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
    router,
    serve_via_kernel,
)

# ---------------------------------------------------------------------------
# grounded_cost — the GROUNDED-COST REDUCTION of compute_idea_metrics.
#
# The richest residual slice of grounded_idea_metrics_service.compute_idea_metrics,
# falling now that the float-field fold (idea_grounded_cost_sum), per-record
# arithmetic, and structure-access are all banked. compute_idea_metrics takes
# SIX pre-fetched collections, FILTERS each by idea_id, and computes many
# outputs. Current decomposition: filtering is still resolved before this recipe
# via _filter_by_idea_id / _filter_commits_by_idea; the NUMERIC REDUCTION over
# the already-relevant records is the kernel computation. Filtering is not
# protected territory — it is next native work once the route grammar carries the
# collection query cleanly. Given the already-filtered records for one idea it folds:
#   spec_actual_cost_sum    = sum(s["actual_cost"]    for s in specs)
#   spec_estimated_cost_sum = sum(s["estimated_cost"] for s in specs)
#   runtime_cost            = the single runtime_cost_estimate (None→0.0 before dispatch)
#   commit_cost_sum         = sum(clamp(0.10 + files*0.15 + lines*0.002, 0.05, 10.0)
#                                 for c in commits)   — _estimate_commit_cost_sum EXACTLY
#   lineage_estimated_cost  = sum(l["estimated_cost"] for l in links)
#   computed_actual_cost    = spec_actual_cost_sum + runtime_cost + commit_cost_sum
# The residual work: filtering/fetching and the six-collection join still happen
# before this recipe. The cost reduction is already the kernel computation; the
# surrounding orchestration is visible backlog, not a stopping point.
#
# Surface: GET with parallel-array query params (the established list-route
# shape). spec_actual_costs / spec_estimated_costs are parallel per-spec arrays;
# commit_change_files / commit_lines_added are parallel per-commit arrays;
# lineage_estimated_costs is the per-link array; runtime_cost is the scalar the
# caller already resolved (None→0.0). A real call site hands the route
# already-filtered dicts/models; the parallel arrays keep the GET surface simple
# while exercising the real list-of-record marshalling. The bridge marshals each
# reconstructed record list to a kernel list-of-records; the recipe folds.
# ---------------------------------------------------------------------------

class GroundedCostResponse(BaseModel):
    """GET /api/utils/grounded_cost response — the grounded-cost reduction outputs."""

    model_config = ConfigDict(extra="forbid")
    spec_actual_cost_sum: Annotated[
        float, Field(description="Summed actual_cost across the specs = sum(s['actual_cost'])")
    ]
    spec_estimated_cost_sum: Annotated[
        float, Field(description="Summed estimated_cost across the specs = sum(s['estimated_cost'])")
    ]
    runtime_cost: Annotated[
        float, Field(description="The idea's runtime_cost_estimate (None resolved to 0.0 before dispatch)")
    ]
    commit_cost_sum: Annotated[
        float,
        Field(
            description="Summed per-commit clamped cost = "
            "sum(max(0.05, min(10.0, 0.10 + files*0.15 + lines*0.002)))"
        ),
    ]
    lineage_estimated_cost: Annotated[
        float, Field(description="Summed estimated_cost across the lineage links = sum(l['estimated_cost'])")
    ]
    computed_actual_cost: Annotated[
        float,
        Field(description="spec_actual_cost_sum + runtime_cost + commit_cost_sum"),
    ]
    spec_count_in: Annotated[int, Field(description="Number of input spec records, echoed back")]
    commit_count_in: Annotated[int, Field(description="Number of input commit records, echoed back")]
    lineage_count_in: Annotated[int, Field(description="Number of input lineage records, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
    ]


@router.get(
    "/grounded_cost",
    response_model=GroundedCostResponse,
    summary="The grounded-cost reduction of compute_idea_metrics, folded over already-filtered records",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — the "
        "GROUNDED-COST REDUCTION of grounded_idea_metrics_service."
        "compute_idea_metrics, the richest residual slice now falling. Given one "
        "idea's ALREADY-FILTERED records it folds: spec_actual_cost_sum, "
        "spec_estimated_cost_sum, the commit_cost_sum "
        "(sum(max(0.05, min(10.0, 0.10 + files*0.15 + lines*0.002)) per commit) "
        "— _estimate_commit_cost_sum EXACTLY, clamp included), "
        "lineage_estimated_cost, and composes computed_actual_cost = "
        "spec_actual_cost_sum + runtime_cost + commit_cost_sum. Filtering the six "
        "collections by idea_id is currently resolved before dispatch; that is "
        "visible next native work, while the kernel already runs the numeric "
        "reduction. The bridge marshals each reconstructed record list to "
        "a kernel list-of-records and the recipe folds via the head/tail fold "
        "with float accumulators and a min2/max2 clamp. Kernel-only via "
        "serve_via_kernel; three-way (CPython/TS/Rust) value-parity is the gate."
    ),
)
async def grounded_cost(
    spec_actual_costs: Annotated[
        str,
        Query(description="Comma-separated per-spec actual_cost floats — e.g. '3.5,1.25'"),
    ] = "3.5,1.25",
    spec_estimated_costs: Annotated[
        str,
        Query(description="Comma-separated per-spec estimated_cost floats — e.g. '4.25,2.5'"),
    ] = "4.25,2.5",
    commit_change_files: Annotated[
        str,
        Query(description="Comma-separated per-commit change_files ints — e.g. '3'"),
    ] = "3",
    commit_lines_added: Annotated[
        str,
        Query(description="Comma-separated per-commit lines_added ints — e.g. '100'"),
    ] = "100",
    lineage_estimated_costs: Annotated[
        str,
        Query(description="Comma-separated per-link estimated_cost floats — e.g. '5.25,1.5'"),
    ] = "5.25,1.5",
    runtime_cost: Annotated[
        float,
        Query(description="The idea's runtime_cost_estimate, already None→0.0 resolved before dispatch"),
    ] = 2.25,
) -> GroundedCostResponse:
    # Reconstruct the already-filtered record lists from the parallel query
    # arrays. A real call site hands the route already-fetched dicts/models for
    # one idea; the parallel arrays keep the GET surface simple while exercising
    # the real list-of-record marshalling and the cost fold.
    sac_list = [float(x) for x in spec_actual_costs.split(",") if x.strip()]
    sec_list = [float(x) for x in spec_estimated_costs.split(",") if x.strip()]
    if len(sac_list) != len(sec_list):
        raise HTTPException(
            status_code=422,
            detail="spec_actual_costs and spec_estimated_costs must have the same length",
        )
    cf_list = [int(float(x)) for x in commit_change_files.split(",") if x.strip()]
    la_list = [int(float(x)) for x in commit_lines_added.split(",") if x.strip()]
    if len(cf_list) != len(la_list):
        raise HTTPException(
            status_code=422,
            detail="commit_change_files and commit_lines_added must have the same length",
        )
    lec_list = [float(x) for x in lineage_estimated_costs.split(",") if x.strip()]
    specs = [
        {"actual_cost": ac, "estimated_cost": ec}
        for ac, ec in zip(sac_list, sec_list)
    ]
    commits = [
        {"change_files": cf, "lines_added": la}
        for cf, la in zip(cf_list, la_list)
    ]
    links = [{"estimated_cost": ec} for ec in lec_list]
    outputs, kernel_runtime = serve_via_kernel(
        "endpoint_grounded_cost_demo.fk",
        bindings={
            "specs": specs,
            "commits": commits,
            "links": links,
            "runtime_cost": runtime_cost,
        },
        parse=_coerce_float_list,
    )
    return GroundedCostResponse(
        spec_actual_cost_sum=outputs[0],
        spec_estimated_cost_sum=outputs[1],
        runtime_cost=outputs[2],
        commit_cost_sum=outputs[3],
        lineage_estimated_cost=outputs[4],
        computed_actual_cost=outputs[5],
        spec_count_in=len(specs),
        commit_count_in=len(commits),
        lineage_count_in=len(links),
        runtime=kernel_runtime,
    )


# ---------------------------------------------------------------------------
# grounded_value — the VALUE / REALIZATION / CONFIDENCE REDUCTION of
# compute_idea_metrics. The SECOND and FINAL numeric slice; with the grounded-
# COST reduction already serving kernel-side (/api/utils/grounded_cost, PR
# #2331) this completes compute_idea_metrics' COMPUTATION kernel-native. What
# remains in CPython after this is visible migration work — collection filtering
# plus boolean-presence derivations — not protected architecture.
#
# THE HONEST DECOMPOSITION. compute_idea_metrics derives three families of fact:
#   (a) NUMERIC REDUCTIONS — max-of-signals, a guarded ratio with a min-clamp, a
#       count→level threshold (min(1.0, count/N)), a five-term weighted sum, a
#       [0.05, 0.95] clamp. This route runs them kernel-side.
#   (b) BOOLEAN / PRESENCE LEVELS — has_specs_with_data, has_lineage,
#       has_friction. Each is an any(...)-over-records boolean-OR fold or a len>0
#       presence ladder resolving to a 3-level {1.0, 0.5/0.3, 0.0} value.
#       Booleans-over-collections is the filtering-adjacent capability; this
#       route currently receives the resolved float level.
#   (c) the FILTERING of the six collections by idea_id — currently resolved
#       before dispatch (_filter_by_idea_id).
#
# Given the host-derived scalars for one idea the recipe computes EXACTLY what
# grounded_idea_metrics_service.compute_idea_metrics computes (verified against
# the source lines, the _WEIGHT_* constants, and the clamps):
#   computed_actual_value   = max(lineage_measured_value, usage_revenue,
#                                 spec_actual_value_sum)
#   computed_estimated_cost = max(spec_estimated_cost_sum, lineage_estimated_cost)
#   value_realization_pct   = min(computed_actual_value / spec_potential_value_sum,
#                                 1.0) if spec_potential_value_sum > 0 else 0.0
#   has_runtime_data        = min(1.0, runtime_event_count / 10.0)
#                                 if runtime_event_count > 0 else 0.0
#   has_commits             = min(1.0, commit_count / 5.0) if commit_count > 0
#                                 else 0.0
#   computed_confidence     = max(0.05, min(0.95,
#       has_specs_with_data*0.30 + has_runtime_data*0.25 + has_lineage*0.25
#       + has_commits*0.10 + has_friction*0.10))
# Weights _WEIGHT_SPECS=0.30, _WEIGHT_RUNTIME=0.25, _WEIGHT_LINEAGE=0.25,
# _WEIGHT_COMMITS=0.10, _WEIGHT_FRICTION=0.10; the clamp [0.05, 0.95] — never
# fully certain, never zero. usage_revenue = runtime_event_count *
# _REVENUE_PER_REQUEST (0.001) is resolved before dispatch; the kernel receives
# it as a scalar. The residual work is booleans-over-records and filtering. They
# are named so they can move native next, not so they stay outside. Kernel-only
# via serve_via_kernel; three-way (CPython/TS/Rust) value-parity is the gate.
# ---------------------------------------------------------------------------

class GroundedValueResponse(BaseModel):
    """GET /api/utils/grounded_value response — the value/realization/confidence outputs."""

    model_config = ConfigDict(extra="forbid")
    computed_actual_value: Annotated[
        float,
        Field(
            description="Strongest value signal = "
            "max(lineage_measured_value, usage_revenue, spec_actual_value_sum)"
        ),
    ]
    computed_estimated_cost: Annotated[
        float,
        Field(description="max(spec_estimated_cost_sum, lineage_estimated_cost)"),
    ]
    value_realization_pct: Annotated[
        float,
        Field(
            description="min(computed_actual_value / spec_potential_value_sum, 1.0) "
            "guarded by spec_potential_value_sum>0 (else 0.0)"
        ),
    ]
    computed_confidence: Annotated[
        float,
        Field(
            description="clamp(weighted coverage sum, 0.05, 0.95) — weights "
            "0.30/0.25/0.25/0.10/0.10 over the five has_* signals"
        ),
    ]
    runtime: Annotated[
        str,
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
    ]


@router.get(
    "/grounded_value",
    response_model=GroundedValueResponse,
    summary="The value/realization/confidence reduction of compute_idea_metrics, from host-derived scalars",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — the "
        "VALUE / REALIZATION / CONFIDENCE REDUCTION of "
        "grounded_idea_metrics_service.compute_idea_metrics. The SECOND and "
        "final numeric slice; with the grounded-cost reduction already serving "
        "(/api/utils/grounded_cost) this completes the function's COMPUTATION "
        "kernel-native. From the host-derived scalars for one idea it computes "
        "computed_actual_value = max(lineage_measured_value, usage_revenue, "
        "spec_actual_value_sum), computed_estimated_cost = "
        "max(spec_estimated_cost_sum, lineage_estimated_cost), "
        "value_realization_pct = min(value/potential, 1.0) guarded by "
        "potential>0, has_runtime_data/has_commits = min(1.0, count/N) guarded "
        "by count>0, and computed_confidence = clamp(weighted sum, 0.05, 0.95) "
        "with weights 0.30/0.25/0.25/0.10/0.10 (_WEIGHT_* read from source). The "
        "boolean-presence levels has_specs_with_data / has_lineage / has_friction "
        "(any(...)-over-records / len>0 ladders) and collection filtering are "
        "currently resolved before dispatch; they are visible next native work. "
        "Kernel-only via serve_via_kernel; three-way "
        "(CPython/TS/Rust) value-parity is the gate."
    ),
)
async def grounded_value(
    lineage_measured_value: Annotated[
        float,
        Query(description="Summed measured value across the idea's lineage valuations"),
    ] = 12.5,
    usage_revenue: Annotated[
        float,
        Query(description="runtime_event_count * _REVENUE_PER_REQUEST (0.001), resolved before dispatch"),
    ] = 0.007,
    spec_actual_value_sum: Annotated[
        float,
        Query(description="Summed actual_value across the idea's specs"),
    ] = 4.25,
    spec_estimated_cost_sum: Annotated[
        float,
        Query(description="Summed estimated_cost across the idea's specs"),
    ] = 6.75,
    lineage_estimated_cost: Annotated[
        float,
        Query(description="Summed estimated_cost across the idea's lineage links"),
    ] = 5.5,
    spec_potential_value_sum: Annotated[
        float,
        Query(description="Summed potential_value across the specs — the realization denominator"),
    ] = 20.0,
    runtime_event_count: Annotated[
        int,
        Query(description="Raw runtime event count — the kernel runs min(1.0, count/10.0) with a zero-guard"),
    ] = 7,
    commit_count: Annotated[
        int,
        Query(description="Raw commit count — the kernel runs min(1.0, count/5.0) with a zero-guard"),
    ] = 3,
    has_specs_with_data: Annotated[
        float,
        Query(
            description="Host-resolved spec-data level (any(actual_cost>0 or "
            "actual_value>0) → 1.0; else 0.5 if specs present; else 0.0)"
        ),
    ] = 1.0,
    has_lineage: Annotated[
        float,
        Query(
            description="Host-resolved lineage level (lineage_measured_value>0 → "
            "1.0; else 0.5 if links present; else 0.0)"
        ),
    ] = 1.0,
    has_friction: Annotated[
        float,
        Query(
            description="Host-resolved friction level (friction_cost_of_delay>0 → "
            "1.0; else 0.3 if friction events present; else 0.0)"
        ),
    ] = 0.3,
) -> GroundedValueResponse:
    bindings = {
        "lineage_measured_value": lineage_measured_value,
        "usage_revenue": usage_revenue,
        "spec_actual_value_sum": spec_actual_value_sum,
        "spec_estimated_cost_sum": spec_estimated_cost_sum,
        "lineage_estimated_cost": lineage_estimated_cost,
        "spec_potential_value_sum": spec_potential_value_sum,
        "runtime_event_count": runtime_event_count,
        "commit_count": commit_count,
        "has_specs_with_data": has_specs_with_data,
        "has_lineage": has_lineage,
        "has_friction": has_friction,
    }
    outputs, kernel_runtime = serve_via_kernel(
        "endpoint_grounded_value_demo.fk",
        bindings=bindings,
        parse=_coerce_float_list,
    )
    return GroundedValueResponse(
        computed_actual_value=outputs[0],
        computed_estimated_cost=outputs[1],
        value_realization_pct=outputs[2],
        computed_confidence=outputs[3],
        runtime=kernel_runtime,
    )
