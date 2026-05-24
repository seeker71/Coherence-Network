"""Teaching encoder — story-arc + transmission-frequency as R_Transmission.

Substrate-side companion to docs/coherence-substrate/teaching-as-recipe.form.

A teaching is composed of:

    arc:           a sequence of scenes joined by turns (noticing → naming → choice)
    carrier:       the transmission-frequency (hz, semantic_field, polarity, locus)
    examples:      embodied-example cells inside the arc
    pointings:     specific from-costume → toward-ground indications
    dispatch:      per-assemblage-point arms (the same teaching arrives differently
                   to @fear vs @sovereignty vs @grief)

Two teachings whose arc + dispatch shape match structurally intern to the
SAME track NodeID — a teaching matches a song's R_Arc, a strategy's
R_Recovery, a healing modality's R_Re-pattern. This is what makes
cross-modal Blueprint equivalence load-bearing for teaching-discovery.

Closes GAP-T1/T2/T3 at the interning altitude.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.substrate.kernel import NamedCell
from app.services.substrate.modality_frontend import (
    intern_extraction,
    register_encoder,
)


MODALITY = "teaching"


def encode_teaching(teaching: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a teaching into the canonical track shape."""
    return {
        "kind": "teaching",
        "arc": _normalize_arc(teaching.get("arc") or {}),
        "carrier": _normalize_carrier(teaching.get("carrier") or {}),
        "examples": [
            _normalize_example(e) for e in (teaching.get("examples") or [])
        ],
        "pointings": [
            _normalize_pointing(p) for p in (teaching.get("pointings") or [])
        ],
        "dispatch": [
            _normalize_dispatch_arm(d)
            for d in (teaching.get("dispatch") or [])
        ],
    }


def ingest_teaching(
    session: Session,
    source_cell: NamedCell,
    teaching: Dict[str, Any],
) -> NamedCell:
    """Attach a teaching extraction to a source concept cell."""
    track = encode_teaching(teaching)
    return intern_extraction(session, source_cell, MODALITY, track)


# ---------------------------------------------------------------------------
# Normalizers — each composes nested LET pairs in canonical key order
# ---------------------------------------------------------------------------


def _normalize_arc(arc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "arc",
        "arc_kind": arc.get("arc_kind", "undefined"),
        "opening_hz": float(arc.get("opening_hz", 0.0)),
        "landing_hz": float(arc.get("landing_hz", 0.0)),
        "scenes": [_normalize_scene(s) for s in (arc.get("scenes") or [])],
        "turns": [_normalize_turn(t) for t in (arc.get("turns") or [])],
    }


def _normalize_scene(scene: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "scene",
        "setting": scene.get("setting", "undefined"),
        "what_arrives": scene.get("what_arrives", "undefined"),
        "hz": float(scene.get("hz", 0.0)),
        "presences": list(scene.get("presences") or []),
    }


def _normalize_turn(turn: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "turn",
        "noticing": turn.get("noticing", "undefined"),
        "naming": turn.get("naming", "undefined"),
        "choice": turn.get("choice", "undefined"),
        "altitude_shift": float(turn.get("altitude_shift", 0.0)),
    }


def _normalize_carrier(carrier: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "carrier",
        "hz": float(carrier.get("hz", 0.0)),
        "semantic_field": carrier.get("semantic_field", "undefined"),
        "polarity": carrier.get("polarity", "undefined"),
        "body_locus": carrier.get("body_locus", "undefined"),
    }


def _normalize_example(example: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "example",
        "moment": example.get("moment", "undefined"),
        "pointing_to": example.get("pointing_to", "undefined"),
    }


def _normalize_pointing(pointing: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "pointing",
        "from_costume": pointing.get("from_costume", "undefined"),
        "toward_ground": pointing.get("toward_ground", "undefined"),
        "breath_count": int(pointing.get("breath_count", 1)),
    }


def _normalize_dispatch_arm(arm: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "dispatch_arm",
        "assemblage_point": arm.get("assemblage_point", "undefined"),
        "expression": arm.get("expression", "undefined"),
    }


register_encoder(MODALITY, ingest_teaching)
