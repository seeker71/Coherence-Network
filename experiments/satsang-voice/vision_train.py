#!/usr/bin/env python3
"""vision_train.py — the NATIVE student, distilled from the oracle. It learns nothing but a
nearest-centroid over Apple Vision feature embeddings (vision_embed), keyed to the oracle's
top label. Then it measures PARITY the honest way: leave-one-out — every frame is classified
by centroids built from the OTHER frames, so it must name a surface it was never trained on
(learning-witness.fk: invariant, not mimicry). Parity = how often the native agrees with the
oracle on held-out frames. Near 1.0, the oracle is falsework to be struck.

  vision_train.py            # trains + reports parity on ~/.coherence-network/vision-training
"""
import json, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EMBED = os.path.join(HERE, "vision_embed")
STORE = os.path.expanduser("~/.coherence-network/vision-training")
SAMPLES = os.path.join(STORE, "samples.jsonl")

def embed(frame):
    try:
        out = subprocess.run([EMBED, frame], capture_output=True, text=True, timeout=30)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return np.array([float(x) for x in out.stdout.strip().split(",")], dtype=np.float32)
    except Exception:
        return None

def top_label(labels):
    if not labels:
        return None
    return max(labels, key=lambda x: x.get("confidence", 0)).get("label")

# load unique samples
seen, rows = set(), []
for line in open(SAMPLES):
    d = json.loads(line)
    if d["id"] in seen:
        continue
    seen.add(d["id"])
    lab = top_label(d.get("labels"))
    if lab is None:
        continue
    v = embed(d["frame"])
    if v is None:
        continue
    v = v / (np.linalg.norm(v) + 1e-9)
    rows.append((d["id"], lab, v))

if len(rows) < 3:
    print(f"[vision-train] only {len(rows)} usable samples — need diverse camera data to train."); sys.exit(0)

labels = sorted(set(r[1] for r in rows))
per = {l: sum(1 for r in rows if r[1] == l) for l in labels}

# leave-one-out nearest-centroid parity
correct = total = novel = 0
for i, (idi, li, vi) in enumerate(rows):
    cents = {}
    for l in labels:
        vs = [r[2] for j, r in enumerate(rows) if j != i and r[1] == l]
        if vs:
            c = np.mean(vs, axis=0)
            cents[l] = c / (np.linalg.norm(c) + 1e-9)
    if li not in cents:            # its class had only this one sample — native cannot know a class it never saw
        novel += 1
        continue
    pred = max(cents, key=lambda l: float(np.dot(vi, cents[l])))
    total += 1
    correct += int(pred == li)

parity = correct / total if total else 0.0
print(f"[vision-train] {len(rows)} samples · {len(labels)} classes distilled from the oracle")
print(f"[vision-train] leave-one-out PARITY (native agrees with oracle on unseen frames): {parity:.2f}  ({correct}/{total})")
print(f"[vision-train] {novel} singleton-class frames held out (native cannot name a class it has one example of — honest)")
print(f"[vision-train] classes: " + ", ".join(f"{l}×{per[l]}" for l in labels))
print(f"[vision-train] toward parity: at 10k diverse samples this same nearest-centroid distills the oracle; near 1.0 the oracle drops to spot-checks.")
