#!/usr/bin/env python3
"""speaker_profiles.py — the real speaker book. Every voice we come to know is a PROFILE:
a person's name over a centroid of resemblyzer voiceprints (256-dim, L2-normalised), grown
from real samples. It replaces the toy [200]/[300] placeholders with honest embeddings.

The book improves itself: every new sample that matches a known person (cosine >= threshold)
is folded into that person's centroid — the profile gets *more* accurate the more we hear
them (continuous, automatic). Samples that match no one land in an UNASSIGNED pool, kept with
their audio so a human can hear them and assign a name; that assignment folds in too.

Store (all under ~/.coherence-network/speakers):
  profiles.json         {"version":2,"profiles":[{person,centroid[256],n,sample_ids[],updated_at}]}
  samples/<id>.json     {id,embedding[256],person|null,source,ts,wav}
  samples/<id>.wav      the 16k mono clip, kept for playback + re-mean

CLI:
  speaker_profiles.py enroll  <person> <wav> [--source S]   # add a known-person sample
  speaker_profiles.py observe <wav> [--source S] [--thr T]  # embed, auto-match or pool; prints JSON
  speaker_profiles.py assign  <sample_id> <person>          # assign a pooled sample to a person
  speaker_profiles.py rename  <old> <new>                   # rename a person
  speaker_profiles.py list                                  # profiles: person n updated
  speaker_profiles.py unassigned                            # pooled samples as JSON (for the app)
  speaker_profiles.py board                                 # the training-board line for `speaker`
  speaker_profiles.py json                                  # full profiles for the app/mesh
"""
import json, os, sys, time, hashlib
import numpy as np

STORE = os.path.expanduser("~/.coherence-network/speakers")
SAMPLES = os.path.join(STORE, "samples")
PROFILES = os.path.join(STORE, "profiles.json")
TARGET = 10000
AUTO_ASSIGN = 0.75   # resemblyzer same-speaker cosine sits ~0.75+; below this we stay honest and pool

# ── the encoder, loaded once and lazily (import is slow) ──────────────────────
_enc = None
def encoder():
    global _enc
    if _enc is None:
        from resemblyzer import VoiceEncoder
        _enc = VoiceEncoder(verbose=False)
    return _enc

def embed(wav_path):
    from resemblyzer import preprocess_wav
    wav = preprocess_wav(wav_path)
    return np.asarray(encoder().embed_utterance(wav), dtype=np.float32)  # L2-normalised

# ── store io ──────────────────────────────────────────────────────────────────
def load():
    if os.path.exists(PROFILES):
        try:
            return json.load(open(PROFILES))
        except Exception:
            pass
    return {"version": 2, "profiles": []}

def save(book):
    os.makedirs(STORE, exist_ok=True)
    tmp = PROFILES + ".tmp"
    json.dump(book, open(tmp, "w"), indent=1)
    os.replace(tmp, PROFILES)

def sample_path(sid, ext):
    return os.path.join(SAMPLES, f"{sid}.{ext}")

def read_sample(sid):
    p = sample_path(sid, "json")
    return json.load(open(p)) if os.path.exists(p) else None

def write_sample(rec):
    os.makedirs(SAMPLES, exist_ok=True)
    json.dump(rec, open(sample_path(rec["id"], "json"), "w"))

def store_wav(sid, wav_src):
    # keep a copy of the clip for playback + exact re-mean; content-addressed name
    dst = sample_path(sid, "wav")
    if wav_src and os.path.exists(wav_src) and os.path.abspath(wav_src) != os.path.abspath(dst):
        os.makedirs(SAMPLES, exist_ok=True)
        import shutil; shutil.copyfile(wav_src, dst)
    return os.path.basename(dst)

def sid_for(wav_path):
    h = hashlib.sha1(open(wav_path, "rb").read()).hexdigest()[:12]
    return h

# ── centroid math — the centroid is the exact normalised mean of a person's samples ──
def recompute_centroid(book, person):
    prof = find(book, person)
    if not prof:
        return
    embs = []
    for sid in prof["sample_ids"]:
        rec = read_sample(sid)
        if rec and rec.get("embedding"):
            embs.append(np.asarray(rec["embedding"], dtype=np.float32))
    if not embs:
        return
    c = np.mean(embs, axis=0)
    c = c / (np.linalg.norm(c) + 1e-9)
    prof["centroid"] = c.tolist()
    prof["n"] = len(embs)
    prof["updated_at"] = stamp()

def find(book, person):
    for p in book["profiles"]:
        if p["person"] == person:
            return p
    return None

def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def attach(book, person, sid):
    prof = find(book, person)
    if not prof:
        prof = {"person": person, "centroid": [], "n": 0, "sample_ids": [], "updated_at": stamp()}
        book["profiles"].append(prof)
    if sid not in prof["sample_ids"]:
        prof["sample_ids"].append(sid)
    recompute_centroid(book, person)

def best_match(book, emb):
    best, score = None, -1.0
    for p in book["profiles"]:
        if not p.get("centroid"):
            continue
        s = float(np.dot(emb, np.asarray(p["centroid"], dtype=np.float32)))
        if s > score:
            best, score = p["person"], s
    return best, score

# ── operations ────────────────────────────────────────────────────────────────
def op_enroll(person, wav, source="manual"):
    e = embed(wav)
    sid = sid_for(wav)
    wavname = store_wav(sid, wav)
    write_sample({"id": sid, "embedding": e.tolist(), "person": person,
                  "source": source, "ts": stamp(), "wav": wavname})
    book = load()
    attach(book, person, sid)
    save(book)
    prof = find(book, person)
    print(f"[enroll] {person} <- sample {sid}  (now n={prof['n']})")

def op_observe(wav, source="room", thr=AUTO_ASSIGN):
    e = embed(wav)
    sid = sid_for(wav)
    book = load()
    person, score = best_match(book, e)
    matched = person is not None and score >= thr
    assigned = person if matched else None
    wavname = store_wav(sid, wav)
    write_sample({"id": sid, "embedding": e.tolist(), "person": assigned,
                  "source": source, "ts": stamp(), "wav": wavname, "match_score": round(score, 4)})
    if matched:
        attach(book, assigned, sid)   # fold into the known person — continuous improvement
        save(book)
    else:
        save(book)  # persist the pooled sample even if no profile changed
    print(json.dumps({"id": sid, "person": assigned, "score": round(score, 4),
                      "matched": matched, "nearest": person}))

def op_assign(sid, person):
    rec = read_sample(sid)
    if not rec:
        print(f"[assign] no sample {sid}", file=sys.stderr); sys.exit(1)
    rec["person"] = person
    write_sample(rec)
    book = load()
    attach(book, person, sid)
    save(book)
    prof = find(book, person)
    print(f"[assign] {sid} -> {person}  (now n={prof['n']})")

def op_rename(old, new):
    book = load()
    prof = find(book, old)
    if not prof:
        print(f"[rename] no profile {old}", file=sys.stderr); sys.exit(1)
    prof["person"] = new
    for sid in prof["sample_ids"]:
        rec = read_sample(sid)
        if rec:
            rec["person"] = new; write_sample(rec)
    save(book)
    print(f"[rename] {old} -> {new}")

def op_list():
    book = load()
    if not book["profiles"]:
        print("(no profiles yet)"); return
    for p in sorted(book["profiles"], key=lambda x: -x["n"]):
        print(f"  {p['person']:20} n={p['n']:<4} updated {p['updated_at']}")

def op_unassigned():
    out = []
    if os.path.isdir(SAMPLES):
        for f in sorted(os.listdir(SAMPLES)):
            if not f.endswith(".json"):
                continue
            rec = json.load(open(os.path.join(SAMPLES, f)))
            if rec.get("person") is None:
                out.append({"id": rec["id"], "wav": os.path.join(SAMPLES, rec.get("wav", rec["id"] + ".wav")),
                            "source": rec.get("source"), "ts": rec.get("ts"),
                            "nearest_score": rec.get("match_score")})
    print(json.dumps(out, indent=1))

def parity(book):
    # leave-one-out over all assigned samples: does each land nearest its own person when
    # its own sample is held out? the honest native success rate. Needs >=2 people, >=2 each.
    samples = []
    for p in book["profiles"]:
        for sid in p["sample_ids"]:
            rec = read_sample(sid)
            if rec and rec.get("embedding"):
                samples.append((p["person"], np.asarray(rec["embedding"], dtype=np.float32), sid))
    people = set(s[0] for s in samples)
    if len(people) < 2 or len(samples) < 4:
        return None
    correct = total = 0
    for person, emb, sid in samples:
        cents = {}
        for q in book["profiles"]:
            embs = [np.asarray(read_sample(s)["embedding"], dtype=np.float32)
                    for s in q["sample_ids"] if s != sid and read_sample(s)]
            if embs:
                c = np.mean(embs, axis=0); cents[q["person"]] = c / (np.linalg.norm(c) + 1e-9)
        if person not in cents:
            continue
        pred = max(cents, key=lambda k: float(np.dot(emb, cents[k])))
        total += 1; correct += int(pred == person)
    return round(correct / total, 2) if total else None

def op_board():
    book = load()
    people = [p["person"] for p in sorted(book["profiles"], key=lambda x: -x["n"])]
    n_samples = sum(p["n"] for p in book["profiles"])
    par = parity(book)
    unassigned_n = len([1 for f in (os.listdir(SAMPLES) if os.path.isdir(SAMPLES) else [])
                        if f.endswith(".json") and json.load(open(os.path.join(SAMPLES, f))).get("person") is None])
    state = "learning" if book["profiles"] else "ready"
    if unassigned_n:
        state = f"learning — {unassigned_n} to assign"
    par_s = str(par) if par is not None else "-"
    stream = ",".join(people[:5])
    # name|samples/target|parity|state|stream-csv
    print(f"speaker|{n_samples}/{TARGET}|{par_s}|{state}|{stream}")

def op_json():
    book = load()
    slim = [{"person": p["person"], "n": p["n"], "updated_at": p["updated_at"]} for p in book["profiles"]]
    print(json.dumps({"profiles": slim, "people": [p["person"] for p in book["profiles"]]}, indent=1))

SPOOL = os.path.join(STORE, "spool")

def observe_wav(wav, source, thr):
    """embed + match + fold, no printing — the watch drain path. Returns (person|None, score)."""
    try:
        e = embed(wav)
    except Exception:
        return (None, -1.0)
    sid = sid_for(wav)
    book = load()
    person, score = best_match(book, e)
    matched = person is not None and score >= thr
    assigned = person if matched else None
    wavname = store_wav(sid, wav)
    write_sample({"id": sid, "embedding": e.tolist(), "person": assigned, "source": source,
                  "ts": stamp(), "wav": wavname, "match_score": round(score, 4)})
    if matched:
        attach(book, assigned, sid)
    save(book)
    return (assigned, score)

def op_watch(thr=AUTO_ASSIGN):
    """Long-lived observer: load the encoder ONCE, drain the spool forever. The speech organ
    drops voiced windows into SPOOL; each is embedded, matched to a known person (folded in —
    the profile sharpens) or pooled for manual assignment. This is the continuous training."""
    os.makedirs(SPOOL, exist_ok=True)
    encoder()  # warm the model once
    print(f"[speaker-watch] draining {SPOOL} (auto-assign>={thr})", flush=True)
    idle = 0
    while True:
        wavs = sorted(f for f in os.listdir(SPOOL) if f.endswith(".wav"))
        if not wavs:
            idle += 1
            time.sleep(5)
            continue
        idle = 0
        for f in wavs:
            p = os.path.join(SPOOL, f)
            if os.path.getsize(p) < 4000:   # too short to be a real utterance
                os.remove(p); continue
            person, score = observe_wav(p, "room", thr)
            tag = person if person else f"pool({score:.2f})"
            print(f"[speaker-watch] {f} -> {tag}", flush=True)
            os.remove(p)
        # a compact status the board/mesh can read
        book = load()
        json.dump({"people": [x["person"] for x in book["profiles"]],
                   "n_samples": sum(x["n"] for x in book["profiles"]),
                   "ts": stamp()}, open(os.path.join(STORE, "watch-status.json"), "w"))

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    a = sys.argv[2:]
    def opt(flag, default=None):
        return a[a.index(flag) + 1] if flag in a else default
    if cmd == "enroll":   op_enroll(a[0], a[1], opt("--source", "manual"))
    elif cmd == "observe": op_observe(a[0], opt("--source", "room"), float(opt("--thr", AUTO_ASSIGN)))
    elif cmd == "assign":  op_assign(a[0], a[1])
    elif cmd == "rename":  op_rename(a[0], a[1])
    elif cmd == "list":    op_list()
    elif cmd == "unassigned": op_unassigned()
    elif cmd == "board":   op_board()
    elif cmd == "json":    op_json()
    elif cmd == "watch":   op_watch(float(opt("--thr", AUTO_ASSIGN)))
    else:
        print(f"unknown command {cmd}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
