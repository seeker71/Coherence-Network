from __future__ import annotations

from pathlib import Path

from scripts import local_runner


def test_impl_without_spec_becomes_needs_decision(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(local_runner, "_get_repo_dir", lambda: tmp_path)
    monkeypatch.setattr(
        local_runner,
        "api",
        lambda method, path, body=None: calls.append((method, path, body or {})) or {"status": body["status"]},
    )

    blocked = local_runner._block_impl_without_active_spec(
        "task_no_spec",
        {"context": {"idea_id": "missing-spec", "spec_path": "none"}},
    )

    assert blocked is True
    body = calls[0][2]
    assert body["status"] == "needs_decision"
    assert "NO_SPEC_GATE" in body["decision_prompt"]
    assert body["context"]["failure_reason_bucket"] == "spec_gate"
    assert body["context"]["failure_signature"] == "impl_without_active_spec"


def test_impl_without_idea_id_uses_spec_id_for_spec_gate(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(local_runner, "_get_repo_dir", lambda: tmp_path)
    monkeypatch.setattr(
        local_runner,
        "api",
        lambda method, path, body=None: calls.append((method, path, body or {})) or {"status": body["status"]},
    )

    blocked = local_runner._block_impl_without_active_spec(
        "task_spec_gap",
        {"context": {"source": "spec_implementation_gap", "spec_id": "089", "spec_path": "specs/089-missing.md"}},
    )

    assert blocked is True
    body = calls[0][2]
    assert body["status"] == "needs_decision"
    assert "NO_SPEC_GATE" in body["decision_prompt"]
    assert body["context"]["failure_reason_bucket"] == "spec_gate"
    assert body["context"]["failure_signature"] == "impl_without_active_spec"


def test_impl_without_idea_id_blocks_done_spec_by_spec_id(monkeypatch, tmp_path: Path) -> None:
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    spec_path = spec_dir / "089-done.md"
    spec_path.write_text("---\nstatus: done\n---\n", encoding="utf-8")
    calls: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(local_runner, "_get_repo_dir", lambda: tmp_path)
    monkeypatch.setattr(
        local_runner,
        "api",
        lambda method, path, body=None: calls.append((method, path, body or {})) or {"status": body["status"]},
    )

    blocked = local_runner._block_impl_without_active_spec(
        "task_done_spec_id",
        {"context": {"source": "spec_implementation_gap", "spec_id": "089", "spec_path": "specs/089-done.md"}},
    )

    assert blocked is True
    body = calls[0][2]
    assert body["status"] == "needs_decision"
    assert "DONE_SPEC_GATE" in body["decision_prompt"]
    assert body["context"]["failure_reason_bucket"] == "done_spec_gate"
    assert body["context"]["failure_signature"] == "impl_for_done_spec"


def test_impl_for_done_spec_becomes_needs_decision(monkeypatch, tmp_path: Path) -> None:
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    spec_path = spec_dir / "done-idea.md"
    spec_path.write_text("---\nstatus: done\n---\n", encoding="utf-8")
    calls: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(local_runner, "_get_repo_dir", lambda: tmp_path)
    monkeypatch.setattr(
        local_runner,
        "api",
        lambda method, path, body=None: calls.append((method, path, body or {})) or {"status": body["status"]},
    )

    blocked = local_runner._block_impl_without_active_spec(
        "task_done_spec",
        {"context": {"idea_id": "done-idea", "spec_path": "specs/done-idea.md"}},
    )

    assert blocked is True
    body = calls[0][2]
    assert body["status"] == "needs_decision"
    assert "DONE_SPEC_GATE" in body["decision_prompt"]
    assert body["context"]["failure_reason_bucket"] == "done_spec_gate"
    assert body["context"]["failure_signature"] == "impl_for_done_spec"


def test_impl_with_active_spec_continues(monkeypatch, tmp_path: Path) -> None:
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    spec_path = spec_dir / "active-idea.md"
    spec_path.write_text("---\nstatus: active\n---\n", encoding="utf-8")
    monkeypatch.setattr(local_runner, "_get_repo_dir", lambda: tmp_path)

    blocked = local_runner._block_impl_without_active_spec(
        "task_active_spec",
        {"context": {"idea_id": "active-idea", "spec_path": "specs/active-idea.md"}},
    )

    assert blocked is False
