"""Song encoder — songs as recipes of note / drum-strike / vowel-tone cells.

The substrate-side companion to docs/coherence-substrate/song-as-recipe.form.
Builds a track-recipe from a structured song description:

    {
      "phrases": [
        {
          "kind": "phrase",
          "arc": "ascending",
          "intention": "invocation",
          "events": [
            {"kind": "note",  "pitch": 432.0, "duration": 1.0, "dynamic": "mp"},
            {"kind": "drum",  "timbre": "frame-drum", "intensity": 0.7},
            {"kind": "vowel", "formant": "ah", "hz": 432.0, "duration": 2.0},
          ],
        },
        ...
      ],
      "arc": "descent-and-return",
    }

The track is interned through modality_frontend.intern_extraction(),
producing an extraction cell attached to the source (an ARTIFACT cell
for a real .mp3, or any source NamedCell for a hand-described song).

Two songs with structurally-identical phrase shapes intern to the SAME
extraction CTOR NodeID — the cross-modal recognition the .form file
promises. A R_Phrase shape that matches a teaching's R_Arc fires the
substrate's `?equivalent` query across modalities.

Closes GAP-S1/S2/S3 (at the substrate-interning altitude — real audio
decode lives in audio-grammar.form's pipeline; this file is the bridge
from already-segmented data into the lattice).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.substrate.kernel import NamedCell
from app.services.substrate.modality_frontend import (
    intern_extraction,
    register_encoder,
)


MODALITY = "song"


def encode_song(song: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a song description into the canonical track shape.

    The shape is a dict that intern_extraction will pass through
    frontmatter_to_structured_ctor — every field becomes a LET pair,
    nested lists become R_Block.SEQUENCE, scalars become typed trivials.
    Identical inputs produce identical CTOR NodeIDs.
    """
    return {
        "kind": "song",
        "arc": song.get("arc", "undefined"),
        "phrases": [
            _normalize_phrase(p) for p in (song.get("phrases") or [])
        ],
    }


def ingest_song(
    session: Session,
    source_cell: NamedCell,
    song: Dict[str, Any],
) -> NamedCell:
    """Attach a song extraction to a source cell.

    Returns the extraction NamedCell. The extraction's CTOR encodes the
    full song shape; structural equivalence is queryable via the
    substrate's equivalent-cells lookup.
    """
    track = encode_song(song)
    return intern_extraction(session, source_cell, MODALITY, track)


# ---------------------------------------------------------------------------
# Internals — leaf-shape normalizers
# ---------------------------------------------------------------------------


def _normalize_phrase(phrase: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "phrase",
        "arc": phrase.get("arc", "undefined"),
        "intention": phrase.get("intention", "undefined"),
        "events": [
            _normalize_event(e) for e in (phrase.get("events") or [])
        ],
    }


def _normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    kind = event.get("kind", "undefined")
    if kind == "note":
        return {
            "kind": "note",
            "pitch": float(event.get("pitch", 0.0)),
            "duration": float(event.get("duration", 0.0)),
            "dynamic": event.get("dynamic", "mp"),
            "breath": event.get("breath", "none"),
            "timbre_field": event.get("timbre_field", "undefined"),
        }
    if kind == "drum":
        return {
            "kind": "drum",
            "timbre": event.get("timbre", "undefined"),
            "ictus": float(event.get("ictus", 0.0)),
            "intensity": float(event.get("intensity", 0.0)),
            "rebound": float(event.get("rebound", 0.0)),
        }
    if kind == "vowel":
        return {
            "kind": "vowel",
            "formant": event.get("formant", "undefined"),
            "breath": event.get("breath", "sustained"),
            "duration": float(event.get("duration", 0.0)),
            "hz": float(event.get("hz", 0.0)),
        }
    # Unknown event kind — preserve as-is so the encoder is forward-compatible
    return {"kind": kind, "raw": event}


# Register on module import so lookup_encoder("song") resolves.
register_encoder(MODALITY, ingest_song)
