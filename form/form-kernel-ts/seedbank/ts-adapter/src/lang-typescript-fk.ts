// lang-typescript-fk.ts — emit kernel-native .fk from lang-typescript.ts trees.
//
//   TypeScript source bytes
//     → parseTypeScript (lang-typescript.ts)  — grammar capture tree
//     → emitTypeScriptFk (this file)          — .fk S-expressions
//     → form-kernel-rust binary               — native execution
//
// Vocabulary mirrors lang-ts-fk.ts so parity_suite ts-run agrees with
// node and ts-eval. Arrow functions lift to module-level defns.

import { Kernel, Level, Triv, type NodeID } from "../../../src/kernel.ts";
import { capturedCtor, capturedChildren } from "../../../src/languages.ts";

export interface EmitFkOptions {
  source_comments?: boolean;
}

let lambdaCounter = 0;
let liftedDefns: string[] = [];

function isNull(n: NodeID): boolean {
  return n.level === Level.TRIVIAL && n.type === Triv.NULL;
}

function ctorOf(k: Kernel, n: NodeID): string {
  return capturedCtor(k, n);
}

function childrenOf(k: Kernel, n: NodeID): readonly NodeID[] {
  return capturedChildren(k, n);
}

function peelExpr(n: NodeID, k: Kernel): NodeID {
  let cur = n;
  while (cur.level !== Level.TRIVIAL) {
    const ctor = ctorOf(k, cur);
    const kids = childrenOf(k, cur);
    if (ctor === "conditional" && kids.length >= 2 && isNull(kids[1]!)) {
      cur = kids[0]!;
      continue;
    }
    if (ctor === "binOp" && kids.length >= 2 && childrenOf(k, kids[1]!).length === 0) {
      cur = kids[0]!;
      continue;
    }
    if (ctor === "postfix" && kids.length >= 2 && childrenOf(k, kids[1]!).length === 0) {
      cur = kids[0]!;
      continue;
    }
    if (ctor === "assignment" && kids.length >= 2 && isNull(kids[1]!)) {
      cur = kids[0]!;
      continue;
    }
    break;
  }
  return cur;
}

function collectParamNames(k: Kernel, paramList: NodeID): string[] {
  const out: string[] = [];
  if (isNull(paramList)) return out;
  const kids = childrenOf(k, paramList);
  const first = kids[0]!;
  const firstKids = childrenOf(k, first);
  out.push(k.strs[firstKids[0]!.inst] ?? "");
  const tail = childrenOf(k, kids[1]!);
  for (const pair of tail) {
    const pk = childrenOf(k, pair);
    const p = pk[1]!;
    const ppk = childrenOf(k, p);
    out.push(k.strs[ppk[0]!.inst] ?? "");
  }
  return out;
}

export function emitTypeScriptFk(
  k: Kernel,
  tree: NodeID,
  opts: EmitFkOptions = {},
): string {
  lambdaCounter = 0;
  liftedDefns = [];
  const body = emitTopLevel(k, tree, opts);
  if (liftedDefns.length === 0) return body;
  const isBareDo = body.startsWith("(do ") && body.endsWith(")");
  if (isBareDo) {
    const inner = body.slice(4, body.length - 1);
    return `(do ${liftedDefns.join(" ")} ${inner})`;
  }
  return `(do ${liftedDefns.join(" ")} ${body})`;
}

function emitTopLevel(k: Kernel, n: NodeID, opts: EmitFkOptions): string {
  const ctor = ctorOf(k, n);
  if (ctor === "program") {
    const parts = childrenOf(k, n).map((c) => emitTopLevel(k, c, opts));
    if (parts.length === 1) return parts[0]!;
    return `(do ${parts.join(" ")})`;
  }
  if (ctor === "funcDecl") return emitFuncDecl(k, n, opts);
  if (ctor === "varDecl") return emitVarDecl(k, n, opts);
  if (ctor === "exprStmt") return emitExpr(k, childrenOf(k, n)[0]!, opts);
  throw new Error(`emitTypeScriptFk: unsupported top-level ctor "${ctor}"`);
}

function emitFuncDecl(k: Kernel, n: NodeID, opts: EmitFkOptions): string {
  const kids = childrenOf(k, n);
  const name = k.strs[kids[1]!.inst] ?? "?";
  const params = collectParamNames(k, kids[3]!);
  const body = emitBlockBody(k, kids[6]!, opts);
  return `(defn ${name} (${params.join(" ")}) ${body})`;
}

function emitVarDecl(k: Kernel, n: NodeID, opts: EmitFkOptions): string {
  const kids = childrenOf(k, n);
  const name = k.strs[kids[1]!.inst] ?? "?";
  let value = "false";
  if (!isNull(kids[3]!)) {
    const initKids = childrenOf(k, kids[3]!);
    value = emitExpr(k, initKids[1]!, opts);
  }
  return `(let ${name} ${value})`;
}

function emitBlockBody(k: Kernel, blockNode: NodeID, opts: EmitFkOptions): string {
  const kids = childrenOf(k, blockNode);
  const stmts = childrenOf(k, kids[1]!);
  if (stmts.length === 1) {
    const ctor = ctorOf(k, stmts[0]!);
    if (ctor === "ifStmt") return emitIfAsExpr(k, stmts[0]!, null, opts);
    if (ctor === "returnStmt") return emitReturnValue(k, stmts[0]!, opts);
  }
  return emitStmtSeq(k, stmts, 0, opts);
}

function emitReturnValue(k: Kernel, returnNode: NodeID, opts: EmitFkOptions): string {
  const kids = childrenOf(k, returnNode);
  if (isNull(kids[1]!)) return "false";
  return emitExpr(k, kids[1]!, opts);
}

function emitStmtValue(k: Kernel, stmt: NodeID, opts: EmitFkOptions): string {
  const ctor = ctorOf(k, stmt);
  if (ctor === "block") return emitBlockBody(k, stmt, opts);
  if (ctor === "ifStmt") return emitIfAsExpr(k, stmt, null, opts);
  if (ctor === "returnStmt") return emitReturnValue(k, stmt, opts);
  if (ctor === "exprStmt") return emitExpr(k, childrenOf(k, stmt)[0]!, opts);
  throw new Error(`emitStmtValue: unsupported stmt ctor "${ctor}"`);
}

function emitIfAsExpr(
  k: Kernel,
  ifNode: NodeID,
  fallthrough: string | null,
  opts: EmitFkOptions,
): string {
  const kids = childrenOf(k, ifNode);
  const cond = emitExpr(k, kids[2]!, opts);
  const thenVal = emitStmtValue(k, kids[4]!, opts);
  let elseVal = fallthrough ?? "false";
  if (!isNull(kids[5]!)) {
    const elseKids = childrenOf(k, kids[5]!);
    elseVal = emitStmtValue(k, elseKids[1]!, opts);
  }
  return `(if ${cond} ${thenVal} ${elseVal})`;
}

function emitStmtSeq(
  k: Kernel,
  stmts: readonly NodeID[],
  start: number,
  opts: EmitFkOptions,
): string {
  if (start >= stmts.length) return "false";
  const stmt = stmts[start]!;
  const ctor = ctorOf(k, stmt);
  if (ctor === "returnStmt") return emitReturnValue(k, stmt, opts);
  if (ctor === "ifStmt") return emitIfInDefBody(k, stmt, stmts, start, opts);
  if (ctor === "varDecl") {
    const bind = emitVarDecl(k, stmt, opts);
    const rest = emitStmtSeq(k, stmts, start + 1, opts);
    return `(do ${bind} ${rest})`;
  }
  const side = emitTopLevel(k, stmt, opts);
  const rest = emitStmtSeq(k, stmts, start + 1, opts);
  return start + 1 >= stmts.length ? side : `(do ${side} ${rest})`;
}

function emitIfInDefBody(
  k: Kernel,
  ifNode: NodeID,
  stmts: readonly NodeID[],
  start: number,
  opts: EmitFkOptions,
): string {
  const fallthrough = emitStmtSeq(k, stmts, start + 1, opts);
  return emitIfAsExpr(k, ifNode, fallthrough, opts);
}

function emitExpr(k: Kernel, n: NodeID, opts: EmitFkOptions): string {
  n = peelExpr(n, k);
  if (n.level === Level.TRIVIAL) return emitTrivial(k, n);

  const ctor = ctorOf(k, n);
  const kids = childrenOf(k, n);
  switch (ctor) {
    case "numLit":
      return emitTrivial(k, kids[0]!);
    case "bigintLit":
      return emitTrivial(k, kids[0]!);
    case "boolLit": {
      const t = k.strs[kids[0]!.inst] ?? "";
      return t === "true" ? "true" : "false";
    }
    case "strLit": {
      const raw = k.strs[kids[0]!.inst] ?? '""';
      return JSON.stringify(raw.substring(1, raw.length - 1));
    }
    case "nullLit":
      return "false";
    case "identExpr": {
      const name = k.strs[kids[0]!.inst] ?? "?";
      return name;
    }
    case "paren":
      return emitExpr(k, kids[1]!, opts);
    case "unary": {
      const op = k.strs[kids[0]!.inst] ?? "";
      const operand = emitExpr(k, kids[1]!, opts);
      if (op === "-") return `(sub 0 ${operand})`;
      if (op === "+") return operand;
      if (op === "!") return `(not ${operand})`;
      throw new Error(`emitExpr: unsupported unary op "${op}"`);
    }
    case "binOp": {
      let acc = emitExpr(k, kids[0]!, opts);
      const tail = childrenOf(k, kids[1]!);
      for (const pair of tail) {
        const pk = childrenOf(k, pair);
        const op = k.strs[pk[0]!.inst] ?? "";
        const rhs = emitExpr(k, pk[1]!, opts);
        acc = emitBinOp(op, acc, rhs);
      }
      return acc;
    }
    case "conditional": {
      if (!isNull(kids[1]!)) {
        const t = childrenOf(k, kids[1]!);
        return `(if ${emitExpr(k, kids[0]!, opts)} ${emitExpr(k, t[1]!, opts)} ${emitExpr(k, t[3]!, opts)})`;
      }
      return emitExpr(k, kids[0]!, opts);
    }
    case "callExpr":
      return emitCallExpr(k, n, opts);
    case "arrowFunc": {
      const params = collectParamNames(k, kids[1]!);
      const bodyNode = kids[5]!;
      const bodyCtor = ctorOf(k, bodyNode);
      const bodyStr =
        bodyCtor === "block"
          ? emitBlockBody(k, bodyNode, opts)
          : emitExpr(k, bodyNode, opts);
      const name = `_lambda_${lambdaCounter++}`;
      liftedDefns.push(`(defn ${name} (${params.join(" ")}) ${bodyStr})`);
      return name;
    }
    case "arrayLit": {
      const parts: string[] = [];
      if (!isNull(kids[1]!)) {
        const inner = childrenOf(k, kids[1]!);
        parts.push(emitExpr(k, inner[0]!, opts));
        const tail = childrenOf(k, inner[1]!);
        for (const pair of tail) {
          const pk = childrenOf(k, pair);
          parts.push(emitExpr(k, pk[1]!, opts));
        }
      }
      return parts.length === 0 ? "(list)" : `(list ${parts.join(" ")})`;
    }
    default:
      throw new Error(`emitExpr: unsupported ctor "${ctor}"`);
  }
}

function emitCallExpr(k: Kernel, n: NodeID, opts: EmitFkOptions): string {
  const kids = childrenOf(k, n);
  const primary = peelExpr(kids[0]!, k);
  const tails = childrenOf(k, kids[1]!);
  if (tails.length === 0) {
    return emitExpr(k, primary, opts);
  }
  const callee = emitExpr(k, primary, opts);
  const argStrs: string[] = [];
  for (const t of tails) {
    const tctor = ctorOf(k, t);
    const tkids = childrenOf(k, t);
    if (tctor === "callTail") {
      if (!isNull(tkids[1]!)) {
        const argKids = childrenOf(k, tkids[1]!);
        argStrs.push(emitExpr(k, argKids[0]!, opts));
        const argTail = childrenOf(k, argKids[1]!);
        for (const pair of argTail) {
          const pk = childrenOf(k, pair);
          argStrs.push(emitExpr(k, pk[1]!, opts));
        }
      }
      continue;
    }
    throw new Error(`emitCallExpr: unsupported tail ctor "${tctor}"`);
  }
  return argStrs.length === 0 ? `(${callee})` : `(${callee} ${argStrs.join(" ")})`;
}

function emitBinOp(op: string, left: string, right: string): string {
  switch (op) {
    case "+":
      // TS + may concat strings; legacy lang-ts-fk uses _plus for parity demos.
      return `(_plus ${left} ${right})`;
    case "-":
      return `(sub ${left} ${right})`;
    case "*":
      return `(mul ${left} ${right})`;
    case "/":
      return `(div ${left} ${right})`;
    case "%":
      return `(mod ${left} ${right})`;
    case "<":
      return `(lt ${left} ${right})`;
    case "<=":
      return `(le ${left} ${right})`;
    case ">":
      return `(gt ${left} ${right})`;
    case ">=":
      return `(ge ${left} ${right})`;
    case "==":
    case "===":
      return `(eq ${left} ${right})`;
    case "!=":
    case "!==":
      return `(ne ${left} ${right})`;
    case "&&":
      return `(and ${left} ${right})`;
    case "||":
      return `(or ${left} ${right})`;
    default:
      throw new Error(`emitBinOp: unsupported op "${op}"`);
  }
}

function emitTrivial(k: Kernel, n: NodeID): string {
  if (n.level !== Level.TRIVIAL) {
    throw new Error("emitTrivial: not a trivial");
  }
  switch (n.type) {
    case Triv.INT:
      return String(n.inst | 0);
    case Triv.INT64:
      return k.decodeInt64(n.inst).toString();
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
      throw new Error(`emitTrivial: unsupported trivial type ${n.type}`);
  }
}

function formatFloatForFk(f: number): string {
  if (Number.isNaN(f)) throw new Error("emitTrivial: NaN has no .fk literal form");
  if (!Number.isFinite(f)) throw new Error("emitTrivial: Infinity has no .fk literal form");
  const s = String(f);
  if (s.includes(".") || s.includes("e") || s.includes("E")) return s;
  return `${s}.0`;
}
