"""Creator resonance report scoring.

The scoring is directional, not predictive. It separates attention,
engagement, conversion, relationship, and income so a creator can see
where effort created movement and where the next measurement belongs.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from app.models.creator_resonance import (
    CreatorDimensionScore,
    CreatorMetricSnapshot,
    CreatorPlatformSnapshot,
    CreatorPlatformSummary,
    CreatorReportAnswer,
    CreatorReportRecommendation,
    CreatorResonanceReport,
    CreatorResonanceReportRequest,
)


METRIC_FIELDS = tuple(CreatorMetricSnapshot.model_fields.keys())

DIMENSIONS: dict[str, tuple[tuple[str, ...], float, float]] = {
    "attention": (("reach", "impressions", "views", "listeners"), 0.20, 5000.0),
    "engagement": (("likes", "saves", "shares", "comments"), 0.25, 500.0),
    "conversion": (
        (
            "profile_visits",
            "link_clicks",
            "streams",
            "playlist_adds",
            "pre_saves",
            "merch_clicks",
            "ticket_clicks",
        ),
        0.25,
        1000.0,
    ),
    "relationship": (("followers", "new_followers", "subscriptions"), 0.15, 500.0),
    "income": (("revenue_usd",), 0.15, 250.0),
}


def build_creator_resonance_report(
    request: CreatorResonanceReportRequest,
    *,
    now: datetime | None = None,
) -> CreatorResonanceReport:
    generated_at = now or datetime.now(timezone.utc)
    by_platform = _group_by_platform(request.snapshots)
    summaries = [
        _summarize_platform(platform, rows)
        for platform, rows in sorted(by_platform.items())
    ]
    dimensions = _score_dimensions(summaries)

    current_totals = {
        name: sum(summary.current.get(metric, 0.0) for summary in summaries for metric in metrics)
        for name, (metrics, _weight, _scale) in DIMENSIONS.items()
    }
    attention_total = current_totals["attention"]
    engagement_total = current_totals["engagement"]
    conversion_total = current_totals["conversion"]
    relationship_total = current_totals["relationship"]
    income_usd = current_totals["income"]
    cost_usd = round(sum(item.amount_usd for item in request.costs), 4)
    net_income_usd = round(income_usd - cost_usd, 4)
    engagement_rate = _rate(engagement_total, attention_total)
    conversion_rate = _rate(conversion_total, attention_total)

    confidence = _confidence(request.snapshots, summaries)
    resonance_score = round(
        sum(item.score * item.weight for item in dimensions) * confidence,
        4,
    )
    evidence_gaps = _evidence_gaps(request, summaries)
    proof_quality = _proof_quality(confidence, request.snapshots, income_usd, conversion_total)
    recommendations = _recommendations(
        summaries=summaries,
        dimensions=dimensions,
        income_usd=income_usd,
        cost_usd=cost_usd,
        evidence_gaps=evidence_gaps,
    )
    answer = _answer(
        resonance_score=resonance_score,
        confidence=confidence,
        income_usd=income_usd,
        conversion_total=conversion_total,
        evidence_gaps=evidence_gaps,
        recommendations=recommendations,
    )

    return CreatorResonanceReport(
        report_id=_report_id(request),
        generated_at=generated_at,
        artist_name=request.artist_name,
        campaign_title=request.campaign_title,
        answer=answer,
        proof_quality=proof_quality,
        resonance_score=resonance_score,
        confidence=confidence,
        attention_total=round(attention_total, 4),
        engagement_total=round(engagement_total, 4),
        conversion_total=round(conversion_total, 4),
        relationship_total=round(relationship_total, 4),
        income_usd=round(income_usd, 4),
        cost_usd=cost_usd,
        net_income_usd=net_income_usd,
        engagement_rate=engagement_rate,
        conversion_rate=conversion_rate,
        platform_summaries=summaries,
        dimensions=dimensions,
        recommendations=recommendations,
        validation_plan=_validation_plan(request),
        evidence_gaps=evidence_gaps,
        sources=_sources(request.snapshots),
        truth_boundary=(
            "Report uses submitted platform snapshots only; it does not claim "
            "direct platform authentication unless an evidence source says so."
        ),
    )


def _group_by_platform(
    snapshots: Iterable[CreatorPlatformSnapshot],
) -> dict[str, list[CreatorPlatformSnapshot]]:
    grouped: dict[str, list[CreatorPlatformSnapshot]] = defaultdict(list)
    for item in snapshots:
        grouped[_normalize_platform(item.platform)].append(item)
    return grouped


def _summarize_platform(
    platform: str,
    rows: list[CreatorPlatformSnapshot],
) -> CreatorPlatformSummary:
    baseline = _sum_metrics(row.metrics for row in rows if row.kind == "baseline")
    current = _sum_metrics(row.metrics for row in rows if row.kind != "baseline")
    delta = {field: round(current[field] - baseline[field], 4) for field in METRIC_FIELDS}
    strongest = max(delta.items(), key=lambda item: item[1])[0] if delta else None
    evidence_count = sum(
        1 for row in rows if row.source_label or row.evidence_url or row.captured_at
    )
    return CreatorPlatformSummary(
        platform=platform,
        baseline=_trim_zeroes(baseline),
        current=_trim_zeroes(current),
        delta=_trim_zeroes(delta),
        strongest_metric=strongest if strongest and delta.get(strongest, 0.0) > 0 else None,
        evidence_count=evidence_count,
    )


def _score_dimensions(
    summaries: list[CreatorPlatformSummary],
) -> list[CreatorDimensionScore]:
    scored: list[CreatorDimensionScore] = []
    for name, (metrics, weight, scale) in DIMENSIONS.items():
        baseline = sum(
            summary.baseline.get(metric, 0.0)
            for summary in summaries
            for metric in metrics
        )
        current = sum(
            summary.current.get(metric, 0.0)
            for summary in summaries
            for metric in metrics
        )
        lift = _lift(baseline, current)
        score = _dimension_score(baseline, current, scale)
        scored.append(
            CreatorDimensionScore(
                name=name,
                score=score,
                baseline_total=round(baseline, 4),
                current_total=round(current, 4),
                lift=round(lift, 4),
                weight=weight,
                metrics=list(metrics),
            )
        )
    return scored


def _sum_metrics(rows: Iterable[CreatorMetricSnapshot]) -> dict[str, float]:
    totals = {field: 0.0 for field in METRIC_FIELDS}
    for row in rows:
        data = row.model_dump()
        for field in METRIC_FIELDS:
            totals[field] += float(data.get(field) or 0.0)
    return {field: round(value, 4) for field, value in totals.items()}


def _trim_zeroes(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 4) for key, value in values.items() if abs(value) > 0.00001}


def _dimension_score(baseline: float, current: float, scale: float) -> float:
    if current <= 0 and baseline <= 0:
        return 0.0
    volume = current / (current + scale) if current > 0 else 0.0
    if baseline <= 0:
        return round(min(1.0, volume * 0.70), 4)
    positive_lift = max(0.0, current - baseline) / max(baseline, scale)
    movement = positive_lift / (1.0 + positive_lift)
    return round(min(1.0, (0.55 * volume) + (0.45 * movement)), 4)


def _lift(baseline: float, current: float) -> float:
    if baseline <= 0:
        return current if current > 0 else 0.0
    return (current - baseline) / baseline


def _rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _confidence(
    snapshots: list[CreatorPlatformSnapshot],
    summaries: list[CreatorPlatformSummary],
) -> float:
    platform_count = len(summaries)
    has_baseline = any(row.kind == "baseline" for row in snapshots)
    has_current = any(row.kind != "baseline" for row in snapshots)
    evidence_ratio = sum(summary.evidence_count for summary in summaries) / max(len(snapshots), 1)
    nonzero_density = _nonzero_density(snapshots)
    score = 0.20
    score += min(platform_count, 3) * 0.10
    score += 0.20 if has_baseline and has_current else 0.0
    score += min(evidence_ratio, 1.0) * 0.20
    score += nonzero_density * 0.10
    return round(max(0.0, min(1.0, score)), 4)


def _nonzero_density(snapshots: list[CreatorPlatformSnapshot]) -> float:
    total = len(snapshots) * len(METRIC_FIELDS)
    if total == 0:
        return 0.0
    nonzero = 0
    for row in snapshots:
        data = row.metrics.model_dump()
        nonzero += sum(1 for value in data.values() if float(value or 0.0) > 0)
    return min(1.0, nonzero / total * 4.0)


def _proof_quality(
    confidence: float,
    snapshots: list[CreatorPlatformSnapshot],
    income_usd: float,
    conversion_total: float,
) -> str:
    has_baseline = any(row.kind == "baseline" for row in snapshots)
    has_current = any(row.kind != "baseline" for row in snapshots)
    has_value_signal = income_usd > 0 or conversion_total > 0
    if confidence >= 0.75 and has_baseline and has_current and has_value_signal:
        return "strong"
    if confidence >= 0.55 and has_current and has_value_signal:
        return "emerging"
    if confidence >= 0.35:
        return "thin"
    return "unproven"


def _evidence_gaps(
    request: CreatorResonanceReportRequest,
    summaries: list[CreatorPlatformSummary],
) -> list[str]:
    gaps: list[str] = []
    if not any(row.kind == "baseline" for row in request.snapshots):
        gaps.append("Add a baseline snapshot from before the campaign window.")
    if not any(row.kind != "baseline" for row in request.snapshots):
        gaps.append("Add a current snapshot from the end of the campaign window.")
    for summary in summaries:
        if summary.evidence_count == 0:
            gaps.append(f"Attach an evidence source for {summary.platform}.")
    if not request.artifacts:
        gaps.append("List the posts, tracks, reels, clips, or offers that carried the campaign.")
    if not any(summary.current.get("revenue_usd", 0.0) > 0 for summary in summaries):
        gaps.append("Add revenue, payout, merch, ticket, or support data when money moves.")
    return gaps


def _recommendations(
    *,
    summaries: list[CreatorPlatformSummary],
    dimensions: list[CreatorDimensionScore],
    income_usd: float,
    cost_usd: float,
    evidence_gaps: list[str],
) -> list[CreatorReportRecommendation]:
    recommendations: list[CreatorReportRecommendation] = []
    dimension_by_name = {item.name: item for item in dimensions}
    engagement = dimension_by_name["engagement"].current_total
    conversion = dimension_by_name["conversion"].current_total
    attention = dimension_by_name["attention"].current_total

    if evidence_gaps:
        recommendations.append(
            CreatorReportRecommendation(
                priority="proof",
                reason="The report can move from thin signal to validation when the missing evidence is attached.",
                action=evidence_gaps[0],
                expected_signal="Higher confidence and clearer before/after comparison.",
            )
        )

    if attention > 0 and engagement / max(attention, 1.0) >= 0.03 and conversion / max(attention, 1.0) < 0.01:
        recommendations.append(
            CreatorReportRecommendation(
                priority="conversion",
                reason="People are reacting, saving, or sharing more than they are taking the next step.",
                action="Give the highest-engagement post one clear next destination: pre-save, listen, join, buy, or RSVP.",
                expected_signal="Lift in link clicks, pre-saves, playlist adds, ticket clicks, or support revenue.",
            )
        )

    instagram = _platform(summaries, "instagram")
    spotify = _platform(summaries, "spotify")
    if instagram and spotify and instagram.current.get("saves", 0.0) + instagram.current.get("shares", 0.0) > spotify.current.get("playlist_adds", 0.0):
        recommendations.append(
            CreatorReportRecommendation(
                priority="reuse",
                reason="Instagram is showing save/share resonance that can feed the listening path.",
                action="Turn the saved visual/story into the Spotify-facing release assets and link route.",
                expected_signal="Lift in streams, saves, playlist adds, and listener conversion.",
            )
        )

    if income_usd <= cost_usd and conversion > 0:
        recommendations.append(
            CreatorReportRecommendation(
                priority="income",
                reason="Conversion exists, but spendable value is not yet covering the campaign cost.",
                action="Attach one priced creator offer to the campaign: a download, private drop, ticket, lesson, commission, or supporter tier.",
                expected_signal="Measured revenue per 1000 attention and positive net income.",
            )
        )

    if not recommendations:
        recommendations.append(
            CreatorReportRecommendation(
                priority="next",
                reason="The current report has enough signal to run one sharper experiment.",
                action="Repeat the strongest artifact with one changed variable and capture baseline/current snapshots.",
                expected_signal="Cleaner lift attribution by platform and artifact.",
            )
        )
    return recommendations[:4]


def _answer(
    *,
    resonance_score: float,
    confidence: float,
    income_usd: float,
    conversion_total: float,
    evidence_gaps: list[str],
    recommendations: list[CreatorReportRecommendation],
) -> CreatorReportAnswer:
    can_generate = resonance_score > 0 or conversion_total > 0 or income_usd > 0
    can_validate = confidence >= 0.55 and not any("baseline" in gap.lower() for gap in evidence_gaps)
    can_show_income = income_usd > 0
    if can_show_income:
        status = "income_signal_present"
    elif can_validate:
        status = "attention_generation_validated_income_needed"
    elif can_generate:
        status = "attention_signal_present_validation_needed"
    else:
        status = "input_signal_needed"
    next_action = recommendations[0].action if recommendations else "Capture baseline and current snapshots."
    return CreatorReportAnswer(
        can_generate_attention_value=can_generate,
        can_validate_generation=can_validate,
        can_show_income=can_show_income,
        status=status,
        healthiest_next_execution=next_action,
    )


def _validation_plan(request: CreatorResonanceReportRequest) -> list[str]:
    platforms = ", ".join(sorted({_normalize_platform(row.platform) for row in request.snapshots}))
    plan = [
        f"Capture baseline and current snapshots for: {platforms}.",
        "Track attention, engagement, conversion, relationship, and income as separate dimensions.",
        "Record every campaign artifact that carried the audience from social attention to owned relation or payment.",
        "Compare the next campaign against this report_id and keep the same metric names.",
    ]
    if request.desired_outcomes:
        plan.append("Validate against declared outcomes: " + ", ".join(request.desired_outcomes[:6]) + ".")
    return plan


def _sources(snapshots: list[CreatorPlatformSnapshot]) -> list[str]:
    sources: list[str] = []
    for row in snapshots:
        if row.source_label:
            sources.append(f"{_normalize_platform(row.platform)}: {row.source_label}")
        elif row.evidence_url:
            sources.append(f"{_normalize_platform(row.platform)}: {row.evidence_url}")
        else:
            sources.append(f"{_normalize_platform(row.platform)}: submitted snapshot")
    return list(dict.fromkeys(sources))


def _report_id(request: CreatorResonanceReportRequest) -> str:
    payload = request.model_dump(mode="json")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "creator-resonance:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _normalize_platform(platform: str) -> str:
    return platform.strip().lower().replace(" ", "-")


def _platform(
    summaries: list[CreatorPlatformSummary],
    name: str,
) -> CreatorPlatformSummary | None:
    normalized = _normalize_platform(name)
    for summary in summaries:
        if summary.platform == normalized:
            return summary
    return None
