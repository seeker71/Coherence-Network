"""Spec 040: load_backlog malformed-line coverage.

Covers all 5 verification scenarios from
specs/040-project-manager-load-backlog-malformed-test.md.
"""
import os
import sys

import pytest

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

from scripts import project_manager as pm


# ---------------------------------------------------------------------------
# Scenario 1 — Canonical Malformed File (Happy Path)
# ---------------------------------------------------------------------------

def test_load_backlog_malformed_missing_number_prefix(tmp_path):
    r"""Mixed numbered/unnumbered: only \d+. items returned, order preserved."""
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


# ---------------------------------------------------------------------------
# Scenario 2 — All Lines Malformed (Edge: Nothing to Parse)
# ---------------------------------------------------------------------------

def test_load_backlog_all_malformed_returns_empty(tmp_path):
    """File with no numbered lines returns empty list, no exception."""
    p = tmp_path / "all_malformed.md"
    p.write_text("This is a heading\nAnother prose line\n- bullet point\n")
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == []


def test_load_backlog_whitespace_only_returns_empty(tmp_path):
    """File with only whitespace returns empty list."""
    p = tmp_path / "whitespace.md"
    p.write_text("   \n   \n\t\n")
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == []


# ---------------------------------------------------------------------------
# Scenario 3 — Comment Lines Are Also Skipped
# ---------------------------------------------------------------------------

def test_load_backlog_comment_lines_skipped(tmp_path):
    r"""Lines starting with # are skipped even if they match \d+. pattern."""
    p = tmp_path / "with_comments.md"
    p.write_text(
        "# This is a comment\n"
        "1. Valid task one\n"
        "Prose without number\n"
        "# Another comment\n"
        "2. Valid task two\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Valid task one", "Valid task two"]


def test_load_backlog_hash_number_treated_as_comment(tmp_path):
    """#1. Not a task — starts with # so treated as comment."""
    p = tmp_path / "hash_number.md"
    p.write_text(
        "#1. Not a task\n"
        "1. Real task\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Real task"]


# ---------------------------------------------------------------------------
# Scenario 4 — Number Present But Missing Dot-Space Separator
# ---------------------------------------------------------------------------

def test_load_backlog_bad_separator_skipped(tmp_path):
    """Lines with 1), 2-, '3 ' separators are skipped; only '4. ' matches."""
    p = tmp_path / "bad_separator.md"
    p.write_text(
        "1) No dot separator\n"
        "2- Dash separator\n"
        "3 No separator at all\n"
        "4. Valid item\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Valid item"]


def test_load_backlog_double_digit_number_parsed(tmp_path):
    """Double-digit number prefix is valid and parsed correctly."""
    p = tmp_path / "double_digit.md"
    p.write_text(
        "10. Double-digit number\n"
        "99. Another large number\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == ["Double-digit number", "Another large number"]


# ---------------------------------------------------------------------------
# Scenario 5 — Order Preservation With Gaps in Numbering
# ---------------------------------------------------------------------------

def test_load_backlog_order_preserved_with_gaps(tmp_path):
    """Items returned in physical file order, not numeric label order."""
    p = tmp_path / "gaps.md"
    p.write_text(
        "prose header\n"
        "3. Third (in file position 2)\n"
        "more prose\n"
        "1. First (in file position 4)\n"
        "99. Ninety-ninth (in file position 6)\n"
    )
    pm.BACKLOG_FILE = str(p)
    items = pm.load_backlog()
    assert items == [
        "Third (in file position 2)",
        "First (in file position 4)",
        "Ninety-ninth (in file position 6)",
    ]
