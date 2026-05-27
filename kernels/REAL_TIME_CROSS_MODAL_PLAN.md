# Real-time cross-modal kernel natives — the actual path

> *"calling an LLM to get a byte? calling an LLM for anything real time?
> there are trained audio TTS and STT encoder/decoders that work real
> time and are free, that is a proofable start that the medium
> boundaries can be crossed in real time"*  — Urs

## What this plan composts

The cross-modal experiments in `form/form-samples/cross-modal/05-..09-..`
use an LLM session as both extractor and generator. That's a useful
*verification-side* demonstration of substrate addressing but it
**cannot scale to real-time** — LLM round-trip latency is 100–10000ms
per call, dwarfing any audio-frame or video-frame budget.

For the universal-translator claim to be real at deployment, modality
crossings need to be handled by **trained, deterministic, real-time
models** invoked from the kernel as native functions. The substrate's
role stays the same — address the intermediate, verify preservation —
but the *translators* are real-time encoders/decoders, not LLM sessions.

## The real-time tools that exist today (free, open-source, CPU-runnable)

### Speech ↔ text (the proofable starting boundary Urs named)

| Tool | License | Real-time on commodity CPU | Notes |
|---|---|---|---|
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | MIT | tiny: ~real-time, base: ~real-time on M1 / 2× on x86 | C++ port of OpenAI Whisper; CLI binary; deterministic given seed |
| [Vosk](https://alphacephei.com/vosk/) | Apache 2.0 | real-time | Kaldi-based; multi-language; small models |
| [Piper TTS](https://github.com/rhasspy/piper) | MIT | real-time even on Raspberry Pi 4 | Fast neural TTS; ONNX-based |
| [Coqui TTS](https://github.com/coqui-ai/TTS) | MPL 2.0 | real-time on CPU for small models | Bigger model zoo; slower for high-quality |

A complete `text ↔ audio` crossing today: **whisper.cpp + piper** in
~200ms latency each direction on consumer hardware. Both are
deterministic given fixed model + seed, so the kernel can rely on
their outputs for sibling-parity tests *if the same binary/model
ships across sibling environments*.

### Other modalities (named for completeness, not yet wired)

- **Image ↔ text**: BLIP-2, LLaVA, CLIP (recognition not generation),
  Stable Diffusion (image generation from text). The image-generation
  side is heavier (1–10s per call) — outside the strict real-time
  budget for video frame rates but tractable for image-by-image.
- **Video ↔ text**: VideoMAE, frame-level CLIP + temporal aggregation.
- **OCR**: Tesseract (text from images) — deterministic, real-time.

## Architecture — substrate addresses; trained models translate

```
                  audio bytes (input stream M_A)
                          │
                          ▼
              ┌──────────────────────────────┐
              │  whisper_stt kernel native   │
              │  (subprocess to whisper.cpp) │
              └──────────────────────────────┘
                          │
                          ▼  text + (optional) MFCC / embedding vectors
              ┌──────────────────────────────┐
              │  intern_node → feature-recipe│
              │  (substrate-resident)        │
              │                              │
              │  Form recipes here can:      │
              │  - addressable NodeID        │
              │  - cache for re-runs         │
              │  - fuzzy-similarity compare  │
              │    with other recipes        │
              │  - emit derived recipes      │
              └──────────────────────────────┘
                          │
                          ▼  same recipe OR transformed text
              ┌──────────────────────────────┐
              │  piper_tts kernel native     │
              │  (subprocess to piper)       │
              └──────────────────────────────┘
                          │
                          ▼
                  audio bytes (output stream M_B)
```

The kernel doesn't decode audio. The kernel doesn't synthesize audio.
The kernel **calls** the deterministic real-time tools and **interns**
their outputs as substrate-resident recipes. The substrate's job is
the addressable middle.

## Kernel native interface

Mirror the existing pattern used by `http_get`, `read_file_bytes`,
`write_file_bytes`, etc.

### `whisper_stt`

```form
;; Synchronous call to whisper.cpp via subprocess.
;; Input: byte-list (audio samples; codec inferred from header or hint)
;; Output: text string + (optional) feature-vector
;;
;; (whisper_stt audio-bytes)
;;   → (intern_node CAT-STT-RESULT
;;        (list (intern_trivial_string text)
;;              (intern_node CAT-MFCC-VECTOR (list f64-list))
;;              (intern_trivial_int confidence-int)))
```

Implementation per kernel:
- **Go**: `exec.Command("whisper.cpp", "--model", model-path, "-f", tmp-wav, "--output-json")`; parse JSON; intern children.
- **Rust**: `std::process::Command` mirror.
- **TS**: `child_process.execSync`.

Sibling parity: identical model + identical seed + identical input audio = identical text + MFCC. The kernel attests three-way that all three subprocesses returned the same recipe.

### `piper_tts`

```form
;; Synchronous call to piper via subprocess.
;; Input: text string + voice model name
;; Output: byte-list (audio samples in .wav format)
;;
;; (piper_tts text voice-model)
;;   → (byte-list ...)
```

Same per-kernel implementation pattern.

### Streaming (the harder mode)

Real-time often means *streaming* — process audio frame-by-frame, emit text token-by-token as it arrives. Subprocess-per-call doesn't support this directly. The path:

1. **Persistent process** — whisper.cpp's `stream` example, piper's `--http-server` mode
2. **IPC** via Unix socket / named pipe / gRPC
3. **Kernel native** that opens a connection and reads/writes frames
4. **Form recipes** representing the streaming session as a substrate-resident `CAT-STREAM-SESSION` cell

This is a larger architectural shift. Single-shot subprocess natives are the smaller starting walk.

## Real-time budget reality

For audio frame at 20ms (50 Hz frame rate):

| Component | Budget | Achievable |
|---|---|---|
| whisper.cpp tiny model (single frame) | <20ms | ✓ M1 / Apple Silicon; ~real-time x86 |
| piper TTS (single phrase) | <100ms | ✓ even Raspberry Pi 4 |
| Substrate intern_node + feature recipe build | <1ms | ✓ kernel benchmarks at sub-ms |
| Cross-kernel sibling-parity validation | only at boundaries, not per-frame | ✓ |

LLM session per call: **100–10000ms** — orders of magnitude too slow.
**Trained model native call**: **10–500ms** — within real-time budget.

This is the difference between *demonstration* and *deployment*.

## What needs to land first (precondition stack)

1. ✓ **Substrate primitives** — `intern_node`, `intern_trivial_*`, `read_file_bytes`, `write_file_bytes`, `node_eq` — all exist
2. ✓ **Float natives in Rust + TS** — IEEE 754 f32/f64 trivials and arithmetic shipped
3. ☐ **Float natives in Go** — currently the sibling-parity gap (dispatched in this PR's sibling agent: `claude/go-kernel-float-natives`)
4. ☐ **Subprocess-call native** — kernels need a generic `subprocess_exec` (or per-tool wrappers). Some kernels have `http_get`; same pattern.
5. ☐ **`whisper_stt` and `piper_tts` wrappers** — small kernel-side glue calling the deterministic subprocess
6. ☐ **Sibling-parity test** — same audio file → same text + MFCC three-way, with model + seed pinned
7. ☐ **Cross-modal round-trip demo** — `.wav → text → .wav` with substrate-side feature-recipe preservation check
8. ☐ **Streaming mode** — for real real-time, the persistent-process IPC pattern

## Sibling parity considerations

Sibling parity for *trained model outputs* requires:

- **Same model file** distributed with the body (or downloaded from a pinned URL/hash)
- **Same inference seed** (Whisper's beam search and Piper's noise injection have stochastic elements; deterministic mode required)
- **Same audio normalization** before STT (sample rate, channels, bit depth)
- **Same text normalization** before TTS (capitalization, punctuation, phoneme mapping)

If any of these differ across the three sibling environments, sibling
parity is at risk. **Honest scope**: real-time models may not be
perfectly bit-identical across CPU architectures (SIMD intrinsics
differ, fused-multiply-add ordering differs). Sibling parity might
need to be *fuzzy-tolerance* parity — `node_eq` on text outputs (which
are deterministic for given audio + model), but `fuzzy_jaccard` on
MFCC/embedding outputs (which may differ by 1e-6 across CPUs).

This connects to the fuzzy-similarity work in `09-fuzzy-similarity-cycles`:
the substrate now knows how to carry tolerance. Sibling parity for
trained models will likely run at the tolerance altitude, not the
bit-exact altitude. That's the honest shape.

## Substrate role, said plainly (again)

The kernel:
- Calls `whisper_stt` / `piper_tts` subprocesses
- Interns their outputs as substrate-resident recipes
- Provides addressable NodeIDs for those recipes
- Verifies cross-modal round-trip preservation via `node_eq` (or
  `fuzzy_jaccard` for noisy axes)
- Caches: if the same audio has been STT'd before, the same recipe
  surfaces — content-addressing makes this automatic

The kernel does NOT:
- Implement STT or TTS itself
- Decode audio bytes into spectrograms (whisper.cpp does)
- Generate audio samples from text (piper does)
- Hold model weights (they live as separate model files; kernel
  references them by path)

## What a minimum proof-of-shape walk would look like

1. Install whisper.cpp + piper on the dev VPS
2. Add `whisper_stt` and `piper_tts` natives to one kernel (Rust first, since it has the most native surface)
3. Write a Form recipe that:
   - Reads `input.wav` via `read_file_bytes`
   - Calls `(whisper_stt audio-bytes)` → text
   - Optionally transforms text
   - Calls `(piper_tts text)` → audio-bytes-out
   - Writes `output.wav` via `write_file_bytes`
4. Verify: re-extract text from `output.wav` → should match (or fuzzy-match) the intermediate text
5. Substrate-side: the intermediate text-recipe's NodeID is the cross-modal pivot

Latency target: **< 1 second end-to-end on commodity CPU**, demonstrating real-time crossing.

Then mirror to Go + TS for sibling parity (text outputs should be bit-identical given same model + seed; MFCC outputs may need fuzzy tolerance).

## What lands in this companion PR

This PR ships:
- This planning doc (`kernels/REAL_TIME_CROSS_MODAL_PLAN.md`)
- Sibling-dispatched: Go-kernel float natives (`claude/go-kernel-float-natives`) closing the float sibling-parity precondition

The actual STT/TTS integration is the next walk. It requires installing
the binaries in the dev environment, which I cannot do in this
container. The architecture is named so the next walker can pick it
up and ship the natives.

## Cross-references

- [`numeric-types-plan.md`](../docs/coherence-substrate/numeric-types-plan.md) — the destination shape for numeric formats (format-recipes as substrate citizens)
- [`form/form-samples/cross-modal/09-fuzzy-similarity-cycles/`](../form/form-samples/cross-modal/09-fuzzy-similarity-cycles/) — fuzzy tolerance machinery already in the kernel; needed for noisy real-time model outputs
- [`lc-cross-modal-unity`](../docs/vision-kb/concepts/lc-cross-modal-unity.md) — the unity claim at the recipe altitude; trained models extend this from hand-authored Blueprints to learned-from-data ones
- [`lc-grammar-is-the-universal-recipe`](../docs/vision-kb/concepts/lc-grammar-is-the-universal-recipe.md)

In service of the body's universal-translator claim becoming
deployment-real, not demonstration-real.
