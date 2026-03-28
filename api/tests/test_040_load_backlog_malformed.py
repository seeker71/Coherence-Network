"""Tests for spec 040: load_backlog with malformed (missing number prefix) lines."""
import os
import sys

import pytest

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

from scripts import project_manager as pm


def test_load_backlog_skips_unnumbered_lines(tmp_path):
    """load_backlog returns only numbered items; unnumbered lines are skipped, order preserved."""
    p = tmp_path / "backlog.md"
    p.write_text(
        "1. First item\n"
        "Unnumbered line\n"
        "2. Second item\n"
        "Another line without number\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["First item", "Second item"]


def test_load_backlog_all_malformed_returns_empty(tmp_path):
    """load_backlog returns [] when every line lacks the numeric prefix."""
    p = tmp_path / "backlog_bad.md"
    p.write_text(
        "No number here\n"
        "Also no number\n"
        "Still nothing\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == []


def test_load_backlog_preserves_order_with_mixed_lines(tmp_path):
    """load_backlog preserves the order of numbered items even when interleaved with malformed lines."""
    p = tmp_path / "backlog_mixed.md"
    p.write_text(
        "Header text without number\n"
        "1. Alpha\n"
        "Some description line\n"
        "2. Beta\n"
        "Another description\n"
        "3. Gamma\n"
        "Footer line\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Alpha", "Beta", "Gamma"]


def test_load_backlog_comment_lines_excluded(tmp_path):
    """load_backlog excludes lines that start with # even if they have a number pattern."""
    p = tmp_path / "backlog_comments.md"
    p.write_text(
        "# 1. This is a comment that looks numbered\n"
        "1. Real item\n"
        "not numbered\n"
        "2. Another real item\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Real item", "Another real item"]
