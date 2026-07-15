"""Changed-path selection for the Form validation shards."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "form_validate_shards.py"
SPEC = importlib.util.spec_from_file_location("form_validate_shards_under_test", SCRIPT)
assert SPEC and SPEC.loader
form_validate_shards = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = form_validate_shards
SPEC.loader.exec_module(form_validate_shards)


def test_changed_paths_reads_staged_changes(monkeypatch):
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        stdout = "form\n" if command == ["git", "diff", "--cached", "--name-only"] else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert form_validate_shards._changed_paths("base") == {"form"}
    assert ["git", "diff", "--cached", "--name-only"] in calls


def test_exact_form_gitlink_selects_full_suite(monkeypatch):
    monkeypatch.setattr(form_validate_shards, "_changed_paths", lambda _ref: {"form"})

    assert form_validate_shards._select_changed([], "base") is None


def test_similarly_named_paths_do_not_select_form_workloads(monkeypatch):
    monkeypatch.setattr(
        form_validate_shards,
        "_changed_paths",
        lambda _ref: {"format", "forms", "form-kernel-rust/src/lib.rs"},
    )

    assert form_validate_shards._select_changed([], "base") == []


def test_nested_kernel_path_still_selects_full_suite(monkeypatch):
    monkeypatch.setattr(
        form_validate_shards,
        "_changed_paths",
        lambda _ref: {"form/form-kernel-rust/src/lib.rs"},
    )

    assert form_validate_shards._select_changed([], "base") is None


def test_nested_stdlib_path_still_selects_dependent_workloads(monkeypatch):
    dependent = form_validate_shards.Workload("core-band", ("form-stdlib/core.fk",))
    unrelated = form_validate_shards.Workload("other-band", ("form-stdlib/other.fk",))
    monkeypatch.setattr(
        form_validate_shards,
        "_changed_paths",
        lambda _ref: {"form/form-stdlib/core.fk"},
    )

    assert form_validate_shards._select_changed([dependent, unrelated], "base") == [dependent]
