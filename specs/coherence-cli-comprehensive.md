---
idea_id: user-surfaces
status: done
source:
  - file: cli/bin/cc.mjs
    symbols: [CLI entry point]
  - file: cli/lib/commands/ideas.mjs
    symbols: [ideas commands]
  - file: cli/lib/commands/tasks.mjs
    symbols: [task commands]
  - file: cli/lib/commands/nodes.mjs
    symbols: [node commands]
requirements:
  - "— Zero Runtime Dependencies: The package must not have any `dependencies` in `package.json`. It must use native Node.js modules (e.g., `fs`, `path`, "
  - "— Identity-First Onboarding: Users can participate without a central account. Onboarding (`identity setup`) guides the user through linking existing "
  - "— Core Command Set (15 Commands): The CLI must support exactly 15 core functional commands (including aliases) that cover the full lifecycle of an idea."
  - "— Public API Integration: By default, the CLI interacts with `https://api.coherencycoin.com` but allows override via `COHERENCE_API_URL`."
  - "— Idea & Spec Traceability: Commands to browse ideas (`ideas`), view details (`idea`), list specs (`specs`), and view spec details (`spec`) with ROI"
  - "— Contribution Lifecycle: Support for `share` (new idea), `stake` (investing CC), `fork` (branching ideas), and `contribute` (recording work)."
  - "— Network Observability: Commands for `status` (health), `resonance` (live activity), and `nodes` (federation status)."
  - "— Messaging & Inbox: Secure communication between nodes/contributors via `msg` and `inbox`."
done_when:
  - "CLI supports the 15 core commands listed in this spec."
  - "`npm ls --production` in `cli/` returns empty (zero dependencies)."
  - "`identity setup` successfully guides a new user to a valid local identity."
test: "cd cli && npm pack --dry-run"
constraints:
  - "No external runtime dependencies allowed."
  - "Must support Node.js >= 18.0.0."
---

> **Parent idea**: [user-surfaces](../ideas/user-surfaces.md)
> **Source**: [`cli/bin/cc.mjs`](../cli/bin/cc.mjs) | [`cli/lib/commands/ideas.mjs`](../cli/lib/commands/ideas.mjs) | [`cli/lib/commands/tasks.mjs`](../cli/lib/commands/tasks.mjs) | [`cli/lib/commands/nodes.mjs`](../cli/lib/commands/nodes.mjs)

# Coherence Network CLI (coherence-cli) Comprehensive Feature Spec

## Purpose

The `coherence-cli` (published as `npm i -g coherence-cli`) is the primary terminal interface for the Coherence Network. It enables developers, researchers, and contributors to interact with the network's decentralized intelligence platform without a web browser. It formalizes identity-first onboarding, idea tracing, and value attribution with zero runtime dependencies to ensure maximum portability and minimal friction.

## Requirements

- [ ] **R1 — Zero Runtime Dependencies** — The package must not have any `dependencies` in `package.json`. It must use native Node.js modules (e.g., `fs`, `path`, `crypto`, `https`) and the built-in `fetch` API (Node 18+).
- [ ] **R2 — Identity-First Onboarding** — Users can participate without a central account. Onboarding (`identity setup`) guides the user through linking existing third-party identities (GitHub, Discord, etc.) which are stored locally or recorded on-chain/on-graph.
- [ ] **R3 — Core Command Set (15 Commands)** — The CLI must support exactly 15 core functional commands (including aliases) that cover the full lifecycle of an idea.
- [ ] **R4 — Public API Integration** — By default, the CLI interacts with `https://api.coherencycoin.com` but allows override via `COHERENCE_API_URL`.
- [ ] **R5 — Idea & Spec Traceability** — Commands to browse ideas (`ideas`), view details (`idea`), list specs (`specs`), and view spec details (`spec`) with ROI and coherence scores.
- [ ] **R6 — Contribution Lifecycle** — Support for `share` (new idea), `stake` (investing CC), `fork` (branching ideas), and `contribute` (recording work).
- [ ] **R7 — Network Observability** — Commands for `status` (health), `resonance` (live activity), and `nodes` (federation status).
- [ ] **R8 — Messaging & Inbox** — Secure communication between nodes/contributors via `msg` and `inbox`.

## Research Inputs (Required)

- `2026-03-24` - [Coherence Network CLI README](cli/README.md) - Current implemented features and usage.
- `2026-03-24` - [Spec 147: coherence-cli Binary Conflict](specs/coherence-cli-macos-cc-binary-conflict.md) - Context on binary naming (`cc`, `coh`, `coherence`).
- `2026-03-24` - [Spec 048: Contributions API](specs/contributions-api.md) - Backend contract for recording contributions.

## Task Card (Required)

```yaml
goal: Formalize the coherence-cli with 15 core commands, zero dependencies, and identity-first onboarding.
files_allowed:
  - cli/package.json
  - cli/bin/cc.mjs
  - cli/lib/commands/*.mjs
  - cli/README.md
  - cli/README.template.md
done_when:
  - CLI supports the 15 core commands listed in this spec.
  - `npm ls --production` in `cli/` returns empty (zero dependencies).
  - `identity setup` successfully guides a new user to a valid local identity.
commands:
  - cd cli && npm pack --dry-run
  - node cli/bin/cc.mjs help
constraints:
  - No external runtime dependencies allowed.
  - Must support Node.js >= 18.0.0.
```

## API Contract (if applicable)

The CLI consumes the existing Public API. No new API changes are required by this spec, but the CLI must adhere to:
- `GET /api/ideas`
- `GET /api/ideas/{id}`
- `POST /api/ideas`
- `POST /api/ideas/{id}/stake`
- `POST /api/ideas/{id}/fork`
- `GET /api/specs`
- `GET /api/specs/{id}`
- `POST /api/contributions`
- `GET /api/identity/lookup/{provider}/{id}`
- `GET /api/health`

## Data Model (if applicable)

Local configuration stored in `~/.coherence-network/config.json`:

```json
{
  "api_url": "https://api.coherencycoin.com",
  "identity": {
    "active_id": "contributor_id",
    "linked_providers": {
      "github": "username",
      "discord": "id"
    }
  },
  "preferences": {
    "output_format": "text|json"
  }
}
```

## Files to Create/Modify

- `specs/coherence-cli-comprehensive.md` — this spec.
- `cli/package.json` — metadata and versioning.
- `cli/bin/cc.mjs` — main entry point and command router.
- `cli/lib/commands/ideas.mjs` — implementation of idea commands.
- `cli/lib/commands/identity.mjs` — implementation of identity commands.
- `cli/lib/commands/contribute.mjs` — contribution recording.
- `cli/lib/commands/specs.mjs` — spec browsing.
- `cli/lib/commands/status.mjs` — network and resonance status.
- `cli/lib/commands/nodes.mjs` — federation and messaging.

## Acceptance Tests

Manual Validation Flow:

- **Identity Flow**:
  ```bash
  node cli/bin/cc.mjs identity setup
  # Follow prompts to link a mock provider
  node cli/bin/cc.mjs identity
  # Confirm identity is persisted in ~/.coherence-network/config.json
  ```
- **Browsing Flow**:
  ```bash
  node cli/bin/cc.mjs ideas
  # Confirm a table of ideas is displayed
  node cli/bin/cc.mjs idea <valid_id>
  # Confirm detailed scores and gaps are shown
  ```
- **Contribution Flow**:
  ```bash
  node cli/bin/cc.mjs share --name "Spec Validation Test"
  # Confirm idea is created
  node cli/bin/cc.mjs contribute --idea <id> --desc "Test contribution"
  # Confirm success
  ```
- **Zero-Dependency Check**:
  ```bash
  cd cli && npm ls --production
  # Confirm output is empty (excluding the package itself)
  ```

## Concurrency Behavior

N/A — CLI is a single-user process. Local config file is updated using atomic write-and-rename pattern to prevent corruption if the process is killed during a write.

## Verification

```bash
# Verify zero dependencies
cd cli && (grep "dependencies" package.json -A 5 | grep -v "devDependencies" || true)

# Verify help output contains the 15 core commands
node cli/bin/cc.mjs help
```

## Out of Scope

- Native GUI components (CLI remains strictly text-based).
- Built-in Node.js version management.
- Multi-user local profiles (one active identity per user account).

## Risks and Assumptions

- **Risk**: Dependency on Public API availability.
- **Mitigation**: CLI supports `COHERENCE_API_URL` to point to local or alternative nodes.
- **Assumption**: Users have Node 18+ installed.

## Known Gaps and Follow-up Tasks

- **E2E Testing**: Automated integration tests against a mock API or staging environment. Follow-up task: `task_cli_e2e_tests`.
- **Local Persistence**: Full offline-first mode where contributions are queued until connectivity is restored. Follow-up task: `task_cli_offline_mode`.

## Failure/Retry Reflection

- Failure mode: `identity setup` fails to reach the API for lookup.
- Blind spot: Network connectivity or firewall issues during onboarding.
- Next action: Allow offline identity setup with later verification.

## Core Command List (15)

1.  `ideas` — Browse the portfolio ranked by ROI.
2.  `idea` — View detailed scores, gaps, and lineage for a specific idea.
3.  `specs` — List feature specifications and their current status.
4.  `spec` — View full specification details and implementation status.
5.  `share` — Submit a new idea to the network.
6.  `stake` — Invest CC (Coherence Credits) into an idea you believe in.
7.  `fork` — Branch an existing idea to take it in a new direction.
8.  `contribute` — Record work (code, docs, review) against an idea/spec.
9.  `resonance` — Real-time view of network activity and "vibe."
10. `status` — Check network health, node count, and your identity status.
11. `identity` — Manage your linked accounts and identities.
12. `nodes` — List and discover other nodes in the federation.
13. `msg` — Send secure messages to other nodes or contributors.
14. `inbox` — Read and manage incoming messages.
15. `help` — Comprehensive help and command documentation.

## Improving the idea, showing it works, and clearer proof over time

| Mechanism | What it proves | How it gets clearer |
|-----------|----------------|---------------------|
| **CLI self-tracking** | The CLI project itself is an idea in the network. | Use `cc contribute` to record every commit to the CLI. The `cc status` command will eventually show the CLI's own coherence score. |
| **Identity ubiquity** | That users can bring *any* identity without friction. | Incrementally add support for more providers (from 37 to 50+) and show usage statistics in `cc status`. |
| **Proof of Resonance** | That the network is "alive" and not just a static database. | `cc resonance` will evolve from a simple log to a real-time stream of high-value contributions and staking events. |
| **ROI-Driven Browsing** | That the ranking algorithm identifies value. | Over time, ideas with higher ROI in `cc ideas` should correlate with higher actual payouts and implementation success. |
