// lang-ts-fk.ts — emit kernel-native .fk S-expression source from a
// parsed TypeScript Form tree.
//
//   TypeScript source bytes
//     → parseTypeScript (lang-ts.ts)         — TS parser → Form tree
//     → emitFk (this file)                   — Form tree → kernel-native .fk
//     → form-kernel-rust binary              — walks the .fk, no host runtime
//
// CTOR vocabulary is shared with the Python adapter, so the emission
// rules below are intentionally parallel to lang-python-fk.ts. Arrow
// functions emit as `defn` (the kernel's statement-level binder), with
// lifting for inline lambdas — same shape as Python's lifted lambdas.

import { Kernel, Level, Triv, type NodeID } from "../../../src/kernel.ts";
import { capturedCtor, capturedChildren } from "../../../src/languages.ts";
import { CTOR } from "./lang-ts.ts";

export interface EmitFkOptions {
  source_comments?: boolean;
}

let lambdaCounter = 0;
let liftedDefns: string[] = [];

// Walk a subtree to see if it contains a `return` along any path.
// Used by emitDefBody to know whether an if-statement short-circuits.
function containsReturn(k: Kernel, n: NodeID): boolean {
  if (n.level === Level.TRIVIAL) return false;
  const ctor = capturedCtor(k, n);
  if (ctor === CTOR.return_) return true;
  if (ctor === CTOR.def_ || ctor === CTOR.lambda_) return false;
  for (const c of capturedChildren(k, n)) {
    if (containsReturn(k, c)) return true;
  }
  return false;
}

function containsStringLiteral(k: Kernel, n: NodeID): boolean {
  if (n.level === Level.TRIVIAL) return n.type === Triv.STRING;
  const ctor = capturedCtor(k, n);
  if (ctor === CTOR.str_literal) return true;
  if (ctor === CTOR.def_ || ctor === CTOR.lambda_) return false;
  for (const c of capturedChildren(k, n)) {
    if (containsStringLiteral(k, c)) return true;
  }
  return false;
}

// CPS-style emission of a TS function body (block of statements).
// Mirrors emitDefBody from the Python adapter: early returns
// short-circuit; if-without-else falls through to the remaining stmts.
function emitDefBody(k: Kernel, bodyNode: NodeID, opts: EmitFkOptions): string {
  const bodyCtor = capturedCtor(k, bodyNode);
  const stmts =
    bodyCtor === CTOR.block ? capturedChildren(k, bodyNode) : [bodyNode];
  return emitStmtSeq(k, stmts, 0, opts);
}

function emitStmtSeq(
  k: Kernel,
  stmts: readonly NodeID[],
  start: number,
  opts: EmitFkOptions,
): string {
  if (start >= stmts.length) return "false"; // implicit fallthrough → null
  const stmt = stmts[start]!;
  const ctor = capturedCtor(k, stmt);
  const kids = capturedChildren(k, stmt);

  if (ctor === CTOR.return_) {
    return emit(k, kids[0]!, opts);
  }

  if (ctor === CTOR.if_) {
    return emitIfInDefBody(k, kids, stmts, start, opts);
  }

  if (ctor === CTOR.assign) {
    const target = emitIdent(k, kids[0]!);
    const value = emit(k, kids[1]!, opts);
    const rest = emitStmtSeq(k, stmts, start + 1, opts);
    return `(do (let ${target} ${value}) ${rest})`;
  }

  // Side-effect statement — emit then continue.
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
  let i = ifKids.length;
  let elseAcc: string;
  if (i % 2 === 1) {
    const elseNode = ifKids[i - 1]!;
    elseAcc = emitBlockInDefBody(k, elseNode, stmts, start + 1, opts);
    i -= 1;
  } else {
    elseAcc = emitStmtSeq(k, stmts, start + 1, opts);
  }
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
    return emitStmtSeq(k, blockStmts, 0, opts);
  }
  const sideEffectStrs = blockStmts.map((s) => emit(k, s, opts));
  const outerRest = emitStmtSeq(k, outerStmts, outerStart, opts);
  return sideEffectStrs.length === 0
    ? outerRest
    : `(do ${sideEffectStrs.join(" ")} ${outerRest})`;
}

export function emitFk(k: Kernel, tree: NodeID, opts: EmitFkOptions = {}): string {
  lambdaCounter = 0;
  liftedDefns = [];
  const body = emit(k, tree, opts);
  if (liftedDefns.length === 0) return body;
  const isBareDo = body.startsWith("(do ") && body.endsWith(")");
  if (isBareDo) {
    const inner = body.slice(4, body.length - 1);
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
      // No null literal in the kernel reader; honest fallback to "false"
      // (same as Python None). Carries TS truthiness across the seam.
      return "false";

    case CTOR.ident: {
      const t = kids[0]!;
      if (t.level === Level.TRIVIAL && t.type === Triv.STRING) {
        return k.strs[t.inst] ?? "?ident";
      }
      return "?ident";
    }

    case CTOR.add: {
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

    case CTOR.eq: return `(eq ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.ne: return `(ne ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.lt: return `(lt ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.le: return `(le ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.gt: return `(gt ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.ge: return `(ge ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;

    case CTOR.and_: return `(and ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.or_:  return `(or ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)})`;
    case CTOR.not_: return `(not ${emit(k, kids[0]!, opts)})`;

    case CTOR.if_: {
      // Ternary (expression form): exactly 3 kids, middle is NOT a block.
      const isExpr =
        kids.length === 3 && capturedCtor(k, kids[1]!) !== CTOR.block;
      if (isExpr) {
        return `(if ${emit(k, kids[0]!, opts)} ${emit(k, kids[1]!, opts)} ${emit(k, kids[2]!, opts)})`;
      }
      // Statement form
      const stmts: string[] = [];
      let i = 0;
      while (i + 1 < kids.length) {
        stmts.push(emit(k, kids[i]!, opts));
        stmts.push(emit(k, kids[i + 1]!, opts));
        i += 2;
      }
      const elseBranch =
        i < kids.length ? emit(k, kids[i]!, opts) : "false";
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
      return emit(k, kids[0]!, opts);

    case CTOR.def_: {
      const name = emitIdent(k, kids[0]!);
      const paramNodes = capturedChildren(k, kids[1]!);
      const paramNames = paramNodes.map((p: NodeID) => emitIdent(k, p));
      const body = emitDefBody(k, kids[2]!, opts);
      return `(defn ${name} (${paramNames.join(" ")}) ${body})`;
    }

    case CTOR.lambda_: {
      // Arrow function: `(x) => expr` or `(x) => { ... }`.
      // Lift to module-level defn with a synthesized name, same as
      // python-adapter's lambda treatment.
      const paramNodes = capturedChildren(k, kids[0]!);
      const paramNames = paramNodes.map((p: NodeID) => emitIdent(k, p));
      const bodyNode = kids[1]!;
      const bodyCtor = capturedCtor(k, bodyNode);
      // If body is a block, run it through the def-body CPS lowering so
      // early-return short-circuits work. If it's a bare expression,
      // emit it directly.
      const bodyStr =
        bodyCtor === CTOR.block
          ? emitDefBody(k, bodyNode, opts)
          : emit(k, bodyNode, opts);
      const name = `_lambda_${lambdaCounter++}`;
      liftedDefns.push(`(defn ${name} (${paramNames.join(" ")}) ${bodyStr})`);
      return name;
    }

    case CTOR.call: {
      const calleeNode = kids[0]!;
      const argsNode = kids[1];
      const argNodes = argsNode !== undefined ? capturedChildren(k, argsNode) : [];
      const argStrs = argNodes.map((a: NodeID) => emit(k, a, opts));
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

    case CTOR.assign: {
      const target = emitIdent(k, kids[0]!);
      const value = emit(k, kids[1]!, opts);
      return `(let ${target} ${value})`;
    }

    default:
      throw new Error(
        `emitFk: unsupported TS CTOR '${ctor}' — needs grammar/kernel work to compile`,
      );
  }
}

function emitTrivial(k: Kernel, n: NodeID): string {
  if (n.level !== Level.TRIVIAL) {
    throw new Error("emitTrivial: not a trivial");
  }
  switch (n.type) {
    case Triv.INT:
      return String(n.inst | 0);
    case Triv.INT64: {
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
      return "false";
    case Triv.FLOAT64: {
      const f = k.decodeFloat64(n.inst);
      return formatFloatForFk(f);
    }
    default:
      throw new Error(
        `emitTrivial: kernel reader can't represent trivial type ${n.type}`,
      );
  }
}

function formatFloatForFk(f: number): string {
  if (Number.isNaN(f)) throw new Error("emitTrivial: NaN has no .fk literal form");
  if (!Number.isFinite(f)) throw new Error("emitTrivial: Infinity has no .fk literal form");
  const s = String(f);
  if (s.includes(".") || s.includes("e") || s.includes("E")) return s;
  return `${s}.0`;
}

function emitIdent(k: Kernel, n: NodeID): string {
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
