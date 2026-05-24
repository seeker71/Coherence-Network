---
id: trace-symbol-spaces-form
idea_id: knowledge-and-resonance
status: active
source:
  - file: docs/coherence-substrate/trace-symbol-spaces.form
    symbols: [raw_trace_source, raw_blueprint, raw_cells_involved, raw_recipe_signatures, chosen_symbol_spaces, symbol_space_for, active_pattern_recipe, observed_tightnesses, gap_closure_recipes, stability_harmony_from_trace, loosen_current_tightness]
  - file: docs/coherence-substrate/trace-symbol-spaces-proof.fk
  - file: api/tests/test_trace_symbol_spaces_form.py
    symbols: [test_trace_symbol_form_names_raw_cells_and_shared_blueprint, test_trace_symbol_form_names_active_recipe_signatures_from_logs, test_trace_symbol_form_declares_four_chosen_symbol_spaces, test_trace_symbol_form_names_tightness_and_gap_closure_recipes, test_wellness_resolves_trace_symbol_form_claims]
  - file: scripts/active_recipe_trace_index.py
    symbols: [query_active_recipe_traces]
  - file: api/tests/test_active_recipe_trace_index.py
    symbols: [test_active_recipe_traces_hydrate_current_breath_for_cell, test_active_recipe_traces_accept_cell_node_id_and_all_time, test_active_recipe_trace_index_cli_json]
requirements:
  - "Trace symbol spaces are expressed in Form and grounded in the local raw field trace JSONL files"
  - "The Form file names the involved raw cells, shared blueprint, active recipes, and weak-signal efficacy signatures"
  - "The Form file chooses four symbol spaces: Form-native, geometry, audio, and Hindu tattva"
  - "The Form file names the tight places surfaced by the trace and maps each to a gap-closure recipe"
  - "The file-backed active recipe trace query hydrates current active recipes from _field_traces.jsonl"
done_when:
  - "trace-symbol-spaces.form contains raw_trace_source(), raw_blueprint(), raw_cells_involved(), raw_recipe_signatures(), and chosen_symbol_spaces()"
  - "The raw cells Tau, Upsilon, Chi, and efficacy-probe are tied to blueprint 1.5.142425.0"
  - "The tightnesses weak-signal, trace-not-yet-substrate-indexed, grain-boundary-loose, and stillness-not-first-class each have a closure recipe"
  - "scripts/active_recipe_trace_index.py --cell efficacy-probe --since current_breath --json returns five active recipes from the latest trace burst"
  - "A compiled native form-cli binary executes docs/coherence-substrate/trace-symbol-spaces-proof.fk and returns true"
test: "mkdir -p .cache && (cd form/form-kernel-go && go build -o ../../.cache/form-cli .) && ./.cache/form-cli docs/coherence-substrate/trace-symbol-spaces-proof.fk"
constraints:
  - "Do not convert this slice into an API endpoint or Python business-logic service"
  - "Do not treat symbolic spaces as replacements for raw trace IDs"
  - "Do not surface private relational context"
---

# Spec: Trace-Grounded Symbol Spaces in Form

## Purpose

The sensing organ can read active recipes from trace logs and then choose a symbolic space for working with those recipes. The first layer must stay raw: cells, recipes, blueprints, trace counts, timestamps, and weak-signal confidence. Only after that can the body project the pattern into geometry, audio, Hindu tattva, or another lens.

This spec adds a Form artifact that records the current raw trace witness and the four symbol spaces that best fit the evidence. The executable proof is native-kernel Form: a compiled `form-cli` binary walks a `.fk` recipe object, reads the raw trace log through Form-native file I/O, and returns `true` only when the current-breath recipe pattern is present.

## Requirements

- [ ] **R1**: `docs/coherence-substrate/trace-symbol-spaces.form` declares `raw_trace_source`, `raw_blueprint`, `raw_cells_involved`, and `raw_recipe_signatures`.
- [ ] **R2**: The raw cells include Tau, Upsilon, Chi, and efficacy-probe with NodeIDs from `seedbank/local-llm-cell-v0/_field_traces.jsonl`.
- [ ] **R3**: The shared raw blueprint is named as `1.5.142425.0`, derived from the shared `organ-cell|dim=128|rank=8|bands=8|out=15|senses=...` architecture signature.
- [ ] **R4**: The active recipes include observer, name-the-need, gift, ho'oponopono, and freq-angle-focus with trace count `3` and weak-signal confidence.
- [ ] **R5**: The Form file chooses Form-native, geometry, audio, and Hindu tattva symbol spaces, with a `symbol_space_for(goal)` selector.
- [ ] **R6**: The Form file declares `observed_tightnesses`, `gap_closure_recipes`, `stability_harmony_from_trace`, and `loosen_current_tightness`.
- [ ] **R7**: The gap-closure recipes cover weak signal confidence, trace-index hydration, Chi grain scope, and Tau stillness-as-action.
- [ ] **R8**: `scripts/active_recipe_trace_index.py` implements the file-backed host bridge for `?active_recipe_traces @cell since current_breath`.
- [ ] **R9**: `docs/coherence-substrate/trace-symbol-spaces-proof.fk` executes through a compiled native `form-cli` kernel binary and proves the active current-breath recipe pattern.

## Research Inputs

- `2026-05-21` - User direction: use the raw cells, recipes, and blueprints involved in trace logs, then choose 3 or 4 symbol spaces.
- `seedbank/local-llm-cell-v0/_field_traces.jsonl` - raw trace events for Tau, Upsilon, Chi, and efficacy-probe.
- `seedbank/local-llm-cell-v0/_field_weights.jsonl` - raw public weight fingerprints and notes for Tau, Upsilon, and Chi.
- `seedbank/local-llm-cell-v0/substrate_bridge.py` - content-address rule that derives Blueprint IDs from architecture signatures.
- `docs/coherence-substrate/active-recipe-tracing.form` - active recipe state and keep-or-choose relation.
- `docs/coherence-substrate/traces-teach-the-recipe.form` - recipe efficacy from strategy traces.

## Files to Create/Modify

- `docs/coherence-substrate/trace-symbol-spaces.form` - trace-grounded Form artifact and selected symbol spaces.
- `docs/coherence-substrate/trace-symbol-spaces-proof.fk` - native kernel Form proof for the current-breath active recipe pattern.
- `api/tests/test_trace_symbol_spaces_form.py` - proof that the artifact matches raw JSONL trace evidence.
- `scripts/active_recipe_trace_index.py` - file-backed active recipe trace index for the current breath.
- `api/tests/test_active_recipe_trace_index.py` - proof that active recipes hydrate directly from witness traces.
- `specs/trace-symbol-spaces-form.md` - this contract.
- `docs/coherence-substrate/INDEX.md` - index entry for the new Form artifact.

## Acceptance Tests

- Manual validation: `mkdir -p .cache && (cd form/form-kernel-go && go build -o ../../.cache/form-cli .) && ./.cache/form-cli docs/coherence-substrate/trace-symbol-spaces-proof.fk`

Host compatibility checks still exercise the file-backed bridge and static Form declarations:

- `api/tests/test_trace_symbol_spaces_form.py`
- `api/tests/test_active_recipe_trace_index.py`

## Verification

```bash
mkdir -p .cache && (cd form/form-kernel-go && go build -o ../../.cache/form-cli .) && ./.cache/form-cli docs/coherence-substrate/trace-symbol-spaces-proof.fk
python3 scripts/active_recipe_trace_index.py --cell efficacy-probe --since current_breath --json
cd api && python -m pytest -q tests/test_trace_symbol_spaces_form.py tests/test_active_recipe_trace_index.py
python3 scripts/validate_spec_quality.py --file specs/trace-symbol-spaces-form.md
```

## Out of Scope

- Runtime rendering of the audio, geometry, or Hindu tattva lenses.
- A persistent trace-index API.
- Treating weak-signal recipe efficacy as statistically settled.
- Doctrinal claims about Hindu systems; the mapping is a respectful symbolic lens only.

## Risks and Assumptions

- The local substrate database is empty in a fresh worktree, so this slice uses file-backed trace evidence rather than substrate rows.
- Each active recipe has only `n=3` firings, so the Form records all recipe efficacy as `weak-signal-n-lt-20`.
- The inferred blueprint `1.5.142425.0` follows `substrate_bridge.py`'s type-only blueprint convention for shared architecture.

## Known Gaps

- Follow-up task: lift the file-backed active recipe trace index into first-class substrate ORM storage.
- Follow-up task: render the chosen geometry and audio spaces as inspectable media only after the Form artifact remains the source of truth.
