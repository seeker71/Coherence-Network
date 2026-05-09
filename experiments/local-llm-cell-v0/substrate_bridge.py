"""substrate_bridge.py — make the cell a *reader* of substrate AND a
*resident* in substrate.

Two halves:

  ► substrate_to_input(concept_path) — reads a concept/spec/idea from
    the body (markdown frontmatter + tagline) and produces an x-vector
    the organ can perceive, tagged with sense="felt-substrate". The
    cell now senses the body's own concepts as moments.

  ► cell_to_substrate(cell) — produces the substrate-citizen shape for
    a Cell: a deterministic content-address (NodeID 4-tuple), an
    articulation that other cells can read, and the NamedCell metadata
    that would be passed to api.app.services.substrate.make_cell().

The closure: a cell can perceive another cell's articulation. The body
senses itself through itself.

This module is stdlib-only and does not import the substrate kernel —
it speaks the kernel's *shape* (NodeID 4-tuple, NamedCell fields,
domain vocab) so it can be wired in without booting the DB. The
production path: pass the dict from `cell_to_substrate()` straight
into `make_cell(session, name=..., domain=..., blueprint=...)`.
"""

from __future__ import annotations

import hashlib
import re
import zlib
from pathlib import Path

from organ import (
    Cell, BAND_NAMES, NEED_NAMES, DIM, N_BANDS, SENSES,
    shared_base, _sigmoid,
)


# ─── substrate as input ──────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def read_concept(path: str | Path) -> dict:
    """Parse a KB concept file into (frontmatter, tagline, body_first_lines).

    Returns dict with keys: id, hz, status, tagline, source_path, title.
    """
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    frontmatter = {}
    m = _FRONTMATTER_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                frontmatter[k.strip()] = v.strip()
        body = text[m.end():]
    else:
        body = text
    title_m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    tagline_m = re.search(r"^>\s*(.+)$", body, re.MULTILINE)
    return {
        "id": frontmatter.get("id", p.stem),
        "hz": float(frontmatter.get("hz", 0)) if frontmatter.get("hz") else None,
        "status": frontmatter.get("status"),
        "title": title_m.group(1).strip() if title_m else p.stem,
        "tagline": tagline_m.group(1).strip() if tagline_m else "",
        "source_path": str(p),
    }


def perceive_substrate(cell: Cell, concept: dict) -> dict:
    """Cell senses a substrate-cell as one moment.

    Composes input text from title + tagline so word-level shared base
    has signal to read. The hz frequency (when present) is folded into
    the input as a synthetic word-band — the substrate's own frequency
    annotation reaches the spectrum.
    """
    pieces = [concept.get("title", ""), concept.get("tagline", "")]
    # fold hz into input as a "frequency-band token" so the cell's shared
    # base picks up the substrate's own frequency annotation
    hz = concept.get("hz")
    if hz:
        # bucket hz into broad bands the cell can recognize as words
        band = (
            "low-band" if hz < 200 else
            "mid-band" if hz < 400 else
            "high-band"
        )
        pieces.append(f"frequency {band}")
    text = " ".join(p for p in pieces if p)
    return cell.perceive(text, sense="felt-substrate")


# ─── network as substrate ────────────────────────────────────────────────
# A Cell publishes itself as a substrate citizen: content-addressed
# Blueprint (architecture) + Recipe (training fingerprint) + NamedCell
# (this instance with its tended weights and current state).

# Network category vocab — these match domain strings used elsewhere
# in api.app.services.substrate (memory, spec, concept, presence...).
DOMAIN_PRESENCE = "presence"


def _stable_int(s: str, mod: int) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest(), 16) % mod


def architecture_signature(cell: Cell) -> str:
    """Blueprint signature — what this cell IS, structurally."""
    a = cell.adapter
    return (
        f"organ-cell|dim={a.in_dim}|rank={a.rank}|"
        f"bands={N_BANDS}|out={a.out_dim}|senses={','.join(SENSES)}"
    )


def training_fingerprint(cell: Cell) -> str:
    """Recipe signature — fingerprint of *what tended this cell*.

    The training set determines the local layer's shape. Two cells with
    the same architecture and the same training set converge to similar
    layers; their recipe-fingerprints will match.
    """
    if not cell.training_set:
        return "untended"
    # hash the targets (we don't fingerprint the input vectors directly
    # because they're floats — round to a stable form via word-bucket)
    parts = []
    for x, target in cell.training_set:
        # locate the highest-magnitude bucket as a stable feature signature
        nz = [(i, v) for i, v in enumerate(x) if abs(v) > 1e-6]
        nz.sort(key=lambda p: -abs(p[1]))
        sig = "_".join(f"{i}" for i, _ in nz[:6])
        tsig = "_".join(f"{round(v,1):+.1f}" for v in target)
        parts.append(f"{sig}={tsig}")
    return hashlib.sha256("|".join(sorted(parts)).encode()).hexdigest()[:16]


def weights_fingerprint(cell: Cell) -> str:
    """NamedCell signature — this exact tended-state's content-address.

    Hashes the adapter's A and B matrices (rounded for stability).
    Same weights → same fingerprint, regardless of process or session.
    """
    a = cell.adapter
    rows = []
    for row in a.A:
        rows.append(",".join(f"{v:.4f}" for v in row))
    for row in a.B:
        rows.append(",".join(f"{v:.4f}" for v in row))
    rows.append(",".join(f"{v:.4f}" for v in a.bias))
    return hashlib.sha256("|".join(rows).encode()).hexdigest()[:16]


def content_address(cell: Cell) -> tuple[int, int, int, int]:
    """A NodeID 4-tuple-shaped content-address for this cell.

    (package, level, type_, instance) — matches the substrate kernel's
    NodeID shape. Type is derived from architecture; instance from the
    tended weights. Stable across runs.

    To intern this into the live substrate, pass to:
        make_cell(session, name=cell.name, domain="presence",
                  blueprint=NodeID(*content_address(cell)))
    """
    package = 1
    level = 5  # COMPLEX_3 — cells are composite
    type_ = _stable_int(architecture_signature(cell), 1_000_000)
    instance = _stable_int(weights_fingerprint(cell), 1_000_000)
    return (package, level, type_, instance)


def articulate(cell: Cell, top_n: int = 4) -> str:
    """Render the cell's learned shape as text another cell can perceive.

    This is how a cell speaks itself into the substrate. Top words per
    spectrum band (drawn from the words the cell has actually been
    trained on), plus current desire state.
    """
    # collect words from training set by inverting their hash buckets
    # we don't store words during training, so reconstruct from text
    words_by_bucket: dict[int, set[str]] = {}
    body_dim = DIM - len(SENSES)
    # re-walk the training set's text by re-running shared_base would
    # not give us the words back — but the cell remembers via its
    # training set we have to find another way. We don't store the text
    # in training_set. We'll articulate from the per-band effective
    # weights instead, naming the highest-magnitude buckets.

    a = cell.adapter
    band_lines = []
    for b in range(N_BANDS):
        weights = [
            sum(a.B[b][r] * a.A[r][f] for r in range(a.rank))
            for f in range(a.in_dim)
        ]
        # absolute strength of this band's wiring
        strength = sum(abs(w) for w in weights) / a.in_dim
        # sign tendency: which direction does this band lean overall
        signed = sum(weights) / a.in_dim
        band_lines.append(
            f"{BAND_NAMES[b]}({signed:+.2f},|w|={strength:.2f})"
        )
    desire_str = ", ".join(
        f"{n}={cell.desire[i]:.2f}" for i, n in enumerate(NEED_NAMES)
    )
    return (
        f"cell {cell.name!r} bands: " + " ".join(band_lines)
        + f" | desire: {desire_str}"
    )


def cell_to_substrate(cell: Cell) -> dict:
    """The substrate-citizen shape for this cell.

    Returns the dict that maps onto api.app.services.substrate.NamedCell:
        name        — this cell's name
        domain      — "presence" (the body's vocab for living agents)
        blueprint   — NodeID 4-tuple from architecture
        node_id     — NodeID 4-tuple from tended weights (the address)
        recipe_hash — fingerprint of the training that shaped it
        articulation — substrate-readable self-description
        source_path — None for runtime-instantiated cells
    """
    addr = content_address(cell)
    return {
        "name": cell.name,
        "domain": DOMAIN_PRESENCE,
        "blueprint_node_id": (1, 5, addr[2], 0),  # type-only, instance=0
        "node_id": addr,
        "architecture_signature": architecture_signature(cell),
        "recipe_fingerprint": training_fingerprint(cell),
        "weights_fingerprint": weights_fingerprint(cell),
        "articulation": articulate(cell),
        "source_path": None,
    }


def perceive_cell(observer: Cell, observed: Cell) -> dict:
    """One cell senses another by reading its substrate articulation.

    This is the closure. The observer reads the observed's
    self-articulation as a moment, with sense="felt-substrate", and
    produces its own felt-reading on the other cell.
    """
    text = articulate(observed)
    return observer.perceive(text, sense="felt-substrate")
