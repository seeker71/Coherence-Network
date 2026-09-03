---
idea_id: public-stewardship-records
status: active
source:
  - file: web/app/stewardship/[[...path]]/page.tsx
    symbols: [StewardshipPage, generateMetadata()]
  - file: web/lib/stewardship-documents.ts
    symbols: [loadStewardshipPage(), rewriteStewardshipLinks()]
  - file: docs/presence-content/urs.json
    symbols: [stewardship links]
requirements:
  - "Every public stewardship link emitted by /people/urs resolves to a readable first-party page"
  - "Stewardship documents remain the canonical content source; the web does not carry a second authored copy"
  - "Relative links inside the stewardship corpus resolve through the same bounded public route"
  - "Path traversal and absent records return the normal not-found boundary"
done_when:
  - "/stewardship/registry and the Tesla onboarding URL return 200 and render their source titles"
  - "Every relative stewardship markdown link maps to an existing page or directory index"
  - "the production verifier checks both /people/urs stewardship doors"
constraints:
  - "Only the already-public docs/stewardship corpus is exposed"
  - "Sensitive specifics remain outside the public repository and runtime image"
  - "No application environment-variable configuration"
test: "cd web && npm test -- --run tests/stewardship-pages.test.ts tests/internal-page-links.test.ts && npm run build"
---

# Spec: Public stewardship pages

## Purpose

The Urs profile names two stewardship records that already exist in the public
body, but their web paths had no route and led readers into a 404. This surface
makes the existing source readable without creating a second authored copy,
and carries its internal document links through the same bounded route.

## Requirements

- [x] **R1 — Source stays singular.** Pages read the committed
  `docs/stewardship` record at request time and link back to its exact GitHub
  source; no parallel content store is introduced.
- [x] **R2 — The whole public cluster is walkable.** Markdown documents,
  directory README files, and directories without a README all have stable
  `/stewardship/...` pages. Relative `.md` and directory links normalize to
  those routes.
- [x] **R3 — The filesystem boundary is closed.** Only conservative path
  segments are accepted. Traversal, invalid segments, and absent records use
  the application not-found boundary.
- [x] **R4 — Deployment carries the source.** The production web image includes
  the already-public `docs/stewardship` corpus, and public verification probes
  the two links emitted by `/people/urs`.

## Files to Create/Modify

- `web/app/stewardship/[[...path]]/page.tsx` — bounded public document and directory surface.
- `web/lib/stewardship-documents.ts` — source resolution and relative-link normalization.
- `web/tests/stewardship-pages.test.ts` — exact source/route and traversal regression.
- `web/tests/internal-page-links.test.ts` — includes authored presence content in link checks.
- `Dockerfile.web` — carries the public source corpus into the runtime image.
- `.github/workflows/hostinger-auto-deploy.yml` — deploys record-only changes.
- `.github/workflows/public-deploy-contract.yml` — verifies record-only changes.
- `scripts/verify_web_api_deploy.sh` — post-deploy checks for both repaired URLs.

## Acceptance Tests

- `web/tests/stewardship-pages.test.ts` proves both profile URLs, every
  relative corpus link, directory indexes, and the traversal boundary.
- `web/tests/internal-page-links.test.ts` proves authored presence-content
  links remain attached to an application route.
- Manual local HTTP validation proves both URLs return 200 with their source
  title, and the production Next.js build includes the catch-all route.

## Verification

```bash
cd web && npm test -- --run tests/stewardship-pages.test.ts tests/internal-page-links.test.ts
cd web && npm run build
./scripts/verify_worktree_local_web.sh --start
```

## Out of Scope

- Private wrapper records, credentials, account numbers, balances, addresses,
  and other sensitive specifics are not part of this surface.
- This change does not alter stewardship status or legal ownership.

## Risks and Assumptions

- The public runtime image must carry the same committed stewardship corpus
  used in local development; the Docker copy and live verifier bind that
  assumption.
- Markdown is rendered with the existing deliberately small prose renderer.
  Richer document widgets are unnecessary for making these records walkable.

## Known Gaps and Follow-up Tasks

- None for this public source surface. No private wrapper record is readable
  through this route. A future private stewardship surface would require its
  own authenticated specification and consent boundary rather than expanding
  this public source reader.
