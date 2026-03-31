from __future__ import annotations

from pathlib import Path

from app.services import maintainability_audit_service


def test_audit_detects_layer_violations_and_runtime_placeholders(tmp_path: Path) -> None:
    (tmp_path / "api" / "app" / "services").mkdir(parents=True, exist_ok=True)
    (tmp_path / "api" / "app" / "models").mkdir(parents=True, exist_ok=True)
    (tmp_path / "web" / "app").mkdir(parents=True, exist_ok=True)

    (tmp_path / "api" / "app" / "services" / "bad_service.py").write_text(
        "from app.routers import agent\n\n\ndef run() -> None:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "api" / "app" / "models" / "bad_model.py").write_text(
        "from app.services import idea_service\n",
        encoding="utf-8",
    )
    (tmp_path / "web" / "app" / "page.tsx").write_text(
        "export default function Page(){ const value='fake runtime data'; return <div>{value}</div> }\n",
        encoding="utf-8",
    )

    report = maintainability_audit_service.build_maintainability_audit(
        project_root=tmp_path,
        policy={
            "large_module_lines": 200,
            "very_large_module_lines": 400,
            "long_function_lines": 80,
            "warning_risk_score": 10,
            "blocking_risk_score": 20,
        },
    )

    summary = report["summary"]
    assert summary["layer_violation_count"] == 2
    assert summary["placeholder_count"] == 1
    assert summary["risk_score"] > 0
    assert summary["severity"] in {"medium", "high"}
    assert report["recommended_tasks"]


def test_audit_ignores_ui_placeholder_attributes(tmp_path: Path) -> None:
    (tmp_path / "web" / "components").mkdir(parents=True, exist_ok=True)
    (tmp_path / "web" / "components" / "search.tsx").write_text(
        'export function Search(){ return <input placeholder="Search projects..." /> }\n',
        encoding="utf-8",
    )

    report = maintainability_audit_service.build_maintainability_audit(project_root=tmp_path)
    assert report["summary"]["placeholder_count"] == 0


def test_audit_detects_regressions_against_baseline(tmp_path: Path) -> None:
    (tmp_path / "api" / "app" / "services").mkdir(parents=True, exist_ok=True)
    (tmp_path / "api" / "app" / "services" / "risk.py").write_text(
        "from app.routers import inventory\n",
        encoding="utf-8",
    )

    report = maintainability_audit_service.build_maintainability_audit(project_root=tmp_path)
    summary = report["summary"]
    regression = maintainability_audit_service.evaluate_regression_against_baseline(
        summary=summary,
        baseline={
            "max_layer_violation_count": 0,
            "max_large_module_count": 0,
            "max_very_large_module_count": 0,
            "max_long_function_count": 0,
            "max_placeholder_count": 0,
            "max_risk_score": 0,
        },
    )

    assert regression["regression"] is True
    assert regression["reasons"]
