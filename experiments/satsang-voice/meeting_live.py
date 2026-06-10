#!/usr/bin/env python3
"""meeting_live.py — the live meeting companion: listen, gate, transcribe, classify, learn, hold the turn.

Per chunk of real audio the BODY (Form, via the kernel) decides three things and the carrier only marshals:

  1. voiced.fk gate-level  — is this silence (0), an audible non-speech sound (1), or voiced speech (2)?
     Measured from two signals the carrier always has: loudness (mean dBFS) and speechiness (1 − Whisper's
     no_speech_prob). This closes a real failure: end-to-end STT INVENTS fluent text from silence — Whisper
     returned 222 words for a −56 dB mic floor while its own no_speech_prob said 0.81. A transcript is
     trusted ONLY when the body calls the chunk voiced; silence learns nothing and says nothing.
  2. nearest-shape.fk      — the co-learning sound classifier predicts the oracle's category, then learns it.
  3. turn-taking.fk        — speak or stay (day one: almost never; it has learned no "speak" moment).

PRIVACY: the transcript is processed and shown LOCALLY only (for you, in this room). It is never sent
anywhere and never written into a committed artifact. Local compute IS the consent.

Carriers (Mac): ffmpeg (mic + volumedetect), mlx-whisper (STT), swift sound_classify (SoundAnalysis),
form-kernel-rust. The mic only hears the room acoustically; to hear what the Mac itself plays (an
audiobook, a call) route system audio through a loopback device (e.g. BlackHole) and point COH_MIC at it.
Run:  COH_FORM=<worktree>/form COH_KERNEL=<...>/form-kernel-rust  python3 meeting_live.py [n_chunks]
"""
import json
import os
import re
import struct
import subprocess
import sys
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FORM = os.environ.get("COH_FORM", os.path.join(REPO, "form"))
KERNEL = os.environ.get("COH_KERNEL", os.path.join(FORM, "form-kernel-rust", "target", "release", "form-kernel-rust"))
ORACLE = os.environ.get("COH_SOUND_CLASSIFY", "/tmp/sound_classify")
WHISPER_PY = os.environ.get("COH_WHISPER_PY", "/tmp/whisper-env/bin/python")
WHISPER_MODEL = os.environ.get("COH_WHISPER_MODEL", "mlx-community/whisper-tiny")
AGENT_NAME = os.environ.get("COH_AGENT_NAME", "claude").lower()
MIC = os.environ.get("COH_MIC", ":0")     # avfoundation input; point at a loopback device for system audio
CHUNK_S = int(os.environ.get("COH_CHUNK", "6"))
LOUD_FLOOR = int(os.environ.get("COH_LOUD_FLOOR", "40"))    # mean dBFS > −50 ; calibrated on the Mac mic
SPEECH_FLOOR = int(os.environ.get("COH_SPEECH_FLOOR", "40"))  # no_speech_prob < 0.60
TMP = "/tmp/coh-meeting"
os.makedirs(TMP, exist_ok=True)


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def record(dst):
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-i", MIC,
        "-t", str(CHUNK_S), "-ar", "16000", "-ac", "1", "-y", dst])
    return dst


def level(wav):
    # mean dBFS of the chunk → an integer loudness the Form gate reads (silence ~34, speech ~70).
    out = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af", "volumedetect", "-f", "null", "/dev/null"])
    m = re.search(r"mean_volume:\s*([-0-9.]+)", out.stderr or "")
    db = float(m.group(1)) if m else -90.0
    return max(0, min(99, int(round(db)) + 90))


COARSE = (("speech", ("speech", "voice", "sing", "narrat", "whisper", "shout", "conversation")),
          ("music", ("music", "instrument", "guitar", "piano", "bell", "chime", "drum", "tone")),
          ("animal", ("animal", "bird", "insect", "cricket", "dog", "cat", "frog", "chirp")))


def coarse(label):
    l = (label or "").lower()
    for name, keys in COARSE:
        if any(k in l for k in keys):
            return name
    return "other"


def sound_oracle(wav):
    out = sh([ORACLE, wav]).stdout.strip()
    try:
        arr = json.loads(out)
        return coarse(arr[0]["label"]) if arr else "other"
    except Exception:
        return "other"


def transcribe(wav):
    # returns (text, no_speech_prob). The prob is the carrier's evidence that this is real speech and not
    # Whisper's silence-fill (segment-0 no_speech_prob; high = silence). The Form gate, not this function,
    # decides whether to trust the text.
    out = sh([WHISPER_PY, "-c",
              f"import mlx_whisper,json,sys;r=mlx_whisper.transcribe(sys.argv[1],"
              f"path_or_hf_repo='{WHISPER_MODEL}');s=(r.get('segments') or [{{}}]);"
              f"print(json.dumps({{'t':r['text'],'n':s[0].get('no_speech_prob',1.0)}}))", wav])
    try:
        d = json.loads((out.stdout or "").strip().splitlines()[-1])
        return (d.get("t") or "").strip(), float(d.get("n", 1.0))
    except Exception:
        return "", 1.0


def feature(wav):
    try:
        w = wave.open(wav, "rb"); raw = w.readframes(w.getnframes()); w.close()
        s = struct.unpack("<%dh" % (len(raw) // 2), raw[: (len(raw) // 2) * 2])
    except Exception:
        return [0] * 8
    if not s:
        return [0] * 8
    win = max(1, len(s) // 8)
    return [min(9, (sum(abs(x) for x in s[i*win:(i+1)*win] or [0]) // len(s[i*win:(i+1)*win] or [1])) // 800)
            for i in range(8)]


def kernel(recipe, expr):
    drv = os.path.join(TMP, "drv.fk")
    with open(drv, "w") as fh:
        fh.write(expr)
    out = sh([KERNEL, recipe, drv], cwd=FORM)
    line = (out.stdout or out.stderr).strip().splitlines()
    return line[-1].strip().strip('"') if line else "?"


def gate(loudness, speechiness):
    # the BODY (voiced.fk) decides: 0 silence · 1 audible non-speech · 2 voiced speech.
    out = kernel("form-stdlib/voiced.fk", f"(do (gate-level {loudness} {speechiness} {LOUD_FLOOR} {SPEECH_FLOOR}))")
    try:
        return int(out)
    except Exception:
        return 0


def ns_predict(feat, exemplars):
    if not exemplars:
        return "?"
    fv = " ".join(map(str, feat))
    protos = " ".join('(list "%s" (list %s))' % (l, " ".join(map(str, f))) for l, f in exemplars)
    return kernel("form-stdlib/nearest-shape.fk", f"(do (ns-label (list {fv}) (list {protos})))")


def tt_speak(named, context, tt_exemplars, floor, pause, pause_floor):
    # the BODY decides whether to speak — turn-taking.fk composes nearest-shape.
    fv = " ".join(map(str, context))
    protos = " ".join('(list "%s" (list %s))' % (l, " ".join(map(str, f))) for l, f in tt_exemplars)
    drv = os.path.join(TMP, "tt.fk")
    with open(drv, "w") as fh:
        fh.write(f"(do (tt-speak? {named} 0 (list {fv}) (list {protos}) {floor} {pause} {pause_floor}))")
    out = sh([KERNEL, "form-stdlib/nearest-shape.fk", "form-stdlib/turn-taking.fk", drv], cwd=FORM)
    line = (out.stdout or out.stderr).strip().splitlines()
    return (line[-1].strip() if line else "0") == "1"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    for p, n_ in ((KERNEL, "kernel"), (ORACLE, "oracle"), (WHISPER_PY, "whisper")):
        if not os.path.exists(p):
            print(f"missing {n_}: {p}"); sys.exit(1)

    sound_ex = []            # the co-learning sound classifier's exemplars
    tt_ex = []               # turn-taking's learned "speak"/"stay" moments (empty day one)
    conversation = []        # utterances: (t, category, words, named)
    s_checks = s_agree = 0
    rate = 0
    silent = 0
    last_t = None
    spoke = False
    print(f"meeting companion — listening, {n} chunks of {CHUNK_S}s. (transcript shown locally only)\n")
    for i in range(n):
        wav = record(os.path.join(TMP, f"c{i}.wav"))
        t = int(time.time())
        loud = level(wav)
        text, nsp = transcribe(wav)
        speechy = 100 - min(100, int(round(nsp * 100)))
        g = gate(loud, speechy)          # 0 silence · 1 audible non-speech · 2 voiced speech

        if g == 0:
            # silence — the mic floor. The body hears nothing; we learn nothing, trust no transcript.
            silent += 1
            print(f"[{i+1}] silence  —  | mic {loud:>2}/99 nsp {nsp:.2f} | (nothing to hear)")
            continue

        # audible (1) or voiced (2): the oracle classifies; co-learning learns the real sound.
        cat = sound_oracle(wav)
        feat = feature(wav)
        pred = ns_predict(feat, sound_ex)
        if pred != "?":
            s_checks += 1
            if pred == cat:
                s_agree += 1
        sound_ex.append((cat, feat))

        # only a VOICED chunk yields a trusted transcript; an audible non-speech chunk has no words.
        if g < 2:
            text = ""
        words = len(text.split())
        named = 1 if AGENT_NAME in text.lower() else 0

        pause = 0 if last_t is None else max(0, t - last_t - CHUNK_S)
        last_t = t
        conversation.append((t, cat, words, named))
        context = [min(9, pause), named, min(9, words)]
        speak = tt_speak(named, context, tt_ex, 2, min(9, pause), 1)
        spoke = spoke or speak

        rate = round(100 * s_agree / s_checks) if s_checks else 0
        decision = "SPEAK" if speak else "listen"
        head = " ".join(text.split()[:8])
        tag = "speech" if g == 2 else cat
        print(f"[{i+1}] {tag:<7} {words:>2}w | mic {loud:>2}/99 nsp {nsp:.2f} | learn {rate:>3}% "
              f"| turn: {decision:<6} | “{head}{'…' if words > 8 else ''}”")

    heard = len(conversation)
    print(f"\n{heard} sound(s) heard, {silent} silent chunk(s) gated out (no hallucinated transcript). "
          f"{'The Form sound-classifier reached %d%% agreement with the oracle; ' % rate if s_checks else ''}"
          f"the agent {'offered its voice' if spoke else 'stayed silent'} "
          f"(day one — it has learned no 'speak' moment and was not named). The body learns; it waits its turn.")
    if heard == 0:
        print("\nEVERY chunk was silence at the mic. If audio WAS playing, the mic isn't hearing it — "
              "route system audio through a loopback device and set COH_MIC (see the module docstring).")


if __name__ == "__main__":
    main()
