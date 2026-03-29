# Progress — concept-translation-views

## Completed phases

- **2026-03-28 — Spec (task_69660a3b43d):** Added `specs/concept-translation-views.md` — full product spec for conceptual lens translation (API `GET /api/ideas/{id}/translate`, `GET /api/concepts/{id}/translate`), web `/ideas/[idea_id]` lens UI, CLI `cc idea <id> --view`, MCP `coherence_translate_idea`, data/provenance model, risks, metrics for “is it working,” and five executable verification scenarios. Cleaned duplicate/corrupt lines in `.gitignore` (task artifact patterns kept once).

## Current task

(none — spec task complete)

## Key decisions

- **Not MT:** Explicitly out of scope for natural-language i18n; “translation” means conceptual framework / lens.
- **Provenance tri-state:** `graph_backed` | `model_augmented` | `fallback_sparse_graph` for honest UI when the graph is thin.
- **MVP lenses:** `original`, `scientific`, `economic`, `spiritual`, `artistic`, `philosophical` as a closed enum for validation.

## Blockers

- Terminal/sandbox in this session could not run `git`, `curl` heartbeat, or `cc`; runner should execute `git add` / `commit` and optional `python3 scripts/validate_spec_quality.py --file specs/concept-translation-views.md` locally.
