// lang-rust.ts — Rust 1.83 as a substrate-resident Language cell.
//
// Task #18, sibling of #15 (Python), #16 (TypeScript), #17 (Go). One
// canonical contract (the Language cell shape from languages.ts), four
// per-language populations. Adding Rust here is a substrate write —
// the kernel does not learn Rust.
//
// What this cell carries:
//
//   • An ingestion grammar (built from gLiteral / gAlt / gCapture / ...
//     in languages.ts) describing the Rust surface shapes we ingest.
//     The grammar is content-addressed; two Rust 1.83 cells in two
//     kernels intern to the same NodeID.
//
//   • An emission template that round-trips a captured recipe tree
//     back to Rust source up to formatting.
//
//   • Numeric defaults — Rust's typed-suffix literal model maps every
//     primitive to a format-recipe from formats.ts. `42i32` → INT32,
//     `3.14f64` → FP64, `1_000_000u64` → UINT64. Unsuffixed integers
//     default to `i32` (Rust's inference default before type-checking);
//     unsuffixed floats default to `f64`.
//
//   • stdlib bindings — surface names ("Vec::len", "println!", ...)
//     each routed to a substrate cell. The bindings let cross-language
//     equivalence work: `vec.len()` here and `len(list)` in Python's
//     cell point at the same underlying recipe.
//
// Beyond the Language cell, the file exposes:
//
//   • parseRust(k, source)  — hand-rolled recursive-descent parser that
//                             produces a captured recipe tree using the
//                             same ctor names the grammar declares.
//                             Carries Rust operator precedence and
//                             whitespace-insensitive token rules the
//                             vertical-slice substrate walker would
//                             grow next.
//
//   • emitRust(k, tree)     — emits source back from a captured tree.
//
//   • evalRust(k, tree, env)— walks a captured Rust recipe tree as a
//                             tree-walking interpreter. Implements
//                             enough surface to evaluate fib(10) = 55.
//
// Lifetimes are stripped at parse time and preserved as recipe
// metadata for round-trip emission. The grammar treats `'a` and longer
// names symmetrically; the parser drops the annotation from positions
// (parameter types, return types) and records it on the parent capture
// as a "_lifetimes" child for re-emission.
//
// Scope note: this is v0. No borrow checker, no trait resolution, no
// macro expansion beyond the two macros we explicitly ingest
// (`vec![...]` and `println!(...)`). Just enough Rust surface for the
// algorithm-shaped corpus the substrate cares about.

import {
  Kernel,
  Level,
  RBasic,
  Triv,
  type NodeID,
} from "./kernel.ts";
import { buildFormatLibrary, type FormatLibrary, type FormatRecipe } from "./formats.ts";
import {
  capturedChildren,
  capturedCtor,
  eJoin,
  gAlt,
  gCapture,
  gLiteral,
  gPlus,
  gTokenClass,
  registerLanguage,
  type Language,
} from "./languages.ts";

// ---------------------------------------------------------------------------
// Token-level helpers
// ---------------------------------------------------------------------------
//
// The grammar in the language cell declares the shape; the runtime
// parser uses precedence-aware recursive descent. Both produce
// CAPTURE-shaped recipe trees with the same ctor names — so any
// cross-language equivalence check that compares ctor + child trees
// works regardless of which side parsed.

const RUST_KEYWORDS = new Set([
  "fn", "let", "mut", "if", "else", "match", "return", "true", "false",
  "struct", "enum", "impl", "for", "while", "loop", "break", "continue",
  "in", "as", "ref", "self", "Self", "pub", "use", "mod", "crate",
  "super", "where", "trait", "type", "const", "static", "move", "dyn",
  "async", "await", "unsafe", "extern",
]);

const NUMERIC_TYPE_SUFFIXES = [
  "i8", "i16", "i32", "i64", "i128", "isize",
  "u8", "u16", "u32", "u64", "u128", "usize",
  "f32", "f64",
];

interface Tok {
  readonly kind:
    | "ident" | "kw" | "lifetime"
    | "int" | "float" | "char" | "string"
    | "punct" | "macro_bang";
  readonly text: string;
  // For numeric tokens, the suffix (if any) is split out — `42i32`
  // tokenizes as { kind: "int", text: "42", suffix: "i32" }.
  readonly suffix?: string;
  readonly pos: number;
}

class Tokenizer {
  private pos = 0;
  private toks: Tok[] = [];

  constructor(private readonly src: string) {}

  static run(src: string): Tok[] {
    const t = new Tokenizer(src);
    t.lex();
    return t.toks;
  }

  private peek(off = 0): number {
    return this.pos + off < this.src.length
      ? this.src.charCodeAt(this.pos + off)
      : -1;
  }

  private skipTrivia(): void {
    while (this.pos < this.src.length) {
      const c = this.src.charCodeAt(this.pos);
      if (c === 32 || c === 9 || c === 10 || c === 13) {
        this.pos++;
        continue;
      }
      // line comment
      if (c === 47 /* / */ && this.peek(1) === 47) {
        while (this.pos < this.src.length &&
               this.src.charCodeAt(this.pos) !== 10) {
          this.pos++;
        }
        continue;
      }
      // block comment (nestable in Rust, we honor that)
      if (c === 47 && this.peek(1) === 42 /* * */) {
        this.pos += 2;
        let depth = 1;
        while (this.pos < this.src.length && depth > 0) {
          const a = this.src.charCodeAt(this.pos);
          const b = this.peek(1);
          if (a === 47 && b === 42) { depth++; this.pos += 2; continue; }
          if (a === 42 && b === 47) { depth--; this.pos += 2; continue; }
          this.pos++;
        }
        continue;
      }
      break;
    }
  }

  private lex(): void {
    while (this.pos < this.src.length) {
      this.skipTrivia();
      if (this.pos >= this.src.length) break;
      const start = this.pos;
      const c = this.src.charCodeAt(this.pos);

      // Identifier / keyword / lifetime / macro
      if (isIdentStart(c)) {
        let p = this.pos + 1;
        while (p < this.src.length && isIdentCont(this.src.charCodeAt(p))) p++;
        const text = this.src.substring(this.pos, p);
        this.pos = p;
        // macro? "ident!"
        if (this.peek() === 33 /* ! */) {
          this.pos++;
          this.toks.push({ kind: "macro_bang", text, pos: start });
          continue;
        }
        if (RUST_KEYWORDS.has(text)) {
          this.toks.push({ kind: "kw", text, pos: start });
        } else {
          this.toks.push({ kind: "ident", text, pos: start });
        }
        continue;
      }

      // Lifetime: 'a, 'abc — distinguished from char literal by the
      // absence of a closing quote at length-1+1.
      if (c === 39 /* ' */) {
        // Could be 'a (lifetime) or 'x' (char literal). Heuristic:
        // a char literal is exactly "'<char>'" or "'\<escape>'". A
        // lifetime is "'" followed by an ident.
        if (isIdentStart(this.peek(1)) && this.peek(2) !== 39) {
          this.pos++;
          const idStart = this.pos;
          while (this.pos < this.src.length && isIdentCont(this.src.charCodeAt(this.pos))) {
            this.pos++;
          }
          const text = "'" + this.src.substring(idStart, this.pos);
          this.toks.push({ kind: "lifetime", text, pos: start });
          continue;
        }
        // char literal
        this.pos++;
        let content = "";
        if (this.peek() === 92 /* \ */) {
          content += String.fromCharCode(this.peek(), this.peek(1));
          this.pos += 2;
        } else if (this.pos < this.src.length) {
          content += String.fromCharCode(this.src.charCodeAt(this.pos));
          this.pos++;
        }
        if (this.peek() === 39) this.pos++;
        this.toks.push({ kind: "char", text: content, pos: start });
        continue;
      }

      // String literal
      if (c === 34 /* " */) {
        this.pos++;
        const sb: string[] = [];
        while (this.pos < this.src.length && this.src.charCodeAt(this.pos) !== 34) {
          const ch = this.src.charCodeAt(this.pos);
          if (ch === 92 /* \ */ && this.pos + 1 < this.src.length) {
            const esc = this.src.charCodeAt(this.pos + 1);
            switch (esc) {
              case 110: sb.push("\n"); break; // n
              case 116: sb.push("\t"); break; // t
              case 114: sb.push("\r"); break; // r
              case 92:  sb.push("\\"); break; // backslash
              case 34:  sb.push("\""); break; // "
              case 39:  sb.push("'"); break;  // '
              case 48:  sb.push("\0"); break; // 0
              default:  sb.push(String.fromCharCode(esc));
            }
            this.pos += 2;
          } else {
            sb.push(String.fromCharCode(ch));
            this.pos++;
          }
        }
        if (this.peek() === 34) this.pos++;
        this.toks.push({ kind: "string", text: sb.join(""), pos: start });
        continue;
      }

      // Numeric literal
      if (isDigit(c)) {
        let p = this.pos;
        // hex / bin / oct prefix
        let base = 10;
        if (c === 48 /* 0 */ && p + 1 < this.src.length) {
          const nx = this.src.charCodeAt(p + 1);
          if (nx === 120 || nx === 88) { base = 16; p += 2; }
          else if (nx === 98 || nx === 66) { base = 2; p += 2; }
          else if (nx === 111 || nx === 79) { base = 8; p += 2; }
        }
        const digitOK = (ch: number): boolean => {
          if (ch === 95) return true; // underscore separator
          if (base === 16) {
            return isDigit(ch) ||
                   (ch >= 97 && ch <= 102) ||
                   (ch >= 65 && ch <= 70);
          }
          if (base === 2) return ch === 48 || ch === 49;
          if (base === 8) return ch >= 48 && ch <= 55;
          return isDigit(ch);
        };
        while (p < this.src.length && digitOK(this.src.charCodeAt(p))) p++;
        let isFloat = false;
        if (base === 10 && p < this.src.length && this.src.charCodeAt(p) === 46) {
          // only treat as float if next is digit
          const nx = p + 1 < this.src.length ? this.src.charCodeAt(p + 1) : -1;
          if (isDigit(nx)) {
            isFloat = true;
            p++;
            while (p < this.src.length && digitOK(this.src.charCodeAt(p))) p++;
          }
        }
        // Exponent
        if (base === 10 && p < this.src.length) {
          const ch = this.src.charCodeAt(p);
          if (ch === 101 || ch === 69) {
            isFloat = true;
            p++;
            if (p < this.src.length) {
              const sgn = this.src.charCodeAt(p);
              if (sgn === 43 || sgn === 45) p++;
            }
            while (p < this.src.length && digitOK(this.src.charCodeAt(p))) p++;
          }
        }
        const digits = this.src.substring(this.pos, p).replace(/_/g, "");
        // Suffix
        let suffix: string | undefined;
        for (const s of NUMERIC_TYPE_SUFFIXES) {
          if (this.src.startsWith(s, p)) {
            const after = p + s.length;
            const ok = after >= this.src.length ||
                       !isIdentCont(this.src.charCodeAt(after));
            if (ok) {
              suffix = s;
              p += s.length;
              if (s.startsWith("f")) isFloat = true;
              break;
            }
          }
        }
        this.pos = p;
        // strip prefix from "digits" for the recorded text (numeric
        // value); we keep base info via the prefix on emission. For
        // simplicity, record decimal-canonicalized text.
        let text: string;
        if (base === 10) {
          text = digits;
        } else {
          // For non-decimal, recompute decimal value as canonical text.
          const stripped = digits.startsWith("0x") || digits.startsWith("0X")
            ? digits.substring(2)
            : digits.startsWith("0b") || digits.startsWith("0B")
              ? digits.substring(2)
              : digits.startsWith("0o") || digits.startsWith("0O")
                ? digits.substring(2)
                : digits;
          try {
            const v = parseInt(stripped, base);
            text = String(v);
          } catch {
            text = digits;
          }
        }
        this.toks.push({
          kind: isFloat ? "float" : "int",
          text,
          suffix,
          pos: start,
        });
        continue;
      }

      // Punctuation — match longest-first.
      const punct = matchPunct(this.src, this.pos);
      if (punct !== null) {
        this.toks.push({ kind: "punct", text: punct, pos: start });
        this.pos += punct.length;
        continue;
      }

      throw new Error(
        `rust tokenize: unexpected char '${this.src[this.pos]}' at ${this.pos}`,
      );
    }
  }
}

function isDigit(c: number): boolean { return c >= 48 && c <= 57; }
function isIdentStart(c: number): boolean {
  return (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c === 95;
}
function isIdentCont(c: number): boolean {
  return isIdentStart(c) || isDigit(c);
}

// Longest-match punctuation table — order matters for tokens that
// share a prefix (`==` before `=`, `->` before `-`, etc.).
const PUNCT_TABLE = [
  "..=", "...",
  "==", "!=", "<=", ">=", "<<", ">>", "&&", "||",
  "->", "=>", "::", "..",
  "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
  "+", "-", "*", "/", "%",
  "&", "|", "^", "!", "~",
  "<", ">", "=",
  "(", ")", "{", "}", "[", "]",
  ",", ";", ":", ".", "@", "#", "?", "$",
];

function matchPunct(src: string, pos: number): string | null {
  for (const p of PUNCT_TABLE) {
    if (src.startsWith(p, pos)) return p;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Recipe-tree constructor — every CAPTURE the parser emits goes
// through `cap` so identity stays content-addressed.
// ---------------------------------------------------------------------------

function cap(k: Kernel, ctorName: string, children: NodeID[]): NodeID {
  const ctorNameID = k.internName(ctorName);
  const ctorCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.LIST,
    inst: ctorNameID,
  };
  return k.intern(ctorCat, children);
}

// String literal as a "str" capture so the tree carries both the
// surface form ("str") and the actual string contents.
function strLit(k: Kernel, s: string): NodeID {
  return cap(k, "str", [k.internString(s)]);
}

function ident(k: Kernel, name: string): NodeID {
  return cap(k, "ident", [k.internString(name)]);
}

// Numeric literal — captured with kind ctor ("int_lit" / "float_lit")
// and a child encoding both the value AND the format suffix. The
// suffix is what routes to the numeric_defaults map; the value lives
// inline in the chosen substrate-trivial slot.
function intLit(k: Kernel, text: string, suffix: string | undefined): NodeID {
  const fmt = suffix ?? "i32"; // unsuffixed default per Rust inference
  const valNode = internIntByFormat(k, text, fmt);
  return cap(k, "int_lit", [valNode, k.internString(fmt)]);
}

function floatLit(k: Kernel, text: string, suffix: string | undefined): NodeID {
  const fmt = suffix ?? "f64";
  const valNode = internFloatByFormat(k, text, fmt);
  return cap(k, "float_lit", [valNode, k.internString(fmt)]);
}

function internIntByFormat(k: Kernel, text: string, fmt: string): NodeID {
  // Routes the parsed value into the appropriate substrate-trivial
  // slot so content-addressing of the captured tree carries width.
  const isNeg = text.startsWith("-");
  switch (fmt) {
    case "i8":  return k.internTrivialInt8(parseInt(text, 10));
    case "i16": return k.internTrivialInt16(parseInt(text, 10));
    case "i32":
    case "isize":
      return k.internTrivialInt(parseInt(text, 10) | 0);
    case "i64":
    case "i128":
      return k.internTrivialInt64(BigInt(text));
    case "u8":  return k.internTrivialUint8(parseInt(text, 10));
    case "u16": return k.internTrivialUint16(parseInt(text, 10));
    case "u32":
    case "usize":
      return k.internTrivialUint32(parseInt(text, 10) >>> 0);
    case "u64":
    case "u128":
      return k.internTrivialUint64(isNeg ? 0n : BigInt(text));
    default:
      return k.internTrivialInt(parseInt(text, 10) | 0);
  }
}

function internFloatByFormat(k: Kernel, text: string, fmt: string): NodeID {
  const v = parseFloat(text);
  if (fmt === "f32") return k.internTrivialFloat32(v);
  return k.internTrivialFloat64(v);
}

// ---------------------------------------------------------------------------
// Parser — recursive descent, Pratt for expressions.
// ---------------------------------------------------------------------------

class Parser {
  private i = 0;
  constructor(private readonly k: Kernel, private readonly toks: Tok[]) {}

  static parseSource(k: Kernel, src: string): NodeID {
    const toks = Tokenizer.run(src);
    const p = new Parser(k, toks);
    return p.parseProgram();
  }

  static parseExpression(k: Kernel, src: string): NodeID {
    const toks = Tokenizer.run(src);
    const p = new Parser(k, toks);
    const e = p.parseExpr();
    if (p.i < p.toks.length) {
      throw new Error(`rust parse: trailing tokens at ${p.toks[p.i]!.pos}`);
    }
    return e;
  }

  // ---- low-level helpers ----

  private peek(off = 0): Tok | undefined { return this.toks[this.i + off]; }
  private done(): boolean { return this.i >= this.toks.length; }
  private bump(): Tok {
    const t = this.toks[this.i];
    if (!t) throw new Error("rust parse: unexpected EOF");
    this.i++;
    return t;
  }
  private match(kind: Tok["kind"], text?: string): Tok | null {
    const t = this.peek();
    if (!t) return null;
    if (t.kind !== kind) return null;
    if (text !== undefined && t.text !== text) return null;
    this.i++;
    return t;
  }
  private expect(kind: Tok["kind"], text?: string): Tok {
    const t = this.match(kind, text);
    if (!t) {
      const got = this.peek();
      throw new Error(
        `rust parse: expected ${kind}${text ? ` "${text}"` : ""}, got ${
          got ? `${got.kind} "${got.text}"` : "EOF"
        } at ${got?.pos ?? "?"}`,
      );
    }
    return t;
  }
  private at(kind: Tok["kind"], text?: string): boolean {
    const t = this.peek();
    if (!t) return false;
    if (t.kind !== kind) return false;
    if (text !== undefined && t.text !== text) return false;
    return true;
  }

  // ---- program ----

  // program ::= item*
  private parseProgram(): NodeID {
    const items: NodeID[] = [];
    while (!this.done()) {
      items.push(this.parseItem());
    }
    return cap(this.k, "program", items);
  }

  // item ::= fn | struct | enum | (expr ';')   — for top-level scripts
  //   we also allow bare expressions so we can ingest test snippets.
  private parseItem(): NodeID {
    if (this.at("kw", "fn"))     return this.parseFn();
    if (this.at("kw", "struct")) return this.parseStruct();
    if (this.at("kw", "enum"))   return this.parseEnum();
    if (this.at("kw", "let"))    return this.parseLetStmt();
    // bare expression-statement (for test scripts)
    const e = this.parseExpr();
    this.match("punct", ";");
    return e;
  }

  // ---- fn ----

  // fn ::= 'fn' ident generic_params? '(' param_list ')' ('->' type)? block
  private parseFn(): NodeID {
    this.expect("kw", "fn");
    const name = this.expect("ident").text;
    const generics = this.parseGenericParamsOpt();
    this.expect("punct", "(");
    const params: NodeID[] = [];
    const lifetimes: string[] = []; // collected as recipe metadata for round-trip
    if (!this.at("punct", ")")) {
      params.push(this.parseParam(lifetimes));
      while (this.match("punct", ",")) {
        if (this.at("punct", ")")) break;
        params.push(this.parseParam(lifetimes));
      }
    }
    this.expect("punct", ")");
    let retType: NodeID = cap(this.k, "type", [ident(this.k, "()")]);
    if (this.match("punct", "->")) {
      retType = this.parseType(lifetimes);
    }
    const body = this.parseBlock();
    const children: NodeID[] = [
      ident(this.k, name),
      generics,
      cap(this.k, "params", params),
      retType,
      body,
    ];
    if (lifetimes.length > 0) {
      children.push(cap(this.k,
        "_lifetimes",
        lifetimes.map((l) => this.k.internString(l)),
      ));
    }
    return cap(this.k, "fn", children);
  }

  // ---- parameter ----
  private parseParam(lifetimes: string[]): NodeID {
    const isMut = !!this.match("kw", "mut");
    const name = this.expect("ident").text;
    this.expect("punct", ":");
    const ty = this.parseType(lifetimes);
    const kids: NodeID[] = [ident(this.k, name), ty];
    if (isMut) kids.push(cap(this.k, "_mut", []));
    return cap(this.k, "param", kids);
  }

  // ---- generic parameters ----
  // <T, U: Trait, 'a> — we keep the surface for round-trip but the
  // parser's main job is to skip them in v0.
  private parseGenericParamsOpt(): NodeID {
    if (!this.match("punct", "<")) return cap(this.k, "generics", []);
    const params: NodeID[] = [];
    while (!this.at("punct", ">")) {
      const t = this.bump();
      if (t.kind === "punct" && t.text === ",") continue;
      params.push(this.k.internString(t.text));
    }
    this.expect("punct", ">");
    return cap(this.k, "generics", params);
  }

  // ---- type ----
  // type ::= path ('<' type (',' type)* '>')? | tuple | ref-type
  private parseType(lifetimes: string[]): NodeID {
    // Reference type &'a T or &mut T or &T — lifetime stripped, kept
    // in `lifetimes` for round-trip.
    if (this.match("punct", "&")) {
      const life = this.match("lifetime");
      if (life) lifetimes.push(life.text);
      const isMut = !!this.match("kw", "mut");
      const inner = this.parseType(lifetimes);
      const kids: NodeID[] = [inner];
      if (isMut) kids.push(cap(this.k, "_mut", []));
      return cap(this.k, "ref_type", kids);
    }
    // Tuple type (T, U) or unit ()
    if (this.match("punct", "(")) {
      const parts: NodeID[] = [];
      if (!this.at("punct", ")")) {
        parts.push(this.parseType(lifetimes));
        while (this.match("punct", ",")) {
          if (this.at("punct", ")")) break;
          parts.push(this.parseType(lifetimes));
        }
      }
      this.expect("punct", ")");
      if (parts.length === 0) return cap(this.k, "type", [ident(this.k, "()")]);
      return cap(this.k, "tuple_type", parts);
    }
    // Path: ident ('::' ident)* ('<' type-args '>')?
    const segments: string[] = [];
    const first = this.match("ident") ?? this.match("kw");
    if (!first) {
      throw new Error(`rust parse: type expected at ${this.peek()?.pos ?? "?"}`);
    }
    segments.push(first.text);
    while (this.match("punct", "::")) {
      const seg = this.match("ident") ?? this.match("kw");
      if (!seg) throw new Error("rust parse: ident after ::");
      segments.push(seg.text);
    }
    const args: NodeID[] = [];
    if (this.match("punct", "<")) {
      if (!this.at("punct", ">")) {
        // generic args can be types or lifetimes
        const life = this.match("lifetime");
        if (life) {
          lifetimes.push(life.text);
        } else {
          args.push(this.parseType(lifetimes));
        }
        while (this.match("punct", ",")) {
          if (this.at("punct", ">")) break;
          const l2 = this.match("lifetime");
          if (l2) { lifetimes.push(l2.text); continue; }
          args.push(this.parseType(lifetimes));
        }
      }
      this.expect("punct", ">");
    }
    const path = cap(this.k, "path",
      segments.map((s) => this.k.internString(s)),
    );
    return cap(this.k, "type", args.length > 0 ? [path, cap(this.k, "type_args", args)] : [path]);
  }

  // ---- struct ----
  // struct Name { field: T, ... }      — record struct
  // struct Name(T, U);                  — tuple struct
  // struct Name;                        — unit struct
  private parseStruct(): NodeID {
    this.expect("kw", "struct");
    const name = this.expect("ident").text;
    const generics = this.parseGenericParamsOpt();
    const lifetimes: string[] = [];
    // Tuple struct
    if (this.match("punct", "(")) {
      const tys: NodeID[] = [];
      if (!this.at("punct", ")")) {
        tys.push(this.parseType(lifetimes));
        while (this.match("punct", ",")) {
          if (this.at("punct", ")")) break;
          tys.push(this.parseType(lifetimes));
        }
      }
      this.expect("punct", ")");
      this.expect("punct", ";");
      return cap(this.k, "tuple_struct", [
        ident(this.k, name),
        generics,
        cap(this.k, "fields", tys),
      ]);
    }
    // Unit struct
    if (this.match("punct", ";")) {
      return cap(this.k, "unit_struct", [ident(this.k, name), generics]);
    }
    // Record struct
    this.expect("punct", "{");
    const fields: NodeID[] = [];
    while (!this.at("punct", "}")) {
      const fname = this.expect("ident").text;
      this.expect("punct", ":");
      const fty = this.parseType(lifetimes);
      fields.push(cap(this.k, "field", [ident(this.k, fname), fty]));
      if (!this.match("punct", ",")) break;
    }
    this.expect("punct", "}");
    return cap(this.k, "struct", [
      ident(this.k, name),
      generics,
      cap(this.k, "fields", fields),
    ]);
  }

  // ---- enum ----
  // enum Name { Variant, Variant(T,U), Variant{field:T}, ... }
  private parseEnum(): NodeID {
    this.expect("kw", "enum");
    const name = this.expect("ident").text;
    const generics = this.parseGenericParamsOpt();
    this.expect("punct", "{");
    const variants: NodeID[] = [];
    const lifetimes: string[] = [];
    while (!this.at("punct", "}")) {
      const vname = this.expect("ident").text;
      if (this.match("punct", "(")) {
        const tys: NodeID[] = [];
        if (!this.at("punct", ")")) {
          tys.push(this.parseType(lifetimes));
          while (this.match("punct", ",")) {
            if (this.at("punct", ")")) break;
            tys.push(this.parseType(lifetimes));
          }
        }
        this.expect("punct", ")");
        variants.push(cap(this.k, "variant_tuple", [
          ident(this.k, vname),
          cap(this.k, "fields", tys),
        ]));
      } else if (this.match("punct", "{")) {
        const fields: NodeID[] = [];
        while (!this.at("punct", "}")) {
          const fname = this.expect("ident").text;
          this.expect("punct", ":");
          const fty = this.parseType(lifetimes);
          fields.push(cap(this.k, "field", [ident(this.k, fname), fty]));
          if (!this.match("punct", ",")) break;
        }
        this.expect("punct", "}");
        variants.push(cap(this.k, "variant_struct", [
          ident(this.k, vname),
          cap(this.k, "fields", fields),
        ]));
      } else {
        variants.push(cap(this.k, "variant_unit", [ident(this.k, vname)]));
      }
      if (!this.match("punct", ",")) break;
    }
    this.expect("punct", "}");
    return cap(this.k, "enum", [
      ident(this.k, name),
      generics,
      cap(this.k, "variants", variants),
    ]);
  }

  // ---- block ----
  // block ::= '{' stmt* expr? '}'
  // In Rust, a block expression's value is either the trailing
  // expression (no semicolon) or unit if everything is statements.
  private parseBlock(): NodeID {
    this.expect("punct", "{");
    const stmts: NodeID[] = [];
    let tail: NodeID | null = null;
    while (!this.at("punct", "}")) {
      // let-statement
      if (this.at("kw", "let")) {
        stmts.push(this.parseLetStmt());
        continue;
      }
      // return-statement
      if (this.at("kw", "return")) {
        this.bump();
        const e = this.at("punct", ";")
          ? cap(this.k, "unit", [])
          : this.parseExpr();
        this.expect("punct", ";");
        stmts.push(cap(this.k, "return", [e]));
        continue;
      }
      // expression — could be statement (followed by ;) or tail.
      const e = this.parseExpr();
      if (this.match("punct", ";")) {
        stmts.push(cap(this.k, "expr_stmt", [e]));
      } else {
        // tail expression
        tail = e;
        break;
      }
    }
    this.expect("punct", "}");
    return cap(this.k, "block",
      tail !== null ? [...stmts, cap(this.k, "tail", [tail])] : stmts,
    );
  }

  // ---- let ----
  // let (mut)? pat (':' type)? '=' expr ';'
  private parseLetStmt(): NodeID {
    this.expect("kw", "let");
    const isMut = !!this.match("kw", "mut");
    const name = this.expect("ident").text;
    const lifetimes: string[] = [];
    let ty: NodeID = cap(this.k, "type_infer", []);
    if (this.match("punct", ":")) {
      ty = this.parseType(lifetimes);
    }
    this.expect("punct", "=");
    const val = this.parseExpr();
    this.expect("punct", ";");
    const kids: NodeID[] = [ident(this.k, name), ty, val];
    if (isMut) kids.push(cap(this.k, "_mut", []));
    return cap(this.k, "let", kids);
  }

  // ---- expression — Pratt precedence ----
  //
  // Precedence (low to high):
  //   1  ||
  //   2  &&
  //   3  == != < <= > >=
  //   4  |
  //   5  ^
  //   6  &
  //   7  << >>
  //   8  + -
  //   9  * / %
  //  10  unary - ! &
  //  11  call/method/index/field
  //  12  primary
  //
  // 'as' is parsed at level 10 (between unary and bin) — between
  // unary and shift, mirroring the Rust reference grammar.
  parseExpr(): NodeID { return this.parseLogicalOr(); }

  private parseLogicalOr(): NodeID {
    let lhs = this.parseLogicalAnd();
    while (this.at("punct", "||")) {
      this.bump();
      const rhs = this.parseLogicalAnd();
      lhs = cap(this.k, "or", [lhs, rhs]);
    }
    return lhs;
  }
  private parseLogicalAnd(): NodeID {
    let lhs = this.parseCompare();
    while (this.at("punct", "&&")) {
      this.bump();
      const rhs = this.parseCompare();
      lhs = cap(this.k, "and", [lhs, rhs]);
    }
    return lhs;
  }
  private parseCompare(): NodeID {
    let lhs = this.parseBitOr();
    const cmpOps = ["==", "!=", "<", "<=", ">", ">="];
    while (true) {
      const t = this.peek();
      if (!t || t.kind !== "punct" || !cmpOps.includes(t.text)) break;
      const op = t.text;
      this.bump();
      const rhs = this.parseBitOr();
      lhs = cap(this.k, "cmp", [this.k.internString(op), lhs, rhs]);
    }
    return lhs;
  }
  private parseBitOr(): NodeID {
    let lhs = this.parseBitXor();
    while (this.at("punct", "|") && !this.atClosureStart()) {
      this.bump();
      const rhs = this.parseBitXor();
      lhs = cap(this.k, "bitor", [lhs, rhs]);
    }
    return lhs;
  }
  // Heuristic: at "|" we might be at a closure start. We're not at
  // expression position when parsing the binary infix, so this only
  // matters when '|' is the first token of a primary — handled there.
  private atClosureStart(): boolean { return false; }
  private parseBitXor(): NodeID {
    let lhs = this.parseBitAnd();
    while (this.at("punct", "^")) {
      this.bump();
      const rhs = this.parseBitAnd();
      lhs = cap(this.k, "bitxor", [lhs, rhs]);
    }
    return lhs;
  }
  private parseBitAnd(): NodeID {
    let lhs = this.parseShift();
    while (this.at("punct", "&") && !this.atRefStart()) {
      this.bump();
      const rhs = this.parseShift();
      lhs = cap(this.k, "bitand", [lhs, rhs]);
    }
    return lhs;
  }
  private atRefStart(): boolean { return false; }
  private parseShift(): NodeID {
    let lhs = this.parseAdditive();
    while (this.at("punct", "<<") || this.at("punct", ">>")) {
      const op = this.bump().text;
      const rhs = this.parseAdditive();
      lhs = cap(this.k, op === "<<" ? "shl" : "shr", [lhs, rhs]);
    }
    return lhs;
  }
  private parseAdditive(): NodeID {
    let lhs = this.parseMultiplicative();
    while (this.at("punct", "+") || this.at("punct", "-")) {
      const op = this.bump().text;
      const rhs = this.parseMultiplicative();
      lhs = cap(this.k, op === "+" ? "add" : "sub", [lhs, rhs]);
    }
    return lhs;
  }
  private parseMultiplicative(): NodeID {
    let lhs = this.parseUnary();
    while (this.at("punct", "*") || this.at("punct", "/") || this.at("punct", "%")) {
      const op = this.bump().text;
      const rhs = this.parseUnary();
      const ctor = op === "*" ? "mul" : op === "/" ? "div" : "mod";
      lhs = cap(this.k, ctor, [lhs, rhs]);
    }
    return lhs;
  }
  private parseUnary(): NodeID {
    if (this.match("punct", "-")) return cap(this.k, "neg", [this.parseUnary()]);
    if (this.match("punct", "!")) return cap(this.k, "not", [this.parseUnary()]);
    if (this.match("punct", "&")) {
      const isMut = !!this.match("kw", "mut");
      const inner = this.parseUnary();
      const kids: NodeID[] = [inner];
      if (isMut) kids.push(cap(this.k, "_mut", []));
      return cap(this.k, "ref", kids);
    }
    if (this.match("punct", "*")) return cap(this.k, "deref", [this.parseUnary()]);
    return this.parsePostfix();
  }
  // postfix ::= primary (call | method | field | index)*
  private parsePostfix(): NodeID {
    let lhs = this.parsePrimary();
    // eslint-disable-next-line no-constant-condition
    while (true) {
      if (this.match("punct", "(")) {
        const args: NodeID[] = [];
        if (!this.at("punct", ")")) {
          args.push(this.parseExpr());
          while (this.match("punct", ",")) {
            if (this.at("punct", ")")) break;
            args.push(this.parseExpr());
          }
        }
        this.expect("punct", ")");
        lhs = cap(this.k, "call", [lhs, cap(this.k, "args", args)]);
        continue;
      }
      if (this.match("punct", ".")) {
        // method or field — Rust tuple-field access uses integer
        // indices (`t.0`), so we accept ident OR int here.
        const nameTok = this.match("ident") ?? this.match("int");
        if (!nameTok) {
          const got = this.peek();
          throw new Error(
            `rust parse: expected field name after '.', got ${
              got ? `${got.kind} "${got.text}"` : "EOF"
            } at ${got?.pos ?? "?"}`,
          );
        }
        if (this.match("punct", "(")) {
          const args: NodeID[] = [];
          if (!this.at("punct", ")")) {
            args.push(this.parseExpr());
            while (this.match("punct", ",")) {
              if (this.at("punct", ")")) break;
              args.push(this.parseExpr());
            }
          }
          this.expect("punct", ")");
          lhs = cap(this.k, "method", [
            lhs, ident(this.k, nameTok.text), cap(this.k, "args", args),
          ]);
        } else {
          lhs = cap(this.k, "field", [lhs, ident(this.k, nameTok.text)]);
        }
        continue;
      }
      if (this.match("punct", "[")) {
        const e = this.parseExpr();
        this.expect("punct", "]");
        lhs = cap(this.k, "index", [lhs, e]);
        continue;
      }
      if (this.match("punct", "?")) {
        lhs = cap(this.k, "try", [lhs]);
        continue;
      }
      break;
    }
    return lhs;
  }

  // primary ::= literal | ident | path | block | if | match | closure
  //           | array | tuple | paren | macro-call | struct-init
  private parsePrimary(): NodeID {
    const t = this.peek();
    if (!t) throw new Error("rust parse: unexpected EOF in primary");

    // literals
    if (t.kind === "int") {
      this.bump();
      return intLit(this.k, t.text, t.suffix);
    }
    if (t.kind === "float") {
      this.bump();
      return floatLit(this.k, t.text, t.suffix);
    }
    if (t.kind === "string") {
      this.bump();
      return strLit(this.k, t.text);
    }
    if (t.kind === "char") {
      this.bump();
      return cap(this.k, "char_lit", [this.k.internString(t.text)]);
    }
    if (t.kind === "kw" && (t.text === "true" || t.text === "false")) {
      this.bump();
      return cap(this.k, "bool_lit", [this.k.internTrivialBool(t.text === "true")]);
    }
    // closure |x, y| body  or  || body
    if (t.kind === "punct" && (t.text === "|" || t.text === "||")) {
      return this.parseClosure();
    }
    // if
    if (t.kind === "kw" && t.text === "if") return this.parseIf();
    // match
    if (t.kind === "kw" && t.text === "match") return this.parseMatch();
    // block
    if (t.kind === "punct" && t.text === "{") return this.parseBlock();
    // paren / tuple / unit
    if (t.kind === "punct" && t.text === "(") {
      this.bump();
      if (this.match("punct", ")")) return cap(this.k, "unit", []);
      const first = this.parseExpr();
      if (this.match("punct", ",")) {
        const items: NodeID[] = [first];
        if (!this.at("punct", ")")) {
          items.push(this.parseExpr());
          while (this.match("punct", ",")) {
            if (this.at("punct", ")")) break;
            items.push(this.parseExpr());
          }
        }
        this.expect("punct", ")");
        return cap(this.k, "tuple", items);
      }
      this.expect("punct", ")");
      return cap(this.k, "paren", [first]);
    }
    // array literal [a, b, c]
    if (t.kind === "punct" && t.text === "[") {
      this.bump();
      const items: NodeID[] = [];
      if (!this.at("punct", "]")) {
        items.push(this.parseExpr());
        while (this.match("punct", ",")) {
          if (this.at("punct", "]")) break;
          items.push(this.parseExpr());
        }
      }
      this.expect("punct", "]");
      return cap(this.k, "array", items);
    }
    // macro call (println!, vec!, etc.)
    if (t.kind === "macro_bang") {
      return this.parseMacroCall();
    }
    // identifier path / struct literal
    if (t.kind === "ident" || t.kind === "kw") {
      return this.parsePathOrStructInit();
    }

    throw new Error(
      `rust parse: unexpected token "${t.text}" (${t.kind}) at ${t.pos}`,
    );
  }

  // closure ::= '|' params '|' expr   |   '||' expr
  private parseClosure(): NodeID {
    if (this.match("punct", "||")) {
      const body = this.parseExpr();
      return cap(this.k, "closure", [cap(this.k, "params", []), body]);
    }
    this.expect("punct", "|");
    const params: NodeID[] = [];
    if (!this.at("punct", "|")) {
      params.push(this.parseClosureParam());
      while (this.match("punct", ",")) {
        if (this.at("punct", "|")) break;
        params.push(this.parseClosureParam());
      }
    }
    this.expect("punct", "|");
    const body = this.parseExpr();
    return cap(this.k, "closure", [cap(this.k, "params", params), body]);
  }
  private parseClosureParam(): NodeID {
    const name = this.expect("ident").text;
    const lifetimes: string[] = [];
    let ty: NodeID = cap(this.k, "type_infer", []);
    if (this.match("punct", ":")) {
      ty = this.parseType(lifetimes);
    }
    return cap(this.k, "param", [ident(this.k, name), ty]);
  }

  // if ::= 'if' expr block ('else' (if | block))?
  private parseIf(): NodeID {
    this.expect("kw", "if");
    const cond = this.parseExpr();
    const thenB = this.parseBlock();
    let elseB: NodeID = cap(this.k, "unit", []);
    if (this.match("kw", "else")) {
      if (this.at("kw", "if")) {
        elseB = this.parseIf();
      } else {
        elseB = this.parseBlock();
      }
    }
    return cap(this.k, "if", [cond, thenB, elseB]);
  }

  // match ::= 'match' expr '{' arm,* '}'
  // arm ::= pattern '=>' (expr ',' | block)
  private parseMatch(): NodeID {
    this.expect("kw", "match");
    const scrut = this.parseExpr();
    this.expect("punct", "{");
    const arms: NodeID[] = [];
    while (!this.at("punct", "}")) {
      const pat = this.parsePattern();
      this.expect("punct", "=>");
      let body: NodeID;
      if (this.at("punct", "{")) {
        body = this.parseBlock();
        this.match("punct", ",");
      } else {
        body = this.parseExpr();
        this.match("punct", ",");
      }
      arms.push(cap(this.k, "arm", [pat, body]));
    }
    this.expect("punct", "}");
    return cap(this.k, "match", [scrut, cap(this.k, "arms", arms)]);
  }

  // pattern ::= '_' | literal | ident | path '(' pat,* ')'
  //           | path '{' field-pat,* '}' | (pat, pat)
  private parsePattern(): NodeID {
    const t = this.peek();
    if (!t) throw new Error("rust parse: pattern expected");
    // wildcard
    if (t.kind === "ident" && t.text === "_") {
      this.bump();
      return cap(this.k, "pat_wild", []);
    }
    // literal patterns
    if (t.kind === "int") {
      this.bump();
      return cap(this.k, "pat_int", [intLit(this.k, t.text, t.suffix)]);
    }
    if (t.kind === "float") {
      this.bump();
      return cap(this.k, "pat_float", [floatLit(this.k, t.text, t.suffix)]);
    }
    if (t.kind === "string") {
      this.bump();
      return cap(this.k, "pat_str", [strLit(this.k, t.text)]);
    }
    if (t.kind === "kw" && (t.text === "true" || t.text === "false")) {
      this.bump();
      return cap(this.k, "pat_bool",
        [cap(this.k, "bool_lit", [this.k.internTrivialBool(t.text === "true")])]);
    }
    // path-shaped: ident ('::' ident)* (variant patterns)
    if (t.kind === "ident" || t.kind === "kw") {
      const segments: string[] = [];
      const first = this.bump();
      segments.push(first.text);
      while (this.match("punct", "::")) {
        const seg = this.match("ident") ?? this.match("kw");
        if (!seg) throw new Error("rust parse: ident after ::");
        segments.push(seg.text);
      }
      const path = cap(this.k, "path", segments.map((s) => this.k.internString(s)));
      // Tuple-variant pattern: Path(p, p, ...)
      if (this.match("punct", "(")) {
        const subs: NodeID[] = [];
        if (!this.at("punct", ")")) {
          subs.push(this.parsePattern());
          while (this.match("punct", ",")) {
            if (this.at("punct", ")")) break;
            subs.push(this.parsePattern());
          }
        }
        this.expect("punct", ")");
        return cap(this.k, "pat_variant", [path, cap(this.k, "subs", subs)]);
      }
      // Struct-variant pattern: Path { f: p, ... } — minimal
      if (this.match("punct", "{")) {
        const fields: NodeID[] = [];
        while (!this.at("punct", "}")) {
          const fname = this.expect("ident").text;
          let sub: NodeID;
          if (this.match("punct", ":")) {
            sub = this.parsePattern();
          } else {
            sub = cap(this.k, "pat_ident", [ident(this.k, fname)]);
          }
          fields.push(cap(this.k, "field", [ident(this.k, fname), sub]));
          if (!this.match("punct", ",")) break;
        }
        this.expect("punct", "}");
        return cap(this.k, "pat_struct", [path, cap(this.k, "fields", fields)]);
      }
      // Plain ident binder, possibly with a single-segment "path"
      if (segments.length === 1) {
        return cap(this.k, "pat_ident", [ident(this.k, segments[0]!)]);
      }
      return cap(this.k, "pat_path", [path]);
    }
    throw new Error(`rust parse: unexpected pattern token "${t.text}"`);
  }

  // macro_call ::= ident '!' ( '(' args ')' | '[' args ']' | '{' args '}' )
  // We've already consumed the 'ident!' as macro_bang.
  private parseMacroCall(): NodeID {
    const name = this.expect("macro_bang").text;
    let delim: "(" | "[" | "{" = "(";
    let open = "(", close = ")";
    if (this.at("punct", "[")) { delim = "["; open = "["; close = "]"; }
    else if (this.at("punct", "{")) { delim = "{"; open = "{"; close = "}"; }
    this.expect("punct", open);
    const args: NodeID[] = [];
    if (!this.at("punct", close)) {
      args.push(this.parseExpr());
      while (this.match("punct", ",")) {
        if (this.at("punct", close)) break;
        args.push(this.parseExpr());
      }
    }
    this.expect("punct", close);
    // Recognize specific macros by name; everything else flows through
    // a generic macro_call ctor.
    if (name === "vec") {
      return cap(this.k, "vec", args);
    }
    if (name === "println" || name === "print" || name === "eprintln" || name === "eprint") {
      return cap(this.k, "println", [
        ident(this.k, name),
        cap(this.k, "args", args),
      ]);
    }
    return cap(this.k, "macro_call", [
      ident(this.k, name),
      this.k.internString(delim),
      cap(this.k, "args", args),
    ]);
  }

  // path-or-struct-init: ident('::' ident)* ('{' ... '}')?
  private parsePathOrStructInit(): NodeID {
    const segments: string[] = [];
    const first = this.bump();
    segments.push(first.text);
    while (this.at("punct", "::")) {
      this.bump();
      const seg = this.match("ident") ?? this.match("kw");
      if (!seg) throw new Error("rust parse: ident after ::");
      segments.push(seg.text);
    }
    const path = cap(this.k, "path", segments.map((s) => this.k.internString(s)));
    // Struct init follows: PathName { field: value, ... }
    //
    // We must not gobble '{' that opens a block (e.g. `if x { ... }`),
    // so this branch only triggers when context allows. We use a
    // simple lookahead: if the next non-{ token is an ident followed
    // by ':' or '}', treat as struct init.
    if (this.at("punct", "{") && looksLikeStructInit(this.toks, this.i)) {
      this.bump(); // {
      const fields: NodeID[] = [];
      while (!this.at("punct", "}")) {
        const fname = this.expect("ident").text;
        let val: NodeID;
        if (this.match("punct", ":")) {
          val = this.parseExpr();
        } else {
          // shorthand: field name is both name and value
          val = ident(this.k, fname);
        }
        fields.push(cap(this.k, "field", [ident(this.k, fname), val]));
        if (!this.match("punct", ",")) break;
      }
      this.expect("punct", "}");
      return cap(this.k, "struct_init", [path, cap(this.k, "fields", fields)]);
    }
    if (segments.length === 1) {
      return ident(this.k, segments[0]!);
    }
    return path;
  }
}

function looksLikeStructInit(toks: Tok[], from: number): boolean {
  // toks[from] is '{'.  Peek through: if it's "{ ident : ..." or "{}",
  // it's a struct init. Anything else, it's a block expression.
  if (toks[from]?.text !== "{") return false;
  const next = toks[from + 1];
  if (!next) return false;
  if (next.kind === "punct" && next.text === "}") return true;
  if (next.kind === "ident") {
    const after = toks[from + 2];
    if (after && after.kind === "punct" && (after.text === ":" || after.text === ",")) {
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Emission — round-trip a captured Rust tree to source.
// ---------------------------------------------------------------------------

export function emitRust(k: Kernel, tree: NodeID): string {
  return emit(k, tree);
}

function emit(k: Kernel, n: NodeID): string {
  if (n.level === Level.TRIVIAL) {
    return emitTrivialNode(k, n);
  }
  const ctor = capturedCtor(k, n);
  const c = capturedChildren(k, n);
  switch (ctor) {
    case "program":
      return c.map((x) => emit(k, x)).join("\n");
    case "fn": {
      const name = emit(k, c[0]!);
      const generics = emit(k, c[1]!);
      const params = emit(k, c[2]!);
      const ret = emit(k, c[3]!);
      const body = emit(k, c[4]!);
      return `fn ${name}${generics}(${params}) -> ${ret} ${body}`;
    }
    case "generics": {
      if (c.length === 0) return "";
      const inner = c.map((x) => emit(k, x)).join(", ");
      return `<${inner}>`;
    }
    case "params":
      return c.map((x) => emit(k, x)).join(", ");
    case "param": {
      const name = emit(k, c[0]!);
      const ty = emit(k, c[1]!);
      const mut = c.length > 2 && capturedCtor(k, c[2]!) === "_mut" ? "mut " : "";
      const isInfer = capturedCtor(k, c[1]!) === "type_infer";
      return isInfer ? `${mut}${name}` : `${mut}${name}: ${ty}`;
    }
    case "type": {
      if (c.length === 0) return "()";
      const path = emit(k, c[0]!);
      if (c.length === 1) return path;
      return `${path}${emit(k, c[1]!)}`;
    }
    case "type_args": {
      const inner = c.map((x) => emit(k, x)).join(", ");
      return `<${inner}>`;
    }
    case "type_infer": return "_";
    case "tuple_type": return `(${c.map((x) => emit(k, x)).join(", ")})`;
    case "ref_type": {
      const inner = emit(k, c[0]!);
      const mut = c.length > 1 && capturedCtor(k, c[1]!) === "_mut" ? "mut " : "";
      return `&${mut}${inner}`;
    }
    case "path":
      return c.map((x) => emitTrivialNode(k, x)).join("::");
    case "block": {
      const parts = c.map((x) => {
        if (capturedCtor(k, x) === "tail") return emit(k, capturedChildren(k, x)[0]!);
        return emit(k, x);
      });
      return `{ ${parts.join(" ")} }`;
    }
    case "expr_stmt": return `${emit(k, c[0]!)};`;
    case "tail": return emit(k, c[0]!);
    case "return": return `return ${emit(k, c[0]!)};`;
    case "let": {
      const name = emit(k, c[0]!);
      const ty = c[1]!;
      const val = emit(k, c[2]!);
      const isMut = c.length > 3 && capturedCtor(k, c[3]!) === "_mut";
      const mut = isMut ? "mut " : "";
      if (capturedCtor(k, ty) === "type_infer") {
        return `let ${mut}${name} = ${val};`;
      }
      return `let ${mut}${name}: ${emit(k, ty)} = ${val};`;
    }
    case "if": {
      const cond = emit(k, c[0]!);
      const thenB = emit(k, c[1]!);
      const elseB = c[2]!;
      const elseCtor = capturedCtor(k, elseB);
      if (elseCtor === "unit" && capturedChildren(k, elseB).length === 0) {
        return `if ${cond} ${thenB}`;
      }
      return `if ${cond} ${thenB} else ${emit(k, elseB)}`;
    }
    case "match": {
      const scrut = emit(k, c[0]!);
      const arms = capturedChildren(k, c[1]!)
        .map((a) => {
          const ac = capturedChildren(k, a);
          return `${emit(k, ac[0]!)} => ${emit(k, ac[1]!)},`;
        })
        .join(" ");
      return `match ${scrut} { ${arms} }`;
    }
    case "arm": {
      return `${emit(k, c[0]!)} => ${emit(k, c[1]!)}`;
    }
    case "arms": return c.map((x) => emit(k, x)).join(", ");
    case "pat_wild": return "_";
    case "pat_int":
    case "pat_float":
    case "pat_str":
    case "pat_bool":
      return emit(k, c[0]!);
    case "pat_ident": return emit(k, c[0]!);
    case "pat_path": return emit(k, c[0]!);
    case "pat_variant": {
      const path = emit(k, c[0]!);
      const subs = capturedChildren(k, c[1]!).map((x) => emit(k, x)).join(", ");
      return `${path}(${subs})`;
    }
    case "pat_struct": {
      const path = emit(k, c[0]!);
      const fields = capturedChildren(k, c[1]!)
        .map((f) => {
          const fc = capturedChildren(k, f);
          return `${emit(k, fc[0]!)}: ${emit(k, fc[1]!)}`;
        })
        .join(", ");
      return `${path} { ${fields} }`;
    }
    case "closure": {
      const params = capturedChildren(k, c[0]!);
      const ps = params.map((p) => emit(k, p)).join(", ");
      const body = emit(k, c[1]!);
      if (params.length === 0) return `|| ${body}`;
      return `|${ps}| ${body}`;
    }
    case "call": {
      const f = emit(k, c[0]!);
      const args = capturedChildren(k, c[1]!).map((x) => emit(k, x)).join(", ");
      return `${f}(${args})`;
    }
    case "method": {
      const recv = emit(k, c[0]!);
      const name = emit(k, c[1]!);
      const args = capturedChildren(k, c[2]!).map((x) => emit(k, x)).join(", ");
      return `${recv}.${name}(${args})`;
    }
    case "field": {
      // overloaded ctor: in expression position c = [recv, ident]; in
      // struct-field position c = [ident, value/type].
      if (c.length === 2) {
        return `${emit(k, c[0]!)}.${emit(k, c[1]!)}`;
      }
      return c.map((x) => emit(k, x)).join(".");
    }
    case "index": return `${emit(k, c[0]!)}[${emit(k, c[1]!)}]`;
    case "try": return `${emit(k, c[0]!)}?`;
    case "args": return c.map((x) => emit(k, x)).join(", ");
    case "ident": return emitTrivialNode(k, c[0]!);
    case "int_lit": {
      const v = emitTrivialNode(k, c[0]!);
      const fmt = emitTrivialNode(k, c[1]!);
      // Suffix only emitted for non-default formats
      if (fmt === "i32") return v;
      return `${v}${fmt}`;
    }
    case "float_lit": {
      const v = emitTrivialNode(k, c[0]!);
      const fmt = emitTrivialNode(k, c[1]!);
      const hasDot = v.includes(".");
      const text = hasDot ? v : `${v}.0`;
      if (fmt === "f64") return text;
      return `${text}${fmt}`;
    }
    case "str": return JSON.stringify(emitTrivialNode(k, c[0]!));
    case "char_lit": return `'${emitTrivialNode(k, c[0]!)}'`;
    case "bool_lit": return emitTrivialNode(k, c[0]!);
    case "unit": return "()";
    case "paren": return `(${emit(k, c[0]!)})`;
    case "tuple": return `(${c.map((x) => emit(k, x)).join(", ")})`;
    case "array": return `[${c.map((x) => emit(k, x)).join(", ")}]`;
    case "vec": return `vec![${c.map((x) => emit(k, x)).join(", ")}]`;
    case "println": {
      const name = emit(k, c[0]!);
      const args = capturedChildren(k, c[1]!).map((x) => emit(k, x)).join(", ");
      return `${name}!(${args})`;
    }
    case "macro_call": {
      const name = emit(k, c[0]!);
      const delim = emitTrivialNode(k, c[1]!);
      const args = capturedChildren(k, c[2]!).map((x) => emit(k, x)).join(", ");
      const close = delim === "(" ? ")" : delim === "[" ? "]" : "}";
      return `${name}!${delim}${args}${close}`;
    }
    case "struct_init": {
      const path = emit(k, c[0]!);
      const fields = capturedChildren(k, c[1]!)
        .map((f) => {
          const fc = capturedChildren(k, f);
          return `${emit(k, fc[0]!)}: ${emit(k, fc[1]!)}`;
        })
        .join(", ");
      return `${path} { ${fields} }`;
    }
    case "struct": {
      const name = emit(k, c[0]!);
      const generics = emit(k, c[1]!);
      const fields = capturedChildren(k, c[2]!)
        .map((f) => {
          const fc = capturedChildren(k, f);
          return `${emit(k, fc[0]!)}: ${emit(k, fc[1]!)}`;
        })
        .join(", ");
      return `struct ${name}${generics} { ${fields} }`;
    }
    case "tuple_struct": {
      const name = emit(k, c[0]!);
      const generics = emit(k, c[1]!);
      const fields = capturedChildren(k, c[2]!).map((x) => emit(k, x)).join(", ");
      return `struct ${name}${generics}(${fields});`;
    }
    case "unit_struct": {
      const name = emit(k, c[0]!);
      const generics = emit(k, c[1]!);
      return `struct ${name}${generics};`;
    }
    case "enum": {
      const name = emit(k, c[0]!);
      const generics = emit(k, c[1]!);
      const vs = capturedChildren(k, c[2]!).map((v) => emit(k, v)).join(", ");
      return `enum ${name}${generics} { ${vs} }`;
    }
    case "variant_unit": return emit(k, c[0]!);
    case "variant_tuple": {
      const name = emit(k, c[0]!);
      const fields = capturedChildren(k, c[1]!).map((x) => emit(k, x)).join(", ");
      return `${name}(${fields})`;
    }
    case "variant_struct": {
      const name = emit(k, c[0]!);
      const fields = capturedChildren(k, c[1]!)
        .map((f) => {
          const fc = capturedChildren(k, f);
          return `${emit(k, fc[0]!)}: ${emit(k, fc[1]!)}`;
        })
        .join(", ");
      return `${name} { ${fields} }`;
    }
    // binary ops
    case "or":     return `(${emit(k, c[0]!)} || ${emit(k, c[1]!)})`;
    case "and":    return `(${emit(k, c[0]!)} && ${emit(k, c[1]!)})`;
    case "cmp":    return `(${emit(k, c[1]!)} ${emitTrivialNode(k, c[0]!)} ${emit(k, c[2]!)})`;
    case "bitor":  return `(${emit(k, c[0]!)} | ${emit(k, c[1]!)})`;
    case "bitxor": return `(${emit(k, c[0]!)} ^ ${emit(k, c[1]!)})`;
    case "bitand": return `(${emit(k, c[0]!)} & ${emit(k, c[1]!)})`;
    case "shl":    return `(${emit(k, c[0]!)} << ${emit(k, c[1]!)})`;
    case "shr":    return `(${emit(k, c[0]!)} >> ${emit(k, c[1]!)})`;
    case "add":    return `(${emit(k, c[0]!)} + ${emit(k, c[1]!)})`;
    case "sub":    return `(${emit(k, c[0]!)} - ${emit(k, c[1]!)})`;
    case "mul":    return `(${emit(k, c[0]!)} * ${emit(k, c[1]!)})`;
    case "div":    return `(${emit(k, c[0]!)} / ${emit(k, c[1]!)})`;
    case "mod":    return `(${emit(k, c[0]!)} % ${emit(k, c[1]!)})`;
    case "neg":    return `(-${emit(k, c[0]!)})`;
    case "not":    return `(!${emit(k, c[0]!)})`;
    case "ref":    return `(&${emit(k, c[0]!)})`;
    case "deref":  return `(*${emit(k, c[0]!)})`;
    case "_mut":   return "mut";
    case "_lifetimes": return c.map((x) => emitTrivialNode(k, x)).join(", ");
    case "subs":
    case "fields":
    case "variants":
      return c.map((x) => emit(k, x)).join(", ");
  }
  // Fallback for any captured ctor not specifically handled.
  return c.map((x) => emit(k, x)).join(" ");
}

function emitTrivialNode(k: Kernel, n: NodeID): string {
  if (n.level !== Level.TRIVIAL) {
    // Composite slipped into a trivial slot — recurse into emit.
    return emit(k, n);
  }
  switch (n.type) {
    case Triv.INT: {
      const u = n.inst >>> 0;
      const i = u > 0x7fffffff ? u - 0x100000000 : u;
      return String(i);
    }
    case Triv.STRING: return k.strs[n.inst] ?? "";
    case Triv.BOOL:   return n.inst ? "true" : "false";
    case Triv.NULL:   return "()";
    case Triv.INT8: {
      const u = n.inst >>> 0;
      return String(u > 0x7f ? (u | 0xffffff00) | 0 : u);
    }
    case Triv.INT16: {
      const u = n.inst >>> 0;
      return String(u > 0x7fff ? (u | 0xffff0000) | 0 : u);
    }
    case Triv.UINT8:  return String(n.inst & 0xff);
    case Triv.UINT16: return String(n.inst & 0xffff);
    case Triv.UINT32: return String(n.inst >>> 0);
    case Triv.INT64:  return String(k.decodeInt64(n.inst));
    case Triv.UINT64: return String(k.decodeUint64(n.inst));
    case Triv.FLOAT32: return String(k.decodeFloat32(n.inst));
    case Triv.FLOAT64: return String(k.decodeFloat64(n.inst));
    default: return `<trivial:${n.type}:${n.inst}>`;
  }
}

// ---------------------------------------------------------------------------
// Evaluator — tree-walking interpreter over the captured recipe tree.
// Implements enough surface to evaluate fib-style recipes and exercise
// match arms.
// ---------------------------------------------------------------------------

type RV =
  | { kind: "i64"; v: bigint }
  | { kind: "i32"; v: number }
  | { kind: "f64"; v: number }
  | { kind: "f32"; v: number }
  | { kind: "u64"; v: bigint }
  | { kind: "u32"; v: number }
  | { kind: "bool"; v: boolean }
  | { kind: "str"; v: string }
  | { kind: "char"; v: string }
  | { kind: "unit" }
  | { kind: "tuple"; items: RV[] }
  | { kind: "array"; items: RV[] }
  | { kind: "vec"; items: RV[] }
  | { kind: "struct"; name: string; fields: Map<string, RV> }
  | { kind: "variant"; ty: string; ctor: string; args: RV[] }
  | { kind: "closure"; params: string[]; body: NodeID; env: Env }
  | { kind: "fn"; node: NodeID };

class Env {
  private parent: Env | null;
  private scope = new Map<string, RV>();
  constructor(parent: Env | null = null) { this.parent = parent; }
  lookup(name: string): RV | undefined {
    if (this.scope.has(name)) return this.scope.get(name);
    return this.parent ? this.parent.lookup(name) : undefined;
  }
  define(name: string, v: RV): void { this.scope.set(name, v); }
  child(): Env { return new Env(this); }
}

export function evalRust(
  k: Kernel,
  programOrExpr: NodeID,
  entryName?: string,
  args: RV[] = [],
): RV {
  const env = new Env();
  // Collect top-level fns into env
  if (capturedCtor(k, programOrExpr) === "program") {
    for (const item of capturedChildren(k, programOrExpr)) {
      const ctor = capturedCtor(k, item);
      if (ctor === "fn") {
        const fname = trivialString(k, capturedChildren(k, item)[0]!);
        env.define(fname, { kind: "fn", node: item });
      }
    }
    if (entryName) {
      const fn = env.lookup(entryName);
      if (!fn) throw new Error(`evalRust: no fn "${entryName}"`);
      return callFn(k, env, fn, args);
    }
    return { kind: "unit" };
  }
  return evalExpr(k, env, programOrExpr);
}

function callFn(k: Kernel, env: Env, fn: RV, args: RV[]): RV {
  if (fn.kind === "fn") {
    const c = capturedChildren(k, fn.node);
    const params = capturedChildren(k, c[2]!);
    const body = c[4]!;
    const callEnv = env.child();
    if (params.length !== args.length) {
      throw new Error(`evalRust: arity mismatch (expected ${params.length}, got ${args.length})`);
    }
    for (let i = 0; i < params.length; i++) {
      const pname = trivialString(k, capturedChildren(k, params[i]!)[0]!);
      callEnv.define(pname, args[i]!);
    }
    return evalExpr(k, callEnv, body);
  }
  if (fn.kind === "closure") {
    const callEnv = fn.env.child();
    for (let i = 0; i < fn.params.length; i++) {
      callEnv.define(fn.params[i]!, args[i] ?? { kind: "unit" });
    }
    return evalExpr(k, callEnv, fn.body);
  }
  throw new Error(`evalRust: not callable (${fn.kind})`);
}

function evalExpr(k: Kernel, env: Env, n: NodeID): RV {
  if (n.level === Level.TRIVIAL) {
    return trivialToRV(k, n);
  }
  const ctor = capturedCtor(k, n);
  const c = capturedChildren(k, n);
  switch (ctor) {
    case "int_lit": {
      const fmt = trivialString(k, c[1]!);
      return numLitToRV(k, c[0]!, fmt);
    }
    case "float_lit": {
      const fmt = trivialString(k, c[1]!);
      return numLitToRV(k, c[0]!, fmt);
    }
    case "str": return { kind: "str", v: trivialString(k, c[0]!) };
    case "char_lit": return { kind: "char", v: trivialString(k, c[0]!) };
    case "bool_lit": return { kind: "bool", v: c[0]!.inst !== 0 };
    case "unit": return { kind: "unit" };
    case "ident": {
      const name = trivialString(k, c[0]!);
      const v = env.lookup(name);
      if (!v) throw new Error(`evalRust: unbound "${name}"`);
      return v;
    }
    case "paren": return evalExpr(k, env, c[0]!);
    case "tuple": return { kind: "tuple", items: c.map((x) => evalExpr(k, env, x)) };
    case "array": return { kind: "array", items: c.map((x) => evalExpr(k, env, x)) };
    case "vec":   return { kind: "vec", items: c.map((x) => evalExpr(k, env, x)) };
    case "block":  return evalBlock(k, env.child(), c);
    case "expr_stmt": { evalExpr(k, env, c[0]!); return { kind: "unit" }; }
    case "tail":   return evalExpr(k, env, c[0]!);
    case "return": return evalExpr(k, env, c[0]!);
    case "let": {
      const name = trivialString(k, capturedChildren(k, c[0]!)[0]!);
      const v = evalExpr(k, env, c[2]!);
      env.define(name, v);
      return { kind: "unit" };
    }
    case "if": {
      const cond = evalExpr(k, env, c[0]!);
      if (cond.kind !== "bool") {
        throw new Error(`evalRust: if condition not bool (${cond.kind})`);
      }
      return cond.v
        ? evalExpr(k, env, c[1]!)
        : evalExpr(k, env, c[2]!);
    }
    case "match": return evalMatch(k, env, c[0]!, c[1]!);
    case "closure": {
      const params = capturedChildren(k, c[0]!)
        .map((p) => trivialString(k, capturedChildren(k, p)[0]!));
      return { kind: "closure", params, body: c[1]!, env };
    }
    case "call": {
      const callee = c[0]!;
      const args = capturedChildren(k, c[1]!).map((x) => evalExpr(k, env, x));
      // Builtin call by ident name
      const calleeCtor = capturedCtor(k, callee);
      if (calleeCtor === "ident") {
        const name = trivialString(k, capturedChildren(k, callee)[0]!);
        const builtin = BUILTINS[name];
        if (builtin) return builtin(args);
        const fn = env.lookup(name);
        if (fn) return callFn(k, env, fn, args);
        throw new Error(`evalRust: unknown fn "${name}"`);
      }
      if (calleeCtor === "path") {
        const segs = capturedChildren(k, callee).map((s) => trivialString(k, s));
        const key = segs.join("::");
        const builtin = BUILTINS[key];
        if (builtin) return builtin(args);
        // Variant constructor: TypeName::Variant(...)
        if (segs.length === 2) {
          return {
            kind: "variant",
            ty: segs[0]!,
            ctor: segs[1]!,
            args,
          };
        }
        throw new Error(`evalRust: unknown path "${key}"`);
      }
      const f = evalExpr(k, env, callee);
      return callFn(k, env, f, args);
    }
    case "method": {
      const recv = evalExpr(k, env, c[0]!);
      const name = trivialString(k, capturedChildren(k, c[1]!)[0]!);
      const args = capturedChildren(k, c[2]!).map((x) => evalExpr(k, env, x));
      return applyMethod(recv, name, args);
    }
    case "field": {
      // expression-position field access
      if (c.length === 2 && capturedCtor(k, c[1]!) === "ident") {
        const recv = evalExpr(k, env, c[0]!);
        const name = trivialString(k, capturedChildren(k, c[1]!)[0]!);
        if (recv.kind === "struct") {
          const v = recv.fields.get(name);
          if (!v) throw new Error(`evalRust: no field "${name}"`);
          return v;
        }
        if (recv.kind === "tuple") {
          const idx = parseInt(name, 10);
          if (!Number.isNaN(idx) && idx < recv.items.length) {
            return recv.items[idx]!;
          }
        }
      }
      throw new Error(`evalRust: bad field access`);
    }
    case "index": {
      const recv = evalExpr(k, env, c[0]!);
      const idx = evalExpr(k, env, c[1]!);
      const i = idx.kind === "i32" || idx.kind === "u32"
        ? idx.v
        : idx.kind === "i64" || idx.kind === "u64"
          ? Number(idx.v)
          : 0;
      if (recv.kind === "array" || recv.kind === "vec") {
        return recv.items[i]!;
      }
      throw new Error(`evalRust: cannot index ${recv.kind}`);
    }
    case "add": case "sub": case "mul": case "div": case "mod":
    case "bitand": case "bitor": case "bitxor": case "shl": case "shr":
    case "and": case "or":
      return evalBinOp(k, env, ctor, c[0]!, c[1]!);
    case "cmp": {
      const op = trivialString(k, c[0]!);
      const a = evalExpr(k, env, c[1]!);
      const b = evalExpr(k, env, c[2]!);
      return { kind: "bool", v: rustCompare(op, a, b) };
    }
    case "neg": {
      const v = evalExpr(k, env, c[0]!);
      if (v.kind === "i64") return { kind: "i64", v: -v.v };
      if (v.kind === "i32") return { kind: "i32", v: -v.v | 0 };
      if (v.kind === "f64") return { kind: "f64", v: -v.v };
      if (v.kind === "f32") return { kind: "f32", v: Math.fround(-v.v) };
      throw new Error(`evalRust: neg on ${v.kind}`);
    }
    case "not": {
      const v = evalExpr(k, env, c[0]!);
      if (v.kind === "bool") return { kind: "bool", v: !v.v };
      if (v.kind === "i32") return { kind: "i32", v: ~v.v | 0 };
      if (v.kind === "i64") return { kind: "i64", v: ~v.v };
      throw new Error(`evalRust: ! on ${v.kind}`);
    }
    case "struct_init": {
      const pathSegs = capturedChildren(k, c[0]!).map((s) => trivialString(k, s));
      const name = pathSegs[pathSegs.length - 1]!;
      const fields = new Map<string, RV>();
      for (const f of capturedChildren(k, c[1]!)) {
        const fc = capturedChildren(k, f);
        const fname = trivialString(k, capturedChildren(k, fc[0]!)[0]!);
        fields.set(fname, evalExpr(k, env, fc[1]!));
      }
      return { kind: "struct", name, fields };
    }
    case "path": {
      const segs = capturedChildren(k, n).map((s) => trivialString(k, s));
      // Unit-variant access: TypeName::Variant
      if (segs.length === 2) {
        return { kind: "variant", ty: segs[0]!, ctor: segs[1]!, args: [] };
      }
      throw new Error(`evalRust: bare path "${segs.join("::")}"`);
    }
    case "println": {
      // Side-effect-free in tests; produce unit.
      return { kind: "unit" };
    }
  }
  throw new Error(`evalRust: unhandled ctor "${ctor}"`);
}

function evalBlock(k: Kernel, env: Env, children: readonly NodeID[]): RV {
  let last: RV = { kind: "unit" };
  for (const child of children) {
    const ctor = capturedCtor(k, child);
    if (ctor === "tail") {
      last = evalExpr(k, env, capturedChildren(k, child)[0]!);
    } else {
      last = evalExpr(k, env, child);
    }
  }
  return last;
}

function evalBinOp(k: Kernel, env: Env, op: string, an: NodeID, bn: NodeID): RV {
  // short-circuit
  if (op === "and") {
    const a = evalExpr(k, env, an);
    if (a.kind !== "bool") throw new Error("&& expects bool");
    if (!a.v) return { kind: "bool", v: false };
    const b = evalExpr(k, env, bn);
    if (b.kind !== "bool") throw new Error("&& expects bool");
    return { kind: "bool", v: b.v };
  }
  if (op === "or") {
    const a = evalExpr(k, env, an);
    if (a.kind !== "bool") throw new Error("|| expects bool");
    if (a.v) return { kind: "bool", v: true };
    const b = evalExpr(k, env, bn);
    if (b.kind !== "bool") throw new Error("|| expects bool");
    return { kind: "bool", v: b.v };
  }
  const a = evalExpr(k, env, an);
  const b = evalExpr(k, env, bn);
  return numericBinOp(op, a, b);
}

function numericBinOp(op: string, a: RV, b: RV): RV {
  const numA = toBig(a);
  const numB = toBig(b);
  if (numA !== null && numB !== null) {
    let r: bigint;
    switch (op) {
      case "add": r = numA + numB; break;
      case "sub": r = numA - numB; break;
      case "mul": r = numA * numB; break;
      case "div": r = numB === 0n ? 0n : numA / numB; break;
      case "mod": r = numB === 0n ? 0n : numA % numB; break;
      case "bitand": r = numA & numB; break;
      case "bitor":  r = numA | numB; break;
      case "bitxor": r = numA ^ numB; break;
      case "shl": r = numA << numB; break;
      case "shr": r = numA >> numB; break;
      default: throw new Error(`numericBinOp: unknown ${op}`);
    }
    // Preserve the wider kind. Prefer i64 if either is i64; else i32.
    const wider = (a.kind === "i64" || b.kind === "i64") ? "i64" : a.kind;
    if (wider === "i32" || wider === "u32") {
      return { kind: wider as "i32" | "u32", v: Number(BigInt.asIntN(32, r)) | 0 };
    }
    return { kind: "i64", v: BigInt.asIntN(64, r) };
  }
  // Floating
  const fA = toFloat(a);
  const fB = toFloat(b);
  if (fA !== null && fB !== null) {
    let r: number;
    switch (op) {
      case "add": r = fA + fB; break;
      case "sub": r = fA - fB; break;
      case "mul": r = fA * fB; break;
      case "div": r = fA / fB; break;
      case "mod": r = fA - Math.floor(fA / fB) * fB; break;
      default: throw new Error(`numericBinOp: ${op} not defined for floats`);
    }
    const k: "f32" | "f64" =
      (a.kind === "f32" || b.kind === "f32") ? "f32" : "f64";
    return { kind: k, v: k === "f32" ? Math.fround(r) : r };
  }
  throw new Error(`numericBinOp: incompatible (${a.kind}, ${b.kind})`);
}

function toBig(v: RV): bigint | null {
  if (v.kind === "i64" || v.kind === "u64") return v.v;
  if (v.kind === "i32" || v.kind === "u32") return BigInt(v.v);
  if (v.kind === "bool") return v.v ? 1n : 0n;
  return null;
}
function toFloat(v: RV): number | null {
  if (v.kind === "f32" || v.kind === "f64") return v.v;
  if (v.kind === "i32" || v.kind === "u32") return v.v;
  if (v.kind === "i64" || v.kind === "u64") return Number(v.v);
  return null;
}

function rustCompare(op: string, a: RV, b: RV): boolean {
  const numA = toBig(a);
  const numB = toBig(b);
  if (numA !== null && numB !== null) {
    switch (op) {
      case "==": return numA === numB;
      case "!=": return numA !== numB;
      case "<":  return numA < numB;
      case "<=": return numA <= numB;
      case ">":  return numA > numB;
      case ">=": return numA >= numB;
    }
  }
  const fA = toFloat(a);
  const fB = toFloat(b);
  if (fA !== null && fB !== null) {
    switch (op) {
      case "==": return fA === fB;
      case "!=": return fA !== fB;
      case "<":  return fA < fB;
      case "<=": return fA <= fB;
      case ">":  return fA > fB;
      case ">=": return fA >= fB;
    }
  }
  if (a.kind === "bool" && b.kind === "bool") {
    switch (op) {
      case "==": return a.v === b.v;
      case "!=": return a.v !== b.v;
    }
  }
  if (a.kind === "str" && b.kind === "str") {
    switch (op) {
      case "==": return a.v === b.v;
      case "!=": return a.v !== b.v;
      case "<":  return a.v < b.v;
      case "<=": return a.v <= b.v;
      case ">":  return a.v > b.v;
      case ">=": return a.v >= b.v;
    }
  }
  throw new Error(`rustCompare: ${op} on (${a.kind}, ${b.kind})`);
}

function evalMatch(k: Kernel, env: Env, scrutN: NodeID, armsN: NodeID): RV {
  const scrut = evalExpr(k, env, scrutN);
  for (const armN of capturedChildren(k, armsN)) {
    const ac = capturedChildren(k, armN);
    const bound = env.child();
    if (matchPattern(k, ac[0]!, scrut, bound)) {
      return evalExpr(k, bound, ac[1]!);
    }
  }
  throw new Error("evalRust: non-exhaustive match");
}

function matchPattern(k: Kernel, patN: NodeID, v: RV, env: Env): boolean {
  const ctor = capturedCtor(k, patN);
  const c = capturedChildren(k, patN);
  switch (ctor) {
    case "pat_wild": return true;
    case "pat_int": {
      const litChildren = capturedChildren(k, c[0]!);
      const fmt = trivialString(k, litChildren[1]!);
      const litRV = numLitToRV(k, litChildren[0]!, fmt);
      return rustCompare("==", litRV, v);
    }
    case "pat_float": {
      const litChildren = capturedChildren(k, c[0]!);
      const fmt = trivialString(k, litChildren[1]!);
      const litRV = numLitToRV(k, litChildren[0]!, fmt);
      return rustCompare("==", litRV, v);
    }
    case "pat_str": {
      const s = trivialString(k, capturedChildren(k, c[0]!)[0]!);
      return v.kind === "str" && v.v === s;
    }
    case "pat_bool": {
      const b = capturedChildren(k, c[0]!)[0]!.inst !== 0;
      return v.kind === "bool" && v.v === b;
    }
    case "pat_ident": {
      const name = trivialString(k, capturedChildren(k, c[0]!)[0]!);
      // Special-case wildcard via "_" already handled as pat_wild.
      env.define(name, v);
      return true;
    }
    case "pat_path": {
      const segs = capturedChildren(k, c[0]!).map((s) => trivialString(k, s));
      if (segs.length === 2 && v.kind === "variant") {
        return v.ty === segs[0] && v.ctor === segs[1] && v.args.length === 0;
      }
      return false;
    }
    case "pat_variant": {
      const segs = capturedChildren(k, c[0]!).map((s) => trivialString(k, s));
      const subs = capturedChildren(k, c[1]!);
      if (v.kind !== "variant") return false;
      const matchTy = segs.length < 2 || v.ty === segs[segs.length - 2];
      const matchCtor = v.ctor === segs[segs.length - 1];
      if (!matchTy || !matchCtor) return false;
      if (v.args.length !== subs.length) return false;
      for (let i = 0; i < subs.length; i++) {
        if (!matchPattern(k, subs[i]!, v.args[i]!, env)) return false;
      }
      return true;
    }
    case "pat_struct": {
      // Minimal — match name only, then per-field
      if (v.kind !== "struct") return false;
      const fields = capturedChildren(k, c[1]!);
      for (const f of fields) {
        const fc = capturedChildren(k, f);
        const fname = trivialString(k, capturedChildren(k, fc[0]!)[0]!);
        const fv = v.fields.get(fname);
        if (fv === undefined) return false;
        if (!matchPattern(k, fc[1]!, fv, env)) return false;
      }
      return true;
    }
  }
  return false;
}

function applyMethod(recv: RV, name: string, args: RV[]): RV {
  if (recv.kind === "vec" || recv.kind === "array") {
    switch (name) {
      case "len": return { kind: "i32", v: recv.items.length | 0 };
      case "push": {
        if (recv.kind !== "vec") throw new Error("push on array");
        recv.items.push(args[0]!);
        return { kind: "unit" };
      }
      case "is_empty": return { kind: "bool", v: recv.items.length === 0 };
    }
  }
  if (recv.kind === "str") {
    switch (name) {
      case "len": return { kind: "i32", v: recv.v.length | 0 };
      case "is_empty": return { kind: "bool", v: recv.v.length === 0 };
    }
  }
  throw new Error(`evalRust: unknown method "${name}" on ${recv.kind}`);
}

const BUILTINS: Record<string, (args: RV[]) => RV> = {
  "String::from": (args) => {
    const a = args[0];
    if (a && a.kind === "str") return { kind: "str", v: a.v };
    throw new Error("String::from: expected &str");
  },
  "println": () => ({ kind: "unit" }),
  "print": () => ({ kind: "unit" }),
};

function trivialString(k: Kernel, n: NodeID): string {
  if (n.level !== Level.TRIVIAL) {
    // It might be wrapped in an "ident" or "path" capture — drill in.
    const ctor = capturedCtor(k, n);
    const c = capturedChildren(k, n);
    if (ctor === "ident" || ctor === "_") return trivialString(k, c[0]!);
    throw new Error("trivialString: composite");
  }
  if (n.type !== Triv.STRING) {
    throw new Error(`trivialString: not string (type=${n.type})`);
  }
  return k.strs[n.inst] ?? "";
}

function trivialToRV(k: Kernel, n: NodeID): RV {
  switch (n.type) {
    case Triv.INT: return { kind: "i32", v: ((n.inst | 0) << 0) | 0 };
    case Triv.STRING: return { kind: "str", v: k.strs[n.inst] ?? "" };
    case Triv.BOOL: return { kind: "bool", v: n.inst !== 0 };
    case Triv.NULL: return { kind: "unit" };
    case Triv.INT8: {
      const u = n.inst >>> 0;
      return { kind: "i32", v: (u > 0x7f ? (u | 0xffffff00) | 0 : u) | 0 };
    }
    case Triv.INT16: {
      const u = n.inst >>> 0;
      return { kind: "i32", v: (u > 0x7fff ? (u | 0xffff0000) | 0 : u) | 0 };
    }
    case Triv.UINT8:  return { kind: "u32", v: n.inst & 0xff };
    case Triv.UINT16: return { kind: "u32", v: n.inst & 0xffff };
    case Triv.UINT32: return { kind: "u32", v: n.inst >>> 0 };
    case Triv.INT64: return { kind: "i64", v: k.decodeInt64(n.inst) };
    case Triv.UINT64: return { kind: "u64", v: k.decodeUint64(n.inst) };
    case Triv.FLOAT32: return { kind: "f32", v: k.decodeFloat32(n.inst) };
    case Triv.FLOAT64: return { kind: "f64", v: k.decodeFloat64(n.inst) };
  }
  throw new Error(`trivialToRV: unknown type ${n.type}`);
}

function numLitToRV(k: Kernel, valNode: NodeID, fmt: string): RV {
  switch (fmt) {
    case "i8": case "i16": case "i32": case "isize":
      return { kind: "i32", v: signedFromTrivial(k, valNode) | 0 };
    case "i64": case "i128":
      if (valNode.type === Triv.INT64) {
        return { kind: "i64", v: k.decodeInt64(valNode.inst) };
      }
      return { kind: "i64", v: BigInt(signedFromTrivial(k, valNode)) };
    case "u8": case "u16": case "u32": case "usize":
      return { kind: "u32", v: unsignedFromTrivial(k, valNode) >>> 0 };
    case "u64": case "u128":
      if (valNode.type === Triv.UINT64) {
        return { kind: "u64", v: k.decodeUint64(valNode.inst) };
      }
      return { kind: "u64", v: BigInt(unsignedFromTrivial(k, valNode)) };
    case "f32":
      return { kind: "f32", v: floatFromTrivial(k, valNode) };
    case "f64":
      return { kind: "f64", v: floatFromTrivial(k, valNode) };
  }
  return trivialToRV(k, valNode);
}

function signedFromTrivial(k: Kernel, n: NodeID): number {
  if (n.level !== Level.TRIVIAL) throw new Error("signedFromTrivial: composite");
  switch (n.type) {
    case Triv.INT: {
      const u = n.inst >>> 0;
      return u > 0x7fffffff ? u - 0x100000000 : u;
    }
    case Triv.INT8: {
      const u = n.inst >>> 0;
      return u > 0x7f ? (u | 0xffffff00) | 0 : u;
    }
    case Triv.INT16: {
      const u = n.inst >>> 0;
      return u > 0x7fff ? (u | 0xffff0000) | 0 : u;
    }
    case Triv.INT64: return Number(k.decodeInt64(n.inst));
  }
  return n.inst | 0;
}

function unsignedFromTrivial(k: Kernel, n: NodeID): number {
  if (n.level !== Level.TRIVIAL) throw new Error("unsignedFromTrivial: composite");
  switch (n.type) {
    case Triv.INT: return n.inst >>> 0;
    case Triv.UINT8: return n.inst & 0xff;
    case Triv.UINT16: return n.inst & 0xffff;
    case Triv.UINT32: return n.inst >>> 0;
    case Triv.UINT64: return Number(k.decodeUint64(n.inst));
  }
  return n.inst >>> 0;
}

function floatFromTrivial(k: Kernel, n: NodeID): number {
  if (n.level !== Level.TRIVIAL) throw new Error("floatFromTrivial: composite");
  if (n.type === Triv.FLOAT64) return k.decodeFloat64(n.inst);
  if (n.type === Triv.FLOAT32) return k.decodeFloat32(n.inst);
  if (n.type === Triv.INT) {
    const u = n.inst >>> 0;
    return u > 0x7fffffff ? u - 0x100000000 : u;
  }
  if (n.type === Triv.INT64) return Number(k.decodeInt64(n.inst));
  return n.inst;
}

// ---------------------------------------------------------------------------
// Public: parseRust, language registration.
// ---------------------------------------------------------------------------

export function parseRust(k: Kernel, source: string): NodeID {
  return Parser.parseSource(k, source);
}

export function parseRustExpr(k: Kernel, source: string): NodeID {
  return Parser.parseExpression(k, source);
}

// Build a Language cell carrying Rust's grammar and emission template.
//
// The grammar declares the surface shape (tokens, keywords, ctor
// names) for cross-language equivalence. The runtime parser lives in
// parseRust(); the grammar cell is what makes "this kernel speaks
// Rust" content-addressable.
export function registerRustLanguage(
  k: Kernel,
  fmts?: FormatLibrary,
): Language {
  const lib = fmts ?? buildFormatLibrary(k);

  // Toy grammar (vertical-slice): enumerates the surface tokens we
  // ingest. The captured ctor names match what parseRust() emits, so
  // any future generic walker (Pratt-aware) reads the same names.
  const numTok = gCapture(k, "int_lit", gTokenClass(k, "number"));
  const idTok = gCapture(k, "ident", gTokenClass(k, "ident"));
  const kwAlt = gAlt(k,
    gLiteral(k, "fn"), gLiteral(k, "let"), gLiteral(k, "mut"),
    gLiteral(k, "if"), gLiteral(k, "else"), gLiteral(k, "match"),
    gLiteral(k, "return"), gLiteral(k, "true"), gLiteral(k, "false"),
    gLiteral(k, "struct"), gLiteral(k, "enum"),
  );
  const punctAlt = gAlt(k,
    gLiteral(k, "->"), gLiteral(k, "=>"), gLiteral(k, "::"),
    gLiteral(k, "=="), gLiteral(k, "!="),
    gLiteral(k, "<="), gLiteral(k, ">="),
    gLiteral(k, "&&"), gLiteral(k, "||"),
    gLiteral(k, "+"), gLiteral(k, "-"), gLiteral(k, "*"),
    gLiteral(k, "/"), gLiteral(k, "%"),
    gLiteral(k, "&"), gLiteral(k, "|"), gLiteral(k, "^"),
    gLiteral(k, "<"), gLiteral(k, ">"), gLiteral(k, "!"),
    gLiteral(k, "("), gLiteral(k, ")"),
    gLiteral(k, "{"), gLiteral(k, "}"),
    gLiteral(k, "["), gLiteral(k, "]"),
    gLiteral(k, ","), gLiteral(k, ";"), gLiteral(k, ":"),
    gLiteral(k, "."), gLiteral(k, "="),
  );
  const tokenRule = gAlt(k, numTok, kwAlt, idTok, punctAlt);
  const ingestionGrammar = gCapture(k, "program", gPlus(k, tokenRule));

  // Emission template: join children with spaces — round-trip is
  // handled by emitRust() for richer formatting. The cell-resident
  // template is the minimal-correct fallback.
  const emissionTemplate = eJoin(k, " ", 0, -1);

  // Numeric defaults — task spec maps i32→INT32, i64→INT64, f32→FP32,
  // f64→FP64, u* to matching unsigned format-recipes.
  const numericDefaults = new Map<string, FormatRecipe>([
    ["i8",  lib.INT8],
    ["i16", lib.INT16],
    ["i32", lib.INT32],
    ["i64", lib.INT64],
    ["isize", lib.INT64],
    ["u8",  lib.UINT8],
    ["u16", lib.UINT16],
    ["u32", lib.UINT32],
    ["u64", lib.UINT64],
    ["usize", lib.UINT64],
    ["f32", lib.FP32],
    ["f64", lib.FP64],
  ]);

  // Stdlib bindings — surface names route to placeholder cells. The
  // cells themselves are interned strings here (the bindings table
  // wants NodeIDs, and the canonical cells for "Vec::len" etc. live
  // in the wider substrate; for v0 we record the name and let the
  // post-parse pass resolve).
  const stdlibBindings = new Map<string, NodeID>([
    ["Vec::len", k.internString("Vec::len")],
    ["Vec::push", k.internString("Vec::push")],
    ["Result", k.internString("Result")],
    ["Option", k.internString("Option")],
    ["std::collections::HashMap", k.internString("std::collections::HashMap")],
    ["println!", k.internString("println!")],
    ["String::from", k.internString("String::from")],
  ]);

  return registerLanguage(k, {
    name: "rust",
    version: "1.83",
    ingestionGrammar,
    emissionTemplate,
    stdlibBindings,
    numericDefaults,
  });
}
