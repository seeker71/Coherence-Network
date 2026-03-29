# Progress — concept-layer-foundation

## Completed phases

- **2026-03-28 — Spec (task_f450e902c7881c4d):** Added `specs/concept-layer-foundation.md` defining the Concept layer: CRUD `/api/concepts`, `/api/concepts/{id}/edges`, `/api/concepts/search`, web `/concepts`, CLI `cc concepts` / `cc concept` / `cc concept link`, MCP `coherence_list_concepts`, `coherence_get_concept`, `coherence_link_concepts`, seed from `config/ontology/core-*.json` (184 / 46 / 53), cross-resource tagging, five runnable Verification Scenarios (create-read-update, edges, search, errors, seed coverage), proof/observability section. Repaired `.gitignore` corruption from prior bad appends.

## Current task

- (complete) Product spec for concept-layer-foundation — committed to branch.

## Key decisions

- Canonical spec path: `specs/concept-layer-foundation.md` (matches idea_id).
- Ontology counts verified in-repo: 184 concepts, 46 relationship types, 53 axes in `config/ontology/`.
- Optional `POST /api/concepts/seed` documented for operators; primary seed may be automatic on deploy.

## Blockers

- None.
