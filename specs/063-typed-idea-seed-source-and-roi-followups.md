# Spec 063: Typed Idea Seed Source and ROI Follow-ups

## Purpose

Reduce reliance on Python hard-coded defaults by introducing a typed JSON seed source for ideas, while keeping safe fallback behavior, and track next higher-investment tracking upgrades as ROI-ranked ideas.

## Requirements

1. Idea default seed supports a typed JSON source at `api/config/idea_defaults.json`.
2. Idea service supports `IDEA_DEFAULTS_PATH` override for machine-controlled seed changes.
3. Seed loading validates idea shape via `Idea` model before use.
4. If seed file is missing/invalid, service must safely fall back to Python defaults.
5. Portfolio includes new ROI-tracked follow-up ideas for:
   - DB-backed evidence storage
   - CI drift gate enforcement
6. Tests verify JSON seed loading path is active.

## Validation

- `cd api && .venv/bin/pytest -v tests/test_ideas.py`
- `GET /api/ideas` returns seeded idea IDs from JSON source when `IDEA_DEFAULTS_PATH` is set.
