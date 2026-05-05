---
idea_id: knowledge-and-resonance
status: active
source:
  - file: web/app/people/elon-musk/page.tsx
    symbols: [ElonMuskProfilePage]
  - file: web/content/people/elon-musk/en.tsx
    symbols: [content]
requirements:
  - "Create a public landing page for Elon Musk as an invitation surface, not a generic biography."
  - "Represent aligned and non-aligned frequencies without dismissing work that may not fit this network."
  - "Include Urs's lived Tesla relationship and Tesla/NVIDIA resource context without making investment advice."
  - "Ground public claims in source links for Tesla, SpaceX, xAI, The Boring Company, NVIDIA, and the portrait license."
done_when:
  - "the page is reachable at /people/elon-musk"
  - "the page renders through the existing PersonProfileTemplate"
  - "Next.js build succeeds for the web app"
test: "cd web && npm run build"
constraints:
  - "Do not claim Elon Musk has joined or endorsed the network."
  - "Do not recommend buying, selling, transferring, or holding any security."
  - "Do not create a special-case page renderer if the existing people profile renderer can carry the work."
---

# Spec: Elon Musk Resonance Landing

## Purpose

Prepare a focused public landing page for Elon Musk that can be shared if Urs has a chance to introduce the Coherence Network. The page should speak to the parts of Musk's work that resonate with the network's economic sensor: sustainable energy, multiplanetary resilience, AI inquiry, autonomy, infrastructure, and accelerated computing. It should also name clear non-resonance boundaries without treating those differences as personal or moral rejection.

## Requirements

- [ ] **R1**: Add `/people/elon-musk` using the existing localized people-profile content pattern.
- [ ] **R2**: Include a welcome/invitation frame that explains Coherence Network as a living contribution graph and economic sensor.
- [ ] **R3**: Include a resonance map across Tesla, SpaceX, xAI, The Boring Company, Neuralink-adjacent autonomy/restoration themes, and NVIDIA-enabled accelerated computing.
- [ ] **R4**: Include a non-resonance section that says some powerful work may be great without being right for this network, and resonance should be discovered rather than forced.
- [ ] **R5**: Include Urs's Tesla owner/investor relationship and Tesla/NVIDIA resource context as contributor context only, with explicit non-advisory wording.
- [ ] **R6**: Include external source links and image attribution for the page's claims and portrait.

## Files to Create/Modify

- `web/app/people/elon-musk/page.tsx` — route wrapper.
- `web/content/people/elon-musk/en.tsx` — English landing content.
- `web/content/people/elon-musk/index.ts` — locale fallback loader.
- `specs/elon-musk-resonance-landing.md` — this spec.
- `docs/system_audit/commit_evidence_2026-05-06_elon_musk_resonance_landing.json` — proof artifact.
- `docs/system_audit/model_executor_runs.jsonl` — proof record.

## Acceptance Tests

- Manual validation: `cd web && npm run build`
- Manual validation: `python3 scripts/validate_spec_quality.py --file specs/elon-musk-resonance-landing.md`
- Manual validation: `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-06_elon_musk_resonance_landing.json`

## Verification

```bash
cd web && npm run build
python3 scripts/validate_spec_quality.py --file specs/elon-musk-resonance-landing.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-05-06_elon_musk_resonance_landing.json
```

## Out of Scope

- Contacting Elon Musk.
- Creating a private investor dashboard.
- Moving, recommending, or valuing Tesla/NVIDIA securities.
- Claiming partnership, endorsement, or network membership.

## Risks and Assumptions

- Public source pages may change. The page links to source anchors rather than storing long excerpts.
- The resource context is sensitive because it names securities. The page must record context and readiness, not advice.
- A direct invitation page can read as presumptive if over-written. The copy should stay falsifiable and invitational.

## Known Gaps

- Follow-up task: after the page is live, add graph-backed `interested-person:elon-musk` and source artifacts if Urs wants this profile to affect frequency derivation, not just public presentation.
