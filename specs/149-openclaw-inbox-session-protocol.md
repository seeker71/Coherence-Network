# Spec 149: OpenClaw inbox at session start (bidirectional messaging baseline)

## Purpose

OpenClaw agents that install the Coherence Network skill must **poll the federation inbox at session start** (`cc inbox`) before other work, so node-to-node messages (`cc msg`, `cc cmd`, or API posts) are observed on the next session. This spec locks the **documentation contract**, the **CLI↔API mapping**, and **automated tests** that prove the behavior. Later phases (webhook push, WebSocket bridge) build on this baseline.

## Goal

- Make the “inbox first, then status” session protocol explicit in the published OpenClaw skill (`skills/coherence-network/SKILL.md`).
- Prove with pytest that (1) the skill text encodes the ordered steps and (2) the API supports create → read for federation messages (the same data `cc inbox` displays when the CLI can resolve a node).

## Files

| File | Role |
|------|------|
| `skills/coherence-network/SKILL.template.md` | Source for generated skill; session protocol section |
| `skills/coherence-network/SKILL.md` | Generated/published skill (must stay aligned with template; regenerate via `python3 scripts/build_readmes.py`) |
| `api/tests/test_openclaw_inbox_session_protocol.py` | Pytest: skill contract + federation inbox API |

## API Contract (relevant endpoints)

### `POST /api/federation/nodes/{node_id}/messages`

- **Path `node_id`**: sender node (stored as `from_node`).
- **Body** (`NodeMessage`): `from_node` (required by schema), `to_node` (optional; `null` = broadcast), `type`, `text`, `payload`.
- **201**: Returns created message including `id`, `timestamp`.

### `GET /api/federation/nodes/{node_id}/messages`

- **Query**: `unread_only` (default `true`), `since`, `limit` (1–200).
- **200**: `{ "node_id", "messages": [...], "count": N }`. Marks returned messages as read for `node_id`.

### CLI (reference)

- `cc inbox` / `cc messages` → `readMessages` in `cli/lib/commands/nodes.mjs` → `GET .../messages?unread_only=false&limit=20` (after resolving `node_id` via `GET /api/federation/nodes` and local hostname). Unread lines are labeled in the CLI output.

## Acceptance Criteria

1. `SKILL.md` contains heading `## OpenClaw session protocol (bidirectional messaging)`.
2. Under “Start of every session (in order):”, step **1** is `cc inbox` and step **2** is `cc status` (in that order).
3. The skill text references `GET /api/federation/nodes/{node_id}/messages` with query parameters matching `readMessages` in `cli/lib/commands/nodes.mjs` (`unread_only=false`, `limit=20`).
4. Pytest demonstrates: message sent from node B to node A appears in A’s GET inbox; invalid POST returns 422; unread-only read hides messages after first fetch.

## Verification Scenarios

### Scenario 1 — Skill document encodes session-start order

- **Setup:** Repo checkout with `skills/coherence-network/SKILL.md` from `main` (or branch under test).
- **Action:** `rg -n "OpenClaw session protocol" skills/coherence-network/SKILL.md` then inspect the numbered list under “Start of every session”.
- **Expected:** First list item includes `` `cc inbox` ``; second includes `` `cc status` ``; the line for inbox appears **before** the line for status.
- **Edge:** If a contributor runs `scripts/build_readmes.py --check` after editing only `SKILL.md` without the template, the check fails — **always edit `SKILL.template.md` first**, then regenerate.

### Scenario 2 — Full create → read cycle (API; mirrors inbox data path)

- **Setup:** Clean test DB (pytest autouse fixture); register two nodes `node_a` and `node_b` via `POST /api/federation/nodes`.
- **Action:**
  ```bash
  curl -sS -X POST "$API/api/federation/nodes/node_b/messages" \
    -H "Content-Type: application/json" \
    -d '{"from_node":"node_b","to_node":"node_a","type":"text","text":"qa-openclaw-inbox-149","payload":{}}'
  curl -sS "$API/api/federation/nodes/node_a/messages?unread_only=true&limit=20"
  ```
- **Expected:** POST returns **201** with a JSON body containing `"id"` starting with `msg_` and the same `text`. GET returns `count >= 1` and a message with `text` equal to `qa-openclaw-inbox-149`.
- **Edge:** Repeat GET with `unread_only=true` — after the first GET, messages are marked read; second GET may return **zero** unread rows (proves read semantics, not duplicate delivery).

### Scenario 3 — Error handling on bad POST body

- **Setup:** Same as scenario 2 (nodes registered).
- **Action:**
  ```bash
  curl -sS -o /dev/stderr -w "%{http_code}" -X POST "$API/api/federation/nodes/node_b/messages" \
    -H "Content-Type: application/json" \
    -d '{"to_node":"node_a","type":"text","text":"missing-from-node","payload":{}}'
  ```
  (Body omits required `from_node` per `NodeMessage`.)
- **Expected:** HTTP **422** with FastAPI validation error (not 500).
- **Edge:** POST to a non-existent path like `/api/federation/nodes//messages` — expect **404** or router rejection (not success).

### Scenario 4 — Missing recipient node (no prior registration)

- **Setup:** No `node_c` registered.
- **Action:** `GET /api/federation/nodes/node_c/messages?unread_only=true&limit=20`
- **Expected:** HTTP **200**, `"messages": []`, `"count": 0` (inbox is empty; API does not require prior registration to query).
- **Edge:** Sending **to** an unregistered node still stores the message; the recipient can register later and then poll — **operational** proof is environment-specific; automated test focuses on happy path + validation errors above.

### Scenario 5 — Production smoke (reviewer)

- **Setup:** `API=https://api.coherencycoin.com`
- **Action:** `curl -sS "$API/api/health" | jq '{status,version}'` then `curl -sS -o /dev/null -w "%{http_code}" "$API/api/federation/nodes"`
- **Expected:** Health JSON with `"status":"ok"` (or documented healthy field); federation nodes endpoint returns **200** (list may be empty).
- **Edge:** If federation is restricted, document response; inbox tests still pass locally via pytest.

## Research Inputs

- `2025+` — [OpenClaw / AgentSkills SKILL.md pattern](https://agentskills.io) — portable skill instructions for session behavior.
- `2025+` — Internal: `cli/lib/commands/nodes.mjs` (`readMessages`, `sendMessage`) — authoritative CLI mapping.

## Task Card

```yaml
goal: Lock OpenClaw session-start inbox protocol in the skill and test skill text + federation inbox API.
files_allowed:
  - skills/coherence-network/SKILL.template.md
  - skills/coherence-network/SKILL.md
  - specs/149-openclaw-inbox-session-protocol.md
  - api/tests/test_openclaw_inbox_session_protocol.py
done_when:
  - pytest api/tests/test_openclaw_inbox_session_protocol.py passes
  - SKILL.md contains OpenClaw session protocol with cc inbox before cc status
commands:
  - cd api && .venv/bin/pytest -v tests/test_openclaw_inbox_session_protocol.py
  - python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
constraints:
  - Do not weaken existing tests; add only this spec and test file plus skill template/synced SKILL.
```

## Verification (CI)

```bash
cd /Users/ursmuff/source/Coherence-Network/api && .venv/bin/pytest -v tests/test_openclaw_inbox_session_protocol.py
```

## Out of Scope

- OpenClaw gateway webhook receiver (Phase 2).
- WebSocket bridge (Phase 3).
- Changing `cc inbox` default `unread_only` flag (would be a separate CLI spec).

## Risks and Assumptions

- **Assumption:** Reviewers run pytest locally or rely on CI; production curl scenarios need a valid `API` base URL.
- **Risk:** Skill drift if `SKILL.md` is edited without `SKILL.template.md` — mitigated by `scripts/build_readmes.py --check` in maintainers’ workflow.

## Known Gaps and Follow-up Tasks

- Add CI check that `scripts/build_readmes.py --check` passes on PRs touching templates (optional automation).
- Phase 2/3: spec separate tickets for webhook and WebSocket with their own verification scenarios.

## Improving proof over time

- Keep **pytest** as the regression anchor for API + skill text.
- Add **metrics**: count of `GET /api/federation/nodes/*/messages` in production logs (privacy-safe aggregation) to show inbox polling adoption.
- Publish a **short reviewer checklist** in the spec’s Verification Scenarios (already above) and run against `api.coherencycoin.com` before releases.
