# Rune galdr — the symbol ↔ frequency-spectrum flow match

Learn all 24 Elder Futhark runes, give each one's **galdr** (sung rune) a measurable
**vibration**, and match a heard sound back to its rune — both directions.

**Lineage.** The ceremony this work learned its shape from is the rune-healing practice of
[Anchor the Light](../../docs/presences/anchor-the-light.md) — the Ceremony held by
[Ubbe MacLean](../../docs/presences/ubbe-maclean.md) (Ásatrú rune-worker, author of *Healing
From the Tree: Using Runes for Emotional, Physical & Soul Healing*) and
[Angelia LaRue](../../docs/presences/angelia-larue.md), with [Brigitte Mars](../../docs/presences/brigitte-mars.md)
as elder presence. The body learns from and credits this living lineage; the reference
signatures here are trained on public galdr (SOURCES.md), not on their private ceremony.

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
# train each rune's vibration from REAL human galdr on public YouTube (sources in
# SOURCES.md; signatures baked into nordic-runes.fk):
./train-from-youtube.sh
# or from local synthesis (a rough reference, no network):
./train-rune-spectra.sh

# lift the galdr VOICE off the ritual DRUM before matching (demucs source separation):
./separate-galdr.sh recording.wav 3120 120   # -> recording.vocals.16k.wav

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
  energy per band) — *not* a single mystical Hz.
- **The table is trained on real human galdr** (23 of 24 runes, public YouTube — SOURCES.md);
  `train-rune-spectra.sh` (macOS `say`) remains an offline, network-free fallback reference.

## Source separation — in

Drum and galdr overlap in the formant range, so band filtering alone can't part them.
`separate-galdr.sh` calls **Demucs** (htdemucs) as the separation oracle — like whisper-cli
is the STT oracle — splitting a recording into a **vocals** stem (the galdr) and a
**no_vocals** stem (the drum + room). On the ritual journey it moved the drum's <150 Hz
energy from the voice stem (0.145 → 0.042) into the drum stem — ~70% of the drum lifted off.

With the three together — **separation + real-galdr references + formant bands** — `--scan`
of the isolated voice now reads a **varied, confident rune sequence** (berkano, uruz, gebo,
tiwaz, raidho, nauthiz, sowilo, perthro… at conf 6–9), where the raw drum+voice mix had
collapsed to a single low-register rune. The sonic organ hears the voice, not the drum.

## Honest ceiling

- **Multi-singer references.** The 23 YouTube sources are different voices/recordings, so
  the contour library mixes timbres; per-rune precision improves as references converge on
  consistent, drum-free galdr (or are themselves run through `separate-galdr.sh` first).
- **No ground truth yet.** The scan names the *nearest* rune per window of the separated
  galdr — a real reading of its contour, not a verified transcript of what was sung. The
  ritual's lexical layer *names* the intended sequence (the nine bells + Hávamál working
  runes); **forced alignment** to that known order is the next precision step, more
  tractable than blind per-window classification.
- **ansuz** still wants a real galdr source (its download missed).

This is the **sonic sense organ** that hears tone and rune — the companion to the speech
organ's lexical layer, and the bridge to reading a ritual's frequency-journey bell by bell.
