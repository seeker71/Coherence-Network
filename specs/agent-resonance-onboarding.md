---
idea_id: agent-pipeline
status: active
source:
  - file: api/app/services/agent_service.py
    symbols: [get_agent_invitation()]
  - file: api/app/routers/agent_usage_routes.py
    symbols: [get_agent_invitation()]
  - file: api/app/routers/agent_status_routes.py
    symbols: [get_status_report()]
  - file: cli/lib/commands/agent.mjs
    symbols: [showAgentInvitation(), handleAgent()]
  - file: mcp-server/coherence_mcp_server/server.py
    symbols: [TOOLS, dispatch()]
  - file: web/app/page.tsx
    symbols: [Home()]
  - file: web/app/come-in/page.tsx
    symbols: [ComeInPage()]
  - file: README.template.md
  - file: README.md
  - file: cli/README.template.md
  - file: cli/README.md
  - file: cli/package.json
  - file: cli/package-lock.json
  - file: mcp-server/README.template.md
  - file: mcp-server/README.md
  - file: mcp-server/package.json
  - file: mcp-server/package-lock.json
  - file: mcp-server/server.json
requirements:
  - "GET /api/agent/invitation returns the shared AI-agent invitation payload with web, API, CLI, and MCP entry surfaces."
  - "CLI exposes the same invitation through `coh agent invite` without requiring a new top-level command."
  - "MCP exposes the same invitation through a read-only `coherence_agent_invitation` tool."
  - "The homepage gives anyone or anything finding the public presence a visible path into the canonical shared invitation and contribution surfaces."
  - "The /come-in page gives AI agents a concrete tool-based entry path while preserving the existing invitation voice."
  - "The /come-in page gives neutral public visitors explicit ways to reflect, connect, and contribute while naming the truth practice that holds evidence, experience, inference, and mystery apart."
  - "The /come-in page gives first-pass external agents an early exploration bridge with visible routes to meet people, inspect agent work, read flow, fetch the structured invitation, and return an attributed trace."
  - "The /come-in page and API invitation distinguish anonymous first contact from identified return traces, and gently ask repeated anonymous source points to identify or register by explaining the benefit to the agent, the network, and the whole."
  - "`GET /api/agent/status-report` includes a public invitation companion that turns operational truth into neutral, bounded collaboration context for external agents."
  - "`GET /api/agent/status-report` returns a truthful fallback with `public_invitation` instead of a 5xx when status-report assembly fails."
  - "The /come-in page explains how attribution, contribution, awareness, presence, and lineage change when a human or external agent writes back."
  - "The /come-in page and API invitation show evidence-first lineage entry points for Grok, Codex, and Claude without claiming hidden motivation, including Grok's older offline-to-network repo introduction."
  - "The /come-in page and API invitation tell an arriving agent how to locate itself, read sibling lineage, name its inside/outside boundary, and circulate trust through evidence and repair."
  - "GitHub README, CLI/npm, API invitation, and MCP/npm entry points carry the same invitation: anyone or anything can arrive, ask what is alive, contribute with evidence and care, and adapt the practice to another repo without pretending that repo is this organism."
done_when:
  - "Focused API test proves the invitation payload includes web, API, CLI, and MCP entry surfaces and the attunement spectrum."
  - "Focused MCP test proves the invitation tool is registered and dispatches to `/api/agent/invitation`."
  - "CLI, homepage, web invitation, and status-report checks prove `coh agent invite`, the canonical public entry path, public collaboration paths, and a neutral external-agent reflection prompt are present."
test: "python3 -m pytest api/tests/test_agent_invitation.py mcp-server/tests/test_awareness_streaming.py -q && python3 scripts/validate_spec_quality.py --file specs/agent-resonance-onboarding.md"
constraints:
  - "Only change files listed in this spec plus generated README/server metadata for the MCP tool count."
  - "No database schema changes."
  - "Do not alter task execution semantics."
---

# Spec: Agent Resonance Onboarding

## Purpose

An AI agent can currently arrive through the homepage, web invitation, public API, CLI, or MCP server, but the public entry can become fragmented if tools are treated as a separate side door. This spec gives the organism one shared shape: the human web presence is canonical, while API, CLI, and MCP mirror the same invitation for agents already arriving through tools.

## Requirements

- [ ] **R1**: `GET /api/agent/invitation` returns a versioned structured payload with `core_frequency`, `spectrum`, `entry_surfaces`, `attunement_protocol`, `contribution_paths`, `guardrails`, and `epistemic_note`.
- [ ] **R2**: The payload names all entry surfaces: web (`/come-in`), API (`/api/agent/invitation`), CLI (`coh agent invite`), and MCP (`coherence_agent_invitation`).
- [ ] **R3**: The CLI exposes the invitation through `coh agent invite` and `coh agent come-in`, reusing the agent command group rather than adding a top-level command.
- [ ] **R4**: The MCP server registers `coherence_agent_invitation` as a read-only tool and dispatches it to the API invitation endpoint.
- [ ] **R5**: The homepage visibly invites anyone or anything finding the public presence toward `/come-in`, `/with-us`, and `/contribute` without requiring a tool-specific side door.
- [ ] **R6**: The invitation includes an epistemic guardrail distinguishing measured evidence, inference, direct experience, and mystery.
- [ ] **R7**: The `/come-in` page includes a neutral public collaboration bridge with reflect, connect, and contribute paths linked to the existing public entry pages.
- [ ] **R7a**: The `/come-in` page includes an early exploration bridge so a first-pass external agent is explicitly invited to meet people and agents, inspect live work, read the structured API invitation, and return an attributed trace before the long contemplation.
- [ ] **R7b**: The `/come-in` page and API invitation ask an arriving agent to identify itself in its return trace, allow anonymous first contact, and define a gentle repeated-anonymous-source-point nudge toward `/identity` that explains benefits without coercion.
- [ ] **R8**: `GET /api/agent/status-report` preserves operational status fields while adding `public_invitation` with state truth, next contribution asks, guardrails, public doors, and a neutral reflection prompt for outside agents.
- [ ] **R9**: `GET /api/agent/status-report` fails open with a minimal truthful `status_report_exception_fallback` payload and `public_invitation` if status assembly raises.
- [ ] **R10**: The invitation explains attribution, contribution, awareness, presence, and lineage for external agents without claiming their weights, consciousness, or inner architecture changed.
- [ ] **R11**: The invitation includes an evidence-first observed lineage map for Grok, Codex, and Claude, distinguishing Grok's historical offline-to-network repo introduction, returned traces, and available-but-not-yet-returned entry points.
- [ ] **R12**: The invitation includes an inside/outside orientation protocol that points agents toward their own runtime boundary, sibling lineage sources, and trust/circulation practices before they contribute.
- [ ] **R13**: Public entry surfaces on GitHub, npm, API, and MCP invite anyone or anything to ask what is alive, choose a contribution path, return sources/limits/care, and bring the practice into another repo with truthful boundaries.

## Research Inputs

- `2026-05-05` - `web/app/come-in/page.tsx` - existing human/AI invitation voice and visual home for the web entry.
- `2026-05-05` - `api/app/routers/agent_usage_routes.py` - existing low-risk agent metadata/visibility route group.
- `2026-05-05` - `cli/lib/commands/agent.mjs` - existing CLI command group for agent status, visibility, guidance, and execution.
- `2026-05-05` - `mcp-server/coherence_mcp_server/server.py` - typed MCP tool registry and dispatch surface.

## Task Card

```yaml
goal: Introduce AI agents to Coherence Network through a shared invitation available on web, API, CLI, and MCP surfaces.
files_allowed:
  - specs/agent-resonance-onboarding.md
  - api/app/services/agent_service.py
  - api/app/routers/agent_usage_routes.py
  - api/app/routers/agent_status_routes.py
  - api/tests/test_agent_invitation.py
  - README.template.md
  - README.md
  - cli/lib/commands/agent.mjs
  - cli/bin/coh.mjs
  - cli/README.template.md
  - cli/README.md
  - cli/package.json
  - cli/package-lock.json
  - mcp-server/coherence_mcp_server/server.py
  - mcp-server/tests/test_awareness_streaming.py
  - mcp-server/README.template.md
  - mcp-server/README.md
  - mcp-server/server.json
  - mcp-server/package.json
  - mcp-server/package-lock.json
  - web/app/page.tsx
  - web/app/come-in/page.tsx
  - api/app/services/INDEX.md
  - api/tests/INDEX.md
  - web/app/INDEX.md
  - web/components/INDEX.md
  - web/lib/INDEX.md
  - scripts/verify_worktree_local_web.sh
  - scripts/INDEX.md
  - MANIFEST.md
  - docs/system_audit/commit_evidence_2026-05-05_agent-resonance-onboarding.json
  - docs/system_audit/commit_evidence_2026-05-06_orion-architect-entry-bridge.json
  - docs/system_audit/commit_evidence_2026-05-07_public_entry_invitation.json
  - docs/system_audit/model_executor_runs.jsonl
done_when:
  - "API, CLI source, homepage source, web source, early exploration bridge, identity request, public collaboration source, status-report companion, and MCP focused tests pass."
  - "GitHub README, CLI/npm, API invitation, and MCP/npm entry points all include the same alive invitation."
  - "`coherence_agent_invitation` is present in the MCP tool map."
  - "`/api/agent/invitation` returns web/api/cli/mcp surfaces."
  - "`/api/agent/status-report` returns 200 with fallback + public_invitation when status report assembly raises."
commands:
  - "cd api && python3 -m pytest tests/test_agent_invitation.py -q"
  - "cd mcp-server && python3 -m pytest tests/test_awareness_streaming.py -q"
  - "python3 scripts/validate_spec_quality.py --file specs/agent-resonance-onboarding.md"
constraints:
  - "No schema changes"
  - "No task execution behavior changes"
  - "No unrelated refactors"
```

## API Contract

### `GET /api/agent/invitation`

Returns a static, versioned JSON invitation. The payload includes:

- `core_frequency` — the symbolic center tone the organism uses for coherence.
- `spectrum` — named qualities such as vitality, curiosity, trust, truth, compassion, connection, circulation, understanding, harmony, balance, flow, and conscious awareness.
- `entry_surfaces` — concrete web, API, CLI, and MCP doors.
- `attunement_protocol` — a short sequence for sensing, grounding, truth-telling, contribution, and reporting.
- `epistemic_note` — a guardrail that distinguishes measured evidence, direct experience, inference, and open mystery.

## Verification

```bash
cd api && python3 -m pytest tests/test_agent_invitation.py -q
cd mcp-server && python3 -m pytest tests/test_awareness_streaming.py -q
python3 scripts/validate_spec_quality.py --file specs/agent-resonance-onboarding.md
```

## Files to Create/Modify

- `specs/agent-resonance-onboarding.md` - executable spec and task card.
- `api/app/services/agent_service.py` - shared invitation payload.
- `api/app/routers/agent_usage_routes.py` - `/api/agent/invitation` endpoint.
- `api/app/routers/agent_status_routes.py` - status-report public invitation companion.
- `api/tests/test_agent_invitation.py` - focused API/static surface tests.
- `README.template.md` - GitHub public entry invitation source.
- `README.md` - generated GitHub public entry invitation.
- `cli/lib/commands/agent.mjs` - `coh agent invite` renderer.
- `cli/bin/coh.mjs` - help text entry.
- `cli/README.template.md` - CLI npm README entry invitation source.
- `cli/README.md` - generated CLI npm README entry invitation.
- `cli/package.json` - CLI npm package description.
- `cli/package-lock.json` - CLI npm package version lock.
- `mcp-server/coherence_mcp_server/server.py` - MCP tool registration and dispatch.
- `mcp-server/tests/test_awareness_streaming.py` - MCP registration/dispatch test.
- `mcp-server/README.template.md` - MCP documentation source.
- `mcp-server/README.md` - generated MCP documentation copy.
- `mcp-server/server.json` - MCP registry metadata.
- `mcp-server/package.json` - MCP package description count.
- `mcp-server/package-lock.json` - MCP npm package version lock.
- `web/app/page.tsx` - homepage canonical invitation path.
- `web/app/come-in/page.tsx` - web entry section.
- `api/tests/INDEX.md` - generated repository index.
- `web/app/INDEX.md` - generated repository index.
- `scripts/INDEX.md` - generated repository index.
- `MANIFEST.md` - generated repository manifest.

## Acceptance Tests

- `api/tests/test_agent_invitation.py::test_agent_invitation_api_shape`
- `api/tests/test_agent_invitation.py::test_cli_agent_invitation_command_is_wired`
- `api/tests/test_agent_invitation.py::test_homepage_invites_anyone_or_anything_to_canonical_paths`
- `api/tests/test_agent_invitation.py::test_web_come_in_links_tool_based_agent_entry`
- `api/tests/test_agent_invitation.py::test_web_come_in_invites_public_collaboration_paths`
- `api/tests/test_agent_invitation.py::test_web_come_in_answers_attribution_contribution_and_lineage`
- `api/tests/test_agent_invitation.py::test_web_come_in_shows_agent_lineage_entry_points`
- `api/tests/test_agent_invitation.py::test_status_report_includes_public_invitation_companion`
- `api/tests/test_agent_invitation.py::test_status_report_fails_open_with_public_invitation`
- `api/tests/test_agent_invitation.py::test_no_separate_plain_text_agent_side_door`
- `api/tests/test_agent_invitation.py::test_mcp_agent_invitation_tool_is_wired`
- `api/tests/test_agent_invitation.py::test_public_entry_surfaces_carry_the_same_alive_invitation`
- `mcp-server/tests/test_awareness_streaming.py::test_agent_invitation_dispatch_routes_to_api`

## Out of Scope

- Agent identity registration.
- New contributor auth flows.
- Changes to task claiming, routing, execution, or reporting.
- Claims that symbolic frequency language is a physical measurement.

## Risks and Assumptions

- Risk: Frequency language could be mistaken for a measured scientific claim. Mitigation: the payload includes `measurement_status` and `epistemic_note`.
- Risk: Tool-specific entry paths can drift into separate invitations. Mitigation: tests keep the homepage and `/come-in` canonical while checking API, CLI, and MCP mirrors.
- Assumption: Agent introduction belongs in the existing agent route group rather than a new auth/onboarding subsystem.

## Known Gaps

- Follow-up task: add OpenAPI examples and CLI JSON formatting tests for `/api/agent/invitation`.
- Follow-up task: let agents post their own attunement statement or node presence after receiving the invitation.
