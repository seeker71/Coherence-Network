# Spec 156: UX web ecosystem links

## Purpose

Contributors landing on the web interface cannot currently discover the rest of the Coherence Network ecosystem (GitHub repository, npm packages, CLI install flow, API docs, and OpenClaw skill) from in-product navigation. This spec adds a single, explicit ecosystem-links surface (footer section or dedicated page linked from footer) so users can move from browsing to contributing and integrating without leaving the site confused.

## Requirements

- [ ] R1: Web UI exposes a visible "Ecosystem" entry point on all primary routes via global footer (or a globally reachable dedicated `/ecosystem` page linked from footer).
- [ ] R2: Ecosystem surface includes a table/list with exactly these resources and labels:
  - GitHub repository
  - CLI package (`coherence-cli`)
  - MCP server package (`coherence-mcp-server`)
  - API docs (`/docs` on API host)
  - OpenClaw skill page
- [ ] R3: Each resource row includes: name, one-line description, link URL, and action label ("Open").
- [ ] R4: External links open in a new tab and include safe external-link attributes (`target="_blank"` and `rel="noopener noreferrer"`).
- [ ] R5: If ecosystem metadata cannot load at runtime, UI renders a deterministic fallback state that still shows the five canonical links from static defaults (no empty block, no crash).
- [ ] R6: At least one web test verifies rendered labels and target URLs exactly, and one test verifies external-link safety attributes.

## Research Inputs (Required)

- `2026-03-26` - [Coherence Network README](https://github.com/seeker71/Coherence-Network) - authoritative source for canonical ecosystem destinations.
- `2026-03-26` - [npm: coherence-cli](https://www.npmjs.com/package/coherence-cli) - official CLI distribution endpoint to expose in web UI.
- `2026-03-26` - [npm: coherence-mcp-server](https://www.npmjs.com/package/coherence-mcp-server) - official MCP package endpoint for AI-agent setup.

## Task Card (Required)

```yaml
goal: Add a globally discoverable ecosystem links surface in web UI with canonical destinations.
files_allowed:
  - specs/156-ux-web-ecosystem-links.md
  - web/app/layout.tsx
  - web/app/page.tsx
  - web/components/site_footer.tsx
  - web/components/ecosystem_links.tsx
  - web/lib/ecosystem_links.ts
  - web/tests/integration/ecosystem-links.test.tsx
done_when:
  - Ecosystem links are visible from homepage and at least one non-home route through global footer or dedicated linked page
  - Integration test asserts all five required resource labels and URLs
  - Integration test asserts target and rel attributes for external links
commands:
  - cd web && npm run build
  - cd web && npx vitest run tests/integration/ecosystem-links.test.tsx
constraints:
  - Use only canonical URLs listed in this spec
  - Do not remove existing footer/legal/status content when adding ecosystem links
```

## API Contract (if applicable)

N/A - no API contract changes in this spec.

## Data Model (if applicable)

N/A - no backend model changes in this spec.

## UI Contract

The ecosystem surface MUST render these rows exactly (labels may include title case variants, URLs must match):

| Key | Display name | Description | URL |
|-----|--------------|-------------|-----|
| `github` | `GitHub` | `Contribute code, issues, and pull requests.` | `https://github.com/seeker71/Coherence-Network` |
| `cli` | `CLI (coherence-cli)` | `Install the cc CLI for terminal workflows.` | `https://www.npmjs.com/package/coherence-cli` |
| `mcp` | `MCP Server (coherence-mcp-server)` | `Connect your AI agent with Coherence tools.` | `https://www.npmjs.com/package/coherence-mcp-server` |
| `api_docs` | `API Docs` | `Build integrations with the public API.` | `https://api.coherencycoin.com/docs` |
| `openclaw` | `OpenClaw` | `Enable the Coherence Network skill in OpenClaw.` | `https://clawhub.com/skills/coherence-network` |

## Files to Create/Modify

- `specs/156-ux-web-ecosystem-links.md` - feature specification
- `web/app/layout.tsx` - ensure ecosystem entry point is globally reachable
- `web/components/site_footer.tsx` - render ecosystem links section or link to dedicated page
- `web/components/ecosystem_links.tsx` - ecosystem table/list component
- `web/lib/ecosystem_links.ts` - canonical link constants used by UI and tests
- `web/tests/integration/ecosystem-links.test.tsx` - rendering and link-attribute contract tests

## Acceptance Tests

- `web/tests/integration/ecosystem-links.test.tsx::renders_required_ecosystem_resources`
- `web/tests/integration/ecosystem-links.test.tsx::uses_canonical_urls`
- `web/tests/integration/ecosystem-links.test.tsx::external_links_use_noopener_noreferrer`
- `web/tests/integration/ecosystem-links.test.tsx::fallback_state_still_renders_static_links`

## Verification

```bash
cd web && npm run build
cd web && npx vitest run tests/integration/ecosystem-links.test.tsx
```

### Verification Scenarios

1. **Scenario 1 - Discoverability from web UI**
   - Action: Open `/` and one secondary route (for example `/ideas`), then navigate to footer.
   - Expected behavior: "Ecosystem" section or link is visible in both routes without scrolling through hidden menus.
   - Pass criteria: User reaches full ecosystem table in <=2 clicks from either route.

2. **Scenario 2 - Canonical destination integrity**
   - Action: Inspect rendered links for GitHub, CLI, MCP, API Docs, OpenClaw.
   - Expected behavior: `href` matches exactly the URLs listed in UI Contract table.
   - Pass criteria: 5/5 links match exact canonical URL strings.

3. **Scenario 3 - External navigation safety**
   - Action: Inspect anchor attributes for each external resource.
   - Expected behavior: each has `target="_blank"` and `rel` containing both `noopener` and `noreferrer`.
   - Pass criteria: 5/5 links include required attributes.

4. **Scenario 4 - Runtime failure fallback**
   - Action: Simulate metadata load failure (throw in data loader or return null).
   - Expected behavior: UI shows a non-blocking notice and still renders the five static fallback links.
   - Pass criteria: page renders without uncaught error and all required links remain actionable.

## Edge Cases and Error Handling Expectations

- If any optional dynamic metadata fetch fails, component falls back to static canonical dataset defined in `web/lib/ecosystem_links.ts`.
- If one link URL is missing/empty in source data, UI skips invalid row and logs a non-fatal warning; fallback dataset restores missing canonical row.
- If external destination is temporarily unavailable (DNS/5xx), UI behavior remains unchanged; user click still opens destination in new tab.
- If footer is collapsed on small screens, ecosystem entry point remains reachable without horizontal overflow or clipped text.

## Out of Scope

- Adding telemetry/analytics for outbound link clicks
- Introducing new ecosystem resources beyond the five required links
- Backend APIs for ecosystem resources
- Information architecture redesign beyond adding discoverable ecosystem access

## Risks and Assumptions

- Risk: Footer density increases and hurts readability on mobile; mitigate with compact row layout and responsive wrapping.
- Risk: URL drift if external destinations change; mitigate by centralizing constants in one module and testing exact URLs.
- Assumption: Canonical destinations in README are the source of truth for this release cycle.
- Assumption: Current web routes already share a global layout/footer insertion point.

## Known Gaps and Follow-up Tasks

- Add click-through analytics to measure conversion from web visitors to contributors (`follow-up: task_ux_ecosystem_links_analytics`).
- Consider localized copy for ecosystem descriptions if multilingual support is introduced.
- Evaluate adding a dedicated `/ecosystem` hero/introduction page if footer-only discoverability underperforms.

## Failure/Retry Reflection

- Failure mode: implementation adds links only on homepage, not globally.
- Blind spot: local testing focused on `/` route only.
- Next action: add integration assertion for at least one non-home route render path.
