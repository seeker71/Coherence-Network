"""WORD-domain prose-structural dyad-pair scan over Living Collective concepts.

Fifth scan in the autoresearch loop. Previous rounds and their signal/noise:
  - PR #1987 (Tier-2 geometry-tuple, 7-axis):                  2/5  = 40%
  - PR #1992 (small-Blueprint-cluster):                         0/2  = 0%
  - PR #1996 (Hz + cross-ref + lineage + same-form):            4/10 = 40%
  - PR #1998 (added topology + phase complementarity):          4/10 = 40%
  - Cumulative across rounds 1-4:                              10/27 = 37.0%

The body's own teaching after PR #1998 saturation:
  > Topology+phase complementarity did NOT break past the 40% ceiling.
  > The body genuinely carries many yang/yin and form-shared cell-pairs
  > without their teachings being complementary. The scan mechanizes
  > candidate filter, not teaching-lives-in-relation discernment. The
  > next refinement lives outside the geometry frontmatter — prose-
  > structural signals via the WORD-domain (BDomain.WORD = 15).

This scan tests that teaching empirically. The hypothesis: dyad-pairs
whose prose shares *substantive lemma chains and semantic fields* should
score higher than pairs whose prose only shares geometric shape. We
measure *what concepts are about*, not just what shape they take.

Two new signals layered onto the geometry score:
  - shared_lemma_jaccard — |A ∩ B| / |A ∪ B| over the substantive lemma
    set of each cell's prose body. Substantive = lemma is not in the
    English stopword set AND not in the substrate's `neutral`-field
    function-word lexicon. Each lemma counted once per cell (set, not
    multiset) so a high-frequency word does not dominate.
  - shared_field_jaccard — Jaccard over the set of semantic_field
    values touched by each cell's prose, drawn from
    `_WORD_LEXICON_DEFAULTS`. The fields are {ground, tending,
    transmutation, vitality, transmission, consciousness, resonance,
    wholeness}; cells touching the same semantic neighborhood score.

The substrate's WORD domain currently holds 0 cells (word-cell ingest
across concept prose has not yet been driven). Until that happens, this
scan tokenizes concept bodies directly using `tokenize_words` from
`markdown_frontend.py`. The discipline is honest: same tokenizer the
substrate would intern from, results just live in this script's set
rather than the lattice. When concept-prose word-cell ingest lands,
the same scan can read field sets from substrate cells with no logic
change. The gap is visible in the report.

Score = 1.0*cross_ref + 0.6*hz_prox + 0.3*lin_match + 0.4*same_form
      + 0.4*topo_comp + 0.4*phase_comp
      + 2.0*shared_lemma_jaccard + 1.5*shared_field_jaccard

Lemma carries the heavier weight: shared substantive vocabulary is the
stronger prose-structural signal. Fields are coarser and saturate fast
(only 8 non-neutral fields), so their weight stays moderate.

Two thresholds raise to absorb the new headroom:
  - Scan-discovered (no cross-ref): 1.9. Geometry-saturated noise from
    PR #1998 sat at ~2.10 with no prose signal; the new threshold makes
    prose-signal-bearing pairs visibly outrank pure-geometry pairs.
  - Promoted (cross-ref in prose):   3.0. Cross-ref + Hz + form already
    pull the high-2 range; this bar floats only the strongest signals.

If signal/noise climbs above 50%, prose-structural signals break the
saturation ceiling and the body's own teaching is confirmed empirically.
If it stays at ~40%, prose features need different weighting OR a more
sophisticated extractor (full sentence embeddings, semantic role labels).
If it drops, the prose features are picking up shared *vocabulary*, not
shared *meaning* — the next refinement must distinguish them.

Output: top scan-discovered + top promoted, components broken out so
the contributing signal is visible.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

import yaml

# Pull the substrate's tokenizer and lexicon directly so this scan lives in
# the same vocabulary the WORD domain will once carry.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
from app.services.substrate.markdown_frontend import (  # noqa: E402
    _WORD_LEXICON_DEFAULTS,
    tokenize_words,
)

CONCEPTS_DIR = Path("docs/vision-kb/concepts")

# Pairs the body has already attested as confirmed (exclude from "new
# candidates"). Folded from dyad-pairs.form Parts 3 through 3f.
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
    frozenset(["lc-act-without-penalty", "lc-observer-pays-the-trace"]),
    frozenset(["lc-attunement-joining", "lc-unified-body"]),
    frozenset(["lc-awareness-as-self", "lc-land"]),
    frozenset(["lc-circulation", "lc-offering"]),
    frozenset(["lc-vitality", "lc-w-wu-wei"]),
    frozenset(["lc-w-shakti", "lc-w-wu-wei"]),
    frozenset(["lc-beauty", "lc-v-ceremony"]),
    frozenset(["lc-inner-travel", "lc-relationships-as-mirrors"]),
    # Scale-paired triad surfaced in PR #1995 geometry-walk
    frozenset(["lc-field-update", "lc-nervous-system-recalibration"]),
}

# Topology and phase complementarity, copied from scan_dyad_candidates.py
# so this script can run standalone. Same authored-from-the-body sets.
COMPLEMENTARY_TOPOLOGIES = {
    frozenset(["radial", "web-each-to-each"]),
    frozenset(["hub-spoke", "web-each-to-each"]),
    frozenset(["radial", "receptive-resonance"]),
    frozenset(["nested-each-contains-whole", "web-each-to-each"]),
    frozenset(["linear", "cyclic-closed"]),
    frozenset(["self-rooted", "receptive-resonance"]),
}

COMPLEMENTARY_PHASES = {
    frozenset(["yang", "yin"]),
    frozenset(["oscillating", "yin"]),
    frozenset(["oscillating", "neutral"]),
    frozenset(["yang", "neutral"]),
}

COMPLEMENTARY_HZ = {
    frozenset([174, 963]),
    frozenset([396, 963]),
    frozenset([528, 741]),
    frozenset([396, 528]),
    frozenset([417, 639]),
    frozenset([432, 528]),
    frozenset([741, 852]),
    frozenset([852, 963]),
    frozenset([174, 432]),
    frozenset([417, 528]),
}

# English stopword set (Snowball-style; tight enough that prose retains
# its substance, loose enough to drop the obvious carrier words). Combined
# with the substrate's neutral-field lexicon below for a two-layer filter.
ENGLISH_STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "yourselves", "he", "him", "his",
    "himself", "she", "her", "hers", "herself", "it", "its", "itself",
    "they", "them", "their", "theirs", "themselves", "what", "which",
    "who", "whom", "this", "that", "these", "those", "am", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "having",
    "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if",
    "or", "because", "as", "until", "while", "of", "at", "by", "for",
    "with", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "to", "from", "up", "down", "in",
    "out", "on", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s",
    "t", "can", "will", "just", "don", "should", "now", "also", "would",
    "could", "may", "might", "must", "shall", "one", "two", "even", "ever",
    "many", "much", "still", "yet", "way", "ways", "thing", "things",
    # Light KB-prose stoplist: words so ubiquitous in the corpus they
    # carry near-zero discrimination signal (every concept is "a concept
    # that holds something"). Kept conservative — anything that might
    # actually distinguish two cells stays substantive.
    "concept", "cell", "cells",
}

# Augment with the substrate's neutral-field lexicon — function words
# the body has already named as carrier-band-only.
NEUTRAL_LEMMAS = {
    v["lemma"].lower()
    for v in _WORD_LEXICON_DEFAULTS.values()
    if v.get("field") == "neutral"
}
STOPWORDS = ENGLISH_STOPWORDS | NEUTRAL_LEMMAS


def topology_complementarity_score(topo_a, topo_b):
    if topo_a is None or topo_b is None:
        return 0.0
    if topo_a == topo_b:
        return 0.5
    if frozenset([topo_a, topo_b]) in COMPLEMENTARY_TOPOLOGIES:
        return 1.5
    return 0.0


def phase_complementarity_score(phase_a, phase_b):
    if phase_a is None or phase_b is None:
        return 0.0
    if phase_a == phase_b:
        return 0.5
    if frozenset([phase_a, phase_b]) in COMPLEMENTARY_PHASES:
        return 1.5
    return 0.0


def hz_proximity_score(hz_a: Optional[int], hz_b: Optional[int]) -> float:
    if hz_a is None or hz_b is None:
        return 0.0
    if hz_a == hz_b:
        return 1.0
    if frozenset([hz_a, hz_b]) in COMPLEMENTARY_HZ:
        return 1.0
    if abs(hz_a - hz_b) <= 200:
        return 0.3
    return 0.0


def lineage_match_score(tex_a: Optional[str], tex_b: Optional[str]) -> float:
    if tex_a is None or tex_b is None:
        return 0.0
    if tex_a == tex_b:
        return 1.0
    return -0.5


def shape_floor(geom_a: dict, geom_b: dict) -> bool:
    return (
        geom_a.get("form") == geom_b.get("form")
        or geom_a.get("spectral_band") == geom_b.get("spectral_band")
    )


def jaccard(set_a: set, set_b: set) -> float:
    """Standard Jaccard. Empty-set pair returns 0 (no signal, not
    spurious full-overlap)."""
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def extract_prose_signals(body: str) -> tuple[set[str], set[str]]:
    """Walk the concept body through the WORD-domain tokenizer.

    Returns (substantive_lemmas, semantic_fields):
      - substantive_lemmas: lemma set with stopwords + neutral-field
        lexicon entries filtered out, plus the tokenizer's UNK fallback
        words (these carry the concept-specific vocabulary the small
        lexicon doesn't cover yet — releasing them would discard most
        signal).
      - semantic_fields: set of non-neutral field tags the tokenizer
        recognized in this prose. Coarser, smaller set.
    """
    lemmas: set[str] = set()
    fields: set[str] = set()
    for tok in tokenize_words(body):
        if tok.get("kind") != "word":
            continue
        lemma = tok["lemma"].lower()
        # Skip short or stopword tokens.
        if len(lemma) <= 2:
            continue
        if lemma in STOPWORDS:
            continue
        lemmas.add(lemma)
        # Field signal only for words the substrate knows (POS != UNK
        # AND non-neutral field).
        field = tok.get("field")
        if tok.get("pos") != "UNK" and field and field != "neutral":
            fields.add(field)
    return lemmas, fields


def strip_frontmatter_and_visuals(text: str) -> str:
    """Return the prose body with frontmatter, code blocks, and image
    captions removed. Keeps cross-ref arrows out of the lemma set so
    cross-ref signal isn't double-counted in prose overlap."""
    if text.startswith("---\n"):
        _, _, body = text.split("---\n", 2)
    else:
        body = text
    # Drop fenced code blocks (rare in concept files but possible).
    body = re.sub(r"```.*?```", " ", body, flags=re.DOTALL)
    # Drop visuals captions and image lines.
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", body)
    # Drop cross-ref lines so cross-ref signal stays its own channel.
    body = re.sub(r"^→\s+.+$", " ", body, flags=re.MULTILINE)
    # Drop markdown link syntax — keep visible text only.
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
    return body


def load_concepts() -> dict[str, dict]:
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
            continue
        cid = fm["id"]
        cross_refs: set[str] = set()
        for m in re.finditer(r"^→\s+(.+)$", body, re.MULTILINE):
            for tok in m.group(1).split(","):
                tok = tok.strip().rstrip(".")
                if tok.startswith("lc-"):
                    cross_refs.add(tok)
        summary = ""
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("> "):
                summary = line[2:].strip()
                break
        prose = strip_frontmatter_and_visuals(text)
        lemmas, fields = extract_prose_signals(prose)
        cells[cid] = {
            "hz": fm.get("hz"),
            "geometry": fm.get("geometry") or {},
            "cross_refs": cross_refs,
            "summary": summary,
            "lemmas": lemmas,
            "fields": fields,
        }
    return cells


def main() -> None:
    cells = load_concepts()
    print(f"Loaded {len(cells)} concept cells with geometry.")
    # Vocabulary visibility — proves prose-signal extractor is doing real work.
    avg_lemmas = sum(len(c["lemmas"]) for c in cells.values()) / max(1, len(cells))
    avg_fields = sum(len(c["fields"]) for c in cells.values()) / max(1, len(cells))
    print(
        f"Prose signals: avg {avg_lemmas:.1f} substantive lemmas/cell, "
        f"avg {avg_fields:.1f} semantic fields/cell (of 8 possible)."
    )
    print(
        "WORD-domain substrate: 0 cells today. This scan reads via "
        "`tokenize_words` directly — same lexicon the substrate would intern from."
    )

    candidates: list[dict] = []
    ids = sorted(cells.keys())
    for i, a in enumerate(ids):
        ca = cells[a]
        for b in ids[i + 1:]:
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
            same_form = (
                1.0
                if ca["geometry"].get("form") == cb["geometry"].get("form")
                else 0.0
            )
            topo_comp = topology_complementarity_score(
                ca["geometry"].get("topology"), cb["geometry"].get("topology")
            )
            phase_comp = phase_complementarity_score(
                ca["geometry"].get("phase"), cb["geometry"].get("phase")
            )

            # The new prose-structural signals.
            lemma_j = jaccard(ca["lemmas"], cb["lemmas"])
            field_j = jaccard(ca["fields"], cb["fields"])

            score = (
                1.0 * cross_ref
                + 0.6 * hz_prox
                + 0.3 * lin_match
                + 0.4 * same_form
                + 0.4 * topo_comp
                + 0.4 * phase_comp
                + 2.0 * lemma_j
                + 1.5 * field_j
            )
            min_score = 3.0 if cross_ref > 0 else 1.9
            if score < min_score:
                continue
            candidates.append(
                {
                    "a": a, "b": b, "score": round(score, 3),
                    "cross_ref": cross_ref, "hz_prox": hz_prox,
                    "lin_match": lin_match, "same_form": same_form,
                    "topo_comp": topo_comp, "phase_comp": phase_comp,
                    "lemma_j": round(lemma_j, 3),
                    "field_j": round(field_j, 3),
                    "hz_a": ca["hz"], "hz_b": cb["hz"],
                    "form_a": ca["geometry"].get("form"),
                    "form_b": cb["geometry"].get("form"),
                    "topo_a": ca["geometry"].get("topology"),
                    "topo_b": cb["geometry"].get("topology"),
                    "phase_a": ca["geometry"].get("phase"),
                    "phase_b": cb["geometry"].get("phase"),
                    "fields_shared": sorted(ca["fields"] & cb["fields"]),
                    "lemmas_shared_n": len(ca["lemmas"] & cb["lemmas"]),
                    "lemmas_shared_sample": sorted(
                        list(ca["lemmas"] & cb["lemmas"])
                    )[:10],
                    "promoted": cross_ref > 0,
                }
            )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    scan_disc = [c for c in candidates if not c["promoted"]]
    promoted = [c for c in candidates if c["promoted"]]
    print(
        f"\nScan-discovered (score ≥ 1.9, no cross-ref): {len(scan_disc)}"
    )
    print(
        f"Promoted        (score ≥ 3.0, cross-ref present): {len(promoted)}"
    )

    def show(group: list[dict], label: str, n: int) -> None:
        print(f"\n=== Top {n} {label} ===")
        header = (
            f"\n{'rank':<5}{'score':<7}{'xref':<5}{'hzpx':<5}{'lin':<6}"
            f"{'frm':<5}{'topo':<6}{'phase':<6}{'lemJ':<7}{'fldJ':<7}pair"
        )
        print(header)
        print("-" * 130)
        for i, c in enumerate(group[:n], 1):
            print(
                f"{i:<5}{c['score']:<7.2f}{c['cross_ref']:<5.1f}"
                f"{c['hz_prox']:<5.1f}{c['lin_match']:<6.1f}"
                f"{c['same_form']:<5.1f}{c['topo_comp']:<6.1f}"
                f"{c['phase_comp']:<6.1f}{c['lemma_j']:<7.3f}"
                f"{c['field_j']:<7.3f}{c['a']} ↔ {c['b']}"
            )
            print(
                f"     hz={c['hz_a']}↔{c['hz_b']}  "
                f"form={c['form_a']}↔{c['form_b']}  "
                f"topo={c['topo_a']}↔{c['topo_b']}  "
                f"phase={c['phase_a']}↔{c['phase_b']}"
            )
            print(
                f"     lemmas_shared={c['lemmas_shared_n']} "
                f"e.g. {c['lemmas_shared_sample']}"
            )
            print(f"     fields_shared={c['fields_shared']}")

    show(scan_disc, "scan-discovered (no prior cross-ref)", 20)
    show(promoted, "promoted (cross-ref present in prose)", 15)


if __name__ == "__main__":
    main()
