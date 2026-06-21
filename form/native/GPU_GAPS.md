# Form-native GPU / ML enablement — gap registry

Living tracker for "any ML layer / diffusion / transformer / attention fully enabled on Mac, Android, RTX."
Status: ✅ done+proven · 🟡 in progress · ⬜ not started · ⛔ blocked.
Backends: **Metal** (Mac **+ iPhone/iOS** — same Apple-GPU MSL) · **PTX** (RTX/NVIDIA, driver JIT) · **Vulkan** (Android+desktop, SPIR-V).
iPhone note: iOS GPU = Metal, identical MSL to Apple-Silicon Mac — the `jte-*-msl` lane IS the iPhone path. iPhone-specific gap = an iOS host app (Metal.framework/MetalKit, code-signed) vs the macOS swiftc CLI runner, + an `ios-arm64` row in hati-os-targets.fk, + on-device run (needs Mac+Xcode+iPhone). MoltenVK would also let the Vulkan lane run on iOS.
"Proven" = bit-exact (or named-epsilon) on real hardware vs the CPU recipe oracle.

## A. Layer carriers (the math exists as portable Form recipes; this tracks the GPU CARRIERS)

| Layer | Recipe (CPU) | Metal | PTX (RTX) | Vulkan (Android) |
|---|---|---|---|---|
| matvec / matmul | ✅ | ✅ f32/f16/bf16 | ✅ f32/f16/bf16 | ✅ f32 **bit-exact, Form-emitted, Android-portable** |
| affine SGD train | ✅ | ✅ | ✅ f32 | ✅ f32 *(GLSL)* |
| gelu (Taylor) | ✅ | ✅ (in FFN) | ✅ f32 *(verdict 127)* | ✅ f32 *(GLSL, RoundingModeRTE)* |
| exp / softmax | ✅ | ✅ (in attn) | ✅ f32 *(verdict 511, Taylor exp)* | ✅ f32 *(GLSL, RoundingModeRTE)* |
| FFN/MLP fwd | ✅ | ✅ | ✅ f32 *(verdict 255, bar.sync)* | ✅ f32 *(GLSL, barrier()+scratch)* |
| FFN/MLP backprop | ✅ | ✅ | ✅ f32 **5-phase SGD step** (fwd-cache→gy→dh1 via gelu'→W2/W1 update), bit-exact 268/268 | ✅ f32 *(GLSL, barrier; 15648/15648 hid=300)* |
| attention (single-head SDPA) | ✅ | ✅ | ✅ f32 *(verdict 1023, fused dot·scale→softmax→·V)* | ✅ f32 *(GLSL, RoundingModeRTE)* |
| attention (MHA/causal/KV) | ✅ | 🟡 (single-head; MHA next) | ✅ f32 **causal multi-head** (per-head slice, masked [0..i]); KV-cache next | ✅ f32 *(GLSL, causal multi-head)* |
| layernorm / rmsnorm | ✅ | ✅ (in block) | ✅ f32 *(verdict 8191, Newton-50 sqrt)* | ✅ layernorm f32 *(GLSL)* |
| residual (vec-add) | ✅ | ✅ (in block) | ✅ f32 *(verdict 8191)* | ✅ f32 *(GLSL)* |
| transformer block fwd | ✅ | ✅ block fwd | ✅ **EXACT tb-block** (QKVO+γβ) + model→logits + autoregressive generation, bit-exact (19-launch graph) | ✅ **multi-dispatch graph** (19 dispatches, 16 barriers, bit-exact) |
| llama block (fwd/causal/decode) | ✅ | ✅ **FULL block** (RMSNorm→RoPE'd QKV→causal attn→res→RMSNorm→SwiGLU FFN→res), bit-exact, 42-launch graph | ⬜ |
| conv2d / groupnorm (diffusion) | ✅ recipe *(verdict 15, 3-way)* | ⬜ | ✅ conv2d f32 **bit-exact to cv2d-conv** (multi-ch, pad/stride, nested ky↓kx↓ic↓) | ✅ conv2d f32 *(GLSL)* |

## B. Precision coverage
- ⬜ f16/bf16 across the **block-level** PTX+Metal kernels (only matvec has all three on PTX/Metal).
- ⬜ affine-train + FFN + attention in f16/bf16 (PTX).
- ⬜ generic fp8 / fp4 (only GGUF Q4_K/Q6_K + int8/NF4 exist as dequant).

## C. Cross-cutting runtime (needed to go from "a kernel" to "a model")
- 🟡 **Kernel-graph / scheduler**: DEMONSTRATED — `form_cuda_ptx_block_host.c` chains 12 launches through resident intermediate device buffers (a full block). Generalize to many layers + persistent weights/KV-cache next.
- ⬜ **Weight load → device**: GGUF dequant recipes exist; loading + keeping resident on GPU not wired.
- ⬜ **Parallel reductions** (perf path): current GPU reductions are serial (bit-exact, O(n)); block/warp reductions need the named-epsilon gate.
- ⬜ **Memory model**: workspace/scratch pooling, KV-cache device buffers.

## D. Algorithm layer (Form recipes, CPU-provable — smaller, mostly diffusion + serving)
- ✅ **conv2d + GroupNorm** (diffusion prerequisite) — `conv2d.fk` + `tests/conv2d-band.fk`, **verdict 15 three-way** (CPU recipe; GPU carriers next).
- 🟡 UNet (diffusion): `unet.fk` (upsample2x, downsample2x, resblock) + band **verdict 127 three-way**. VAE/full-UNet still ⬜.
- ⬜ Flash-attention (current attention materializes O(n²) scores).
- ✅ Sampling: temperature / softmax / top-k / top-p — `sampling.fk` + band **verdict 2047 three-way** (in-recipe sort; beam still ⬜).
- ✅ Loss: MAE, **natural-log** (atanh series, 1e-9 vs libm), softmax **cross-entropy** — `loss.fk` + band **verdict 63 three-way**. Batch training still ⬜.
- ⬜ GroupNorm / BatchNorm; rsqrt as an explicit recipe.

## E. Backend infra
- ✅ **PTX (RTX)**: `form-ptx.fk` lane, driver-JIT -O0, gcc driver-only hosts. Four-way (verdict 127).
- ✅ **Vulkan (Android+desktop)**: matvec **bit-exact on RTX Vulkan ICD** (`native/vulkan/matvec_vk.c`, driver-only `dlopen(vulkan-1.dll)`); Form-emitted (`form-glsl.fk` → glslang `.spv`, **verdict 7 three-way**); `precise`→NoContraction keeps it unfused (do NOT run spirv-opt). Same `.spv` runs on Adreno/Mali (NDK arm64 + `libvulkan.so`; risks: FMA re-fusion, RelaxedPrecision, subnormal FTZ — all controlled). **arm64-android build PROVEN**: the exact carrier cross-compiles with NDK r27c → `matvec_vk_android` = `ELF aarch64, /system/bin/linker64, Android 24`, NEEDED libdl/libc (bionic), references `libvulkan.so` (not vulkan-1.dll). **Remaining gap: on-device RUN** — needs an actual Android device/emulator (none on this host; if connected via adb: install platform-tools, push `matvec_vk_android`+`.spv` to /data/local/tmp, run). Vulkan kernels now (6): matvec, residual, layernorm, gelu, softmax, FFN (`*.comp` + `kernel_vk.c`/`kernel_vk2.c` carriers). FFN proves the hard path — single workgroup/token, `barrier()` (=PTX `bar.sync`) + global scratch, bit-exact incl. multi-iteration strided threads. **KEY:** NVIDIA Vulkan `OpFDiv` ≠ PTX `div.rn.f32` (off 1 ULP) — kernels that divide need `RoundingModeRTE 32` via `SPV_KHR_float_controls` (`GL_EXT_spirv_intrinsics`, SPIR-V 1.3 / vulkan1.1; core in VK1.1, advertised Adreno/Mali). residual/matvec don't divide so don't need it. Next: attention + affine-train shaders; Form-emit all via form-glsl.fk (like matvec) for the four-way wrap.
- ✅ **Metal (Mac)**: most complete (matvec, affine, mlp, attn, block, llama) — but Mac-only proof (off-Mac the audits SKIP).
- ⬜ **gcc-clean fkwu** on Windows (emitter emits socket shims before def → gcc rejects; clang-built today). Upstream `hati-os-kernel-emit.fk` fix.
- ⬜ `hati-os-targets.fk` rows for `windows-x64-cuda` and `android-vulkan` (each needs the targets-band extension: count + verdict bit + artifact row).

## Active lanes (who's on what)
- **RTX climb**: ✅ 13 kernels (form-ptx 8191 + form-ptx-block 3, four-way) + **EXACT tb-block** (QKVO proj + gamma/beta) + **model forward → logits** + **autoregressive generation**, all bit-exact end-to-end. NEXT: MHA/causal/KV on GPU; FFN backprop; llama block; f16/bf16 on the block-level kernels.
- **Android/Vulkan**: ✅ matvec proven (RTX Vulkan) + Form-emitted + arm64-android cross-compiled. NEXT: on-device run (needs device); f16/bf16 GLSL; FFN/attention compute shaders.
- **Diffusion**: ✅ conv2d/groupnorm recipe. NEXT: GPU carriers (PTX/MSL/GLSL) for conv2d.
- **Serving/Training**: ✅ sampling (top-k/p, temperature). NEXT: loss functions (cross-entropy + log) — agent.

## Proven milestones (RTX/PTX lane)
- **11 kernels** bit-exact on RTX 4070, driver-only, `form-ptx` band **verdict 8191 PASS-4WAY**: matvec f32/f16/bf16, affine-train, gelu(Taylor), FFN, softmax, attention, layernorm, rmsnorm, residual.
- **Full transformer block** end-to-end on GPU, bit-exact (`form_cuda_ptx_block_host.c`, 12-launch kernel-graph).
- **Tiny transformer FORWARD → logits** end-to-end on GPU, bit-exact (`form_cuda_ptx_model_host.c`: embed → N×block → final-ln → logits; 3 layers/144, 4 layers/576).
- **AUTOREGRESSIVE GENERATION** on GPU, bit-exact (`form_cuda_ptx_generate_host.c`: greedy loop, growing seq; prompt [1,2,3] → `13 21 16 12 12 9 13 20`, token-id seq matches CPU oracle, final logits bit-exact). A form-native transformer GENERATES.
- **EXACT tb-block** end-to-end on GPU, bit-exact (`form_cuda_ptx_exact_block_host.c`, 19-launch graph): ln-seq(gamma/beta) → Q/K/V/O projections → attention → +residual → ln-seq → FFN → +residual. Closes the "simplified block" caveat. 13 kernels total (proj + gamma/beta = `form-ptx-block` band verdict 3).
- Ideas: `04d35058-...` (lane), `0702a906-...` (carrier).
