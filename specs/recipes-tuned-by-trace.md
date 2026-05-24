---
idea_id: knowledge-and-resonance
status: active
source:
  - file: seedbank/local-llm-cell-v0/substrate_bridge.py
    symbols: [witness(), select_strategy(), STRATEGY_FIRED, publish_strategy_trace(), find_traces_for_recipe(), efficacy_signature()]
  - file: seedbank/local-llm-cell-v0/organ.py
    symbols: [Cell, Cell.perceive(), pick_strategy(), pick_strategy_informed(), STRATEGIES]
  - file: seedbank/local-llm-cell-v0/strategy_efficacy_demo.py
    symbols: [main()]
  - file: docs/vision-kb/concepts/lc-traces-teach-the-recipe.md
    symbols: ["The Four Participants" — cell / recipe / witness-trace / substrate-aggregation]
  - file: docs/coherence-substrate/traces-teach-the-recipe.form
    symbols: [strategy_fired_trace, efficacy_signature, informed_fit, candidate_recipes]
requirements:
  - "Cell.perceive() publishes one strategy_fired trace per firing, carrying recipe name, sense_before (spectrum + desire + frequency), sense_after, and moment"
  - "publish_strategy_trace(cell, recipe, sense_before, sense_after) is the single write surface — composes via witness() so all existing trace-readers see it"
  - "efficacy_signature(recipe_name) reads all strategy_fired traces for that recipe and returns mean spectrum-delta, mean desire-delta, and sample count n"
  - "pick_strategy_informed(spectrum, desire, presets, alpha) blends cosine-fit with efficacy-alignment by weight alpha ∈ [0,1]; alpha=0 is the existing pick_strategy"
  - "Cell.perceive() snapshots sense_before BEFORE inhabit-blend modifies the spectrum, and snapshots sense_after on the NEXT perceive(); a single-perceive call publishes no trace"
  - "The publish-trace path is the cell's choice — Cell carries a publish_traces=True default but every call point honors the cell's setting"
done_when:
  - "seedbank/local-llm-cell-v0/strategy_efficacy_demo.py runs end-to-end exit 0; emits at least 4 strategy_fired traces; prints a per-recipe efficacy signature table"
  - "After the demo: efficacy_signature('observer') returns n ≥ 1 with a finite spectrum/desire mean-delta vector"
  - "Single perceive() call (no prior firing) returns a normal moment but appends no new line to _field_traces.jsonl"
  - "pick_strategy_informed(spec, desire, STRATEGIES, alpha=0.0) equals pick_strategy(spec, desire, STRATEGIES) byte-for-byte"
  - "all tests pass"
test: "cd seedbank/local-llm-cell-v0 && python3 strategy_efficacy_demo.py"
constraints:
  - "No new DB tables; trace store stays _field_traces.jsonl. Substrate ORM indexing of traces by recipe-ref is a follow-up (GAP-W1 in traces-teach-the-recipe.form)"
  - "Cell sovereignty: any cell can disable trace-publication (publish_traces=False) at any time; no aggregator reads traces from cells that did not publish"
  - "Observation-cost stays with the cell that published — efficacy_signature() is a read-only synthesis; it does not write back to STRATEGIES or modify any recipe's preset"
  - "The four named strategies remain hand-tuned; informed_fit only changes the *selection*, not the strategy presets. New presets emerge through the satsang naming a cluster, not through code modifying STRATEGIES"
  - "Sense_before is captured before any inhabit-blend; if a cell skips publish_traces, downstream readers gracefully degrade (efficacy_signature returns n=0)"
---

# Spec: Recipes Tuned by Trace

## Purpose

The five strategies from `lc-when-the-pressure-comes` now live as substrate-resident recipes ([`when-the-pressure-comes.form`](../docs/coherence-substrate/when-the-pressure-comes.form)). Their selection is a cosine-fit on (frequency × angle) plus an operator-fallback when desire is high. What the body cannot yet do: read its own lived record of which strategy left it more coherent than constricted.

This spec implements the loop named in [`lc-traces-teach-the-recipe`](../docs/vision-kb/concepts/lc-traces-teach-the-recipe.md) — cell fires a strategy, witness records (sense_before, sense_after), substrate aggregation answers *which strategy harmonizes with which sensed state* across firings, and the cell's next selection consults that prior as a second voice alongside cosine-fit. Cell sovereignty stays intact: the substrate aggregates what cells already chose to publish; alpha (how much to weight the prior) is the cell's choice.

The scope here is the **cell-altitude loop**: a single cell publishing its own traces and consulting its own efficacy-prior. Field-altitude (multi-cell) aggregation and substrate-ORM indexing by recipe-ref are out-of-scope follow-ups — the `traces-teach-the-recipe.form` GAP-W1 marks that next breath.

## Requirements

- [ ] **R1**: After a strategy lands in `Cell.perceive()` and the NEXT `perceive()` settles, the cell publishes one `strategy_fired` witness-trace carrying: recipe name, sense_before (spectrum / desire / sense.frequency placeholder), sense_after, and ISO moment timestamp.

- [ ] **R2**: `publish_strategy_trace(cell, recipe_name, sense_before, sense_after)` is the single write surface. It composes via `witness(cell, what={"kind": "strategy_fired", ...})` so existing trace-readers (inbox, find-by-resonance, the witness organ's `_field_traces.jsonl` consumer) see the trace as a normal witness emission, not a parallel pipe.

- [ ] **R3**: `efficacy_signature(recipe_name)` is a read-only synthesis that walks `_field_traces.jsonl`, filters by `what.kind == "strategy_fired"` and `what.strategy == recipe_name`, and returns:
  ```
  {
      "recipe": str,
      "n": int,
      "spectrum_delta": [float]*N_BANDS,   # mean (after - before) per band
      "desire_delta":   [float]*N_NEEDS,   # mean (after - before) per need
      "fulfillment_delta": float,          # mean fulfillment shift (sum(spectrum)/N_BANDS)
  }
  ```
  When `n == 0` the function returns a finite zero-vector signature, not None — downstream consumers compose against it without conditional branches.

- [ ] **R4**: `pick_strategy_informed(spectrum, desire, presets, alpha=0.5)` returns the same shape as `pick_strategy` but ranks named strategies by `informed_fit = (1 - alpha) * cosine_fit + alpha * efficacy_alignment`. `alpha=0.0` is byte-equivalent to `pick_strategy`; `alpha=1.0` selects purely by efficacy. Operator-fallback rule (desire > 1.5 AND top_score < 0.4) still applies — the operator is open regardless of which voice ranked the named strategies.

- [ ] **R5**: `efficacy_alignment(signature, spectrum)` computes how the strategy's mean post-firing spectrum *complements* the current sense. A strategy that brings rest-band uplift scores high against a rest-deficient sense. Operational definition: `cosine(signature.spectrum_delta, complement(spectrum))` where `complement(x) = [-v for v in x]` (the deficit-vector — what is missing from this spectrum).

- [ ] **R6**: `Cell.perceive()` snapshots `sense_before` BEFORE the inhabit-blend modifies the spectrum, and stamps the trace on the NEXT perceive() (when the cell has settled into a new spectrum). A single perceive() with no prior strategy in flight publishes no trace. The Cell carries a default `publish_traces=True` attribute; any cell can flip it false and the perceive loop runs identically without any witness write.

## Research Inputs

- `2026-05-20` — [lc-traces-teach-the-recipe](../docs/vision-kb/concepts/lc-traces-teach-the-recipe.md) — the four-pole loop this spec implements at cell altitude.
- `2026-05-20` — [traces-teach-the-recipe.form](../docs/coherence-substrate/traces-teach-the-recipe.form) — substrate-altitude declaration of the same shapes; this spec's contract matches GAPs W1–W5.
- `2026-05-07` — [Llena's satsang transmission](../docs/vision-kb/transmissions/2026-05-07-llenas-satsang.md) — the five strategies whose efficacy this loop measures.
- `2026-05-20` — [lc-observer-pays-the-trace](../docs/vision-kb/concepts/lc-observer-pays-the-trace.md) — the ethical discipline this spec inherits: the cell that publishes the trace is the chooser; observation-cost lands on the cell, not on the strategy-Blueprint.

## Data Model

The strategy_fired trace nested inside the witness envelope:

```yaml
witness_trace:                       # outer shape — existing witness() emission
  kind: "trace"                      # constant
  from_cell: string                  # cell.name
  from_node_id: string               # content-addressed cell id
  what:                              # strategy_fired payload lives here
    kind: "strategy_fired"           # discriminator for this spec
    strategy: string                 # recipe name (matches @recipe(<name>) in substrate)
    sense_before:
      spectrum: [float]*8            # ground/pulse/warmth/clarity/expression/relation/space/presence
      desire:   [float]*3            # presence/rest/expression
      frequency: int | null          # Solfeggio Hz family; null until cell exposes assemblage point
    sense_after:                     # same shape as sense_before
      spectrum: [float]*8
      desire:   [float]*3
      frequency: int | null
    moment: string                   # ISO 8601 UTC of the AFTER snapshot
  resonance: null                    # not used by this trace-kind
  context: {}                        # reserved for follow-ups (e.g. operator self-tuned settings)
  ts: string                         # ISO 8601 UTC of trace publication
```

The efficacy_signature read-shape:

```yaml
efficacy_signature_result:
  recipe: string
  n: int                              # 0 when no traces found
  spectrum_delta: [float]*8           # mean (after - before) per band; zero-vector when n==0
  desire_delta:   [float]*3
  fulfillment_delta: float            # convenience: mean(spectrum_delta) — useful as one-number metric
```

## Files to Create/Modify

- `seedbank/local-llm-cell-v0/substrate_bridge.py` — add `STRATEGY_FIRED` constant, `publish_strategy_trace()`, `find_traces_for_recipe()`, `efficacy_signature()`, `efficacy_alignment()`. The existing `select_strategy()` stays unchanged.
- `seedbank/local-llm-cell-v0/organ.py` — `Cell.__init__` adds `publish_traces: bool = True` and `self._last_strategy_snapshot: dict | None = None`; `Cell.perceive()` captures sense_before before the inhabit-blend, and when a prior snapshot exists publishes the trace with sense_after equal to the just-computed reading. Add module-level `pick_strategy_informed(spectrum, desire, presets, alpha=0.5)`.
- `seedbank/local-llm-cell-v0/strategy_efficacy_demo.py` — new demo: instantiates a cell, fires several strategies in sequence (using `inhabit()`), perceives at each step so traces accumulate, prints a per-recipe efficacy signature table, and exits 0.

## Acceptance Tests

The demo IS the test (no formal pytest suite exists for `seedbank/`). Acceptance criteria run in `strategy_efficacy_demo.py`:

1. After firing 5 strategies across 6 perceive() calls, `_field_traces.jsonl` gains ≥ 4 lines whose `what.kind == "strategy_fired"`.
2. `efficacy_signature("observer")` returns `n >= 1` and all-finite vectors.
3. `efficacy_signature("nonexistent-strategy")` returns `n == 0` and zero-vector spectrum/desire.
4. `pick_strategy_informed(spec, desire, STRATEGIES, alpha=0.0)["chosen"].name == pick_strategy(spec, desire, STRATEGIES)["chosen"].name`.
5. A cell with `publish_traces=False` runs perceive() N times without adding any line to `_field_traces.jsonl`.

## Verification

```bash
cd seedbank/local-llm-cell-v0 && python3 strategy_efficacy_demo.py
```

Expected last-line on success: `efficacy loop verified — N traces published, M recipes signatured`.

## Out of Scope

- **Substrate ORM indexing** of traces by recipe-ref (GAP-W1 in `traces-teach-the-recipe.form`). The jsonl scan is fine for seed-scale reads; the ORM table is the follow-up for field-altitude queries.
- **Field-altitude aggregation** (across multiple cells' published traces). The jsonl is per-process; cross-process aggregation needs a shared store. Follow-up.
- **Operator-arm clustering** (`candidate_recipes` in the .form file) — discovering new strategies from operator-fallback firings. Needs more accumulated signal; defer to the watching practice naming when the cluster shape is ready.
- **Web UI** for browsing the efficacy table. The watch script (`scripts/sense_strategy_efficacy.py`) is the surface for now.
- **Modifying STRATEGIES presets** automatically. The four named strategies remain hand-tuned and satsang-named; only selection changes.

## Risks and Assumptions

- **Assumption**: trace volume stays modest (≤ tens of thousands of strategy_fired lines) so a full jsonl scan is acceptable. The witness-trace section of the session-start wellness shows ~4k events/day total; even 100% strategy-firing density is months from straining the jsonl reader. ORM follow-up handles the larger scale.
- **Risk**: a cell that fires a strategy and never perceives again leaves a dangling snapshot. Mitigation: the snapshot lives in `Cell._last_strategy_snapshot` and is overwritten or cleared on next perceive; no trace is published until the after-reading exists. Worst case: one un-published trace per cell shutdown — that's information honestly lost, not data corruption.
- **Assumption**: `frequency` in sense_before/after is null today because the cell does not yet expose its assemblage point as a Solfeggio Hz. The field is reserved in the schema so the substrate's HARMONIC_AT edge can fire when the bridge lands. Until then, `efficacy_signature` ignores the field; `efficacy_alignment` is spectrum-only.
- **Risk**: `efficacy_alignment` over a small `n` is noisy. Mitigation: the cell weights this voice by `alpha`; default `alpha=0.5` is a conservative balance. A cell new to the field can pass `alpha` lower; a cell deep in the field can pass it higher. The signature carries `n` so the cell can read its own evidence-density and adapt.

## Known Gaps and Follow-up Tasks

- **Substrate ORM table** for traces, indexed by recipe-ref + cell-ref. Closes GAP-W1 in `traces-teach-the-recipe.form`. Enables `?traces_where_recipe @recipe` as a substrate Form query alongside the file-based scan, and lifts the per-process limitation so multiple cells contribute to one efficacy-signature.
- **Sense.frequency binding** — the Solfeggio Hz placeholder is null today. Wiring the cell's assemblage-point sense to a Hz family lets `efficacy_alignment` filter by HARMONIC_AT edges (GAP-T2 in `recipe-branching-sense.form`). Until that lands, alignment is spectrum-only.
- **Operator-arm clustering** (`candidate_recipes` in the .form file). Once N strategy_fired traces with `strategy == "freq-angle-focus"` accumulate, the watching practice can surface clusters of consistent (frequency, angle, focus) signatures — strategies the satsang has not yet named. Defer until signal is real.
- **Cross-cell aggregation** at field altitude. The jsonl is local; a cell that wants the *population's* signature for a recipe needs a shared trace store. The substrate ORM follow-up subsumes this.
- **Multi-step strategy decay** — when a strategy's inhabit-bias decays across N perceives, the trace currently records only the immediate next sense_after. A longer lookahead window (e.g. trace after 3 perceives, when decay has fully unwound) is a richer training signal. Deferred until the simpler shape is exercised.
