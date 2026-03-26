"""Contract tests for public presence modularization.

These tests validate the shared-template/readme build pipeline in scripts/build_readmes.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_READMES_PATH = REPO_ROOT / "scripts" / "build_readmes.py"


def _load_build_readmes_module():
    spec = importlib.util.spec_from_file_location("build_readmes_module", BUILD_READMES_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_templates_cover_all_public_presences():
    module = _load_build_readmes_module()

    expected = {
        "README.template.md",
        "cli/README.template.md",
        "mcp-server/README.template.md",
        "skills/coherence-network/SKILL.template.md",
    }
    assert expected.issubset(set(module.TEMPLATES))


def test_output_path_rewrites_template_suffix():
    module = _load_build_readmes_module()

    assert module.output_path("README.template.md") == "README.md"
    assert module.output_path("cli/README.template.md") == "cli/README.md"


def test_expand_adds_header_and_expands_include(tmp_path, monkeypatch):
    module = _load_build_readmes_module()

    fragment_path = tmp_path / "docs" / "shared" / "fragment.md"
    fragment_path.parent.mkdir(parents=True, exist_ok=True)
    fragment_path.write_text("Fragment body line\n", encoding="utf-8")

    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))

    template_text = "before\n<!-- include: docs/shared/fragment.md -->\nafter\n"
    expanded = module.expand(template_text, "README.template.md")

    assert expanded.startswith(
        "<!-- AUTO-GENERATED from README.template.md. Edit the template, not this file. -->\n"
    )
    assert "before\nFragment body line\nafter\n" in expanded
    assert "<!-- include:" not in expanded


def test_expand_missing_fragment_exits_with_error(tmp_path, monkeypatch):
    module = _load_build_readmes_module()

    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))

    with pytest.raises(SystemExit) as exc:
        module.expand("<!-- include: docs/shared/missing.md -->\n", "README.template.md")

    assert exc.value.code == 1


def test_build_check_returns_false_when_output_is_outdated(tmp_path, monkeypatch):
    module = _load_build_readmes_module()

    template = tmp_path / "README.template.md"
    fragment = tmp_path / "docs" / "shared" / "lifecycle.md"
    output = tmp_path / "README.md"

    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_text("Current fragment content\n", encoding="utf-8")
    template.write_text("<!-- include: docs/shared/lifecycle.md -->\n", encoding="utf-8")
    output.write_text("stale output\n", encoding="utf-8")

    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(module, "TEMPLATES", ["README.template.md"])

    assert module.build(check=True) is False


def test_build_check_returns_true_when_output_matches_template(tmp_path, monkeypatch):
    module = _load_build_readmes_module()

    template = tmp_path / "README.template.md"
    fragment = tmp_path / "docs" / "shared" / "lifecycle.md"
    output = tmp_path / "README.md"

    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_text("Current fragment content\n", encoding="utf-8")
    template.write_text("<!-- include: docs/shared/lifecycle.md -->\n", encoding="utf-8")

    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(module, "TEMPLATES", ["README.template.md"])

    output.write_text(module.expand(template.read_text(encoding="utf-8"), "README.template.md"), encoding="utf-8")

    assert module.build(check=True) is True
