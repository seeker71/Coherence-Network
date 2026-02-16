"""Public mapping of human web pages to idea ids (for ontology traversal)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _config_path() -> Path:
    return _project_root() / "config" / "page_lineage.json"


FALLBACK_PAGES: list[dict[str, str]] = [
    {"path": "/", "idea_id": "portfolio-governance"},
    {"path": "/portfolio", "idea_id": "portfolio-governance"},
    {"path": "/flow", "idea_id": "portfolio-governance"},
    {"path": "/ideas", "idea_id": "portfolio-governance"},
    {"path": "/ideas/[idea_id]", "idea_id": "portfolio-governance"},
    {"path": "/specs", "idea_id": "coherence-network-api-runtime"},
    {"path": "/usage", "idea_id": "coherence-network-value-attribution"},
    {"path": "/automation", "idea_id": "coherence-network-agent-pipeline"},
    {"path": "/friction", "idea_id": "coherence-network-agent-pipeline"},
    {"path": "/gates", "idea_id": "oss-interface-alignment"},
    {"path": "/import", "idea_id": "coherence-signal-depth"},
    {"path": "/project/[ecosystem]/[name]", "idea_id": "coherence-signal-depth"},
    {"path": "/search", "idea_id": "coherence-signal-depth"},
    {"path": "/api-health", "idea_id": "oss-interface-alignment"},
    {"path": "/contributors", "idea_id": "portfolio-governance"},
    {"path": "/contributions", "idea_id": "portfolio-governance"},
    {"path": "/assets", "idea_id": "portfolio-governance"},
    {"path": "/tasks", "idea_id": "coherence-network-agent-pipeline"},
    {"path": "/agent", "idea_id": "coherence-network-agent-pipeline"},
]


def get_page_lineage() -> dict[str, Any]:
    """Return page->idea mapping for public traversal."""
    path = _config_path()
    pages = None
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("pages"), list):
                pages = [
                    row
                    for row in raw["pages"]
                    if isinstance(row, dict)
                    and isinstance(row.get("path"), str)
                    and isinstance(row.get("idea_id"), str)
                ]
        except (OSError, ValueError):
            pages = None

    items = pages if pages else FALLBACK_PAGES
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pages": items,
        "source": "config/page_lineage.json" if pages else "fallback",
    }
