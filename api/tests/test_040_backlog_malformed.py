"""Spec 040: project_manager load_backlog malformed file tests.

Verification scenarios from specs/040-project-manager-load-backlog-malformed-test.md.
All scenarios use real file I/O (tmp_path) with no mocks.
"""
import os
import sys

import pytest

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

from scripts import project_manager as pm


@pytest.fixture(autouse=True)
def reset_backlog_file():
    """Restore pm.BACKLOG_FILE to its original value after each test."""
    original = pm.BACKLOG_FILE
    yield
    pm.BACKLOG_FILE = original


def test_load_backlog_malformed_mixed_lines(tmp_path):
    """Scenario 1: numbered and unnumbered lines mixed — returns only numbered items."""
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
    """Scenario 2: all lines malformed — returns empty list, no crash."""
    p = tmp_path / "backlog.md"
    p.write_text(
        "This is a header\n"
        "- bullet point\n"
        "## Section title\n"
        "No numbers here\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == []


def test_load_backlog_only_numbered_items(tmp_path):
    """Scenario 3: all valid numbered items — returns all in order (regression guard)."""
    p = tmp_path / "backlog.md"
    p.write_text(
        "1. Alpha\n"
        "2. Beta\n"
        "3. Gamma\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Alpha", "Beta", "Gamma"]


def test_load_backlog_multi_digit_numbers(tmp_path):
    """Scenario 3 edge case: multi-digit numbers (10+) are also matched."""
    p = tmp_path / "backlog.md"
    p.write_text(
        "1. First\n"
        "10. Ten\n"
        "100. Hundred\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["First", "Ten", "Hundred"]


def test_load_backlog_comment_lines_excluded(tmp_path):
    """Scenario 4: comment lines (starting with #) are excluded even if otherwise valid."""
    p = tmp_path / "backlog.md"
    p.write_text(
        "# This is a comment\n"
        "1. Real item\n"
        "# Another comment\n"
        "2. Second real item\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Real item", "Second real item"]


def test_load_backlog_hash_inside_item_is_included(tmp_path):
    """Scenario 4 edge case: # inside item text (not at line start) IS included."""
    p = tmp_path / "backlog.md"
    p.write_text("1. # item with hash inside\n")
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["# item with hash inside"]
