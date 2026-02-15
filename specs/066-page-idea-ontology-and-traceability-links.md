# Spec 066: Page-Idea Ontology and Traceability Links

## Purpose

Ensure every human page is explicitly traceable to:

- the originating idea
- the root idea
- the API contract
- the governing spec
- process/pseudocode
- source files and endpoint usage examples

## Requirements

1. Add machine-readable page lineage registry at `api/config/page_lineage.json`.
2. Add API endpoint `GET /api/inventory/page-lineage` with optional `page_path` filter.
3. Endpoint must report mapping coverage and missing page mappings.
4. Web UI must render lineage links on every page via shared layout component.
5. Lineage view must support contributor-origin ideas and explicitly mark when not tied to core system.
6. Tests must verify:
   - endpoint returns coverage and no missing pages
   - specific page lookup returns expected idea/root mapping

## Validation

- `cd api && .venv/bin/pytest -v tests/test_inventory_api.py`
- `cd web && npm run build`
