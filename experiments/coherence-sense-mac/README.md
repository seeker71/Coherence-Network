# coherence-sense-mac

The mac sibling of `experiments/coherence-sense-android` — a single-window SwiftUI app
that is a **thin carrier over the fkwu sensing recipes**. Swift only captures the camera,
reduces each frame to a couple of integers, draws the UI, and speaks. The **decisions**
run in the C-bootstrapped `fkwu` kernel on this Mac's metal — no go/rust/clang/python/bash
in the gate loop.

## The window

1. **Speaking toggle** — on ⇒ speaks the summary on a rhythm (every 12 s) and immediately on
   each surprise spike, via the host TTS carrier (`NSSpeechSynthesizer`; native vocoder is the
   bring-home). Off ⇒ silent; sensing + display continue.
2. **What is being sensed** — live presence / brightness / surprise, updating from the camera.
3. **Surprise events** — a scrolling, timestamped log of fkwu surprise spikes.
4. **Inquiry-plane probes** — WHAT · WHEN · WHERE · HOW · WHO · WHY; tapping shows that
   plane's current reading.

## Body vs carrier (honest lane)

| reading | who computes it |
|---------|-----------------|
| presence (`pf-present?` over the 16×16 luminance grid) | **recipe-run** — fkwu on metal (`presence-feature` OCCUPANCY decision) |
| surprise (`(if (le tol salience) 1 0)`) | **recipe-run** — fkwu on metal (`ambient-surprise` `as-surprise?` gate) |
| grid-average brightness | carrier-computed (thin reduction in Swift) |
| salience magnitude `abs(reading − baseline)` | carrier-computed — the curated `loop-table` vocabulary carries `le`/`sub`, not `abs`/`gt`, so the magnitude is Swift's and the **decision** is fkwu's |

Presence reads **structure, not brightness.** A Mac camera auto-exposes — a covered lens cranks
gain, so the average luminance stays high. A naive `(if (le threshold luma) 1 0)` gate would read
a false always-YES with the lens covered. `pf-occupancy` (region variance — a present body breaks
the room's uniformity) is robust to auto-exposure: a covered camera's grain averages out across the
coarse grid → uniform → occupancy ~0 → correctly NO presence; a real body breaks the lower-center
uniformity → presence. Swift extracts the grid (thin carrier); fkwu runs the occupancy decision.

The native body is bundled in `Resources/native/`: `fkwu-mac` (the arm64 C-bootstrap kernel),
`loop-table.txt` (the flattened `form-eval-full` table for the surprise/scene gates), and
`presence-table.txt` (`presence-cli` flattened with `presence-feature`, the occupancy decision).
`presence-feature` crosses four-way at `validate.sh` → band 15; the android sibling runs the same
recipe through `live-observe-cli` (`FkwuSense.kt`).

## Build & run

```bash
./build.sh                 # → build/CoherenceSense.app (swiftc, ad-hoc signed)
open build/CoherenceSense.app
```

Bundle id is reused from the Android sibling (`com.coherence.sense`) so an existing camera
TCC grant carries; `Info.plist` carries `NSCameraUsageDescription` and `Sense.entitlements`
requests the camera so macOS prompts on first run if no grant exists.

## Honest floor / bring-home

- **Recipe-run gates** (presence + surprise) run on `fkwu` on this Mac's metal — toolchain-free
  in the gate loop. This is the honest floor; the **standard receipt** platform row for mac is
  thereby `observed` for the gate, `pending` for the full pipeline.
- **Carrier-computed** still: the frame→grid reduction and the salience magnitude. The
  bring-home is lowering those reductions (and the TTS vocoder) into Form too, so the whole
  loop is body, not just the decision.
- **Not yet**: HOW / WHY planes (motion-kinematics, intent), WHO (face-embed) — named as
  pending, never faked.
