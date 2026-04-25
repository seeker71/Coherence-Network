# Onboarding — Coherence Network workspace

Welcome. This workspace runs the Coherence Network platform itself.

## First pass

1. **Read `CLAUDE.md`** — architecture, conventions, deploy flow.
2. **Read `ideas/INDEX.md`** — the 16 super-ideas in 6 pillars.
3. **Pick a super-idea that matches your interest.** Open its `.md` file.
4. **Drill into one of its child ideas** or one of its linked specs.

## CLI tour

```bash
coh idea list                 # 16 curated super-ideas
coh idea list --all           # every idea (325+)
coh idea agent-pipeline       # a specific idea
coh spec list                 # all specs
coh tasks --status pending    # work waiting for an agent
coh status                    # pipeline health
```

## Anatomy of a spec

- ~25 lines of frontmatter: `idea_id`, `source` (files+symbols), `requirements`,
  `done_when`, `test`, `constraints`. An agent needs only the frontmatter.
- Body: API contract, data model, acceptance tests, risks. Reference for humans.

## Anatomy of an idea

- `.md` file: problem statement, capabilities, linked specs, absorbed ideas.
- DB record: full metrics (`potential_value`, `estimated_cost`, `confidence`,
  `stage`, `lifecycle`, `parent_idea_id`, `pillar`, `workspace_id`).

## Where to ask

- GitHub issues for bugs / feature requests
- Questions about the pipeline: see `ideas/agent-pipeline.md`
- Federation questions: see `ideas/federation-and-nodes.md`
