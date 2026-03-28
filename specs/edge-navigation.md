# Edge navigation — typed graph relationships

## Summary

Expose Living Codex relationship types and universal graph edges so clients can browse how entities connect (ideas, concepts, contributors, specs, tasks, news, etc.).

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/edges` | Paginated edge listing; query: `type`, `from_id`, `to_id`, `limit`, `offset` |
| GET | `/api/edges/types` | 46 ontology relationship types from `config/ontology/core-relationships.json` |
| GET | `/api/entities/{id}/edges` | Edges for a graph node; query: `direction` (`both`|`outgoing`|`incoming`), `type` |

Legacy graph CRUD remains at `/api/graph/*`.

## Web

- Route: `/edges` — interactive explorer: load entity by id, optional type filter, click edge to navigate to peer.

## CLI

- `cc edg types` — list relationship types  
- `cc edg list [limit]` — recent edges  
- `cc edg <entity_id> [type]` — edges for entity  

## Files

- `api/app/services/graph_service.py` — `list_edges`, `get_edges_for_entity_nav`
- `api/app/models/edge_navigation.py` — response envelopes
- `api/app/routers/edge_navigation.py` — routes
- `api/app/main.py` — router registration
- `web/app/edges/page.tsx`, `web/components/edge_graph_explorer.tsx`
- `web/components/site_header.tsx` — nav link
- `cli/lib/commands/edges.mjs`, `cli/bin/cc.mjs`

## Verification

- `cd api && .venv/bin/ruff check app/services/graph_service.py app/routers/edge_navigation.py app/models/edge_navigation.py`
- `cd api && .venv/bin/pytest -q -k edge` (or full suite if no edge-specific test)
- Manual: `curl -s "$API/api/edges/types" | jq '.total'`, `curl -s "$API/api/entities/<id>/edges"`

## Risks and Assumptions

- Assumes unified DB (`graph_edges`) is populated; empty DB returns empty lists, not errors (except unknown entity → 404).
- Relationship type count is defined by ontology JSON (currently 46).

## Known Gaps and Follow-up Tasks

- Force-directed or canvas graph visualization (currently list-based navigation).
- Batch peer resolution for very large fan-out.
