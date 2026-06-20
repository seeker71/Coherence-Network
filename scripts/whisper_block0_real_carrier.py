#!/usr/bin/env python3
# scripts/whisper_block0_real_carrier.py — run REAL whisper-tiny encoder block-0 weights,
# REAL 6-head multi-head, through the Form tb-mh-block recipe and check parity vs numpy.
# Honest scope: full d_model=384 is gated on M5's JIT (literal-emit doesn't scale); this
# proves the multi-head block on real (sliced) weights at the largest tractable dim.
import os, sys, json, math, time, subprocess, glob
import numpy as np
from safetensors import safe_open

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DM=int(sys.argv[1]) if len(sys.argv)>1 else 96
NH=6; HD=DM//NH; DFF=DM*4; T=2; EPS=1e-5; SCALE=1.0/math.sqrt(HD)
assert DM%NH==0, "d_model must divide n_head"
path=glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--openai--whisper-tiny/snapshots/*/model.safetensors"))[0]
P="model.encoder.layers.0."
with safe_open(path, framework="numpy") as fh:
    def g(n): return fh.get_tensor(P+n).astype(float)
    g1=g("self_attn_layer_norm.weight")[:DM]; be1=g("self_attn_layer_norm.bias")[:DM]
    Wq=g("self_attn.q_proj.weight")[:DM,:DM]; bq=g("self_attn.q_proj.bias")[:DM]
    Wk=g("self_attn.k_proj.weight")[:DM,:DM]; bk=np.zeros(DM)
    Wv=g("self_attn.v_proj.weight")[:DM,:DM]; bv=g("self_attn.v_proj.bias")[:DM]
    Wo=g("self_attn.out_proj.weight")[:DM,:DM]; bo=g("self_attn.out_proj.bias")[:DM]
    g2=g("final_layer_norm.weight")[:DM]; be2=g("final_layer_norm.bias")[:DM]
    W1=g("fc1.weight")[:DFF,:DM]; b1=g("fc1.bias")[:DFF]
    W2=g("fc2.weight")[:DM,:DFF]; b2=g("fc2.bias")[:DM]
np.random.seed(0); x=(np.random.rand(T,DM)-0.5)
def ln(v,gm,bt):
    m=v.mean(); var=((v-m)**2).mean(); return (v-m)/math.sqrt(var+EPS)*gm+bt
def softmax(s): e=np.exp(s-s.max()); return e/e.sum()
def gelu_tanh(z): return 0.5*z*(1.0+np.tanh(0.7978845608028654*(z+0.044715*z**3)))
def gelu_erf(z): return 0.5*z*(1.0+np.vectorize(math.erf)(z/math.sqrt(2)))
def block(gelu):
    lns=np.array([ln(x[t],g1,be1) for t in range(T)])
    q=lns@Wq.T+bq; k=lns@Wk.T+bk; v=lns@Wv.T+bv
    ctx=np.zeros((T,DM))
    for h in range(NH):
        sl=slice(h*HD,(h+1)*HD)
        for i in range(T):
            a=softmax(np.array([(q[i,sl]@k[j,sl])*SCALE for j in range(T)]))
            ctx[i,sl]=sum(a[j]*v[j,sl] for j in range(T))
    h1=x+(ctx@Wo.T+bo)
    l2=np.array([ln(h1[t],g2,be2) for t in range(T)])
    return h1+(gelu(l2@W1.T+b1)@W2.T+b2)
ref_tanh=block(gelu_tanh); ref_erf=block(gelu_erf)
def f(a):
    a=np.asarray(a)
    return "(list "+" ".join((repr(float(z)) for z in a) if a.ndim==1 else (f(r) for r in a))+")"
STD=f"{ROOT}/form/form-stdlib"
pre="".join(open(f"{STD}/{m}.fk").read() for m in ["trig","transformer-numerics","transformer-block","transformer-mh"])
prog=pre+f"""
(do
 (let x {f(x)}) (let eps {EPS!r}) (let scale {SCALE!r}) (let n {NH}) (let hd {HD})
 (let g1 {f(g1)}) (let be1 {f(be1)}) (let g2 {f(g2)}) (let be2 {f(be2)})
 (let wq {f(Wq)}) (let bq {f(bq)}) (let wk {f(Wk)}) (let bk {f(bk)})
 (let wv {f(Wv)}) (let bv {f(bv)}) (let wo {f(Wo)}) (let bo {f(bo)})
 (let w1 {f(W1)}) (let b1 {f(b1)}) (let w2 {f(W2)}) (let b2 {f(b2)})
 (print (tb-mh-block x eps g1 be1 wq bq wk bk wv bv wo bo n hd scale g2 be2 w1 b1 w2 b2))
 0)
"""
pf=f"/tmp/wb_real_{DM}.fk"; open(pf,"w").write(prog)
sz=os.path.getsize(pf)/1e6
t0=time.time(); o=subprocess.run([f"{ROOT}/form/form-kernel-go/bin-go",pf],capture_output=True,text=True); dt=time.time()-t0
line=[l for l in o.stdout.splitlines() if l.startswith("[")]
if not line: print("KERNEL ERR\n",o.stdout[-600:],o.stderr[-600:]); sys.exit(1)
got=np.array(json.loads(line[0]))
mt=float(np.max(np.abs(got-ref_tanh))); me=float(np.max(np.abs(got-ref_erf)))
print(f"REAL whisper-tiny block-0  d_model={DM}  n_head={NH}  head_dim={HD}  T={T}")
print(f"  program size {sz:.1f} MB   kernel wall {dt:.1f}s")
print(f"  max|Form - numpy(tanh-gelu)| = {mt:.2e}   (the body's gelu — should be ~1e-6)")
print(f"  max|Form - numpy(erf-gelu)|  = {me:.2e}   (whisper's true gelu — residual = the named erf gap)")
print("  VERDICT:", "PASS (multi-head on real weights matches numpy)" if mt<1e-5 else "FAIL")
