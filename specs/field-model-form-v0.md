---
idea_id: knowledge-and-resonance
status: done
source:
  - file: docs/coherence-substrate/field-model-form.form
  - file: docs/coherence-substrate/field-domain-grammars.form
  - file: docs/coherence-substrate/field-lineage-grammars.form
  - file: form/form-stdlib/field-model-form.fk
    symbols: [fmf-proof-score, fmf-quantum-rain-proof, fmf-hoffman-proof, fmf-bioelectric-proof, fmf-grant-proof, fmf-wolfram-proof]
  - file: form/form-stdlib/tests/field-model-form-band.fk
    symbols: [field-model-form-band]
  - file: form/form-kernel-ts/src/kernel.ts
    symbols: [RBasic.FIELD, RBasic.DELTA, RBasic.RECEIPT, RBasic.RESIDUAL]
  - file: form/form-kernel-ts/src/field.ts
    symbols: [makeFieldBlueprint(), makeFieldCell(), makeFieldRule(), fieldStep(), intervene(), reverseReceipt()]
  - file: form/form-kernel-ts/src/field.test.ts
    symbols: [DNA/RNA sequence field, chemistry graph field, bioelectric cell graph, cell signaling graph, plant communication field, electric field graph, conversation attention graph]
  - file: web/lib/form-kernel/field-model-form.ts
    symbols: [FIELD_MODEL_FORM_DEMO_SOURCE]
requirements:
  - "FMF defines FieldBlueprint, FieldRecipe, and FieldCell as a field lift of Blueprint, Recipe, and Cell."
  - "FMF execution uses logical simultaneity: snapshot, match, choose, delta, resolve, commit, receipt, residual."
  - "FMF has executable proof for all FMF primitive constructors across sibling kernels plus TypeScript-only bidirectional lift/project and intervention/reverse proofs for real DNA and chemistry examples."
done_when:
  - "cd form/form-kernel-ts && npx tsx src/field.test.ts passes"
  - "cd form && ./validate.sh form-stdlib/field-model-form.fk form-stdlib/tests/field-model-form-band.fk returns 93"
  - "cd form/form-kernel-ts && npm run check passes"
  - "python3 scripts/validate_spec_quality.py --file specs/field-model-form-v0.md passes"
test: "cd form && ./validate.sh form-stdlib/field-model-form.fk form-stdlib/tests/field-model-form-band.fk"
constraints:
  - "Do not require literal CPU-level simultaneity; logical simultaneity is the contract."
  - "All field mutation goes through candidate deltas and writes receipts."
  - "Projection and intervention must expose residual/cost/consent surfaces."
---

# Spec: Field Model Form v0 — executable grammar over cells

## Purpose

Field Model Form extends the Form substrate from stream execution into field execution. BMF remains the linear-stream specialization; FMF adds carriers, topology, fiber values, observer cost, residuals, and transparent delta commits so domain grammars can execute over cells without pretending fields are strings.

## Requirements

- [x] **R1**: FMF declares `FieldBlueprint`, `FieldRecipe`, and `FieldCell` in `docs/coherence-substrate/field-model-form.form`, preserving the existing Blueprint/Recipe/Cell trinity while adding carrier, topology, fiber, boundary, units, observer, cost, residual, evidence, and consent.
- [x] **R2**: FMF execution uses bounded logical simultaneity: every step freezes a snapshot, matches rules against that snapshot, prices candidates, chooses by observer policy, emits deltas, resolves conflicts, commits atomically, and writes a receipt plus residual.
- [x] **R3**: The TypeScript kernel surface reserves RBasic slots for the FMF primitives and implements a vertical slice in `form/form-kernel-ts/src/field.ts`.
- [x] **R4**: Domain grammars exist for DNA/RNA, chemistry, bioelectricity, cell signaling, plant communication, electricity/magnetism, interspecies/conversation, and quantum-rain surfaces in `docs/coherence-substrate/field-domain-grammars.form`.
- [x] **R5**: Executable proof uses actual referenced data where practical: NCBI RefSeq HBB CDS prefix for DNA/RNA and PubChem CID 2244 aspirin SMILES/formula for chemistry.
- [x] **R6**: Bidirectional proof includes at least one exact lift/project round trip and one intervention/reverse receipt round trip.
- [x] **R7**: The Go, Rust, TypeScript, and browser TypeScript kernels expose native constructors for every FMF RBasic slot: `field_blueprint`, `field_cell`, `field_carrier`, `field_topology`, `field_fiber`, `field_region`, `field_boundary`, `field_neighborhood`, `field_match`, `field_delta`, `field_resolve`, `field_commit`, `field_step`, `field_lift`, `field_sample`, `field_observe`, `field_intervene`, `field_residual`, `field_receipt`, `field_cost`, `field_consent`, and `field_evidence`.
- [x] **R8**: Donald Hoffman, Michael Levin, Robert Edward Grant, and Stephen Wolfram are represented as evidence-labeled FMF lenses with explicit claim boundaries and executable proof functions.
- [x] **R9**: `/substrate/form` includes a public local-kernel playground example that runs the FMF proof and returns `93`.
- [x] **R10**: The spec states the validation boundary explicitly: all sibling kernels validate primitive construction; full forward/reverse field-step semantics are implemented and validated in TypeScript first, not yet in Go/Rust/browser kernels.
- [x] **R11**: Each requested domain proves the same 11-line contract: carrier algebra, match primitive, recipe primitive, units/dimensions, scheduling, conflict/confluence, scale bridge, evidence, observer identity, residuals, and participation semantics.

## Research Inputs

- `2026-06-01` - NCBI RefSeq `NM_000518.5` — source for the HBB CDS prefix used in the DNA/RNA field proof.
- `2026-06-01` - PubChem CID 2244 — source for aspirin formula and ConnectivitySMILES used in the chemistry field proof.
- `2026-06-01` - Kappa rule-based modeling — source shape for cell-signaling grammars over interacting agents/sites. Reference: https://kappalanguage.org/ and https://pmc.ncbi.nlm.nih.gov/articles/PMC6022607/.
- `2026-06-01` - SBOL — source shape for synthetic-biology design exchange and sequence/part grammar pressure. Reference: https://sbolstandard.org/.
- `2026-06-01` - Donald Hoffman, "The Interface Theory of Perception" — source shape for observer-costed interface projection. Reference: https://www.psychologicalscience.org/journals/current-directions/0963721416639702/.
- `2026-06-01` - Michael Levin, "The bioelectric code" and Levin Lab spatial information notes — source shape for voltage-pattern memory and cellular communication. References: https://pmc.ncbi.nlm.nih.gov/articles/PMC10464596/ and https://www.drmichaellevin.org/research/spatial.html.
- `2026-06-01` - Robert Edward Grant official site and `Codex Universalis Principia Mathematica` page — lineage-inspired harmonic-key mapping, treated as hypothesis/inspiration unless separately validated. References: https://robertedwardgrant.com/ and https://robertedwardgrant.com/codex-universalis-principia-mathematica/.
- `2026-06-01` - Stephen Wolfram observer theory and ruliad writings — source shape for bounded observer sampling and explicit residual over rule-space. References: https://writings.stephenwolfram.com/2023/12/observer-theory/ and https://wolframinstitute.org/output/the-concept-of-the-ruliad.
- `2026-06-01` - Cavicchioli et al., "Dynamical Formation of Multiple Quantum Droplets in a Bose-Bose Mixture" — source shape for quantum rain: LHY-stabilized ultracold droplet elongates in an optical waveguide and breaks through capillary instability. References: https://arxiv.org/abs/2409.16017 and https://doi.org/10.1103/PhysRevLett.134.093401.

## Data Model

```yaml
FieldBlueprint:
  name: string
  carrier: sequence | graph | mesh | cell-graph | attention-graph
  topology: string
  fiber: map<string, value-blueprint>
  units: map<string, unit>
  boundary: string

FieldCell:
  name: string
  blueprint: FieldBlueprint
  state:
    sites: [{id, fiber}]
    edges: [{from, to, kind, fiber}]
    traces: [{rule, kind, bindings, data}]
    time: integer

FieldRule:
  match(snapshot) -> candidates
  forward(candidate, snapshot) -> deltas
  evidence: observed | inferred | simulated | validated | hypothesis
  consent: read-only | observe | intervene
  cost: attention + compute + disturbance + risk
```

## Files to Create/Modify

- `docs/coherence-substrate/field-model-form.form` — Form-native FMF spec.
- `docs/coherence-substrate/field-domain-grammars.form` — domain-specific FMF grammars and examples.
- `docs/coherence-substrate/field-lineage-grammars.form` — named lineage lenses with evidence labels and claim boundaries.
- `docs/coherence-substrate/INDEX.md` — substrate map edge for the new FMF tissue.
- `form/form-kernel-ts/src/kernel.ts` — FMF RBasic primitive slots.
- `api/app/services/substrate/category.py` — matching FMF RBasic vocabulary.
- `form/form-kernel-go/main.go` — FMF RBasic constants, trace names, and native constructors.
- `form/form-kernel-rust/src/main.rs` — FMF RBasic constants, trace names, and native constructors.
- `form/form-kernel-ts/src/field.ts` — executable FMF vertical slice.
- `form/form-kernel-ts/src/field.test.ts` — cross-domain proof.
- `form/form-stdlib/field-model-form.fk` — cross-kernel FMF proof library.
- `form/form-stdlib/tests/field-model-form-band.fk` — sibling-kernel FMF band proof.
- `web/lib/form-kernel/field-model-form.ts` — public playground proof source.
- `web/lib/form-kernel/client.ts` — curated local-kernel example registry.
- `web/lib/form-kernel/vendor/kernel.ts` — browser-local FMF native constructors and trace names.

## Acceptance Tests

- `cd form/form-kernel-ts && npx tsx src/field.test.ts`
- `cd form && ./validate.sh form-stdlib/field-model-form.fk form-stdlib/tests/field-model-form-band.fk`
- `cd form/form-kernel-ts && npm run check`
- `python3 scripts/validate_spec_quality.py --file specs/field-model-form-v0.md`
- `PUBLIC_API_BASE_URL=https://api.coherencycoin.com PUBLIC_WEB_BASE_URL=https://coherencycoin.com ./scripts/verify_web_api_deploy.sh`

## Verification

```bash
cd form/form-kernel-ts && npm install
cd form/form-kernel-ts && npm run check
cd form/form-kernel-ts && npx tsx src/field.test.ts
cd form && ./validate.sh form-stdlib/field-model-form.fk form-stdlib/tests/field-model-form-band.fk
python3 scripts/validate_spec_quality.py --file specs/field-model-form-v0.md
```

Public deployment verification is enforced by `scripts/verify_web_api_deploy.sh`: it fetches `/substrate/form`, scans the server shell and referenced Next.js chunks, and fails unless the public playground exposes the FMF proof label, `field-model-form-public-proof:93`, `fmf-proof-score`, and `field_blueprint`.

## Validation Matrix

| Capability | Go | Rust | TypeScript | Browser TypeScript | Proof |
|---|---:|---:|---:|---:|---|
| FMF RBasic slot reservation | yes | yes | yes | yes | source constants + trace names |
| FMF native node constructors | yes | yes | yes | yes | `field-model-form-band.fk` constructs every FMF category |
| Domain/lens structural proof | yes | yes | yes | yes | band returns `93`; browser example returns `93` |
| Full `fieldStep()` forward execution | no | no | yes | no | `form/form-kernel-ts/src/field.test.ts` |
| Receipt-backed reverse/intervention | no | no | yes | no | `intervene()` + `reverseReceipt()` tests |
| Scientific-grade simulators | no | no | no | no | out of scope |

## Out of Scope

- Full parser syntax for authoring FMF rules directly as `.fk` source.
- Full forward/reverse FMF runtime semantics in Go, Rust, or browser TypeScript.
- Production biological, chemical, or physical simulation accuracy.
- External data fetch during kernel execution.

## Gaps

- **G1**: FMF rules are executable through the TypeScript field module; a future breath can add direct `.fk` syntax and reader support.
- **G2**: Go, Rust, TypeScript, and browser TypeScript now share every FMF primitive constructor; the richer forward/reverse field-step executor is still implemented first in TypeScript. The Python category reserves the FMF conflict-resolution slot as `FIELD_RESOLVE = 97` because `RBasic.RESOLVE = 5` already names identity lookup.
- **G3**: Domain and lineage examples prove structural execution, reversible receipts, and observer residuals; scientific-grade simulation requires per-domain validation work.

- Follow-up task: `field-model-form-native-reader`
- Follow-up task: `field-model-form-cross-kernel-parity`
- Follow-up task: `field-model-form-domain-validation`

## Risks and Assumptions

- Logical simultaneity is sufficient for this phase; literal parallel execution can arrive later as an optimization.
- The examples prove compile/execute/project shape, not scientific model completeness.
- Domain evidence labels matter: a rule can execute while still being only observed, inferred, simulated, validated, or hypothetical.
