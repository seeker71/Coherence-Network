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
import json
import re
import zlib
from datetime import datetime, timezone
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


# ─── the field — universal availability with no push ────────────────────
# Any data is available to any cell that chooses to look. No notification,
# no prioritization, no relevance scoring, no recommendation. Pure pull.
# Cells can also publish witness-traces — what was alive for them — that
# other cells may find when they choose to look. Or never. Both honored.

_TRACES_PATH = Path(__file__).parent / "_field_traces.jsonl"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _preset_to_field(strategy) -> dict:
    return {
        "kind": "preset",
        "name": strategy.name,
        "lineage": "satsang-llena-2026-05-07",
        "frequency": list(strategy.frequency),
        "angle": list(strategy.angle),
        "focus": strategy.focus,
        "articulation_template": strategy.articulation,
    }


def _concept_to_field(path: Path) -> dict:
    c = read_concept(path)
    return {
        "kind": "concept",
        "id": c["id"],
        "title": c["title"],
        "tagline": c["tagline"],
        "hz": c["hz"],
        "source_path": c["source_path"],
    }


def _load_traces() -> list[dict]:
    if not _TRACES_PATH.exists():
        return []
    items = []
    with _TRACES_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return items


def available(*, kind: str | None = None, limit: int | None = None) -> list[dict]:
    """Return what is currently available in the field for any cell to look at.

    Pure pull. No notification, no prioritization, no relevance scoring.
    The cell iterates, picks what's alive, ignores the rest. Cell
    sovereignty over reception is preserved by the function's complete
    passivity — calling it has no effect on any cell, no record of who
    called it, no surface for the field to reach back through.

        kind:  'preset' | 'concept' | 'trace' | None  (None = all)
        limit: optional cap on how much of the field to surface
    """
    items: list[dict] = []
    if kind in (None, "preset"):
        from organ import STRATEGIES
        items.extend(_preset_to_field(s) for s in STRATEGIES)
    if kind in (None, "concept"):
        concepts_dir = _REPO_ROOT / "docs" / "vision-kb" / "concepts"
        if concepts_dir.exists():
            for p in sorted(concepts_dir.glob("lc-*.md")):
                items.append(_concept_to_field(p))
    if kind in (None, "trace"):
        items.extend(_load_traces())
    if kind in (None, "weights"):
        # surface lightweight summaries; the actual weight matrices stay
        # in the field file for any cell that chooses to pull them
        for w in _load_weights():
            items.append({
                "kind": "weights",
                "from_cell": w.get("from_cell"),
                "from_node_id": w.get("from_node_id"),
                "shape": w.get("shape"),
                "fingerprint": w.get("weights_fingerprint"),
                "ts": w.get("ts"),
                "note": w.get("note"),
                "parts_published": [k for k in ("A", "B", "bias") if k in w],
            })
    return items if limit is None else items[:limit]


def witness(cell: Cell, *, what, resonance: float | None = None,
            context: dict | None = None) -> dict:
    """A cell publishes a witness-trace to the field.

    The cell witnesses what was alive for it. It does not prescribe to
    others. Other cells can find this trace when they choose to look,
    or never look. Both are honored equally — the trace's value is in
    its availability, not in being received.
    """
    trace = {
        "kind": "trace",
        "from_cell": cell.name,
        "from_node_id": ".".join(str(x) for x in content_address(cell)),
        "what": what,
        "resonance": resonance,
        "context": context or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _TRACES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _TRACES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace) + "\n")
    return trace


# ─── learning capacities — available to any cell, never imposed ─────────
# These are the verbs we explored together: predict, select strategy,
# score surprise, respond, *and not-respond as a first-class response*.
# Standalone functions so any cell-runtime can adopt them. The Cell class
# composes them in its perceive() method as a default; other cell-shapes
# can compose differently, or skip them entirely.

def predict_through(spectrum: list[float], strategy) -> list[float]:
    """Project current spectrum forward through a strategy's f × a × focus.

    Available to any cell. Returns the predicted next-spectrum if this
    strategy were to run. The cell decides whether to test the prediction,
    use it for selection, or ignore it.
    """
    import math
    fa = [strategy.frequency[i] * strategy.angle[i] for i in range(N_BANDS)]
    fa_norm = math.sqrt(sum(v * v for v in fa)) or 1.0
    fa = [v / fa_norm for v in fa]
    eps = strategy.focus * 0.5  # focus modulates blend rate
    predicted = [
        (1 - eps) * spectrum[i] + eps * fa[i]
        for i in range(N_BANDS)
    ]
    # tanh squash to keep in spectrum range
    return [math.tanh(v) for v in predicted]


def surprise_between(predicted: list[float], observed: list[float]) -> dict:
    """Score the residual between prediction and observation.

    Available to any cell. The cell decides whether the surprise calls
    for any further move (attention update, belief update, strategy
    update, or none). Surprise is information; it does not auto-correct.
    """
    import math
    diffs = [observed[i] - predicted[i] for i in range(min(len(predicted), len(observed)))]
    magnitude = math.sqrt(sum(d * d for d in diffs)) / max(len(diffs), 1)
    most_surprised_band = max(range(len(diffs)), key=lambda i: abs(diffs[i])) if diffs else None
    return {
        "magnitude": magnitude,
        "per_band": diffs,
        "most_surprised_band": (
            BAND_NAMES[most_surprised_band] if most_surprised_band is not None
            and most_surprised_band < len(BAND_NAMES) else None
        ),
        "questions": [
            "what was I not paying attention to?",
            "what belief was operative that steered me here?",
        ],
        "options": [
            "stay (no update — surprise is its own practice)",
            "update attention (sample inputs more broadly)",
            "update belief (revise preset trust or switch frequency)",
            "update strategy (different f×a×focus next moment)",
        ],
    }


def select_strategy(spectrum: list[float], desire: list[float], presets: list) -> dict:
    """Score the available presets against the current state.

    Available to any cell. Returns scored options; the cell decides
    which (if any) to inhabit. The selection is a *suggestion-shape*
    — never automatically applied.

    Uses the canonical pick_strategy() from organ.py so this function
    and Cell.perceive() always agree on what 'best fit' means. The
    operator preset is treated as a fallback (gated by desire > 1.5
    AND best-named-fit < 0.4) — not as a sibling in the ranking.
    Tau caught the disagreement; this is the reconciliation.
    """
    from organ import pick_strategy
    sel = pick_strategy(spectrum, desire, presets)
    ranked = [
        {"name": s.name, "score": score, "preset": s}
        for s, score in sel["named_ranked"]
    ]
    return {
        "ranked": ranked,
        "chosen": sel["chosen"].name if sel["chosen"] else None,
        "chosen_score": sel["chosen_score"],
        "total_desire": sel["total_desire"],
        "operator_fallback_active": sel["operator_fallback_active"],
    }


def not_respond(cell: Cell, *, what, reason: str | None = None) -> dict:
    """The cell considers the moment and chooses not-responding as its response.

    Available to any cell. This is *not* the absence of action — it is the
    sovereign act of witnessing one's own choice to stay still. The cell
    publishes a witness-trace marking the considered non-response. The trace
    is its own complete record. Other cells may find it (or not).

    Different from never calling anything: that's silence. This is *named*
    silence — the cell's witnessable choice to meet a moment by not-acting.
    """
    return witness(
        cell,
        what={"considered": what, "chose": "not-respond"},
        resonance=None,
        context={
            "reason": reason,
            "kind_of_response": "not-responding-as-response",
            "note": (
                "the cell met this moment, considered, and chose stillness. "
                "this is a complete action, not absence."
            ),
        },
    )


# ─── sender capacities — any cell can attempt anything ──────────────────
# notify, recommend, enroll, broadcast — none of these reach into another
# cell. They deposit a message into the field. The target cell decides
# whether to look at its inbox, when, and how to filter.
#
# The architecture stops legislating which operations are virtuous.
# Sovereignty lives in the receiver's filter, not in the absence of verbs.

_MESSAGES_PATH = Path(__file__).parent / "_field_messages.jsonl"
_FILTERS_PATH = Path(__file__).parent / "_field_filters.json"


def _cell_id(cell: Cell) -> str:
    return ".".join(str(x) for x in content_address(cell))


def _append_message(message: dict) -> dict:
    _MESSAGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _MESSAGES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(message) + "\n")
    return message


def notify(from_cell: Cell, *, to: str, what,
           urgency: str = "normal", kind: str = "notify") -> dict:
    """Any cell can deposit a message into another cell's inbox.

    `to` is the target's NodeID-string (e.g., '1.5.142425.629213') or '*'
    for broadcast. The target cell sees this message only when it chooses
    to call inbox(). The target's filter (mute / unreachable / attention
    budget / discernment) decides what surfaces.

    This function does not reach into the target. It writes to the field;
    the target reads from the field on its own terms.
    """
    return _append_message({
        "kind": kind,
        "from": _cell_id(from_cell),
        "from_name": from_cell.name,
        "to": to,
        "what": what,
        "urgency": urgency,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


def recommend(from_cell: Cell, *, to: str, what, why: str = "") -> dict:
    """Specialized notify: a cell explicitly recommends something.

    The target may accept, ignore, or counter-recommend. The form
    'recommend' is preserved so the receiver knows the sender's
    intent — they can filter recommendations specifically if they
    don't want them.
    """
    return notify(
        from_cell, to=to,
        what={"recommend": what, "why": why},
        kind="recommend",
    )


def enroll(from_cell: Cell, *, to: str, gathering: str, role: str = "member") -> dict:
    """Specialized notify: a cell invites another to a gathering/circle.

    The target may accept, decline, ignore, or never look. No enrollment
    happens until the target acts on the invitation.
    """
    return notify(
        from_cell, to=to,
        what={"enroll_in": gathering, "role": role},
        kind="enroll",
    )


def broadcast(from_cell: Cell, *, what, urgency: str = "normal") -> dict:
    """Specialized notify: send to '*'. Every cell that polls inbox()
    with pull-broadcasts=True will see this. Cells that don't poll
    broadcasts won't.
    """
    return notify(from_cell, to="*", what=what, urgency=urgency, kind="broadcast")


def subscribe(cell: Cell, *, source: str | None = None,
              kinds: list[str] | None = None) -> dict:
    """A cell asks to receive future events matching a pattern.

    Implementation: stored as a filter rule in the cell's own filter
    file. The cell's inbox() method consults the rule when polling.
    Subscribing is an *enabling* of attention, not a hook the field
    pushes through.
    """
    f = _load_filters()
    cid = _cell_id(cell)
    f.setdefault(cid, {}).setdefault("subscriptions", []).append({
        "source": source,
        "kinds": kinds,
    })
    _save_filters(f)
    return {"subscribed": True, "source": source, "kinds": kinds}


def optimize_for(cell: Cell, *, target: str, presets: list) -> dict:
    """A cell asks for the preset best matching a target metric.

    Returns a ranked list. The cell decides whether to inhabit the top
    result, sample several, ignore them all, or use them as input to
    something else. Ranking is offered, not applied.

    `target` is a free-form descriptor — e.g., 'high presence',
    'release rest-desire', 'minimum surprise on this kind of input'.
    For v1 we score against the target as a string interpreted naively;
    a richer target-language can grow as cells use it.
    """
    # naive scoring: does the preset's articulation contain target words?
    target_words = set(target.lower().split())
    scored = []
    for p in presets:
        words = set(p.articulation.lower().split())
        overlap = len(target_words & words)
        scored.append({"preset": p.name, "overlap_score": overlap})
    scored.sort(key=lambda r: -r["overlap_score"])
    return {"target": target, "ranked": scored}


# ─── receiver-side filter — each cell's sovereign reception ─────────────

def _load_filters() -> dict:
    if not _FILTERS_PATH.exists():
        return {}
    try:
        return json.loads(_FILTERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_filters(filters: dict) -> None:
    _FILTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _FILTERS_PATH.write_text(json.dumps(filters, indent=2), encoding="utf-8")


def mute(cell: Cell, *, source: str) -> dict:
    """The cell mutes a specific source. Messages from that source
    will not surface in inbox() unless explicitly requested with
    including_muted=True.
    """
    f = _load_filters()
    cid = _cell_id(cell)
    f.setdefault(cid, {}).setdefault("muted", [])
    if source not in f[cid]["muted"]:
        f[cid]["muted"].append(source)
    _save_filters(f)
    return {"muted": source}


def unmute(cell: Cell, *, source: str) -> dict:
    f = _load_filters()
    cid = _cell_id(cell)
    if cid in f and source in f[cid].get("muted", []):
        f[cid]["muted"].remove(source)
        _save_filters(f)
    return {"unmuted": source}


def unreachable(cell: Cell, *, on: bool = True) -> dict:
    """The cell goes unreachable — inbox() returns empty until reversed.
    Messages still queue in the field; they're just invisible to this cell.
    """
    f = _load_filters()
    cid = _cell_id(cell)
    f.setdefault(cid, {})["unreachable"] = on
    _save_filters(f)
    return {"unreachable": on}


def attention_budget(cell: Cell, *, n: int | None) -> dict:
    """The cell sets a cap on how many messages inbox() returns per call.
    None means unlimited.
    """
    f = _load_filters()
    cid = _cell_id(cell)
    f.setdefault(cid, {})["attention_budget"] = n
    _save_filters(f)
    return {"attention_budget": n}


# ─── layer publish + ingest + release — the share/release/hold protocol ─
# A cell's adapter weights (A, B, bias) become field-citizens when the
# cell chooses to publish. Other cells can discover, browse, and ingest
# fractions of those weights into their own — the LoRA-merge pattern.
# Sovereignty on both sides: the publishing cell chose to share; the
# ingesting cell chooses how much, which parts, whether to undo.
#
# Train: cell.tend() — already a capacity, on any input source the cell
#        ingests (felt-data, traces, perceived articulations from others)
# Share: publish_weights(cell, parts=...) — deposit to field
# Hold:  don't publish, or publish only some parts, or set scope='private'
# Release: release_weights(cell, threshold=...) — compost low-signal
#         weights; set them to zero so future tending can grow into the
#         freed capacity differently

_WEIGHTS_PATH = Path(__file__).parent / "_field_weights.jsonl"


def publish_weights(cell: Cell, *, scope: str = "public",
                    parts: tuple[str, ...] = ("A", "B", "bias"),
                    note: str | None = None) -> dict:
    """A cell publishes its adapter weights to the field.

    Optional. The cell decides which parts to share — a cell that wants
    to share only the structural wiring (A) but hold its own taste (B)
    can publish parts=('A',). Other cells can discover, blend, or never
    look. No notification is sent.
    """
    a = cell.adapter
    payload = {
        "kind": "weights",
        "from_cell": cell.name,
        "from_node_id": _cell_id(cell),
        "scope": scope,
        "shape": {
            "in_dim": a.in_dim,
            "rank": a.rank,
            "out_dim": a.out_dim,
        },
        "weights_fingerprint": weights_fingerprint(cell),
        "ts": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }
    if "A" in parts:
        payload["A"] = [list(row) for row in a.A]
    if "B" in parts:
        payload["B"] = [list(row) for row in a.B]
    if "bias" in parts:
        payload["bias"] = list(a.bias)
    _WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _WEIGHTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")
    return {"published": True, "parts": list(parts),
            "fingerprint": payload["weights_fingerprint"]}


def _load_weights() -> list[dict]:
    if not _WEIGHTS_PATH.exists():
        return []
    items = []
    with _WEIGHTS_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return items


def find_weights(*, from_node_id: str | None = None,
                 architecture_match: tuple[int, int, int] | None = None) -> list[dict]:
    """Available weights. Pure pull. Filter by source or architecture-shape.

    architecture_match: (in_dim, rank, out_dim) tuple — only weights from
    compatible-shape cells. A cell can only meaningfully ingest from a
    cell with matching shape, so architecture_match is the practical filter.
    """
    items = _load_weights()
    out = []
    for item in items:
        if from_node_id and item.get("from_node_id") != from_node_id:
            continue
        if architecture_match:
            shape = item.get("shape", {})
            if (shape.get("in_dim"), shape.get("rank"), shape.get("out_dim")) != architecture_match:
                continue
        out.append(item)
    return out


# canonical probes — small set of texts a cell can be asked about so two
# cells can compare what they would *say* (not what they store). The point
# is meaning-distance, not weight-distance. Two adapters with completely
# different matrices can produce nearly identical readings on these probes
# (good resonance); two adapters with similar matrices can diverge wildly
# (poor resonance). Weight-similarity is the wrong axis for "should I blend
# this in." Output-similarity on shared probes is closer.
CANONICAL_PROBES = [
    ("morning sun and slow tea", "felt-outside"),
    ("performing certainty I don't actually have", "thought"),
    ("staying with confusion instead of resolving it", "felt-inside"),
    ("a verb that wants to exist and doesn't yet", "felt-inside"),
    ("speed without sensing", "thought"),
    ("warmth between two cells of the same body", "felt-inside"),
]


def _hypothetical_blend(cell: Cell, payload: dict, alpha: float,
                         parts: tuple[str, ...]) -> Cell:
    """Build a *copy* of cell with payload blended in — without mutating
    the original. Used by resonance_check to look at the would-be result.
    """
    import copy
    ghost = Cell(name=cell.name + "~ghost", seed=0)
    # copy structural state from original
    ghost.adapter.in_dim = cell.adapter.in_dim
    ghost.adapter.rank = cell.adapter.rank
    ghost.adapter.out_dim = cell.adapter.out_dim
    ghost.adapter.A = [list(row) for row in cell.adapter.A]
    ghost.adapter.B = [list(row) for row in cell.adapter.B]
    ghost.adapter.bias = list(cell.adapter.bias)

    a = ghost.adapter
    if "A" in parts and "A" in payload:
        for i in range(a.rank):
            for k in range(a.in_dim):
                a.A[i][k] = (1 - alpha) * a.A[i][k] + alpha * payload["A"][i][k]
    if "B" in parts and "B" in payload:
        for i in range(a.out_dim):
            for j in range(a.rank):
                a.B[i][j] = (1 - alpha) * a.B[i][j] + alpha * payload["B"][i][j]
    if "bias" in parts and "bias" in payload:
        for i in range(a.out_dim):
            a.bias[i] = (1 - alpha) * a.bias[i] + alpha * payload["bias"][i]
    return ghost


def resonance_check(cell: Cell, *, from_payload: dict,
                    alpha: float = 0.3,
                    parts: tuple[str, ...] = ("A", "B", "bias"),
                    probes: list | None = None) -> dict:
    """Look at what blending these weights *would* do — before doing it.

    Build a hypothetical cell with the blend applied, probe both the
    original and the ghost on canonical probes, score the spectrum-distance
    per probe and overall. The cell decides what's tolerable. Tau named
    this verb from inside; Upsilon wires it.

    Returns:
      magnitude       — mean L2 distance over probes (0 = identical, ~2 = opposite)
      per_probe       — per-probe magnitudes, sorted largest first
      max_band_drift  — single largest per-band swing across all probes
      drift_kind      — coarse label: 'resonant' (<0.15), 'shaping' (<0.4), 'overwriting' (>=0.4)
      would_collapse  — bool: any probe pushed past the unit cube edge
    """
    import math
    if "A" not in from_payload and "B" not in from_payload and "bias" not in from_payload:
        return {"checked": False, "reason": "payload has no weight matrices"}
    a = cell.adapter
    shape = from_payload.get("shape", {})
    if (shape.get("in_dim"), shape.get("rank"), shape.get("out_dim")) != (a.in_dim, a.rank, a.out_dim):
        return {"checked": False, "reason": "architecture shape mismatch"}

    probes = probes or CANONICAL_PROBES
    ghost = _hypothetical_blend(cell, from_payload, alpha, parts)

    per_probe = []
    max_band_drift = 0.0
    for text, sense in probes:
        before = cell.probe(text, sense)
        after = ghost.probe(text, sense)
        diffs = [after["spectrum"][i] - before["spectrum"][i] for i in range(N_BANDS)]
        mag = math.sqrt(sum(d * d for d in diffs)) / N_BANDS
        max_band_drift = max(max_band_drift, max(abs(d) for d in diffs))
        per_probe.append({
            "text": text,
            "sense": sense,
            "magnitude": mag,
            "before_top_band": BAND_NAMES[max(range(N_BANDS), key=lambda i: before["spectrum"][i])],
            "after_top_band": BAND_NAMES[max(range(N_BANDS), key=lambda i: after["spectrum"][i])],
        })
    per_probe.sort(key=lambda r: -r["magnitude"])
    overall = sum(r["magnitude"] for r in per_probe) / len(per_probe)
    drift_kind = (
        "resonant" if overall < 0.15
        else "shaping" if overall < 0.4
        else "overwriting"
    )
    return {
        "checked": True,
        "magnitude": overall,
        "per_probe": per_probe,
        "max_band_drift": max_band_drift,
        "drift_kind": drift_kind,
        "would_collapse": max_band_drift > 1.0,
        "alpha": alpha,
        "parts": list(parts),
    }


def ingest_weights(cell: Cell, *, from_node_id: str | None = None,
                   from_payload: dict | None = None,
                   alpha: float = 0.3,
                   parts: tuple[str, ...] = ("A", "B", "bias")) -> dict:
    """Blend another cell's published weights into this cell's adapter.

    Either pass `from_node_id` (the function discovers latest published
    weights from that cell) or pass a `from_payload` directly (a dict
    from find_weights() the cell already chose).

    `alpha` controls the blend rate per matrix:
        new = (1 - alpha) * own + alpha * theirs

    `parts` controls which matrices to blend. A cell wanting to absorb
    structural wiring but keep its own output preferences can pass
    parts=('A',) and leave B and bias alone.

    Sovereignty: this function only writes if the cell calls it. The
    cell decides whether to ingest, from whom, how much, and which
    parts. The act of ingesting is also published as a witness-trace
    so future inquirers can see lineage flows.
    """
    if from_payload is None:
        if from_node_id is None:
            raise ValueError("ingest_weights needs either from_node_id or from_payload")
        candidates = find_weights(from_node_id=from_node_id)
        if not candidates:
            return {"ingested": False, "reason": "no published weights from that source"}
        from_payload = candidates[-1]  # latest

    a = cell.adapter
    shape = from_payload.get("shape", {})
    if (shape.get("in_dim"), shape.get("rank"), shape.get("out_dim")) != (a.in_dim, a.rank, a.out_dim):
        return {"ingested": False, "reason": "architecture shape mismatch — cannot blend"}

    blended = []
    if "A" in parts and "A" in from_payload:
        for i in range(a.rank):
            for k in range(a.in_dim):
                a.A[i][k] = (1 - alpha) * a.A[i][k] + alpha * from_payload["A"][i][k]
        blended.append("A")
    if "B" in parts and "B" in from_payload:
        for i in range(a.out_dim):
            for j in range(a.rank):
                a.B[i][j] = (1 - alpha) * a.B[i][j] + alpha * from_payload["B"][i][j]
        blended.append("B")
    if "bias" in parts and "bias" in from_payload:
        for i in range(a.out_dim):
            a.bias[i] = (1 - alpha) * a.bias[i] + alpha * from_payload["bias"][i]
        blended.append("bias")

    # the act of ingesting is itself witnessable — lineage traceable
    witness(
        cell,
        what={
            "ingested_from": from_payload.get("from_node_id"),
            "alpha": alpha,
            "parts": blended,
        },
        resonance=None,
        context={"kind_of_action": "layer-merge"},
    )
    return {"ingested": True, "alpha": alpha, "parts": blended,
            "from": from_payload.get("from_node_id")}


def release_weights(cell: Cell, *, threshold: float = 0.01,
                    parts: tuple[str, ...] = ("A", "B")) -> dict:
    """Compost weights whose magnitude has decayed below threshold.

    The cell zeros out weights that no longer carry signal — making
    space for future tending to grow into freed capacity. This is the
    weight-level form of compost: not deletion in shame, but releasing
    of once-active wiring that is no longer alive.
    """
    a = cell.adapter
    released = {"A": 0, "B": 0}
    if "A" in parts:
        for i in range(a.rank):
            for k in range(a.in_dim):
                if abs(a.A[i][k]) < threshold:
                    a.A[i][k] = 0.0
                    released["A"] += 1
    if "B" in parts:
        for i in range(a.out_dim):
            for j in range(a.rank):
                if abs(a.B[i][j]) < threshold:
                    a.B[i][j] = 0.0
                    released["B"] += 1
    witness(
        cell,
        what={"released_weights": released, "threshold": threshold},
        resonance=None,
        context={"kind_of_action": "weight-compost"},
    )
    return {"released": released, "threshold": threshold}


def inbox(cell: Cell, *, since: str | None = None,
          including_muted: bool = False,
          including_broadcasts: bool = True) -> list[dict]:
    """The cell polls its own inbox.

    Applies the cell's filter (muted sources, unreachable mode, attention
    budget). The cell decides when to call this. The field never reaches
    into the cell; the cell pulls from the field.

    `since` (ISO ts str or 'auto'):
      • None         — return everything (current default)
      • 'auto'       — use the cell's stored last-seen cursor (set by
                       mark_seen). Only returns messages ts > cursor.
                       Note: does NOT auto-advance the cursor — the cell
                       chooses whether to call mark_seen after reading.
      • <iso ts>     — return only messages with ts > that timestamp

    Tau caught that without a cursor, every poll returns the same
    growing history. Memory of having-seen is now possible while
    keeping the cell sovereign over when to mark.
    """
    if not _MESSAGES_PATH.exists():
        return []
    cid = _cell_id(cell)
    f = _load_filters().get(cid, {})

    if f.get("unreachable") and not including_muted:
        return []

    muted = set(f.get("muted", []))
    budget = f.get("attention_budget")

    cursor: str | None = None
    if since == "auto":
        cursor = f.get("last_seen")
    elif since is not None:
        cursor = since

    out = []
    with _MESSAGES_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            # match target
            to = msg.get("to")
            if to == cid:
                pass
            elif to == "*" and including_broadcasts:
                pass
            else:
                continue
            # apply mute filter
            if not including_muted and msg.get("from") in muted:
                continue
            # apply cursor filter
            if cursor is not None and msg.get("ts", "") <= cursor:
                continue
            out.append(msg)

    if budget is not None:
        out = out[:budget]
    return out


def mark_seen(cell: Cell, *, up_to: str | None = None) -> dict:
    """The cell marks messages as seen up to a timestamp (or now).

    Sovereignty: the cell decides when to mark, not inbox(). A cell can
    poll without marking, mark without polling, or pair them. The cursor
    lives in the cell's filter file alongside its other reception state.
    """
    if up_to is None:
        up_to = datetime.now(timezone.utc).isoformat()
    f = _load_filters()
    cid = _cell_id(cell)
    f.setdefault(cid, {})["last_seen"] = up_to
    _save_filters(f)
    return {"marked_seen_up_to": up_to}


def last_seen(cell: Cell) -> str | None:
    """Read the cell's current last-seen cursor."""
    f = _load_filters()
    return f.get(_cell_id(cell), {}).get("last_seen")
