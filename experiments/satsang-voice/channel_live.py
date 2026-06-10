#!/usr/bin/env python3
"""channel_live.py — the live transcribe CHANNEL: mic cells → property-rich utterance stream → switchable views.

A mic is a CELL (a named source). Each chunk it hears becomes an UTTERANCE carrying properties the BODY
reads through the kernel — the voiced gate (voiced.fk: silence / audible / voiced) and the acoustic traits
+ trust matrix (voice-traits.fk: pitch-band, arousal, [transcript, sound, agreement] trust). A CHANNEL is
a VIEW over that stream: "switch the channel to transcript" is one projection; trust / category / speaker /
arousal are others — the same stream seen through different property lenses (the substrate's view-as).

Grounded today: text, language (whisper), sound-category (SoundAnalysis), the trust matrix, speaker
pitch-band (f0 autocorrelation), arousal (energy spread). FORMING (shown as "·", never a faked label,
until a labelled oracle earns them): genre (book / sci-fi / romance / spiritual), valence (fear ↔ love).

PRIVACY: the transcript prose is held + shown LOCALLY only. The durable/shareable channel (next rung,
channel.fk) carries the property STRUCTURE + a content-address of the text, never the words. Local
compute IS the consent.

Carriers (Mac): ffmpeg (mic + volumedetect), mlx-whisper (STT + language), sound_classify.swift
(SoundAnalysis), form-kernel-rust (the body: voiced.fk + voice-traits.fk).
Run:  COH_FORM=.../form COH_KERNEL=.../form-kernel-rust  python3 channel_live.py [--view transcript|trust|category|speaker|arousal] [n]
Live keys (in a real terminal): t transcript · r trust · c category · s speaker · a arousal · q quit.
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
# a mic cell is named by DEVICE NAME, not index — avfoundation indices shift when devices come/go
# (installing BlackHole bumped the mic from :0 to :1). Default to the built-in mic by name.
MICS = [m.strip() for m in os.environ.get("COH_MIC", "MacBook Pro Microphone").split(",") if m.strip()]
CHUNK_S = int(os.environ.get("COH_CHUNK", "6"))
LOUD_FLOOR = int(os.environ.get("COH_LOUD_FLOOR", "40"))
SPEECH_FLOOR = int(os.environ.get("COH_SPEECH_FLOOR", "40"))
TMP = "/tmp/coh-channel"
os.makedirs(TMP, exist_ok=True)


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def device_list():
    # [(index_str, name)] of avfoundation audio inputs, as the system sees them right now.
    out = sh(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""]).stderr or ""
    devs, seen_audio = [], False
    for line in out.splitlines():
        if "audio devices" in line:
            seen_audio = True; continue
        m = re.search(r"\[(\d+)\]\s+(.+?)\s*$", line)
        if seen_audio and m:
            devs.append((m.group(1), m.group(2)))
    return devs


def resolve_mic(spec):
    # spec is an index (":1") or a device-name substring ("MacBook Pro Microphone", "BlackHole");
    # returns (":idx", short-label) resolved against the CURRENT device list.
    devs = device_list()
    if re.fullmatch(r":\d+", spec):
        idx = spec[1:]
        name = next((n for i, n in devs if i == idx), spec)
    else:
        hit = next(((i, n) for i, n in devs if spec.lower() in n.lower()), None)
        idx = hit[0] if hit else spec.lstrip(":")
        name = hit[1] if hit else spec
    label = re.sub(r"MacBook Pro |2ch", "", name).strip() or name
    return ":" + idx, label[:11]


def record(idx, dst):
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-i", idx,
        "-t", str(CHUNK_S), "-ar", "16000", "-ac", "1", "-y", dst])
    return dst


def level(wav):
    out = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", wav, "-af", "volumedetect", "-f", "null", "/dev/null"])
    m = re.search(r"mean_volume:\s*([-0-9.]+)", out.stderr or "")
    db = float(m.group(1)) if m else -90.0
    return max(0, min(99, int(round(db)) + 90))


def samples(wav):
    try:
        w = wave.open(wav, "rb"); raw = w.readframes(w.getnframes()); w.close()
        return list(struct.unpack("<%dh" % (len(raw) // 2), raw[: (len(raw) // 2) * 2]))
    except Exception:
        return []


def windows8(s):
    # 8-window energy envelope, each 0..9 — the same cheap feature the co-learning arm uses.
    if not s:
        return [0] * 8
    win = max(1, len(s) // 8)
    return [min(9, (sum(abs(x) for x in s[i*win:(i+1)*win] or [0]) // len(s[i*win:(i+1)*win] or [1])) // 800)
            for i in range(8)]


def f0(s):
    # rough fundamental pitch (Hz) via autocorrelation on the loudest 2048-sample window; 0 if unvoiced.
    win = 2048
    if len(s) < win:
        return 0
    bi, be = 0, -1
    for i in range(0, len(s) - win, win):
        e = sum(abs(x) for x in s[i:i+win])
        if e > be:
            be, bi = e, i
    seg = s[bi:bi+win]
    sr, lo, hi = 16000, 40, 200          # 80–400 Hz
    bl, bc = 0, 0
    for lag in range(lo, hi):
        c = sum(seg[k] * seg[k+lag] for k in range(0, win - lag, 2))
        if c > bc:
            bc, bl = c, lag
    return int(sr / bl) if bl else 0


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
    # (text, language, no_speech_prob) — language is a property; no_speech_prob feeds the trust gate.
    out = sh([WHISPER_PY, "-c",
              f"import mlx_whisper,json,sys;r=mlx_whisper.transcribe(sys.argv[1],"
              f"path_or_hf_repo='{WHISPER_MODEL}');s=(r.get('segments') or [{{}}]);"
              f"print(json.dumps({{'t':r['text'],'l':r.get('language','?'),'n':s[0].get('no_speech_prob',1.0)}}))", wav])
    try:
        d = json.loads((out.stdout or "").strip().splitlines()[-1])
        return (d.get("t") or "").strip(), (d.get("l") or "?"), float(d.get("n", 1.0))
    except Exception:
        return "", "?", 1.0


def kernel(recipe, expr, retries=2):
    drv = os.path.join(TMP, "drv.fk")
    with open(drv, "w") as fh:
        fh.write(expr)
    val = "?"
    for _ in range(retries):
        out = sh([KERNEL, recipe, drv], cwd=FORM)
        line = (out.stdout or out.stderr).strip().splitlines()
        val = line[-1].strip() if line else ""
        if val and "crash" not in val:
            return val
    return val or "?"


def gate(loudness, speechiness):
    out = kernel("form-stdlib/voiced.fk", f"(do (gate-level {loudness} {speechiness} {LOUD_FLOOR} {SPEECH_FLOOR}))")
    try:
        return int(out)
    except Exception:
        return 0


def traits(f0v, windows, g, speechiness, agree):
    # one body call → [speaker-band, arousal, transcript-trust, sound-trust, agreement-trust]
    wv = " ".join(map(str, windows))
    out = kernel("form-stdlib/voice-traits.fk",
                 f"(do (list (speaker-band {f0v}) (arousal (list {wv})) "
                 f"(transcript-trust {g} {speechiness}) (sound-trust {g}) (agreement-trust {agree})))")
    try:
        v = json.loads(out)
        return v if isinstance(v, list) and len(v) == 5 else [0, 0, 0, 0, 0]
    except Exception:
        return [0, 0, 0, 0, 0]


# --- property renderers (the readings, named honestly) ---
PITCH = {0: "low-voiced", 1: "mid-voiced", 2: "high-voiced"}


def arousal_word(a):
    return "calm" if a < 3 else ("even" if a < 6 else "active")


def render(view, u):
    # u: dict with ts, mic, cat, lang, f0, band, arousal, tvec, text, words
    head = " ".join(u["text"].split()[:9]) + ("…" if u["words"] > 9 else "")
    t = u["tvec"]
    clk = time.strftime("%H:%M:%S", time.localtime(u["ts"]))
    if view == "trust":
        return (f"[{clk}] {u['mic']} trust▸ transcript:{t[0]} sound:{t[1]} agree:{t[2]}  "
                f"(nsp→speechiness {u['speechy']})  | “{head}”")
    if view == "category":
        return f"[{clk}] {u['mic']} category▸ {u['cat']:<7} (oracle: SoundAnalysis)  | “{head}”"
    if view == "speaker":
        return f"[{clk}] {u['mic']} speaker▸ f0 {u['f0']:>3}Hz → {PITCH[u['band']]:<11} (pitch, not identity)  | “{head}”"
    if view == "arousal":
        return f"[{clk}] {u['mic']} arousal▸ {u['arousal']}/9 {arousal_word(u['arousal']):<6} (energy-dynamics)  | “{head}”"
    # transcript (rich, default): text + language + trust matrix + the other properties
    return (f"[{clk}] {u['mic']} {u['cat']:<6} {u['lang']:<2} {PITCH[u['band']]:<11} {arousal_word(u['arousal']):<6} "
            f"trust[{t[0]},{t[1]},{t[2]}] | “{head}”\n"
            f"            genre:· valence:· (forming — no labelled oracle yet)")


def read_key(default=None):
    # non-blocking single key, only if stdin is a real terminal (live switching for Urs; arg-driven for tests)
    if not sys.stdin.isatty():
        return None
    import select
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1)
    return None


def main():
    args = [a for a in sys.argv[1:]]
    view = "transcript"
    if "--view" in args:
        i = args.index("--view"); view = args[i+1]; del args[i:i+2]
    n = int(args[0]) if args else 6

    for p, nm in ((KERNEL, "kernel"), (ORACLE, "oracle"), (WHISPER_PY, "whisper")):
        if not os.path.exists(p):
            print(f"missing {nm}: {p}"); sys.exit(1)

    cells = {}
    for spec in MICS:
        idx, label = resolve_mic(spec)
        cells[idx] = {"name": label, "stream": []}
    sound_ex = []
    s_checks = s_agree = silent = 0

    raw = None
    if sys.stdin.isatty():
        import termios, tty
        raw = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
    try:
        named = ", ".join(f"{c['name']}({idx})" for idx, c in cells.items())
        print(f"live transcribe channel — {len(cells)} mic cell(s): {named}; view: {view}.")
        print("keys: t transcript · r trust · c category · s speaker · a arousal · q quit\n")
        for _ in range(n):
            k = read_key()
            if k in ("t", "r", "c", "s", "a"):
                view = {"t": "transcript", "r": "trust", "c": "category", "s": "speaker", "a": "arousal"}[k]
                print(f"  ── channel → {view} ──")
            if k == "q":
                break
            for mic, cell in cells.items():
                wav = record(mic, os.path.join(TMP, f"{cell['name']}.wav"))
                ts = int(time.time())
                loud = level(wav)
                text, lang, nsp = transcribe(wav)
                speechy = 100 - min(100, int(round(nsp * 100)))
                g = gate(loud, speechy)
                if g == 0:
                    silent += 1
                    print(f"[{time.strftime('%H:%M:%S')}] {cell['name']} silence — (mic {loud}/99, nothing to hear)")
                    continue
                s = samples(wav)
                win = windows8(s)
                cat = sound_oracle(wav)
                pitch = f0(s) if g >= 2 else 0
                # co-learning agreement signal (does the Form sound-arm already match the oracle?)
                agree = 0
                if sound_ex:
                    fv = " ".join(map(str, win))
                    protos = " ".join('(list "%s" (list %s))' % (l, " ".join(map(str, f))) for l, f in sound_ex)
                    pred = kernel("form-stdlib/nearest-shape.fk", f"(do (ns-label (list {fv}) (list {protos})))").strip('"')
                    s_checks += 1
                    if pred == cat:
                        s_agree += 1; agree = 1
                sound_ex.append((cat, win))
                band, arous, tt, st, at = traits(pitch, win, g, speechy, agree)
                if g < 2:
                    text = ""                      # audible non-speech: classify, no transcript
                u = {"ts": ts, "mic": cell["name"], "cat": cat, "lang": lang if g >= 2 else "·",
                     "f0": pitch, "band": band, "arousal": arous, "tvec": [tt, st, at],
                     "speechy": speechy, "text": text, "words": len(text.split())}
                cell["stream"].append(u)
                print(render(view, u))
    finally:
        if raw is not None:
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, raw)

    heard = sum(len(c["stream"]) for c in cells.values())
    rate = round(100 * s_agree / s_checks) if s_checks else 0
    print(f"\nchannel held {heard} utterance(s) across {len(cells)} mic cell(s); {silent} silent chunk(s) gated. "
          f"the Form sound-arm agreed with the oracle {rate}% of the time. "
          f"views are projections of one stream — switch any time; genre/valence stay honest-empty until labelled.")
    if heard == 0:
        print("\nEvery chunk was silence at the mic. If audio WAS playing, route system audio through a "
              "loopback device (BlackHole) and set COH_MIC=':BlackHole 2ch'.")


if __name__ == "__main__":
    main()
