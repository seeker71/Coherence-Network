// languages.ts — language-as-substrate-cell architecture.
//
// Languages are not hardcoded in the kernel; they are substrate-resident
// cells. A `Language` carries an ingestion grammar (parse rules) and an
// emission template (emit rules) as NodeID-rooted trees. Generic
// parse_through / emit_through walkers consume the grammar cells to
// turn source text into Form recipe trees, and recipe trees back into
// source text.
//
// This is the structural twin of format-recipes-as-substrate-cells
// (formats.ts). One canonical contract (language.canonical.json), many
// per-language populations (Python, TypeScript, Go, Rust — deferred to
// tasks #15-18).
//
// The N+M reframing of transpilation:
//   Without substrate languages: N source languages × M target
//     languages = N×M pairwise transpilers, each its own codebase.
//   With substrate languages: N ingest grammars + M emit templates,
//     all routed through one canonical recipe tree. Any source goes to
//     any target by composition.
//
// Semantically-equivalent code in two languages produces identical
// recipe sub-trees (content-addressed NodeIDs) — cross-language
// identity comes for free, the same way cross-kernel format identity
// did.
//
// See docs/coherence-substrate/language-cells.md for the broader
// teaching and docs/coherence-substrate/language.canonical.json for
// the schema template.

import {
  Kernel,
  Level,
  RBasic,
  type NodeID,
} from "./kernel.ts";
import type { FormatRecipe } from "./formats.ts";

// ---------------------------------------------------------------------------
// RBasic.LANGUAGE — well-known category for Language cells.
// ---------------------------------------------------------------------------
//
// Aligned with the canonical numbering plan: 50 = format, 51 = numeric,
// 60 = language. Cross-kernel agreement requires every implementation to
// use the same value.
export const RBasicLanguage = 60;

// Grammar production kinds — the small alphabet of parse-rule nodes.
// Each kind is a category whose children carry the production's
// parameters. New kinds are substrate writes, not kernel patches.
export const GrammarRuleKind = {
  // Match a literal string token. children: [string-trivial].
  LITERAL: 1,
  // Match any of a set of alternatives, first that matches wins.
  // children: [rule-ref...].
  ALT: 2,
  // Match a sequence of rules in order. children: [rule-ref...].
  SEQ: 3,
  // Match zero or more occurrences of one rule. children: [rule-ref].
  STAR: 4,
  // Match one or more occurrences. children: [rule-ref].
  PLUS: 5,
  // Match the rule optionally (zero or one). children: [rule-ref].
  OPT: 6,
  // Match by a kernel-builtin token class (e.g. "number", "ident",
  // "whitespace"). children: [string-trivial naming the class].
  TOKEN_CLASS: 7,
  // Reference another named rule. children: [string-trivial rule-name].
  RULE_REF: 8,
  // Capture the matched span under a recipe constructor. children:
  // [string-trivial ctor-name, rule-ref body].
  CAPTURE: 9,
} as const;

export type GrammarRuleKindCode =
  (typeof GrammarRuleKind)[keyof typeof GrammarRuleKind];

// Emission template kinds — the dual alphabet, used by emit_through to
// walk a recipe tree and produce source text.
export const EmitRuleKind = {
  // Emit a literal string. children: [string-trivial].
  LITERAL: 1,
  // Emit the result of recursively emitting a child of the current
  // recipe node. children: [int-trivial child-index].
  CHILD: 2,
  // Emit each child separated by a literal. children: [string-trivial
  // separator, int-trivial first-child-index, int-trivial last-or-neg-1].
  JOIN_CHILDREN: 3,
  // Dispatch to a per-category emit template. children: [int-trivial
  // category-marker, rule-ref template].
  WHEN_CATEGORY: 4,
  // Sequence of emits. children: [rule-ref...].
  SEQ: 5,
} as const;

export type EmitRuleKindCode =
  (typeof EmitRuleKind)[keyof typeof EmitRuleKind];

// ---------------------------------------------------------------------------
// Language — the meta-structure.
// ---------------------------------------------------------------------------
//
// A Language carries:
//   • name             diagnostic identifier (e.g. "python", "rpn")
//   • version          semver-shaped string; bumps invalidate cached NodeIDs
//   • ingestion_grammar  NodeID of the root grammar rule (typically an ALT
//                        over top-level productions, or a single SEQ)
//   • emission_template  NodeID of the root emit rule
//   • stdlib_bindings    name → recipe NodeID (e.g. "len" → list-length cell)
//   • numeric_defaults   per-language numeric-type name → format-recipe
//                        (e.g. for Python, "int" → BigInt-like,
//                        "float" → FP64; for Rust, "i32" → INT32 format)
//
// Two semantically-equivalent ingestion grammars (same rule tree
// structure) intern to the same NodeID. That's how cross-language
// equivalence becomes structural rather than nominal.
export interface Language {
  readonly nodeID: NodeID;
  readonly name: string;
  readonly version: string;
  readonly ingestionGrammar: NodeID;
  readonly emissionTemplate: NodeID;
  readonly stdlibBindings: ReadonlyMap<string, NodeID>;
  readonly numericDefaults: ReadonlyMap<string, FormatRecipe>;
}

// LanguageSpec — the populator's input to register_language. The
// grammar and template are passed as already-interned NodeIDs (the
// caller builds them via the grammar-builder helpers below).
export interface LanguageSpec {
  readonly name: string;
  readonly version: string;
  readonly ingestionGrammar: NodeID;
  readonly emissionTemplate: NodeID;
  readonly stdlibBindings?: ReadonlyMap<string, NodeID>;
  readonly numericDefaults?: ReadonlyMap<string, FormatRecipe>;
}

// ---------------------------------------------------------------------------
// Grammar-builder helpers — convenience wrappers around `intern` for the
// recipe shapes the parser walker understands. Each returns a NodeID
// the caller composes into larger rules.
// ---------------------------------------------------------------------------

function ruleCategory(k: Kernel, kind: GrammarRuleKindCode): NodeID {
  // Grammar rule recipes sit under RBasic.LANGUAGE with inst = kind.
  // Two rules with the same kind + children intern to the same NodeID.
  return { pkg: 1, level: Level.BASIC, type: RBasicLanguage, inst: kind };
}

function emitCategory(k: Kernel, kind: EmitRuleKindCode): NodeID {
  // Emit rules share the LANGUAGE category but use the high bit to
  // distinguish from grammar rules. inst = 0x80 | kind keeps the two
  // namespaces disjoint while sharing the same RBasic slot.
  return { pkg: 1, level: Level.BASIC, type: RBasicLanguage, inst: 0x80 | kind };
}

export function gLiteral(k: Kernel, text: string): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.LITERAL), [k.internString(text)]);
}

export function gTokenClass(k: Kernel, className: string): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.TOKEN_CLASS), [
    k.internString(className),
  ]);
}

export function gRuleRef(k: Kernel, name: string): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.RULE_REF), [k.internString(name)]);
}

export function gAlt(k: Kernel, ...alts: NodeID[]): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.ALT), alts);
}

export function gSeq(k: Kernel, ...parts: NodeID[]): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.SEQ), parts);
}

export function gStar(k: Kernel, body: NodeID): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.STAR), [body]);
}

export function gPlus(k: Kernel, body: NodeID): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.PLUS), [body]);
}

export function gOpt(k: Kernel, body: NodeID): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.OPT), [body]);
}

export function gCapture(k: Kernel, ctorName: string, body: NodeID): NodeID {
  return k.intern(ruleCategory(k, GrammarRuleKind.CAPTURE), [
    k.internString(ctorName),
    body,
  ]);
}

// Symmetric emit-builders.

export function eLiteral(k: Kernel, text: string): NodeID {
  return k.intern(emitCategory(k, EmitRuleKind.LITERAL), [k.internString(text)]);
}

export function eChild(k: Kernel, index: number): NodeID {
  return k.intern(emitCategory(k, EmitRuleKind.CHILD), [k.internTrivialInt(index)]);
}

export function eJoin(k: Kernel, separator: string, first = 0, last = -1): NodeID {
  return k.intern(emitCategory(k, EmitRuleKind.JOIN_CHILDREN), [
    k.internString(separator),
    k.internTrivialInt(first),
    k.internTrivialInt(last),
  ]);
}

export function eSeq(k: Kernel, ...parts: NodeID[]): NodeID {
  return k.intern(emitCategory(k, EmitRuleKind.SEQ), parts);
}

// ---------------------------------------------------------------------------
// Language registry — interns the Language cell itself.
// ---------------------------------------------------------------------------

// The Language cell has inst = 0xFF (a reserved instance marker so it
// is disjoint from grammar/emit rules under RBasic.LANGUAGE). Children:
//   [name-string, version-string, ingestion-grammar, emission-template,
//    stdlib-binding-list, numeric-defaults-list].
//
// Two Languages with identical name+version+grammar+template+bindings
// intern to the same NodeID.
const LANGUAGE_CELL_INST = 0xff;

export function registerLanguage(k: Kernel, spec: LanguageSpec): Language {
  const cat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasicLanguage,
    inst: LANGUAGE_CELL_INST,
  };

  // Encode stdlib bindings as a flat SEQUENCE of (name, recipe-ref)
  // pairs. The recipe-ref is the binding's NodeID directly.
  const stdlibChildren: NodeID[] = [];
  if (spec.stdlibBindings) {
    for (const [name, ref] of spec.stdlibBindings) {
      stdlibChildren.push(k.internString(name));
      stdlibChildren.push(ref);
    }
  }
  const stdlibList = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    stdlibChildren,
  );

  // Numeric defaults: per-language numeric-type name → format-recipe
  // NodeID. Encoded the same way as stdlib_bindings.
  const numericChildren: NodeID[] = [];
  if (spec.numericDefaults) {
    for (const [name, fmt] of spec.numericDefaults) {
      numericChildren.push(k.internString(name));
      numericChildren.push(fmt.nodeID);
    }
  }
  const numericList = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
    numericChildren,
  );

  const nodeID = k.intern(cat, [
    k.internString(spec.name),
    k.internString(spec.version),
    spec.ingestionGrammar,
    spec.emissionTemplate,
    stdlibList,
    numericList,
  ]);

  return {
    nodeID,
    name: spec.name,
    version: spec.version,
    ingestionGrammar: spec.ingestionGrammar,
    emissionTemplate: spec.emissionTemplate,
    stdlibBindings: spec.stdlibBindings ?? new Map(),
    numericDefaults: spec.numericDefaults ?? new Map(),
  };
}

// ---------------------------------------------------------------------------
// parse_through — generic top-down backtracking parser driven by the
// language's ingestion grammar.
// ---------------------------------------------------------------------------
//
// The walker reads grammar-rule nodes by category-inst and recurses
// according to the kind's semantics. Whitespace is skipped between
// tokens by default; built-in TOKEN_CLASS names cover "number",
// "ident", and "whitespace".
//
// The result is a recipe tree built from CAPTURE rules. Each CAPTURE
// produces a composite recipe whose category is `(BASIC, RBasic.LIST,
// inst=ctor-name-id)` and whose children are the captured sub-results
// in source order. Leaf tokens (number, ident) become trivial nodes.
//
// This is intentionally minimal — a vertical-slice proof that the
// grammar-as-substrate-cell shape is sufficient. Production parsers
// will grow Pratt operator-precedence, error recovery, source-map
// emission, etc. — all as grammar-rule extensions, not kernel patches.

export class ParseError extends Error {
  constructor(
    public readonly position: number,
    public readonly expectedRule: NodeID,
    message: string,
  ) {
    super(message);
    this.name = "ParseError";
  }
}

interface ParseState {
  readonly source: string;
  pos: number;
}

function skipWhitespace(state: ParseState): void {
  while (state.pos < state.source.length) {
    const ch = state.source.charCodeAt(state.pos);
    // space, tab, LF, CR
    if (ch === 32 || ch === 9 || ch === 10 || ch === 13) {
      state.pos++;
    } else {
      break;
    }
  }
}

function isDigit(ch: number): boolean {
  return ch >= 48 && ch <= 57;
}

function isIdentStart(ch: number): boolean {
  return (ch >= 65 && ch <= 90) || (ch >= 97 && ch <= 122) || ch === 95;
}

function isIdentCont(ch: number): boolean {
  return isIdentStart(ch) || isDigit(ch);
}

// matchRule — attempt to match `rule` at the current position. Returns
// a NodeID on success (the captured recipe; or a sentinel for non-
// capturing rules) and advances the state's pos; returns null on
// failure and leaves pos unchanged.
function matchRule(
  k: Kernel,
  rule: NodeID,
  state: ParseState,
): NodeID | null {
  const recipe = k.recipeAt(rule);
  if (!recipe) {
    // Trivial leaf — should not appear as a rule root, but tolerate.
    return rule;
  }
  const cat = recipe.category;
  // Grammar rules: category type = RBasicLanguage, inst < 0x80.
  // Emit rules use inst >= 0x80 and are handled separately.
  if (cat.type !== RBasicLanguage || cat.inst >= 0x80) {
    throw new Error(
      `parse_through: rule ${rule.inst} has non-grammar category ${cat.type}/${cat.inst}`,
    );
  }
  const kind = cat.inst as GrammarRuleKindCode;
  switch (kind) {
    case GrammarRuleKind.LITERAL: {
      skipWhitespace(state);
      const lit = strFromTrivial(k, recipe.children[0]!);
      if (state.source.startsWith(lit, state.pos)) {
        state.pos += lit.length;
        return k.internString(lit);
      }
      return null;
    }
    case GrammarRuleKind.TOKEN_CLASS: {
      skipWhitespace(state);
      const className = strFromTrivial(k, recipe.children[0]!);
      return matchTokenClass(k, className, state);
    }
    case GrammarRuleKind.RULE_REF: {
      // RULE_REF resolves by name from the active rule table. In this
      // vertical slice the caller wires the grammar without indirection,
      // so a RULE_REF should not appear at runtime; if it does, fall
      // through to a no-op match. Production parsers will keep a name→
      // NodeID table on the Language cell.
      return null;
    }
    case GrammarRuleKind.ALT: {
      for (const alt of recipe.children) {
        const saved = state.pos;
        const result = matchRule(k, alt, state);
        if (result !== null) return result;
        state.pos = saved;
      }
      return null;
    }
    case GrammarRuleKind.SEQ: {
      const saved = state.pos;
      const results: NodeID[] = [];
      for (const part of recipe.children) {
        const r = matchRule(k, part, state);
        if (r === null) {
          state.pos = saved;
          return null;
        }
        results.push(r);
      }
      // SEQ returns a synthetic list of its parts so CAPTURE above can
      // see the structure. The CAPTURE wraps; SEQ on its own is just
      // a tuple-ish gather.
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
        results,
      );
    }
    case GrammarRuleKind.STAR: {
      const body = recipe.children[0]!;
      const results: NodeID[] = [];
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const saved = state.pos;
        const r = matchRule(k, body, state);
        if (r === null) {
          state.pos = saved;
          break;
        }
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
      const first = matchRule(k, body, state);
      if (first === null) return null;
      results.push(first);
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const saved = state.pos;
        const r = matchRule(k, body, state);
        if (r === null) {
          state.pos = saved;
          break;
        }
        results.push(r);
      }
      return k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 0 },
        results,
      );
    }
    case GrammarRuleKind.OPT: {
      const body = recipe.children[0]!;
      const saved = state.pos;
      const r = matchRule(k, body, state);
      if (r !== null) return r;
      state.pos = saved;
      return k.internTrivialNull();
    }
    case GrammarRuleKind.CAPTURE: {
      const ctorName = strFromTrivial(k, recipe.children[0]!);
      const body = recipe.children[1]!;
      const inner = matchRule(k, body, state);
      if (inner === null) return null;
      // The CAPTURE wraps inner under a recipe whose category encodes
      // the ctor-name. Two CAPTUREs with the same ctor + same inner
      // tree intern to the same NodeID — cross-language equivalence.
      const ctorNameID = k.internName(ctorName);
      const ctorCat: NodeID = {
        pkg: 1,
        level: Level.BASIC,
        type: RBasic.LIST,
        inst: ctorNameID,
      };
      // If inner is a SEQ-list, splice its children directly so the
      // capture's children are the matched parts, not a wrapping list.
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

function matchTokenClass(
  k: Kernel,
  className: string,
  state: ParseState,
): NodeID | null {
  switch (className) {
    case "number": {
      const start = state.pos;
      let pos = start;
      const src = state.source;
      if (pos < src.length && src.charCodeAt(pos) === 45 /* '-' */) pos++;
      const numStart = pos;
      while (pos < src.length && isDigit(src.charCodeAt(pos))) pos++;
      if (pos === numStart) return null;
      let isFloat = false;
      if (pos < src.length && src.charCodeAt(pos) === 46 /* '.' */) {
        isFloat = true;
        pos++;
        while (pos < src.length && isDigit(src.charCodeAt(pos))) pos++;
      }
      const text = src.substring(start, pos);
      state.pos = pos;
      if (isFloat) {
        return k.internTrivialFloat64(parseFloat(text));
      }
      return k.internTrivialInt(parseInt(text, 10));
    }
    case "ident": {
      const start = state.pos;
      const src = state.source;
      if (start >= src.length || !isIdentStart(src.charCodeAt(start))) {
        return null;
      }
      let pos = start + 1;
      while (pos < src.length && isIdentCont(src.charCodeAt(pos))) pos++;
      const text = src.substring(start, pos);
      state.pos = pos;
      return k.internString(text);
    }
    case "whitespace": {
      const start = state.pos;
      skipWhitespace(state);
      if (state.pos === start) return null;
      return k.internTrivialNull();
    }
    default:
      throw new Error(`parse_through: unknown token class "${className}"`);
  }
}

function strFromTrivial(k: Kernel, n: NodeID): string {
  if (n.level !== Level.TRIVIAL) {
    throw new Error("strFromTrivial: not a trivial");
  }
  return k.strs[n.inst] ?? "";
}

// parseThrough — top-level entry. Walks the language's ingestion
// grammar against source_text and returns the resulting recipe tree.
// Throws ParseError on failure or if input remains unconsumed.
export function parseThrough(
  k: Kernel,
  lang: Language,
  sourceText: string,
): NodeID {
  const state: ParseState = { source: sourceText, pos: 0 };
  const result = matchRule(k, lang.ingestionGrammar, state);
  if (result === null) {
    throw new ParseError(
      state.pos,
      lang.ingestionGrammar,
      `parse failed at position ${state.pos} in language "${lang.name}"`,
    );
  }
  skipWhitespace(state);
  if (state.pos < sourceText.length) {
    throw new ParseError(
      state.pos,
      lang.ingestionGrammar,
      `unconsumed input at position ${state.pos} (${sourceText
        .substring(state.pos, state.pos + 16)
        .replace(/\n/g, "\\n")}...)`,
    );
  }
  return result;
}

// ---------------------------------------------------------------------------
// emit_through — generic emitter driven by the language's emission
// template.
// ---------------------------------------------------------------------------
//
// emitRule reads the template node and produces text. CHILD references
// look up the indexed child of the current "subject" recipe node and
// recursively emit through the template-for-its-category, if any.
// WHEN_CATEGORY entries declare per-ctor templates.
//
// For the vertical slice the template is a single root that emits the
// subject's children separated by a literal; production languages will
// build category-dispatch tables.

interface EmitState {
  readonly k: Kernel;
  out: string[];
}

function emitTrivial(state: EmitState, n: NodeID): void {
  switch (n.type) {
    case 1: // INT / INT32
      state.out.push(String(n.inst | 0));
      return;
    case 2: { // STRING
      const s = state.k.strs[n.inst] ?? "";
      state.out.push(s);
      return;
    }
    case 3: // BOOL
      state.out.push(n.inst ? "true" : "false");
      return;
    case 4: // NULL
      state.out.push("null");
      return;
    case 7: // FLOAT64
      state.out.push(String(state.k.decodeFloat64(n.inst)));
      return;
    default:
      state.out.push(`<trivial:${n.type}:${n.inst}>`);
  }
}

function emitRule(
  state: EmitState,
  template: NodeID,
  subject: NodeID,
): void {
  const k = state.k;
  const recipe = k.recipeAt(template);
  if (!recipe) {
    // Template is a trivial — emit subject as-is.
    emitSubject(state, subject);
    return;
  }
  const cat = recipe.category;
  if (cat.type !== RBasicLanguage || cat.inst < 0x80) {
    throw new Error(
      `emit_through: template ${template.inst} is not an emit rule (cat ${cat.type}/${cat.inst})`,
    );
  }
  const kind = (cat.inst & 0x7f) as EmitRuleKindCode;
  switch (kind) {
    case EmitRuleKind.LITERAL: {
      state.out.push(strFromTrivial(k, recipe.children[0]!));
      return;
    }
    case EmitRuleKind.CHILD: {
      const idx = recipe.children[0]!.inst | 0;
      const subjectRecipe = k.recipeAt(subject);
      if (!subjectRecipe) {
        emitTrivial(state, subject);
        return;
      }
      const child = subjectRecipe.children[idx];
      if (child) emitSubject(state, child);
      return;
    }
    case EmitRuleKind.JOIN_CHILDREN: {
      const sep = strFromTrivial(k, recipe.children[0]!);
      const first = recipe.children[1]!.inst | 0;
      const lastRaw = recipe.children[2]!.inst | 0;
      const subjectRecipe = k.recipeAt(subject);
      if (!subjectRecipe) return;
      const kids = subjectRecipe.children;
      const last = lastRaw < 0 ? kids.length - 1 : Math.min(lastRaw, kids.length - 1);
      for (let i = first; i <= last; i++) {
        if (i > first) state.out.push(sep);
        emitSubject(state, kids[i]!);
      }
      return;
    }
    case EmitRuleKind.SEQ: {
      for (const part of recipe.children) {
        emitRule(state, part, subject);
      }
      return;
    }
    case EmitRuleKind.WHEN_CATEGORY: {
      // The first child carries the category-marker we match against;
      // the second child is the template to apply if it matches. This
      // is rudimentary dispatch — production templates will use a
      // map keyed by category. For now, always apply.
      emitRule(state, recipe.children[1]!, subject);
      return;
    }
  }
}

function emitSubject(state: EmitState, subject: NodeID): void {
  if (subject.level === Level.TRIVIAL) {
    emitTrivial(state, subject);
    return;
  }
  // Composite: emit each child with whitespace by default (the
  // template's job to override).
  const recipe = state.k.recipeAt(subject);
  if (!recipe) return;
  for (let i = 0; i < recipe.children.length; i++) {
    if (i > 0) state.out.push(" ");
    emitSubject(state, recipe.children[i]!);
  }
}

export function emitThrough(
  k: Kernel,
  lang: Language,
  recipeTree: NodeID,
): string {
  const state: EmitState = { k, out: [] };
  emitRule(state, lang.emissionTemplate, recipeTree);
  return state.out.join("");
}

// ---------------------------------------------------------------------------
// Helpers for downstream tooling (used by smoke tests and per-language
// implementations to inspect captured trees).
// ---------------------------------------------------------------------------

// capturedCtor — read back the ctor name from a captured recipe node.
// Returns "" if `n` was not produced by a CAPTURE rule.
export function capturedCtor(k: Kernel, n: NodeID): string {
  const recipe = k.recipeAt(n);
  if (!recipe) return "";
  if (recipe.category.type !== RBasic.LIST) return "";
  if (recipe.category.inst === 0) return "";
  return k.strs[recipe.category.inst] ?? "";
}

// capturedChildren — recipe children, in source order.
export function capturedChildren(k: Kernel, n: NodeID): readonly NodeID[] {
  const r = k.recipeAt(n);
  return r ? r.children : [];
}
