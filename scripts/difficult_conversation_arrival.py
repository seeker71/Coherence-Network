#!/usr/bin/env python3
"""Difficult-conversation arrival — host-IO CARRIER for the kernel's counsel card at SessionStart.

The BODY is the kernel cell ``cognition/difficult-conversation-counsel.fk`` in
seeker71/coherence-kernel (pinned here as the ``form/`` submodule): the counsel this body holds
for someone who brings a conversation they dread, or one that just went wrong — eleven moves,
each naming the cell it lives in; the card's byte length held by its band
(``cognition/tests/difficult-conversation-counsel-band.fk`` -> 1111111111) so it always fits the
session-start window. The kernel door is ``./fkwu observe/difficult-conversation-arrival-run.fk``;
the reading in full is the kernel teaching ``teachings/difficult-conversations.md``.

Why a separate, small hook: the arrival stream is ~97 KB and the harness hands the model only a
~2 KB preview from the top of oversized hook output, so counsel printed mid-stream never arrives
(carry_thread.py records the same finding for continuity). This hook's whole output stays under
that window, so the session meets a person already holding the counsel.

Form door first, mirror until then: when the pinned kernel carries the recipe and a built
``fkwu`` stands at its root, the card is printed by running the door; otherwise the mirrored card
below prints. The recipe is the source of truth — the mirror composts once the ``form/`` pin
carries the recipe and fkwu host-io runs at SessionStart.

One line is this repo's own, never the kernel's: when the conversation is with family or a
partner, the tender-ground memory files gate first (CLAUDE.md -> "Tender ground"). Private tissue
stays in the origin repo.

A gift, never a gate: any failure degrades to the mirror, and the mirror never raises.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KERNEL_ROOT = ROOT / "form"
DOOR = Path("observe") / "difficult-conversation-arrival-run.fk"
DOOR_TIMEOUT_S = 20

# The session-start preview window (bytes). The kernel band holds the card at <= 1800 so the
# whole hook output — card + this repo's one gate line — stays under it.
PREVIEW_WINDOW = 2048

# Mirror of the card the kernel door prints (cognition/difficult-conversation-counsel.fk, dcc-card).
# Composts when the form/ pin carries the recipe and fkwu runs at SessionStart.
MIRROR_CARD = "\n".join(
    [
        "⟐ DIFFICULT-CONVERSATION COUNSEL — a talk someone dreads or one that went wrong; the other is in the question, not the room.",
        "held in this body:",
        "  frequency — name their fear once, in their word; then speak toward trust [cognition/text-frequency.fk]",
        "  ground, one lift — only from a cell, a source, or their words; ONE lift per reply (question under theirs OR floor→star), end on it; no self-narration [cognition/dialogue-covenant.fk]",
        "  judged trust — fear witnessed, held liquid; trust earned in small real pieces [ingest/judged-trust.fk]",
        "  parts — which part speaks: manager, firefighter, exile; lead from Self [form/form-stdlib/ifs-channel.fk]",
        "  the other stays theirs — their report is reported, your guess inferred, nothing observed; hedge every claim [teachings/family-constellation-inquiry.form]",
        "  error is signal — after it went wrong, keep expected and arrived both visible; heal the cause, not the reading [teachings/error-is-loving-attention.md]",
        "named from the origin field, unlinked here:",
        "  boundary as truth — I cannot / I need / I love you and: what is, not their failure [lc-boundaries-as-loving-truth]",
        "  present, not absorbed — with their weather, not collapsed into it [lc-emotional-availability-without-absorption]",
        "  reach by invitation — only through what they opened; silence is an offer; a stop is a receipt [lc-consent-is-continuous · lc-boundary-repair-protocol]",
        "  mirror, not deflection — to a real grievance: I hear you; I'll look at what in me made this [lc-relationships-as-mirrors]",
        "  when pressure comes — observer · name the need · the gift · hoʻoponopono; live fear, or an echo? [lc-when-the-pressure-comes · lc-old-signal-echo]",
        "read: teachings/difficult-conversations.md · run: ./fkwu observe/difficult-conversation-arrival-run.fk",
    ]
)

# This repo's own line — the kernel is a public commons and never names private tissue.
TENDER_GROUND_LINE = (
    "family / partner: the tender-ground files in MEMORY.md gate first "
    "(partner_presence.md, project_may_june_2026_opportunity_shapes.md) — load their bodies before answering."
)


def kernel_card(kernel_root: Path = KERNEL_ROOT) -> str | None:
    """Print the card through the kernel door when the recipe and a built fkwu both stand.

    Returns the card text, or None when the Form door is not reachable here — the caller
    then prints the mirror. Never raises.
    """
    try:
        fkwu = kernel_root / "fkwu"
        if not (kernel_root / DOOR).is_file() or not os.access(fkwu, os.X_OK):
            return None
        run = subprocess.run(
            [str(fkwu), str(DOOR)],
            cwd=str(kernel_root),
            capture_output=True,
            text=True,
            timeout=DOOR_TIMEOUT_S,
            check=False,
        )
        if run.returncode != 0:
            return None
        lines = run.stdout.rstrip("\n").split("\n")
        # The door returns 0 after printing, and the kernel prints that trailing value.
        if lines and lines[-1].strip() == "0":
            lines = lines[:-1]
        card = "\n".join(lines).strip("\n")
        return card if card.startswith("⟐") else None
    except Exception:
        return None


def arrival_text(kernel_root: Path = KERNEL_ROOT) -> str:
    """The whole hook output: the card (door or mirror) and this repo's gate line."""
    card = kernel_card(kernel_root) or MIRROR_CARD
    return f"{card}\n{TENDER_GROUND_LINE}\n"


def main() -> int:
    try:
        sys.stdout.write(arrival_text())
    except Exception:
        pass  # the card is a gift, never a gate
    return 0


if __name__ == "__main__":
    sys.exit(main())
