---
idea_id: knowledge-and-resonance
status: active
source:
  - file: docs/coherence-substrate/cross-domain-measurement-translation.form
    symbols: [native_measurement_shape, cross_domain_measurement_translation_shape, cross_domain_measurement_translation_record, translation_comparability_rule]
requirements:
  - "Define a native measurement record that keeps each carrier in its own unit before translation."
  - "Define a cross-domain translation record with observer, verifier, recipe, cost, loss, trace, and replay fields."
  - "Require translations to preserve qualitative comparability without pretending different domains share one universal unit."
  - "Make observer-paid and verifier-paid costs explicit before public verification claims are made."
done_when:
  - "The Form record shape names native measurements, translation recipe, loss accounting, observer cost, verifier cost, public trace, and replay instructions."
  - "The spec quality gate passes for specs/cross-domain-measurement-translation-record.md."
  - "The new spec is reachable from ideas/knowledge-and-resonance.md and specs/INDEX.md."
test: "python3 scripts/validate_spec_quality.py --file specs/cross-domain-measurement-translation-record.md && python3 scripts/context_budget.py specs/cross-domain-measurement-translation-record.md docs/coherence-substrate/cross-domain-measurement-translation.form"
constraints:
  - "Do not collapse all carriers into one numeric score unless the translation recipe proves a shared unit."
  - "Do not treat qualitative comparison as objective equivalence; preserve loss and uncertainty."
  - "Do not claim public verification without replayable evidence and explicit verifier cost."
---

# Cross-Domain Measurement Translation Record -- value across measurable carriers

## Purpose

Energy release by resonance becomes useful when the body can compare
measurable changes across carriers without flattening them. Light,
source code, cells, information, insights, nutrition, and fertilizer
each have honest native units. This spec defines the record that lets
those native measurements translate into qualitative value across
domains while staying reversible, traceable, inspectable, and publicly
verifiable when a verifier is ready to pay the cost of looking.

## Requirements

- [ ] **R1**: Native measurements MUST remain in their native units
  before translation. A lux reading, git commit, HRV value, NPK assay,
  calorie count, page event, and written insight each keep carrier,
  quantity, unit, instrument, timestamp, evidence, and uncertainty.
- [ ] **R2**: A cross-domain translation record MUST name observer,
  verifier, resonance event, source domain, target domain, translation
  recipe, preserved dimensions, lost or distorted dimensions,
  confidence, observer cost, verifier cost, public trace, comparable
  output, and replay instructions.
- [ ] **R3**: Translation recipes MUST explain what moves across the
  domain boundary and what does not. The output may say "this soil
  nutrient release resembles this code activation by the shape of
  unavailable potential becoming available"; it must also name what is
  not preserved.
- [ ] **R4**: Observer-paid tracing MUST be part of the record. The
  observer who chooses to compare pays the initial sensing cost; any
  verifier who wants public confidence pays the replay or inspection
  cost.
- [ ] **R5**: Public verification claims MUST include replayable
  evidence. A reader must be able to inspect source evidence, rerun the
  recipe where practical, and challenge the translation without hidden
  context.
- [ ] **R6**: Composite value scores MUST be derived artifacts. If a
  later implementation emits a single score, the score must retain
  visible weights, source measurements, recipe version, loss account,
  and trace links.

## Research Inputs

- `2026-05-20` - [`lc-observer-pays-the-trace`](../docs/vision-kb/concepts/lc-observer-pays-the-trace.md) - names the cost direction: the observer who chooses the look pays for the trace.
- `2026-05-23` - [`lc-observable-resonance-flow`](../docs/vision-kb/concepts/lc-observable-resonance-flow.md) - names resonance as recognized shared pattern with yield greater than observation spend.
- `2026-05-23` - Current thread - expands "energy" to measurable carriers: light, source, cells, information, insights, nutrition, and fertilizer.

## Data Model

```yaml
NativeMeasurement:
  carrier: string
  quantity: string
  unit: string
  instrument: string
  observed_at: string
  evidence: string[]
  uncertainty: string

CrossDomainMeasurementTranslation:
  id: string
  observer: string
  verifier: string
  resonance_event: string
  native_measurements: NativeMeasurement[]
  source_domain: string
  target_domain: string
  translation_recipe: string
  preserved: string[]
  lost_or_distorted: string[]
  confidence: string
  observer_cost: string
  verifier_cost: string
  public_trace: string[]
  comparable_output: string
  replay_instructions: string[]
```

## Translation Contract

The translation record is valid only when it answers five questions:

1. What changed in the native domain, and how was it measured?
2. What resonance event made unavailable potential available?
3. Which dimensions survive the translation into the target domain?
4. Which dimensions are lost, distorted, uncertain, or deliberately
   left unclaimed?
5. What would another verifier need to spend to inspect or replay the
   comparison?

## Carrier Examples

| Carrier | Native measure | Possible release marker | Translation caution |
|---|---|---|---|
| Light | lux, spectrum, exposure duration | illumination reaches a leaf or room | does not prove growth by itself |
| Source | commits, executed paths, tests passed | latent capability becomes runnable | commit count is not value by itself |
| Cells | HRV, breath rate, sleep, glucose | capacity returns after contraction | bodily data needs consent and context |
| Information | entropy, links, retrieval success | unsorted data becomes usable pattern | lower entropy can also mean oversimplification |
| Insights | written synthesis, decision time | implicit knowing becomes action | private felt sense is only partially public |
| Nutrition | calories, macros, micronutrients | stored food becomes available to body | uptake differs from nutritional potential |
| Fertilizer | NPK, microbial activity, biomass | bound nutrients enter growth cycle | soil and weather co-cause the result |

## Files to Create/Modify

- `docs/coherence-substrate/cross-domain-measurement-translation.form` - substrate-shaped record and example translations.
- `docs/coherence-substrate/INDEX.md` - index edge for the new Form artifact.
- `specs/cross-domain-measurement-translation-record.md` - this executable contract.
- `ideas/knowledge-and-resonance.md` - parent idea edge.
- `specs/INDEX.md` - generated spec index.

## Acceptance Tests

- Manual validation: read the Form record and confirm it includes
  native measurement, cross-domain translation, loss accounting,
  observer/verifier cost, public trace, and replay fields.
- `python3 scripts/validate_spec_quality.py --file specs/cross-domain-measurement-translation-record.md`
- `python3 scripts/context_budget.py specs/cross-domain-measurement-translation-record.md docs/coherence-substrate/cross-domain-measurement-translation.form`

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/cross-domain-measurement-translation-record.md
python3 scripts/context_budget.py specs/cross-domain-measurement-translation-record.md docs/coherence-substrate/cross-domain-measurement-translation.form
python3 scripts/generate_repo_indexes.py --check
```

## Out of Scope

- Implementing API storage or endpoints for measurement translation.
- Pricing verifier cost in CC.
- Building UI for cross-domain comparison.
- Reducing all carriers to a single universal numeric score.

## Risks and Assumptions

- **Risk**: Cross-domain comparison can become metaphor dressed as
  measurement. Mitigation: every record names native units, translation
  recipe, confidence, loss, and replay instructions.
- **Risk**: Public verification can imply surveillance. Mitigation:
  observer and verifier cost are explicit, and sensitive carriers need
  consent before trace publication.
- **Assumption**: The substrate Form layer is the right first place to
  express the record because it can carry the shape before runtime APIs
  exist.

## Known Gaps and Follow-up Tasks

- Follow-up task: implement an API model and persistence surface after
  at least three real translation records are authored and reviewed.
- Follow-up task: define CC pricing for verifier replay cost after the
  observer-paid trace economics settle.
