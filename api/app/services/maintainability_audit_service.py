"""Maintainability audit service: architecture drift + runtime placeholder debt."""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_POLICY: dict[str, int] = {
    "large_module_lines": 600,
    "very_large_module_lines": 1000,
    "long_function_lines": 90,
    "warning_risk_score": 40,
    "blocking_risk_score": 90,
}

BASELINE_KEYS: tuple[str, ...] = (
    "max_layer_violation_count",
    "max_large_module_count",
    "max_very_large_module_count",
    "max_long_function_count",
    "max_placeholder_count",
    "max_risk_score",
)

PLACEHOLDER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("todo_fixme", re.compile(r"(#|//)\s*(TODO|FIXME|XXX)\b", re.IGNORECASE)),
    (
        "fake_marker_constant",
        re.compile(r"\b(MOCK|FAKE|DUMMY|STUB)_?[A-Z0-9_]*\b"),
    ),
    (
        "literal_fake_data",
        re.compile(r"""=\s*['"][^'"]*\b(fake|mock|dummy|stub|placeholder)\b[^'"]*['"]""", re.IGNORECASE),
    ),
    (
        "return_fake_data",
        re.compile(r"""return\s+.*['"][^'"]*\b(fake|mock|dummy|stub|placeholder)\b[^'"]*['"]""", re.IGNORECASE),
    ),
)

RUNTIME_SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}
RUNTIME_SCAN_DIRS = ("api/app", "web/app", "web/components")
IGNORED_PATH_PARTS = {"tests", "__tests__", "node_modules", ".next", "dist", "build", ".git"}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _iter_runtime_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    for rel in RUNTIME_SCAN_DIRS:
        base = project_root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in RUNTIME_SCAN_SUFFIXES:
                continue
            if any(part in IGNORED_PATH_PARTS for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def _python_app_files(project_root: Path) -> list[Path]:
    base = project_root / "api" / "app"
    if not base.exists():
        return []
    return sorted(path for path in base.rglob("*.py") if path.is_file())


def _module_layer(relative_path: str) -> str:
    value = relative_path.replace("\\", "/")
    if "/routers/" in value:
        return "routers"
    if "/services/" in value:
        return "services"
    if "/models/" in value:
        return "models"
    if "/adapters/" in value:
        return "adapters"
    return "other"


def _imported_modules(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if isinstance(alias.name, str) and alias.name.strip():
                    out.append(alias.name.strip())
        elif isinstance(node, ast.ImportFrom):
            if isinstance(node.module, str) and node.module.strip():
                out.append(node.module.strip())
    return out


def _scan_architecture(project_root: Path, policy: dict[str, int]) -> dict[str, Any]:
    files = _python_app_files(project_root)
    large_threshold = int(policy["large_module_lines"])
    very_large_threshold = int(policy["very_large_module_lines"])
    long_fn_threshold = int(policy["long_function_lines"])

    layer_violations: list[dict[str, Any]] = []
    large_modules: list[dict[str, Any]] = []
    very_large_modules: list[dict[str, Any]] = []
    long_functions: list[dict[str, Any]] = []
    parse_errors: list[str] = []

    for path in files:
        rel = str(path.relative_to(project_root)).replace("\\", "/")
        layer = _module_layer(rel)
        source = _safe_read_text(path)
        if not source:
            continue
        lines = source.splitlines()
        line_count = len(lines)
        if line_count >= large_threshold:
            large_modules.append({"file": rel, "line_count": line_count})
        if line_count >= very_large_threshold:
            very_large_modules.append({"file": rel, "line_count": line_count})

        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            parse_errors.append(rel)
            continue

        for module in _imported_modules(tree):
            if layer == "models" and module.startswith(("app.services", "app.routers")):
                layer_violations.append(
                    {
                        "file": rel,
                        "layer": layer,
                        "forbidden_import": module,
                        "reason": "models should not depend on services/routers",
                    }
                )
            elif layer == "services" and module.startswith("app.routers"):
                layer_violations.append(
                    {
                        "file": rel,
                        "layer": layer,
                        "forbidden_import": module,
                        "reason": "services should not depend on routers",
                    }
                )

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.end_lineno is None:
                continue
            span = int(node.end_lineno) - int(node.lineno) + 1
            if span < long_fn_threshold:
                continue
            long_functions.append(
                {
                    "file": rel,
                    "function": node.name,
                    "line_count": span,
                    "line_start": int(node.lineno),
                }
            )

    large_modules.sort(key=lambda row: (int(row["line_count"]), row["file"]), reverse=True)
    very_large_modules.sort(key=lambda row: (int(row["line_count"]), row["file"]), reverse=True)
    long_functions.sort(key=lambda row: (int(row["line_count"]), row["file"]), reverse=True)

    return {
        "python_module_count": len(files),
        "layer_violations": layer_violations,
        "large_modules": large_modules,
        "very_large_modules": very_large_modules,
        "long_functions": long_functions,
        "parse_errors": parse_errors,
    }


def _should_ignore_placeholder_line(path: Path, line: str) -> bool:
    text = line.strip()
    if not text:
        return True
    # UI placeholder attributes are UX text, not fake runtime payload.
    if path.suffix.lower() in {".tsx", ".jsx"} and "placeholder=" in text.lower():
        return True
    if "placeholder:text-" in text.lower():
        return True
    if "command templates" in text.lower() and "placeholder" in text.lower():
        return True
    # Regex pattern declarations are scanner internals, not runtime placeholders.
    if "re.compile(" in text:
        return True
    return False


def _scan_runtime_placeholders(project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    scanned_files = _iter_runtime_files(project_root)

    for path in scanned_files:
        rel = str(path.relative_to(project_root)).replace("\\", "/")
        source = _safe_read_text(path)
        if not source:
            continue
        for idx, line in enumerate(source.splitlines(), start=1):
            if _should_ignore_placeholder_line(path, line):
                continue
            for finding_type, pattern in PLACEHOLDER_PATTERNS:
                if not pattern.search(line):
                    continue
                findings.append(
                    {
                        "file": rel,
                        "line": idx,
                        "type": finding_type,
                        "snippet": line.strip()[:220],
                    }
                )
                break

    findings.sort(key=lambda row: (row["file"], int(row["line"]), row["type"]))
    return {
        "scanned_file_count": len(scanned_files),
        "findings": findings,
    }


def evaluate_regression_against_baseline(summary: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    if not baseline:
        return {"regression": False, "reasons": []}

    expected = {
        "max_layer_violation_count": int(summary.get("layer_violation_count", 0)),
        "max_large_module_count": int(summary.get("large_module_count", 0)),
        "max_very_large_module_count": int(summary.get("very_large_module_count", 0)),
        "max_long_function_count": int(summary.get("long_function_count", 0)),
        "max_placeholder_count": int(summary.get("placeholder_count", 0)),
        "max_risk_score": int(summary.get("risk_score", 0)),
    }

    reasons: list[str] = []
    for key, actual in expected.items():
        limit = int(baseline.get(key, actual))
        if actual > limit:
            reasons.append(f"{key}: {actual} > baseline {limit}")

    return {"regression": len(reasons) > 0, "reasons": reasons}


def _severity_for_score(risk_score: int, policy: dict[str, int]) -> str:
    if risk_score >= int(policy["blocking_risk_score"]):
        return "high"
    if risk_score >= int(policy["warning_risk_score"]):
        return "medium"
    return "low"


def _task_roi(value_to_whole: float, estimated_cost_hours: float) -> float:
    if estimated_cost_hours <= 0:
        return 0.0
    return round(float(value_to_whole) / float(estimated_cost_hours), 4)


def _recommended_tasks(summary: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    layer_violations = int(summary.get("layer_violation_count", 0))
    large_modules = int(summary.get("large_module_count", 0))
    very_large_modules = int(summary.get("very_large_module_count", 0))
    long_functions = int(summary.get("long_function_count", 0))
    placeholders = int(summary.get("placeholder_count", 0))
    risk_score = int(summary.get("risk_score", 0))

    if layer_violations > 0 or large_modules > 0 or very_large_modules > 0 or long_functions > 0:
        estimated_cost = round(
            1.5
            + (layer_violations * 2.0)
            + (very_large_modules * 1.25)
            + (large_modules * 0.75)
            + (long_functions * 0.1),
            2,
        )
        value = round(min(100.0, 18.0 + risk_score * 0.85), 2)
        tasks.append(
            {
                "task_id": "architecture-modularization-review",
                "title": "Architecture modularization review",
                "direction": (
                    "Refactor high-risk modules and remove cross-layer dependencies. "
                    "Split oversized files and long functions, then re-run maintainability audit."
                ),
                "estimated_cost_hours": estimated_cost,
                "value_to_whole": value,
                "roi_estimate": _task_roi(value, estimated_cost),
                "priority": "high" if risk_score >= 90 else "medium",
            }
        )

    if placeholders > 0:
        estimated_cost = round(1.0 + placeholders * 0.4, 2)
        value = round(min(100.0, 12.0 + placeholders * 8.0), 2)
        tasks.append(
            {
                "task_id": "runtime-placeholder-elimination",
                "title": "Runtime placeholder elimination",
                "direction": (
                    "Replace runtime mock/fake/placeholder markers with production-grade logic or tracked backlog tasks."
                ),
                "estimated_cost_hours": estimated_cost,
                "value_to_whole": value,
                "roi_estimate": _task_roi(value, estimated_cost),
                "priority": "high",
            }
        )

    tasks.sort(key=lambda row: float(row.get("roi_estimate", 0.0)), reverse=True)
    return tasks


def build_maintainability_audit(
    *,
    project_root: Path | None = None,
    baseline: dict[str, Any] | None = None,
    policy: dict[str, int] | None = None,
) -> dict[str, Any]:
    root = project_root or _project_root()
    merged_policy = dict(DEFAULT_POLICY)
    if policy:
        merged_policy.update({k: int(v) for k, v in policy.items() if k in merged_policy})

    architecture = _scan_architecture(root, merged_policy)
    placeholders = _scan_runtime_placeholders(root)

    layer_violation_count = len(architecture["layer_violations"])
    large_module_count = len(architecture["large_modules"])
    very_large_module_count = len(architecture["very_large_modules"])
    long_function_count = len(architecture["long_functions"])
    placeholder_count = len(placeholders["findings"])

    risk_score = (
        layer_violation_count * 25
        + very_large_module_count * 15
        + large_module_count * 8
        + long_function_count * 2
        + placeholder_count * 10
    )
    severity = _severity_for_score(risk_score, merged_policy)
    regression = evaluate_regression_against_baseline(
        summary={
            "layer_violation_count": layer_violation_count,
            "large_module_count": large_module_count,
            "very_large_module_count": very_large_module_count,
            "long_function_count": long_function_count,
            "placeholder_count": placeholder_count,
            "risk_score": risk_score,
        },
        baseline=baseline or {},
    )

    summary = {
        "python_module_count": int(architecture["python_module_count"]),
        "runtime_file_count": int(placeholders["scanned_file_count"]),
        "layer_violation_count": layer_violation_count,
        "large_module_count": large_module_count,
        "very_large_module_count": very_large_module_count,
        "long_function_count": long_function_count,
        "placeholder_count": placeholder_count,
        "risk_score": int(risk_score),
        "severity": severity,
        "blocking_gap": severity == "high",
        "regression": bool(regression["regression"]),
        "regression_reasons": regression["reasons"],
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": merged_policy,
        "baseline": baseline or {},
        "summary": summary,
        "architecture": architecture,
        "placeholder_scan": placeholders,
        "recommended_tasks": _recommended_tasks(summary),
    }


def baseline_from_summary(summary: dict[str, Any]) -> dict[str, int]:
    return {
        "max_layer_violation_count": int(summary.get("layer_violation_count", 0)),
        "max_large_module_count": int(summary.get("large_module_count", 0)),
        "max_very_large_module_count": int(summary.get("very_large_module_count", 0)),
        "max_long_function_count": int(summary.get("long_function_count", 0)),
        "max_placeholder_count": int(summary.get("placeholder_count", 0)),
        "max_risk_score": int(summary.get("risk_score", 0)),
    }


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, Any] = {}
    for key in BASELINE_KEYS:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            out[key] = int(value)
    return out
