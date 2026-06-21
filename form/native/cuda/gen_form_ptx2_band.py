import sys

# usage: gen_form_ptx2_band.py <out.fk> <proj.ptx> <gb.ptx>
# A SECOND, small form-ptx band (proj + gamma/beta) — kept separate so no single band file
# outgrows the Rust/TS parser (the monolithic form-ptx-band is ~38KB; see GPU_GAPS notes).
out, proj_tpl, gb_tpl = sys.argv[1], sys.argv[2], sys.argv[3]


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def want(t):
    return esc(open(t, newline="").read().replace("\r\n", "\n"))


body = (
    "; preludes: form-stdlib/core.fk form-stdlib/form-ptx.fk\n"
    ";\n"
    "; form-ptx-block-band - the exact-block emitters proven three-way: the projection (matvec+bias,\n"
    "; tb-affine) and the gamma/beta affine (tb-ln-seq's *gamma+beta) PTX are byte-identical across\n"
    "; kernels. Each is bit-exact on the GPU (native/cuda/form_cuda_ptx_proj_host.c). Split from the\n"
    "; main form-ptx-band so neither band file outgrows the reference-kernel parser.\n"
    ";\n"
    "; Verdict 3 when the emission lands:\n"
    ";   1   emitted projection PTX for form_proj_f32 equals the canonical template\n"
    ";   2   emitted gamma/beta PTX for form_affine_gb_f32 equals the canonical template\n"
    "(do\n"
    '    (let c0 (if (str_eq (fptx-proj "form_proj_f32") "%s") 1 0))\n' % want(proj_tpl)
    + '    (let c1 (if (str_eq (fptx-affine-gb "form_affine_gb_f32") "%s") 2 0))\n' % want(gb_tpl)
    + "    (add c0 c1))\n"
)
open(out, "w", newline="\n").write(body)
print("wrote", out, "-", len(body), "bytes")
