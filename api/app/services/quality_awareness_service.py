"""Guidance-first quality awareness summary derived from maintainability audits."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services import maintainability_audit_service

_QUALITY_AWARENESS_CACHE: dict[str, Any] = {"expires_at": 0.0, "summary": None}
_QUALITY_AWARENESS_TTL_SECONDS = float(os.getenv("AUTOMATION_QUALITY_AWARENESS_TTL_SECONDS", "300"))


def _maintainability_baseline_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "system_audit" / "maintainability_baseline.json"


def _default_payload(*, detail: str | None = None) -> dict[str, Any]:
    guidance = ["Current maintainability signals are stable; keep shipping in small, reviewable modules."]
    if detail:
        guidance = [detail]
    return {
        "status": "unavailable" if detail else "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "intent_focus": ["trust", "clarity", "reuse"],
        "summary": {
            "severity": "unknown" if detail else "low",
            "risk_score": 0,
            "regression": False,
            "regression_reasons": [],
            "python_module_count": 0,
            "runtime_file_count": 0,
            "layer_violations": 0,
            "large_modules": 0,
            "very_large_modules": 0,
            "long_functions": 0,
            "placeholder_findings": 0,
        },
        "hotspots": [],
        "guidance": guidance,
        "recommended_tasks": [],
    }


def _hotspots_from_audit(audit: dict[str, Any], *, top_n: int) -> list[dict[str, Any]]:
    architecture = audit.get("architecture") if isinstance(audit.get("architecture"), dict) else {}
    placeholder_scan = audit.get("placeholder_scan") if isinstance(audit.get("placeholder_scan"), dict) else {}

    hotspots: list[dict[str, Any]] = []
    for row in list(architecture.get("very_large_modules") or [])[:top_n]:
        if not isinstance(row, dict):
            continue
        hotspots.append(
            {
                "kind": "very_large_module",
                "path": str(row.get("file") or "unknown"),
                "line_count": int(row.get("line_count") or 0),
                "detail": "Split module into smaller focused units.",
                "attention_score": int(row.get("line_count") or 0),
            }
        )
    for row in list(architecture.get("long_functions") or [])[:top_n]:
        if not isinstance(row, dict):
            continue
        hotspots.append(
            {
                "kind": "long_function",
                "path": str(row.get("file") or "unknown"),
                "line_count": int(row.get("line_count") or 0),
                "function": str(row.get("function") or ""),
                "detail": "Extract helper steps to improve readability and testability.",
                "attention_score": int(row.get("line_count") or 0),
            }
        )
    for row in list(architecture.get("layer_violations") or [])[:top_n]:
        if not isinstance(row, dict):
            continue
        hotspots.append(
            {
                "kind": "layer_violation",
                "path": str(row.get("file") or "unknown"),
                "forbidden_import": str(row.get("forbidden_import") or ""),
                "detail": str(row.get("reason") or "Cross-layer dependency should be removed."),
                "attention_score": 250,
            }
        )
    for row in list(placeholder_scan.get("findings") or [])[:top_n]:
        if not isinstance(row, dict):
            continue
        hotspots.append(
            {
                "kind": "runtime_placeholder",
                "path": str(row.get("file") or "unknown"),
                "line": int(row.get("line") or 0),
                "detail": str(row.get("snippet") or ""),
                "attention_score": 120,
            }
        )
    hotspots.sort(key=lambda row: int(row.get("attention_score") or 0), reverse=True)
    return hotspots[: max(3, min(top_n * 2, 10))]


def _guidance_from_summary(summary: dict[str, Any]) -> list[str]:
    guidance: list[str] = []
    if int(summary.get("very_large_module_count") or 0) > 0:
        guidance.append("Prioritize splitting very large modules before adding new feature logic.")
    if int(summary.get("long_function_count") or 0) > 0:
        guidance.append("Use extraction-by-intent for long functions to preserve behavior and reduce drift.")
    if int(summary.get("layer_violation_count") or 0) > 0:
        guidance.append("Repair cross-layer imports to keep service/model/router boundaries maintainable.")
    if bool(summary.get("regression")):
        guidance.append("Recent maintainability metrics regressed; schedule a debt-reduction cycle this week.")
    if not guidance:
        guidance.append("Current maintainability signals are stable; keep shipping in small, reviewable modules.")
    return guidance[:5]


def build_quality_awareness_summary(*, top_n: int, force_refresh: bool = False) -> dict[str, Any]:
    now_ts = time.time()
    cached = _QUALITY_AWARENESS_CACHE.get("summary")
    if (
        not force_refresh
        and isinstance(cached, dict)
        and now_ts < float(_QUALITY_AWARENESS_CACHE.get("expires_at") or 0.0)
    ):
        return cached

    try:
        baseline = maintainability_audit_service.load_baseline(_maintainability_baseline_path())
        audit = maintainability_audit_service.build_maintainability_audit(baseline=baseline)
        summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
        recommended = list(audit.get("recommended_tasks") or [])

        payload = {
            "status": "ok",
            "generated_at": str(audit.get("generated_at") or datetime.now(timezone.utc).isoformat()),
            "intent_focus": ["trust", "clarity", "reuse"],
            "summary": {
                "severity": str(summary.get("severity") or "low"),
                "risk_score": int(summary.get("risk_score") or 0),
                "regression": bool(summary.get("regression")),
                "regression_reasons": list(summary.get("regression_reasons") or []),
                "python_module_count": int(summary.get("python_module_count") or 0),
                "runtime_file_count": int(summary.get("runtime_file_count") or 0),
                "layer_violations": int(summary.get("layer_violation_count") or 0),
                "large_modules": int(summary.get("large_module_count") or 0),
                "very_large_modules": int(summary.get("very_large_module_count") or 0),
                "long_functions": int(summary.get("long_function_count") or 0),
                "placeholder_findings": int(summary.get("placeholder_count") or 0),
            },
            "hotspots": _hotspots_from_audit(audit, top_n=top_n),
            "guidance": _guidance_from_summary(summary),
            "recommended_tasks": [
                {
                    "task_id": str(row.get("task_id") or ""),
                    "title": str(row.get("title") or ""),
                    "priority": str(row.get("priority") or "medium"),
                    "roi_estimate": float(row.get("roi_estimate") or 0.0),
                    "direction": str(row.get("direction") or ""),
                }
                for row in recommended[:top_n]
                if isinstance(row, dict)
            ],
        }
    except Exception as exc:
        payload = _default_payload(detail=f"Quality awareness unavailable: {exc}")

    _QUALITY_AWARENESS_CACHE["summary"] = payload
    _QUALITY_AWARENESS_CACHE["expires_at"] = now_ts + max(30.0, _QUALITY_AWARENESS_TTL_SECONDS)
    return payload
