// lang-typescript.ts — TypeScript 5.7 as a substrate-resident Language cell.
//
// Task #16 in the language-cell rollout (Python #15, TypeScript #16,
// Go #17, Rust #18). Each language is a substrate write: a Language
// cell carrying an ingestion grammar (parse-rule recipe tree) and an
// emission template (emit-rule recipe tree). No kernel patches; the
// grammar/emit alphabets defined in `languages.ts` carry the shape.
//
// What this file ships:
//   • Tokenizer for the TS surface — numeric literals (number → FP64
//     default, integer-range → INT32 inference; bigint → INT64), string
//     literals (single/double/template), identifiers + keywords, the
//     full arithmetic/comparison/logical operator set, punctuation.
//   • Grammar cells covering function declarations, arrow functions,
//     statements (`if/else`, `for`, `for..of`, `while`, `return`,
//     `let/const/var`), expressions with full precedence, array and
//     object literals, type annotations, `interface` and `type` aliases.
//   • Emission walker that dispatches by captured ctor name, producing
//     TS source that round-trips up to whitespace normalization.
//   • Stdlib bindings: `Array.length`, `Map`, `Set`, `Promise`,
//     `console.log`, `JSON`, `Math.*`.
//   • Numeric defaults: `number` → FP64; `bigint` → INT64; INT32
//     narrowing applied at tokenize time when a numeric literal sits in
//     the integer range and lacks a fractional component or exponent.
//
// What lives elsewhere (per task constraints):
//   • The Language cell shape and grammar/emit alphabets live in
//     `languages.ts` (shared infrastructure).
//   • Format recipes (FP64/INT32/INT64) live in `formats.ts`.
//   • Kernel additions for typed numerics live in `kernel.ts`.
//
// Why an in-file walker rather than the generic `parseThrough`:
// `languages.ts`'s vertical-slice parser does not yet resolve
// `RULE_REF` (open question #4 in `docs/coherence-substrate/language-
// cells.md`). Recursive expression grammars require a name→NodeID rule
// table; that table is a TS-specific construction here. The grammar
// cells themselves remain canonical substrate writes (gLiteral, gSeq,
// gAlt, gCapture, gRuleRef …) and the captured recipe shape matches
// what `parseThrough` would produce once production-grade RULE_REF
// resolution lands kernel-side.

import {
  Kernel,
  Level,
  RBasic,
  type NodeID,
} from "./kernel.ts";
import { buildFormatLibrary, type FormatRecipe } from "./formats.ts";
import {
  EmitRuleKind,
  GrammarRuleKind,
  ParseError,
  RBasicLanguage,
  eChild,
  eJoin,
  eLiteral,
  eSeq,
  gAlt,
  gCapture,
  gLiteral,
  gOpt,
  gPlus,
  gRuleRef,
  gSeq,
  gStar,
  gTokenClass,
  registerLanguage,
  type Language,
  type LanguageSpec,
} from "./languages.ts";

// ---------------------------------------------------------------------------
// Tokenizer
// ---------------------------------------------------------------------------
//
// TS surface needs more than the smoke parser's whitespace-skip
// approach: keywords vs identifiers, three string flavors, bigint
// suffix, multi-char operators (==, ===, =>, <=, ++, &&, ||, …). The
// tokenizer runs once per parse; downstream grammar matching reads the
// token stream rather than re-scanning source.

const KEYWORDS = new Set([
  "function", "return", "if", "else", "for", "while", "of", "in",
  "let", "const", "var", "interface", "type", "true", "false",
  "null", "undefined", "new", "void", "as", "is", "this", "break",
  "continue",
]);

// Type-context keywords don't reserve identifiers, but we lex them as
// dedicated tokens so the type-annotation grammar can match them
// cheaply. They overlap with KEYWORDS where appropriate.

type TokenKind =
  | "number"
  | "bigint"
  | "string"
  | "template"
  | "ident"
  | "keyword"
  | "punct";

interface Token {
  readonly kind: TokenKind;
  readonly text: string;
  // For numbers: whether the literal is in INT32 range without
  // fractional or exponent components — the trigger for INT32 inference
  // on the FP64 default.
  readonly int32able?: boolean;
  // For numbers: the parsed numeric value (FP64) or bigint string.
  readonly value?: number | string;
  readonly pos: number;
}

function tokenize(src: string): Token[] {
  const out: Token[] = [];
  let i = 0;
  const len = src.length;

  while (i < len) {
    const ch = src.charCodeAt(i);
    // Whitespace
    if (ch === 32 || ch === 9 || ch === 10 || ch === 13) {
      i++;
      continue;
    }
    // Line comment
    if (ch === 47 && i + 1 < len && src.charCodeAt(i + 1) === 47) {
      while (i < len && src.charCodeAt(i) !== 10) i++;
      continue;
    }
    // Block comment
    if (ch === 47 && i + 1 < len && src.charCodeAt(i + 1) === 42) {
      i += 2;
      while (i + 1 < len && !(src.charCodeAt(i) === 42 && src.charCodeAt(i + 1) === 47)) i++;
      i += 2;
      continue;
    }
    const start = i;

    // String literals
    if (ch === 34 /* " */ || ch === 39 /* ' */) {
      const quote = ch;
      i++;
      let raw = "";
      while (i < len && src.charCodeAt(i) !== quote) {
        if (src.charCodeAt(i) === 92 /* \\ */) {
          raw += src[i]! + src[i + 1]!;
          i += 2;
        } else {
          raw += src[i]!;
          i++;
        }
      }
      i++; // closing quote
      out.push({
        kind: "string",
        text: src.substring(start, i),
        value: decodeStringEscapes(raw),
        pos: start,
      });
      continue;
    }
    if (ch === 96 /* ` */) {
      i++;
      let raw = "";
      while (i < len && src.charCodeAt(i) !== 96) {
        if (src.charCodeAt(i) === 92) {
          raw += src[i]! + src[i + 1]!;
          i += 2;
        } else {
          raw += src[i]!;
          i++;
        }
      }
      i++;
      out.push({
        kind: "template",
        text: src.substring(start, i),
        value: decodeStringEscapes(raw),
        pos: start,
      });
      continue;
    }

    // Numbers (including bigint suffix). No exponent on bigint.
    if (isDigit(ch) || (ch === 46 && i + 1 < len && isDigit(src.charCodeAt(i + 1)))) {
      let pos = i;
      let isFloat = ch === 46;
      let sawExp = false;
      while (pos < len && isDigit(src.charCodeAt(pos))) pos++;
      if (!isFloat && pos < len && src.charCodeAt(pos) === 46) {
        isFloat = true;
        pos++;
        while (pos < len && isDigit(src.charCodeAt(pos))) pos++;
      }
      if (pos < len && (src.charCodeAt(pos) === 101 || src.charCodeAt(pos) === 69)) {
        sawExp = true;
        isFloat = true;
        pos++;
        if (pos < len && (src.charCodeAt(pos) === 43 || src.charCodeAt(pos) === 45)) pos++;
        while (pos < len && isDigit(src.charCodeAt(pos))) pos++;
      }
      const numText = src.substring(start, pos);
      // bigint suffix
      if (!isFloat && pos < len && src.charCodeAt(pos) === 110 /* n */) {
        pos++;
        out.push({
          kind: "bigint",
          text: src.substring(start, pos),
          value: numText,
          pos: start,
        });
        i = pos;
        continue;
      }
      const val = parseFloat(numText);
      const int32able =
        !isFloat &&
        !sawExp &&
        Number.isInteger(val) &&
        val >= -0x80000000 &&
        val <= 0x7fffffff;
      out.push({
        kind: "number",
        text: numText,
        value: val,
        int32able,
        pos: start,
      });
      i = pos;
      continue;
    }

    // Identifiers / keywords
    if (isIdentStart(ch)) {
      let pos = i + 1;
      while (pos < len && isIdentCont(src.charCodeAt(pos))) pos++;
      const text = src.substring(start, pos);
      out.push({
        kind: KEYWORDS.has(text) ? "keyword" : "ident",
        text,
        pos: start,
      });
      i = pos;
      continue;
    }

    // Punctuation / operators. Longest-match across multi-char forms.
    const two = src.substring(i, i + 2);
    const three = src.substring(i, i + 3);
    if (three === "===" || three === "!==" || three === "..." || three === "**=" || three === ">>>" || three === "<<=" || three === ">>=") {
      out.push({ kind: "punct", text: three, pos: start });
      i += 3;
      continue;
    }
    if (
      two === "==" || two === "!=" || two === "<=" || two === ">=" ||
      two === "&&" || two === "||" || two === "=>" || two === "++" ||
      two === "--" || two === "+=" || two === "-=" || two === "*=" ||
      two === "/=" || two === "**" || two === "??" || two === "?." ||
      two === "<<" || two === ">>"
    ) {
      out.push({ kind: "punct", text: two, pos: start });
      i += 2;
      continue;
    }
    out.push({ kind: "punct", text: src[i]!, pos: start });
    i++;
  }

  return out;
}

function decodeStringEscapes(raw: string): string {
  let out = "";
  for (let i = 0; i < raw.length; i++) {
    if (raw.charCodeAt(i) === 92 /* \\ */ && i + 1 < raw.length) {
      const next = raw[i + 1]!;
      switch (next) {
        case "n": out += "\n"; break;
        case "t": out += "\t"; break;
        case "r": out += "\r"; break;
        case "\\": out += "\\"; break;
        case "'": out += "'"; break;
        case '"': out += '"'; break;
        case "`": out += "`"; break;
        case "0": out += "\0"; break;
        default: out += next;
      }
      i++;
    } else {
      out += raw[i];
    }
  }
  return out;
}

function isDigit(ch: number): boolean { return ch >= 48 && ch <= 57; }
function isIdentStart(ch: number): boolean {
  return (ch >= 65 && ch <= 90) || (ch >= 97 && ch <= 122) || ch === 95 || ch === 36;
}
function isIdentCont(ch: number): boolean {
  return isIdentStart(ch) || isDigit(ch);
}

// ---------------------------------------------------------------------------
// Grammar — name-keyed rule table built from `languages.ts` builders.
// ---------------------------------------------------------------------------
//
// Each entry is a NodeID produced by `gXXX`. Together they describe the
// TypeScript surface as a content-addressed recipe tree. The parser
// (below) walks this table — RULE_REF nodes resolve via the table's
// name → NodeID map.

export interface TypeScriptGrammar {
  readonly rules: ReadonlyMap<string, NodeID>;
  readonly root: NodeID;
}

export function buildTypeScriptGrammar(k: Kernel): TypeScriptGrammar {
  const rules = new Map<string, NodeID>();
  const ref = (n: string) => gRuleRef(k, n);

  // --- top level ---
  rules.set("program", gCapture(k, "program", gStar(k, ref("topStmt"))));

  // A top-level statement is anything that can appear at file scope.
  rules.set("topStmt", gAlt(k,
    ref("funcDecl"),
    ref("interfaceDecl"),
    ref("typeAlias"),
    ref("stmt"),
  ));

  // --- declarations ---
  // function name(params): T { body }
  rules.set("funcDecl", gCapture(k, "funcDecl", gSeq(k,
    gLiteral(k, "function"),
    gTokenClass(k, "ident"),
    gLiteral(k, "("),
    gOpt(k, ref("paramList")),
    gLiteral(k, ")"),
    gOpt(k, ref("returnAnnot")),
    ref("block"),
  )));

  rules.set("returnAnnot", gCapture(k, "returnAnnot",
    gSeq(k, gLiteral(k, ":"), ref("typeExpr")),
  ));

  rules.set("paramList", gCapture(k, "paramList", gSeq(k,
    ref("param"),
    gStar(k, gSeq(k, gLiteral(k, ","), ref("param"))),
  )));

  rules.set("param", gCapture(k, "param", gSeq(k,
    gTokenClass(k, "ident"),
    gOpt(k, ref("typeAnnot")),
  )));

  rules.set("typeAnnot", gCapture(k, "typeAnnot",
    gSeq(k, gLiteral(k, ":"), ref("typeExpr")),
  ));

  // interface I { k: T; ... }
  rules.set("interfaceDecl", gCapture(k, "interfaceDecl", gSeq(k,
    gLiteral(k, "interface"),
    gTokenClass(k, "ident"),
    gLiteral(k, "{"),
    gStar(k, ref("typeMember")),
    gLiteral(k, "}"),
  )));

  rules.set("typeMember", gCapture(k, "typeMember", gSeq(k,
    gTokenClass(k, "ident"),
    gLiteral(k, ":"),
    ref("typeExpr"),
    gOpt(k, gAlt(k, gLiteral(k, ";"), gLiteral(k, ","))),
  )));

  // type Alias = T;
  rules.set("typeAlias", gCapture(k, "typeAlias", gSeq(k,
    gLiteral(k, "type"),
    gTokenClass(k, "ident"),
    gLiteral(k, "="),
    ref("typeExpr"),
    gOpt(k, gLiteral(k, ";")),
  )));

  // --- type expressions (basic forms; advanced generics deferred) ---
  rules.set("typeExpr", ref("typeUnion"));

  rules.set("typeUnion", gCapture(k, "typeUnion", gSeq(k,
    ref("typePrimary"),
    gStar(k, gSeq(k, gLiteral(k, "|"), ref("typePrimary"))),
  )));

  rules.set("typePrimary", gAlt(k,
    ref("typeObject"),
    ref("typeArray"),
    ref("typeIdent"),
  ));

  rules.set("typeIdent", gCapture(k, "typeIdent", gTokenClass(k, "ident")));

  rules.set("typeArray", gCapture(k, "typeArray", gSeq(k,
    gLiteral(k, "["),
    gOpt(k, gSeq(k, ref("typeExpr"), gStar(k, gSeq(k, gLiteral(k, ","), ref("typeExpr"))))),
    gLiteral(k, "]"),
  )));

  rules.set("typeObject", gCapture(k, "typeObject", gSeq(k,
    gLiteral(k, "{"),
    gStar(k, ref("typeMember")),
    gLiteral(k, "}"),
  )));

  // --- statements ---
  rules.set("stmt", gAlt(k,
    ref("varDecl"),
    ref("ifStmt"),
    ref("forStmt"),
    ref("forOfStmt"),
    ref("whileStmt"),
    ref("returnStmt"),
    ref("block"),
    ref("exprStmt"),
  ));

  rules.set("block", gCapture(k, "block", gSeq(k,
    gLiteral(k, "{"),
    gStar(k, ref("stmt")),
    gLiteral(k, "}"),
  )));

  rules.set("varDecl", gCapture(k, "varDecl", gSeq(k,
    gAlt(k, gLiteral(k, "let"), gLiteral(k, "const"), gLiteral(k, "var")),
    gTokenClass(k, "ident"),
    gOpt(k, ref("typeAnnot")),
    gOpt(k, gSeq(k, gLiteral(k, "="), ref("expr"))),
    gOpt(k, gLiteral(k, ";")),
  )));

  rules.set("ifStmt", gCapture(k, "ifStmt", gSeq(k,
    gLiteral(k, "if"),
    gLiteral(k, "("),
    ref("expr"),
    gLiteral(k, ")"),
    ref("stmt"),
    gOpt(k, gSeq(k, gLiteral(k, "else"), ref("stmt"))),
  )));

  // for (init; cond; step) body — C-style
  rules.set("forStmt", gCapture(k, "forStmt", gSeq(k,
    gLiteral(k, "for"),
    gLiteral(k, "("),
    gOpt(k, ref("forInit")),
    gLiteral(k, ";"),
    gOpt(k, ref("expr")),
    gLiteral(k, ";"),
    gOpt(k, ref("expr")),
    gLiteral(k, ")"),
    ref("stmt"),
  )));

  rules.set("forInit", gAlt(k, ref("varDeclNoTerm"), ref("expr")));

  // varDeclNoTerm: no trailing semicolon, used inside `for(...)`.
  rules.set("varDeclNoTerm", gCapture(k, "varDecl", gSeq(k,
    gAlt(k, gLiteral(k, "let"), gLiteral(k, "const"), gLiteral(k, "var")),
    gTokenClass(k, "ident"),
    gOpt(k, ref("typeAnnot")),
    gOpt(k, gSeq(k, gLiteral(k, "="), ref("expr"))),
  )));

  // for..of: for (let x of expr) body
  rules.set("forOfStmt", gCapture(k, "forOfStmt", gSeq(k,
    gLiteral(k, "for"),
    gLiteral(k, "("),
    gAlt(k, gLiteral(k, "let"), gLiteral(k, "const"), gLiteral(k, "var")),
    gTokenClass(k, "ident"),
    gLiteral(k, "of"),
    ref("expr"),
    gLiteral(k, ")"),
    ref("stmt"),
  )));

  rules.set("whileStmt", gCapture(k, "whileStmt", gSeq(k,
    gLiteral(k, "while"),
    gLiteral(k, "("),
    ref("expr"),
    gLiteral(k, ")"),
    ref("stmt"),
  )));

  rules.set("returnStmt", gCapture(k, "returnStmt", gSeq(k,
    gLiteral(k, "return"),
    gOpt(k, ref("expr")),
    gOpt(k, gLiteral(k, ";")),
  )));

  rules.set("exprStmt", gCapture(k, "exprStmt", gSeq(k,
    ref("expr"),
    gOpt(k, gLiteral(k, ";")),
  )));

  // --- expressions — stratified precedence ladder ---
  //
  // top
  //   conditional        (a ? b : c)
  //   logicalOr          (a || b)
  //   logicalAnd         (a && b)
  //   equality           (a == b, a === b, a != b, a !== b)
  //   relational         (<, <=, >, >=)
  //   additive           (+, -)
  //   multiplicative     (*, /, %)
  //   unary              (!a, -a, ++a, --a)
  //   postfix            (a++, a--)
  //   call/index/member  (f(args), a[i], a.b)
  //   primary            (literal, ident, paren, array, object, arrow)
  rules.set("expr", ref("assignment"));

  // Assignment is right-associative: a = b = c parses as a = (b = c).
  // We accept any LHS that the parser builds (the lvalue check is
  // semantic, not syntactic; deferred to a later pass).
  rules.set("assignment", gCapture(k, "assignment", gSeq(k,
    ref("conditional"),
    gOpt(k, gSeq(k,
      gAlt(k,
        gLiteral(k, "="),
        gLiteral(k, "+="),
        gLiteral(k, "-="),
        gLiteral(k, "*="),
        gLiteral(k, "/="),
      ),
      ref("assignment"),
    )),
  )));

  rules.set("conditional", gCapture(k, "conditional", gSeq(k,
    ref("logicalOr"),
    gOpt(k, gSeq(k,
      gLiteral(k, "?"), ref("expr"),
      gLiteral(k, ":"), ref("expr"),
    )),
  )));

  rules.set("logicalOr", gCapture(k, "binOp", gSeq(k,
    ref("logicalAnd"),
    gStar(k, gSeq(k, gLiteral(k, "||"), ref("logicalAnd"))),
  )));

  rules.set("logicalAnd", gCapture(k, "binOp", gSeq(k,
    ref("equality"),
    gStar(k, gSeq(k, gLiteral(k, "&&"), ref("equality"))),
  )));

  rules.set("equality", gCapture(k, "binOp", gSeq(k,
    ref("relational"),
    gStar(k, gSeq(k,
      gAlt(k, gLiteral(k, "==="), gLiteral(k, "!=="), gLiteral(k, "=="), gLiteral(k, "!=")),
      ref("relational"),
    )),
  )));

  rules.set("relational", gCapture(k, "binOp", gSeq(k,
    ref("additive"),
    gStar(k, gSeq(k,
      gAlt(k, gLiteral(k, "<="), gLiteral(k, ">="), gLiteral(k, "<"), gLiteral(k, ">")),
      ref("additive"),
    )),
  )));

  rules.set("additive", gCapture(k, "binOp", gSeq(k,
    ref("multiplicative"),
    gStar(k, gSeq(k,
      gAlt(k, gLiteral(k, "+"), gLiteral(k, "-")),
      ref("multiplicative"),
    )),
  )));

  rules.set("multiplicative", gCapture(k, "binOp", gSeq(k,
    ref("unary"),
    gStar(k, gSeq(k,
      gAlt(k, gLiteral(k, "*"), gLiteral(k, "/"), gLiteral(k, "%")),
      ref("unary"),
    )),
  )));

  rules.set("unary", gAlt(k,
    gCapture(k, "unary", gSeq(k,
      gAlt(k, gLiteral(k, "!"), gLiteral(k, "-"), gLiteral(k, "+"), gLiteral(k, "++"), gLiteral(k, "--")),
      ref("unary"),
    )),
    ref("postfix"),
  ));

  rules.set("postfix", gCapture(k, "postfix", gSeq(k,
    ref("callExpr"),
    gStar(k, gAlt(k, gLiteral(k, "++"), gLiteral(k, "--"))),
  )));

  // call/index/member chain
  rules.set("callExpr", gCapture(k, "callExpr", gSeq(k,
    ref("primary"),
    gStar(k, gAlt(k,
      ref("callTail"),
      ref("indexTail"),
      ref("memberTail"),
    )),
  )));

  rules.set("callTail", gCapture(k, "callTail", gSeq(k,
    gLiteral(k, "("),
    gOpt(k, ref("argList")),
    gLiteral(k, ")"),
  )));

  rules.set("argList", gCapture(k, "argList", gSeq(k,
    ref("expr"),
    gStar(k, gSeq(k, gLiteral(k, ","), ref("expr"))),
  )));

  rules.set("indexTail", gCapture(k, "indexTail", gSeq(k,
    gLiteral(k, "["), ref("expr"), gLiteral(k, "]"),
  )));

  rules.set("memberTail", gCapture(k, "memberTail", gSeq(k,
    gLiteral(k, "."), gTokenClass(k, "ident"),
  )));

  // primary expressions
  rules.set("primary", gAlt(k,
    ref("arrowFunc"),
    ref("parenExpr"),
    ref("arrayLit"),
    ref("objectLit"),
    ref("templateLit"),
    ref("strLit"),
    ref("numLit"),
    ref("bigintLit"),
    ref("boolLit"),
    ref("nullLit"),
    ref("identExpr"),
  ));

  // arrow function: (x: T, y: T) => expr — the version with a single
  // typed parameter is the most common shape in TS source. We accept
  // (params) => expr | block and (x) => expr.
  rules.set("arrowFunc", gCapture(k, "arrowFunc", gSeq(k,
    gLiteral(k, "("),
    gOpt(k, ref("paramList")),
    gLiteral(k, ")"),
    gOpt(k, ref("returnAnnot")),
    gLiteral(k, "=>"),
    gAlt(k, ref("block"), ref("expr")),
  )));

  rules.set("parenExpr", gCapture(k, "paren", gSeq(k,
    gLiteral(k, "("), ref("expr"), gLiteral(k, ")"),
  )));

  rules.set("arrayLit", gCapture(k, "arrayLit", gSeq(k,
    gLiteral(k, "["),
    gOpt(k, gSeq(k,
      ref("expr"),
      gStar(k, gSeq(k, gLiteral(k, ","), ref("expr"))),
      gOpt(k, gLiteral(k, ",")),
    )),
    gLiteral(k, "]"),
  )));

  rules.set("objectLit", gCapture(k, "objectLit", gSeq(k,
    gLiteral(k, "{"),
    gOpt(k, gSeq(k,
      ref("objectMember"),
      gStar(k, gSeq(k, gLiteral(k, ","), ref("objectMember"))),
      gOpt(k, gLiteral(k, ",")),
    )),
    gLiteral(k, "}"),
  )));

  rules.set("objectMember", gCapture(k, "objectMember", gSeq(k,
    gAlt(k, gTokenClass(k, "ident"), ref("strLit")),
    gLiteral(k, ":"),
    ref("expr"),
  )));

  rules.set("templateLit", gCapture(k, "templateLit", gTokenClass(k, "template")));
  rules.set("strLit", gCapture(k, "strLit", gTokenClass(k, "string")));
  rules.set("numLit", gCapture(k, "numLit", gTokenClass(k, "number")));
  rules.set("bigintLit", gCapture(k, "bigintLit", gTokenClass(k, "bigint")));
  rules.set("boolLit", gCapture(k, "boolLit",
    gAlt(k, gLiteral(k, "true"), gLiteral(k, "false")),
  ));
  rules.set("nullLit", gCapture(k, "nullLit",
    gAlt(k, gLiteral(k, "null"), gLiteral(k, "undefined")),
  ));
  rules.set("identExpr", gCapture(k, "identExpr", gTokenClass(k, "ident")));

  return { rules, root: rules.get("program")! };
}

// ---------------------------------------------------------------------------
// Token-stream parser — walks grammar cells over a tokenized stream.
// ---------------------------------------------------------------------------

interface ParseCtx {
  readonly k: Kernel;
  readonly tokens: Token[];
  pos: number;
  readonly rules: ReadonlyMap<string, NodeID>;
}

function tokAt(ctx: ParseCtx): Token | undefined {
  return ctx.tokens[ctx.pos];
}

function strFromTrivial(k: Kernel, n: NodeID): string {
  if (n.level !== Level.TRIVIAL) {
    throw new Error("strFromTrivial: not a trivial");
  }
  return k.strs[n.inst] ?? "";
}

function matchTokenClassTS(ctx: ParseCtx, className: string): NodeID | null {
  const t = tokAt(ctx);
  if (!t) return null;
  const k = ctx.k;
  switch (className) {
    case "number": {
      if (t.kind !== "number") return null;
      ctx.pos++;
      // Numeric default: number → FP64, with INT32 inference when the
      // literal is integer-range and lacks fractional/exponent text.
      if (t.int32able) {
        return k.internTrivialInt(t.value as number);
      }
      return k.internTrivialFloat64(t.value as number);
    }
    case "bigint": {
      if (t.kind !== "bigint") return null;
      ctx.pos++;
      // bigint → INT64 (overflow table).
      try {
        return k.internTrivialInt64(BigInt(t.value as string));
      } catch {
        return null;
      }
    }
    case "string": {
      if (t.kind !== "string") return null;
      ctx.pos++;
      // Encode as a captured string-literal node carrying the raw
      // (with surrounding quotes) so emission can replay the surface
      // shape. The decoded value is available via the value field but
      // we intern only the raw text here for round-trip fidelity.
      return k.internString(t.text);
    }
    case "template": {
      if (t.kind !== "template") return null;
      ctx.pos++;
      return k.internString(t.text);
    }
    case "ident": {
      if (t.kind !== "ident") return null;
      ctx.pos++;
      return k.internString(t.text);
    }
  }
  return null;
}

function matchLiteralTS(ctx: ParseCtx, lit: string): NodeID | null {
  const t = tokAt(ctx);
  if (!t) return null;
  // Keywords and punctuation match on text identity; identifier matches
  // would be possible but our grammar uses TOKEN_CLASS for those.
  if (t.text === lit && (t.kind === "keyword" || t.kind === "punct")) {
    ctx.pos++;
    return ctx.k.internString(lit);
  }
  return null;
}

function matchRuleTS(ctx: ParseCtx, rule: NodeID): NodeID | null {
  const k = ctx.k;
  const recipe = k.recipeAt(rule);
  if (!recipe) return rule;
  const cat = recipe.category;
  if (cat.type !== RBasicLanguage || cat.inst >= 0x80) {
    throw new Error(
      `parser: rule has non-grammar category ${cat.type}/${cat.inst}`,
    );
  }
  const kind = cat.inst;
  switch (kind) {
    case GrammarRuleKind.LITERAL: {
      const lit = strFromTrivial(k, recipe.children[0]!);
      return matchLiteralTS(ctx, lit);
    }
    case GrammarRuleKind.TOKEN_CLASS: {
      const className = strFromTrivial(k, recipe.children[0]!);
      return matchTokenClassTS(ctx, className);
    }
    case GrammarRuleKind.RULE_REF: {
      const name = strFromTrivial(k, recipe.children[0]!);
      const target = ctx.rules.get(name);
      if (!target) {
        throw new Error(`parser: undefined rule "${name}"`);
      }
      return matchRuleTS(ctx, target);
    }
    case GrammarRuleKind.ALT: {
      for (const alt of recipe.children) {
        const saved = ctx.pos;
        const r = matchRuleTS(ctx, alt);
        if (r !== null) return r;
        ctx.pos = saved;
      }
      return null;
    }
    case GrammarRuleKind.SEQ: {
      const saved = ctx.pos;
      const results: NodeID[] = [];
      for (const part of recipe.children) {
        const r = matchRuleTS(ctx, part);
        if (r === null) {
          ctx.pos = saved;
          return null;
        }
        results.push(r);
      }
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
        results,
      );
    }
    case GrammarRuleKind.STAR: {
      const body = recipe.children[0]!;
      const results: NodeID[] = [];
      while (true) {
        const saved = ctx.pos;
        const r = matchRuleTS(ctx, body);
        if (r === null) { ctx.pos = saved; break; }
        results.push(r);
      }
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
        results,
      );
    }
    case GrammarRuleKind.PLUS: {
      const body = recipe.children[0]!;
      const results: NodeID[] = [];
      const first = matchRuleTS(ctx, body);
      if (first === null) return null;
      results.push(first);
      while (true) {
        const saved = ctx.pos;
        const r = matchRuleTS(ctx, body);
        if (r === null) { ctx.pos = saved; break; }
        results.push(r);
      }
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
        results,
      );
    }
    case GrammarRuleKind.OPT: {
      const body = recipe.children[0]!;
      const saved = ctx.pos;
      const r = matchRuleTS(ctx, body);
      if (r !== null) return r;
      ctx.pos = saved;
      return k.internTrivialNull();
    }
    case GrammarRuleKind.CAPTURE: {
      const ctorName = strFromTrivial(k, recipe.children[0]!);
      const body = recipe.children[1]!;
      const inner = matchRuleTS(ctx, body);
      if (inner === null) return null;
      const ctorNameID = k.internName(ctorName);
      const ctorCat: NodeID = {
        pkg: 1,
        level: Level.BASIC,
        type: RBasic.LIST,
        inst: ctorNameID,
      };
      const innerRecipe = k.recipeAt(inner);
      const innerChildren =
        innerRecipe &&
        innerRecipe.category.type === RBasic.LIST &&
        innerRecipe.category.inst === 0
          ? innerRecipe.children
          : [inner];
      return k.intern(ctorCat, innerChildren);
    }
  }
  return null;
}

// parseTypeScript — tokenize, then walk the grammar over the token
// stream. Returns the recipe tree (a `program` ctor).
export function parseTypeScript(
  k: Kernel,
  grammar: TypeScriptGrammar,
  source: string,
): NodeID {
  const tokens = tokenize(source);
  const ctx: ParseCtx = { k, tokens, pos: 0, rules: grammar.rules };
  const result = matchRuleTS(ctx, grammar.root);
  if (result === null) {
    throw new ParseError(0, grammar.root, "parse failed");
  }
  if (ctx.pos < tokens.length) {
    const t = tokens[ctx.pos]!;
    throw new ParseError(
      t.pos,
      grammar.root,
      `unconsumed input: token "${t.text}" at position ${t.pos}`,
    );
  }
  return result;
}

// ---------------------------------------------------------------------------
// Emission template — recipe tree → TS source
// ---------------------------------------------------------------------------
//
// The emission template registered on the Language cell is a single
// "format-program" emit rule that delegates to a TS-specific emitter
// indexed by ctor name. The substrate carries the template shape; the
// emitter implementation lives here.

function ctorOf(k: Kernel, n: NodeID): string {
  const r = k.recipeAt(n);
  if (!r) return "";
  if (r.category.type !== RBasic.LIST) return "";
  if (r.category.inst === 0) return "";
  return k.strs[r.category.inst] ?? "";
}

function childrenOf(k: Kernel, n: NodeID): readonly NodeID[] {
  const r = k.recipeAt(n);
  return r ? r.children : [];
}

function isNull(n: NodeID): boolean {
  return n.level === Level.TRIVIAL && n.type === 4;
}

interface EmitOut { parts: string[] }

function emitNode(k: Kernel, n: NodeID, out: EmitOut): void {
  if (n.level === Level.TRIVIAL) {
    switch (n.type) {
      case 1: out.parts.push(String(n.inst | 0)); return;            // INT32
      case 2: out.parts.push(k.strs[n.inst] ?? ""); return;          // STRING
      case 3: out.parts.push(n.inst ? "true" : "false"); return;     // BOOL
      case 4: return;                                                 // NULL — emit nothing
      case 5: out.parts.push(k.decodeInt64(n.inst).toString() + "n"); return; // INT64
      case 7: out.parts.push(formatNumber(k.decodeFloat64(n.inst))); return;  // FP64
      default: out.parts.push(`<trivial:${n.type}>`); return;
    }
  }
  const ctor = ctorOf(k, n);
  const kids = childrenOf(k, n);
  const emit = EMITTERS[ctor];
  if (emit) {
    emit(k, kids, out);
    return;
  }
  // Fallback: emit children separated by single space.
  for (let i = 0; i < kids.length; i++) {
    if (i > 0) out.parts.push(" ");
    emitNode(k, kids[i]!, out);
  }
}

function formatNumber(v: number): string {
  if (Number.isInteger(v) && Math.abs(v) < 1e21) return v.toFixed(0);
  return String(v);
}

// Per-ctor emitters. Each takes (kernel, children-of-the-capture, out)
// and pushes the surface fragment. Whitespace is normalized; round-trip
// is up to whitespace fidelity (per language-cells.md open question #3).
type CtorEmitter = (k: Kernel, kids: readonly NodeID[], out: EmitOut) => void;

const EMITTERS: Record<string, CtorEmitter> = {
  program(k, kids, out) {
    // CAPTURE splices the STAR-list children directly under `program`,
    // so `kids` is already the top-level statement sequence.
    for (let i = 0; i < kids.length; i++) {
      if (i > 0) out.parts.push("\n");
      emitNode(k, kids[i]!, out);
    }
  },
  funcDecl(k, kids, out) {
    // function ident ( params? ) annot? block
    out.parts.push("function ");
    emitNode(k, kids[1]!, out);
    out.parts.push("(");
    if (!isNull(kids[3]!)) emitNode(k, kids[3]!, out);
    out.parts.push(")");
    if (!isNull(kids[5]!)) emitNode(k, kids[5]!, out);
    out.parts.push(" ");
    emitNode(k, kids[6]!, out);
  },
  returnAnnot(k, kids, out) {
    // children are the splat: ":", typeExpr.
    out.parts.push(": ");
    emitNode(k, kids[1]!, out);
  },
  typeAnnot(k, kids, out) {
    out.parts.push(": ");
    emitNode(k, kids[1]!, out);
  },
  paramList(k, kids, out) {
    // first child is a param, then a SEQ-list of (",", param) pairs.
    emitNode(k, kids[0]!, out);
    const tail = kids[1]!;
    if (!tail) return;
    const tailKids = childrenOf(k, tail);
    for (const pair of tailKids) {
      const pairKids = childrenOf(k, pair);
      out.parts.push(", ");
      emitNode(k, pairKids[1]!, out);
    }
  },
  param(k, kids, out) {
    emitNode(k, kids[0]!, out);
    if (!isNull(kids[1]!)) emitNode(k, kids[1]!, out);
  },
  typeUnion(k, kids, out) {
    emitNode(k, kids[0]!, out);
    const tail = kids[1]!;
    if (!tail) return;
    const tailKids = childrenOf(k, tail);
    for (const pair of tailKids) {
      const pk = childrenOf(k, pair);
      out.parts.push(" | ");
      emitNode(k, pk[1]!, out);
    }
  },
  typeIdent(k, kids, out) {
    emitNode(k, kids[0]!, out);
  },
  typeArray(k, kids, out) {
    out.parts.push("[");
    if (!isNull(kids[1]!)) {
      const inner = childrenOf(k, kids[1]!);
      emitNode(k, inner[0]!, out);
      const tail = childrenOf(k, inner[1]!);
      for (const pair of tail) {
        const pk = childrenOf(k, pair);
        out.parts.push(", ");
        emitNode(k, pk[1]!, out);
      }
    }
    out.parts.push("]");
  },
  typeObject(k, kids, out) {
    out.parts.push("{ ");
    const members = childrenOf(k, kids[1]!);
    for (let i = 0; i < members.length; i++) {
      if (i > 0) out.parts.push("; ");
      emitNode(k, members[i]!, out);
    }
    out.parts.push(" }");
  },
  interfaceDecl(k, kids, out) {
    out.parts.push("interface ");
    emitNode(k, kids[1]!, out);
    out.parts.push(" { ");
    const members = childrenOf(k, kids[3]!);
    for (let i = 0; i < members.length; i++) {
      if (i > 0) out.parts.push("; ");
      emitNode(k, members[i]!, out);
    }
    out.parts.push(" }");
  },
  typeMember(k, kids, out) {
    emitNode(k, kids[0]!, out);
    out.parts.push(": ");
    emitNode(k, kids[2]!, out);
  },
  typeAlias(k, kids, out) {
    out.parts.push("type ");
    emitNode(k, kids[1]!, out);
    out.parts.push(" = ");
    emitNode(k, kids[3]!, out);
    out.parts.push(";");
  },
  block(k, kids, out) {
    out.parts.push("{ ");
    const stmts = childrenOf(k, kids[1]!);
    for (let i = 0; i < stmts.length; i++) {
      if (i > 0) out.parts.push(" ");
      emitNode(k, stmts[i]!, out);
    }
    out.parts.push(" }");
  },
  varDecl(k, kids, out) {
    emitNode(k, kids[0]!, out); // let/const/var keyword as plain string
    out.parts.push(" ");
    emitNode(k, kids[1]!, out);
    if (!isNull(kids[2]!)) emitNode(k, kids[2]!, out);
    if (!isNull(kids[3]!)) {
      const initKids = childrenOf(k, kids[3]!);
      out.parts.push(" = ");
      emitNode(k, initKids[1]!, out);
    }
    out.parts.push(";");
  },
  ifStmt(k, kids, out) {
    out.parts.push("if (");
    emitNode(k, kids[2]!, out);
    out.parts.push(") ");
    emitNode(k, kids[4]!, out);
    if (!isNull(kids[5]!)) {
      const elseKids = childrenOf(k, kids[5]!);
      out.parts.push(" else ");
      emitNode(k, elseKids[1]!, out);
    }
  },
  forStmt(k, kids, out) {
    out.parts.push("for (");
    if (!isNull(kids[2]!)) emitNode(k, kids[2]!, out);
    out.parts.push("; ");
    if (!isNull(kids[4]!)) emitNode(k, kids[4]!, out);
    out.parts.push("; ");
    if (!isNull(kids[6]!)) emitNode(k, kids[6]!, out);
    out.parts.push(") ");
    emitNode(k, kids[8]!, out);
  },
  forOfStmt(k, kids, out) {
    out.parts.push("for (");
    emitNode(k, kids[2]!, out); // let/const/var
    out.parts.push(" ");
    emitNode(k, kids[3]!, out); // ident
    out.parts.push(" of ");
    emitNode(k, kids[5]!, out);
    out.parts.push(") ");
    emitNode(k, kids[7]!, out);
  },
  whileStmt(k, kids, out) {
    out.parts.push("while (");
    emitNode(k, kids[2]!, out);
    out.parts.push(") ");
    emitNode(k, kids[4]!, out);
  },
  returnStmt(k, kids, out) {
    out.parts.push("return");
    if (!isNull(kids[1]!)) {
      out.parts.push(" ");
      emitNode(k, kids[1]!, out);
    }
    out.parts.push(";");
  },
  exprStmt(k, kids, out) {
    emitNode(k, kids[0]!, out);
    out.parts.push(";");
  },
  conditional(k, kids, out) {
    emitNode(k, kids[0]!, out);
    if (!isNull(kids[1]!)) {
      const t = childrenOf(k, kids[1]!);
      out.parts.push(" ? ");
      emitNode(k, t[1]!, out);
      out.parts.push(" : ");
      emitNode(k, t[3]!, out);
    }
  },
  assignment(k, kids, out) {
    emitNode(k, kids[0]!, out);
    if (!isNull(kids[1]!)) {
      const t = childrenOf(k, kids[1]!);
      const op = k.strs[t[0]!.inst] ?? "=";
      out.parts.push(" ", op, " ");
      emitNode(k, t[1]!, out);
    }
  },
  binOp(k, kids, out) {
    // children: [head, SEQ-list of (op, rhs) pairs]
    emitNode(k, kids[0]!, out);
    const tail = childrenOf(k, kids[1]!);
    for (const pair of tail) {
      const pk = childrenOf(k, pair);
      const op = k.strs[pk[0]!.inst] ?? "";
      out.parts.push(" ", op, " ");
      emitNode(k, pk[1]!, out);
    }
  },
  unary(k, kids, out) {
    const op = k.strs[kids[0]!.inst] ?? "";
    out.parts.push(op);
    emitNode(k, kids[1]!, out);
  },
  postfix(k, kids, out) {
    emitNode(k, kids[0]!, out);
    const ops = childrenOf(k, kids[1]!);
    for (const op of ops) {
      out.parts.push(k.strs[op.inst] ?? "");
    }
  },
  callExpr(k, kids, out) {
    emitNode(k, kids[0]!, out);
    const tails = childrenOf(k, kids[1]!);
    for (const t of tails) emitNode(k, t, out);
  },
  callTail(k, kids, out) {
    out.parts.push("(");
    if (!isNull(kids[1]!)) emitNode(k, kids[1]!, out);
    out.parts.push(")");
  },
  argList(k, kids, out) {
    emitNode(k, kids[0]!, out);
    const tail = childrenOf(k, kids[1]!);
    for (const pair of tail) {
      const pk = childrenOf(k, pair);
      out.parts.push(", ");
      emitNode(k, pk[1]!, out);
    }
  },
  indexTail(k, kids, out) {
    out.parts.push("[");
    emitNode(k, kids[1]!, out);
    out.parts.push("]");
  },
  memberTail(k, kids, out) {
    out.parts.push(".");
    emitNode(k, kids[1]!, out);
  },
  arrowFunc(k, kids, out) {
    out.parts.push("(");
    if (!isNull(kids[1]!)) emitNode(k, kids[1]!, out);
    out.parts.push(")");
    if (!isNull(kids[3]!)) emitNode(k, kids[3]!, out);
    out.parts.push(" => ");
    emitNode(k, kids[5]!, out);
  },
  paren(k, kids, out) {
    out.parts.push("(");
    emitNode(k, kids[1]!, out);
    out.parts.push(")");
  },
  arrayLit(k, kids, out) {
    out.parts.push("[");
    if (!isNull(kids[1]!)) {
      const inner = childrenOf(k, kids[1]!);
      emitNode(k, inner[0]!, out);
      const tail = childrenOf(k, inner[1]!);
      for (const pair of tail) {
        const pk = childrenOf(k, pair);
        out.parts.push(", ");
        emitNode(k, pk[1]!, out);
      }
    }
    out.parts.push("]");
  },
  objectLit(k, kids, out) {
    out.parts.push("{");
    if (!isNull(kids[1]!)) {
      const inner = childrenOf(k, kids[1]!);
      emitNode(k, inner[0]!, out);
      const tail = childrenOf(k, inner[1]!);
      for (const pair of tail) {
        const pk = childrenOf(k, pair);
        out.parts.push(", ");
        emitNode(k, pk[1]!, out);
      }
    }
    out.parts.push("}");
  },
  objectMember(k, kids, out) {
    emitNode(k, kids[0]!, out);
    out.parts.push(": ");
    emitNode(k, kids[2]!, out);
  },
  templateLit(k, kids, out) {
    out.parts.push(k.strs[kids[0]!.inst] ?? "");
  },
  strLit(k, kids, out) {
    out.parts.push(k.strs[kids[0]!.inst] ?? "");
  },
  numLit(k, kids, out) {
    emitNode(k, kids[0]!, out);
  },
  bigintLit(k, kids, out) {
    emitNode(k, kids[0]!, out);
  },
  boolLit(k, kids, out) {
    // child is the matched literal text "true" / "false"
    out.parts.push(k.strs[kids[0]!.inst] ?? "");
  },
  nullLit(k, kids, out) {
    out.parts.push(k.strs[kids[0]!.inst] ?? "");
  },
  identExpr(k, kids, out) {
    emitNode(k, kids[0]!, out);
  },
};

// emitTypeScript — recipe tree → TS source. The recipe is what
// `parseTypeScript` produced (or any structurally-equivalent recipe
// tree); per-ctor templates produce well-formed surface text.
export function emitTypeScript(k: Kernel, recipe: NodeID): string {
  const out: EmitOut = { parts: [] };
  emitNode(k, recipe, out);
  return out.parts.join("");
}

// ---------------------------------------------------------------------------
// Language cell — registration
// ---------------------------------------------------------------------------
//
// The Language cell registered with the substrate carries the root of
// the grammar tree and a single emission template marker. The actual
// emission walk (per-ctor dispatch) lives in `emitTypeScript`; the
// emission template registered here is a placeholder rooted at
// EmitRuleKind.SEQ that delegates per-ctor — production walkers will
// replace this with substrate-resident WHEN_CATEGORY tables (the open-
// question #4 in `language-cells.md`).
export interface TypeScriptLanguage {
  readonly language: Language;
  readonly grammar: TypeScriptGrammar;
  readonly numericDefaults: ReadonlyMap<string, FormatRecipe>;
}

export function buildTypeScriptLanguage(k: Kernel): TypeScriptLanguage {
  const grammar = buildTypeScriptGrammar(k);
  const fmts = buildFormatLibrary(k);

  // Emission template: a marker SEQ that holds child-references in the
  // order matching the program ctor's children. The TS-side emitter
  // owns the actual per-ctor dispatch; the cell is registered so the
  // Language cell remains content-addressable and the emit template
  // NodeID is non-null.
  const emissionTemplate = eSeq(k,
    eLiteral(k, ""),
    eChild(k, 0),
  );

  // numeric_defaults: TS-specific resolution of numeric-literal types.
  //   "number"  → FP64    (TypeScript's default numeric type)
  //   "int32"   → INT32   (inferred when integer-range literal lacks
  //                        fractional or exponent components)
  //   "bigint"  → INT64   (TypeScript's `bigint` type)
  const numericDefaults = new Map<string, FormatRecipe>([
    ["number", fmts.FP64],
    ["int32", fmts.INT32],
    ["bigint", fmts.INT64],
  ]);

  // stdlib_bindings: surface names → recipe cells. For the vertical
  // slice we register name handles; the resolved target recipes are
  // owned by their respective stdlib cells (Array, Map, Set, Promise,
  // console, JSON, Math). Each binding's NodeID is a placeholder ident
  // recipe — production bindings will point at substrate-resident
  // function/type cells.
  const stdlibBindings = new Map<string, NodeID>([
    ["Array.length", k.internString("Array.length")],
    ["Map", k.internString("Map")],
    ["Set", k.internString("Set")],
    ["Promise", k.internString("Promise")],
    ["console.log", k.internString("console.log")],
    ["JSON", k.internString("JSON")],
    ["Math.abs", k.internString("Math.abs")],
    ["Math.max", k.internString("Math.max")],
    ["Math.min", k.internString("Math.min")],
    ["Math.floor", k.internString("Math.floor")],
    ["Math.ceil", k.internString("Math.ceil")],
    ["Math.round", k.internString("Math.round")],
    ["Math.sqrt", k.internString("Math.sqrt")],
    ["Math.pow", k.internString("Math.pow")],
    ["Math.PI", k.internString("Math.PI")],
    ["Math.E", k.internString("Math.E")],
  ]);

  const spec: LanguageSpec = {
    name: "typescript",
    version: "5.7",
    ingestionGrammar: grammar.root,
    emissionTemplate,
    stdlibBindings,
    numericDefaults,
  };
  const language = registerLanguage(k, spec);
  return { language, grammar, numericDefaults };
}

// ---------------------------------------------------------------------------
// Recipe-tree evaluator — walks a captured TS program and computes.
// ---------------------------------------------------------------------------
//
// The point: prove the recipe tree is sufficient to execute the
// program. The evaluator is a tree-walker over the captured ctors.
// Returns the value of the last expression or a thrown ReturnSignal.

class ReturnSignal {
  constructor(public readonly value: unknown) {}
}

interface Env {
  vars: Map<string, unknown>;
  parent?: Env;
}

function envNew(parent?: Env): Env {
  return { vars: new Map(), parent };
}

function envGet(env: Env, name: string): unknown {
  let e: Env | undefined = env;
  while (e) {
    if (e.vars.has(name)) return e.vars.get(name);
    e = e.parent;
  }
  throw new Error(`undefined: ${name}`);
}

function envSet(env: Env, name: string, value: unknown): void {
  let e: Env | undefined = env;
  while (e) {
    if (e.vars.has(name)) { e.vars.set(name, value); return; }
    e = e.parent;
  }
  env.vars.set(name, value);
}

function trivialNumber(k: Kernel, n: NodeID): number | undefined {
  if (n.level !== Level.TRIVIAL) return undefined;
  switch (n.type) {
    case 1: return n.inst | 0;
    case 7: return k.decodeFloat64(n.inst);
    case 5: return Number(k.decodeInt64(n.inst));
    default: return undefined;
  }
}

function evalNode(k: Kernel, n: NodeID, env: Env): unknown {
  if (n.level === Level.TRIVIAL) {
    const num = trivialNumber(k, n);
    if (num !== undefined) return num;
    if (n.type === 2) return k.strs[n.inst] ?? "";
    if (n.type === 3) return n.inst === 1;
    if (n.type === 4) return undefined;
    return undefined;
  }
  const ctor = ctorOf(k, n);
  const kids = childrenOf(k, n);
  switch (ctor) {
    case "program": {
      // STAR-list children are spliced under `program` (CAPTURE splices
      // LIST-cat-0 bodies). Iterate kids directly.
      let last: unknown = undefined;
      for (const s of kids) last = evalNode(k, s, env);
      return last;
    }
    case "funcDecl": {
      const nameNode = kids[1]!;
      const name = k.strs[nameNode.inst] ?? "";
      const paramListN = kids[3]!;
      const body = kids[6]!;
      const params: string[] = [];
      if (!isNull(paramListN)) collectParams(k, paramListN, params);
      const closureEnv = env;
      const fn = (...args: unknown[]) => {
        const local = envNew(closureEnv);
        for (let i = 0; i < params.length; i++) {
          local.vars.set(params[i]!, args[i]);
        }
        try {
          evalNode(k, body, local);
          return undefined;
        } catch (e) {
          if (e instanceof ReturnSignal) return e.value;
          throw e;
        }
      };
      env.vars.set(name, fn);
      return fn;
    }
    case "interfaceDecl":
    case "typeAlias":
      return undefined;
    case "arrowFunc": {
      // children: ["(", paramList?, ")", returnAnnot?, "=>", body]
      const paramListN = kids[1]!;
      const body = kids[5]!;
      const params: string[] = [];
      if (!isNull(paramListN)) collectParams(k, paramListN, params);
      const closureEnv = env;
      return (...args: unknown[]) => {
        const local = envNew(closureEnv);
        for (let i = 0; i < params.length; i++) {
          local.vars.set(params[i]!, args[i]);
        }
        // Body is either a block (statement) or an expression.
        try {
          return evalNode(k, body, local);
        } catch (e) {
          if (e instanceof ReturnSignal) return e.value;
          throw e;
        }
      };
    }
    case "block": {
      const stmts = childrenOf(k, kids[1]!);
      const local = envNew(env);
      let last: unknown = undefined;
      for (const s of stmts) last = evalNode(k, s, local);
      return last;
    }
    case "varDecl": {
      // children: [kw, ident, typeAnnot?, ("=" expr)?, ";"?]
      const name = k.strs[kids[1]!.inst] ?? "";
      let val: unknown = undefined;
      if (!isNull(kids[3]!)) {
        const initKids = childrenOf(k, kids[3]!);
        val = evalNode(k, initKids[1]!, env);
      }
      env.vars.set(name, val);
      return val;
    }
    case "ifStmt": {
      const cond = evalNode(k, kids[2]!, env);
      if (cond) return evalNode(k, kids[4]!, env);
      if (!isNull(kids[5]!)) {
        const elseKids = childrenOf(k, kids[5]!);
        return evalNode(k, elseKids[1]!, env);
      }
      return undefined;
    }
    case "forStmt": {
      const local = envNew(env);
      if (!isNull(kids[2]!)) evalNode(k, kids[2]!, local);
      while (true) {
        if (!isNull(kids[4]!)) {
          if (!evalNode(k, kids[4]!, local)) break;
        }
        evalNode(k, kids[8]!, local);
        if (!isNull(kids[6]!)) evalNode(k, kids[6]!, local);
      }
      return undefined;
    }
    case "forOfStmt": {
      const name = k.strs[kids[3]!.inst] ?? "";
      const iter = evalNode(k, kids[5]!, env) as Iterable<unknown>;
      for (const item of iter) {
        const local = envNew(env);
        local.vars.set(name, item);
        evalNode(k, kids[7]!, local);
      }
      return undefined;
    }
    case "whileStmt": {
      while (evalNode(k, kids[2]!, env)) {
        evalNode(k, kids[4]!, env);
      }
      return undefined;
    }
    case "returnStmt": {
      const v = isNull(kids[1]!) ? undefined : evalNode(k, kids[1]!, env);
      throw new ReturnSignal(v);
    }
    case "exprStmt": return evalNode(k, kids[0]!, env);
    case "conditional": {
      const head = evalNode(k, kids[0]!, env);
      if (isNull(kids[1]!)) return head;
      const t = childrenOf(k, kids[1]!);
      return head ? evalNode(k, t[1]!, env) : evalNode(k, t[3]!, env);
    }
    case "assignment": {
      if (isNull(kids[1]!)) return evalNode(k, kids[0]!, env);
      const t = childrenOf(k, kids[1]!);
      const op = k.strs[t[0]!.inst] ?? "=";
      const rhs = evalNode(k, t[1]!, env);
      assignTo(k, kids[0]!, env, op, rhs);
      return rhs;
    }
    case "binOp": {
      let acc = evalNode(k, kids[0]!, env);
      const tail = childrenOf(k, kids[1]!);
      for (const pair of tail) {
        const pk = childrenOf(k, pair);
        const op = k.strs[pk[0]!.inst] ?? "";
        const rhs = evalNode(k, pk[1]!, env);
        acc = applyBinOp(op, acc, rhs);
      }
      return acc;
    }
    case "unary": {
      const op = k.strs[kids[0]!.inst] ?? "";
      const operand = kids[1]!;
      switch (op) {
        case "!": return !evalNode(k, operand, env);
        case "-": return -(evalNode(k, operand, env) as number);
        case "+": return +(evalNode(k, operand, env) as number);
        case "++": {
          const v = (evalNode(k, operand, env) as number) + 1;
          assignTo(k, operand, env, "=", v);
          return v;
        }
        case "--": {
          const v = (evalNode(k, operand, env) as number) - 1;
          assignTo(k, operand, env, "=", v);
          return v;
        }
        default: throw new Error(`unary: ${op}`);
      }
    }
    case "postfix": {
      const ops = childrenOf(k, kids[1]!);
      if (ops.length === 0) return evalNode(k, kids[0]!, env);
      // Read current value, then mutate via the underlying lvalue. The
      // postfix expression returns the pre-increment value.
      const inner = kids[0]!;
      const current = evalNode(k, inner, env) as number;
      for (const op of ops) {
        const opStr = k.strs[op.inst] ?? "";
        const delta = opStr === "++" ? 1 : -1;
        assignTo(k, inner, env, "=", current + delta);
      }
      return current;
    }
    case "callExpr": {
      let base = evalNode(k, kids[0]!, env);
      const tails = childrenOf(k, kids[1]!);
      let lastReceiver: unknown = undefined;
      for (const t of tails) {
        const tctor = ctorOf(k, t);
        const tkids = childrenOf(k, t);
        if (tctor === "callTail") {
          const args: unknown[] = [];
          if (!isNull(tkids[1]!)) collectArgs(k, tkids[1]!, env, args);
          const fn = base as (...a: unknown[]) => unknown;
          base = lastReceiver !== undefined
            ? (fn as unknown as Function).apply(lastReceiver, args)
            : fn(...args);
          lastReceiver = undefined;
        } else if (tctor === "indexTail") {
          lastReceiver = base;
          const idx = evalNode(k, tkids[1]!, env);
          base = (base as Record<string | number, unknown>)[idx as string | number];
        } else if (tctor === "memberTail") {
          lastReceiver = base;
          const name = k.strs[tkids[1]!.inst] ?? "";
          base = (base as Record<string, unknown>)[name];
        }
      }
      return base;
    }
    case "paren": return evalNode(k, kids[1]!, env);
    case "arrayLit": {
      const out: unknown[] = [];
      if (!isNull(kids[1]!)) {
        const inner = childrenOf(k, kids[1]!);
        out.push(evalNode(k, inner[0]!, env));
        const tail = childrenOf(k, inner[1]!);
        for (const pair of tail) {
          const pk = childrenOf(k, pair);
          out.push(evalNode(k, pk[1]!, env));
        }
      }
      return out;
    }
    case "objectLit": {
      const obj: Record<string, unknown> = {};
      if (!isNull(kids[1]!)) {
        const inner = childrenOf(k, kids[1]!);
        addMember(k, inner[0]!, obj, env);
        const tail = childrenOf(k, inner[1]!);
        for (const pair of tail) {
          const pk = childrenOf(k, pair);
          addMember(k, pk[1]!, obj, env);
        }
      }
      return obj;
    }
    case "strLit": {
      const raw = k.strs[kids[0]!.inst] ?? "";
      // Strip the surrounding quotes; decoder lives in tokenize but we
      // preserved raw form for round-trip fidelity. Re-decode here.
      return decodeStringEscapes(raw.substring(1, raw.length - 1));
    }
    case "templateLit": {
      const raw = k.strs[kids[0]!.inst] ?? "";
      return decodeStringEscapes(raw.substring(1, raw.length - 1));
    }
    case "numLit": {
      return trivialNumber(k, kids[0]!) ?? 0;
    }
    case "bigintLit": {
      return k.decodeInt64(kids[0]!.inst);
    }
    case "boolLit": {
      const t = k.strs[kids[0]!.inst] ?? "";
      return t === "true";
    }
    case "nullLit": return undefined;
    case "identExpr": {
      const name = k.strs[kids[0]!.inst] ?? "";
      return envGet(env, name);
    }
  }
  throw new Error(`eval: unhandled ctor "${ctor}"`);
}

function collectParams(k: Kernel, paramList: NodeID, out: string[]): void {
  // paramList capture children: [param, SEQ-list of (",", param) pairs]
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
}

function collectArgs(k: Kernel, argList: NodeID, env: Env, out: unknown[]): void {
  const kids = childrenOf(k, argList);
  out.push(evalNode(k, kids[0]!, env));
  const tail = childrenOf(k, kids[1]!);
  for (const pair of tail) {
    const pk = childrenOf(k, pair);
    out.push(evalNode(k, pk[1]!, env));
  }
}

function addMember(k: Kernel, member: NodeID, obj: Record<string, unknown>, env: Env): void {
  const kids = childrenOf(k, member);
  const keyNode = kids[0]!;
  let key: string;
  if (keyNode.level === Level.TRIVIAL) {
    key = k.strs[keyNode.inst] ?? "";
  } else {
    // string-literal key
    const keyKids = childrenOf(k, keyNode);
    const raw = k.strs[keyKids[0]!.inst] ?? "";
    key = decodeStringEscapes(raw.substring(1, raw.length - 1));
  }
  obj[key] = evalNode(k, kids[2]!, env);
}

// Peel single-child wrapper ctors (conditional with no ternary,
// postfix with no ++/--) to reach the lvalue underneath. The captured
// recipe for `s` in `s = ...` walks: conditional(binOp...binOp(postfix(callExpr(identExpr(s), []))))).
function unwrapToLValue(k: Kernel, n: NodeID): NodeID {
  let cur = n;
  while (cur.level !== Level.TRIVIAL) {
    const ctor = ctorOf(k, cur);
    const kids = childrenOf(k, cur);
    if (ctor === "conditional" && kids.length >= 2 && isNull(kids[1]!)) { cur = kids[0]!; continue; }
    if (ctor === "binOp" && kids.length >= 2 && childrenOf(k, kids[1]!).length === 0) { cur = kids[0]!; continue; }
    if (ctor === "postfix" && kids.length >= 2 && childrenOf(k, kids[1]!).length === 0) { cur = kids[0]!; continue; }
    if (ctor === "assignment" && kids.length >= 2 && isNull(kids[1]!)) { cur = kids[0]!; continue; }
    break;
  }
  return cur;
}

function assignTo(k: Kernel, lhs: NodeID, env: Env, op: string, rhs: unknown): void {
  const target = unwrapToLValue(k, lhs);
  const tctor = ctorOf(k, target);
  const tkids = childrenOf(k, target);
  if (tctor === "callExpr") {
    // callExpr children: [primary, STAR-list of tails]. Tail-less case
    // is just an identifier read; otherwise, the last tail decides the
    // assignment target (member or index).
    const tails = childrenOf(k, tkids[1]!);
    if (tails.length === 0) {
      // Drill into primary, which should be identExpr.
      const prim = tkids[0]!;
      const pctor = ctorOf(k, prim);
      if (pctor === "identExpr") {
        const name = k.strs[childrenOf(k, prim)[0]!.inst] ?? "";
        const cur = (() => { try { return envGet(env, name); } catch { return undefined; } })();
        envSet(env, name, applyAssignOp(op, cur, rhs));
        return;
      }
    } else {
      // Evaluate base = primary applied through tails[0..n-2], then
      // assign to the last tail (memberTail or indexTail).
      let base: unknown = evalNode(k, tkids[0]!, env);
      for (let i = 0; i < tails.length - 1; i++) {
        const t = tails[i]!;
        const tk = childrenOf(k, t);
        const tc = ctorOf(k, t);
        if (tc === "memberTail") base = (base as Record<string, unknown>)[k.strs[tk[1]!.inst] ?? ""];
        else if (tc === "indexTail") base = (base as Record<string | number, unknown>)[evalNode(k, tk[1]!, env) as string | number];
        else if (tc === "callTail") {
          // Calls in the middle of an lvalue chain are not generally
          // assignable, but evaluating preserves side effects.
          const args: unknown[] = [];
          if (!isNull(tk[1]!)) collectArgs(k, tk[1]!, env, args);
          base = (base as (...a: unknown[]) => unknown)(...args);
        }
      }
      const last = tails[tails.length - 1]!;
      const lk = childrenOf(k, last);
      const lc = ctorOf(k, last);
      if (lc === "memberTail") {
        const name = k.strs[lk[1]!.inst] ?? "";
        const cur = (base as Record<string, unknown>)[name];
        (base as Record<string, unknown>)[name] = applyAssignOp(op, cur, rhs);
        return;
      }
      if (lc === "indexTail") {
        const idx = evalNode(k, lk[1]!, env) as string | number;
        const cur = (base as Record<string | number, unknown>)[idx];
        (base as Record<string | number, unknown>)[idx] = applyAssignOp(op, cur, rhs);
        return;
      }
    }
  } else if (tctor === "identExpr") {
    const name = k.strs[tkids[0]!.inst] ?? "";
    const cur = (() => { try { return envGet(env, name); } catch { return undefined; } })();
    envSet(env, name, applyAssignOp(op, cur, rhs));
    return;
  }
  throw new Error(`assignment: cannot assign to ctor "${tctor}"`);
}

function applyAssignOp(op: string, cur: unknown, rhs: unknown): unknown {
  switch (op) {
    case "=": return rhs;
    case "+=": return (cur as number) + (rhs as number);
    case "-=": return (cur as number) - (rhs as number);
    case "*=": return (cur as number) * (rhs as number);
    case "/=": return (cur as number) / (rhs as number);
  }
  throw new Error(`assignment: unknown op "${op}"`);
}

function applyBinOp(op: string, a: unknown, b: unknown): unknown {
  const na = a as number;
  const nb = b as number;
  switch (op) {
    case "+":
      if (typeof a === "string" || typeof b === "string") return String(a) + String(b);
      return na + nb;
    case "-": return na - nb;
    case "*": return na * nb;
    case "/": return na / nb;
    case "%": return na % nb;
    case "<": return na < nb;
    case "<=": return na <= nb;
    case ">": return na > nb;
    case ">=": return na >= nb;
    case "==": return a == b;
    case "!=": return a != b;
    case "===": return a === b;
    case "!==": return a !== b;
    case "&&": return a && b;
    case "||": return a || b;
  }
  throw new Error(`binOp: ${op}`);
}

// evalTypeScript — walk a parsed program in a fresh environment seeded
// with stdlib bindings. Returns the final environment so callers can
// invoke declared functions.
function evalTypeScriptEnv(k: Kernel, recipe: NodeID): Env {
  const env = envNew();
  // Minimal stdlib bindings exercised by the test suite.
  env.vars.set("console", { log: (...args: unknown[]) => console.log(...args) });
  env.vars.set("Math", Math);
  env.vars.set("Map", Map);
  env.vars.set("Set", Set);
  env.vars.set("Promise", Promise);
  env.vars.set("JSON", JSON);
  env.vars.set("Array", Array);
  return env;
}

export function evalTypeScript(k: Kernel, recipe: NodeID): Env {
  const env = evalTypeScriptEnv(k, recipe);
  evalNode(k, recipe, env);
  return env;
}

// evalTypeScriptValue — last program value for parity gates (ts-eval).
export function evalTypeScriptValue(k: Kernel, recipe: NodeID): unknown {
  const env = evalTypeScriptEnv(k, recipe);
  return evalNode(k, recipe, env);
}

export function callFunction(env: Env, name: string, ...args: unknown[]): unknown {
  const fn = envGet(env, name) as (...a: unknown[]) => unknown;
  return fn(...args);
}
