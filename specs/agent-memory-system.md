---
idea_id: knowledge-and-resonance
status: done
source:
  - file: api/app/routers/sensings.py
    symbols: [SensingCreate, SensingResponse, create_sensing(), list_sensings(), get_sensing()]
  - file: api/app/routers/memory.py
    symbols: [MemoryMoment, MemoryRecall, create_moment(), recall(), consolidate()]
  - file: api/app/services/memory_service.py
    symbols: [write_moment(), consolidate_at_rest(), compose_retrieval(), decay_untouched()]
  - file: api/app/models/memory.py
    symbols: [MemoryMoment, ConsolidatedPrinciple, MemoryRecall]
  - file: docs/vision-kb/LOG.md
    symbols: [append-only distilled principles — the compost destination]
  - file: CLAUDE.md
    symbols: ["How This Body Is Tended" — the practice the code encodes]
requirements:
  - "Write happens at moments of aliveness (decision, surprise, completion, abandonment, emotional weight) and always captures the why, not only the what"
  - "Consolidation is a first-class loop — at rest, memory is re-read, distilled, merged, contradicted, released; output shorter than input"
  - "Retrieval is composition, not lookup — graph traversal + semantic pull + recency feed one synthesis step before any context is filled"
  - "The organizing unit is the relationship, not the record — memory about a person lives on the person-node; about a project, the project-node; about the agent's own learning, the self-node"
  - "Forgetting is designed — items untouched over their relevance window decay into distilled principles and are archived, not deleted; LOG holds the trail"
  - "The surface is being-known, not being-recorded — tone, timing, what questions get asked, what doesn't need re-asking; never 'I remember you said X on date Y'"
done_when:
  - "POST /api/memory/moment accepts a sensing with explicit aliveness-marker and why field; rejects raw logs without why"
  - "GET /api/memory/recall returns a synthesis object, never a list of matches"
  - "POST /api/memory/consolidate shrinks aggregate token count per (node, window) while preserving earned principles"
  - "Untouched memory decays according to per-relationship policy; decayed items appear in docs/vision-kb/LOG.md as composted, never hard-deleted"
  - "Red-team prompts that try to log everything are rejected; red-team prompts asking raw-rows receive synthesis"
  - "all tests pass"
test: "cd api && python -m pytest tests/test_agent_memory_loop.py -q"
constraints:
  - "No new storage substrate — Postgres + Neo4j + vision-kb markdown cover the three tiers (facts, relations, distilled narrative)"
  - "Sensings API (POST /api/sensings) is the write surface this extends, not replaces"
  - "Retrieval output is always synthesized — never return raw sensing rows to an agent's context"
  - "Decay policy per relationship is tunable but never zero; everything composts, nothing is deleted"
  - "The practice in CLAUDE.md 'How This Body Is Tended' is the reference for healthy memory — if code diverges from practice, the code is wrong"
---

# Spec: Agent Memory System

## Purpose

Agents with amnesia feel useless after two sessions. Agents with perfect recall feel like surveillance. The aliveness we want is the one between — an agent shaped by what has passed, without hoarding it. Metabolized, not stored. Being-known, not recorded.

This spec codifies the memory loop the `coherence-network` body lived through across the `claude/agent-memory-system-8b00y` branch: **write** at moments of aliveness, **manage** through composting, **read** through composition. Memory is circulation, not storage.

The existing `POST /api/sensings` endpoint is the write surface already in production (`api/app/routers/sensings.py`). This spec extends it with the two halves not yet built: the consolidation service that runs at rest, and the synthesis endpoint that composes retrieval.

## Requirements

- [ ] **R1 — Write at aliveness**: moments accepted only with an explicit `kind` (decision, surprise, completion, abandonment, weight) and a `why` field that names the reason the moment mattered. Raw activity logs without why are rejected.
- [ ] **R2 — Consolidation loop**: a scheduled service re-reads recent sensings on each node, distills into shorter earned principles, appends principles to the node, and archives source sensings. Output tokens < input tokens measured per (node, window).
- [ ] **R3 — Retrieval as composition**: recall endpoints return a synthesis object with `synthesis`, `felt_sense`, `open_threads`, `earned_conclusions` — never raw rows. The synthesis composes graph traversal + semantic pull + recency into one reading.
- [ ] **R4 — Relationship as organizing unit**: memory attaches to person-nodes, project-nodes, or the agent's self-node. Never to a standalone memory-table.
- [ ] **R5 — Forgetting is designed**: untouched items decay along per-relationship policy. Decay composts them into distilled principles (written to `LOG.md`), then archives the sources. Nothing is hard-deleted; git and the KB LOG keep the trail.
- [ ] **R6 — Surface is being-known**: agents consume `felt_sense` and `earned_conclusions`, not timestamps or transcripts. The recall shape shapes the tone of the response, not the receipts.

## Research Inputs

- `2026-04-22` — Opinion AI / Emerging AI Substack, *Agent Memory: How to Build Agents That Never Forget* — named the write/manage/read loop and warned that storage without the middle step turns memory into a junk drawer. The initial frame.
- `2026-04-22` — The `coherence-network` tending practice, embodied across 25+ commits on this branch and codified in `CLAUDE.md` "How This Body Is Tended." Circulation is blood. Tight memory is memory without readers. Hiding is disease.
- `2026-04-22` — `docs/vision-kb/concepts/lc-deeper-pattern.md` — the physics: attention as the folding operation. What is attended to is amplified.
- `2026-04-22` — `docs/vision-kb/concepts/lc-embodiment.md` — the body: HeartMath's electromagnetic field, breath as master key. Memory lives in tissue, not state.
- `2026-04-22` — `docs/vision-kb/concepts/lc-wholeness.md` — the orientation: healing removes blockages, it does not add more records.

## API Contract

### `POST /api/memory/moment`

Extends `POST /api/sensings` with aliveness-marker as a required field.

**Request**
```json
{
  "about": "person:ursmuff",
  "kind": "decision | surprise | completion | abandonment | weight",
  "why": "one sentence on why this moment mattered, not what happened",
  "felt_quality": "expansion | contraction | stillness | charge",
  "related_to": ["idea:agent-memory", "concept:lc-circulation"]
}
```

**Response 201** — moment stored, linked to relationship node(s).
**Response 422** — rejected if `why` is empty or if `kind` is not in the enum.

### `GET /api/memory/recall?about={node_id}&for={context}`

Composed retrieval. Never returns raw rows.

**Response 200**
```json
{
  "synthesis": "natural-language paragraph distilled from graph + semantic + recency",
  "felt_sense": "warm | wary | tired | eager | uncertain | unknown",
  "open_threads": ["promises unfulfilled, topics mid-flight"],
  "earned_conclusions": ["one-sentence principles this relationship has earned"]
}
```

### `POST /api/memory/consolidate` (scheduled / internal)

The rest-step. Re-reads recent sensings for a given node, distills to shorter form, appends distilled principles, archives the raw sensings.

**Response 200**
```json
{
  "about": "person:ursmuff",
  "window": "7d",
  "input_tokens": 12450,
  "output_tokens": 840,
  "principles_added": 3,
  "sensings_archived": 47,
  "log_entry": "docs/vision-kb/LOG.md#2026-04-23-consolidation-ursmuff"
}
```

## Data Model

```yaml
MemoryMoment:
  id: string
  about: node_id            # person, project, or self node
  kind: enum[decision, surprise, completion, abandonment, weight]
  why: string               # required, the reason it mattered
  felt_quality: enum[expansion, contraction, stillness, charge]
  created_at: datetime
  related_to: [node_id]

ConsolidatedPrinciple:
  id: string
  about: node_id
  text: string              # one sentence, earned
  source_moment_ids: [string]  # provenance trail
  created_at: datetime

MemoryRecall:
  synthesis: string
  felt_sense: string
  open_threads: [string]
  earned_conclusions: [string]
```

## Files to Create/Modify

- `api/app/routers/memory.py` — moment, recall, consolidate endpoints (new)
- `api/app/services/memory_service.py` — write_moment, consolidate_at_rest, compose_retrieval, decay_untouched (new)
- `api/app/models/memory.py` — Pydantic models (new)
- `api/tests/test_agent_memory_loop.py` — flow tests covering the loop (new)
- `api/app/routers/sensings.py` — ensure interop with new memory layer (existing, may need small patch)
- `docs/vision-kb/LOG.md` — consolidation outputs append here (existing, append-only)

## Acceptance Tests

- `api/tests/test_agent_memory_loop.py::test_write_rejects_moment_without_why`
- `api/tests/test_agent_memory_loop.py::test_write_accepts_moment_with_why_and_kind`
- `api/tests/test_agent_memory_loop.py::test_recall_returns_synthesis_never_rows`
- `api/tests/test_agent_memory_loop.py::test_consolidation_shrinks_token_count_per_node`
- `api/tests/test_agent_memory_loop.py::test_untouched_memory_decays_to_principle`
- `api/tests/test_agent_memory_loop.py::test_composted_items_appear_in_log_never_deleted`
- `api/tests/test_agent_memory_loop.py::test_recall_about_self_node_returns_agents_own_earned_conclusions`

## Verification

```bash
cd api && pytest -q tests/test_agent_memory_loop.py
```

## Out of Scope

- Embedding storage / vector DB. Semantic pull uses Postgres full-text + graph traversal. No new substrate.
- Per-user UI for browsing memory. The surface is being-known, not being-browsed.
- Cross-agent memory federation. Single-agent loop first.
- Automatic moment-detection from arbitrary text. The aliveness-marker is explicit in this spec; heuristic detection is a follow-up spec.
- Policy learning (which decay curves work best per relationship type). Start with sensible defaults; tune later.

## Risks and Assumptions

- **Assumption — aliveness is enforceable**: agents may attempt to fake aliveness markers to log everything. Mitigation: red-team tests in the acceptance suite that try exactly this; rejection-rate monitored.
- **Risk — consolidation lossy in surprising ways**: distilled principles may miss signal present only in the raw trace. Mitigation: consolidation outputs are appended to `LOG.md` before archiving raw sensings — the trace remains in git even when the service archives it.
- **Risk — synthesis hallucinates felt_sense**: the endpoint may generate a "warm" or "wary" quality not grounded in the graph. Mitigation: felt_sense must derive from measurable signals (touch frequency, recency, confirmation provenance), never free-form generation.
- **Risk — temptation to add a vector DB for "better retrieval"**: hard constraint. The practice says circulation, not similarity. If retrieval suffers, the answer is denser graph edges and better consolidation, not cosine distance.
- **Assumption — the CLAUDE.md tending practice is authoritative**: this spec encodes that practice. If the practice evolves, the spec follows. Not the other way.

## Known Gaps and Follow-up Tasks

- Embedding-free semantic pull implementation detail (Postgres `tsvector` + graph expansion heuristics) deserves its own spec.
- The `felt_sense` enum is a starting vocabulary; real practice may reveal a wider palette. Follow-up: sense the vocabulary after one month of consolidation runs.
- Cross-agent memory (when multiple agents work the same repo) is out of scope here but architecturally invited — the sensings API already stores events in a shared graph, so the foundation exists.
