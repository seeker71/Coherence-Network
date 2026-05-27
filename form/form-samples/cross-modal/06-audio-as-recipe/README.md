# 06 — Audio as Recipe

**Discovery**: audio is a Form recipe in its own right, same shape as image
(#01). A 1-second 440 Hz tone composes from a 200-entry sine table + the
RIFF/WAVE header arithmetic; same recipe → byte-identical `.wav` across
runs and across all three sibling kernels.

## Run

```bash
cd <repo-root>
go build -o /tmp/form-kernel-go ./form/form-kernel-go
/tmp/form-kernel-go form/form-samples/cross-modal/06-audio-as-recipe/gen-sine.fk
```

This emits `gen-sine.wav` next to the recipe and prints `8044` (the byte
length of the generated file: 44-byte WAV header + 8000 samples).

All three kernels produce the same bytes:

```bash
# Go
/tmp/form-kernel-go form/form-samples/cross-modal/06-audio-as-recipe/gen-sine.fk
sha256sum form/form-samples/cross-modal/06-audio-as-recipe/gen-sine.wav

# Rust
./form/form-kernel-rust/target/release/form-kernel-rust \
    form/form-samples/cross-modal/06-audio-as-recipe/gen-sine.fk
sha256sum form/form-samples/cross-modal/06-audio-as-recipe/gen-sine.wav

# TypeScript (run from repo root so the relative output path resolves there)
./form/form-kernel-ts/node_modules/.bin/tsx \
    ./form/form-kernel-ts/src/main.ts \
    form/form-samples/cross-modal/06-audio-as-recipe/gen-sine.fk
sha256sum form/form-samples/cross-modal/06-audio-as-recipe/gen-sine.wav
```

All three SHAs are `6d170ffe323b378ce29b886252105cb5e6d68e0bc1589160a472075afc635447`.

## What's reachable today

- **Procedural audio as a tree of Form recipes.** `u16-le`, `u32-le`,
  `str-bytes`, `wav-header`, `build-period-rec`, `concat-n-copies` are
  ordinary Form functions over integer math. The body composes them.
- **Same recipe → same bytes** across Go, Rust, and TypeScript kernels,
  and across repeated runs of any one kernel. Determinism = content-
  addressing in practice, same as image-as-recipe.
- **A 200-entry sine table is the only numeric leaf.** Every other byte
  the recipe emits — including the entire 44-byte WAV header and the
  8000 sample bytes — is derived from those 200 values by composition.
  Form has integer arithmetic and no `sin` native; the table is the
  honest answer to "how does sin live in Form?" — as interned trivials,
  not as floating-point Taylor.
- **The arithmetic falls clean.** 440 / 8000 = 11 / 200 exactly, so the
  phase index advances by exactly 11 per sample modulo 200. The full
  period is 200 samples carrying 11 complete cycles; 8000 samples is
  exactly 40 copies of the fundamental period. No round-off, no
  accumulation drift.

## Why 8000 Hz / 8-bit / 1 second

This is intentionally the smallest WAV that proves the point. The claim
is **reproducibility through Form composition**, not fidelity.

The frequency-fidelity tradeoff at these settings:
- **8 kHz sample rate** caps the Nyquist limit at 4 kHz — telephone-grade
  bandwidth. 440 Hz is well below, so the tone is clean.
- **8-bit unsigned PCM** has ~48 dB of dynamic range; quantization noise
  is audible on a quiet system but inconsequential for a continuous tone.
- **127-amplitude (out of 128)** uses the full positive range without
  clipping. At i where `sin(2π · 440 · i / 8000) = ±1` exactly, the
  sample is 128 ± 127 = 255 or 1, never wrapping past byte bounds.
- **1 second / 8000 samples** is enough for the ear to identify pitch and
  for `wc -c` to verify file size (8044 = 44 + 8000) without ambiguity.

Larger formats (44.1 kHz, 16-bit, stereo) would mean ~176 kB of sample
data instead of 8 kB. The recipe shape doesn't change; the byte budget
does. A future breath could extend this with parameterized rate/depth
(forward-map #7-style: same recipe, multiple parameter NodeIDs, distinct
outputs).

## What surprised

- **TS kernel was missing `write_file_bytes`.** Go and Rust had it; the
  TS kernel had only a comment *referring* to it ("Byte codecs still use
  write_file_bytes in kernels that expose it"). This breath added the
  missing native to `form/form-kernel-ts/src/kernel.ts` for sibling-
  parity. Cross-modal walks surface sibling-parity gaps the same way
  any other walk does — the missing native didn't show up until the
  body tried to actually emit bytes through TS.
- **The 200-entry table beats a Taylor implementation.** Without floats
  in the Go kernel, a Form-side sin would have to be fixed-point
  arithmetic with custom precision. The table is honest about where the
  numeric leaves live — interned in the recipe, identical across all
  three kernels because Form intern-equality is content-addressed.
- **Period folding is free at this frequency.** Because 440/8000 reduces
  to 11/200, the waveform repeats every 200 samples. The recipe builds
  one period (200 samples), then concatenates 40 copies. For a frequency
  whose ratio with 8000 doesn't reduce cleanly (e.g. 441 Hz), you would
  have to compute all 8000 samples directly — same recipe shape, longer
  build path.

## What's not reachable today

- **WAV → recipe roundtrip.** The recipe goes one direction: Form → WAV.
  Parsing an arbitrary WAV back into a structural tree (sample rate,
  format chunks, pitch+rhythm) is forward-map walk #8 — "audio-grammar
  extracts pitch+rhythm into a recipe, then re-synthesizes" — a separate
  breath.
- **Higher-fidelity synthesis.** 16-bit signed PCM and 44.1 kHz are
  reachable in principle (the recipe shape is the same; the byte budget
  grows). FM, additive, and envelope-driven synthesis would need either
  larger lookup tables or fixed-point arithmetic in Form. Honest: not
  attempted in this breath.
- **The sample is monochrome.** Stereo channels interleave; the WAV
  header changes (`channels = 2`, doubled block-align, doubled byte
  rate). Reachable as a parameter, not walked here.

## The teaching

"Audio as recipe" doesn't mean "synthesize audio with code" (every DAW
does that). It means **the recipe is the canonical form and the audio is
one emission**. Same recipe → same NodeID → same bytes, every kernel,
every host. The sine table is interned trivials; the WAV header is
composed from `u16-le` / `u32-le` / `str-bytes`; the sample bytes are
composed from `nth` / `mul` / `mod` / `add` over the table. There is no
"audio engine" between the recipe and the bytes — just the kernel.

This extends the cross-modal claim from one modality (image, #01) to two
(image + audio). The same content-addressing property holds across both;
the same byte-determinism holds across all three kernels for both. The
universal-translator's surface area grows by one verified modality.

Lineage:
- [`lc-cross-modal-unity`](../../../../docs/vision-kb/concepts/lc-cross-modal-unity.md)
- [`lc-grammar-is-the-universal-recipe`](../../../../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md)
- [`lc-the-kernel-knows-itself`](../../../../docs/vision-kb/concepts/lc-the-kernel-knows-itself.md)

## Generated artifact

[`gen-sine.wav`](gen-sine.wav) — 8044 bytes, sha256
`6d170ffe323b378ce29b886252105cb5e6d68e0bc1589160a472075afc635447`.

Plays as a 1-second 440 Hz tone in any audio app (`aplay`, `ffplay`,
QuickTime, browser `<audio>`). The recipe lives in `gen-sine.fk`.
