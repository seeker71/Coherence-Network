#!/usr/bin/env python3
"""Run any Form practice and record substrate cells plus witness ledger."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.substrate import (  # noqa: E402
    BID_presence,
    BID_task,
    form_evaluate_text,
    form_execute_text,
    form_serialize_node_id,
    ingest_witness_event,
    lattice_stats,
    make_cell,
)
from app.services.substrate.kernel import NodeID  # noqa: E402
from app.services.substrate.markdown_frontend import (  # noqa: E402
    body_to_access_recipe,
    frontmatter_to_blueprint,
    frontmatter_to_structured_ctor,
)
from app.services.unified_db import ensure_schema, session as session_scope  # noqa: E402


DEFAULT_TIMESTAMP = "2026-05-18T08:00:00+08:00"
DEFAULT_SEPARATOR = " -> "


def load_form_source(path: Path, marker: str | None = None) -> str:
    """Read a Form file, using a named marker when present."""
    src = path.read_text()
    if marker is not None:
        pattern = rf"# >>> BEGIN {re.escape(marker)}\n(.*?)\n# >>> END {re.escape(marker)}"
        match = re.search(pattern, src, re.DOTALL)
        if match is None:
            raise ValueError(f"practice marker {marker!r} not found in {path}")
        return match.group(1).strip()

    match = re.search(r"# >>> BEGIN ([^\n]+)\n(.*?)\n# >>> END \1", src, re.DOTALL)
    if match is not None:
        return match.group(2).strip()
    return src.strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _node(value: NodeID | None) -> str | None:
    return form_serialize_node_id(value) if value is not None else None


def _source_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _make_structured_cell(
    session: Any,
    *,
    domain: str,
    name: str,
    domain_blueprint: NodeID,
    frontmatter: dict[str, Any],
    body: str,
    source_path: str,
) -> dict[str, Any]:
    blueprint = frontmatter_to_blueprint(session, frontmatter, domain_blueprint)
    ctor = frontmatter_to_structured_ctor(session, frontmatter)
    access = body_to_access_recipe(session, body, blueprint)
    cell = make_cell(
        session,
        name=name,
        domain=domain,
        blueprint=blueprint,
        access=access,
        ctor=ctor,
        source_path=source_path,
    )
    return {
        "domain": domain,
        "name": name,
        "cell_id": cell.cell_id,
        "blueprint": blueprint,
        "ctor": ctor,
        "access": access,
        "source_path": source_path,
    }


def _serializable_cell(cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": cell["domain"],
        "name": cell["name"],
        "cell_id": cell["cell_id"],
        "blueprint": _node(cell.get("blueprint")),
        "ctor": _node(cell.get("ctor")),
        "access": _node(cell.get("access")),
        "source_path": cell.get("source_path"),
    }


def _ledger_entry(practice: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "recorded_at": _now_iso(),
        "practice": practice,
        "kind": kind,
        **payload,
    }


def execute_form_practice(
    session: Any,
    *,
    form_path: Path,
    practice: str,
    presence_name: str,
    task_name: str,
    timestamp: str = DEFAULT_TIMESTAMP,
    source_url: str | None = None,
    ledger_path: Path | None = None,
    marker: str | None = None,
    separator: str = DEFAULT_SEPARATOR,
) -> dict[str, Any]:
    """Run Form, create practice cells, and optionally write a JSONL ledger."""
    form_source = load_form_source(form_path, marker=marker)
    practice_recipe = form_evaluate_text(session, form_source).value
    practice_value = form_execute_text(session, form_source)
    if not isinstance(practice_value, str):
        raise TypeError("Form practice must return a string stream")

    rel_source_path = _source_path(form_path)
    source_context = {"source_url": source_url} if source_url else {}
    practice_slug = practice.replace("_", "-")

    presence = _make_structured_cell(
        session,
        domain="presence",
        name=presence_name,
        domain_blueprint=BID_presence(),
        frontmatter={
            "id": presence_name,
            "kind": "AGENT",
            "role": "embodied-practice-cell",
            "mode": "form-runtime",
            **source_context,
            "practice_recipe": _node(practice_recipe),
        },
        body=f"A practice cell that runs {practice_slug} through Form.",
        source_path=rel_source_path,
    )
    task = _make_structured_cell(
        session,
        domain="task",
        name=task_name,
        domain_blueprint=BID_task(),
        frontmatter={
            "idea_id": practice_slug,
            "status": "completed",
            "context": {
                "form": rel_source_path,
                "recipe": _node(practice_recipe),
                **source_context,
                "stream": practice_value,
            },
        },
        body=practice_value,
        source_path=rel_source_path,
    )

    witness_cells: list[dict[str, Any]] = []
    actions = [part for part in practice_value.split(separator) if part]
    for index, action in enumerate(actions, start=1):
        witness_cell, blueprint, ctor = ingest_witness_event(
            session,
            presence_name,
            action,
            f"substrate-ledger://{practice_slug}/{index}",
            f"{timestamp}#{index}",
        )
        witness_cells.append(
            {
                "domain": "witness",
                "name": witness_cell.name,
                "cell_id": witness_cell.cell_id,
                "blueprint": blueprint,
                "ctor": ctor,
                "access": witness_cell.access,
                "source_path": None,
            }
        )

    result = {
        "form_source": form_source,
        "form_value": practice_value,
        "practice": practice,
        "practice_recipe": practice_recipe,
        "named_cells": {
            "presence": presence,
            "task": task,
            "witnesses": witness_cells,
        },
        "stats": lattice_stats(session),
    }

    if ledger_path is not None:
        entries = [
            _ledger_entry(
                practice,
                "form_recipe",
                {
                    "phase": "water",
                    "recipe": _node(practice_recipe),
                    **source_context,
                    "form_value": practice_value,
                },
            ),
            _ledger_entry(practice, "cell", {"phase": "gas", "cell": _serializable_cell(presence)}),
            _ledger_entry(practice, "cell", {"phase": "gas", "cell": _serializable_cell(task)}),
        ]
        entries.extend(
            _ledger_entry(practice, "witness", {"phase": "gas", "cell": _serializable_cell(witness)})
            for witness in witness_cells
        )
        entries.append(
            _ledger_entry(
                practice,
                "completion",
                {
                    "phase": "whole",
                    "practice_recipe": _node(practice_recipe),
                    "named_cell_count": 2 + len(witness_cells),
                },
            )
        )
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(
            "\n".join(json.dumps(entry, sort_keys=True) for entry in entries) + "\n"
        )

    return result


def serializable_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "form_source": result["form_source"],
        "form_value": result["form_value"],
        "practice": result["practice"],
        "practice_recipe": _node(result["practice_recipe"]),
        "named_cells": {
            "presence": _serializable_cell(result["named_cells"]["presence"]),
            "task": _serializable_cell(result["named_cells"]["task"]),
            "witnesses": [
                _serializable_cell(witness)
                for witness in result["named_cells"]["witnesses"]
            ],
        },
        "stats": result["stats"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a Form practice.")
    parser.add_argument("--form", type=Path, required=True)
    parser.add_argument("--practice", required=True)
    parser.add_argument("--presence", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--marker")
    parser.add_argument("--separator", default=DEFAULT_SEPARATOR)
    parser.add_argument("--source-url")
    parser.add_argument("--timestamp", default=DEFAULT_TIMESTAMP)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ensure_schema()
    with session_scope() as session:
        result = execute_form_practice(
            session,
            form_path=args.form,
            practice=args.practice,
            presence_name=args.presence,
            task_name=args.task,
            timestamp=args.timestamp,
            source_url=args.source_url,
            ledger_path=args.ledger,
            marker=args.marker,
            separator=args.separator,
        )

    out = serializable_result(result)
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print("Form practice executed")
        print(f"  form: {args.form}")
        print(f"  practice: {args.practice}")
        print(f"  recipe: {out['practice_recipe']}")
        print(f"  value: {out['form_value']}")
        print(f"  presence: {out['named_cells']['presence']}")
        print(f"  task: {out['named_cells']['task']}")
        print(f"  witness cells: {len(out['named_cells']['witnesses'])}")
        if args.ledger:
            print(f"  ledger: {args.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
