"""Living append-only adjustments for field-story view attribution flow."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services import unified_db as _udb
from app.services.field_view_attribution_service import (
    ADJUSTMENT_POLICY_ID,
    FieldViewFlowAdjustmentRecord,
    FieldViewFlowRecord,
    FieldViewReceiptRecord,
    POLICY_ID,
)


def adjustment_dict(row: FieldViewFlowAdjustmentRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "event_hash": row.event_hash,
        "from_recipient_id": row.from_recipient_id,
        "to_recipient_id": row.to_recipient_id,
        "amount_cc": row.amount_cc,
        "reason_code": row.reason_code,
        "attested_by": row.attested_by,
        "attestation_type": row.attestation_type,
        "policy_id": row.policy_id,
        "from_ledger_contribution_id": row.from_ledger_contribution_id,
        "to_ledger_contribution_id": row.to_ledger_contribution_id,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
    }


def effective_flow_totals(
    flows: list[FieldViewFlowRecord],
    adjustments: list[FieldViewFlowAdjustmentRecord],
) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    reasons: dict[str, set[str]] = defaultdict(set)
    for row in flows:
        totals[row.recipient_id] += row.amount_cc
        reasons[row.recipient_id].add(row.reason_code)
    apply_adjustments_to_totals(totals, reasons, adjustments)
    return [
        {
            "recipient_id": recipient,
            "amount_cc": round(amount, 4),
            "reason_codes": sorted(reasons[recipient]),
        }
        for recipient, amount in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
        if round(amount, 4) != 0
    ]


def apply_adjustments_to_totals(
    totals: dict[str, float],
    reasons: dict[str, set[str]],
    adjustments: list[FieldViewFlowAdjustmentRecord],
) -> None:
    for row in adjustments:
        totals[row.from_recipient_id] -= row.amount_cc
        totals[row.to_recipient_id] += row.amount_cc
        reasons[row.from_recipient_id].add(f"adjustment-out:{row.reason_code}")
        reasons[row.to_recipient_id].add(f"adjustment-in:{row.reason_code}")


def policy_summary() -> dict[str, Any]:
    return {
        "base_policy": {
            "policy_id": POLICY_ID,
            "behavior": "creates immutable receipt + initial CC flow rows",
            "splits": [
                {"recipient": "original creator", "fraction": 0.40, "reason_code": "original-work"},
                {"recipient": "lived contributor", "fraction": 0.20, "reason_code": "lived-integration"},
                {"recipient": "trace artifact", "fraction": 0.12, "reason_code": "queryable-map"},
                {"recipient": "agent", "fraction": 0.10, "reason_code": "trace-builder"},
                {"recipient": "infrastructure", "fraction": 0.10, "reason_code": "serve-verify-host"},
                {"recipient": "viewer session", "fraction": 0.08, "reason_code": "attention-discovery"},
            ],
        },
        "living_policy": {
            "policy_id": ADJUSTMENT_POLICY_ID,
            "behavior": "adds append-only adjustments; never mutates original receipts or base flows",
            "influence_paths": [
                "creator preference",
                "viewer gratitude",
                "contributor attestation",
                "agent trace correction",
                "source artifact refinement",
                "community stewardship",
            ],
            "conservation": "each adjustment records a negative ledger row from one recipient and a positive row to another",
        },
    }


def _adjustment_metadata(
    *,
    receipt: FieldViewReceiptRecord,
    adjustment_id: str,
    from_recipient_id: str,
    to_recipient_id: str,
    amount_cc: float,
    reason_code: str,
    attested_by: str,
    attestation_type: str,
    note: str,
) -> dict[str, Any]:
    return {
        "adjustment_id": adjustment_id,
        "event_hash": receipt.event_hash,
        "story_slug": receipt.story_slug,
        "presence_id": receipt.presence_id,
        "target_id": receipt.target_id,
        "target_selector": receipt.target_selector,
        "target_value": receipt.target_value,
        "trace_root": receipt.trace_root,
        "from_recipient_id": from_recipient_id,
        "to_recipient_id": to_recipient_id,
        "amount_cc": round(float(amount_cc), 4),
        "reason_code": reason_code,
        "attested_by": attested_by,
        "attestation_type": attestation_type,
        "note": note,
        "policy_id": ADJUSTMENT_POLICY_ID,
    }


def _record_adjustment_ledger(metadata: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.services import contribution_ledger_service

    amount = float(metadata["amount_cc"])
    from_row = contribution_ledger_service.record_contribution(
        contributor_id=metadata["from_recipient_id"],
        contribution_type="field_view_flow_adjustment",
        amount_cc=-amount,
        idea_id="profile-contribution-derived-data",
        metadata={**metadata, "direction": "from"},
    )
    to_row = contribution_ledger_service.record_contribution(
        contributor_id=metadata["to_recipient_id"],
        contribution_type="field_view_flow_adjustment",
        amount_cc=amount,
        idea_id="profile-contribution-derived-data",
        metadata={**metadata, "direction": "to"},
    )
    return from_row, to_row


def record_flow_adjustment(
    *,
    slug: str,
    event_hash: str,
    from_recipient_id: str,
    to_recipient_id: str,
    amount_cc: float,
    reason_code: str,
    attested_by: str,
    attestation_type: str = "steward-attestation",
    note: str = "",
) -> dict[str, Any]:
    amount = round(float(amount_cc), 4)
    if amount <= 0:
        raise ValueError("amount_cc must be positive")
    adjustment_id = f"fva_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    with _udb.session() as session:
        receipt = session.get(FieldViewReceiptRecord, event_hash)
        if not receipt or receipt.story_slug != slug:
            raise KeyError(event_hash)
        metadata = _adjustment_metadata(
            receipt=receipt,
            adjustment_id=adjustment_id,
            from_recipient_id=from_recipient_id,
            to_recipient_id=to_recipient_id,
            amount_cc=amount,
            reason_code=reason_code,
            attested_by=attested_by,
            attestation_type=attestation_type,
            note=note,
        )
    from_ledger, to_ledger = _record_adjustment_ledger(metadata)
    with _udb.session() as session:
        row = FieldViewFlowAdjustmentRecord(
            id=adjustment_id,
            event_hash=event_hash,
            from_recipient_id=from_recipient_id,
            to_recipient_id=to_recipient_id,
            amount_cc=amount,
            reason_code=reason_code,
            attested_by=attested_by,
            attestation_type=attestation_type,
            policy_id=ADJUSTMENT_POLICY_ID,
            from_ledger_contribution_id=from_ledger["id"],
            to_ledger_contribution_id=to_ledger["id"],
            metadata_json=json.dumps(metadata, sort_keys=True, ensure_ascii=False),
            recorded_at=now,
        )
        session.add(row)
    from app.services import field_view_attribution_service

    summary = field_view_attribution_service.receipt_summary(event_hash)
    return {
        "adjustment": {
            **metadata,
            "from_ledger_contribution_id": from_ledger["id"],
            "to_ledger_contribution_id": to_ledger["id"],
            "recorded_at": now.isoformat(),
        },
        "receipt": summary["receipt"],
        "effective_flows": summary["effective_flows"],
    }
