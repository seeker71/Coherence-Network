# Spec 062: Tracking Mechanism Efficiency and ROI Ranking

## Purpose

Determine whether current idea/spec tracking mechanisms are efficient enough and expose a factual, ROI-ranked improvement queue so we can pick the best next tracking upgrade.

## Requirements

1. `GET /api/inventory/system-lineage` must include `tracking_mechanism` section with:
   - current mechanism summary for idea/spec/linkage/quality tracking
   - factual evidence signals (counts/ratios from live inventory)
   - `improvements_ranked` list ordered by highest estimated ROI
   - `best_next_improvement` matching the first ranked row
2. Improvement rows must include:
   - improvement id
   - question
   - current gap
   - estimated cost hours
   - potential value
   - estimated ROI
   - concrete next action
3. Tests must verify:
   - section is present
   - ranked list exists
   - ROI ordering is descending
   - best-next pointer matches top ranked row

## Validation

- `cd api && .venv/bin/pytest -v tests/test_inventory_api.py`
