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

import { Kernel, Level, Triv, type NodeID } from "./kernel.ts";
import { capturedCtor, capturedChildren } from "./languages.ts";
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
    const target = emitIdent(k, kids[0]!);
    const value = emit(k, kids[1]!, opts);
    const rest = emitStmtSeq(k, stmts, start + 1, opts);
    return `(do (let ${target} ${value}) ${rest})`;
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

// Recursively collect assignment-target names from any node in a
// subtree. Used by while/for emitters to find all loop-mutated
// variables, including those nested inside if-statements, blocks,
// etc. Names are returned in order of first encounter.
function collectAssignTargets(k: Kernel, n: NodeID, out: string[], seen: Set<string>): void {
  if (n.level === Level.TRIVIAL) return;
  const ctor = capturedCtor(k, n);
  const kids = capturedChildren(k, n);
  if (ctor === CTOR.assign) {
    const tn = emitIdent(k, kids[0]!);
    if (!seen.has(tn)) {
      seen.add(tn);
      out.push(tn);
    }
    // Also scan the value side — though assignments-into-assignments
    // (walrus) are unusual; skip for now.
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
      // kernel reader treats them as one program. Single-statement
      // modules emit bare to keep the .fk minimal.
      const parts = kids.map((c: NodeID) => emit(k, c, opts));
      if (parts.length === 1) return parts[0]!;
      return `(do ${parts.join(" ")})`;
    }
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
    case CTOR.add: return `(add ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
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

    case CTOR.list_literal: {
      const parts = kids.map((c: NodeID) => emit(k, c, opts));
      return parts.length === 0 ? "(list)" : `(list ${parts.join(" ")})`;
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
      // children: [target-ident-node, value-node]
      const target = emitIdent(k, kids[0]!);
      const value = emit(k, kids[1]!, opts);
      return `(let ${target} ${value})`;
    }

    // ── subscript ─────────────────────────────────────────────
    // Python `lst[i]` → kernel `(nth lst i)` using the existing nth
    // native. Closes the lst[i] gap the python_demo had to avoid.
    case "subscript": {
      // children: [value-node, slice-node]
      const value = emit(k, kids[0]!, opts);
      const slice = emit(k, kids[1]!, opts);
      return `(nth ${value} ${slice})`;
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
      const iterExpr = emit(k, kids[1]!, opts);
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
    default:
      // Higher-numeric trivials (FLOAT32/64, UINT64, etc.) aren't
      // representable in the kernel reader's bootstrap syntax today.
      // Honest gap until the reader (or a Form-native parser) handles them.
      throw new Error(
        `emitTrivial: kernel reader can't represent trivial type ${n.type}`,
      );
  }
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
