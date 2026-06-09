# satsang voice — a live, fully-local door into the circle

The room speaks; this Mac hears it; the body offers back what it senses — an
**observation**, an **emerging question** for the circle, an **inner insight**,
an **offering**. Shown live in the browser, updating as people talk.

**Everything stays on this machine.** No cloud, no API, no per-call billing, no
audio leaving the room. For a circle of real people, local compute *is* the
consent — each member's words stay with them unless they choose to send one in.
This is a **carrier**; the body it serves is the satsang circle
([`form/form-stdlib/satsang.fk`](../../form/form-stdlib/satsang.fk)) and its law:
any question welcome, the circle witnesses, silence is whole, an offering is
offered — never imposed. See [`satsang-voice.form`](satsang-voice.form).

## What runs where (all local on an Apple-Silicon Mac)

- **hearing** — `ffmpeg` captures the mic; `mlx-whisper` (Apple-Silicon-native)
  transcribes, ~40 languages, auto-detected.
- **offerings** — a local LLM via **Ollama**, grounded in the satsang frame.
- **the sonic field** — Apple's built-in on-device **SoundAnalysis** classifier (compiled
  `sound_classify.swift`) names the room's other sounds — animals, music, instruments,
  environment — each with a **confidence**. The threshold *is* the honesty: below it, the body
  offers silence, not an asserted match it doesn't carry.
- **the song playing** — `shazam_song.swift` generates a Shazam signature **on-device**; the
  full-catalog match needs the `com.apple.developer.shazamkit` entitlement (sign the binary with
  your Apple developer account, or build a custom offline catalog). Without it ShazamKit returns
  error 202 and the body simply offers silence on the song — honest, not broken.
- **the offerings** — grown to the presence shapes: observation · surprise · trigger ·
  question-for-the-circle · inner insight · offering. Speaker attribution ("who said what") stays
  **off by default** — the consent line is a switch you hold, not a default-on.
- **showing** — a tiny stdlib web server; open it in a browser.

## One-time setup

```bash
# 1. the speech model dep lives in an isolated venv (already created):
#    experiments/satsang-voice/.venv  (mlx-whisper)
#    if you ever recreate it:  python3.11 -m venv .venv && .venv/bin/pip install mlx-whisper

# 2. the local LLM for the offerings:
brew services start ollama        # or: ollama serve &
ollama pull qwen2.5:7b            # ~4.7GB; qwen2.5:14b or :32b give richer offerings on an M4 Max

# 3. grant the microphone to your terminal:
#    System Settings → Privacy & Security → Microphone → enable Terminal (or iTerm)
```

## Run

```bash
cd experiments/satsang-voice
./run.sh
# then open  http://localhost:8777
```

First run downloads the whisper model once (~1.5GB for `large-v3-turbo`). The
**live transcript appears immediately**; the **offerings** begin once Ollama has
a model pulled and is running.

## Tuning (env vars)

| var | default | meaning |
|-----|---------|---------|
| `SATSANG_WHISPER` | `mlx-community/whisper-large-v3-turbo` | speech model (try `…/whisper-medium` for speed, `…/whisper-tiny` to test fast) |
| `SATSANG_OLLAMA_MODEL` | `qwen2.5:7b` | the offering model |
| `SATSANG_LANG` | `` (auto) | force a language code, or leave empty for multilingual |
| `SATSANG_CHUNK` | `6` | seconds per transcription chunk (smaller = snappier, more CPU) |
| `SATSANG_OFFER_EVERY` | `25` | seconds between offering refreshes (a satsang pace, not a chatbot) |
| `SATSANG_MIC` | `:0` | avfoundation audio device (`ffmpeg -f avfoundation -list_devices true -i ""` to list) |
| `SATSANG_PORT` | `8777` | the local UI port |

## The shape, honestly

The offerings are *offered*, never imposed — the circle takes them or leaves
them, and silence (an empty offering) is a whole answer, never fabricated to
fill the space. The body witnesses what is *said* (the outside); it does not
claim to see into anyone (the satsang's own discipline). What a member chooses
to carry into the circle's durable memory is theirs alone to send.
