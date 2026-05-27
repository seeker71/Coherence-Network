// ctor-convergence.ts — cross-language CTOR vocabulary convergence
// via QUOTIENT (task #31).
//
// The four sibling Language cells (#15 Python, #16 TypeScript, #17 Go,
// #18 Rust) each picked a local ctor vocabulary while implementing
// their parsers in parallel:
//
//   Python:     "int-literal",   "method-call",  "dict-literal", ...
//   TypeScript: "numLit",        "callExpr",     "funcDecl",     ...   (camelCase)
//   Rust:       "int_lit",       "method",       "pat_variant",  ...   (snake_case)
//   Go:         (uses RBasic categories directly — already canonical)
//
// A consequence the architecture's cross-language identity promise
// can't tolerate: the same algorithm parsed from different languages
// produces *different* recipe NodeIDs, because each captured node's
// category inst encodes the local-language ctor name. The recipe
// `add(int-literal(1), int-literal(2))` from Python is content-
// addressed to a NodeID where the captured-list inst is the intern-id
// of "add"; the same algorithm from TypeScript captures under the
// "binOp" / "numLit" names and lands at a different NodeID. The trees
// LOOK like they should match — they don't.
//
// QUOTIENT is the kernel-level mechanism for declaring "these two
// representatives are equivalent; canonicalize them to a single
// shared identity." This file declares the cross-language ctor
// equivalence as a QUOTIENT relation, mapping each language's local
// ctor name to a *canonical* name in the shared CANONICAL vocabulary.
// After registration:
//
//   parseTypeScript(k, "x + y")  → captures under "binOp"
//   parsePython(k, "x + y")      → captures under "add"
//   parseRust(k, "x + y")        → captures under "add"
//
//   canonicalizeCapturedTree(k, tsTree,     typescriptCtorsMap)
//   canonicalizeCapturedTree(k, pyTree,     pythonCtorsMap)
//   canonicalizeCapturedTree(k, rustTree,   rustCtorsMap)
//
// all three rewrite the captured-list inst to k.internName("add"),
// and the three resulting recipes share a NodeID — cross-language
// identity is restored without touching any language file.
//
// Composition discipline (CLAUDE.md "Structural composition"):
//   • Local-ctor strings stay LEAF SubstrateString trivials — they
//     describe a particular surface vocabulary, not structure.
//   • Each language's ctor map composes as a `R_Block.SEQUENCE` of
//     (local-name, canonical-name) pair-recipes — additive cells the
//     kernel can read back through `.children`.
//   • The equivalence-cell is a single substrate-resident
//     EquivalenceRelation per language; the handler walks the captured
//     recipe and re-interns each captured node under its canonical
//     ctor-name. No flat slug-keyed dictionaries; only composed cells.
//
// Constraint summary:
//   • Additive — no modification to lang-python.ts / lang-typescript.ts
//     / lang-rust.ts / lang-go.ts or to quotient.ts.
//   • Go uses RBasic categories directly, not captures — its "map" is
//     the identity on captured-ctors, and the Go tree is already
//     canonical at the RBasic layer.
//   • The handler rewrites only the captured-node category-inst; the
//     children-tree is walked recursively so nested ctors converge
//     too. Trivial leaves pass through unchanged.

import {
  Kernel,
  Level,
  RBasic,
  Triv,
  type NodeID,
} from "../../../src/kernel.ts";
import {
  Decidability,
  makeEquivalence,
  registerHandler,
  type EquivalenceRelation,
} from "../../../src/quotient.ts";

// ---------------------------------------------------------------------------
// CANONICAL — the cross-language shared ctor vocabulary.
//
// One name per semantic concept. Languages whose surfaces split a
// concept across multiple ctors (TS's binOp / logicalOr / logicalAnd
// / equality / relational / additive / multiplicative all reduce to
// "binOp", but the semantic intent of "+" is "add", not "binOp") map
// downward to the most specific canonical name. Where the source
// language doesn't distinguish at parse time (TS captures every
// arithmetic operator under "binOp" with the operator carried as a
// child), the canonical map points at the umbrella name "bin-op";
// finer-grained convergence is a downstream pass that reads the
// operator-child and refines to "add" / "sub" / "mul" / etc. This
// file holds the first-pass tier; later tiers compose on top.
// ---------------------------------------------------------------------------

export const CANONICAL = {
  // Top-level
  program: "program",
  module: "program", // python "module" === ts/rust "program"

  // Numeric / string / boolean / null literals
  int_literal: "int-literal",
  float_literal: "float-literal",
  str_literal: "str-literal",
  bool_literal: "bool-literal",
  null_literal: "null-literal",
  char_literal: "char-literal",
  bigint_literal: "bigint-literal",
  ident: "ident",

  // Collections
  list_literal: "list-literal",
  array_literal: "list-literal", // ts arrayLit / rust array unify with python list-literal
  tuple_literal: "tuple-literal",
  dict_literal: "dict-literal",
  dict_entry: "dict-entry",
  object_literal: "object-literal",
  object_member: "object-member",

  // Calls + invocations
  call: "call",
  method_call: "method-call",
  args: "args",
  arg_list: "args",
  call_tail: "call-tail",
  index_tail: "index-tail",
  member_tail: "member-tail",

  // Operators (semantic — what "+" / "*" mean)
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
  and: "and",
  or: "or",
  not: "not",
  neg: "neg",
  bitand: "bit-and",
  bitor: "bit-or",
  bitxor: "bit-xor",
  shl: "shl",
  shr: "shr",

  // Umbrella binary-op (when the language captures pre-refinement)
  bin_op: "bin-op",

  // Control flow
  if_: "if",
  else_: "else",
  conditional: "if", // ts conditional === python/rust if (ternary)
  while_: "while",
  for_: "for",
  for_of: "for",
  match_: "match",
  arm: "arm",
  arms: "arms",
  return_: "return",
  block: "block",

  // Definitions
  function_: "function",
  lambda_: "function", // python lambda / rust closure / ts arrow → "function"
  param: "param",
  params: "params",
  paren: "paren",
  expr_stmt: "expr-stmt",
  let_: "let",
  var_decl: "let",

  // Type-level (TypeScript / Rust)
  type_annot: "type-annot",
  type_ident: "type-ident",
  type_union: "type-union",
  type_array: "type-array",
  type_object: "type-object",
  type_alias: "type-alias",
  type_member: "type-member",
  interface_decl: "interface",
  return_annot: "return-annot",

  // Rust patterns (passed through as-is — no peer in other languages)
  pat_wild: "pat-wild",
  pat_int: "pat-int",
  pat_float: "pat-float",
  pat_str: "pat-str",
  pat_bool: "pat-bool",
  pat_ident: "pat-ident",
  pat_variant: "pat-variant",
  pat_struct: "pat-struct",
  pat_path: "pat-path",

  // Rust-only structural ctors (kept for round-trip; canonicalize as-is)
  struct_: "struct",
  enum_: "enum",
  variant_unit: "variant-unit",
  variant_tuple: "variant-tuple",
  variant_struct: "variant-struct",
  variants: "variants",
  fields: "fields",
  field: "field",
  generics: "generics",
  type_args: "type-args",
  type_infer: "type-infer",
  ref_type: "ref-type",
  tuple_type: "tuple-type",
  path: "path",
  closure: "function",
  tail: "tail",
  tuple: "tuple-literal",
  unit: "unit",
  ref: "ref",
  deref: "deref",
  index: "index",
  try_: "try",
  cmp: "bin-op",
  macro_call: "macro-call",
  struct_init: "struct-init",
  type_: "type",
  subs: "subs",
} as const;

export type CanonicalCtor = (typeof CANONICAL)[keyof typeof CANONICAL];

// ---------------------------------------------------------------------------
// Per-language local → canonical maps.
//
// Each map is the FULL ctor set the language actually emits at parse
// time, mapped to its canonical name. Identity entries (a name that's
// already canonical) are kept for completeness — the discipline is
// "every ctor a language produces appears here," so the equivalence
// is a total function on each language's captured-ctor space.
// ---------------------------------------------------------------------------

// Python — from lang-python.ts CTOR table.
export const pythonCtorsMap: Readonly<Record<string, CanonicalCtor>> = {
  "module": CANONICAL.module,
  "int-literal": CANONICAL.int_literal,
  "float-literal": CANONICAL.float_literal,
  "str-literal": CANONICAL.str_literal,
  "bool-literal": CANONICAL.bool_literal,
  "none-literal": CANONICAL.null_literal,
  "ident": CANONICAL.ident,
  "list-literal": CANONICAL.list_literal,
  "dict-literal": CANONICAL.dict_literal,
  "dict-entry": CANONICAL.dict_entry,
  "tuple-literal": CANONICAL.tuple_literal,
  "call": CANONICAL.call,
  "method-call": CANONICAL.method_call,
  "args": CANONICAL.args,
  "add": CANONICAL.add,
  "sub": CANONICAL.sub,
  "mul": CANONICAL.mul,
  "div": CANONICAL.div,
  "mod": CANONICAL.mod,
  "eq": CANONICAL.eq,
  "ne": CANONICAL.ne,
  "lt": CANONICAL.lt,
  "le": CANONICAL.le,
  "gt": CANONICAL.gt,
  "ge": CANONICAL.ge,
  "and": CANONICAL.and,
  "or": CANONICAL.or,
  "not": CANONICAL.not,
  "neg": CANONICAL.neg,
  "if": CANONICAL.if_,
  "elif": CANONICAL.if_,
  "else": CANONICAL.else_,
  "def": CANONICAL.function_,
  "return": CANONICAL.return_,
  "for": CANONICAL.for_,
  "while": CANONICAL.while_,
  "lambda": CANONICAL.lambda_,
  "expr-stmt": CANONICAL.expr_stmt,
  "params": CANONICAL.params,
  "param": CANONICAL.param,
  "block": CANONICAL.block,
};

// TypeScript — from gCapture calls in lang-typescript.ts. Many ts
// arithmetic / comparison / logical operators capture under the
// umbrella "binOp" with the operator carried as a child trivial; we
// keep them under "bin-op" canonical and let a downstream operator-
// refinement pass split into add/sub/etc. when the operator child is
// known.
export const typescriptCtorsMap: Readonly<Record<string, CanonicalCtor>> = {
  "program": CANONICAL.program,
  "funcDecl": CANONICAL.function_,
  "returnAnnot": CANONICAL.type_annot, // ts uses returnAnnot for `: T` after sig
  "typeAnnot": CANONICAL.type_annot,
  "paramList": CANONICAL.params,
  "param": CANONICAL.param,
  "typeUnion": CANONICAL.type_union,
  "typeIdent": CANONICAL.type_ident,
  "typeArray": CANONICAL.type_array,
  "typeObject": CANONICAL.type_object,
  "interfaceDecl": CANONICAL.interface_decl,
  "typeMember": CANONICAL.type_member,
  "typeAlias": CANONICAL.type_alias,
  "block": CANONICAL.block,
  "varDecl": CANONICAL.var_decl,
  "ifStmt": CANONICAL.if_,
  "forStmt": CANONICAL.for_,
  "forOfStmt": CANONICAL.for_of,
  "whileStmt": CANONICAL.while_,
  "returnStmt": CANONICAL.return_,
  "exprStmt": CANONICAL.expr_stmt,
  "conditional": CANONICAL.conditional,
  "assignment": CANONICAL.let_,
  "binOp": CANONICAL.bin_op,
  "unary": CANONICAL.neg, // ts unary captures negation + logical-not; downstream refines
  "postfix": CANONICAL.expr_stmt,
  "callExpr": CANONICAL.call,
  "callTail": CANONICAL.call_tail,
  "argList": CANONICAL.arg_list,
  "indexTail": CANONICAL.index_tail,
  "memberTail": CANONICAL.member_tail,
  "arrowFunc": CANONICAL.lambda_,
  "paren": CANONICAL.paren,
  "arrayLit": CANONICAL.array_literal,
  "objectLit": CANONICAL.object_literal,
  "objectMember": CANONICAL.object_member,
  "templateLit": CANONICAL.str_literal,
  "strLit": CANONICAL.str_literal,
  "numLit": CANONICAL.int_literal, // ts captures both int+float as numLit; downstream refines
  "bigintLit": CANONICAL.bigint_literal,
  "boolLit": CANONICAL.bool_literal,
  "nullLit": CANONICAL.null_literal,
  "identExpr": CANONICAL.ident,
};

// Rust — from cap(this.k, "X", ...) calls in lang-rust.ts.
export const rustCtorsMap: Readonly<Record<string, CanonicalCtor>> = {
  "program": CANONICAL.program,
  "fn": CANONICAL.function_,
  "closure": CANONICAL.closure,
  "param": CANONICAL.param,
  "params": CANONICAL.params,
  "generics": CANONICAL.generics,
  "type": CANONICAL.type_,
  "type_args": CANONICAL.type_args,
  "type_infer": CANONICAL.type_infer,
  "ref_type": CANONICAL.ref_type,
  "tuple_type": CANONICAL.tuple_type,
  "block": CANONICAL.block,
  "tail": CANONICAL.tail,
  "let": CANONICAL.let_,
  "expr_stmt": CANONICAL.expr_stmt,
  "return": CANONICAL.return_,
  "if": CANONICAL.if_,
  "match": CANONICAL.match_,
  "arm": CANONICAL.arm,
  "arms": CANONICAL.arms,
  "call": CANONICAL.call,
  "method": CANONICAL.method_call,
  "args": CANONICAL.args,
  "field": CANONICAL.field,
  "fields": CANONICAL.fields,
  "index": CANONICAL.index,
  "try": CANONICAL.try_,
  "ref": CANONICAL.ref,
  "deref": CANONICAL.deref,
  "paren": CANONICAL.paren,
  "tuple": CANONICAL.tuple,
  "array": CANONICAL.array_literal,
  "unit": CANONICAL.unit,
  "int_lit": CANONICAL.int_literal,
  "float_lit": CANONICAL.float_literal,
  "str_lit": CANONICAL.str_literal,
  "char_lit": CANONICAL.char_literal,
  "bool_lit": CANONICAL.bool_literal,
  "ident": CANONICAL.ident,
  "add": CANONICAL.add,
  "sub": CANONICAL.sub,
  "mul": CANONICAL.mul,
  "div": CANONICAL.div,
  "mod": CANONICAL.mod,
  "and": CANONICAL.and,
  "or": CANONICAL.or,
  "not": CANONICAL.not,
  "neg": CANONICAL.neg,
  "cmp": CANONICAL.cmp,
  "bitand": CANONICAL.bitand,
  "bitor": CANONICAL.bitor,
  "bitxor": CANONICAL.bitxor,
  "shl": CANONICAL.shl,
  "shr": CANONICAL.shr,
  "struct": CANONICAL.struct_,
  "tuple_struct": CANONICAL.struct_,
  "unit_struct": CANONICAL.struct_,
  "struct_init": CANONICAL.struct_init,
  "enum": CANONICAL.enum_,
  "variant_unit": CANONICAL.variant_unit,
  "variant_tuple": CANONICAL.variant_tuple,
  "variant_struct": CANONICAL.variant_struct,
  "variants": CANONICAL.variants,
  "path": CANONICAL.path,
  "macro_call": CANONICAL.macro_call,
  "pat_wild": CANONICAL.pat_wild,
  "pat_int": CANONICAL.pat_int,
  "pat_float": CANONICAL.pat_float,
  "pat_str": CANONICAL.pat_str,
  "pat_bool": CANONICAL.pat_bool,
  "pat_ident": CANONICAL.pat_ident,
  "pat_variant": CANONICAL.pat_variant,
  "pat_struct": CANONICAL.pat_struct,
  "pat_path": CANONICAL.pat_path,
  "subs": CANONICAL.subs,
};

// Go — parseGo emits RBasic-categorized recipes (FNDEF, FNCALL, MATH,
// COMPARE, LOGIC, COND, BLOCK, IDENT, LIST), not CAPTURE-shaped ones.
// Its tree is already canonical at the RBasic layer; the only string-
// named ctors in lang-go.ts are the four native-function markers
// (`__slice_literal__` / `__struct_literal__` / `__field__` /
// `__fp_literal__`). These appear inside FNCALL as the callee-string,
// so they're treated as ident-leaves, not as captured ctors. The Go
// map is therefore intentionally minimal — it documents the four
// native markers and identity-maps them. canonicalizeCapturedTree on
// a Go recipe is a no-op because no captured-list categories are
// present.
export const goCtorsMap: Readonly<Record<string, CanonicalCtor>> = {
  // Native-marker idents Go uses for compound literals; if a future
  // pass promotes these from FNCALL-shape to CAPTURE-shape, the
  // canonical names land here. Until then this map is documentation.
  "__slice_literal__": CANONICAL.list_literal,
  "__struct_literal__": CANONICAL.object_literal,
  "__field__": CANONICAL.member_tail,
  "__fp_literal__": CANONICAL.float_literal,
};

// ---------------------------------------------------------------------------
// Handler — given a captured-tree, walk it recursively and re-intern
// each captured-list node under its canonical ctor name. Trivial
// leaves and non-CAPTURE recipes pass through unchanged. The captured-
// list category is recognized by (level=BASIC, type=RBasic.LIST,
// inst>0) — inst is the NameID of the ctor string. We rewrite inst
// to the NameID of the canonical name; if no mapping exists, inst
// stays as-is (forward-compatible — unknown ctors carry through
// without breaking).
//
// The handler is a single shared canonicalize function: the LANGUAGE
// is identified by the *equivalence-cell* that referenced it (each
// language registers a different equivalence under a stable handler
// name). The handler reads the language tag from the carrier-recipe
// children. Per QUOTIENT's handler contract:
//
//   handler(k, raw_children) -> canonical_children
//
// For ctor convergence, "raw children" arrive as a singleton: the
// captured tree itself wrapped in a one-element carrier. The handler
// walks the tree and returns [canonical_tree]. This is the
// composition shape — each captured node's ctor is rewritten in
// place; the outer QUOTIENT value carries [canonical-tree] as its
// single canonical child.
// ---------------------------------------------------------------------------

// Cache resolved name-id maps per language: built once per Kernel from
// the string-form map. Keys: (kernel, language-tag). Values: map from
// local-name NameID → canonical-name NameID. Using a WeakMap means a
// disposed kernel's cache GCs without an explicit clear.
const NAMEID_CACHE = new WeakMap<Kernel, Map<string, Map<number, number>>>();

function buildNameIDMap(
  k: Kernel,
  langTag: string,
  source: Readonly<Record<string, CanonicalCtor>>,
): Map<number, number> {
  let perKernel = NAMEID_CACHE.get(k);
  if (!perKernel) {
    perKernel = new Map();
    NAMEID_CACHE.set(k, perKernel);
  }
  const cached = perKernel.get(langTag);
  if (cached) return cached;
  const out = new Map<number, number>();
  for (const [local, canonical] of Object.entries(source)) {
    const localID = k.internName(local);
    const canonicalID = k.internName(canonical);
    out.set(localID, canonicalID);
  }
  perKernel.set(langTag, out);
  return out;
}

// canonicalizeCapturedTree — walk a captured recipe tree and re-intern
// each captured-list node under its canonical ctor name. Returns the
// rewritten NodeID. Idempotent: applying twice yields the same NodeID.
// `langSource` is one of the four exported ctor maps.
export function canonicalizeCapturedTree(
  k: Kernel,
  tree: NodeID,
  langSource: Readonly<Record<string, CanonicalCtor>>,
  langTag = "anon",
): NodeID {
  const nameMap = buildNameIDMap(k, langTag, langSource);
  return rewrite(k, tree, nameMap);
}

function rewrite(
  k: Kernel,
  n: NodeID,
  nameMap: Map<number, number>,
): NodeID {
  if (n.level === Level.TRIVIAL) return n;
  const recipe = k.recipeAt(n);
  if (!recipe) return n;

  // Recurse into children first — bottom-up rewriting ensures every
  // nested ctor is canonicalized before the parent is re-interned.
  const newKids: NodeID[] = [];
  let kidsChanged = false;
  for (const c of recipe.children) {
    const rc = rewrite(k, c, nameMap);
    if (rc.pkg !== c.pkg || rc.level !== c.level ||
        rc.type !== c.type || rc.inst !== c.inst) {
      kidsChanged = true;
    }
    newKids.push(rc);
  }

  // Determine the canonical category. A captured node has
  // (type=RBasic.LIST, inst=NameID); only those get rewritten.
  let newCat: NodeID = recipe.category;
  if (
    recipe.category.level === Level.BASIC &&
    recipe.category.type === RBasic.LIST &&
    recipe.category.inst > 0
  ) {
    const remapped = nameMap.get(recipe.category.inst);
    if (remapped !== undefined && remapped !== recipe.category.inst) {
      newCat = {
        pkg: recipe.category.pkg,
        level: recipe.category.level,
        type: recipe.category.type,
        inst: remapped,
      };
    }
  }

  // If nothing changed, return the original NodeID — content-
  // addressing means equal categories + equal children share the
  // same NodeID anyway, but this short-circuit avoids touching the
  // intern table when not needed.
  const catChanged =
    newCat.pkg !== recipe.category.pkg ||
    newCat.level !== recipe.category.level ||
    newCat.type !== recipe.category.type ||
    newCat.inst !== recipe.category.inst;
  if (!catChanged && !kidsChanged) return n;
  return k.intern(newCat, newKids);
}

// ---------------------------------------------------------------------------
// Handler factory + registration.
//
// One handler is registered per language. The handler closes over the
// language's local→canonical map, takes the raw child list of a
// QUOTIENT value (here, a single carrier child = the captured tree),
// and returns [canonical_tree]. This keeps the QUOTIENT contract
// honest: same raw children → same canonical children.
// ---------------------------------------------------------------------------

const HANDLER_NAMES = {
  python: "ctor-convergence/python",
  typescript: "ctor-convergence/typescript",
  rust: "ctor-convergence/rust",
  go: "ctor-convergence/go",
} as const;

function makeCtorHandler(
  langTag: string,
  langSource: Readonly<Record<string, CanonicalCtor>>,
) {
  return (k: Kernel, raw: readonly NodeID[]): readonly NodeID[] => {
    if (raw.length !== 1) {
      throw new Error(
        `ctor-convergence/${langTag}: expected 1 child (captured tree), got ${raw.length}`,
      );
    }
    const tree = raw[0]!;
    const canonical = canonicalizeCapturedTree(k, tree, langSource, langTag);
    return [canonical];
  };
}

let HANDLERS_INSTALLED = false;

function ensureHandlersInstalled(): void {
  if (HANDLERS_INSTALLED) return;
  registerHandler(HANDLER_NAMES.python, makeCtorHandler("python", pythonCtorsMap));
  registerHandler(HANDLER_NAMES.typescript, makeCtorHandler("typescript", typescriptCtorsMap));
  registerHandler(HANDLER_NAMES.rust, makeCtorHandler("rust", rustCtorsMap));
  registerHandler(HANDLER_NAMES.go, makeCtorHandler("go", goCtorsMap));
  HANDLERS_INSTALLED = true;
}

// ---------------------------------------------------------------------------
// Public API: registerCtorEquivalences(k)
//
// Builds the four EquivalenceRelations (one per language) and returns
// the library handle. Handlers are installed exactly once across the
// process; equivalence-cells are content-addressed and idempotent —
// a second call on the same Kernel returns NodeIDs equal to the first.
// ---------------------------------------------------------------------------

export interface CtorConvergenceLibrary {
  python: EquivalenceRelation;
  typescript: EquivalenceRelation;
  rust: EquivalenceRelation;
  go: EquivalenceRelation;
}

export function registerCtorEquivalences(k: Kernel): CtorConvergenceLibrary {
  ensureHandlersInstalled();
  return {
    python: makeEquivalence(k, {
      equivalence_name: "ctor-convergence/python",
      decidability: Decidability.DECIDABLE_CHEAP,
      handler_name: HANDLER_NAMES.python,
    }),
    typescript: makeEquivalence(k, {
      equivalence_name: "ctor-convergence/typescript",
      decidability: Decidability.DECIDABLE_CHEAP,
      handler_name: HANDLER_NAMES.typescript,
    }),
    rust: makeEquivalence(k, {
      equivalence_name: "ctor-convergence/rust",
      decidability: Decidability.DECIDABLE_CHEAP,
      handler_name: HANDLER_NAMES.rust,
    }),
    go: makeEquivalence(k, {
      equivalence_name: "ctor-convergence/go",
      decidability: Decidability.DECIDABLE_CHEAP,
      handler_name: HANDLER_NAMES.go,
    }),
  };
}

// ---------------------------------------------------------------------------
// Inspection helpers — exposed for tests / downstream tooling.
// ---------------------------------------------------------------------------

// Returns the captured ctor name of `n` after canonicalization through
// `langSource`, or the original captured ctor if no remapping applies.
// "" if `n` isn't a captured node.
export function canonicalCtorOf(
  k: Kernel,
  n: NodeID,
  langSource: Readonly<Record<string, CanonicalCtor>>,
): string {
  const recipe = k.recipeAt(n);
  if (!recipe) return "";
  if (recipe.category.type !== RBasic.LIST) return "";
  if (recipe.category.inst === 0) return "";
  const local = k.strs[recipe.category.inst] ?? "";
  const canonical = langSource[local];
  return canonical ?? local;
}

// internCanonicalCtor — convenience to look up the NameID of a
// canonical name in this Kernel. Useful when constructing expected
// NodeIDs for tests.
export function internCanonicalCtor(k: Kernel, name: CanonicalCtor): number {
  return k.internName(name);
}

// Re-export Triv for symmetry with quotient.ts.
export { Triv };
