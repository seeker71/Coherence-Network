"""Attribution bridge for editable entity views.

Entity views are the mutable text surface behind concepts, ideas, assets,
specs, and contribution renderings. This service records two append-only
facts:

1. a human-authored view write points at a contribution ledger record;
2. a later view ping can credit attention back to that source contribution.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

CONTENT_VIEW_TYPE = "content_view"
ATTENTION_TYPE = "attention"


def record_view_attribution(
    *,
    entity_type: str,
    entity_id: str,
    view_id: str,
    lang: str,
    content_hash: str,
    author_id: str | None,
    author_type: str,
    content_title: str = "",
) -> str | None:
    """Record a content-view write in the contribution ledger.

    Returns the ledger contribution id, or None when the write has no author.
    """
    if not author_id:
        return None

    try:
        from app.services import contribution_ledger_service

        record = contribution_ledger_service.record_contribution(
            contributor_id=author_id,
            contribution_type=CONTENT_VIEW_TYPE,
            amount_cc=1.0,
            idea_id=entity_id if entity_type == "idea" else None,
            metadata={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "view_id": view_id,
                "lang": lang,
                "content_hash": content_hash,
                "author_type": author_type,
                "content_title": content_title,
            },
        )
        return record["id"]
    except Exception as exc:  # pragma: no cover - attribution must not block writes
        log.warning(
            "entity_view_attribution: failed to record source for %s/%s view %s: %s",
            entity_type,
            entity_id,
            view_id,
            exc,
        )
        return None


def infer_entity_from_view_ping(
    *,
    asset_id: str,
    concept_id: str | None = None,
    source_page: str | None = None,
) -> tuple[str, str]:
    """Infer entity identity from the existing read-ping shape."""
    if concept_id:
        return "concept", concept_id
    if asset_id.startswith("lc-"):
        return "concept", asset_id
    if asset_id.startswith("page:"):
        return "page", asset_id.split(":", 1)[1]

    page = source_page or ""
    if page.startswith("/ideas/"):
        return "idea", asset_id
    if page.startswith("/assets/"):
        return "asset", asset_id
    if page.startswith("/specs/"):
        return "spec", asset_id
    if page and page != "/":
        return "page", page.strip("/").split("/", 1)[0]
    return "asset", asset_id


def _metadata_matches(raw: str, entity_type: str, entity_id: str) -> tuple[bool, dict[str, Any]]:
    try:
        metadata = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return False, {}
    return (
        metadata.get("entity_type") == entity_type
        and metadata.get("entity_id") == entity_id,
        metadata,
    )


def latest_source_contribution(entity_type: str, entity_id: str) -> dict[str, Any] | None:
    """Return the newest content-view contribution for an entity."""
    try:
        from app.services import unified_db as _udb
        from app.services.contribution_ledger_service import ContributionLedgerRecord

        _udb.ensure_schema()
        with _udb.session() as session:
            rows = (
                session.query(ContributionLedgerRecord)
                .filter(ContributionLedgerRecord.contribution_type == CONTENT_VIEW_TYPE)
                .order_by(ContributionLedgerRecord.recorded_at.desc())
                .limit(1000)
                .all()
            )
            for row in rows:
                matches, metadata = _metadata_matches(
                    row.metadata_json,
                    entity_type,
                    entity_id,
                )
                if matches:
                    return {
                        "id": row.id,
                        "contributor_id": row.contributor_id,
                        "metadata": metadata,
                        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                    }
    except Exception as exc:  # pragma: no cover - read pings must remain best-effort
        log.warning(
            "entity_view_attribution: failed to find source for %s/%s: %s",
            entity_type,
            entity_id,
            exc,
        )
    return None


def credit_view_source(
    *,
    entity_type: str,
    entity_id: str,
    asset_id: str,
    view_event_id: str | None,
    viewer_contributor_id: str | None = None,
    source_page: str | None = None,
    workspace_id: str = "coherence-network",
) -> dict[str, Any] | None:
    """Credit a viewed entity's latest source contribution with attention CC."""
    source = latest_source_contribution(entity_type, entity_id)
    if not source:
        return None
    source_contributor_id = source["contributor_id"]
    if viewer_contributor_id and viewer_contributor_id == source_contributor_id:
        return None

    try:
        from app.services import contribution_ledger_service, reward_policy_service

        reward_cc = reward_policy_service.get_policy_value(
            "discovery.view_reward_cc",
            workspace_id,
        )
        try:
            amount_cc = float(reward_cc)
        except (TypeError, ValueError):
            amount_cc = 0.01
        if amount_cc <= 0:
            return None

        attention = contribution_ledger_service.record_contribution(
            contributor_id=source_contributor_id,
            contribution_type=ATTENTION_TYPE,
            amount_cc=amount_cc,
            idea_id=entity_id if entity_type == "idea" else None,
            metadata={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "asset_id": asset_id,
                "source_contribution_id": source["id"],
                "source_view_id": source["metadata"].get("view_id"),
                "source_content_hash": source["metadata"].get("content_hash"),
                "view_event_id": view_event_id,
                "viewer_contributor_id": viewer_contributor_id,
                "source_page": source_page,
                "workspace_id": workspace_id,
            },
        )
        return {
            "source_contribution_id": source["id"],
            "attention_contribution_id": attention["id"],
            "source_contributor_id": source_contributor_id,
            "amount_cc": amount_cc,
        }
    except Exception as exc:  # pragma: no cover - read pings must remain best-effort
        log.warning(
            "entity_view_attribution: failed to credit source %s for %s/%s: %s",
            source["id"],
            entity_type,
            entity_id,
            exc,
        )
        return None
