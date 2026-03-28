# Spec: Submit to 5+ MCP and skill registries for discovery

**Idea ID**: `idea-4deb5bd7c800`
**Task ID**: `task_daa7b04df9672625`
**Status**: Draft - 2026-03-28
**Author**: product-manager agent

## Summary

Coherence Network already exposes two discovery-ready artifacts in this repository: the MCP server
entry point in `api/mcp_server.py` and the skill content under `skills/coherence-network/SKILL.md`
and `.cursor/skills/`. Today those artifacts are mostly discoverable through direct links, README
copy, or word of mouth. That is too fragile for a project that wants external contributors and
agent tooling to find it without prior context.

This spec defines the minimum discovery push: submit or list the Coherence Network MCP and skill
artifacts in at least five public registries, store proof of those listings in the repository, and
stop there. The scope stays intentionally narrow. No analytics, no re-sync automation, no paid
placement, and no new mandatory runtime feature work are required to close this item.

## Purpose

Operators and contributors need a repeatable way to prove that Coherence Network's MCP and skill
artifacts are discoverable in the wider ecosystem. Listing on multiple registries reduces
single-point dependency on one directory and aligns with the project's "adapters over features"
posture for external surfaces.

## Requirements

1. **Minimum coverage**: Complete successful submission or accepted listing for at least five
   distinct registries. At least two entries must be MCP-oriented and at least two must be
   skill-oriented. The fifth may be either category.
2. **Canonical source mapping**: Every submission must point back to the same local source-of-truth
   paths: `api/mcp_server.py` for the MCP server and `skills/coherence-network/SKILL.md` or
   `.cursor/skills/` for the skill surface.
3. **Install clarity**: Each registry entry must include the canonical asset name plus a minimal
   install or configuration hint so a reader can find the repo and wire the MCP server or skill
   without reverse-engineering the codebase.
4. **Evidence**: For each registry, store proof in-repo: a public listing URL, a merged PR URL, or
   a screenshot path under `docs/` only if the registry offers no stable public URL.
5. **No scope creep**: Out of scope for this spec: analytics, scheduled re-submission, paid
   placement, OAuth to registries, or any new required API/database work.

## API changes

**Core requirement:** None. Registry submission is a documentation and external-PR workflow, not a
product feature.

**Optional only if already modeled:** A read-only endpoint such as
`GET /api/registry-submissions/inventory` returning a `RegistrySubmissionInventory` is optional and
not required to close this spec. If implemented, it must stay read-only and be backed by static
repo data or build-time data, with no secrets.

## Data model

**Core:** No database migration. Proof lives in version-controlled markdown or JSON under `docs/`
(for example `docs/registry-submissions.md` or `docs/registry-submissions.json`) listing each
registry row with:

- `registry_id`
- `registry_name`
- `category` (`mcp` or `skill`)
- `asset_name`
- `status`
- `install_hint`
- `source_paths`
- `notes`

If an optional inventory endpoint already exists, it may reuse the existing
`RegistrySubmissionRecord`, `RegistrySubmissionSummary`, and `RegistrySubmissionInventory` models.

## Verification criteria

| Check | Pass condition |
|-------|----------------|
| Count | >= 5 distinct registries with documented proof |
| Mix | >= 2 MCP + >= 2 skill registries |
| Traceability | Each entry links to in-repo source paths |
| Minimal scope | No required runtime API, DB migration, or automation work added to close the spec |
| Review | `python3 scripts/validate_spec_quality.py --base origin/main --head HEAD` passes if this spec is touched |

**Manual smoke:** Open each public listing URL or PR from the evidence doc and confirm Coherence
Network appears as intended.

## Risks

1. **Registry policy churn**: Listings may require maintainer approval or break URLs. Mitigation:
   prefer registries with stable listing pages and capture PR numbers for list-based submissions.
2. **Duplicate or conflicting names**: Another project may use a similar name. Mitigation: use the
   official repo/org naming in descriptions and link to the canonical repository.
3. **Scope creep**: Analytics and automation are explicitly excluded because they delay the
   five-registry bar. Mitigation: ship the evidence doc first and open follow-up ideas for metrics.

## Risks and Assumptions

- Assumption: at least five suitable public registries remain open for OSS submissions at
  implementation time; if fewer exist, escalate with a short blocker list instead of widening
  product scope.
- Assumption: the MCP server and skill artifacts in-repo already have enough packaging and README
  clarity for registry maintainers to accept them without additional product work.

## Review record — task `task_2eeb12fa477ac8ae` (2026-03-28)

**Verdict: REVIEW_FAILED** (idea closure criteria not met; partial implementation quality is acceptable).

### What exists and works

- **API (optional per this spec):** `GET /api/discovery/registry-submissions` is implemented in
  `api/app/routers/registry_discovery.py`, backed by `api/app/services/registry_discovery_service.py`,
  with Pydantic models in `api/app/models/registry_discovery.py`. The router is mounted under `/api`
  with tag `discovery` (see `api/app/main.py`). Contract tests live in
  `api/tests/test_registry_discovery_api.py` (asserts HTTP 200, `core_requirement_met`, six target
  registry IDs including `smithery` and `mcp-so`, mix of `mcp` and `skill`, OpenAPI tag).
- **Readiness logic:** Targets are validated against on-disk artifacts (`mcp-server/server.json`,
  `mcp-server/package.json`, `skills/coherence-network/SKILL.md`, `README.md` content). The code is
  straightforward, side-effect free, and suitable for deployment as a read-only inventory.

### Gaps vs this idea spec (blocking)

1. **Evidence artifact missing:** Section “Data model” requires version-controlled proof under
  `docs/` (e.g. `docs/registry-submissions.md` or `docs/registry-submissions.json`) with per-row
  `registry_id`, listing URL or merged PR, status, and `source_paths`. **No such file exists in the
  repository** (glob search for `registry-submissions*` under `docs/` returns nothing). Without
  that, the “>= 5 distinct registries with documented proof” requirement cannot be verified from the
  repo alone.
2. **External submissions not provable from code:** Actual listings on Smithery, Glama,
   PulseMCP, MCP.so, skills.sh, askill.sh (or substitutes) are operational/out-of-band; the current
   implementation only proves **asset readiness**, not **acceptance** on those surfaces.

### Gaps vs broader task narrative (if interpreted as named registries + metrics)

- `registry_discovery_service._TARGETS` includes npm, official MCP registry, ClawHub, and
  AgentSkills rather than first-class rows for Glama, PulseMCP, skills.sh, and askill.sh (as
  described in `specs/task_edfa105d1d6ae46c.md` / `specs/180-mcp-skill-registry-submission.md`).
- **Install/download counts** are explicitly out of scope in *this* idea spec (“No analytics”);
  there is no `registry_stats_service` or metrics endpoint in-tree for the idea file’s scope.

### Open questions — how to improve proof over time

1. **Add the evidence table** in `docs/registry-submissions.json` (or `.md`) and optionally extend
   the API to merge **readiness** (current) with **submitted URL / PR / last-checked** fields read
   from that file—still no live analytics required to satisfy the narrow idea.
2. **Adoption signal:** Where APIs exist (e.g. Smithery/npm), a follow-up idea can add cached
   counts; where they do not, store **manual snapshot date + link** in the evidence file so proof
   strengthens over time without pretending precision.
3. **CI check:** A small script that fails if evidence rows &lt; 5 or mix &lt; 2 MCP / 2 skill would
   make regression visible on every PR.

### Production verification (reviewer could not execute here)

Automated shell/network from this environment was unavailable; a human or runner should confirm:

- `curl -sS https://api.coherencycoin.com/api/discovery/registry-submissions` → HTTP 200,
  `summary.core_requirement_met == true`.
- Same on Railway host if that is the canonical production URL for this deployment.

### DIF

No new code was written in this review task; DIF verify was not applicable.

