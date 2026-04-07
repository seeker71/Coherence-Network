#!/usr/bin/env python3
"""Pinned-idea (portfolio-governance) acceptance: one path, proof at each step.

Guidance: Run after the agent has done spec → impl → test → review. This script
runs the checklist in order and prints [PROOF] for each step so you have required
data and files that passed.

Steps: 1) No placeholder/mock in spec+impl  2) Spec quality gate  3) Pytest  4) Live API (real data).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / ".cache"
STATE_FILE = STATE_DIR / "pinned_idea_acceptance_state.json"

NO_PLACEHOLDER_FILES = [
    "specs/ideas-prioritization.md",
    "api/app/routers/ideas.py",
    "api/app/services/idea_service.py",
    "api/app/models/idea.py",
]
FORBIDDEN_TOKENS = re.compile(
    r"\b(placeholder|mock\s+data|fake\s+data|dummy\s+data|lorem\s+ipsum|example\.com|TODO\s*:.*implement|FIXME\s*:.*implement)\b",
    re.IGNORECASE,
)


def _proof(step_id: str, evidence: dict) -> None:
    print(f"[PROOF] {step_id}: {json.dumps(evidence, indent=2)}", flush=True)


def _run_no_placeholder(idea_id: str) -> tuple[int, str, str | None]:
    hits: list[str] = []
    for rel in NO_PLACEHOLDER_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        raw = path.read_text(errors="replace")
        for m in FORBIDDEN_TOKENS.finditer(raw):
            line = raw[: m.start()].count("\n") + 1
            hits.append(f"{rel}:{line}: {m.group(0)!r}")
    if hits:
        return 1, "\n".join(hits[:20]), "Remove placeholder/mock/fake/TODO implement from spec and implementation files."
    _proof("step_1_no_placeholder", {"files_checked": NO_PLACEHOLDER_FILES, "result": "no_forbidden_tokens"})
    return 0, "No placeholder/mock in spec and impl files.", None


def _run_spec_quality(idea_id: str) -> tuple[int, str, str | None]:
    spec_file = "specs/ideas-prioritization.md"
    cmd = [sys.executable, "scripts/validate_spec_quality.py", "--file", spec_file]
    p = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        return p.returncode, out, f"Fix spec: run {' '.join(cmd)} and address reported gaps."
    path = REPO_ROOT / spec_file
    text = path.read_text(errors="replace")
    has = {s: (s in text and f"## {s}" in text or f"**{s}**" in text) for s in ["Purpose", "Requirements", "Verification", "Risks", "Known Gaps"]}
    _proof("step_2_spec_quality", {"spec_file": spec_file, "validator_exit": 0, "sections_present": has})
    return 0, out, None


def _run_pytest_ideas(idea_id: str) -> tuple[int, str, str | None]:
    cmd = [sys.executable, "-m", "pytest", "-q", "tests/test_ideas.py"]
    p = subprocess.run(cmd, cwd=REPO_ROOT / "api", capture_output=True, text=True, timeout=180)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        return p.returncode, out, "Fix tests: cd api && pytest -q tests/test_ideas.py."
    passed = 0
    for line in out.splitlines():
        if " passed" in line:
            try:
                passed = int(line.strip().split()[0])
            except (ValueError, IndexError):
                pass
            break
    _proof("step_3_pytest", {"command": "pytest -q tests/test_ideas.py", "exit_code": 0, "tests_passed": passed, "output_tail": out.strip()[-400:]})
    return 0, out, None


def _run_curl_ideas(idea_id: str) -> tuple[int, str, str | None]:
    api_url = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
    cmd = ["curl", "-sS", f"{api_url}/api/ideas?only_unvalidated=true"]
    p = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        return p.returncode, out, "Start API: cd api && uvicorn app.main:app --port 8000, then re-run."
    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        return 1, out[:500], f"API response is not JSON: {e}"
    ideas = data.get("ideas") or []
    summary = data.get("summary") or {}
    if not isinstance(ideas, list) or not isinstance(summary, dict):
        return 1, out[:500], "Response missing ideas or summary."
    if summary.get("total_ideas", 0) < 1 or len(ideas) < 1:
        return 1, out[:500], "ideas list or total_ideas is empty."
    for i, idea in enumerate(ideas[:3]):
        if not isinstance(idea, dict) or not idea.get("id") or "free_energy_score" not in idea:
            return 1, out[:500], f"ideas[{i}] missing id or free_energy_score."
    first_ids = [ideas[i].get("id") for i in range(min(3, len(ideas)))]
    _proof("step_4_live_api", {
        "url": f"{api_url}/api/ideas?only_unvalidated=true",
        "status": 200,
        "summary": {k: summary.get(k) for k in ["total_ideas", "unvalidated_ideas", "validated_ideas"]},
        "ideas_returned": len(ideas),
        "first_idea_ids": first_ids,
        "shape_ok": True,
    })
    return 0, out[:600], None


def main() -> int:
    idea_id = os.environ.get("PINNED_IDEA_ID", "portfolio-governance")
    force = "--force" in sys.argv or os.environ.get("PINNED_IDEA_FORCE", "")
    state_file = STATE_DIR / "pinned_idea_acceptance_state.json"
    state: dict = {}
    if state_file.exists() and not force:
        try:
            state = json.loads(state_file.read_text())
            if state.get("idea_id") != idea_id:
                state = {}
        except (json.JSONDecodeError, OSError):
            state = {}

    steps = [
        ("step_1_no_placeholder", "No placeholder/mock in spec+impl", _run_no_placeholder),
        ("step_2_spec_quality", "Spec quality gate", _run_spec_quality),
        ("step_3_pytest", "Pytest ideas", _run_pytest_ideas),
        ("step_4_live_api", "Live API real data", _run_curl_ideas),
    ]
    to_run = steps if force else [s for s in steps if state.get("steps", {}).get(s[0]) != "ok"]
    if not to_run and not force:
        print("[PROOF] all steps already passed (use --force to re-run).", flush=True)
        return 0

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for step_id, label, run_fn in to_run:
        print(f"[STATUS] {step_id} {label}", flush=True)
        code, out, suggested = run_fn(idea_id)
        if out and not out.startswith("[PROOF]"):
            print(out.strip()[:1200], flush=True)
        if code != 0:
            print(f"[FAILURE] {json.dumps({'step': step_id, 'suggested_action': suggested})}", flush=True)
            state["steps"] = state.get("steps", {}) | {step_id: "failed"}
            state["idea_id"] = idea_id
            state_file.write_text(json.dumps(state, indent=2))
            return code
        state["steps"] = state.get("steps", {}) | {step_id: "ok"}
        state["last_completed_step"] = step_id
        state["idea_id"] = idea_id
        state_file.write_text(json.dumps(state, indent=2))
    print("[PROOF] acceptance_complete: all steps passed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
