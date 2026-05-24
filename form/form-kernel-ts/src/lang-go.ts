// lang-go.ts — Language cell for Go 1.23, sibling to lang-ts / lang-rust.
//
// What a Language cell is: a content-addressed bundle of (id, version, parser,
// emitter, numeric format-recipes, stdlib bindings) — enough that arbitrary
// Go source can be ingested into the substrate as a recipe tree, walked by
// the kernel, and round-tripped back to Go source. Cross-language structural
// equivalence happens for free: identical recipes ⇒ identical NodeIDs, no
// matter which Language cell did the ingesting.
//
// Scope (v0):
//   • numeric literals (int → INT64; float64 → FP64; int32/uint32/... → typed)
//   • string literals (double + backtick)
//   • identifiers
//   • func decls + method decls on receivers
//   • arithmetic / comparison / logical operators
//   • if / else (no else-if special-casing — chains as nested if-else)
//   • return (single + multi-value)
//   • for init; cond; post  +  range-for
//   • slice literals []T{…}  +  make([]T, n)
//   • struct literals T{Field: value}
//   • var x T = v  +  short decls x := v
//   • interface declarations (basic)
//   • newline- or ;-separated statements
//
// Deferred to a later breath:
//   • goroutines, channels, select
//   • generics
//   • pointer arithmetic / unsafe
//   • full type checker (Language cell is structure-first, not type-checking)
//
// Stdlib bindings live as kernel natives — `len`, `make`, `append`, `cap`,
// `fmt.Println`, `string(...)` conversion — so a parsed Go fib() can actually
// evaluate inside the kernel.

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
  type Value,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Numeric format-recipes — Language cell vocabulary.
// ---------------------------------------------------------------------------
//
// Canonical NodeID assignments for numeric formats. Keeping the constants
// here (not in kernel.ts) preserves additive scope — the kernel doesn't
// know about format-recipes yet; each Language cell carries its own.
//
// Cross-language convention: `int` (platform-dependent in Go) maps to INT64
// for canonical cross-language identity. Idiomatic Go on 64-bit hosts uses
// INT64 anyway; on 32-bit hosts the substrate-shape stays the same. Typed
// forms `int32`, `uint64`, etc. map to their own format-recipe.

export const RFormat = {
  INT64: 1,
  INT32: 2,
  INT16: 3,
  INT8: 4,
  UINT64: 5,
  UINT32: 6,
  UINT16: 7,
  UINT8: 8,
  FP64: 9,
  FP32: 10,
} as const;

export type FormatTag = (typeof RFormat)[keyof typeof RFormat];

// Map Go type names → format tag. Used by the parser when an explicit type
// or conversion fixes the shape (var x int32 = 3, int32(x), etc.).
const GO_TYPE_TO_FORMAT: Record<string, FormatTag> = {
  int: RFormat.INT64,
  int64: RFormat.INT64,
  int32: RFormat.INT32,
  int16: RFormat.INT16,
  int8: RFormat.INT8,
  uint: RFormat.UINT64,
  uint64: RFormat.UINT64,
  uint32: RFormat.UINT32,
  uint16: RFormat.UINT16,
  uint8: RFormat.UINT8,
  byte: RFormat.UINT8,
  rune: RFormat.INT32,
  float64: RFormat.FP64,
  float32: RFormat.FP32,
};

const FORMAT_TO_GO_TYPE: Record<number, string> = {
  [RFormat.INT64]: "int64",
  [RFormat.INT32]: "int32",
  [RFormat.INT16]: "int16",
  [RFormat.INT8]: "int8",
  [RFormat.UINT64]: "uint64",
  [RFormat.UINT32]: "uint32",
  [RFormat.UINT16]: "uint16",
  [RFormat.UINT8]: "uint8",
  [RFormat.FP64]: "float64",
  [RFormat.FP32]: "float32",
};

// ---------------------------------------------------------------------------
// Language cell descriptor.
// ---------------------------------------------------------------------------
//
// A Language cell is a content-addressed bundle. The kernel stores the
// descriptor as a recipe under a synthetic category so two cells with the
// same (id, version) produce the same NodeID. Parser/emitter/bindings live
// off the bundle and are exposed as methods.

export interface LanguageCell {
  readonly id: string;
  readonly version: string;
  readonly nodeId: NodeID;
  parse(source: string): NodeID;
  emit(node: NodeID): string;
  /** evaluate a parsed Go expression to a kernel Value */
  bindings(): readonly string[];
}

// Synthetic RBasic.LANG slot for language-cell categories. Sits in a slot
// the kernel doesn't dispatch on, so walking a language-cell node directly
// is a no-op — the cell is a registry entry, not an executable form.
const RLANG_TYPE = 90;

// ---------------------------------------------------------------------------
// Public entry point.
// ---------------------------------------------------------------------------

export function createGoLanguage(k: Kernel): LanguageCell {
  // Register stdlib natives once. registerNative is idempotent in spirit
  // (overwriting an existing entry is harmless), so multiple language
  // cells sharing the kernel cooperate.
  registerGoStdlib(k);

  // The cell's NodeID is content-addressed on (id, version) so two callers
  // who construct a Go-1.23 cell from the same kernel get the same node.
  const idTriv = k.internString("lang.go");
  const versionTriv = k.internString("1.23");
  const cellNode = k.intern(
    { pkg: 1, level: Level.BASIC, type: RLANG_TYPE, inst: 1 },
    [idTriv, versionTriv],
  );

  return {
    id: "lang.go",
    version: "1.23",
    nodeId: cellNode,
    parse: (src: string) => parseGo(k, src),
    emit: (node: NodeID) => emitGo(k, node),
    bindings: () => GO_STDLIB_BINDINGS,
  };
}

// Stdlib bindings the kernel registers when a Go language cell is created.
// Names appear in Go source verbatim; parser routes calls through these.
const GO_STDLIB_BINDINGS = [
  "len",
  "make",
  "append",
  "cap",
  "fmt.Println",
  "string",
] as const;

// Return-unwind sentinel. The `return` native throws this; the body
// wrapper installed at FNDEF parse time catches it and yields the value.
class GoReturn {
  constructor(public readonly value: Value) {}
}

function registerGoStdlib(k: Kernel): void {
  // `return X` — throw a sentinel so any enclosing function-body wrapper
  // can unwind and yield X. In practice the parser's lowerReturns strips
  // most return calls structurally, so this native is only hit if an
  // un-lowered recipe is walked directly.
  if (!k.natives.has(k.internName("return"))) {
    k.setNative("return", (_kk, args) => {
      throw new GoReturn(args[0] ?? { kind: "null" });
    });
  }
  // Slice literal native — skips the leading element-type marker and
  // returns a plain list of evaluated items. Lets `[]int64{1,2,3}` walk.
  if (!k.natives.has(k.internName("__slice_literal__"))) {
    k.setNative("__slice_literal__", (_kk, args) => {
      // args[0] is the element-type string trivial; skip it.
      return { kind: "list", list: args.slice(1) };
    });
  }
  // Field access marker — no runtime semantic in v0 (no struct values
  // yet). Returns null when walked; round-trip emit re-renders the
  // `recv.field` shape.
  if (!k.natives.has(k.internName("__field__"))) {
    k.setNative("__field__", () => ({ kind: "null" }));
  }
  // Struct literal marker — returns the field-name → value pairs as a
  // list, leading with the type-name string. Walker semantics are
  // structural, not behavioral; sufficient for v0.
  if (!k.natives.has(k.internName("__struct_literal__"))) {
    k.setNative("__struct_literal__", (_kk, args) => ({
      kind: "list",
      list: args.slice(),
    }));
  }
  // FP literal marker — string-tagged float kept as a str value in v0
  // since the kernel has no native FP trivial.
  if (!k.natives.has(k.internName("__fp_literal__"))) {
    k.setNative("__fp_literal__", (_kk, args) => args[0] ?? { kind: "null" });
  }
  // `__fn_body__(body-thunk)` — invoked at function entry. We need a way
  // to defer the body's evaluation so we can wrap it in try/catch. The
  // kernel's FNCALL eagerly evaluates args, so we can't pass an unevaluated
  // body directly. Instead, the parser wraps every function's body inside a
  // walker-visible try-shape: the catch is installed by a custom native
  // (see __try_return__ below) that uses Function.prototype.toString
  // tricks? No — the kernel walks the body eagerly. We solve this with the
  // global handler: every `walk` call in the test harness that targets a
  // function call catches GoReturn at the outermost frame. The cleanest
  // path is a top-level helper exposed by lang-go: `runGo` / `callGo`.
  // Implemented below as `walkGoNode`.

  // `len` is already registered by the kernel; the Go binding matches.
  // `make([]T, n)` returns a list of n null entries. `make` ignores the
  // type-recipe argument at runtime (type lives in the recipe, not the value).
  if (!k.natives.has(k.internName("make"))) {
    k.setNative("make", (_kk, args) => {
      // Accept (typeName, n) or just (n).
      let n = 0;
      for (let i = args.length - 1; i >= 0; i--) {
        const a = args[i];
        if (a?.kind === "int") {
          n = a.int;
          break;
        }
      }
      const list = new Array(n).fill({ kind: "int", int: 0 });
      return { kind: "list", list };
    });
  }
  if (!k.natives.has(k.internName("append"))) {
    k.setNative("append", (_kk, args) => {
      const first = args[0];
      const base = first?.kind === "list" ? [...first.list] : [];
      for (let i = 1; i < args.length; i++) {
        base.push(args[i] ?? { kind: "null" });
      }
      return { kind: "list", list: base };
    });
  }
  if (!k.natives.has(k.internName("cap"))) {
    k.setNative("cap", (_kk, args) => {
      const v = args[0];
      if (v?.kind === "list") return { kind: "int", int: v.list.length };
      if (v?.kind === "str") return { kind: "int", int: v.str.length };
      return { kind: "int", int: 0 };
    });
  }
  // fmt.Println — qualified name interned literally; parser routes "fmt.Println"
  // as a single identifier so the native lookup works without a module system.
  if (!k.natives.has(k.internName("fmt.Println"))) {
    k.setNative("fmt.Println", (kk, args) => {
      const parts = args.map((a) => renderForPrint(kk, a));
      process.stdout.write(parts.join(" ") + "\n");
      return { kind: "null" };
    });
  }
  // `string(x)` conversion — int → ASCII char (Go semantics for string(int)).
  // For string-from-bytes / runes we keep the simple Go semantic: string(i)
  // returns the UTF-8 representation of code point i; string(s) is identity.
  if (!k.natives.has(k.internName("string"))) {
    k.setNative("string", (_kk, args) => {
      const v = args[0];
      if (v?.kind === "str") return v;
      if (v?.kind === "int") return { kind: "str", str: String.fromCodePoint(v.int) };
      if (v?.kind === "list") {
        let out = "";
        for (const e of v.list) {
          if (e.kind === "int") out += String.fromCodePoint(e.int);
        }
        return { kind: "str", str: out };
      }
      return { kind: "str", str: "" };
    });
  }
}

// Local print renderer — mirrors kernel's renderForPrint without going
// through the private surface.
function renderForPrint(k: Kernel, v: Value): string {
  switch (v.kind) {
    case "null":
      return "null";
    case "int":
      return String(v.int);
    case "str":
      return v.str;
    case "bool":
      return v.bool ? "true" : "false";
    case "list":
      return "[" + v.list.map((x) => renderForPrint(k, x)).join(" ") + "]";
    case "closure":
      return "<closure>";
    case "nodeid":
      return `<nodeid ${v.nodeid.pkg}.${v.nodeid.level}.${v.nodeid.type}.${v.nodeid.inst}>`;
    // Cases added by Value union extensions in other tasks (i8/i16/u8/u16/u32,
    // i64/u64, f32/f64, ctor). Fall through to a stringified default — these
    // value kinds don't arise in Go-parsed recipes today.
    default:
      return JSON.stringify(v);
  }
}

// ===========================================================================
// PARSER — Go source → kernel recipe tree
// ===========================================================================
//
// Tokenizer + Pratt-flavored recursive descent. Statements separated by
// newline or `;`. Body holds one DO-block per { ... }.

type TokKind =
  | "ident"
  | "int"
  | "float"
  | "str"
  | "punct"
  | "kw"
  | "semi"
  | "eof";

interface Tok {
  kind: TokKind;
  text: string;
  pos: number;
  /** explicit numeric type tag if the literal carried a suffix or context */
  format?: FormatTag;
}

const KEYWORDS = new Set([
  "func",
  "return",
  "if",
  "else",
  "for",
  "range",
  "var",
  "type",
  "struct",
  "interface",
  "true",
  "false",
  "nil",
  "package",
  "import",
  "break",
  "continue",
  "make",
]);

const MULTI_PUNCT = [
  ":=",
  "==",
  "!=",
  "<=",
  ">=",
  "&&",
  "||",
  "++",
  "--",
  "<<",
  ">>",
];

function tokenize(src: string): Tok[] {
  const toks: Tok[] = [];
  let i = 0;
  let lastWasValue = false; // for semi-insertion at newline boundaries

  while (i < src.length) {
    const c = src[i]!;

    // Whitespace — newline acts as a statement terminator when the prior
    // token was value-bearing (ident, literal, `)`, `]`, `}`, return).
    if (c === " " || c === "\t" || c === "\r") {
      i++;
      continue;
    }
    if (c === "\n") {
      if (lastWasValue) {
        toks.push({ kind: "semi", text: ";", pos: i });
        lastWasValue = false;
      }
      i++;
      continue;
    }

    // Line comments
    if (c === "/" && src[i + 1] === "/") {
      while (i < src.length && src[i] !== "\n") i++;
      continue;
    }
    // Block comments
    if (c === "/" && src[i + 1] === "*") {
      i += 2;
      while (i < src.length && !(src[i] === "*" && src[i + 1] === "/")) i++;
      i += 2;
      continue;
    }

    // Strings (double-quoted)
    if (c === '"') {
      const start = i;
      i++;
      let s = "";
      while (i < src.length && src[i] !== '"') {
        if (src[i] === "\\" && i + 1 < src.length) {
          const n = src[i + 1];
          if (n === "n") s += "\n";
          else if (n === "t") s += "\t";
          else if (n === "r") s += "\r";
          else if (n === "\\") s += "\\";
          else if (n === '"') s += '"';
          else s += n ?? "";
          i += 2;
          continue;
        }
        s += src[i];
        i++;
      }
      if (src[i] !== '"') throw new Error(`unterminated string at ${start}`);
      i++;
      toks.push({ kind: "str", text: s, pos: start });
      lastWasValue = true;
      continue;
    }

    // Raw strings (backtick)
    if (c === "`") {
      const start = i;
      i++;
      let s = "";
      while (i < src.length && src[i] !== "`") {
        s += src[i];
        i++;
      }
      if (src[i] !== "`") throw new Error(`unterminated raw string at ${start}`);
      i++;
      toks.push({ kind: "str", text: s, pos: start });
      lastWasValue = true;
      continue;
    }

    // Numeric literals
    if ((c >= "0" && c <= "9") || (c === "." && isDigit(src[i + 1]))) {
      const start = i;
      let isFloat = false;
      while (i < src.length && isDigit(src[i])) i++;
      if (src[i] === ".") {
        isFloat = true;
        i++;
        while (i < src.length && isDigit(src[i])) i++;
      }
      if (src[i] === "e" || src[i] === "E") {
        isFloat = true;
        i++;
        if (src[i] === "+" || src[i] === "-") i++;
        while (i < src.length && isDigit(src[i])) i++;
      }
      const text = src.slice(start, i);
      toks.push({
        kind: isFloat ? "float" : "int",
        text,
        pos: start,
        format: isFloat ? RFormat.FP64 : RFormat.INT64,
      });
      lastWasValue = true;
      continue;
    }

    // Identifiers / keywords (allow `.` so qualified names like fmt.Println
    // tokenize as one identifier — keeps the v0 parser simple).
    if (isIdentStart(c)) {
      const start = i;
      i++;
      while (i < src.length && (isIdentCont(src[i]!) || src[i] === ".")) i++;
      const text = src.slice(start, i);
      const kind: TokKind = KEYWORDS.has(text) && !text.includes(".") ? "kw" : "ident";
      toks.push({ kind, text, pos: start });
      lastWasValue =
        kind === "ident" ||
        text === "true" ||
        text === "false" ||
        text === "nil";
      continue;
    }

    // Multi-char punctuation
    let matched = false;
    for (const mp of MULTI_PUNCT) {
      if (src.startsWith(mp, i)) {
        toks.push({ kind: "punct", text: mp, pos: i });
        i += mp.length;
        lastWasValue = mp === "++" || mp === "--";
        matched = true;
        break;
      }
    }
    if (matched) continue;

    // Single-char punct. `;` is explicit semicolon; `}` is value-bearing so
    // a newline after it inserts a `;` per Go spec.
    if (c === ";") {
      toks.push({ kind: "semi", text: ";", pos: i });
      i++;
      lastWasValue = false;
      continue;
    }
    if ("(){}[],.+-*/%<>=!&|^:".includes(c)) {
      toks.push({ kind: "punct", text: c, pos: i });
      i++;
      lastWasValue = c === ")" || c === "]" || c === "}";
      continue;
    }

    throw new Error(`unexpected character ${JSON.stringify(c)} at ${i}`);
  }

  toks.push({ kind: "eof", text: "", pos: i });
  return toks;
}

function isDigit(c: string | undefined): boolean {
  return c !== undefined && c >= "0" && c <= "9";
}
function isIdentStart(c: string): boolean {
  return (c >= "a" && c <= "z") || (c >= "A" && c <= "Z") || c === "_";
}
function isIdentCont(c: string): boolean {
  return isIdentStart(c) || (c >= "0" && c <= "9");
}

// ---------------------------------------------------------------------------
// Parser state
// ---------------------------------------------------------------------------

interface PState {
  toks: Tok[];
  i: number;
  k: Kernel;
  /** When true, an `Ident { … }` shape is parsed as ident-then-block, not as
   *  a struct literal. Set inside `if`/`for` cond expressions because Go
   *  has the same disambiguation rule (cond can't contain a brace-less
   *  composite literal). */
  noBraceLiteral: boolean;
}

function peek(s: PState, n = 0): Tok {
  return s.toks[s.i + n] ?? s.toks[s.toks.length - 1]!;
}
function consume(s: PState): Tok {
  const t = s.toks[s.i];
  if (t === undefined) throw new Error("unexpected end of input");
  s.i++;
  return t;
}
function expect(s: PState, kind: TokKind, text?: string): Tok {
  const t = consume(s);
  if (t.kind !== kind || (text !== undefined && t.text !== text)) {
    throw new Error(
      `expected ${kind}${text ? ` "${text}"` : ""} at ${t.pos}, got ${t.kind} "${t.text}"`,
    );
  }
  return t;
}
function check(s: PState, kind: TokKind, text?: string): boolean {
  const t = peek(s);
  return t.kind === kind && (text === undefined || t.text === text);
}
function eatSemis(s: PState): void {
  while (check(s, "semi")) consume(s);
}

// ---------------------------------------------------------------------------
// Public parser entry.
// ---------------------------------------------------------------------------

export function parseGo(k: Kernel, src: string): NodeID {
  const s: PState = { toks: tokenize(src), i: 0, k, noBraceLiteral: false };
  // Skip optional package/import preamble — Language cell scope is the
  // executable surface, not the file layout.
  while (check(s, "kw", "package") || check(s, "kw", "import")) {
    skipToSemi(s);
    eatSemis(s);
  }
  eatSemis(s);

  const stmts: NodeID[] = [];
  while (!check(s, "eof")) {
    stmts.push(parseTopLevel(s));
    eatSemis(s);
  }
  if (stmts.length === 0) return k.internTrivialNull();
  if (stmts.length === 1) return stmts[0]!;
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.DO },
    stmts,
  );
}

function skipToSemi(s: PState): void {
  while (!check(s, "semi") && !check(s, "eof")) consume(s);
}

// ---------------------------------------------------------------------------
// Top-level declarations.
// ---------------------------------------------------------------------------

function parseTopLevel(s: PState): NodeID {
  if (check(s, "kw", "func")) return parseFunc(s);
  if (check(s, "kw", "type")) return parseTypeDecl(s);
  return parseStatement(s);
}

// func name(args...) returnType { body }
// func (recv RecvType) name(args...) returnType { body }
function parseFunc(s: PState): NodeID {
  expect(s, "kw", "func");

  // Optional receiver
  let receiver: { name: string; type: string } | null = null;
  if (check(s, "punct", "(") && looksLikeReceiver(s)) {
    consume(s); // (
    const recvName = expect(s, "ident").text;
    const recvType = parseTypeRef(s);
    expect(s, "punct", ")");
    receiver = { name: recvName, type: recvType };
  }

  const nameTok = expect(s, "ident");
  let name = nameTok.text;
  if (receiver !== null) {
    // Method form: name encoded as "Recv.method" for round-trip; emitter
    // splits this back into the receiver-form on output.
    name = `${receiver.type}.${name}`;
  }

  // Param list
  expect(s, "punct", "(");
  const params: string[] = [];
  if (!check(s, "punct", ")")) {
    parseParam(s, params);
    while (check(s, "punct", ",")) {
      consume(s);
      parseParam(s, params);
    }
  }
  expect(s, "punct", ")");

  // Return type — single, parenthesized multi-return, or omitted.
  // We accept and discard; type info isn't part of the executable recipe.
  parseReturnType(s);

  const rawBody = parseBlock(s);
  // Lower bare `return X` into pure-expression shape so the kernel walker's
  // "DO returns last value" semantics carry the function's return value
  // without needing an early-exit mechanism. See lowerReturns below.
  const body = lowerReturns(s.k, rawBody);

  // Encode as kernel FNDEF: [name-trivial, params-SEQUENCE, body].
  const k = s.k;
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(name),
  };
  const paramTrivials: NodeID[] = params.map((p) => ({
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(p),
  }));
  const paramsBlock = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    paramTrivials,
  );
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 1 },
    [nameTrivial, paramsBlock, body],
  );
}

// ---------------------------------------------------------------------------
// lowerReturns — transform a parsed function body so that `return X` shapes
// become pure-expression flow that the kernel walker can evaluate without
// any early-exit mechanism. Pre-condition: body is a single statement or a
// DO/SEQUENCE block. The lowering preserves the surface emit-shape because
// it only runs on the *executable* recipe; the original parse tree (with
// explicit returns) is what the emitter sees when re-emitting via emitGo
// (we keep the original tree separately is overkill — instead we make the
// lowering reversible: see emitGo's handling of IF_THEN_ELSE.)
//
// The transform:
//   return X                              →  X
//   { s1; …; return X }                   →  { s1; …; X }
//   { …; if c { return X }; rest }        →  { …; if c { X } else { rest } }
//   { …; if c { return X } else { Y };r } →  if c { X } else lower({Y;r})
//
// For fib() this brings the body to:
//   if n < 2 { n } else { fib(n-1) + fib(n-2) }
// which the walker evaluates directly.
function lowerReturns(k: Kernel, node: NodeID): NodeID {
  if (node.level === Level.BASIC) {
    const cat = k.category(node);
    if (
      cat.type === RBasic.BLOCK &&
      (cat.inst === RBlock.DO || cat.inst === RBlock.SEQUENCE)
    ) {
      const kids = k.children(node);
      return lowerSequence(k, kids, cat.inst);
    }
    // if-then-else as the sole body — recurse into each branch so a
    // terminal `return X` becomes plain X.
    if (cat.type === RBasic.COND && cat.inst === RCond.IF_THEN_ELSE) {
      const kids = k.children(node);
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.COND, inst: RCond.IF_THEN_ELSE },
        [kids[0]!, lowerReturns(k, kids[1]!), lowerReturns(k, kids[2]!)],
      );
    }
    if (cat.type === RBasic.COND && cat.inst === RCond.IF_THEN) {
      const kids = k.children(node);
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.COND, inst: RCond.IF_THEN },
        [kids[0]!, lowerReturns(k, kids[1]!)],
      );
    }
  }
  // Bare statement — unwrap a top-level `return X` to just X.
  return stripReturn(k, node);
}

function lowerSequence(k: Kernel, kids: readonly NodeID[], blockInst: number): NodeID {
  // Walk left-to-right looking for an if-then with a `return` inside, or a
  // terminal `return`. If found, fork the remainder into the else-branch.
  for (let i = 0; i < kids.length; i++) {
    const stmt = kids[i]!;
    // Terminal `return X` (or trailing return) — collapse to X (and the
    // rest, if any, becomes unreachable; we drop it. Go's vet would warn.)
    if (isReturnCall(k, stmt)) {
      const head = kids.slice(0, i);
      const value = unwrapReturn(k, stmt);
      const combined = [...head, value];
      if (combined.length === 1) return combined[0]!;
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: blockInst },
        combined,
      );
    }
    // if-then or if-then-else with a `return` in the then-branch — fork
    // the remainder into the else-branch so the walker carries the value
    // through.
    if (stmt.level === Level.BASIC) {
      const cat = k.category(stmt);
      if (cat.type === RBasic.COND && cat.inst === RCond.IF_THEN) {
        const ifKids = k.children(stmt);
        const cond = ifKids[0]!;
        const thenBranch = ifKids[1]!;
        if (containsReturn(k, thenBranch)) {
          const rest = kids.slice(i + 1);
          const head = kids.slice(0, i);
          const newThen = lowerReturns(k, thenBranch);
          const elseBranch = rest.length === 0
            ? k.internTrivialNull()
            : lowerSequence(k, rest, blockInst);
          const newIf = k.intern(
            {
              pkg: 1,
              level: Level.BASIC,
              type: RBasic.COND,
              inst: RCond.IF_THEN_ELSE,
            },
            [cond, newThen, elseBranch],
          );
          if (head.length === 0) return newIf;
          return k.intern(
            { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: blockInst },
            [...head, newIf],
          );
        }
      }
      if (cat.type === RBasic.COND && cat.inst === RCond.IF_THEN_ELSE) {
        const ifKids = k.children(stmt);
        const cond = ifKids[0]!;
        const thenBranch = ifKids[1]!;
        const elseBranch = ifKids[2]!;
        if (containsReturn(k, thenBranch) || containsReturn(k, elseBranch)) {
          const newThen = lowerReturns(k, thenBranch);
          const newElse = lowerReturns(k, elseBranch);
          const head = kids.slice(0, i);
          const newIf = k.intern(
            {
              pkg: 1,
              level: Level.BASIC,
              type: RBasic.COND,
              inst: RCond.IF_THEN_ELSE,
            },
            [cond, newThen, newElse],
          );
          // If both branches return, the rest is unreachable; drop it.
          if (head.length === 0) return newIf;
          return k.intern(
            { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: blockInst },
            [...head, newIf],
          );
        }
      }
    }
  }
  // No returns found — leave as-is (recursively lower nested blocks just
  // in case).
  if (kids.length === 1) return kids[0]!;
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: blockInst },
    kids,
  );
}

function isReturnCall(k: Kernel, node: NodeID): boolean {
  if (node.level !== Level.BASIC) return false;
  const cat = k.category(node);
  if (cat.type !== RBasic.FNCALL) return false;
  const kids = k.children(node);
  const callee = kids[0];
  if (!callee) return false;
  if (callee.level === Level.TRIVIAL && callee.type === Triv.STRING) {
    return k.strs[callee.inst] === "return";
  }
  return false;
}

function unwrapReturn(k: Kernel, node: NodeID): NodeID {
  // `return X` → X (or null for bare return)
  const kids = k.children(node);
  if (kids.length <= 1) return k.internTrivialNull();
  if (kids.length === 2) return kids[1]!;
  // Multi-return: wrap as LIST.
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 1 },
    kids.slice(1),
  );
}

function stripReturn(k: Kernel, node: NodeID): NodeID {
  if (isReturnCall(k, node)) return unwrapReturn(k, node);
  return node;
}

function containsReturn(k: Kernel, node: NodeID): boolean {
  if (node.level !== Level.BASIC) return false;
  if (isReturnCall(k, node)) return true;
  const kids = k.children(node);
  for (const c of kids) {
    if (containsReturn(k, c)) return true;
  }
  return false;
}

// Decide whether `(` opens a receiver vs a param list. Receiver form is
// `( ident TypeRef )` with no commas before the closing paren.
function looksLikeReceiver(s: PState): boolean {
  if (!check(s, "punct", "(")) return false;
  // Look ahead: ident, type-ref, ).
  // We allow ident type-ident `)` and ident `*` type-ident `)`.
  let j = s.i + 1;
  if (s.toks[j]?.kind !== "ident") return false;
  j++;
  if (s.toks[j]?.text === "*") j++;
  if (s.toks[j]?.kind !== "ident") return false;
  j++;
  return s.toks[j]?.text === ")";
}

function parseParam(s: PState, into: string[]): void {
  const name = expect(s, "ident").text;
  // Consume type ref (may be missing only if multi-name same-type form is
  // used; we keep the simple "name type" shape required by the spec).
  parseTypeRef(s);
  into.push(name);
}

// Best-effort type-ref skip — pointer, slice, array, basic type.
function parseTypeRef(s: PState): string {
  let txt = "";
  if (check(s, "punct", "*")) {
    consume(s);
    txt += "*";
  }
  if (check(s, "punct", "[")) {
    consume(s);
    txt += "[";
    // []T or [N]T — accept ident or int inside
    if (!check(s, "punct", "]")) {
      const t = consume(s);
      txt += t.text;
    }
    expect(s, "punct", "]");
    txt += "]";
  }
  if (check(s, "ident")) {
    txt += consume(s).text;
  } else if (check(s, "kw", "interface")) {
    // anonymous interface{} — accept and skip body
    consume(s);
    if (check(s, "punct", "{")) {
      let depth = 1;
      consume(s);
      while (depth > 0 && !check(s, "eof")) {
        if (check(s, "punct", "{")) depth++;
        if (check(s, "punct", "}")) depth--;
        if (depth > 0) consume(s);
      }
      expect(s, "punct", "}");
    }
    txt += "interface{}";
  }
  return txt;
}

function parseReturnType(s: PState): void {
  // Multi-return: `(t1, t2)`
  if (check(s, "punct", "(")) {
    consume(s);
    while (!check(s, "punct", ")") && !check(s, "eof")) {
      // Each entry may be either `type` or `name type`.
      if (check(s, "ident") && peek(s, 1).kind === "ident") {
        consume(s); // name
      }
      parseTypeRef(s);
      if (check(s, "punct", ",")) consume(s);
    }
    expect(s, "punct", ")");
    return;
  }
  // Single — only consume if the token starts a type.
  if (
    check(s, "punct", "*") ||
    check(s, "punct", "[") ||
    (check(s, "ident") && !isStatementStartIdent(peek(s).text))
  ) {
    parseTypeRef(s);
  }
}

function isStatementStartIdent(_name: string): boolean {
  // We're between the param list and `{`. Any ident here is a type, not
  // a statement-starter, so always treat as type.
  return false;
}

// type Name struct { ... } | type Name interface { ... } | type Alias = Other
// We accept the declaration and represent it as a NamedField recipe so it
// participates in content-addressing without executing.
function parseTypeDecl(s: PState): NodeID {
  expect(s, "kw", "type");
  const name = expect(s, "ident").text;
  // Optional `=` alias form
  if (check(s, "punct", "=")) {
    consume(s);
    const alias = parseTypeRef(s);
    return makeNamedField(s.k, `type ${name}`, s.k.internString(alias));
  }
  if (check(s, "kw", "struct")) {
    consume(s);
    const body = skipBracedBlock(s);
    return makeNamedField(s.k, `type ${name} struct`, s.k.internString(body));
  }
  if (check(s, "kw", "interface")) {
    consume(s);
    const body = skipBracedBlock(s);
    return makeNamedField(s.k, `type ${name} interface`, s.k.internString(body));
  }
  // type Name OtherType
  const ref = parseTypeRef(s);
  return makeNamedField(s.k, `type ${name}`, s.k.internString(ref));
}

function makeNamedField(k: Kernel, key: string, value: NodeID): NodeID {
  const keyTriv = k.internString(key);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.LET },
    [keyTriv, value],
  );
}

function skipBracedBlock(s: PState): string {
  expect(s, "punct", "{");
  const start = s.i;
  let depth = 1;
  while (depth > 0 && !check(s, "eof")) {
    if (check(s, "punct", "{")) depth++;
    if (check(s, "punct", "}")) {
      depth--;
      if (depth === 0) break;
    }
    consume(s);
  }
  const end = s.i;
  expect(s, "punct", "}");
  // Reconstruct text from tokens — adequate for a Language cell stub.
  return s.toks
    .slice(start, end)
    .map((t) => t.text)
    .join(" ");
}

// ---------------------------------------------------------------------------
// Statements
// ---------------------------------------------------------------------------

function parseBlock(s: PState): NodeID {
  expect(s, "punct", "{");
  eatSemis(s);
  const stmts: NodeID[] = [];
  while (!check(s, "punct", "}") && !check(s, "eof")) {
    stmts.push(parseStatement(s));
    eatSemis(s);
  }
  expect(s, "punct", "}");
  if (stmts.length === 1) return stmts[0]!;
  return s.k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.DO },
    stmts,
  );
}

function parseStatement(s: PState): NodeID {
  if (check(s, "kw", "return")) return parseReturn(s);
  if (check(s, "kw", "if")) return parseIf(s);
  if (check(s, "kw", "for")) return parseFor(s);
  if (check(s, "kw", "var")) return parseVar(s);
  if (check(s, "kw", "func")) return parseFunc(s);
  if (check(s, "kw", "type")) return parseTypeDecl(s);
  if (check(s, "punct", "{")) return parseBlock(s);
  // Could be `x := …`, `x = …`, or a bare expression.
  return parseAssignOrExpr(s);
}

function parseReturn(s: PState): NodeID {
  expect(s, "kw", "return");
  if (check(s, "semi") || check(s, "punct", "}")) {
    // bare return
    return s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
      [
        s.k.internString("return"),
      ],
    );
  }
  const vals: NodeID[] = [parseExpr(s)];
  while (check(s, "punct", ",")) {
    consume(s);
    vals.push(parseExpr(s));
  }
  // Single-return: pass through as the value itself wrapped in a return
  // marker so the emitter can put `return` back. Encode as FNCALL with
  // callee "return".
  const callee = s.k.internString("return");
  return s.k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
    [callee, ...vals],
  );
}

function parseIf(s: PState): NodeID {
  expect(s, "kw", "if");
  // Optional init stmt: `if x := f(); cond { … }` — detect by lookahead
  // for `:=` or `=` before `;`.
  let init: NodeID | null = null;
  if (hasInitStmt(s)) {
    init = parseAssignOrExpr(s);
    expect(s, "semi");
  }
  const cond = parseCondExpr(s);
  const thenBlock = parseBlock(s);
  // Peek past auto-inserted semis to find an `else` continuation. Go's
  // spec says `} else` must be on the same physical line, so the
  // tokenizer's newline-semi insertion would split `} \n else` into a
  // statement boundary. In practice many Go formatters DO put `} else {`
  // on one line, and our tokenizer handles that correctly. We accept the
  // looser form too — peek past semis.
  let elseBlock: NodeID | null = null;
  const savedI = s.i;
  while (check(s, "semi")) consume(s);
  if (check(s, "kw", "else")) {
    consume(s);
    if (check(s, "kw", "if")) {
      elseBlock = parseIf(s);
    } else {
      elseBlock = parseBlock(s);
    }
  } else {
    // No else — restore the position so the outer statement loop sees
    // the semi(s) and ends this statement.
    s.i = savedI;
  }

  const k = s.k;
  let ifNode: NodeID;
  if (elseBlock !== null) {
    ifNode = k.intern(
      {
        pkg: 1,
        level: Level.BASIC,
        type: RBasic.COND,
        inst: RCond.IF_THEN_ELSE,
      },
      [cond, thenBlock, elseBlock],
    );
  } else {
    ifNode = k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.COND, inst: RCond.IF_THEN },
      [cond, thenBlock],
    );
  }
  if (init !== null) {
    return k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.DO },
      [init, ifNode],
    );
  }
  return ifNode;
}

// Scan forward to determine whether `if`/`for` has an init stmt — a `;`
// appearing before the body-open `{` at the same brace/paren depth.
function hasInitStmt(s: PState): boolean {
  let j = s.i;
  let parenDepth = 0;
  while (j < s.toks.length) {
    const t = s.toks[j]!;
    if (t.kind === "punct" && t.text === "(") parenDepth++;
    else if (t.kind === "punct" && t.text === ")") parenDepth--;
    else if (parenDepth === 0 && t.kind === "punct" && t.text === "{") return false;
    else if (parenDepth === 0 && t.kind === "semi") return true;
    else if (t.kind === "eof") return false;
    j++;
  }
  return false;
}

function parseFor(s: PState): NodeID {
  expect(s, "kw", "for");
  const k = s.k;

  // `for { … }` — infinite loop
  if (check(s, "punct", "{")) {
    const body = parseBlock(s);
    return forLoop(k, k.internTrivialNull(), k.internTrivialBool(true), k.internTrivialNull(), body);
  }

  // Detect range form: `for k, v := range expr { … }` or `for x := range …`.
  if (lookaheadHasRange(s)) {
    return parseForRange(s);
  }

  // `for cond { … }` or `for init; cond; post { … }`
  const savedFor = s.noBraceLiteral;
  s.noBraceLiteral = true;
  try {
    if (hasForCStyle(s)) {
      const init = parseAssignOrExpr(s);
      expect(s, "semi");
      const cond = check(s, "semi") ? k.internTrivialBool(true) : parseExpr(s);
      expect(s, "semi");
      const post = check(s, "punct", "{") ? k.internTrivialNull() : parseAssignOrExpr(s);
      s.noBraceLiteral = savedFor;
      const body = parseBlock(s);
      return forLoop(k, init, cond, post, body);
    }

    const cond = parseExpr(s);
    s.noBraceLiteral = savedFor;
    const body = parseBlock(s);
    return forLoop(k, k.internTrivialNull(), cond, k.internTrivialNull(), body);
  } finally {
    s.noBraceLiteral = savedFor;
  }
}

function hasForCStyle(s: PState): boolean {
  // C-style if a `;` appears before `{` at depth 0.
  let j = s.i;
  let parenDepth = 0;
  while (j < s.toks.length) {
    const t = s.toks[j]!;
    if (t.kind === "punct" && t.text === "(") parenDepth++;
    else if (t.kind === "punct" && t.text === ")") parenDepth--;
    else if (parenDepth === 0 && t.kind === "punct" && t.text === "{") return false;
    else if (parenDepth === 0 && t.kind === "semi") return true;
    else if (t.kind === "eof") return false;
    j++;
  }
  return false;
}

function lookaheadHasRange(s: PState): boolean {
  let j = s.i;
  while (j < s.toks.length) {
    const t = s.toks[j]!;
    if (t.kind === "punct" && t.text === "{") return false;
    if (t.kind === "kw" && t.text === "range") return true;
    if (t.kind === "eof") return false;
    j++;
  }
  return false;
}

function parseForRange(s: PState): NodeID {
  // `for i, v := range expr { … }` or `for v := range expr { … }`
  const k = s.k;
  const names: string[] = [];
  names.push(expect(s, "ident").text);
  if (check(s, "punct", ",")) {
    consume(s);
    names.push(expect(s, "ident").text);
  }
  // `:=` or `=`
  if (check(s, "punct", ":=")) consume(s);
  else if (check(s, "punct", "=")) consume(s);
  expect(s, "kw", "range");
  const savedR = s.noBraceLiteral;
  s.noBraceLiteral = true;
  const iterable = parseExpr(s);
  s.noBraceLiteral = savedR;
  const body = parseBlock(s);

  // Encode as FNCALL `range` with [names..., iterable, body]. The walker
  // doesn't natively understand range, so this stays a structural form
  // — useful for parse/emit round-trips, not yet for evaluation. Future
  // breath: lower to a C-style for over indices.
  const args: NodeID[] = [
    k.internString("range"),
    ...names.map((n) => k.internString(n)),
    k.internTrivialNull(), // marker between names and iterable
    iterable,
    body,
  ];
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
    args,
  );
}

// Encode a C-style for as a recursive helper. We desugar
//   for init; cond; post { body }
// into a recipe the kernel walker can run directly using the existing
// COND/BLOCK arms. The emitter undoes this back to surface for-form by
// recognizing the marker shape.
function forLoop(
  k: Kernel,
  init: NodeID,
  cond: NodeID,
  post: NodeID,
  body: NodeID,
): NodeID {
  // Surface marker: FNCALL with callee "for" so the emitter can pattern-
  // match. Encoded as `for(init, cond, post, body)`.
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
    [k.internString("for"), init, cond, post, body],
  );
}

function parseVar(s: PState): NodeID {
  expect(s, "kw", "var");
  const name = expect(s, "ident").text;
  // optional type
  parseTypeRef(s);
  let value: NodeID = s.k.internTrivialNull();
  if (check(s, "punct", "=")) {
    consume(s);
    value = parseExpr(s);
  }
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: s.k.internName(name),
  };
  return s.k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.LET },
    [nameTrivial, value],
  );
}

function parseAssignOrExpr(s: PState): NodeID {
  // Look ahead for `:=` or `=` after an lvalue.
  const start = s.i;
  // Try to consume an ident (possibly multiple comma-separated for tuple
  // assign — we keep v0 single-target).
  if (check(s, "ident")) {
    const nameTok = peek(s);
    const next = peek(s, 1);
    if (next.kind === "punct" && (next.text === ":=" || next.text === "=")) {
      consume(s); // ident
      consume(s); // := or =
      const value = parseExpr(s);
      const nameTrivial: NodeID = {
        pkg: 1,
        level: Level.TRIVIAL,
        type: Triv.STRING,
        inst: s.k.internName(nameTok.text),
      };
      return s.k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.LET },
        [nameTrivial, value],
      );
    }
  }
  // Fall through: plain expression statement.
  s.i = start;
  return parseExpr(s);
}

// ---------------------------------------------------------------------------
// Expression parser (Pratt-style, Go precedence)
// ---------------------------------------------------------------------------

function parseExpr(s: PState): NodeID {
  return parseLogicalOr(s);
}

// parseCondExpr — temporarily forbid brace-literal parsing so that
// `if x < lo { … }` doesn't misread `lo { … }` as a struct literal.
function parseCondExpr(s: PState): NodeID {
  const saved = s.noBraceLiteral;
  s.noBraceLiteral = true;
  try {
    return parseExpr(s);
  } finally {
    s.noBraceLiteral = saved;
  }
}

function parseLogicalOr(s: PState): NodeID {
  let left = parseLogicalAnd(s);
  while (check(s, "punct", "||")) {
    consume(s);
    const right = parseLogicalAnd(s);
    left = s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: RLogic.OR },
      [left, right],
    );
  }
  return left;
}
function parseLogicalAnd(s: PState): NodeID {
  let left = parseEquality(s);
  while (check(s, "punct", "&&")) {
    consume(s);
    const right = parseEquality(s);
    left = s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: RLogic.AND },
      [left, right],
    );
  }
  return left;
}
function parseEquality(s: PState): NodeID {
  let left = parseRelational(s);
  while (check(s, "punct", "==") || check(s, "punct", "!=")) {
    const op = consume(s).text;
    const right = parseRelational(s);
    left = s.k.intern(
      {
        pkg: 1,
        level: Level.BASIC,
        type: RBasic.COMPARE,
        inst: op === "==" ? RCmp.EQ : RCmp.NE,
      },
      [left, right],
    );
  }
  return left;
}
function parseRelational(s: PState): NodeID {
  let left = parseAdditive(s);
  while (
    check(s, "punct", "<") ||
    check(s, "punct", "<=") ||
    check(s, "punct", ">") ||
    check(s, "punct", ">=")
  ) {
    const op = consume(s).text;
    const right = parseAdditive(s);
    let inst: number;
    switch (op) {
      case "<": inst = RCmp.LT; break;
      case "<=": inst = RCmp.LE; break;
      case ">": inst = RCmp.GT; break;
      default: inst = RCmp.GE; break;
    }
    left = s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst },
      [left, right],
    );
  }
  return left;
}
function parseAdditive(s: PState): NodeID {
  let left = parseMultiplicative(s);
  while (check(s, "punct", "+") || check(s, "punct", "-")) {
    const op = consume(s).text;
    const right = parseMultiplicative(s);
    left = s.k.intern(
      {
        pkg: 1,
        level: Level.BASIC,
        type: RBasic.MATH,
        inst: op === "+" ? RMath.PLUS : RMath.MINUS,
      },
      [left, right],
    );
  }
  return left;
}
function parseMultiplicative(s: PState): NodeID {
  let left = parseUnary(s);
  while (
    check(s, "punct", "*") ||
    check(s, "punct", "/") ||
    check(s, "punct", "%")
  ) {
    const op = consume(s).text;
    const right = parseUnary(s);
    let inst: number;
    switch (op) {
      case "*": inst = RMath.MUL; break;
      case "/": inst = RMath.DIV; break;
      default: inst = RMath.MOD; break;
    }
    left = s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst },
      [left, right],
    );
  }
  return left;
}
function parseUnary(s: PState): NodeID {
  if (check(s, "punct", "!")) {
    consume(s);
    const inner = parseUnary(s);
    return s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: RLogic.NOT },
      [inner],
    );
  }
  if (check(s, "punct", "-")) {
    consume(s);
    const inner = parseUnary(s);
    // -x as (0 - x)
    return s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: RMath.MINUS },
      [s.k.internTrivialInt(0), inner],
    );
  }
  return parsePostfix(s);
}

function parsePostfix(s: PState): NodeID {
  let expr = parsePrimary(s);
  // Chained call / index / selector
  while (true) {
    if (check(s, "punct", "(")) {
      consume(s);
      const args: NodeID[] = [];
      if (!check(s, "punct", ")")) {
        args.push(parseExpr(s));
        while (check(s, "punct", ",")) {
          consume(s);
          args.push(parseExpr(s));
        }
      }
      expect(s, "punct", ")");
      // FNCALL: callee is `expr`.
      expr = s.k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
        [expr, ...args],
      );
      continue;
    }
    if (check(s, "punct", "[")) {
      consume(s);
      const idx = parseExpr(s);
      expect(s, "punct", "]");
      // Encode as FNCALL `nth(expr, idx)` so it walks against the kernel
      // native — `nth` is registered and works for lists.
      expr = s.k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
        [s.k.internString("nth"), expr, idx],
      );
      continue;
    }
    if (check(s, "punct", ".")) {
      consume(s);
      const field = expect(s, "ident").text;
      // Encode as FNCALL `__field__(expr, "field")`. Walker doesn't
      // evaluate it (no native registered), but parse/emit round-trip
      // closes.
      expr = s.k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
        [s.k.internString("__field__"), expr, s.k.internString(field)],
      );
      continue;
    }
    break;
  }
  return expr;
}

function parsePrimary(s: PState): NodeID {
  const t = peek(s);
  if (t.kind === "int") {
    consume(s);
    return s.k.internTrivialInt(parseInt(t.text, 10));
  }
  if (t.kind === "float") {
    consume(s);
    // No FP trivial in the kernel; store the literal as a string-encoded
    // marker so the emitter can round-trip and Form code that needs the
    // value can convert. Kernel-side fib doesn't need floats.
    const sTriv = s.k.internString(`fp:${t.text}`);
    return s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
      [s.k.internString("__fp_literal__"), sTriv],
    );
  }
  if (t.kind === "str") {
    consume(s);
    return s.k.internString(t.text);
  }
  if (t.kind === "kw" && t.text === "true") {
    consume(s);
    return s.k.internTrivialBool(true);
  }
  if (t.kind === "kw" && t.text === "false") {
    consume(s);
    return s.k.internTrivialBool(false);
  }
  if (t.kind === "kw" && t.text === "nil") {
    consume(s);
    return s.k.internTrivialNull();
  }
  if (t.kind === "punct" && t.text === "(") {
    consume(s);
    const inner = parseExpr(s);
    expect(s, "punct", ")");
    return inner;
  }
  if (t.kind === "kw" && t.text === "make") {
    // make([]T, n) or make(T, n)
    consume(s);
    expect(s, "punct", "(");
    // Skip the type ref
    const typeTxt = parseTypeRefExpr(s);
    const args: NodeID[] = [s.k.internString("make"), s.k.internString(typeTxt)];
    while (check(s, "punct", ",")) {
      consume(s);
      args.push(parseExpr(s));
    }
    expect(s, "punct", ")");
    return s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
      args,
    );
  }
  // Slice literal: []T{a,b,c}
  if (t.kind === "punct" && t.text === "[") {
    consume(s);
    expect(s, "punct", "]");
    const elemType = parseTypeRefExpr(s);
    expect(s, "punct", "{");
    const items: NodeID[] = [];
    if (!check(s, "punct", "}")) {
      items.push(parseExpr(s));
      while (check(s, "punct", ",")) {
        consume(s);
        if (check(s, "punct", "}")) break;
        items.push(parseExpr(s));
      }
    }
    expect(s, "punct", "}");
    // Encode as LIST with a leading type-marker as first child so the
    // emitter can recover `[]T`. The walker's LIST arm ignores the marker
    // gracefully because it evaluates every child — so for evaluation we
    // wrap in FNCALL `list` instead, which skips the marker via the
    // native (it just makes a flat list).
    return s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
      [
        s.k.internString("__slice_literal__"),
        s.k.internString(elemType),
        ...items,
      ],
    );
  }
  if (t.kind === "ident") {
    consume(s);
    // Could be a struct literal `Ident{...}` or simple ident.
    if (!s.noBraceLiteral && check(s, "punct", "{") && looksLikeStructLit(s)) {
      return parseStructLiteral(s, t.text);
    }
    return s.k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 1 },
      [s.k.internString(t.text)],
    );
  }
  throw new Error(
    `unexpected token ${t.kind} "${t.text}" at ${t.pos} in expression`,
  );
}

function parseTypeRefExpr(s: PState): string {
  let txt = "";
  if (check(s, "punct", "[")) {
    consume(s);
    txt += "[";
    if (!check(s, "punct", "]")) {
      const t = consume(s);
      txt += t.text;
    }
    expect(s, "punct", "]");
    txt += "]";
  }
  if (check(s, "punct", "*")) {
    consume(s);
    txt += "*";
  }
  if (check(s, "ident")) {
    txt += consume(s).text;
  }
  return txt;
}

// Heuristic — struct literal vs block statement. A struct literal has
// `Field: value` pairs or `value` items; a block has statements.
// We accept any `{` directly after an Ident in expression context.
function looksLikeStructLit(_s: PState): boolean {
  return true;
}

function parseStructLiteral(s: PState, typeName: string): NodeID {
  expect(s, "punct", "{");
  const fields: NodeID[] = [s.k.internString("__struct_literal__"), s.k.internString(typeName)];
  while (!check(s, "punct", "}") && !check(s, "eof")) {
    // Could be `Field: value` or `value`.
    if (check(s, "ident") && peek(s, 1).text === ":") {
      const fname = consume(s).text;
      consume(s); // :
      const fval = parseExpr(s);
      fields.push(s.k.internString(fname), fval);
    } else {
      fields.push(s.k.internString(""), parseExpr(s));
    }
    if (check(s, "punct", ",")) consume(s);
  }
  expect(s, "punct", "}");
  return s.k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
    fields,
  );
}

// ===========================================================================
// EMITTER — recipe → Go source
// ===========================================================================

export function emitGo(k: Kernel, node: NodeID): string {
  return emit(k, node, 0).trim();
}

function emit(k: Kernel, node: NodeID, indent: number): string {
  if (node.level === Level.TRIVIAL) {
    switch (node.type) {
      case Triv.INT:
        return String(k.trivialValue(node).kind === "int" ? (k.trivialValue(node) as { int: number }).int : 0);
      case Triv.STRING:
        return JSON.stringify(k.strs[node.inst] ?? "");
      case Triv.BOOL:
        return node.inst !== 0 ? "true" : "false";
      case Triv.NULL:
        return "nil";
      default:
        return "/* unknown trivial */";
    }
  }

  const cat = k.category(node);
  const kids = k.children(node);

  switch (cat.type) {
    case RBasic.IDENT: {
      const nameKid = kids[0];
      if (nameKid && nameKid.level === Level.TRIVIAL && nameKid.type === Triv.STRING) {
        return k.strs[nameKid.inst] ?? "";
      }
      return "/* ident */";
    }
    case RBasic.MATH: {
      const op = mathOpStr(cat.inst);
      return kids.map((c) => emit(k, c, indent)).join(` ${op} `);
    }
    case RBasic.COMPARE: {
      const op = cmpOpStr(cat.inst);
      return kids.map((c) => emit(k, c, indent)).join(` ${op} `);
    }
    case RBasic.LOGIC: {
      if (cat.inst === RLogic.NOT) {
        return "!" + emit(k, kids[0]!, indent);
      }
      const op = cat.inst === RLogic.AND ? "&&" : "||";
      return kids.map((c) => emit(k, c, indent)).join(` ${op} `);
    }
    case RBasic.COND: {
      const cond = emit(k, kids[0]!, indent);
      const thenBlock = emitBlock(k, kids[1]!, indent);
      if (cat.inst === RCond.IF_THEN_ELSE) {
        const elseBlock = emitBlock(k, kids[2]!, indent);
        return `if ${cond} ${thenBlock} else ${elseBlock}`;
      }
      return `if ${cond} ${thenBlock}`;
    }
    case RBasic.BLOCK: {
      if (cat.inst === RBlock.LET) {
        const name = emit(k, kids[0]!, indent);
        const value = emit(k, kids[1]!, indent);
        // type-decl markers
        if (name.startsWith('"type ')) {
          const unquoted = name.slice(1, -1);
          return `${unquoted} ${stripQuotes(value)}`;
        }
        return `${stripQuotes(name)} := ${value}`;
      }
      // DO / SEQUENCE
      return emitStatements(k, kids, indent);
    }
    case RBasic.FNDEF: {
      const nameNode = kids[0]!;
      const paramsNode = kids[1]!;
      const bodyNode = kids[2]!;
      const name = nameNode.level === Level.TRIVIAL && nameNode.type === Triv.STRING
        ? (k.strs[nameNode.inst] ?? "")
        : "_";
      const paramKids = k.children(paramsNode);
      const params = paramKids
        .map((p) => (p.level === Level.TRIVIAL && p.type === Triv.STRING
          ? k.strs[p.inst] ?? "_"
          : "_") + " int64")
        .join(", ");
      // Function-body emit re-introduces `return` at terminal positions
      // because parse-time lowerReturns stripped them. Round-trip closes
      // because parse(emit(x)) lowers again identically.
      const body = emitFnBody(k, bodyNode, indent);
      // Method form?
      const dotIdx = name.indexOf(".");
      if (dotIdx > 0 && /^[A-Z]/.test(name)) {
        const recvType = name.slice(0, dotIdx);
        const methodName = name.slice(dotIdx + 1);
        return `func (r ${recvType}) ${methodName}(${params}) int64 ${body}`;
      }
      return `func ${name}(${params}) int64 ${body}`;
    }
    case RBasic.FNCALL: {
      return emitCall(k, kids, indent);
    }
    case RBasic.LIST: {
      const items = kids.map((c) => emit(k, c, indent)).join(", ");
      return `[]interface{}{${items}}`;
    }
    default:
      return `/* unsupported category ${cat.type} */`;
  }
}

function emitCall(k: Kernel, kids: readonly NodeID[], indent: number): string {
  if (kids.length === 0) return "()";
  const callee = kids[0]!;
  let calleeName = "";
  if (callee.level === Level.TRIVIAL && callee.type === Triv.STRING) {
    calleeName = k.strs[callee.inst] ?? "";
  } else if (callee.level === Level.BASIC && callee.type === RBasic.IDENT) {
    const nameKid = k.children(callee)[0];
    if (nameKid && nameKid.level === Level.TRIVIAL && nameKid.type === Triv.STRING) {
      calleeName = k.strs[nameKid.inst] ?? "";
    }
  }

  // Surface markers.
  if (calleeName === "return") {
    const rest = kids.slice(1).map((c) => emit(k, c, indent)).join(", ");
    return rest.length > 0 ? `return ${rest}` : "return";
  }
  if (calleeName === "for") {
    // for(init, cond, post, body)
    const initN = kids[1]!;
    const condN = kids[2]!;
    const postN = kids[3]!;
    const bodyN = kids[4]!;
    const init = isTrivialNull(initN) ? "" : emit(k, initN, indent);
    const cond = isTrivialBoolTrue(condN) ? "" : emit(k, condN, indent);
    const post = isTrivialNull(postN) ? "" : emit(k, postN, indent);
    const body = emitBlock(k, bodyN, indent);
    if (init === "" && post === "" && cond === "") return `for ${body}`;
    if (init === "" && post === "") return `for ${cond} ${body}`;
    return `for ${init}; ${cond}; ${post} ${body}`;
  }
  if (calleeName === "range") {
    // [range, name1, name2?, NULL, iterable, body]
    const names: string[] = [];
    let j = 1;
    while (j < kids.length && !isTrivialNull(kids[j]!)) {
      const t = kids[j]!;
      if (t.level === Level.TRIVIAL && t.type === Triv.STRING) {
        names.push(k.strs[t.inst] ?? "_");
      }
      j++;
    }
    j++; // skip the NULL marker
    const iterable = emit(k, kids[j]!, indent);
    const body = emitBlock(k, kids[j + 1]!, indent);
    return `for ${names.join(", ")} := range ${iterable} ${body}`;
  }
  if (calleeName === "__slice_literal__") {
    const elemType = stripQuotes(emit(k, kids[1]!, indent));
    const items = kids.slice(2).map((c) => emit(k, c, indent)).join(", ");
    return `[]${elemType}{${items}}`;
  }
  if (calleeName === "__struct_literal__") {
    const typeName = stripQuotes(emit(k, kids[1]!, indent));
    const fields: string[] = [];
    for (let j = 2; j < kids.length; j += 2) {
      const fnameTriv = kids[j]!;
      const fval = kids[j + 1]!;
      const fname =
        fnameTriv.level === Level.TRIVIAL && fnameTriv.type === Triv.STRING
          ? k.strs[fnameTriv.inst] ?? ""
          : "";
      if (fname === "") fields.push(emit(k, fval, indent));
      else fields.push(`${fname}: ${emit(k, fval, indent)}`);
    }
    return `${typeName}{${fields.join(", ")}}`;
  }
  if (calleeName === "__fp_literal__") {
    const inner = stripQuotes(emit(k, kids[1]!, indent));
    return inner.startsWith("fp:") ? inner.slice(3) : inner;
  }
  if (calleeName === "nth") {
    return `${emit(k, kids[1]!, indent)}[${emit(k, kids[2]!, indent)}]`;
  }
  if (calleeName === "__field__") {
    const recv = emit(k, kids[1]!, indent);
    const fieldName = stripQuotes(emit(k, kids[2]!, indent));
    return `${recv}.${fieldName}`;
  }
  if (calleeName === "make") {
    // make("[]T", n) → make([]T, n)
    const typeArg = stripQuotes(emit(k, kids[1]!, indent));
    const rest = kids.slice(2).map((c) => emit(k, c, indent));
    return `make(${typeArg}${rest.length > 0 ? ", " + rest.join(", ") : ""})`;
  }
  // Plain call
  const args = kids.slice(1).map((c) => emit(k, c, indent)).join(", ");
  return `${calleeName}(${args})`;
}

// Function-body emit. Wraps the body in `{ … }` and re-introduces `return`
// at terminal expression positions (whose value is the function's result).
// In an if-then-else, both branches are terminal. In a DO-block, only the
// last statement is terminal.
function emitFnBody(k: Kernel, node: NodeID, indent: number): string {
  const nestedIndent = indent + 1;
  const pad = "\t".repeat(nestedIndent);
  const closePad = "\t".repeat(indent);

  if (node.level === Level.BASIC) {
    const cat = k.category(node);
    if (
      cat.type === RBasic.BLOCK &&
      (cat.inst === RBlock.DO || cat.inst === RBlock.SEQUENCE)
    ) {
      const kids = k.children(node);
      const lines: string[] = [];
      for (let i = 0; i < kids.length; i++) {
        const c = kids[i]!;
        const isLast = i === kids.length - 1;
        lines.push(pad + emitFnStmt(k, c, nestedIndent, isLast));
      }
      return `{\n${lines.join("\n")}\n${closePad}}`;
    }
  }
  // Single-statement body — it's terminal.
  return `{\n${pad}${emitFnStmt(k, node, nestedIndent, true)}\n${closePad}}`;
}

// Emit a single statement inside a function body. `terminal` means its
// value flows to the function's return slot — wrap in `return` (or, for
// an if-then-else, recurse into each branch).
function emitFnStmt(k: Kernel, node: NodeID, indent: number, terminal: boolean): string {
  if (!terminal) return emit(k, node, indent);

  if (node.level === Level.BASIC) {
    const cat = k.category(node);
    if (cat.type === RBasic.COND && cat.inst === RCond.IF_THEN_ELSE) {
      const kids = k.children(node);
      const cond = emit(k, kids[0]!, indent);
      const thenBlock = emitFnBody(k, kids[1]!, indent);
      const elseBlock = emitFnBody(k, kids[2]!, indent);
      return `if ${cond} ${thenBlock} else ${elseBlock}`;
    }
    if (cat.type === RBasic.COND && cat.inst === RCond.IF_THEN) {
      // Half-open if at terminal position can't carry a value; emit as
      // plain if-statement and add a bare return after (no value).
      const kids = k.children(node);
      const cond = emit(k, kids[0]!, indent);
      const thenBlock = emitFnBody(k, kids[1]!, indent);
      return `if ${cond} ${thenBlock}`;
    }
    if (
      cat.type === RBasic.BLOCK &&
      (cat.inst === RBlock.DO || cat.inst === RBlock.SEQUENCE)
    ) {
      // Nested DO at terminal position — re-emit as a function-body shape.
      return emitFnBody(k, node, indent).slice(1, -1).trim();
    }
    // LET at terminal position is a statement, not a value-bearing
    // expression — emit as-is, no `return`.
    if (cat.type === RBasic.BLOCK && cat.inst === RBlock.LET) {
      return emit(k, node, indent);
    }
  }
  // Plain expression at terminal position → `return X`.
  return `return ${emit(k, node, indent)}`;
}

function emitBlock(k: Kernel, node: NodeID, indent: number): string {
  // Unwrap single-statement bodies.
  const nestedIndent = indent + 1;
  const pad = "\t".repeat(nestedIndent);
  if (node.level === Level.BASIC) {
    const cat = k.category(node);
    if (cat.type === RBasic.BLOCK && (cat.inst === RBlock.DO || cat.inst === RBlock.SEQUENCE)) {
      const kids = k.children(node);
      const lines = kids.map((c) => pad + emit(k, c, nestedIndent));
      return `{\n${lines.join("\n")}\n${"\t".repeat(indent)}}`;
    }
  }
  return `{\n${pad}${emit(k, node, nestedIndent)}\n${"\t".repeat(indent)}}`;
}

function emitStatements(k: Kernel, kids: readonly NodeID[], indent: number): string {
  return kids.map((c) => emit(k, c, indent)).join("\n");
}

function isTrivialNull(n: NodeID): boolean {
  return n.level === Level.TRIVIAL && n.type === Triv.NULL;
}
function isTrivialBoolTrue(n: NodeID): boolean {
  return n.level === Level.TRIVIAL && n.type === Triv.BOOL && n.inst === 1;
}
function stripQuotes(s: string): string {
  if (s.length >= 2 && s.startsWith('"') && s.endsWith('"')) {
    try {
      return JSON.parse(s) as string;
    } catch {
      return s.slice(1, -1);
    }
  }
  return s;
}

function mathOpStr(op: number): string {
  switch (op) {
    case RMath.PLUS: return "+";
    case RMath.MINUS: return "-";
    case RMath.MUL: return "*";
    case RMath.DIV: return "/";
    case RMath.MOD: return "%";
    default: return "?";
  }
}
function cmpOpStr(op: number): string {
  switch (op) {
    case RCmp.EQ: return "==";
    case RCmp.NE: return "!=";
    case RCmp.LT: return "<";
    case RCmp.LE: return "<=";
    case RCmp.GT: return ">";
    case RCmp.GE: return ">=";
    default: return "?";
  }
}

// ---------------------------------------------------------------------------
// Format-recipe helpers exposed for the test suite / future Language cells.
// ---------------------------------------------------------------------------

export function formatForGoType(typeName: string): FormatTag | undefined {
  return GO_TYPE_TO_FORMAT[typeName];
}

export function goTypeForFormat(fmt: FormatTag): string | undefined {
  return FORMAT_TO_GO_TYPE[fmt];
}
