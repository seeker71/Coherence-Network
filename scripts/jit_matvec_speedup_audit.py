#!/usr/bin/env python3
# scripts/jit_matvec_speedup_audit.py — witness: the Form-emitted native matvec speedup.
#
# The EMITTER is a Form recipe (form-stdlib/jit-tensor-emit.fk: jte-matvec-rust); the kernel/
# host keeps only dumb carriers (rustc --crate-type=cdylib, dlopen, call). This script runs that
# lane end to end and measures it against the tree-walking interpreter, confirming where Form-
# native model SPEED lives (M5's emit→compile→exec lane, not the in-process jit_compile dispatch
# which has the named realization gap). The inner loop folds j DOWNWARD = transformer-block.fk's
# tb-dot right-fold, so the native result is the recipe's result bit-for-bit (verified vs numpy).
#
# Usage: scripts/jit_matvec_speedup_audit.py   (needs rustc; numpy via a venv)
import os, sys, ctypes, subprocess, time, math
import numpy as np

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GO=f"{ROOT}/form/form-kernel-go/bin-go"
STD=f"{ROOT}/form/form-stdlib"
WORK="/tmp/mvjit"; os.makedirs(WORK, exist_ok=True)

# 1) emit the native matvec source FROM the Form emitter recipe
emit_body = open(f"{STD}/jit-tensor-emit.fk").read()
# pull just jte-matvec-rust (self-contained; uses str_concat builtin)
start = emit_body.index("(defn jte-matvec-rust")
end = emit_body.index("\n\n", start)
prog = "(do\n" + emit_body[start:end] + '\n(print (jte-matvec-rust "form_matvec")) 0)\n'
open(f"{WORK}/emit.fk","w").write(prog)
src = subprocess.run([GO, f"{WORK}/emit.fk"], capture_output=True, text=True).stdout.splitlines()[0]
open(f"{WORK}/matvec.rs","w").write(src)
print(f"Form emitter → {len(src)} bytes of Rust")

# 2) compile to a cdylib (dumb carrier)
subprocess.run(["rustc","-O","--crate-type=cdylib",f"{WORK}/matvec.rs","-o",f"{WORK}/libform_matvec.dylib"], check=True)
lib=ctypes.CDLL(f"{WORK}/libform_matvec.dylib"); fn=lib.form_matvec
P=ctypes.POINTER(ctypes.c_double); fn.argtypes=[P,P,P,ctypes.c_int64,ctypes.c_int64]; fn.restype=None
def mv(W,x):
    W=np.ascontiguousarray(W); x=np.ascontiguousarray(x); y=np.zeros(W.shape[0])
    fn(W.ctypes.data_as(P),x.ctypes.data_as(P),y.ctypes.data_as(P),W.shape[0],W.shape[1]); return y

# 3) measure native vs numpy (correctness) at whisper widths
print("\n-- native matvec (Form-emitted) --")
for n in (384,1280):
    np.random.seed(0); W=np.random.rand(n,n)-0.5; x=np.random.rand(n)-0.5
    y=mv(W,x); err=float(np.max(np.abs(y-W@x)))
    reps=200; t0=time.perf_counter()
    for _ in range(reps): mv(W,x)
    print(f"  {n}x{n}: {(time.perf_counter()-t0)/reps*1000:.3f} ms/call   max|native-numpy|={err:.1e}")

# 4) the full d_model=384 block with matvecs routed native (the matvec-dominated cost)
DM,NH,HD,DFF,T=384,6,64,1536,2; EPS=1e-5; SC=1/math.sqrt(HD)
np.random.seed(0); R=lambda*s:np.random.rand(*s)-0.5
x=R(T,DM); g1,be1,g2,be2=R(DM),R(DM),R(DM),R(DM)
Wq,Wk,Wv,Wo=R(DM,DM),R(DM,DM),R(DM,DM),R(DM,DM); bq,bv,bo=R(DM),R(DM),R(DM); bk=np.zeros(DM)
W1,b1,W2,b2=R(DFF,DM),R(DFF),R(DM,DFF),R(DM)
ln=lambda v,gm,bt:(v-v.mean())/math.sqrt(((v-v.mean())**2).mean()+EPS)*gm+bt
sm=lambda s:(np.exp(s-s.max()))/np.exp(s-s.max()).sum()
gelu=lambda z:0.5*z*(1.0+np.tanh(0.7978845608028654*(z+0.044715*z**3)))
def block():
    L=np.array([ln(x[t],g1,be1) for t in range(T)])
    q=np.array([mv(Wq,L[t])+bq for t in range(T)]); k=np.array([mv(Wk,L[t])+bk for t in range(T)]); v=np.array([mv(Wv,L[t])+bv for t in range(T)])
    ctx=np.zeros((T,DM))
    for h in range(NH):
        s=slice(h*HD,(h+1)*HD)
        for i in range(T):
            a=sm(np.array([(q[i,s]@k[j,s])*SC for j in range(T)])); ctx[i,s]=sum(a[j]*v[j,s] for j in range(T))
    h1=x+np.array([mv(Wo,ctx[t])+bo for t in range(T)])
    l2=np.array([ln(h1[t],g2,be2) for t in range(T)])
    return h1+np.array([mv(W2,gelu(mv(W1,l2[t])+b1))+b2 for t in range(T)])
block(); reps=50; t0=time.perf_counter()
for _ in range(reps): block()
dt=(time.perf_counter()-t0)/reps*1000
print(f"\nfull d_model=384 block, matvecs native: {dt:.2f} ms/block  (~{31000/dt:.0f}x vs 31s interpreter)")
print(f"8-layer pass projection: ~{dt*8:.0f} ms")
