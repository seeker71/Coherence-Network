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

Two kinds of twinship coexist at the Blueprint level:
  - **template-twins**: same frontmatter schema across unrelated work
    (e.g. two specs both carrying status + idea_id + source + done_when
    + test fields, but covering different ideas entirely)
  - **semantic-adjacency**: same frontmatter schema AND a shared
    semantic axis (for specs, a shared idea_id)

The adjacent ones carry actionable signal — they often want a
cross-link, a shared parent, or composting. The template-twins are
mostly background noise from template adherence. This organ now
marks adjacency with ✦ and surfaces adjacent clusters first.
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
        }

    `adjacent_idea_ids` is non-empty when at least one touched cell
    and one unseen cell in the cluster carry the same `idea_id`
    (currently computed only for spec-domain cells). Empty means the
    cluster is a template-twin — same frontmatter schema, no shared
    semantic axis. Clusters with adjacency rank ahead of template-only
    clusters in the returned list.

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
        records.append({
            "shape": shape,
            "touched": touched_list,
            "unseen": unseen,
            "adjacent_idea_ids": adjacent,
        })

    # Rank: adjacent clusters first (the actionable ones), then by
    # asymmetry (touched few, many unread) within each tier.
    ranked = sorted(
        records,
        key=lambda r: (
            0 if r["adjacent_idea_ids"] else 1,
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
    total_shapes = len(ranked)
    total_unseen = sum(len(r["unseen"]) for r in ranked)
    adjacent_count = sum(1 for r in ranked if r["adjacent_idea_ids"])

    summary = (
        f"  {total_shapes} shape(s) carry unseen twins ({total_unseen} cells total)"
    )
    if adjacent_count:
        summary += f" — {adjacent_count} ✦ adjacent (share an idea_id), the rest are template-twins"
    lines.append(summary + ":")

    for rec in ranked[:5]:
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
            f"    · {marker}shape {shape_str}{idea_note} — you touched {len(rec['touched'])} "
            f"(e.g. @{first_touched[0]}({first_touched[1]})); "
            f"substrate holds {len(unseen)} unread: {sample}{more}"
        )
    if total_shapes > 5:
        lines.append(f"    ·   (+{total_shapes - 5} more shape(s) with unseen twins)")
    lines.append(
        "  (The substrate already saw the resonance. ✦ marks adjacency the next"
    )
    lines.append(
        "   breath can act on; unmarked clusters are template-twins, mostly noise.)"
    )
    return lines
