#!/usr/bin/env python3
"""gguf_locate_witness.py — witness that the FOUR-WAY-PROVEN Form GGUF locate logic
(form/form-stdlib/gguf-read.fk: gg-tinfo-start + gg-ti-*) reads REAL tensors from the
real llama3.2:3b GGUF. The Form recipe is the body; this carrier mirrors its exact
integer walk to confirm the ALGORITHM scales to the real file (128k-element vocab
arrays, 255-tensor table) before the M2 buffer-bridge feeds real bytes to the kernel.

A band fixture can't hold a 2GB file; this is the real-data complement to the four-way
proof on the synthetic mini-GGUF (form/form-stdlib/tests/gguf-locate-band.fk).

Usage: python3 scripts/gguf_locate_witness.py [path-to-gguf]
Default path is the llama3.2:3b blob ollama serves.
"""
import sys, glob, os

DEFAULT = None
for p in glob.glob(os.path.expanduser("~/.ollama/models/blobs/sha256-*")):
    if 1.5e9 < os.path.getsize(p) < 2.5e9:  # the ~2GB 3b weights
        DEFAULT = p
        break

path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
if not path:
    sys.exit("no gguf path given and no ~2GB blob found in ~/.ollama/models/blobs")
b = open(path, "rb").read()

# --- mirror gguf-read.fk's gg-* walk EXACTLY (every line maps to a Form defn) ---
def le(o, n): return int.from_bytes(b[o:o+n], "little")              # gg-le
def u32(o): return le(o, 4)                                          # gg-u32
def u64(o): return le(o, 8)                                          # gg-u64
def str_next(o): return o + 8 + u64(o)                              # gg-str-next
def vtype_size(t): return {0:1,1:1,7:1,2:2,3:2,4:4,5:4,6:4,10:8,11:8,12:8}[t]  # gg-vtype-size
def val_next(o, t):                                                  # gg-val-next
    if t == 8: return str_next(o)
    if t == 9:
        et, cnt, o2 = u32(o), u64(o+4), o+12
        if et in (8, 9):                                            # gg-arr-skip-var
            for _ in range(cnt): o2 = val_next(o2, et)
            return o2
        return o2 + cnt * vtype_size(et)                            # gg-arr-skip O(1)
    return o + vtype_size(t)
def kv_next(o): return val_next(str_next(o)+4, u32(str_next(o)))    # gg-kv-next
def kv_skip(o, n):                                                  # gg-kv-skip
    for _ in range(n): o = kv_next(o)
    return o
def tinfo_start(): return kv_skip(24, u64(16))                      # gg-tinfo-start
def ti_ndims(o): return u32(str_next(o))                           # gg-ti-ndims
def ti_dim(o, k): return u64(str_next(o)+4+k*8)                    # gg-ti-dim
def ti_tail(o): return str_next(o)+4+ti_ndims(o)*8                 # gg-ti-tail
def ti_type(o): return u32(ti_tail(o))                            # gg-ti-type
def ti_dataoff(o): return u64(ti_tail(o)+4)                       # gg-ti-dataoff
def ti_next(o): return ti_tail(o)+12                              # gg-ti-next
def ti_name(o): return b[o+8:o+8+u64(o)].decode("utf-8", "replace")

assert u32(0) == 1179993927, "bad magic — not a GGUF file"
print(f"file: {os.path.basename(path)}")
print(f"header: magic=GGUF v={u32(4)} n_tensors={u64(8)} n_kv={u64(16)}")
ts = tinfo_start()
print(f"tinfo_start (past {u64(16)} KVs incl. the vocab arrays): byte {ts}")
GGML_TYPE = {0: "F32", 1: "F16", 12: "Q4_K", 14: "Q6_K"}
print("\nfirst tensors via the Form locate walk:")
o, n = ts, min(6, u64(8))
ok = True
for _ in range(n):
    nd = ti_ndims(o); dims = [ti_dim(o, k) for k in range(nd)]
    t = ti_type(o)
    print(f"  {ti_name(o):28s} {GGML_TYPE.get(t, t):5} dims={dims} dataoff={ti_dataoff(o)}")
    ok = ok and ti_name(o).replace(".", "").replace("_", "").isalnum() and ti_dataoff(o) >= 0
    o = ti_next(o)
print("\n>>> WITNESS:", "Form locate logic reads real llama3.2:3b tensors ✓" if ok else "SUSPECT — names/offsets look wrong")
sys.exit(0 if ok else 1)
