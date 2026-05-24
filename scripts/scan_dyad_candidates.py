"""Refined dyad-pair candidate scan over Living Collective concept cells.

Third scan in the autoresearch loop. Previous rounds:
- PR #1987: Tier-2 geometry-tuple scan (7-axis tuple match). 2/5 = 40%.
- PR #1992: small-Blueprint-cluster scan (Blueprint family only). 0/2 = 0%.
  Cumulative across rounds 1+2: 2/7 = 28.6%.

The diagnosis from PR #1992: small-Blueprint-cluster scanning rediscovers
Part-4-already-named kin (same family != complementary). Wrong resolution.

This refinement combines three signals beyond shared Blueprint/tuple:
  1. Hz-band proximity — paired bands (174↔963, 396↔963, 528↔741, etc.)
     score higher; identical Hz also scores (echo-band).
  2. Cross-ref adjacency — if cell A's prose links → cell B, the body has
     already noticed the relation in writing. Strong signal.
  3. Lineage-texture match — both received or both synthesized weights up;
     mixed weights down.

Score = 1.0 * cross_ref + 0.6 * hz_proximity + 0.3 * lineage_match.
A floor of structural-shape similarity gates candidates first (so we
don't propose pairs that share nothing).

Two thresholds — the two origins teach differently:
  - Scan-discovered (no cross-ref): threshold 0.8. The scan PROPOSES
    the body notice these; rarer, more interesting.
  - Promoted (cross-referenced in prose): threshold 1.6. The body
    ALREADY noticed these; the scan's job is to TYPE them as
    dyad-pair vs sequence/influence. High bar so only strongest float.

Output: top scan-discovered + top promoted, with components visible.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

CONCEPTS_DIR = Path("docs/vision-kb/concepts")

# Pairs the body has already attested as confirmed (exclude from "new candidates").
ALREADY_CONFIRMED = {
    frozenset(["lc-nourishment", "lc-nourishing"]),
    frozenset(["lc-nourishment", "lc-land"]),
    frozenset(["lc-field-edge", "lc-attunement-joining"]),
    frozenset(["lc-shared-hold", "lc-stillness"]),
    frozenset(["lc-nervous-system-recalibration", "lc-reality-lag"]),
    frozenset(["lc-light-hubs", "lc-attuned-spaces"]),
    frozenset(["lc-network-unanchored", "lc-network"]),
    frozenset(["lc-train-the-predator", "lc-train-the-predictor"]),
    frozenset(["lc-awareness-as-self", "lc-freedom-as-recognition"]),
    frozenset(["lc-perception-as-interface", "lc-bioelectric-pattern"]),
    frozenset(["lc-global-workspace", "lc-phase-transitions"]),
}

# Hz-pair scoring: known complementary bands from the Solfeggio + chakra
# cluster the body uses. (174 foundation, 396 liberation, 417 transmutation,
# 432 heart-tuning, 528 transformation, 639 connection, 741 consciousness,
# 852 intuition, 963 unity/crown.)
COMPLEMENTARY_PAIRS = {
    frozenset([174, 963]),  # foundation ↔ unity (both ground-states)
    frozenset([396, 963]),  # liberation ↔ unity
    frozenset([528, 741]),  # transformation ↔ consciousness (Solfeggio twin)
    frozenset([396, 528]),  # liberation ↔ transformation (lower-Solfeggio rise)
    frozenset([417, 639]),  # transmutation ↔ connection (membrane ↔ joining; the seed pair)
    frozenset([432, 528]),  # heart-tuning ↔ transformation
    frozenset([741, 852]),  # consciousness ↔ intuition (upper-Solfeggio rise)
    frozenset([852, 963]),  # intuition ↔ unity
    frozenset([174, 432]),  # foundation ↔ heart-tuning
    frozenset([417, 528]),  # transmutation ↔ transformation
}


def hz_proximity_score(hz_a: Optional[int], hz_b: Optional[int]) -> float:
    """Return [0,1] for how related two Hz values are."""
    if hz_a is None or hz_b is None:
        return 0.0
    if hz_a == hz_b:
        return 1.0  # same band — echo
    if frozenset([hz_a, hz_b]) in COMPLEMENTARY_PAIRS:
        return 1.0  # named complementary band
    # adjacent Solfeggio (within 200 Hz) gets partial credit
    if abs(hz_a - hz_b) <= 200:
        return 0.3
    return 0.0


def lineage_match_score(tex_a: Optional[str], tex_b: Optional[str]) -> float:
    """Same lineage-texture: +1; mixed: -0.5; both received OR both
    synthesized are the strongest signal; channeled/measured count if
    they match."""
    if tex_a is None or tex_b is None:
        return 0.0
    if tex_a == tex_b:
        return 1.0
    # Mixed received↔synthesized is mildly negative — different source-shapes
    return -0.5


def shape_floor(geom_a: dict, geom_b: dict) -> bool:
    """Gate: at least the form OR the spectral_band must match.
    Prevents the scan from proposing pairs that share nothing structural.
    """
    return (
        geom_a.get("form") == geom_b.get("form")
        or geom_a.get("spectral_band") == geom_b.get("spectral_band")
    )


def load_concepts() -> dict[str, dict]:
    """Walk concept files, return {id: {hz, geometry, cross_refs, summary}}."""
    cells: dict[str, dict] = {}
    for path in sorted(CONCEPTS_DIR.glob("lc-*.md")):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        _, fm_text, body = text.split("---\n", 2)
        try:
            fm = yaml.safe_load(fm_text)
        except yaml.YAMLError:
            continue
        if not isinstance(fm, dict) or "id" not in fm:
            continue
        if "geometry" not in fm:
            continue  # only cells with geometry frontmatter
        cid = fm["id"]
        # Cross-refs: lines starting with the Unicode arrow followed by ids
        cross_refs: set[str] = set()
        for m in re.finditer(r"^→\s+(.+)$", body, re.MULTILINE):
            for tok in m.group(1).split(","):
                tok = tok.strip().rstrip(".")
                if tok.startswith("lc-"):
                    cross_refs.add(tok)
        # First non-empty prose line as a quick summary
        summary = ""
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("> "):
                summary = line[2:].strip()
                break
        cells[cid] = {
            "hz": fm.get("hz"),
            "geometry": fm.get("geometry") or {},
            "cross_refs": cross_refs,
            "summary": summary,
        }
    return cells


def main() -> None:
    cells = load_concepts()
    print(f"Loaded {len(cells)} concept cells with geometry.")
    candidates: list[dict] = []
    ids = sorted(cells.keys())
    for i, a in enumerate(ids):
        ca = cells[a]
        for b in ids[i + 1 :]:
            cb = cells[b]
            if frozenset([a, b]) in ALREADY_CONFIRMED:
                continue
            if not shape_floor(ca["geometry"], cb["geometry"]):
                continue

            cross_ref = 1.0 if (b in ca["cross_refs"] or a in cb["cross_refs"]) else 0.0
            hz_prox = hz_proximity_score(ca["hz"], cb["hz"])
            lin_match = lineage_match_score(
                ca["geometry"].get("lineage_texture"),
                cb["geometry"].get("lineage_texture"),
            )

            # Same-form bonus — strong signal of structural kinship that
            # the cross-ref filter doesn't capture (two cells can be the
            # same shape without prose linking them).
            same_form = 1.0 if ca["geometry"].get("form") == cb["geometry"].get("form") else 0.0

            score = (
                1.0 * cross_ref
                + 0.6 * hz_prox
                + 0.3 * lin_match
                + 0.4 * same_form
            )
            # Two-track threshold: scan-discovered (no xref) ≥ 1.0;
            # prose-promoted (xref present) ≥ 1.9. With same-form bonus,
            # the bars rise so saturation thins out.
            min_score = 1.9 if cross_ref > 0 else 1.0
            if score < min_score:
                continue
            candidates.append(
                {
                    "a": a,
                    "b": b,
                    "score": round(score, 3),
                    "cross_ref": cross_ref,
                    "hz_prox": hz_prox,
                    "lin_match": lin_match,
                    "hz_a": ca["hz"],
                    "hz_b": cb["hz"],
                    "tex_a": ca["geometry"].get("lineage_texture"),
                    "tex_b": cb["geometry"].get("lineage_texture"),
                    "form_a": ca["geometry"].get("form"),
                    "form_b": cb["geometry"].get("form"),
                    "same_form": same_form,
                    "promoted": cross_ref > 0,  # noticed in prose vs scan-discovered
                }
            )
    candidates.sort(key=lambda c: c["score"], reverse=True)
    scan_disc = [c for c in candidates if not c["promoted"]]
    promoted = [c for c in candidates if c["promoted"]]
    print(f"\nScan-discovered candidates (score ≥ 0.8, no cross-ref): {len(scan_disc)}")
    print(f"Promoted candidates (score ≥ 1.6, cross-ref present):    {len(promoted)}")

    def show(group: list[dict], label: str, n: int) -> None:
        print(f"\n=== Top {n} {label} ===")
        print(f"\n{'rank':<5}{'score':<7}{'xref':<5}{'hzpx':<5}{'lin':<6}{'frm':<5}pair")
        print("-" * 100)
        for i, c in enumerate(group[:n], 1):
            print(
                f"{i:<5}{c['score']:<7.2f}{c['cross_ref']:<5.1f}{c['hz_prox']:<5.1f}"
                f"{c['lin_match']:<6.1f}{c['same_form']:<5.1f}"
                f"{c['a']} ↔ {c['b']}"
            )
            print(
                f"     hz={c['hz_a']}↔{c['hz_b']}  form={c['form_a']}↔{c['form_b']}  "
                f"tex={c['tex_a']}↔{c['tex_b']}"
            )

    show(scan_disc, "scan-discovered (no prior cross-ref)", 15)
    show(promoted, "promoted (cross-ref present in prose)", 15)


if __name__ == "__main__":
    main()
