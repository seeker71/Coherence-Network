"""Enforcement gate tests — file scope, task card validation,
direction size, hygiene catch-all, and credential routing.

Three flows cover the surface:

  · Enforcement gates (create_task): file scope soft gate / hard
    limit / under-limit pass; weak task card soft gate / bare-empty
    pass / complete-card pass; oversized direction soft gate /
    normal passes
  · Hygiene scoring + catch-all: clean score, flags for long
    direction / broad file scope / output bloat, low-score catch-all
    fires NEEDS_DECISION/FAILED, clean task passes all gates
  · Credential routing: token lookup (exact/stripped/case-insensitive/
    trailing-slash/no-match/empty-url/missing-keystore) + worker-
    loop repo filter logic across all branches
"""

from __future__ import annotations

import json
import os

import pytest

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service
from app.services.context_hygiene_service import summarize_task_context


def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0


def _full_task_card(*, files: list[str] | None = None, goal: str = "implement",
                    done_when: str = "tests pass",
                    commands: list[str] | None = None,
                    constraints: str = "no scope creep") -> dict:
    card: dict = {"goal": goal, "done_when": done_when,
                  "commands": commands if commands is not None else ["pytest"],
                  "constraints": constraints}
    if files is not None:
        card["files_allowed"] = files
    return card


def test_create_task_enforcement_gates(monkeypatch: pytest.MonkeyPatch):
    """Every gate in create_task: file scope (soft/hard/pass),
    task card (weak/bare-empty/complete), direction size (oversized/
    normal). Soft gates → NEEDS_DECISION with specific prompt codes;
    hard limits → FAILED; clean tasks → PENDING."""
    # File scope — 25 files is soft gate, 45 is hard, 10 passes.
    _reset(monkeypatch)
    files_25 = [f"api/app/services/mod_{i}.py" for i in range(25)]
    soft = agent_service.create_task(AgentTaskCreate(
        direction="refactor many modules", task_type=TaskType.IMPL,
        context={"task_card": _full_task_card(files=files_25),
                 "files_allowed": files_25},
    ))
    assert soft["status"] == TaskStatus.NEEDS_DECISION
    assert "BROAD_FILE_SCOPE" in soft["decision_prompt"]
    assert "25 files" in soft["decision_prompt"]

    _reset(monkeypatch)
    files_45 = [f"api/app/services/mod_{i}.py" for i in range(45)]
    hard = agent_service.create_task(AgentTaskCreate(
        direction="massive refactor", task_type=TaskType.IMPL,
        context={"task_card": _full_task_card(files=files_45),
                 "files_allowed": files_45},
    ))
    assert hard["status"] == TaskStatus.FAILED
    assert "FILE_SCOPE_HARD_LIMIT" in hard["output"]
    assert "45 files" in hard["output"]

    _reset(monkeypatch)
    files_10 = [f"api/app/services/mod_{i}.py" for i in range(10)]
    under_limit = agent_service.create_task(AgentTaskCreate(
        direction="small refactor", task_type=TaskType.IMPL,
        context={"task_card": _full_task_card(files=files_10),
                 "files_allowed": files_10},
    ))
    assert under_limit["status"] == TaskStatus.PENDING

    # Task card — weak (only goal) → soft gate; bare empty ctx → pass;
    # complete 5-field card → pass.
    _reset(monkeypatch)
    weak = agent_service.create_task(AgentTaskCreate(
        direction="vague", task_type=TaskType.IMPL,
        context={"task_card": {"goal": "vague"}},
    ))
    assert weak["status"] == TaskStatus.NEEDS_DECISION
    assert "WEAK_TASK_CARD" in weak["decision_prompt"]

    _reset(monkeypatch)
    bare = agent_service.create_task(AgentTaskCreate(
        direction="simple bare task", task_type=TaskType.IMPL, context={},
    ))
    assert bare["status"] == TaskStatus.PENDING
    assert bare.get("decision_prompt") is None

    _reset(monkeypatch)
    one_file = ["api/app/main.py"]
    complete = agent_service.create_task(AgentTaskCreate(
        direction="Add health check endpoint", task_type=TaskType.IMPL,
        context={"task_card": {
            "goal": "Add /health endpoint", "files_allowed": one_file,
            "done_when": "tests pass", "commands": ["pytest"],
            "constraints": "none",
        }, "files_allowed": one_file},
    ))
    assert complete["status"] == TaskStatus.PENDING
    assert complete.get("decision_prompt") is None

    # Direction size — 3500 chars soft, 500 passes.
    _reset(monkeypatch)
    oversized = agent_service.create_task(AgentTaskCreate(
        direction="x" * 3500, task_type=TaskType.IMPL,
        context={"task_card": _full_task_card(files=one_file),
                 "files_allowed": one_file},
    ))
    assert oversized["status"] == TaskStatus.NEEDS_DECISION
    assert "OVERSIZED_DIRECTION" in oversized["decision_prompt"]
    assert "3500 chars" in oversized["decision_prompt"]

    _reset(monkeypatch)
    normal = agent_service.create_task(AgentTaskCreate(
        direction="y" * 500, task_type=TaskType.IMPL,
        context={"task_card": _full_task_card(files=one_file),
                 "files_allowed": one_file},
    ))
    assert normal["status"] == TaskStatus.PENDING


def test_hygiene_scoring_and_catchall(monkeypatch: pytest.MonkeyPatch):
    """Hygiene scoring flags specific issues (long_direction,
    broad_file_scope, output_bloat) while keeping clean tasks near
    100. The catch-all fires NEEDS_DECISION or FAILED when enough
    medium/high flags drop score < 40 without any specific gate
    tripping. A well-formed task with few files + short direction
    passes every gate."""
    # Hygiene scoring — clean near 100.
    clean = summarize_task_context({"direction": "Short task",
                                    "context": {}, "output": ""})
    assert clean["score"] >= 90

    long_dir = summarize_task_context({"direction": "x" * 1500,
                                       "context": {}, "output": ""})
    assert any(f["id"] == "long_direction" for f in long_dir["flags"])

    broad = summarize_task_context({"direction": "task",
                                    "context": {"files_allowed": [f"f{i}.py" for i in range(15)]},
                                    "output": ""})
    assert any(f["id"] == "broad_file_scope" for f in broad["flags"])

    bloat = summarize_task_context({"direction": "task",
                                    "context": {}, "output": "z" * 2500})
    assert any(f["id"] == "output_bloat" for f in bloat["flags"])

    # Catch-all — 19 files + 2900 char direction + large context +
    # many commands + many guard agents → score < 40 → not PENDING.
    _reset(monkeypatch)
    catchall_files = [f"api/app/services/mod_{i}.py" for i in range(19)]
    catchall = agent_service.create_task(AgentTaskCreate(
        direction="A" * 2900, task_type=TaskType.IMPL,
        context={"task_card": _full_task_card(files=catchall_files),
                 "files_allowed": catchall_files,
                 "commands": [f"cmd_{i}" for i in range(10)],
                 "guard_agents": ["a", "b", "c", "d"],
                 "extra_notes": "B" * 3000},
    ))
    assert catchall["status"] in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)

    # Clean task passes every gate.
    _reset(monkeypatch)
    clean_files = ["api/app/services/agent_service_crud.py", "api/app/models/agent.py"]
    passes = agent_service.create_task(AgentTaskCreate(
        direction="Add a new field to the task model",
        task_type=TaskType.IMPL,
        context={"task_card": {
            "goal": "Add new field", "files_allowed": clean_files,
            "done_when": "tests pass", "commands": ["pytest"],
            "constraints": "none",
        }, "files_allowed": clean_files},
    ))
    assert passes["status"] == TaskStatus.PENDING
    assert passes.get("decision_prompt") is None


def test_credential_routing(tmp_path):
    """Token lookup by repo URL + worker-loop repo filter. Token
    lookup is case-insensitive, protocol-agnostic, trailing-slash
    forgiving; returns None on no match, empty URL, or missing
    keystore. Worker-loop filter: --repo flag restricts to matching
    repos, auto-filter (no flag) skips tasks without tokens, no
    workspace URL always passes."""

    def write_keys(tokens: dict) -> str:
        ks_dir = os.path.join(str(tmp_path), ".coherence-network")
        os.makedirs(ks_dir, exist_ok=True)
        ks_path = os.path.join(ks_dir, "keys.json")
        with open(ks_path, "w") as f:
            json.dump({"repo_tokens": tokens}, f)
        return ks_path

    def get_token(repo_url: str, ks_path: str) -> str | None:
        """Mirror of _get_repo_token in local_runner.py."""
        if not repo_url:
            return None
        if os.path.exists(ks_path):
            try:
                with open(ks_path, encoding="utf-8") as f:
                    ks = json.load(f)
                normalized = repo_url.lower().replace("https://", "").replace("http://", "").rstrip("/")
                for rurl, token in ks.get("repo_tokens", {}).items():
                    nrurl = rurl.lower().replace("https://", "").replace("http://", "").rstrip("/")
                    if nrurl == normalized:
                        return token
            except Exception:
                pass
        return None

    def should_skip(task_url: str, repo_filter: str, has_token: bool) -> bool:
        """Mirror of worker-loop credential gate."""
        if repo_filter:
            norm_filter = repo_filter.lower().replace("https://", "").replace("http://", "").rstrip("/")
            norm_task = task_url.lower().replace("https://", "").replace("http://", "").rstrip("/")
            if norm_task and norm_task != norm_filter:
                return True
        elif task_url and not has_token:
            return True
        return False

    # Token lookup — every normalization case.
    ks = write_keys({"https://github.com/user/repo": "ghp_token123"})
    assert get_token("https://github.com/user/repo", ks) == "ghp_token123"
    assert get_token("github.com/user/repo", ks) == "ghp_token123"  # protocol stripped

    ks_case = write_keys({"https://GitHub.com/User/Repo": "ghp_case"})
    assert get_token("https://github.com/user/repo", ks_case) == "ghp_case"

    ks_slash = write_keys({"https://github.com/user/repo/": "ghp_slash"})
    assert get_token("https://github.com/user/repo", ks_slash) == "ghp_slash"

    ks_other = write_keys({"https://github.com/user/other-repo": "ghp_other"})
    assert get_token("https://github.com/user/repo", ks_other) is None

    assert get_token("", ks_other) is None
    assert get_token("https://github.com/user/repo",
                     os.path.join(str(tmp_path), "nope", "keys.json")) is None

    # Worker-loop repo filter — every branch of the gate.
    # --repo flag matching URL passes.
    assert not should_skip("https://github.com/user/repo",
                           "https://github.com/user/repo", True)
    # --repo flag mismatch → skipped.
    assert should_skip("https://github.com/user/other",
                       "https://github.com/user/repo", True)
    # Normalization applies to filter comparison.
    assert not should_skip("github.com/User/Repo/",
                           "https://GitHub.com/user/repo", True)
    # Auto-filter (no --repo), no token → skipped.
    assert should_skip("https://github.com/user/repo", "", False)
    # Auto-filter with token → passes.
    assert not should_skip("https://github.com/user/repo", "", True)
    # Empty task URL always passes (nothing to mismatch).
    assert not should_skip("", "", False)
    assert not should_skip("", "https://github.com/user/repo", False)
