"""Transmuted /api/utils entropy / breath-balance endpoints (bodies run as Form recipes).

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
    Query,
    _coerce_float_list,
    router,
    serve_via_kernel,
)

# ---------------------------------------------------------------------------
# Endpoint: /api/utils/breath_balance
#
# Pure computation: normalized Shannon entropy H / H_max over three phase
# counts (gas / water / ice), H_max = ln(3). The substrate's breath-rhythm
# balance signal — 1.0 for equal thirds, -0.0 (zero) for a single phase.
# Shares the breath-rhythm arithmetic used by vitality_service. This is the first kernel-served
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
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
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
        "p>0 guard is the log-of-zero guard. Kernel-only via "
        "serve_via_kernel; CPython==Rust value-parity is the gate."
    ),
)
async def breath_balance(
    gas: Annotated[int, Query(ge=0, description="Gas-phase count")] = 1,
    water: Annotated[int, Query(ge=0, description="Water-phase count")] = 1,
    ice: Annotated[int, Query(ge=0, description="Ice-phase count")] = 1,
) -> BreathBalanceResponse:
    balance, runtime = serve_via_kernel(
        "endpoint_breath_balance_demo.fk",
        bindings={"gas": gas, "water": water, "ice": ice},
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
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
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
        "guard is the log-of-zero guard. Kernel-only via serve_via_kernel; "
        "CPython==Rust value-parity is the gate."
    ),
)
async def shannon_entropy(
    gas: Annotated[int, Query(ge=0, description="Gas-phase count")] = 1,
    water: Annotated[int, Query(ge=0, description="Water-phase count")] = 1,
    ice: Annotated[int, Query(ge=0, description="Ice-phase count")] = 1,
) -> ShannonEntropyResponse:
    entropy, runtime = serve_via_kernel(
        "endpoint_shannon_entropy_demo.fk",
        bindings={"gas": gas, "water": water, "ice": ice},
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
# Endpoint: /api/utils/coherence_summary_score
#
# COVERAGE/SCORE REDUCTION of collective_health_service._coherence_summary,
# transmuted to a Form recipe. Another per-slice scoring transmutation built
# entirely from banked capabilities — the guarded ratio, the neutral-score
# guard, the two-sided clamp, and round_ndigits — folded into the collective-
# health domain. It uses existing kernel capabilities.
#
# Current decomposition. _coherence_summary derives, over the task list:
#   (a) the COUNTS — task_count, target_state_count, evidence_count,
#       task_card_count, and the task_card_scores list (its sum + len). Each is
#       produced by walking the heterogeneous `context` dicts on each task and
#       counting / accumulating presence conditions (target_state_contract is a
#       dict, success/abort evidence present, task_card_validation present with
#       its clamped score). This dict-walk over a collection is currently
#       precomputed before dispatch; it is next native work, not protected
#       architecture.
#   (b) the NUMERIC REDUCTION — given those counts, the four guarded coverage
#       ratios (each over task_count; quality over the scores len), the
#       weighted-sum score with the task_count==0 neutral guard and the
#       [0.0, 1.0] clamp, and round(_, 4) on each output. This route runs (b).
#
# Given the precomputed counts the recipe computes EXACTLY what
# _coherence_summary computes (verified against the source — _safe_ratio's guard
# `denominator <= 0 -> default`, _score_with_neutral `task_count <= 0 -> 0.5
# else _clamp01`, the 0.35/0.30/0.20/0.15 weights, and round(_, 4)):
#   target_state_coverage = safe_ratio(target_state_count, task_count)
#   evidence_coverage      = safe_ratio(evidence_count, task_count)
#   task_card_coverage     = safe_ratio(task_card_count, task_count)
#   task_card_quality      = safe_ratio(task_card_scores_sum, task_card_scores_len)
#   score = 0.5 if task_count == 0 else clamp01(0.35*target_state_coverage
#       + 0.30*task_card_quality + 0.20*task_card_coverage + 0.15*evidence_coverage)
# The residual work is the heterogeneous dict/list walk that produces the
# counts. It is named here so it can move native next.
# Kernel-only via serve_via_kernel; three-way (CPython/TS/Rust) value-
# parity is the gate.
# ---------------------------------------------------------------------------

class CoherenceSummaryScoreResponse(BaseModel):
    """GET /api/utils/coherence_summary_score response — the coverage/score outputs."""

    model_config = ConfigDict(extra="forbid")
    score: Annotated[
        float,
        Field(
            description="0.5 if task_count==0 else clamp01(weighted coverage sum) "
            "— weights 0.35/0.30/0.20/0.15 over target/quality/card/evidence, round(_,4)"
        ),
    ]
    task_count: Annotated[int, Field(description="Precomputed count of tasks in the slice")]
    target_state_coverage: Annotated[
        float, Field(description="safe_ratio(target_state_count, task_count), round(_,4)")
    ]
    task_card_coverage: Annotated[
        float, Field(description="safe_ratio(task_card_count, task_count), round(_,4)")
    ]
    task_card_quality: Annotated[
        float,
        Field(description="safe_ratio(task_card_scores_sum, task_card_scores_len), round(_,4)"),
    ]
    evidence_coverage: Annotated[
        float, Field(description="safe_ratio(evidence_count, task_count), round(_,4)")
    ]
    runtime: Annotated[
        str,
        Field(description="Which kernel carrier computed the answer — 'inline' or 'subprocess'"),
    ]


@router.get(
    "/coherence_summary_score",
    response_model=CoherenceSummaryScoreResponse,
    summary="The coverage/score reduction of _coherence_summary, from precomputed counts",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe — the "
        "COVERAGE/SCORE REDUCTION of collective_health_service._coherence_summary. "
        "From the precomputed counts it computes four guarded coverage ratios "
        "(target_state/evidence/task_card over task_count, quality over the "
        "task_card_scores len), a weighted-sum score (weights 0.35/0.30/0.20/0.15) "
        "with the task_count==0 neutral guard (0.5) and a [0.0, 1.0] clamp, and "
        "round(_, 4) on each output. The dict-walk over the task collection that "
        "produces the counts (heterogeneous `context` dicts, presence conditions) "
        "is currently precomputed before dispatch; it is visible next native work. "
        "Kernel-only via "
        "serve_via_kernel; three-way (CPython/TS/Rust) value-parity is the gate."
    ),
)
async def coherence_summary_score(
    task_count: Annotated[
        int, Query(description="Host-extracted count of tasks in the slice")
    ] = 10,
    target_state_count: Annotated[
        int, Query(description="Tasks whose context carries a target_state_contract dict")
    ] = 7,
    evidence_count: Annotated[
        int, Query(description="Tasks whose context carries success_evidence or abort_evidence")
    ] = 5,
    task_card_count: Annotated[
        int, Query(description="Tasks whose context.task_card_validation is present")
    ] = 6,
    task_card_scores_sum: Annotated[
        float, Query(description="Sum of the clamped task-card validation scores")
    ] = 4.5,
    task_card_scores_len: Annotated[
        int, Query(description="Count of task-card validation scores — the quality denominator")
    ] = 6,
) -> CoherenceSummaryScoreResponse:
    bindings = {
        "task_count": task_count,
        "target_state_count": target_state_count,
        "evidence_count": evidence_count,
        "task_card_count": task_card_count,
        "task_card_scores_sum": task_card_scores_sum,
        "task_card_scores_len": task_card_scores_len,
    }
    outputs, runtime = serve_via_kernel(
        "endpoint_coherence_summary_score_demo.fk",
        bindings=bindings,
        parse=_coerce_float_list,
    )
    return CoherenceSummaryScoreResponse(
        score=outputs[0],
        task_count=task_count,
        target_state_coverage=outputs[1],
        task_card_coverage=outputs[2],
        task_card_quality=outputs[3],
        evidence_coverage=outputs[4],
        runtime=runtime,
    )
