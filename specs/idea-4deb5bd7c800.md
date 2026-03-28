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

