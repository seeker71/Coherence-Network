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
"""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, List, Tuple


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
        }

    Returns (0, []) when no substrate-ingested paths were touched, or
    when no Blueprint has an unread twin. Shapes are sorted so the
    biggest asymmetry comes first (you touched few; many remain unread).

    Caller is responsible for formatting the records for display.
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

    ranked = sorted(
        (
            {
                "shape": shape,
                "touched": shape_to_touched[shape],
                "unseen": shape_to_unseen[shape],
            }
            for shape in shape_to_touched
            if shape_to_unseen[shape]
        ),
        key=lambda r: (len(r["touched"]), -len(r["unseen"])),
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
    lines.append(
        f"  {total_shapes} shape(s) carry unseen twins ({total_unseen} cells total):"
    )
    for rec in ranked[:5]:
        shape_str = "@" + ".".join(str(x) for x in rec["shape"])
        first_touched = rec["touched"][0]
        unseen = rec["unseen"]
        sample = ", ".join(f"@{d}({n})" for d, n in unseen[:3])
        more = f", +{len(unseen) - 3} more" if len(unseen) > 3 else ""
        lines.append(
            f"    · shape {shape_str} — you touched {len(rec['touched'])} "
            f"(e.g. @{first_touched[0]}({first_touched[1]})); "
            f"substrate holds {len(unseen)} unread: {sample}{more}"
        )
    if total_shapes > 5:
        lines.append(f"    · (+{total_shapes - 5} more shape(s) with unseen twins)")
    lines.append(
        "  (The substrate already saw the resonance. This is the shoulder-tap"
    )
    lines.append(
        "   so the next breath can choose whether to read across.)"
    )
    return lines
