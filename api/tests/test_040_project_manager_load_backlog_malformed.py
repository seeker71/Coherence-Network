"""Tests for spec 040: project_manager load_backlog handles malformed input gracefully.

Covers _parse_backlog_file and load_backlog with invalid, incomplete, and edge-case
backlog file content — ensuring only valid `\\d+. item` lines are returned and all
malformed input is silently skipped.
"""
import os
import sys

import pytest

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _api_dir)

from scripts import project_manager as pm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_backlog(tmp_path, content: str):
    p = tmp_path / "backlog.md"
    p.write_text(content, encoding="utf-8")
    pm.BACKLOG_FILE = str(p)
    return p


# ---------------------------------------------------------------------------
# Missing / unreadable file
# ---------------------------------------------------------------------------

class TestMissingFile:
    def test_nonexistent_file_returns_empty(self, tmp_path):
        """load_backlog returns [] when BACKLOG_FILE does not exist (no crash)."""
        pm.BACKLOG_FILE = str(tmp_path / "does_not_exist.md")
        result = pm.load_backlog()
        assert result == [], "Expected empty list for missing file"

    def test_empty_file_returns_empty(self, tmp_path):
        """load_backlog returns [] for a completely empty file."""
        _write_backlog(tmp_path, "")
        assert pm.load_backlog() == []

    def test_whitespace_only_file_returns_empty(self, tmp_path):
        """load_backlog returns [] when file is all whitespace/newlines."""
        _write_backlog(tmp_path, "   \n\n\t\n   \n")
        assert pm.load_backlog() == []


# ---------------------------------------------------------------------------
# Completely malformed lines (no valid numbered items at all)
# ---------------------------------------------------------------------------

class TestNoValidItems:
    def test_unnumbered_lines_only(self, tmp_path):
        """Only non-numbered lines → empty list."""
        _write_backlog(tmp_path, "Just prose\nAnother line\nNo numbers here\n")
        assert pm.load_backlog() == []

    def test_markdown_headers_only(self, tmp_path):
        """Markdown headers (# / ## / ###) are not numbered items → empty list."""
        _write_backlog(tmp_path, "# Heading\n## Sub-heading\n### Deep heading\n")
        assert pm.load_backlog() == []

    def test_bullet_list_items(self, tmp_path):
        """Bullet markers (- / * / +) without a leading digit are skipped."""
        _write_backlog(tmp_path, "- bullet one\n* bullet two\n+ bullet three\n")
        assert pm.load_backlog() == []

    def test_lines_starting_with_hash_digit(self, tmp_path):
        """Lines like '# 1. item' start with '#' which matches comment guard → skipped."""
        _write_backlog(tmp_path, "# 1. This looks numbered but starts with #\n")
        assert pm.load_backlog() == []

    def test_parenthesised_numbers(self, tmp_path):
        """Items like '1) item' do not match `^\\d+\\.` → skipped."""
        _write_backlog(tmp_path, "1) First\n2) Second\n3) Third\n")
        assert pm.load_backlog() == []

    def test_dotless_numbers(self, tmp_path):
        """Lines like '1 item' without a dot are skipped."""
        _write_backlog(tmp_path, "1 First item\n2 Second item\n")
        assert pm.load_backlog() == []

    def test_number_dot_no_text(self, tmp_path):
        """'3.' with nothing after the dot (stripped) produces no item."""
        _write_backlog(tmp_path, "1.\n2.   \n3.\t\n")
        assert pm.load_backlog() == []

    def test_leading_whitespace_before_number(self, tmp_path):
        """Lines with leading spaces before the digit are stripped and then parsed."""
        # The parser does line.strip() first, so indented numbered lines SHOULD match.
        _write_backlog(tmp_path, "  1. Indented item\n    2. Deeply indented\n")
        result = pm.load_backlog()
        # After strip(), "  1. ..." becomes "1. ..." which matches — so items are found.
        assert result == ["Indented item", "Deeply indented"]

    def test_negative_number_prefix(self, tmp_path):
        """-1. item is not a valid numbered item (negative numbers)."""
        _write_backlog(tmp_path, "-1. Negative item\n-2. Another\n")
        assert pm.load_backlog() == []

    def test_roman_numeral_prefix(self, tmp_path):
        """Roman numerals (i., ii., iv.) don't match \\d+. → skipped."""
        _write_backlog(tmp_path, "i. First\nii. Second\niv. Fourth\n")
        assert pm.load_backlog() == []

    def test_letter_prefix(self, tmp_path):
        """Letter-prefixed items (a., b.) are not valid numbered items."""
        _write_backlog(tmp_path, "a. Alpha\nb. Beta\nc. Gamma\n")
        assert pm.load_backlog() == []


# ---------------------------------------------------------------------------
# Mixed valid and malformed lines
# ---------------------------------------------------------------------------

class TestMixedContent:
    def test_valid_items_among_junk(self, tmp_path):
        """Only numbered items survive; prose, headers, blanks are dropped."""
        _write_backlog(tmp_path, (
            "# Backlog\n"
            "\n"
            "1. First valid item\n"
            "This is a description line\n"
            "2. Second valid item\n"
            "  - sub-bullet\n"
            "## Section heading\n"
            "3. Third valid item\n"
            "\n"
        ))
        result = pm.load_backlog()
        assert result == ["First valid item", "Second valid item", "Third valid item"]

    def test_numbered_header_comments_skipped(self, tmp_path):
        """Lines like '# 2. Heading' start with '#' → skipped even though they contain a digit."""
        _write_backlog(tmp_path, (
            "1. Real item\n"
            "# 2. Not an item\n"
            "3. Another real item\n"
        ))
        result = pm.load_backlog()
        assert result == ["Real item", "Another real item"]

    def test_non_sequential_numbers_preserved_in_order(self, tmp_path):
        """Items with non-sequential numbers are returned in file order."""
        _write_backlog(tmp_path, (
            "5. Fifth\n"
            "1. First\n"
            "99. Ninety-ninth\n"
            "2. Second\n"
        ))
        result = pm.load_backlog()
        assert result == ["Fifth", "First", "Ninety-ninth", "Second"]

    def test_duplicate_numbers_both_returned(self, tmp_path):
        """Duplicate numbering (two '1.' lines) → both items are included."""
        _write_backlog(tmp_path, (
            "1. Item A\n"
            "1. Item B\n"
            "2. Item C\n"
        ))
        result = pm.load_backlog()
        assert result == ["Item A", "Item B", "Item C"]

    def test_inline_code_and_markdown_in_item(self, tmp_path):
        """Markdown formatting inside the item text is preserved as-is."""
        _write_backlog(tmp_path, "1. Implement `foo()` endpoint — **high priority**\n")
        result = pm.load_backlog()
        assert len(result) == 1
        assert "`foo()`" in result[0]

    def test_trailing_whitespace_stripped_from_items(self, tmp_path):
        """Trailing spaces/tabs on item text are stripped."""
        _write_backlog(tmp_path, "1. Item with trailing spaces   \n2. Tab-trailing\t\n")
        result = pm.load_backlog()
        assert result[0] == "Item with trailing spaces"
        assert result[1] == "Tab-trailing"

    def test_very_long_item_text_included(self, tmp_path):
        """A very long (>500 char) item line is still returned (no length cap in parser)."""
        long_text = "x" * 600
        _write_backlog(tmp_path, f"1. {long_text}\n")
        result = pm.load_backlog()
        assert len(result) == 1
        assert result[0] == long_text

    def test_multiline_description_only_numbered_line_captured(self, tmp_path):
        """Continuation/description lines after a numbered item are ignored."""
        _write_backlog(tmp_path, (
            "1. Main item\n"
            "   This is a continuation paragraph for item 1.\n"
            "   It spans multiple lines.\n"
            "2. Next item\n"
        ))
        result = pm.load_backlog()
        assert result == ["Main item", "Next item"]


# ---------------------------------------------------------------------------
# Encoding / special characters
# ---------------------------------------------------------------------------

class TestEncodingEdgeCases:
    def test_unicode_text_in_items(self, tmp_path):
        """UTF-8 unicode in item text is handled correctly."""
        _write_backlog(tmp_path, "1. Ünïcödé item — résumé\n2. 中文项目\n3. العربية\n")
        result = pm.load_backlog()
        assert len(result) == 3
        assert "Ünïcödé" in result[0]
        assert "中文" in result[1]

    def test_emoji_in_item_text(self, tmp_path):
        """Emoji characters in item text do not break parsing."""
        _write_backlog(tmp_path, "1. 🚀 Launch feature\n2. Fix 🐛 bug\n")
        result = pm.load_backlog()
        assert len(result) == 2
        assert "🚀" in result[0]
        assert "🐛" in result[1]

    def test_crlf_line_endings(self, tmp_path):
        """Windows CRLF line endings are handled gracefully (strip removes \\r)."""
        p = tmp_path / "backlog.md"
        p.write_bytes(b"1. First item\r\n2. Second item\r\nJunk line\r\n3. Third item\r\n")
        pm.BACKLOG_FILE = str(p)
        result = pm.load_backlog()
        assert result == ["First item", "Second item", "Third item"]

    def test_tab_after_dot_separator(self, tmp_path):
        """'1.\\tItem' (tab separator instead of space) — \\s+ in pattern catches tab."""
        _write_backlog(tmp_path, "1.\tTab-separated item\n2.\t Another one\n")
        result = pm.load_backlog()
        assert len(result) == 2
        assert result[0] == "Tab-separated item"
        assert result[1] == "Another one"

    def test_multiple_spaces_after_dot(self, tmp_path):
        """'1.   item' (multiple spaces) — \\s+ collapses all spaces correctly."""
        _write_backlog(tmp_path, "1.   Triple spaced\n2.  Double spaced\n")
        result = pm.load_backlog()
        assert result == ["Triple spaced", "Double spaced"]


# ---------------------------------------------------------------------------
# Large / stress cases
# ---------------------------------------------------------------------------

class TestStressCases:
    def test_large_file_with_many_items(self, tmp_path):
        """Parser handles 1000 numbered items without error."""
        lines = "\n".join(f"{i}. Item number {i}" for i in range(1, 1001))
        _write_backlog(tmp_path, lines + "\n")
        result = pm.load_backlog()
        assert len(result) == 1000
        assert result[0] == "Item number 1"
        assert result[999] == "Item number 1000"

    def test_large_file_with_mostly_junk(self, tmp_path):
        """Parser extracts only valid items from a large noisy file."""
        lines = []
        for i in range(1, 201):
            lines.append(f"{i}. Valid item {i}")
            lines.append(f"  description line for item {i}")
            lines.append(f"  - sub-bullet {i}")
        _write_backlog(tmp_path, "\n".join(lines) + "\n")
        result = pm.load_backlog()
        assert len(result) == 200
        assert all(r.startswith("Valid item") for r in result)

    def test_file_with_only_headers_and_bullets(self, tmp_path):
        """A file that looks like a structured doc but has zero numbered items → empty list."""
        content = (
            "# Sprint Goals\n"
            "## Week 1\n"
            "- Design API\n"
            "- Set up CI\n"
            "## Week 2\n"
            "- Implement endpoints\n"
            "- Write tests\n"
            "## Week 3\n"
            "- Deploy\n"
            "- Monitor\n"
        )
        _write_backlog(tmp_path, content)
        assert pm.load_backlog() == []


# ---------------------------------------------------------------------------
# parse_backlog_file directly (internal function)
# ---------------------------------------------------------------------------

class TestParseBacklogFileDirect:
    def test_empty_path_returns_empty(self):
        """_parse_backlog_file('') returns [] without raising."""
        result = pm._parse_backlog_file("")
        assert result == []

    def test_nonexistent_path_returns_empty(self, tmp_path):
        """_parse_backlog_file with missing path returns []."""
        result = pm._parse_backlog_file(str(tmp_path / "nope.md"))
        assert result == []

    def test_valid_items_parsed(self, tmp_path):
        """_parse_backlog_file returns stripped item text for each valid line."""
        p = tmp_path / "b.md"
        p.write_text("1. Alpha\n2. Beta\n3. Gamma\n")
        result = pm._parse_backlog_file(str(p))
        assert result == ["Alpha", "Beta", "Gamma"]

    def test_comment_lines_with_numbers_skipped(self, tmp_path):
        """Lines starting with '#' are skipped even if they contain '\\d+.'."""
        p = tmp_path / "b.md"
        p.write_text("# 1. Heading one\n1. Real item\n# 2. Another heading\n")
        result = pm._parse_backlog_file(str(p))
        assert result == ["Real item"]

    def test_number_dot_only_no_text(self, tmp_path):
        """'1.' with nothing after (strip → empty group) produces no item per regex."""
        p = tmp_path / "b.md"
        p.write_text("1.\n2.\n3.\n")
        result = pm._parse_backlog_file(str(p))
        # regex requires (.+) — one or more chars — so bare "1." produces no match
        assert result == []

    def test_multi_digit_numbers(self, tmp_path):
        """Items with multi-digit numbers (10., 99., 100.) are parsed correctly."""
        p = tmp_path / "b.md"
        p.write_text("10. Tenth item\n99. Ninety-ninth\n100. Hundredth\n")
        result = pm._parse_backlog_file(str(p))
        assert result == ["Tenth item", "Ninety-ninth", "Hundredth"]

    def test_item_text_with_dots(self, tmp_path):
        """Dots in the item text (e.g. 'v1.2.3') are preserved."""
        p = tmp_path / "b.md"
        p.write_text("1. Upgrade to v1.2.3\n2. See README.md for details\n")
        result = pm._parse_backlog_file(str(p))
        assert result == ["Upgrade to v1.2.3", "See README.md for details"]

    def test_item_text_with_url(self, tmp_path):
        """URLs in item text are preserved intact."""
        p = tmp_path / "b.md"
        p.write_text("1. See https://example.com/docs for spec\n")
        result = pm._parse_backlog_file(str(p))
        assert len(result) == 1
        assert "https://example.com/docs" in result[0]

    def test_zero_prefixed_numbers(self, tmp_path):
        """'01. item' and '007. item' are valid \\d+. matches."""
        p = tmp_path / "b.md"
        p.write_text("01. Zero-padded one\n007. Bond item\n")
        result = pm._parse_backlog_file(str(p))
        assert result == ["Zero-padded one", "Bond item"]
