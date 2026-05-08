"""Field story view attribution receipts and CC circulation rows."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.services import unified_db as _udb
from app.services.unified_db import Base


POLICY_ID = "cc-flow-policy:presence-work-view:v1"


class FieldViewReceiptRecord(Base):
    __tablename__ = "field_view_receipts"

    event_hash: Mapped[str] = mapped_column(String, primary_key=True)
    story_slug: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String, nullable=False)
    presence_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_selector: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_value: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    creator_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    trace_api: Mapped[str] = mapped_column(String, nullable=False)
    trace_root: Mapped[str] = mapped_column(String, nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    cc_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    session_hash: Mapped[str] = mapped_column(String, nullable=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class FieldViewFlowRecord(Base):
    __tablename__ = "field_view_flows"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    recipient_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    reason_code: Mapped[str] = mapped_column(String, nullable=False, index=True)
    amount_cc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ledger_contribution_id: Mapped[str] = mapped_column(String, nullable=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


def _ensure_schema() -> None:
    _udb.ensure_schema()


def _canonical_hash(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_size(payload: Any) -> int:
    return len(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _trace_root(slug: str) -> str:
    from app.services import field_story_service

    artifact = field_story_service.get_field_story_artifact(slug, "trace-source-crypto")
    payload = json.loads(artifact["content"])
    return payload["roots"]["combined_trace_root"]


def _target_trace(slug: str, selector: str, value: str) -> dict[str, Any]:
    from app.services import field_story_service

    return field_story_service.get_field_story_trace_slice(slug, selector, value)


def _target_identity(selector: str, trace_result: dict[str, Any]) -> tuple[str, str]:
    result = trace_result["result"]
    target_id = str(result.get("id") or f"{selector}:{trace_result['value']}")
    creator = "creator:unknown"
    if selector in {"significant-work", "significant_work"}:
        authors = result.get("authors") or []
        if authors:
            creator = f"creator:{authors[0]}"
    elif selector == "author":
        creator = f"creator:{result.get('name') or trace_result['value']}"
    elif selector == "work":
        creator = f"creator:{result.get('author') or result.get('author_id') or 'unknown'}"
    elif selector == "concept":
        creator = f"concept-origin:{trace_result['value']}"
    return target_id, creator


def _flow_policy(*, creator_id: str, target_id: str, cc_amount: float) -> list[dict[str, Any]]:
    splits = [
        (creator_id, "original-work", 0.40),
        ("contributor:urs", "lived-integration", 0.20),
        ("artifact:trace-significant-work-index", "queryable-map", 0.12),
        ("agent:gpt-5-codex", "trace-builder", 0.10),
        ("infrastructure:coherence-network", "serve-verify-host", 0.10),
        ("viewer-session", "attention-discovery", 0.08),
    ]
    rows = []
    remaining = round(float(cc_amount), 4)
    for index, (recipient, reason, fraction) in enumerate(splits):
        amount = round(float(cc_amount) * fraction, 4)
        if index == len(splits) - 1:
            amount = remaining
        remaining = round(remaining - amount, 4)
        rows.append({"recipient_id": recipient, "reason_code": reason, "amount_cc": amount, "target_id": target_id})
    return rows


def _artifact_id(selector: str) -> str:
    return "trace-significant-work-index" if selector == "significant-work" else f"trace-{selector}"


def _build_receipt_context(
    *,
    slug: str,
    surface: str,
    presence_id: str,
    target_selector: str,
    target_value: str,
    session_hash: str | None = None,
    viewer_contributor_id: str | None = None,
    cc_amount: float = 1.0,
) -> dict[str, Any]:
    selector = target_selector.lower().replace("_", "-")
    trace = _target_trace(slug, selector, target_value)
    target_id, creator_id = _target_identity(selector, trace)
    trace_api = f"/api/field-stories/{slug}/trace/{selector}/{target_value}"
    root = _trace_root(slug)
    now = datetime.now(timezone.utc)
    receipt = {
        "v": 1,
        "event": "presence_work_view",
        "ts": now.isoformat(),
        "session": session_hash,
        "viewer_contributor_id": viewer_contributor_id,
        "surface": surface,
        "presence": presence_id,
        "target_selector": selector,
        "target_value": target_value,
        "target_id": target_id,
        "creator": creator_id,
        "artifact": _artifact_id(selector),
        "trace": trace_api,
        "root": root,
        "policy": POLICY_ID,
        "cc": round(float(cc_amount), 4),
    }
    event_hash = _canonical_hash(receipt)
    receipt["event_hash"] = event_hash
    return {
        "slug": slug,
        "surface": surface,
        "presence_id": presence_id,
        "selector": selector,
        "target_value": target_value,
        "target_id": target_id,
        "creator_id": creator_id,
        "trace_api": trace_api,
        "root": root,
        "now": now,
        "receipt": receipt,
        "trace_result": trace["result"],
        "cc_amount": round(float(cc_amount), 4),
        "session_hash": session_hash,
    }


def _persist_receipt(context: dict[str, Any]) -> dict[str, Any] | None:
    with _udb.session() as session:
        existing = session.get(FieldViewReceiptRecord, context["receipt"]["event_hash"])
        if existing:
            return receipt_summary(context["receipt"]["event_hash"], session=session)
        record = FieldViewReceiptRecord(
            event_hash=context["receipt"]["event_hash"],
            story_slug=context["slug"],
            event_type="presence_work_view",
            surface=context["surface"],
            presence_id=context["presence_id"],
            target_selector=context["selector"],
            target_value=context["target_value"],
            target_id=context["target_id"],
            creator_id=context["creator_id"],
            trace_api=context["trace_api"],
            trace_root=context["root"],
            policy_id=POLICY_ID,
            cc_amount=context["cc_amount"],
            session_hash=context["session_hash"],
            metadata_json=json.dumps(context["receipt"], sort_keys=True, ensure_ascii=False),
            recorded_at=context["now"],
        )
        session.add(record)
    return None


def _ledger_metadata(context: dict[str, Any], flow: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_hash": context["receipt"]["event_hash"],
        "story_slug": context["slug"],
        "presence_id": context["presence_id"],
        "target_selector": context["selector"],
        "target_value": context["target_value"],
        "target_id": context["target_id"],
        "reason_code": flow["reason_code"],
        "trace_root": context["root"],
        "policy_id": POLICY_ID,
    }


def _persist_flow_row(context: dict[str, Any], flow: dict[str, Any], ledger_id: str) -> dict[str, Any]:
    row = {
        "id": f"fvf_{uuid4().hex[:12]}",
        "event_hash": context["receipt"]["event_hash"],
        "recipient_id": flow["recipient_id"],
        "reason_code": flow["reason_code"],
        "amount_cc": flow["amount_cc"],
        "ledger_contribution_id": ledger_id,
    }
    with _udb.session() as session:
        session.add(
            FieldViewFlowRecord(
                id=row["id"],
                event_hash=row["event_hash"],
                recipient_id=row["recipient_id"],
                reason_code=row["reason_code"],
                amount_cc=row["amount_cc"],
                ledger_contribution_id=row["ledger_contribution_id"],
                metadata_json=json.dumps(flow, sort_keys=True, ensure_ascii=False),
                recorded_at=context["now"],
            )
        )
    return row


def _record_flow_rows(context: dict[str, Any], flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from app.services import contribution_ledger_service

    flow_rows: list[dict[str, Any]] = []
    for flow in flows:
        ledger = contribution_ledger_service.record_contribution(
            contributor_id=flow["recipient_id"],
            contribution_type="field_view_flow",
            amount_cc=flow["amount_cc"],
            idea_id="profile-contribution-derived-data",
            metadata=_ledger_metadata(context, flow),
        )
        flow_rows.append(_persist_flow_row(context, flow, ledger["id"]))
    return flow_rows


def record_presence_view(
    *,
    slug: str,
    surface: str,
    presence_id: str,
    target_selector: str,
    target_value: str,
    session_hash: str | None = None,
    viewer_contributor_id: str | None = None,
    cc_amount: float = 1.0,
) -> dict[str, Any]:
    """Persist one compact field-story view receipt and its CC flow rows."""
    _ensure_schema()
    context = _build_receipt_context(
        slug=slug,
        surface=surface,
        presence_id=presence_id,
        target_selector=target_selector,
        target_value=target_value,
        session_hash=session_hash,
        viewer_contributor_id=viewer_contributor_id,
        cc_amount=cc_amount,
    )
    existing = _persist_receipt(context)
    if existing:
        return existing
    flows = _flow_policy(
        creator_id=context["creator_id"],
        target_id=context["target_id"],
        cc_amount=context["cc_amount"],
    )
    flow_rows = _record_flow_rows(context, flows)

    return {
        "receipt": context["receipt"],
        "flows": flow_rows,
        "storage_shape": {
            "receipt_bytes": _json_size(context["receipt"]),
            "flow_rows": len(flow_rows),
            "flow_bytes": _json_size(flow_rows),
            "stored_strategy": "compact receipt ids + flow rows + ledger ids; raw source bodies stay behind trace roots",
        },
        "trace_result": context["trace_result"],
    }


def receipt_summary(event_hash: str, *, session: Session | None = None) -> dict[str, Any]:
    close = False
    if session is None:
        _ensure_schema()
        session = _udb.get_sessionmaker()()
        close = True
    try:
        receipt = session.get(FieldViewReceiptRecord, event_hash)
        if not receipt:
            raise KeyError(event_hash)
        flows = (
            session.query(FieldViewFlowRecord)
            .filter(FieldViewFlowRecord.event_hash == event_hash)
            .order_by(FieldViewFlowRecord.recorded_at.asc())
            .all()
        )
        return {
            "receipt": json.loads(receipt.metadata_json),
            "flows": [
                {
                    "recipient_id": row.recipient_id,
                    "reason_code": row.reason_code,
                    "amount_cc": row.amount_cc,
                    "ledger_contribution_id": row.ledger_contribution_id,
                }
                for row in flows
            ],
        }
    finally:
        if close:
            session.close()


def circulation_summary(slug: str, *, limit: int = 12) -> dict[str, Any]:
    _ensure_schema()
    with _udb.session() as session:
        receipts = (
            session.query(FieldViewReceiptRecord)
            .filter(FieldViewReceiptRecord.story_slug == slug)
            .order_by(FieldViewReceiptRecord.recorded_at.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        flows = (
            session.query(FieldViewFlowRecord)
            .join(FieldViewReceiptRecord, FieldViewFlowRecord.event_hash == FieldViewReceiptRecord.event_hash)
            .filter(FieldViewReceiptRecord.story_slug == slug)
            .all()
        )
        by_recipient: dict[str, float] = defaultdict(float)
        by_reason: dict[str, float] = defaultdict(float)
        for row in flows:
            by_recipient[row.recipient_id] += row.amount_cc
            by_reason[row.reason_code] += row.amount_cc
        tension = Counter(row.target_id for row in receipts)
        vitality = sum(row.amount_cc for row in flows)
        return {
            "story_slug": slug,
            "receipt_count_sampled": len(receipts),
            "flow_row_count": len(flows),
            "total_cc_circulated": round(vitality, 4),
            "top_recipients": [
                {"recipient_id": key, "amount_cc": round(value, 4)}
                for key, value in sorted(by_recipient.items(), key=lambda item: (-item[1], item[0]))[:limit]
            ],
            "reason_totals": {key: round(value, 4) for key, value in sorted(by_reason.items())},
            "sensing": {
                "circulation": "flowing" if flows else "quiet",
                "vitality": round(vitality, 4),
                "tension_points": [{"target_id": key, "views": count} for key, count in tension.most_common(5)],
                "flexibility": "multi-recipient" if len(by_recipient) >= 5 else "narrow",
                "friction": "none-visible" if flows else "no-recorded-flow-yet",
            },
            "recent_receipts": [
                {
                    "event_hash": row.event_hash,
                    "presence_id": row.presence_id,
                    "target_id": row.target_id,
                    "creator_id": row.creator_id,
                    "cc_amount": row.cc_amount,
                    "trace_root": row.trace_root,
                    "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
                }
                for row in receipts
            ],
        }
