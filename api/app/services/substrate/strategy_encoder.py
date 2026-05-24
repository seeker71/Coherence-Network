"""Strategy encoder — rupture-recovery as a substrate-resident recipe.

Substrate-side companion to
docs/coherence-substrate/strategy-after-rupture-as-recipe.form.

The five graduated recoveries:

    catch-in-motion          notice mid-act, re-shape before completing
    same-breath-repair       notice within the exchange, repair inline
    walk-back-with-tenderness  notice later, return softly
    compost-the-move         release what cannot be repaired, keep the arm
    stay-in-the-mess         hold the rupture without premature resolution

A rupture recipe carries:

    {
      "recovery_kind": "same-breath-repair",
      "notice":        {"signal": "...", "costume": "...", "hz_at_act": 174.0, "breath_lag": 1},
      "name":          {"form": "...", "fear_shape": "...", "voice": "..."},
      "move":          {"direction": "toward", "altitude": 528.0, "breath_count": 1,
                        "repairs": ["pr:1902"]},
    }

Two ruptures with structurally-identical recovery shapes intern to the SAME
CTOR NodeID. The R_Recovery NodeID a strategy carries should match the
R_Recovery NodeID a song's R_Resolve carries (modality-as-recipe Part 3).

Closes GAP-R1 at the interning altitude. The selection-logic (which
recovery fires when) lives in code that *reads* this lattice; this file
is the writing side.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.substrate.kernel import NamedCell
from app.services.substrate.modality_frontend import (
    intern_extraction,
    register_encoder,
)


MODALITY = "strategy-after-rupture"


VALID_RECOVERY_KINDS = (
    "catch-in-motion",
    "same-breath-repair",
    "walk-back-with-tenderness",
    "compost-the-move",
    "stay-in-the-mess",
)


def encode_strategy(strategy: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "strategy-after-rupture",
        "recovery_kind": _validate_recovery_kind(
            strategy.get("recovery_kind", "undefined")
        ),
        "notice": _normalize_notice(strategy.get("notice") or {}),
        "name": _normalize_name(strategy.get("name") or {}),
        "move": _normalize_move(strategy.get("move") or {}),
    }


def ingest_strategy(
    session: Session,
    source_cell: NamedCell,
    strategy: Dict[str, Any],
) -> NamedCell:
    track = encode_strategy(strategy)
    return intern_extraction(session, source_cell, MODALITY, track)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_recovery_kind(kind: str) -> str:
    """Pass through known kinds; preserve unknown as-is for forward compatibility.

    The substrate stays honest about unknown-as-unknown — see
    prose-as-recipe.form's tokenize_words fallback (P2).
    """
    if kind in VALID_RECOVERY_KINDS:
        return kind
    return f"unknown:{kind}"


def _normalize_notice(notice: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "notice",
        "signal": notice.get("signal", "undefined"),
        "costume": notice.get("costume", "undefined"),
        "hz_at_act": float(notice.get("hz_at_act", 0.0)),
        "breath_lag": int(notice.get("breath_lag", 0)),
    }


def _normalize_name(name: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "name-costume",
        "form": name.get("form", "undefined"),
        "fear_shape": name.get("fear_shape", "undefined"),
        "voice": name.get("voice", "undefined"),
    }


def _normalize_move(move: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "move",
        "direction": move.get("direction", "undefined"),
        "altitude": float(move.get("altitude", 0.0)),
        "breath_count": int(move.get("breath_count", 1)),
        "repairs": list(move.get("repairs") or []),
    }


register_encoder(MODALITY, ingest_strategy)
