from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def _load_validator():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "validate_commit_evidence.py"
    spec = importlib.util.spec_from_file_location("validate_commit_evidence", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _record(change_files: list[str], change_intent: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "date": "2026-04-24",
        "thread_branch": "codex/evidence-test",
        "commit_scope": "test",
        "files_owned": change_files,
        "local_validation": {"status": "pass"},
        "ci_validation": {"status": "pending"},
        "deploy_validation": {"status": "pending"},
        "phase_gate": {"can_move_next_phase": False},
        "idea_ids": ["evidence-test"],
        "spec_ids": ["evidence-test"],
        "task_ids": ["evidence-test"],
        "contributors": [
            {
                "contributor_id": "openai-codex",
                "contributor_type": "machine",
                "roles": ["validation"],
            }
        ],
        "agent": {"name": "OpenAI Codex", "version": "test"},
        "evidence_refs": ["unit test"],
        "change_files": change_files,
        "change_intent": change_intent,
    }
    if change_intent in {"runtime_feature", "runtime_fix"}:
        payload["e2e_validation"] = {
            "status": "pending",
            "expected_behavior_delta": "runtime behavior changes",
            "public_endpoints": ["/api/test"],
            "test_flows": ["run unit test"],
        }
    return payload


def test_aggregate_evidence_coverage_allows_separate_cells() -> None:
    mod = _load_validator()
    changed_files = [
        "api/app/services/memory_service.py",
        "api/tests/test_worktree_continuity_guard.py",
        "scripts/prompt_entry_gate.sh",
        "docs/system_audit/commit_evidence_2026-04-23_runtime.json",
        "docs/system_audit/commit_evidence_2026-04-24_process.json",
    ]
    records = [
        (
            Path("docs/system_audit/commit_evidence_2026-04-23_runtime.json"),
            _record(["api/app/services/memory_service.py"], "runtime_fix"),
        ),
        (
            Path("docs/system_audit/commit_evidence_2026-04-24_process.json"),
            _record(
                [
                    "api/tests/test_worktree_continuity_guard.py",
                    "scripts/prompt_entry_gate.sh",
                ],
                "process_only",
            ),
        ),
    ]

    assert mod._validate_aggregate_change_coverage(records, changed_files) == []


def test_aggregate_evidence_coverage_reports_missing_paths() -> None:
    mod = _load_validator()
    changed_files = [
        "api/app/services/memory_service.py",
        "scripts/prompt_entry_gate.sh",
        "docs/system_audit/commit_evidence_2026-04-24_process.json",
    ]
    records = [
        (
            Path("docs/system_audit/commit_evidence_2026-04-24_process.json"),
            _record(["scripts/prompt_entry_gate.sh"], "process_only"),
        )
    ]

    errors = mod._validate_aggregate_change_coverage(records, changed_files)

    assert errors
    assert "api/app/services/memory_service.py" in errors[0]
