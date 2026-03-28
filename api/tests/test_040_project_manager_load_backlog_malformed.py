"""Tests for spec 040: load_backlog skips lines without the required N. prefix."""
import os
import sys

import pytest

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

from scripts import project_manager as pm


def test_load_backlog_mixed_numbered_and_unnumbered_lines(tmp_path, monkeypatch):
    """Backlog with both `N. ` lines and unnumbered lines returns only parsed items, order preserved."""
    monkeypatch.delenv("PIPELINE_META_BACKLOG", raising=False)
    monkeypatch.setenv("PIPELINE_META_RATIO", "0")
    p = tmp_path / "backlog.md"
    p.write_text(
        "1. First item\n"
        "Unnumbered line\n"
        "2. Second item\n"
        "Another line without number\n",
        encoding="utf-8",
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["First item", "Second item"]


def test_load_backlog_real_file_io_no_mocks(tmp_path, monkeypatch):
    """Uses real file I/O and real load_backlog (not mocked)."""
    monkeypatch.delenv("PIPELINE_META_BACKLOG", raising=False)
    monkeypatch.setenv("PIPELINE_META_RATIO", "0")
    path = tmp_path / "mixed.md"
    path.write_text("1. Alpha\nnot a task\n2. Beta\n", encoding="utf-8")
    assert path.is_file()
    pm.BACKLOG_FILE = str(path)
    assert pm.load_backlog() == ["Alpha", "Beta"]
