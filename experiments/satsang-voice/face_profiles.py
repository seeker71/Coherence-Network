#!/usr/bin/env python3
"""face_profiles.py — the face book, the seeing twin of speaker_profiles.py. A person is a name
over a centroid of Vision face feature-prints (768-d, detect→crop→featureprint — Apple has no
public face-embedding API, so this is the honest floor). It grows itself: a new face that matches
a known person folds in and sharpens the centroid; a face that matches no one waits in the pool to
be SEEN and named.

It operates on the face-distill store (face-training/samples.jsonl), where each face sample already
carries {id, frame, box, embedding[768], person|null}. This module adds the profile centroids,
auto-match, and assignment on top of that same store — one book for the seeing.

CLI (mirrors speaker_profiles.py):
  face_profiles.py match                # match every unassigned face to a known person; fold ≥ thr
  face_profiles.py assign <id> <person> # name a pooled face; folds in
  face_profiles.py rename <old> <new>
  face_profiles.py list                 # profiles: person n updated
  face_profiles.py unassigned           # pooled faces as JSON (id, frame, box) for the app
  face_profiles.py board                # the training-board line for person/face
  face_profiles.py json                 # full profiles for the app/mesh
"""
import json, os, sys, time
import numpy as np

STORE = os.path.expanduser("~/.coherence-network/face-training")
SAMPLES = os.path.join(STORE, "samples.jsonl")
PROFILES = os.path.join(STORE, "profiles.json")
TARGET = 10000
# Vision feature-prints of face crops are less separable than voiceprints; keep the auto-assign
# bar high so we pool-and-ask rather than mislabel a person. Manual assignment carries the rest.
AUTO_ASSIGN = 0.82

def stamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def load_samples():
    rows = []
    if os.path.exists(SAMPLES):
        for line in open(SAMPLES):
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except Exception: pass
    return rows

def save_samples(rows):
    tmp = SAMPLES + ".tmp"
    with open(tmp, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    os.replace(tmp, SAMPLES)

def load_book():
    if os.path.exists(PROFILES):
        try: return json.load(open(PROFILES))
        except Exception: pass
    return {"version": 1, "profiles": []}

def save_book(book):
    tmp = PROFILES + ".tmp"
    json.dump(book, open(tmp, "w"), indent=1)
    os.replace(tmp, PROFILES)

def vec(r):
    e = r.get("embedding")
    if not e: return None
    v = np.asarray(e, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else None

def find(book, person):
    for p in book["profiles"]:
        if p["person"] == person: return p
    return None

def recompute(book, person, rows):
    prof = find(book, person)
    if not prof: return
    embs = [vec(r) for r in rows if r.get("person") == person and vec(r) is not None]
    if not embs: return
    c = np.mean(embs, axis=0); c = c / (np.linalg.norm(c) + 1e-9)
    prof["centroid"] = c.tolist(); prof["n"] = len(embs); prof["updated_at"] = stamp()

def attach(book, person, rows):
    if not find(book, person):
        book["profiles"].append({"person": person, "centroid": [], "n": 0, "updated_at": stamp()})
    recompute(book, person, rows)

def best_match(book, v):
    best, score = None, -1.0
    for p in book["profiles"]:
        if not p.get("centroid"): continue
        s = float(np.dot(v, np.asarray(p["centroid"], dtype=np.float32)))
        if s > score: best, score = p["person"], s
    return best, score

def op_match(thr=AUTO_ASSIGN):
    rows = load_samples(); book = load_book()
    changed = 0
    for r in rows:
        if r.get("person") is not None: continue
        v = vec(r)
        if v is None: continue
        person, score = best_match(book, v)
        r["match_score"] = round(score, 4)
        if person is not None and score >= thr:
            r["person"] = person; changed += 1
    save_samples(rows)
    for p in book["profiles"]:
        recompute(book, p["person"], rows)
    save_book(book)
    print(f"[face-match] folded {changed} faces into known people")

def op_assign(fid, person):
    rows = load_samples()
    hit = False
    for r in rows:
        if r["id"] == fid:
            r["person"] = person; hit = True
    if not hit:
        print(f"[assign] no face {fid}", file=sys.stderr); sys.exit(1)
    save_samples(rows)
    book = load_book(); attach(book, person, rows); save_book(book)
    print(f"[assign] {fid} -> {person}  (n={find(book, person)['n']})")

def op_unassign(fid):
    rows = load_samples()
    who = None
    for r in rows:
        if r["id"] == fid:
            who = r.get("person"); r["person"] = None
    save_samples(rows)
    book = load_book()
    if who:
        if any(r.get("person") == who for r in rows):
            recompute(book, who, rows)
        else:
            book["profiles"] = [p for p in book["profiles"] if p["person"] != who]
        save_book(book)
    print(f"[unassign] {fid} released from {who or '(none)'}")

def op_release(person):
    rows = load_samples()
    hit = False
    for r in rows:
        if r.get("person") == person:
            r["person"] = None; hit = True
    save_samples(rows)
    book = load_book()
    book["profiles"] = [p for p in book["profiles"] if p["person"] != person]
    save_book(book)
    print(f"[release] {person} -> pool" if hit else f"[release] no profile {person}")

def op_rename(old, new):
    rows = load_samples()
    for r in rows:
        if r.get("person") == old: r["person"] = new
    save_samples(rows)
    book = load_book(); prof = find(book, old)
    if prof: prof["person"] = new
    save_book(book)
    print(f"[rename] {old} -> {new}")

def op_list():
    book = load_book()
    if not book["profiles"]: print("(no face profiles yet)"); return
    for p in sorted(book["profiles"], key=lambda x: -x["n"]):
        print(f"  {p['person']:20} n={p['n']:<4} updated {p['updated_at']}")

def op_unassigned():
    rows = load_samples()
    out = [{"id": r["id"], "frame": r.get("frame"), "box": r.get("box"),
            "nearest_score": r.get("match_score"), "ts": r.get("ts")}
           for r in rows if r.get("person") is None]
    print(json.dumps(out, indent=1))

def parity(rows, book):
    labelled = [(r["person"], vec(r), r["id"]) for r in rows
                if r.get("person") and vec(r) is not None]
    people = set(p for p, _, _ in labelled)
    if len(people) < 2 or len(labelled) < 4: return None
    correct = total = 0
    for person, v, fid in labelled:
        cents = {}
        for q in people:
            embs = [vv for pp, vv, ii in labelled if pp == q and ii != fid]
            if embs:
                c = np.mean(embs, axis=0); cents[q] = c / (np.linalg.norm(c) + 1e-9)
        if person not in cents: continue
        pred = max(cents, key=lambda k: float(np.dot(v, cents[k])))
        total += 1; correct += int(pred == person)
    return round(correct / total, 2) if total else None

def op_board():
    rows = load_samples(); book = load_book()
    n = len(rows)
    people = [p["person"] for p in sorted(book["profiles"], key=lambda x: -x["n"])]
    pooled = sum(1 for r in rows if r.get("person") is None)
    par = parity(rows, book)
    if n == 0:
        state = "ready — awaiting camera frames"
    elif not people:
        state = f"{pooled} faces pooled — assign to people"
    else:
        state = "learning" + (f" — {pooled} to assign" if pooled else "")
    par_s = str(par) if par is not None else "-"
    print(f"person / face|{n}/{TARGET}|{par_s}|{state}|{','.join(people[:5])}")

def op_json():
    book = load_book()
    slim = [{"person": p["person"], "n": p["n"], "updated_at": p["updated_at"]} for p in book["profiles"]]
    print(json.dumps({"profiles": slim, "people": [p["person"] for p in book["profiles"]]}, indent=1))

def main():
    if len(sys.argv) < 2: print(__doc__); sys.exit(1)
    cmd, a = sys.argv[1], sys.argv[2:]
    if cmd == "match": op_match(float(a[a.index("--thr")+1]) if "--thr" in a else AUTO_ASSIGN)
    elif cmd == "assign": op_assign(a[0], a[1])
    elif cmd == "unassign": op_unassign(a[0])
    elif cmd == "release": op_release(a[0])
    elif cmd == "rename": op_rename(a[0], a[1])
    elif cmd == "list": op_list()
    elif cmd == "unassigned": op_unassigned()
    elif cmd == "board": op_board()
    elif cmd == "json": op_json()
    else: print(f"unknown command {cmd}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
