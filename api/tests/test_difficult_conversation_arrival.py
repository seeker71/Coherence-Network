"""Difficult-conversation arrival — the SessionStart carrier for the kernel's counsel card.

The carrier (scripts/difficult_conversation_arrival.py) prints the counsel card a session
holds when someone brings a conversation they dread. These tests pin the door's constraint —
the whole hook output fits the ~2 KB session-start preview — and the carrier's order: the
kernel door is preferred when a built fkwu and the recipe stand beside it, the mirror prints
otherwise, and nothing in it can raise into the hook.
"""
from __future__ import annotations

import os
import stat
import sys

import pytest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import difficult_conversation_arrival as dca  # noqa: E402

KERNEL_CARD_WINDOW = 1800  # the band's bound in cognition/difficult-conversation-counsel.fk


def test_mirror_card_fits_the_kernel_window() -> None:
    assert len(dca.MIRROR_CARD.encode("utf-8")) <= KERNEL_CARD_WINDOW


def test_whole_output_fits_the_preview_window(tmp_path: Path) -> None:
    text = dca.arrival_text(kernel_root=tmp_path)  # no kernel here -> the mirror
    assert len(text.encode("utf-8")) <= dca.PREVIEW_WINDOW
    assert text.startswith("⟐ DIFFICULT-CONVERSATION COUNSEL")
    assert "the other stays theirs" in text
    assert "tender-ground" in text
    assert text.endswith("\n")


def test_mirror_names_a_cell_for_every_move() -> None:
    rows = [ln for ln in dca.MIRROR_CARD.splitlines() if ln.startswith("  ")]
    assert len(rows) == 11  # six held in the kernel body, five named from the origin field
    for row in rows:
        assert " — " in row and row.endswith("]") and " [" in row


def _fake_kernel(root: Path, script: str) -> None:
    (root / "observe").mkdir(parents=True)
    (root / "observe" / "difficult-conversation-arrival-run.fk").write_text("(do 0)\n")
    fkwu = root / "fkwu"
    fkwu.write_text(script)
    fkwu.chmod(fkwu.stat().st_mode | stat.S_IXUSR)


def test_kernel_door_is_preferred_and_its_value_line_stripped(tmp_path: Path) -> None:
    _fake_kernel(tmp_path, "#!/bin/sh\nprintf '⟐ CARD FROM THE DOOR\\nrow\\n0\\n'\n")
    text = dca.arrival_text(kernel_root=tmp_path)
    assert text.startswith("⟐ CARD FROM THE DOOR\nrow\n")
    assert "\n0\n" not in text
    assert text.endswith(dca.TENDER_GROUND_LINE + "\n")


def test_failed_door_falls_back_to_the_mirror(tmp_path: Path) -> None:
    _fake_kernel(tmp_path, "#!/bin/sh\nexit 1\n")
    assert dca.kernel_card(tmp_path) is None
    assert dca.arrival_text(kernel_root=tmp_path).startswith(dca.MIRROR_CARD)


def test_door_without_recipe_is_not_run(tmp_path: Path) -> None:
    fkwu = tmp_path / "fkwu"
    fkwu.write_text("#!/bin/sh\necho should-not-run\n")
    fkwu.chmod(fkwu.stat().st_mode | stat.S_IXUSR)
    assert dca.kernel_card(tmp_path) is None


def test_main_never_raises(monkeypatch, capsys) -> None:
    monkeypatch.setattr(dca, "arrival_text", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert dca.main() == 0
    assert capsys.readouterr().out == ""


def test_gate_line_is_this_repos_own_and_not_in_the_mirror() -> None:
    assert "partner_presence.md" in dca.TENDER_GROUND_LINE
    assert "partner_presence" not in dca.MIRROR_CARD
    assert os.linesep is not None  # the hook prints text; no platform-specific bytes


def test_mirror_matches_the_pinned_door_wherever_it_can_run() -> None:
    """Where form/ is initialized and fkwu is built, the door's card and the mirror are one text."""
    root = dca.KERNEL_ROOT
    if not (root / dca.DOOR).is_file() or not os.access(root / "fkwu", os.X_OK):
        pytest.skip("the pinned kernel door cannot run here (form/ uninitialized or fkwu not built)")
    card = dca.kernel_card(root)
    assert card is not None
    assert card == dca.MIRROR_CARD
