# Spec: MCP and skill registry discovery (5+ surfaces) + install metrics

## Summary

Coherence Network ships a typed MCP server (`coherence-mcp-server`) and a portable Agent skill (`coherence-network`). To grow adoption, both must be **discoverable** on at least **five independent registry or directory surfaces** (Smithery, Glama via `awesome-mcp-servers`, PulseMCP, MCP.so, skills.sh, askill.sh—plus existing npm/ClawHub/AgentSkills coverage where applicable). This spec defines the **operational submission playbook**, **evidence artifacts**, **metrics capture** for installs/downloads, and **API inventory** alignment so humans and automation can prove readiness and track impact over time.

**Goal:** Register or list the MCP server and skill on the named discovery surfaces; persist proof links and periodic install/download counts; expose a machine-readable inventory via the existing discovery API so production verification is one `curl` away.

## Purpose

Discovery registries are the primary funnel for developers finding MCP servers and skills. Without deliberate listing and measurable adoption signals, we cannot tell whether packaging work translated into usage. This spec ties **external listing work** to **in-repo assets** (manifests, README, SKILL.md) and **observable metrics**, reducing guesswork and making regressions visible when manifests drift.

## Requirements

1. **Minimum surface coverage:** Achieve **submission or merge acceptance** on at least **five** distinct discovery surfaces from this set (MCP unless noted): Smithery, Glama (`awesome-mcp-servers` PR), PulseMCP, MCP.so, **and** skill directories **skills.sh** and **askill.sh** for the `coherence-network` skill. npm registry and ClawHub may count as additional proof but do not replace the five named external surfaces.
2. **Asset consistency:** `mcp-server/server.json`, `mcp-server/package.json`, `mcp-server/README.md`, `skills/coherence-network/SKILL.md`, and root `README.md` remain the canonical sources referenced by listings; any registry-specific metadata files are additive, not forks of behavior.
3. **Metrics tracking:** Capture **install count, download count, or closest public proxy** (stars, weekly downloads, listing “uses”) per registry **at least monthly**, stored under `docs/system_audit/` as versioned JSON (see Data model) with ISO timestamps and source URLs.
4. **Inventory API:** The running API exposes **`GET /api/discovery/registry-submissions`** returning an inventory whose `summary.core_requirement_met` reflects **submission readiness** for defined targets (implementation extends `_TARGETS` in `registry_discovery_service.py` to include Glama, PulseMCP, skills.sh, askill.sh as first-class rows with validators and notes).
5. **Documentation:** Add or update a short **runbook section** (existing `docs/RUNBOOK.md` or `docs/MCP-SKILL-REGISTRY.md` if created by implementation) describing how to submit to each surface and where metrics snapshots live—**only if** the implementation task explicitly lists that file; this spec recommends the path for follow-up work.
6. **No scope creep:** Listing copy and third-party moderation timelines are outside code control; the contract is **evidence of attempt + merge/link** and **metrics when available**.

## Research Inputs (Required)

| Date | Source | Why it matters |
|------|--------|----------------|
| 2026-03-28 | [Smithery](https://smithery.ai/) | MCP server distribution and install analytics patterns. |
| 2026-03-28 | [Glama — awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) | PR-based inclusion for MCP directory discovery. |
| 2026-03-28 | [PulseMCP](https://www.pulsemcp.com/) | Directory and adoption signals for MCP servers. |
| 2026-03-28 | [MCP.so](https://mcp.so/) | Search and ranking for MCP listings. |
| 2026-03-28 | [skills.sh](https://skills.sh/) / [askill.sh](https://askill.sh/) | Skill registry discovery surfaces for portable skills. |
| 2026-03-28 | [Model Context Protocol — registry schema](https://registry.modelcontextprotocol.io/) | Validates `server.json` shape for MCP packaging. |

## Open Questions (addressed)

| Question | Direction |
|----------|-----------|
| How can we improve this idea? | Treat each registry as a **row** in the inventory with explicit `required_files` and validators; automate **monthly** metric snapshots via CI or a scheduled script; add **deep links** to listing URLs in the inventory model (follow-up field). |
| How do we show whether it is working? | Combine **`core_requirement_met`** (readiness) with **external metrics snapshots** (growth/flat/decline) and optional referrer logs if the MCP server reports version pings later. |
| How do we make proof clearer over time? | Append-only **`docs/system_audit/registry_metrics_YYYY-MM.json`** files; each entry includes `captured_at_utc`, `registry_id`, `metric_name`, `value`, `source_url`; diff-friendly for reviewers. |

## API Contract

### `GET /api/discovery/registry-submissions`

**Purpose:** Machine-readable readiness and (after implementation extension) listing references for all registry targets.

**Request**

- No query parameters (MVP).

**Response 200** (`RegistrySubmissionInventory`)

- `summary.target_count`: integer ≥ 5 after targets include Glama, PulseMCP, skills.sh, askill.sh, Smithery, MCP.so (exact set in implementation).
- `summary.submission_ready_count`: count of items with `status == "submission_ready"`.
- `summary.core_requirement_met`: boolean; **true** iff `submission_ready_count >= 5` (existing rule—document any change if product adjusts threshold).
- `items[]`: each `RegistrySubmissionRecord` includes `registry_id`, `registry_name`, `category` (`mcp` \| `skill`), `status`, `install_hint`, `missing_files`, `notes`.

**Response errors**

- Standard FastAPI behavior: unknown paths under `/api` return **404** with `{"detail":"Not Found"}` (verify with mistyped path).

### Future (optional follow-up spec—not blocking this discovery initiative)

### `GET /api/discovery/registry-metrics`

- Returns latest merged snapshot from `docs/system_audit/registry_metrics_*.json` or DB—define in implementation spec when metrics are automated.

## Data Model

### Existing (API)

- `RegistrySubmissionRecord`, `RegistrySubmissionInventory` — see `api/app/models/registry_discovery.py`.

### Metrics evidence (file-based, committed)

```yaml
RegistryMetricSnapshot:
  captured_at_utc: { type: string, format: iso8601 }
  registry_id: { type: string }
  registry_name: { type: string }
  category: { type: string, enum: [mcp, skill] }
  metrics:
    - name: { type: string }  # e.g. installs_30d, downloads_all_time, stars
      value: { type: number }
      unit: { type: string }
  source_urls:
    - { type: string, format: uri }
  notes: { type: string }
```

Store as **`docs/system_audit/registry_metrics_<YYYY-MM>.json`** (array of snapshots or wrapped object with `snapshots: []`).

## Files to Create/Modify (implementation follow-up)

- `api/app/services/registry_discovery_service.py` — extend `_TARGETS` for Glama, PulseMCP, skills.sh, askill.sh (validators: link or file presence in docs, or README section markers agreed in review).
- `api/app/models/registry_discovery.py` — optional: `listing_url` per item when implementation adds it.
- `docs/system_audit/registry_metrics_2026-03.json` — first metrics file after listings go live.
- `README.md` — badges or “Listed on” links (optional, if spec for web/docs allows).

## Task Card (Required)

```yaml
goal: List coherence MCP server and coherence-network skill on 5+ discovery registries and record periodic install/download metrics with API-visible readiness.
files_allowed:
  - api/app/services/registry_discovery_service.py
  - api/app/models/registry_discovery.py
  - docs/system_audit/registry_metrics_YYYY-MM.json
  - docs/RUNBOOK.md
done_when:
  - GET /api/discovery/registry-submissions returns target_count >= 5 and items include smithery, mcp-so, glama or awesome-mcp-servers, pulsemcp, skills-sh, askill-sh identifiers.
  - At least one registry_metrics_*.json exists with captured metrics or explicit nulls where APIs do not expose numbers.
commands:
  - curl -sS https://api.coherencycoin.com/api/discovery/registry-submissions | jq '.summary, .items[].registry_id'
  - cd api && pytest -q api/tests/test_registry_discovery_api.py
constraints:
  - Do not fork skill or MCP behavior into registry-specific codebases; listings point to this repo.
```

## Acceptance Criteria

1. **Coverage:** Five or more distinct external discovery surfaces have **verifiable links or merged PRs** documented in metrics JSON or README “Listed on” section.
2. **API:** Production `GET /api/discovery/registry-submissions` returns **200** and includes rows for each implemented target; `core_requirement_met` is meaningful (not always false due to missing validators).
3. **Metrics:** At least **one** monthly (or initial) snapshot file exists under `docs/system_audit/` with schema above.
4. **Regression:** Removing `mcp-server/server.json` or breaking `skills/coherence-network/SKILL.md` causes corresponding items to show `missing_assets` in inventory after implementation wires validators.

## Verification Scenarios

### Scenario 1 — Readiness inventory (happy path)

- **Setup:** Production API is deployed; repo assets for MCP and skill are intact.
- **Action:**  
  `curl -sS https://api.coherencycoin.com/api/discovery/registry-submissions`
- **Expected:** HTTP **200**; JSON includes `"summary"` with `"target_count"` ≥ **5**, `"items"` is a non-empty array; each item has `"registry_id"`, `"category"`, `"status"`, and `"install_hint"`.
- **Edge (bad path):**  
  `curl -sS -o /dev/null -w "%{http_code}" https://api.coherencycoin.com/api/discovery/registry-submissions/typo`  
  **Expected:** HTTP **404** (not 500).

### Scenario 2 — Error handling and stability

- **Setup:** Same as Scenario 1.
- **Action:**  
  `curl -sS https://api.coherencycoin.com/api/discovery/registry-submissions` | jq '.summary.core_requirement_met, .summary.missing_asset_count'
- **Expected:** Both fields present; `core_requirement_met` is boolean; `missing_asset_count` is a non-negative integer.
- **Edge:** Request with unsupported method **POST** to the same path (if not implemented):  
  `curl -sS -o /dev/null -w "%{http_code}" -X POST https://api.coherencycoin.com/api/discovery/registry-submissions`  
  **Expected:** HTTP **405** Method Not Allowed (FastAPI default) or **404** if routed elsewhere—document actual behavior once; must not return **500**.

### Scenario 3 — Create–read–update cycle for metrics evidence (file + read)

- **Setup:** No prior month file for the current month in the reviewer’s branch (or use a test month).
- **Action (create):** Add `docs/system_audit/registry_metrics_2026-03.json` with at least one snapshot for `registry_id: "smithery"` and `captured_at_utc` set.
- **Action (read):** `git show HEAD:docs/system_audit/registry_metrics_2026-03.json | jq '.snapshots[0].registry_id // .[0].registry_id'`
- **Expected:** JSON parses; registry id is **smithery** (or array equivalent).
- **Edge (duplicate):** Second snapshot same month with duplicate `registry_id` and same `captured_at_utc`—process should **merge or reject** in automation; manual spec: reviewers ensure one logical row per registry per month.

### Scenario 4 — Skill vs MCP categorization

- **Setup:** API returns inventory.
- **Action:**  
  `curl -sS https://api.coherencycoin.com/api/discovery/registry-submissions | jq '[.items[] | select(.category=="skill")] | length'`
- **Expected:** Count ≥ **1** (coherence-network skill targets).
- **Edge:** Invalid category filter client-side—API still returns full list; no server crash.

### Scenario 5 — Proof over time (documentation check)

- **Setup:** Two monthly metric files exist for consecutive months.
- **Action:** Compare `captured_at_utc` and metric values in both files with `diff` or `jq`.
- **Expected:** Later file shows non-decreasing understanding (values may be null if provider hides stats—then `notes` explains the gap).
- **Edge:** Missing file for a month—CI or review checklist flags **absent snapshot** as debt, not a runtime 500.

## Risks and Assumptions

- **Risks:** Third-party registries change submission rules; PRs to `awesome-mcp-servers` may lag; some sites may not expose numeric installs—**mitigation:** store **link + screenshot or archive.org link** in `notes` when metrics are unavailable.
- **Assumptions:** `api.coherencycoin.com` remains the production base URL for verification; if it changes, update this spec’s curl examples in the same PR as DNS/docs.

## Known Gaps and Follow-up Tasks

- Automate metric pulls where APIs exist (Smithery/npm download counts).
- Add optional `listing_url` field to inventory items once URLs are stable.
- Wire **PulseMCP** and **Glama** validators to concrete repo artifacts (e.g., merged PR number in `docs/system_audit/commit_evidence_*.json`).

## Out of Scope

- Paid promotion or SEO campaigns.
- Forking the MCP server per registry.
- Web UI pages unless a separate web spec is opened; this spec’s network contract is **GET /api/discovery/registry-submissions** plus audit files.

## Failure/Retry Reflection

- **Failure mode:** Registry rejects listing for policy reasons.  
- **Blind spot:** Assuming numeric metrics exist everywhere.  
- **Next action:** Record rejection reason in metrics `notes` and retry on next policy window with minimal asset diff.

---

## Verification (CI / local)

```bash
curl -sS https://api.coherencycoin.com/api/discovery/registry-submissions | jq .
cd api && pytest -q api/tests/test_registry_discovery_api.py 2>/dev/null || true
```

(Second line applies once tests exist; spec author leaves `|| true` only for environments without tests—implementers must remove escape when tests land.)
