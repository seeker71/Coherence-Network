from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from app.models.contributor import Contributor, ContributorType
from app.models.contributor_recognition import ContributorRecognitionSnapshot
from app.services import graph_service

WINDOW_DAYS = 30
_GRAPH_CONTRIBUTOR_SCAN_LIMIT = 5000


@dataclass(frozen=True)
class _ContributionRecord:
    record_id: str | None
    cost_amount: Decimal
    coherence_score: float
    timestamp: datetime | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _safe_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _safe_score(value: object) -> float:
    try:
        score = float(value)
    except Exception:
        return 0.0
    return min(max(score, 0.0), 1.0)


def _normalize_contributor_type(value: object) -> ContributorType:
    try:
        return ContributorType(str(value))
    except ValueError:
        return ContributorType.HUMAN


def _find_graph_contributor(contributor_id: UUID) -> dict | None:
    direct = graph_service.get_node(f"contributor:{contributor_id}")
    if direct:
        return direct
    result = graph_service.list_nodes(type="contributor", limit=_GRAPH_CONTRIBUTOR_SCAN_LIMIT)
    for node in result.get("items", []):
        if (
            node.get("legacy_id") == str(contributor_id)
            or node.get("name") == str(contributor_id)
            or node.get("id") == f"contributor:{contributor_id}"
        ):
            return node
    return None


def _resolve_graph_contributor_id(node: dict) -> UUID:
    legacy_id = node.get("legacy_id")
    if legacy_id:
        try:
            return UUID(str(legacy_id))
        except (TypeError, ValueError):
            pass
    node_id = str(node.get("id") or "")
    if node_id.startswith("contributor:"):
        candidate = node_id.split("contributor:", 1)[1]
        try:
            return UUID(candidate)
        except (TypeError, ValueError):
            pass
    raise ValueError("Contributor node is missing a valid UUID identifier")


def _graph_contributor_to_model(node: dict) -> Contributor:
    email = str(node.get("email") or "")
    if "@" not in email:
        safe_name = str(node.get("name") or "unknown").replace(" ", "-").lower()
        email = f"{safe_name}@coherence.network"
    return Contributor(
        id=_resolve_graph_contributor_id(node),
        name=str(node.get("name") or ""),
        type=_normalize_contributor_type(node.get("contributor_type") or ContributorType.HUMAN.value),
        email=email,
        wallet_address=node.get("wallet_address") or None,
        hourly_rate=_safe_decimal(node.get("hourly_rate")) if node.get("hourly_rate") is not None else None,
        created_at=_coerce_utc(node.get("created_at")) or _utc_now(),
    )


def _graph_contributions_for_node(node: dict) -> list[_ContributionRecord]:
    edges = graph_service.get_edges(str(node["id"]), direction="outgoing", edge_type="contribution")
    records: list[_ContributionRecord] = []
    for edge in edges:
        props = edge.get("properties", {})
        records.append(
            _ContributionRecord(
                record_id=str(props.get("contribution_id") or edge.get("id") or "") or None,
                cost_amount=_safe_decimal(props.get("cost_amount", "0")),
                coherence_score=_safe_score(props.get("coherence_score", 0.0)),
                timestamp=_coerce_utc(props.get("timestamp")) or _coerce_utc(edge.get("created_at")),
            )
        )
    return records


def _store_contributions(store, contributor_id: UUID) -> list[_ContributionRecord]:
    records: list[_ContributionRecord] = []
    for contribution in store.get_contributor_contributions(contributor_id):
        records.append(
            _ContributionRecord(
                record_id=str(getattr(contribution, "id", "") or "") or None,
                cost_amount=_safe_decimal(contribution.cost_amount),
                coherence_score=_safe_score(contribution.coherence_score),
                timestamp=_coerce_utc(contribution.timestamp),
            )
        )
    return records


def _merge_contribution_records(
    primary: list[_ContributionRecord],
    secondary: list[_ContributionRecord],
) -> list[_ContributionRecord]:
    merged: list[_ContributionRecord] = list(primary)
    seen_keys: set[tuple[str, str]] = set()

    def _record_key(record: _ContributionRecord) -> tuple[str, str]:
        if record.record_id:
            return ("id", record.record_id)
        timestamp = record.timestamp.isoformat() if record.timestamp is not None else ""
        return (
            "fingerprint",
            "|".join(
                (
                    str(record.cost_amount),
                    f"{record.coherence_score:.6f}",
                    timestamp,
                )
            ),
        )

    for record in primary:
        seen_keys.add(_record_key(record))

    for record in secondary:
        key = _record_key(record)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(record)

    return merged


def _window_counts(records: list[_ContributionRecord], *, now: datetime, window_days: int) -> tuple[int, int]:
    current_start = now - timedelta(days=window_days)
    prior_start = current_start - timedelta(days=window_days)

    current_count = 0
    prior_count = 0
    for record in records:
        if record.timestamp is None:
            continue
        if current_start <= record.timestamp < now:
            current_count += 1
        elif prior_start <= record.timestamp < current_start:
            prior_count += 1
    return current_count, prior_count


def get_contributor_recognition_snapshot(contributor_id: UUID, store=None) -> ContributorRecognitionSnapshot | None:
    contributor: Contributor | None = None
    records: list[_ContributionRecord] = []

    graph_node = _find_graph_contributor(contributor_id)
    if graph_node is not None:
        contributor = _graph_contributor_to_model(graph_node)
        records = _graph_contributions_for_node(graph_node)

    if store is not None:
        store_contributor = store.get_contributor(contributor_id)
        if store_contributor is not None:
            contributor = contributor or store_contributor
            records = _merge_contribution_records(records, _store_contributions(store, contributor_id))

    if contributor is None:
        return None

    total_contributions = len(records)
    total_cost = sum((record.cost_amount for record in records), Decimal("0"))
    if total_contributions:
        average_coherence_score = round(
            sum(record.coherence_score for record in records) / total_contributions,
            2,
        )
    else:
        average_coherence_score = 0.0

    now = _utc_now()
    current_window_contributions, prior_window_contributions = _window_counts(
        records,
        now=now,
        window_days=WINDOW_DAYS,
    )

    return ContributorRecognitionSnapshot(
        contributor_id=contributor.id,
        name=contributor.name,
        total_contributions=total_contributions,
        total_cost=total_cost,
        average_coherence_score=average_coherence_score,
        window_days=WINDOW_DAYS,
        current_window_contributions=current_window_contributions,
        prior_window_contributions=prior_window_contributions,
        delta_contributions=current_window_contributions - prior_window_contributions,
    )
