// Parametric format-recipes + strict-typed FNDEF + alias.
//
// Three related surface additions:
//
//   1. Strict-typed FNDEF (inst=2) — every parameter carries a format-recipe
//      reference (i32, f64, FP64-VEC8, ...). The compiler reads these at
//      compile-recipe-time and emits specialized code; the walker ignores
//      the metadata and dispatches by runtime tag like before.
//
//   2. Parametric FNDEF — a type-parameter list `[T: Format, U: Format]`
//      sits beside the value-parameter list. specializeFnDef() substitutes
//      concrete FormatRecipes for the type-parameters and produces a
//      strict-typed FNDEF specialized to that binding.
//
//   3. RBasic.ALIAS (slot 75) — compile-time `name → NodeID` bindings.
//      `alias VECTOR_WIDTH = 8` interns an ALIAS recipe; resolveAlias()
//      looks up the target. Walkers don't see aliases on the hot path.
//
// Layout of the typed FNDEF (inst=2):
//
//   FNDEF inst=2
//     ├─ name-trivial          (Triv.STRING)
//     ├─ params-SEQUENCE       (one name-string-trivial per parameter)
//     ├─ body                  (any recipe)
//     └─ fnmeta-SEQUENCE
//          ├─ tparams-SEQUENCE   (interleaved [name, constraint, name, constraint, ...])
//          ├─ ptypes-SEQUENCE    (one string-trivial-or-null per value parameter)
//          └─ ret-SEQUENCE       (zero or one string-trivial)
//
// Type tokens are strings interned in the kernel's string table. They name
// either a concrete FormatRecipe (i32, f64, ...) or a bound type-parameter
// (T, U, ...). Resolution is lexical — within the FNDEF body, the names in
// tparams shadow same-named outer FormatRecipes.
//
// Why strings, not opaque tokens: the type-parameter binding `T → FP64` is
// a substitution from string-name to a target format identifier (also a
// string in the current vertical slice). When the FormatRecipe layer lands
// in formats.ts, this evolves to NodeID-keyed bindings via aliases —
// `alias i32 = <format-recipe-NodeID>` puts the format in the substrate
// and resolveAlias() picks it up. Until then, strings carry it cleanly.

import {
  Kernel,
  Level,
  RBasic,
  RBlock,
  Triv,
  type NameID,
  type NodeID,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface TypeParam {
  readonly name: string;
  // Constraint name — currently "Format" (the only supported class). When
  // universe polymorphism lands (#22), "Level" joins this enum.
  readonly constraint: string;
}

export interface TypedParam {
  readonly name: string;
  // Type-token name (e.g. "i32", "f64", or a bound type-param like "T").
  // null means untyped (legacy back-compat path).
  readonly type: string | null;
}

export interface FnDefShape {
  readonly name: string;
  readonly typeParams: readonly TypeParam[];
  readonly params: readonly TypedParam[];
  readonly returnType: string | null;
  readonly body: NodeID;
}

// FormatBindings — `{ T: "f64", U: "i32" }` at specialization time.
export type FormatBindings = Readonly<Record<string, string>>;

// ---------------------------------------------------------------------------
// parameterizedFnDef — construct a typed/parametric FNDEF recipe.
// ---------------------------------------------------------------------------

export function parameterizedFnDef(
  k: Kernel,
  name: string,
  typeParams: readonly TypeParam[],
  params: readonly TypedParam[],
  body: NodeID,
  returnType: string | null = null,
): NodeID {
  const nameTrivial = stringTrivial(k, name);
  const paramTrivials: NodeID[] = params.map((p) => stringTrivial(k, p.name));
  const paramsBlock = k.intern(
    blockCat(RBlock.SEQUENCE),
    paramTrivials,
  );

  const anyTypeMeta =
    typeParams.length > 0 ||
    returnType !== null ||
    params.some((p) => p.type !== null);

  if (!anyTypeMeta) {
    // Reuse the back-compat untyped FNDEF (inst=1) for content-addressing
    // parity with the legacy reader.
    return k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 1 },
      [nameTrivial, paramsBlock, body],
    );
  }

  const tparamsChildren: NodeID[] = [];
  for (const tp of typeParams) {
    tparamsChildren.push(k.internString(tp.name));
    tparamsChildren.push(k.internString(tp.constraint));
  }
  const tparamsSeq = k.intern(blockCat(RBlock.SEQUENCE), tparamsChildren);

  const ptypesChildren: NodeID[] = params.map((p) =>
    p.type === null ? k.internTrivialNull() : k.internString(p.type),
  );
  const ptypesSeq = k.intern(blockCat(RBlock.SEQUENCE), ptypesChildren);

  const retSeq = k.intern(
    blockCat(RBlock.SEQUENCE),
    returnType === null ? [] : [k.internString(returnType)],
  );

  const fnmeta = k.intern(blockCat(RBlock.SEQUENCE), [
    tparamsSeq,
    ptypesSeq,
    retSeq,
  ]);

  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 2 },
    [nameTrivial, paramsBlock, body, fnmeta],
  );
}

// ---------------------------------------------------------------------------
// readFnDef — pull the shape back out of a recipe.
// ---------------------------------------------------------------------------

export function readFnDef(k: Kernel, fnDef: NodeID): FnDefShape {
  const cat = k.category(fnDef);
  if (cat.type !== RBasic.FNDEF) {
    throw new Error("readFnDef: not a FNDEF recipe");
  }
  const kids = k.children(fnDef);
  if (kids.length !== 3 && kids.length !== 4) {
    throw new Error("readFnDef: FNDEF must have 3 or 4 children");
  }
  const name = readStringTrivial(k, kids[0]!);
  const paramKids = k.children(kids[1]!);
  const paramNames = paramKids.map((p) => readStringTrivial(k, p));
  const body = kids[2]!;

  if (kids.length === 3) {
    return {
      name,
      typeParams: [],
      params: paramNames.map((n) => ({ name: n, type: null })),
      returnType: null,
      body,
    };
  }

  const fnmetaKids = k.children(kids[3]!);
  if (fnmetaKids.length !== 3) {
    throw new Error("readFnDef: fnmeta must have 3 children");
  }
  const tparamsKids = k.children(fnmetaKids[0]!);
  const ptypesKids = k.children(fnmetaKids[1]!);
  const retKids = k.children(fnmetaKids[2]!);

  if (tparamsKids.length % 2 !== 0) {
    throw new Error("readFnDef: tparams must be even-length (name+constraint pairs)");
  }
  const typeParams: TypeParam[] = [];
  for (let i = 0; i < tparamsKids.length; i += 2) {
    typeParams.push({
      name: readStringTrivial(k, tparamsKids[i]!),
      constraint: readStringTrivial(k, tparamsKids[i + 1]!),
    });
  }

  if (ptypesKids.length !== paramNames.length) {
    throw new Error(
      `readFnDef: ptypes length ${ptypesKids.length} != params length ${paramNames.length}`,
    );
  }
  const params: TypedParam[] = paramNames.map((n, i) => {
    const ptype = ptypesKids[i]!;
    if (ptype.level === Level.TRIVIAL && ptype.type === Triv.NULL) {
      return { name: n, type: null };
    }
    return { name: n, type: readStringTrivial(k, ptype) };
  });

  const returnType =
    retKids.length === 0 ? null : readStringTrivial(k, retKids[0]!);

  return { name, typeParams, params, returnType, body };
}

// ---------------------------------------------------------------------------
// specializeFnDef — substitute concrete formats for type-parameters and
// produce a specialized strict-typed FNDEF.
// ---------------------------------------------------------------------------

export function specializeFnDef(
  k: Kernel,
  fnDef: NodeID,
  bindings: FormatBindings,
): NodeID {
  const shape = readFnDef(k, fnDef);

  // Verify every declared type-parameter has a binding.
  for (const tp of shape.typeParams) {
    if (!(tp.name in bindings)) {
      throw new Error(
        `specializeFnDef: type-parameter ${tp.name} has no binding`,
      );
    }
  }

  // Substitute: each parameter type that matches a type-parameter name
  // becomes the bound format. Already-concrete types stay.
  const specializedParams: TypedParam[] = shape.params.map((p) => {
    if (p.type !== null && p.type in bindings) {
      return { name: p.name, type: bindings[p.type] ?? p.type };
    }
    return p;
  });

  const specializedReturn =
    shape.returnType !== null && shape.returnType in bindings
      ? (bindings[shape.returnType] ?? shape.returnType)
      : shape.returnType;

  // The specialized FNDEF has no remaining type-parameters — all bound.
  return parameterizedFnDef(
    k,
    shape.name,
    [],
    specializedParams,
    shape.body,
    specializedReturn,
  );
}

// ---------------------------------------------------------------------------
// Aliases — compile-time name→NodeID bindings.
// ---------------------------------------------------------------------------

// Per-kernel alias registry. Aliases are interned recipes (RBasic.ALIAS),
// but the lookup index lives outside the substrate so resolveAlias() is
// O(1) without walking. We attach it to the kernel via a WeakMap keyed by
// kernel instance — matches the "per-kernel registry" convention.
const aliasRegistry = new WeakMap<Kernel, Map<NameID, NodeID>>();

function registryFor(k: Kernel): Map<NameID, NodeID> {
  let reg = aliasRegistry.get(k);
  if (reg === undefined) {
    reg = new Map();
    aliasRegistry.set(k, reg);
  }
  return reg;
}

export function makeAlias(
  k: Kernel,
  name: string,
  target: NodeID,
): NodeID {
  const nameID = k.internName(name);
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: nameID,
  };
  const recipe = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.ALIAS, inst: 1 },
    [nameTrivial, target],
  );
  registryFor(k).set(nameID, target);
  return recipe;
}

export function resolveAlias(k: Kernel, name: string): NodeID | undefined {
  const nameID = k.internName(name);
  return registryFor(k).get(nameID);
}

// registerAliasFromRecipe — when the reader parses `(alias name target)`
// the recipe is interned but the registry isn't populated. Call this on
// every ALIAS recipe in a freshly-read source to make resolveAlias() work.
export function registerAliasFromRecipe(k: Kernel, aliasNode: NodeID): void {
  const cat = k.category(aliasNode);
  if (cat.type !== RBasic.ALIAS) {
    throw new Error("registerAliasFromRecipe: not an ALIAS recipe");
  }
  const kids = k.children(aliasNode);
  if (kids.length !== 2) {
    throw new Error("registerAliasFromRecipe: ALIAS must have 2 children");
  }
  const nameNode = kids[0]!;
  if (nameNode.level !== Level.TRIVIAL || nameNode.type !== Triv.STRING) {
    throw new Error("registerAliasFromRecipe: name must be a string trivial");
  }
  registryFor(k).set(nameNode.inst, kids[1]!);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function blockCat(inst: number): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst };
}

function stringTrivial(k: Kernel, s: string): NodeID {
  return {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(s),
  };
}

function readStringTrivial(k: Kernel, n: NodeID): string {
  if (n.level !== Level.TRIVIAL || n.type !== Triv.STRING) {
    throw new Error("readStringTrivial: not a string trivial");
  }
  return k.nameStr(n.inst);
}
