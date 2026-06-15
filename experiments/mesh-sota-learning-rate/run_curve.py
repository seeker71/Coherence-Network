#!/usr/bin/env python3
"""run_curve.py — ORCHESTRATION carrier. The learning runs in Form, not here.

Reads a fingerprints JSONL (speaker-labelled quantized acoustic vectors), splits
each speaker's utterances into train/heldout, then walks an increasing number of
TRAIN samples N. At each N it hands the N interned prototypes + the full heldout
set to the Form-native classifier (form-stdlib/nearest-shape.fk) running on the Go
kernel, and reads back how many heldout utterances it recognized. ns-sim / ns-label
— the recognition — happen in the kernel; this script only marshals data in and the
count out, and stamps wall-clock. The result is a sample-efficiency learning curve:
accuracy vs #samples-seen and vs wall-clock.

Output JSONL row per curve point:
  {n_train, speakers_seen, heldout, correct, accuracy, kernel_ms, wall_ms, ts_s}
"""
import argparse, json, subprocess, time, sys
from collections import defaultdict, OrderedDict


def load(fp):
    rows = []
    with open(fp) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def split(rows, heldout_frac, label_key):
    """Per-label deterministic split: last `heldout_frac` of each label's rows held out."""
    by = OrderedDict()
    for r in rows:
        by.setdefault(r[label_key], []).append(r)
    train, heldout = [], []
    for lab, rs in by.items():
        k = max(1, int(round(len(rs) * (1 - heldout_frac))))
        if len(rs) == 1:                    # singleton: keep in train, can't eval it
            train.extend(rs)
            continue
        train.extend(rs[:k])
        heldout.extend(rs[k:])
    return train, heldout


def vec_lit(v):
    return "(list " + " ".join(str(int(x)) for x in v) + ")"


def proto_lit(label, v):
    return f'(list "{label}" {vec_lit(v)})'


def build_driver(train_slice, heldout, label_key):
    protos = " ".join(proto_lit(r[label_key], r["vec"]) for r in train_slice)
    queries = " ".join(f'(list "{r[label_key]}" {vec_lit(r["vec"])})' for r in heldout)
    return f"""(do
    (defn cc (qs protos)
        (if (eq (len qs) 0) 0
            (add
                (if (str_eq (ns-label (nth (head qs) 1) protos) (nth (head qs) 0)) 1 0)
                (cc (tail qs) protos))))
    (cc (list {queries}) (list {protos})))
"""


def run_kernel(kernel, nearest_shape, driver_text):
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as f:
        f.write(driver_text)
        path = f.name
    try:
        t0 = time.time()
        p = subprocess.run([kernel, nearest_shape, path],
                           capture_output=True, text=True)
        ms = (time.time() - t0) * 1000.0
        out = (p.stdout or "").strip().splitlines()
        val = None
        for line in reversed(out):
            line = line.strip()
            if line.lstrip("-").isdigit():
                val = int(line)
                break
        if val is None:
            sys.stderr.write(f"[kernel] no integer output. stderr={p.stderr[:300]}\n")
        return val, ms
    finally:
        os.unlink(path)


def points(n, mode):
    if mode == "geometric":
        pts, k = [], 1
        while k < n:
            pts.append(k)
            k *= 2
        pts.append(n)
        return pts
    return list(range(1, n + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fingerprints", required=True)
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--nearest-shape", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="speaker", choices=["speaker", "sex"])
    ap.add_argument("--heldout-frac", type=float, default=0.3)
    ap.add_argument("--mode", default="geometric", choices=["geometric", "all"])
    ap.add_argument("--shuffle-seed", type=int, default=1)
    args = ap.parse_args()

    rows = load(args.fingerprints)
    # deterministic interleave so prototypes arrive speaker-mixed, not block-by-speaker
    import random
    rnd = random.Random(args.shuffle_seed)
    train, heldout = split(rows, args.heldout_frac, args.label)
    rnd.shuffle(train)
    sys.stderr.write(f"train={len(train)} heldout={len(heldout)} "
                     f"labels={len(set(r[args.label] for r in rows))}\n")

    t_start = time.time()
    with open(args.out, "w") as out:
        for n in points(len(train), args.mode):
            sl = train[:n]
            seen = len(set(r[args.label] for r in sl))
            val, kms = run_kernel(args.kernel, args.nearest_shape,
                                  build_driver(sl, heldout, args.label))
            if val is None:
                continue
            acc = val / len(heldout) if heldout else 0.0
            row = {"n_train": n, "speakers_seen": seen, "heldout": len(heldout),
                   "correct": val, "accuracy": round(acc, 4),
                   "kernel_ms": round(kms, 1),
                   "wall_ms": round((time.time() - t_start) * 1000.0, 1)}
            out.write(json.dumps(row) + "\n")
            out.flush()
            sys.stderr.write(f"  N={n:5d} seen={seen:3d} acc={acc:.3f} "
                             f"({val}/{len(heldout)}) kernel={kms:.0f}ms\n")
    sys.stderr.write(f"curve -> {args.out}\n")


if __name__ == "__main__":
    main()
