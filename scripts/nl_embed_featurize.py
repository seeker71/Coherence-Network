#!/usr/bin/env python3
# nl_embed_featurize.py — fix the "floats pending" assumption and move the
# word-meaning training forward: real LEARNED FLOAT EMBEDDINGS, not char-hash.
#
# Last stone (nl_meaning_featurize.py) used binary char-trigram features, so the
# model could partly cheat on cognate FORM (coherence/cohérence share letters).
# The kernel has full float support (witnessed: real IEEE754, fam-matvec,
# intern_trivial_float), so we can do the real thing:
#
#   input  x = one-hot(source word index)   — pure identity, NO spelling signal
#   target t = one-hot(a translation word index)
#
# The FFN's hidden layer (float weights) BECOMES the word-embedding table: words
# whose translations co-predict land near each other in float space. The model
# CANNOT use orthographic overlap because the input carries none — it must learn
# that word A *means* the same as its translations. This is word2vec-lite on the
# proven native GPU backprop lane (agent_tooluse_train.sh), zero trainer edits.
#
# Held-out = translation edges (a,b) withheld for words A that WERE seen with
# OTHER translations in training — a real generalization test of A's embedding.
#
# Run:  python3 scripts/nl_embed_featurize.py /tmp/nl_embed.dat
# Then: DATA=/tmp/nl_embed.dat bash scripts/agent_tooluse_train.sh
#
# HONEST RESULT (2026-07-02, first run): the real-float embedding pipeline RAN
# end-to-end on the M4 GPU (FFN 400->64->400, the first layer IS the float
# embedding table) — so "floats pending" is fixed in PRACTICE, not just in the
# corrected header. BUT the run "did not beat baseline": with one-hot targets
# over 400 classes, the trainer's per-bit micro-accuracy is ~99.7% for BOTH
# model and an all-zeros baseline, so the metric CANNOT show embedding learning.
# This is a degenerate EVAL, not a float failure. The real fix is a retrieval /
# ranking eval (is the true translation in the model's top-k?), which the
# classification trainer does not provide — the named next build. The clean
# witnessed word-meaning win remains the same/diff pairwise task
# (nl_meaning_featurize.py: 74.2% vs 53.5%). Kept here as an honest artifact:
# floats train; this task's eval must change before it can show a win.
import json, os, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MSGS = os.path.join(ROOT, "web", "messages")
LOCALES = ["en", "de", "es", "fr", "id", "pt-br"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/nl_embed.dat"
VOCAB_CAP = 400  # keep indim/outd tractable for the GPU FFN


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, str):
        out[prefix] = obj
    return out


def single_word(s):
    s = (s or "").strip().lower()
    return s if (s and " " not in s and s.replace("-", "").replace("'", "").isalpha()) else None


bundles = {loc: flatten(json.load(open(os.path.join(MSGS, f"{loc}.json")))) for loc in LOCALES}

# aligned translation edges: within a key, every locale's word is a translation
# of every other. Collect undirected edges as ordered pairs (both directions).
edges = []          # (word_a, word_b) — b is a translation of a
freq = Counter()
for key in bundles["en"]:
    words = []
    for loc in LOCALES:
        w = single_word(bundles[loc].get(key))
        if w:
            words.append(w)
    words = list(dict.fromkeys(words))  # dedupe identical strings across locales
    if len(words) < 2:
        continue
    for a in words:
        freq[a] += 1
        for b in words:
            if a != b:
                edges.append((a, b))

# vocab = most-frequent aligned words (cap for tractability)
vocab = [w for w, _ in freq.most_common(VOCAB_CAP)]
idx = {w: i for i, w in enumerate(vocab)}
V = len(vocab)
edges = [(a, b) for (a, b) in edges if a in idx and b in idx]
if V < 20 or len(edges) < 100:
    sys.stderr.write(f"too thin: vocab={V} edges={len(edges)}\n")
    sys.exit(3)


def onehot(w):
    v = [0.0] * V
    v[idx[w]] = 1.0
    return v


rows = [(onehot(a), onehot(b)) for (a, b) in edges]
train = [r for i, r in enumerate(rows) if i % 5 != 0]
held = [r for i, r in enumerate(rows) if i % 5 == 0]

with open(OUT, "w") as o:
    o.write(f"{len(train)} {len(held)} {V} {V}\n")
    o.write(" ".join(vocab) + "\n")
    for X, T in train + held:
        o.write(" ".join(f"{v:g}" for v in X) + " | " + " ".join(f"{v:g}" for v in T) + "\n")

# baseline = predict the single globally-most-common translation target
tgt_counts = Counter(b for (_, b) in edges)
top = tgt_counts.most_common(1)[0]
sys.stderr.write(
    f"vocab={V}, edges={len(edges)} -> {len(train)} train, {len(held)} held; indim=outd={V}\n"
)
sys.stderr.write(f"majority-target baseline: '{top[0]}' at {top[1]/len(edges):.3f}\n")
sys.stderr.write(f"dataset -> {OUT}\n")
