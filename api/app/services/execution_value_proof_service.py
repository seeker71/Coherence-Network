"""Compose execution, grounded value, and paid-read income proof."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.models.execution_value import (
    ExecutionProofSummary,
    ExecutionValueAnswer,
    ExecutionValueProofResponse,
    ExecutionValueSource,
    GroundedValueProofSummary,
    IdeaValueSlice,
    IncomeProofSummary,
    NutritionProofSummary,
)
from app.services import (
    agent_service,
    cc_economics_service,
    grounded_idea_metrics_service,
    idea_service,
    metrics_service,
    settlement_service,
    value_lineage_service,
)


def build_execution_value_proof(
    *,
    window_days: int = 30,
    daily_nutrition_usd: float | None = None,
) -> ExecutionValueProofResponse:
    """Build the public proof from existing measured services."""
    now = datetime.now(timezone.utc)
    window_days = max(1, min(int(window_days), 90))
    sources: list[ExecutionValueSource] = []

    execution = collect_execution_summary(window_days, now, sources)

    data = _collect_grounded_data(sources)
    idea_ids = collect_idea_ids(data, sources)
    value = summarize_grounded_value(idea_ids, data)

    paid_events = _collect_paid_read_events(window_days, now, sources)
    settled_cc = _collect_settled_cc(window_days, now, sources)
    cc_per_usd = _collect_cc_per_usd(sources)
    income = summarize_income(
        paid_events=paid_events,
        settled_cc=settled_cc,
        cc_per_usd=cc_per_usd,
    )
    nutrition = summarize_nutrition(
        income=income,
        daily_nutrition_usd=daily_nutrition_usd,
    )
    answer = answer_from_summaries(
        execution=execution,
        value=value,
        income=income,
        nutrition=nutrition,
    )

    return ExecutionValueProofResponse(
        generated_at=now,
        window_days=window_days,
        answer=answer,
        execution=execution,
        value=value,
        income=income,
        nutrition=nutrition,
        sources=sources,
    )


def collect_execution_summary(
    window_days: int,
    now: datetime,
    sources: list[ExecutionValueSource] | None = None,
) -> ExecutionProofSummary:
    metrics = metrics_service.get_aggregates(window_days=window_days)
    success = metrics.get("success_rate", {}) if isinstance(metrics, dict) else {}
    timing = metrics.get("execution_time", {}) if isinstance(metrics, dict) else {}

    metric_completed = _safe_int(success, "completed")
    metric_failed = _safe_int(success, "failed")
    metric_terminal = _safe_int(success, "total")
    metric_rate = _safe_float(success, "rate")

    task_completed = 0
    task_failed = 0
    task_running = 0
    task_pending = 0
    task_total = 0
    runtime_backfill = 0
    cutoff = now - timedelta(days=window_days)
    try:
        tasks, _total, runtime_backfill = agent_service.list_tasks(limit=5000, offset=0)
        for task in tasks:
            task_created = _coerce_datetime(_safe_get(task, "created_at"))
            if task_created is not None and task_created < cutoff:
                continue
            task_total += 1
            status = _status_value(_safe_get(task, "status"))
            if status == "completed":
                task_completed += 1
            elif status in {"failed", "timed_out"}:
                task_failed += 1
            elif status == "running":
                task_running += 1
            elif status == "pending":
                task_pending += 1
    except Exception as exc:
        if sources is not None:
            sources.append(
                ExecutionValueSource(
                    name="agent_tasks",
                    status="error",
                    details={"error": exc.__class__.__name__},
                )
            )
    else:
        if sources is not None:
            sources.append(
                ExecutionValueSource(
                    name="agent_tasks",
                    status="measured",
                    details={"windowed_task_count": task_total},
                )
            )

    completed = metric_completed if metric_terminal > 0 else task_completed
    failed = metric_failed if metric_terminal > 0 else task_failed
    terminal = completed + failed
    tasks_total = max(metric_terminal, task_total, terminal)
    success_rate = metric_rate if metric_terminal > 0 else (
        round(completed / terminal, 4) if terminal > 0 else 0.0
    )
    if sources is not None:
        sources.append(
            ExecutionValueSource(
                name="task_metrics",
                status="measured" if metric_terminal > 0 else "empty",
                details={"terminal_tasks": metric_terminal},
            )
        )

    return ExecutionProofSummary(
        tasks_total=tasks_total,
        terminal_tasks=terminal,
        completed=completed,
        failed=failed,
        running=task_running,
        pending=task_pending,
        success_rate=max(0.0, min(1.0, float(success_rate))),
        p50_seconds=_safe_int(timing, "p50_seconds"),
        p95_seconds=_safe_int(timing, "p95_seconds"),
        runtime_backfill_count=max(0, int(runtime_backfill)),
    )


def collect_idea_ids(
    data: dict[str, Any],
    sources: list[ExecutionValueSource] | None = None,
) -> list[str]:
    idea_ids: set[str] = set()
    try:
        idea_ids.update(str(item) for item in idea_service.list_tracked_idea_ids() if item)
        if sources is not None:
            sources.append(
                ExecutionValueSource(
                    name="idea_registry",
                    status="measured",
                    details={"tracked_ideas": len(idea_ids)},
                )
            )
    except Exception as exc:
        if sources is not None:
            sources.append(
                ExecutionValueSource(
                    name="idea_registry",
                    status="error",
                    details={"error": exc.__class__.__name__},
                )
            )

    for field in ("specs", "runtime_summaries", "lineage_links", "friction_events"):
        for item in data.get(field, []) or []:
            idea_id = str(_safe_get(item, "idea_id", "") or "").strip()
            if idea_id:
                idea_ids.add(idea_id)

    for record in data.get("commit_records", []) or []:
        for idea_id in _commit_idea_ids(record):
            if idea_id:
                idea_ids.add(idea_id)

    return sorted(idea_ids)


def summarize_grounded_value(
    idea_ids: list[str],
    data: dict[str, Any],
) -> GroundedValueProofSummary:
    metrics = grounded_idea_metrics_service.compute_all_idea_metrics(idea_ids, **data)
    slices: list[IdeaValueSlice] = []
    for item in metrics:
        value = _safe_float(item, "computed_actual_value")
        cost = _safe_float(item, "computed_actual_cost")
        roi = round(value / cost, 4) if cost > 0 else None
        slices.append(
            IdeaValueSlice(
                idea_id=str(item.get("idea_id") or ""),
                measured_value_usd=round(value, 4),
                measured_cost_usd=round(cost, 4),
                net_value_usd=round(value - cost, 4),
                roi_ratio=roi,
                confidence=max(0.0, min(1.0, _safe_float(item, "computed_confidence"))),
                grounding_sources=item.get("grounding_sources", {}),
            )
        )

    measured_value = round(sum(item.measured_value_usd for item in slices), 4)
    measured_cost = round(sum(item.measured_cost_usd for item in slices), 4)
    roi = round(measured_value / measured_cost, 4) if measured_cost > 0 else None
    if slices and measured_value > 0:
        confidence = sum(
            item.confidence * item.measured_value_usd for item in slices
        ) / measured_value
    elif slices:
        confidence = sum(item.confidence for item in slices) / len(slices)
    else:
        confidence = 0.0

    top_ideas = sorted(
        slices,
        key=lambda item: (item.net_value_usd, item.measured_value_usd),
        reverse=True,
    )[:10]
    return GroundedValueProofSummary(
        ideas_count=len(slices),
        ideas_with_value=sum(1 for item in slices if item.measured_value_usd > 0),
        measured_value_usd=measured_value,
        measured_cost_usd=measured_cost,
        net_value_usd=round(measured_value - measured_cost, 4),
        roi_ratio=roi,
        confidence=round(max(0.0, min(1.0, confidence)), 4),
        top_ideas=top_ideas,
    )


def summarize_income(
    *,
    paid_events: list[Any],
    settled_cc: float,
    cc_per_usd: float | None,
) -> IncomeProofSummary:
    paid_cc = round(sum(_event_cc_amount(event) for event in paid_events), 6)
    paid_asset_count = len(
        {
            str(_safe_get(event, "asset_id", "") or "")
            for event in paid_events
            if str(_safe_get(event, "asset_id", "") or "").strip()
        }
    )
    estimated_usd = None
    if cc_per_usd is not None and cc_per_usd > 0:
        estimated_usd = round(paid_cc / cc_per_usd, 6)

    income_proven = len(paid_events) > 0 and paid_cc > 0
    proof_level = "none"
    if income_proven and settled_cc > 0:
        proof_level = "paid_read_and_settled_cc_measured"
    elif income_proven:
        proof_level = "paid_read_cc_measured"
    elif settled_cc > 0:
        proof_level = "settled_cc_measured"

    notes: list[str] = []
    if estimated_usd is not None:
        notes.append("estimated_paid_read_usd uses the current CC oracle midpoint")
    if income_proven:
        notes.append("paid reads prove CC-denominated income, not spendable fiat")

    return IncomeProofSummary(
        paid_read_count=len(paid_events),
        paid_asset_count=paid_asset_count,
        paid_read_cc=paid_cc,
        settled_cc=round(float(settled_cc), 6),
        estimated_paid_read_usd=estimated_usd,
        cc_per_usd=cc_per_usd,
        spendable_fiat_usd=0.0,
        income_proven=income_proven or settled_cc > 0,
        spendable_income_proven=False,
        proof_level=proof_level,
        offramp_status="not_observed_in_current_runtime",
        notes=notes,
    )


def summarize_nutrition(
    *,
    income: IncomeProofSummary,
    daily_nutrition_usd: float | None,
) -> NutritionProofSummary:
    if daily_nutrition_usd is None or daily_nutrition_usd <= 0:
        return NutritionProofSummary()
    target = float(daily_nutrition_usd)
    estimated_cc_days = None
    if income.estimated_paid_read_usd is not None:
        estimated_cc_days = round(income.estimated_paid_read_usd / target, 4)
    spendable_days = round(income.spendable_fiat_usd / target, 4)
    return NutritionProofSummary(
        daily_nutrition_usd=round(target, 4),
        covered_days_by_spendable_fiat=spendable_days,
        covered_days_by_estimated_cc=estimated_cc_days,
        can_cover_nutrition=spendable_days >= 1.0,
    )


def answer_from_summaries(
    *,
    execution: ExecutionProofSummary,
    value: GroundedValueProofSummary,
    income: IncomeProofSummary,
    nutrition: NutritionProofSummary,
) -> ExecutionValueAnswer:
    can_generate_value = value.measured_value_usd > 0 or income.income_proven
    can_cover = nutrition.can_cover_nutrition

    if not can_generate_value:
        status = "needs_measured_usage"
        next_execution = "route the next execution through a measured idea, runtime, and lineage path"
    elif not income.income_proven:
        status = "execution_value_proven_income_signal_needed"
        next_execution = "attach the highest-value executed surface to a paid read or settlement event"
    elif not income.spendable_income_proven:
        status = "paid_cc_income_proven_offramp_needed"
        next_execution = "close one CC-to-spendable-fiat settlement record before treating it as nutrition funding"
    elif can_cover is False:
        status = "spendable_income_proven_below_nutrition_target"
        next_execution = "increase paid usage on the top grounded idea before widening scope"
    else:
        status = "nutrition_cover_proven"
        next_execution = "compound the top grounded route and preserve the same evidence path"

    if execution.terminal_tasks == 0 and not can_generate_value:
        next_execution = "complete one measurable execution before optimizing the income loop"

    return ExecutionValueAnswer(
        can_generate_value_with_execution=can_generate_value,
        can_prove_income=income.income_proven,
        can_cover_nutrition=can_cover,
        status=status,
        healthiest_next_execution=next_execution,
    )


def _collect_grounded_data(sources: list[ExecutionValueSource]) -> dict[str, Any]:
    try:
        data = grounded_idea_metrics_service.collect_all_data()
    except Exception as exc:
        sources.append(
            ExecutionValueSource(
                name="grounded_idea_metrics",
                status="error",
                details={"error": exc.__class__.__name__},
            )
        )
        return {
            "specs": [],
            "runtime_summaries": [],
            "lineage_links": [],
            "lineage_valuations": {},
            "commit_records": [],
            "friction_events": [],
        }
    sources.append(
        ExecutionValueSource(
            name="grounded_idea_metrics",
            status="measured",
            details={
                "specs": len(data.get("specs", []) or []),
                "runtime_summaries": len(data.get("runtime_summaries", []) or []),
                "lineage_links": len(data.get("lineage_links", []) or []),
                "commit_records": len(data.get("commit_records", []) or []),
                "friction_events": len(data.get("friction_events", []) or []),
            },
        )
    )
    return data


def _collect_paid_read_events(
    window_days: int,
    now: datetime,
    sources: list[ExecutionValueSource],
) -> list[Any]:
    since = now - timedelta(days=window_days)
    try:
        events = value_lineage_service.query_read_events(since=since)
    except Exception as exc:
        sources.append(
            ExecutionValueSource(
                name="value_lineage_read_events",
                status="error",
                details={"error": exc.__class__.__name__},
            )
        )
        return []
    paid = [event for event in events if _is_paid_event(event)]
    sources.append(
        ExecutionValueSource(
            name="value_lineage_read_events",
            status="measured" if paid else "empty",
            details={"read_events": len(events), "paid_read_events": len(paid)},
        )
    )
    return paid


def _collect_settled_cc(
    window_days: int,
    now: datetime,
    sources: list[ExecutionValueSource],
) -> float:
    cutoff = (now - timedelta(days=window_days)).date()
    try:
        batches = settlement_service.list_batches()
    except Exception as exc:
        sources.append(
            ExecutionValueSource(
                name="settlement_batches",
                status="error",
                details={"error": exc.__class__.__name__},
            )
        )
        return 0.0
    total = Decimal("0")
    count = 0
    for batch in batches:
        batch_date = _safe_get(batch, "batch_date")
        if batch_date is not None and batch_date < cutoff:
            continue
        total += Decimal(str(_safe_get(batch, "total_cc_distributed", 0) or 0))
        count += 1
    sources.append(
        ExecutionValueSource(
            name="settlement_batches",
            status="measured" if count else "empty",
            details={"batch_count": count},
        )
    )
    return float(total)


def _collect_cc_per_usd(sources: list[ExecutionValueSource]) -> float | None:
    try:
        rate = cc_economics_service.exchange_rate()
    except Exception as exc:
        sources.append(
            ExecutionValueSource(
                name="cc_economics_rate",
                status="error",
                details={"error": exc.__class__.__name__},
            )
        )
        return None
    if rate is None:
        sources.append(
            ExecutionValueSource(
                name="cc_economics_rate",
                status="unavailable",
                details={},
            )
        )
        return None
    cc_per_usd = _safe_float(rate, "cc_per_usd")
    sources.append(
        ExecutionValueSource(
            name="cc_economics_rate",
            status="estimated",
            details={"cc_per_usd": cc_per_usd, "oracle_source": _safe_get(rate, "oracle_source")},
        )
    )
    return cc_per_usd if cc_per_usd > 0 else None


def _is_paid_event(event: Any) -> bool:
    return (
        str(_safe_get(event, "read_type", "") or "").lower() == "paid"
        or bool(_safe_get(event, "payment_token"))
        or _event_cc_amount(event) > 0
    )


def _event_cc_amount(event: Any) -> float:
    cc_amount = _safe_float(event, "cc_amount")
    if cc_amount > 0:
        return cc_amount
    return _safe_float(event, "value")


def _commit_idea_ids(record: dict[str, Any]) -> list[str]:
    if not isinstance(record, dict):
        return []
    raw = record.get("idea_ids")
    if not raw and isinstance(record.get("payload"), dict):
        raw = record["payload"].get("idea_ids")
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    return []


def _safe_get(obj: Any, field: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)


def _safe_float(obj: Any, field: str) -> float:
    value = _safe_get(obj, field, 0.0)
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _safe_int(obj: Any, field: str) -> int:
    value = _safe_get(obj, field, 0)
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _status_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value or "")
