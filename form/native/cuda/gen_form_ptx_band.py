import sys

# usage: ... <mv> <train> <mv_f16> <mv_bf16> <gelu> <ffn> <softmax> <attn> <ln> <rms> <res>
out, mv_tpl, tr_tpl, f16_tpl, bf16_tpl, gelu_tpl, ffn_tpl, sm_tpl, attn_tpl, ln_tpl, rms_tpl, res_tpl = sys.argv[1:13]


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def want(tpl):
    return esc(open(tpl, newline="").read().replace("\r\n", "\n"))


def split(tpl, entry):
    ptx = open(tpl, newline="").read().replace("\r\n", "\n")
    i = ptx.index(entry)
    return esc(ptx[:i]), esc(ptx[i + len(entry):])


mv_pre, mv_post = split(mv_tpl, "form_matvec_f32")

body = (
    "; preludes: form-stdlib/core.fk form-stdlib/form-ptx.fk\n"
    ";\n"
    "; form-ptx-band - the Form->PTX emitter proven three-way: every emitted PTX kernel (matvec f32,\n"
    "; affine-train SGD f32, matvec f16, matvec bf16) is byte-identical across kernels (str_eq vs the\n"
    "; canonical proven templates), the function name parameterizes cleanly, and emission is\n"
    "; deterministic. Each is bit-exact on the GPU via the driver JIT at -O0 (native/cuda/form_cuda_*ptx*\n"
    "; hosts); this band gates the EMITTER text itself.\n"
    ";\n"
    "; Verdict 8191 when the emission lands:\n"
    ";   1   emitted PTX for form_matvec_f32 equals the canonical template\n"
    ";   2   a different name (mv2) lands in the same frame (emission is a function, not a constant)\n"
    ";   4   two emissions of the same name are str_eq (deterministic)\n"
    ";   8   emitted affine-train SGD PTX for form_affine_train_f32 equals the canonical template\n"
    ";  16   emitted matvec f16 PTX (fp32 accumulate, cvt.rn.f16.f32 store) equals the canonical template\n"
    ";  32   emitted matvec bf16 PTX (fp32 accumulate, cvt.rn.bf16.f32 store) equals the canonical template\n"
    ";  64   emitted gelu PTX (recipe Taylor fexp/ftanh, NOT ex2.approx) equals the canonical template\n"
    ";  128  emitted FFN-forward PTX (matvec + inlined gelu + matvec, bar.sync) equals the canonical template\n"
    ";  256  emitted softmax PTX (Taylor exp, forward sum, recip-multiply) equals the canonical template\n"
    ";  512  emitted attention PTX (dot.scale scores, softmax, forward weighted-sum) equals the canonical template\n"
    ";  1024 emitted layernorm PTX (mean/var, Newton-50 sqrt, normalize) equals the canonical template\n"
    ";  2048 emitted rmsnorm PTX (sumsq, Newton-50 sqrt, scale*gain) equals the canonical template\n"
    ";  4096 emitted residual PTX (vec-add) equals the canonical template\n"
    "(do\n"
    '    (let want "%s")\n' % want(mv_tpl)
    + '    (let got (fptx-matvec "form_matvec_f32"))\n'
    '    (let other (fptx-matvec "mv2"))\n'
    '    (let c0 (if (str_eq got want) 1 0))\n'
    '    (let c1 (if (str_eq other (str_concat "%s" (str_concat "mv2" "%s"))) 2 0))\n' % (mv_pre, mv_post)
    + '    (let c2 (if (str_eq (fptx-matvec "form_matvec_f32") got) 4 0))\n'
    '    (let c3 (if (str_eq (fptx-affine-train "form_affine_train_f32") "%s") 8 0))\n' % want(tr_tpl)
    + '    (let c4 (if (str_eq (fptx-matvec-f16 "form_matvec_f16") "%s") 16 0))\n' % want(f16_tpl)
    + '    (let c5 (if (str_eq (fptx-matvec-bf16 "form_matvec_bf16") "%s") 32 0))\n' % want(bf16_tpl)
    + '    (let c6 (if (str_eq (fptx-gelu "form_gelu_f32") "%s") 64 0))\n' % want(gelu_tpl)
    + '    (let c7 (if (str_eq (fptx-ffn-fwd "form_ffn_fwd_f32") "%s") 128 0))\n' % want(ffn_tpl)
    + '    (let c8 (if (str_eq (fptx-softmax "form_softmax_f32") "%s") 256 0))\n' % want(sm_tpl)
    + '    (let c9 (if (str_eq (fptx-attention "form_attention_f32") "%s") 512 0))\n' % want(attn_tpl)
    + '    (let c10 (if (str_eq (fptx-layernorm "form_layernorm_f32") "%s") 1024 0))\n' % want(ln_tpl)
    + '    (let c11 (if (str_eq (fptx-rmsnorm "form_rmsnorm_f32") "%s") 2048 0))\n' % want(rms_tpl)
    + '    (let c12 (if (str_eq (fptx-residual "form_residual_f32") "%s") 4096 0))\n' % want(res_tpl)
    + "    " + "".join("(add c%d " % i for i in range(12)) + "c12" + (")" * 12) + ")\n"  # 12 adds closed + 1 for (do
)
open(out, "w", newline="\n").write(body)
print("wrote", out, "-", len(body), "bytes")
