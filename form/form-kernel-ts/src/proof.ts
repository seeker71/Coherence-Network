// proof.ts — PROOF + INFERENCE arms (propositions-as-types in substrate shape).
//
// Curry-Howard correspondence rendered as content-addressed substrate cells:
//   - Proposition  : any NodeID (a recipe whose identity is its claim).
//   - Proof        : a PROOF-category recipe with children [proposition, construction].
//                    The construction is itself a recipe — either a direct rule
//                    application (INFERENCE-category) or an axiom/assumption.
//   - InferenceRule: a substrate-resident INFERENCE-category recipe carrying
//                    [name, premises, conclusion]. Premises and conclusion are
//                    proposition-recipes that may contain VAR holes (string
//                    trivials with a leading "?") for unification.
//
// Why this shape works:
//   - Content-addressing gives proof-irrelevance for free: two structurally
//     identical proofs of the same proposition share a NodeID.
//   - Propositions ARE types: P being inhabited (provable) means ∃ proof : P.
//   - Inference rules are substrate-resident cells — same intern table, same
//     equivalence machinery. The body knows its own logic.
//
// Additive only — no existing kernel semantics change. The walker does not
// dispatch RBasic.PROOF or RBasic.INFERENCE; they are recipe-shape markers
// consumed by the helpers in this module.

import {
  Kernel,
  Level,
  RBasic,
  Triv,
  nodeKey,
  type NodeID,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Interface shapes — every value here is ultimately a NodeID; the interfaces
// document the role each NodeID plays.
// ---------------------------------------------------------------------------

// A Proposition is a NodeID — any recipe shape whose identity expresses a
// logical claim. The recipe could be: an equality (lc-style INDUCTIVE eq),
// an implication, a conjunction, a universal, a custom predicate, etc.
export interface Proposition {
  readonly node: NodeID;
}

// A Proof is a PROOF-category recipe with children [proposition, construction].
// `node` is the interned PROOF cell; `proposition` and `construction` are
// child NodeIDs surfaced for ergonomic access.
export interface Proof {
  readonly node: NodeID;
  readonly proposition: NodeID;
  readonly construction: NodeID;
}

// An InferenceRule is an INFERENCE-category recipe with children
// [name, premises-list, conclusion]. Premises is a LIST recipe of
// proposition-schemas; conclusion is a proposition-schema. Schemas may
// contain VAR holes — string trivials whose value begins with "?" — that
// unify against concrete propositions during `apply`.
export interface InferenceRule {
  readonly node: NodeID;
  readonly name: string;
  readonly premises: readonly NodeID[];
  readonly conclusion: NodeID;
}

// ---------------------------------------------------------------------------
// Category cells — interned once, shared across all constructors.
// ---------------------------------------------------------------------------

// PROOF category cell — shape marker for proof recipes. Stored as a TRIVIAL
// NodeID with type=PROOF; serves as the `category` argument to intern() for
// proof cells, so they all share recipeKey prefix `C|1.2.73.0`.
function proofCategory(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.PROOF, inst: 0 };
}

function inferenceCategory(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.INFERENCE, inst: 0 };
}

// ---------------------------------------------------------------------------
// Constructors
// ---------------------------------------------------------------------------

// Intern a PROOF-category recipe with [proposition, construction] children.
// Same shape → same NodeID (proof-irrelevance).
export function makeProof(
  k: Kernel,
  proposition: NodeID,
  construction: NodeID,
): Proof {
  const node = k.intern(proofCategory(), [proposition, construction]);
  return { node, proposition, construction };
}

// Intern an INFERENCE-category recipe:
//   children = [name-trivial, premises-LIST, conclusion]
// `name` is interned as a string trivial; premises are wrapped in an
// RBasic.LIST recipe so the rule itself is fully substrate-resident.
export function makeInferenceRule(
  k: Kernel,
  name: string,
  premises: readonly NodeID[],
  conclusion: NodeID,
): InferenceRule {
  const nameNode = k.internString(name);
  const listCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.LIST,
    inst: 0,
  };
  const premisesList = k.intern(listCat, premises);
  const node = k.intern(inferenceCategory(), [
    nameNode,
    premisesList,
    conclusion,
  ]);
  return { node, name, premises, conclusion };
}

// ---------------------------------------------------------------------------
// Proposition schemas + holes
//
// A "hole" is a string trivial whose name begins with "?". During unification
// holes bind to concrete sub-recipes. Unification is structural, like
// first-order pattern matching — no higher-order goals.
// ---------------------------------------------------------------------------

// Make a VAR hole — a string trivial whose name starts with "?". The leading
// "?" is the only convention this module uses to recognize a hole; nothing
// else in the kernel cares.
export function hole(k: Kernel, name: string): NodeID {
  const tag = name.startsWith("?") ? name : `?${name}`;
  return k.internString(tag);
}

function isHole(k: Kernel, n: NodeID): boolean {
  if (n.level !== Level.TRIVIAL || n.type !== Triv.STRING) return false;
  const s = k.strs[n.inst];
  return typeof s === "string" && s.startsWith("?");
}

// Unification — match `schema` against `target`. Holes in schema bind to
// sub-NodeIDs of target. Returns a binding map keyed by hole NodeID
// (canonical nodeKey), or null on failure. Holes that re-appear must bind
// consistently.
function unify(
  k: Kernel,
  schema: NodeID,
  target: NodeID,
  bindings: Map<string, NodeID>,
): boolean {
  if (isHole(k, schema)) {
    const key = nodeKey(schema);
    const prior = bindings.get(key);
    if (prior !== undefined) {
      // Must equal — structural identity via nodeKey is canonical.
      return nodeKey(prior) === nodeKey(target);
    }
    bindings.set(key, target);
    return true;
  }
  // Trivial — must be identical.
  if (schema.level === Level.TRIVIAL || target.level === Level.TRIVIAL) {
    return nodeKey(schema) === nodeKey(target);
  }
  // Composite — categories must match, children must unify pointwise.
  const sCat = k.category(schema);
  const tCat = k.category(target);
  if (nodeKey(sCat) !== nodeKey(tCat)) return false;
  const sKids = k.children(schema);
  const tKids = k.children(target);
  if (sKids.length !== tKids.length) return false;
  for (let i = 0; i < sKids.length; i++) {
    if (!unify(k, sKids[i]!, tKids[i]!, bindings)) return false;
  }
  return true;
}

// Substitute — walk `schema` replacing every hole that appears in `bindings`
// with its bound NodeID. Re-interns each composite so the result is a fresh
// substrate cell.
function substitute(
  k: Kernel,
  schema: NodeID,
  bindings: Map<string, NodeID>,
): NodeID {
  if (isHole(k, schema)) {
    const bound = bindings.get(nodeKey(schema));
    return bound ?? schema;
  }
  if (schema.level === Level.TRIVIAL) return schema;
  const cat = k.category(schema);
  const kids = k.children(schema).map((c) => substitute(k, c, bindings));
  return k.intern(cat, kids);
}

// ---------------------------------------------------------------------------
// Built-in inference rules — propositional + (simple) first-order
//
// These are substrate-resident cells; making them more than once returns the
// same NodeID via content-addressing. `builtinRules(k)` interns them all.
//
// Schema conventions:
//   ?P, ?Q, ?R, ?A, ?x  — VAR holes for propositions / terms
//
// We use simple recipe shapes for the logical connectives, all interned
// against a Logic category cell with op-instance distinguishing each:
//   LOGIC.AND(P, Q), LOGIC.OR(P, Q), LOGIC.NOT(P), and
//   IMPL(P, Q) / FORALL(x, P) / EXISTS(x, P)
// Implication and quantifiers are encoded as FNCALL of a named connective
// trivial, so they round-trip through the existing intern table without
// burning new kernel slots.
// ---------------------------------------------------------------------------

function logicCat(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: 0 };
}

function andProp(k: Kernel, p: NodeID, q: NodeID): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: 1 }, // AND
    [p, q],
  );
}

function orProp(k: Kernel, p: NodeID, q: NodeID): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: 2 }, // OR
    [p, q],
  );
}

function notProp(k: Kernel, p: NodeID): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.LOGIC, inst: 3 }, // NOT
    [p],
  );
}

// Implication is its own connective — we use FNCALL with the head trivial
// "==>" so it shows up cleanly in form-language renderings and round-trips
// through the existing walker shape.
function impliesProp(k: Kernel, p: NodeID, q: NodeID): NodeID {
  const head = k.internString("==>");
  const cat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.FNCALL,
    inst: 0,
  };
  return k.intern(cat, [head, p, q]);
}

function forallProp(k: Kernel, varName: NodeID, body: NodeID): NodeID {
  const head = k.internString("forall");
  const cat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.FNCALL,
    inst: 0,
  };
  return k.intern(cat, [head, varName, body]);
}

function existsProp(k: Kernel, varName: NodeID, body: NodeID): NodeID {
  const head = k.internString("exists");
  const cat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.FNCALL,
    inst: 0,
  };
  return k.intern(cat, [head, varName, body]);
}

// Falsum — distinguished proposition representing ⊥ (used by notElim).
function falsumProp(k: Kernel): NodeID {
  return k.internString("⊥");
}

export interface BuiltinRules {
  modusPonens: InferenceRule;
  andIntro: InferenceRule;
  andElim1: InferenceRule;
  andElim2: InferenceRule;
  orIntro1: InferenceRule;
  orIntro2: InferenceRule;
  impliesIntro: InferenceRule;
  impliesElim: InferenceRule;
  notIntro: InferenceRule;
  notElim: InferenceRule;
  forallIntro: InferenceRule;
  forallElim: InferenceRule;
  existsIntro: InferenceRule;
  existsElim: InferenceRule;
}

// Intern the standard rule set. Called once per Kernel; safe to call again —
// content-addressing returns the same NodeIDs.
export function builtinRules(k: Kernel): BuiltinRules {
  const P = hole(k, "P");
  const Q = hole(k, "Q");
  const x = hole(k, "x");

  const PimpliesQ = impliesProp(k, P, Q);
  const PandQ = andProp(k, P, Q);
  const PorQ = orProp(k, P, Q);
  const notP = notProp(k, P);
  const forallxP = forallProp(k, x, P);
  const existsxP = existsProp(k, x, P);

  return {
    // P → Q, P ⊢ Q
    modusPonens: makeInferenceRule(k, "modus-ponens", [PimpliesQ, P], Q),
    // P, Q ⊢ P ∧ Q
    andIntro: makeInferenceRule(k, "and-intro", [P, Q], PandQ),
    // P ∧ Q ⊢ P
    andElim1: makeInferenceRule(k, "and-elim-1", [PandQ], P),
    // P ∧ Q ⊢ Q
    andElim2: makeInferenceRule(k, "and-elim-2", [PandQ], Q),
    // P ⊢ P ∨ Q
    orIntro1: makeInferenceRule(k, "or-intro-1", [P], PorQ),
    // Q ⊢ P ∨ Q
    orIntro2: makeInferenceRule(k, "or-intro-2", [Q], PorQ),
    // P ⊢ Q   gives   P → Q   (discharging the assumption — encoded as
    // a rule with single premise; full natural-deduction assumption tracking
    // is deferred to mathlib bootstrap #24)
    impliesIntro: makeInferenceRule(k, "implies-intro", [Q], PimpliesQ),
    // alias of modus ponens, surfaced for natural-deduction parity
    impliesElim: makeInferenceRule(k, "implies-elim", [PimpliesQ, P], Q),
    // P ⊢ ⊥   gives   ¬P  (again, assumption-discharge deferred)
    notIntro: makeInferenceRule(k, "not-intro", [falsumProp(k)], notP),
    // ¬P, P ⊢ ⊥
    notElim: makeInferenceRule(k, "not-elim", [notP, P], falsumProp(k)),
    // P[x] ⊢ ∀x. P
    forallIntro: makeInferenceRule(k, "forall-intro", [P], forallxP),
    // ∀x. P ⊢ P[x]
    forallElim: makeInferenceRule(k, "forall-elim", [forallxP], P),
    // P[x] ⊢ ∃x. P
    existsIntro: makeInferenceRule(k, "exists-intro", [P], existsxP),
    // ∃x. P, P ⊢ Q   gives  Q   (witness extraction; assumption-discharge
    // deferred to #24)
    existsElim: makeInferenceRule(k, "exists-elim", [existsxP, P], Q),
  };
}

// Constructors exported for caller-driven proposition building. These are
// the shapes the bundled inference rules unify against.
export const Prop = {
  and: andProp,
  or: orProp,
  not: notProp,
  implies: impliesProp,
  forall: forallProp,
  exists: existsProp,
  falsum: falsumProp,
} as const;

// ---------------------------------------------------------------------------
// apply — run a rule against a list of premise proofs.
//
// Semantics:
//   1. Each premise-proof's proposition is unified against the corresponding
//      premise schema, accumulating a single binding environment.
//   2. If all unifications succeed, the rule's conclusion is substituted
//      with the accumulated bindings to yield the concluded proposition.
//   3. A construction recipe is built from this rule application — an
//      INFERENCE-category recipe carrying [rule, ...premise-proofs] — and
//      makeProof wraps that with the concluded proposition.
//
// Returns null if arity mismatches or unification fails. Never throws on
// shape mismatch — the failure is part of the algebra.
// ---------------------------------------------------------------------------

export function apply(
  k: Kernel,
  rule: InferenceRule,
  premiseProofs: readonly Proof[],
): Proof | null {
  if (premiseProofs.length !== rule.premises.length) return null;
  const bindings = new Map<string, NodeID>();
  for (let i = 0; i < rule.premises.length; i++) {
    const schema = rule.premises[i]!;
    const propProvided = premiseProofs[i]!.proposition;
    if (!unify(k, schema, propProvided, bindings)) return null;
  }
  const conclusion = substitute(k, rule.conclusion, bindings);
  // Build construction = INFERENCE-shaped application cell.
  // children = [rule-NodeID, premise-proof-NodeIDs...]
  const construction = k.intern(inferenceCategory(), [
    rule.node,
    ...premiseProofs.map((p) => p.node),
  ]);
  return makeProof(k, conclusion, construction);
}

// ---------------------------------------------------------------------------
// axiom — wrap a proposition as a self-evident proof. The construction is
// the special string trivial "axiom" so axiom-cells are distinguishable from
// inference applications.
//
// Useful for assumptions, induction base cases sourced from #21's INDUCTIVE
// constructors, and externally-provided premises.
// ---------------------------------------------------------------------------

export function axiom(k: Kernel, proposition: NodeID): Proof {
  const construction = k.internString("axiom");
  return makeProof(k, proposition, construction);
}

// ---------------------------------------------------------------------------
// proofOf — return the proposition a proof establishes.
// ---------------------------------------------------------------------------

export function proofOf(_k: Kernel, proof: Proof): NodeID {
  return proof.proposition;
}

// ---------------------------------------------------------------------------
// valid — check the proof's construction is well-formed.
//
// Recursively descends:
//   - Axiom proofs are trivially valid (their proposition is the claim).
//   - Inference-application proofs must:
//       (a) reference an actual INFERENCE-category rule,
//       (b) have sub-proofs whose propositions unify with rule premises,
//       (c) yield a conclusion equal (by NodeID) to the proof's proposition.
//   - Anything else (orphan PROOF cells with unrecognized construction) is
//     invalid.
// ---------------------------------------------------------------------------

export function valid(k: Kernel, proof: Proof): boolean {
  return validateNode(k, proof.node);
}

function validateNode(k: Kernel, proofNode: NodeID): boolean {
  const recipe = k.recipeAt(proofNode);
  if (!recipe) return false;
  if (recipe.category.type !== RBasic.PROOF) return false;
  if (recipe.children.length !== 2) return false;
  const proposition = recipe.children[0]!;
  const construction = recipe.children[1]!;

  // Axiom: construction is the string trivial "axiom".
  if (
    construction.level === Level.TRIVIAL &&
    construction.type === Triv.STRING
  ) {
    const s = k.strs[construction.inst];
    return s === "axiom" || (typeof s === "string" && s.startsWith("axiom:"));
  }

  // Inference application: construction is an INFERENCE-category cell with
  // [rule, ...premise-proofs].
  const cRecipe = k.recipeAt(construction);
  if (!cRecipe) return false;
  if (cRecipe.category.type !== RBasic.INFERENCE) return false;
  if (cRecipe.children.length < 1) return false;

  const ruleNode = cRecipe.children[0]!;
  const ruleRecipe = k.recipeAt(ruleNode);
  if (!ruleRecipe) return false;
  if (ruleRecipe.category.type !== RBasic.INFERENCE) return false;
  if (ruleRecipe.children.length !== 3) return false;

  const premiseList = ruleRecipe.children[1]!;
  const ruleConclusion = ruleRecipe.children[2]!;
  const premiseSchemas = k.children(premiseList);

  const subProofs = cRecipe.children.slice(1);
  if (subProofs.length !== premiseSchemas.length) return false;

  // Recursively validate each sub-proof, and unify its proposition against
  // the corresponding schema.
  const bindings = new Map<string, NodeID>();
  for (let i = 0; i < subProofs.length; i++) {
    const sub = subProofs[i]!;
    if (!validateNode(k, sub)) return false;
    const subRecipe = k.recipeAt(sub);
    if (!subRecipe) return false;
    const subProp = subRecipe.children[0]!;
    if (!unify(k, premiseSchemas[i]!, subProp, bindings)) return false;
  }
  const derived = substitute(k, ruleConclusion, bindings);
  return nodeKey(derived) === nodeKey(proposition);
}
