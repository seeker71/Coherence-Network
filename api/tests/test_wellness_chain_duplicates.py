"""Regression test: the chain organ tolerates duplicate ``test:`` keys.

A spec frontmatter that carried two ``test:`` keys (YAML list form
followed by a scalar, or vice versa) used to silently break the chain
organ — its regex stopped at the second ``test:`` line and captured an
empty group, mis-classifying the spec as "no proof claimed."

The fix: ``re.findall`` with a lookahead terminator concatenates every
``test:`` block, and the duplicate is surfaced as a soft warning so the
next author cleans up the YAML smell.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_wellness(monkeypatch, root: Path):
    """Import ``scripts/wellness_check.py`` with ``ROOT`` pointed at ``root``."""
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "scripts" / "wellness_check.py"
    spec = importlib.util.spec_from_file_location("wellness_check_under_test", src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wellness_check_under_test"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", root)
    return mod


def _write_spec(specs_dir: Path, stem: str, frontmatter: str) -> None:
    specs_dir.mkdir(parents=True, exist_ok=True)
    (specs_dir / f"{stem}.md").write_text(f"---\n{frontmatter}\n---\n\nbody\n")


def test_duplicate_test_keys_do_not_false_no_proof(monkeypatch, tmp_path):
    """Two ``test:`` keys still read as proof-claimed, and the warning fires."""
    specs_dir = tmp_path / "specs"
    src_path = tmp_path / "api" / "app" / "foo.py"
    src_path.parent.mkdir(parents=True)
    src_path.write_text("# present")
    test_path = tmp_path / "api" / "tests" / "test_foo.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_foo(): pass")

    _write_spec(
        specs_dir,
        "dup-test-keys",
        "status: done\n"
        "idea_id: foo\n"
        "source:\n"
        "  - file: api/app/foo.py\n"
        "test:\n"
        "  - cd api && pytest tests/test_foo.py\n"
        "test: cd api && pytest tests/test_foo.py\n",
    )

    mod = _load_wellness(monkeypatch, tmp_path)
    out = "\n".join(mod.sense_chain())

    assert "no proof claimed" not in out, out
    assert "duplicate `test:` keys" in out, out
    assert "dup-test-keys" in out, out


def test_single_test_key_emits_no_duplicate_warning(monkeypatch, tmp_path):
    """A clean single ``test:`` key keeps the warning silent."""
    specs_dir = tmp_path / "specs"
    src_path = tmp_path / "api" / "app" / "foo.py"
    src_path.parent.mkdir(parents=True)
    src_path.write_text("# present")
    test_path = tmp_path / "api" / "tests" / "test_foo.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_foo(): pass")

    _write_spec(
        specs_dir,
        "clean-test-key",
        "status: done\n"
        "idea_id: foo\n"
        "source:\n"
        "  - file: api/app/foo.py\n"
        "test: cd api && pytest tests/test_foo.py\n",
    )

    mod = _load_wellness(monkeypatch, tmp_path)
    out = "\n".join(mod.sense_chain())

    assert "duplicate `test:` keys" not in out, out
    assert "no proof claimed" not in out, out
