# Coherence Network — Consolidated Plan

> Synthesized from Crypo-Coin-Coherency-Network (Feb 2026) and Living-Codex-CSharp (Oct 2025).
> Baseline: Get to working, shareable platform fast. Evolve toward generic knowledge graph + coherence.

## 1. Product: Open Source Contribution Intelligence

**One sentence:** Coherence maps the open source ecosystem as an intelligence graph, computes project health scores, and enables fair funding flows from enterprises to maintainers.

### Three Layers

| Layer | What |
|-------|------|
| **Graph** | Every package, repo, contributor, dependency, commit, PR — indexed as concepts and relationships. Built from public data. |
| **Intelligence** | AI agents analyze: project health, contributor attribution, dependency risk, cross-project connections. |
| **Funding** | Enterprise subscribes → money flows → coherence algorithm distributes proportionally → maintainers receive compensation. |

### Why This First

- No cold start: data is public (GitHub, npm, PyPI)
- Acute pain: 60% maintainers unpaid, 60% quitting
- Proven willingness to pay: Tidelift model
- Perfect fit for concept-as-graph architecture

---

## 2. Tech Stack (Hybrid — MVP)

| Component | Choice | Rationale |
|-----------|--------|-----------|
| API | FastAPI (Python) | Fast iteration, OpenAPI, data ecosystem |
| Web | Next.js 16 + shadcn/ui | SSR, BFF, professional UI |
| Graph | Neo4j | Dependency traversals |
| Relational | PostgreSQL | Users, billing, events |
| Data sources | deps.dev, Libraries.io, GitHub | 100M+ edges, public APIs |

**Future:** C#/.NET + Orleans when scale or multi-agent framework demands it. Specs remain framework-agnostic.

---

## 3. Concept Model (OSS-First, Generalization Path)

### OSS Concepts (MVP)

| Concept | Purpose |
|---------|---------|
| `Project` | Repo, package, or module |
| `Contributor` | Developer, maintainer, reviewer |
| `Dependency` | DEPENDS_ON, MAINTAINED_BY edges |
| `Contribution` | Commits, PRs, issues, reviews |
| `CoherenceScore` | Project health 0.0–1.0 |

### Coherence Algorithm (Initial)

```
Coherence = f(
  contributor_diversity,    # bus factor
  dependency_health,       # maintained?
  activity_cadence,        # releases, responsiveness
  documentation_quality,
  community_responsiveness,
  funding_sustainability,
  security_posture,
  downstream_impact
)
```

### Generalization Path (Later)

- Generic `Node`, `Edge` base from Living Codex
- Breath loop: compose → expand → validate → melt/patch/refreeze → contract
- States of matter: Ice (specs), Water (materialized), Gas (runtime)
- Do not start super-generic; add abstraction only when second use case emerges.

---

## 4. Agent Council (Human-on-the-Loop)

| Agent | Role | Model (see MODEL-ROUTING.md) |
|-------|------|------------------------------|
| Spec Drafter | Expands direction into full spec | Local / OpenRouter free |
| Test Writer | Writes tests from spec (must fail initially) | Local / OpenRouter free |
| Impl Worker | Implements to make tests pass | Local / Cursor / Claude Code |
| Review Panel | Correctness, Security, Spec compliance | Local / subscription |
| Healer | Fixes failing CI | Claude Code / Cursor |

**Human:** 2–3 sentence direction, approve/reject merges, decision gates. ~15–30 min/day target.

---

## 5. Manual vs Autonomous Interface

- **Cursor** — Primary manual interface. Use for interactive development, UI, debugging.
- **Chat (Grok, OpenAI)** — Copy/paste for resolving hard framework issues when API not available.
- **Future** — OpenClaw, Agent Zero, or similar for autonomous agent work. API keys and multi-agent setup deferred until framework is decided.

---

## 6. Roadmap (Months)

| Month | Focus | Deliverables |
|-------|-------|--------------|
| 1 | Graph foundation | Concept specs, indexer, top 1K npm packages, basic API |
| 2 | Coherence scores | Algorithm spec, calculator agent, dashboard, PyPI indexing |
| 3 | Intelligence | Risk monitor, connection discovery, Import Your Stack |
| 4 | Funding flows | Energy token, funding router, Team tier, Stripe |
| 5 | Scale & polish | NuGet, crates, Go; Enterprise tier; public launch prep |

---

## 7. Principles (From Living Codex)

- **Everything is a Node** — Data, structure, flow as nodes/edges
- **Adapters Over Features** — External I/O adapterized; core stays thin
- **Tiny Deltas** — Minimal patches; large rewrites must be justified
- **Deterministic Projections** — OpenAPI/JSON Schema from specs
- **One-Shot First** — Minimal sufficiency; prove each coil runs from atoms
- **No mocks** — Real data and algorithms; avoid simulation

---

## 8. Pitfalls to Avoid

- Over-generic framework before delivering value
- Test swapping (fix implementation, not tests)
- Scope creep (only modify spec-listed files)
- Long AI sessions (context rot ~45 min)
- Ignoring security review for auth/input code
- Chat-only tools (Grok, OpenAI) used as primary dev — reserve for hard issues, copy/paste
