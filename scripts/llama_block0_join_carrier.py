#!/usr/bin/env python3
# scripts/llama_block0_join_carrier.py — gap D₄: independent numpy-free reference vs Form
# bj-block-causal-gqa-d4 on REAL loaded Q6_K weights (mini-GGUF fixture, d_model=4).
import ast
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORM = os.path.join(ROOT, "form")
GO = os.path.join(FORM, "form-kernel-go", "bin-go")
DM = int(sys.argv[1]) if len(sys.argv) > 1 else 4
if DM != 4:
    sys.exit("only d=4 slice is implemented; pass 4")

T, N_Q, N_KV, HD = 2, 2, 1, 2
EPS = 1e-5
SCALE = 1.0 / math.sqrt(HD)
CFG = (500000.0, 32.0, 1.0, 4.0, 8192.0)
TAU = 2 * math.pi

x = [[1.0, -0.5, 0.5, 2.0], [-1.0, 0.25, 1.5, -0.75]]
g1 = [0.9, 1.1, 1.0, 0.95]
g2 = [1.05, 0.95, 1.0, 0.9]

EXPORT_PRE = [
    "form-stdlib/core.fk",
    "form-stdlib/format-arith.fk",
    "form-stdlib/f16-decode.fk",
    "form-stdlib/gguf-read.fk",
    "form-stdlib/q6k-dequant.fk",
    "form-stdlib/weight-load.fk",
    "form-stdlib/block-join.fk",
    "form-stdlib/tests/block-join-carrier-export.fk",
]
FWD_PRE = [
    "form-stdlib/core.fk",
    "form-stdlib/format-arith.fk",
    "form-stdlib/f16-decode.fk",
    "form-stdlib/gguf-read.fk",
    "form-stdlib/q6k-dequant.fk",
    "form-stdlib/weight-load.fk",
    "form-stdlib/trig.fk",
    "form-stdlib/transformer-numerics.fk",
    "form-stdlib/llama-numerics.fk",
    "form-stdlib/rope.fk",
    "form-stdlib/transformer-block.fk",
    "form-stdlib/transformer-mh.fk",
    "form-stdlib/gqa-attn.fk",
    "form-stdlib/llama-block.fk",
    "form-stdlib/llama-gqa-block.fk",
    "form-stdlib/block-join.fk",
]


def ensure_go():
    if not os.path.isfile(GO):
        subprocess.check_call(["go", "build", "-o", "bin-go", "."], cwd=os.path.join(FORM, "form-kernel-go"))


def run_go(preludes, extra_fk=None):
    ensure_go()
    args = [GO] + [os.path.join(FORM, p) for p in preludes]
    if extra_fk:
        args.append(extra_fk)
    o = subprocess.run(args, capture_output=True, text=True, cwd=FORM)
    if o.returncode != 0:
        sys.stderr.write(o.stdout[-600:] + o.stderr[-600:])
        sys.exit(1)
    return o.stdout


def dot(a, b):
    return sum(ai * bi for ai, bi in zip(a, b))


def matvec(W, v):
    return [dot(row, v) for row in W]


def vadd(a, b):
    return [ai + bi for ai, bi in zip(a, b)]


def vscale(a, s):
    return [ai * s for ai in a]


def vmaxdiff(a, b):
    return max(abs(ai - bi) for ai, bi in zip(a, b))


def mmaxdiff(A, B):
    return max(vmaxdiff(a, b) for a, b in zip(A, B))


def rope_freq_cfg(hd, HD):
    base, factor, low_f, high_f, orig = CFG
    f = base ** (-hd / HD)
    wavelen = TAU / f
    if wavelen > orig / low_f:
        return f / factor
    if wavelen < orig / high_f:
        return f
    s = (orig / wavelen - low_f) / (high_f - low_f)
    return f * ((1 - s) / factor + s)


def rope_scaled(vec, pos, HD):
    v = list(vec)
    i = 0
    while i < len(v):
        a = pos * rope_freq_cfg(i % HD, HD)
        c, s = math.cos(a), math.sin(a)
        q0, q1 = v[i], v[i + 1]
        v[i] = q0 * c - q1 * s
        v[i + 1] = q0 * s + q1 * c
        i += 2
    return v


def rmsnorm(vec, g, eps):
    ms = sum(v * v for v in vec) / len(vec)
    inv = 1.0 / math.sqrt(ms + eps)
    return [gi * vi * inv for gi, vi in zip(g, vec)]


def silu(z):
    return [zi / (1.0 + math.exp(-zi)) for zi in z]


def softmax(scores):
    m = max(scores)
    e = [math.exp(s - m) for s in scores]
    t = sum(e)
    return [ei / t for ei in e]


def lgqa_block_causal_ref(xs, mats, n_q, n_kv, HD, scale):
    wq, wk, wv, wo, wg, wu, wd = mats
    grp = n_q // n_kv
    n1 = [rmsnorm(xs[t], g1, EPS) for t in range(T)]
    q = [matvec(wq, n1[t]) for t in range(T)]
    k = [matvec(wk, n1[t]) for t in range(T)]
    v = [matvec(wv, n1[t]) for t in range(T)]
    q = [rope_scaled(q[t], t, HD) for t in range(T)]
    k = [rope_scaled(k[t], t, HD) for t in range(T)]
    ctx = []
    for t in range(T):
        parts = []
        for h in range(n_q):
            kvh = h // grp
            q_h = q[t][h * HD : (h + 1) * HD]
            scores = [
                dot(q_h, k[j][kvh * HD : (kvh + 1) * HD]) * scale for j in range(t + 1)
            ]
            sm = softmax(scores)
            out_h = [0.0] * HD
            for j in range(t + 1):
                v_h = v[j][kvh * HD : (kvh + 1) * HD]
                out_h = vadd(out_h, vscale(v_h, sm[j]))
            parts.extend(out_h)
        ctx.append(parts)
    h1 = [vadd(xs[t], matvec(wo, ctx[t])) for t in range(T)]
    out = []
    for t in range(T):
        n2 = rmsnorm(h1[t], g2, EPS)
        gate = matvec(wg, n2)
        up = matvec(wu, n2)
        ffn = matvec(wd, [gi * ui for gi, ui in zip(silu(gate), up)])
        out.append(vadd(h1[t], ffn))
    return out


def flt(a):
    if isinstance(a[0], list):
        return "(list " + " ".join(flt(r) for r in a) + ")"
    return "(list " + " ".join(repr(float(z)) for z in a) + ")"


def parse_form_lists(stdout):
    line = stdout.strip().splitlines()[0]
    py = line.replace("(list", "[").replace(")", "]")
    return ast.literal_eval(py)


def parse_go_validate(stdout):
    for line in stdout.splitlines():
        if "go" in line and "=" in line and ("[[" in line or "[[" in line):
            part = line.split("=", 1)[1].strip()
            if part.startswith("["):
                return ast.literal_eval(part)
    for line in stdout.splitlines():
        if "→" in line:
            part = line.split("→", 1)[1].strip()
            if part.startswith("["):
                return ast.literal_eval(part)
    sys.stderr.write(stdout[-600:])
    sys.exit("parse go validate output failed")


def run_validate_go(preludes, band_path=None):
    cmd = ["./validate.sh"] + preludes
    if band_path:
        cmd.append(band_path)
    o = subprocess.run(cmd, capture_output=True, text=True, cwd=FORM)
    parsed = None
    try:
        parsed = parse_go_validate(o.stdout)
    except (SyntaxError, ValueError):
        pass
    if parsed is None:
        sys.stderr.write(o.stdout[-800:] + o.stderr[-800:])
        sys.exit(1)
    return parsed


mats = run_validate_go(EXPORT_PRE[:-1], EXPORT_PRE[-1])
ref = lgqa_block_causal_ref(x, mats, N_Q, N_KV, HD, SCALE)

fwd = f"""(do
 (let mats {flt(mats)})
 (let x {flt(x)})
 (let g1 {flt(g1)}) (let g2 {flt(g2)}) (let eps {EPS!r})
 (print (bj-block-causal-gqa-d4 mats x g1 eps g2))
 0)
"""
pf = os.path.join(FORM, "form-stdlib", "tests", f"_carrier_fwd_{os.getpid()}.fk")
open(pf, "w").write(fwd)
rel_pf = os.path.relpath(pf, FORM)
t0 = time.time()
got = run_validate_go(FWD_PRE, rel_pf)
dt = time.time() - t0
try:
    os.remove(pf)
except OSError:
    pass

mx = mmaxdiff(got, ref)
print(f"llama block-0 JOIN carrier  d_model={DM}  S={T}  n_q={N_Q}  n_kv={N_KV}  HD={HD}")
print(f"  kernel wall {dt:.2f}s")
print(f"  max|Form - ref| = {mx:.2e}")
print(f"  ref y[0][0] = {ref[0][0]:.6f}  (band pin 1.000297)")
print(f"  got y[0][0] = {got[0][0]:.6f}")
ok = mx == 0.0
print("  VERDICT:", "PASS (join forward matches independent ref on loaded weights)" if ok else "FAIL")
sys.exit(0 if ok else 1)
