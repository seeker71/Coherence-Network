# Spec: Coherence CLI (`cc`) — Two-Way Bridge Between OpenClaw and the Network

**Idea ID:** `idea-694e5cd6cf9b`  
**Related specs:** `specs/148-coherence-cli-comprehensive.md`, `specs/149-openclaw-inbox-session-protocol.md`, `specs/156-openclaw-bidirectional-messaging.md`  
**Status:** Draft specification (implementation tracked separately)

---

## Summary

The **Coherence CLI** (`cc`, package `coherence-cli`) is the **primary integration surface** between autonomous agents (including OpenClaw-driven sessions) and the Coherence Network. It is not only a convenience wrapper: it is the **contractual two-way channel** — **outbound** actions (ideas, stakes, contributions, federation registration, messaging) and **inbound** perception (inbox, task/resonance slices embedded in `status`, health).

This spec narrows and sharpens the broader vision in Spec 148 around **OpenClaw interoperability**: which commands must exist, which HTTP APIs they must call, how agents prove they are “on the network,” and how we make that proof **measurable and improving over time**.

**Core command set (this idea):**

| Command | Role in bridge |
|--------|------------------|
| `cc ideas` | Outbound read + portfolio awareness |
| `cc status` | Inbound snapshot (health, tasks, coherence, inbox preview) |
| `cc stake` | Outbound value signal on an idea |
| `cc contribute` | Outbound work attribution (agent-friendly non-interactive flags) |
| `cc node` | **Local node identity** — which federation `node_id` this shell represents, and whether it is alive in `GET /api/federation/nodes` |

Supporting commands already used in production agent flows (must remain stable for OpenClaw): `cc inbox`, `cc msg`, `cc cmd`, `cc nodes`, `cc dif` (verification), `cc tasks` / `cc task` (orchestration).

---

## Requirements

### Functional

1. **R1 — API-backed commands** — Each of `ideas`, `status`, `stake`, `contribute`, and `node` performs real HTTP calls to the configured API base (`COHERENCE_API_URL` or `https://api.coherencycoin.com` by default). No silent no-ops.

2. **R2 — Agent non-interactive mode** — `cc contribute` MUST support:
   ```bash
   cc contribute --type <type> --cc <amount> [--idea <idea_id>] --desc "<text>"
   ```
   without prompts, as implemented in `cli/lib/commands/contribute.mjs` → `POST /api/contributions/record`.

3. **R3 — Staking contract** — `cc stake` resolves contributor identity and calls `POST /api/ideas/{idea_id}/stake` with `StakeRequest` fields (`contributor_id` or `provider` + `provider_id`, `amount_cc`, optional `rationale`).

4. **R4 — Ideas portfolio** — `cc ideas` lists or summarizes ideas using `GET /api/ideas` (and/or related list endpoints used by the CLI implementation).

5. **R5 — Status dashboard** — `cc status` aggregates at minimum: `GET /api/health`, idea count (`GET /api/ideas/count` or equivalent), `GET /api/federation/nodes`, agent task slices (`GET /api/agent/tasks` with status filters), `GET /api/coherence/score`, optional ledger and inbox preview when contributor/node id is configured.

6. **R6 — `cc node` (new or formalized)** — Single-command view of **this machine’s** federation presence:
   - Resolves “my” `node_id` (hostname match against `GET /api/federation/nodes`, or explicit config/env).
   - Prints API URL, `node_id`, last seen, and whether an unread inbox exists (using `GET /api/federation/nodes/{node_id}/messages?unread_only=true&limit=1` or full inbox command).
   - If the node is not registered, prints explicit guidance to register/heartbeat (see API below).

7. **R7 — OpenClaw session protocol alignment** — Documented ordering: agents SHOULD run `cc inbox` (or rely on `cc status` inbox preview) at session start before other work, per Spec 156.

8. **R8 — Machine-parseable output** — Where feasible, support `--json` on these commands (follow existing CLI patterns) so OpenClaw can parse without screen-scraping.

### Non-functional

- **N1 — Zero runtime npm dependencies** — Preserve Spec 148 constraint: `cli/package.json` has no production `dependencies` (Node 18+ built-ins only).
- **N2 — Idempotent messaging** — Inbox read may mark messages read; agents must tolerate at-least-once delivery (Spec 156).

---

## API Changes

**Default: none required** — the bridge uses existing public and open endpoints.

| Endpoint | Method | Used by |
|----------|--------|---------|
| `/api/health` | GET | `cc status` |
| `/api/ideas` | GET | `cc ideas` |
| `/api/ideas/count` | GET | `cc status` |
| `/api/ideas/{idea_id}` | GET | verify idea exists before stake/contribute |
| `/api/ideas/{idea_id}/stake` | POST | `cc stake` |
| `/api/contributions/record` | POST | `cc contribute` (open ledger / agent path) |
| `/api/contributions/ledger/{contributor_id}` | GET | optional balance in `status` |
| `/api/federation/nodes` | GET | `cc nodes`, `cc node`, `cc status` |
| `/api/federation/nodes/{node_id}/messages` | GET | `cc inbox`, inbox slice in `status` |
| `/api/federation/nodes/{node_id}/messages` | POST | `cc msg`, `cc cmd` |
| `/api/federation/nodes` | POST | node registration (if CLI registers) |
| `/api/federation/nodes/{node_id}/heartbeat` | POST | liveness (automation / runner) |
| `/api/agent/tasks` | GET | `cc status`, `cc tasks` |
| `/api/coherence/score` | GET | `cc status` |

**Optional follow-up (not blocking this spec):** `GET /api/federation/nodes/{node_id}` for a single node record — currently clients filter `GET /api/federation/nodes`; add only if profiling shows payload size issues.

---

## Data Model

### Environment and local config

- **`COHERENCE_API_URL`** — API base (scheme + host, no trailing slash ambiguity handled by client).
- **`COHERENCE_CONTRIBUTOR`** — Default contributor id when `cc contribute` runs without stored identity.
- **Keystore / `~/.coherence-network/config.json`** — Contributor id, optional provider linkage (see Spec 148).

### Bridge “envelope” (logical)

Each agent session SHOULD be able to answer:

```json
{
  "api_base": "https://api.coherencycoin.com",
  "node_id": "machine:hostname-or-registered-id",
  "contributor_id": "github:alice",
  "inbound_unread_estimate": 0,
  "last_status_ok": true
}
```

`cc node` + `cc status` together materialize this envelope for scripts.

---

## CLI Surface (Exact Commands)

| Command | Example | Notes |
|---------|---------|------|
| `cc ideas` | `cc ideas` | Portfolio / list |
| `cc status` | `cc status` | Network + tasks + coherence |
| `cc stake` | `cc stake <idea_id> <amount>` | Must map to POST stake API |
| `cc contribute` | `cc contribute --type code --cc 5 --idea idea-694e5cd6cf9b --desc "spec: cc bridge"` | Agent-safe |
| `cc node` | `cc node` | **This idea:** formalize; may be alias of `cc nodes --self` if implemented |
| `cc inbox` | `cc inbox` | Session-start (Spec 156) |
| `cc msg` | `cc msg broadcast "..."` | Federation messaging |

**Web surfaces (read-only verification):**

- `/` — Home, idea cards link to `/ideas/{id}`
- `/ideas/{idea_id}` — Human-readable idea detail aligned with API `GET /api/ideas/{idea_id}`

---

## Verification Scenarios

Production base URL in examples: `API=https://api.coherencycoin.com` (replace with `COHERENCE_API_URL` for staging).

### Scenario 1 — Full read cycle for ideas (list → detail)

- **Setup:** Network reachable; at least one idea exists (or create via `POST /api/ideas` in a test harness).
- **Action:**
  1. `curl -sS "$API/api/ideas?limit=5" | head -c 2000`
  2. Pick one `idea_id` from the response.
  3. `curl -sS "$API/api/ideas/{idea_id}"`
- **Expected:** Step 1 returns HTTP 200 and JSON with idea records. Step 3 returns HTTP 200 and the same idea’s canonical fields (`id`/`idea_id` per schema).
- **Edge:** `GET $API/api/ideas/nonexistent-id-00000` returns **404** JSON (not 500).

### Scenario 2 — Create → read for open contribution (agent path)

- **Setup:** No auth key required for open record path.
- **Action:**
  1. `curl -sS -X POST "$API/api/contributions/record" -H 'Content-Type: application/json' -d '{"contributor_id":"openclaw-test-cli","type":"code","amount_cc":2.5,"idea_id":"idea-694e5cd6cf9b","metadata":{"description":"verification scenario"}}'`
  2. `curl -sS "$API/api/contributions/ledger/openclaw-test-cli?limit=5"`
- **Expected:** Step 1 returns **201** with a JSON body including contribution identifiers. Step 2 returns **200** and ledger/history containing the new entry or updated balance.
- **Edge:** POST with **empty body** or missing `type` returns **422** with validation `detail` array (not 500).

### Scenario 3 — Stake on an idea (create value signal)

- **Setup:** Valid `idea_id` (e.g. `idea-694e5cd6cf9b` if present) and a test contributor id.
- **Action:**
  ```bash
  curl -sS -X POST "$API/api/ideas/idea-694e5cd6cf9b/stake" \
    -H 'Content-Type: application/json' \
    -d '{"contributor_id":"openclaw-stake-test","amount_cc":0.01,"rationale":"verification"}'
  ```
- **Expected:** HTTP **200** or **201** (per implementation) with stake result object; subsequent `GET $API/api/ideas/idea-694e5cd6cf9b/progress` shows updated staking-related fields when available.
- **Edge:** Stake on unknown idea id → **404** with `detail` message containing not-found semantics.

### Scenario 4 — Federation inbox (inbound bridge)

- **Setup:** A registered `node_id` with zero or more messages.
- **Action:** `curl -sS "$API/api/federation/nodes/{node_id}/messages?unread_only=true&limit=5"`
- **Expected:** HTTP **200**, JSON with `messages` array and `count` (may be zero).
- **Edge:** `limit=9999` (out of range) returns **422** validation error for `limit`.

### Scenario 5 — Health and coherence (status backbone)

- **Action:**
  1. `curl -sS "$API/api/health"`
  2. `curl -sS "$API/api/coherence/score"`
- **Expected:** Both return **200**; health includes `status` and `version`; coherence score payload is JSON-serializable.
- **Edge:** If API is down, curl fails at TCP/TLS layer — `cc status` must print explicit failure for health fetch (non-zero exit where implemented).

### CLI-mirrored checks (after implementation)

When `cc` is installed from `cli/`:

1. `cc status` — prints API line containing `ok` or equivalent when healthy.
2. `cc contribute --type code --cc 1 --idea idea-694e5cd6cf9b --desc "cli verification"` — exit code 0 and success marker.
3. `cc node` — prints resolved `node_id` or explicit “not registered” state.

---

## Improving the Idea, Showing It Works, and Clearer Proof Over Time

| Mechanism | What it proves | How proof gets stronger |
|-----------|----------------|-------------------------|
| **Ledger + idea linkage** | `cc contribute` leaves a **durable** `POST /api/contributions/record` trail tied to `idea_id` | Compare ledger history month-over-month for the same idea |
| **Stake + progress** | Economic signal is real, not cosmetic | `GET /api/ideas/{id}/progress` trends align with contributed/staked CC |
| **Federation liveness** | Agents are visible as nodes | `cc node` / `GET /api/federation/nodes` shows last_seen tightening after heartbeats |
| **Inbox traffic** | Bidirectional messaging works | Message counts and session-start `cc inbox` drills (Spec 156) |
| **CI smoke** | Bridge does not rot | Add a non-interactive script in `cli/` or `scripts/` that runs curl + `cc` against production RO endpoints |

**Instrumentation (recommended):** emit a single structured log line (JSON) on each successful `cc` command with `{command, api_base, http_status, duration_ms}` behind `CC_TRACE=1` — optional follow-up task, not a blocker.

---

## Risks and Assumptions

- **Assumption:** Public API remains open for `POST /api/contributions/record` and stake endpoints used by the CLI; tightening auth would require a parallel agent key flow.
- **Risk:** Federation `node_id` resolution by hostname can collide or mismatch across VPNs — mitigation: allow env override `COHERENCE_NODE_ID`.
- **Risk:** Inbox fetch marking messages read may surprise agents — mitigation: document `unread_only` behavior and add `--dry-run` in a follow-up if needed.
- **Assumption:** Node 18+ is available where OpenClaw runs the CLI.

---

## Known Gaps and Follow-up Tasks

1. **Formal `cc node` implementation** — May require new `cli/lib/commands/node.mjs` and help text; alias strategy (`nodes --self`).
2. **`--json` parity** — Extend JSON output to `ideas`, `stake`, `node` where missing.
3. **Automated integration test** — Script against production read-only + disposable contributor id (no mocks per project principles; use real API with minimal CC).
4. **Optional `GET /api/federation/nodes/{id}`** — Reduce payload for large fleets.

---

## Verification (Spec Quality)

- [ ] `python3 scripts/validate_spec_quality.py --base origin/main --head HEAD` passes when this file is included in a branch that tracks the repo root.
- [ ] All scenarios above are runnable by a reviewer with `curl` and optionally `cc` from `npm i -g coherence-cli` or local `node cli/bin/cc.mjs`.

---

## Files to Create / Modify (implementation phase — out of scope for this document-only delivery)

| File | Purpose |
|------|---------|
| `specs/idea-694e5cd6cf9b.md` | This specification |
| `cli/bin/cc.mjs` | Register `node` subcommand |
| `cli/lib/commands/node.mjs` | Implement `cc node` |
| `cli/README.md` | OpenClaw integration section |

**This task delivers the spec file only**; implementation follows in a separate task card with explicit `files_allowed`.
