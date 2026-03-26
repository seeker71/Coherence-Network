# Spec: UX — Idea detail call to action

## Purpose

Visitors landing on a public idea detail page (`/ideas/[idea_id]`) should immediately see what they can do next. Today the page stacks editors and panels without a single obvious primary action. This spec adds a compact, above-the-fold call-to-action strip that routes people to create work, inspect progress, or contribute—using existing public routes only.

## Requirements

- [ ] After the idea title, description, and share block, render a **What to do next** section with three actions:
  - **Create next work** — in-page anchor to the existing quick-create work panel (`#idea-detail-start-work`).
  - **See progress** — link to `/flow?idea_id={idea.id}`.
  - **Contribute** — link to `/contribute`.
- [ ] Wrap the existing `IdeaTaskQuickCreate` block in a container with `id="idea-detail-start-work"` and `scroll-mt-*` so anchor navigation clears any sticky UI.
- [ ] Primary action uses the same warm primary button styling pattern as the homepage explore CTA (`Button` + `Link`, rounded-full, `bg-primary`).
- [ ] Secondary actions use outline-style buttons for clear hierarchy without adding new dependencies.

## Research Inputs (Required)

- `2026-03-26` - [specs/075-web-ideas-specs-usage-pages.md](./075-web-ideas-specs-usage-pages.md) - idea detail route and content expectations.
- `2026-03-26` - [docs/DESIGN.md](../docs/DESIGN.md) - primary CTA visual language (warm, rounded, restrained).
- `2026-03-26` - [web/app/page.tsx](../web/app/page.tsx) - reference `Button asChild` + `Link` primary CTA pattern.

## Task Card (Required)

```yaml
goal: Add an above-the-fold call-to-action strip on public idea detail pages with clear next steps.
files_allowed:
  - specs/157-ux-idea-detail-call-to-action.md
  - web/app/ideas/[idea_id]/page.tsx
done_when:
  - `/ideas/{id}` renders the What to do next section with Create next work (anchor), See progress, and Contribute.
  - `cd web && npm run build` completes without errors.
commands:
  - cd web && npm run build
constraints:
  - Modify only files_allowed; no API or test changes in this spec.
```

## API Contract (if applicable)

N/A - no API contract changes in this spec.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `specs/157-ux-idea-detail-call-to-action.md` - this specification.
- `web/app/ideas/[idea_id]/page.tsx` - CTA section, anchor wrapper for quick create.

## Acceptance Tests

- Manual: Open any idea detail URL; confirm **What to do next** appears below the hero and above progress editing.
- Manual: Click **Create next work**; viewport scrolls to the quick-create panel.
- Manual: **See progress** opens the flow view for the same idea id; **Contribute** opens `/contribute`.
- `cd web && npm run build` succeeds.

## Concurrency Behavior

N/A - static server-rendered UI.

## Verification

### Acceptance Criteria

1. CTA strip is visible on first paint for typical desktop heights without scrolling (placed directly under the title/share block).
2. All three actions are keyboard-focusable and labeled.
3. No new network calls or API dependencies.

### Test Scenarios

#### Scenario 1 - CTA visible and ordered

- **Setup**: Load `/ideas/{valid-idea-id}` with JS enabled.
- **Action**: View the top of the page.
- **Expected**: **What to do next** shows primary **Create next work** and secondary **See progress** / **Contribute**.

#### Scenario 2 - Anchor navigation

- **Setup**: Same page.
- **Action**: Activate **Create next work**.
- **Expected**: Page scrolls to the quick-create section; `#idea-detail-start-work` is in the URL bar.

#### Scenario 3 - Progress and contribute links

- **Setup**: Same page.
- **Action**: Open **See progress** and **Contribute** in new tabs or navigate.
- **Expected**: Flow URL includes `idea_id`; contribute route is `/contribute`.

## Edge Cases and Error Handling

- If flow data failed to load, CTA links still work (they do not depend on flow fetch).
- Error-state idea page (upstream failure) is unchanged; CTA applies only to successful idea loads.

## Risks and Assumptions

- **Assumption**: `/contribute` and `/flow` remain stable public routes.
- **Risk**: Anchor scroll may be partially obscured on very small viewports; `scroll-mt` mitigates overlap with sticky headers if added later.

## Known Gaps and Follow-up Tasks

- Optional: track CTA clicks via existing analytics when available.
- Optional: align copy with portfolio/cockpit terminology in a future UX pass.

## Out of Scope

- Changing `IdeaTaskQuickCreate` behavior or styling beyond the wrapper `id`.
- New API fields or idea schema changes.
