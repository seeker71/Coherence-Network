// S-expression bootstrap reader — `.fk` text → recipe tree.
//
// Surface vocabulary matches the Go/Rust kernels exactly via buildVerb.
// Verb names (`add`, `sub`, `mul`, `eq`, `le`, ...) intern to specific
// RBasic recipes; everything else is a function call.
//
// Operator forms (`+`, `-`, `<`, `<=`, ...) are also accepted as aliases
// so the playground stays ergonomic. The interned NodeIDs are identical.

import {
  Kernel,
  Level,
  mathInst,
  RBasic,
  RBlock,
  RCmp,
  RCond,
  RLogic,
  RMatch,
  RMath,
  RMathWidth,
  Triv,
  type NodeID,
} from "./kernel.ts";

interface Token {
  kind: "lparen" | "rparen" | "int" | "float" | "str" | "ident";
  text: string;
  pos: number;
}

function tokenize(src: string): Token[] {
  const toks: Token[] = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (c === undefined) break;
    if (c === " " || c === "\t" || c === "\n" || c === "\r") {
      i++;
      continue;
    }
    if (c === ";") {
      while (i < src.length && src[i] !== "\n") i++;
      continue;
    }
    if (c === "(") {
      toks.push({ kind: "lparen", text: "(", pos: i });
      i++;
      continue;
    }
    if (c === ")") {
      toks.push({ kind: "rparen", text: ")", pos: i });
      i++;
      continue;
    }
    if (c === '"' || c === "'") {
      const quote = c;
      const start = i;
      i++;
      let s = "";
      while (i < src.length && src[i] !== quote) {
        if (src[i] === "\\" && i + 1 < src.length) {
          const next = src[i + 1];
          if (next === "n") s += "\n";
          else if (next === "r") s += "\r";
          else if (next === "t") s += "\t";
          else if (next === "\\") s += "\\";
          else if (next === '"') s += '"';
          else if (next === "'") s += "'";
          else s += next ?? "";
          i += 2;
          continue;
        }
        s += src[i];
        i++;
      }
      if (src[i] !== quote) throw new Error(`unterminated string at ${start}`);
      i++;
      toks.push({ kind: "str", text: s, pos: start });
      continue;
    }
    const start = i;
    while (i < src.length) {
      const ch = src[i];
      if (ch === undefined) break;
      if (
        ch === " " ||
        ch === "\t" ||
        ch === "\n" ||
        ch === "\r" ||
        ch === "(" ||
        ch === ")" ||
        ch === ";"
      )
        break;
      i++;
    }
    const text = src.slice(start, i);
    if (/^-?\d+$/.test(text)) {
      toks.push({ kind: "int", text, pos: start });
    } else if (/^-?\d+\.\d+(e-?\d+)?$/i.test(text) || /^-?\d+e-?\d+$/i.test(text)) {
      toks.push({ kind: "float", text, pos: start });
    } else {
      toks.push({ kind: "ident", text, pos: start });
    }
  }
  return toks;
}

interface ParseState {
  toks: Token[];
  i: number;
}

function peek(s: ParseState): Token | undefined {
  return s.toks[s.i];
}

function consume(s: ParseState): Token {
  const t = s.toks[s.i];
  if (t === undefined) throw new Error("unexpected end of input");
  s.i++;
  return t;
}

export function readForm(k: Kernel, src: string): NodeID {
  const s: ParseState = { toks: tokenize(src), i: 0 };
  const node = readOne(k, s);
  if (s.i !== s.toks.length) {
    const t = s.toks[s.i];
    throw new Error(`extra tokens after expression at ${t?.pos}`);
  }
  return node;
}

export function readAll(k: Kernel, src: string): NodeID {
  const s: ParseState = { toks: tokenize(src), i: 0 };
  const forms: NodeID[] = [];
  while (s.i < s.toks.length) {
    forms.push(readOne(k, s));
  }
  if (forms.length === 0) return k.internTrivialNull();
  if (forms.length === 1) return forms[0]!;
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.DO },
    forms,
  );
}

function readOne(k: Kernel, s: ParseState): NodeID {
  const t = consume(s);
  if (t.kind === "int") {
    return k.internTrivialInt(parseInt(t.text, 10));
  }
  if (t.kind === "float") {
    return k.internTrivialFloat64(parseFloat(t.text));
  }
  if (t.kind === "str") {
    return k.internString(t.text);
  }
  if (t.kind === "ident") {
    if (t.text === "true") return k.internTrivialBool(true);
    if (t.text === "false") return k.internTrivialBool(false);
    if (t.text === "null") return k.internTrivialNull();
    // Bare identifier: wrap in IDENT recipe; the walker resolves through frame.
    return k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 1 },
      [k.internString(t.text)],
    );
  }
  if (t.kind === "lparen") {
    return readList(k, s);
  }
  throw new Error(`unexpected token ${t.kind} at ${t.pos}`);
}

function readList(k: Kernel, s: ParseState): NodeID {
  const head = peek(s);
  if (head === undefined) throw new Error("unterminated list");
  if (head.kind === "rparen") {
    consume(s);
    return k.internTrivialNull();
  }
  // Special forms with non-uniform child shapes (let, defn) need to peek
  // at the verb before reading children.
  if (head.kind === "ident") {
    const verb = head.text;
    if (verb === "let") {
      consume(s);
      return readLet(k, s);
    }
    if (verb === "defn") {
      consume(s);
      return readDefn(k, s);
    }
    if (verb === "alias") {
      consume(s);
      return readAlias(k, s);
    }
    if (verb === "if") {
      consume(s);
      const kids = readChildrenUntilRparen(k, s);
      if (kids.length === 2) {
        return k.intern(
          { pkg: 1, level: Level.BASIC, type: RBasic.COND, inst: RCond.IF_THEN },
          kids,
        );
      }
      if (kids.length === 3) {
        return k.intern(
          {
            pkg: 1,
            level: Level.BASIC,
            type: RBasic.COND,
            inst: RCond.IF_THEN_ELSE,
          },
          kids,
        );
      }
      throw new Error("if: need 2 or 3 args");
    }
    // Verb forms: consume the verb, read remaining children, dispatch
    // through buildVerb.
    consume(s);
    const kids = readChildrenUntilRparen(k, s);
    return buildVerb(k, verb, kids);
  }
  // (expr expr...) with no leading ident — function call where first item
  // is the callee expression
  const callee = readOne(k, s);
  const args = readChildrenUntilRparen(k, s);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
    [callee, ...args],
  );
}

function readChildrenUntilRparen(k: Kernel, s: ParseState): NodeID[] {
  const out: NodeID[] = [];
  while (true) {
    const t = peek(s);
    if (t === undefined) throw new Error("unterminated list");
    if (t.kind === "rparen") {
      consume(s);
      return out;
    }
    out.push(readOne(k, s));
  }
}

// (let <name> <value>) — interns name as a bare string trivial so the
// walker reads NameID directly from the inst slot (no IDENT recipe).
function readLet(k: Kernel, s: ParseState): NodeID {
  const nameTok = consume(s);
  if (nameTok.kind !== "ident")
    throw new Error("let: name must be identifier");
  const value = readOne(k, s);
  const close = consume(s);
  if (close.kind !== "rparen") throw new Error("let: expected )");
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(nameTok.text),
  };
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.LET },
    [nameTrivial, value],
  );
}

// (defn <name> (<params>...) <body>) — names and params get repackaged as
// bare string trivials so the walker reads NameID via inst (matches Go).
//
// Extended surface (additive; back-compat preserved):
//
//   (defn foo (a b) <body>)                           — untyped, original
//   (defn foo (a:i32 b:i32) <body>)                   — strict-typed params
//   (defn foo (a:i32 b:i32) :ret i32 <body>)          — strict-typed + return
//   (defn foo :tparams (T:Format U:Format)            — parametric: T,U bound
//                (a:T b:T) :ret T <body>)               to FormatRecipe-class
//
// A type annotation `name:type` is one ident token (the tokenizer doesn't
// split on ':'). The walker dispatches on the FNDEF inst slot:
//   inst = 1  → original 3-child shape (back-compat: [name, params, body])
//   inst = 2  → typed/parametric 4-child shape:
//                 [name, params, body, fnmeta] where fnmeta carries the
//                 type-parameter list, the per-arg type slots, and the
//                 return-type slot.  See parametric.ts for the layout.
function readDefn(k: Kernel, s: ParseState): NodeID {
  const nameTok = consume(s);
  if (nameTok.kind !== "ident") throw new Error("defn: name must be identifier");

  // Optional :tparams (T:C ...) — type parameters with constraints.
  let typeParamPairs: { name: string; constraint: string }[] = [];
  let next = peek(s);
  if (next?.kind === "ident" && next.text === ":tparams") {
    consume(s);
    const lp = consume(s);
    if (lp.kind !== "lparen") throw new Error("defn: :tparams expects (");
    while (true) {
      const tp = peek(s);
      if (tp === undefined) throw new Error("defn: unterminated :tparams");
      if (tp.kind === "rparen") {
        consume(s);
        break;
      }
      if (tp.kind !== "ident")
        throw new Error("defn: :tparams entries must be ident");
      consume(s);
      // Accept `T` or `T:Constraint`. Default constraint is "Format".
      const colon = tp.text.indexOf(":");
      if (colon < 0) {
        typeParamPairs.push({ name: tp.text, constraint: "Format" });
      } else {
        typeParamPairs.push({
          name: tp.text.slice(0, colon),
          constraint: tp.text.slice(colon + 1) || "Format",
        });
      }
    }
  }

  const lparen = consume(s);
  if (lparen.kind !== "lparen") throw new Error("defn: expected ( for params");
  const paramTrivials: NodeID[] = [];
  const paramTypes: (string | null)[] = [];
  let anyTyped = false;
  while (true) {
    const t = peek(s);
    if (t === undefined) throw new Error("defn: unterminated param list");
    if (t.kind === "rparen") {
      consume(s);
      break;
    }
    if (t.kind !== "ident") throw new Error("defn: params must be identifiers");
    consume(s);
    const colon = t.text.indexOf(":");
    let paramName: string;
    let paramType: string | null;
    if (colon < 0) {
      paramName = t.text;
      paramType = null;
    } else {
      paramName = t.text.slice(0, colon);
      paramType = t.text.slice(colon + 1);
      anyTyped = true;
    }
    paramTrivials.push({
      pkg: 1,
      level: Level.TRIVIAL,
      type: Triv.STRING,
      inst: k.internName(paramName),
    });
    paramTypes.push(paramType);
  }

  // Optional :ret <type-ident>
  let retType: string | null = null;
  next = peek(s);
  if (next?.kind === "ident" && next.text === ":ret") {
    consume(s);
    const rt = consume(s);
    if (rt.kind !== "ident") throw new Error("defn: :ret expects ident");
    retType = rt.text;
  }

  const body = readOne(k, s);
  const close = consume(s);
  if (close.kind !== "rparen") throw new Error("defn: expected )");
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(nameTok.text),
  };
  const paramsBlock = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    paramTrivials,
  );

  const typed = anyTyped || retType !== null || typeParamPairs.length > 0;
  if (!typed) {
    // Back-compat: original 3-child FNDEF shape, inst=1.
    return k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 1 },
      [nameTrivial, paramsBlock, body],
    );
  }

  // Typed shape: inst=2, 4 children [name, params, body, fnmeta].
  // fnmeta is a SEQUENCE of three SEQUENCEs:
  //   tparams-seq: [name-trivial, constraint-trivial, ...]
  //   ptypes-seq:  [type-trivial-or-null, ...] (one per param)
  //   ret-seq:     [type-trivial] or [] when no return type
  const tparamsChildren: NodeID[] = [];
  for (const tp of typeParamPairs) {
    tparamsChildren.push(k.internString(tp.name));
    tparamsChildren.push(k.internString(tp.constraint));
  }
  const tparamsSeq = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    tparamsChildren,
  );
  const ptypesChildren: NodeID[] = paramTypes.map((t) =>
    t === null ? k.internTrivialNull() : k.internString(t),
  );
  const ptypesSeq = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    ptypesChildren,
  );
  const retSeq = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    retType === null ? [] : [k.internString(retType)],
  );
  const fnmeta = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    [tparamsSeq, ptypesSeq, retSeq],
  );
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 2 },
    [nameTrivial, paramsBlock, body, fnmeta],
  );
}

// (alias <name> <value-expr>) — interns an ALIAS recipe whose children are
// the name-string-trivial and the target node. Read at compile time via
// resolveAlias(); not walked at run time.
function readAlias(k: Kernel, s: ParseState): NodeID {
  const nameTok = consume(s);
  if (nameTok.kind !== "ident")
    throw new Error("alias: name must be identifier");
  const target = readOne(k, s);
  const close = consume(s);
  if (close.kind !== "rparen") throw new Error("alias: expected )");
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(nameTok.text),
  };
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.ALIAS, inst: 1 },
    [nameTrivial, target],
  );
}

// buildVerb — map a surface verb to its RBasic recipe. Matches Go/Rust
// kernel's buildVerb exactly so the same source produces the same NodeIDs.
function buildVerb(k: Kernel, verb: string, args: NodeID[]): NodeID {
  switch (verb) {
    case "do":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.DO },
        args,
      );
    case "seq":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
        args,
      );
    // Math
    case "add":
    case "+":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: RMath.PLUS },
        args,
      );
    case "sub":
    case "-":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: RMath.MINUS },
        args,
      );
    case "mul":
    case "*":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: RMath.MUL },
        args,
      );
    case "div":
    case "/":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: RMath.DIV },
        args,
      );
    case "mod":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: RMath.MOD },
        args,
      );
    // Float64 math
    case "addf":
    case "+.":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: mathInst(RMathWidth.F64, RMath.PLUS) },
        args,
      );
    case "subf":
    case "-.":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: mathInst(RMathWidth.F64, RMath.MINUS) },
        args,
      );
    case "mulf":
    case "*.":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: mathInst(RMathWidth.F64, RMath.MUL) },
        args,
      );
    case "divf":
    case "/.":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: mathInst(RMathWidth.F64, RMath.DIV) },
        args,
      );
    // Int64 math
    case "addq":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: mathInst(RMathWidth.I64, RMath.PLUS) },
        args,
      );
    case "subq":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: mathInst(RMathWidth.I64, RMath.MINUS) },
        args,
      );
    case "mulq":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: mathInst(RMathWidth.I64, RMath.MUL) },
        args,
      );
    // Compare
    case "eq":
    case "==":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst: RCmp.EQ },
        args,
      );
    case "ne":
    case "!=":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst: RCmp.NE },
        args,
      );
    case "lt":
    case "<":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst: RCmp.LT },
        args,
      );
    case "le":
    case "<=":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst: RCmp.LE },
        args,
      );
    case "gt":
    case ">":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst: RCmp.GT },
        args,
      );
    case "ge":
    case ">=":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst: RCmp.GE },
        args,
      );
    // Logic
    case "and":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: RLogic.AND },
        args,
      );
    case "or":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: RLogic.OR },
        args,
      );
    case "not":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: RLogic.NOT },
        args,
      );
    case "match":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATCH, inst: RMatch.SWITCH },
        args,
      );
    case "list":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 1 },
        args,
      );
    case "params":
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
        args,
      );
    default: {
      // Function call: bare-string-trivial callee, then args.
      const nameTrivial: NodeID = {
        pkg: 1,
        level: Level.TRIVIAL,
        type: Triv.STRING,
        inst: k.internName(verb),
      };
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 1 },
        [nameTrivial, ...args],
      );
    }
  }
}
