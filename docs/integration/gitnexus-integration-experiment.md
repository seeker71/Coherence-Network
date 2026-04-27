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

### 1. Pin the GitNexus revision

Trial uses GitNexus pinned at the SHA recorded in `scripts/measure_gitnexus_value.py::GITNEXUS_PIN`. If the upstream API shifts mid-trial, we want to know — re-pinning would invalidate the measurement window.

### 2. Install on the runner host

```bash
# On the agent runner host (e.g., the VPS at 187.77.152.42 or each worker node)
git clone https://github.com/abhigyanpatwari/GitNexus.git ~/gitnexus
cd ~/gitnexus
git checkout "$(cat /docker/coherence-network/repo/scripts/.gitnexus-pin)"
npm install
npm run build

# Index this repository
node dist/cli.js index /docker/coherence-network/repo

# Start the sidecar MCP server (background, port 8765)
node dist/cli.js mcp serve --port 8765 &
```

Verify: `curl -s http://localhost:8765/tools | jq '.tools | length'` returns `16`.

### 3. Register with each agent

**Claude Code** (`~/.claude.json` or `.mcp.json` per project):

```json
{
  "mcpServers": {
    "gitnexus": {
      "url": "http://localhost:8765",
      "type": "sse"
    }
  }
}
```

**Cursor** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "gitnexus": {
      "command": "node",
      "args": ["/home/user/gitnexus/dist/cli.js", "mcp", "stdio"]
    }
  }
}
```

**Local runner agents**: register via the MCP loader the runner already uses for `coherence-mcp-server` — point at `http://localhost:8765` as a second server, no code changes to the runner needed.

### 4. Reindex on commit

GitNexus's index can drift from `HEAD`. For the trial, reindex after every commit to the runner's working tree:

```bash
# Add to the runner's post-commit hook or pipeline-advance step
node ~/gitnexus/dist/cli.js index /docker/coherence-network/repo --incremental
```

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
