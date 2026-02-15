# Spec 069: Question/Answer Ontology and Evolution Trace

## Purpose

Ensure every question and answer is anchored to the system ontology so humans and machines can reason about why paths were chosen and how the system evolved.

## Requirements

1. Extend idea question model with ontology/provenance fields:
   - `question_id`
   - `parent_idea_id`
   - `parent_question_id`
   - `evolved_from_answer_of`
   - `asked_by`
   - `answered_by`
   - `evidence_refs`
2. Auto-enforce ontology defaults during portfolio reads/migrations:
   - all questions must have a stable `question_id`
   - all questions must be linked to a valid idea (or parent question)
3. Extend answer API to accept provenance:
   - `answered_by`
   - `evidence_refs`
   - `evolved_from_answer_of`
4. `GET /api/inventory/system-lineage` must include `question_ontology` section:
   - linked/unlinked counts
   - answered-without-provenance count
   - evolution edge rows

## Validation

- `cd api && .venv/bin/pytest -v tests/test_ideas.py tests/test_inventory_api.py`
