from __future__ import annotations

import pytest

from app.services import quality_awareness_service


def test_build_quality_awareness_summary_reports_hotspots_and_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_awareness_service._QUALITY_AWARENESS_CACHE["expires_at"] = 0.0
    quality_awareness_service._QUALITY_AWARENESS_CACHE["summary"] = None
    monkeypatch.setattr(quality_awareness_service.maintainability_audit_service, "load_baseline", lambda path: {})
    monkeypatch.setattr(
        quality_awareness_service.maintainability_audit_service,
        "build_maintainability_audit",
        lambda baseline=None: {
            "generated_at": "2026-02-23T12:00:00Z",
            "summary": {
                "severity": "medium",
                "risk_score": 71,
                "regression": True,
                "regression_reasons": ["max_risk_score: 71 > baseline 60"],
                "python_module_count": 100,
                "runtime_file_count": 180,
                "layer_violation_count": 1,
                "large_module_count": 2,
                "very_large_module_count": 1,
                "long_function_count": 8,
                "placeholder_count": 1,
            },
            "architecture": {
                "very_large_modules": [{"file": "api/app/services/automation_usage_service.py", "line_count": 1800}],
                "long_functions": [{"file": "api/app/services/agent_service.py", "function": "sync", "line_count": 120}],
                "layer_violations": [
                    {
                        "file": "api/app/models/runtime.py",
                        "forbidden_import": "app.services.agent_service",
                        "reason": "models should not depend on services/routers",
                    }
                ],
            },
            "placeholder_scan": {"findings": [{"file": "web/app/page.tsx", "line": 20, "snippet": "TODO real data"}]},
            "recommended_tasks": [{"task_id": "architecture-modularization-review", "title": "Architecture modularization review"}],
        },
    )

    payload = quality_awareness_service.build_quality_awareness_summary(top_n=3, force_refresh=True)
    assert payload["status"] == "ok"
    assert payload["summary"]["risk_score"] == 71
    assert payload["hotspots"]
    assert any("regressed" in row for row in payload["guidance"])


def test_build_quality_awareness_summary_falls_back_when_audit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality_awareness_service._QUALITY_AWARENESS_CACHE["expires_at"] = 0.0
    quality_awareness_service._QUALITY_AWARENESS_CACHE["summary"] = None
    monkeypatch.setattr(quality_awareness_service.maintainability_audit_service, "load_baseline", lambda path: {})
    monkeypatch.setattr(
        quality_awareness_service.maintainability_audit_service,
        "build_maintainability_audit",
        lambda baseline=None: (_ for _ in ()).throw(RuntimeError("scan failed")),
    )

    payload = quality_awareness_service.build_quality_awareness_summary(top_n=3, force_refresh=True)
    assert payload["status"] == "unavailable"
    assert payload["hotspots"] == []
    assert "scan failed" in payload["guidance"][0]
