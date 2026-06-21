# Rune galdr — the symbol ↔ frequency-spectrum flow match

Learn all 24 Elder Futhark runes, give each one's **galdr** (sung rune) a measurable
**vibration**, and match a heard sound back to its rune — both directions.

The **body is Form**, proven four-way (Go/Rust/TS/fkwu):

- [`form-stdlib/nordic-runes.fk`](../../form/form-stdlib/nordic-runes.fk) — the 24 runes
  as cells: glyph, name, phoneme, ætt (1–3), keyword, and a 6-band peak-normalized
  spectral **shape** over [0–200, 200–500, 500–1k, 1k–2k, 2k–4k, 4k–8k] Hz.
- [`form-stdlib/rune-frequency.fk`](../../form/form-stdlib/rune-frequency.fk) — the
  flow match: `rf-match` (spectrum → rune), `rf-glyph`, `rf-aett`, `rf-confidence`, and
  `rf-spectrum-at` (rune → spectrum). L1 over the contour, so loud/soft doesn't matter.
- Bands: `tests/nordic-runes-band.fk`, `tests/rune-frequency-band.fk` → verdict 255,
  registered in `fourth-arm-bands.txt` (`fks`). `bash scripts/fourth-arm-gate.sh
  nordic-runes rune-frequency` → **PASS-4WAY**.

The **carriers are thin** (physical I/O + sox DSP only — every decision is the Form recipe's):

The 6 bands sit in the **vocal formant range** (250–4000 Hz), above a frame drum's
~80–100 Hz fundamental — a voice-isolation front-end shared by training and matching.

```bash
# train each rune's vibration: synthesize its galdr, measure the 6-band signature,
# emit Form rows (already baked into nordic-runes.fk):
./train-rune-spectra.sh

# live flow match — name the rune in a sound:
./rune-galdr.sh --say "ssssss"           # → sowilo ᛋ   (synthesized round-trip, conf 9)
./rune-galdr.sh --listen 6               # the mic (needs a Microphone TCC grant)
./rune-galdr.sh --wav clip.wav 0 8       # a clean galdr clip (16k wav; sox can't read mp3)

# scan a recording into a nearest-rune timeline (from→to, window, hop seconds):
./rune-galdr.sh --scan journey.wav 3060 3660 3 60
```

## Honest floor

- **Clean galdr matches well.** Sowilo (s), Isa (i), Raidho (r) round-trip correctly at
  full confidence. The two nasals **nauthiz/mannaz share a contour and tie** — named, not
  hidden (their phonemes are near-identical).
- **A rune's "frequency" is the acoustic spectrum of its sung phoneme** (formant/fricative
  energy per band) — *not* a single mystical Hz. The synthesized table is a reproducible
  **reference**; the true vibrations come from real galdr matched against it.
- **macOS `say` is a weak galdr source** — one voice, stop-consonant runes (k/g/p/t/b/d)
  collapse toward their vowel. Stronger signatures want real sustained galdr samples.

## Voice isolation — in, and its honest ceiling

The bands now live in the formant range above the drum (voice-isolation front-end), and
`--scan` walks a recording into a rune timeline. On a clean galdr (synthesized, or live
through `--listen`) the round-trip is exact. On a **real drum+voice ritual mix** the scan
resolves mostly to the **low/earth-register runes** (Uruz ᚢ, Othala ᛟ, Wunjo ᚹ) — an
honest reading of the journey's *aggregate* sound-register (deep drum + low chant-toning,
fittingly earth-anchoring), not the precise rune galled in each window.

Simple sox filtering can't fully part the drum from the voice — they overlap in the
formant range. The clean per-rune reading needs one of:

- **Live close-mic galdr** (`--listen`) — no drum in the signal; works now.
- **True source separation** — harmonic/percussive split (HPSS) or a model like Demucs to
  lift the voice off the drum before matching. Needs ML tooling (numpy/torch) not yet here.
- **Forced alignment to the known order** — the ritual's lexical layer *names* the rune
  sequence (the nine bells + the Hávamál working runes); aligning the journey to that known
  order is more tractable than blind per-window classification.

This is the prototype for a **sonic sense organ** that hears tone and rune — the companion
to the speech organ's lexical layer.
