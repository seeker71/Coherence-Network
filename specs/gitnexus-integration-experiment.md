---
idea_id: knowledge-and-resonance
status: draft
source:
  - file: docs/integration/gitnexus-integration-experiment.md
    symbols: [setup steps, agent contract, decision criteria]
  - file: scripts/measure_gitnexus_value.py
    symbols: [collect_window(), render_report(), WindowMetrics]
  - file: mcp-server/coherence_mcp_server/server.py
    symbols: [MCP server entrypoint — sidecar registration target]
  - file: specs/source-artifact-sensing-graph-integration.md
    symbols: [meaning-layer pattern this experiment instantiates at the structure layer]
  - file: api/scripts/local_runner.py
    symbols: [agent runner that consumes MCP tools]
requirements:
  - "Run GitNexus as a sidecar MCP server pointed at this repo, separate from our Neo4j-backed graph."
  - "Document the agent contract: when to call GitNexus's `query`, `context`, `impact` tools vs our existing 60 MCP tools."
  - "Measure pipeline outcomes for 30 tasks with vs without GitNexus access — break/heal counts, downstream-caller misses, time-to-merge."
  - "Decide at the end of the trial: adopt permanently (write a follow-up integration spec), drop, or pivot to schema absorption."
done_when:
  - "GitNexus's MCP server is reachable from the runner host and its 16 tools appear in agent tool-list output."
  - "docs/integrations/gitnexus-integration-experiment.md describes when an agent should call GitNexus tools (with concrete examples) and when our existing tools are sufficient."
  - "scripts/measure_gitnexus_value.py produces a comparison report across at least 30 paired tasks."
  - "A signed-off decision (adopt / drop / pivot) is recorded in the spec's `## Outcome` section with the measurement evidence."
test: "python3 scripts/measure_gitnexus_value.py --report-only"
constraints:
  - "No changes to Neo4j schema — GitNexus runs alongside, not merged into, our existing graph."
  - "GitNexus index lives outside the repo (in `~/.gitnexus/`); do not commit its database files."
  - "Trial runs on the agent runner only — no production API surface changes."
  - "If GitNexus's index goes stale during the trial, that counts as a failure mode to record, not a setup bug to silence."
---

# Spec: GitNexus Integration Experiment

## Purpose

GitNexus is an open-source MCP-native code-intelligence engine that parses a repo with tree-sitter into a property graph (Functions, Classes, Methods; CALLS, IMPORTS, EXTENDS, IMPLEMENTS edges) and exposes 16 MCP tools — `query`, `context`, `impact`/blast-radius, `cypher`, multi-repo `group_*` — for AI agents to consult before editing code. Our agents currently work spec-to-file at the granularity of frontmatter `source:` paths; they don't have call-graph awareness, which means a confident edit can silently break a downstream caller. This spec runs a bounded experiment: install GitNexus as a sidecar MCP server, document when agents should call it, and measure whether call-graph awareness reduces break/heal cycles enough to earn a permanent place in the toolchain.

## Requirements

- [ ] **R1 — Sidecar deployment, not schema merge**: Install GitNexus's CLI + MCP server on the runner host, pointed at this repo. Index lives in `~/.gitnexus/` outside the working tree. No changes to our Neo4j schema, no merging of node types. The two graphs remain independent: ours is the meaning layer (idea → spec → contribution → CC), GitNexus is the structure layer (function → call → class → process).

- [ ] **R2 — Agent contract documented**: `docs/integrations/gitnexus-integration-experiment.md` defines, with concrete examples, when an agent should reach for GitNexus tools vs. our existing 60. Initial draft: GitNexus for "what depends on X / what does X depend on / what breaks if I change X" (impact, context, query); ours for "what idea/spec/contributor owns this work" (coherence_trace, idea/spec lookup). The doc is the contract — agents read it before adopting the new tools, not after.

- [ ] **R3 — Paired measurement across 30 tasks**: `scripts/measure_gitnexus_value.py` runs the same task batch twice — once with our existing tools only, once with GitNexus tools added — and records: (a) number of `*_composted` failures, (b) `heal` cycles per task, (c) time-to-merge, (d) downstream-caller misses (review-flagged regressions). 30 paired tasks is a noisy signal but enough to surface gross effect sizes; it's a sensing breath, not a clinical trial.

- [ ] **R4 — Decision recorded with evidence**: At trial end, the spec gains an `## Outcome` section that records: (a) the measurement deltas, (b) qualitative agent feedback (is the additional tool surface confusing? does it help or just inflate context?), (c) a binding decision — `adopt` (write follow-up integration spec for permanent install), `drop` (uninstall, document why), or `pivot` (e.g., absorb just the impact-analysis concept into our own graph). Decisions made without recorded evidence don't count.

## Research Inputs

- `2026-04-27` - [GitNexus README](https://github.com/abhigyanpatwari/GitNexus/blob/main/README.md) — schema, MCP tool list, deployment modes (CLI native + browser WASM)
- `2026-04-24` - [Meet GitNexus — MarkTechPost](https://www.marktechpost.com/2026/04/24/meet-gitnexus-an-open-source-mcp-native-knowledge-graph-engine-that-gives-claude-code-and-cursor-full-codebase-structural-awareness/) — context on the problem GitNexus addresses (agents shipping confident downstream-breaking edits)
- `2026-04-27` - [pi-gitnexus](https://github.com/tintinweb/pi-gitnexus) — example of a coding agent integrating GitNexus's knowledge graph; reference for our own agent contract
- `2026-04-27` - `specs/source-artifact-sensing-graph-integration.md` — our existing spec that names "source artifacts as first-class graph nodes"; GitNexus is the fine-grained code instance of that pattern

## API Contract

No public API changes. GitNexus exposes its 16 MCP tools through its own server process; our existing API and MCP server are unchanged for the duration of this experiment.

## Data Model

GitNexus's graph schema (separate from ours):

```yaml
Nodes:
  - File, Folder
  - Function, Method, Class, Interface
  - Community (semantic cluster, with heuristicLabel)

Edges:
  - CALLS (function/method invocation, confidence-scored 0–1)
  - IMPORTS (file-level dependency)
  - EXTENDS (class inheritance)
  - IMPLEMENTS (interface implementation)
  - MEMBER_OF (symbol ↔ community)
```

Our existing schema is untouched. Composition between the two graphs (e.g., "blast radius for function X → which spec → which idea → which CC stake") is **out of scope for this experiment** — it would be the work of a follow-up integration spec only if the trial's outcome is `adopt`.

## Files to Create/Modify

- `specs/gitnexus-integration-experiment.md` — this spec
- `docs/integrations/gitnexus-integration-experiment.md` — setup steps, agent contract, measurement protocol
- `scripts/measure_gitnexus_value.py` — paired-task measurement runner + comparison report
- `api/app/config/mcp_servers.json` — register GitNexus's MCP server endpoint so agents can discover it (or equivalent existing registry; refer to current MCP loader in `mcp-server/`)

## Acceptance Tests

```bash
# Setup: install GitNexus and verify MCP reachability
gitnexus index .
gitnexus mcp serve --port 8765 &
curl -s http://localhost:8765/tools | jq '.tools | length'   # expect 16

# Measurement: paired-task report
python3 scripts/measure_gitnexus_value.py --baseline-tasks 30 --report-only
```

## Verification Scenarios

### Scenario 1 — GitNexus tools reachable from runner
After installing per the integration doc, the runner's MCP client lists GitNexus's 16 tools alongside our 60. Agent `tool_use` traces show successful `query` and `context` calls returning structured JSON.

### Scenario 2 — Documented agent contract is followed
Sample 10 agent runs from the trial. For each, check whether the tool-call pattern matches the contract (GitNexus for impact/blast-radius questions, ours for idea/spec/contribution lookups). Mismatches flag a contract problem (the doc is unclear) or a discipline problem (the agent ignored the doc) — both are useful signal.

### Scenario 3 — Decision surfaces in spec body
At trial end, the spec contains an `## Outcome` section with: comparison table (with-GitNexus vs without across the 4 metrics), at least 3 qualitative agent observations, and one of `adopt` / `drop` / `pivot` declared explicitly with justification.

## Out of Scope

- Merging GitNexus's Function/Class/Method node types into our Neo4j graph.
- The "blast radius → spec → idea → CC stake" composition that would let our agents answer "if I change function X, which contributor's CC stake is touched?" — only worth building if this experiment outcomes `adopt`.
- Multi-repo `group_*` features — we have one repo for now; cross-repo analysis is for federation-stage work.
- Replacing existing tools (grep, our `coherence_trace`, etc.). GitNexus is additive in this trial.

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| GitNexus's index goes stale between commits and agents act on outdated graph | Document the staleness window in the agent contract; trial counts a confident edit on stale graph as a `pivot` signal, not a setup bug |
| 30-task sample is too small to surface effect | Treat it as a sensing breath; if signal is genuinely ambiguous after 30, extend to 60 before deciding |
| Adding 16 tools inflates agents' context budget without helping | Measure context tokens consumed per task; if GitNexus tools dominate without changing outcome, that's a `drop` signal |
| GitNexus is a young project (v0.x), API may shift mid-trial | Pin to a specific git SHA at trial start; record the SHA in the integration doc |
| Agents ignore the contract and call GitNexus tools randomly | The mismatch metric in Scenario 2 captures this — it's signal, not failure |

**Assumptions:**
- Tree-sitter has working grammars for the languages in this repo (Python, TypeScript, JavaScript, Bash). Verified per GitNexus's published language matrix.
- Running a sidecar MCP server doesn't conflict with our existing MCP infrastructure. To verify in setup.

## Outcome

*To be filled at trial end.*

```
Comparison (n=30 paired tasks):

Metric                     | Baseline | With GitNexus | Delta
---------------------------|----------|---------------|-------
*_composted failures       |    ?     |       ?       |   ?
heal cycles per task       |    ?     |       ?       |   ?
time-to-merge (median min) |    ?     |       ?       |   ?
downstream-caller misses   |    ?     |       ?       |   ?

Qualitative observations:
- ...

Decision: [adopt | drop | pivot] — [justification]
```

## Known Gaps

- The 30-task sample size is a sensing breath, not a clinical trial — it surfaces gross effect sizes but won't catch subtle improvements. If the trial outcomes `pivot`, larger-N follow-up is in scope of the pivot spec.
- We have no current way to detect "downstream-caller miss" automatically; the trial relies on review-flagged regressions, which itself is a noisy signal. A future spec could add a structured post-merge regression catcher.
- GitNexus's index can drift from HEAD between commits; the experiment treats stale-index incidents as data, but a permanent integration would need the staleness story figured out (event-driven reindex, hooks on commit, etc.).
- The composition story — "blast radius for function X → which idea/spec/contributor stake" — is the genuinely interesting layer this experiment doesn't touch. Only the `adopt` outcome justifies opening that follow-up.

