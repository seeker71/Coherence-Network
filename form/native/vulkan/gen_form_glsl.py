import sys

# usage: gen_form_glsl.py <out.fk> <band.fk> <matvec.comp>
out_fk, out_band, comp = sys.argv[1], sys.argv[2], sys.argv[3]
glsl = open(comp, newline="").read().replace("\r\n", "\n")
# parameterize the workgroup size (the only "64" in the shader) like the PTX name param
tok = "64"
i = glsl.index(tok)
pre, post = glsl[:i], glsl[i + len(tok):]


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


header = (
    "; form-glsl.fk - emit the GLSL compute shader for the Vulkan/Android lane DIRECTLY from Form\n"
    "; (the Android twin of form-ptx.fk / jit-tensor-emit MSL). glslangValidator MINTS the .spv\n"
    "; (authoring, like nvrtc->cubin); the Vulkan driver loads SPIR-V + dispatches (runtime, driver-\n"
    "; only). `precise` -> NoContraction keeps mul+add unfused, so the result is bit-exact to the CPU\n"
    "; right-fold AND to fptx-matvec / jte-matvec-msl. Proven on the RTX's Vulkan ICD by\n"
    "; native/vulkan/matvec_vk.c; the SAME .spv runs on Adreno/Mali. The workgroup size is the only\n"
    "; parameter; the body is the proven native/vulkan/matvec.comp byte-for-byte.\n\n"
    "(defn fglsl-matvec (wg)\n"
    '  (str_concat "%s" (str_concat wg "%s")))\n' % (esc(pre), esc(post))
)
open(out_fk, "w", newline="\n").write(header)

band = (
    "; preludes: form-stdlib/core.fk form-stdlib/form-glsl.fk\n"
    ";\n"
    "; form-glsl-band - the Form->GLSL emitter proven three-way: the emitted matvec compute shader is\n"
    "; byte-identical across kernels (str_eq vs the canonical proven matvec.comp), the workgroup size\n"
    "; parameterizes cleanly, and emission is deterministic. The GLSL mints to SPIR-V that runs bit-\n"
    "; exact on Vulkan (native/vulkan/matvec_vk.c, RTX + Android-portable); this band gates the text.\n"
    ";\n"
    "; Verdict 7 when the emission lands:\n"
    ";   1   the full emitted GLSL at local_size 64 equals the canonical shader\n"
    ";   2   a different workgroup size (32) lands in the same frame (emission is a function)\n"
    ";   4   two emissions of the same size are str_eq (deterministic)\n"
    "(do\n"
    '    (let want "%s")\n' % esc(glsl)
    + '    (let got (fglsl-matvec "64"))\n'
    '    (let other (fglsl-matvec "32"))\n'
    '    (let c0 (if (str_eq got want) 1 0))\n'
    '    (let c1 (if (str_eq other (str_concat "%s" (str_concat "32" "%s"))) 2 0))\n' % (esc(pre), esc(post))
    + '    (let c2 (if (str_eq (fglsl-matvec "64") got) 4 0))\n'
    "    (add c0 (add c1 c2)))\n"
)
open(out_band, "w", newline="\n").write(band)
print("wrote", out_fk, "and", out_band)
