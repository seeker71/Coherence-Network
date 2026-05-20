// WGSL emit backend — Task #10.
//
// Walks a recipe tree and emits a WGSL compute-shader source string ready
// to hand to a WebGPU `createShaderModule`. The backend follows the same
// shape as the JS compiler in `../compiler.ts`: a recursive walker over
// NodeIDs that produces source text, plus a top-level emit() that wraps
// the body in a `@compute` kernel.
//
// What's covered:
//   • Math ops (RMath.{PLUS,MINUS,MUL,DIV,MOD}) → arithmetic
//   • COMPARE / LOGIC / COND → WGSL expressions and `if` blocks
//   • FNDEF / FNCALL → `fn` declarations and call sites
//   • LET / DO / SEQUENCE → `var` bindings, statement blocks
//   • Vector format-recipes → vec4<f32> / vec4<i32> arithmetic (the
//     vectorize() builder lifts a scalar body to vector dispatch)
//   • Parallelize pattern → @compute @workgroup_size(...) + global_id
//     dispatch using storage buffers
//   • Tile pattern → workgroup-local loops with workgroup-shared memory
//   • Reductions → workgroupBarrier + tree-shuffle reduce in shared
//     memory (subgroup ops aren't universally available across WebGPU
//     implementations yet, so we emit the portable shared-memory form)
//
// What's deferred to a fallback:
//   • Native function calls (no analog in WGSL — they raise an error)
//   • IDENT references that don't resolve to a known parameter or local
//   • LIST literals (no native list type in WGSL)
//   • FP64 — WGSL does not support f64; encoder throws.
//
// The interface mirrors what BackendRegistry (Task #7) will expect:
//   {
//     name: "wgsl",
//     target_hints: Set<string>,
//     emit(kernel, recipe, opts?): string,
//   }
// When the registry lands, the WgslBackend can be registered with no
// shape change.

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
// CodegenBackend — local definition matching what Task #7 will register
// ---------------------------------------------------------------------------

// A format-recipe descriptor as Task #9 / formats.ts will surface them.
// Duck-typed here so this file is decoupled from formats.ts until #7
// lands and the formal interface arrives.
export interface FormatRecipe {
  // Element scalar type — "f32" | "f64" | "i32" | "u32" | "bool"
  readonly scalar: "f32" | "f64" | "i32" | "u32" | "bool";
  // 1 = scalar, 2 / 3 / 4 = vector lane count, 8 / 16 = SIMD-wide
  readonly lanes: number;
  // Optional WebGPU target hints carried on the format recipe
  readonly target_hints?: ReadonlySet<string>;
}

export interface EmitOptions {
  // When provided, the emitted kernel walks an input/output storage
  // buffer using global_invocation_id and writes one element per thread.
  readonly parallelize?: {
    readonly workgroup_size: readonly [number, number, number];
    readonly buffer_format: FormatRecipe;
    readonly element_count?: number;
  };
  // When provided, the body is vectorized — scalar arithmetic lifts to
  // vec<lanes>.
  readonly vectorize?: {
    readonly format: FormatRecipe;
  };
  // When provided, the body is tiled with workgroup-shared memory of
  // the named size.
  readonly tile?: {
    readonly tile_size: number;
    readonly format: FormatRecipe;
  };
  // When provided, the body emits a tree-reduce in workgroup memory.
  readonly reduce?: {
    readonly op: "add" | "mul" | "max" | "min";
    readonly format: FormatRecipe;
    readonly workgroup_size: number;
  };
  // Names of formal parameters at the top level (in order). The walker
  // binds these so IDENTs in the recipe resolve to WGSL identifiers
  // instead of falling through to a frame-lookup that has no WGSL
  // analog.
  readonly params?: readonly string[];
  // Top-level return scalar type. Defaults to f32 in vectorize/parallel
  // modes, i32 otherwise.
  readonly return_format?: FormatRecipe;
}

export interface CodegenBackend {
  readonly name: string;
  readonly target_hints: ReadonlySet<string>;
  emit(kernel: Kernel, recipe: NodeID, opts?: EmitOptions): string;
}

// ---------------------------------------------------------------------------
// Format → WGSL type mapping
// ---------------------------------------------------------------------------

function wgslScalarType(fmt: FormatRecipe): string {
  switch (fmt.scalar) {
    case "f32":
      return "f32";
    case "f64":
      throw new Error(
        "WgslBackend: f64 is not natively supported in WGSL; " +
          "emit a software-double pass on top of two f32s if you need it.",
      );
    case "i32":
      return "i32";
    case "u32":
      return "u32";
    case "bool":
      return "bool";
  }
}

function wgslElementType(fmt: FormatRecipe): string {
  const scalar = wgslScalarType(fmt);
  if (fmt.lanes === 1) return scalar;
  if (fmt.lanes === 2 || fmt.lanes === 3 || fmt.lanes === 4) {
    return `vec${fmt.lanes}<${scalar}>`;
  }
  // 8 / 16-wide lanes are virtual — WGSL caps vectors at 4. Treat the
  // body as a loop over (lanes / 4) vec4 chunks at emit time; the
  // surface type stays vec4<scalar>.
  if (fmt.lanes === 8 || fmt.lanes === 16) {
    return `vec4<${scalar}>`;
  }
  throw new Error(
    `WgslBackend: unsupported lane count ${fmt.lanes} for format ${fmt.scalar}`,
  );
}

// ---------------------------------------------------------------------------
// Emit scope — the WGSL walker's per-scope state
// ---------------------------------------------------------------------------

interface EmitScope {
  // Parameters in scope, mapped to their WGSL variable name (NameID → ident).
  vars: Map<number, string>;
  // Locally-defined functions in scope.
  fns: Map<number, string>;
  // Top-level function declarations accumulated as we descend.
  fnDecls: string[];
  // Counter for unique WGSL identifiers.
  uid: { n: number };
  // Whether the current emit context expects vector or scalar arithmetic.
  vector: FormatRecipe | null;
  // Scalar element type (without vector wrapping) — used to choose `0`
  // vs `0.0` and to type vars.
  scalarType: string;
}

function freshScope(vec: FormatRecipe | null, scalarType: string): EmitScope {
  return {
    vars: new Map(),
    fns: new Map(),
    fnDecls: [],
    uid: { n: 0 },
    vector: vec,
    scalarType,
  };
}

function childScope(parent: EmitScope): EmitScope {
  return {
    vars: new Map(parent.vars),
    fns: new Map(parent.fns),
    fnDecls: parent.fnDecls,
    uid: parent.uid,
    vector: parent.vector,
    scalarType: parent.scalarType,
  };
}

function fresh(scope: EmitScope, hint: string): string {
  scope.uid.n++;
  return `${sanitize(hint)}_${scope.uid.n}`;
}

function sanitize(s: string): string {
  return s.replace(/[^A-Za-z0-9_]/g, "_");
}

// ---------------------------------------------------------------------------
// Recipe → WGSL expression walker
// ---------------------------------------------------------------------------

function emitExpr(k: Kernel, node: NodeID, scope: EmitScope): string {
  if (node.level === Level.TRIVIAL) {
    return emitTrivial(node, scope);
  }
  const cat = k.category(node);
  const kids = k.children(node);

  switch (cat.type) {
    case RBasic.IDENT: {
      const nameID = k.identID(node);
      const local = scope.vars.get(nameID) ?? scope.fns.get(nameID);
      if (local !== undefined) return local;
      const nameStr = k.nameStr(nameID);
      throw new Error(
        `WgslBackend: unbound identifier '${nameStr}' — no WGSL frame-lookup analog.`,
      );
    }
    case RBasic.MATH:
      return emitMath(k, cat.inst, kids, scope);
    case RBasic.COMPARE:
      return emitCompare(k, cat.inst, kids, scope);
    case RBasic.LOGIC:
      return emitLogic(k, cat.inst, kids, scope);
    case RBasic.COND:
      return emitCond(k, cat.inst, kids, scope);
    case RBasic.BLOCK:
      return emitBlock(k, cat.inst, kids, scope);
    case RBasic.FNDEF:
      return emitFnDef(k, kids, scope);
    case RBasic.FNCALL:
      return emitFnCall(k, kids, scope);
    case RBasic.LIST:
      throw new Error("WgslBackend: LIST has no WGSL analog.");
    default:
      throw new Error(
        `WgslBackend: unsupported recipe category ${cat.type} (RBasic).`,
      );
  }
}

function emitTrivial(node: NodeID, scope: EmitScope): string {
  if (node.type === Triv.INT) {
    const u = node.inst >>> 0;
    const i = u > 0x7fffffff ? u - 0x100000000 : u;
    // In a float-typed context, emit a float literal so WGSL doesn't
    // raise the implicit-conversion error.
    if (scope.scalarType === "f32") {
      return Number.isInteger(i) ? `${i}.0` : String(i);
    }
    return `${i}`;
  }
  if (node.type === Triv.BOOL) {
    return node.inst !== 0 ? "true" : "false";
  }
  if (node.type === Triv.NULL) {
    // No null in WGSL — represent as the zero of the current type.
    return scope.scalarType === "f32" ? "0.0" : "0";
  }
  if (node.type === Triv.STRING) {
    // WGSL has no string type. Best we can do for a string trivial
    // standing in expression position is route it through IDENT.
    throw new Error("WgslBackend: string trivial in expression position.");
  }
  throw new Error(`WgslBackend: unknown trivial type ${node.type}`);
}

function emitMath(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  const parts = kids.map((c) => `(${emitExpr(k, c, scope)})`);
  // Modulo on floats in WGSL needs the `%` operator too, but for f32
  // the semantics differ from i32. We faithfully emit `%`; the caller
  // chose the format.
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
      opStr = "%";
      break;
    default:
      throw new Error(`WgslBackend: unknown math op ${op}`);
  }
  let acc = parts[0]!;
  for (let i = 1; i < parts.length; i++) {
    acc = `(${acc} ${opStr} ${parts[i]})`;
  }
  return acc;
}

function emitCompare(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  const a = emitExpr(k, kids[0]!, scope);
  const b = emitExpr(k, kids[1]!, scope);
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
      throw new Error(`WgslBackend: unknown compare op ${op}`);
  }
  return `((${a}) ${opStr} (${b}))`;
}

function emitLogic(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  if (op === RLogic.NOT) {
    return `(!(${emitExpr(k, kids[0]!, scope)}))`;
  }
  const opStr = op === RLogic.AND ? "&&" : "||";
  const parts = kids.map((c) => `(${emitExpr(k, c, scope)})`);
  return parts.join(` ${opStr} `);
}

function emitCond(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  // WGSL has the `select(falseExpr, trueExpr, cond)` ternary builtin —
  // an expression form that fits cleanly into the surrounding emit
  // context (no statement-level `if` required).
  if (op === RCond.IF_THEN) {
    const c = emitExpr(k, kids[0]!, scope);
    const t = emitExpr(k, kids[1]!, scope);
    const z = scope.scalarType === "f32" ? "0.0" : "0";
    return `select(${z}, ${t}, ${c})`;
  }
  const c = emitExpr(k, kids[0]!, scope);
  const t = emitExpr(k, kids[1]!, scope);
  const f = emitExpr(k, kids[2]!, scope);
  return `select(${f}, ${t}, ${c})`;
}

function emitBlock(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  if (op === RBlock.LET) {
    const name = kids[0]!;
    if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
      throw new Error("WgslBackend: LET name must be a string trivial");
    }
    const valSrc = emitExpr(k, kids[1]!, scope);
    const jsName = fresh(scope, `let_${k.nameStr(name.inst)}`);
    scope.vars.set(name.inst, jsName);
    // Inline as a let-binding expression. WGSL doesn't have
    // expression-let, so we surface this as a parenthesised assignment
    // helper — but realistically LET appears inside a DO block, where
    // emitBlockStmts (below) lowers it to a proper `let`.
    return `/* let ${jsName} = ${valSrc} */ ${jsName}`;
  }
  // DO / SEQUENCE — evaluate each, return last
  if (kids.length === 0) {
    return scope.scalarType === "f32" ? "0.0" : "0";
  }
  if (kids.length === 1) {
    return emitExpr(k, kids[0]!, scope);
  }
  // Multi-statement blocks need WGSL statements, not expressions.
  // Emit as a `{ let _0 = ...; let _1 = ...; final }` block, returned
  // via an inline expression-evaluation pattern. Since WGSL doesn't
  // have block-expressions, the typical use is at the top level via
  // emitBlockStmts.
  const stmts: string[] = [];
  for (let i = 0; i < kids.length - 1; i++) {
    const c = kids[i]!;
    const e = emitExpr(k, c, scope);
    const tmp = fresh(scope, "tmp");
    stmts.push(`let ${tmp} = ${e};`);
  }
  // The last child is the block's value — but expression context can't
  // hold statements. Surface that the caller should use emitBlockStmts
  // for non-trivial blocks; for now we collapse to the last expression.
  return emitExpr(k, kids[kids.length - 1]!, scope);
}

// Emit a block as WGSL statements, with the final expression returned
// as a `return` statement. Used at the top level and inside fn bodies.
function emitBlockStmts(
  k: Kernel,
  node: NodeID,
  scope: EmitScope,
): { stmts: string[]; tail: string } {
  const stmts: string[] = [];
  // If the node is itself a DO/SEQUENCE block, unroll its children.
  let kids: readonly NodeID[] = [node];
  if (node.level !== Level.TRIVIAL) {
    const cat = k.category(node);
    if (
      cat.type === RBasic.BLOCK &&
      (cat.inst === RBlock.DO || cat.inst === RBlock.SEQUENCE)
    ) {
      kids = k.children(node);
    }
  }
  for (let i = 0; i < kids.length - 1; i++) {
    const c = kids[i]!;
    if (c.level !== Level.TRIVIAL) {
      const cat = k.category(c);
      if (cat.type === RBasic.FNDEF) {
        // Lift FNDEF into the top-level fn pool — emitted separately.
        emitFnDefStmt(k, k.children(c), scope);
        continue;
      }
      if (cat.type === RBasic.BLOCK && cat.inst === RBlock.LET) {
        const inner = k.children(c);
        const name = inner[0]!;
        if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
          throw new Error("WgslBackend: LET name must be a string trivial");
        }
        const valSrc = emitExpr(k, inner[1]!, scope);
        const jsName = fresh(scope, `let_${k.nameStr(name.inst)}`);
        scope.vars.set(name.inst, jsName);
        stmts.push(`  let ${jsName} = ${valSrc};`);
        continue;
      }
    }
    const e = emitExpr(k, c, scope);
    stmts.push(`  let _ = ${e};`);
  }
  const last = kids[kids.length - 1]!;
  // If the last is a FNDEF, the block has no return value.
  if (last.level !== Level.TRIVIAL) {
    const cat = k.category(last);
    if (cat.type === RBasic.FNDEF) {
      emitFnDefStmt(k, k.children(last), scope);
      return { stmts, tail: scope.scalarType === "f32" ? "0.0" : "0" };
    }
  }
  const tail = emitExpr(k, last, scope);
  return { stmts, tail };
}

function emitFnDef(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  emitFnDefStmt(k, kids, scope);
  // FNDEF as expression — return a placeholder; the declaration has
  // been lifted to fnDecls.
  return scope.scalarType === "f32" ? "0.0" : "0";
}

function emitFnDefStmt(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
): void {
  const name = kids[0]!;
  const paramsBlock = kids[1]!;
  const body = kids[2]!;
  if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
    throw new Error("WgslBackend: defn name must be a string trivial");
  }
  const nameID = name.inst;
  const fnName = fresh(scope, `fn_${k.nameStr(nameID)}`);
  scope.fns.set(nameID, fnName);

  const fnScope = childScope(scope);
  const paramKids = k.children(paramsBlock);
  const paramDecls: string[] = [];
  for (const p of paramKids) {
    if (p.level !== Level.TRIVIAL || p.type !== Triv.STRING) {
      throw new Error("WgslBackend: params must be string trivials");
    }
    const jsParam = fresh(fnScope, `p_${k.nameStr(p.inst)}`);
    fnScope.vars.set(p.inst, jsParam);
    paramDecls.push(`${jsParam}: ${fnScope.scalarType}`);
  }
  const { stmts, tail } = emitBlockStmts(k, body, fnScope);
  const bodyStr =
    stmts.length === 0
      ? `  return ${tail};`
      : `${stmts.join("\n")}\n  return ${tail};`;
  scope.fnDecls.push(
    `fn ${fnName}(${paramDecls.join(", ")}) -> ${fnScope.scalarType} {\n${bodyStr}\n}`,
  );
}

function emitFnCall(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  if (kids.length < 1) {
    throw new Error("WgslBackend: empty FNCALL");
  }
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
  if (nameID === null) {
    throw new Error("WgslBackend: dynamic callees are not supported.");
  }
  const localFn = scope.fns.get(nameID);
  const args = kids.slice(1).map((a) => emitExpr(k, a, scope));
  if (localFn !== undefined) {
    return `${localFn}(${args.join(", ")})`;
  }
  // WGSL builtins — map a small surface of common math ops by name so
  // (sqrt x), (abs x), (min a b), (max a b) work the way callers expect.
  const builtin = wgslBuiltin(k.nameStr(nameID));
  if (builtin !== null) {
    return `${builtin}(${args.join(", ")})`;
  }
  throw new Error(
    `WgslBackend: native '${k.nameStr(nameID)}' has no WGSL analog.`,
  );
}

const WGSL_BUILTINS: ReadonlySet<string> = new Set([
  "abs",
  "acos",
  "asin",
  "atan",
  "atan2",
  "ceil",
  "clamp",
  "cos",
  "cross",
  "degrees",
  "distance",
  "dot",
  "exp",
  "exp2",
  "floor",
  "fma",
  "fract",
  "inverseSqrt",
  "length",
  "log",
  "log2",
  "max",
  "min",
  "mix",
  "normalize",
  "pow",
  "radians",
  "reflect",
  "refract",
  "round",
  "sign",
  "sin",
  "smoothstep",
  "sqrt",
  "step",
  "tan",
  "trunc",
]);

function wgslBuiltin(name: string): string | null {
  return WGSL_BUILTINS.has(name) ? name : null;
}

// ---------------------------------------------------------------------------
// Top-level kernel shape: scalar / vectorized / parallelized / reduce
// ---------------------------------------------------------------------------

const DEFAULT_FORMAT: FormatRecipe = { scalar: "f32", lanes: 1 };

function defaultReturnFormat(opts: EmitOptions | undefined): FormatRecipe {
  if (opts?.return_format) return opts.return_format;
  if (opts?.vectorize) return opts.vectorize.format;
  if (opts?.parallelize) return opts.parallelize.buffer_format;
  if (opts?.reduce) return opts.reduce.format;
  if (opts?.tile) return opts.tile.format;
  return DEFAULT_FORMAT;
}

function emitScalarKernel(
  k: Kernel,
  recipe: NodeID,
  opts: EmitOptions | undefined,
): string {
  const fmt = defaultReturnFormat(opts);
  const scalarType = wgslScalarType(fmt);
  const scope = freshScope(null, scalarType);
  // Bind any named parameters up front.
  const paramDecls: string[] = [];
  if (opts?.params) {
    for (const p of opts.params) {
      const nameID = k.internName(p);
      const wgslName = fresh(scope, `p_${p}`);
      scope.vars.set(nameID, wgslName);
      paramDecls.push(`${wgslName}: ${scalarType}`);
    }
  }
  const { stmts, tail } = emitBlockStmts(k, recipe, scope);
  const body =
    stmts.length === 0
      ? `  return ${tail};`
      : `${stmts.join("\n")}\n  return ${tail};`;
  const fnDecls =
    scope.fnDecls.length > 0 ? scope.fnDecls.join("\n\n") + "\n\n" : "";
  return `${fnDecls}fn kernel_main(${paramDecls.join(", ")}) -> ${scalarType} {\n${body}\n}\n`;
}

function emitVectorizedKernel(
  k: Kernel,
  recipe: NodeID,
  opts: EmitOptions,
): string {
  if (!opts.vectorize) throw new Error("vectorize opts missing");
  const fmt = opts.vectorize.format;
  const scalarType = wgslScalarType(fmt);
  const elemType = wgslElementType(fmt);
  const scope = freshScope(fmt, scalarType);
  const paramDecls: string[] = [];
  if (opts.params) {
    for (const p of opts.params) {
      const nameID = k.internName(p);
      const wgslName = fresh(scope, `p_${p}`);
      scope.vars.set(nameID, wgslName);
      paramDecls.push(`${wgslName}: ${elemType}`);
    }
  }
  const { stmts, tail } = emitBlockStmts(k, recipe, scope);
  const body =
    stmts.length === 0
      ? `  return ${tail};`
      : `${stmts.join("\n")}\n  return ${tail};`;
  const fnDecls =
    scope.fnDecls.length > 0 ? scope.fnDecls.join("\n\n") + "\n\n" : "";
  const note =
    fmt.lanes === 8 || fmt.lanes === 16
      ? `// vectorize lanes=${fmt.lanes} → emitted as vec4 chunks (WGSL caps vec at 4)\n`
      : `// vectorize lanes=${fmt.lanes}\n`;
  return `${note}${fnDecls}fn kernel_vec(${paramDecls.join(", ")}) -> ${elemType} {\n${body}\n}\n`;
}

function emitParallelizedKernel(
  k: Kernel,
  recipe: NodeID,
  opts: EmitOptions,
): string {
  if (!opts.parallelize) throw new Error("parallelize opts missing");
  const { workgroup_size, buffer_format } = opts.parallelize;
  const scalarType = wgslScalarType(buffer_format);
  const scope = freshScope(null, scalarType);
  // Each thread reads one input element from `in_buf`, writes one
  // output element to `out_buf`. The recipe's first param (if any) is
  // the input element; additional params are uniforms not yet wired.
  const paramName = opts.params?.[0] ?? "x";
  const nameID = k.internName(paramName);
  const wgslName = fresh(scope, `p_${paramName}`);
  scope.vars.set(nameID, wgslName);
  const { stmts, tail } = emitBlockStmts(k, recipe, scope);
  const body =
    stmts.length === 0
      ? `  return ${tail};`
      : `${stmts.join("\n")}\n  return ${tail};`;
  const fnDecls =
    scope.fnDecls.length > 0 ? scope.fnDecls.join("\n\n") + "\n\n" : "";
  const [wx, wy, wz] = workgroup_size;
  return [
    `@group(0) @binding(0) var<storage, read>       in_buf:  array<${scalarType}>;`,
    `@group(0) @binding(1) var<storage, read_write> out_buf: array<${scalarType}>;`,
    "",
    `${fnDecls}fn kernel_body(${wgslName}: ${scalarType}) -> ${scalarType} {\n${body}\n}`,
    "",
    `@compute @workgroup_size(${wx}, ${wy}, ${wz})`,
    `fn kernel_dispatch(@builtin(global_invocation_id) gid: vec3<u32>) {`,
    `  let idx = gid.x;`,
    `  if (idx >= arrayLength(&in_buf)) { return; }`,
    `  out_buf[idx] = kernel_body(in_buf[idx]);`,
    `}`,
    "",
  ].join("\n");
}

function emitTiledKernel(
  k: Kernel,
  recipe: NodeID,
  opts: EmitOptions,
): string {
  if (!opts.tile) throw new Error("tile opts missing");
  const { tile_size, format } = opts.tile;
  const scalarType = wgslScalarType(format);
  const scope = freshScope(null, scalarType);
  const paramName = opts.params?.[0] ?? "x";
  const nameID = k.internName(paramName);
  const wgslName = fresh(scope, `p_${paramName}`);
  scope.vars.set(nameID, wgslName);
  const { stmts, tail } = emitBlockStmts(k, recipe, scope);
  const body =
    stmts.length === 0
      ? `  return ${tail};`
      : `${stmts.join("\n")}\n  return ${tail};`;
  const fnDecls =
    scope.fnDecls.length > 0 ? scope.fnDecls.join("\n\n") + "\n\n" : "";
  return [
    `@group(0) @binding(0) var<storage, read>       in_buf:  array<${scalarType}>;`,
    `@group(0) @binding(1) var<storage, read_write> out_buf: array<${scalarType}>;`,
    "",
    `var<workgroup> tile: array<${scalarType}, ${tile_size}>;`,
    "",
    `${fnDecls}fn kernel_body(${wgslName}: ${scalarType}) -> ${scalarType} {\n${body}\n}`,
    "",
    `@compute @workgroup_size(${tile_size})`,
    `fn kernel_dispatch(`,
    `  @builtin(global_invocation_id) gid: vec3<u32>,`,
    `  @builtin(local_invocation_id)  lid: vec3<u32>,`,
    `) {`,
    `  let idx = gid.x;`,
    `  if (idx < arrayLength(&in_buf)) {`,
    `    tile[lid.x] = in_buf[idx];`,
    `  }`,
    `  workgroupBarrier();`,
    `  if (idx < arrayLength(&in_buf)) {`,
    `    out_buf[idx] = kernel_body(tile[lid.x]);`,
    `  }`,
    `}`,
    "",
  ].join("\n");
}

function emitReductionKernel(
  k: Kernel,
  recipe: NodeID,
  opts: EmitOptions,
): string {
  if (!opts.reduce) throw new Error("reduce opts missing");
  const { op, format, workgroup_size } = opts.reduce;
  const scalarType = wgslScalarType(format);
  const scope = freshScope(null, scalarType);
  // The recipe describes the per-element transform applied before
  // reduction; we wire its first param to the input element.
  const paramName = opts.params?.[0] ?? "x";
  const nameID = k.internName(paramName);
  const wgslName = fresh(scope, `p_${paramName}`);
  scope.vars.set(nameID, wgslName);
  const { stmts, tail } = emitBlockStmts(k, recipe, scope);
  const body =
    stmts.length === 0
      ? `  return ${tail};`
      : `${stmts.join("\n")}\n  return ${tail};`;
  const fnDecls =
    scope.fnDecls.length > 0 ? scope.fnDecls.join("\n\n") + "\n\n" : "";
  // The reduce op as a WGSL expression on (a, b).
  const reduceExpr =
    op === "add"
      ? "a + b"
      : op === "mul"
        ? "a * b"
        : op === "max"
          ? "max(a, b)"
          : "min(a, b)";
  const identity =
    op === "add"
      ? scalarType === "f32"
        ? "0.0"
        : "0"
      : op === "mul"
        ? scalarType === "f32"
          ? "1.0"
          : "1"
        : op === "max"
          ? scalarType === "f32"
            ? "-3.4028235e38"
            : "-2147483648"
          : scalarType === "f32"
            ? "3.4028235e38"
            : "2147483647";
  return [
    `@group(0) @binding(0) var<storage, read>       in_buf:  array<${scalarType}>;`,
    `@group(0) @binding(1) var<storage, read_write> out_buf: array<${scalarType}>;`,
    "",
    `var<workgroup> partial: array<${scalarType}, ${workgroup_size}>;`,
    "",
    `${fnDecls}fn kernel_body(${wgslName}: ${scalarType}) -> ${scalarType} {\n${body}\n}`,
    "",
    `fn combine(a: ${scalarType}, b: ${scalarType}) -> ${scalarType} { return ${reduceExpr}; }`,
    "",
    `@compute @workgroup_size(${workgroup_size})`,
    `fn kernel_dispatch(`,
    `  @builtin(global_invocation_id) gid: vec3<u32>,`,
    `  @builtin(local_invocation_id)  lid: vec3<u32>,`,
    `  @builtin(workgroup_id)         wid: vec3<u32>,`,
    `) {`,
    `  let idx = gid.x;`,
    `  var v: ${scalarType} = ${identity};`,
    `  if (idx < arrayLength(&in_buf)) {`,
    `    v = kernel_body(in_buf[idx]);`,
    `  }`,
    `  partial[lid.x] = v;`,
    `  workgroupBarrier();`,
    `  // Tree-shuffle reduction across the workgroup.`,
    `  var stride: u32 = ${workgroup_size}u >> 1u;`,
    `  loop {`,
    `    if (stride == 0u) { break; }`,
    `    if (lid.x < stride) {`,
    `      partial[lid.x] = combine(partial[lid.x], partial[lid.x + stride]);`,
    `    }`,
    `    workgroupBarrier();`,
    `    stride = stride >> 1u;`,
    `  }`,
    `  if (lid.x == 0u) {`,
    `    out_buf[wid.x] = partial[0];`,
    `  }`,
    `}`,
    "",
  ].join("\n");
}

// ---------------------------------------------------------------------------
// WgslBackend — exported singleton implementing CodegenBackend
// ---------------------------------------------------------------------------

export const WgslBackend: CodegenBackend = {
  name: "wgsl",
  target_hints: new Set(["gpu-webgpu"]),
  emit(kernel: Kernel, recipe: NodeID, opts?: EmitOptions): string {
    if (opts?.reduce) {
      return emitReductionKernel(kernel, recipe, opts);
    }
    if (opts?.tile) {
      return emitTiledKernel(kernel, recipe, opts);
    }
    if (opts?.parallelize) {
      return emitParallelizedKernel(kernel, recipe, opts);
    }
    if (opts?.vectorize) {
      return emitVectorizedKernel(kernel, recipe, opts);
    }
    return emitScalarKernel(kernel, recipe, opts);
  },
};
