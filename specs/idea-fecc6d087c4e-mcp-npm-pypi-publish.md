# Spec — Publish coherence-network MCP Server to npm and PyPI

**ID:** idea-fecc6d087c4e-mcp-npm-pypi-publish
**Status:** approved
**Priority:** high
**Category:** distribution / packaging
**Author:** claude (product-manager)
**Created:** 2026-03-28
**Task:** task_c729074f7d7ff038
**Related:** spec 180 (registry submission), spec 024 (pypi-indexing)

---

## Summary

Package the Coherence Network MCP server as a first-class, installable artifact on
both **npm** (`coherence-mcp-server`) and **PyPI** (`coherence-mcp-server`) so that:

1. Any developer can run it with `npx coherence-mcp-server` (zero install).
2. Any Python developer can install it with `pip install coherence-mcp-server`.
3. It appears on **Smithery**, **Glama**, **PulseMCP**, and the **Official MCP
   Registry** via the `mcp-server/server.json` manifest consumed by `mcp-publisher`.
4. Download counts are measurable and visible through the existing
   `/api/discovery/registry-stats` endpoint (built in spec 180), proving adoption
   over time.

The MCP server implementation itself already exists (`mcp-server/index.mjs`,
`api/mcp_server.py`) and the registry manifests are present
(`mcp-server/server.json`, `mcp-server/package.json`, `mcp-server/pyproject.toml`).
**This spec closes the gap between the artifacts existing and them being reliably
published, versioned, and tracked.**

---

## Goals

| # | Goal |
|---|------|
| G1 | `npm install -g coherence-mcp-server` and `pip install coherence-mcp-server` succeed from a fresh machine. |
| G2 | `npx coherence-mcp-server` starts the MCP server and responds to `list_tools`. |
| G3 | A GitHub Actions workflow publishes to npm **and** PyPI on every semver tag (`v*.*.*`). |
| G4 | `mcp-server/server.json` is valid for `mcp-publisher` and references the correct npm package name and version. |
| G5 | `GET /api/discovery/registry-stats` returns live npm and PyPI download counts, updated at least daily. |
| G6 | Proof of adoption is visible in a single API call — download count > 0 after first publish. |

---

## What Already Exists

| Asset | Status | Gap |
|-------|--------|-----|
| `mcp-server/index.mjs` | ✅ implemented | — |
| `mcp-server/package.json` v0.3.1 | ✅ exists | Not yet published to npm registry |
| `mcp-server/pyproject.toml` v0.3.1 | ✅ exists | Not yet published to PyPI; `src/coherence_mcp_server/` Python package missing |
| `mcp-server/server.json` | ✅ exists | Needs `mcp-publisher` `$schema` validation and `python` entry |
| `.github/workflows/` | ✅ CI exists | No `publish.yml` workflow |
| `GET /api/discovery/registry-stats` | ❌ not yet built | Spec 180 (impl pending) |
| npm download tracking | ❌ absent | New: `registry_stats_service.py` downloads npm API count |
| PyPI download tracking | ❌ absent | New: `registry_stats_service.py` downloads PyPI stats API count |

---

## Architecture

```
mcp-server/
  index.mjs                  ← npm entry point (Node ≥ 18, ESM)
  package.json               ← npm manifest (name, version, bin, files)
  pyproject.toml             ← PyPI manifest (hatchling, scripts entry)
  server.json                ← MCP manifest (consumed by mcp-publisher)
  src/
    coherence_mcp_server/
      __init__.py
      __main__.py            ← python -m coherence_mcp_server
      server.py              ← Python MCP server (delegates to api backend)

.github/workflows/
  publish.yml                ← Release workflow: npm publish + PyPI publish

api/app/services/
  registry_stats_service.py  ← NEW: fetch npm + PyPI download counts
  registry_discovery_service.py  ← Extended: add "npm" and "pypi" stat sources

api/app/routers/
  registry_discovery.py      ← Extended: add GET /api/discovery/registry-stats
                                and GET /api/discovery/registry-dashboard
```

---

## File Changes

### 1. `mcp-server/src/coherence_mcp_server/__init__.py` — NEW

```python
"""Coherence Network MCP server — Python package."""
__version__ = "0.3.1"
```

### 2. `mcp-server/src/coherence_mcp_server/__main__.py` — NEW

```python
"""Entry point: python -m coherence_mcp_server"""
import subprocess
import sys
import os
from pathlib import Path

def main() -> None:
    """Launch the Node.js MCP server bundled with this package."""
    server_js = Path(__file__).parent / "index.mjs"
    env = os.environ.copy()
    env.setdefault("COHERENCE_API_URL", "https://api.coherencycoin.com")
    proc = subprocess.run(
        ["node", str(server_js)],
        env=env,
    )
    sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
```

### 3. `mcp-server/pyproject.toml` — UPDATE

Add `[tool.hatch.build.targets.wheel].include` to bundle `index.mjs`
alongside the Python package so `pip install coherence-mcp-server` brings
the Node binary along:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/coherence_mcp_server"]
include-data = [
  { from = ".", include = ["index.mjs"] },
]
```

Also verify the `[project.scripts]` entry:
```toml
[project.scripts]
coherence-mcp-server = "coherence_mcp_server.__main__:main"
```

### 4. `mcp-server/server.json` — UPDATE

Add Python package entry and ensure `mcp-publisher` `$schema` is present:

```json
{
  "$schema": "https://registry.modelcontextprotocol.io/schemas/server.json",
  "name": "coherence-mcp-server",
  "version": "0.3.1",
  "description": "MCP server for the Coherence Network — tools for ideas, specs, lineage, identity, and contributions.",
  "repository": "https://github.com/seeker71/Coherence-Network",
  "homepage": "https://coherencycoin.com",
  "license": "MIT",
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
  ...
}
```

### 5. `.github/workflows/publish.yml` — NEW

```yaml
name: Publish MCP Server

on:
  push:
    tags:
      - 'v[0-9]+.[0-9]+.[0-9]+'

jobs:
  publish-npm:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: mcp-server
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          registry-url: 'https://registry.npmjs.org'
      - run: npm ci
      - run: npm publish --access public
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}

  publish-pypi:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: mcp-server
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install hatch
      - run: hatch build
      - run: hatch publish
        env:
          HATCH_INDEX_USER: __token__
          HATCH_INDEX_AUTH: ${{ secrets.PYPI_TOKEN }}
```

### 6. `api/app/services/registry_stats_service.py` — NEW (partial, tied to spec 180 impl)

```python
"""Fetch live install/download counts from npm and PyPI registries."""
from __future__ import annotations
import httpx
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
CACHE_DIR = Path(".cache/registry_stats")
CACHE_TTL = timedelta(hours=24)

NPM_PACKAGE = "coherence-mcp-server"
PYPI_PACKAGE = "coherence-mcp-server"

async def fetch_npm_downloads(refresh: bool = False) -> dict:
    """Fetch weekly download count from npm registry API."""
    cache_file = CACHE_DIR / "npm.json"
    cached = _read_cache(cache_file)
    if cached and not refresh:
        return {**cached, "source": "cached"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"https://api.npmjs.org/downloads/point/last-week/{NPM_PACKAGE}"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            result = {
                "registry_id": "npm",
                "install_count": data.get("downloads", 0),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "source": "live",
            }
            _write_cache(cache_file, result)
            return result
    except Exception as exc:
        logger.warning("npm stats fetch failed: %s", exc)
        if cached:
            return {**cached, "source": "cached"}
        return {"registry_id": "npm", "install_count": None, "source": "unavailable", "error": str(exc)}

async def fetch_pypi_downloads(refresh: bool = False) -> dict:
    """Fetch recent download count from PyPI stats via pypistats.org."""
    cache_file = CACHE_DIR / "pypi.json"
    cached = _read_cache(cache_file)
    if cached and not refresh:
        return {**cached, "source": "cached"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"https://pypistats.org/api/packages/{PYPI_PACKAGE}/recent"
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            result = {
                "registry_id": "pypi",
                "install_count": data.get("data", {}).get("last_week", 0),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "source": "live",
            }
            _write_cache(cache_file, result)
            return result
    except Exception as exc:
        logger.warning("PyPI stats fetch failed: %s", exc)
        if cached:
            return {**cached, "source": "cached"}
        return {"registry_id": "pypi", "install_count": None, "source": "unavailable", "error": str(exc)}

def _read_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at < CACHE_TTL:
            return data
    except Exception:
        pass
    return None

def _write_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
```

---

## API Changes

This spec extends spec 180's data layer. The following endpoints are **required**
by this spec (and must be implemented, whether by spec 180's impl or here):

### `GET /api/discovery/registry-stats`

Returns download counts per registry. This spec requires `npm` and `pypi`
entries with live counts from the npm downloads API and pypistats.org.

```json
{
  "summary": {
    "total_installs": 42,
    "registries_with_counts": 2,
    "registries_unavailable": 4,
    "last_updated": "2026-03-28T22:00:00Z"
  },
  "items": [
    {
      "registry_id": "npm",
      "registry_name": "npm",
      "install_count": 37,
      "source": "live",
      "fetched_at": "2026-03-28T22:00:00Z"
    },
    {
      "registry_id": "pypi",
      "registry_name": "PyPI",
      "install_count": 5,
      "source": "cached",
      "fetched_at": "2026-03-28T21:00:00Z"
    },
    {
      "registry_id": "smithery",
      "registry_name": "Smithery",
      "install_count": null,
      "source": "unavailable",
      "error": "no public stats API"
    }
  ]
}
```

Query params:
- `?refresh=true` — bypass 24-hour cache and fetch live
- `?registry_id=npm` — filter to one registry

### `GET /api/discovery/registry-dashboard`

Merges submission readiness (spec 180) with download counts (this spec) into
a single response. Must be HTTP 200 even when all stat fetches fail.

### `POST /api/discovery/publish-event` — NEW

Record a publish event (manual trigger when CI publishes a new version):

```json
{
  "registry": "npm",
  "version": "0.3.1",
  "published_at": "2026-03-28T22:00:00Z"
}
```

Returns `{"id": "<uuid>", "registry": "npm", "version": "0.3.1", "recorded": true}`.

Allows the CI workflow to ping the API after each publish so the dashboard
always reflects the latest known version.

---

## Data Model

### `PublishEvent` (new Pydantic model)

```python
class PublishEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    registry: Literal["npm", "pypi"]
    version: str       # semver string, e.g. "0.3.1"
    published_at: datetime
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sha: str | None = None  # git SHA of the commit tagged for this release

class PublishEventList(BaseModel):
    items: list[PublishEvent]
    latest_npm_version: str | None
    latest_pypi_version: str | None
```

### `GET /api/discovery/publish-events`

Returns `PublishEventList`. Allows the dashboard to show "last published:
v0.3.1 on 2026-03-28" for each registry.

---

## Version Management

- Single source of truth: `mcp-server/package.json` `.version` field.
- `mcp-server/pyproject.toml` version must match `package.json` version.
- `mcp-server/server.json` package entries must match both.
- A pre-commit hook or CI check should fail if the three versions diverge.

### Version Sync Check (CI)

```yaml
- name: Check version sync
  run: |
    NPM_VER=$(node -p "require('./mcp-server/package.json').version")
    PY_VER=$(python3 -c "import tomllib; d=tomllib.load(open('mcp-server/pyproject.toml','rb')); print(d['project']['version'])")
    JSON_VER=$(python3 -c "import json; d=json.load(open('mcp-server/server.json')); print(d['version'])")
    if [ "$NPM_VER" != "$PY_VER" ] || [ "$NPM_VER" != "$JSON_VER" ]; then
      echo "Version mismatch: npm=$NPM_VER pypi=$PY_VER server.json=$JSON_VER"
      exit 1
    fi
```

---

## Proof That It Is Working

The question "is this working yet, and how do we prove that over time?" is central
to this spec. Here is the layered proof system:

### Layer 1 — Package exists on registries (static proof)

```bash
# npm
curl -s https://registry.npmjs.org/coherence-mcp-server/latest | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['version'])"
# Expected: 0.3.1

# PyPI
curl -s https://pypi.org/pypi/coherence-mcp-server/json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['version'])"
# Expected: 0.3.1
```

### Layer 2 — Package is runnable (functional proof)

```bash
# npm (zero-install)
npx coherence-mcp-server &
sleep 2
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | node -e "
const {StdioClientTransport}=require('@modelcontextprotocol/sdk/client/stdio.js');
// ... client call
"
# Expected: JSON response listing 14+ tools

# PyPI
pip install coherence-mcp-server
coherence-mcp-server &
# Same MCP protocol test
```

### Layer 3 — Download counts over time (growth proof)

```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); [print(i['registry_id'], i['install_count'], i['source']) for i in d['items']]"
# Expected:
# npm 37 live
# pypi 5 cached
# smithery None unavailable
```

- Call weekly and store results.
- A monotonically increasing `install_count` for `npm` or `pypi` over consecutive
  weeks is the definitive proof of adoption.

### Layer 4 — Publish events recorded (pipeline proof)

```bash
curl -s "https://api.coherencycoin.com/api/discovery/publish-events" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['latest_npm_version'], d['latest_pypi_version'])"
# Expected: 0.3.1 0.3.1
```

If the version here diverges from what `registry-stats` reports, the publish
pipeline broke silently — immediately actionable.

---

## Verification Scenarios

### Scenario 1 — npm package resolves and has correct metadata

**Setup:** `coherence-mcp-server@0.3.1` is published to npm.

**Action:**
```bash
curl -s https://registry.npmjs.org/coherence-mcp-server/latest | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['name'], d['version'], d.get('bin',{}))"
```

**Expected:**
```
coherence-mcp-server 0.3.1 {'coherence-mcp-server': 'index.mjs'}
```

**Edge — package not yet published:**
Response is HTTP 404 from npm registry. `GET /api/discovery/registry-submissions`
returns `smithery` with `status: "missing_assets"` if `packages[].version` in
`server.json` doesn't match any published npm release.

---

### Scenario 2 — PyPI package installs and CLI entry point works

**Setup:** `coherence-mcp-server==0.3.1` is published to PyPI.

**Action:**
```bash
pip install coherence-mcp-server==0.3.1 --quiet
coherence-mcp-server --version 2>/dev/null || echo "running server"
# Start and send MCP initialize
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | timeout 5 coherence-mcp-server 2>/dev/null | head -1
```

**Expected:** JSON response `{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05",...}}`

**Edge — PyPI upload fails during CI:** The `publish-pypi` job exits non-zero.
The `POST /api/discovery/publish-event` step is skipped. `GET /api/discovery/publish-events`
still returns the last successful version, and `latest_pypi_version` does not update.

---

### Scenario 3 — Download counts visible via API (create-read cycle)

**Setup:** Both packages published; `registry_stats_service.py` is deployed.

**Action (read live counts):**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats?refresh=true" | \
  python3 -c "
import sys,json
d=json.load(sys.stdin)
npm=[i for i in d['items'] if i['registry_id']=='npm'][0]
pypi=[i for i in d['items'] if i['registry_id']=='pypi'][0]
print('npm:', npm['install_count'], npm['source'])
print('pypi:', pypi['install_count'], pypi['source'])
print('total:', d['summary']['total_installs'])
"
```

**Expected:** Both items have `source: "live"`. `install_count` is an integer ≥ 0.
`total_installs` = sum of non-null counts.

**Then (record a publish event):**
```bash
curl -s -X POST "https://api.coherencycoin.com/api/discovery/publish-event" \
  -H "Content-Type: application/json" \
  -d '{"registry":"npm","version":"0.3.1","published_at":"2026-03-28T22:00:00Z"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['recorded'], d['registry'], d['version'])"
```
**Expected:** `True npm 0.3.1`

**Then (list events to confirm):**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/publish-events" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['latest_npm_version'])"
```
**Expected:** `0.3.1`

**Edge — duplicate publish event:** POST same `{registry, version}` twice → second
response returns `{"recorded": false, "reason": "already_exists"}` (idempotent).

---

### Scenario 4 — CI publish workflow triggers correctly on tag push

**Setup:** A commit tagged `v0.3.2` is pushed to `origin`.

**Action (simulate via GitHub API / observed in Actions UI):**
```bash
gh run list --workflow=publish.yml --json conclusion,headBranch,createdAt | \
  python3 -c "import sys,json; runs=json.load(sys.stdin); print(runs[0]['conclusion'], runs[0]['headBranch'])"
```

**Expected:** `success refs/tags/v0.3.2`

Both `publish-npm` and `publish-pypi` jobs succeed. After the run:
```bash
curl -s https://registry.npmjs.org/coherence-mcp-server/latest | python3 -c "import sys,json; print(json.load(sys.stdin)['version'])"
# → 0.3.2
curl -s https://pypi.org/pypi/coherence-mcp-server/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"
# → 0.3.2
```

**Edge — tag without version bump:** If `package.json` still reads `0.3.1` when
tag `v0.3.2` is pushed, `npm publish` will reject with `E403 You cannot publish
over the previously published versions`. Workflow fails, Slack/email alert fires.

---

### Scenario 5 — Stats API gracefully degrades when npm API is unreachable

**Setup:** npm downloads API is unreachable (simulated by pointing to an invalid host
in a test env, or using the mock in unit tests).

**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/discovery/registry-stats" | \
  python3 -c "
import sys,json
d=json.load(sys.stdin)
npm=[i for i in d['items'] if i['registry_id']=='npm'][0]
print('HTTP status was 200 (no exception)')
print('npm source:', npm['source'])
print('npm error:', npm.get('error'))
print('other items unaffected:', all(i['source']!='unavailable' for i in d['items'] if i['registry_id']!='npm'))
"
```

**Expected:**
```
HTTP status was 200 (no exception)
npm source: unavailable
npm error: upstream timeout
other items unaffected: True
```

No 500 error is returned regardless of upstream failures.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| npm `coherence-mcp-server` name may be taken | Check `npm view coherence-mcp-server` before implementation; reserve package under org scope `@coherence-network/mcp-server` as fallback |
| PyPI name collision | `pip index versions coherence-mcp-server` to verify name is unclaimed |
| Python PyPI package requires Node to run (non-standard) | `__main__.py` checks for `node` binary and emits a clear error if missing; README documents the dependency |
| Secrets `NPM_TOKEN` and `PYPI_TOKEN` not configured in GitHub | CI workflow fails at publish step; must be added to repository secrets before tagging |
| `server.json` not picked up by mcp-publisher | Validate locally with `npx mcp-publisher validate mcp-server/server.json` before submitting PR |
| pypistats.org API may be rate-limited | 24-hour cache means at most 1 request/day/instance; no risk at current scale |
| Version drift between package.json / pyproject.toml / server.json | Version sync CI check (see Version Management section) blocks merges when versions diverge |

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| AC1 | `npm view coherence-mcp-server version` returns the expected semver. |
| AC2 | `pip index versions coherence-mcp-server` lists at least one version. |
| AC3 | `npx coherence-mcp-server` starts the MCP server (exits 0 when piped an empty stdin with `--help` flag or responds to MCP `initialize`). |
| AC4 | `pip install coherence-mcp-server` installs successfully and `coherence-mcp-server` binary is available. |
| AC5 | `.github/workflows/publish.yml` exists, triggers on `v*.*.*` tags, and runs both `publish-npm` and `publish-pypi` jobs. |
| AC6 | `mcp-server/server.json` has both `npm` and `pypi` entries in `packages[]` with matching version. |
| AC7 | `GET /api/discovery/registry-stats` returns `npm` and `pypi` items with `source` in `["live","cached","unavailable"]`. |
| AC8 | `POST /api/discovery/publish-event` records an event and `GET /api/discovery/publish-events` reflects it. |
| AC9 | Version sync CI check fails when `package.json` and `pyproject.toml` versions differ. |
| AC10 | When npm or PyPI stats APIs are unreachable, `GET /api/discovery/registry-stats` returns HTTP 200 with `source: "unavailable"` — no 500. |

---

## Known Gaps and Follow-up Tasks

- [ ] **Spec 183** — Web dashboard panel at `/discovery` rendering `RegistryDashboard`
  with npm/PyPI download sparklines and "last published" badges.
- [ ] **Scope 184** — Automated version-bump PR: when a release is tagged, open a
  PR that bumps `package.json`, `pyproject.toml`, and `server.json` in sync.
- [ ] `mcp-server/src/coherence_mcp_server/` Python package stub needs to be created
  (implementation task, not spec scope).
- [ ] Investigate whether Smithery's `mcp-publisher` CLI also consumes PyPI entries;
  if so, ensure `server.json` `packages[].registry = "pypi"` is the correct key.
- [ ] `npm publish --provenance` (Sigstore) requires npm ≥ 9 and token with
  `write:packages` scope — evaluate for supply-chain security.
- [ ] Add weekly cron job (`0 9 * * 1`) to call
  `GET /api/discovery/registry-stats?refresh=true` and append to a PostgreSQL
  time-series table for long-term trend analysis.
