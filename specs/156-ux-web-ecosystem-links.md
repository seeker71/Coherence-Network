# Spec: Web Ecosystem Links Surface (`ux-web-ecosystem-links`)

## Purpose

Contributors using the web interface cannot currently discover core ecosystem entry points (GitHub repository, npm packages, CLI install path, API docs, and OpenClaw). This creates a contributor drop-off gap because users must leave the product and search elsewhere for onboarding and integration links. This spec introduces a single, visible ecosystem links surface so contributors can reliably discover and navigate all core project touchpoints from the web UI.

## Requirements

- [ ] R1: The web UI must expose an always-discoverable "Ecosystem" entry point from all primary routes via footer and/or a dedicated page linked in global navigation.
- [ ] R2: The ecosystem surface must include links for: GitHub repository, npm package(s), CLI installation instructions, API docs, and OpenClaw.
- [ ] R3: Each ecosystem entry must display `name`, `purpose`, `url`, and `type` (for example: `source`, `package`, `docs`, `runtime`, `tooling`).
- [ ] R4: External links must open in a new tab with safe link behavior (`target="_blank"` and `rel="noreferrer noopener"`).
- [ ] R5: If a configured link is unavailable, the UI must render a non-blocking "Unavailable" status for that row instead of removing the row.
- [ ] R6: The page must include lightweight contributor guidance describing when to use each link category (build, integrate, contribute, run agents).
- [ ] R7: The feature must not require new backend endpoints; data is sourced from static web configuration defined in the web app codebase.

## Research Inputs (Required)

- `2026-03-26` - Task direction from `task_4351f8a4cb0f24b3` - defines missing ecosystem navigation and required destinations.
- `2026-03-26` - Existing Coherence web spec conventions (`specs/TEMPLATE.md`, `specs/140-oss-interface-alignment.md`) - defines required spec quality format and verification structure.

## Task Card (Required)

```yaml
goal: Add a visible web ecosystem links surface that consistently exposes core project destinations
files_allowed:
  - web/app/layout.tsx
  - web/app/ecosystem/page.tsx
  - web/components/site-footer.tsx
  - web/lib/ecosystem-links.ts
  - web/tests/integration/ecosystem-links.test.tsx
  - specs/156-ux-web-ecosystem-links.md
done_when:
  - Ecosystem entry point is visible from all primary routes and navigates to a rendered links table
  - Links table contains GitHub, npm, CLI, API docs, and OpenClaw rows with required metadata
  - Unavailable link state renders gracefully without runtime errors
commands:
  - cd web && npm run build
  - cd web && npx vitest run tests/integration/ecosystem-links.test.tsx
constraints:
  - No API changes or new backend endpoints
  - No edits outside files_allowed
  - Keep existing navigation structure; only add ecosystem discovery surface
```

## API Contract

N/A - no API contract changes in this spec.

## Data Model (if applicable)

```yaml
EcosystemLink:
  properties:
    id: { type: string }
    name: { type: string }
    purpose: { type: string }
    type: { type: string, enum: [source, package, docs, runtime, tooling] }
    url: { type: string, nullable: true }
    status: { type: string, enum: [available, unavailable] }
```

## Files to Create/Modify

- `specs/156-ux-web-ecosystem-links.md` - feature specification and verification contract
- `web/lib/ecosystem-links.ts` - canonical typed list of ecosystem destinations
- `web/components/site-footer.tsx` - always-visible ecosystem entry point in global footer
- `web/app/layout.tsx` - ensure footer renders across routed pages
- `web/app/ecosystem/page.tsx` - dedicated ecosystem links table and contributor guidance
- `web/tests/integration/ecosystem-links.test.tsx` - rendering and link behavior tests

## Expected UI Behaviors

1. **Global discoverability**
   - A user on any primary route can see an "Ecosystem" link in footer navigation.
   - Selecting it navigates to `/ecosystem`.

2. **Ecosystem table rendering**
   - `/ecosystem` renders a table (or equivalent semantic list) with one row per required destination:
     - GitHub
     - npm
     - CLI install
     - API docs
     - OpenClaw
   - Each row shows `name`, `purpose`, and a CTA link when available.

3. **Unavailable destination behavior**
   - If `url` is missing/empty for a row, row remains visible with:
     - status badge/text: `Unavailable`
     - disabled/non-clickable CTA affordance
     - helper text: "Link not configured yet"

4. **External link security behavior**
   - Available link CTA uses:
     - `target="_blank"`
     - `rel="noreferrer noopener"`

## Acceptance Tests

- `web/tests/integration/ecosystem-links.test.tsx::renders_all_required_ecosystem_rows`
- `web/tests/integration/ecosystem-links.test.tsx::ecosystem_entry_point_visible_in_footer`
- `web/tests/integration/ecosystem-links.test.tsx::external_links_use_safe_target_and_rel`
- `web/tests/integration/ecosystem-links.test.tsx::unavailable_link_row_is_rendered_with_non_clickable_state`

## Test Scenarios

1. **Contributor discovery flow**
   - Given a user opens `/`
   - When they inspect footer actions
   - Then they can click "Ecosystem" and land on `/ecosystem`
   - And they see all required destinations in one surface.

2. **Integration builder flow**
   - Given a user opens `/ecosystem`
   - When they choose "API docs"
   - Then a new tab opens to API documentation URL
   - And the current app tab remains unchanged.

3. **Agent setup flow**
   - Given OpenClaw and CLI rows exist
   - When a user selects either row CTA
   - Then each link opens correctly in a new tab
   - And row purpose text clarifies setup intent.

4. **Missing link resilience**
   - Given a configured ecosystem entry has no URL
   - When `/ecosystem` renders
   - Then the row appears with `Unavailable`
   - And there is no runtime exception or broken layout.

## Edge Cases and Error Handling

- Missing URL for a required destination must not hide the row.
- Duplicate link `id` entries in config should fail test validation to prevent ambiguous rendering.
- Invalid URL format should render row as `Unavailable` and log a non-fatal client warning in development mode.
- If the ecosystem config import fails, `/ecosystem` must show a fallback container:
  - heading: "Ecosystem links temporarily unavailable"
  - retry guidance: "Refresh page or check again shortly"
  - no unhandled error boundary crash.

## Concurrency Behavior

- Read-only UI surface with static config; safe for concurrent requests and navigation.
- No write operations and no locking requirements.

## Verification

```bash
cd web && npx vitest run tests/integration/ecosystem-links.test.tsx
cd web && npm run build
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

Manual verification:
1. Run web app locally.
2. Open `/`, `/ideas`, `/usage`, `/flow`.
3. Confirm footer contains "Ecosystem" on each route.
4. Open `/ecosystem` and confirm all required rows and unavailable-state behavior.

## Out of Scope

- Creating or changing backend/API endpoints
- Dynamic admin editing for ecosystem links
- Localization/internationalization of link copy
- Visual redesign of full global navigation beyond adding ecosystem discoverability

## Risks and Assumptions

- **Risk**: Source URLs can drift over time (renamed docs paths, moved repositories).  
  **Mitigation**: Keep a single canonical config module and test required destination presence.
- **Risk**: Footer-only discoverability might be overlooked by some users.  
  **Mitigation**: Keep option for dedicated page plus optional top-nav link in follow-up.
- **Assumption**: Canonical URLs for GitHub, npm, CLI docs, API docs, and OpenClaw are known and stable at implementation time.
- **Assumption**: Existing web layout permits adding footer link without regressions in responsive behavior.

## Known Gaps and Follow-up Tasks

- Add telemetry for ecosystem link click-through rates to measure onboarding impact. Follow-up task: `task_ecosystem_link_analytics`.
- Add automated link health checks in CI (HTTP status scan for configured URLs). Follow-up task: `task_ecosystem_link_health_checks`.
- Consider adding "Copy command" snippets for CLI and MCP setup in a phase-2 enhancement. Follow-up task: `task_ecosystem_cli_quickstart`.

## Failure/Retry Reflection

- Failure mode: Integration test fails due to route/layout rendering mismatch.
- Blind spot: Footer composition may vary between server and client route trees.
- Next action: Move footer composition to a single shared layout boundary and rerun tests.

## Decision Gates (if any)

- Confirm final destination URLs for npm package(s) and OpenClaw canonical page before implementation merge.
