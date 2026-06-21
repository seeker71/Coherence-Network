import sys

# usage: gen_form_ptx.py <out.fk> <defn1> <entry1> <template1.ptx> [<defn2> <entry2> <template2.ptx> ...]
out = sys.argv[1]
triples = sys.argv[2:]


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def recipe(defn, entry, tpl):
    ptx = open(tpl, newline="").read().replace("\r\n", "\n")
    i = ptx.index(entry)
    pre, post = ptx[:i], ptx[i + len(entry):]
    return '(defn %s (fname)\n  (str_concat "%s" (str_concat fname "%s")))\n' % (defn, esc(pre), esc(post))


header = (
    "; form-ptx.fk - emit PTX (NVIDIA's documented virtual ISA, text assembly) DIRECTLY from Form,\n"
    "; the GPU twin of form-asm-x64.fk: no nvcc, no nvrtc, no CUDA compiler EVER. The driver's built-in\n"
    "; PTX JIT (part of nvcuda.dll, intrinsic to the GPU) lowers it; loaded at CU_JIT_OPTIMIZATION_LEVEL=0\n"
    "; the explicit mul.f32 + add.f32/sub.f32 stay two roundings, so the GPU result equals the recipe's\n"
    "; CPU right-fold to the last bit (proven by native/cuda/form_cuda_ptx_host.c and\n"
    "; form_cuda_train_ptx_host.c). One thread per output row; the inner loops count DOWN from cols\n"
    "; (tb-dot's downward right-fold), the same order as jte-matvec-cuda / jte-affine-train-cuda. The\n"
    "; function name is the only parameter; each body is the proven native/cuda/template_*.ptx byte-for-byte.\n"
    "; fptx-matvec: y = W.x.   fptx-affine-train: one SGD step of y = W.x + b (forward + loss + in-place update).\n\n"
)
blocks = [recipe(triples[k], triples[k + 1], triples[k + 2]) for k in range(0, len(triples), 3)]
open(out, "w", newline="\n").write(header + "\n".join(blocks))
print("wrote", out, "with", len(blocks), "recipe(s)")
