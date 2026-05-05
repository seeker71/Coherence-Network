---
idea_id: user-surfaces
status: active
source:
  - file: api/app/services/design_artifact_service.py
    symbols: [generate_artifact, list_artifacts_for_concept, get_artifact]
  - file: api/app/routers/design.py
    symbols: [post_generate_artifact, get_artifacts, get_artifact]
  - file: api/app/models/design.py
    symbols: [GenerateArtifactRequest, Artifact, ArtifactKind]
  - file: scripts/od_generate.py
    symbols: [main, call_daemon, persist_artifact]
  - file: web/components/GenerateArtifactButton.tsx
    symbols: [GenerateArtifactButton]
  - file: docker-compose.yml
    symbols: [open-design]
requirements:
  - Python service `design_artifact_service` that POSTs to a running open-design daemon and captures the streamed artifact (HTML/PDF/PPTX/MP4) plus metadata (skill, prompt, design system, agent, model)
  - API endpoint `POST /api/design/generate` accepting `{concept_id|spec_id|idea_id, skill, design_system?, prompt?}` and returning an artifact node id + status
  - API endpoint `GET /api/design/artifacts?source_id={id}` returning artifacts attached to a concept/spec/idea
  - Artifacts persisted as graph nodes (`type: artifact`, properties carry `kind`, `format`, `skill`, `design_system`, `prompt_hash`, `agent`, `model`, `source_id`, `file_path`)
  - CLI script `scripts/od_generate.py {source_id} {skill}` that calls the API, streams progress, prints artifact id + path
  - React button component `GenerateArtifactButton` that opens the open-design interactive form (skill picker + visual direction picker), streams the agent panel, lands the artifact attached to the source
  - Open-design daemon running as a sidecar — local: `pnpm tools-dev` from a sibling directory; production: optional docker-compose service behind the same Traefik reverse proxy
done_when:
  - `POST /api/design/generate` returns 202 with artifact id when daemon is reachable, 503 with clear message when daemon is down
  - `GET /api/design/artifacts?source_id=lc-open-design` returns the seed artifact created during initial verification
  - `coh design generate lc-open-design weekly-update` produces a real `.html` and `.pdf` on disk and a graph node referencing them
  - `GenerateArtifactButton` rendered on `/vision/{conceptId}` opens, runs end-to-end, and the resulting artifact appears in a small gallery on the same page on next render
  - All new tests pass; existing 700+ tests still green; type-check + lint clean
test: "cd api && python -m pytest tests/test_design_artifact_service.py tests/test_design_router.py -q"
constraints:
  - Daemon-as-sidecar — the network does not vendor open-design's source; it depends on the daemon's HTTP surface only, so upstream stays free to evolve
  - BYOK preserved — credentials flow from `~/.coherence-network/keys.json` (or container env) to the daemon at request time; the network never stores model API keys
  - Artifacts are commons by default — every artifact node carries `license: CC` unless the prompter explicitly marks otherwise
  - Provider pluralism honored — the skill picker exposes whichever coding-agent CLI the daemon detects on PATH (Claude Code, Codex, Cursor, Gemini, OpenCode, Qwen, Copilot, Hermes, Kimi); nothing is hard-coded to Anthropic
  - Pollinations stays the path for inline concept visuals; this loop covers the artifact-shaped output (decks, prototypes, posters, films) the existing visual pipeline does not
  - The graph already has an artifact node type — extend, do not duplicate; reuse `type: artifact` and add properties rather than creating a parallel `design_artifact` type
---

# Spec: Open Design Integration — Phase 1

## Purpose

The body has the rails for an artifact loop (agent pipeline, model routing, BYOK keystore, Pollinations visuals, graph storage) but no surface where a prompt becomes a deck, prototype, or printable that another cell can hold. Phase 1 wires the open-source [nexu-io/open-design](https://github.com/nexu-io/open-design) daemon as a sidecar, exposes a thin generate endpoint, persists artifacts as graph nodes, and surfaces a button on `/vision/{conceptId}`. The named home for this capability is the KB concept [`lc-open-design`](../docs/vision-kb/concepts/lc-open-design.md). This spec realizes the first phase the concept sketches.

## Requirements

- [ ] **R1** — `design_artifact_service.generate_artifact(source_id, skill, ...)` POSTs to the open-design daemon's `/api/agent/run` (or equivalent), streams the response, captures the artifact file(s) into `web/public/artifacts/{source_id}/{artifact_id}/`, and returns metadata.
- [ ] **R2** — `POST /api/design/generate` accepts `{source_id, skill, design_system?, prompt?, visual_direction?}`, queues the generation, returns 202 with `{artifact_id, status_url}`. `GET /api/design/artifacts/{id}` returns the artifact node with computed `file_url`.
- [ ] **R3** — Artifacts persist as graph nodes (`type: artifact`) attached to their source via `produced-from` edges. The properties block carries `kind` (deck/prototype/poster/carousel/...), `format` (html/pdf/pptx/mp4), `skill`, `design_system`, `prompt_hash`, `agent`, `model`, `file_path`, `license` (default `CC-BY-SA`).
- [ ] **R4** — CLI `scripts/od_generate.py {source_id} {skill} [--design-system X] [--direction Y]` calls the API, streams progress to stderr, prints the artifact id and final file path on success.
- [ ] **R5** — `GenerateArtifactButton.tsx` on `/vision/{conceptId}` opens an interactive form (skill picker, design-system picker, visual-direction picker), streams the agent panel from the daemon's SSE surface, and on success refreshes the artifact gallery on the same page.
- [ ] **R6** — `docker-compose.yml` adds an optional `open-design` service that runs `pnpm tools-dev daemon` and exposes the daemon's HTTP port to api only (not public). Local dev path: a sibling clone the developer runs themselves.
- [ ] **R7** — A seed run during deploy verification creates one artifact for `lc-open-design` itself (skill: `weekly-update`) so the loop has a witness on production day one.

## API Contract

### `POST /api/design/generate`

**Body**
```json
{
  "source_id": "lc-open-design",
  "skill": "weekly-update",
  "design_system": "editorial-monocle",
  "visual_direction": "editorial-monocle",
  "prompt": "optional override prompt"
}
```

**Response 202**
```json
{
  "artifact_id": "art-7f2a",
  "status": "queued",
  "status_url": "/api/design/artifacts/art-7f2a"
}
```

**Response 503** — daemon unreachable
```json
{
  "detail": "open-design daemon not reachable; start it with `pnpm tools-dev daemon` or check docker compose"
}
```

### `GET /api/design/artifacts/{artifact_id}`

**Response 200**
```json
{
  "id": "art-7f2a",
  "type": "artifact",
  "kind": "deck",
  "format": "pdf",
  "skill": "weekly-update",
  "design_system": "editorial-monocle",
  "source_id": "lc-open-design",
  "file_url": "/artifacts/lc-open-design/art-7f2a/deck.pdf",
  "agent": "claude-code",
  "model": "claude-opus-4-7",
  "license": "CC-BY-SA",
  "created_at": "2026-05-06T08:00:00Z"
}
```

### `GET /api/design/artifacts?source_id={id}`

**Response 200** — list of artifacts for a concept/spec/idea.

## Data Model

```yaml
Artifact:
  id: string
  type: "artifact"
  kind: "deck" | "prototype" | "poster" | "carousel" | "magazine" | "weekly-update" | ...
  format: "html" | "pdf" | "pptx" | "mp4" | "zip"
  skill: string             # which open-design skill ran
  design_system: string     # which design system shaped the form
  source_id: string         # concept/spec/idea this artifact was generated from
  prompt_hash: string       # sha256 of the prompt for dedup
  agent: string             # which coding-agent CLI ran (claude-code / codex / cursor / ...)
  model: string             # the model the agent was running
  file_path: string         # repo-relative
  file_url: string          # served via /artifacts/...
  license: string           # default "CC-BY-SA"
  created_by: string        # contributor id
  created_at: datetime
```

## Files to Create/Modify

- `api/app/services/design_artifact_service.py` — daemon client + persistence
- `api/app/routers/design.py` — `/api/design/...` endpoints
- `api/app/models/design.py` — Pydantic shapes for request/response
- `scripts/od_generate.py` — CLI wrapper
- `web/components/GenerateArtifactButton.tsx` — button + form modal
- `web/app/vision/[conceptId]/_components/ArtifactGallery.tsx` — per-page artifact list
- `web/app/vision/[conceptId]/page.tsx` — wire the button + gallery into the page
- `docker-compose.yml` — optional `open-design` service for prod
- `api/tests/test_design_artifact_service.py` — service unit tests with mocked daemon
- `api/tests/test_design_router.py` — endpoint tests
- `docs/INTEGRATIONS.md` — operational notes for running the daemon

## Acceptance Tests

- `api/tests/test_design_router.py::test_generate_returns_202_when_daemon_up`
- `api/tests/test_design_router.py::test_generate_returns_503_when_daemon_down`
- `api/tests/test_design_router.py::test_get_artifacts_by_source_id`
- `api/tests/test_design_artifact_service.py::test_streams_artifact_to_disk`
- `api/tests/test_design_artifact_service.py::test_persists_graph_node_with_produced_from_edge`

## Verification

```bash
# unit tests
cd api && pytest -q tests/test_design_artifact_service.py tests/test_design_router.py

# end-to-end smoke (requires daemon running locally)
pnpm --dir ../open-design tools-dev daemon &
DAEMON_PID=$!
python3 scripts/od_generate.py lc-open-design weekly-update --design-system editorial-monocle
kill $DAEMON_PID

# the file should land at web/public/artifacts/lc-open-design/{art-id}/{deck.pdf|deck.html}
ls -la web/public/artifacts/lc-open-design/
```

## Known Gaps

- No daemon HTTP contract document yet — the open-design project's API surface needs to be pinned to a known version before the adapter is implemented; first task in the PR is a quick spike to capture the request/response shapes the daemon currently exposes.
- Authentication between api and the daemon: the daemon trusts whoever can reach it on its port. Production exposure stays internal-only (api → daemon over docker network); for local dev no auth is needed.
- The gallery component on `/vision/{id}` reads from `GET /api/design/artifacts?source_id={id}` — needs the contract to land before the UI can render real entries.
- Naming: "artifact" is already used loosely in the codebase. This spec narrows the meaning under `type: artifact` to mean "design artifact produced by an open-design generation." If a different domain claims that name, a rename pass becomes necessary before the seed lands.

## Out of Scope

- Phase 2: generate buttons on `/specs/{id}` and `/idea/{id}` — same pattern, separate spec
- Phase 3: MCP tool `coherence_generate_artifact` exposing the loop to agents in the pipeline — separate spec
- Phase 4: a custom design system carrying the field's emerging visual voice (`docs/vision-kb/visual-language.md` becoming a registered design system) — separate spec
- Vendoring open-design's source — the daemon stays an external sidecar
- Bundling specific coding-agent CLIs — they remain the user's choice via PATH detection

## Risks and Assumptions

- **Risk**: open-design's HTTP surface evolves and breaks the adapter. **Mitigation**: pin a daemon version in `docker-compose.yml`, version-bump deliberately, integration test exercises the contract.
- **Risk**: artifacts blow up storage. **Mitigation**: per-source artifact gallery shows newest first with a "compost older" action; old artifacts age out unless pinned.
- **Assumption**: the field actually wants generated artifacts per-concept. The first deck for `lc-open-design` itself is the canary — if the body recoils, we sense before scaling.
- **Assumption**: contributors carry their own model API keys via the keystore. Anyone whose keystore is empty sees a clear "BYOK to use this" prompt rather than a silent failure.
