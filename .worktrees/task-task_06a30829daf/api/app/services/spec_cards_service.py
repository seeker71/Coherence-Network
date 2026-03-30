"""Specs cards feed builder for /api/spec-registry/cards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import quote

from app.models.spec_registry import SpecRegistryEntry

_CARD_ALLOWED_STATES = {"all", "unlinked", "linked", "in_progress", "implemented", "measured"}
_CARD_ALLOWED_ATTENTION = {"all", "none", "low", "medium", "high"}
_CARD_ALLOWED_SORTS = {
    "attention_desc",
    "roi_desc",
    "gap_desc",
    "state_desc",
    "updated_desc",
    "name_asc",
}
_CARD_DEFAULT_LIMIT = 50
_CARD_MAX_LIMIT = 200
_CARD_STATE_RANK = {
    "unlinked": 4,
    "linked": 3,
    "in_progress": 2,
    "implemented": 1,
    "measured": 0,
}


@dataclass
class EnrichedSpecRow:
    spec: SpecRegistryEntry
    state: str
    attention_level: str
    attention_score: int
    attention_reason: str | None
    links_count: int
    search_blob: str


@dataclass
class SpecCardsQuery:
    q: str
    state: str
    attention: str
    sort: str
    cursor: int
    limit: int
    linked: str
    min_roi: float | None
    min_value_gap: float | None


def _normalize_enum(value: str, *, allowed: set[str], fallback: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in allowed:
        return normalized
    return fallback


def _normalize_cursor(value: str | None) -> int:
    if value is None:
        return 0
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _normalize_limit(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return _CARD_DEFAULT_LIMIT
    if parsed < 1:
        return _CARD_DEFAULT_LIMIT
    return max(1, min(parsed, _CARD_MAX_LIMIT))


def _normalize_optional_float(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not parsed == parsed:  # NaN check
        return None
    return parsed


def normalize_query(
    *,
    q: str = "",
    state: str = "all",
    attention: str = "all",
    sort: str = "attention_desc",
    cursor: str | None = None,
    limit: int = _CARD_DEFAULT_LIMIT,
    linked: str = "all",
    min_roi: float | None = None,
    min_value_gap: float | None = None,
) -> SpecCardsQuery:
    return SpecCardsQuery(
        q=str(q or "").strip().lower(),
        state=_normalize_enum(state, allowed=_CARD_ALLOWED_STATES, fallback="all"),
        attention=_normalize_enum(attention, allowed=_CARD_ALLOWED_ATTENTION, fallback="all"),
        sort=_normalize_enum(sort, allowed=_CARD_ALLOWED_SORTS, fallback="attention_desc"),
        cursor=_normalize_cursor(cursor),
        limit=_normalize_limit(limit),
        linked=_normalize_enum(linked, allowed={"all", "linked", "unlinked"}, fallback="all"),
        min_roi=_normalize_optional_float(min_roi),
        min_value_gap=_normalize_optional_float(min_value_gap),
    )


def _derive_spec_state(spec: SpecRegistryEntry) -> str:
    has_idea = bool((spec.idea_id or "").strip())
    has_process = bool((spec.process_summary or "").strip() or (spec.pseudocode_summary or "").strip())
    has_implementation = bool((spec.implementation_summary or "").strip())
    has_measurement = float(spec.actual_value or 0.0) > 0.0 or float(spec.actual_cost or 0.0) > 0.0

    if not has_idea:
        return "unlinked"
    if has_measurement:
        return "measured"
    if has_implementation:
        return "implemented"
    if has_process:
        return "in_progress"
    return "linked"


def _derive_attention(spec: SpecRegistryEntry, *, state: str) -> tuple[str, int, str | None]:
    score = 0
    reasons: list[str] = []

    if state == "unlinked":
        score += 3
        reasons.append("missing idea link")

    value_gap = float(spec.value_gap or 0.0)
    if value_gap >= 10:
        score += 2
        reasons.append("large value gap")
    elif value_gap >= 5:
        score += 1
        reasons.append("value gap rising")

    actual_roi = float(spec.actual_roi or 0.0)
    estimated_roi = float(spec.estimated_roi or 0.0)
    if estimated_roi >= 3 and actual_roi < 1:
        score += 1
        reasons.append("actual roi below plan")

    missing_process = not bool((spec.process_summary or "").strip())
    missing_implementation = not bool((spec.implementation_summary or "").strip())
    if state in {"linked", "in_progress"} and missing_process:
        score += 1
        reasons.append("missing process summary")
    if state in {"linked", "in_progress", "implemented"} and missing_implementation:
        score += 1
        reasons.append("missing implementation notes")

    now_utc_naive = datetime.now(UTC).replace(tzinfo=None)
    age_days = (now_utc_naive - spec.updated_at.replace(tzinfo=None)).total_seconds() / 86400.0
    if age_days > 45:
        score += 1
        reasons.append("stale updates")

    if score >= 4:
        level = "high"
    elif score >= 2:
        level = "medium"
    elif score >= 1:
        level = "low"
    else:
        level = "none"

    reason = ", ".join(reasons[:2]) if reasons else None
    return level, score, reason


def _build_search_blob(spec: SpecRegistryEntry) -> str:
    fields = [
        spec.spec_id,
        spec.title,
        spec.summary,
        spec.idea_id or "",
        spec.created_by_contributor_id or "",
        spec.updated_by_contributor_id or "",
        spec.process_summary or "",
        spec.pseudocode_summary or "",
        spec.implementation_summary or "",
    ]
    return " ".join(fields).lower()


def _list_all_specs(list_specs_fn: Callable[[int, int], list[SpecRegistryEntry]]) -> list[SpecRegistryEntry]:
    rows: list[SpecRegistryEntry] = []
    offset = 0
    page_size = 1000
    while True:
        page = list_specs_fn(page_size, offset)
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += len(page)
    return rows


def _enrich_specs(specs: list[SpecRegistryEntry]) -> list[EnrichedSpecRow]:
    rows: list[EnrichedSpecRow] = []
    for spec in specs:
        state = _derive_spec_state(spec)
        attention_level, attention_score, attention_reason = _derive_attention(spec, state=state)
        links_count = sum(
            1
            for value in (
                spec.idea_id,
                spec.process_summary,
                spec.pseudocode_summary,
                spec.implementation_summary,
                spec.created_by_contributor_id,
                spec.updated_by_contributor_id,
            )
            if bool(str(value or "").strip())
        )
        rows.append(
            EnrichedSpecRow(
                spec=spec,
                state=state,
                attention_level=attention_level,
                attention_score=attention_score,
                attention_reason=attention_reason,
                links_count=links_count,
                search_blob=_build_search_blob(spec),
            )
        )
    return rows


def _matches_filters(row: EnrichedSpecRow, query: SpecCardsQuery) -> bool:
    if query.q and query.q not in row.search_blob:
        return False
    if query.state != "all" and row.state != query.state:
        return False
    if query.attention != "all" and row.attention_level != query.attention:
        return False
    if query.linked == "linked" and not bool((row.spec.idea_id or "").strip()):
        return False
    if query.linked == "unlinked" and bool((row.spec.idea_id or "").strip()):
        return False
    if query.min_roi is not None and float(row.spec.actual_roi or 0.0) < query.min_roi:
        return False
    if query.min_value_gap is not None and float(row.spec.value_gap or 0.0) < query.min_value_gap:
        return False
    return True


def _sort_rows(rows: list[EnrichedSpecRow], sort: str) -> None:
    if sort == "name_asc":
        rows.sort(key=lambda row: (str(row.spec.title).lower(), row.spec.spec_id))
        return
    if sort == "roi_desc":
        rows.sort(
            key=lambda row: (
                -float(row.spec.actual_roi or 0.0),
                -float(row.spec.estimated_roi or 0.0),
                -float(row.spec.value_gap or 0.0),
                str(row.spec.title).lower(),
            )
        )
        return
    if sort == "gap_desc":
        rows.sort(
            key=lambda row: (
                -float(row.spec.value_gap or 0.0),
                -row.attention_score,
                str(row.spec.title).lower(),
            )
        )
        return
    if sort == "state_desc":
        rows.sort(
            key=lambda row: (
                -_CARD_STATE_RANK.get(row.state, 0),
                -row.attention_score,
                str(row.spec.title).lower(),
            )
        )
        return
    if sort == "updated_desc":
        rows.sort(
            key=lambda row: (
                -row.spec.updated_at.timestamp(),
                str(row.spec.title).lower(),
            )
        )
        return
    rows.sort(
        key=lambda row: (
            -row.attention_score,
            -float(row.spec.value_gap or 0.0),
            -float(row.spec.actual_roi or 0.0),
            -row.spec.updated_at.timestamp(),
            str(row.spec.title).lower(),
        )
    )


def _build_counts(rows: list[EnrichedSpecRow]) -> tuple[dict[str, int], dict[str, int]]:
    state_counts = {key: 0 for key in ("unlinked", "linked", "in_progress", "implemented", "measured")}
    attention_counts = {key: 0 for key in ("none", "low", "medium", "high")}
    for row in rows:
        state_counts[row.state] = int(state_counts.get(row.state, 0)) + 1
        attention_counts[row.attention_level] = int(attention_counts.get(row.attention_level, 0)) + 1
    return state_counts, attention_counts


def _build_items(page_rows: list[EnrichedSpecRow]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in page_rows:
        spec = row.spec
        encoded_spec_id = quote(spec.spec_id, safe="")
        encoded_idea_id = quote(spec.idea_id, safe="") if spec.idea_id else None
        items.append(
            {
                "spec_id": spec.spec_id,
                "title": spec.title,
                "summary": spec.summary,
                "state": row.state,
                "attention_level": row.attention_level,
                "attention_score": row.attention_score,
                "attention_reason": row.attention_reason,
                "value_gap": float(spec.value_gap or 0.0),
                "actual_roi": float(spec.actual_roi or 0.0),
                "estimated_roi": float(spec.estimated_roi or 0.0),
                "potential_value": float(spec.potential_value or 0.0),
                "actual_value": float(spec.actual_value or 0.0),
                "estimated_cost": float(spec.estimated_cost or 0.0),
                "actual_cost": float(spec.actual_cost or 0.0),
                "links_count": row.links_count,
                "idea_id": spec.idea_id,
                "created_by_contributor_id": spec.created_by_contributor_id,
                "updated_by_contributor_id": spec.updated_by_contributor_id,
                "updated_at": spec.updated_at.isoformat(),
                "links": {
                    "web_detail_path": f"/specs/{encoded_spec_id}",
                    "web_idea_path": f"/ideas/{encoded_idea_id}" if encoded_idea_id else None,
                    "api_path": f"/api/spec-registry/{encoded_spec_id}",
                },
            }
        )
    return items


def build_spec_cards_feed_payload(
    *,
    list_specs_fn: Callable[[int, int], list[SpecRegistryEntry]],
    q: str = "",
    state: str = "all",
    attention: str = "all",
    sort: str = "attention_desc",
    cursor: str | None = None,
    limit: int = _CARD_DEFAULT_LIMIT,
    linked: str = "all",
    min_roi: float | None = None,
    min_value_gap: float | None = None,
) -> dict[str, Any]:
    query = normalize_query(
        q=q,
        state=state,
        attention=attention,
        sort=sort,
        cursor=cursor,
        limit=limit,
        linked=linked,
        min_roi=min_roi,
        min_value_gap=min_value_gap,
    )
    rows = _enrich_specs(_list_all_specs(list_specs_fn))
    filtered = [row for row in rows if _matches_filters(row, query)]
    _sort_rows(filtered, query.sort)

    state_counts, attention_counts = _build_counts(filtered)
    total = len(filtered)
    page_start = min(query.cursor, total)
    page_end = min(page_start + query.limit, total)
    page_rows = filtered[page_start:page_end]
    has_more = page_end < total
    next_cursor = str(page_end) if has_more else None
    items = _build_items(page_rows)

    return {
        "summary": {
            "total": total,
            "returned": len(items),
            "state_counts": state_counts,
            "attention_counts": attention_counts,
            "needs_attention": attention_counts["high"],
        },
        "pagination": {
            "cursor": str(page_start),
            "next_cursor": next_cursor,
            "limit": query.limit,
            "returned": len(items),
            "has_more": has_more,
        },
        "query": {
            "q": query.q,
            "state": query.state,
            "attention": query.attention,
            "sort": query.sort,
            "cursor": page_start,
            "limit": query.limit,
            "linked": query.linked,
            "min_roi": query.min_roi,
            "min_value_gap": query.min_value_gap,
        },
        "items": items,
    }
