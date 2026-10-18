# GitNexus Integration — Experiment Setup & Agent Contract

> **Status**: experiment in progress (per `specs/gitnexus-integration-experiment.md`).
> **Decision pending**: adopt / drop / pivot at end of 30-task trial.

[GitNexus](https://github.com/abhigyanpatwari/GitNexus) is a tree-sitter-powered code-intelligence engine that builds a property graph of every function call, import, class, and inheritance edge in a repository, and exposes 16 MCP tools for AI agents.

This document is **the agent contract** for the trial: it defines when an agent should reach for GitNexus's tools versus our existing 60, and how to set up the sidecar.

---

## Why we're trying this

Our agents work spec-to-file at the granularity of frontmatter `source:` paths. They don't have call-graph awareness. Symptom: a confident edit can silently break a downstream caller, surfacing only as a `*_composted` failure or a review-flagged regression. GitNexus addresses exactly this gap by precomputing blast-radius answers at index time.

The trial is bounded — 30 paired tasks, then decide.

## Setup

GitNexus ships as the npm package `gitnexus`. Both local developer agents and the VPS runner use the same npx-based install so the trial measures one version everywhere.

### 1. The pin lives in two places (kept in sync)

| File | What it pins | Read by |
|------|--------------|---------|
| `.mcp.json` (repo root) | `gitnexus@1.6.3` | Claude Code, Cursor (project-scoped MCP) |
| `scripts/.gitnexus-pin` | `npm:1.6.3` + `sha:ffa0510...` | `deploy/hostinger/install-gitnexus.sh` |

When bumping the pin, update **both** files in the same PR. The git SHA in `.gitnexus-pin` records what was tested upstream so a measurement window is reproducible even if the npm version is later yanked or republished.

### 2. Local developer setup (Claude Code, Cursor)

The repo's `.mcp.json` is auto-discovered by Claude Code when the working directory is inside this repo. No global install needed:

```json
{
  "mcpServers": {
    "gitnexus": {
      "command": "npx",
      "args": ["-y", "gitnexus@1.6.3", "mcp"]
    }
  }
}
```

First call pays the npm fetch (~10s); subsequent calls use the npx cache. Verify by listing tools in your agent — you should see 16 GitNexus tools (`query`, `context`, `impact`, `cypher`, ...) alongside the 60 from `coherence-mcp-server`.

### 3. VPS runner setup (automatic via Hostinger Auto Deploy)

`deploy/hostinger/install-gitnexus.sh` runs at the end of every push-to-main deploy:

1. Reads `npm:` line from `scripts/.gitnexus-pin`.
2. Pre-caches `gitnexus@$NPM_VERSION` via `npx --yes gitnexus@$NPM_VERSION --version`.
3. Stops the previous sidecar (PID at `/var/run/gitnexus.pid`).
4. Starts a new sidecar via `nohup npx --yes gitnexus@$NPM_VERSION mcp --port 8765`.
5. Logs to `/docker/coherence-network/gitnexus.log`.

Non-blocking: any failure logs and exits 0 so api/web/pulse deploy keeps flowing.

### 4. Register the VPS sidecar with runner agents

Runner agents on the VPS (which is where the trial actually measures) connect to `http://localhost:8765` via SSE. Add the second server alongside `coherence-mcp-server` in the runner's MCP loader config — no code changes to the runner itself.

If the agent acts on a stale index, count it as a `pivot` signal in the measurement, not a setup bug to silence.

---

## Agent Contract — when to call which tool

The body has two graph layers running in parallel during the trial. They serve different intents and don't merge. Use this table as a decision rule.

| Question the agent has | Call this tool | Returns |
|------------------------|----------------|---------|
| **Structure-layer** (GitNexus) | | |
| "What functions call `X`?" | `gitnexus.context` | callers + call sites + confidence |
| "What breaks if I rename `X`?" | `gitnexus.impact` | blast-radius graph with depth + confidence |
| "What does this file import?" | `gitnexus.context` | imports + re-exports + bindings |
| "What classes extend `X`?" | `gitnexus.cypher` | inheritance subtree |
| "Is there a function semantically like `Y`?" | `gitnexus.query` | hybrid search (BM25 + semantic + RRF) |
| "What execution flow does `endpoint_X` participate in?" | `gitnexus.context` (process view) | upstream + downstream call chain |
| **Meaning-layer** (our existing tools) | | |
| "Which idea owns this work?" | `coherence_trace` | idea → spec → contributors |
| "Which spec covers this file?" | `coherence_trace` (file → spec) | spec frontmatter `source:` match |
| "Which contributor staked CC on this idea?" | `coherence_lineage` | CC stake graph |
| "What's the next pending task in this idea?" | `coherence_task_seed` / `coherence_select_idea` | task queue |
| "How is this concept used across ideas?" | `coherence_concept_*` | concept-resonance graph |

**The discipline**: if the agent's question is "what code is connected to this code," GitNexus first. If the question is "what intent / contributor / value is connected to this code," our tools first. The two layers compose only at the agent's discretion — no pre-built joiners exist during the trial.

### Concrete examples

**Before editing `api/app/services/coherence_service.py::compute_score`:**

1. `gitnexus.impact(symbol="compute_score")` → list of callers across the repo. The agent reads this to decide whether the edit is safe.
2. `coherence_trace(file="api/app/services/coherence_service.py")` → which spec(s) reference this file, what `done_when` items rely on it. The agent uses this to plan tests.

The two outputs are independent. Compose them in the agent's plan, not in a query.

**Before renaming `Idea.coherence_score` field:**

1. `gitnexus.cypher` → all references in the codebase, weighted by confidence.
2. `coherence_trace(symbol="Idea.coherence_score")` → which spec frontmatter mentions this symbol.

If GitNexus surfaces a caller that no spec covers, that's a finding regardless of the rename — surface it to the user.

---

## Worked example — adding a parameter to `_coherence_score`

A real demonstration of how the agent contract changes the workflow on a concrete edit task in this codebase.

**Hypothetical task**: extend `_coherence_score(exchange_rate)` in `api/app/services/cc_treasury_service.py` to accept an optional `target_supply` parameter so callers can model what-if scenarios. Default value preserves existing behavior.

### Without GitNexus (today's pattern)

The agent typically does:

```bash
grep -rn "_coherence_score" api/  # raw textual sweep
```

This returns 4 hits, all in the same file. Agent edits the function and the 3 internal callers. Tests pass. Ships.

What's missed:
- Two **public** wrappers (`coherence_status()`, `can_mint()`) call `_coherence_score(exchange_rate)` and re-expose its return through dicts. Their callers don't grep against `_coherence_score` because they call the public wrappers — but those wrappers' contracts depend on `_coherence_score`'s signature.
- `coherence_status()` is consumed by `api/app/routers/energy_sensing.py:252` (`cc_treasury_service.coherence_status(rate)`), which feeds the `/api/sensings/energy` route, which feeds the web `/practice` page.
- The agent didn't see this chain. If the wrapper's return shape changes downstream of the new param, the practice page silently breaks.

This is the **downstream-caller miss** the trial is measuring.

### With GitNexus (the trial pattern)

The agent calls in order:

1. **`gitnexus.impact(symbol="_coherence_score")`** — returns the blast-radius graph:
   - 3 direct callers in `cc_treasury_service.py` (depth 1, confidence 1.0)
   - 2 indirect callers via wrapper functions (`coherence_status`, `can_mint`) at depth 2
   - Following the wrappers: `routers/energy_sensing.py::coherence_status` and `routers/practice.py::practice_summary` at depth 3
   - That's the chain the grep missed.

2. **`gitnexus.context(symbol="coherence_status")`** — returns the wrapper's return shape so the agent can decide whether the new param leaks through. If `coherence_status` returns `{"coherence_score": ...}` literally, the wrapper can keep its current contract by passing `target_supply=None` through. If callers rely on the score being computed against the live supply only, the wrapper signature needs widening too.

3. **`coherence_trace(file="api/app/services/cc_treasury_service.py")`** — returns the meaning-layer info: which spec covers this file (`cc-economics-and-value-coherence`), which `done_when` items reference it, which contributors have stake.

4. **`coherence_trace(file="web/app/practice/page.tsx")`** *(if step 1 surfaces it)* — checks whether the practice page has spec coverage. If it doesn't, that's a finding to surface independent of this edit.

The agent now has a **full picture**: code surface (GitNexus), intent surface (our tools), and the spec coverage that defines what tests must pass. The edit plan can then propagate the new parameter as a no-op default through the wrappers, write tests at each layer, and ship without the silent practice-page regression.

### What the trial measures from this difference

The trial isn't measuring whether GitNexus is *capable* of this — it clearly is. It's measuring whether agents **actually use it** when given the option, and whether outcomes (composted failures, heal cycles, downstream-caller misses) actually move. An impressive tool that agents skip because the contract isn't sharp earns a `drop`. A tool agents reach for and outcomes shift earns `adopt`.

---

## What we are measuring

`scripts/measure_gitnexus_value.py` runs the same task batch twice (with vs. without GitNexus tools registered) and emits a comparison report. Metrics:

- `composted_failures`: count of tasks ending in any `*_composted` status.
- `heal_cycles`: total `heal` task type count across the batch.
- `time_to_merge_minutes_median`: from task seed to PR merge.
- `downstream_caller_misses`: review-flagged regressions where a reviewer notes "this broke caller X."

Run during trial:

```bash
python3 scripts/measure_gitnexus_value.py --window-start 2026-04-27 --window-end 2026-05-27
python3 scripts/measure_gitnexus_value.py --report-only   # render the comparison without re-collecting
```

---

## Decision criteria (filled at trial end, recorded in the spec's `## Outcome` section)

- **adopt** — the deltas show meaningful reduction in composted failures or downstream-caller misses, AND agent feedback is positive (tools are not just inflating context). Write a follow-up integration spec for permanent install + the meaning↔structure composition layer.
- **drop** — deltas are flat or negative, OR agents ignored the contract and consumed extra tokens without using the tools. Uninstall and document why.
- **pivot** — the structural intelligence helps but the deployment shape doesn't (e.g., index staleness too painful, schema mismatch obvious, sidecar adds operational drag). Specify what to absorb (e.g., just the impact-analysis concept built into our own graph) and write a focused spec for that.

---

## What this trial deliberately does NOT do

- Merge GitNexus's node types into our Neo4j graph — premature.
- Build the "blast radius for function X → which idea/spec/contributor stake" join — only worth it if `adopt`.
- Replace any existing tool. GitNexus is purely additive.
- Multi-repo `group_*` features. Single-repo for now.
