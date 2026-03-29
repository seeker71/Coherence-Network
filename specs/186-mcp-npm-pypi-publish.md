# Spec 186 — Publish Coherence Network MCP Server to npm and PyPI

**ID:** 186-mcp-npm-pypi-publish
**Status:** approved
**Priority:** high
**Category:** distribution / discoverability
**Author:** claude (product-manager)
**Created:** 2026-03-28
**Task:** task_2ff2afcd1d57b8e1

---

## Summary

The Coherence Network MCP server currently exists in two forms:

1. **JavaScript** — `mcp-server/index.mjs`, packaged as `coherence-mcp-server` on npm (v0.3.1 in
   `package.json`, v0.2.0 in `server.json` — these are **out of sync**).
2. **Python** — `api/mcp_server.py`, backed by `api/app/services/mcp_tool_registry.py`, runnable
   as `python -m api.mcp_server` but **not yet published to PyPI**.

This spec defines:

- Keeping the **npm package current and discoverable** — version sync, manifest hygiene, CI
  publish gate, and `server.json` updated so MCP registries show the correct version.
- Publishing a **PyPI package** (`coherence-mcp-server`) so Python-first operators (Cursor with
  uv, Claude Code with Python toolchain) can install via `pip install coherence-mcp-server` or
  `uvx coherence-mcp-server`.
- Updating the **`server.json` manifest** to include both packages so the Official MCP Registry,
  Smithery, Glama, and PulseMCP all surface the canonical install command for each ecosystem.
- Adding a **`/api/discovery/package-versions`** endpoint so the network can prove, at any time,
  that published versions match the repo version.

---

## Goals

| # | Goal |
|---|------|
| G1 | npm package `coherence-mcp-server` is published, version-synced with `server.json`, and discoverable via `npx coherence-mcp-server`. |
| G2 | PyPI package `coherence-mcp-server` is published and installable via `pip install coherence-mcp-server` or `uvx coherence-mcp-server`. |
| G3 | `mcp-server/server.json` lists both the npm and PyPI packages under `packages[]`. |
| G4 | A new API endpoint `/api/discovery/package-versions` returns live published versions from npm and PyPI registries, compared to the repo's declared version. |
| G5 | A GitHub Actions workflow publishes npm on tag push (`v*`) and PyPI on the same tag using Trusted Publishing (no token stored in secrets). |
| G6 | Proof of "it is working" is queryable: install counts from npm and PyPI are surfaced alongside submission status in `/api/discovery/registry-dashboard`. |

---

## Architecture

### Current state

```
mcp-server/
  index.mjs           ← JS MCP server entry point
  package.json        ← npm package (coherence-mcp-server, v0.3.1)
  server.json         ← MCP registry manifest (version 0.2.0 — STALE)
  glama.json          ← Glama registry metadata
  pulsemcp.json       ← PulseMCP metadata

api/
  mcp_server.py       ← Python MCP server entry point
  app/services/
    mcp_tool_registry.py   ← tool definitions and handlers
```

### Target state (after this spec)

```
mcp-server/
  (existing files — no change except server.json version bump)

mcp-python/             ← NEW directory
  pyproject.toml        ← PyPI package metadata (coherence-mcp-server)
  coherence_mcp/
    __init__.py
    __main__.py         ← entry point: python -m coherence_mcp
  README.md             ← PyPI long description

.github/workflows/
  publish-mcp-npm.yml   ← publish to npm on v* tag
  publish-mcp-pypi.yml  ← publish to PyPI on v* tag (Trusted Publishing)

api/app/
  routers/
    discovery.py        ← add GET /api/discovery/package-versions route
  services/
    package_versions_service.py   ← NEW: fetch npm and PyPI published versions
  models/
    registry_discovery.py         ← add PackageVersionInfo model
```

---

## Data Model

### `PackageVersionInfo` (new Pydantic model)

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel

class VersionStatus(str, Enum):
    SYNCED = "synced"          # published version matches repo version
    AHEAD = "ahead"            # repo is ahead (not yet published)
    BEHIND = "behind"          # published is ahead (unusual — stale repo?)
    UNKNOWN = "unknown"        # could not fetch published version

class PackageVersionInfo(BaseModel):
    registry: str              # "npm" | "pypi"
    package_name: str          # "coherence-mcp-server"
    repo_version: str          # version declared in package.json / pyproject.toml
    published_version: str | None  # latest version on registry (None if not published)
    status: VersionStatus
    install_count: int | None  # weekly downloads (npm) or total downloads (pypi)
    install_count_window: str | None  # "last-week" | "all-time" | None
    fetched_at: datetime | None
    error: str | None

class PackageVersionSummary(BaseModel):
    all_synced: bool           # True when all packages are SYNCED
    any_published: bool        # True when at least one package is published
    packages: list[PackageVersionInfo]
```

---

## npm Package Details

### Current gaps to close

| Gap | Fix |
|----|-----|
| `server.json` version is `0.2.0` but `package.json` is `0.3.1` | Update `server.json` version to match `package.json` on every release |
| No CI publish workflow | Add `.github/workflows/publish-mcp-npm.yml` |
| `server.json` has no PyPI entry | Add PyPI entry to `packages[]` once PyPI is published |

### CI Publish Workflow (`publish-mcp-npm.yml`)

```yaml
name: Publish MCP Server to npm
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://registry.npmjs.org'
      - run: cd mcp-server && npm ci && npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

### Version Sync Script

A new script `scripts/sync-mcp-version.py` reads `mcp-server/package.json` and rewrites
`mcp-server/server.json` version field to match. Run as part of the release process.

---

## PyPI Package Details

### Package name: `coherence-mcp-server`

Matches the npm package name for brand consistency. The Python entry point:

```bash
pip install coherence-mcp-server
coherence-mcp-server           # starts the MCP server via stdio
# or
uvx coherence-mcp-server       # zero-install run via uv
# or
python -m coherence_mcp        # module invocation
```

### `mcp-python/pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "coherence-mcp-server"
version = "0.3.1"
description = "MCP server for the Coherence Network — typed tools for AI agents to browse ideas, trace value chains, link identities, and record contributions."
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
]
keywords = ["mcp", "model-context-protocol", "coherence", "ai-agent", "claude", "cursor"]

[project.scripts]
coherence-mcp-server = "coherence_mcp.__main__:main"

[project.urls]
Homepage = "https://coherencycoin.com"
Repository = "https://github.com/seeker71/Coherence-Network"
```

### `mcp-python/coherence_mcp/__main__.py`

Thin wrapper that re-uses `api/mcp_server.py` logic but is standalone — does not import the
FastAPI app. It communicates directly with `api.coherencycoin.com` via HTTP (same as the JS
server). This allows `pip install coherence-mcp-server` to work on any machine without
installing the full API stack.

**Key design decision:** The Python package is a *client-side* MCP server (like the JS one). It
calls the live API over HTTP. It is NOT the server-side FastAPI app. This is the same pattern
used by `index.mjs`.

### CI Publish Workflow (`publish-mcp-pypi.yml`)

```yaml
name: Publish MCP Server to PyPI
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # required for Trusted Publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install build
      - run: cd mcp-python && python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: mcp-python/dist/
```

---

## Updated `server.json` Manifest

```json
{
  "$schema": "https://registry.modelcontextprotocol.io/schemas/server.json",
  "name": "coherence-mcp-server",
  "version": "0.3.1",
  "description": "MCP server for the Coherence Network — 20 typed tools for AI agents to browse ideas, trace value chains, link identities, and record contributions.",
  "repository": "https://github.com/seeker71/Coherence-Network",
  "homepage": "https://coherencycoin.com",
  "license": "MIT",
  "authors": ["coherence-network"],
  "categories": ["collaboration", "project-management", "open-source"],
  "tags": ["ideas", "collaboration", "investment", "federation", "coherence", "open-source", "value-attribution"],
  "packages": [
    {
      "registry": "npm",
      "name": "coherence-mcp-server",
      "version": "0.3.1"
    },
    {
      "registry": "pypi",
      "name": "coherence-mcp-server",
      "version": "0.3.1"
    }
  ],
  "tools": [
    {"name": "coherence_list_ideas", "description": "Browse ideas sorted by free energy score"},
    {"name": "coherence_get_idea", "description": "Get idea details including tasks and progress"},
    {"name": "coherence_create_idea", "description": "Share a new idea"},
    {"name": "coherence_list_specs", "description": "Browse registered specs"},
    {"name": "coherence_list_nodes", "description": "List federation compute nodes"},
    {"name": "coherence_get_coherence_score", "description": "Get coherence score with signal breakdown"},
    {"name": "coherence_ask_question", "description": "Ask a question on an idea"},
    {"name": "coherence_stake", "description": "Invest CC in an idea (triggers compute tasks)"},
    {"name": "coherence_record_contribution", "description": "Record a contribution to the network"},
    {"name": "coherence_list_tasks", "description": "List agent tasks by status"},
    {"name": "coherence_get_resonance", "description": "Get recent network activity"},
    {"name": "coherence_link_identity", "description": "Link an external identity to a contributor"},
    {"name": "coherence_get_portfolio", "description": "Get idea portfolio summary"},
    {"name": "coherence_get_provider_stats", "description": "Get provider execution statistics"}
  ]
}
```

---

## API Changes

### New endpoint

```
GET /api/discovery/package-versions
```

Returns `PackageVersionSummary`. Fetches live data from:
- npm: `https://registry.npmjs.org/coherence-mcp-server` (latest version + weekly downloads)
- PyPI: `https://pypi.org/pypi/coherence-mcp-server/json` (latest version + total downloads)

Query params:
- `?refresh=true` — bypass 1-hour cache and fetch live data

Response (example):
```json
{
  "all_synced": false,
  "any_published": true,
  "packages": [
    {
      "registry": "npm",
      "package_name": "coherence-mcp-server",
      "repo_version": "0.3.1",
      "published_version": "0.3.1",
      "status": "synced",
      "install_count": 142,
      "install_count_window": "last-week",
      "fetched_at": "2026-03-28T20:00:00Z",
      "error": null
    },
    {
      "registry": "pypi",
      "package_name": "coherence-mcp-server",
      "repo_version": "0.3.1",
      "published_version": null,
      "status": "unknown",
      "install_count": null,
      "install_count_window": null,
      "fetched_at": "2026-03-28T20:00:00Z",
      "error": "404 Not Found — package not yet published"
    }
  ]
}
```

### Extended existing endpoint

```
GET /api/discovery/registry-dashboard
```

The `RegistryDashboardItem` for `npm` and `pypi` entries will include `install_count` sourced
from the new `package_versions_service`. No breaking change to the response shape.

---

## File Changes

| File | Change |
|------|--------|
| `mcp-server/server.json` | Update version to `0.3.1`; add PyPI entry to `packages[]` |
| `mcp-python/pyproject.toml` | **NEW** — PyPI package metadata |
| `mcp-python/coherence_mcp/__init__.py` | **NEW** — package init |
| `mcp-python/coherence_mcp/__main__.py` | **NEW** — standalone Python MCP server (HTTP-based, no FastAPI dep) |
| `mcp-python/README.md` | **NEW** — PyPI long description |
| `scripts/sync-mcp-version.py` | **NEW** — reads `package.json`, updates `server.json` version field |
| `.github/workflows/publish-mcp-npm.yml` | **NEW** — CI npm publish on `v*` tag |
| `.github/workflows/publish-mcp-pypi.yml` | **NEW** — CI PyPI publish on `v*` tag (Trusted Publishing) |
| `api/app/models/registry_discovery.py` | Add `PackageVersionInfo`, `PackageVersionSummary` models |
| `api/app/services/package_versions_service.py` | **NEW** — fetch npm and PyPI version + download counts |
| `api/app/routers/discovery.py` | Add `GET /api/discovery/package-versions` route |
| `api/tests/test_package_versions.py` | **NEW** — pytest tests for version endpoint |

---

## How This Proves It Is Working

The key question from the task brief: *"How can we improve this idea, show whether it is working
yet, and make that proof clearer over time?"*

### Proof Level 1 — Package exists on registry

```bash
# npm
npm show coherence-mcp-server version
# Expected: 0.3.1 (or current)

# PyPI
pip index versions coherence-mcp-server
# Expected: 0.3.1 (or current)
```

### Proof Level 2 — Installable and runnable

```bash
# npm (zero-install)
npx coherence-mcp-server --version

# PyPI (zero-install via uv)
uvx coherence-mcp-server --version
```

### Proof Level 3 — API proves version sync

```bash
curl -s https://api.coherencycoin.com/api/discovery/package-versions | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['all_synced'], [(p['registry'], p['status'], p['install_count']) for p in d['packages']])"
```

Expected once both are published:
```
True [('npm', 'synced', 142), ('pypi', 'synced', 31)]
```

### Proof Level 4 — Download counts grow over time

The `fetched_at` timestamp on each `PackageVersionInfo` entry means every call to
`?refresh=true` captures a new count. Plot `install_count` over `fetched_at` — a monotonically
increasing line is the clearest possible proof that real operators are installing and running the
server.

---

## Verification Scenarios

### Scenario 1 — npm package is published and version-synced

**Setup:** `coherence-mcp-server@0.3.1` is published to npm.

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/package-versions | \
  python3 -c "import sys,json; d=json.load(sys.stdin); npm=[p for p in d['packages'] if p['registry']=='npm'][0]; print(npm['status'], npm['published_version'])"
```

**Expected:** `synced 0.3.1`

**Edge — version mismatch:** If `package.json` is bumped to `0.4.0` but npm still has `0.3.1`,
the API returns `status: "ahead"` for npm. `all_synced` is `false`. No 500.

**Edge — npm registry unreachable:** `status: "unknown"`, `error` contains the HTTP error message,
HTTP 200 still returned.

---

### Scenario 2 — PyPI package is not yet published (expected initial state)

**Setup:** PyPI package does not yet exist (before first `v*` tag and CI run).

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/discovery/package-versions | \
  python3 -c "import sys,json; d=json.load(sys.stdin); pypi=[p for p in d['packages'] if p['registry']=='pypi'][0]; print(pypi['status'], pypi['error'])"
```

**Expected:** `unknown 404 Not Found — package not yet published`

`any_published` is `true` (npm is published). `all_synced` is `false`.
HTTP 200 returned — partial unavailability is not an error.

---

### Scenario 3 — server.json version matches package.json after sync script

**Setup:** `mcp-server/package.json` declares `version: "0.3.1"`.

**Action:**
```bash
python3 scripts/sync-mcp-version.py
cat mcp-server/server.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['version'], [p['version'] for p in d['packages']])"
```

**Expected:** `0.3.1 ['0.3.1', '0.3.1']`

**Edge — `server.json` missing:** Script creates the file from template with the version set.

---

### Scenario 4 — Python package installs and starts (post-PyPI publish)

**Setup:** `coherence-mcp-server` is published to PyPI. `uv` is available on the test runner.

**Action:**
```bash
uvx coherence-mcp-server --help 2>&1 | head -5
```

**Expected:** Output contains `Coherence Network MCP Server` and the server exits cleanly (not
with an import error or missing dependency).

**Edge — no network access:** Server prints `COHERENCE_API_URL not reachable` to stderr but does
not crash on import. Exit code is 0 for `--help`.

---

### Scenario 5 — Full create-read-update cycle for version tracking

**Setup:** API is running. No cache files present for package-versions.

**Action (initial fetch):**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/package-versions" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['any_published'], len(d['packages']))"
```
**Expected:** `True 2` (two packages tracked: npm and pypi)

**Action (force refresh):**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/package-versions?refresh=true" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); npm=[p for p in d['packages'] if p['registry']=='npm'][0]; print(npm['fetched_at'])"
```
**Expected:** New `fetched_at` timestamp, more recent than the previous call.

**Edge — duplicate rapid calls:** Second call within the cache window returns `fetched_at` of the
first call (cached, not refetched). Only `?refresh=true` bypasses the cache.

**Edge — unknown package name:** `GET /api/discovery/package-versions?package=nonexistent` returns
`{"error": "Package not tracked"}` with HTTP 404.

---

## Release Process

1. Bump version in `mcp-server/package.json` and `mcp-python/pyproject.toml` to the new version.
2. Run `python3 scripts/sync-mcp-version.py` to update `mcp-server/server.json`.
3. Commit and merge to `main`.
4. Push a `v{version}` tag: `git tag v0.3.1 && git push origin v0.3.1`.
5. GitHub Actions runs:
   - `publish-mcp-npm.yml` → publishes to npm
   - `publish-mcp-pypi.yml` → publishes to PyPI via Trusted Publishing
6. Verify: `curl -s https://api.coherencycoin.com/api/discovery/package-versions?refresh=true`
   should return `all_synced: true`.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| npm package name `coherence-mcp-server` may be taken | Check before implementing; if taken, use `@coherence-network/mcp-server` (scoped) |
| PyPI name conflict | Same as npm — check `pypi.org/project/coherence-mcp-server/` |
| Trusted Publishing requires PyPI project pre-configured | Set up PyPI project and add GitHub Actions trusted publisher before first CI run |
| `server.json` version drift causes MCP registry to show stale version | `sync-mcp-version.py` must run in CI before any publish step |
| Python package imports `api/` which imports FastAPI | The `mcp-python/` package must be **standalone** — no FastAPI dependency; re-implement the HTTP calls using `httpx` |
| npm weekly download counts reset to 0 for new packages | Expected; first week will show low counts; trend line starts from publish date |
| PyPI download counts require `pypistats` API | Use `https://pypistats.org/api/packages/{name}/recent` which is public and returns last day/week/month |

---

## Known Gaps and Follow-up Tasks

- [ ] Once both packages have non-zero install counts for 4 consecutive weeks, add a PostgreSQL
  table `package_install_snapshots(registry, package_name, install_count, snapshot_at)` for
  trend graphing (Spec 187).
- [ ] Add a web panel at `/discovery` that renders the version sync status and download sparkline
  (Spec 181 extension).
- [ ] Submit `coherence-mcp-server` to the Official MCP Registry
  (`registry.modelcontextprotocol.io`) via PR once the `server.json` includes both package
  entries (tracked separately in Spec 180).
- [ ] Automated PR to update `server.json` and `pyproject.toml` versions on each release as a
  GitHub Actions step.

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC1 | `mcp-server/server.json` version matches `mcp-server/package.json` version. |
| AC2 | `mcp-server/server.json` `packages[]` contains both an `npm` entry and a `pypi` entry. |
| AC3 | `mcp-python/pyproject.toml` exists with `name = "coherence-mcp-server"`, `requires-python = ">=3.10"`, and a `project.scripts` entry. |
| AC4 | `mcp-python/coherence_mcp/__main__.py` exists and is runnable with `python -m coherence_mcp --help` without importing FastAPI. |
| AC5 | `scripts/sync-mcp-version.py` reads version from `package.json` and writes it to `server.json`; idempotent on repeated runs. |
| AC6 | `.github/workflows/publish-mcp-npm.yml` triggers on `v*` tag push and uses `npm publish` with `NODE_AUTH_TOKEN`. |
| AC7 | `.github/workflows/publish-mcp-pypi.yml` triggers on `v*` tag push and uses PyPA Trusted Publishing (no static secret). |
| AC8 | `GET /api/discovery/package-versions` returns HTTP 200 with two items (`npm`, `pypi`) under all conditions — including when one or both registries are unreachable. |
| AC9 | `status` field is `synced` when `repo_version == published_version`, `ahead` when repo is newer, `behind` when registry is newer, `unknown` when fetch failed. |
| AC10 | `?refresh=true` bypasses cache and updates `fetched_at`. Without it, responses within the 1-hour window return cached data. |
| AC11 | All new models and service functions are covered by pytest tests in `api/tests/test_package_versions.py`. |
| AC12 | `npm show coherence-mcp-server version` returns the expected version string after first publish. |
