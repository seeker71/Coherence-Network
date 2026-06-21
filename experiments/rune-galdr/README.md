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

```bash
# train each rune's vibration: synthesize its galdr, measure the 6-band signature,
# emit Form rows (already baked into nordic-runes.fk):
./train-rune-spectra.sh

# live flow match — name the rune in a sound:
./rune-galdr.sh --say "ssssss"          # → sowilo ᛋ   (synthesized round-trip)
./rune-galdr.sh --wav clip.wav 0 10      # a recording clip (16k wav; sox can't read mp3)
./rune-galdr.sh --listen 6               # the mic (needs a Microphone TCC grant)
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

## Next step — voice/drum separation for live ritual recordings

Matching a rune inside a real ritual recording fails today because the **frame drum
(~80–100 Hz) dominates the low band**, so 10 s clips of the drum+voice mix resolve to
low-energy runes regardless of what's sung. To hear the *sung* rune, the carrier must
isolate the vocal formant range (bandpass ~180–3400 Hz) before extracting the contour,
with training re-run through the same filter. That is the prototype for a **sonic sense
organ** that hears tone and rune — the companion to the speech organ's lexical layer.
