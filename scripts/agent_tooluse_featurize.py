#!/usr/bin/env python3
# agent_tooluse_featurize.py — CARRIER (data prep only). Turns the real agent corpus
# (~/.coherence-network/form-cli-corpus/corpus.jsonl) into a (features -> tool-set)
# dataset for the Form-native FFN trainer (jte-mlp-train-msl is the model+step; this
# only prepares data). Features = a bag over discriminative keywords + structural bits
# of the task text; labels = multi-hot over the most-used tools. Deterministic split
# (every 5th turn held out). Emits a flat text dataset the Metal harness loads:
#   line 1: n_train n_held indim outd
#   line 2: tool names (outd, space-separated)   — for readable eval
#   then n_train lines "x... | t...", then n_held lines, floats space-separated.
import json, os, re, sys, collections

CORPUS = os.path.expanduser("~/.coherence-network/form-cli-corpus/corpus.jsonl")
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/agent_tooluse.dat"

# discriminative keyword vocabulary (lowercased substring match over the task text)
KEYWORDS = [
    "file","code","fix","bug","function","test","error","class","import","build",
    "deploy","kernel","web","search","read","write","edit","run","commit","branch",
    "pr","merge","grep","find","docs","spec","idea","api","route","band","four-way",
    "fkwu","rust","train","model","data","prove","verify","check","why","how","plan",
    "refactor","add","remove","update","native",
]
# the tools that actually appear with nonzero rate (Grep/Glob are 0 here — the agent uses `bash grep`)
TOOLS = ["Bash","Read","Edit","Write","StructuredOutput","ToolSearch","Agent","WebSearch"]

def tools_of(turn):
    s = set()
    for st in turn.get("steps", []):
        if isinstance(st, dict) and st.get("tool") in TOOLS:
            s.add(st["tool"])
    return s

def features(task):
    t = task.lower()
    f = [1.0 if kw in t else 0.0 for kw in KEYWORDS]
    f += [
        min(len(task) / 400.0, 1.0),          # task length (normalized)
        1.0 if "```" in task else 0.0,         # has code fence
        1.0 if "/" in task else 0.0,           # has a path-ish token
        1.0 if "http" in t else 0.0,           # has a url
        1.0 if "?" in task else 0.0,           # is a question
        1.0,                                   # bias feature
    ]
    return f

rows = []
for l in open(CORPUS):
    try: turn = json.loads(l)
    except: continue
    if not turn.get("steps"): continue
    tl = tools_of(turn)
    if not tl: continue
    rows.append((features(turn["task"]), [1.0 if t in tl else 0.0 for t in TOOLS]))

train = [r for i, r in enumerate(rows) if i % 5 != 0]
held  = [r for i, r in enumerate(rows) if i % 5 == 0]
indim, outd = len(rows[0][0]), len(TOOLS)

with open(OUT, "w") as o:
    o.write(f"{len(train)} {len(held)} {indim} {outd}\n")
    o.write(" ".join(TOOLS) + "\n")
    for X, T in train + held:
        o.write(" ".join(f"{v:g}" for v in X) + " | " + " ".join(f"{v:g}" for v in T) + "\n")

# report the real signal so we can see it's learnable, not trivial
base = [sum(T[i] for _, T in train) / len(train) for i in range(outd)]
sys.stderr.write(f"corpus: {len(rows)} turns -> {len(train)} train, {len(held)} held; indim={indim}, outd={outd}\n")
sys.stderr.write("tool base-rate (train): " + ", ".join(f"{TOOLS[i]} {base[i]:.2f}" for i in range(outd)) + "\n")
sys.stderr.write(f"dataset -> {OUT}\n")
