// MetalBackend — emit Metal Shading Language (MSL) source from a recipe tree.
//
// Companion to compiler.ts (which emits JS for V8) and the still-ripening
// vector.ts / parallel.ts modules (Form-level vector/parallel intrinsics).
// This backend targets Apple GPUs via MSL — `kernel void` functions dispatched
// across a grid, with optional SIMD-group matrix ops for BF16/FP16 paths.
//
// Target hints (declared on `MetalBackend.target_hints`):
//   - "gpu-metal"               — baseline kernel emission (float / int / float4)
//   - "gpu-metal-simdgroup"     — emit `simdgroup_matrix<...>` for bf16/fp16
//                                 dense kernels (Apple M-series GPUs)
//
// Shape of what's emitted:
//
//   #include <metal_stdlib>
//   using namespace metal;
//   #if __METAL_VERSION__ >= 310
//   using namespace metal::simdgroup_matrix_8x8;
//   #endif
//
//   kernel void {name}(
//       device const T* in    [[buffer(0)]],
//       device       T* out   [[buffer(1)]],
//       uint tid              [[thread_position_in_grid]],
//       uint lid              [[thread_position_in_threadgroup]])
//   {
//       <body>
//       out[tid] = <expr>;
//   }
//
// What the backend does NOT do yet:
//   - Reflection over substrate (intern_node, walk_recipe, ...) — those are
//     host-side concepts; MSL is a static-shader language.
//   - General FNCALL into native primitives — only inlinable arithmetic gets
//     a direct MSL emission. Anything else surfaces as a `/* unsupported */`
//     marker so the host can fall back to the walker / compiler path.
//   - Lists. MSL has no first-class list; List recipes degrade to comments.
//
// The discipline: every node that has an MSL-shaped equivalent emits the
// direct MSL form; anything else emits a tagged fallback marker rather than
// silently producing wrong shader code. The host decides whether to dispatch
// to GPU or fall back to CPU based on whether the emitted source contains
// any `/* fallback:` markers.

import {
  Frame,
  Kernel,
  Level,
  RBasic,
  RBlock,
  RCmp,
  RCond,
  RLogic,
  RMath,
  Triv,
  type NodeID,
} from "../kernel.ts";

// -----------------------------------------------------------------------------
// Public surface
// -----------------------------------------------------------------------------

export type MetalTargetHint = "gpu-metal" | "gpu-metal-simdgroup";

/**
 * Scalar element type emitted into MSL signatures and buffers.
 * - "int"     → int32_t
 * - "float"   → float (FP32)
 * - "half"    → half (FP16)
 * - "bfloat"  → bfloat (BF16; available in Metal 3.1+)
 */
export type MetalScalarType = "int" | "float" | "half" | "bfloat";

/**
 * Vector lane count used by `vectorize`. Maps to MSL packed/simd types:
 *   float × 4  → simd_float4 (also written `simd_packed_float4` when packed)
 *   half  × 2  → simd_half2
 *   bfloat× 2  → simd_bfloat2
 *   int   × 4  → simd_int4
 */
export type MetalVectorLanes = 1 | 2 | 4 | 8;

/**
 * Parallel dispatch hint. `parallelize: { kind: "grid", size: N }` lifts the
 * emitted function from a scalar body into a kernel dispatched across N
 * threads, with `tid = thread_position_in_grid` driving indexing.
 *
 * `kind: "threadgroup"` adds the threadgroup-local position as well, useful
 * for reductions and shared-memory tiles.
 */
export type MetalParallelHint =
  | { readonly kind: "scalar" }
  | { readonly kind: "grid"; readonly size: number }
  | {
      readonly kind: "threadgroup";
      readonly grid: number;
      readonly threadgroup: number;
    };

export interface MetalEmitOptions {
  /** Function name in the emitted MSL. Defaults to "form_kernel". */
  readonly name?: string;
  /** Scalar element type for buffer pointers. Defaults to "float". */
  readonly scalar?: MetalScalarType;
  /** SIMD lane width when vectorizing. Defaults to 1 (scalar). */
  readonly vectorize?: MetalVectorLanes;
  /** Parallel dispatch shape. Defaults to scalar (no kernel wrapping). */
  readonly parallelize?: MetalParallelHint;
  /**
   * When true, emit `simdgroup_matrix<T,8,8>` setup for the kernel.
   * Only honored for half / bfloat scalar types — the path SIMD-group
   * matrix ops are designed for.
   */
  readonly simdgroupMatrix?: boolean;
  /**
   * Free names in the recipe that should be exposed as input buffer
   * parameters, in order. Each becomes `device const T* {name} [[buffer(i)]]`.
   * If empty, the emitter assumes the recipe is a pure constant expression.
   */
  readonly inputs?: readonly string[];
  /** Output buffer name. Defaults to "out". */
  readonly output?: string;
}

export interface MetalEmitResult {
  /** The full MSL source string. */
  readonly source: string;
  /** True if any subtree fell back to a comment marker. */
  readonly hasFallback: boolean;
  /** Resolved options after defaults applied. */
  readonly resolved: Required<
    Omit<MetalEmitOptions, "inputs" | "parallelize" | "simdgroupMatrix">
  > & {
    readonly inputs: readonly string[];
    readonly parallelize: MetalParallelHint;
    readonly simdgroupMatrix: boolean;
  };
}

export interface MetalBackendShape {
  readonly name: "metal";
  readonly target_hints: ReadonlySet<MetalTargetHint>;
  readonly emit: (
    k: Kernel,
    root: NodeID,
    opts?: MetalEmitOptions,
  ) => MetalEmitResult;
}

export const MetalBackend: MetalBackendShape = {
  name: "metal",
  target_hints: new Set<MetalTargetHint>([
    "gpu-metal",
    "gpu-metal-simdgroup",
  ]),
  emit(
    k: Kernel,
    root: NodeID,
    opts: MetalEmitOptions = {},
  ): MetalEmitResult {
    return emitMetal(k, root, opts);
  },
};

// Backwards-compat aliases — some callers may import lower-case forms.
export const metalBackend = MetalBackend;

// -----------------------------------------------------------------------------
// Type system — MSL type strings derived from scalar + vectorize options
// -----------------------------------------------------------------------------

function mslScalar(t: MetalScalarType): string {
  switch (t) {
    case "int":
      return "int";
    case "float":
      return "float";
    case "half":
      return "half";
    case "bfloat":
      return "bfloat";
  }
}

function mslVector(t: MetalScalarType, lanes: MetalVectorLanes): string {
  if (lanes === 1) return mslScalar(t);
  // Apple SIMD types: simd_float4, simd_half2, simd_int4, simd_bfloat2, ...
  return `simd_${mslScalar(t)}${lanes}`;
}

function mslPackedVector(
  t: MetalScalarType,
  lanes: MetalVectorLanes,
): string {
  // `simd_packed_*` are the tightly-packed memory-layout variants — used in
  // device-buffer signatures so loads/stores aren't penalized by alignment.
  if (lanes === 1) return mslScalar(t);
  return `simd_packed_${mslScalar(t)}${lanes}`;
}

// -----------------------------------------------------------------------------
// Emit core
// -----------------------------------------------------------------------------

interface EmitCtx {
  readonly k: Kernel;
  readonly scalar: MetalScalarType;
  readonly lanes: MetalVectorLanes;
  /** Param name → resolved MSL identifier (for unbound IDENTs). */
  readonly params: Map<number, string>;
  /** Locally defined functions emitted to the top of the source. */
  readonly localFns: string[];
  readonly fnNames: Map<number, string>;
  readonly fallback: { hit: boolean };
  readonly uid: { n: number };
}

function freshCtx(
  k: Kernel,
  scalar: MetalScalarType,
  lanes: MetalVectorLanes,
  inputs: readonly string[],
): EmitCtx {
  const params = new Map<number, string>();
  for (const name of inputs) {
    const id = k.internName(name);
    params.set(id, mslSanitize(name));
  }
  return {
    k,
    scalar,
    lanes,
    params,
    localFns: [],
    fnNames: new Map(),
    fallback: { hit: false },
    uid: { n: 0 },
  };
}

function mslSanitize(s: string): string {
  return s.replace(/[^A-Za-z0-9_]/g, "_");
}

function fresh(ctx: EmitCtx, hint: string): string {
  ctx.uid.n++;
  return `${mslSanitize(hint)}_${ctx.uid.n}`;
}

function emitMetal(
  k: Kernel,
  root: NodeID,
  opts: MetalEmitOptions,
): MetalEmitResult {
  const name = opts.name ?? "form_kernel";
  const scalar = opts.scalar ?? "float";
  const lanes = opts.vectorize ?? 1;
  const parallelize = opts.parallelize ?? { kind: "scalar" };
  const inputs = opts.inputs ?? [];
  const output = opts.output ?? "out";
  const simdgroupMatrix =
    opts.simdgroupMatrix === true && (scalar === "half" || scalar === "bfloat");

  const ctx = freshCtx(k, scalar, lanes, inputs);

  // Emit body — a single MSL expression representing the recipe result.
  const bodyExpr = emitExpr(ctx, root);

  const header = emitHeader(simdgroupMatrix);
  const localFnsBlock =
    ctx.localFns.length === 0 ? "" : ctx.localFns.join("\n\n") + "\n\n";

  let body: string;
  if (parallelize.kind === "scalar") {
    body = emitScalarKernel({
      name,
      scalar,
      lanes,
      inputs,
      output,
      bodyExpr,
      simdgroupMatrix,
    });
  } else if (parallelize.kind === "grid") {
    body = emitGridKernel({
      name,
      scalar,
      lanes,
      inputs,
      output,
      bodyExpr,
      simdgroupMatrix,
      size: parallelize.size,
    });
  } else {
    body = emitThreadgroupKernel({
      name,
      scalar,
      lanes,
      inputs,
      output,
      bodyExpr,
      simdgroupMatrix,
      grid: parallelize.grid,
      threadgroup: parallelize.threadgroup,
    });
  }

  const source = `${header}\n${localFnsBlock}${body}\n`;

  return {
    source,
    hasFallback: ctx.fallback.hit,
    resolved: {
      name,
      scalar,
      vectorize: lanes,
      output,
      inputs,
      parallelize,
      simdgroupMatrix,
    },
  };
}

function emitHeader(simdgroupMatrix: boolean): string {
  const lines = [
    "#include <metal_stdlib>",
    "using namespace metal;",
  ];
  if (simdgroupMatrix) {
    lines.push(
      "// simdgroup_matrix path — Metal 3.1+ on Apple M-series GPUs",
      "#if __METAL_VERSION__ >= 310",
      "using metal::simdgroup_matrix;",
      "#endif",
    );
  }
  return lines.join("\n");
}

// -----------------------------------------------------------------------------
// Kernel wrappers — scalar / grid / threadgroup
// -----------------------------------------------------------------------------

interface KernelEmitInputs {
  readonly name: string;
  readonly scalar: MetalScalarType;
  readonly lanes: MetalVectorLanes;
  readonly inputs: readonly string[];
  readonly output: string;
  readonly bodyExpr: string;
  readonly simdgroupMatrix: boolean;
}

function bufferParams(
  inputs: readonly string[],
  scalar: MetalScalarType,
  lanes: MetalVectorLanes,
  outName: string,
): string {
  const elemTy = mslPackedVector(scalar, lanes);
  const parts: string[] = [];
  for (let i = 0; i < inputs.length; i++) {
    parts.push(
      `    device const ${elemTy}* ${mslSanitize(inputs[i]!)} [[buffer(${i})]]`,
    );
  }
  parts.push(
    `    device ${elemTy}* ${mslSanitize(outName)} [[buffer(${inputs.length})]]`,
  );
  return parts.join(",\n");
}

function emitScalarKernel(args: KernelEmitInputs): string {
  // Scalar kernel — single thread, useful for unit tests and degenerate cases.
  const { name, output, bodyExpr } = args;
  const params = bufferParams(args.inputs, args.scalar, args.lanes, output);
  const simdSetup = args.simdgroupMatrix
    ? `    // SIMD-group matrix scratch (8x8 tiles); use within threadgroup.\n` +
      `    simdgroup_matrix<${mslScalar(args.scalar)}, 8, 8> sg_acc(0);\n` +
      `    (void)sg_acc;\n`
    : "";
  return [
    `kernel void ${mslSanitize(name)}(`,
    params + ",",
    `    uint tid [[thread_position_in_grid]])`,
    `{`,
    `    if (tid != 0) return;`,
    simdSetup,
    `    ${mslSanitize(output)}[0] = ${bodyExpr};`,
    `}`,
  ].join("\n");
}

function emitGridKernel(
  args: KernelEmitInputs & { readonly size: number },
): string {
  const { name, output, bodyExpr } = args;
  const params = bufferParams(args.inputs, args.scalar, args.lanes, output);
  const simdSetup = args.simdgroupMatrix
    ? `    simdgroup_matrix<${mslScalar(args.scalar)}, 8, 8> sg_acc(0);\n` +
      `    (void)sg_acc;\n`
    : "";
  return [
    `// dispatched across ${args.size} threads`,
    `kernel void ${mslSanitize(name)}(`,
    params + ",",
    `    uint tid [[thread_position_in_grid]])`,
    `{`,
    `    if (tid >= ${args.size}) return;`,
    simdSetup,
    `    ${mslSanitize(output)}[tid] = ${bodyExpr};`,
    `}`,
  ].join("\n");
}

function emitThreadgroupKernel(
  args: KernelEmitInputs & {
    readonly grid: number;
    readonly threadgroup: number;
  },
): string {
  const { name, output, bodyExpr } = args;
  const params = bufferParams(args.inputs, args.scalar, args.lanes, output);
  const simdSetup = args.simdgroupMatrix
    ? `    threadgroup ${mslScalar(args.scalar)} tg_scratch[8 * 8];\n` +
      `    simdgroup_matrix<${mslScalar(args.scalar)}, 8, 8> sg_acc(0);\n` +
      `    (void)tg_scratch; (void)sg_acc;\n`
    : "";
  return [
    `// grid=${args.grid}, threadgroup=${args.threadgroup}`,
    `kernel void ${mslSanitize(name)}(`,
    params + ",",
    `    uint tid [[thread_position_in_grid]],`,
    `    uint lid [[thread_position_in_threadgroup]])`,
    `{`,
    `    if (tid >= ${args.grid}) return;`,
    `    (void)lid;`,
    simdSetup,
    `    ${mslSanitize(output)}[tid] = ${bodyExpr};`,
    `}`,
  ].join("\n");
}

// -----------------------------------------------------------------------------
// Expression emit
// -----------------------------------------------------------------------------

function emitExpr(ctx: EmitCtx, node: NodeID): string {
  if (node.level === Level.TRIVIAL) {
    return emitTrivial(ctx, node);
  }
  const cat = ctx.k.category(node);
  const kids = ctx.k.children(node);

  switch (cat.type) {
    case RBasic.IDENT: {
      const id = ctx.k.identID(node);
      const param = ctx.params.get(id);
      if (param !== undefined) {
        // For grid kernels, IDENTs index by `tid` to read element-wise.
        return `${param}[tid]`;
      }
      const local = ctx.fnNames.get(id);
      if (local !== undefined) return local;
      ctx.fallback.hit = true;
      return `/* fallback: unbound ident name#${id} */ 0`;
    }
    case RBasic.MATH:
      return emitMath(ctx, cat.inst, kids);
    case RBasic.COMPARE:
      return emitCompare(ctx, cat.inst, kids);
    case RBasic.LOGIC:
      return emitLogic(ctx, cat.inst, kids);
    case RBasic.COND:
      return emitCond(ctx, cat.inst, kids);
    case RBasic.BLOCK:
      return emitBlock(ctx, cat.inst, kids);
    case RBasic.FNDEF:
      return emitFnDef(ctx, kids);
    case RBasic.FNCALL:
      return emitFnCall(ctx, kids);
    case RBasic.LIST: {
      ctx.fallback.hit = true;
      return `/* fallback: list literal */ 0`;
    }
    default: {
      ctx.fallback.hit = true;
      return `/* fallback: rbasic ${cat.type} */ 0`;
    }
  }
}

function emitTrivial(ctx: EmitCtx, node: NodeID): string {
  if (node.type === Triv.INT) {
    const u = node.inst >>> 0;
    const i = u > 0x7fffffff ? u - 0x100000000 : u;
    // Cast int literal to scalar type so mixed-precision arithmetic stays
    // in the requested precision. For int scalar, leave as plain int.
    if (ctx.scalar === "int") return String(i);
    return `${mslScalar(ctx.scalar)}(${i})`;
  }
  if (node.type === Triv.BOOL) {
    return node.inst !== 0 ? "true" : "false";
  }
  if (node.type === Triv.NULL) {
    ctx.fallback.hit = true;
    return `/* fallback: null literal */ 0`;
  }
  // STRING — no MSL string type
  ctx.fallback.hit = true;
  return `/* fallback: string trivial */ 0`;
}

function emitMath(
  ctx: EmitCtx,
  op: number,
  kids: readonly NodeID[],
): string {
  if (kids.length < 2) {
    ctx.fallback.hit = true;
    return `/* fallback: math arity */ 0`;
  }
  const parts = kids.map((c) => `(${emitExpr(ctx, c)})`);
  let opStr: string;
  switch (op) {
    case RMath.PLUS:
      opStr = "+";
      break;
    case RMath.MINUS:
      opStr = "-";
      break;
    case RMath.MUL:
      opStr = "*";
      break;
    case RMath.DIV:
      opStr = "/";
      break;
    case RMath.MOD:
      // MSL has `fmod` for float, `%` for int. Use the right one.
      if (ctx.scalar === "int") {
        opStr = "%";
      } else {
        // Build nested fmod() calls
        let acc = parts[0]!;
        for (let i = 1; i < parts.length; i++) {
          acc = `fmod(${acc}, ${parts[i]})`;
        }
        return acc;
      }
      break;
    default:
      ctx.fallback.hit = true;
      return `/* fallback: math op ${op} */ 0`;
  }
  return `(${parts.join(` ${opStr} `)})`;
}

function emitCompare(
  ctx: EmitCtx,
  op: number,
  kids: readonly NodeID[],
): string {
  if (kids.length !== 2) {
    ctx.fallback.hit = true;
    return `/* fallback: compare arity */ false`;
  }
  const a = emitExpr(ctx, kids[0]!);
  const b = emitExpr(ctx, kids[1]!);
  let opStr: string;
  switch (op) {
    case RCmp.EQ:
      opStr = "==";
      break;
    case RCmp.NE:
      opStr = "!=";
      break;
    case RCmp.LT:
      opStr = "<";
      break;
    case RCmp.LE:
      opStr = "<=";
      break;
    case RCmp.GT:
      opStr = ">";
      break;
    case RCmp.GE:
      opStr = ">=";
      break;
    default:
      ctx.fallback.hit = true;
      return `/* fallback: compare op ${op} */ false`;
  }
  return `((${a}) ${opStr} (${b}))`;
}

function emitLogic(
  ctx: EmitCtx,
  op: number,
  kids: readonly NodeID[],
): string {
  if (op === RLogic.NOT) {
    if (kids.length !== 1) {
      ctx.fallback.hit = true;
      return `/* fallback: not arity */ false`;
    }
    return `(!(${emitExpr(ctx, kids[0]!)}))`;
  }
  const opStr = op === RLogic.AND ? "&&" : "||";
  const parts = kids.map((c) => `(${emitExpr(ctx, c)})`);
  return `(${parts.join(` ${opStr} `)})`;
}

function emitCond(
  ctx: EmitCtx,
  op: number,
  kids: readonly NodeID[],
): string {
  if (op === RCond.IF_THEN) {
    if (kids.length !== 2) {
      ctx.fallback.hit = true;
      return `/* fallback: if arity */ 0`;
    }
    // No "null" return in MSL — collapse to the then-branch when true,
    // and a typed-zero otherwise. Caller must ensure conditional makes sense.
    const zero =
      ctx.scalar === "int" ? "0" : `${mslScalar(ctx.scalar)}(0)`;
    return `((${emitExpr(ctx, kids[0]!)}) ? (${emitExpr(ctx, kids[1]!)}) : ${zero})`;
  }
  if (kids.length !== 3) {
    ctx.fallback.hit = true;
    return `/* fallback: if/else arity */ 0`;
  }
  return `((${emitExpr(ctx, kids[0]!)}) ? (${emitExpr(ctx, kids[1]!)}) : (${emitExpr(ctx, kids[2]!)}))`;
}

function emitBlock(
  ctx: EmitCtx,
  op: number,
  kids: readonly NodeID[],
): string {
  if (op === RBlock.LET) {
    if (kids.length !== 2) {
      ctx.fallback.hit = true;
      return `/* fallback: let arity */ 0`;
    }
    const name = kids[0]!;
    if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
      ctx.fallback.hit = true;
      return `/* fallback: let name */ 0`;
    }
    const valSrc = emitExpr(ctx, kids[1]!);
    const mslName = fresh(ctx, `let_${name.inst}`);
    ctx.params.set(name.inst, mslName);
    // MSL is statement-based — express LET via comma operator inside a
    // GNU statement expression-ish trick that MSL actually supports via
    // `({...})`. Apple's MSL compiler accepts GCC-statement-expressions in
    // most modern versions; if it doesn't, this would lift to a local var
    // outside the expression. Conservative form: a parenthesized assignment
    // chained with the bound name.
    return `(${mslName} = ${valSrc}, ${mslName})`;
  }
  if (kids.length === 0) {
    ctx.fallback.hit = true;
    return `/* fallback: empty block */ 0`;
  }
  if (kids.length === 1) return emitExpr(ctx, kids[0]!);
  // DO / SEQUENCE — comma-fold; MSL accepts comma operator in expressions.
  const parts = kids.map((c) => `(${emitExpr(ctx, c)})`);
  return `(${parts.join(", ")})`;
}

function emitFnDef(ctx: EmitCtx, kids: readonly NodeID[]): string {
  if (kids.length !== 3) {
    ctx.fallback.hit = true;
    return `/* fallback: defn arity */ 0`;
  }
  const name = kids[0]!;
  const paramsBlock = kids[1]!;
  const body = kids[2]!;
  if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
    ctx.fallback.hit = true;
    return `/* fallback: defn name */ 0`;
  }
  const nameID = name.inst;
  const paramKids = ctx.k.children(paramsBlock);
  const mslName = fresh(ctx, `fn_${nameID}`);
  ctx.fnNames.set(nameID, mslName);

  // Track previous param bindings so we can restore (functions are flat —
  // no nested scope here).
  const prevParams = new Map(ctx.params);
  const paramDecls: string[] = [];
  const scalarTy = mslScalar(ctx.scalar);
  for (const p of paramKids) {
    if (p.level !== Level.TRIVIAL || p.type !== Triv.STRING) {
      ctx.fallback.hit = true;
      continue;
    }
    const pname = fresh(ctx, `p_${p.inst}`);
    ctx.params.set(p.inst, pname);
    paramDecls.push(`${scalarTy} ${pname}`);
  }
  const bodySrc = emitExpr(ctx, body);
  ctx.localFns.push(
    `inline ${scalarTy} ${mslName}(${paramDecls.join(", ")}) {\n    return ${bodySrc};\n}`,
  );
  // Restore param bindings — emitted fn doesn't leak its params upward.
  ctx.params.clear();
  for (const [k, v] of prevParams) ctx.params.set(k, v);

  // FNDEF evaluates to a function-typed value in Form; MSL has no such
  // first-class type. Returning a typed-zero keeps callers happy when the
  // FNDEF is in a DO block that ends with a different expression.
  return ctx.scalar === "int" ? "0" : `${scalarTy}(0)`;
}

function emitFnCall(ctx: EmitCtx, kids: readonly NodeID[]): string {
  if (kids.length < 1) {
    ctx.fallback.hit = true;
    return `/* fallback: call no callee */ 0`;
  }
  const callee = kids[0]!;
  let nameID: number | null = null;
  if (callee.level === Level.TRIVIAL && callee.type === Triv.STRING) {
    nameID = callee.inst;
  } else if (
    callee.level === Level.BASIC &&
    callee.type === RBasic.IDENT
  ) {
    nameID = ctx.k.identID(callee);
  }
  if (nameID === null) {
    ctx.fallback.hit = true;
    return `/* fallback: dynamic callee */ 0`;
  }
  const local = ctx.fnNames.get(nameID);
  if (local !== undefined) {
    const args = kids.slice(1).map((a) => emitExpr(ctx, a));
    return `${local}(${args.join(", ")})`;
  }
  // Map a small set of natives onto MSL stdlib functions.
  const nativeName = ctx.k.nameStr(nameID);
  const mapped = METAL_NATIVE_MAP[nativeName];
  if (mapped !== undefined) {
    const args = kids.slice(1).map((a) => emitExpr(ctx, a));
    return `${mapped}(${args.join(", ")})`;
  }
  ctx.fallback.hit = true;
  return `/* fallback: native ${nativeName} */ 0`;
}

// MSL stdlib mapping for a curated set of Form natives that have direct
// equivalents on the GPU. Anything not in here falls back to walker/compiler.
const METAL_NATIVE_MAP: Record<string, string> = {
  // Math
  add: "(+)",
  sub: "(-)",
  mul: "(*)",
  div: "(/)",
  abs: "abs",
  min: "min",
  max: "max",
  sqrt: "sqrt",
  rsqrt: "rsqrt",
  exp: "exp",
  log: "log",
  sin: "sin",
  cos: "cos",
  tan: "tan",
  floor: "floor",
  ceil: "ceil",
  // Trig + activation primitives that show up in shader kernels.
  fma: "fma",
  pow: "pow",
};

// -----------------------------------------------------------------------------
// Frame is imported but not actively used in MSL emit — keeping the import
// so the surface mirrors compiler.ts and we can wire reflection later.
// -----------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _frameRef: typeof Frame = Frame;
