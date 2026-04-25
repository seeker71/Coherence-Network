---
idea_id: knowledge-and-resonance
status: done
source:
  - file: specs/living-signal-layer.md
    symbols: [living signal layer contract]
  - file: web/lib/living-signal.ts
    symbols: [senseLivingField(), receiveMovement()]
  - file: web/tests/integration/living-signal.test.ts
    symbols: [living signal behavior tests]
  - file: web/components/living-signal/LivingSignalInstrument.tsx
    symbols: [LivingSignalInstrument]
  - file: web/app/signals/page.tsx
    symbols: [SignalsPage]
requirements:
  - "Sense useful signals as a changing field rather than fixed categories"
  - "Measure form vitality and living pulse separately"
  - "Guide with gentle language that adapts after each movement"
done_when:
  - "Vitest proves guidance changes after a new movement is received"
  - "The /signals page renders a dynamic living signal instrument"
  - "npm run build completes successfully in web/"
test: "cd web && npm run test -- tests/integration/living-signal.test.ts"
constraints:
  - "Keep this slice client-side with no backend routes or persistence"
  - "Use live signal streams in the UI"
  - "Keep the page usable without external services"
---

# Spec: Living Signal Layer

## Purpose

Create a small, dynamic instrument that shows how Coherence Network can sense what is already present and guide it toward vitality. The feature should make the idea tangible in the web app: signals arrive, the field senses them, guidance emerges, a movement is received, and the field resenses itself.

## Requirements

- [ ] **R1**: The signal engine accepts a stream of useful signal events and returns a sensed field with form vitality, living pulse, active tone, guidance, and a next movement.
- [ ] **R2**: The signal engine separates structural presence from dynamic aliveness so implementation can be measured as both form and living pulse.
- [ ] **R3**: The signal engine updates guidance after a movement is received, proving the layer adapts through contact.
- [ ] **R4**: The web page renders an interactive signal instrument at `/signals` with motion, meters, recent signals, and gentle guidance.

## Research Inputs

- `2026-04-20` - User direction in this thread: use a dynamic signal system, guide through useful signals gently, and measure implementation as both form and aliveness.

## API Contract

No API changes. This is a client-side vertical slice.

## Data Model

```yaml
LivingSignalEvent:
  id: string
  surface: vision | evidence | agent | task | community | implementation
  quality: gathering | orienting | grounding | embodying | integrating | renewing
  intensity: number
  vitality:
    breath: number
    clarity: number
    agency: number
    grounding: number
  receivedAt: string
  note: string

SensedLivingField:
  formVitality:
    score: number
    label: string
  livingPulse:
    score: number
    label: string
    trajectory: number
  activeTone: string
  guidance: string
  nextMovement: string
```

## Files to Create/Modify

- `specs/living-signal-layer.md` -- implementation contract
- `web/lib/living-signal.ts` -- deterministic signal sensing logic
- `web/tests/integration/living-signal.test.ts` -- signal behavior tests
- `web/components/living-signal/LivingSignalInstrument.tsx` -- interactive client component
- `web/app/signals/page.tsx` -- route entry point

## Acceptance Tests

- `web/tests/integration/living-signal.test.ts::senses living pulse above form when varied signals gather`
- `web/tests/integration/living-signal.test.ts::adapts guidance after receiving an embodied movement`
- `web/tests/integration/living-signal.test.ts::keeps sparse signals gentle and actionable`

## Verification

```bash
cd web && npm run test -- tests/integration/living-signal.test.ts
cd web && npm run build
```

## Out of Scope

- Persisting signal events to the API
- Adding graph database schema
- Adding navigation changes beyond the `/signals` route
- Scoring users or communities

## Risks and Assumptions

- The first slice uses deterministic local signals so the page is available without API dependencies.
- Gentle language must stay precise enough to guide action without becoming vague inspiration.
- Later persistence should reuse the same pure signal contract where possible.

## Known Gaps and Follow-up Tasks

- Follow-up: connect the signal stream to real task, evidence, PR, and agent events.
- Follow-up: add telemetry that compares guidance hypotheses with observed user and agent outcomes.
