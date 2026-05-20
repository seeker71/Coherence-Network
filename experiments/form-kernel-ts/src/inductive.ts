// inductive.ts — INDUCTIVE recipes and CHOICE totality, as substrate cells.
//
// An inductive type is a substrate recipe whose category is RBasic.INDUCTIVE.
// Its shape — defined here once, read everywhere by content-addressing — is:
//
//   children: [
//     type-name        : Triv.STRING        ; "Nat", "List", ...
//     type-params      : RBasic.LIST        ; parametric types (T, E, ...)
//     ctor0            : RBasic.CONSTRUCTOR ; the type's constructors
//     ctor1            : RBasic.CONSTRUCTOR ;
//     ...
//   ]
//
// A constructor recipe is RBasic.CONSTRUCTOR with children:
//
//   children: [
//     inductive-ref    : NodeID  ; the inductive type this ctor belongs to
//     ctor-name        : Triv.STRING
//     ctor-index       : Triv.INT
//     arg-type0        : NodeID  ; type-recipe (self-ref allowed)
//     arg-type1        : NodeID
//     ...
//   ]
//
// Constructor *application* — value-shape — reuses the same RBasic.CONSTRUCTOR
// recipe shape but with concrete value-recipes in place of arg-types. The
// walker (kernel.ts walkConstructor) builds a Value of kind "ctor" from one.
//
// Because the recipes are content-addressed, two inductives defined with
// identical name + identical params + identical constructor lists are the
// SAME substrate cell. That is what the substrate's promise of structural
// equivalence buys us here.

import {
  Kernel,
  Level,
  RBasic,
  Triv,
  type NodeID,
  type Value,
} from "./kernel.ts";

// InductiveType — the structural description we hand to the kernel.
// Lives at intern time; the recipe in the substrate is the source of truth.
export interface InductiveType {
  readonly type_name: string;
  readonly type_params: NodeID[];
  readonly constructors: ConstructorDef[];
}

export interface ConstructorDef {
  readonly ctor_name: string;
  readonly ctor_index: number;
  readonly arg_types: NodeID[];
}

// catNode — synthesize the category NodeID for an RBasic arm. The level is
// fixed at BASIC and the type is the arm index; instance carries the
// arm-specific subtype (e.g. RBlock.LET, RMath.PLUS). For INDUCTIVE /
// CONSTRUCTOR / CHOICE we use inst=1 to mean "the only shape this arm has."
function catNode(armType: number, inst: number = 1): NodeID {
  return { pkg: 1, level: Level.BASIC, type: armType, inst };
}

// make_inductive — intern an INDUCTIVE recipe. Returns the NodeID of the
// inductive type itself. Constructors are interned as nested CONSTRUCTOR
// recipes whose `inductive-ref` is the placeholder for the parent (it's
// resolved in-place after intern so equivalence still holds).
//
// Two-phase intern: we first build the constructors with a *placeholder*
// inductive ref (the type-name + params hash), then intern the inductive
// recipe with those constructors, then patch references — but because
// the kernel interns by content, a stable encoding requires the inductive
// to refer to its own constructors and the constructors to refer back.
// To break the cycle we use a SELF-REF sentinel: constructor's `inductive-ref`
// child is the inductive's own type-name trivial, and walkConstructor
// resolves it lazily. For the proof-of-shape, we keep it concrete: the
// inductive-ref slot in the *type definition* CONSTRUCTOR recipes is the
// type-name trivial. At constructor *application* time, we plug in the
// real inductive NodeID.
export function make_inductive(
  k: Kernel,
  name: string,
  params: NodeID[],
  ctors: ConstructorDef[],
): NodeID {
  const typeName = k.internString(name);
  const paramsList = k.intern(catNode(RBasic.LIST), params);

  // Constructor *type definitions* — these are part of the inductive's
  // shape, not value-recipes. Their first child is the type-name trivial
  // (self-reference by name, since the inductive's NodeID isn't known yet).
  const ctorDefs: NodeID[] = ctors.map((c) => {
    const nameNode = k.internString(c.ctor_name);
    const indexNode = k.internTrivialInt(c.ctor_index);
    return k.intern(catNode(RBasic.CONSTRUCTOR), [
      typeName,
      nameNode,
      indexNode,
      ...c.arg_types,
    ]);
  });

  return k.intern(catNode(RBasic.INDUCTIVE), [typeName, paramsList, ...ctorDefs]);
}

// make_constructor — apply a constructor to value-recipe arguments,
// producing a value-recipe that walks to a ctor Value. The first child
// is the inductive type's NodeID (so the walker / totality checker
// can find the type without a symbol table).
export function make_constructor(
  k: Kernel,
  inductive: NodeID,
  ctor_name: string,
  args: NodeID[],
): NodeID {
  const ctorIndex = constructorIndex(k, inductive, ctor_name);
  if (ctorIndex < 0) {
    throw new Error(
      `make_constructor: '${ctor_name}' is not a constructor of this inductive`,
    );
  }
  const nameNode = k.internString(ctor_name);
  const indexNode = k.internTrivialInt(ctorIndex);
  return k.intern(catNode(RBasic.CONSTRUCTOR), [
    inductive,
    nameNode,
    indexNode,
    ...args,
  ]);
}

// constructorIndex — look up a constructor's index by name. Returns -1
// if the constructor doesn't exist on this inductive.
export function constructorIndex(
  k: Kernel,
  inductive: NodeID,
  ctor_name: string,
): number {
  const recipe = k.recipeAt(inductive);
  if (recipe === undefined) return -1;
  if (recipe.category.type !== RBasic.INDUCTIVE) return -1;
  for (let i = 2; i < recipe.children.length; i++) {
    const ctorNode = recipe.children[i]!;
    const ctorRecipe = k.recipeAt(ctorNode);
    if (ctorRecipe === undefined) continue;
    const nameNode = ctorRecipe.children[1];
    if (
      nameNode !== undefined &&
      nameNode.level === Level.TRIVIAL &&
      nameNode.type === Triv.STRING &&
      k.nameStr(nameNode.inst) === ctor_name
    ) {
      const idxNode = ctorRecipe.children[2];
      if (
        idxNode !== undefined &&
        idxNode.level === Level.TRIVIAL &&
        idxNode.type === Triv.INT
      ) {
        return idxNode.inst;
      }
    }
  }
  return -1;
}

// constructorNames — every constructor name declared on an inductive,
// in declaration order.
export function constructorNames(k: Kernel, inductive: NodeID): string[] {
  const recipe = k.recipeAt(inductive);
  if (recipe === undefined) return [];
  if (recipe.category.type !== RBasic.INDUCTIVE) return [];
  const out: string[] = [];
  for (let i = 2; i < recipe.children.length; i++) {
    const ctorRecipe = k.recipeAt(recipe.children[i]!);
    if (ctorRecipe === undefined) continue;
    const nameNode = ctorRecipe.children[1];
    if (
      nameNode !== undefined &&
      nameNode.level === Level.TRIVIAL &&
      nameNode.type === Triv.STRING
    ) {
      out.push(k.nameStr(nameNode.inst));
    }
  }
  return out;
}

// is_total — true iff every constructor name declared on `inductive`
// appears in `match_arms`. The CHOICE walker uses this on every match.
export function is_total(
  k: Kernel,
  inductive: NodeID,
  match_arms: readonly string[],
): boolean {
  const all = constructorNames(k, inductive);
  const set = new Set(match_arms);
  return all.every((n) => set.has(n));
}

// match_value — exhaustive runtime pattern match. Returns the result of
// the matched arm. Raises if non-total or if no arm matches.
//
// `arms` is a list of (ctor_name, handler) pairs; the handler is a JS
// function taking the constructor's argument values and returning the
// arm result. This is the imperative entry-point used by tests and by
// kernel-internal helpers; in surface Form, CHOICE recipes carry the
// match arms structurally.
export function match_value<T>(
  k: Kernel,
  value: Value,
  arms: ReadonlyArray<readonly [string, (args: Value[]) => T]>,
): T {
  if (value.kind !== "ctor") {
    throw new Error(`match_value: expected ctor value, got ${value.kind}`);
  }
  const armNames = arms.map(([n]) => n);
  const allCovered = is_total(k, value.inductive, armNames);
  if (!allCovered) {
    const declared = constructorNames(k, value.inductive);
    const missing = declared.filter((n) => !armNames.includes(n));
    throw new Error(
      `match_value: non-total — missing: ${missing.join(", ")}`,
    );
  }
  for (const [name, handler] of arms) {
    if (name === value.ctor_name) return handler(value.args);
  }
  throw new Error(`match_value: no arm matched '${value.ctor_name}'`);
}

// ---------------------------------------------------------------------------
// Built-in inductive types — interned as substrate cells. These exist so
// the rest of the body has a stable Nat / Bool / Option / Result / List
// to reach for; downstream code does not redefine its own.
// ---------------------------------------------------------------------------

export interface BuiltinInductives {
  Nat: NodeID;
  Bool: NodeID;
  Option: NodeID;
  Result: NodeID;
  List: NodeID;
  // Parametric type-variable nodes — referenced from constructors of
  // parametric types. These are SubstrateString trivials carrying the
  // parameter name (T, E). They are not "type values" in any deeper sense;
  // task #22 will give parametric types a richer encoding.
  T: NodeID;
  E: NodeID;
}

export function install_builtin_inductives(k: Kernel): BuiltinInductives {
  // Type parameters as named placeholders. The proof-of-shape uses bare
  // string trivials; richer parametricity lands with task #22.
  const T = k.internString("T");
  const E = k.internString("E");

  // Nat ::= zero | succ Nat
  // Self-reference: the `succ` constructor's arg type is Nat itself,
  // but we don't have Nat's NodeID until after intern. To keep proof-
  // of-shape simple, we use the type-name trivial as the self-ref
  // sentinel; the walker treats it as "the inductive being defined."
  const NatName = k.internString("Nat");
  const Nat = make_inductive(k, "Nat", [], [
    { ctor_name: "zero", ctor_index: 0, arg_types: [] },
    { ctor_name: "succ", ctor_index: 1, arg_types: [NatName] },
  ]);

  // Bool ::= false | true
  const Bool = make_inductive(k, "Bool", [], [
    { ctor_name: "false", ctor_index: 0, arg_types: [] },
    { ctor_name: "true", ctor_index: 1, arg_types: [] },
  ]);

  // Option[T] ::= none | some T
  const Option = make_inductive(k, "Option", [T], [
    { ctor_name: "none", ctor_index: 0, arg_types: [] },
    { ctor_name: "some", ctor_index: 1, arg_types: [T] },
  ]);

  // Result[T, E] ::= ok T | err E
  const Result = make_inductive(k, "Result", [T, E], [
    { ctor_name: "ok", ctor_index: 0, arg_types: [T] },
    { ctor_name: "err", ctor_index: 1, arg_types: [E] },
  ]);

  // List[T] ::= nil | cons T (List T)
  const ListName = k.internString("List");
  const List = make_inductive(k, "List", [T], [
    { ctor_name: "nil", ctor_index: 0, arg_types: [] },
    { ctor_name: "cons", ctor_index: 1, arg_types: [T, ListName] },
  ]);

  return { Nat, Bool, Option, Result, List, T, E };
}

// ---------------------------------------------------------------------------
// Convenience builders — return value-recipe NodeIDs for common shapes.
// Tests and downstream code use these to construct ctor values without
// re-deriving the structure every time.
// ---------------------------------------------------------------------------

export function nat_zero(k: Kernel, inductives: BuiltinInductives): NodeID {
  return make_constructor(k, inductives.Nat, "zero", []);
}

export function nat_succ(
  k: Kernel,
  inductives: BuiltinInductives,
  prev: NodeID,
): NodeID {
  return make_constructor(k, inductives.Nat, "succ", [prev]);
}

export function nat_of(
  k: Kernel,
  inductives: BuiltinInductives,
  n: number,
): NodeID {
  if (n < 0) throw new Error("nat_of: negative");
  let out = nat_zero(k, inductives);
  for (let i = 0; i < n; i++) out = nat_succ(k, inductives, out);
  return out;
}

export function list_nil(k: Kernel, inductives: BuiltinInductives): NodeID {
  return make_constructor(k, inductives.List, "nil", []);
}

export function list_cons(
  k: Kernel,
  inductives: BuiltinInductives,
  head: NodeID,
  tail: NodeID,
): NodeID {
  return make_constructor(k, inductives.List, "cons", [head, tail]);
}

// nat_to_int — walk a Nat value into a JS number. Useful for tests.
export function nat_to_int(v: Value): number {
  let n = 0;
  let cur = v;
  while (cur.kind === "ctor" && cur.ctor_name === "succ") {
    n++;
    cur = cur.args[0]!;
  }
  if (cur.kind !== "ctor" || cur.ctor_name !== "zero") {
    throw new Error("nat_to_int: not a Nat");
  }
  return n;
}

// list_length — count cons cells in a List value.
export function list_length(v: Value): number {
  let n = 0;
  let cur = v;
  while (cur.kind === "ctor" && cur.ctor_name === "cons") {
    n++;
    cur = cur.args[1]!;
  }
  if (cur.kind !== "ctor" || cur.ctor_name !== "nil") {
    throw new Error("list_length: not a List");
  }
  return n;
}
