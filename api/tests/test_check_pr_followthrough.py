from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "check_pr_followthrough.py"
    spec = importlib.util.spec_from_file_location("check_pr_followthrough", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_status_rollup_all_green_accepts_success_rows() -> None:
    mod = _load_module()
    ok, errors = mod._status_rollup_all_green(
        [
            {
                "__typename": "CheckRun",
                "name": "test",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
            },
            {
                "__typename": "StatusContext",
                "context": "Vercel",
                "state": "SUCCESS",
            },
        ]
    )
    assert ok is True
    assert errors == []


def test_is_merge_ready_rejects_requested_changes() -> None:
    mod = _load_module()
    ready, reason = mod._is_merge_ready(
        {
            "state": "OPEN",
            "isDraft": False,
            "mergeStateStatus": "CLEAN",
            "reviewDecision": "CHANGES_REQUESTED",
            "statusCheckRollup": [],
        }
    )
    assert ready is False
    assert "CHANGES_REQUESTED" in reason


def test_auto_merge_ready_stale_prs_merges_only_ready(monkeypatch) -> None:
    mod = _load_module()
    stale = [
        {"number": 101, "head": "codex/a"},
        {"number": 102, "head": "codex/b"},
    ]
    details = {
        101: {
            "state": "OPEN",
            "isDraft": False,
            "mergeStateStatus": "CLEAN",
            "reviewDecision": "",
            "statusCheckRollup": [
                {
                    "__typename": "CheckRun",
                    "name": "test",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                }
            ],
        },
        102: {
            "state": "OPEN",
            "isDraft": False,
            "mergeStateStatus": "BLOCKED",
            "reviewDecision": "",
            "statusCheckRollup": [],
        },
    }
    merged_calls: list[tuple[str, int, str]] = []

    monkeypatch.setattr(mod, "_pr_details", lambda repo, number: details[number])
    monkeypatch.setattr(mod, "_merge_pr", lambda repo, number, method: merged_calls.append((repo, number, method)))

    merged, skipped = mod._auto_merge_ready_stale_prs(
        repo="owner/repo",
        stale=stale,
        method="merge",
        limit=5,
        dry_run=False,
    )
    assert merged == [101]
    assert merged_calls == [("owner/repo", 101, "merge")]
    assert len(skipped) == 1
    assert skipped[0]["number"] == 102
    assert "merge_state" in skipped[0]["reason"]


def test_auto_merge_ready_stale_prs_dry_run_does_not_merge(monkeypatch) -> None:
    mod = _load_module()
    stale = [{"number": 201, "head": "codex/dry"}]

    monkeypatch.setattr(
        mod,
        "_pr_details",
        lambda repo, number: {
            "state": "OPEN",
            "isDraft": False,
            "mergeStateStatus": "CLEAN",
            "reviewDecision": "",
            "statusCheckRollup": [],
        },
    )

    merge_calls: list[int] = []
    monkeypatch.setattr(mod, "_merge_pr", lambda repo, number, method: merge_calls.append(number))

    merged, skipped = mod._auto_merge_ready_stale_prs(
        repo="owner/repo",
        stale=stale,
        method="merge",
        limit=1,
        dry_run=True,
    )
    assert merged == [201]
    assert skipped == []
    assert merge_calls == []
