from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


def _load_module():
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_pr_followthrough.py"
    spec = importlib.util.spec_from_file_location("check_pr_followthrough", script)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_repo_falls_back_to_git_remote_when_graphql_is_exhausted(monkeypatch):
    module = _load_module()

    def exhausted(_args):
        raise subprocess.CalledProcessError(1, ["gh"])

    monkeypatch.setattr(module, "_run_gh", exhausted)
    monkeypatch.setattr(module, "_repo_from_git_remote", lambda: "seeker71/Coherence-Network")

    assert module._resolve_repo("") == "seeker71/Coherence-Network"


def test_list_open_prs_falls_back_to_rest_shape(monkeypatch):
    module = _load_module()
    calls = []

    def fake_run(args):
        calls.append(args)
        if args[:2] == ["pr", "list"]:
            raise subprocess.CalledProcessError(1, ["gh", *args])
        if args[:2] == ["api", "repos/seeker71/Coherence-Network/pulls"]:
            return json.dumps(
                [
                    {
                        "number": 123,
                        "title": "fix: breathe",
                        "head": {"ref": "codex/substrate-form-access-fallback-20260528"},
                        "updated_at": "2026-05-28T14:00:00Z",
                        "html_url": "https://github.com/seeker71/Coherence-Network/pull/123",
                        "draft": False,
                    }
                ]
            )
        raise AssertionError(args)

    monkeypatch.setattr(module, "_run_gh", fake_run)

    assert module._list_open_prs("seeker71/Coherence-Network") == [
        {
            "number": 123,
            "title": "fix: breathe",
            "headRefName": "codex/substrate-form-access-fallback-20260528",
            "updatedAt": "2026-05-28T14:00:00Z",
            "url": "https://github.com/seeker71/Coherence-Network/pull/123",
            "isDraft": False,
        }
    ]
    assert calls[0][:2] == ["pr", "list"]
    assert calls[1][:2] == ["api", "repos/seeker71/Coherence-Network/pulls"]
