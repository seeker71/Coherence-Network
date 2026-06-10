#!/usr/bin/env python3
"""voice_io.py — the channel's two mouths: TTS (text → wav) and STT (wav → text), free carriers, gated by the body.

audio-grammar.form names the emit and parse intrinsics; this carrier binds the free, cross-platform
halves so the loop runs anywhere — the Mac-native carriers (mlx-whisper, `say`) stay first where they
live, these stand in everywhere else. Same discipline as affect_sense.py: every oracle optional,
absence shown as forming, and the BODY decides what a transcript is worth — voiced.fk gates before
the words count, voice-traits' transcript-trust scales by the recognizer's own confidence.

  TTS  — piper (rhasspy, free, local onnx voice; COH_PIPER_VOICE names the .onnx)
         → espeak-ng fallback (apt/brew install, formant synth — robotic but honest and tiny)
  STT  — faster-whisper (free, CPU int8, ~40 languages)
         → mlx-whisper fallback (Apple-Silicon)

The round-trip is the witness: text → TTS → wav → loudness + speechiness → voiced.fk gate →
STT → transcript. A synthesis the recognizer can't hear as speech fails the gate — the loop
proves both mouths at once or names which one is forming.

Run:  python3 voice_io.py "anything you want spoken and heard back"
      python3 voice_io.py --stt clip.wav        # one direction only
      python3 voice_io.py --tts "text" out.wav  # one direction only
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from affect_sense import FORMING, RECIPES, kernel, loudness_db  # noqa: E402  (one experiment, one helper set)

LOUD_FLOOR = int(os.environ.get("COH_LOUD_FLOOR", "40"))
SPEECH_FLOOR = int(os.environ.get("COH_SPEECH_FLOOR", "40"))
PIPER_VOICE = os.environ.get("COH_PIPER_VOICE", "/tmp/piper-voices/en_US-lessac-medium.onnx")
TMP = "/tmp/coh-affect"
os.makedirs(TMP, exist_ok=True)


def tts(text, wav_out):
    # piper first (natural, local onnx), espeak-ng second (tiny, everywhere). Returns the carrier
    # name, or None when no mouth is present — never a silent empty file.
    if os.path.exists(PIPER_VOICE):
        r = subprocess.run([os.path.join(os.path.dirname(sys.executable), "piper"),
                            "-m", PIPER_VOICE, "-f", wav_out],
                           input=text, capture_output=True, text=True)
        if r.returncode == 0 and os.path.getsize(wav_out) > 44:
            return "piper"
    r = subprocess.run(["espeak-ng", "-v", "en-us", "-w", wav_out, text], capture_output=True)
    if r.returncode == 0 and os.path.exists(wav_out) and os.path.getsize(wav_out) > 44:
        return "espeak-ng"
    return None


def stt(wav):
    # (text, language, speechiness 0..100, carrier) — speechiness is 100 − no_speech_prob·100,
    # the same number voiced.fk gates on. None carrier → forming.
    try:
        from faster_whisper import WhisperModel
        segs, info = WhisperModel("tiny", compute_type="int8").transcribe(wav)
        segs = list(segs)
        nsp = min((s.no_speech_prob for s in segs), default=1.0)
        text = " ".join(s.text.strip() for s in segs).strip()
        return text, info.language, int(round((1.0 - nsp) * 100)), "faster-whisper"
    except Exception:
        pass
    try:
        import mlx_whisper
        d = mlx_whisper.transcribe(wav)
        nsp = min((s.get("no_speech_prob", 1.0) for s in d.get("segments", [])), default=1.0)
        return (d.get("text") or "").strip(), d.get("language", "?"), int(round((1.0 - nsp) * 100)), "mlx-whisper"
    except Exception:
        return "", "?", None, None


def roundtrip(text):
    wav = os.path.join(TMP, "roundtrip.wav")
    mouth = tts(text, wav)
    if mouth is None:
        print(f"tts   ▸ {FORMING}  (no piper voice at COH_PIPER_VOICE, no espeak-ng)")
        return
    loud = loudness_db(wav)
    print(f"tts   ▸ {mouth} spoke {os.path.getsize(wav)} bytes  (loudness {loud})")

    heard, lang, sp, ear = stt(wav)
    if ear is None:
        print(f"stt   ▸ {FORMING}  (no faster-whisper, no mlx-whisper)")
        return
    gate = int(kernel(RECIPES, f"(do (gate-level {loud} {sp} {LOUD_FLOOR} {SPEECH_FLOOR}))") or 0)
    trust = int(kernel(RECIPES, f"(do (transcript-trust {gate} {sp}))") or 0)
    print(f"gate  ▸ {['silence', 'audible', 'voiced'][gate]}  (speechiness {sp}) → transcript-trust {trust}/9")
    if gate >= 2:
        print(f"stt   ▸ {ear} [{lang}] heard: “{heard}”")
    else:
        print(f"stt   ▸ transcript withheld — the body doesn't trust words below the voiced gate")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--stt":
        text, lang, sp, ear = stt(sys.argv[2])
        print(f"[{ear or FORMING}] [{lang}] speechiness {sp if sp is not None else FORMING}: “{text}”")
    elif len(sys.argv) >= 4 and sys.argv[1] == "--tts":
        mouth = tts(sys.argv[2], sys.argv[3])
        print(f"[{mouth or FORMING}] → {sys.argv[3]}")
    elif len(sys.argv) == 2:
        roundtrip(sys.argv[1])
    else:
        print(__doc__.strip().splitlines()[0])
        print("usage: voice_io.py \"text\" | --stt clip.wav | --tts \"text\" out.wav")
        sys.exit(1)
