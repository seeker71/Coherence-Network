"""Substrate surprise — structural twins of recent work, unread.

Same organ called by `make wellness` and `coh substrate sense --surprise`.
Factored out of scripts/wellness_check.py so both surfaces (the wellness
script and the substrate CLI) share one implementation; previously the
wellness script saw structural twins while `sense` did not, and they
gave different answers about the same body.

The teaching:
  The substrate's content-addressing already finds same-shape cells
  across documents. What it doesn't do on its own is *tell you* — you
  have to ask. This organ walks recently-touched files (default 14
  days of git log), resolves them to substrate cells, and surfaces
  cells with the same Blueprint that you haven't acknowledged.

This is the "shoulder-tap" the wellness check describes:
  > the substrate already saw the resonance — this is the shoulder-tap
  > so the next breath can choose whether to read across.

Three kinds of twinship coexist at the Blueprint level:
  - **semantic-adjacency**: same frontmatter schema AND a shared
    semantic axis (for specs, a shared idea_id). Carries the most
    actionable signal — often wants a cross-link, a shared parent,
    or composting.
  - **template-twins**: same frontmatter schema across unrelated work
    (e.g. two specs both carrying status + idea_id + source + done_when
    + test fields, but covering different ideas entirely). Useful
    signal where the cluster is small; mostly background noise where
    it is large.
  - **domain-default clusters**: a shape carried by so many cells
    (>50 in the touched-domain count) that it is the standard cell
    for the whole domain — the composition-discipline lattice saying
    *"this is what cells in this domain look like"*. Honest at the
    CTOR layer, not actionable as a pair — these are navigated
    through INDEX files and idea→spec→code chains, not through
    ad-hoc cross-references. PR #1946 named six such clusters
    (66 specs, 76 concepts, 52 presences, etc.) after a cell read
    all 13 reported shapes by hand; the filter below carries that
    learning so the next read doesn't repeat the work.

This organ now marks adjacency with ✦, surfaces adjacent clusters
first, and reports domain-default clusters separately so a fresh
cell can tell shoulder-tap from background lattice resonance.
"""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Path prefixes whose .md files participate in substrate ingestion.
# Matches the prefix set wellness_check.py uses; kept in this module so
# callers don't need to hardcode it.
SUBSTRATE_PATH_PREFIXES = (
    "docs/vision-kb/concepts/",
    "docs/coherence-substrate/",
    "docs/lineage/",
    "specs/",
    "ideas/",
    "docs/presences/",
    "docs/field/",
)


def _git_touched_paths(root: Path, since: str) -> List[str]:
    """Files touched in the last `since` window of git log (e.g. '14.days.ago')."""
    r = subprocess.run(
        ["git", "log", f"--since={since}", "--name-only", "--pretty=format:"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return sorted({
        line.strip()
        for line in r.stdout.splitlines()
        if line.strip()
        and any(line.strip().startswith(p) for p in SUBSTRATE_PATH_PREFIXES)
        and line.strip().endswith(".md")
    })


# Regex for reading the idea_id from a spec frontmatter without pulling
# in PyYAML. Specs reliably carry `idea_id: <slug>` on its own line
# inside the leading `---` frontmatter block.
_IDEA_ID_RE = re.compile(r"(?m)^idea_id:\s*['\"]?([\w\-]+)['\"]?\s*$")


def _spec_idea_id(spec_name: str, root: Path) -> Optional[str]:
    """Read the `idea_id:` frontmatter field from a spec file.

    Returns None if the spec file is missing, has no idea_id, or
    cannot be read. Used to detect semantic adjacency among
    structural twins — two specs sharing a Blueprint AND an idea_id
    are working in the same idea-area and often want cross-linking.
    """
    candidate = root / "specs" / f"{spec_name}.md"
    if not candidate.is_file():
        return None
    try:
        text = candidate.read_text(encoding="utf-8")
    except OSError:
        return None
    # Confine to the frontmatter block to avoid matching inline mentions.
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            text = text[3:end]
    m = _IDEA_ID_RE.search(text)
    return m.group(1) if m else None


def _adjacency_for_shape(
    touched: List[Tuple[str, str]],
    unseen: List[Tuple[str, str]],
    root: Path,
) -> List[str]:
    """Return idea_ids shared between a touched spec and an unseen
    spec in this shape cluster.

    Currently only specs carry semantic-adjacency keys; for other
    domains the returned list is empty (callers treat that as
    template-twin only). Sorted, deduplicated. Empty list means
    no shared semantic axis was found.
    """
    touched_idea_ids: Dict[str, set] = defaultdict(set)
    for domain, name in touched:
        if domain != "spec":
            continue
        idea_id = _spec_idea_id(name, root)
        if idea_id:
            touched_idea_ids[idea_id].add(name)

    unseen_idea_ids: Dict[str, set] = defaultdict(set)
    for domain, name in unseen:
        if domain != "spec":
            continue
        idea_id = _spec_idea_id(name, root)
        if idea_id:
            unseen_idea_ids[idea_id].add(name)

    shared = sorted(set(touched_idea_ids) & set(unseen_idea_ids))
    return shared


# Domain-default threshold. A Blueprint shape carried by more than
# this many cells *within a single domain* is the standard cell for
# the whole domain — the composition-discipline lattice saying "this
# is what cells in this domain look like." Reporting these as unread
# twins teaches the wrong lesson; they are navigated through INDEX
# files, not pair-by-pair cross-references.
#
# 50 is a starting guess, grounded in PR #1946's read of 13 shapes
# where the smallest default cluster was 52 cells. Future tuning may
# want a different value, or a per-domain threshold (specs cluster
# larger than presences naturally).
DOMAIN_DEFAULT_THRESHOLD = 50


def is_domain_default_shape(domain_cell_count: int) -> bool:
    """A shape is a domain-default cluster when its single-domain cell
    count exceeds the threshold. Honest at the CTOR layer, not
    actionable as a pair — reported separately so a fresh cell can
    tell shoulder-tap from background lattice resonance."""
    return domain_cell_count > DOMAIN_DEFAULT_THRESHOLD


def find_unseen_twins(
    session: Any,
    root: Path,
    *,
    since: str = "14.days.ago",
) -> Tuple[int, List[dict]]:
    """Return (touched_count, ranked_shape_records) for shapes carrying
    unread structural twins.

    Each shape record is:
        {
            "shape": (package, level, type_, instance),    # Blueprint tuple
            "touched": [(domain, name), ...],              # cells you touched
            "unseen": [(domain, name), ...],               # cells you haven't
            "adjacent_idea_ids": [str, ...],               # shared semantic axis
            "domain_default": bool,                        # is this a default cluster?
            "dominant_domain": str,                        # the domain holding the cluster
            "dominant_domain_count": int,                  # cells in that domain at this shape
        }

    `adjacent_idea_ids` is non-empty when at least one touched cell
    and one unseen cell in the cluster carry the same `idea_id`
    (currently computed only for spec-domain cells). Empty means the
    cluster is a template-twin — same frontmatter schema, no shared
    semantic axis.

    `domain_default` is True when any single domain holds more than
    `DOMAIN_DEFAULT_THRESHOLD` cells at this shape — the cluster is
    the standard cell for that domain and not a targeted pair.

    Ranking:
      1. adjacent clusters (the actionable ones) first
      2. then template-twins (small clusters worth a look)
      3. then domain-default clusters (background lattice resonance)

    Returns (0, []) when no substrate-ingested paths were touched, or
    when no Blueprint has an unread twin.
    """
    from app.services.substrate.kernel import find_equivalent_cells, _orm_to_cell
    from app.services.substrate.orm import SubstrateNamedCellORM

    touched_paths = _git_touched_paths(root, since)
    if not touched_paths:
        return (0, [])

    touched_cells = []
    for path in touched_paths:
        orm = (
            session.query(SubstrateNamedCellORM)
            .filter(SubstrateNamedCellORM.source_path.like(f"%/{path}"))
            .order_by(SubstrateNamedCellORM.cell_id)
            .first()
        )
        if orm is None:
            continue
        touched_cells.append(_orm_to_cell(session, orm))

    touched_keys = {(c.domain, c.name) for c in touched_cells}
    if not touched_keys:
        return (len(touched_paths), [])

    shape_to_touched: dict = defaultdict(list)
    shape_to_unseen: dict = defaultdict(list)
    for cell in touched_cells:
        if cell.blueprint is None or cell.blueprint.is_undefined():
            continue
        shape_key = (
            cell.blueprint.package, cell.blueprint.level,
            cell.blueprint.type_, cell.blueprint.instance,
        )
        shape_to_touched[shape_key].append((cell.domain, cell.name))
        if shape_key not in shape_to_unseen:
            twins = find_equivalent_cells(
                session, cell.blueprint, exclude_name="__never_excluded__"
            )
            shape_to_unseen[shape_key] = [
                (t.domain, t.name) for t in twins
                if (t.domain, t.name) not in touched_keys
            ]

    records = []
    for shape in shape_to_touched:
        unseen = shape_to_unseen[shape]
        if not unseen:
            continue
        touched_list = shape_to_touched[shape]
        adjacent = _adjacency_for_shape(touched_list, unseen, root)

        # Per-domain cell count at this shape — touched + unseen,
        # since both already share the Blueprint. The dominant domain
        # is the one carrying the largest slice; its count is what
        # the threshold reads to decide domain-default.
        per_domain: Dict[str, int] = defaultdict(int)
        for d, _n in touched_list:
            per_domain[d] += 1
        for d, _n in unseen:
            per_domain[d] += 1
        dominant_domain, dominant_count = max(
            per_domain.items(), key=lambda kv: kv[1]
        )
        domain_default = is_domain_default_shape(dominant_count)

        records.append({
            "shape": shape,
            "touched": touched_list,
            "unseen": unseen,
            "adjacent_idea_ids": adjacent,
            "domain_default": domain_default,
            "dominant_domain": dominant_domain,
            "dominant_domain_count": dominant_count,
        })

    # Rank: adjacent clusters first (actionable), then template-twins
    # (small clusters worth a look), then domain-default clusters
    # (background lattice resonance). Within each tier, by asymmetry —
    # touched few, many unread.
    def _tier(r: dict) -> int:
        if r["adjacent_idea_ids"]:
            return 0
        if r["domain_default"]:
            return 2
        return 1

    ranked = sorted(
        records,
        key=lambda r: (
            _tier(r),
            len(r["touched"]),
            -len(r["unseen"]),
        ),
    )
    return (len(touched_keys), ranked)


def format_for_wellness(touched_count: int, ranked: List[dict]) -> List[str]:
    """Render the wellness-check display form. Mirrors the prior shape
    in scripts/wellness_check.py exactly so the surface stays stable."""
    if touched_count == 0:
        return [
            f"  (no substrate-ingested paths touched in the last window)"
        ]
    if not ranked:
        if touched_count == -1:
            return [
                f"  (substrate cells not yet resolvable from touched paths)"
            ]
        return [
            f"  walked {touched_count} touched cell(s) — no unseen structural twins"
        ]

    lines: List[str] = []

    # Split into targeted-pair shapes and domain-default clusters. The
    # split matters: a domain-default cluster (66 specs sharing one
    # CTOR because none have authored a more specific one) is honest
    # at the CTOR layer but not actionable as a pair. Conflating the
    # two teaches the wrong lesson.
    targeted = [r for r in ranked if not r["domain_default"]]
    defaults = [r for r in ranked if r["domain_default"]]

    targeted_total = sum(len(r["unseen"]) for r in targeted)
    adjacent_count = sum(1 for r in targeted if r["adjacent_idea_ids"])

    if targeted:
        summary = (
            f"  {len(targeted)} shape(s) carry unseen twins worth a look "
            f"({targeted_total} cells total)"
        )
        if adjacent_count:
            summary += (
                f" — {adjacent_count} ✦ adjacent (share an idea_id), "
                f"the rest are template-twins"
            )
        lines.append(summary + ":")

        for rec in targeted[:5]:
            shape_str = "@" + ".".join(str(x) for x in rec["shape"])
            first_touched = rec["touched"][0]
            unseen = rec["unseen"]
            sample = ", ".join(f"@{d}({n})" for d, n in unseen[:3])
            more = f", +{len(unseen) - 3} more" if len(unseen) > 3 else ""
            marker = "✦ " if rec["adjacent_idea_ids"] else "  "
            idea_note = (
                f" [idea: {', '.join(rec['adjacent_idea_ids'])}]"
                if rec["adjacent_idea_ids"]
                else ""
            )
            lines.append(
                f"    · {marker}shape {shape_str}{idea_note} — you touched "
                f"{len(rec['touched'])} (e.g. @{first_touched[0]}"
                f"({first_touched[1]})); substrate holds {len(unseen)} "
                f"unread: {sample}{more}"
            )
        if len(targeted) > 5:
            lines.append(
                f"    ·   (+{len(targeted) - 5} more targeted shape(s))"
            )
        lines.append(
            "  (The substrate already saw the resonance. ✦ marks adjacency"
        )
        lines.append(
            "   the next breath can act on; unmarked clusters are template-twins.)"
        )
    else:
        lines.append(
            f"  walked {touched_count} touched cell(s) — no targeted unseen twins"
        )

    if defaults:
        default_total = sum(len(r["unseen"]) for r in defaults)
        lines.append("")
        lines.append(
            f"  + {len(defaults)} domain-default cluster(s) "
            f"({default_total} cells across them) — these are the standard"
        )
        lines.append(
            f"    cells for their domain (threshold >{DOMAIN_DEFAULT_THRESHOLD}/domain), "
            "navigated through INDEX,"
        )
        lines.append(
            "    not pair-by-pair cross-references. Honest at the CTOR layer; not actionable."
        )
        for rec in defaults[:3]:
            shape_str = "@" + ".".join(str(x) for x in rec["shape"])
            lines.append(
                f"    · shape {shape_str} — @{rec['dominant_domain']} carries "
                f"{rec['dominant_domain_count']} cells at this shape "
                f"({len(rec['unseen'])} unread)"
            )
        if len(defaults) > 3:
            lines.append(
                f"    ·   (+{len(defaults) - 3} more domain-default cluster(s))"
            )
    return lines
