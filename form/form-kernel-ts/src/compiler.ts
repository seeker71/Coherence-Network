// Recipe → JS compiler — the two-order-of-magnitude unlock.
//
// The tree-walking kernel pays ~500-2000× native overhead per step because
// every dispatch is a Map lookup + function call + Value allocation. The
// compiler lifts the recipe tree into a JS function via `new Function`,
// emitting direct arithmetic that V8 can JIT to ~near-native speed.
//
// Architecture:
//
//   compileNode(kernel, root)
//     → walks the NodeID tree
//     → emits a JS source string per FNDEF body and per top-level expr
//     → wraps in `new Function(src)` once
//     → returns a CompiledFn = (frame) => Value
//
//   Inside the generated JS:
//     • Function parameters live as raw JS variables (no Value-boxing).
//     • Local FNDEFs become local JS function declarations — V8 JITs them.
//     • Arithmetic on raw numbers stays raw (a + b) | 0.
//     • Comparisons return raw bool.
//     • (list a b c) constructs a Value{kind:"list", ...} inline; items
//       get boxAny'd at the boundary.
//     • Chained (let x ...) inside a do-block declares JS `const` at IIFE
//       statement level so later siblings resolve directly to the JS var,
//       no frame.lookup.
//     • The top-level result gets boxed back into a Value at the boundary.
//     • Closure-over-outer-frame names fall back to frame.lookup — the
//       slow path. The fast path is pure arithmetic + locally-defined fns.
//
// What the compiler can NOT do (falls back to walker):
//     • Reflection over substrate (intern_node, walk_recipe, etc.)
//     • Free IDENT references to frame variables (e.g. dynamic closures
//       over outer state) — supported via frame.lookup but slow
//     • Categories outside the handled set (WITNESS, CALL, ACCESS,
//       METHOD, TRANSMUTE, INDUCTIVE, CONSTRUCTOR, CHOICE, QUOTIENT,
//       ALIAS) — fall through to the walker fallback for now.
//
// For the bench cases (fib28, fact12, sum1000, ackermann) the compiler
// emits straight-line recursive JS that's structurally identical to the
// native reference. V8 JITs both to comparable native code; the kernel
// overhead approaches the runtime cost of one boxed-Value return at the
// outermost boundary, plus the parameter-extraction at entry.

import {
  Frame,
  Kernel,
  Level,
  mathOp,
  mathWidth,
  RBasic,
  RBlock,
  RCmp,
  RCond,
  RLogic,
  RMath,
  RMathWidth,
  Triv,
  type NodeID,
  type Value,
  walk,
} from "./kernel.ts";

export type CompiledFn = (frame: Frame) => Value;

interface CompileScope {
  // Parameters in scope, mapped to their JS variable name.
  vars: Map<number, string>;
  // Locally-defined functions in scope, mapped to JS variable name.
  fns: Map<number, string>;
  // Counter for unique JS var names.
  uid: { n: number };
}

function freshScope(): CompileScope {
  return { vars: new Map(), fns: new Map(), uid: { n: 0 } };
}

function childScope(parent: CompileScope): CompileScope {
  return {
    vars: new Map(parent.vars),
    fns: new Map(parent.fns),
    uid: parent.uid,
  };
}

function fresh(scope: CompileScope, hint: string): string {
  scope.uid.n++;
  return `${sanitize(hint)}_${scope.uid.n}`;
}

function sanitize(s: string): string {
  return s.replace(/[^A-Za-z0-9_$]/g, "_");
}

// Top-level entry point.
export function compileNode(k: Kernel, root: NodeID): CompiledFn {
  const scope = freshScope();
  const body = emitExpr(k, root, scope);
  // The generated function takes a Frame at the boundary, may use it for
  // unbound-name lookups (rare in compiled code), and returns a Value.
  // We inject `kernel` and `walk` and helpers via closure capture from
  // the compileNode call.
  const src = `
    "use strict";
    return (function compiledRoot(frame) {
      const result = ${body};
      return ${emitBox(body, "result")};
    });
  `;
  // We need to provide the runtime environment to the generated code.
  // Capture the kernel and natives via a wrapping closure rather than
  // passing them as arguments to every call — they're constants for the
  // lifetime of the compiled fn.
  const factory = new Function(
    "k",
    "walk",
    "Frame",
    "lookupName",
    "callNative",
    "callFreeFn",
    "valueAsInt",
    "valueAsBool",
    "valueAsNum",
    "boxInt",
    "boxBool",
    "boxNull",
    "boxFloat",
    "boxBig",
    "boxAny",
    src,
  );
  return factory(
    k,
    walk,
    Frame,
    lookupName,
    callNative,
    callFreeFn,
    valueAsInt,
    valueAsBool,
    valueAsNum,
    boxInt,
    boxBool,
    boxNull,
    boxFloat,
    boxBig,
    boxAny,
  ) as CompiledFn;
}

// Runtime helpers injected into the generated function's scope.
function lookupName(frame: Frame, nameID: number): Value {
  const v = frame.lookup(nameID);
  if (v === undefined) {
    throw new Error(`unbound identifier: name#${nameID}`);
  }
  return v;
}

function callNative(
  k: Kernel,
  nameID: number,
  args: Value[],
): Value {
  const ne = k.natives.get(nameID);
  if (ne === undefined) {
    throw new Error(`no such native: name#${nameID}`);
  }
  return ne.fn(k, args);
}

// callFreeFn — runtime helper for emitFnCall's free-fn fallback path.
// Looks up the closure under nameID in the caller's frame, binds args
// to the closure's params, and walks the body. If the body itself has
// been JIT-compiled (in kernel.jitCompiled), dispatches through the
// compiled fn instead — so recursive recipes stay JIT'd through every
// recursion level.
function callFreeFn(
  k: Kernel,
  frame: Frame,
  nameID: number,
  args: Value[],
): Value {
  const v = frame.lookup(nameID);
  if (v === undefined) throw new Error(`callFreeFn: unbound name#${nameID}`);
  if (v.kind !== "closure") {
    throw new Error(`callFreeFn: name#${nameID} is not a closure (got ${v.kind})`);
  }
  const cl = v.closure;
  if (args.length !== cl.params.length) {
    throw new Error(
      `callFreeFn: name#${nameID} arity mismatch (expected ${cl.params.length}, got ${args.length})`,
    );
  }
  const cf = new Frame(cl.env);
  for (let i = 0; i < cl.params.length; i++) cf.bind(cl.params[i]!, args[i]!);
  const bodyKey = `${cl.body.pkg}.${cl.body.level}.${cl.body.type}.${cl.body.inst}`;
  const compiled = k.jitCompiled.get(bodyKey);
  if (compiled !== undefined) return compiled(cf);
  return walk(k, cl.body, cf);
}

function valueAsInt(v: Value): number {
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return v.int;
  if (v.kind === "f32" || v.kind === "f64") return v.float | 0;
  if (v.kind === "i64" || v.kind === "u64") return Number(v.bigint);
  throw new Error(`expected int, got ${v.kind}`);
}

function valueAsBool(v: Value): boolean {
  if (v.kind === "bool") return v.bool;
  throw new Error(`expected bool, got ${v.kind}`);
}

// Generic primitive extractor — returns raw JS number / bigint / bool /
// string / null for scalar Value kinds, or passes the Value through
// unchanged for composite kinds (list / closure / nodeid / ctor). The
// downstream consumer (typically boxAny on the next call site, or the
// top-level emitBox at the boundary) recognizes Value shapes and forwards
// them, so a list returned from a free-fn or native crosses the compiled
// boundary intact.
function valueAsNum(
  v: Value,
): number | bigint | boolean | null | string | Value {
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return v.int;
  if (v.kind === "f32" || v.kind === "f64") return v.float;
  if (v.kind === "i64" || v.kind === "u64") return v.bigint;
  if (v.kind === "bool") return v.bool;
  if (v.kind === "str") return v.str;
  if (v.kind === "null") return null;
  // list / closure / nodeid / ctor — pass the Value through; downstream
  // boxAny / emitBox recognize Value-shapes and forward them unchanged.
  return v;
}

// Generic boxer — wraps a raw JS primitive into the smallest fitting Value.
function boxAny(x: number | bigint | boolean | null | string | Value): Value {
  if (typeof x === "number") {
    if (Number.isInteger(x) && Math.abs(x) < 0x80000000) {
      return { kind: "int", int: x };
    }
    return { kind: "f64", float: x };
  }
  if (typeof x === "bigint") return { kind: "i64", bigint: x };
  if (typeof x === "boolean") return { kind: "bool", bool: x };
  if (typeof x === "string") return { kind: "str", str: x };
  if (x === null) return { kind: "null" };
  return x;
}

function boxInt(n: number): Value {
  return { kind: "int", int: n | 0 };
}

function boxBool(b: boolean): Value {
  return { kind: "bool", bool: b };
}

function boxNull(): Value {
  return { kind: "null" };
}

function boxFloat(n: number): Value {
  return { kind: "f64", float: n };
}

function boxBig(n: bigint): Value {
  return { kind: "i64", bigint: n };
}

// emitExpr returns a JS source string. The expression's type is inferred
// structurally — pure-numeric subtrees emit raw JS that V8 JITs natively.
// Boundary-crossing emissions (entering/leaving the compiled scope) get
// boxed/unboxed through helpers.
function emitExpr(k: Kernel, node: NodeID, scope: CompileScope): string {
  if (node.level === Level.TRIVIAL) {
    return emitTrivial(node, k);
  }
  const cat = k.category(node);
  const kids = k.children(node);

  switch (cat.type) {
    case RBasic.IDENT: {
      const nameID = k.identID(node);
      const local = scope.vars.get(nameID) ?? scope.fns.get(nameID);
      if (local !== undefined) return local;
      // Frame lookup fallback
      return `valueAsInt(lookupName(frame, ${nameID}))`;
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
    case RBasic.LIST: {
      // (list a b c) → a Value{kind:"list", list:[boxAny(a), boxAny(b), ...]}.
      // Each element gets boxAny'd at the boundary — raw JS numbers/bools
      // become Value{kind:"int"|"bool"|...}, existing Values pass through.
      // The result is itself a Value, so callers that consume lists (e.g.
      // natives with list args) receive a properly-shaped object.
      const items = kids.map((c) => `boxAny(${emitExpr(k, c, scope)})`);
      return `({ kind: "list", list: [${items.join(", ")}] })`;
    }
    default:
      return emitWalkerFallback(node);
  }
}

function emitTrivial(node: NodeID, k?: Kernel): string {
  if (node.type === Triv.INT32) {
    const u = node.inst >>> 0;
    const i = u > 0x7fffffff ? u - 0x100000000 : u;
    return String(i);
  }
  if (node.type === Triv.BOOL) {
    return node.inst !== 0 ? "true" : "false";
  }
  if (node.type === Triv.NULL) {
    return "null";
  }
  // FLOAT32 — inline IEEE bits as a literal.
  if (node.type === Triv.FLOAT32) {
    const buf = new ArrayBuffer(4);
    new Uint32Array(buf)[0] = node.inst;
    const f = new Float32Array(buf)[0]!;
    return Number.isFinite(f) ? `${f}` : f > 0 ? "Infinity" : f < 0 ? "-Infinity" : "NaN";
  }
  // FLOAT64, INT64, UINT64 — overflow types, need kernel to decode.
  if (k !== undefined) {
    if (node.type === Triv.FLOAT64) {
      const v = k.decodeFloat64(node.inst);
      if (Number.isNaN(v)) return "NaN";
      if (v === Infinity) return "Infinity";
      if (v === -Infinity) return "-Infinity";
      return String(v);
    }
    if (node.type === Triv.INT64) {
      return `${k.decodeInt64(node.inst).toString()}n`;
    }
    if (node.type === Triv.UINT64) {
      return `${k.decodeUint64(node.inst).toString()}n`;
    }
  }
  // STRING and others: not on the hot path; box at the boundary.
  return `(/* trivial type ${node.type} */ null)`;
}

function emitMath(
  k: Kernel,
  inst: number,
  kids: readonly NodeID[],
  scope: CompileScope,
): string {
  const width = mathWidth(inst);
  const op = mathOp(inst);
  const parts = kids.map((c) => `(${emitExpr(k, c, scope)})`);
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

  // FLOAT64 — emit straight JS arithmetic with no boxing, no | 0.
  // V8 will keep these as f64 throughout the chain.
  if (width === RMathWidth.F64) {
    let acc = parts[0]!;
    for (let i = 1; i < parts.length; i++) {
      acc = `(${acc} ${opStr} ${parts[i]})`;
    }
    return acc;
  }

  // FLOAT32 — same but narrow with Math.fround at each step.
  if (width === RMathWidth.F32) {
    let acc = parts[0]!;
    for (let i = 1; i < parts.length; i++) {
      acc = `Math.fround(${acc} ${opStr} ${parts[i]})`;
    }
    return acc;
  }

  // INT64 / UINT64 — BigInt arithmetic. Slower than primitives but real.
  if (width === RMathWidth.I64 || width === RMathWidth.U64) {
    let acc = `BigInt(${parts[0]})`;
    for (let i = 1; i < parts.length; i++) {
      acc = `(${acc} ${opStr} BigInt(${parts[i]}))`;
    }
    return acc;
  }

  // I32 default — | 0 / Math.imul to keep V8's SMI tagging.
  if (op === RMath.MUL) {
    if (parts.length === 2) return `Math.imul(${parts[0]}, ${parts[1]})`;
    let acc = parts[0]!;
    for (let i = 1; i < parts.length; i++) {
      acc = `Math.imul(${acc}, ${parts[i]})`;
    }
    return acc;
  }
  if (op === RMath.DIV) {
    if (parts.length === 2) return `((${parts[0]} / ${parts[1]}) | 0)`;
    let acc = parts[0]!;
    for (let i = 1; i < parts.length; i++) {
      acc = `((${acc} / ${parts[i]}) | 0)`;
    }
    return acc;
  }
  let acc = parts[0]!;
  for (let i = 1; i < parts.length; i++) {
    acc = `((${acc} ${opStr} ${parts[i]}) | 0)`;
  }
  return acc;
}

function emitCompare(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: CompileScope,
): string {
  const a = emitExpr(k, kids[0]!, scope);
  const b = emitExpr(k, kids[1]!, scope);
  const opStr =
    op === RCmp.EQ
      ? "==="
      : op === RCmp.NE
        ? "!=="
        : op === RCmp.LT
          ? "<"
          : op === RCmp.LE
            ? "<="
            : op === RCmp.GT
              ? ">"
              : op === RCmp.GE
                ? ">="
                : "===";
  return `((${a}) ${opStr} (${b}))`;
}

function emitLogic(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: CompileScope,
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
  scope: CompileScope,
): string {
  if (op === RCond.IF_THEN) {
    return `((${emitExpr(k, kids[0]!, scope)}) ? (${emitExpr(k, kids[1]!, scope)}) : null)`;
  }
  return `((${emitExpr(k, kids[0]!, scope)}) ? (${emitExpr(k, kids[1]!, scope)}) : (${emitExpr(k, kids[2]!, scope)}))`;
}

function emitBlock(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  scope: CompileScope,
): string {
  if (op === RBlock.LET) {
    // Standalone LET as expression — IIFE-scoped binding (no escape to
    // siblings). When a LET sits inside a DO/SEQUENCE block,
    // emitBlockAsIife handles it as a statement so the binding stays
    // visible to later siblings in the same block, matching the walker's
    // frame.bind semantics.
    const name = kids[0]!;
    const valueSrc = emitExpr(k, kids[1]!, scope);
    if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
      return emitWalkerFallback(kids[1]!);
    }
    const jsName = fresh(scope, `let_${name.inst}`);
    // NOTE: do NOT mutate scope.vars here — the JS variable lives only
    // inside the IIFE we emit below, so sibling expressions in an outer
    // block cannot reference it. Statement-form LETs (declared inside
    // emitBlockAsIife) DO bind into the surrounding scope.
    return `(function(){ const ${jsName} = ${valueSrc}; return ${jsName}; })()`;
  }
  // DO / SEQUENCE — evaluate each, return last
  if (kids.length === 0) return "null";
  if (kids.length === 1) return emitExpr(k, kids[0]!, scope);
  // If any child is a FNDEF or LET, switch to statement-form IIFE so the
  // declarations bind visibly across siblings. Otherwise emit a flat
  // comma-sequence — cheaper, no extra closure.
  for (const c of kids) {
    if (isStatementForm(k, c)) {
      return emitBlockAsIife(k, kids, scope);
    }
  }
  const parts = kids.map((c) => `(${emitExpr(k, c, scope)})`);
  return `(${parts.join(", ")})`;
}

function isFnDef(k: Kernel, node: NodeID): boolean {
  if (node.level === Level.TRIVIAL) return false;
  const cat = k.category(node);
  return cat.type === RBasic.FNDEF;
}

function isLetForm(k: Kernel, node: NodeID): boolean {
  if (node.level === Level.TRIVIAL) return false;
  const cat = k.category(node);
  return cat.type === RBasic.BLOCK && cat.inst === RBlock.LET;
}

// Statement-form constructs need to be declared at the IIFE's statement
// level so their bindings (function name, let name) become visible to
// later siblings in the same block.
function isStatementForm(k: Kernel, node: NodeID): boolean {
  return isFnDef(k, node) || isLetForm(k, node);
}

function emitBlockAsIife(
  k: Kernel,
  kids: readonly NodeID[],
  outerScope: CompileScope,
): string {
  const scope = childScope(outerScope);
  const stmts: string[] = [];
  let lastIsExpr = false;
  let lastExpr = "null";
  for (let i = 0; i < kids.length; i++) {
    const c = kids[i]!;
    const isLast = i === kids.length - 1;
    if (isFnDef(k, c)) {
      stmts.push(emitFnDefAsStatement(k, c, scope));
      if (isLast) {
        lastIsExpr = false;
        lastExpr = "null";
      }
    } else if (isLetForm(k, c)) {
      // (let name value) as statement — declares a JS const so later
      // siblings in this block can reference the binding directly,
      // matching the walker's frame.bind semantics. Falls back to walker
      // for the value subtree if the name is malformed.
      const letKids = k.children(c);
      const nameNode = letKids[0]!;
      if (nameNode.level !== Level.TRIVIAL || nameNode.type !== Triv.STRING) {
        const fb = emitWalkerFallback(c);
        if (isLast) {
          lastIsExpr = true;
          lastExpr = fb;
        } else {
          stmts.push(`(${fb});`);
        }
      } else {
        const valueSrc = emitExpr(k, letKids[1]!, scope);
        const jsName = fresh(scope, `let_${nameNode.inst}`);
        scope.vars.set(nameNode.inst, jsName);
        stmts.push(`const ${jsName} = ${valueSrc};`);
        if (isLast) {
          lastIsExpr = true;
          lastExpr = jsName;
        }
      }
    } else {
      const e = emitExpr(k, c, scope);
      if (isLast) {
        lastIsExpr = true;
        lastExpr = e;
      } else {
        stmts.push(`(${e});`);
      }
    }
  }
  if (!lastIsExpr) {
    // No trailing expression — block returns null
    return `(function(){ ${stmts.join("\n")} return null; })()`;
  }
  return `(function(){ ${stmts.join("\n")} return ${lastExpr}; })()`;
}

function emitFnDefAsStatement(
  k: Kernel,
  node: NodeID,
  scope: CompileScope,
): string {
  const kids = k.children(node);
  return emitFnDefStmt(k, kids, scope);
}

function emitFnDefStmt(
  k: Kernel,
  kids: readonly NodeID[],
  scope: CompileScope,
): string {
  const name = kids[0]!;
  const paramsBlock = kids[1]!;
  const body = kids[2]!;
  if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
    throw new Error("compiler: defn name must be string trivial");
  }
  const nameID = name.inst;
  const paramKids = k.children(paramsBlock);
  const jsName = fresh(scope, `fn_${nameID}`);
  scope.fns.set(nameID, jsName);

  const fnScope = childScope(scope);
  const paramNames: string[] = [];
  for (const p of paramKids) {
    if (p.level !== Level.TRIVIAL || p.type !== Triv.STRING) {
      throw new Error("compiler: params must be string trivials");
    }
    const jsParam = fresh(fnScope, `p_${p.inst}`);
    fnScope.vars.set(p.inst, jsParam);
    paramNames.push(jsParam);
  }
  const bodySrc = emitExpr(k, body, fnScope);
  return `function ${jsName}(${paramNames.join(", ")}) { return ${bodySrc}; }`;
}

function emitFnDef(
  k: Kernel,
  kids: readonly NodeID[],
  scope: CompileScope,
): string {
  // FNDEF as expression — wrap in IIFE so the surrounding scope can use it
  return `(function(){ ${emitFnDefStmt(k, kids, scope)} return null; })()`;
}

function emitFnCall(
  k: Kernel,
  kids: readonly NodeID[],
  scope: CompileScope,
): string {
  if (kids.length < 1) {
    return "null";
  }
  const callee = kids[0]!;
  // Resolve callee statically when possible.
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
    return emitWalkerFallback(kids[0]!);
  }
  // Compiled local fn — direct call
  const localFn = scope.fns.get(nameID);
  if (localFn !== undefined) {
    const args = kids.slice(1).map((a) => emitExpr(k, a, scope));
    return `${localFn}(${args.join(", ")})`;
  }
  // Native — emit a callNative with generic-boxed args + generic unbox.
  const nat = k.natives.get(nameID);
  if (nat !== undefined) {
    const argExprs = kids
      .slice(1)
      .map((a) => `boxAny(${emitExpr(k, a, scope)})`);
    return `valueAsNum(callNative(k, ${nameID}, [${argExprs.join(", ")}]))`;
  }
  // Free-fn (closure resolved via frame) — emit a callFreeFn dispatch
  // that looks up the closure at runtime and walks its body in a fresh
  // frame. Lets recursive Form-defined functions compile cleanly even
  // when their definition isn't in the compile scope.
  const argExprs = kids
    .slice(1)
    .map((a) => `boxAny(${emitExpr(k, a, scope)})`);
  return `valueAsNum(callFreeFn(k, frame, ${nameID}, [${argExprs.join(", ")}]))`;
}

function emitWalkerFallback(node: NodeID): string {
  const j = JSON.stringify(node);
  return `valueAsInt(walk(k, ${j}, frame))`;
}

// Box the top-level result back into a Value. The structural type of `result`
// is inferred from the expression: arithmetic chains yield numbers, compares
// yield bools, function calls of compiled local fns return numbers (since
// compiled fns return raw types).
function emitBox(_bodySrc: string, varName: string): string {
  // Type-discriminate at runtime — covers all paths cleanly.
  // Number → int (smi-fit) or float; bigint → i64; bool/null/Value passthrough.
  return `(
    typeof ${varName} === "bigint" ? boxBig(${varName}) :
    typeof ${varName} === "boolean" ? boxBool(${varName}) :
    typeof ${varName} === "number"
      ? (Number.isInteger(${varName}) && Math.abs(${varName}) < 0x80000000 ? boxInt(${varName}) : boxFloat(${varName}))
      : ${varName} == null ? boxNull() : ${varName}
  )`;
}
