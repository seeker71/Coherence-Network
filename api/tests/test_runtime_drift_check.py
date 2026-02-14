from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "check_runtime_drift.py"


def test_runtime_drift_check_passes_when_only_known_drift(tmp_path: Path) -> None:
    audit = {
        "missing_for_web": ["/api/search?q="],
        "agent_router": {"unmounted_paths": ["/agent/tasks"]},
    }
    allowlist = {
        "known_missing_for_web": ["/api/search?q="],
        "known_unmounted_agent_paths": ["/agent/tasks"],
    }
    audit_path = tmp_path / "audit.json"
    allow_path = tmp_path / "allow.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    allow_path.write_text(json.dumps(allowlist), encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(_script_path()), "--audit", str(audit_path), "--allowlist", str(allow_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_runtime_drift_check_fails_on_new_drift(tmp_path: Path) -> None:
    audit = {
        "missing_for_web": ["/api/new-endpoint"],
        "agent_router": {"unmounted_paths": ["/agent/new"]},
    }
    allowlist = {
        "known_missing_for_web": [],
        "known_unmounted_agent_paths": [],
    }
    audit_path = tmp_path / "audit.json"
    allow_path = tmp_path / "allow.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    allow_path.write_text(json.dumps(allowlist), encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(_script_path()), "--audit", str(audit_path), "--allowlist", str(allow_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1
    assert "exceeded baseline" in (r.stdout + r.stderr)
