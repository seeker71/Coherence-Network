#!/usr/bin/env python3
"""world_featurize.py — the world-store featurizer: makes the vision-training embeddings PERSISTENT.

vision_train.py proved the yardstick (leave-one-out nearest-centroid over Vision feature-prints)
but recomputed every embedding on every run and threw them away. face-training rows already carry
embedding[768]; this module gives world rows the same organ: each samples.jsonl row gains
"embedding": [...768 floats] — the whole-frame VNGenerateImageFeaturePrint via the vision_embed
CLI (the exact mechanism face_profiles.py's pipeline uses, applied to the WHOLE frame, which is
squarely the public API's purpose).

The store is LIVE (earth.hati.vision-distill appends every 90s), so writing follows the family
pattern (face_profiles.py): full read → temp file → atomic os.replace — plus an optimistic check
that the live file did not grow between the final read and the rename (retry if it did).
Embeddings are computed into an append-only staging sidecar first, so the expensive work never
holds the store open; the merge itself is one fast atomic pass.

CLI:
  world_featurize.py embed <frame>        # one frame -> comma-joined 768 floats (mechanism witness)
  world_featurize.py backfill [--limit N] [--workers K]   # compute missing embeddings -> staging
  world_featurize.py merge                # fold staging into samples.jsonl (atomic, live-safe)
  world_featurize.py verify [--limit N]   # honesty checks: coverage, non-constant, scale, distinct
  world_featurize.py parity [--limit N]   # leave-one-out nearest-centroid vs oracle top label,
                                          #   over PERSISTED embeddings (vision_train.py yardstick)
  world_featurize.py board                # one-line status
"""
import json, os, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EMBED = os.path.join(HERE, "vision_embed")
STORE = os.path.expanduser("~/.coherence-network/vision-training")
SAMPLES = os.path.join(STORE, "samples.jsonl")
STAGE = os.path.join(STORE, "embeddings.staging.jsonl")
DIM = 768


def ensure_embed():
    """The compiled featurizer lives next to this script; auto-build from source like
    vision-distill.sh builds its oracle."""
    if os.access(EMBED, os.X_OK):
        return EMBED
    src = EMBED + ".swift"
    if os.path.exists(src):
        r = subprocess.run(["swiftc", "-O", src, "-o", EMBED], capture_output=True)
        if r.returncode == 0:
            return EMBED
    print(f"[world-featurize] no vision_embed binary and could not build from {src}", file=sys.stderr)
    sys.exit(1)


def embed_frame(frame, binary=None):
    """768-d Vision feature-print of the WHOLE frame, or None (missing frame / Vision silent)."""
    try:
        out = subprocess.run([binary or EMBED, frame], capture_output=True, text=True, timeout=30)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        v = [round(float(x), 5) for x in out.stdout.strip().split(",")]
        return v if len(v) == DIM else None
    except Exception:
        return None


def load_rows():
    rows = []
    if os.path.exists(SAMPLES):
        for line in open(SAMPLES):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    rows.append(None)  # keep position; merge re-reads raw lines anyway
    return [r for r in rows if r is not None]


def load_stage():
    staged = {}
    if os.path.exists(STAGE):
        for line in open(STAGE):
            line = line.strip()
            if line:
                try:
                    d = json.loads(line)
                    if len(d.get("embedding") or []) == DIM:
                        staged[d["id"]] = d["embedding"]
                except Exception:
                    pass
    return staged


def top_label(labels):
    if not labels:
        return None
    return max(labels, key=lambda x: x.get("confidence", 0)).get("label")


# ---------------------------------------------------------------- backfill

def op_backfill(limit=None, workers=4):
    binary = ensure_embed()
    rows = load_rows()
    staged = load_stage()
    # unique ids still lacking a persisted or staged embedding, in store order (oldest first)
    todo, seen = [], set()
    for r in rows:
        rid = r.get("id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        if r.get("embedding") or rid in staged:
            continue
        todo.append((rid, r.get("frame")))
    if limit:
        todo = todo[:limit]
    if not todo:
        print("[backfill] nothing to do — all rows embedded or staged")
        return
    print(f"[backfill] {len(todo)} frames to featurize ({workers} workers)")
    from concurrent.futures import ThreadPoolExecutor
    done = missing = 0
    t0 = time.time()
    with open(STAGE, "a") as out:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for rid, v in zip([t[0] for t in todo],
                              ex.map(lambda t: embed_frame(t[1], binary), todo)):
                if v is None:
                    missing += 1
                    continue
                out.write(json.dumps({"id": rid, "embedding": v}) + "\n")
                out.flush()
                done += 1
                if done % 100 == 0:
                    rate = done / (time.time() - t0)
                    print(f"[backfill] {done}/{len(todo)} staged ({rate:.1f}/s)", flush=True)
    print(f"[backfill] staged {done}, frames missing/unreadable {missing}, "
          f"{time.time()-t0:.0f}s — run `merge` to fold into samples.jsonl")


# ---------------------------------------------------------------- merge

def op_merge(max_retries=5):
    staged = load_stage()
    if not staged:
        print("[merge] staging empty — nothing to fold")
        return
    for attempt in range(max_retries):
        before = os.stat(SAMPLES)
        out_lines, merged, had = [], 0, 0
        for line in open(SAMPLES):
            s = line.strip()
            if not s:
                continue
            try:
                r = json.loads(s)
            except Exception:
                out_lines.append(s)          # never drop a line we cannot parse
                continue
            if r.get("embedding"):
                had += 1
                out_lines.append(s)          # already embedded: keep byte-identical
                continue
            emb = staged.get(r.get("id"))
            if emb:
                r["embedding"] = emb
                merged += 1
                out_lines.append(json.dumps(r))
            else:
                out_lines.append(s)
        tmp = SAMPLES + ".tmp"
        with open(tmp, "w") as f:
            f.write("\n".join(out_lines) + "\n")
        after = os.stat(SAMPLES)
        if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
            os.unlink(tmp)                   # the organ appended mid-merge: retry on fresh read
            print(f"[merge] store moved under us (attempt {attempt+1}) — re-reading")
            time.sleep(1.0)
            continue
        os.replace(tmp, SAMPLES)
        print(f"[merge] folded {merged} embeddings into samples.jsonl "
              f"({had} rows already carried one)")
        return
    print("[merge] gave up after retries — store is being written too fast", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- verify

def op_verify(limit=None):
    rows = load_rows()
    n_total = len(rows)
    embedded = [(r["id"], np.asarray(r["embedding"], dtype=np.float32))
                for r in rows if len(r.get("embedding") or []) == DIM]
    if limit:
        embedded = embedded[:limit]
    n = len(embedded)
    print(f"[verify] {n_total} rows in store, {n} carrying embedding[{DIM}]"
          + (f" (checking first {limit})" if limit else ""))
    if n == 0:
        return
    vecs = np.stack([v for _, v in embedded])
    stds = vecs.std(axis=1)
    norms = np.linalg.norm(vecs, axis=1)
    constant = int((stds < 1e-6).sum())
    print(f"[verify] per-vector std  min {stds.min():.4f}  mean {stds.mean():.4f}  "
          f"({constant} constant vectors)")
    print(f"[verify] L2 norm         min {norms.min():.3f}  mean {norms.mean():.3f}  "
          f"max {norms.max():.3f}")
    # distinctness: cosine over a deterministic sample of pairs
    rng = np.random.default_rng(7)
    k = min(n, 200)
    idx = rng.choice(n, size=k, replace=False)
    sub = vecs[idx] / (np.linalg.norm(vecs[idx], axis=1, keepdims=True) + 1e-9)
    cos = sub @ sub.T
    off = cos[~np.eye(k, dtype=bool)]
    dup_ids = len(embedded) - len({i for i, _ in embedded})
    print(f"[verify] pairwise cosine ({k} sampled): min {off.min():.3f}  "
          f"mean {off.mean():.3f}  max {off.max():.3f}")
    print(f"[verify] identical-vector pairs in sample: {int((off > 0.99999).sum() // 2)}  "
          f"(duplicate ids among embedded rows: {dup_ids})")


# ---------------------------------------------------------------- parity (the yardstick)

def op_parity(limit=None):
    rows = load_rows()
    seen, data = set(), []
    for r in rows:
        rid = r.get("id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        lab = top_label(r.get("labels"))
        emb = r.get("embedding")
        if lab is None or len(emb or []) != DIM:
            continue
        v = np.asarray(emb, dtype=np.float32)
        v = v / (np.linalg.norm(v) + 1e-9)
        data.append((rid, lab, v))
        if limit and len(data) >= limit:
            break
    if len(data) < 3:
        print(f"[parity] only {len(data)} embedded+labelled samples — not enough to witness")
        return
    labels = sorted(set(d[1] for d in data))
    vecs = np.stack([d[2] for d in data])
    labs = np.array([labels.index(d[1]) for d in data])
    # leave-one-out nearest-centroid, vectorized: per-class sum minus self
    sums = np.zeros((len(labels), DIM), dtype=np.float32)
    counts = np.zeros(len(labels), dtype=np.int64)
    for li in range(len(labels)):
        mask = labs == li
        sums[li] = vecs[mask].sum(axis=0)
        counts[li] = mask.sum()
    correct = total = novel = 0
    for i in range(len(data)):
        li = labs[i]
        if counts[li] < 2:      # singleton class: native cannot know a class it saw once
            novel += 1
            continue
        cents = sums.copy()
        cents[li] -= vecs[i]
        cnt = counts.copy()
        cnt[li] -= 1
        valid = cnt > 0
        cents = cents[valid] / (np.linalg.norm(cents[valid], axis=1, keepdims=True) + 1e-9)
        pred = int(np.argmax(cents @ vecs[i]))
        pred_label = [l for l, ok in zip(range(len(labels)), valid) if ok][pred]
        total += 1
        correct += int(pred_label == li)
    parity = correct / total if total else 0.0
    per = {l: int((labs == li).sum()) for li, l in enumerate(labels)}
    print(f"[parity] {len(data)} embedded samples · {len(labels)} classes"
          + (f" (first {limit} slice)" if limit else " (full store)"))
    print(f"[parity] leave-one-out nearest-centroid PARITY vs oracle: "
          f"{parity:.2f}  ({correct}/{total}, {novel} singleton-class held out)")
    print(f"[parity] classes: " + ", ".join(f"{l}×{per[l]}" for l in labels))


# ---------------------------------------------------------------- board

def op_board():
    rows = load_rows()
    n = len(rows)
    emb = sum(1 for r in rows if len(r.get("embedding") or []) == DIM)
    staged = len(load_stage())
    pct = (emb * 100 // n) if n else 0
    print(f"world-embedding|{emb}/{n}|{pct}%|staged {staged}|"
          f"{'complete' if emb == n else 'backfilling'}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd, a = sys.argv[1], sys.argv[2:]

    def opt(name, default=None, cast=int):
        return cast(a[a.index(name) + 1]) if name in a else default

    if cmd == "embed":
        binary = ensure_embed()
        v = embed_frame(a[0], binary)
        if v is None:
            print("(vision silent)", file=sys.stderr)
            sys.exit(2)
        print(",".join(f"{x:.5f}" for x in v))
    elif cmd == "backfill":
        op_backfill(limit=opt("--limit"), workers=opt("--workers", 4))
    elif cmd == "merge":
        op_merge()
    elif cmd == "verify":
        op_verify(limit=opt("--limit"))
    elif cmd == "parity":
        op_parity(limit=opt("--limit"))
    elif cmd == "board":
        op_board()
    else:
        print(f"unknown command {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
