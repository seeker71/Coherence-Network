"""Contract tests for spec 167 — Social Platform Bots (platform selection, ROI, /cc-link).

Verifies documented acceptance criteria: spec text, Discord-first decision, ROI signals R1–R5,
/cc-link command wiring, contributors persistence shape, and Phase 2 X stub.
Tests read repo files only; do not modify production code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_api_dir = Path(__file__).resolve().parent.parent
_repo_root = _api_dir.parent
_spec_path = _repo_root / "specs" / "167-social-platform-bots.md"
_cc_link_js = _repo_root / "discord-bot" / "src" / "commands" / "cc-link.js"
_register_js = _repo_root / "discord-bot" / "src" / "register-commands.js"
_db_js = _repo_root / "discord-bot" / "src" / "lib" / "db.js"


def _spec_text() -> str:
    if not _spec_path.exists():
        pytest.skip("spec 167 not in repo")
    return _spec_path.read_text(encoding="utf-8")


def test_spec_167_file_exists():
    """Spec file must exist (spec 167 file paths table)."""
    assert _spec_path.is_file(), f"Expected {_spec_path}"


def test_spec_records_discord_first_decision():
    """Acceptance: platform decision names Discord as first platform."""
    text = _spec_text()
    assert "Discord First" in text or "Winner: Discord" in text
    assert "Discord" in text and "X" in text


def test_spec_defines_roi_signals_r1_through_r5():
    """Acceptance: ROI framework lists R1–R5 with measurable hooks."""
    text = _spec_text()
    for n in range(1, 6):
        assert f"R{n}" in text, f"Missing ROI signal R{n}"
    assert "interface=discord" in text or "interface" in text
    assert "question_votes" in text
    assert "RestartCount" in text or "restart" in text.lower()


def test_spec_documents_cc_link_command_and_flow():
    """Acceptance: /cc-link flow and contributor mapping are documented."""
    text = _spec_text()
    assert "/cc-link" in text
    assert "contributor_id" in text
    assert "contributors.db" in text or "contributors" in text
    assert "cc-idea" in text and "cc-stake" in text


def test_spec_lists_cc_link_implementation_path():
    """Acceptance: file path table points to discord-bot cc-link command."""
    text = _spec_text()
    assert "discord-bot/src/commands/cc-link.js" in text


def test_spec_phase_2_x_twitter_stub():
    """Acceptance: Phase 2 X/Twitter announcement bot is stubbed with triggers."""
    text = _spec_text()
    assert "Phase 2" in text
    assert "X" in text or "Twitter" in text
    assert "tweepy" in text or "announcement" in text.lower()


def test_spec_verification_table_present():
    """Acceptance: Verification section lists proof rows."""
    text = _spec_text()
    assert "## Verification" in text
    assert "Discord" in text or "cc-link" in text.lower()


def test_cc_link_command_file_exists():
    """Proof: /cc-link implementation file exists (spec file paths)."""
    assert _cc_link_js.is_file(), f"Expected {_cc_link_js}"


def test_cc_link_registers_slash_command():
    """Acceptance: command registers as cc-link with contributor_id option."""
    src = _cc_link_js.read_text(encoding="utf-8")
    assert ".setName('cc-link')" in src or '.setName("cc-link")' in src
    assert "contributor_id" in src
    assert "SlashCommandBuilder" in src


def test_cc_link_persists_and_replies_ephemeral():
    """Acceptance: stores mapping via contributors helper and replies ephemeral."""
    src = _cc_link_js.read_text(encoding="utf-8")
    assert "contributors.link" in src
    assert "ephemeral: true" in src
    assert "Linked" in src


def test_register_commands_includes_cc_link():
    """Acceptance: register-commands must register cc-link (spec)."""
    src = _register_js.read_text(encoding="utf-8")
    assert "cc-link.js" in src or "ccLink" in src
    assert "ccLink" in src
    assert "commands" in src


def test_db_stores_discord_contributor_mapping():
    """Acceptance: SQLite mapping discord_user_id ↔ contributor_id (spec flow)."""
    src = _db_js.read_text(encoding="utf-8")
    assert "contributors.db" in src
    assert "discord_contributors" in src
    assert "getContributorId" in src
    assert "link(" in src
