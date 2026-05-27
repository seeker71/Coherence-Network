// lang-python-fk.ts — emit kernel-native .fk S-expression source from
// a parsed Python Form tree. The compilation step that closes the
// Python → Form → native-kernel pipeline:
//
//   Python source bytes
//     → parsePython (lang-python.ts)        — BMF parser produces Form tree
//     → emitFk (this file)                  — Form tree → kernel-native .fk
//     → form-kernel-rust binary             — walks the .fk, no host runtime
//
// The mapping is Python CTOR → kernel RBasic arm. Each Python construct
// supported by the BMF parser is translated into the matching kernel
// expression. Unsupported constructs (assignment, subscript, slicing,
// classes, etc.) are honest errors here — they need either grammar-level
// support or new kernel arms.
//
// Companion concept: lc-parser-as-form-recipe — names the multi-breath
// arc this file is one step of.

import { Kernel, Level, Triv, type NodeID } from "../../../src/kernel.ts";
import { capturedCtor, capturedChildren } from "../../../src/languages.ts";
import { CTOR } from "./lang-python.ts";

export interface EmitFkOptions {
  // When set, prefix each top-level form with a comment naming its
  // source line for debugging. Off by default — the kernel reader
  // tolerates comments but they bloat the .fk.
  source_comments?: boolean;
}

// Counter for synthesized helper names (`_while_N`, `_for_N`,
// `_lambda_N`). Reset at each emitFk call so output is deterministic.
let whileCounter = 0;

// Lifted lambda definitions — collected during emit, prepended to the
// module's top-level (do ...) before the body runs. Lambdas are
// expression-level in Python but the kernel's defn binds names at
// statement-level; lifting puts the defn where the kernel can see it.
let liftedDefns: string[] = [];

// Does this node end with a `return` (somewhere along all paths)?
// Used by emitDefBody to decide whether an if-statement's then-branch
// short-circuits the function. A return at the bottom of the then-block,
// or a return inside an inner if/loop within the then-block, all count.
function containsReturn(k: Kernel, n: NodeID): boolean {
  if (n.level === Level.TRIVIAL) return false;
  const ctor = capturedCtor(k, n);
  if (ctor === CTOR.return_) return true;
  // Don't recurse into nested def/lambda — they have their own bodies.
  if (ctor === CTOR.def_ || ctor === CTOR.lambda_) return false;
  for (const c of capturedChildren(k, n)) {
    if (containsReturn(k, c)) return true;
  }
  return false;
}

// CPS-style emission of a Python def body. Walks statements in order;
// when an `if cond: <body-with-return>` appears, the *rest* of the
// function body becomes the implicit else, lowered into a nested
// (if cond <then-value> <rest>) shape. Without this, multi-statement
// def bodies with early returns silently fall through.
function emitDefBody(k: Kernel, bodyNode: NodeID, opts: EmitFkOptions): string {
  // Body is typically CTOR.block; otherwise it's a single expression
  // (matches the v1 def_rule shape for single-line bodies).
  const bodyCtor = capturedCtor(k, bodyNode);
  const stmts =
    bodyCtor === CTOR.block ? capturedChildren(k, bodyNode) : [bodyNode];
  return emitStmtSeq(k, stmts, 0, opts);
}

// Emit statements stmts[start..end] as a CPS-style chain. Early returns
// short-circuit; the function's value is determined by the first
// return that fires.
function emitStmtSeq(
  k: Kernel,
  stmts: readonly NodeID[],
  start: number,
  opts: EmitFkOptions,
): string {
  if (start >= stmts.length) return "false"; // implicit fallthrough → None-ish
  const stmt = stmts[start]!;
  const ctor = capturedCtor(k, stmt);
  const kids = capturedChildren(k, stmt);

  if (ctor === CTOR.return_) {
    return emit(k, kids[0]!, opts);
  }

  if (ctor === CTOR.if_) {
    // CTOR.if_'s children are alternating [cond, body, cond, body, ..., else?].
    // For def-body CPS, look at the then-bodies: if a then-body contains
    // a return, the if becomes (if cond <then-value> <rest>) where
    // <rest> is the CPS of the remaining function-body stmts.
    return emitIfInDefBody(k, kids, stmts, start, opts);
  }

  if (ctor === CTOR.assign) {
    // Reuse the assign emitter so subscript-targets (d[k] = v) work
    // inside def bodies the same way they work at module scope.
    const assignStr = emit(k, stmt, opts);
    const rest = emitStmtSeq(k, stmts, start + 1, opts);
    return `(do ${assignStr} ${rest})`;
  }

  // Side-effect statement (call, etc.) — emit, then continue.
  const sideEffect = emit(k, stmt, opts);
  const rest = emitStmtSeq(k, stmts, start + 1, opts);
  return start + 1 >= stmts.length
    ? sideEffect
    : `(do ${sideEffect} ${rest})`;
}

function emitIfInDefBody(
  k: Kernel,
  ifKids: readonly NodeID[],
  stmts: readonly NodeID[],
  start: number,
  opts: EmitFkOptions,
): string {
  // ifKids: [cond0, body0, cond1, body1, ..., elseBody?]
  // Compose right-to-left: nested ifs with the function's REST as the
  // ultimate else.
  let i = ifKids.length;
  // Determine if there's an explicit else (odd count means odd kid is else).
  let elseAcc: string;
  if (i % 2 === 1) {
    // Explicit else block
    const elseNode = ifKids[i - 1]!;
    elseAcc = emitBlockInDefBody(k, elseNode, stmts, start + 1, opts);
    i -= 1;
  } else {
    // No explicit else — the function-body REST is the implicit else.
    elseAcc = emitStmtSeq(k, stmts, start + 1, opts);
  }
  // Walk pairs (cond, body) from end to start.
  while (i >= 2) {
    const body = ifKids[i - 1]!;
    const cond = ifKids[i - 2]!;
    const condStr = emit(k, cond, opts);
    const thenStr = emitBlockInDefBody(k, body, stmts, start + 1, opts);
    elseAcc = `(if ${condStr} ${thenStr} ${elseAcc})`;
    i -= 2;
  }
  return elseAcc;
}

// Emit a then-/else-block in def-body context. If the block ends with
// a return, the block's value is that return's expression. Otherwise
// the block executes for side effects and falls through to the function
// body's REST (via emitStmtSeq on the outer stmts).
function emitBlockInDefBody(
  k: Kernel,
  blockNode: NodeID,
  outerStmts: readonly NodeID[],
  outerStart: number,
  opts: EmitFkOptions,
): string {
  const blockCtor = capturedCtor(k, blockNode);
  const blockStmts =
    blockCtor === CTOR.block ? capturedChildren(k, blockNode) : [blockNode];

  if (containsReturn(k, blockNode)) {
    // The block short-circuits — its CPS chain ends in the return value.
    return emitStmtSeq(k, blockStmts, 0, opts);
  }
  // No return — execute for side effects, then continue with outer rest.
  // Build: (do <block-stmts...> <outer-rest>)
  const sideEffectStrs = blockStmts.map((s) => emit(k, s, opts));
  const outerRest = emitStmtSeq(k, outerStmts, outerStart, opts);
  return sideEffectStrs.length === 0
    ? outerRest
    : `(do ${sideEffectStrs.join(" ")} ${outerRest})`;
}

// Detect any string literal anywhere in a subtree. Used to decide
// whether to use the polymorphic `_plus` native (string dispatch) or
// the faster kernel-native `add` (pure int).
function containsStringLiteral(k: Kernel, n: NodeID): boolean {
  if (n.level === Level.TRIVIAL) {
    return n.type === Triv.STRING;
  }
  const ctor = capturedCtor(k, n);
  if (ctor === CTOR.str_literal) return true;
  // Don't recurse INTO def/lambda — they're separate scopes.
  if (ctor === CTOR.def_ || ctor === CTOR.lambda_) return false;
  for (const c of capturedChildren(k, n)) {
    if (containsStringLiteral(k, c)) return true;
  }
  return false;
}

// Recursively collect assignment-target names from any node in a
// subtree. Used by while/for emitters to find all loop-mutated
// variables, including those nested inside if-statements, blocks,
// etc. Names are returned in order of first encounter.
function collectAssignTargets(k: Kernel, n: NodeID, out: string[], seen: Set<string>): void {
  if (n.level === Level.TRIVIAL) return;
  const ctor = capturedCtor(k, n);
  const kids = capturedChildren(k, n);
  if (ctor === CTOR.assign) {
    // Loop variable is the rebound name in scope. For ident targets that's
    // the target itself; for subscript targets (d[k] = v) the rebound
    // name is the container ident (the kernel-level emit rebuilds the
    // dict and rebinds `d`).
    const target = kids[0]!;
    const tCtor = capturedCtor(k, target);
    let tn: string | null = null;
    if (tCtor === CTOR.ident) {
      tn = emitIdent(k, target);
    } else if (tCtor === CTOR.subscript) {
      const subKids = capturedChildren(k, target);
      if (capturedCtor(k, subKids[0]!) === CTOR.ident) {
        tn = emitIdent(k, subKids[0]!);
      }
    }
    if (tn !== null && !seen.has(tn)) {
      seen.add(tn);
      out.push(tn);
    }
    return;
  }
  // Don't recurse INTO def_/lambda — their bodies are separate scopes.
  if (ctor === CTOR.def_ || ctor === CTOR.lambda_) return;
  for (const c of kids) {
    collectAssignTargets(k, c, out, seen);
  }
}

export function emitFk(k: Kernel, tree: NodeID, opts: EmitFkOptions = {}): string {
  whileCounter = 0;
  liftedDefns = [];
  const body = emit(k, tree, opts);
  // If any lambdas got lifted, prepend their defns inside the outer
  // (do ...). For a single-stmt module we still need to wrap.
  if (liftedDefns.length === 0) return body;
  const isBareDo = body.startsWith("(do ") && body.endsWith(")");
  if (isBareDo) {
    // Splice into the existing do-block: insert lifted defns right after "(do "
    const inner = body.slice(4, body.length - 1); // strip "(do " and ")"
    return `(do ${liftedDefns.join(" ")} ${inner})`;
  }
  return `(do ${liftedDefns.join(" ")} ${body})`;
}

function emit(k: Kernel, n: NodeID, opts: EmitFkOptions): string {
  if (n.level === Level.TRIVIAL) {
    return emitTrivial(k, n);
  }
  const ctor = capturedCtor(k, n);
  const kids = capturedChildren(k, n);
  switch (ctor) {
    case CTOR.module: {
      // Module is a sequence of statements. Wrap in (do ...) so the
      // kernel reader treats them as one program. Import statements
      // are noops at runtime — drop them from the emitted .fk rather
      // than emitting (do "import"). Single-statement modules emit
      // bare to keep the .fk minimal.
      const parts: string[] = [];
      for (const c of kids) {
        if (capturedCtor(k, c) === CTOR.import_) continue;
        parts.push(emit(k, c, opts));
      }
      if (parts.length === 0) return "false";
      if (parts.length === 1) return parts[0]!;
      return `(do ${parts.join(" ")})`;
    }
    case CTOR.import_:
      // Imports never compile to a runtime instruction — the parser
      // already rewrote member accesses to call the kernel native
      // directly. An import node appearing outside a module top-level
      // (e.g. inside a function — currently unreachable) emits the
      // same noop.
      return "false";
    case CTOR.expr_stmt:
      return emit(k, kids[0]!, opts);

    case CTOR.int_literal:
    case CTOR.float_literal:
    case CTOR.bool_literal:
    case CTOR.str_literal:
      return emitTrivial(k, kids[0]!);

    case CTOR.none_literal:
      // The kernel reader doesn't have a None literal. Python None
      // maps to the "false" reserved ident — preserves truthiness
      // (None is falsy) without inventing a syntax the reader can't
      // parse. Honest gap for richer None semantics.
      return "false";

    case CTOR.ident: {
      const t = kids[0]!;
      // The .fk reader treats `true`, `false` as bool literals.
      // Python identifiers True/False/None are already handled by the
      // bool_literal / none_literal CTORs above; ident.children[0]
      // here is a plain string trivial.
      if (t.level === Level.TRIVIAL && t.type === Triv.STRING) {
        return k.strs[t.inst] ?? "?ident";
      }
      return "?ident";
    }

    // ── arithmetic ─────────────────────────────────────────────
    case CTOR.add: {
      // Python `+` is overloaded: int+int → arithmetic; str+str → concat;
      // list+list → concat. emitFk can't always determine operand types
      // (variables, function returns). When the expression tree CONTAINS
      // a string literal anywhere, we route to the polymorphic `_plus`
      // kernel native that dispatches at runtime. Pure-numeric trees
      // stay on the faster kernel-native MATH.PLUS arm.
      const polymorphicNeeded =
        containsStringLiteral(k, kids[0]!) || containsStringLiteral(k, kids[1]!);
      const op = polymorphicNeeded ? "_plus" : "add";
      return `(${op} ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    }
    case CTOR.sub: return `(sub ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.mul: return `(mul ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.div: return `(div ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.mod: return `(mod ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.neg: return `(sub 0 ${emit(k, kids[0]!, opts)})`;

    // ── comparison ─────────────────────────────────────────────
    case CTOR.eq: return `(eq ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.ne: return `(ne ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.lt: return `(lt ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.le: return `(le ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.gt: return `(gt ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.ge: return `(ge ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;

    // ── logic ──────────────────────────────────────────────────
    case CTOR.and_: return `(and ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.or_:  return `(or ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.not_: return `(not ${emit(k, kids[0]!, opts)})`;

    // ── conditional expression / if-statement ───────────────────
    case CTOR.if_: {
      // Conditional expression: [cond, then, else] where neither
      // branch is a CTOR.block. Statement form: pairs of (cond, body)
      // optionally with a trailing else. Both compile to nested
      // kernel if-expressions.
      const isExpr =
        kids.length === 3 && capturedCtor(k, kids[1]!) !== CTOR.block;
      if (isExpr) {
        return `(if ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)} ${emit(k, kids[2]!, opts)})`;
      }
      // Statement form: pairs of (cond, body) with optional final else.
      // Lower right-to-left into nested ifs.
      const stmts: string[] = [];
      let i = 0;
      while (i + 1 < kids.length) {
        stmts.push(emit(k, kids[i]!, opts));
        stmts.push(emit(k, kids[i + 1]!, opts));
        i += 2;
      }
      const elseBranch =
        i < kids.length ? emit(k, kids[i]!, opts) : "false";
      // Build: (if c0 b0 (if c1 b1 ... (if cN bN elseBranch)))
      let acc = elseBranch;
      for (let j = stmts.length - 2; j >= 0; j -= 2) {
        acc = `(if ${stmts[j]} ${stmts[j + 1]} ${acc})`;
      }
      return acc;
    }

    case CTOR.block: {
      const parts = kids.map((c: NodeID) => emit(k, c, opts));
      if (parts.length === 1) return parts[0]!;
      return `(do ${parts.join(" ")})`;
    }

    case CTOR.return_:
      // The kernel's defn body evaluates to the last expression's
      // value, matching `return expr` from a Python def. Strip the
      // CTOR.return_ wrapper. Multi-path returns inside conditionals
      // become nested (if ...) expressions through the if_ CTOR above.
      return emit(k, kids[0]!, opts);

    case CTOR.def_: {
      // children: [name-ident-node, params-node, body-node]
      // Body uses CPS-style emission: early returns short-circuit;
      // if-then-without-else falls through to the remaining stmts as
      // the implicit else. The kernel has no RETURN arm — the
      // function's value is the last-evaluated expression, so the body
      // must be one nested expression that yields the right value
      // along every path.
      const name = emitIdent(k, kids[0]!);
      const paramNodes = capturedChildren(k, kids[1]!);
      const paramNames = paramNodes.map((p: NodeID) => emitIdent(k, p));
      const body = emitDefBody(k, kids[2]!, opts);
      return `(defn ${name} (${paramNames.join(" ")}) ${body})`;
    }

    case CTOR.lambda_: {
      // children: [params-node, body-node]
      // Lift to a module-level defn with a synthetic name. The body
      // is a single expression (lambda's defining shape); emit it
      // directly (not via emitDefBody which would CPS-transform).
      const paramNodes = capturedChildren(k, kids[0]!);
      const paramNames = paramNodes.map((p: NodeID) => emitIdent(k, p));
      const body = emit(k, kids[1]!, opts);
      const name = `_lambda_${whileCounter++}`;
      liftedDefns.push(`(defn ${name} (${paramNames.join(" ")}) ${body})`);
      // The lambda expression evaluates to the closure value — referencing
      // the lifted name does that lookup at the call site.
      return name;
    }
    case CTOR.call: {
      // children: [callee-node, args-node]
      const calleeNode = kids[0]!;
      const argsNode = kids[1];
      const argNodes = argsNode !== undefined ? capturedChildren(k, argsNode) : [];
      const argStrs = argNodes.map((a: NodeID) => emit(k, a, opts));
      // If callee is a simple ident, emit (name arg1 arg2 ...). Else,
      // calling an expression — the kernel reader doesn't support
      // first-class expression callees in (call ...) form yet; let
      // the user know honestly.
      if (capturedCtor(k, calleeNode) === CTOR.ident) {
        const calleeName = emitIdent(k, calleeNode);
        return argStrs.length === 0
          ? `(${calleeName})`
          : `(${calleeName} ${argStrs.join(" ")})`;
      }
      throw new Error(
        "emitFk: call with non-ident callee not yet supported (lambdas/method-chains/etc.)",
      );
    }

    // ── method call ───────────────────────────────────────────
    // Python `obj.method(args…)` lowers to a runtime `_dispatch` call.
    // The receiver's record carries a "__class__" string field; the
    // dispatch native uses that to find `<ClassName>__<methodName>` in
    // the surrounding scope (where the class emit lifted it as a defn).
    // This keeps method dispatch composable across multiple classes
    // without baking class identity into compile-time call sites.
    case CTOR.method_call: {
      const recv = emit(k, kids[0]!, opts);
      const methodName = emitIdent(k, kids[1]!);
      const argNodes = capturedChildren(k, kids[2]!);
      const argStrs = argNodes.map((a: NodeID) => emit(k, a, opts));
      const tail = argStrs.length === 0 ? "" : ` ${argStrs.join(" ")}`;
      return `(_dispatch ${recv} ${JSON.stringify(methodName)}${tail})`;
    }

    // ── attribute read ────────────────────────────────────────
    // Python `obj.field` → `(_get obj "field")` reading from the
    // receiver's record (Value::List of alternating key/value entries).
    case CTOR.attr: {
      const recv = emit(k, kids[0]!, opts);
      const field = emitIdent(k, kids[1]!);
      return `(_get ${recv} ${JSON.stringify(field)})`;
    }

    // ── class declaration ─────────────────────────────────────
    // Compiles to:
    //   1. A constructor function bound at the class name.
    //   2. One lifted `<ClassName>__<methodName>` for each method (other
    //      than __init__).
    // Both land in the module's top-level `(do ...)` via liftedDefns.
    case CTOR.class_: {
      emitClass(k, kids, opts);
      // The class statement itself evaluates to None (Python returns
      // the class object; the kernel binds it via the constructor defn
      // and we don't model class objects in v1).
      return "false";
    }

    case CTOR.list_literal: {
      const parts = kids.map((c: NodeID) => emit(k, c, opts));
      return parts.length === 0 ? "(list)" : `(list ${parts.join(" ")})`;
    }

    // ── dict literal ──────────────────────────────────────────
    // Python `{k: v, ...}` → kernel `(_dict_new k0 v0 k1 v1 ...)`
    // The _dict_new native builds a "__dict__"-tagged list; subsequent
    // subscript / `in` / iteration go through the dict-aware _get / _in
    // natives so the same .fk runs over either container.
    case CTOR.dict_literal: {
      const flat: string[] = [];
      for (const entry of kids) {
        const eKids = capturedChildren(k, entry);
        flat.push(emit(k, eKids[0]!, opts), emit(k, eKids[1]!, opts));
      }
      return flat.length === 0 ? "(_dict_new)" : `(_dict_new ${flat.join(" ")})`;
    }
    case CTOR.dict_entry: {
      // Standalone — shouldn't normally happen; emit as a 2-list.
      return `(list ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    }

    // ── membership: `k in container` ──────────────────────────
    case CTOR.in_: {
      // Note arg order: Form's _in takes (needle, hay) matching the
      // Python source `needle in hay`.
      return `(_in ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    }

    // ── assignment ─────────────────────────────────────────────
    // Python `x = expr` compiles to kernel `(let x expr)`. The
    // kernel's LET binds in the enclosing block; subsequent `(let x
    // ...)` re-bindings shadow within the same block. For top-level
    // module assignments and intra-function single-shot bindings this
    // matches Python's semantics. Augmented assignment (`x += y`),
    // tuple unpacking, and attribute/subscript targets need richer
    // lowering — honest gaps for follow-up breaths.
    case "assign": {
      // children: [target-node, value-node]. Targets:
      //   ident      → (let name expr)
      //   subscript  → (let container (_dict_set container key value))
      //                Dicts are immutable in the kernel layer; rebinding
      //                the container LET in the enclosing scope gives the
      //                same observable effect as `d[k] = v` within one
      //                scope. Multi-alias mutation would need a mutable
      //                dict variant — pending.
      const target = kids[0]!;
      const tCtor = capturedCtor(k, target);
      if (tCtor === CTOR.ident) {
        return `(let ${emitIdent(k, target)} ${emit(k, kids[1]!, opts)})`;
      }
      if (tCtor === CTOR.subscript) {
        const subKids = capturedChildren(k, target);
        const containerNode = subKids[0]!;
        if (capturedCtor(k, containerNode) !== CTOR.ident) {
          throw new Error(
            "emitFk: subscript-assign target's container must be a simple name (v1)",
          );
        }
        const containerName = emitIdent(k, containerNode);
        const key = emit(k, subKids[1]!, opts);
        const value = emit(k, kids[1]!, opts);
        return `(let ${containerName} (_dict_set ${containerName} ${key} ${value}))`;
      }
      throw new Error(
        `emitFk: unsupported assign target ${tCtor}`,
      );
    }

    // ── subscript ─────────────────────────────────────────────
    // Python `lst[i]` / `d[k]` / `s[i]` → kernel `(_get value index)`.
    // _get is polymorphic over list / dict / str so the same .fk runs
    // regardless of container shape. Pre-dict code used `nth`; _get
    // delegates to nth for list/str so behaviour is identical there.
    case "subscript": {
      const value = emit(k, kids[0]!, opts);
      const slice = emit(k, kids[1]!, opts);
      return `(_get ${value} ${slice})`;
    }

    // ── for-loop over a list ────────────────────────────────────
    // Python:                Kernel (.fk):
    //   for x in xs:          (defn _for_K (xs <loopvars>)
    //       body                (if (eq (len xs) 0)
    //                               <return-state>
    //                               (do (let x (head xs))
    //                                   body-with-recursive-tail-call)))
    //                         (let _for_K_result (_for_K xs <loopvars>))
    //
    // Today supports for-loops over a list expression. range(N) and
    // generic iterators land when the kernel grows iter/next natives.
    case CTOR.for_: {
      // children: [target-ident, iter-expr, body]
      const target = emitIdent(k, kids[0]!);
      // Wrap in _iter so dicts iterate as keys (matching Python) and
      // lists pass through unchanged. Avoids the helper having to know
      // whether _remaining is a dict or a list.
      const iterExpr = `(_iter ${emit(k, kids[1]!, opts)})`;
      const bodyNode = kids[2]!;

      // Recursively collect every assignment target in the body —
      // accounts for nested if-statements, conditional mutation, etc.
      const loopVars: string[] = [];
      collectAssignTargets(k, bodyNode, loopVars, new Set<string>());

      const helperName = `_for_${whileCounter++}`;
      const params = ["_remaining", ...loopVars].join(" ");

      // Body emits as a single block (do ...). The kernel's LET binds
      // in the current frame; rebinds within the helper's body update
      // the iteration's local copies of the loop vars. The trailing
      // recursive call passes the current (rebound) loop var bindings.
      const bodyStr = emit(k, bodyNode, opts);
      const recCall =
        loopVars.length === 0
          ? `(${helperName} (tail _remaining))`
          : `(${helperName} (tail _remaining) ${loopVars.join(" ")})`;

      const wrappedBody = `(do (let ${target} (head _remaining)) ${bodyStr} ${recCall})`;

      const elseBranch =
        loopVars.length === 0
          ? "null"
          : loopVars.length === 1
            ? loopVars[0]!
            : `(list ${loopVars.join(" ")})`;

      const helperDef = `(defn ${helperName} (${params}) (if (eq (len _remaining) 0) ${elseBranch} ${wrappedBody}))`;

      let helperCall: string;
      if (loopVars.length === 0) {
        helperCall = `(${helperName} ${iterExpr})`;
      } else if (loopVars.length === 1) {
        helperCall = `(let ${loopVars[0]} (${helperName} ${iterExpr} ${loopVars[0]}))`;
      } else {
        const resultName = `_for_${whileCounter}_result`;
        const destructure = loopVars
          .map((v, i) => `(let ${v} (nth ${resultName} ${i}))`)
          .join(" ");
        helperCall =
          `(let ${resultName} (${helperName} ${iterExpr} ${loopVars.join(" ")})) ` +
          destructure;
      }
      return `(do ${helperDef} ${helperCall})`;
    }

    // ── while-loop via accumulator-passing recursion ──────────
    // Python:                Kernel (Form-native equivalent):
    //   i = 0                (let i 0)
    //   while i < N:         (defn _while_K (i) (if (lt i N) (_while_K (add i 1)) i))
    //       i = i + 1        (let i (_while_K i))
    //
    // The kernel has no LOOP arm — recursion IS the loop in Form-native.
    // The transformation:
    //   1. Scan the loop body for `name = expr` assignments — these
    //      are the "loop variables" the iteration mutates.
    //   2. Generate a helper recipe `_while_<counter>` taking those
    //      variables as params.
    //   3. The helper body: `(if cond (_while_K new_v1 new_v2 ...)
    //      (return-state))` where new_v_i is the RHS of v_i's
    //      assignment in the body.
    //   4. Initial call passes the current bindings of the loop vars.
    //
    // Restrictions today:
    //   - Body statements must be (a) assignments to loop vars, or
    //     (b) other expression-statements / side-effects that run
    //     before each recursive call.
    //   - All loop vars must be already bound in the enclosing scope
    //     (the assignments inside the loop are re-binds, not first
    //     definitions).
    //   - Single-var loops first; multi-var lands when needed.
    case CTOR.while_: {
      // children: [cond-node, body-node]
      const cond = emit(k, kids[0]!, opts);
      const bodyNode = kids[1]!;
      const bodyCtor = capturedCtor(k, bodyNode);
      const bodyKids =
        bodyCtor === CTOR.block ? capturedChildren(k, bodyNode) : [bodyNode];

      // Recursively collect every assignment target in the body —
      // accounts for nested if-statements, conditional mutation, etc.
      const loopVars: string[] = [];
      collectAssignTargets(k, bodyNode, loopVars, new Set<string>());

      if (loopVars.length === 0) {
        throw new Error(
          "emitFk: while-loop has no assigned loop variables — would loop forever. " +
            "Need at least one `var = expr` (possibly inside a conditional) in the body to progress.",
        );
      }

      // Generate a unique helper name. Counter lives in the closure.
      const helperName = `_while_${whileCounter++}`;

      // Body emits as a single (do ...) chain. The kernel's LET binds
      // in the helper's frame; rebinds within the body update the
      // iteration's local copies. The trailing recursive call passes
      // the current (rebound) loop var bindings.
      const bodyStr =
        bodyKids.length === 1
          ? emit(k, bodyKids[0]!, opts)
          : `(do ${bodyKids.map((s) => emit(k, s, opts)).join(" ")})`;
      const recCall =
        loopVars.length === 0
          ? `(${helperName})`
          : `(${helperName} ${loopVars.join(" ")})`;
      const trueBranch = `(do ${bodyStr} ${recCall})`;

      // The "else" branch — when cond is false — returns the current
      // state. For a single loop var, return that var's value. For
      // multi-var, wrap in (list ...) — callers must destructure (or
      // we return only the first var for now).
      const elseBranch =
        loopVars.length === 1
          ? loopVars[0]!
          : `(list ${loopVars.join(" ")})`;

      // Helper definition + invocation. The invocation passes the
      // current bindings of the loop vars (which the enclosing scope
      // already has). For multi-var loops, destructure the returned
      // list back into the individual names so subsequent code reads
      // the updated values.
      const helperDef =
        `(defn ${helperName} (${loopVars.join(" ")}) (if ${cond} ${trueBranch} ${elseBranch}))`;
      let helperCall: string;
      if (loopVars.length === 1) {
        helperCall = `(let ${loopVars[0]} (${helperName} ${loopVars[0]}))`;
      } else {
        const resultName = `_while_${whileCounter}_result`;
        const destructure = loopVars
          .map((v, i) => `(let ${v} (nth ${resultName} ${i}))`)
          .join(" ");
        helperCall =
          `(let ${resultName} (${helperName} ${loopVars.join(" ")})) ` +
          destructure;
      }
      return `(do ${helperDef} ${helperCall})`;
    }

    default:
      throw new Error(
        `emitFk: unsupported Python CTOR '${ctor}' — needs grammar/kernel work to compile`,
      );
  }
}

function emitTrivial(k: Kernel, n: NodeID): string {
  if (n.level !== Level.TRIVIAL) {
    throw new Error("emitTrivial: not a trivial");
  }
  switch (n.type) {
    case Triv.INT:
      // INT (== INT32) trivials encode their value in the inst field.
      return String((n.inst | 0));
    case Triv.INT64: {
      // Python int default is INT64 in the TS parser; the kernel's
      // bootstrap reader parses .fk INT tokens as i64 (truncated to
      // i32 in the Rust kernel). For values that fit in i32 we emit
      // the integer literal; for genuinely-wide values, we still emit
      // the integer (the kernel will truncate, matching the existing
      // INT semantics).
      const v = k.decodeInt64(n.inst);
      return v.toString();
    }
    case Triv.INT8:
    case Triv.INT16:
    case Triv.UINT8:
    case Triv.UINT16:
    case Triv.UINT32:
      return String(n.inst | 0);
    case Triv.STRING:
      return JSON.stringify(k.strs[n.inst] ?? "");
    case Triv.BOOL:
      return n.inst !== 0 ? "true" : "false";
    case Triv.NULL:
      return "false"; // honest None→false fallback
    case Triv.FLOAT64: {
      // The Rust kernel's reader recognizes float tokens (digits + dot
      // + digits, optional exponent). Emit a form that always parses
      // back as float on the kernel side: include the dot even for
      // integer-valued floats (`1.0`, not `1`) so `(add 1.0 2)` routes
      // through the float-promotion arm instead of the int fast path.
      const f = k.decodeFloat64(n.inst);
      return formatFloatForFk(f);
    }
    default:
      // Higher-numeric trivials (FLOAT32, UINT64, etc.) aren't yet
      // representable in the kernel reader's bootstrap syntax. Honest
      // gap until the reader (or a Form-native parser) handles them.
      throw new Error(
        `emitTrivial: kernel reader can't represent trivial type ${n.type}`,
      );
  }
}

// formatFloatForFk — render an f64 as a token the Rust .fk reader
// recognizes as FLOAT. The reader requires at least one digit on either
// side of the dot, so integer-valued floats become "N.0" rather than
// "N". NaN and Inf have no .fk syntax — fall back to a sentinel that
// will surface as a parse error if it ever shows up (no current path
// emits these from a parsed Python literal).
function formatFloatForFk(f: number): string {
  if (Number.isNaN(f)) {
    throw new Error("emitTrivial: NaN has no .fk literal form");
  }
  if (!Number.isFinite(f)) {
    throw new Error("emitTrivial: Infinity has no .fk literal form");
  }
  const s = String(f);
  if (s.includes(".") || s.includes("e") || s.includes("E")) {
    return s;
  }
  return `${s}.0`;
}

function emitIdent(k: Kernel, n: NodeID): string {
  // An ident node carries one trivial-STRING child holding the name.
  if (n.level === Level.TRIVIAL && n.type === Triv.STRING) {
    return k.strs[n.inst] ?? "?";
  }
  const kids = capturedChildren(k, n);
  if (kids.length > 0) {
    const t = kids[0]!;
    if (t.level === Level.TRIVIAL && t.type === Triv.STRING) {
      return k.strs[t.inst] ?? "?";
    }
  }
  throw new Error("emitIdent: expected an ident shape");
}

// ---------------------------------------------------------------------------
// Class emission — the v1 minimum shape:
//
//   class Counter:
//       def __init__(self, start, step):
//           self.n = start
//           self.step = step
//       def increment(self):
//           return self.n + self.step
//
// Lowers to two lifted `defn`s plus a constructor `defn` bound at the
// class's own name:
//
//   (defn Counter__increment (self) (_plus (_get self "n") (_get self "step")))
//   (defn Counter (start step)
//       (do (let n start)
//           (let step step)
//           (list "__class__" "Counter" "n" n "step" step)))
//
// The constructor's body is the __init__ body, with `self.<f> = <expr>`
// lines lowered to `(let <f> <expr>)` for the local copy, and the final
// expression is the record literal — a flat alist with "__class__" as
// the first key so _dispatch can find the right method namespace.
//
// Restrictions in v1 (each is a named gap in the PR body):
//   - No inheritance, no super(), no decorators, no classmethods /
//     staticmethods, no metaclasses, no class-vars, no __slots__,
//     no dunder methods beyond __init__.
//   - __init__ body may only contain `self.<field> = <expr>` lines and
//     local-variable assignments. No conditional field assignment.
//   - Method bodies use `self.x` for read-only field access; field
//     writes mid-method aren't supported.
//   - No method-to-method call via self.other_method() chains within a
//     class body (dispatch lookup needs the receiver's __class__ to
//     resolve, which works for normal call sites).
//
// emitClass appends the lifted defns to the module-level liftedDefns
// list; the wrapper at the top of emitFk splices those in front of the
// program body before the kernel binary executes it.
// ---------------------------------------------------------------------------
function emitClass(
  k: Kernel,
  classKids: readonly NodeID[],
  opts: EmitFkOptions,
): void {
  const className = emitIdent(k, classKids[0]!);
  const methodList = capturedChildren(k, classKids[1]!);

  // Split methods into __init__ vs the rest.
  let initMethod: NodeID | null = null;
  const otherMethods: NodeID[] = [];
  for (const m of methodList) {
    const mKids = capturedChildren(k, m);
    const mName = emitIdent(k, mKids[0]!);
    if (mName === "__init__") {
      initMethod = m;
    } else {
      otherMethods.push(m);
    }
  }

  // --- Constructor (the class name itself, callable as Counter(2, 1)) -----
  // Each `self.<f> = expr` becomes a local `(let <f> expr)`; the final
  // value is `(list "__class__" "<ClassName>" "<f1>" <f1> ...)`.
  const fields: string[] = [];
  const initBindings: string[] = [];
  let ctorParams: string[] = [];
  if (initMethod !== null) {
    const initKids = capturedChildren(k, initMethod);
    const paramNodes = capturedChildren(k, initKids[1]!);
    // First param is `self` — skip; remaining are constructor args.
    ctorParams = paramNodes
      .slice(1)
      .map((p: NodeID) => emitIdent(k, p));
    const bodyNode = initKids[2]!;
    const bodyCtor = capturedCtor(k, bodyNode);
    const stmts =
      bodyCtor === CTOR.block ? capturedChildren(k, bodyNode) : [bodyNode];
    for (const stmt of stmts) {
      const stmtCtor = capturedCtor(k, stmt);
      if (stmtCtor !== CTOR.assign) {
        throw new Error(
          `emitFk: __init__ body must be only self.<field> = <expr> or local assigns (v1); got '${stmtCtor}'`,
        );
      }
      const stmtKids = capturedChildren(k, stmt);
      const target = stmtKids[0]!;
      const valueNode = stmtKids[1]!;
      const targetCtor = capturedCtor(k, target);
      if (targetCtor === CTOR.attr) {
        // self.<field> = expr — emit (let <field> expr); collect into fields.
        const recvCtor = capturedCtor(k, capturedChildren(k, target)[0]!);
        if (recvCtor !== CTOR.ident) {
          throw new Error(
            `emitFk: __init__ attribute target must be 'self.<field>' (v1)`,
          );
        }
        const recvName = emitIdent(k, capturedChildren(k, target)[0]!);
        if (recvName !== "self") {
          throw new Error(
            `emitFk: __init__ attribute target must be on 'self' (v1)`,
          );
        }
        const fieldName = emitIdent(k, capturedChildren(k, target)[1]!);
        if (!fields.includes(fieldName)) fields.push(fieldName);
        const valStr = emit(k, valueNode, opts);
        initBindings.push(`(let ${fieldName} ${valStr})`);
      } else if (targetCtor === CTOR.ident) {
        // local variable inside __init__ — emit (let name expr).
        const localName = emitIdent(k, target);
        const valStr = emit(k, valueNode, opts);
        initBindings.push(`(let ${localName} ${valStr})`);
      } else {
        throw new Error(
          `emitFk: __init__ assignment target must be self.<field> or a local (v1)`,
        );
      }
    }
  }

  // Constructor body: bindings followed by the record literal.
  const recordParts: string[] = [];
  recordParts.push(JSON.stringify("__class__"), JSON.stringify(className));
  for (const f of fields) {
    recordParts.push(JSON.stringify(f), f);
  }
  const recordExpr = `(list ${recordParts.join(" ")})`;
  const ctorBody =
    initBindings.length === 0
      ? recordExpr
      : `(do ${initBindings.join(" ")} ${recordExpr})`;
  liftedDefns.push(
    `(defn ${className} (${ctorParams.join(" ")}) ${ctorBody})`,
  );

  // --- Other methods (lifted as `<ClassName>__<methodName>`) --------------
  for (const m of otherMethods) {
    const mKids = capturedChildren(k, m);
    const mName = emitIdent(k, mKids[0]!);
    const paramNodes = capturedChildren(k, mKids[1]!);
    const paramNames = paramNodes.map((p: NodeID) => emitIdent(k, p));
    // First param must be `self`; we keep it as-is so attribute reads
    // (`self.x` → `(_get self "x")`) resolve at runtime.
    const body = emitDefBody(k, mKids[2]!, opts);
    liftedDefns.push(
      `(defn ${className}__${mName} (${paramNames.join(" ")}) ${body})`,
    );
  }
}
