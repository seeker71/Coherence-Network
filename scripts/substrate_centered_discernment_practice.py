#!/usr/bin/env python3
"""Execute the centered-discernment Form practice and record substrate witnesses."""
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


FORM_PATH = REPO_ROOT / "docs/coherence-substrate/centered-discernment-practice.form"
DEFAULT_LEDGER = REPO_ROOT / "docs/system_audit/substrate_centered_discernment_2026-05-18.jsonl"
DEFAULT_TIMESTAMP = "2026-05-18T08:00:00+08:00"
DEFAULT_SOURCE_URL = "https://youtu.be/KFaU6qR_iPg?si=LzzMcKcOY5mfThCf"


def load_form_source(path: Path = FORM_PATH) -> str:
    """Read the marked centered-discernment Form body from disk."""
    src = path.read_text()
    match = re.search(
        r"# >>> BEGIN centered-discernment-practice\n(.*?)\n# >>> END centered-discernment-practice",
        src,
        re.DOTALL,
    )
    if match is None:
        raise ValueError(f"practice markers not found in {path}")
    return match.group(1).strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _node(value: NodeID | None) -> str | None:
    return form_serialize_node_id(value) if value is not None else None


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


def _ledger_entry(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "recorded_at": _now_iso(),
        "practice": "centered_discernment",
        "kind": kind,
        **payload,
    }


def execute_practice(
    session: Any,
    *,
    timestamp: str = DEFAULT_TIMESTAMP,
    source_url: str = DEFAULT_SOURCE_URL,
    ledger_path: Path | None = None,
    form_path: Path = FORM_PATH,
) -> dict[str, Any]:
    """Run the Form practice, then record its cells and witness ledger."""
    form_source = load_form_source(form_path)
    practice_recipe = form_evaluate_text(session, form_source).value
    practice_value = form_execute_text(session, form_source)
    if not isinstance(practice_value, str):
        raise TypeError("centered discernment Form practice must return a string stream")

    life_agent = _make_structured_cell(
        session,
        domain="presence",
        name="life-sub-agent",
        domain_blueprint=BID_presence(),
        frontmatter={
            "id": "life-sub-agent",
            "kind": "AGENT",
            "role": "embodied-practice-cell",
            "mode": "form-runtime",
            "source_url": source_url,
            "practice_recipe": _node(practice_recipe),
        },
        body="A life sub-agent cell that runs centered discernment through Form.",
        source_path=str(form_path.relative_to(REPO_ROOT)),
    )
    practice_task = _make_structured_cell(
        session,
        domain="task",
        name="centered-discernment-practice",
        domain_blueprint=BID_task(),
        frontmatter={
            "idea_id": "centered-discernment",
            "status": "completed",
            "context": {
                "form": str(form_path.relative_to(REPO_ROOT)),
                "recipe": _node(practice_recipe),
                "source_url": source_url,
                "stream": practice_value,
            },
        },
        body=practice_value,
        source_path=str(form_path.relative_to(REPO_ROOT)),
    )

    witness_cells: list[dict[str, Any]] = []
    for index, action in enumerate(practice_value.split(" -> "), start=1):
        witness_cell, blueprint, ctor = ingest_witness_event(
            session,
            "life-sub-agent",
            action,
            f"substrate-ledger://centered-discernment/{index}",
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
        "practice_recipe": practice_recipe,
        "named_cells": {
            "life_sub_agent": life_agent,
            "practice_task": practice_task,
            "witnesses": witness_cells,
        },
        "stats": lattice_stats(session),
    }

    if ledger_path is not None:
        entries = [
            _ledger_entry(
                "form_recipe",
                {
                    "phase": "water",
                    "recipe": _node(practice_recipe),
                    "source_url": source_url,
                    "form_value": practice_value,
                },
            ),
            _ledger_entry("cell", {"phase": "gas", "cell": _serializable_cell(life_agent)}),
            _ledger_entry("cell", {"phase": "gas", "cell": _serializable_cell(practice_task)}),
        ]
        entries.extend(
            _ledger_entry("witness", {"phase": "gas", "cell": _serializable_cell(witness)})
            for witness in witness_cells
        )
        entries.append(
            _ledger_entry(
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
        "practice_recipe": _node(result["practice_recipe"]),
        "named_cells": {
            "life_sub_agent": _serializable_cell(result["named_cells"]["life_sub_agent"]),
            "practice_task": _serializable_cell(result["named_cells"]["practice_task"]),
            "witnesses": [
                _serializable_cell(witness)
                for witness in result["named_cells"]["witnesses"]
            ],
        },
        "stats": result["stats"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute the centered discernment Form practice."
    )
    parser.add_argument("--form", type=Path, default=FORM_PATH)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--timestamp", default=DEFAULT_TIMESTAMP)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ensure_schema()
    with session_scope() as session:
        result = execute_practice(
            session,
            timestamp=args.timestamp,
            source_url=args.source_url,
            ledger_path=args.ledger,
            form_path=args.form,
        )

    out = serializable_result(result)
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print("centered discernment Form practice executed")
        print(f"  form: {args.form}")
        print(f"  recipe: {out['practice_recipe']}")
        print(f"  value: {out['form_value']}")
        print(f"  life sub-agent: {out['named_cells']['life_sub_agent']}")
        print(f"  task: {out['named_cells']['practice_task']}")
        print(f"  witness cells: {len(out['named_cells']['witnesses'])}")
        print(f"  ledger: {args.ledger}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
