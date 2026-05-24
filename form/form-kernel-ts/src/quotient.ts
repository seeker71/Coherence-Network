// quotient.ts — QUOTIENT RBasic arm: canonicalization under equivalence.
//
// A recipe whose category is RBasic.QUOTIENT has the shape:
//
//   QUOTIENT[carrier-recipe, equivalence-recipe]
//
// Where `equivalence-recipe` is itself a substrate cell describing the
// equivalence relation. When a *value* of the quotient type is interned
// (via `intern_quotient_value`), the equivalence-recipe's canonicalize
// step runs first; the canonical form is what hits the intern table.
// Two values equivalent under the relation therefore receive the SAME
// NodeID — content-addressing IS the quotient.
//
// This generalizes the canonicalization the format library already
// performs (NaN → quiet, ±0 → +0). The shape: equivalence-recipes are
// SUBSTRATE CELLS, not hardcoded kernel logic. Adding a new equivalence
// is a substrate write — the kernel reads the cell and dispatches the
// canonicalize_fn. The body grows; the kernel stays small.
//
// See docs/coherence-substrate/higher-math-surface.md for the full
// design (and PROOF / INDUCTIVE / symmetry-aware canonicalization that
// build on top of QUOTIENT).
//
// Decidability + cost policy:
//   - is_decidable=true + cheap_algorithm=true  → EAGER canonicalize at intern
//   - is_decidable=true + cheap_algorithm=false → LAZY canonicalize on equality query
//   - is_decidable=false                        → LAZY + requires explicit proof
//                                                  recipe to merge NodeIDs
// Honest default: EAGER unless the equivalence declares heavy.

import {
  Kernel,
  Level,
  RBasic,
  Triv,
  nodeKey,
  type NodeID,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Decidability + canonicalization-strategy metadata
// ---------------------------------------------------------------------------

export const Decidability = {
  /** Effective algorithm, cheap to run — canonicalize eagerly. */
  DECIDABLE_CHEAP: 1,
  /** Effective algorithm, expensive (e.g. Knuth-Bendix) — canonicalize lazily. */
  DECIDABLE_HEAVY: 2,
  /** No effective algorithm (e.g. function-equality, group iso in general). */
  UNDECIDABLE: 3,
} as const;

export type DecidabilityCode =
  (typeof Decidability)[keyof typeof Decidability];

export const CanonStrategy = {
  EAGER: 1,
  LAZY: 2,
} as const;

export type CanonStrategyCode =
  (typeof CanonStrategy)[keyof typeof CanonStrategy];

// Per-equivalence canonicalization. Operates on a value's children
// (the raw representative) and returns the canonical-children-tuple.
// Returning the same tuple-shape for any two equivalent inputs is the
// canonicalize_fn's job; the kernel handles the content-addressing.
export type CanonicalizeFn = (
  k: Kernel,
  rawChildren: readonly NodeID[],
) => readonly NodeID[];

// EquivalenceRelation — the substrate-resident relation descriptor.
// In a Form program this is itself a recipe whose category is a known
// equivalence-relation type (handler_name resolves to a registered fn).
// For the TS proof-of-shape we hold the JS side here as a thin wrapper;
// the substrate-cell projection (a recipe carrying name + decidability
// + handler_name as children) is interned in parallel for cross-kernel
// agreement.
export interface EquivalenceRelation {
  /** Human-readable identifier ("integer-from-nat-pair"). */
  readonly equivalence_name: string;
  /** Decidability + algorithm-cost classification. */
  readonly decidability: DecidabilityCode;
  /** Computed strategy honoring decidability + honest-defaults policy. */
  readonly strategy: CanonStrategyCode;
  /** Cheap-flag is informational; strategy already folded it in. */
  readonly is_decidable: boolean;
  /** Handler name — string-handle into the kernel's registered table. */
  readonly handler_name: string;
  /** Canonicalize function — resolved from the handler at registration. */
  readonly canonicalize_fn: CanonicalizeFn;
  /** Substrate cell projection — NodeID of the equivalence-recipe. */
  readonly nodeID: NodeID;
}

// ---------------------------------------------------------------------------
// Handler registry — name → CanonicalizeFn.
//
// In the cross-kernel design the handler-name is itself a substrate
// string trivial; resolution is "look up the registered fn by name".
// Form programs construct equivalence-recipes purely as substrate writes;
// the kernel side of the registry binds the name to a runtime fn. New
// equivalences arrive in two halves: a substrate write (the recipe) and
// a handler registration (the runtime). For purely-Form equivalences
// (canonicalize_fn expressed AS a Form recipe), the handler is a single
// "walk-this-recipe" stub — but that path is follow-up work.
// ---------------------------------------------------------------------------

const HANDLERS = new Map<string, CanonicalizeFn>();

export function registerHandler(name: string, fn: CanonicalizeFn): void {
  HANDLERS.set(name, fn);
}

export function getHandler(name: string): CanonicalizeFn | undefined {
  return HANDLERS.get(name);
}

// ---------------------------------------------------------------------------
// Computing strategy from decidability + the honest-defaults policy.
// ---------------------------------------------------------------------------

function strategyFor(d: DecidabilityCode): CanonStrategyCode {
  // Honest defaults: eager unless the equivalence declares heavy.
  // Undecidable equivalences are necessarily lazy (no eager option).
  if (d === Decidability.DECIDABLE_CHEAP) return CanonStrategy.EAGER;
  return CanonStrategy.LAZY;
}

// ---------------------------------------------------------------------------
// Substrate-cell projection: the equivalence-recipe.
//
// Stored shape (children, all substrate-resident):
//   [ name-trivial, decidability-int, strategy-int, handler-name-trivial ]
//
// The category instance is the decidability code so the NodeID inst
// already encodes the major axis without a child lookup. Two recipes
// with identical children intern to the SAME NodeID — equivalences are
// content-addressed like everything else.
// ---------------------------------------------------------------------------

const EQUIV_CATEGORY_PKG = 1;
const EQUIV_CATEGORY_LEVEL = Level.BASIC;
// Reuse a high-slot RBasic-ish type for the equivalence-recipe itself;
// the QUOTIENT-arm consumes these as substrate-resident metadata.
// Aligned with kernel.ts QUOTIENT slot but the equivalence-recipe is a
// SIBLING category, not the QUOTIENT recipe itself.
const EQUIV_CATEGORY_TYPE = RBasic.QUOTIENT + 1; // 71

function makeEquivalenceCell(
  k: Kernel,
  equivalence_name: string,
  decidability: DecidabilityCode,
  strategy: CanonStrategyCode,
  handler_name: string,
): NodeID {
  return k.intern(
    {
      pkg: EQUIV_CATEGORY_PKG,
      level: EQUIV_CATEGORY_LEVEL,
      type: EQUIV_CATEGORY_TYPE,
      inst: decidability,
    },
    [
      k.internString(equivalence_name),
      k.internTrivialInt(decidability),
      k.internTrivialInt(strategy),
      k.internString(handler_name),
    ],
  );
}

// Register a new equivalence relation. The handler must already be
// registered under `handler_name` (registerHandler). Returns the
// EquivalenceRelation handle (carrying the substrate cell NodeID).
export function makeEquivalence(
  k: Kernel,
  spec: {
    equivalence_name: string;
    decidability: DecidabilityCode;
    handler_name: string;
  },
): EquivalenceRelation {
  const handler = HANDLERS.get(spec.handler_name);
  if (handler === undefined) {
    throw new Error(
      `quotient: handler '${spec.handler_name}' is not registered`,
    );
  }
  const strategy = strategyFor(spec.decidability);
  const nodeID = makeEquivalenceCell(
    k,
    spec.equivalence_name,
    spec.decidability,
    strategy,
    spec.handler_name,
  );
  return {
    equivalence_name: spec.equivalence_name,
    decidability: spec.decidability,
    strategy,
    is_decidable: spec.decidability !== Decidability.UNDECIDABLE,
    handler_name: spec.handler_name,
    canonicalize_fn: handler,
    nodeID,
  };
}

// ---------------------------------------------------------------------------
// QUOTIENT recipe construction.
//
//   make_quotient_recipe(k, carrier_nid, equiv_nid) — intern a
//   QUOTIENT[carrier, equivalence] recipe. The carrier is the underlying
//   recipe whose values get quotiented; the equivalence-recipe carries
//   canonicalization rules. Same (carrier, equivalence) pair always
//   interns to the same NodeID (content-addressing).
// ---------------------------------------------------------------------------

export function make_quotient_recipe(
  k: Kernel,
  carrier_nid: NodeID,
  equiv_nid: NodeID,
): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.QUOTIENT, inst: 1 },
    [carrier_nid, equiv_nid],
  );
}

// Inspect a QUOTIENT recipe: extract (carrier, equivalence).
export function quotient_parts(
  k: Kernel,
  quotient_nid: NodeID,
): { carrier: NodeID; equivalence: NodeID } {
  if (
    quotient_nid.level !== Level.BASIC ||
    quotient_nid.type !== RBasic.QUOTIENT
  ) {
    throw new Error(
      `quotient_parts: ${nodeKey(quotient_nid)} is not a QUOTIENT recipe`,
    );
  }
  const kids = k.children(quotient_nid);
  if (kids.length !== 2) {
    throw new Error(
      `quotient_parts: malformed QUOTIENT recipe (children=${kids.length})`,
    );
  }
  return { carrier: kids[0]!, equivalence: kids[1]! };
}

// Resolve the EquivalenceRelation handle from a substrate-cell NodeID.
// The equivalence-cell's children carry [name, decidability, strategy,
// handler-name]; we decode and look up the registered handler.
export function resolve_equivalence(
  k: Kernel,
  equiv_nid: NodeID,
): EquivalenceRelation {
  const kids = k.children(equiv_nid);
  if (kids.length !== 4) {
    throw new Error(
      `resolve_equivalence: malformed equivalence cell (children=${kids.length})`,
    );
  }
  const name = k.trivialValue(kids[0]!);
  const dec = k.trivialValue(kids[1]!);
  const strat = k.trivialValue(kids[2]!);
  const hname = k.trivialValue(kids[3]!);
  if (
    name.kind !== "str" ||
    dec.kind !== "int" ||
    strat.kind !== "int" ||
    hname.kind !== "str"
  ) {
    throw new Error("resolve_equivalence: bad cell children types");
  }
  const handler = HANDLERS.get(hname.str);
  if (handler === undefined) {
    throw new Error(
      `resolve_equivalence: handler '${hname.str}' not registered in this kernel`,
    );
  }
  return {
    equivalence_name: name.str,
    decidability: dec.int as DecidabilityCode,
    strategy: strat.int as CanonStrategyCode,
    is_decidable: (dec.int as DecidabilityCode) !== Decidability.UNDECIDABLE,
    handler_name: hname.str,
    canonicalize_fn: handler,
    nodeID: equiv_nid,
  };
}

// ---------------------------------------------------------------------------
// Interning a value through a quotient.
//
//   intern_quotient_value(k, quotient_recipe, raw_children)
//
// `raw_children` are the carrier-shape children of the raw value (e.g.
// [int(3), int(1)] for an integer-from-nat-pair representative). The
// equivalence's canonicalize_fn reduces them to canonical-children; the
// kernel then interns a recipe whose category is the QUOTIENT cell and
// whose children are the canonical-children. Two equivalent raw values
// therefore produce the SAME NodeID — that's the quotient.
//
// Strategy = EAGER: canonicalize NOW, then intern canonical form.
// Strategy = LAZY:  intern raw form (as a different recipe shape that
//                   carries `lazy` marker); equality_query canonicalizes
//                   on demand. The shapes differ structurally so the raw
//                   form has its own NodeID; equality queries route
//                   through canonicalize_then_compare.
// ---------------------------------------------------------------------------

export function intern_quotient_value(
  k: Kernel,
  quotient_recipe: NodeID,
  raw_children: readonly NodeID[],
): NodeID {
  const { equivalence } = quotient_parts(k, quotient_recipe);
  const eq = resolve_equivalence(k, equivalence);

  if (eq.strategy === CanonStrategy.EAGER) {
    const canonical = eq.canonicalize_fn(k, raw_children);
    // The value-recipe's category is the QUOTIENT recipe itself; same
    // (quotient, canonical-children) pair always interns to same NodeID.
    return k.intern(
      {
        pkg: 1,
        level: Level.BASIC,
        type: RBasic.QUOTIENT,
        // Distinguish a quotient *value* from the quotient recipe by
        // using inst=2 (values) vs inst=1 (recipes).
        inst: 2,
      },
      [quotient_recipe, ...canonical],
    );
  }

  // LAZY: intern the raw form with a distinct inst marker so eager- and
  // lazy-shapes don't collide. The canonical form computed on-equality
  // shares an inst=2 slot with the eager path so cross-strategy hits
  // still land at the same canonical NodeID once forced.
  return k.intern(
    {
      pkg: 1,
      level: Level.BASIC,
      type: RBasic.QUOTIENT,
      inst: 3, // lazy raw form
    },
    [quotient_recipe, ...raw_children],
  );
}

// Force-canonicalize a value (eager or lazy) and return its canonical
// NodeID. Used by equality queries and by callers that want to merge
// equivalent representatives explicitly.
export function canonical_form(
  k: Kernel,
  quotient_value: NodeID,
): NodeID {
  if (
    quotient_value.level !== Level.BASIC ||
    quotient_value.type !== RBasic.QUOTIENT
  ) {
    throw new Error(
      `canonical_form: ${nodeKey(quotient_value)} is not a QUOTIENT value`,
    );
  }
  const kids = k.children(quotient_value);
  if (kids.length < 1) {
    throw new Error("canonical_form: malformed quotient value");
  }
  const quotient_recipe = kids[0]!;
  const rest = kids.slice(1);
  if (quotient_value.inst === 2) {
    // Already canonical.
    return quotient_value;
  }
  // Lazy (inst=3) — canonicalize and re-intern as inst=2 form.
  const { equivalence } = quotient_parts(k, quotient_recipe);
  const eq = resolve_equivalence(k, equivalence);
  const canonical = eq.canonicalize_fn(k, rest);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.QUOTIENT, inst: 2 },
    [quotient_recipe, ...canonical],
  );
}

// quotient_equal — equality under the quotient. Two values are equal
// iff their canonical forms share a NodeID.
export function quotient_equal(
  k: Kernel,
  a: NodeID,
  b: NodeID,
): boolean {
  const ca = canonical_form(k, a);
  const cb = canonical_form(k, b);
  return (
    ca.pkg === cb.pkg &&
    ca.level === cb.level &&
    ca.type === cb.type &&
    ca.inst === cb.inst
  );
}

// ---------------------------------------------------------------------------
// Built-in equivalence relations.
//
// Each registers a handler under a stable name and constructs the
// substrate-resident equivalence-recipe. The names are part of the
// cross-kernel contract — Python / Go / Rust register the same handler
// names so a Form program ingested into any kernel canonicalizes
// identically.
// ---------------------------------------------------------------------------

// ── EQUIV_INTEGER_FROM_NAT_PAIR ───────────────────────────────────────
// Integers as Z := (N × N) / ~ where (a,b) ~ (c,d) iff a+d = b+c.
// The canonical representative is (a-b, 0) — sign carried by the
// difference. We use int32 children for the natural-number pairs in
// this proof-of-shape; cross-kernel ports likely use bigints.
function handler_integer_from_nat_pair(
  k: Kernel,
  raw: readonly NodeID[],
): readonly NodeID[] {
  if (raw.length !== 2) {
    throw new Error(
      `integer-from-nat-pair: expected 2 children, got ${raw.length}`,
    );
  }
  const av = k.trivialValue(raw[0]!);
  const bv = k.trivialValue(raw[1]!);
  if (av.kind !== "int" || bv.kind !== "int") {
    throw new Error("integer-from-nat-pair: children must be int trivials");
  }
  if (av.int < 0 || bv.int < 0) {
    throw new Error(
      "integer-from-nat-pair: natural-number pair must be non-negative",
    );
  }
  const diff = av.int - bv.int;
  // Canonical form: (diff, 0) — preserves the integer's identity.
  return [k.internTrivialInt(diff), k.internTrivialInt(0)];
}

// ── EQUIV_RATIONAL_FROM_INT_PAIR ──────────────────────────────────────
// Rationals as Q := (Z × Z*) / ~ where (p,q) ~ (r,s) iff p*s = q*r.
// Canonical form: (p/gcd, q/gcd) with sign normalized into numerator.
function gcd(a: number, b: number): number {
  a = Math.abs(a);
  b = Math.abs(b);
  while (b !== 0) {
    const t = b;
    b = a % b;
    a = t;
  }
  return a === 0 ? 1 : a;
}

function handler_rational_from_int_pair(
  k: Kernel,
  raw: readonly NodeID[],
): readonly NodeID[] {
  if (raw.length !== 2) {
    throw new Error(
      `rational-from-int-pair: expected 2 children, got ${raw.length}`,
    );
  }
  const pv = k.trivialValue(raw[0]!);
  const qv = k.trivialValue(raw[1]!);
  if (pv.kind !== "int" || qv.kind !== "int") {
    throw new Error("rational-from-int-pair: children must be int trivials");
  }
  if (qv.int === 0) {
    throw new Error("rational-from-int-pair: zero denominator");
  }
  let p = pv.int;
  let q = qv.int;
  // Sign normalization — keep sign in numerator.
  if (q < 0) {
    p = -p;
    q = -q;
  }
  const g = gcd(p, q);
  return [k.internTrivialInt(p / g), k.internTrivialInt(q / g)];
}

// ── EQUIV_COMMUTATIVE_PAIR ────────────────────────────────────────────
// (a, b) ~ (b, a). Canonicalize by sorting on the NodeID's packed key.
// Works for any pair of substrate NodeIDs — no value-level constraint.
function nodeOrderKey(n: NodeID): string {
  // Stable lexicographic key; matches what nodeKey produces but inlined
  // to avoid a function call in the hot inner loop.
  return `${n.pkg}.${n.level}.${n.type}.${n.inst}`;
}

function handler_commutative_pair(
  _k: Kernel,
  raw: readonly NodeID[],
): readonly NodeID[] {
  if (raw.length !== 2) {
    throw new Error(
      `commutative-pair: expected 2 children, got ${raw.length}`,
    );
  }
  const a = raw[0]!;
  const b = raw[1]!;
  return nodeOrderKey(a) <= nodeOrderKey(b) ? [a, b] : [b, a];
}

// ── EQUIV_ASSOCIATIVE_LEFT_FOLD ───────────────────────────────────────
// For an N-ary binary op, canonicalize to a left-fold. Given children
// [a, b, c, d, ...], the canonical form is the same sequence — the
// presentation is what changes. For substrate-as-tree, what we actually
// canonicalize is: flatten any nested children of the same shape into
// one sequence, then keep order. For this proof-of-shape we only flatten
// at depth 1 (children whose category matches the parent are spliced in).
// The parent-category check is omitted here since we don't know the
// parent at canonicalize time; instead we accept a flat children list
// and return it unchanged — the equivalence's job in practice is to
// canonicalize different *presentations* (right-fold vs left-fold) at
// the recipe-construction layer, which is handled by the symmetry-aware
// canonicalization arm (task #23 — follow-up).
function handler_associative_left_fold(
  _k: Kernel,
  raw: readonly NodeID[],
): readonly NodeID[] {
  // No-op flattening at the children-tuple layer for this proof-of-shape.
  // Real left-fold canonicalization needs recipe-tree access; deferred
  // to the symmetry-aware arm. We still return the children unchanged so
  // structurally-equal inputs share a NodeID — which is the minimum the
  // equivalence promises at this layer.
  return raw;
}

// ---------------------------------------------------------------------------
// Bootstrap registration — runs once per kernel; returns the library of
// built-in EquivalenceRelations. Form code can register more via the
// handler-registry + makeEquivalence path.
// ---------------------------------------------------------------------------

export interface QuotientLibrary {
  EQUIV_INTEGER_FROM_NAT_PAIR: EquivalenceRelation;
  EQUIV_RATIONAL_FROM_INT_PAIR: EquivalenceRelation;
  EQUIV_COMMUTATIVE_PAIR: EquivalenceRelation;
  EQUIV_ASSOCIATIVE_LEFT_FOLD: EquivalenceRelation;
}

let HANDLERS_BOOTSTRAPPED = false;

function bootstrapHandlers(): void {
  if (HANDLERS_BOOTSTRAPPED) return;
  registerHandler("integer-from-nat-pair", handler_integer_from_nat_pair);
  registerHandler("rational-from-int-pair", handler_rational_from_int_pair);
  registerHandler("commutative-pair", handler_commutative_pair);
  registerHandler("associative-left-fold", handler_associative_left_fold);
  HANDLERS_BOOTSTRAPPED = true;
}

export function buildQuotientLibrary(k: Kernel): QuotientLibrary {
  bootstrapHandlers();
  return {
    EQUIV_INTEGER_FROM_NAT_PAIR: makeEquivalence(k, {
      equivalence_name: "integer-from-nat-pair",
      decidability: Decidability.DECIDABLE_CHEAP,
      handler_name: "integer-from-nat-pair",
    }),
    EQUIV_RATIONAL_FROM_INT_PAIR: makeEquivalence(k, {
      equivalence_name: "rational-from-int-pair",
      decidability: Decidability.DECIDABLE_CHEAP,
      handler_name: "rational-from-int-pair",
    }),
    EQUIV_COMMUTATIVE_PAIR: makeEquivalence(k, {
      equivalence_name: "commutative-pair",
      decidability: Decidability.DECIDABLE_CHEAP,
      handler_name: "commutative-pair",
    }),
    EQUIV_ASSOCIATIVE_LEFT_FOLD: makeEquivalence(k, {
      equivalence_name: "associative-left-fold",
      decidability: Decidability.DECIDABLE_CHEAP,
      handler_name: "associative-left-fold",
    }),
  };
}

// Triv.QUOTIENT_LEAF is reserved for a future encoding where the
// canonical form is a single trivial slot rather than a recipe — used
// when the canonical-children-tuple is a fixed-shape integer pair and
// the kernel wants to avoid recipe overhead. The constant is exported
// from kernel.ts; this proof-of-shape uses the recipe form throughout.
export { Triv };
