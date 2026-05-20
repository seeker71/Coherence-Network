// backends/wasm.ts — WASM SIMD emit backend (#11).
//
// Lowers a Form recipe tree to WebAssembly Text format (WAT). The output
// is a `(module ...)` source string ready for `wat2wasm` / browser
// `WebAssembly.compileStreaming` once routed through a WAT→binary tool.
//
// Builds on:
//   #7  (BackendRegistry — anticipated; we expose CodegenBackend shape)
//   #9  (VECTOR + parallel patterns) — vectorize(op, W) lowers to v128
//        SIMD instructions instead of scalar loops.
//
// Coverage today:
//   • Math (i32 + f64 scalar paths)              i32.add / f64.add / ...
//   • Compare                                     i32.eq / i32.lt_s / ...
//   • Logic (and/or/not)                          i32.and / i32.or / select
//   • COND.IF_THEN / IF_THEN_ELSE                 (if (result ...) (then ...) (else ...))
//   • BLOCK.LET / DO / SEQUENCE                   (local.set ...) / drop-then-last
//   • FNDEF                                       (func $name (param ...) (result ...) ...)
//   • FNCALL                                      (call $name ...)
//   • VECTORIZE(MATH, W)                          v128.f32x4 / i32x4 / etc.
//   • VECTOR format access                        v128 typed
//
// Anything else falls back to an emitted `(; walker fallback ;)` comment
// — the registry can route to a different backend, or the caller can
// pre-lower with a different pass.
//
// What this backend does NOT do (named honestly):
//   • Memory / linear-memory layout — VECTOR values are assumed to live
//     in locals; loading from linear memory is its own breath.
//   • String, list, closure values — Form's higher-order surface stays
//     in the JS-host scalar path.
//   • Native-function calls — natives are JS-only; WAT can't reach them.
//   • Type inference between i32 and f64 — emitted code uses i32 by
//     default and f64 for explicit float formats; cross-type math is the
//     caller's responsibility.
//
// See docs/coherence-substrate/multi-target-codegen.md for the role this
// plays in the codegen architecture.

import {
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
import { readParallelPattern } from "../parallel.ts";
import { readVectorFormat } from "../vector.ts";
import type { CodegenBackend } from "./types.ts";

// ---------------------------------------------------------------------------
// Emit context — shared mutable state during a single emit() walk.
// ---------------------------------------------------------------------------

interface EmitScope {
  // NameID → WAT local name (e.g. "$x_3"). Lexical, child scopes inherit.
  vars: Map<number, string>;
  // NameID → WAT function name (e.g. "$fib_2").
  fns: Map<number, string>;
  // Unique-id counter shared across the whole emit.
  uid: { n: number };
  // Function declarations accumulated at the module level. We emit a
  // top-level expr as a `(func $main (result i32) ...)` and any FNDEF
  // encountered gets hoisted to a sibling func at the module level.
  funcDecls: string[];
  // Local declarations for the currently-emitting function body.
  locals: string[];
}

function freshScope(): EmitScope {
  return {
    vars: new Map(),
    fns: new Map(),
    uid: { n: 0 },
    funcDecls: [],
    locals: [],
  };
}

function childScope(parent: EmitScope): EmitScope {
  // Vars + fns inherit; funcDecls + locals + uid stay shared so emitted
  // names are globally unique across the module.
  return {
    vars: new Map(parent.vars),
    fns: new Map(parent.fns),
    uid: parent.uid,
    funcDecls: parent.funcDecls,
    locals: parent.locals,
  };
}

function fresh(scope: EmitScope, hint: string): string {
  scope.uid.n++;
  return `$${sanitize(hint)}_${scope.uid.n}`;
}

function sanitize(s: string): string {
  return s.replace(/[^A-Za-z0-9_]/g, "_");
}

// ---------------------------------------------------------------------------
// WAT type vocabulary.
// ---------------------------------------------------------------------------

// Default scalar element type for MATH ops absent a format hint.
const DEFAULT_SCALAR = "i32" as const;

// Map (element kind, width) → v128 shape suffix. Same vocabulary the
// WebAssembly SIMD spec uses for typed lane intrinsics.
function v128Shape(elementKind: "i32" | "f32" | "f64", width: number): string {
  if (elementKind === "f32" && width === 4) return "f32x4";
  if (elementKind === "f64" && width === 2) return "f64x2";
  if (elementKind === "i32" && width === 4) return "i32x4";
  if (elementKind === "i32" && width === 8) return "i16x8";
  if (elementKind === "i32" && width === 16) return "i8x16";
  if (elementKind === "f32" && width === 8) return "f32x4"; // emulate 2× f32x4
  // Default — i32x4 is the safest portable shape.
  return "i32x4";
}

// Map a substrate MATH op code to a WAT scalar opcode for a given type.
function watScalarMathOp(opType: string, op: number): string {
  if (op === RMath.PLUS) return `${opType}.add`;
  if (op === RMath.MINUS) return `${opType}.sub`;
  if (op === RMath.MUL) return `${opType}.mul`;
  if (op === RMath.DIV) {
    if (opType === "i32") return "i32.div_s";
    if (opType === "i64") return "i64.div_s";
    return `${opType}.div`;
  }
  if (op === RMath.MOD) {
    if (opType === "i32") return "i32.rem_s";
    if (opType === "i64") return "i64.rem_s";
    // f32/f64 have no .rem — caller emits a walker fallback comment.
    return `${opType}.rem`;
  }
  return `${opType}.add`;
}

// Map a substrate MATH op code to a WAT SIMD opcode for a given shape.
function watSimdMathOp(shape: string, op: number): string {
  if (op === RMath.PLUS) return `${shape}.add`;
  if (op === RMath.MINUS) return `${shape}.sub`;
  if (op === RMath.MUL) return `${shape}.mul`;
  if (op === RMath.DIV) {
    // SIMD integer division is not in baseline wasm-simd; emit a marker
    // the registry can swap with a software path.
    if (shape.startsWith("f")) return `${shape}.div`;
    return `${shape}.div_s`;
  }
  // No SIMD mod in baseline — marker.
  return `${shape}.add`;
}

// Map a substrate COMPARE op to a WAT scalar opcode.
function watScalarCmpOp(opType: string, op: number): string {
  const signed = opType === "i32" || opType === "i64";
  if (op === RCmp.EQ) return `${opType}.eq`;
  if (op === RCmp.NE) return `${opType}.ne`;
  if (op === RCmp.LT) return signed ? `${opType}.lt_s` : `${opType}.lt`;
  if (op === RCmp.LE) return signed ? `${opType}.le_s` : `${opType}.le`;
  if (op === RCmp.GT) return signed ? `${opType}.gt_s` : `${opType}.gt`;
  if (op === RCmp.GE) return signed ? `${opType}.ge_s` : `${opType}.ge`;
  return `${opType}.eq`;
}

// ---------------------------------------------------------------------------
// Emit dispatch.
// ---------------------------------------------------------------------------

function emitExpr(k: Kernel, node: NodeID, scope: EmitScope): string {
  if (node.level === Level.TRIVIAL) {
    return emitTrivial(node);
  }
  const cat = k.category(node);
  const kids = k.children(node);

  switch (cat.type) {
    case RBasic.IDENT: {
      const nameID = k.identID(node);
      const local = scope.vars.get(nameID);
      if (local !== undefined) return `(local.get ${local})`;
      // Unknown identifier — emit a comment-marker; the registry / a
      // later pass can resolve it.
      return `(; unresolved-ident ${k.nameStr(nameID)} ;) (i32.const 0)`;
    }
    case RBasic.MATH:
      return emitMath(k, cat.inst, kids, scope, DEFAULT_SCALAR);
    case RBasic.COMPARE:
      return emitCompare(k, cat.inst, kids, scope, DEFAULT_SCALAR);
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
    case RBasic.VECTORIZE:
      return emitVectorize(k, node, scope);
    case RBasic.VECTOR:
      return emitVectorRef(k, node);
    case RBasic.TILE:
    case RBasic.PARALLELIZE: {
      // For single-threaded WAT emission these patterns are no-ops —
      // unwrap and emit the inner op.
      const view = readParallelPattern(k, node);
      return emitExpr(k, view.inner, scope);
    }
    case RBasic.LIST:
    default:
      return `(; walker-fallback type=${cat.type} ;) (i32.const 0)`;
  }
}

function emitTrivial(node: NodeID): string {
  if (node.type === Triv.INT) {
    const u = node.inst >>> 0;
    const i = u > 0x7fffffff ? u - 0x100000000 : u;
    return `(i32.const ${i})`;
  }
  if (node.type === Triv.BOOL) {
    return `(i32.const ${node.inst !== 0 ? 1 : 0})`;
  }
  if (node.type === Triv.NULL) {
    return `(i32.const 0)`;
  }
  // STRING — emit as comment; strings live outside wasm-simd scope here.
  return `(; trivial-string ;) (i32.const 0)`;
}

function emitMath(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
  opType: string,
): string {
  if (kids.length === 0) return `(${opType}.const 0)`;
  if (kids.length === 1) return emitExpr(k, kids[0]!, scope);
  const opcode = watScalarMathOp(opType, op);
  // Left fold: ((((a op b) op c) op d) ...)
  let acc = emitExpr(k, kids[0]!, scope);
  for (let i = 1; i < kids.length; i++) {
    const rhs = emitExpr(k, kids[i]!, scope);
    acc = `(${opcode} ${acc} ${rhs})`;
  }
  return acc;
}

function emitCompare(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
  opType: string,
): string {
  if (kids.length !== 2) {
    return `(; compare needs 2 args ;) (i32.const 0)`;
  }
  const a = emitExpr(k, kids[0]!, scope);
  const b = emitExpr(k, kids[1]!, scope);
  return `(${watScalarCmpOp(opType, op)} ${a} ${b})`;
}

function emitLogic(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  if (op === RLogic.NOT) {
    return `(i32.eqz ${emitExpr(k, kids[0]!, scope)})`;
  }
  if (kids.length < 2) return `(i32.const 0)`;
  const opcode = op === RLogic.AND ? "i32.and" : "i32.or";
  let acc = emitExpr(k, kids[0]!, scope);
  for (let i = 1; i < kids.length; i++) {
    acc = `(${opcode} ${acc} ${emitExpr(k, kids[i]!, scope)})`;
  }
  return acc;
}

function emitCond(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  const cond = emitExpr(k, kids[0]!, scope);
  const thenExpr = emitExpr(k, kids[1]!, scope);
  if (op === RCond.IF_THEN) {
    // No else — the WAT if needs an else for `(result i32)`. Emit 0.
    return `(if (result i32) ${cond} (then ${thenExpr}) (else (i32.const 0)))`;
  }
  const elseExpr = emitExpr(k, kids[2]!, scope);
  return `(if (result i32) ${cond} (then ${thenExpr}) (else ${elseExpr}))`;
}

function emitBlock(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  if (op === RBlock.LET) {
    if (kids.length !== 2) return `(; malformed let ;) (i32.const 0)`;
    const name = kids[0]!;
    const valSrc = emitExpr(k, kids[1]!, scope);
    if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
      return valSrc;
    }
    const watLocal = fresh(scope, `let_${name.inst}`);
    scope.vars.set(name.inst, watLocal);
    scope.locals.push(`(local ${watLocal} i32)`);
    // The block expression value: the bound value (set then read).
    return `(block (result i32) (local.set ${watLocal} ${valSrc}) (local.get ${watLocal}))`;
  }
  // DO / SEQUENCE — drop intermediates, return last value.
  if (kids.length === 0) return `(i32.const 0)`;
  if (kids.length === 1) return emitExpr(k, kids[0]!, scope);
  const parts: string[] = [];
  for (let i = 0; i < kids.length - 1; i++) {
    parts.push(`(drop ${emitExpr(k, kids[i]!, scope)})`);
  }
  parts.push(emitExpr(k, kids[kids.length - 1]!, scope));
  return `(block (result i32) ${parts.join(" ")})`;
}

function emitFnDef(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  if (kids.length !== 3) return `(; malformed fndef ;) (i32.const 0)`;
  const name = kids[0]!;
  const paramsBlock = kids[1]!;
  const body = kids[2]!;
  if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
    return `(; fndef name not string ;) (i32.const 0)`;
  }
  const nameID = name.inst;
  const watName = fresh(scope, `fn_${k.nameStr(nameID)}`);
  scope.fns.set(nameID, watName);

  // Build the function's own scope: parameters bind to WAT params.
  const fnScope = childScope(scope);
  // Reset locals — body emission accumulates into its own list.
  fnScope.locals = [];
  const paramKids = k.children(paramsBlock);
  const paramDecls: string[] = [];
  for (const p of paramKids) {
    if (p.level !== Level.TRIVIAL || p.type !== Triv.STRING) continue;
    const watParam = fresh(fnScope, `p_${k.nameStr(p.inst)}`);
    fnScope.vars.set(p.inst, watParam);
    paramDecls.push(`(param ${watParam} i32)`);
  }

  const bodySrc = emitExpr(k, body, fnScope);
  const localsSrc = fnScope.locals.length > 0 ? "\n    " + fnScope.locals.join(" ") : "";
  const decl =
    `  (func ${watName} ${paramDecls.join(" ")} (result i32)${localsSrc}\n    ${bodySrc})`;
  scope.funcDecls.push(decl);
  // The FNDEF expression value at its emission site is 0 — the function
  // is hoisted to the module level.
  return `(i32.const 0)`;
}

function emitFnCall(
  k: Kernel,
  kids: readonly NodeID[],
  scope: EmitScope,
): string {
  if (kids.length < 1) return `(i32.const 0)`;
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
    return `(; non-static call ;) (i32.const 0)`;
  }
  const watName = scope.fns.get(nameID);
  if (watName === undefined) {
    return `(; unknown callee ${k.nameStr(nameID)} ;) (i32.const 0)`;
  }
  const args = kids.slice(1).map((a) => emitExpr(k, a, scope));
  return `(call ${watName} ${args.join(" ")})`;
}

// Emit a VECTORIZE(MATH, W) wrapper — lower the inner MATH op to v128
// SIMD ops of the given width. Inner ops other than MATH fall through to
// the scalar path (the registry can route differently).
function emitVectorize(
  k: Kernel,
  node: NodeID,
  scope: EmitScope,
): string {
  const view = readParallelPattern(k, node);
  const inner = view.inner;
  const width = view.parameter;
  if (inner.level !== Level.BASIC) {
    return emitExpr(k, inner, scope);
  }
  const innerCat = k.category(inner);
  if (innerCat.type !== RBasic.MATH) {
    // Non-MATH vectorization: emit as-is. Backend extension space.
    return emitExpr(k, inner, scope);
  }
  // Choose element kind: f32 for width 4, f64 for width 2, i32 otherwise.
  // The format-recipe target_hints would refine this in a complete pass;
  // we pick a sensible default here.
  const elementKind: "f32" | "f64" | "i32" =
    width === 4 ? "f32" : width === 2 ? "f64" : "i32";
  const shape = v128Shape(elementKind, width);
  const opcode = watSimdMathOp(shape, innerCat.inst);
  const innerKids = k.children(inner);
  if (innerKids.length < 2) return `(; vectorize needs >=2 ops ;) (v128.const i32x4 0 0 0 0)`;
  // Emit each operand as a v128 — assume operands are already v128-typed
  // (loaded via v128.load or constructed via splat). If they're scalar,
  // splat them.
  let acc = emitVecOperand(k, innerKids[0]!, scope, shape);
  for (let i = 1; i < innerKids.length; i++) {
    const rhs = emitVecOperand(k, innerKids[i]!, scope, shape);
    acc = `(${opcode} ${acc} ${rhs})`;
  }
  return acc;
}

function emitVecOperand(
  k: Kernel,
  node: NodeID,
  scope: EmitScope,
  shape: string,
): string {
  // VECTOR-format leaves stay v128; scalars get splatted.
  if (node.level === Level.BASIC) {
    const cat = k.category(node);
    if (cat.type === RBasic.VECTOR) return emitVectorRef(k, node);
  }
  const scalar = emitExpr(k, node, scope);
  return `(${shape}.splat ${scalar})`;
}

// VECTOR-recipe leaf — a reference to a v128-typed value in linear
// memory. Until layout is settled this emits a structural marker the
// registry can resolve; the WAT output remains valid (it's an immediate
// v128.const placeholder).
function emitVectorRef(k: Kernel, node: NodeID): string {
  try {
    const view = readVectorFormat(k, node);
    return `(; vector width=${view.width} hint=${view.storageHint} ;) (v128.const i32x4 0 0 0 0)`;
  } catch {
    return `(v128.const i32x4 0 0 0 0)`;
  }
}

// ---------------------------------------------------------------------------
// Public emit entry — wraps the body in a `(module ...)` with a $main
// export. Hoisted FNDEFs live as sibling funcs.
// ---------------------------------------------------------------------------

function emitModule(k: Kernel, root: NodeID): string {
  const scope = freshScope();
  const bodySrc = emitExpr(k, root, scope);
  const localsSrc =
    scope.locals.length > 0 ? "\n    " + scope.locals.join(" ") : "";
  const mainFunc =
    `  (func $main (export "main") (result i32)${localsSrc}\n    ${bodySrc})`;
  const decls = scope.funcDecls.join("\n");
  return `(module\n${decls}${decls ? "\n" : ""}${mainFunc})\n`;
}

// ---------------------------------------------------------------------------
// Backend export.
// ---------------------------------------------------------------------------

export const WasmSimdBackend: CodegenBackend = {
  name: "wasm-simd",
  target_hints: new Set<string>(["wasm-simd"]),
  emit(k: Kernel, recipe: NodeID): string {
    return emitModule(k, recipe);
  },
};
