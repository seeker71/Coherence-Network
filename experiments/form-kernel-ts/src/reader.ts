// S-expression bootstrap reader — `.fk` text → recipe tree.
//
// Syntax recognized in v0:
//
//   atoms:         123 -45 "string" true false null ident
//   forms:         (op arg1 arg2 ...)
//   math ops:      + - * / mod
//   compare ops:   < <= > >= == !=
//   logic ops:     and or not
//   special:       (if c t e)  (do e1 e2 ...)  (defn name (p1 p2) body)
//                  (list e1 e2 ...)
//   call:          (ident arg1 ...)  — when ident resolves to a closure
//
// Aligned with Go/Rust kernel readers. Same source text ⇒ same NodeIDs.

import {
  Kernel,
  RBasic,
  RBlock,
  RCmp,
  RCond,
  RLogic,
  RMath,
  Triv,
  Level,
  type NodeID,
} from "./kernel.ts";

interface Token {
  kind: "lparen" | "rparen" | "int" | "str" | "ident";
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
      // line comment to end of line
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
      i++; // consume closing quote
      toks.push({ kind: "str", text: s, pos: start });
      continue;
    }
    // ident or number
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

// readForm — read one S-expression atom or list and intern as recipe.
export function readForm(k: Kernel, src: string): NodeID {
  const s: ParseState = { toks: tokenize(src), i: 0 };
  const node = readOne(k, s);
  // Allow trailing whitespace only.
  if (s.i !== s.toks.length) {
    const t = s.toks[s.i];
    throw new Error(`extra tokens after expression at ${t?.pos}`);
  }
  return node;
}

// readAll — read a sequence of top-level forms, wrap them in a BLOCK.
// This is what file reading uses.
export function readAll(k: Kernel, src: string): NodeID {
  const s: ParseState = { toks: tokenize(src), i: 0 };
  const forms: NodeID[] = [];
  while (s.i < s.toks.length) {
    forms.push(readOne(k, s));
  }
  if (forms.length === 0) return k.internTrivialNull();
  if (forms.length === 1 && forms[0] !== undefined) return forms[0];
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
  if (t.kind === "str") {
    return k.internString(t.text);
  }
  if (t.kind === "ident") {
    if (t.text === "true") return k.internTrivialBool(true);
    if (t.text === "false") return k.internTrivialBool(false);
    if (t.text === "null") return k.internTrivialNull();
    // bare identifier — wrap in IDENT recipe so the walker resolves it
    // through the frame, not as a string literal
    return k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
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
  if (head.kind !== "ident") {
    // (expr expr ...) with no leading op → treat as function call where
    // first item is the callee
    return readFnCall(k, s);
  }

  switch (head.text) {
    case "+":
    case "-":
    case "*":
    case "/":
    case "mod":
      return readMath(k, s);
    case "<":
    case "<=":
    case ">":
    case ">=":
    case "==":
    case "!=":
      return readCompare(k, s);
    case "and":
    case "or":
    case "not":
      return readLogic(k, s);
    case "if":
      return readIf(k, s);
    case "do":
      return readDo(k, s);
    case "defn":
      return readDefn(k, s);
    case "list":
      return readListForm(k, s);
    default:
      return readFnCall(k, s);
  }
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

function readMath(k: Kernel, s: ParseState): NodeID {
  const opTok = consume(s);
  const opMap: Record<string, number> = {
    "+": RMath.PLUS,
    "-": RMath.MINUS,
    "*": RMath.MUL,
    "/": RMath.DIV,
    "mod": RMath.MOD,
  };
  const op = opMap[opTok.text];
  if (op === undefined) throw new Error(`unknown math op ${opTok.text}`);
  const kids = readChildrenUntilRparen(k, s);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: op },
    kids,
  );
}

function readCompare(k: Kernel, s: ParseState): NodeID {
  const opTok = consume(s);
  const opMap: Record<string, number> = {
    "<": RCmp.LT,
    "<=": RCmp.LE,
    ">": RCmp.GT,
    ">=": RCmp.GE,
    "==": RCmp.EQ,
    "!=": RCmp.NE,
  };
  const op = opMap[opTok.text];
  if (op === undefined) throw new Error(`unknown compare op ${opTok.text}`);
  const kids = readChildrenUntilRparen(k, s);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst: op },
    kids,
  );
}

function readLogic(k: Kernel, s: ParseState): NodeID {
  const opTok = consume(s);
  const opMap: Record<string, number> = {
    "and": RLogic.AND,
    "or": RLogic.OR,
    "not": RLogic.NOT,
  };
  const op = opMap[opTok.text];
  if (op === undefined) throw new Error(`unknown logic op ${opTok.text}`);
  const kids = readChildrenUntilRparen(k, s);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: op },
    kids,
  );
}

function readIf(k: Kernel, s: ParseState): NodeID {
  consume(s); // "if"
  const kids = readChildrenUntilRparen(k, s);
  if (kids.length !== 3) throw new Error("if needs 3 args (cond, then, else)");
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.COND, inst: RCond.IF },
    kids,
  );
}

function readDo(k: Kernel, s: ParseState): NodeID {
  consume(s); // "do"
  const kids = readChildrenUntilRparen(k, s);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.DO },
    kids,
  );
}

// (defn name (p1 p2 ...) body)
function readDefn(k: Kernel, s: ParseState): NodeID {
  consume(s); // "defn"
  const nameTok = consume(s);
  if (nameTok.kind !== "ident")
    throw new Error("defn: name must be identifier");
  // parameters list
  const lparen = consume(s);
  if (lparen.kind !== "lparen")
    throw new Error("defn: expected ( for parameter list");
  const params: NodeID[] = [];
  while (true) {
    const t = peek(s);
    if (t === undefined) throw new Error("defn: unterminated parameter list");
    if (t.kind === "rparen") {
      consume(s);
      break;
    }
    if (t.kind !== "ident")
      throw new Error("defn: parameters must be identifiers");
    consume(s);
    params.push(
      k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
        [k.internString(t.text)],
      ),
    );
  }
  const paramList = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    params,
  );
  const body = readOne(k, s);
  const close = consume(s);
  if (close.kind !== "rparen") throw new Error("defn: expected )");
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 0 },
    [
      k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
        [k.internString(nameTok.text)],
      ),
      paramList,
      body,
    ],
  );
}

function readListForm(k: Kernel, s: ParseState): NodeID {
  consume(s); // "list"
  const kids = readChildrenUntilRparen(k, s);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    kids,
  );
}

function readFnCall(k: Kernel, s: ParseState): NodeID {
  const calleeTok = peek(s);
  if (calleeTok === undefined) throw new Error("call: missing callee");
  // The callee can be any expression; pass through readOne.
  const callee = readOne(k, s);
  const args = readChildrenUntilRparen(k, s);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [callee, ...args],
  );
}
