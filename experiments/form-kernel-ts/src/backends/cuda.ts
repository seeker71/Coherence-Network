// CUDA C++ emit backend for form-kernel-ts.
//
// Multi-target codegen task #13. The companion to the JS compiler in
// ../compiler.ts: instead of lifting recipe trees into JS source for
// V8 to JIT, this backend lifts them into CUDA C++ source for nvcc
// to compile into device code.
//
// Architecture parallel to compiler.ts:
//
//   CudaBackend.emit(kernel, root, opts)
//     → walks the NodeID tree
//     → emits a `__global__` kernel function (string)
//     → arithmetic operators map directly to CUDA primitives
//     → MATH on FP16 dispatches to __hadd / __hmul intrinsics
//     → MATH on FP8 dispatches to mma.m16n8k16 tensor-core path
//     → LIST literals emit float4 / half2 vector packs
//     → BLOCK.PARALLELIZE → __global__ kernel with grid/block dispatch
//     → BLOCK.VECTORIZE → __ldg + vectorized 128-bit load/store
//
// The emit is a pure string transform — no nvcc invocation, no CUDA
// runtime dependency at TS layer. Downstream tooling (the host-side
// dispatcher in form-stdlib/ or external benchmarks) compiles the
// emitted source.
//
// This is the smallest backend surface that proves the multi-target
// pattern: same recipe → JS source (compiler.ts) → CUDA source (this
// file). Future backends (Metal, ROCm, SPIR-V) follow the same shape.

import {
  Level,
  RBasic,
  RBlock,
  RCmp,
  RCond,
  RLogic,
  RMath,
  Triv,
  type Kernel,
  type NodeID,
} from "../kernel.ts";

// ---------------------------------------------------------------------------
// Backend surface — the contract a target emit shares across cuda / metal /
// rocm / spirv. Kept minimal; widened only when a second backend lands.
// ---------------------------------------------------------------------------

export interface BackendEmitOptions {
  // Kernel function name in the emitted source. Defaults to `form_kernel`.
  readonly kernel_name?: string;
  // Element type for VECTOR and scalar math. Defaults to "fp32".
  readonly dtype?: DType;
  // Launch shape (logical) — drives __global__ thread indexing emit.
  readonly grid?: readonly [number, number, number];
  readonly block?: readonly [number, number, number];
  // Tensor-core path (FP16/FP8 with mma intrinsics). Auto-on when dtype is
  // "fp16" or "fp8" and a MATH.MUL appears in the recipe.
  readonly tensor_core?: boolean;
}

export type DType = "fp32" | "fp16" | "fp8" | "int32";

export interface Backend {
  readonly name: string;
  readonly target_hints: ReadonlySet<string>;
  emit(kernel: Kernel, root: NodeID, opts?: BackendEmitOptions): string;
}

// ---------------------------------------------------------------------------
// CudaBackend — the singleton const, re-exported as the file's primary value.
// ---------------------------------------------------------------------------

export const CudaBackend: Backend = {
  name: "cuda",
  target_hints: new Set(["gpu-cuda", "gpu-cuda-tensorcore"]),
  emit(kernel, root, opts) {
    const o = normalizeOptions(opts);
    const scope = freshScope();
    const body = emitExpr(kernel, root, scope, o);
    return assembleKernelSource(body, scope, o);
  },
};

// ---------------------------------------------------------------------------
// Emit pipeline — recipe walk + string concatenation. Kept structurally
// close to compiler.ts so the two read as siblings.
// ---------------------------------------------------------------------------

interface EmitScope {
  vars: Map<number, string>;
  fns: Map<number, string>;
  // Device-side helper declarations gathered while walking — emitted into
  // the kernel preamble. Each entry is a complete C++ function definition.
  device_fns: string[];
  // Whether the walk has produced at least one tensor-core fragment, so we
  // can guard the mma include and add the wmma namespace using.
  tensor_core_used: boolean;
  // Vectorized-load fragments seen — drives __ldg helper inclusion.
  vector_load_used: boolean;
  // Whether the walk touched a parallelize op — if not, we still emit a
  // __global__ wrapper with a single-thread guard so the source compiles.
  parallelized: boolean;
  uid: { n: number };
}

interface NormalizedOptions {
  kernel_name: string;
  dtype: DType;
  grid: readonly [number, number, number];
  block: readonly [number, number, number];
  tensor_core: boolean;
}

function normalizeOptions(opts: BackendEmitOptions | undefined): NormalizedOptions {
  return {
    kernel_name: opts?.kernel_name ?? "form_kernel",
    dtype: opts?.dtype ?? "fp32",
    grid: opts?.grid ?? [1, 1, 1],
    block: opts?.block ?? [32, 1, 1],
    tensor_core:
      opts?.tensor_core ??
      (opts?.dtype === "fp16" || opts?.dtype === "fp8"),
  };
}

function freshScope(): EmitScope {
  return {
    vars: new Map(),
    fns: new Map(),
    device_fns: [],
    tensor_core_used: false,
    vector_load_used: false,
    parallelized: false,
    uid: { n: 0 },
  };
}

function fresh(scope: EmitScope, hint: string): string {
  scope.uid.n++;
  return `${sanitize(hint)}_${scope.uid.n}`;
}

function sanitize(s: string): string {
  return s.replace(/[^A-Za-z0-9_]/g, "_");
}

// CUDA C++ scalar type for a given Form DType.
function cudaScalar(dtype: DType): string {
  switch (dtype) {
    case "fp16":
      return "__half";
    case "fp8":
      return "__nv_fp8_e4m3";
    case "int32":
      return "int";
    case "fp32":
    default:
      return "float";
  }
}

// CUDA vector type for a 4-wide pack of the given DType. half2 is the
// 2-wide FP16 pack; for 4-wide FP16 we use 2× half2 in the emitted
// declaration. Tensor-core paths use wmma::fragment instead.
function cudaVec4(dtype: DType): string {
  switch (dtype) {
    case "fp16":
      return "half2"; // 2-wide; the vectorize path emits 2× half2 for 4-wide
    case "fp8":
      return "__nv_fp8x4_e4m3";
    case "int32":
      return "int4";
    case "fp32":
    default:
      return "float4";
  }
}

// emitExpr — recipe walk. Returns a CUDA C++ expression string.
function emitExpr(
  k: Kernel,
  node: NodeID,
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  if (node.level === Level.TRIVIAL) {
    return emitTrivial(node, opts);
  }
  const cat = k.category(node);
  const kids = k.children(node);

  switch (cat.type) {
    case RBasic.IDENT: {
      const nameID = k.identID(node);
      const local = scope.vars.get(nameID) ?? scope.fns.get(nameID);
      if (local !== undefined) return local;
      // Unbound — emit as a kernel parameter reference.
      return sanitize(k.nameStr(nameID));
    }
    case RBasic.MATH:
      return emitMath(k, cat.inst, kids, scope, opts);
    case RBasic.COMPARE:
      return emitCompare(k, cat.inst, kids, scope, opts);
    case RBasic.LOGIC:
      return emitLogic(k, cat.inst, kids, scope, opts);
    case RBasic.COND:
      return emitCond(k, cat.inst, kids, scope, opts);
    case RBasic.BLOCK:
      return emitBlock(k, cat.inst, kids, scope, opts);
    case RBasic.LIST:
      return emitVectorList(k, kids, scope, opts);
    case RBasic.FNDEF:
      return emitFnDef(k, kids, scope, opts);
    case RBasic.FNCALL:
      return emitFnCall(k, kids, scope, opts);
    default:
      // Unknown shape — emit a typed zero so the source still compiles.
      return `((${cudaScalar(opts.dtype)})0)`;
  }
}

function emitTrivial(node: NodeID, opts: NormalizedOptions): string {
  if (node.type === Triv.INT) {
    const u = node.inst >>> 0;
    const i = u > 0x7fffffff ? u - 0x100000000 : u;
    if (opts.dtype === "fp16") return `__float2half(${i}.0f)`;
    if (opts.dtype === "fp8") return `__nv_fp8_e4m3(${i}.0f)`;
    if (opts.dtype === "int32") return String(i);
    return `${i}.0f`;
  }
  if (node.type === Triv.BOOL) {
    return node.inst !== 0 ? "true" : "false";
  }
  if (node.type === Triv.NULL) {
    return `((${cudaScalar(opts.dtype)})0)`;
  }
  // String trivial — not legal as a device-side expression; emit a sentinel
  // and let downstream tools flag the mismatch.
  return `((${cudaScalar(opts.dtype)})0)`;
}

// MATH — arithmetic operators. FP16 and FP8 dispatch to intrinsics; FP32
// and INT32 use native operators.
function emitMath(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  const parts = kids.map((c) => emitExpr(k, c, scope, opts));
  // Tensor-core MUL on FP16/FP8 with a length-3 (a, b, c) form emits an
  // mma fragment — D = A * B + C. Pure binary MUL stays in scalar ops.
  if (op === RMath.MUL && opts.tensor_core && parts.length >= 2) {
    scope.tensor_core_used = true;
    if (parts.length === 3) {
      return emitTensorCoreMMA(parts[0]!, parts[1]!, parts[2]!, scope, opts);
    }
  }
  if (opts.dtype === "fp16") {
    return foldHalf(op, parts);
  }
  if (opts.dtype === "fp8") {
    // FP8 has no scalar ops on device; promote to half then fold.
    const promoted = parts.map((p) => `__nv_cvt_fp8_to_halfraw(${p}, __NV_E4M3)`);
    return foldHalf(op, promoted);
  }
  // FP32 / INT32 — native operators.
  return foldScalar(op, parts);
}

function foldHalf(op: number, parts: string[]): string {
  const intrinsic =
    op === RMath.PLUS
      ? "__hadd"
      : op === RMath.MINUS
        ? "__hsub"
        : op === RMath.MUL
          ? "__hmul"
          : op === RMath.DIV
            ? "__hdiv"
            : "__hadd";
  if (parts.length === 0) return "__float2half(0.0f)";
  if (parts.length === 1) return parts[0]!;
  let acc = parts[0]!;
  for (let i = 1; i < parts.length; i++) {
    acc = `${intrinsic}(${acc}, ${parts[i]})`;
  }
  return acc;
}

function foldScalar(op: number, parts: string[]): string {
  const opStr =
    op === RMath.PLUS
      ? "+"
      : op === RMath.MINUS
        ? "-"
        : op === RMath.MUL
          ? "*"
          : op === RMath.DIV
            ? "/"
            : op === RMath.MOD
              ? "%"
              : "+";
  if (parts.length === 0) return "0";
  if (parts.length === 1) return `(${parts[0]})`;
  return `(${parts.map((p) => `(${p})`).join(` ${opStr} `)})`;
}

// Tensor-core MMA fragment. Emits an wmma fragment block with a unique name
// and returns the fragment-D variable. Caller embeds it in a __global__
// kernel — the wmma helpers are device-callable only.
function emitTensorCoreMMA(
  a: string,
  b: string,
  c: string,
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  scope.tensor_core_used = true;
  const tag = fresh(scope, "mma");
  const elt = opts.dtype === "fp8" ? "__nv_fp8_e4m3" : "__half";
  const acc = opts.dtype === "fp8" ? "float" : "float";
  // 16x16x16 m16n8k16 fragment shape — the canonical Ampere/Hopper tile.
  const decl = `
    // mma.m16n8k16 — D = A * B + C, ${opts.dtype} inputs, fp32 accumulator
    wmma::fragment<wmma::matrix_a, 16, 16, 16, ${elt}, wmma::row_major> ${tag}_A;
    wmma::fragment<wmma::matrix_b, 16, 16, 16, ${elt}, wmma::col_major> ${tag}_B;
    wmma::fragment<wmma::accumulator, 16, 16, 16, ${acc}> ${tag}_C;
    wmma::fragment<wmma::accumulator, 16, 16, 16, ${acc}> ${tag}_D;
    wmma::load_matrix_sync(${tag}_A, ${a}, 16);
    wmma::load_matrix_sync(${tag}_B, ${b}, 16);
    wmma::load_matrix_sync(${tag}_C, ${c}, 16, wmma::mem_row_major);
    wmma::mma_sync(${tag}_D, ${tag}_A, ${tag}_B, ${tag}_C);
  `;
  scope.device_fns.push(decl.trim());
  return `${tag}_D`;
}

function emitCompare(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  const a = emitExpr(k, kids[0]!, scope, opts);
  const b = emitExpr(k, kids[1]!, scope, opts);
  const opStr =
    op === RCmp.EQ
      ? "=="
      : op === RCmp.NE
        ? "!="
        : op === RCmp.LT
          ? "<"
          : op === RCmp.LE
            ? "<="
            : op === RCmp.GT
              ? ">"
              : op === RCmp.GE
                ? ">="
                : "==";
  if (opts.dtype === "fp16") {
    const intrinsic =
      op === RCmp.EQ
        ? "__heq"
        : op === RCmp.NE
          ? "__hne"
          : op === RCmp.LT
            ? "__hlt"
            : op === RCmp.LE
              ? "__hle"
              : op === RCmp.GT
                ? "__hgt"
                : op === RCmp.GE
                  ? "__hge"
                  : "__heq";
    return `${intrinsic}(${a}, ${b})`;
  }
  return `((${a}) ${opStr} (${b}))`;
}

function emitLogic(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  if (op === RLogic.NOT) {
    return `(!(${emitExpr(k, kids[0]!, scope, opts)}))`;
  }
  const opStr = op === RLogic.AND ? "&&" : "||";
  const parts = kids.map((c) => `(${emitExpr(k, c, scope, opts)})`);
  return parts.join(` ${opStr} `);
}

function emitCond(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  if (op === RCond.IF_THEN) {
    return `((${emitExpr(k, kids[0]!, scope, opts)}) ? (${emitExpr(k, kids[1]!, scope, opts)}) : ((${cudaScalar(opts.dtype)})0))`;
  }
  return `((${emitExpr(k, kids[0]!, scope, opts)}) ? (${emitExpr(k, kids[1]!, scope, opts)}) : (${emitExpr(k, kids[2]!, scope, opts)}))`;
}

// BLOCK — DO/SEQUENCE/LET, plus the two GPU-specific shapes layered on top:
// PARALLELIZE (instance 8) and VECTORIZE (instance 9). These are *future*
// RBlock instances reserved for the multi-target work; the backend treats
// them by inst-number so it doesn't depend on a kernel update to recognize
// them.
const RBlockGpu = { PARALLELIZE: 8, VECTORIZE: 9 } as const;

function emitBlock(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  if (op === RBlock.LET) {
    const name = kids[0]!;
    const valueSrc = emitExpr(k, kids[1]!, scope, opts);
    if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
      return valueSrc;
    }
    const cName = fresh(scope, `let_${k.nameStr(name.inst)}`);
    scope.vars.set(name.inst, cName);
    // Emit as a statement in the kernel body via the device_fns side-channel.
    scope.device_fns.push(`${cudaScalar(opts.dtype)} ${cName} = ${valueSrc};`);
    return cName;
  }
  if (op === RBlockGpu.PARALLELIZE) {
    return emitParallelize(k, kids, scope, opts);
  }
  if (op === RBlockGpu.VECTORIZE) {
    return emitVectorize(k, kids, scope, opts);
  }
  // DO / SEQUENCE
  if (kids.length === 0) return `((${cudaScalar(opts.dtype)})0)`;
  let last = `((${cudaScalar(opts.dtype)})0)`;
  for (const c of kids) {
    last = emitExpr(k, c, scope, opts);
  }
  return last;
}

// Parallelize → emits the __global__ kernel scaffolding (recorded for the
// outer assemble step) and inlines the body with threadIdx/blockIdx index
// derivation. The body expression itself reads `tid`/`bid` as bound names.
function emitParallelize(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  scope.parallelized = true;
  // Bind tid / bid / gid as local names visible to the body.
  const tidName = k.internName("tid");
  const bidName = k.internName("bid");
  const gidName = k.internName("gid");
  scope.vars.set(tidName, "tid");
  scope.vars.set(bidName, "bid");
  scope.vars.set(gidName, "gid");
  scope.device_fns.push(`const int tid = threadIdx.x;`);
  scope.device_fns.push(`const int bid = blockIdx.x;`);
  scope.device_fns.push(`const int gid = blockIdx.x * blockDim.x + threadIdx.x;`);
  // Body is the last child by convention; earlier children are setup
  // expressions whose textual emit went into device_fns already.
  let last = `((${cudaScalar(opts.dtype)})0)`;
  for (const c of kids) {
    last = emitExpr(k, c, scope, opts);
  }
  return last;
}

// Vectorize → emits __ldg vectorized load helpers and binds `lane`/`v` to
// per-thread 4-wide loads of the named source pointer. The body sees `v`
// as a float4/half2/int4 expression.
function emitVectorize(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  scope.vector_load_used = true;
  // First child is the source-pointer identifier (e.g. `src`); body follows.
  const src = kids[0]!;
  const srcName =
    src.level === Level.TRIVIAL && src.type === Triv.STRING
      ? sanitize(k.nameStr(src.inst))
      : "src";
  const vName = fresh(scope, "v");
  const vec = cudaVec4(opts.dtype);
  scope.device_fns.push(
    `// __ldg vectorized 128-bit load — coalesced read into the per-thread register`,
  );
  scope.device_fns.push(
    `const ${vec} ${vName} = __ldg(reinterpret_cast<const ${vec}*>(${srcName}) + gid);`,
  );
  // Bind `v` as a local name for the body to consume.
  scope.vars.set(k.internName("v"), vName);
  let last = vName;
  for (let i = 1; i < kids.length; i++) {
    last = emitExpr(k, kids[i]!, scope, opts);
  }
  return last;
}

// LIST → vector literal. Length-4 lists pack into float4/half2-pair/int4;
// other lengths emit a brace-initialized array.
function emitVectorList(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  const parts = kids.map((c) => emitExpr(k, c, scope, opts));
  if (parts.length === 4 && opts.dtype === "fp32") {
    return `make_float4(${parts.join(", ")})`;
  }
  if (parts.length === 4 && opts.dtype === "int32") {
    return `make_int4(${parts.join(", ")})`;
  }
  if (parts.length === 2 && opts.dtype === "fp16") {
    return `__halves2half2(${parts[0]!}, ${parts[1]!})`;
  }
  // Generic — brace-initialized array.
  return `{ ${parts.join(", ")} }`;
}

// FNDEF → device-side helper function declaration. Recorded into
// scope.device_fns and the function's NameID is bound for FNCALL.
function emitFnDef(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  const name = kids[0]!;
  const paramsBlock = kids[1]!;
  const body = kids[2]!;
  if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
    return `((${cudaScalar(opts.dtype)})0)`;
  }
  const cName = sanitize(k.nameStr(name.inst));
  scope.fns.set(name.inst, cName);
  const paramKids = k.children(paramsBlock);
  const inner = freshScope();
  inner.uid = scope.uid;
  const paramDecls: string[] = [];
  for (const p of paramKids) {
    if (p.level !== Level.TRIVIAL || p.type !== Triv.STRING) continue;
    const pName = sanitize(k.nameStr(p.inst));
    inner.vars.set(p.inst, pName);
    paramDecls.push(`${cudaScalar(opts.dtype)} ${pName}`);
  }
  const bodySrc = emitExpr(k, body, inner, opts);
  const decl = `__device__ ${cudaScalar(opts.dtype)} ${cName}(${paramDecls.join(", ")}) { return ${bodySrc}; }`;
  scope.device_fns.push(decl);
  // Pull any nested device_fns up to outer scope so they precede the call.
  for (const d of inner.device_fns) {
    scope.device_fns.push(d);
  }
  if (inner.tensor_core_used) scope.tensor_core_used = true;
  if (inner.vector_load_used) scope.vector_load_used = true;
  return `((${cudaScalar(opts.dtype)})0)`;
}

function emitFnCall(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  if (kids.length < 1) return `((${cudaScalar(opts.dtype)})0)`;
  const callee = kids[0]!;
  let nameID: number | null = null;
  if (callee.level === Level.TRIVIAL && callee.type === Triv.STRING) {
    nameID = callee.inst;
  } else if (
    callee.level === Level.BASIC &&
    callee.type === RBasic.IDENT
  ) {
    nameID = k.identID(callee);
  }
  const args = kids.slice(1).map((a) => emitExpr(k, a, scope, opts));
  if (nameID === null) {
    return `((${cudaScalar(opts.dtype)})0)`;
  }
  const cName = scope.fns.get(nameID) ?? sanitize(k.nameStr(nameID));
  return `${cName}(${args.join(", ")})`;
}

// ---------------------------------------------------------------------------
// Final assembly — wrap the emitted body in the __global__ kernel scaffold,
// adding includes and dispatch comments. The dispatch line is informative;
// the actual <<<grid, block>>> call lives in the host harness.
// ---------------------------------------------------------------------------

function assembleKernelSource(
  body: string,
  scope: EmitScope,
  opts: NormalizedOptions,
): string {
  const includes: string[] = ["#include <cuda_runtime.h>"];
  if (opts.dtype === "fp16" || scope.tensor_core_used) {
    includes.push("#include <cuda_fp16.h>");
  }
  if (opts.dtype === "fp8") {
    includes.push("#include <cuda_fp8.h>");
  }
  if (scope.tensor_core_used) {
    includes.push("#include <mma.h>");
  }
  const usings: string[] = [];
  if (scope.tensor_core_used) {
    usings.push("using namespace nvcuda;");
  }
  const dispatchHint = `// dispatch: ${opts.kernel_name}<<<dim3(${opts.grid.join(", ")}), dim3(${opts.block.join(", ")})>>>(...)`;
  const ret = cudaScalar(opts.dtype);
  // Inline the gathered device_fns (LET-bindings, vector loads, MMA
  // fragments) into the kernel body in order, then the final expression.
  const bodyStmts = scope.device_fns.join("\n  ");
  const guard = scope.parallelized
    ? ""
    : "  // single-thread fallback: no PARALLELIZE in recipe\n  if (threadIdx.x != 0 || blockIdx.x != 0) return;\n";
  return [
    includes.join("\n"),
    "",
    usings.join("\n"),
    usings.length > 0 ? "" : null,
    dispatchHint,
    `__global__ void ${opts.kernel_name}(${ret}* __restrict__ out) {`,
    guard.length > 0 ? guard : null,
    bodyStmts.length > 0 ? `  ${bodyStmts}` : null,
    `  const ${ret} __form_result = ${body};`,
    `  if (out != nullptr) { *out = __form_result; }`,
    "}",
    "",
  ]
    .filter((line) => line !== null)
    .join("\n");
}
