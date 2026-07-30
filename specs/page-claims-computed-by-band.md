---
id: page-claims-computed-by-band
idea_id: knowledge-and-resonance
status: active
decision: approved-2026-07-30-lanes-computed-not-typed
source:
  - file: form/form-stdlib/evidence-grounding.fk
    symbols: [eg-lane, eg-forms?, eg-honest-absence?, eg-contested?, eg-surface, eg-spectrum]
  - file: form/form-stdlib/tests/evidence-grounding-band.fk
  - file: form/form-stdlib/tests/zero-point-ladder-band.fk
    symbols: [zpl-claims, zpl-lane-at, zpl-tally, zpl-surface]
  - file: form/fourth-arm-bands.txt
  - file: docs/vision-kb/resources/zero-point-plasma-water.md
  - file: docs/vision-kb/concepts/lc-honest-lane.md
  - file: docs/coherence-substrate/evidence-grounding.form
requirements:
  - "A page that assigns evidence lanes to claims does not type those lanes: the claims live as signal tuples in a Form band and eg-lane computes every lane, so the author cannot grade their own claim"
  - "The band is registered in fourth-arm-bands.txt and crosses all four kernels, so a changed signal or a changed classifier rule moves the verdict and fails the band rather than silently re-grading the page"
  - "The page states the band it was transcribed from and that band's verdict, so a reader can re-run one command and compare"
  - "Where the engine's output disagrees with what the author had typed, the computed lane wins and the disagreement is recorded rather than argued down"
  - "Band vocabulary is held to what the fourth arm proves: no list construction (fourth-shim.fk carries no cons/empty) and a three-file prelude chain at most, since the fourth arm drops the earliest module at four"
done_when:
  - "zero-point-ladder-band.fk returns 65535 identically on Go, Rust, TS AND crosses the fourth arm (fkwu), registered in fourth-arm-bands.txt (1 ok, 0 divergent)"
  - "evidence-grounding-band.fk still returns 8191 four-way — the classifier is unchanged by gaining a caller"
  - "Every lane tag on docs/vision-kb/resources/zero-point-plasma-water.md matches the band's computed walk 5 4 5 5 4 4 4 4 4 5 4 5 2 2 5 2 2 1 2 5 2 0, and the page names the band and verdict it was transcribed from"
  - 'file_exists("form/form-stdlib/tests/zero-point-ladder-band.fk")'
constraints:
  - "The lane logic is Form and only Form; no Python or shell decides a lane. validate.sh is the honest-floor parity harness, not the classifier"
  - "Transcription from band output to page text is manual today — there is NO automated parser comparing the Markdown labels to the band. The page says so plainly; a no-drift guarantee is not claimed until such a check exists"
  - "The band asserts its own tuples, so it catches a changed signal or classifier rule. It cannot catch a page edited by hand to disagree with it — that is the named open edge below"
  - "A page may hold claims in several lanes at once; a rung that mixes strata names both rather than collapsing to the harshest"
---

# Spec: A page's claims are computed by a band, not typed beside one

## Purpose

An evidence-lane discipline that grades its own claims by hand is not a discipline. The
[zero-point ladder](../docs/vision-kb/resources/zero-point-plasma-water.md) shipped with typed
lane tags sitting beside [`evidence-grounding.fk`](../form/form-stdlib/evidence-grounding.fk), a
classifier already proven four-way — the exact failure the lane discipline exists to catch, an
author grading their own claim, committed inside the document warning about it.

This spec names the shape that closes it, so the next page inherits it: **claims become signal
tuples in a Form band; `eg-lane` decides; the page carries the output.**

## The shape

A claim is `(name observed? independent? measured? derived? refuted?)`. The band holds the
page's claims as a table, calls `eg-lane` on each, and asserts the result bit by bit. Registered
in `fourth-arm-bands.txt`, it crosses Go, Rust, TypeScript and the c-bootstrapped fkwu.

Change a signal, change a classifier rule, and the verdict moves — the band fails rather than
the page quietly re-grading itself.

## What running it bought

The engine disagreed with the author in five places, twice in the harsh direction. The page had
typed **CONTESTED** across the whole plasma-water end of the ladder; only `water-car` computes
there, the one claim with a real history of attempted and failed replication. The mechanism, the
Brown's-gas tungsten report, the EVO-as-vacuum-object reading and crater transmutation compute to
**INFERENCE** — single-source and unreplicated, weaker than measured but *not evidence against*.

It also split two rungs the page had flattened, and surfaced a fact invisible while the lanes
were prose: **practice = 0** across all twenty-two claims. A physics ladder holds no
phenomenology. Nothing could see that until something counted.

## Fourth-arm constraints this shape must respect

Both measured rather than assumed, and built around over the minimal proven core:

- **Prelude depth.** The fourth arm resolves a three-file chain (core + module + band). At four
  files the earliest module is dropped: fkwu returned a claim table intact — 22 claims, 6 fields,
  correct values — while every `eg-lane` call came back `0`, including on a claim built inline.
  The same calls return `5 / 4 / 1` at three files. So a page's claim table lives *in* its band.
- **No list construction.** `fourth-shim.fk` carries no `cons` and no `empty`, so any walk that
  builds a list returns nothing on the fourth arm while the three walkers return it. Vocabulary
  is held to what `evidence-grounding.fk` proves: `add / eq / ge / head / if / len / list / nth /
  tail`, and nothing constructs a list except a `list` literal.

## Requirements

- [ ] A page assigning evidence lanes holds its claims as `(name observed? independent? measured? derived? refuted?)` tuples in a Form band; `eg-lane` computes every lane, and no lane is typed by the author
- [ ] The band is registered in `fourth-arm-bands.txt` and crosses Go, Rust, TypeScript and the c-bootstrapped fkwu, so a changed signal or classifier rule moves the verdict and fails the band
- [ ] The page names the band and the verdict it was transcribed from, so a reader can re-run one command and compare
- [ ] Where the computed lane disagrees with what the author typed, the computed lane wins and the disagreement is recorded rather than argued down
- [ ] Band vocabulary stays inside what the fourth arm proves: no list construction, and a three-file prelude chain at most
- [ ] Any gap between page and band is stated on the page; a no-drift guarantee is claimed only when a check implements it

## Files to Create/Modify

- `form/form-stdlib/tests/zero-point-ladder-band.fk` — the claim table plus computed assertions (the first instance)
- `form/form-stdlib/evidence-grounding.fk` — the classifier the band calls, unchanged by gaining a caller
- `form/fourth-arm-bands.txt` — registers `zero-point-ladder fks 65535` so fkwu is gated
- `docs/vision-kb/resources/zero-point-plasma-water.md` — carries the computed tags, names the band, names the manual-transcription edge
- `docs/vision-kb/concepts/lc-honest-lane.md` — the six-stratum spectrum the classifier implements
- `docs/coherence-substrate/evidence-grounding.form` — the teaching cell behind the classifier

## Acceptance Tests

- `cd form && ./validate.sh form-stdlib/tests/zero-point-ladder-band.fk` → `65535`, `fourth arm: 1 band(s) four-way`, `1 ok, 0 divergent`
- `cd form && ./validate.sh form-stdlib/tests/evidence-grounding-band.fk` → `8191` four-way; the classifier is unchanged by its new caller
- Every lane tag on the page matches the computed walk `5 4 5 5 4 4 4 4 4 5 4 5 2 2 5 2 2 1 2 5 2 0`
- The page states the band, the verdict, and that transcription is manual

## Verification

Flip any signal in `zpl-claims` and the band must move rather than the page silently re-grading. Measured, not asserted: setting `water-car` `refuted?` from `1` to `0` drops verdict **65535 → 48127** — bit 1024 (water-car CONTESTED) and bit 16384 (the profile) both fall. Restoring it returns 65535 four-way. That movement is the guarantee this spec actually provides.

```bash
cd form && ./validate.sh form-stdlib/tests/zero-point-ladder-band.fk
```

```bash
cd form && ./validate.sh form-stdlib/tests/evidence-grounding-band.fk
```

```bash
cd form && sed -i '' 's/(list "water-car"             1 0 0 0 1)/(list "water-car"             1 0 0 0 0)/' form-stdlib/tests/zero-point-ladder-band.fk && ./validate.sh form-stdlib/tests/zero-point-ladder-band.fk; git checkout form-stdlib/tests/zero-point-ladder-band.fk
```

## Risks

- **Transcription rot.** The page is copied from band output by hand, so a hand-edited page can disagree with a passing band. Mitigation today is that the page says so; the real mitigation is the comparison check named under Gaps.
- **Signals are still authored.** The engine computes the lane, but a human sets `observed?`/`independent?`/`measured?`/`derived?`/`refuted?`. Bias moves one level down rather than disappearing. What changes is that the signals are few, discrete, reviewable, and cited — a reviewer can argue a bit, where they could not argue a paragraph.
- **Fourth-arm ceilings shift.** The three-file chain and no-list-construction limits are measured against today's fkwu. A future flattener may lift them; a band written to the tighter shape stays valid either way.

## Out of Scope

- Deciding whether any claim on the ladder is *true* — the spectrum grades evidence strength, never truth
- Automating the Markdown comparison check (named as the open edge, not built here)
- Extending the six strata; that is `lc-honest-lane`'s ground, changed only with its own four-way proof
- Any Python or shell participating in lane logic — `validate.sh` is the parity harness, not the classifier

## Gaps

- **Follow-up task `task-2026-07-30-page-band-sync-check`** — no parser compares the Markdown labels to the band output; transcription is manual. The band catches a changed signal or classifier rule, not a hand-edited page. Closing this means a generator or comparison check; until it exists, no no-drift guarantee is claimed.
- **Follow-up task `task-2026-07-30-signal-provenance`** — the signals themselves are authored. `eg-lane` removes the author's discretion over the *lane*, not over `observed?`/`independent?`/`measured?`/`derived?`/`refuted?`. Bias moves one level down, into units small enough to argue about.
- **Follow-up task `task-2026-07-30-generalise-claim-table`** — the band covers one page. A second page adopting this shape needs its own band; nothing yet generalises the table format across pages.

## The open edge, named

There is **no automated check** that parses the Markdown and compares its labels to the band's
output. The band asserts its own tuples, so it catches a changed signal or a changed classifier
rule; it does not catch a page hand-edited to disagree with it. Transcription is manual, the page
says so, and a no-drift guarantee is not claimed until a generator or comparison check exists.

Naming that here rather than in a commit message is the point: the previous version of this work
claimed the guarantee it had not built, which is the same overclaim in a different room.
