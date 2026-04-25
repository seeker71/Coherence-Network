---
idea_id: value-attribution
status: active
source:
  - file: docs/shared/ecosystem-table.md
    symbols: [canonical 6-presence table]
  - file: README.template.md
    symbols: [ecosystem section include directive]
  - file: cli/README.template.md
    symbols: [ecosystem section]
  - file: mcp-server/README.template.md
    symbols: [ecosystem section]
  - file: skills/coherence-network/SKILL.template.md
    symbols: [ecosystem section]
  - file: api/app/main.py
    symbols: [FastAPI(description=...) constructor]
  - file: scripts/build_readmes.py
    symbols: [TEMPLATES list, expand()]
requirements:
  - "docs/shared/ecosystem-table.md has exactly 6 rows: Web, API docs, CLI (npm), MCP (npm), OpenClaw, GitHub"
  - "cli/README.template.md ecosystem section uses <!-- include: docs/shared/ecosystem-table.md -->"
  - "mcp-server/README.template.md ecosystem section uses <!-- include: docs/shared/ecosystem-table.md -->"
  - "skills/coherence-network/SKILL.template.md ecosystem section uses <!-- include: docs/shared/ecosystem-table.md -->"
  - "api/app/main.py description string references all 6 presences with live URLs"
  - "python scripts/build_readmes.py exits 0 and regenerates all 4 output READMEs"
  - "CLI README contains no cc help or cc binary references (bug: cc shadowed /usr/bin/cc)"
done_when:
  - "grep -c 'coherencycoin.com\\|github.com/seeker71\\|npmjs.com/package/coherence-cli\\|npmjs.com/package/coherence-mcp-server\\|clawhub.com\\|api.coherencycoin.com/docs' cli/README.md returns 6+"
  - "grep -c 'coherencycoin.com\\|github.com/seeker71\\|npmjs.com/package/coherence-cli\\|npmjs.com/package/coherence-mcp-server\\|clawhub.com\\|api.coherencycoin.com/docs' mcp-server/README.md returns 6+"
  - "curl -s https://api.coherencycoin.com/openapi.json | python3 -c \"import sys,json; d=json.load(sys.stdin); assert 'github.com/seeker71' in d['info']['description']\" exits 0"
  - "python scripts/build_readmes.py --check exits 0 (no stale outputs)"
test: "python scripts/build_readmes.py --check"
constraints:
  - "Edit templates only — never edit auto-generated README.md files directly"
  - "Do not add new template files; expand the include mechanism in build_readmes.py if needed"
  - "Ecosystem table rows must be identical across all surfaces (single source in docs/shared/ecosystem-table.md)"
  - "Keep API description under 500 chars to avoid OpenAPI rendering issues"
---

# Spec: Cross-Linked Public Presences

## Purpose

Every discovery path — GitHub, npm CLI, npm MCP, OpenClaw, API docs, Web — should lead to every other. Today the six surfaces each carry their own ecosystem table, and those tables drift from each other (the shared fragment lacks GitHub; the CLI template still says `cc help`; the API description omits OpenClaw). A contributor landing on npm finds the CLI but not the GitHub repo. An agent loading the MCP server sees one table; a developer browsing the API docs sees another. This spec closes all divergence: one canonical table, one build step, consistent links on every surface.

## Requirements

- [ ] **R1 — Canonical table**: `docs/shared/ecosystem-table.md` contains exactly 6 rows, in order: Web (`coherencycoin.com`), API docs (`api.coherencycoin.com/docs`), CLI (`npmjs.com/package/coherence-cli`), MCP Server (`npmjs.com/package/coherence-mcp-server`), OpenClaw Skill (`clawhub.com/skills/coherence-network`), GitHub (`github.com/seeker71/Coherence-Network`). No other rows (remove skills.sh, askill.sh, Join the Network). Row descriptions must be distinct — each surface explains what it is from the reader's perspective on that surface.

- [ ] **R2 — CLI template uses shared fragment**: `cli/README.template.md` replaces its inline ecosystem table with `<!-- include: docs/shared/ecosystem-table.md -->`. The heading ("The Coherence Network ecosystem") and surrounding prose stay in the template; only the table content moves to the fragment.

- [ ] **R3 — MCP template uses shared fragment**: `mcp-server/README.template.md` replaces its inline ecosystem table with `<!-- include: docs/shared/ecosystem-table.md -->`.

- [ ] **R4 — SKILL template uses shared fragment**: `skills/coherence-network/SKILL.template.md` replaces its inline ecosystem table with `<!-- include: docs/shared/ecosystem-table.md -->`.

- [ ] **R5 — CLI binary bug fixed**: All references to `cc help` or `` `cc` `` in `cli/README.template.md` are replaced with `coh help` / `` `coh` ``. (The `cc` binary was retired in v0.13.0.)

- [ ] **R6 — API description updated**: The `description=` string in `api/app/main.py` (FastAPI constructor) references all 6 presences. Current: 6 links but no consistent ordering. Required: Web · API Docs · CLI · MCP Server · OpenClaw · GitHub, all on one line for readability.

- [ ] **R7 — Build script regenerates outputs**: `python scripts/build_readmes.py` processes all 4 templates (including SKILL) and writes the 4 output files without error. The `--check` flag must pass after a fresh build.

- [ ] **R8 — Proof endpoint**: `GET /api/meta/ecosystem` returns a JSON array of the 6 presence objects `{name, description, url}` sourced from a parseable version of `docs/shared/ecosystem-table.md`. This endpoint is the machine-readable proof that the canonical table is live and reachable.

## API Contract

### `GET /api/meta/ecosystem`

Returns the 6 canonical presences in table order.

**Response 200**
```json
[
  {
    "name": "Web",
    "description": "Browse ideas, specs, contributors, and value chains visually",
    "url": "https://coherencycoin.com"
  },
  {
    "name": "API",
    "description": "100+ endpoints with full OpenAPI docs — the engine behind everything",
    "url": "https://api.coherencycoin.com/docs"
  },
  {
    "name": "CLI",
    "description": "Terminal-first access — npx coherence-cli help or npm i -g coherence-cli",
    "url": "https://www.npmjs.com/package/coherence-cli"
  },
  {
    "name": "MCP Server",
    "description": "84 typed tools for AI agents (Claude, Cursor, Windsurf)",
    "url": "https://www.npmjs.com/package/coherence-mcp-server"
  },
  {
    "name": "OpenClaw Skill",
    "description": "Auto-triggers inside any OpenClaw instance",
    "url": "https://clawhub.com/skills/coherence-network"
  },
  {
    "name": "GitHub",
    "description": "Source code, specs, issues, and contribution tracking",
    "url": "https://github.com/seeker71/Coherence-Network"
  }
]
```

**Note**: This endpoint reads from a static config or parses `docs/shared/ecosystem-table.md` at startup. It does not hit the database.

## Data Model

```yaml
EcosystemPresence:
  name: string          # Display name, e.g. "CLI"
  description: string   # One-line description for that surface
  url: string           # Canonical URL
```

## Files to Create/Modify

- `docs/shared/ecosystem-table.md` — rewrite to exactly 6 rows matching the canonical set; remove skills.sh, askill.sh, Join the Network rows
- `cli/README.template.md` — replace inline ecosystem table with `<!-- include: docs/shared/ecosystem-table.md -->` include; fix `cc help` → `coh help`
- `mcp-server/README.template.md` — replace inline ecosystem table with `<!-- include: docs/shared/ecosystem-table.md -->`
- `skills/coherence-network/SKILL.template.md` — replace inline ecosystem table with `<!-- include: docs/shared/ecosystem-table.md -->`
- `api/app/main.py` — update `description=` string in FastAPI constructor to list all 6 presences in canonical order
- `api/app/routers/meta.py` — add `GET /api/meta/ecosystem` route returning the 6-presence list
- `api/app/models/meta.py` (or equivalent) — add `EcosystemPresence` Pydantic model if not present
- `README.md`, `cli/README.md`, `mcp-server/README.md`, `skills/coherence-network/SKILL.md` — regenerated outputs; only modify via `python scripts/build_readmes.py`

## Acceptance Tests

- `api/tests/test_meta.py::test_ecosystem_returns_six_presences` — `GET /api/meta/ecosystem` returns list of length 6, each item has `name`, `description`, `url`
- `api/tests/test_meta.py::test_ecosystem_urls_all_distinct` — all 6 `url` values are unique
- `api/tests/test_meta.py::test_ecosystem_contains_github` — one entry has url containing `github.com/seeker71`

## Verification Scenarios

**Scenario 1 — Shared fragment in all outputs**
```bash
# After running build_readmes.py, all 3 templated outputs contain "github.com/seeker71"
grep "github.com/seeker71" cli/README.md mcp-server/README.md README.md skills/coherence-network/SKILL.md
# Expected: 4 matching lines (one per file)
```

**Scenario 2 — API description contains GitHub**
```bash
curl -s https://api.coherencycoin.com/openapi.json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); desc=d['info']['description']; print(desc); assert 'github.com/seeker71' in desc"
# Expected: description printed, exits 0
```

**Scenario 3 — Proof endpoint is live and complete**
```bash
curl -s https://api.coherencycoin.com/api/meta/ecosystem \
  | python3 -c "import sys,json; items=json.load(sys.stdin); assert len(items)==6; urls=[i['url'] for i in items]; print('\n'.join(urls))"
# Expected: 6 URLs printed, exits 0
```

**Scenario 4 — CLI README has no cc binary references**
```bash
grep -n "\bcc\b" cli/README.md | grep -v "https://" | grep -v "CC\b"
# Expected: no output (the cc binary bug is gone)
```

**Scenario 5 — Build check passes**
```bash
python scripts/build_readmes.py --check
# Expected: "OK:" for all 4 outputs, exits 0
```

## Out of Scope

- Social platform bots (Discord, Telegram, X) — covered by `external-presence` idea
- Translating ecosystem table into other languages — i18n spec handles that
- skills.sh / askill.sh submission — separate distribution concern
- Auto-submission of SKILL.md to external registries — covered by presence-modularization

## Risks and Assumptions

- **Risk**: `GET /api/meta/ecosystem` parsing `docs/shared/ecosystem-table.md` at startup adds a file I/O dependency. Mitigation: seed from a static Python dict seeded from the markdown at startup; fall back to hardcoded defaults if file missing.
- **Risk**: The SKILL.template.md uses the include directive, but `build_readmes.py` already handles it. Verify the template is already in `TEMPLATES` list (it is, at line 26).
- **Assumption**: All 6 URLs are stable and not expected to change. If any URL changes, only `docs/shared/ecosystem-table.md` needs updating, and the build propagates it everywhere.
- **Assumption**: The meta router already exists at `api/app/routers/meta.py` — the new endpoint adds to it rather than creating a new file.
