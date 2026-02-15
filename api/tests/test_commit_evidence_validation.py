from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "validate_commit_evidence.py"


def _base_payload() -> dict:
    return {
        "date": "2026-02-14",
        "thread_branch": "codex/example",
        "commit_scope": "Example",
        "files_owned": ["docs/a.md"],
        "idea_ids": ["coherence-network-agent-pipeline"],
        "spec_ids": ["054"],
        "task_ids": ["example-task"],
        "contributors": [
            {
                "contributor_id": "openai-codex",
                "contributor_type": "machine",
                "roles": ["implementation"],
            }
        ],
        "agent": {"name": "OpenAI Codex", "version": "gpt-5"},
        "evidence_refs": ["pytest api/tests/test_commit_evidence_validation.py -q"],
        "change_files": ["scripts/validate_commit_evidence.py"],
        "change_intent": "process_only",
        "local_validation": {"status": "pass"},
        "ci_validation": {"status": "pending"},
        "deploy_validation": {"status": "pending"},
        "phase_gate": {"can_move_next_phase": False, "blocked_by": ["ci_validation", "deploy_validation"]},
    }


def test_validate_commit_evidence_passes_for_valid_pending_gate(tmp_path: Path) -> None:
    evidence = tmp_path / "commit_evidence_valid.json"
    evidence.write_text(json.dumps(_base_payload()), encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(_script_path()), "--file", str(evidence)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_validate_commit_evidence_fails_when_gate_true_without_ci_deploy_pass(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["phase_gate"]["can_move_next_phase"] = True
    evidence = tmp_path / "commit_evidence_invalid.json"
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(_script_path()), "--file", str(evidence)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "requires ci_validation.status=pass" in (r.stdout + r.stderr)


def test_validate_commit_evidence_fails_when_runtime_intent_has_no_runtime_changes(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["change_intent"] = "runtime_feature"
    payload["change_files"] = ["scripts/validate_commit_evidence.py"]
    payload["e2e_validation"] = {
        "status": "pending",
        "expected_behavior_delta": "New endpoint returns enriched runtime data.",
        "public_endpoints": ["https://coherence-network-production.up.railway.app/api/inventory/system-lineage"],
        "test_flows": ["portfolio-load->api-summary->roi-render"],
    }
    evidence = tmp_path / "commit_evidence_runtime_missing_runtime_files.json"
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    r = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--file",
            str(evidence),
            "--base",
            "HEAD",
            "--head",
            "HEAD",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "requires runtime changes" in (r.stdout + r.stderr)


def test_validate_commit_evidence_fails_when_runtime_intent_missing_e2e_block(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["change_intent"] = "runtime_fix"
    payload["change_files"] = ["api/app/routers/inventory.py"]
    evidence = tmp_path / "commit_evidence_runtime_missing_e2e.json"
    evidence.write_text(json.dumps(payload), encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(_script_path()), "--file", str(evidence)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "requires e2e_validation object" in (r.stdout + r.stderr)
