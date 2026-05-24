// universe.ts — universe polymorphism in FNDEF.
//
// Spec source: task #22 in the higher-math surface arc, building on #8
// (parametric formats). Where #8 adds type-parameters constrained to
// formats (`T: Format`), this layer adds type-parameters constrained to
// the substrate's Level ladder (`L: Level`). A function written once at
// the surface — `defn id[L: Level] (x: Recipe[L]) -> Recipe[L] = x` —
// specializes at compile time into concrete-level FNDEFs without the
// walker needing any new dispatch arms.
//
// Why this matters. The substrate is already level-aware: every NodeID
// carries a level in its 4-tuple, and `intern` propagates the category's
// level to the resulting node. What was missing was a surface for
// authors to write *one* function that is generic over which level its
// recipe arguments inhabit. Without that surface, polymorphic combinators
// (`id`, `compose`, `apply`) had to be re-stated at every level, or
// rely on level-erased duck-typing that lost the structural guarantee.
//
// The implementation is deliberately additive — it composes the existing
// FNDEF, IDENT, and intern machinery; it does not modify the walker.
// Specialization is a pure rewrite from one body NodeID to another, so
// the kernel sees only ordinary FNDEFs after the rewrite. Level-bindings
// land in the body as trivial-int recipes carrying the chosen level
// value, which means downstream code can observe `L` as data when it
// needs to (e.g. dispatching on level inside the body) while still
// benefitting from the structural guarantee at definition time.

import {
  Kernel,
  Level,
  type LevelValue,
  type NameID,
  type NodeID,
  RBasic,
  RBlock,
  Triv,
  nodeKey,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// LevelParam — a type-parameter constrained to Level
// ---------------------------------------------------------------------------

// LevelConstraint — the allowed set of concrete levels this parameter can
// be specialized to. `kind: "any"` means the parameter is unconstrained
// (accepts any LevelValue); `kind: "oneOf"` enumerates the permitted
// concrete levels. Bound checking happens at specialization time.
export type LevelConstraint =
  | { readonly kind: "any" }
  | { readonly kind: "oneOf"; readonly levels: readonly LevelValue[] };

export interface LevelParam {
  // The parameter's name, e.g. "L". Interned in the kernel's string table
  // so the same NameID is used wherever the body references it.
  readonly name: NameID;
  // Constraint on which concrete levels the parameter may bind to.
  readonly constraint: LevelConstraint;
}

// ValueParam — placeholder for #8's parametric-format machinery. A value
// parameter carries a name and (when #8 lands) a Format type-binding;
// today only the name is structurally required. Kept here so the
// signature of `parameterizedByLevel` matches what #8 will extend.
export interface ValueParam {
  readonly name: NameID;
  // Optional level the parameter's recipe is expected to inhabit. When
  // set to a LevelParam name (string), it's interpreted as a reference to
  // one of this function's level-params. When set to a LevelValue, it's
  // a concrete pinned level. When omitted, the value is level-erased.
  readonly levelBinding?: NameID | LevelValue;
}

// ParameterizedFnDef — the surface-level metadata for a universe-
// polymorphic FNDEF. The `fnDef` field is the underlying FNDEF NodeID,
// shaped exactly like a normal three-child FNDEF (name-trivial,
// params-SEQUENCE, body); the polymorphic metadata is carried out-of-band
// in this record. Specialization produces a new ParameterizedFnDef whose
// `levelParams` is shorter (or empty, if all levels are bound) and whose
// `fnDef` body has the level-param IDENTs rewritten to int trivials.
export interface ParameterizedFnDef {
  readonly name: NameID;
  readonly levelParams: readonly LevelParam[];
  readonly valueParams: readonly ValueParam[];
  readonly fnDef: NodeID;
}

// ---------------------------------------------------------------------------
// parameterizedByLevel — author a universe-polymorphic FNDEF
// ---------------------------------------------------------------------------

// Build the FNDEF NodeID for a parameterized function and return the
// ParameterizedFnDef bundle. The level-params do NOT appear in the
// underlying FNDEF's params-SEQUENCE — that block holds only value
// params, matching the walker's expectation. The level-param IDENTs are
// expected to occur naked inside `body` wherever the author references
// the level as data; `specializeByLevel` rewrites them to int trivials.
//
// `name`, `levelParams[*].name`, and `valueParams[*].name` are NameIDs
// (interned strings); callers typically resolve them via
// `kernel.internName("L")`. The function's NodeID is shaped so the
// existing walker can run it as soon as level-params are bound and the
// resulting closure is invoked through ordinary FNCALL.
export function parameterizedByLevel(
  k: Kernel,
  name: NameID,
  levelParams: readonly LevelParam[],
  valueParams: readonly ValueParam[],
  body: NodeID,
): ParameterizedFnDef {
  // Build the params-SEQUENCE child: one name-trivial per value param.
  // The kernel walker reads this exact shape in `walkFnDef`.
  const paramKids: NodeID[] = valueParams.map((vp) => ({
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: vp.name,
  }));
  const paramsSeq = k.intern(
    {
      pkg: 1,
      level: Level.BASIC,
      type: RBasic.BLOCK,
      inst: RBlock.SEQUENCE,
    },
    paramKids,
  );

  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: name,
  };

  const fnDef = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 0 },
    [nameTrivial, paramsSeq, body],
  );

  return {
    name,
    levelParams,
    valueParams,
    fnDef,
  };
}

// ---------------------------------------------------------------------------
// specializeByLevel — substitute concrete levels for level-params
// ---------------------------------------------------------------------------

// LevelBindings — map from level-param NameID to the concrete level
// value selected for it. Every level-param in `fn.levelParams` MUST be
// bound; partial specialization is a future move and would change the
// resulting ParameterizedFnDef's `levelParams` field rather than empty
// it.
export type LevelBindings = ReadonlyMap<NameID, LevelValue>;

// specializeByLevel — produce a fresh ParameterizedFnDef whose level
// parameters are all bound. The new FNDEF has the same value-param
// signature; its body has every IDENT (or bare string-trivial) whose
// NameID matches a bound level-param rewritten to an int-trivial whose
// `inst` is the bound level value. This is a pure rewrite over the
// recipe tree — content-addressed intern dedups any shape that already
// existed, so re-specializing the same function with the same bindings
// returns the same NodeID.
export function specializeByLevel(
  k: Kernel,
  fn: ParameterizedFnDef,
  bindings: LevelBindings,
): ParameterizedFnDef {
  // Enforce arity and constraint compliance.
  if (bindings.size !== fn.levelParams.length) {
    throw new Error(
      `specializeByLevel: arity mismatch (expected ${fn.levelParams.length} level binding(s), got ${bindings.size})`,
    );
  }
  for (const lp of fn.levelParams) {
    const v = bindings.get(lp.name);
    if (v === undefined) {
      throw new Error(
        `specializeByLevel: missing binding for level-param "${k.nameStr(lp.name)}"`,
      );
    }
    if (lp.constraint.kind === "oneOf") {
      if (!lp.constraint.levels.includes(v)) {
        throw new Error(
          `specializeByLevel: level ${v} is not in the constraint for "${k.nameStr(lp.name)}"`,
        );
      }
    }
  }

  // Pull the underlying FNDEF's three children: [name-trivial, params, body].
  const fndef = k.recipeAt(fn.fnDef);
  if (fndef === undefined) {
    throw new Error(`specializeByLevel: fnDef ${nodeKey(fn.fnDef)} not interned`);
  }
  const [nameTrivial, paramsSeq, body] = fndef.children;
  if (
    nameTrivial === undefined ||
    paramsSeq === undefined ||
    body === undefined
  ) {
    throw new Error("specializeByLevel: malformed FNDEF children");
  }

  // Rewrite the body, replacing level-param references with int trivials.
  const memo = new Map<string, NodeID>();
  const rewrittenBody = rewriteLevelRefs(k, body, bindings, memo);

  // Re-intern the FNDEF with the rewritten body. Content-addressing
  // means an identical specialization produces an identical NodeID.
  const newFnDef = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 0 },
    [nameTrivial, paramsSeq, rewrittenBody],
  );

  return {
    name: fn.name,
    levelParams: [], // fully specialized
    valueParams: fn.valueParams,
    fnDef: newFnDef,
  };
}

// rewriteLevelRefs — walk a recipe tree and replace any reference to a
// bound level-param NameID with an int-trivial NodeID whose `inst` is
// the bound level value. Two patterns get rewritten:
//
//   1. A bare string-trivial (level=TRIVIAL, type=STRING) whose `inst`
//      equals a bound level-param NameID. This is how the reader emits
//      identifiers in some shapes.
//   2. An IDENT recipe (BASIC, IDENT) whose single child is a bare
//      string-trivial with a matching NameID. This is the more common
//      shape produced by `readForm`.
//
// All other recipes get rewritten by recursing into their children and
// re-interning if any child changed. Trivials that aren't level-param
// references pass through unchanged.
function rewriteLevelRefs(
  k: Kernel,
  node: NodeID,
  bindings: LevelBindings,
  memo: Map<string, NodeID>,
): NodeID {
  const key = nodeKey(node);
  const cached = memo.get(key);
  if (cached !== undefined) return cached;

  // Pattern 1: bare string-trivial.
  if (node.level === Level.TRIVIAL && node.type === Triv.STRING) {
    const bound = bindings.get(node.inst);
    if (bound !== undefined) {
      const replacement: NodeID = {
        pkg: 1,
        level: Level.TRIVIAL,
        type: Triv.INT,
        inst: (bound | 0) >>> 0,
      };
      memo.set(key, replacement);
      return replacement;
    }
    memo.set(key, node);
    return node;
  }

  // Other trivials pass through.
  if (node.level === Level.TRIVIAL) {
    memo.set(key, node);
    return node;
  }

  const recipe = k.recipeAt(node);
  if (recipe === undefined) {
    memo.set(key, node);
    return node;
  }
  const { category, children } = recipe;

  // Pattern 2: IDENT recipe wrapping a level-param NameID.
  if (category.type === RBasic.IDENT) {
    const inner = children[0];
    if (
      inner !== undefined &&
      inner.level === Level.TRIVIAL &&
      inner.type === Triv.STRING
    ) {
      const bound = bindings.get(inner.inst);
      if (bound !== undefined) {
        const replacement: NodeID = {
          pkg: 1,
          level: Level.TRIVIAL,
          type: Triv.INT,
          inst: (bound | 0) >>> 0,
        };
        memo.set(key, replacement);
        return replacement;
      }
    }
  }

  // Recurse into children, re-interning if anything changed.
  let changed = false;
  const newChildren: NodeID[] = [];
  for (const c of children) {
    const nc = rewriteLevelRefs(k, c, bindings, memo);
    if (
      nc.pkg !== c.pkg ||
      nc.level !== c.level ||
      nc.type !== c.type ||
      nc.inst !== c.inst
    ) {
      changed = true;
    }
    newChildren.push(nc);
  }

  if (!changed) {
    memo.set(key, node);
    return node;
  }

  const reinterned = k.intern(category, newChildren);
  memo.set(key, reinterned);
  return reinterned;
}

// ---------------------------------------------------------------------------
// Sample polymorphic functions — id, compose, apply
// ---------------------------------------------------------------------------

// Helpers to build small recipe shapes. These compose the same primitives
// `readForm` would emit, but spelled out so the samples don't depend on
// the bootstrap reader.
function ident(k: Kernel, nameID: NameID): NodeID {
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: nameID,
  };
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
    [nameTrivial],
  );
}

function fnCall(k: Kernel, callee: NodeID, args: readonly NodeID[]): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [callee, ...args],
  );
}

// makeId — `defn id[L: Level] (x) = x`. The level param L is captured
// but never referenced in the body, so specialization is a no-op on the
// recipe tree (and content-addressed intern returns the same NodeID).
// This is the simplest polymorphic combinator and the canonical
// motivating example.
export function makeId(k: Kernel): ParameterizedFnDef {
  const L = k.internName("L");
  const x = k.internName("x");
  const body = ident(k, x);
  return parameterizedByLevel(
    k,
    k.internName("id"),
    [{ name: L, constraint: { kind: "any" } }],
    [{ name: x, levelBinding: L }],
    body,
  );
}

// makeApply — `defn apply[L: Level] (f, x) = (f x)`. The body is an
// FNCALL of the value parameter `f` on `x`. Like `id`, `L` doesn't
// occur in the body, so specialization is structurally a no-op; the
// metadata still records what level was chosen.
export function makeApply(k: Kernel): ParameterizedFnDef {
  const L = k.internName("L");
  const f = k.internName("f");
  const x = k.internName("x");
  const body = fnCall(k, ident(k, f), [ident(k, x)]);
  return parameterizedByLevel(
    k,
    k.internName("apply"),
    [{ name: L, constraint: { kind: "any" } }],
    [{ name: f, levelBinding: L }, { name: x, levelBinding: L }],
    body,
  );
}

// makeCompose — `defn compose[L: Level] (f, g, x) = (f (g x))`. The
// classic right-to-left composition combinator. Like `id` and `apply`,
// the level param is metadata; the body is structurally invariant
// across all bindings of L. This is the test that universe polymorphism
// composes with itself across multiple value parameters.
export function makeCompose(k: Kernel): ParameterizedFnDef {
  const L = k.internName("L");
  const f = k.internName("f");
  const g = k.internName("g");
  const x = k.internName("x");
  const inner = fnCall(k, ident(k, g), [ident(k, x)]);
  const body = fnCall(k, ident(k, f), [inner]);
  return parameterizedByLevel(
    k,
    k.internName("compose"),
    [{ name: L, constraint: { kind: "any" } }],
    [
      { name: f, levelBinding: L },
      { name: g, levelBinding: L },
      { name: x, levelBinding: L },
    ],
    body,
  );
}
