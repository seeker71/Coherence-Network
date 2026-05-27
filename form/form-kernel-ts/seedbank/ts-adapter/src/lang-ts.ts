// lang-ts.ts — TypeScript (small subset) as a substrate-resident Language cell.
//
// The destination half PYTHON_PIPELINE_STATUS.md names as `ts-grammar.form
// 0/?`. python-adapter is the template; this adapter's ctor vocabulary
// reuses Python's CTOR names so semantically-equivalent fragments —
// `(x) => x + 1` in TS, `lambda x: x + 1` in Python — intern to the same
// recipe NodeIDs by content-addressing. That is the cross-language
// identity the language-cells architecture exists to make load-bearing.
//
// Subset shipped in this bootstrap breath (the smallest closing one):
//   - arrow functions: `(x) => x + 1`, `(a, b) => { return a + b; }`
//   - `const` / `let` bindings (no destructuring, no type annotations)
//   - `if` / `else` statements + ternary `c ? a : b`
//   - arithmetic: `+ - * / %`, unary `-`, `!`
//   - comparison: `== === != !== < <= > >=` (=== folds to ==)
//   - logic: `&& ||`
//   - function calls, return, recursion
//   - number / string / boolean / null literals, identifiers
//   - block `{ ... }` and expression-statement
//
// Pending (each is its own breath, named honestly here so we don't fake
// progress): classes, interfaces, generics, modules / import / export,
// async / await, JSX, type annotations beyond bare-name skip, enums,
// destructuring, spread, template literals, regex, switch, try/catch,
// optional chaining, nullish coalescing.

import {
  Frame,
  Kernel,
  Level,
  RBasic,
  Triv,
  type NodeID,
  type Value,
} from "../../../src/kernel.ts";
import {
  capturedChildren,
  capturedCtor,
} from "../../../src/languages.ts";

// ---------------------------------------------------------------------------
// CTOR — shared vocabulary with the Python adapter.
//
// Names are deliberately the same as lang-python.ts so a TS arrow
// `(x) => x + 1` and a Python lambda `lambda x: x + 1` capture into
// the same `lambda` / `param` / `add` / `int-literal` recipe shape.
// Same Blueprint → same NodeID → cross-language identity for free.
// ---------------------------------------------------------------------------

export const CTOR = {
  module: "module",
  // Literals
  int_literal: "int-literal",
  float_literal: "float-literal",
  str_literal: "str-literal",
  bool_literal: "bool-literal",
  none_literal: "none-literal", // TS null/undefined → none
  ident: "ident",
  // Collections
  list_literal: "list-literal",
  // Calls
  call: "call",
  args: "args",
  // Operators — names align with Python adapter
  add: "add",
  sub: "sub",
  mul: "mul",
  div: "div",
  mod: "mod",
  eq: "eq",
  ne: "ne",
  lt: "lt",
  le: "le",
  gt: "gt",
  ge: "ge",
  and_: "and",
  or_: "or",
  not_: "not",
  neg: "neg",
  // Statements
  if_: "if",
  def_: "def",       // arrow functions lower to `def` for cross-language identity
  return_: "return",
  lambda_: "lambda",
  expr_stmt: "expr-stmt",
  assign: "assign",  // `let x = e` re-binds (Python: same)
  // Function/lambda params
  params: "params",
  param: "param",
  block: "block",
} as const;

// ---------------------------------------------------------------------------
// Recursive-descent parser — produces the captured-recipe shape that
// shares its CTOR vocabulary with the Python adapter.
// ---------------------------------------------------------------------------

interface Cursor {
  readonly src: string;
  pos: number;
}

function ctorCategory(k: Kernel, ctor: string): NodeID {
  return {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.LIST,
    inst: k.internName(ctor),
  };
}

function captureNode(k: Kernel, ctor: string, children: NodeID[]): NodeID {
  return k.intern(ctorCategory(k, ctor), children);
}

function skipWS(c: Cursor): void {
  // Skip spaces, tabs, newlines, and `//` line-comments + `/* */` block
  // comments. Semicolons are skipped at the statement level.
  while (c.pos < c.src.length) {
    const ch = c.src.charCodeAt(c.pos);
    if (ch === 32 || ch === 9 || ch === 10 || ch === 13) {
      c.pos++;
    } else if (ch === 47 && c.src.charCodeAt(c.pos + 1) === 47 /* // */) {
      while (c.pos < c.src.length && c.src.charCodeAt(c.pos) !== 10) c.pos++;
    } else if (ch === 47 && c.src.charCodeAt(c.pos + 1) === 42 /* /* */) {
      c.pos += 2;
      while (c.pos + 1 < c.src.length) {
        if (c.src.charCodeAt(c.pos) === 42 && c.src.charCodeAt(c.pos + 1) === 47) {
          c.pos += 2;
          break;
        }
        c.pos++;
      }
    } else {
      break;
    }
  }
}

function atEnd(c: Cursor): boolean {
  return c.pos >= c.src.length;
}

function peek(c: Cursor): string {
  return c.src[c.pos] ?? "";
}

function startsWith(c: Cursor, lit: string): boolean {
  return c.src.startsWith(lit, c.pos);
}

function consume(c: Cursor, lit: string): boolean {
  skipWS(c);
  if (startsWith(c, lit)) {
    c.pos += lit.length;
    return true;
  }
  return false;
}

function expect(c: Cursor, lit: string): void {
  if (!consume(c, lit)) {
    throw new SyntaxError(
      `ts: expected '${lit}' at position ${c.pos} (got ` +
        JSON.stringify(c.src.substring(c.pos, c.pos + 16)) +
        ")",
    );
  }
}

function isIdentStart(ch: number): boolean {
  return (ch >= 65 && ch <= 90) || (ch >= 97 && ch <= 122) || ch === 95 || ch === 36;
}

function isIdentCont(ch: number): boolean {
  return isIdentStart(ch) || (ch >= 48 && ch <= 57);
}

const KEYWORDS = new Set([
  "const", "let", "var", "if", "else", "return", "function",
  "true", "false", "null", "undefined", "while", "for", "in", "of",
]);

function readIdentRaw(c: Cursor): string | null {
  skipWS(c);
  const start = c.pos;
  if (atEnd(c) || !isIdentStart(c.src.charCodeAt(start))) return null;
  let pos = start + 1;
  while (pos < c.src.length && isIdentCont(c.src.charCodeAt(pos))) pos++;
  c.pos = pos;
  return c.src.substring(start, pos);
}

function peekKeyword(c: Cursor, kw: string): boolean {
  const saved = c.pos;
  skipWS(c);
  if (!startsWith(c, kw)) {
    c.pos = saved;
    return false;
  }
  const after = c.pos + kw.length;
  if (after < c.src.length) {
    const ch = c.src.charCodeAt(after);
    if (isIdentCont(ch)) {
      c.pos = saved;
      return false;
    }
  }
  c.pos = saved;
  return true;
}

function consumeKeyword(c: Cursor, kw: string): boolean {
  if (peekKeyword(c, kw)) {
    skipWS(c);
    c.pos += kw.length;
    return true;
  }
  return false;
}

// ----- numeric literal -----

function parseNumber(k: Kernel, c: Cursor): NodeID | null {
  skipWS(c);
  const start = c.pos;
  let pos = start;
  while (pos < c.src.length && c.src.charCodeAt(pos) >= 48 && c.src.charCodeAt(pos) <= 57)
    pos++;
  if (pos === start) return null;
  let isFloat = false;
  if (pos < c.src.length && c.src.charCodeAt(pos) === 46 /* '.' */) {
    const after = c.src.charCodeAt(pos + 1) || 0;
    if (after >= 48 && after <= 57) {
      isFloat = true;
      pos++;
      while (pos < c.src.length && c.src.charCodeAt(pos) >= 48 && c.src.charCodeAt(pos) <= 57)
        pos++;
    }
  }
  const text = c.src.substring(start, pos);
  c.pos = pos;
  if (isFloat) {
    const value = k.internTrivialFloat64(parseFloat(text));
    return captureNode(k, CTOR.float_literal, [value]);
  }
  const n = BigInt(text);
  const value = k.internTrivialInt64(n);
  return captureNode(k, CTOR.int_literal, [value]);
}

// ----- string literal -----

function parseString(k: Kernel, c: Cursor): NodeID | null {
  skipWS(c);
  if (atEnd(c)) return null;
  const ch = peek(c);
  if (ch !== '"' && ch !== "'" && ch !== "`") return null;
  const quote = ch;
  c.pos++;
  const start = c.pos;
  let out = "";
  while (c.pos < c.src.length) {
    const cur = c.src[c.pos]!;
    if (cur === quote) {
      const text = out === "" ? c.src.substring(start, c.pos) : out;
      c.pos++;
      const str = k.internString(text);
      return captureNode(k, CTOR.str_literal, [str]);
    }
    if (c.src.charCodeAt(c.pos) === 92 /* '\\' */ && c.pos + 1 < c.src.length) {
      if (out === "") out = c.src.substring(start, c.pos);
      const nx = c.src[c.pos + 1]!;
      switch (nx) {
        case "n": out += "\n"; break;
        case "t": out += "\t"; break;
        case "r": out += "\r"; break;
        case "\\": out += "\\"; break;
        case "'": out += "'"; break;
        case '"': out += '"'; break;
        case "`": out += "`"; break;
        default: out += nx;
      }
      c.pos += 2;
      continue;
    }
    if (out !== "") out += cur;
    c.pos++;
  }
  throw new SyntaxError(`ts: unterminated string at position ${start}`);
}

// ----- expression precedence -----
// Expression hierarchy (subset):
//   conditional `c ? a : b`
//   ||
//   &&
//   comparison
//   add/sub
//   mul/div/mod
//   unary - / !
//   call
//   atom

function parseAtom(k: Kernel, c: Cursor): NodeID | null {
  skipWS(c);
  if (atEnd(c)) return null;

  // Parenthesized expression OR arrow function with paren-wrapped params
  if (peek(c) === "(") {
    const saved = c.pos;
    // Try to parse as arrow function first.
    const arrow = tryParseArrow(k, c);
    if (arrow !== null) return arrow;
    c.pos = saved;
    // Plain parenthesized expression
    expect(c, "(");
    const e = parseExpr(k, c);
    if (e === null) throw new SyntaxError(`ts: expression required after '(' at ${c.pos}`);
    expect(c, ")");
    return e;
  }

  // Array literal
  if (consume(c, "[")) {
    const items: NodeID[] = [];
    skipWS(c);
    if (!consume(c, "]")) {
      const first = parseExpr(k, c);
      if (first !== null) items.push(first);
      while (consume(c, ",")) {
        skipWS(c);
        if (peek(c) === "]") break;
        const next = parseExpr(k, c);
        if (next === null) break;
        items.push(next);
      }
      skipWS(c);
      expect(c, "]");
    }
    return captureNode(k, CTOR.list_literal, items);
  }

  // Keyword literals
  if (peekKeyword(c, "true")) {
    consumeKeyword(c, "true");
    return captureNode(k, CTOR.bool_literal, [k.internTrivialBool(true)]);
  }
  if (peekKeyword(c, "false")) {
    consumeKeyword(c, "false");
    return captureNode(k, CTOR.bool_literal, [k.internTrivialBool(false)]);
  }
  if (peekKeyword(c, "null") || peekKeyword(c, "undefined")) {
    if (peekKeyword(c, "null")) consumeKeyword(c, "null");
    else consumeKeyword(c, "undefined");
    return captureNode(k, CTOR.none_literal, []);
  }

  // Unary -, !
  if (peek(c) === "-") {
    c.pos++;
    const inner = parseUnary(k, c);
    if (inner === null) throw new SyntaxError(`ts: expr after unary '-' at ${c.pos}`);
    return captureNode(k, CTOR.neg, [inner]);
  }
  if (peek(c) === "!") {
    c.pos++;
    const inner = parseUnary(k, c);
    if (inner === null) throw new SyntaxError(`ts: expr after unary '!' at ${c.pos}`);
    return captureNode(k, CTOR.not_, [inner]);
  }

  // String
  const s = parseString(k, c);
  if (s !== null) return s;

  // Number
  const n = parseNumber(k, c);
  if (n !== null) return n;

  // Single-arg arrow without parens: `x => expr`
  // Try ident-then-=> form.
  const savedPos = c.pos;
  const name = readIdentRaw(c);
  if (name !== null) {
    if (KEYWORDS.has(name)) {
      c.pos = savedPos;
      return null;
    }
    // Check for `=>` to see if this is a single-arg arrow.
    const afterIdent = c.pos;
    skipWS(c);
    if (startsWith(c, "=>")) {
      c.pos += 2;
      const param = captureNode(k, CTOR.param, [k.internString(name)]);
      const params = captureNode(k, CTOR.params, [param]);
      const body = parseArrowBody(k, c);
      return captureNode(k, CTOR.lambda_, [params, body]);
    }
    c.pos = afterIdent;
    return captureNode(k, CTOR.ident, [k.internString(name)]);
  }

  return null;
}

// tryParseArrow — attempt `(p1, p2, ...) => body`. Backtrack and return
// null if the shape isn't an arrow.
function tryParseArrow(k: Kernel, c: Cursor): NodeID | null {
  const saved = c.pos;
  if (!consume(c, "(")) {
    c.pos = saved;
    return null;
  }
  const params: NodeID[] = [];
  skipWS(c);
  if (!consume(c, ")")) {
    while (true) {
      skipWS(c);
      const name = readIdentRaw(c);
      if (name === null) {
        c.pos = saved;
        return null;
      }
      // Skip optional `: Type` annotation by scanning to next `,` or `)`.
      skipWS(c);
      if (peek(c) === ":") {
        c.pos++;
        // Crude type-annotation skip — eat tokens until `,` or `)` at depth 0.
        let depth = 0;
        while (c.pos < c.src.length) {
          const ch = peek(c);
          if (depth === 0 && (ch === "," || ch === ")")) break;
          if (ch === "(" || ch === "<" || ch === "[" || ch === "{") depth++;
          else if (ch === ")" || ch === ">" || ch === "]" || ch === "}") depth--;
          c.pos++;
        }
      }
      params.push(captureNode(k, CTOR.param, [k.internString(name)]));
      if (!consume(c, ",")) break;
    }
    if (!consume(c, ")")) {
      c.pos = saved;
      return null;
    }
  }
  // Optional return-type annotation: `) : T => body`. Skip-to-`=>`.
  skipWS(c);
  if (peek(c) === ":") {
    c.pos++;
    while (c.pos < c.src.length && !startsWith(c, "=>")) c.pos++;
  }
  skipWS(c);
  if (!startsWith(c, "=>")) {
    c.pos = saved;
    return null;
  }
  c.pos += 2;
  const body = parseArrowBody(k, c);
  const paramsNode = captureNode(k, CTOR.params, params);
  return captureNode(k, CTOR.lambda_, [paramsNode, body]);
}

// parseArrowBody — either `{ stmts; }` (treated as a def body) or a single
// expression. For block bodies we wrap as CTOR.block; for expr bodies we
// wrap the expression in an implicit `return` so the lambda's value is
// the expression — matches the kernel's defn semantics.
function parseArrowBody(k: Kernel, c: Cursor): NodeID {
  skipWS(c);
  if (peek(c) === "{") {
    return parseBlock(k, c);
  }
  const e = parseExpr(k, c);
  if (e === null) throw new SyntaxError(`ts: arrow body expression required at ${c.pos}`);
  return e;
}

function parseCallChain(k: Kernel, c: Cursor): NodeID | null {
  let node = parseAtom(k, c);
  if (node === null) return null;
  while (true) {
    skipWS(c);
    if (peek(c) === "(") {
      c.pos++;
      const args = parseArgs(k, c);
      expect(c, ")");
      node = captureNode(k, CTOR.call, [node, args]);
      continue;
    }
    break;
  }
  return node;
}

function parseArgs(k: Kernel, c: Cursor): NodeID {
  const args: NodeID[] = [];
  skipWS(c);
  if (peek(c) === ")") return captureNode(k, CTOR.args, []);
  while (true) {
    skipWS(c);
    const e = parseExpr(k, c);
    if (e === null) break;
    args.push(e);
    skipWS(c);
    if (!consume(c, ",")) break;
  }
  return captureNode(k, CTOR.args, args);
}

function parseUnary(k: Kernel, c: Cursor): NodeID | null {
  skipWS(c);
  if (peek(c) === "-") {
    c.pos++;
    const inner = parseUnary(k, c);
    if (inner === null) return null;
    return captureNode(k, CTOR.neg, [inner]);
  }
  if (peek(c) === "!") {
    c.pos++;
    const inner = parseUnary(k, c);
    if (inner === null) return null;
    return captureNode(k, CTOR.not_, [inner]);
  }
  return parseCallChain(k, c);
}

function parseMul(k: Kernel, c: Cursor): NodeID | null {
  let left = parseUnary(k, c);
  if (left === null) return null;
  while (true) {
    skipWS(c);
    // Don't consume `*` / `/` / `%` when followed by `=` (augmented assign,
    // not supported v0 — but defensive against future expansion).
    if (c.pos + 1 < c.src.length && c.src.charCodeAt(c.pos + 1) === 61) {
      const ch = c.src.charCodeAt(c.pos);
      if (ch === 42 || ch === 47 || ch === 37) break;
    }
    let ctor: string | null = null;
    if (consume(c, "*")) ctor = CTOR.mul;
    else if (consume(c, "/")) ctor = CTOR.div;
    else if (consume(c, "%")) ctor = CTOR.mod;
    else break;
    const right = parseUnary(k, c);
    if (right === null) throw new SyntaxError(`ts: rhs expected at ${c.pos}`);
    left = captureNode(k, ctor, [left, right]);
  }
  return left;
}

function parseAdd(k: Kernel, c: Cursor): NodeID | null {
  let left = parseMul(k, c);
  if (left === null) return null;
  while (true) {
    skipWS(c);
    // Don't consume `+` / `-` when followed by `=` or another `+`/`-` (++ / --).
    if (c.pos + 1 < c.src.length) {
      const ch = c.src.charCodeAt(c.pos);
      const nx = c.src.charCodeAt(c.pos + 1);
      if ((ch === 43 || ch === 45) && (nx === 61 || nx === ch)) break;
    }
    let ctor: string | null = null;
    if (startsWith(c, "+")) {
      c.pos++;
      ctor = CTOR.add;
    } else if (startsWith(c, "-")) {
      c.pos++;
      ctor = CTOR.sub;
    } else break;
    const right = parseMul(k, c);
    if (right === null) throw new SyntaxError(`ts: rhs expected at ${c.pos}`);
    left = captureNode(k, ctor, [left, right]);
  }
  return left;
}

function parseCmp(k: Kernel, c: Cursor): NodeID | null {
  let left = parseAdd(k, c);
  if (left === null) return null;
  while (true) {
    skipWS(c);
    let ctor: string | null = null;
    // 3-char operators first (===, !==), then 2-char (==, !=, <=, >=), then 1-char.
    if (consume(c, "===")) ctor = CTOR.eq;
    else if (consume(c, "!==")) ctor = CTOR.ne;
    else if (consume(c, "==")) ctor = CTOR.eq;
    else if (consume(c, "!=")) ctor = CTOR.ne;
    else if (consume(c, "<=")) ctor = CTOR.le;
    else if (consume(c, ">=")) ctor = CTOR.ge;
    else if (peek(c) === "<" && c.src[c.pos + 1] !== "=") {
      c.pos++;
      ctor = CTOR.lt;
    } else if (peek(c) === ">" && c.src[c.pos + 1] !== "=") {
      c.pos++;
      ctor = CTOR.gt;
    } else break;
    const right = parseAdd(k, c);
    if (right === null) throw new SyntaxError(`ts: rhs expected at ${c.pos}`);
    left = captureNode(k, ctor, [left, right]);
  }
  return left;
}

function parseAnd(k: Kernel, c: Cursor): NodeID | null {
  let left = parseCmp(k, c);
  if (left === null) return null;
  while (true) {
    skipWS(c);
    if (!startsWith(c, "&&")) break;
    c.pos += 2;
    const right = parseCmp(k, c);
    if (right === null) throw new SyntaxError(`ts: rhs after '&&' at ${c.pos}`);
    left = captureNode(k, CTOR.and_, [left, right]);
  }
  return left;
}

function parseOr(k: Kernel, c: Cursor): NodeID | null {
  let left = parseAnd(k, c);
  if (left === null) return null;
  while (true) {
    skipWS(c);
    if (!startsWith(c, "||")) break;
    c.pos += 2;
    const right = parseAnd(k, c);
    if (right === null) throw new SyntaxError(`ts: rhs after '||' at ${c.pos}`);
    left = captureNode(k, CTOR.or_, [left, right]);
  }
  return left;
}

// Ternary: `c ? a : b`. Captures as CTOR.if_ — same shape as Python's
// conditional expression so cross-language identity holds.
function parseTernary(k: Kernel, c: Cursor): NodeID | null {
  const cond = parseOr(k, c);
  if (cond === null) return null;
  skipWS(c);
  if (peek(c) !== "?") return cond;
  c.pos++;
  const then_ = parseExpr(k, c);
  if (then_ === null) throw new SyntaxError(`ts: then-branch after '?' at ${c.pos}`);
  expect(c, ":");
  const else_ = parseExpr(k, c);
  if (else_ === null) throw new SyntaxError(`ts: else-branch after ':' at ${c.pos}`);
  return captureNode(k, CTOR.if_, [cond, then_, else_]);
}

export function parseExpr(k: Kernel, c: Cursor): NodeID | null {
  return parseTernary(k, c);
}

// ----- statements -----

function parseBlock(k: Kernel, c: Cursor): NodeID {
  expect(c, "{");
  const stmts: NodeID[] = [];
  while (true) {
    skipWS(c);
    if (consume(c, "}")) break;
    const s = parseStmt(k, c);
    if (s === null) break;
    stmts.push(s);
  }
  return captureNode(k, CTOR.block, stmts);
}

function parseReturn(k: Kernel, c: Cursor): NodeID {
  expect(c, "return");
  skipWS(c);
  // Bare `return;` → return null
  if (peek(c) === ";" || peek(c) === "}") {
    consume(c, ";");
    return captureNode(k, CTOR.return_, [captureNode(k, CTOR.none_literal, [])]);
  }
  const e = parseExpr(k, c);
  if (e === null) {
    consume(c, ";");
    return captureNode(k, CTOR.return_, [captureNode(k, CTOR.none_literal, [])]);
  }
  consume(c, ";");
  return captureNode(k, CTOR.return_, [e]);
}

function parseIf(k: Kernel, c: Cursor): NodeID {
  expect(c, "if");
  expect(c, "(");
  const cond = parseExpr(k, c);
  if (cond === null) throw new SyntaxError(`ts: condition required at ${c.pos}`);
  expect(c, ")");
  const thenBranch = parseStmtOrBlock(k, c);
  const branches: NodeID[] = [cond, thenBranch];
  skipWS(c);
  if (peekKeyword(c, "else")) {
    consumeKeyword(c, "else");
    skipWS(c);
    if (peekKeyword(c, "if")) {
      // else-if chains
      const elseIf = parseIf(k, c);
      // Splice: the elseIf is itself a CTOR.if_; flatten its branches.
      const eiKids = capturedChildren(k, elseIf);
      for (const x of eiKids) branches.push(x);
    } else {
      const elseBranch = parseStmtOrBlock(k, c);
      branches.push(elseBranch);
    }
  }
  return captureNode(k, CTOR.if_, branches);
}

// parseStmtOrBlock — accepts either `{ ... }` or a single statement.
// Single statements get wrapped in CTOR.block of length 1 so downstream
// code can treat both forms uniformly.
function parseStmtOrBlock(k: Kernel, c: Cursor): NodeID {
  skipWS(c);
  if (peek(c) === "{") return parseBlock(k, c);
  const s = parseStmt(k, c);
  if (s === null) throw new SyntaxError(`ts: statement required at ${c.pos}`);
  return captureNode(k, CTOR.block, [s]);
}

// parseBinding — `const name = expr;` or `let name = expr;`. Type annotations
// (`: T`) are parsed-and-ignored (skipped to `=`).
function parseBinding(k: Kernel, c: Cursor): NodeID {
  // Already consumed `const` or `let` by caller.
  skipWS(c);
  const name = readIdentRaw(c);
  if (name === null) throw new SyntaxError(`ts: binding name required at ${c.pos}`);
  skipWS(c);
  if (peek(c) === ":") {
    c.pos++;
    // Skip until `=` (type annotation parse-and-ignore).
    while (c.pos < c.src.length && peek(c) !== "=" && peek(c) !== ";") c.pos++;
  }
  expect(c, "=");
  const value = parseExpr(k, c);
  if (value === null) throw new SyntaxError(`ts: expression after '=' at ${c.pos}`);
  consume(c, ";");
  const target = captureNode(k, CTOR.ident, [k.internString(name)]);
  return captureNode(k, CTOR.assign, [target, value]);
}

// parseFunctionDecl — `function name(args) { body }`. Lowers to CTOR.def_
// so cross-language identity with Python `def` holds.
function parseFunctionDecl(k: Kernel, c: Cursor): NodeID {
  expect(c, "function");
  skipWS(c);
  const name = readIdentRaw(c);
  if (name === null) throw new SyntaxError(`ts: function name required at ${c.pos}`);
  expect(c, "(");
  const params: NodeID[] = [];
  skipWS(c);
  if (!consume(c, ")")) {
    while (true) {
      skipWS(c);
      const pn = readIdentRaw(c);
      if (pn === null) break;
      // optional `: T` annotation
      skipWS(c);
      if (peek(c) === ":") {
        c.pos++;
        let depth = 0;
        while (c.pos < c.src.length) {
          const ch = peek(c);
          if (depth === 0 && (ch === "," || ch === ")")) break;
          if (ch === "(" || ch === "<" || ch === "[" || ch === "{") depth++;
          else if (ch === ")" || ch === ">" || ch === "]" || ch === "}") depth--;
          c.pos++;
        }
      }
      params.push(captureNode(k, CTOR.param, [k.internString(pn)]));
      if (!consume(c, ",")) break;
    }
    expect(c, ")");
  }
  // Optional return-type annotation
  skipWS(c);
  if (peek(c) === ":") {
    c.pos++;
    while (c.pos < c.src.length && peek(c) !== "{") c.pos++;
  }
  const body = parseBlock(k, c);
  return captureNode(k, CTOR.def_, [
    captureNode(k, CTOR.ident, [k.internString(name)]),
    captureNode(k, CTOR.params, params),
    body,
  ]);
}

export function parseStmt(k: Kernel, c: Cursor): NodeID | null {
  skipWS(c);
  if (atEnd(c)) return null;
  // Skip stray semicolons
  if (consume(c, ";")) return parseStmt(k, c);

  if (peekKeyword(c, "const") || peekKeyword(c, "let") || peekKeyword(c, "var")) {
    if (peekKeyword(c, "const")) consumeKeyword(c, "const");
    else if (peekKeyword(c, "let")) consumeKeyword(c, "let");
    else consumeKeyword(c, "var");
    return parseBinding(k, c);
  }
  if (peekKeyword(c, "if")) return parseIf(k, c);
  if (peekKeyword(c, "return")) return parseReturn(k, c);
  if (peekKeyword(c, "function")) return parseFunctionDecl(k, c);

  // Expression statement
  const e = parseExpr(k, c);
  if (e === null) return null;
  consume(c, ";");
  return captureNode(k, CTOR.expr_stmt, [e]);
}

// ---------------------------------------------------------------------------
// Top-level: parseTypeScript — module wrapping the statement sequence.
// ---------------------------------------------------------------------------

export function parseTypeScript(k: Kernel, source: string): NodeID {
  const c: Cursor = { src: source, pos: 0 };
  const stmts: NodeID[] = [];
  while (true) {
    skipWS(c);
    if (atEnd(c)) break;
    const s = parseStmt(k, c);
    if (s === null) break;
    stmts.push(s);
  }
  return captureNode(k, CTOR.module, stmts);
}

// ---------------------------------------------------------------------------
// evalTypeScript — third-runtime walker for parity.
//
// Walks the captured-recipe tree directly (no .fk round-trip, no kernel
// native binary). Same shape as evalPython since the CTOR vocabulary is
// shared. Used by `ts-eval` to provide the second sibling-runtime in the
// three-way parity check (alongside tsc-evaluation and form-kernel-rust
// on the emitted .fk).
// ---------------------------------------------------------------------------

interface TsEnv {
  parent: TsEnv | null;
  vars: Map<number, Value>;
}

interface TsClosure {
  params: number[];
  body: NodeID;
  env: TsEnv;
}

class ReturnSignal {
  constructor(public value: Value) {}
}

function newEnv(parent: TsEnv | null = null): TsEnv {
  return { parent, vars: new Map() };
}

function envLookup(env: TsEnv, nameID: number): Value | undefined {
  let e: TsEnv | null = env;
  while (e !== null) {
    const v = e.vars.get(nameID);
    if (v !== undefined) return v;
    e = e.parent;
  }
  return undefined;
}

function envBind(env: TsEnv, nameID: number, value: Value): void {
  env.vars.set(nameID, value);
}

export function evalTypeScript(k: Kernel, tree: NodeID, env?: TsEnv): Value {
  const E = env ?? newEnv();
  // Built-in bindings for the eval path.
  envBind(E, k.internName("true"), { kind: "bool", bool: true });
  envBind(E, k.internName("false"), { kind: "bool", bool: false });
  envBind(E, k.internName("null"), { kind: "null" });
  envBind(E, k.internName("undefined"), { kind: "null" });
  return evalNode(k, tree, E);
}

function evalNode(k: Kernel, n: NodeID, env: TsEnv): Value {
  if (n.level === Level.TRIVIAL) {
    return trivialToValue(k, n);
  }
  const ctor = capturedCtor(k, n);
  const kids = capturedChildren(k, n);
  switch (ctor) {
    case CTOR.module: {
      let last: Value = { kind: "null" };
      for (const s of kids) last = evalNode(k, s, env);
      return last;
    }
    case CTOR.expr_stmt:
      return evalNode(k, kids[0]!, env);
    case CTOR.int_literal:
    case CTOR.float_literal:
      return trivialToValue(k, kids[0]!);
    case CTOR.bool_literal:
      return kids.length > 0 ? trivialToValue(k, kids[0]!) : { kind: "bool", bool: false };
    case CTOR.none_literal:
      return { kind: "null" };
    case CTOR.str_literal: {
      const t = kids[0]!;
      if (t.level === Level.TRIVIAL && t.type === Triv.STRING) {
        return { kind: "str", str: k.strs[t.inst] ?? "" };
      }
      return { kind: "str", str: "" };
    }
    case CTOR.ident: {
      const nameTriv = kids[0]!;
      if (nameTriv.level !== Level.TRIVIAL || nameTriv.type !== Triv.STRING) {
        throw new Error("ident: missing name");
      }
      const v = envLookup(env, nameTriv.inst);
      if (v === undefined) {
        throw new Error(`ts: unbound name '${k.nameStr(nameTriv.inst)}'`);
      }
      return v;
    }
    case CTOR.list_literal:
      return { kind: "list", list: kids.map((c) => evalNode(k, c, env)) };
    case CTOR.add:
      return numBinop(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "+");
    case CTOR.sub:
      return numBinop(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "-");
    case CTOR.mul:
      return numBinop(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "*");
    case CTOR.div:
      return numBinop(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "/");
    case CTOR.mod:
      return numBinop(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "%");
    case CTOR.eq:
      return { kind: "bool", bool: valueEq(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env)) };
    case CTOR.ne:
      return { kind: "bool", bool: !valueEq(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env)) };
    case CTOR.lt: return cmpOp(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "<");
    case CTOR.le: return cmpOp(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "<=");
    case CTOR.gt: return cmpOp(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), ">");
    case CTOR.ge: return cmpOp(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), ">=");
    case CTOR.and_: {
      const a = evalNode(k, kids[0]!, env);
      if (!truthy(a)) return a;
      return evalNode(k, kids[1]!, env);
    }
    case CTOR.or_: {
      const a = evalNode(k, kids[0]!, env);
      if (truthy(a)) return a;
      return evalNode(k, kids[1]!, env);
    }
    case CTOR.not_:
      return { kind: "bool", bool: !truthy(evalNode(k, kids[0]!, env)) };
    case CTOR.neg: {
      const v = evalNode(k, kids[0]!, env);
      if (v.kind === "int") return { kind: "int", int: -v.int };
      if (v.kind === "f64") return { kind: "f64", float: -v.float };
      throw new Error("neg: expected numeric");
    }
    case CTOR.if_: {
      // Ternary form: exactly 3 kids and middle is NOT a block.
      if (kids.length === 3 && capturedCtor(k, kids[1]!) !== CTOR.block) {
        const cond = evalNode(k, kids[0]!, env);
        return truthy(cond) ? evalNode(k, kids[1]!, env) : evalNode(k, kids[2]!, env);
      }
      // Statement form: pairs of (cond, body) optionally with trailing else.
      let i = 0;
      while (i + 1 < kids.length) {
        const cond = evalNode(k, kids[i]!, env);
        if (truthy(cond)) return evalNode(k, kids[i + 1]!, env);
        i += 2;
      }
      if (i < kids.length) return evalNode(k, kids[i]!, env);
      return { kind: "null" };
    }
    case CTOR.block: {
      let last: Value = { kind: "null" };
      for (const s of kids) last = evalNode(k, s, env);
      return last;
    }
    case CTOR.return_: {
      const v = evalNode(k, kids[0]!, env);
      throw new ReturnSignal(v);
    }
    case CTOR.assign: {
      const target = kids[0]!;
      const value = evalNode(k, kids[1]!, env);
      const tCtor = capturedCtor(k, target);
      if (tCtor !== CTOR.ident) throw new Error(`ts: assign target must be ident (got ${tCtor})`);
      const nameID = capturedChildren(k, target)[0]!.inst;
      envBind(env, nameID, value);
      return { kind: "null" };
    }
    case CTOR.def_: {
      const nameNode = kids[0]!;
      const params = capturedChildren(k, kids[1]!);
      const body = kids[2]!;
      const paramNames = params.map((p) => capturedChildren(k, p)[0]!.inst);
      const fnNameID = capturedChildren(k, nameNode)[0]!.inst;
      const closure: TsClosure = { params: paramNames, body, env };
      envBind(env, fnNameID, { kind: "list", list: [], tsClosure: closure } as Value & { tsClosure?: TsClosure });
      return { kind: "null" };
    }
    case CTOR.lambda_: {
      const params = capturedChildren(k, kids[0]!);
      const body = kids[1]!;
      const paramNames = params.map((p) => capturedChildren(k, p)[0]!.inst);
      const closure: TsClosure = { params: paramNames, body, env };
      return { kind: "list", list: [], tsClosure: closure } as Value & { tsClosure?: TsClosure };
    }
    case CTOR.call: {
      const callee = kids[0]!;
      const argsNode = kids[1]!;
      const argKids = capturedChildren(k, argsNode);
      const argVals = argKids.map((a) => evalNode(k, a, env));
      let calleeVal: Value;
      if (capturedCtor(k, callee) === CTOR.ident) {
        const nameID = capturedChildren(k, callee)[0]!.inst;
        const bound = envLookup(env, nameID);
        if (bound === undefined) {
          // Minimal built-in fallback (console.log isn't here; emit-side
          // doesn't carry side effects through .fk parity anyway).
          throw new Error(`ts: unbound callable '${k.nameStr(nameID)}'`);
        }
        calleeVal = bound;
      } else {
        calleeVal = evalNode(k, callee, env);
      }
      return invokeClosure(k, calleeVal, argVals);
    }
    default:
      throw new Error(`evalTypeScript: unsupported ctor '${ctor}'`);
  }
}

function invokeClosure(k: Kernel, v: Value, args: Value[]): Value {
  const closure = (v as Value & { tsClosure?: TsClosure }).tsClosure;
  if (!closure) throw new Error("call: callee is not a TS closure");
  if (args.length !== closure.params.length) {
    throw new Error(`call: arity mismatch (expected ${closure.params.length}, got ${args.length})`);
  }
  const callEnv = newEnv(closure.env);
  for (let i = 0; i < closure.params.length; i++) {
    envBind(callEnv, closure.params[i]!, args[i]!);
  }
  try {
    // Function-body shape: CTOR.block. For lambda expr-body, body is the
    // expression itself — evaluate and return its value (no implicit
    // return-signal needed).
    const bodyCtor = capturedCtor(k, closure.body);
    if (bodyCtor === CTOR.block) {
      // Walk statements; if no `return` fires, last expression's value is
      // not the return — function returns undefined. But for the demos we
      // exercise, the function always has a return.
      const stmts = capturedChildren(k, closure.body);
      for (const s of stmts) evalNode(k, s, callEnv);
      return { kind: "null" };
    }
    // Expression body — value of the expression IS the return value.
    return evalNode(k, closure.body, callEnv);
  } catch (e) {
    if (e instanceof ReturnSignal) return e.value;
    throw e;
  }
}

function trivialToValue(k: Kernel, n: NodeID): Value {
  if (n.level !== Level.TRIVIAL) throw new Error("trivialToValue: not a trivial");
  switch (n.type) {
    case Triv.INT32: {
      const u = n.inst >>> 0;
      return { kind: "int", int: u > 0x7fffffff ? u - 0x100000000 : u };
    }
    case Triv.INT64: {
      const i = (k as unknown as { i64s: bigint[] }).i64s[n.inst];
      if (i === undefined) return { kind: "int", int: 0 };
      return { kind: "int", int: Number(i) };
    }
    case Triv.FLOAT64:
      return { kind: "f64", float: k.decodeFloat64(n.inst) };
    case Triv.STRING:
      return { kind: "str", str: k.strs[n.inst] ?? "" };
    case Triv.BOOL:
      return { kind: "bool", bool: n.inst !== 0 };
    case Triv.NULL:
      return { kind: "null" };
    default:
      throw new Error(`trivialToValue: unknown trivial type ${n.type}`);
  }
}

function numBinop(a: Value, b: Value, op: string): Value {
  if (op === "+") {
    if (a.kind === "str" || b.kind === "str") {
      // JS `+` with any string operand coerces both → string concat.
      return { kind: "str", str: renderForPrint(a) + renderForPrint(b) };
    }
    if (a.kind === "list" && b.kind === "list") {
      return { kind: "list", list: [...a.list, ...b.list] };
    }
  }
  const an = numericOf(a);
  const bn = numericOf(b);
  // JS `/` always produces a float; everything else stays int when both
  // operands are ints (consistent with TypeScript demo expectations
  // post-`| 0` truncation — but we follow TS / runtime semantics here).
  const bothInt = an.isInt && bn.isInt && op !== "/";
  let r: number;
  switch (op) {
    case "+": r = an.v + bn.v; break;
    case "-": r = an.v - bn.v; break;
    case "*": r = an.v * bn.v; break;
    case "/": r = an.v / bn.v; break;
    case "%": r = an.v % bn.v; break;
    default: throw new Error(`numBinop: ${op}`);
  }
  if (bothInt) return { kind: "int", int: r };
  return { kind: "f64", float: r };
}

function numericOf(v: Value): { v: number; isInt: boolean } {
  if (v.kind === "int") return { v: v.int, isInt: true };
  if (v.kind === "f64") return { v: v.float, isInt: false };
  if (v.kind === "bool") return { v: v.bool ? 1 : 0, isInt: true };
  throw new Error(`numeric: unexpected kind ${v.kind}`);
}

function valueEq(a: Value, b: Value): boolean {
  if (a.kind === "int" && b.kind === "int") return a.int === b.int;
  if (a.kind === "f64" && b.kind === "f64") return a.float === b.float;
  if (a.kind === "int" && b.kind === "f64") return a.int === b.float;
  if (a.kind === "f64" && b.kind === "int") return a.float === b.int;
  if (a.kind === "str" && b.kind === "str") return a.str === b.str;
  if (a.kind === "bool" && b.kind === "bool") return a.bool === b.bool;
  if (a.kind === "null" && b.kind === "null") return true;
  return false;
}

function cmpOp(a: Value, b: Value, op: string): Value {
  const av = numericOf(a).v;
  const bv = numericOf(b).v;
  let r: boolean;
  switch (op) {
    case "<": r = av < bv; break;
    case "<=": r = av <= bv; break;
    case ">": r = av > bv; break;
    case ">=": r = av >= bv; break;
    default: throw new Error(`cmpOp: ${op}`);
  }
  return { kind: "bool", bool: r };
}

function truthy(v: Value): boolean {
  switch (v.kind) {
    case "null": return false;
    case "bool": return v.bool;
    case "int": return v.int !== 0;
    case "f64": return v.float !== 0;
    case "str": return v.str.length > 0;
    case "list": return v.list.length > 0;
    default: return true;
  }
}

function renderForPrint(v: Value): string {
  switch (v.kind) {
    case "null": return "null";
    case "bool": return v.bool ? "true" : "false";
    case "int": return String(v.int);
    case "f64": return String(v.float);
    case "str": return v.str;
    case "list": return "[" + v.list.map(renderForPrint).join(", ") + "]";
    default: return "<value>";
  }
}

// Re-export shared utilities Frame/Kernel for the emitter
export { Frame, Kernel } from "../../../src/kernel.ts";
