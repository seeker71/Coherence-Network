"""Product idea anchor for self-balancing graph (entropy, anti-collapse, organic growth).

Implementation lives in :mod:`app.services.graph_health_service` and spec **172**.
This module is the stable string surface for routing, tests, and API metadata.
"""

from __future__ import annotations

IDEA_ID = "self-balancing-graph"
IDEA_NAME = (
    "Self-balancing graph: anti-collapse, organic expansion, entropy management"
)
SPEC_REF = "spec-172"
PARENT_IDEA_ID = "fractal-ontology-core"


def idea_metadata() -> dict[str, str]:
    """Return identifiers for lineage and observability (no I/O)."""
    return {
        "idea_id": IDEA_ID,
        "idea_name": IDEA_NAME,
        "spec_ref": SPEC_REF,
        "parent_idea_id": PARENT_IDEA_ID,
    }
