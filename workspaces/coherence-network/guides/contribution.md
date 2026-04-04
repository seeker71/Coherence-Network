# Contributing to the Coherence Network workspace

This is the default workspace — it hosts the platform's own ideas and specs.
If you're adding features to the Coherence Network itself, work lives here.

## The fractal

6 pillars → 16 super-ideas → leaf ideas. Every new idea must pick a parent
super-idea and inherit its pillar. See `ideas/INDEX.md` for the taxonomy.

## Workflow

```
spec → test → implement → CI → review → merge → deploy → verify
```

Every idea has a spec. Every spec declares its `source:` files and symbols.
Every task is linked to an idea via `context.idea_id`.

## Non-negotiables

- **Do not modify tests to force passing behavior.** Fix the code, not the test.
- **Implement exactly what the spec requires.** Read the frontmatter `source:` map first.
- **Every new idea must be recorded via `POST /api/ideas`** before the session ends.
- **Spec authoring**: run `python3 scripts/validate_spec_quality.py` before committing.
- **No scope creep**: changes stay within requested files/tasks.
- **Escalate via `needs-decision`** for security or architecture changes.

## Pillar ownership

| Pillar | Owns |
|--------|------|
| realization | Idea lifecycle, portfolio governance, scoring |
| pipeline | Agent orchestration, reliability, CI/CD, CLI/MCP |
| economics | Coherence Credit, value attribution, exchange |
| surfaces | Web UI, dashboards, developer experience |
| network | Federation, identity, contributor onboarding |
| foundation | Graph DB, data hygiene, knowledge/resonance, external presence |
