"""Tests for backlog validation script.

Validates that backlog files conform to expected format per spec 006.
"""

import tempfile
from pathlib import Path

import pytest

# Import the validation function
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_backlog import validate


def test_valid_backlog_with_sequential_numbers():
    """Valid backlog with sequential numbering should pass."""
    content = """# Test Backlog

## Phase 1: Testing

1. First item
2. Second item
3. Third item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    assert valid is True
    assert len(errors) == 0
    assert len(warnings) == 0


def test_valid_backlog_with_non_sequential_numbers_shows_warning():
    """Backlog with non-sequential numbering should warn but not error."""
    content = """# Test Backlog

1. First item
3. Third item (skipped 2)
5. Fifth item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    assert valid is True  # Still valid, just warnings
    assert len(errors) == 0
    assert len(warnings) == 2  # Two non-sequential jumps


def test_invalid_backlog_with_duplicate_numbers():
    """Backlog with duplicate item numbers should error."""
    content = """# Test Backlog

1. First item
2. Second item
2. Another second item (duplicate!)
3. Third item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    assert valid is False
    assert len(errors) == 1
    assert "Duplicate" in errors[0]


def test_invalid_backlog_with_malformed_numbering():
    """Backlog with invalid item format should error."""
    content = """# Test Backlog

1. First item
2.Second item (missing space after dot)
3. Third item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    assert valid is False
    assert len(errors) == 1
    assert "Invalid format" in errors[0]


def test_backlog_ignores_comments_and_headers():
    """Comments and markdown headers should be ignored."""
    content = """# Test Backlog

## Phase 1: Items

1. First item
# This is a comment
## Subheading
2. Second item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    assert valid is True
    assert len(errors) == 0


def test_backlog_ignores_metadata_lines():
    """Metadata lines like 'Use:', 'Work:', etc. should be ignored."""
    content = """# Test Backlog

Use: `python scripts/run.py --backlog file.md`
Progress: Phase 1 done
Work items ordered for overnight runs.

## Phase 1

1. First item
2. Second item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    assert valid is True
    assert len(errors) == 0


def test_empty_backlog_shows_warning():
    """Empty backlog (no numbered items) should show warning."""
    content = """# Test Backlog

## Phase 1: Empty

No items here.
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    assert valid is True  # Not an error, just a warning
    assert len(errors) == 0
    assert len(warnings) == 1
    assert "No numbered items" in warnings[0]


def test_file_not_found():
    """Non-existent file should return error."""
    valid, errors, warnings = validate("/nonexistent/path/to/backlog.md")

    assert valid is False
    assert len(errors) == 1
    assert "File not found" in errors[0]


def test_backlog_with_mixed_valid_and_invalid_items():
    """Backlog with both valid and invalid items should report all errors."""
    content = """# Test Backlog

1. First item
2.Second item (malformed)
3. Third item
4.Fourth item (also malformed)
5. Fifth item
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    assert valid is False
    assert len(errors) == 2  # Two malformed items


def test_spec_006_overnight_backlog_format():
    """Real spec 006 backlog file should validate successfully.

    This test verifies the actual overnight backlog format matches requirements.
    """
    # Find the actual backlog file
    import os
    script_dir = Path(__file__).parent.parent / "scripts"
    project_root = script_dir.parent.parent
    backlog_file = project_root / "specs" / "006-overnight-backlog.md"

    if backlog_file.exists():
        valid, errors, warnings = validate(str(backlog_file))

        # The real backlog should be valid
        assert valid is True, f"Errors: {errors}"
        # Warnings are OK (might have non-sequential numbering by design)


def test_backlog_validation_matches_project_manager_parsing():
    """Validation should match the parsing logic in project_manager.py.

    Items that project_manager.py would parse should pass validation.
    Items it would skip should not cause errors.
    """
    content = """# Test Backlog for Project Manager

## Phase 1: Test Items

1. First task - should be parsed
Some text without a number - should be skipped silently
2. Second task - should be parsed
# Comment line - should be ignored
3. Third task - should be parsed
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        f.flush()

        valid, errors, warnings = validate(f.name)

    # Should be valid - non-numbered lines are allowed (just ignored)
    assert valid is True
    assert len(errors) == 0
