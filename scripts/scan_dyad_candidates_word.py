"""WORD-domain prose-structural dyad-pair scan over Living Collective concepts.

Six scan rounds in the autoresearch loop. Signal/noise across rounds:
  - PR #1987 (Tier-2 geometry-tuple, 7-axis):                  2/5  = 40%
  - PR #1992 (small-Blueprint-cluster):                         0/2  = 0%
  - PR #1996 (Hz + cross-ref + lineage + same-form):            4/10 = 40%
  - PR #1998 (added topology + phase complementarity):          4/10 = 40%
  - PR #2001 (WORD-domain prose Jaccard, tokenizer-direct):     4/18 = 22%
  - Round 6 (this script's --substrate-native mode):            see GAP-D6
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

PR #2001's honest finding (40 → 0 → 40 → 40 → 22 across five rounds)
named the ceiling. Round 5 added a new mode: `--cross-ref-only`. The
mode drops the scan-discovered track entirely and only emits pairs
whose prose names the other cell. The cross-reference IS the body's
noticing; the promoted track sustained ~75% confirmation across the
five rounds while the scan-discovered track capped near 40% and
dropped to ~20% with prose-Jaccard. The structural-scoring becomes
a *candidate ordering* over the body's own noticing, not a
*candidate discovery* mechanism in its own right.

Usage:
  python3 scripts/scan_dyad_candidates_word.py
  python3 scripts/scan_dyad_candidates_word.py --cross-ref-only
"""

from __future__ import annotations

import argparse
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
from app.services.unified_db import session as session_scope  # noqa: E402
from sqlalchemy import text  # noqa: E402

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
    # PR #2001 — WORD-domain prose-structural scan additions
    frozenset(["lc-trust-as-gateway", "lc-vitality"]),
    frozenset(["lc-grammar-as-readable-bnf", "lc-parsers-as-recipes"]),
    frozenset(["lc-rest", "lc-tend-your-flame"]),
    frozenset(["lc-shifted-return", "lc-train-the-predator"]),
    # PR #2002 — cross-ref-only scan promotion
    frozenset(["lc-resonating", "lc-sensing"]),
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


def load_substrate_prose_signals() -> dict[str, tuple[set[str], set[str]]]:
    """Walk every concept's ctor_recipe in the substrate, collect its
    word-cell REF leaves, and return {concept_id: (lemmas, fields)}.

    This is the substrate-native read: prose lives in the lattice as a
    SEQUENCE of word-cell refs (via section_content_to_word_sequence).
    We traverse the recipe tree until we hit RType.REF (1.1.9.*) leaves,
    each of which is a cell_id pointing at a word-cell in substrate_named_cells.
    The word-cell's name encodes (lemma, POS); we parse it back.

    Field tagging comes from _WORD_LEXICON_DEFAULTS — the 50-word seed
    lexicon. 99.5% of interned word-cells are POS=UNK (the lemmatizer
    is the v0 fallback) so most cells contribute lemma signal but no
    field signal. Honest finding; do not engineer around it.

    Returns empty dict when WORD domain is empty (caller falls back).
    """
    cells_by_path: dict[str, tuple[set[str], set[str]]] = {}
    with session_scope() as s:
        # Verify WORD domain is populated first.
        word_count = s.execute(
            text("SELECT COUNT(*) FROM substrate_named_cells WHERE domain='word'")
        ).scalar() or 0
        if word_count == 0:
            return {}

        # Pull all word-cells once into an in-memory map: cell_id -> (lemma, pos)
        word_rows = s.execute(
            text("SELECT cell_id, name FROM substrate_named_cells WHERE domain='word'")
        ).fetchall()
        word_map: dict[int, tuple[str, str]] = {}
        for row in word_rows:
            # name format is "{lemma}.{POS}"; some lemmas contain dots
            # (e.g. punctuation) so rsplit once on the rightmost dot.
            if "." in row.name:
                lemma, pos = row.name.rsplit(".", 1)
            else:
                lemma, pos = row.name, "UNK"
            word_map[row.cell_id] = (lemma.lower(), pos)

        # Pull all substrate_nodes once into a serialized-map for fast walk.
        # node_id -> serialized string. Trade memory for query count.
        node_rows = s.execute(
            text("SELECT node_id, serialized FROM substrate_nodes")
        ).fetchall()
        ser_by_id: dict[int, str] = {r.node_id: r.serialized for r in node_rows}
        # Also reverse-index by (p,l,t,i) -> node_id so child refs resolve.
        id_by_quad: dict[tuple[int, int, int, int], int] = {}
        node_rows2 = s.execute(
            text("SELECT node_id, package, level, type, instance FROM substrate_nodes")
        ).fetchall()
        for r in node_rows2:
            id_by_quad[(r.package, r.level, r.type, r.instance)] = r.node_id

        def collect_refs(node_id: int, visited: set[int]) -> list[int]:
            if node_id in visited:
                return []
            visited.add(node_id)
            ser = ser_by_id.get(node_id)
            if not ser:
                return []
            parts = ser.split("+")
            refs: list[int] = []
            # Skip first part (the category); walk children.
            for piece in parts[1:]:
                try:
                    a, b, c, d = (int(x) for x in piece.split("."))
                except ValueError:
                    continue
                if a == 1 and b == 1 and c == 9:
                    # RType.REF — cell_id is d
                    refs.append(d)
                else:
                    child_nid = id_by_quad.get((a, b, c, d))
                    if child_nid is not None:
                        refs.extend(collect_refs(child_nid, visited))
            return refs

        # Walk each concept's ctor_recipe.
        concept_rows = s.execute(
            text(
                "SELECT name, source_path, ctor_recipe_node_id FROM "
                "substrate_named_cells WHERE domain='concept' AND "
                "ctor_recipe_node_id IS NOT NULL"
            )
        ).fetchall()
        for cr in concept_rows:
            if cr.ctor_recipe_node_id is None:
                continue
            ref_cell_ids = collect_refs(cr.ctor_recipe_node_id, set())
            lemmas: set[str] = set()
            fields: set[str] = set()
            for cid in ref_cell_ids:
                wm = word_map.get(cid)
                if wm is None:
                    continue
                lemma, pos = wm
                if len(lemma) <= 2:
                    continue
                if lemma in STOPWORDS:
                    continue
                lemmas.add(lemma)
                # Field tagging: look up in the lexicon by lemma.
                lex = _WORD_LEXICON_DEFAULTS.get(lemma)
                if lex and pos != "UNK":
                    field = lex.get("field")
                    if field and field != "neutral":
                        fields.add(field)
            # Concept's lc-id is the file basename (concept name in substrate
            # IS the lc-id already since ingest sets name=fm['id']).
            cells_by_path[cr.name] = (lemmas, fields)
    return cells_by_path


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


def load_concepts(substrate_native: bool = False) -> dict[str, dict]:
    """Walk concept files and assemble per-cell signals.

    When `substrate_native=True`, lemma/field sets come from
    `load_substrate_prose_signals` (the WORD-domain substrate read)
    rather than from re-tokenizing the markdown body. If the substrate
    is empty, fall back to tokenizer-direct with a printed warning so
    the gap is visible.
    """
    substrate_signals: dict[str, tuple[set[str], set[str]]] = {}
    if substrate_native:
        substrate_signals = load_substrate_prose_signals()
        if not substrate_signals:
            print(
                "WARN: --substrate-native requested but WORD domain is empty. "
                "Falling back to tokenizer-direct read for this run."
            )
            substrate_native = False

    cells: dict[str, dict] = {}
    for path in sorted(CONCEPTS_DIR.glob("lc-*.md")):
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---\n"):
            continue
        _, fm_text, body = raw.split("---\n", 2)
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
        if substrate_native and cid in substrate_signals:
            lemmas, fields = substrate_signals[cid]
        else:
            prose = strip_frontmatter_and_visuals(raw)
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
    parser = argparse.ArgumentParser(
        description=(
            "Dyad-pair candidate scan over Living Collective concepts. "
            "Default mode runs the geometry+prose scoring against both "
            "scan-discovered and promoted tracks. --cross-ref-only drops "
            "the scan-discovered track entirely and only emits pairs whose "
            "prose already names the other cell (cross-reference present). "
            "The cross-ref track sustained ~75% confirmation across five "
            "scan rounds while the scan-discovered track capped near 40% "
            "and dropped to ~20% with prose-Jaccard. See dyad-pairs.form "
            "Part 5 GAP-D6 for the empirical trace."
        )
    )
    parser.add_argument(
        "--cross-ref-only",
        action="store_true",
        help=(
            "Drop the scan-discovered track entirely. Return only "
            "candidates where one cell's prose contains a cross-reference "
            "to the other. Cross-reference IS the body's noticing; this "
            "mode honors that."
        ),
    )
    parser.add_argument(
        "--substrate-native",
        action="store_true",
        help=(
            "Read lemma/field sets from the WORD-domain substrate (via "
            "each concept's ctor_recipe walk) rather than re-tokenizing "
            "the markdown file. Empirical round-6 test: does substrate-"
            "native prose reading change signal/noise vs tokenizer-direct?"
        ),
    )
    args = parser.parse_args()

    cells = load_concepts(substrate_native=args.substrate_native)
    print(f"Loaded {len(cells)} concept cells with geometry.")
    # Vocabulary visibility — proves prose-signal extractor is doing real work.
    avg_lemmas = sum(len(c["lemmas"]) for c in cells.values()) / max(1, len(cells))
    avg_fields = sum(len(c["fields"]) for c in cells.values()) / max(1, len(cells))
    print(
        f"Prose signals: avg {avg_lemmas:.1f} substantive lemmas/cell, "
        f"avg {avg_fields:.1f} semantic fields/cell (of 8 possible)."
    )
    if args.substrate_native:
        print(
            "WORD-domain substrate: read directly via concept ctor_recipe "
            "walk. Each lemma set comes from interned word-cell REF leaves "
            "(99.5% POS=UNK in current lexicon — field signal is degraded)."
        )
    else:
        print(
            "WORD-domain substrate: read via `tokenize_words` directly — "
            "same lexicon the substrate would intern from. Use "
            "--substrate-native to read from the lattice instead."
        )
    if args.cross_ref_only:
        print(
            "\nMode: --cross-ref-only — scan-discovered track DROPPED. "
            "Returning only pairs whose prose already names the other cell."
        )

    candidates: list[dict] = []
    ids = sorted(cells.keys())
    for i, a in enumerate(ids):
        ca = cells[a]
        for b in ids[i + 1:]:
            cb = cells[b]
            if frozenset([a, b]) in ALREADY_CONFIRMED:
                continue
            cross_ref = 1.0 if (b in ca["cross_refs"] or a in cb["cross_refs"]) else 0.0
            # In cross-ref-only mode, the scan-discovered track is dropped
            # entirely. Only promoted pairs (cross-reference already present
            # in prose) reach the scoring stage. The body's noticing —
            # the cross-reference itself — is load-bearing.
            if args.cross_ref_only and cross_ref == 0.0:
                continue
            if not shape_floor(ca["geometry"], cb["geometry"]):
                continue

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
            # In cross-ref-only mode, drop the score threshold to 0 — the
            # cross-reference itself is the body's noticing; if it's
            # present, the pair is worth surfacing for human assessment
            # whether or not the geometry+prose features back it up.
            if args.cross_ref_only:
                min_score = 0.0
            else:
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
    if args.cross_ref_only:
        print(
            f"\nCross-ref-promoted candidates (cross-ref present): "
            f"{len(promoted)}"
        )
    else:
        print(
            f"\nScan-discovered (score ≥ 1.9, no cross-ref): {len(scan_disc)}"
        )
        print(
            f"Promoted        (score ≥ 3.0, cross-ref present): "
            f"{len(promoted)}"
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

    if args.cross_ref_only:
        show(promoted, "cross-ref-promoted (the body's noticing)", 50)
    else:
        show(scan_disc, "scan-discovered (no prior cross-ref)", 20)
        show(promoted, "promoted (cross-ref present in prose)", 15)


if __name__ == "__main__":
    main()
