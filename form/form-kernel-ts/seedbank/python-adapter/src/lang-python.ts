// lang-python.ts — Python 3.13 as a substrate-resident Language cell.
//
// This is task #15 of the per-language population pass announced in
// docs/coherence-substrate/language-cells.md. The Language cell carries
// an ingestion grammar (substrate-resident tree of grammar-rule cells),
// an emission template, stdlib bindings, and numeric defaults.
//
// Cross-language identity: Python's `lambda x: x + 1`, TypeScript's
// `(x) => x + 1`, and Rust's `|x| x + 1` are intended to capture under
// the same ctor names (`lambda`, `arg`, `add`, `int-literal`) so the
// resulting recipe sub-trees intern to the same NodeIDs. The ctor
// vocabulary used by all four sibling languages (#15-#18) is named
// in CTOR below — keeping it small and stable is what earns the N+M
// transpilation savings the architecture promises.
//
// Round-trip is preserved up to insignificant whitespace; comments and
// layout are dropped (open question #3 in language-cells.md).
//
// The v0 generic parse_through walker in languages.ts is non-recursive
// (RULE_REF is a no-op pending the production rule-table), so the
// substrate grammar tree below stands as the cell's structural identity
// while the recursive-descent driver in this file does the actual
// parse. Both produce the same captured-recipe shape — what the cell
// represents and what the cell does converge.

import {
  Frame,
  Kernel,
  Level,
  RBasic,
  Triv,
  type NodeID,
  type Value,
} from "../../../src/kernel.ts";
import { buildFormatLibrary, type FormatLibrary } from "../../../src/formats.ts";
import {
  capturedChildren,
  capturedCtor,
  eJoin,
  gAlt,
  gCapture,
  gLiteral,
  gOpt,
  gPlus,
  gSeq,
  gStar,
  gTokenClass,
  registerLanguage,
  type Language,
} from "../../../src/languages.ts";

// ---------------------------------------------------------------------------
// CTOR — the shared ctor-name vocabulary for the Python Language cell.
//
// Every CAPTURE in the grammar (and every recipe the recursive-descent
// parser constructs) uses one of these names. Keeping the vocabulary
// small and stable is how cross-language identity stays load-bearing:
// semantically-equivalent fragments in Python / TS / Go / Rust all
// capture under the same names, so their recipe sub-trees intern to
// the same NodeIDs.
// ---------------------------------------------------------------------------

export const CTOR = {
  // Top-level
  module: "module",
  // Literals
  int_literal: "int-literal",
  float_literal: "float-literal",
  str_literal: "str-literal",
  bool_literal: "bool-literal",
  none_literal: "none-literal",
  ident: "ident",
  // Collections
  list_literal: "list-literal",
  dict_literal: "dict-literal",
  dict_entry: "dict-entry",
  tuple_literal: "tuple-literal",
  // Calls
  call: "call",
  method_call: "method-call",
  args: "args",
  // Operators — names align across languages
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
  in_: "in",
  // Statements
  if_: "if",
  elif_: "elif",
  else_: "else",
  def_: "def",
  return_: "return",
  for_: "for",
  while_: "while",
  lambda_: "lambda",
  expr_stmt: "expr-stmt",
  assign: "assign",
  subscript: "subscript",
  import_: "import",
  // Function/lambda params
  params: "params",
  param: "param",
  block: "block",
  // Classes — v1 minimum shape (class X:, __init__(self, …) storing
  // attributes on self, instance methods that take self and use self.x).
  // No inheritance, no super(), no decorators in v1. Each is named in
  // PR body as a pending follow-up breath.
  class_: "class",
  attr: "attr", // bare attribute read:  obj.field
} as const;

// ---------------------------------------------------------------------------
// Grammar — substrate-resident structural identity of the language.
//
// The grammar tree is built with the substrate's grammar-rule builders
// from languages.ts. Recursive productions can't be expressed via
// RULE_REF in the v0 walker, so this tree captures the surface tokens
// + top-level shape rather than the full recursive expression
// hierarchy. The recursive-descent parser below converges to the same
// recipe shape the grammar would produce if RULE_REF were live.
// ---------------------------------------------------------------------------

function buildIngestionGrammar(k: Kernel): NodeID {
  // Atoms — leaves that don't recurse.
  const numLit = gAlt(
    k,
    gCapture(k, CTOR.float_literal, gTokenClass(k, "number")),
    gCapture(k, CTOR.int_literal, gTokenClass(k, "number")),
  );
  const strLit = gCapture(k, CTOR.str_literal, gTokenClass(k, "ident")); // placeholder — real strings via TOKEN_CLASS extension
  const boolLit = gCapture(
    k,
    CTOR.bool_literal,
    gAlt(k, gLiteral(k, "True"), gLiteral(k, "False")),
  );
  const noneLit = gCapture(k, CTOR.none_literal, gLiteral(k, "None"));
  const identCap = gCapture(k, CTOR.ident, gTokenClass(k, "ident"));

  // Top-level shape: a module is a sequence of statement-like atoms.
  // The recursive substance is provided by the driver in parsePython.
  const atom = gAlt(k, numLit, strLit, boolLit, noneLit, identCap);
  return gCapture(k, CTOR.module, gStar(k, atom));
}

function buildEmissionTemplate(k: Kernel): NodeID {
  // The substrate emit-rule walker in languages.ts is a generic
  // children-join; for round-trip we need ctor-dispatch which lives in
  // emitPython below. The template is the structural placeholder so
  // the cell carries an emission identity.
  return eJoin(k, " ", 0, -1);
}

// ---------------------------------------------------------------------------
// Recursive-descent parser — produces the captured-recipe shape.
//
// Every CAPTURE name corresponds to a ctor in CTOR above. The recipe
// node category is (BASIC, RBasic.LIST, inst=NameID-of-ctor); two
// recipes built from the same source text intern to the same NodeID
// via the kernel's content-addressing. That's content-addressing on
// the program structure, not the surface text.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Known kernel-resident module bindings. Each module attribute maps to a
// flat kernel-native name. `math.sqrt` → `math_sqrt`; `math.pi` → `math_pi`.
//
// Imports are noops at runtime — the import statement records aliases in
// the parser cursor, and subsequent identifiers/attribute accesses are
// rewritten to call the kernel native directly. Three runtimes converge:
// CPython resolves math.sqrt through the real module; TS evalPython and
// form-kernel-rust resolve `math_sqrt` through their native table.
//
// Keep this list tight: each entry needs a matching native in the Rust
// kernel (and the TS kernel for evalPython parity). Demonstrably useful
// for substrate code is the bar.
// ---------------------------------------------------------------------------

const KERNEL_MODULES: Record<string, Record<string, string>> = {
  math: {
    sqrt: "math_sqrt",
    pi: "math_pi",
    floor: "math_floor",
    ceil: "math_ceil",
    pow: "math_pow",
  },
};

interface ImportState {
  // Module aliases: alias name → real module name (e.g. `m` → `math`).
  // `import math` and `import math as m` both populate this; the value
  // is what we look up in KERNEL_MODULES.
  moduleAliases: Map<string, string>;
  // Direct name bindings from `from <module> import <name> [as alias]`:
  // alias → native name (e.g. `sqrt` → `math_sqrt`).
  directImports: Map<string, string>;
}

interface Cursor {
  readonly src: string;
  pos: number;
  indent: number; // current indent level being parsed inside a block
  imports: ImportState;
}

function ctorCategory(k: Kernel, ctor: string): NodeID {
  // Same encoding parseThrough's CAPTURE uses: RBasic.LIST with inst
  // = the interned ctor-name's NameID. Two recipes with the same ctor
  // + same children → same NodeID.
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

function skipSpacesAndComments(c: Cursor): void {
  // Skip spaces, tabs, and # comments. Newlines are significant in
  // Python statements, so they're NOT skipped here.
  while (c.pos < c.src.length) {
    const ch = c.src.charCodeAt(c.pos);
    if (ch === 32 || ch === 9) {
      c.pos++;
    } else if (ch === 35 /* '#' */) {
      while (c.pos < c.src.length && c.src.charCodeAt(c.pos) !== 10) c.pos++;
    } else {
      break;
    }
  }
}

function skipAllWhitespace(c: Cursor): void {
  while (c.pos < c.src.length) {
    const ch = c.src.charCodeAt(c.pos);
    if (ch === 32 || ch === 9 || ch === 10 || ch === 13) {
      c.pos++;
    } else if (ch === 35) {
      while (c.pos < c.src.length && c.src.charCodeAt(c.pos) !== 10) c.pos++;
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

// Consume an exact literal (with optional surrounding-space skip first).
function consume(c: Cursor, lit: string): boolean {
  skipSpacesAndComments(c);
  if (startsWith(c, lit)) {
    c.pos += lit.length;
    return true;
  }
  return false;
}

// Expect a literal — throws on mismatch.
function expect(c: Cursor, lit: string): void {
  if (!consume(c, lit)) {
    throw new SyntaxError(
      `python: expected '${lit}' at position ${c.pos} (got ` +
        JSON.stringify(c.src.substring(c.pos, c.pos + 16)) +
        ")",
    );
  }
}

function isIdentStart(ch: number): boolean {
  return (ch >= 65 && ch <= 90) || (ch >= 97 && ch <= 122) || ch === 95;
}

function isIdentCont(ch: number): boolean {
  return isIdentStart(ch) || (ch >= 48 && ch <= 57);
}

const KEYWORDS = new Set([
  "if",
  "elif",
  "else",
  "def",
  "return",
  "for",
  "while",
  "lambda",
  "True",
  "False",
  "None",
  "and",
  "or",
  "not",
  "in",
  "import",
  "from",
  "as",
  "class",
  "pass",
]);

function readIdentRaw(c: Cursor): string | null {
  skipSpacesAndComments(c);
  const start = c.pos;
  if (atEnd(c) || !isIdentStart(c.src.charCodeAt(start))) return null;
  let pos = start + 1;
  while (pos < c.src.length && isIdentCont(c.src.charCodeAt(pos))) pos++;
  c.pos = pos;
  return c.src.substring(start, pos);
}

// Lookahead a keyword without consuming.
function peekKeyword(c: Cursor, kw: string): boolean {
  const saved = c.pos;
  skipSpacesAndComments(c);
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
    skipSpacesAndComments(c);
    c.pos += kw.length;
    return true;
  }
  return false;
}

// ----- numeric literal -----

function parseNumber(k: Kernel, c: Cursor): NodeID | null {
  skipSpacesAndComments(c);
  const start = c.pos;
  let pos = start;
  if (pos < c.src.length && c.src.charCodeAt(pos) === 45 /* '-' */) {
    // Unary minus is handled at the expression level; bare numeric
    // doesn't consume a leading sign.
    return null;
  }
  while (pos < c.src.length && c.src.charCodeAt(pos) >= 48 && c.src.charCodeAt(pos) <= 57)
    pos++;
  if (pos === start) return null;
  let isFloat = false;
  if (pos < c.src.length && c.src.charCodeAt(pos) === 46 /* '.' */) {
    // Disambiguate from method-call '.' followed by an ident.
    const after = c.src.charCodeAt(pos + 1) || 0;
    if (after >= 48 && after <= 57) {
      isFloat = true;
      pos++;
      while (
        pos < c.src.length &&
        c.src.charCodeAt(pos) >= 48 &&
        c.src.charCodeAt(pos) <= 57
      )
        pos++;
    }
  }
  const text = c.src.substring(start, pos);
  c.pos = pos;
  if (isFloat) {
    // Python `float` defaults to FP64.
    const value = k.internTrivialFloat64(parseFloat(text));
    return captureNode(k, CTOR.float_literal, [value]);
  }
  // Python `int` is arbitrary-precision; we map to INT64 as the
  // default substrate format. Out-of-range integers fall back to
  // INT32 with a soft cap; v0 doesn't carry bignum.
  const n = BigInt(text);
  let value: NodeID;
  if (n >= -2147483648n && n <= 2147483647n) {
    value = k.internTrivialInt64(n);
  } else {
    value = k.internTrivialInt64(n);
  }
  return captureNode(k, CTOR.int_literal, [value]);
}

// ----- string literal -----

function parseString(k: Kernel, c: Cursor): NodeID | null {
  skipSpacesAndComments(c);
  if (atEnd(c)) return null;
  const ch = peek(c);
  if (ch !== '"' && ch !== "'") return null;
  // Triple-quoted detection
  const tripleSingle = startsWith(c, "'''");
  const tripleDouble = startsWith(c, '"""');
  const triple = tripleSingle || tripleDouble;
  const quote = tripleSingle ? "'''" : tripleDouble ? '"""' : ch;
  c.pos += quote.length;
  const start = c.pos;
  while (c.pos < c.src.length) {
    if (startsWith(c, quote)) {
      const text = c.src.substring(start, c.pos);
      c.pos += quote.length;
      const str = k.internString(unescapePython(text, triple));
      return captureNode(k, CTOR.str_literal, [str]);
    }
    if (!triple && c.src.charCodeAt(c.pos) === 92 /* '\\' */) {
      c.pos += 2;
      continue;
    }
    c.pos++;
  }
  throw new SyntaxError(`python: unterminated string at position ${start}`);
}

function unescapePython(s: string, triple: boolean): string {
  if (triple) return s;
  // Minimal escape handling — enough for the round-trip test corpus.
  let out = "";
  for (let i = 0; i < s.length; i++) {
    if (s.charCodeAt(i) === 92 && i + 1 < s.length) {
      const next = s[i + 1]!;
      switch (next) {
        case "n":
          out += "\n";
          break;
        case "t":
          out += "\t";
          break;
        case "r":
          out += "\r";
          break;
        case "\\":
          out += "\\";
          break;
        case "'":
          out += "'";
          break;
        case '"':
          out += '"';
          break;
        default:
          out += s[i] + next;
      }
      i++;
    } else {
      out += s[i];
    }
  }
  return out;
}

// ----- primary expressions -----
//
// Python expression precedence (subset):
//   or
//   and
//   not
//   comparison (<, <=, >, >=, ==, !=)
//   add/sub
//   mul/div/mod
//   unary -
//   call / attribute
//   atom

function parseAtom(k: Kernel, c: Cursor): NodeID | null {
  skipSpacesAndComments(c);
  if (atEnd(c)) return null;

  // Parenthesized expression or tuple literal
  if (consume(c, "(")) {
    const first = parseExpr(k, c);
    if (first === null) {
      expect(c, ")");
      return captureNode(k, CTOR.tuple_literal, []);
    }
    // Tuple if a comma follows.
    if (consume(c, ",")) {
      const items: NodeID[] = [first];
      while (true) {
        skipSpacesAndComments(c);
        if (peek(c) === ")") break;
        const next = parseExpr(k, c);
        if (next === null) break;
        items.push(next);
        if (!consume(c, ",")) break;
      }
      expect(c, ")");
      return captureNode(k, CTOR.tuple_literal, items);
    }
    expect(c, ")");
    return first;
  }

  // List literal
  if (consume(c, "[")) {
    const items: NodeID[] = [];
    skipAllWhitespace(c);
    if (!consume(c, "]")) {
      const first = parseExpr(k, c);
      if (first !== null) items.push(first);
      while (consume(c, ",")) {
        skipAllWhitespace(c);
        if (peek(c) === "]") break;
        const next = parseExpr(k, c);
        if (next === null) break;
        items.push(next);
      }
      skipAllWhitespace(c);
      expect(c, "]");
    }
    return captureNode(k, CTOR.list_literal, items);
  }

  // Dict literal
  if (consume(c, "{")) {
    const entries: NodeID[] = [];
    skipAllWhitespace(c);
    if (!consume(c, "}")) {
      while (true) {
        skipAllWhitespace(c);
        if (peek(c) === "}") break;
        const key = parseExpr(k, c);
        if (key === null)
          throw new SyntaxError(`python: expected dict key at ${c.pos}`);
        expect(c, ":");
        const val = parseExpr(k, c);
        if (val === null)
          throw new SyntaxError(`python: expected dict value at ${c.pos}`);
        entries.push(captureNode(k, CTOR.dict_entry, [key, val]));
        if (!consume(c, ",")) break;
      }
      skipAllWhitespace(c);
      expect(c, "}");
    }
    return captureNode(k, CTOR.dict_literal, entries);
  }

  // Lambda
  if (consumeKeyword(c, "lambda")) {
    const params = parseLambdaParams(k, c);
    expect(c, ":");
    const body = parseExpr(k, c);
    if (body === null)
      throw new SyntaxError(`python: lambda body required at ${c.pos}`);
    return captureNode(k, CTOR.lambda_, [params, body]);
  }

  // Keyword literals (must precede ident).
  if (peekKeyword(c, "True")) {
    consumeKeyword(c, "True");
    return captureNode(k, CTOR.bool_literal, [k.internTrivialBool(true)]);
  }
  if (peekKeyword(c, "False")) {
    consumeKeyword(c, "False");
    return captureNode(k, CTOR.bool_literal, [k.internTrivialBool(false)]);
  }
  if (peekKeyword(c, "None")) {
    consumeKeyword(c, "None");
    return captureNode(k, CTOR.none_literal, []);
  }

  // String
  const s = parseString(k, c);
  if (s !== null) return s;

  // Number
  const n = parseNumber(k, c);
  if (n !== null) return n;

  // Identifier (not a keyword).
  const savedPos = c.pos;
  const name = readIdentRaw(c);
  if (name !== null) {
    if (KEYWORDS.has(name)) {
      c.pos = savedPos;
      return null;
    }
    // `from <module> import <name>` rewrite: bare identifier `sqrt`
    // becomes ident("math_sqrt"). If `(` follows, parsePostfix wraps as
    // a normal call. If not, the name refers to a value (e.g. `pi`); we
    // synthesize a 0-arg call so the kernel native fires. CPython
    // resolves the same `pi` through the module's attribute table — same
    // result, no behavioural divergence.
    const directNative = c.imports.directImports.get(name);
    if (directNative !== undefined) {
      const savedAfter = c.pos;
      skipSpacesAndComments(c);
      const followsCall = !atEnd(c) && peek(c) === "(";
      c.pos = savedAfter;
      if (followsCall) {
        return captureNode(k, CTOR.ident, [k.internString(directNative)]);
      }
      // Value-import — wrap as 0-arg call so the kernel native fires.
      return captureNode(k, CTOR.call, [
        captureNode(k, CTOR.ident, [k.internString(directNative)]),
        captureNode(k, CTOR.args, []),
      ]);
    }
    return captureNode(k, CTOR.ident, [k.internString(name)]);
  }

  return null;
}

function parseLambdaParams(k: Kernel, c: Cursor): NodeID {
  const params: NodeID[] = [];
  // Stop at ':'
  while (true) {
    skipSpacesAndComments(c);
    if (peek(c) === ":") break;
    const name = readIdentRaw(c);
    if (name === null) break;
    params.push(captureNode(k, CTOR.param, [k.internString(name)]));
    if (!consume(c, ",")) break;
  }
  return captureNode(k, CTOR.params, params);
}

// parsePostfix handles call f(a,b), method x.m(a), attribute x.m.
function parsePostfix(k: Kernel, c: Cursor): NodeID | null {
  let node = parseAtom(k, c);
  if (node === null) return null;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    skipSpacesAndComments(c);
    if (peek(c) === "(") {
      // Call
      c.pos++;
      const args = parseArgs(k, c);
      expect(c, ")");
      node = captureNode(k, CTOR.call, [node, args]);
      continue;
    }
    if (peek(c) === "[") {
      // Subscript: value[index]. v1 covers the simple-index case;
      // slicing (`a[i:j]`) lands as a separate postfix when CTOR.slice
      // is wired into evalNode + emitFk.
      c.pos++;
      skipSpacesAndComments(c);
      const idx = parseExpr(k, c);
      if (idx === null) {
        throw new SyntaxError(`python: expected index after '[' at ${c.pos}`);
      }
      skipSpacesAndComments(c);
      expect(c, "]");
      node = captureNode(k, CTOR.subscript, [node, idx]);
      continue;
    }
    if (peek(c) === ".") {
      // Attribute or method call
      const savedDot = c.pos;
      c.pos++;
      const member = readIdentRaw(c);
      if (member === null) {
        c.pos = savedDot;
        break;
      }
      // `<module-alias>.<member>` rewrite: if the LHS is a bare ident
      // whose name is registered as a module alias (`import math`,
      // `import math as m`), and the member is one the kernel exposes,
      // produce a direct call to the kernel-native binding. The module
      // itself never becomes a runtime value — same as CPython's bound-
      // method resolution shortcut, but happening at parse time.
      const moduleNative = resolveModuleMember(k, node, member, c);
      if (moduleNative !== null) {
        // If followed by '(', collect args; else 0-arg call (constant).
        skipSpacesAndComments(c);
        if (peek(c) === "(") {
          c.pos++;
          const args = parseArgs(k, c);
          expect(c, ")");
          node = captureNode(k, CTOR.call, [
            captureNode(k, CTOR.ident, [k.internString(moduleNative)]),
            args,
          ]);
        } else {
          node = captureNode(k, CTOR.call, [
            captureNode(k, CTOR.ident, [k.internString(moduleNative)]),
            captureNode(k, CTOR.args, []),
          ]);
        }
        continue;
      }
      // If followed by '(', it's a method call; else attribute.
      skipSpacesAndComments(c);
      if (peek(c) === "(") {
        c.pos++;
        const args = parseArgs(k, c);
        expect(c, ")");
        node = captureNode(k, CTOR.method_call, [
          node,
          captureNode(k, CTOR.ident, [k.internString(member)]),
          args,
        ]);
      } else {
        // Bare attribute access — distinct CTOR so emit/eval can
        // dispatch differently from a zero-arg method call. Carries
        // the receiver + the attribute-name ident.
        node = captureNode(k, CTOR.attr, [
          node,
          captureNode(k, CTOR.ident, [k.internString(member)]),
        ]);
      }
      continue;
    }
    break;
  }
  return node;
}

function parseArgs(k: Kernel, c: Cursor): NodeID {
  const args: NodeID[] = [];
  skipAllWhitespace(c);
  if (peek(c) === ")") return captureNode(k, CTOR.args, []);
  while (true) {
    skipAllWhitespace(c);
    const e = parseExpr(k, c);
    if (e === null) break;
    args.push(e);
    skipAllWhitespace(c);
    if (!consume(c, ",")) break;
  }
  return captureNode(k, CTOR.args, args);
}

function parseUnary(k: Kernel, c: Cursor): NodeID | null {
  skipSpacesAndComments(c);
  if (consume(c, "-")) {
    const inner = parseUnary(k, c);
    if (inner === null) return null;
    return captureNode(k, CTOR.neg, [inner]);
  }
  if (consumeKeyword(c, "not")) {
    const inner = parseUnary(k, c);
    if (inner === null) return null;
    return captureNode(k, CTOR.not_, [inner]);
  }
  return parsePostfix(k, c);
}

function parseMul(k: Kernel, c: Cursor): NodeID | null {
  let left = parseUnary(k, c);
  if (left === null) return null;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    skipSpacesAndComments(c);
    // Don't consume `*`/`/`/`%` when followed by `=` — augmented assign.
    if (c.pos + 1 < c.src.length && c.src.charCodeAt(c.pos + 1) === 61 /* = */) {
      const ch = c.src.charCodeAt(c.pos);
      if (ch === 42 || ch === 47 || ch === 37) break;
    }
    let ctor: string | null = null;
    if (consume(c, "*")) ctor = CTOR.mul;
    else if (consume(c, "/")) ctor = CTOR.div;
    else if (consume(c, "%")) ctor = CTOR.mod;
    else break;
    const right = parseUnary(k, c);
    if (right === null) throw new SyntaxError(`python: rhs expected at ${c.pos}`);
    left = captureNode(k, ctor, [left, right]);
  }
  return left;
}

function parseAdd(k: Kernel, c: Cursor): NodeID | null {
  let left = parseMul(k, c);
  if (left === null) return null;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    skipSpacesAndComments(c);
    // Don't consume `+` or `-` when followed by `=` — that's an
    // augmented-assignment operator, parseStmt's job.
    if (c.pos + 1 < c.src.length && c.src.charCodeAt(c.pos + 1) === 61 /* = */) {
      const ch = c.src.charCodeAt(c.pos);
      if (ch === 43 /* + */ || ch === 45 /* - */) break;
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
    if (right === null) throw new SyntaxError(`python: rhs expected at ${c.pos}`);
    left = captureNode(k, ctor, [left, right]);
  }
  return left;
}

function parseCmp(k: Kernel, c: Cursor): NodeID | null {
  let left = parseAdd(k, c);
  if (left === null) return null;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    skipSpacesAndComments(c);
    let ctor: string | null = null;
    // Two-char comparisons first.
    if (consume(c, "==")) ctor = CTOR.eq;
    else if (consume(c, "!=")) ctor = CTOR.ne;
    else if (consume(c, "<=")) ctor = CTOR.le;
    else if (consume(c, ">=")) ctor = CTOR.ge;
    else if (consume(c, "<")) ctor = CTOR.lt;
    else if (consume(c, ">")) ctor = CTOR.gt;
    else if (consumeKeyword(c, "in")) ctor = CTOR.in_;
    else break;
    const right = parseAdd(k, c);
    if (right === null) throw new SyntaxError(`python: rhs expected at ${c.pos}`);
    left = captureNode(k, ctor, [left, right]);
  }
  return left;
}

function parseAnd(k: Kernel, c: Cursor): NodeID | null {
  let left = parseCmp(k, c);
  if (left === null) return null;
  while (consumeKeyword(c, "and")) {
    const right = parseCmp(k, c);
    if (right === null) throw new SyntaxError(`python: rhs after 'and' at ${c.pos}`);
    left = captureNode(k, CTOR.and_, [left, right]);
  }
  return left;
}

function parseOr(k: Kernel, c: Cursor): NodeID | null {
  let left = parseAnd(k, c);
  if (left === null) return null;
  while (consumeKeyword(c, "or")) {
    const right = parseAnd(k, c);
    if (right === null) throw new SyntaxError(`python: rhs after 'or' at ${c.pos}`);
    left = captureNode(k, CTOR.or_, [left, right]);
  }
  return left;
}

// Python conditional expression: <true-branch> if <cond> else <false-branch>
function parseConditional(k: Kernel, c: Cursor): NodeID | null {
  const trueBranch = parseOr(k, c);
  if (trueBranch === null) return null;
  if (!peekKeyword(c, "if")) return trueBranch;
  // It's a conditional expression iff `if` here is not part of a
  // statement (we're inside an expression context — return the
  // captured if-expr shape).
  consumeKeyword(c, "if");
  const cond = parseOr(k, c);
  if (cond === null)
    throw new SyntaxError(`python: cond required after 'if' at ${c.pos}`);
  expectKeyword(c, "else");
  const falseBranch = parseConditional(k, c);
  if (falseBranch === null)
    throw new SyntaxError(`python: false-branch required after 'else' at ${c.pos}`);
  // Conditional expression captures as if(cond, true, false) — same
  // ctor as the if statement to keep cross-language semantic identity;
  // emit dispatches based on whether the if children are statements
  // or expressions.
  return captureNode(k, CTOR.if_, [cond, trueBranch, falseBranch]);
}

function expectKeyword(c: Cursor, kw: string): void {
  if (!consumeKeyword(c, kw)) {
    throw new SyntaxError(
      `python: expected '${kw}' at position ${c.pos}`,
    );
  }
}

export function parseExpr(k: Kernel, c: Cursor): NodeID | null {
  return parseConditional(k, c);
}

// ----- statements -----

function currentLineIndent(c: Cursor): number {
  // Count leading spaces of the current line.
  let p = c.pos;
  while (p > 0 && c.src.charCodeAt(p - 1) !== 10) p--;
  let indent = 0;
  while (p < c.src.length && c.src.charCodeAt(p) === 32) {
    indent++;
    p++;
  }
  return indent;
}

function skipBlankLines(c: Cursor): void {
  while (!atEnd(c)) {
    const saved = c.pos;
    skipSpacesAndComments(c);
    if (atEnd(c)) return;
    if (c.src.charCodeAt(c.pos) === 10) {
      c.pos++;
      continue;
    }
    c.pos = saved;
    return;
  }
}

// Read the indent of the next non-blank line without consuming it.
function nextLineIndent(c: Cursor): number {
  const saved = c.pos;
  skipBlankLines(c);
  // Walk to start of current line.
  let p = c.pos;
  while (p > 0 && c.src.charCodeAt(p - 1) !== 10) p--;
  let indent = 0;
  while (p < c.src.length && c.src.charCodeAt(p) === 32) {
    indent++;
    p++;
  }
  c.pos = saved;
  return indent;
}

function parseStmt(k: Kernel, c: Cursor, blockIndent: number): NodeID | null {
  skipBlankLines(c);
  if (atEnd(c)) return null;
  const lineIndent = currentLineIndent(c);
  if (lineIndent < blockIndent) return null;
  // Move past leading spaces.
  c.pos += lineIndent - currentLineIndentRemaining(c);
  skipSpacesAndComments(c);

  if (peekKeyword(c, "def")) return parseDef(k, c, lineIndent);
  if (peekKeyword(c, "class")) return parseClass(k, c, lineIndent);
  if (peekKeyword(c, "if")) return parseIfStmt(k, c, lineIndent);
  if (peekKeyword(c, "for")) return parseForStmt(k, c, lineIndent);
  if (peekKeyword(c, "while")) return parseWhileStmt(k, c, lineIndent);
  if (peekKeyword(c, "return")) return parseReturn(k, c);
  if (peekKeyword(c, "import")) return parseImportStmt(k, c);
  if (peekKeyword(c, "from")) return parseFromImportStmt(k, c);
  if (peekKeyword(c, "pass")) {
    consumeKeyword(c, "pass");
    consumeEndOfLine(c);
    // `pass` lowers to an empty block — emitFk treats CTOR.block of zero
    // children as a no-op (emits "false").
    return captureNode(k, CTOR.block, []);
  }

  // Expression statement OR assignment.
  // Lookahead: parse an expression, then check for `=` (single-target
  // assignment). If `=` follows an IDENT-only LHS, this is an assignment;
  // otherwise it's an expression statement.
  const savedPos = c.pos;
  const e = parseExpr(k, c);
  if (e === null) return null;
  skipSpacesAndComments(c);
  // Variable type annotation: `name: <type-expr>` or `name: <type-expr> = <rhs>`.
  // Parse-and-ignore the annotation. The bare form becomes a no-op
  // expression statement (None); the annotated-assign form lowers to a
  // plain assignment — annotations carry no runtime semantics.
  if (
    c.pos < c.src.length &&
    c.src.charCodeAt(c.pos) === 58 /* : */ &&
    c.src.charCodeAt(c.pos + 1) !== 61 /* not := (walrus) */
  ) {
    const lhsCtor = capturedCtor(k, e);
    if (lhsCtor === CTOR.ident) {
      c.pos++; // skip `:`
      const ann = parseExpr(k, c);
      if (ann === null) {
        throw new SyntaxError(`python: type expression required after ':' at ${c.pos}`);
      }
      skipSpacesAndComments(c);
      // Annotated assignment: `name: T = value`
      if (
        c.pos < c.src.length &&
        c.src.charCodeAt(c.pos) === 61 /* = */ &&
        c.src.charCodeAt(c.pos + 1) !== 61 /* not == */
      ) {
        c.pos++; // skip `=`
        skipSpacesAndComments(c);
        const value = parseExpr(k, c);
        if (value === null) {
          throw new SyntaxError(`python: expr required after '=' in annotated assignment at ${c.pos}`);
        }
        consumeEndOfLine(c);
        return captureNode(k, CTOR.assign, [e, value]);
      }
      // Bare annotation: `name: T` — no runtime effect.
      consumeEndOfLine(c);
      return captureNode(k, CTOR.expr_stmt, [captureNode(k, CTOR.none_literal, [])]);
    }
  }
  // Check for augmented assignment first: += -= *= /= %=
  // Each is `<op>=` followed by an expr; the LHS must be an IDENT (v1).
  const augOp = (() => {
    if (c.pos + 1 >= c.src.length) return null;
    if (c.src.charCodeAt(c.pos + 1) !== 61 /* = */) return null;
    const ch = c.src.charCodeAt(c.pos);
    if (ch === 43) return "add"; // +
    if (ch === 45) return "sub"; // -
    if (ch === 42) return "mul"; // *
    if (ch === 47) return "div"; // /
    if (ch === 37) return "mod"; // %
    return null;
  })();
  if (augOp !== null) {
    const lhsCtor = capturedCtor(k, e);
    if (lhsCtor !== CTOR.ident) {
      throw new SyntaxError(
        `python: augmented assignment target must be a simple name (v1) at ${savedPos}`,
      );
    }
    c.pos += 2; // skip op + `=`
    skipSpacesAndComments(c);
    const rhs = parseExpr(k, c);
    if (rhs === null) {
      throw new SyntaxError(`python: expr required after '${String.fromCharCode(c.src.charCodeAt(c.pos - 2))}=' at ${c.pos}`);
    }
    consumeEndOfLine(c);
    // Lower `x += y` to `x = x + y` — same semantics, no new CTOR
    // needed. The CTOR-name picker uses the augOp value to choose the
    // arithmetic combinator.
    const opCtorMap: Record<string, string> = {
      add: CTOR.add, sub: CTOR.sub, mul: CTOR.mul, div: CTOR.div, mod: CTOR.mod,
    };
    const combined = captureNode(k, opCtorMap[augOp]!, [e, rhs]);
    return captureNode(k, CTOR.assign, [e, combined]);
  }
  // Check for `=` (and not `==`) — single-target assignment.
  if (
    c.pos < c.src.length &&
    c.src.charCodeAt(c.pos) === 61 /* = */ &&
    c.src.charCodeAt(c.pos + 1) !== 61 /* not == */
  ) {
    // Confirm LHS is a target Python permits (IDENT or ATTR for v1).
    const lhsCtor = capturedCtor(k, e);
    if (lhsCtor === CTOR.ident || lhsCtor === CTOR.attr) {
    const lhsCtor = capturedCtor(k, e);
    // CTOR.ident → plain `x = expr`. CTOR.subscript → `d[k] = v`
    // (dict / list mutation; emitFk lowers via _dict_set so dicts are
    // immutable-updated). Other targets remain pending.
    if (lhsCtor === CTOR.ident || lhsCtor === CTOR.subscript) {
      c.pos++; // skip `=`
      skipSpacesAndComments(c);
      const value = parseExpr(k, c);
      if (value === null) {
        throw new SyntaxError(`python: expr required after '=' at ${c.pos}`);
      }
      consumeEndOfLine(c);
      return captureNode(k, CTOR.assign, [e, value]);
    }
    // Subscript target — not yet supported as an assignment LHS.
    throw new SyntaxError(
      `python: assignment target must be a name or attribute (v1) at ${savedPos}`,
    throw new SyntaxError(
      `python: assignment target must be a name or subscript (v1) at ${savedPos}`,
    );
  }
  consumeEndOfLine(c);
  return captureNode(k, CTOR.expr_stmt, [e]);
}

function currentLineIndentRemaining(c: Cursor): number {
  // Helper: how many leading spaces remain to be skipped on the
  // current line, given that c.pos may already be partly past them.
  let p = c.pos;
  while (p > 0 && c.src.charCodeAt(p - 1) !== 10) p--;
  // p is at start of line; spaces from p to first non-space.
  let firstNonSpace = p;
  while (
    firstNonSpace < c.src.length &&
    c.src.charCodeAt(firstNonSpace) === 32
  )
    firstNonSpace++;
  return Math.max(0, firstNonSpace - c.pos);
}

function consumeEndOfLine(c: Cursor): void {
  skipSpacesAndComments(c);
  if (!atEnd(c) && c.src.charCodeAt(c.pos) === 10) c.pos++;
}

// resolveModuleMember — when the LHS of `X.Y` is a bare ident `X` that
// was bound by `import math` (or `import math as X`), return the kernel-
// native name for `math.Y`. Returns null if X isn't a module alias or Y
// isn't a known module member; in that case parsePostfix falls through
// to ordinary method_call shape.
function resolveModuleMember(
  k: Kernel,
  lhs: NodeID,
  member: string,
  c: Cursor,
): string | null {
  if (capturedCtor(k, lhs) !== CTOR.ident) return null;
  const nameKid = capturedChildren(k, lhs)[0]!;
  if (nameKid.level !== Level.TRIVIAL || nameKid.type !== Triv.STRING) return null;
  const aliasName = k.strs[nameKid.inst] ?? "";
  const moduleName = c.imports.moduleAliases.get(aliasName);
  if (moduleName === undefined) return null;
  const members = KERNEL_MODULES[moduleName];
  if (members === undefined) return null;
  const native = members[member];
  if (native === undefined) {
    throw new SyntaxError(
      `python: '${moduleName}' has no kernel-resident attribute '${member}' (have: ${Object.keys(members).join(", ")})`,
    );
  }
  return native;
}

// `import math` and `import math as m`. The body of the program never
// references the import-statement node again — it's emitted as a noop
// at runtime. The real effect lives in the cursor's import table, which
// the parser consults when rewriting subsequent identifiers and method
// calls into kernel-native invocations.
//
// Only KERNEL_MODULES entries (today: `math`) are recognized. Any other
// `import X` is an honest error — the substrate-resident module surface
// is exactly what the kernel has natives for; pretending otherwise would
// drift CPython away from the kernel runtimes silently.
function parseImportStmt(k: Kernel, c: Cursor): NodeID {
  expectKeyword(c, "import");
  skipSpacesAndComments(c);
  const moduleName = readIdentRaw(c);
  if (moduleName === null) {
    throw new SyntaxError(`python: module name required after 'import' at ${c.pos}`);
  }
  if (!(moduleName in KERNEL_MODULES)) {
    throw new SyntaxError(
      `python: 'import ${moduleName}' — only kernel-resident modules supported (have: ${Object.keys(KERNEL_MODULES).join(", ")})`,
    );
  }
  // Optional `as <alias>`
  let alias = moduleName;
  if (consumeKeyword(c, "as")) {
    skipSpacesAndComments(c);
    const a = readIdentRaw(c);
    if (a === null) {
      throw new SyntaxError(`python: alias name required after 'as' at ${c.pos}`);
    }
    alias = a;
  }
  c.imports.moduleAliases.set(alias, moduleName);
  consumeEndOfLine(c);
  // The import node is structural — emit/eval treat it as a noop. The
  // children carry the module name and alias for round-trip / introspection.
  return captureNode(k, CTOR.import_, [
    captureNode(k, CTOR.ident, [k.internString(moduleName)]),
    captureNode(k, CTOR.ident, [k.internString(alias)]),
  ]);
}

// `from math import sqrt, pi` and `from math import sqrt as s, pi as p`.
// Each imported name binds directly to a kernel-native; the parser
// records the binding so subsequent references to `sqrt` rewrite to
// `(math_sqrt ...)` and bare references to `pi` rewrite to `(math_pi)`.
function parseFromImportStmt(k: Kernel, c: Cursor): NodeID {
  expectKeyword(c, "from");
  skipSpacesAndComments(c);
  const moduleName = readIdentRaw(c);
  if (moduleName === null) {
    throw new SyntaxError(`python: module name required after 'from' at ${c.pos}`);
  }
  if (!(moduleName in KERNEL_MODULES)) {
    throw new SyntaxError(
      `python: 'from ${moduleName} import ...' — only kernel-resident modules supported`,
    );
  }
  const moduleMembers = KERNEL_MODULES[moduleName]!;
  expectKeyword(c, "import");
  // Comma-separated list of `name [as alias]` entries.
  const importedNames: NodeID[] = [];
  while (true) {
    skipSpacesAndComments(c);
    const name = readIdentRaw(c);
    if (name === null) {
      throw new SyntaxError(`python: name required after 'import' at ${c.pos}`);
    }
    const native = moduleMembers[name];
    if (native === undefined) {
      throw new SyntaxError(
        `python: '${moduleName}' has no kernel-resident attribute '${name}' (have: ${Object.keys(moduleMembers).join(", ")})`,
      );
    }
    let alias = name;
    if (consumeKeyword(c, "as")) {
      skipSpacesAndComments(c);
      const a = readIdentRaw(c);
      if (a === null) {
        throw new SyntaxError(`python: alias name required after 'as' at ${c.pos}`);
      }
      alias = a;
    }
    c.imports.directImports.set(alias, native);
    importedNames.push(
      captureNode(k, CTOR.ident, [k.internString(alias)]),
    );
    if (!consume(c, ",")) break;
  }
  consumeEndOfLine(c);
  return captureNode(k, CTOR.import_, [
    captureNode(k, CTOR.ident, [k.internString(moduleName)]),
    ...importedNames,
  ]);
}

function parseReturn(k: Kernel, c: Cursor): NodeID {
  expectKeyword(c, "return");
  skipSpacesAndComments(c);
  // Empty return → return None
  if (atEnd(c) || c.src.charCodeAt(c.pos) === 10) {
    consumeEndOfLine(c);
    return captureNode(k, CTOR.return_, [captureNode(k, CTOR.none_literal, [])]);
  }
  const e = parseExpr(k, c);
  if (e === null) throw new SyntaxError(`python: expr required after 'return' at ${c.pos}`);
  consumeEndOfLine(c);
  return captureNode(k, CTOR.return_, [e]);
}

function parseDef(k: Kernel, c: Cursor, lineIndent: number): NodeID {
  expectKeyword(c, "def");
  skipSpacesAndComments(c);
  const name = readIdentRaw(c);
  if (name === null) throw new SyntaxError(`python: function name required at ${c.pos}`);
  expect(c, "(");
  const params = parseDefParams(k, c);
  expect(c, ")");
  // Optional return-type annotation: `-> <type-expr>` before the `:`.
  // Parse-and-ignore — annotations carry no runtime semantics. The type
  // expression reuses the full expression parser so `-> List[int]`,
  // `-> Optional[T]`, `-> "Forward"` etc. all consume cleanly.
  skipSpacesAndComments(c);
  if (consume(c, "->")) {
    const ann = parseExpr(k, c);
    if (ann === null) {
      throw new SyntaxError(`python: type expression required after '->' at ${c.pos}`);
    }
  }
  expect(c, ":");
  const body = parseBlock(k, c, lineIndent);
  return captureNode(k, CTOR.def_, [
    captureNode(k, CTOR.ident, [k.internString(name)]),
    params,
    body,
  ]);
}

// parseClass — class shape with optional single base class:
//   class Name:                — no inheritance
//   class Name(Base):          — single base class (v2)
//       def __init__(self, …): … self.x = …
//       def method(self, …):   … self.y …
//
// Single-inheritance only — multiple inheritance, MRO complexity,
// metaclasses, abstract base classes, __init_subclass__ are each named
// as separate follow-up breaths. The class body is parsed as a sequence
// of method `def`s; the captured shape is
//   CTOR.class_(name-ident, base-ident-or-none, [methods…])
// where base-ident-or-none is a CTOR.ident node (the base class name)
// when inheritance is present, or a CTOR.none_literal when the class
// has no base.
function parseClass(k: Kernel, c: Cursor, lineIndent: number): NodeID {
  expectKeyword(c, "class");
  skipSpacesAndComments(c);
  const name = readIdentRaw(c);
  if (name === null) throw new SyntaxError(`python: class name required at ${c.pos}`);
  // Optional `(Base)` after the name — single inheritance. `class Foo():`
  // with no bases is also permitted (and equivalent to `class Foo:`).
  // Multiple bases (`class Foo(A, B):`) and metaclass kwargs remain
  // honest gaps for later breaths.
  let baseNode: NodeID = captureNode(k, CTOR.none_literal, []);
  skipSpacesAndComments(c);
  if (peek(c) === "(") {
    c.pos++;
    skipAllWhitespace(c);
    if (peek(c) !== ")") {
      const baseName = readIdentRaw(c);
      if (baseName === null) {
        throw new SyntaxError(
          `python: expected base class name after '(' at ${c.pos}`,
        );
      }
      if (KEYWORDS.has(baseName)) {
        throw new SyntaxError(
          `python: base class name cannot be a keyword '${baseName}' at ${c.pos}`,
        );
      }
      baseNode = captureNode(k, CTOR.ident, [k.internString(baseName)]);
      skipAllWhitespace(c);
      if (peek(c) === ",") {
        throw new SyntaxError(
          `python: multiple inheritance not supported (v2 is single base only) at ${c.pos}`,
        );
      }
      if (peek(c) !== ")") {
        throw new SyntaxError(
          `python: expected ')' after base class at ${c.pos}`,
        );
      }
    }
    c.pos++; // consume ')'
  }
  expect(c, ":");
  // Body — same indented-block shape as parseBlock, but each body
  // statement must be a method `def`. Accepts a trailing bare `pass`
  // for the empty class case.
  const bodyNode = parseBlock(k, c, lineIndent);
  const bodyKids = capturedChildren(k, bodyNode);
  const methods: NodeID[] = [];
  for (const stmt of bodyKids) {
    const ctor = capturedCtor(k, stmt);
    if (ctor === CTOR.def_) {
      methods.push(stmt);
    } else if (ctor === CTOR.block && capturedChildren(k, stmt).length === 0) {
      // bare `pass` — skip.
      continue;
    } else {
      throw new SyntaxError(
        `python: class body may only contain method defs; got '${ctor}'`,
      );
    }
  }
  return captureNode(k, CTOR.class_, [
    captureNode(k, CTOR.ident, [k.internString(name)]),
    baseNode,
    captureNode(k, CTOR.block, methods),
  ]);
}

function parseDefParams(k: Kernel, c: Cursor): NodeID {
  const params: NodeID[] = [];
  skipAllWhitespace(c);
  if (peek(c) === ")") return captureNode(k, CTOR.params, []);
  while (true) {
    skipAllWhitespace(c);
    const name = readIdentRaw(c);
    if (name === null) break;
    // Optional parameter type annotation: `name: <type-expr>`.
    // Parse-and-ignore — the type is metadata; the kernel doesn't
    // type-check. The type expression goes through parseExpr so subscripted
    // generics (`List[int]`, `Dict[str, int]`) and pipe/Optional unions
    // are absorbed.
    skipAllWhitespace(c);
    if (peek(c) === ":") {
      c.pos++;
      const ann = parseExpr(k, c);
      if (ann === null) {
        throw new SyntaxError(`python: type expression required after ':' for param '${name}' at ${c.pos}`);
      }
    }
    params.push(captureNode(k, CTOR.param, [k.internString(name)]));
    skipAllWhitespace(c);
    if (!consume(c, ",")) break;
  }
  return captureNode(k, CTOR.params, params);
}

function parseIfStmt(k: Kernel, c: Cursor, lineIndent: number): NodeID {
  expectKeyword(c, "if");
  const cond = parseExpr(k, c);
  if (cond === null) throw new SyntaxError(`python: condition required at ${c.pos}`);
  expect(c, ":");
  const thenBlock = parseBlock(k, c, lineIndent);
  const branches: NodeID[] = [cond, thenBlock];

  // Collect elif / else
  while (true) {
    skipBlankLines(c);
    const li = currentLineIndent(c);
    if (li !== lineIndent) break;
    if (peekKeywordAtIndent(c, "elif", lineIndent)) {
      skipToKeyword(c);
      expectKeyword(c, "elif");
      const ec = parseExpr(k, c);
      if (ec === null) throw new SyntaxError(`python: elif condition at ${c.pos}`);
      expect(c, ":");
      const eb = parseBlock(k, c, lineIndent);
      branches.push(ec, eb);
    } else if (peekKeywordAtIndent(c, "else", lineIndent)) {
      skipToKeyword(c);
      expectKeyword(c, "else");
      expect(c, ":");
      const eb = parseBlock(k, c, lineIndent);
      branches.push(eb);
      break;
    } else {
      break;
    }
  }
  return captureNode(k, CTOR.if_, branches);
}

function peekKeywordAtIndent(c: Cursor, kw: string, indent: number): boolean {
  const saved = c.pos;
  skipBlankLines(c);
  const li = currentLineIndent(c);
  if (li !== indent) {
    c.pos = saved;
    return false;
  }
  // Walk to first non-space.
  let p = c.pos;
  while (p < c.src.length && c.src.charCodeAt(p) === 32) p++;
  const r = c.src.startsWith(kw, p);
  if (r) {
    const after = c.src.charCodeAt(p + kw.length);
    if (!isNaN(after) && isIdentCont(after)) {
      c.pos = saved;
      return false;
    }
  }
  c.pos = saved;
  return r;
}

function skipToKeyword(c: Cursor): void {
  skipBlankLines(c);
  while (!atEnd(c) && c.src.charCodeAt(c.pos) === 32) c.pos++;
}

function parseForStmt(k: Kernel, c: Cursor, lineIndent: number): NodeID {
  expectKeyword(c, "for");
  skipSpacesAndComments(c);
  const varName = readIdentRaw(c);
  if (varName === null) throw new SyntaxError(`python: for var at ${c.pos}`);
  expectKeyword(c, "in");
  const iterExpr = parseExpr(k, c);
  if (iterExpr === null) throw new SyntaxError(`python: iter required at ${c.pos}`);
  expect(c, ":");
  const body = parseBlock(k, c, lineIndent);
  return captureNode(k, CTOR.for_, [
    captureNode(k, CTOR.ident, [k.internString(varName)]),
    iterExpr,
    body,
  ]);
}

function parseWhileStmt(k: Kernel, c: Cursor, lineIndent: number): NodeID {
  expectKeyword(c, "while");
  const cond = parseExpr(k, c);
  if (cond === null) throw new SyntaxError(`python: while cond at ${c.pos}`);
  expect(c, ":");
  const body = parseBlock(k, c, lineIndent);
  return captureNode(k, CTOR.while_, [cond, body]);
}

function parseBlock(k: Kernel, c: Cursor, parentIndent: number): NodeID {
  // After the ':' of a compound header, either there are statements on
  // the same line (inline) or we move to the next line and the block
  // is the next indent level.
  skipSpacesAndComments(c);
  const stmts: NodeID[] = [];
  if (!atEnd(c) && c.src.charCodeAt(c.pos) !== 10) {
    // Inline single-statement block.
    if (peekKeyword(c, "return")) {
      stmts.push(parseReturn(k, c));
    } else {
      const e = parseExpr(k, c);
      if (e !== null) {
        stmts.push(captureNode(k, CTOR.expr_stmt, [e]));
        consumeEndOfLine(c);
      }
    }
    return captureNode(k, CTOR.block, stmts);
  }
  // Move to next line; the block indent is whatever the first non-
  // blank line's indent is (must be > parentIndent).
  c.pos++; // consume newline
  skipBlankLines(c);
  if (atEnd(c)) return captureNode(k, CTOR.block, stmts);
  const blockIndent = currentLineIndent(c);
  if (blockIndent <= parentIndent) {
    return captureNode(k, CTOR.block, stmts);
  }
  while (!atEnd(c)) {
    skipBlankLines(c);
    if (atEnd(c)) break;
    const li = currentLineIndent(c);
    if (li < blockIndent) break;
    const stmt = parseStmt(k, c, blockIndent);
    if (stmt === null) break;
    stmts.push(stmt);
  }
  return captureNode(k, CTOR.block, stmts);
}

// ---------------------------------------------------------------------------
// Top-level entry: parsePython — produces a CTOR.module wrapping a list
// of top-level statements.
// ---------------------------------------------------------------------------

export function parsePython(k: Kernel, source: string): NodeID {
  const c: Cursor = {
    src: source,
    pos: 0,
    indent: 0,
    imports: { moduleAliases: new Map(), directImports: new Map() },
  };
  const stmts: NodeID[] = [];
  while (true) {
    skipBlankLines(c);
    if (atEnd(c)) break;
    const stmt = parseStmt(k, c, 0);
    if (stmt === null) break;
    stmts.push(stmt);
  }
  return captureNode(k, CTOR.module, stmts);
}

// ---------------------------------------------------------------------------
// emitPython — round-trip via ctor dispatch.
// ---------------------------------------------------------------------------

export function emitPython(k: Kernel, tree: NodeID): string {
  const out: string[] = [];
  emit(k, tree, 0, out);
  return out.join("");
}

function emit(k: Kernel, n: NodeID, depth: number, out: string[]): void {
  if (n.level === Level.TRIVIAL) {
    emitTrivial(k, n, out);
    return;
  }
  const ctor = capturedCtor(k, n);
  const kids = capturedChildren(k, n);
  switch (ctor) {
    case CTOR.module: {
      for (let i = 0; i < kids.length; i++) {
        emit(k, kids[i]!, 0, out);
        if (i < kids.length - 1) out.push("\n");
      }
      return;
    }
    case CTOR.expr_stmt: {
      indent(out, depth);
      emit(k, kids[0]!, depth, out);
      return;
    }
    case CTOR.int_literal:
    case CTOR.float_literal: {
      emitTrivial(k, kids[0]!, out);
      return;
    }
    case CTOR.bool_literal: {
      const v = kids[0]!;
      if (v.level === Level.TRIVIAL && v.type === Triv.BOOL) {
        out.push(v.inst ? "True" : "False");
        return;
      }
      out.push("False");
      return;
    }
    case CTOR.none_literal:
      out.push("None");
      return;
    case CTOR.str_literal: {
      const s = kids[0]!;
      if (s.level === Level.TRIVIAL && s.type === Triv.STRING) {
        out.push(JSON.stringify(k.strs[s.inst] ?? ""));
        return;
      }
      out.push('""');
      return;
    }
    case CTOR.ident: {
      const s = kids[0]!;
      if (s.level === Level.TRIVIAL && s.type === Triv.STRING) {
        out.push(k.strs[s.inst] ?? "");
        return;
      }
      return;
    }
    case CTOR.list_literal: {
      out.push("[");
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) out.push(", ");
        emit(k, kids[i]!, depth, out);
      }
      out.push("]");
      return;
    }
    case CTOR.dict_literal: {
      out.push("{");
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) out.push(", ");
        emit(k, kids[i]!, depth, out);
      }
      out.push("}");
      return;
    }
    case CTOR.dict_entry: {
      emit(k, kids[0]!, depth, out);
      out.push(": ");
      emit(k, kids[1]!, depth, out);
      return;
    }
    case CTOR.tuple_literal: {
      out.push("(");
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) out.push(", ");
        emit(k, kids[i]!, depth, out);
      }
      if (kids.length === 1) out.push(",");
      out.push(")");
      return;
    }
    case CTOR.call: {
      emit(k, kids[0]!, depth, out);
      out.push("(");
      emitArgs(k, kids[1]!, depth, out);
      out.push(")");
      return;
    }
    case CTOR.method_call: {
      emit(k, kids[0]!, depth, out);
      out.push(".");
      emit(k, kids[1]!, depth, out);
      const args = kids[2]!;
      const argKids = capturedChildren(k, args);
      if (argKids.length > 0 || capturedCtor(k, args) === CTOR.args) {
        out.push("(");
        emitArgs(k, args, depth, out);
        out.push(")");
      }
      return;
    }
    case CTOR.args: {
      // Emitted by parent (call / method_call). Standalone shouldn't happen.
      emitArgs(k, n, depth, out);
      return;
    }
    case CTOR.add:
      emitBin(k, kids, " + ", depth, out);
      return;
    case CTOR.sub:
      emitBin(k, kids, " - ", depth, out);
      return;
    case CTOR.mul:
      emitBin(k, kids, " * ", depth, out);
      return;
    case CTOR.div:
      emitBin(k, kids, " / ", depth, out);
      return;
    case CTOR.mod:
      emitBin(k, kids, " % ", depth, out);
      return;
    case CTOR.eq:
      emitBin(k, kids, " == ", depth, out);
      return;
    case CTOR.ne:
      emitBin(k, kids, " != ", depth, out);
      return;
    case CTOR.lt:
      emitBin(k, kids, " < ", depth, out);
      return;
    case CTOR.le:
      emitBin(k, kids, " <= ", depth, out);
      return;
    case CTOR.gt:
      emitBin(k, kids, " > ", depth, out);
      return;
    case CTOR.ge:
      emitBin(k, kids, " >= ", depth, out);
      return;
    case CTOR.and_:
      emitBin(k, kids, " and ", depth, out);
      return;
    case CTOR.or_:
      emitBin(k, kids, " or ", depth, out);
      return;
    case CTOR.not_:
      out.push("not ");
      emit(k, kids[0]!, depth, out);
      return;
    case CTOR.neg:
      out.push("-");
      emit(k, kids[0]!, depth, out);
      return;
    case CTOR.lambda_: {
      out.push("lambda");
      const params = capturedChildren(k, kids[0]!);
      if (params.length > 0) out.push(" ");
      emitParamList(k, kids[0]!, out);
      out.push(": ");
      emit(k, kids[1]!, depth, out);
      return;
    }
    case CTOR.params:
      emitParamList(k, n, out);
      return;
    case CTOR.param: {
      const nm = kids[0]!;
      if (nm.level === Level.TRIVIAL && nm.type === Triv.STRING)
        out.push(k.strs[nm.inst] ?? "");
      return;
    }
    case CTOR.def_: {
      indent(out, depth);
      out.push("def ");
      emit(k, kids[0]!, depth, out);
      out.push("(");
      emitParamList(k, kids[1]!, out);
      out.push("):");
      emitBlock(k, kids[2]!, depth, out);
      return;
    }
    case CTOR.return_: {
      indent(out, depth);
      out.push("return ");
      emit(k, kids[0]!, depth, out);
      return;
    }
    case CTOR.if_: {
      // Detect conditional expression form: exactly 3 children where the
      // middle is an expression (not a block) — emit as ternary.
      if (kids.length === 3 && capturedCtor(k, kids[1]!) !== CTOR.block) {
        // truthy-branch if cond else falsy-branch — but our parse stores
        // [cond, true, false]; emit Python's expression form.
        emit(k, kids[1]!, depth, out);
        out.push(" if ");
        emit(k, kids[0]!, depth, out);
        out.push(" else ");
        emit(k, kids[2]!, depth, out);
        return;
      }
      // Statement form: [cond0, block0, cond1, block1, ..., elseBlock?]
      indent(out, depth);
      out.push("if ");
      emit(k, kids[0]!, depth, out);
      out.push(":");
      emitBlock(k, kids[1]!, depth, out);
      let i = 2;
      while (i + 1 < kids.length) {
        out.push("\n");
        indent(out, depth);
        out.push("elif ");
        emit(k, kids[i]!, depth, out);
        out.push(":");
        emitBlock(k, kids[i + 1]!, depth, out);
        i += 2;
      }
      if (i < kids.length) {
        out.push("\n");
        indent(out, depth);
        out.push("else:");
        emitBlock(k, kids[i]!, depth, out);
      }
      return;
    }
    case CTOR.for_: {
      indent(out, depth);
      out.push("for ");
      emit(k, kids[0]!, depth, out);
      out.push(" in ");
      emit(k, kids[1]!, depth, out);
      out.push(":");
      emitBlock(k, kids[2]!, depth, out);
      return;
    }
    case CTOR.while_: {
      indent(out, depth);
      out.push("while ");
      emit(k, kids[0]!, depth, out);
      out.push(":");
      emitBlock(k, kids[1]!, depth, out);
      return;
    }
    case CTOR.block: {
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) out.push("\n");
        emit(k, kids[i]!, depth + 1, out);
      }
      return;
    }
    default:
      // Fall through: emit children naively.
      for (let i = 0; i < kids.length; i++) {
        if (i > 0) out.push(" ");
        emit(k, kids[i]!, depth, out);
      }
  }
}

function emitArgs(k: Kernel, args: NodeID, depth: number, out: string[]): void {
  const kids = capturedChildren(k, args);
  for (let i = 0; i < kids.length; i++) {
    if (i > 0) out.push(", ");
    emit(k, kids[i]!, depth, out);
  }
}

function emitParamList(k: Kernel, params: NodeID, out: string[]): void {
  const kids = capturedChildren(k, params);
  for (let i = 0; i < kids.length; i++) {
    if (i > 0) out.push(", ");
    emit(k, kids[i]!, 0, out);
  }
}

function emitBin(
  k: Kernel,
  kids: readonly NodeID[],
  op: string,
  depth: number,
  out: string[],
): void {
  emit(k, kids[0]!, depth, out);
  out.push(op);
  emit(k, kids[1]!, depth, out);
}

function emitBlock(k: Kernel, block: NodeID, depth: number, out: string[]): void {
  const kids = capturedChildren(k, block);
  if (kids.length === 0) {
    out.push(" pass");
    return;
  }
  if (kids.length === 1) {
    // Inline form: " <stmt>"
    out.push(" ");
    emitInlineStmt(k, kids[0]!, depth, out);
    return;
  }
  for (const s of kids) {
    out.push("\n");
    emit(k, s, depth + 1, out);
  }
}

function emitInlineStmt(k: Kernel, n: NodeID, depth: number, out: string[]): void {
  // Same as emit, but without the leading indent that the block-form uses.
  const ctor = capturedCtor(k, n);
  const kids = capturedChildren(k, n);
  switch (ctor) {
    case CTOR.return_:
      out.push("return ");
      emit(k, kids[0]!, depth, out);
      return;
    case CTOR.expr_stmt:
      emit(k, kids[0]!, depth, out);
      return;
    default:
      emit(k, n, depth, out);
  }
}

function emitTrivial(k: Kernel, n: NodeID, out: string[]): void {
  if (n.level !== Level.TRIVIAL) return;
  switch (n.type) {
    case Triv.INT32:
      // INT32 inst is unsigned-stored; reinterpret as signed.
      out.push(String((n.inst | 0)));
      return;
    case Triv.INT64: {
      // Decode from kernel's int64 table.
      const i = (k as unknown as { i64s: bigint[] }).i64s[n.inst];
      out.push(i !== undefined ? i.toString() : "0");
      return;
    }
    case Triv.FLOAT64:
      out.push(String(k.decodeFloat64(n.inst)));
      return;
    case Triv.STRING:
      out.push(k.strs[n.inst] ?? "");
      return;
    case Triv.BOOL:
      out.push(n.inst ? "True" : "False");
      return;
    case Triv.NULL:
      out.push("None");
      return;
    default:
      out.push("<?>");
  }
}

function indent(out: string[], depth: number): void {
  for (let i = 0; i < depth; i++) out.push("    ");
}

// ---------------------------------------------------------------------------
// evalPython — minimal walker over the captured-recipe tree.
//
// Lives here (not in kernel.ts) because the captured-recipe shape is
// defined by the Python Language cell's ctor vocabulary. Sibling
// languages will share the same vocabulary, so over time this can be
// promoted into a generic captured-recipe walker — but for #15's
// proof of shape, keep it local.
// ---------------------------------------------------------------------------

interface PyEnv {
  parent: PyEnv | null;
  vars: Map<number, Value>;
}

function newEnv(parent: PyEnv | null = null): PyEnv {
  return { parent, vars: new Map() };
}

function envLookup(env: PyEnv, nameID: number): Value | undefined {
  let e: PyEnv | null = env;
  while (e !== null) {
    const v = e.vars.get(nameID);
    if (v !== undefined) return v;
    e = e.parent;
  }
  return undefined;
}

function envBind(env: PyEnv, nameID: number, value: Value): void {
  env.vars.set(nameID, value);
}

// Walk a captured-recipe tree; returns a Value or throws ReturnSignal
// when a return statement fires inside a function body.

class ReturnSignal {
  constructor(public value: Value) {}
}

export function evalPython(k: Kernel, tree: NodeID, env?: PyEnv): Value {
  const E = env ?? newEnv();
  installBuiltins(k, E);
  return evalNode(k, tree, E);
}

function installBuiltins(k: Kernel, env: PyEnv): void {
  // Bind a minimal stdlib for the eval path. The Language cell's
  // stdlibBindings carries the canonical NodeIDs; here we map ident
  // names directly to runtime values so fib() can call itself.
  const intern = (s: string) => k.internName(s);
  envBind(env, intern("True"), { kind: "bool", bool: true });
  envBind(env, intern("False"), { kind: "bool", bool: false });
  envBind(env, intern("None"), { kind: "null" });
}

function evalNode(k: Kernel, n: NodeID, env: PyEnv): Value {
  if (n.level === Level.TRIVIAL) {
    return trivialToValue(k, n);
  }
  const ctor = capturedCtor(k, n);
  const kids = capturedChildren(k, n);
  // Language-cell trace hook: when k.ctorCounts is set (by python-trace
  // or similar), record each CTOR dispatch. Surfaces the structural
  // shape of evaluated Python at its own altitude — separate from the
  // kernel's `walk()` arm trace (which evalNode doesn't go through).
  if (k.ctorCounts !== undefined) {
    k.ctorCounts.set(ctor, (k.ctorCounts.get(ctor) ?? 0) + 1);
  }
  switch (ctor) {
    case CTOR.module: {
      let last: Value = { kind: "null" };
      for (const s of kids) last = evalNode(k, s, env);
      return last;
    }
    case CTOR.import_:
      // Noop at runtime — the parser already rewrote member accesses to
      // resolve through k.natives at the call site (kernel.natives carries
      // the math_sqrt / math_pi / math_floor / math_ceil / math_pow
      // bindings registered alongside the other Python builtins).
      return { kind: "null" };
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
        // Fall through to builtins via natives map.
        const nat = k.natives.get(nameTriv.inst);
        if (nat !== undefined) {
          return {
            kind: "closure",
            closure: { params: [], body: n, env: new Frame(null) },
          };
        }
        throw new Error(`python: unbound name '${k.nameStr(nameTriv.inst)}'`);
      }
      return v;
    }
    case CTOR.list_literal: {
      return { kind: "list", list: kids.map((c) => evalNode(k, c, env)) };
    }
    case CTOR.tuple_literal: {
      return { kind: "list", list: kids.map((c) => evalNode(k, c, env)) };
    }
    case CTOR.dict_literal: {
      // Build a "__dict__"-tagged alist sibling-parity with the kernel's
      // dict natives. Children are CTOR.dict_entry pairs.
      const items: Value[] = [{ kind: "str", str: "__dict__" }];
      for (const entry of kids) {
        const eKids = capturedChildren(k, entry);
        items.push(evalNode(k, eKids[0]!, env));
        items.push(evalNode(k, eKids[1]!, env));
      }
      return { kind: "list", list: items };
    }
    case CTOR.dict_entry: {
      // dict_entry is handled by dict_literal; reaching here standalone
      // means someone built one outside that context. Return a 2-list.
      return {
        kind: "list",
        list: [evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env)],
      };
    }
    case CTOR.in_: {
      // `k in container` — dict-key check, list membership, or substring.
      const needle = evalNode(k, kids[0]!, env);
      const hay = evalNode(k, kids[1]!, env);
      return { kind: "bool", bool: pythonIn(needle, hay) };
    }
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
    case CTOR.lt:
      return cmpOp(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "<");
    case CTOR.le:
      return cmpOp(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), "<=");
    case CTOR.gt:
      return cmpOp(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), ">");
    case CTOR.ge:
      return cmpOp(evalNode(k, kids[0]!, env), evalNode(k, kids[1]!, env), ">=");
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
    case CTOR.not_: {
      return { kind: "bool", bool: !truthy(evalNode(k, kids[0]!, env)) };
    }
    case CTOR.neg: {
      const v = evalNode(k, kids[0]!, env);
      if (v.kind === "int") return { kind: "int", int: -v.int };
      if (v.kind === "f64") return { kind: "f64", float: -v.float };
      throw new Error("neg: expected numeric");
    }
    case CTOR.if_: {
      // Conditional expression: [cond, true, false]; middle is NOT a block.
      if (kids.length === 3 && capturedCtor(k, kids[1]!) !== CTOR.block) {
        const cond = evalNode(k, kids[0]!, env);
        return truthy(cond) ? evalNode(k, kids[1]!, env) : evalNode(k, kids[2]!, env);
      }
      // Statement form
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
      // children: [target-node, value-node]. v1 targets: CTOR.ident
      // (simple name) and CTOR.attr (attribute write — the __init__
      // shape for classes). Richer targets (tuple unpack, subscript)
      // would dispatch here with their own assignment lowering.
      // children: [target-node, value-node]. Targets supported:
      //   ident         → bind in env
      //   subscript     → dict[k] = v (immutable rebind) or list[i] = v (in place)
      const target = kids[0]!;
      const value = evalNode(k, kids[1]!, env);
      const targetCtor = capturedCtor(k, target);
      if (targetCtor === CTOR.ident) {
        const nameID = capturedChildren(k, target)[0]!.inst;
        envBind(env, nameID, value);
        return { kind: "null" };
      }
      if (targetCtor === CTOR.attr) {
        const recv = evalNode(k, capturedChildren(k, target)[0]!, env);
        const fieldID = capturedChildren(k, capturedChildren(k, target)[1]!)[0]!.inst;
        const field = k.nameStr(fieldID);
        recordPut(recv, field, value);
        return { kind: "null" };
      }
      throw new Error(
        `python: assignment target must be a name or attribute (got ${targetCtor})`,
      }
      if (targetCtor === CTOR.subscript) {
        const subKids = capturedChildren(k, target);
        const container = evalNode(k, subKids[0]!, env);
        const idx = evalNode(k, subKids[1]!, env);
        if (isPyDict(container)) {
          // Find or append the key. Mutates the underlying list in-place
          // to match Python's dict semantics — d[k] = v changes d for
          // every alias.
          const xs = pyDictList(container);
          for (let i = 1; i + 1 < xs.length; i += 2) {
            if (pyDictKeyEq(xs[i]!, idx)) {
              xs[i + 1] = value;
              return { kind: "null" };
            }
          }
          xs.push(idx, value);
          return { kind: "null" };
        }
        if (container.kind === "list" && idx.kind === "int") {
          container.list[idx.int] = value;
          return { kind: "null" };
        }
        throw new Error(
          `python: subscript-assign requires dict or list container`,
        );
      }
      throw new Error(
        `python: assignment target must be a name or subscript (got ${targetCtor})`,
      );
    }
    case CTOR.subscript: {
      // children: [value-node, index-node]. Python d[k] / lst[i] / s[i] semantics.
      const v = evalNode(k, kids[0]!, env);
      const i = evalNode(k, kids[1]!, env);
      if (isPyDict(v)) {
        const xs = pyDictList(v);
        for (let j = 1; j + 1 < xs.length; j += 2) {
          if (pyDictKeyEq(xs[j]!, i)) return xs[j + 1]!;
        }
        return { kind: "null" };
      }
      if (v.kind === "list" && i.kind === "int") {
        const item = v.list[i.int];
        return item ?? { kind: "null" };
      }
      if (v.kind === "str" && i.kind === "int") {
        return { kind: "str", str: v.str[i.int] ?? "" };
      }
      throw new Error(
        `python: subscript requires dict, list, or str on LHS`,
      );
    }
    case CTOR.def_: {
      const nameNode = kids[0]!;
      const params = capturedChildren(k, kids[1]!);
      const body = kids[2]!;
      const paramNames: number[] = params.map((p) => {
        const t = capturedChildren(k, p)[0]!;
        return t.inst;
      });
      const fnNameID = capturedChildren(k, nameNode)[0]!.inst;
      const closure: PyClosure = {
        params: paramNames,
        body,
        env,
      };
      envBind(env, fnNameID, { kind: "list", list: [], pyClosure: closure } as Value & { pyClosure?: PyClosure });
      return { kind: "null" };
    }
    case CTOR.call: {
      const callee = kids[0]!;
      const argsNode = kids[1]!;
      const argKids = capturedChildren(k, argsNode);
      const argVals = argKids.map((a) => evalNode(k, a, env));
      // Resolve callee.
      let calleeVal: Value;
      if (capturedCtor(k, callee) === CTOR.ident) {
        const nameID = capturedChildren(k, callee)[0]!.inst;
        const bound = envLookup(env, nameID);
        if (bound !== undefined) {
          calleeVal = bound;
        } else {
          const nat = k.natives.get(nameID);
          if (nat !== undefined) {
            return nat.fn(k, argVals);
          }
          // Built-in fallbacks
          const builtin = builtinByName(k.nameStr(nameID));
          if (builtin !== null) return builtin(argVals);
          throw new Error(`python: unbound callable '${k.nameStr(nameID)}'`);
        }
      } else {
        calleeVal = evalNode(k, callee, env);
      }
      return invokePyClosure(k, calleeVal, argVals);
    }
    case CTOR.method_call: {
      const recvNode = kids[0]!;
      const methodNameID = capturedChildren(k, kids[1]!)[0]!.inst;
      const methodName = k.nameStr(methodNameID);
      const args = capturedChildren(k, kids[2]!).map((a) => evalNode(k, a, env));
      // Detect super().method(args) — receiver is the call node
      // `super()` with no arguments. Resolve to the parent class via
      // `__current_class__` (stashed by invokePyClosure when the method
      // frame was opened), then dispatch directly to the parent's
      // qualified method with the current `self`.
      if (isSuperCall(k, recvNode)) {
        const currentClassVal = envLookup(env, k.internName("__current_class__"));
        if (currentClassVal === undefined || currentClassVal.kind !== "str") {
          throw new Error(
            "python: super() used outside a class method body",
          );
        }
        const selfVal = envLookup(env, k.internName("self"));
        if (selfVal === undefined) {
          throw new Error("python: super() needs an enclosing self");
        }
        // `super().__init__(args)` chains through the parent constructor.
        // The parent constructor expects to build a fresh self; here we
        // need to populate the *current* self with the parent's fields.
        // We invoke the parent's constructor (which builds a fresh record),
        // then copy its data fields onto our current self.
        if (methodName === "__init__") {
          const baseID = k.internName(`${currentClassVal.str}__base`);
          const baseVal = envLookup(env, baseID);
          if (baseVal === undefined || baseVal.kind !== "str" || baseVal.str === "") {
            throw new Error(
              `python: super().__init__ in class '${currentClassVal.str}' which has no base class`,
            );
          }
          const parentCtorID = k.internName(baseVal.str);
          const parentCtor = envLookup(env, parentCtorID);
          if (parentCtor === undefined) {
            throw new Error(
              `python: parent constructor '${baseVal.str}' not bound`,
            );
          }
          const parentRecord = invokePyClosure(k, parentCtor, args);
          mergeParentFields(selfVal, parentRecord);
          return { kind: "null" };
        }
        return dispatchSuperMethod(
          k,
          env,
          currentClassVal.str,
          methodName,
          selfVal,
          args,
        );
      }
      const recv = evalNode(k, recvNode, env);
      // Class-record receivers route through env-bound qualified
      // closures (`<ClassName>__<methodName>`) — mirrors the kernel's
      // _dispatch native. Falls back to dispatchMethod for built-in
      // str/list method dispatch. Inheritance: walk the `__base__`
      // chain when the qualified method isn't bound on the immediate
      // class — first match wins.
      if (recv.kind === "list" && hasClassTag(recv)) {
        const className = recordGet(recv, "__class__");
        if (className.kind !== "str") {
          throw new Error("python: receiver's __class__ is not a string");
        }
        return dispatchOnChain(k, env, className.str, methodName, recv, args);
      }
      return dispatchMethod(k, recv, methodName, args);
    }
    case CTOR.lambda_: {
      const params = capturedChildren(k, kids[0]!);
      const body = kids[1]!;
      const paramNames: number[] = params.map((p) => {
        const t = capturedChildren(k, p)[0]!;
        return t.inst;
      });
      const closure: PyClosure = { params: paramNames, body, env };
      return { kind: "list", list: [], pyClosure: closure } as Value & { pyClosure?: PyClosure };
    }
    case CTOR.for_: {
      const varNameID = capturedChildren(k, kids[0]!)[0]!.inst;
      const iter = evalNode(k, kids[1]!, env);
      const body = kids[2]!;
      if (iter.kind !== "list") throw new Error("for: expected iterable");
      // Iterating a dict yields its keys (Python semantics).
      const items: Value[] = [];
      if (isPyDict(iter)) {
        const xs = pyDictList(iter);
        for (let i = 1; i + 1 < xs.length; i += 2) items.push(xs[i]!);
      } else {
        for (const item of iter.list) items.push(item);
      }
      let last: Value = { kind: "null" };
      for (const item of items) {
        envBind(env, varNameID, item);
        last = evalNode(k, body, env);
      }
      return last;
    }
    case CTOR.while_: {
      const cond = kids[0]!;
      const body = kids[1]!;
      let last: Value = { kind: "null" };
      while (truthy(evalNode(k, cond, env))) {
        last = evalNode(k, body, env);
      }
      return last;
    }
    case CTOR.class_: {
      // children: [name-ident, base-ident-or-none, methods-block]
      // Build a constructor closure bound under the class name, plus one
      // closure per method bound under `<ClassName>__<methodName>`.
      // Method dispatch reads `__class__` from the receiver record and
      // walks the `__base__` chain — matches the kernel's `_dispatch`
      // native. `super().method(args)` inside a method body resolves to
      // the parent's method via the class context carried on each method
      // closure (`methodClassName`).
      const classNameID = capturedChildren(k, kids[0]!)[0]!.inst;
      const className = k.nameStr(classNameID);
      const baseNode = kids[1]!;
      const baseCtor = capturedCtor(k, baseNode);
      let baseName = "";
      if (baseCtor === CTOR.ident) {
        const baseID = capturedChildren(k, baseNode)[0]!.inst;
        baseName = k.nameStr(baseID);
      }
      // Bind `<ClassName>__base` so super().X() can find the parent.
      // Mirrors the kernel-side `<C>__base` defn-binding.
      envBind(
        env,
        k.internName(`${className}__base`),
        { kind: "str", str: baseName },
      );
      const methodNodes = capturedChildren(k, kids[2]!);
      let initMethod: NodeID | null = null;
      const others: NodeID[] = [];
      for (const m of methodNodes) {
        const mKids = capturedChildren(k, m);
        const mNameID = capturedChildren(k, mKids[0]!)[0]!.inst;
        const mName = k.nameStr(mNameID);
        if (mName === "__init__") initMethod = m;
        else others.push(m);
      }
      // Constructor: call into the init body with self as a fresh record.
      const constructorValue: Value = {
        kind: "list",
        list: [],
        pyClosure: makeConstructorClosure(
          k,
          className,
          baseName,
          initMethod,
          env,
        ),
      } as Value & { pyClosure?: PyClosure };
      envBind(env, classNameID, constructorValue);
      // Each non-init method becomes a closure under `<ClassName>__<m>`.
      // The closure carries `methodClassName` so super() inside the body
      // can find the parent via the class chain.
      for (const m of others) {
        const mKids = capturedChildren(k, m);
        const mNameID = capturedChildren(k, mKids[0]!)[0]!.inst;
        const mName = k.nameStr(mNameID);
        const paramNodes = capturedChildren(k, mKids[1]!);
        const paramNames = paramNodes.map(
          (p) => capturedChildren(k, p)[0]!.inst,
        );
        const body = mKids[2]!;
        const closure: PyClosure = {
          params: paramNames,
          body,
          env,
          methodClassName: className,
        };
        const qualifiedID = k.internName(`${className}__${mName}`);
        envBind(env, qualifiedID, {
          kind: "list",
          list: [],
          pyClosure: closure,
        } as Value & { pyClosure?: PyClosure });
      }
      return { kind: "null" };
    }
    case CTOR.attr: {
      // children: [receiver-node, field-ident]
      const recv = evalNode(k, kids[0]!, env);
      const fieldID = capturedChildren(k, kids[1]!)[0]!.inst;
      const field = k.nameStr(fieldID);
      return recordGet(recv, field);
    }
    default:
      throw new Error(`evalPython: unsupported ctor '${ctor}'`);
  }
}

// Build the constructor closure for a class. Body is the original
// __init__'s body; invokePyClosure recognises `ctorClassName` and
// arranges for a fresh tagged record to be bound as `self` before the
// body runs, then returns that record. `baseName` carries the parent
// class so `super().__init__(args)` inside the body resolves correctly.
function makeConstructorClosure(
  k: Kernel,
  className: string,
  baseName: string,
  initMethod: NodeID | null,
  env: PyEnv,
): PyClosure {
  if (initMethod === null) {
    // No __init__ — constructor takes no args and returns a bare record
    // tagged with the class name. The body is an empty block; the ctor
    // branch in invokePyClosure builds the record regardless.
    const emptyBlock = k.intern(
      {
        pkg: 1,
        level: Level.BASIC,
        type: RBasic.LIST,
        inst: k.internName(CTOR.block),
      },
      [],
    );
    return {
      params: [],
      body: emptyBlock,
      env,
      ctorClassName: className,
      ctorBaseName: baseName,
    };
  }
  const initKids = capturedChildren(k, initMethod);
  const paramNodes = capturedChildren(k, initKids[1]!);
  // Skip `self` (first param) — constructor args are the rest.
  const ctorParamIDs = paramNodes
    .slice(1)
    .map((p) => capturedChildren(k, p)[0]!.inst);
  return {
    params: ctorParamIDs,
    body: initKids[2]!,
    env,
    ctorClassName: className,
    ctorBaseName: baseName,
  };
}

// Is this node the shape `super()` — CTOR.call where callee is the
// ident "super" and the args list is empty? Receiver-position super
// with arguments (Python 3's two-arg super) is a follow-up gap.
function isSuperCall(k: Kernel, n: NodeID): boolean {
  if (n.level === Level.TRIVIAL) return false;
  if (capturedCtor(k, n) !== CTOR.call) return false;
  const callKids = capturedChildren(k, n);
  if (callKids.length !== 2) return false;
  const callee = callKids[0]!;
  if (capturedCtor(k, callee) !== CTOR.ident) return false;
  const nameID = capturedChildren(k, callee)[0]!.inst;
  if (k.nameStr(nameID) !== "super") return false;
  // Args list must be empty.
  return capturedChildren(k, callKids[1]!).length === 0;
}

// Walk a class's inheritance chain looking for `<C>__<m>` binding.
// First match wins; matches dispatch with `self` as the first arg.
function dispatchOnChain(
  k: Kernel,
  env: PyEnv,
  startClass: string,
  methodName: string,
  selfVal: Value,
  args: Value[],
): Value {
  let current: string | null = startClass;
  const chain: string[] = [startClass];
  while (current !== null) {
    const qualifiedID = k.internName(`${current}__${methodName}`);
    const cl = envLookup(env, qualifiedID);
    if (cl !== undefined) {
      return invokePyClosure(k, cl, [selfVal, ...args]);
    }
    // Walk to base.
    const baseID = k.internName(`${current}__base`);
    const baseVal = envLookup(env, baseID);
    if (baseVal === undefined || baseVal.kind !== "str" || baseVal.str === "") {
      break;
    }
    current = baseVal.str;
    chain.push(current);
  }
  throw new Error(
    `python: no method '${methodName}' in inheritance chain [${chain.join(" -> ")}]`,
  );
}

// `super().method(args)` from inside a method of `currentClass`:
// resolve `method` starting at `currentClass`'s base, walk further if
// needed. Always uses the current `self`.
function dispatchSuperMethod(
  k: Kernel,
  env: PyEnv,
  currentClass: string,
  methodName: string,
  selfVal: Value,
  args: Value[],
): Value {
  const baseID = k.internName(`${currentClass}__base`);
  const baseVal = envLookup(env, baseID);
  if (baseVal === undefined || baseVal.kind !== "str" || baseVal.str === "") {
    throw new Error(
      `python: super() in class '${currentClass}' which has no base class`,
    );
  }
  return dispatchOnChain(k, env, baseVal.str, methodName, selfVal, args);
}

function hasClassTag(recv: Value): boolean {
  if (recv.kind !== "list") return false;
  for (let i = 0; i + 1 < recv.list.length; i += 2) {
    const k = recv.list[i]!;
    if (k.kind === "str" && k.str === "__class__") return true;
  }
  return false;
}

// Record read on a list-shaped record (alternating key/value entries).
function recordGet(recv: Value, field: string): Value {
  if (recv.kind !== "list") {
    throw new Error(`python: _get on non-record (${recv.kind})`);
  }
  for (let i = 0; i + 1 < recv.list.length; i += 2) {
    const k = recv.list[i]!;
    if (k.kind === "str" && k.str === field) return recv.list[i + 1]!;
  }
  throw new Error(`python: no field '${field}' on record`);
}

// super().__init__ chains by invoking the parent constructor (which
// builds a fresh record) and then copying the parent's data fields onto
// the current self. Strips `__class__` and `__base__` from the parent
// — the child's identity carries through unchanged. Existing child
// fields aren't overwritten (matches `_merge_record` on the kernel
// side: child wins for shared field names).
function mergeParentFields(self: Value, parentRecord: Value): void {
  if (self.kind !== "list") {
    throw new Error("python: super().__init__ self is not a record");
  }
  if (parentRecord.kind !== "list") {
    throw new Error("python: parent constructor did not return a record");
  }
  const existing = new Set<string>();
  for (let i = 0; i + 1 < self.list.length; i += 2) {
    const k = self.list[i]!;
    if (k.kind === "str") existing.add(k.str);
  }
  for (let i = 0; i + 1 < parentRecord.list.length; i += 2) {
    const key = parentRecord.list[i]!;
    if (key.kind !== "str") continue;
    if (key.str === "__class__" || key.str === "__base__") continue;
    if (existing.has(key.str)) continue;
    self.list.push(key);
    self.list.push(parentRecord.list[i + 1]!);
  }
}

// In-place record write — mirrors what `self.x = expr` does during
// __init__. Outside __init__, attribute assignment would normally be
// a v1 honest gap, but the TS eval path tolerates it since list entries
// are mutable.
function recordPut(recv: Value, field: string, value: Value): void {
  if (recv.kind !== "list") {
    throw new Error(`python: attribute assign on non-record (${recv.kind})`);
  }
  for (let i = 0; i + 1 < recv.list.length; i += 2) {
    const k = recv.list[i]!;
    if (k.kind === "str" && k.str === field) {
      recv.list[i + 1] = value;
      return;
    }
  }
  recv.list.push({ kind: "str", str: field });
  recv.list.push(value);
}

interface PyClosure {
  params: number[];
  body: NodeID;
  env: PyEnv;
  // When set, this is a constructor closure: invocation allocates a
  // fresh record tagged with this className, binds it as `self` in the
  // call frame, runs the body (which is the __init__ body), and
  // returns the populated record. None ⇒ plain function/method.
  ctorClassName?: string;
  // When set, names the parent class — constructor chains through the
  // parent's __init__ first (super().__init__ semantics), then runs the
  // child's body. Only used when ctorClassName is also set. Empty
  // string ⇒ no base.
  ctorBaseName?: string;
  // When set, this is a method closure — the class it was defined in.
  // Used by `super().X(args)` inside the body to find the parent class
  // via `<methodClassName>__base`.
  methodClassName?: string;
}

function invokePyClosure(k: Kernel, v: Value, args: Value[]): Value {
  const closure = (v as Value & { pyClosure?: PyClosure }).pyClosure;
  if (!closure) throw new Error("call: callee is not a Python closure");
  if (args.length !== closure.params.length) {
    throw new Error(
      `call: arity mismatch (expected ${closure.params.length}, got ${args.length})`,
    );
  }
  const callEnv = newEnv(closure.env);
  for (let i = 0; i < closure.params.length; i++) {
    envBind(callEnv, closure.params[i]!, args[i]!);
  }
  // Constructor invocation: allocate a fresh record tagged with the
  // class name + base name, bind it as `self`, run the __init__ body,
  // return the record. The body's `self.x = v` writes go through
  // recordPut and the record mutates in-place. `super().__init__(args)`
  // inside the body dispatches via the parent's init closure with the
  // same `self`, populating parent-defined fields directly.
  if (closure.ctorClassName !== undefined) {
    const self: Value = {
      kind: "list",
      list: [
        { kind: "str", str: "__class__" },
        { kind: "str", str: closure.ctorClassName },
        { kind: "str", str: "__base__" },
        { kind: "str", str: closure.ctorBaseName ?? "" },
      ],
    };
    envBind(callEnv, k.internName("self"), self);
    // Methods called via super() from within __init__ need to know the
    // current class context. We stash methodClassName on the call frame
    // by binding `__current_class__` to a string value.
    envBind(callEnv, k.internName("__current_class__"), {
      kind: "str",
      str: closure.ctorClassName,
    });
    try {
      evalNode(k, closure.body, callEnv);
    } catch (e) {
      if (!(e instanceof ReturnSignal)) throw e;
      // __init__ shouldn't `return` anything, but tolerate it for parity
      // with CPython which silently ignores the return value.
    }
    return self;
  }
  // Method-frame: when this closure carries a methodClassName, stash it
  // on the call frame so super().X(args) inside the body can pick it up.
  if (closure.methodClassName !== undefined) {
    envBind(callEnv, k.internName("__current_class__"), {
      kind: "str",
      str: closure.methodClassName,
    });
  }
  try {
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
      // Fit into JS number where possible.
      if (i >= BigInt(-2147483648) && i <= BigInt(2147483647)) {
        return { kind: "int", int: Number(i) };
      }
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
  // Python's `+` is overloaded: int+int / float+float / str+str / list+list.
  // The kernel's polymorphic `_plus` native handles the same shape;
  // the TS evaluator mirrors it so the runtimes agree.
  if (op === "+") {
    if (a.kind === "str" && b.kind === "str") {
      return { kind: "str", str: a.str + b.str };
    }
    if (a.kind === "list" && b.kind === "list") {
      return { kind: "list", list: [...a.list, ...b.list] };
    }
  }
  const an = numericOf(a);
  const bn = numericOf(b);
  const bothInt = an.isInt && bn.isInt && op !== "/";
  let r: number;
  switch (op) {
    case "+":
      r = an.v + bn.v;
      break;
    case "-":
      r = an.v - bn.v;
      break;
    case "*":
      r = an.v * bn.v;
      break;
    case "/":
      r = an.v / bn.v;
      break;
    case "%":
      r = an.v - Math.floor(an.v / bn.v) * bn.v;
      break;
    default:
      throw new Error(`numBinop: ${op}`);
  }
  if (bothInt) return { kind: "int", int: r | 0 };
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
    case "<":
      r = av < bv;
      break;
    case "<=":
      r = av <= bv;
      break;
    case ">":
      r = av > bv;
      break;
    case ">=":
      r = av >= bv;
      break;
    default:
      throw new Error(`cmpOp: ${op}`);
  }
  return { kind: "bool", bool: r };
}

function truthy(v: Value): boolean {
  switch (v.kind) {
    case "null":
      return false;
    case "bool":
      return v.bool;
    case "int":
      return v.int !== 0;
    case "f64":
      return v.float !== 0;
    case "str":
      return v.str.length > 0;
    case "list":
      return v.list.length > 0;
    default:
      return true;
  }
}

// Minimal builtin fallback for the few Python names not bound via natives.
function builtinByName(name: string): ((args: Value[]) => Value) | null {
  switch (name) {
    case "len":
      return (args) => {
        const v = args[0];
        if (v?.kind === "list") {
          if (isPyDict(v)) return { kind: "int", int: (pyDictList(v).length - 1) / 2 };
          return { kind: "int", int: v.list.length };
        }
        if (v?.kind === "str") return { kind: "int", int: v.str.length };
        return { kind: "int", int: 0 };
      };
    case "range":
      return (args) => {
        const start = args.length >= 2 ? numericOf(args[0]!).v : 0;
        const stop = args.length >= 2 ? numericOf(args[1]!).v : numericOf(args[0]!).v;
        const step = args.length >= 3 ? numericOf(args[2]!).v : 1;
        const out: Value[] = [];
        if (step > 0) for (let i = start; i < stop; i += step) out.push({ kind: "int", int: i | 0 });
        else if (step < 0) for (let i = start; i > stop; i += step) out.push({ kind: "int", int: i | 0 });
        return { kind: "list", list: out };
      };
    case "print":
      return (args) => {
        process.stdout.write(
          args.map((a) => renderForPrint(a)).join(" ") + "\n",
        );
        return { kind: "null" };
      };
    case "str":
      return (args) => ({ kind: "str", str: renderForPrint(args[0] ?? { kind: "null" }) });
    case "int":
      return (args) => {
        const v = args[0];
        if (v?.kind === "int") return v;
        if (v?.kind === "f64") return { kind: "int", int: v.float | 0 };
        if (v?.kind === "str") return { kind: "int", int: parseInt(v.str, 10) || 0 };
        if (v?.kind === "bool") return { kind: "int", int: v.bool ? 1 : 0 };
        return { kind: "int", int: 0 };
      };
    case "float":
      return (args) => {
        const v = args[0];
        if (v?.kind === "f64") return v;
        if (v?.kind === "int") return { kind: "f64", float: v.int };
        if (v?.kind === "str") return { kind: "f64", float: parseFloat(v.str) || 0 };
        return { kind: "f64", float: 0 };
      };
    case "list":
      return (args) => {
        const v = args[0];
        if (!v) return { kind: "list", list: [] };
        if (v.kind === "list") return v;
        if (v.kind === "str") return { kind: "list", list: v.str.split("").map((c) => ({ kind: "str", str: c } as Value)) };
        return { kind: "list", list: [v] };
      };
    case "dict":
      return () => ({ kind: "list", list: [] });
    default:
      return null;
  }
}

function renderForPrint(v: Value): string {
  switch (v.kind) {
    case "null":
      return "None";
    case "bool":
      return v.bool ? "True" : "False";
    case "int":
      return String(v.int);
    case "f64":
      return String(v.float);
    case "str":
      return v.str;
    case "list":
      if (isPyDict(v)) {
        const xs = pyDictList(v);
        const parts: string[] = [];
        for (let i = 1; i + 1 < xs.length; i += 2) {
          parts.push(`${renderForPrint(xs[i]!)}: ${renderForPrint(xs[i + 1]!)}`);
        }
        return "{" + parts.join(", ") + "}";
      }
      return "[" + v.list.map(renderForPrint).join(", ") + "]";
    default:
      return "<value>";
  }
}

// Dict tagged-list helpers — shared by evalNode + builtins. Same shape
// the kernel's _dict_* natives use, so the evaluator and the kernel
// agree on what counts as a dict. Plain boolean predicate (not a TS
// type guard) so the "v.kind === 'list'" narrowing after the dict
// branch still admits the regular list path.
function isPyDict(v: Value): boolean {
  return (
    v.kind === "list" &&
    v.list.length > 0 &&
    v.list[0]!.kind === "str" &&
    (v.list[0] as { kind: "str"; str: string }).str === "__dict__"
  );
}
// Cast a dict-shaped value's underlying list — TS narrowing has been
// satisfied by isPyDict, this just makes the access ergonomic.
function pyDictList(v: Value): Value[] {
  return (v as { kind: "list"; list: Value[] }).list;
}

function pyDictKeyEq(a: Value, b: Value): boolean {
  if (a.kind === "str" && b.kind === "str") return a.str === b.str;
  if (a.kind === "int" && b.kind === "int") return a.int === b.int;
  return false;
}

function pythonIn(needle: Value, hay: Value): boolean {
  if (isPyDict(hay)) {
    const xs = pyDictList(hay);
    for (let i = 1; i + 1 < xs.length; i += 2) {
      if (pyDictKeyEq(xs[i]!, needle)) return true;
    }
    return false;
  }
  if (hay.kind === "list") {
    for (const v of hay.list) {
      if (
        (needle.kind === "int" && v.kind === "int" && needle.int === v.int) ||
        (needle.kind === "str" && v.kind === "str" && needle.str === v.str) ||
        (needle.kind === "bool" && v.kind === "bool" && needle.bool === v.bool)
      ) {
        return true;
      }
    }
    return false;
  }
  if (needle.kind === "str" && hay.kind === "str") {
    return hay.str.includes(needle.str);
  }
  return false;
}

function dispatchMethod(k: Kernel, recv: Value, name: string, args: Value[]): Value {
  // Minimal method dispatch. Real Python method resolution lives in the
  // type system; this is enough for round-trip + bench-equivalent code.
  if (recv.kind === "str") {
    switch (name) {
      case "upper":
        return { kind: "str", str: recv.str.toUpperCase() };
      case "lower":
        return { kind: "str", str: recv.str.toLowerCase() };
      case "len":
        return { kind: "int", int: recv.str.length };
    }
  }
  if (recv.kind === "list") {
    switch (name) {
      case "len":
        return { kind: "int", int: recv.list.length };
      case "append":
        recv.list.push(args[0] ?? { kind: "null" });
        return { kind: "null" };
    }
  }
  throw new Error(`method '${name}' not supported on ${recv.kind}`);
}

// ---------------------------------------------------------------------------
// Public surface: build & register the Python Language cell.
// ---------------------------------------------------------------------------

export interface PythonLanguage {
  readonly lang: Language;
  readonly formats: FormatLibrary;
}

export function buildPythonLanguage(k: Kernel): PythonLanguage {
  const formats = buildFormatLibrary(k);
  const ingestionGrammar = buildIngestionGrammar(k);
  const emissionTemplate = buildEmissionTemplate(k);

  // stdlib bindings: surface-name → identifier-cell NodeID. The
  // identifier-cells are placeholders for the real per-builtin recipe
  // cells (range-cell, list-length-cell, ...) that the broader
  // substrate will resolve. Two languages that ship the same name +
  // recipe NodeID will share semantic identity for that builtin.
  const stdlibBindings = new Map<string, NodeID>();
  for (const name of [
    "len",
    "range",
    "print",
    "str",
    "int",
    "float",
    "list",
    "dict",
    "True",
    "False",
    "None",
  ]) {
    const bindingCell = k.intern(
      {
        pkg: 1,
        level: Level.BASIC,
        type: RBasic.IDENT,
        inst: 0,
      },
      [k.internString(name)],
    );
    stdlibBindings.set(name, bindingCell);
  }

  // Numeric defaults — Python's `int` is mapped to INT64; Python's
  // `float` to FP64. `complex` is left unbound (v0 doesn't support it).
  const numericDefaults = new Map([
    ["int", formats.INT64],
    ["float", formats.FP64],
  ]);

  const lang = registerLanguage(k, {
    name: "python",
    version: "3.13",
    ingestionGrammar,
    emissionTemplate,
    stdlibBindings,
    numericDefaults,
  });

  return { lang, formats };
}
