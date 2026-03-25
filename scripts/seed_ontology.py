#!/usr/bin/env python3
"""Seed the graph with Living Codex ontology — concepts, relationships, axes, frequencies.

Run once to populate graph_nodes + graph_edges from config/ontology/ JSON files.
Idempotent — skips nodes/edges that already exist.

Usage:
    python scripts/seed_ontology.py
    python scripts/seed_ontology.py --api https://api.coherencycoin.com
    python scripts/seed_ontology.py --dry-run
"""

import json
import logging
import os
import sys
from pathlib import Path

# Add api/ to path so we can import services
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "api"))
sys.path.insert(0, str(_ROOT / "api" / "scripts"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("seed_ontology")

ONTOLOGY_DIR = _ROOT / "config" / "ontology"


def load_json(filename: str) -> dict:
    path = ONTOLOGY_DIR / filename
    if not path.exists():
        log.warning("Missing: %s", path)
        return {}
    return json.loads(path.read_text())


def seed_via_api(api_base: str, dry_run: bool = False):
    """Seed via HTTP API — works against local or remote."""
    import urllib.request
    import ssl

    ctx = ssl.create_default_context()

    def post(path: str, body: dict) -> dict | None:
        if dry_run:
            log.info("DRY-RUN: POST %s %s", path, json.dumps(body)[:80])
            return {"id": body.get("id", "dry-run")}
        try:
            req = urllib.request.Request(
                f"{api_base}{path}",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            return json.loads(resp.read())
        except Exception as e:
            if "409" in str(e) or "exists" in str(e).lower():
                return {"id": body.get("id"), "skipped": True}
            log.warning("POST %s failed: %s", path, e)
            return None

    # 1. Seed concepts as nodes
    concepts_data = load_json("core-concepts.json")
    concepts = concepts_data.get("concepts", [])
    log.info("Seeding %d concepts...", len(concepts))
    created = 0
    for c in concepts:
        result = post("/api/graph/nodes", {
            "id": c["id"],
            "type": "concept",
            "name": c.get("name", c["id"]),
            "description": c.get("description", ""),
            "properties": {
                "categories": c.get("categories", []),
                "aliases": c.get("aliases", []),
                "ontology_source": "living-codex",
            },
            "phase": "ice",  # ontology concepts are stable/reference
        })
        if result and not result.get("skipped"):
            created += 1
    log.info("Concepts: %d created, %d skipped", created, len(concepts) - created)

    # 2. Seed axes as nodes
    axes_data = load_json("core-axes.json")
    axes = axes_data.get("axes", [])
    log.info("Seeding %d axes...", len(axes))
    created = 0
    for a in axes:
        result = post("/api/graph/nodes", {
            "id": f"axis:{a['id']}",
            "type": "axis",
            "name": a.get("name", a["id"]),
            "description": a.get("description", ""),
            "properties": {
                "states": a.get("states", []),
                "ontology_source": "living-codex",
            },
            "phase": "ice",
        })
        if result and not result.get("skipped"):
            created += 1
    log.info("Axes: %d created, %d skipped", created, len(axes) - created)

    # 3. Seed frequencies as nodes
    freq_data = load_json("core-frequencies.json")
    frequencies = freq_data.get("frequencies", [])
    log.info("Seeding %d frequencies...", len(frequencies))
    created = 0
    for f in frequencies:
        result = post("/api/graph/nodes", {
            "id": f"freq:{f['id']}",
            "type": "frequency",
            "name": f.get("name", f["id"]),
            "description": f.get("description", ""),
            "properties": {
                "hz": f.get("hz"),
                "octave": f.get("octave"),
                "ontology_source": "living-codex",
            },
            "phase": "ice",
        })
        if result and not result.get("skipped"):
            created += 1
    log.info("Frequencies: %d created, %d skipped", created, len(frequencies) - created)

    # 4. Seed relationship types as edges between a meta-node and each concept
    # First create a meta-node for the ontology itself
    post("/api/graph/nodes", {
        "id": "ontology:living-codex",
        "type": "concept",
        "name": "Living Codex Ontology",
        "description": "The root ontology from the Living Codex project. 184 concepts, 46 relationship types, 53 axes.",
        "properties": {"ontology_source": "living-codex", "is_root": True},
        "phase": "ice",
    })

    rels_data = load_json("core-relationships.json")
    relationships = rels_data.get("relationships", [])
    log.info("Seeding %d relationship type definitions...", len(relationships))
    # Store relationship types as properties on a meta-node
    post("/api/graph/nodes", {
        "id": "meta:relationship-types",
        "type": "concept",
        "name": "Relationship Types",
        "description": f"{len(relationships)} edge types from the Living Codex ontology",
        "properties": {
            "types": [{"id": r["id"], "name": r.get("name", r["id"]), "description": r.get("description", "")} for r in relationships],
            "count": len(relationships),
            "ontology_source": "living-codex",
        },
        "phase": "ice",
    })

    # 5. Create edges: each concept belongs_to the ontology root
    log.info("Creating ontology edges...")
    edge_created = 0
    for c in concepts:
        result = post("/api/graph/edges", {
            "from_id": c["id"],
            "to_id": "ontology:living-codex",
            "type": "part-of",
            "strength": 1.0,
            "created_by": "seed_ontology",
        })
        if result and not result.get("skipped"):
            edge_created += 1
    log.info("Ontology edges: %d created", edge_created)

    # Summary
    stats_resp = urllib.request.urlopen(f"{api_base}/api/graph/stats", timeout=10, context=ctx)
    stats = json.loads(stats_resp.read())
    log.info("Graph stats: %s", stats)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed ontology into graph")
    parser.add_argument("--api", default=os.environ.get("COHERENCE_API_URL", "https://api.coherencycoin.com"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log.info("Seeding ontology from %s into %s", ONTOLOGY_DIR, args.api)
    seed_via_api(args.api, dry_run=args.dry_run)
