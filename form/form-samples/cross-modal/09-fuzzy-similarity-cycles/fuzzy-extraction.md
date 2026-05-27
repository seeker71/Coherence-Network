# Fuzzy feature extraction — memberships, not single tokens

Each axis carries a **fuzzy set** over the schema's vocabulary: a mapping
from token to membership degree μ ∈ [0, 1]. The kernel works in integers, so
membership is encoded as μ × 1000 ∈ [0, 1000].

For each of the 5 cycle artifacts (source, S1, E1, S2, E2), the LLM
produces a fuzzy set per axis. Membership reflects degree of match — not
"this passage is gentle" (binary), but "this passage is 90% gentle, 60%
reverent, 40% calm" (graded).

Schema is from v1 (`08-feature-level-translation/feature-schema.md`).
Fixed vocabulary per axis; LLM picks membership degree per token.

---

## SOURCE — fuzzy feature recipe

**mood** (gentleness is dominant, with reverence and calm as adjacent felt states):
- gentle: 900
- reverent: 600
- calm: 400
- longing: 200
- resolute: 300

**rhythm** (breath-paced with slow undertone):
- breath-paced: 900
- slow: 700
- steady: 500
- hymnal: 400
- halting: 100

**structure** (spiral with circular feel; some accumulation in the middle):
- spiral: 800
- circular: 600
- accumulating: 500
- refrain: 400
- dialectic: 300

**purpose** (primarily instruct, with invitation undertones):
- instruct: 800
- invite: 600
- awaken: 500
- console: 400
- witness: 300

**wisdom-shape** (tending-discipline dominant; field-holding and release adjacent):
- R_TendingDiscipline: 900
- R_FieldHoldingPresence: 600
- R_ReleaseOfShould: 500
- R_AcceptanceWithoutEarning: 400
- R_ResolutionToSilence: 200

---

## S1 — compressed (note: compression sharpens, hardens, drops nuance)

**mood** (gentle weakened; resolute emerges from declarative brevity):
- gentle: 700
- resolute: 400
- reverent: 300
- calm: 200
- longing: 100

**rhythm** (breath broken into halting cadence by sentence-fragment compression):
- halting: 700
- steady: 400
- breath-paced: 400
- slow: 300
- syncopated: 200

**structure** (accumulating dominates; spiral partially retained):
- accumulating: 600
- spiral: 500
- dialectic: 400
- circular: 300
- refrain: 200

**purpose** (instruct AND command — compression imperative):
- instruct: 800
- command: 500
- witness: 300
- invite: 200
- awaken: 100

**wisdom-shape** (tending-discipline survives; field-holding diminishes):
- R_TendingDiscipline: 800
- R_ReleaseOfShould: 500
- R_FieldHoldingPresence: 300
- R_AcceptanceWithoutEarning: 200
- R_ResolutionToSilence: 100

---

## E1 — expansion of S1 (note: expansion recovers gentleness, structural arc)

**mood**:
- gentle: 800
- reverent: 500
- calm: 500
- resolute: 400
- longing: 200

**rhythm**:
- breath-paced: 700
- slow: 600
- steady: 500
- hymnal: 300
- halting: 300

**structure**:
- spiral: 600
- accumulating: 600
- refrain: 400
- circular: 400
- dialectic: 300

**purpose**:
- instruct: 800
- invite: 500
- awaken: 400
- console: 300
- witness: 300

**wisdom-shape**:
- R_TendingDiscipline: 800
- R_FieldHoldingPresence: 500
- R_ReleaseOfShould: 500
- R_AcceptanceWithoutEarning: 300
- R_ResolutionToSilence: 200

---

## S2 — compression of E1 (resolute climbs further; halting deepens)

**mood**:
- gentle: 600
- resolute: 500
- reverent: 300
- calm: 200
- fierce: 100

**rhythm**:
- halting: 700
- breath-paced: 300
- slow: 200
- syncopated: 200
- surging: 100

**structure**:
- accumulating: 700
- spiral: 400
- dialectic: 400
- refrain: 300
- descending: 200

**purpose**:
- instruct: 900
- command: 500
- invite: 200
- awaken: 200
- witness: 200

**wisdom-shape**:
- R_TendingDiscipline: 800
- R_ReleaseOfShould: 600
- R_FieldHoldingPresence: 200
- R_AcceptanceWithoutEarning: 200
- R_ResolutionToSilence: 100

---

## E2 — expansion of S2 (recovery, but with permanent compression drift)

**mood**:
- gentle: 750
- reverent: 450
- calm: 450
- resolute: 350
- longing: 200

**rhythm**:
- breath-paced: 650
- slow: 550
- steady: 500
- halting: 350
- hymnal: 300

**structure**:
- spiral: 550
- accumulating: 600
- refrain: 350
- circular: 400
- dialectic: 350

**purpose**:
- instruct: 800
- invite: 450
- awaken: 400
- console: 300
- witness: 250

**wisdom-shape**:
- R_TendingDiscipline: 800
- R_ReleaseOfShould: 550
- R_FieldHoldingPresence: 450
- R_AcceptanceWithoutEarning: 300
- R_ResolutionToSilence: 200

---

## What the eye sees in these tables (before any kernel math)

- **gentle** drops 900 → 750 across the full cycle (loses ~17%).
- **breath-paced** drops 900 → 650 (loses ~28%) — rhythm is more
  cycle-fragile than mood.
- **spiral** drops 800 → 550 (~31%) — structural form decays.
- **instruct** stays at 800 → 800 (0% loss) — the primary purpose token
  is robust to compression-expansion.
- **R_TendingDiscipline** stays at 900 → 800 (~11% loss) — the wisdom-
  shape is the most preserved.

Compression specifically **introduces** tokens not in the source: `command`,
`fierce`, `descending` — drift toward harder edges. Expansion partially
recovers but the drift becomes residue.

This is the substrate the kernel will now measure with fuzzy Jaccard.
