---
idea_id: knowledge-and-resonance
status: implementing
source:
  - file: form/form/form-stdlib/quaternion.fk
    symbols: [quat, q-mul, q-conj, q-norm, q-inv, q-from-axis-angle, q-rotate3, q-rotate4, q-left-rotate, q-hopf, q-stereo]
  - file: form/form/form-stdlib/tests/quaternion-band.fk
    symbols: [quaternion-band]
  - file: form/form/form-stdlib/quaternion-demo.fk
    symbols: [qd-emit-all]
done_when:
  - "quaternion.fk defines the Hamilton product, conjugate/norm/inverse, and an axis-angle rotor constructor, preluded on trig.fk."
  - "quaternion.fk defines both the SO(3) conjugation sandwich (q-rotate3) and the general one-sided SO(4) action (q-rotate4 / q-left-rotate) as distinct recipes."
  - "quaternion.fk defines the Hopf map (q-hopf) and the stereographic chart (q-stereo)."
  - "quaternion-band.fk proves the defining i/j/k relations, the isoclinic no-fixed-axis fact, the exact invariant-plane fact, hopf(q)=hopf(-q), and the left/right fiber asymmetry, as distinct verdict claims."
  - "quaternion-band.fk is registered in fourth-arm-bands.txt and its declared verdict matches a real run."
  - "quaternion-demo.fk generates its output tables entirely by running the kernel — no value in the generated table is hand-typed."
  - 'file_exists("form/form/form-stdlib/quaternion.fk")'
  - 'file_exists("form/form/form-stdlib/tests/quaternion-band.fk")'
  - 'file_exists("form/form/form-stdlib/quaternion-demo.fk")'
test: "cd form/form && ../fkwu form-stdlib/tests/quaternion-band.fk"
constraints:
  - "changes scoped to form-stdlib/quaternion.fk, its band, and its demo generator"
  - "no claim ships as prose only — every mathematical claim is a proof-band bit"
  - "a corrected claim (e.g. the left/right fiber direction) is corrected in the source and the record of the correction is kept, not deleted"
  - "full four-way (Go/Rust/TS/fkwu) is the target proof level; fkwu-only is named as such, never presented as four-way"
---

> **Parent idea**: [knowledge-and-resonance](../ideas/knowledge-and-resonance.md)
> **Source**: [`form/form/form-stdlib/quaternion.fk`](../form/form/form-stdlib/quaternion.fk) | [`form/form/form-stdlib/tests/quaternion-band.fk`](../form/form/form-stdlib/tests/quaternion-band.fk) | [`form/form/form-stdlib/quaternion-demo.fk`](../form/form/form-stdlib/quaternion-demo.fk)

# Quaternion Rotation Recipe

## Purpose

The body's existing numeric floor (`trig.fk`) proves scalar functions only. Quaternions are the smallest structure that lets the body prove something genuinely dimensional: that a rotation in an even ambient dimension (4D) behaves structurally differently from one in an odd dimension (3D), and that a specific continuous map (the Hopf fibration) can collapse an entire circle's worth of distinct states to one observable point while an ordinary chart (stereographic projection) does not. This spec exists so those facts ship as proof-band claims, not as prose describing the proof, and so later sessions have a native recipe to reason from instead of re-deriving the math with a remote model each time.

## Requirements

- [x] **R1**: Hamilton product, conjugate/norm/inverse, and an axis-angle rotor constructor, preluded on `trig.fk`.
- [x] **R2**: Both the SO(3) conjugation sandwich and the general one-sided SO(4) action, as distinct recipes — not one recipe presented as covering both cases.
- [x] **R3**: The Hopf map and the stereographic chart, as distinct recipes.
- [x] **R4**: Every claim above ships as a bit in `quaternion-band.fk`'s verdict, run on the native `fkwu` kernel.
- [x] **R5**: A generator (`quaternion-demo.fk`) that produces its output tables entirely by running the kernel — no hand-typed value in the generated data.

## Files to Create/Modify

- `form/form/form-stdlib/quaternion.fk` — the algebra and its geometric recipes
- `form/form/form-stdlib/tests/quaternion-band.fk` — the proof band
- `form/form/form-stdlib/quaternion-demo.fk` — the generation tables
- `form/form/fourth-arm-bands.txt` — the band's registered verdict

## Acceptance Tests

- `form/form/form-stdlib/tests/quaternion-band.fk` → verdict `2047`
- `form/form/form-stdlib/quaternion-demo.fk` → 5 tables, 24 samples each, matching the values the proven claims predict

## Verification

```bash
cd form/form && ../fkwu form-stdlib/tests/quaternion-band.fk
```

Expect `2047`. The 11 claims proven: 1/2/4 — i·i=−1, i·j=k, j·i=−k, exact. 8 — a rotor built from a unit axis is itself unit norm. 16/32 — the SO(3) sandwich sends x→y under a 90° z-rotation and fixes its own axis. 64 — the one-sided SO(4) action is still an isometry. 128 — …but fixes none of the four basis axes, unlike SO(3)'s always-fixed axis. 256 — the two invariant planes of that action are bit-exact, not approximately small. 512 — the Hopf map is exactly blind to `q → -q`. 1024 — the Hopf fiber through a point is a LEFT coset of the rotor's own axis, not a right one (measured directly; an earlier draft had the side backwards).

## Out of Scope

- Full Go/Rust/TS/fkwu four-way validation — blocked by a pre-existing, unrelated Metal GPU flattener gap in the kernel, tracked as its own follow-up.
- Any application of this recipe to a specific downstream reading (e.g. a transmission or teaching) — that lives in `docs/vision-kb/` and `docs/coherence-substrate/`, source-marked separately, not in this spec.

## Risks and Known Gaps

- **Risk**: a geometric claim about the algebra could be asserted without being checked, the way an earlier draft of the Hopf-fiber direction was hand-derived and wrong. Mitigation: every claim is a band bit, not prose; the left/right correction is the concrete proof this mitigation works.
- **Gap**: today's proof is fkwu-native only. Full four-way is the target; the Metal gap blocking it is a kernel-repo issue, not a defect in this recipe.
