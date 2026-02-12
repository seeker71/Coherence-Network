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
- **Gap we fill:** Graph intelligence + coherence scoring + AI agents + funding flows in one platform (Tidelift, tea.xyz, GitHub Sponsors, Socket, Snyk, deps.dev, CHAOSS each address one slice)

### Revenue Tiers

| Tier | Price | Key Features |
|------|-------|--------------|
| Free | $0 | View scores, explore graph, receive funding (no platform fee) |
| Pro | $29/mo | Full analytics, AI recommendations, dashboards, limited API |
| Team | $99/mo | Stack risk monitoring, team tracking, funding distribution, CI integration |
| Enterprise | $499–2,999/mo | OSPO dashboard, SBOM, custom algorithm weights, SLA, SSO |
| Transaction | 3–5% | On funding flows facilitated |

### User Journeys (Brief)

- **Maintainer:** Dashboard → coherence score → downstream impact → improvement suggestions → funding when enterprises subscribe
- **Enterprise Lead:** Import stack → coherence map → identify risks → subscribe → funding distributes; report "reduced risk 40%"
- **Contributor:** Explore graph by coherence (low = needs help) → contribute → attribution tracked → earn when funding flows
- **OSPO:** Connect org GitHub → full map → policy alerts (e.g. coherence < 0.4) → AI: "These 3 projects need sponsor. Budget: $2,400/mo."

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

**Pitfalls to guard against:** Balance contribution types (code, docs, triage); prevent gaming (fake commits, inflation); balance short-term vs long-term sustainability.

### States of Matter (OSS Examples)

| Phase | Examples |
|-------|----------|
| **Ice** | Specs in Git: project schema, coherence algorithm, API contracts |
| **Water** | Generated code, Neo4j schema, materialized coherence scores, event store |
| **Gas** | Live coherence calculation, active indexer, WebSocket dashboards |

**Phase transitions:** Melting (Ice→Water): specs → Pydantic/OpenAPI. Evaporating (Water→Gas): runtime loads data. Condensing (Gas→Water): persist events. Freezing (Water→Ice): significant changes committed back to specs.

### Generalization Path (Later)

- Generic `Node`, `Edge` base from Living Codex
- Breath loop: compose → expand → validate → melt/patch/refreeze → contract
- Meta-nodes: schemas, APIs as `codex.meta/*` for deterministic codegen
- Keep Ice tiny; let Water/Gas carry weight. Resonance before refreeze.
- Do not start super-generic; add abstraction only when second use case emerges.

---

## 4. Agent Council (Human-on-the-Loop)

| Agent | Role | Model (see docs/MODEL-ROUTING.md) |
|-------|------|-----------------------------------|
| Spec Drafter | Expands direction into full spec | Local / OpenRouter free |
| Test Writer | Writes tests from spec (must fail initially) | Local / OpenRouter free |
| Impl Worker | Implements to make tests pass | Local / Cursor / Claude Code |
| Review Panel | Correctness, Security, Spec compliance | Local / subscription |
| Healer | Fixes failing CI | Claude Code / Cursor |

**Human:** 2–3 sentence direction, approve/reject merges, decision gates. ~15–30 min/day target.

### Grounding Techniques

1. **Deterministic grounding** — Code compiles, tests pass, lint clean, CI green
2. **Holdout tests** — `tests/holdout/` excluded from agent context; CI runs them (prevents "return true")
3. **Spec-as-oracle** — Review Panel checks implementation against spec checkboxes
4. **Multi-model review** — Different models break echo chamber
5. **Failure-mode framing** — Ask "what could go wrong?" not "is this good?"

### Bounce-Back Pattern

When choosing approaches: Sub-agents research alternatives in parallel; Judge compares with failure-mode framing; Orchestrator chooses or escalates.

### Decision Routing

- **Routine (auto):** impl endpoint, fix bug, add test, refactor
- **Scope change (agent draft, human approve):** new field, new param, new error code
- **Major (human):** new service, schema change, auth, deploy, new dep

### Escalation Triggers (see CLAUDE.md)

Stop and create `needs-decision` issue for: new pip/npm dependency; Neo4j label/relationship changes; coherence formula/weights; new API resource; auth/authorization; deployment; token cost > $50; 3+ iterations stuck; agents disagree.

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

### Sprint-Level (Month 1–2)

| Sprint | Focus | Exit Criteria |
|--------|-------|---------------|
| 0 | Skeleton, CI, deploy | `git push` → CI green; `/health` 200; landing live |
| 1 | Graph | 5K+ npm packages; API returns real data; search works |
| 2 | Coherence + UI | `/project/npm/react` shows score; search across npm+PyPI |
| 3 | Import Stack | Drop package-lock.json → full risk analysis + tree |

### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Neo4j free tier insufficient | Medium | High | Migrate to self-hosted on Railway |
| GitHub API rate limits | High | Medium | deps.dev primary; GitHub supplementary; ETags |
| Coherence algorithm wrong/gameable | High | Medium | Ship v1 as beta; make weights adjustable |
| Test swapping | Medium | High | Holdout tests; explicit rule |
| Scope creep into funding too early | Medium | High | Strict sprint discipline; funding Month 4+ |
| Context rot | High | Medium | Fresh sessions per task; max 45 min |

---

## 7. Principles (From Living Codex)

- **Everything is a Node** — Data, structure, flow as nodes/edges
- **Adapters Over Features** — External I/O adapterized; core stays thin
- **Tiny Deltas** — Minimal patches; large rewrites must be justified
- **Deterministic Projections** — OpenAPI/JSON Schema from specs
- **One-Shot First** — Minimal sufficiency; prove each coil runs from atoms
- **No mocks** — Real data and algorithms; avoid simulation
- **Keep Ice Tiny** — Persist only atoms, deltas, essential indices; Water/Gas carry weight
- **Resonance Before Refreeze** — Structural edits must harmonize with anchors

**Language:** Lead externally with what the system does ("map the ecosystem, score health, route fair funding"), not internal design terms.

---

## 8. Pitfalls to Avoid

- Over-generic framework before delivering value
- Test swapping (fix implementation, not tests)
- Scope creep (only modify spec-listed files)
- Long AI sessions (context rot ~45 min)
- Ignoring security review for auth/input code
- Chat-only tools (Grok, OpenAI) used as primary dev — reserve for hard issues, copy/paste
- Creating new docs/files unless spec/issue requires or absolutely needed
