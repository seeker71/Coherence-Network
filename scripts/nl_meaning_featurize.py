#!/usr/bin/env python3
# nl_meaning_featurize.py — the first native training on WORD MEANING, not tool
# labels. Sibling of agent_tooluse_featurize.py: emits the exact same flat format
# the proven GPU trainer (agent_tooluse_train.sh -> transformer-backprop.fk
# tbp-mlp-step -> jit-tensor-emit.fk jte-mlp-train-msl) reads, so it drops into
# that dimension-generic lane with ZERO trainer edits.
#
# TASK (honest, learnable, corpus-grounded): cross-lingual meaning-match. The
# real parallel corpus web/messages/{en,de,es,fr,id,pt-br}.json aligns UI strings
# by key: for a key, every locale's value MEANS the same thing. So:
#   positive pair = (en_word[K], other_word[K])  -> same meaning   (label 1,0)
#   negative pair = (en_word[K1], other_word[K2]) K1!=K2 -> different (label 0,1)
# x = char-trigram-hash features of word A ++ of word B. The FFN learns to
# recognize when two words across languages carry the same meaning.
#
# HONEST FLOOR: cognates (coherence/cohérence) share form, so a first pass can
# lean partly on orthographic overlap — a REAL signal ("related tongues share
# form for shared meaning") but not deep semantics. Negatives include same-key
# different-locale confusions to push past pure form; true meaning embeddings
# (embedding-as-recipe.fk, float kernel-natives) are the deeper, later stone.
#
# Run:  python3 scripts/nl_meaning_featurize.py /tmp/nl_meaning.dat
# Then: DATA=/tmp/nl_meaning.dat bash scripts/agent_tooluse_train.sh
import json, os, sys, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MSGS = os.path.join(ROOT, "web", "messages")
LOCALES = ["en", "de", "es", "fr", "id", "pt-br"]
OTHERS = [l for l in LOCALES if l != "en"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/nl_meaning.dat"
HASHDIM = 48  # char-trigram hash bins per word


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, str):
        out[prefix] = obj
    return out


def single_word(s):
    s = s.strip()
    return s if (s and " " not in s and s.replace("-", "").replace("'", "").isalpha()) else None


def wfeat(word):
    """Char-trigram hash + length: an orthographic fingerprint, no dictionary."""
    w = "^" + word.lower() + "$"
    v = [0.0] * HASHDIM
    for i in range(len(w) - 2):
        h = int(hashlib.md5(w[i:i + 3].encode()).hexdigest(), 16) % HASHDIM
        v[h] = 1.0
    v.append(min(len(word) / 20.0, 1.0))  # normalized length
    v.append(1.0)                          # bias
    return v


# Load aligned single-word entries per key.
bundles = {}
for loc in LOCALES:
    p = os.path.join(MSGS, f"{loc}.json")
    bundles[loc] = flatten(json.load(open(p)))

en = bundles["en"]
# keys where en AND at least one other locale have an aligned single word
aligned = {}  # key -> {locale: word}
for key, ev in en.items():
    ew = single_word(ev)
    if not ew:
        continue
    row = {"en": ew}
    for loc in OTHERS:
        ov = bundles[loc].get(key)
        ow = single_word(ov) if ov else None
        if ow and ow.lower() != ew.lower():  # skip identical strings (untranslated)
            row[loc] = ow
    if len(row) >= 2:  # en + at least one real translation
        aligned[key] = row

keys = sorted(aligned)
if len(keys) < 20:
    sys.stderr.write(f"only {len(keys)} aligned keys — corpus too thin; aborting\n")
    sys.exit(3)

# Positive pairs: (en, other) same key. Negative: (en[K1], other[K2]) K1!=K2.
rows = []
for i, key in enumerate(keys):
    r = aligned[key]
    for loc in OTHERS:
        if loc not in r:
            continue
        # positive
        rows.append((wfeat(r["en"]) + wfeat(r[loc]), [1.0, 0.0]))
        # negative: same locale word from a different key (deterministic pick)
        nk = keys[(i + 7) % len(keys)]
        if nk != key and loc in aligned[nk]:
            rows.append((wfeat(r["en"]) + wfeat(aligned[nk][loc]), [0.0, 1.0]))

# deterministic 80/20 split
train = [r for i, r in enumerate(rows) if i % 5 != 0]
held = [r for i, r in enumerate(rows) if i % 5 == 0]
indim, outd = len(rows[0][0]), 2
LABELS = ["same", "diff"]

with open(OUT, "w") as o:
    o.write(f"{len(train)} {len(held)} {indim} {outd}\n")
    o.write(" ".join(LABELS) + "\n")
    for X, T in train + held:
        o.write(" ".join(f"{v:g}" for v in X) + " | " + " ".join(f"{v:g}" for v in T) + "\n")

base = [sum(T[i] for _, T in train) / len(train) for i in range(outd)]
sys.stderr.write(
    f"aligned keys: {len(keys)}; pairs: {len(rows)} -> {len(train)} train, {len(held)} held; "
    f"indim={indim}, outd={outd}\n"
)
sys.stderr.write(f"label base-rate (train): same {base[0]:.2f}, diff {base[1]:.2f}\n")
sys.stderr.write(f"dataset -> {OUT}\n")
