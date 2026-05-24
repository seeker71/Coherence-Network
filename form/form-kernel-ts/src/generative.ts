// generative.ts — substrate-resident generative model recipes.
//
// Each cell carries a generative model: a recipe declaring what it expects to
// receive at its blanket's sensory channel, what priors it holds over its
// environment, and how to predict an internal update from a sensory NodeID.
// The model IS the protocol — declared as a substrate cell, no serialization
// at the boundary.
//
// Recipe shape (GENERATIVE, slot 82):
//   children = [cell, expected_sensory_LIST, prior_belief_LIST, prediction_fn]
//
// All four children are NodeIDs in the substrate. Content-addressing through
// the intern table means structurally identical models share the same NodeID.
// Two cells with same-shape generative models are recognized as equivalent
// without any external diff.
//
// Pairs with the Markov blanket (slot 81). The blanket carves the cell/world
// surface; the model interprets what flows through that surface. Together
// they enable cross-cell prediction: cell A emits at its active channel →
// arrives at cell B's sensory channel → B's model predicts an internal
// update → B's internal state advances.
//
// What's deferred to #29: free-energy-aware intern that weights the intern
// dedup by predictive surprise, and a richer surprise-metrics integration
// that closes the perception–action loop in form-runtime-in-form.

import {
  Kernel,
  Level,
  NodeID,
  RBasic,
  Triv,
  nodeKey,
  walk,
  Frame,
  Value,
} from "./kernel.ts";

// ---------------------------------------------------------------------------
// Branded NodeID wrapper — same pattern as blanket.ts
// ---------------------------------------------------------------------------

// A GenerativeModel is a NodeID branded by intent. Structurally it is a plain
// substrate node whose category.type === RBasic.GENERATIVE; the brand is a
// reader-side affordance, not a runtime tag.
export interface GenerativeModel {
  readonly node: NodeID;
  readonly __brand: "GenerativeModel";
}

function brand(node: NodeID): GenerativeModel {
  return { node, __brand: "GenerativeModel" };
}

// ---------------------------------------------------------------------------
// Per-kernel cell → model registry
// ---------------------------------------------------------------------------

// WeakMap keyed by Kernel instance so multiple kernels in the same process
// don't share registries. Inside the per-kernel store we key by `nodeKey(cell)`
// — same content-address as the substrate's own internal table.
const registries = new WeakMap<Kernel, Map<string, GenerativeModel>>();

function registryFor(k: Kernel): Map<string, GenerativeModel> {
  let r = registries.get(k);
  if (r === undefined) {
    r = new Map<string, GenerativeModel>();
    registries.set(k, r);
  }
  return r;
}

// ---------------------------------------------------------------------------
// Category sentinel — RBasic.GENERATIVE category node (level=BASIC, inst=0)
// ---------------------------------------------------------------------------

// The category NodeID for a GENERATIVE recipe. inst=0 marks it as the category
// sentinel itself, not an instance. Content-addressing the recipe always uses
// this exact category node, so structurally identical models hash equal.
function generativeCategory(): NodeID {
  return {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.GENERATIVE,
    inst: 0,
  };
}

// ---------------------------------------------------------------------------
// makeGenerativeModel — intern a GENERATIVE recipe for a cell
// ---------------------------------------------------------------------------

// Builds a LIST recipe from the given NodeIDs. Lists are RBasic.LIST with
// category inst=0; same-content lists intern to the same NodeID.
function internList(k: Kernel, items: readonly NodeID[]): NodeID {
  const cat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.LIST,
    inst: 0,
  };
  return k.intern(cat, items);
}

export function makeGenerativeModel(
  k: Kernel,
  cell: NodeID,
  expected: readonly NodeID[],
  priors: readonly NodeID[],
  prediction: NodeID,
): GenerativeModel {
  const expectedList = internList(k, expected);
  const priorsList = internList(k, priors);
  const node = k.intern(generativeCategory(), [
    cell,
    expectedList,
    priorsList,
    prediction,
  ]);
  const model = brand(node);
  // Register cell → model. If a different model is being declared for the
  // same cell, last-write-wins — the substrate keeps both recipes (they
  // have different NodeIDs because their children differ), but the registry
  // tracks the cell's current model.
  registryFor(k).set(nodeKey(cell), model);
  return model;
}

// ---------------------------------------------------------------------------
// modelOf — lookup a cell's currently-registered generative model
// ---------------------------------------------------------------------------

export function modelOf(k: Kernel, cell: NodeID): GenerativeModel | null {
  const m = registryFor(k).get(nodeKey(cell));
  return m ?? null;
}

// ---------------------------------------------------------------------------
// Accessors — read structured fields back from a GENERATIVE recipe
// ---------------------------------------------------------------------------

export function modelCell(k: Kernel, m: GenerativeModel): NodeID {
  const kids = k.children(m.node);
  const c = kids[0];
  if (c === undefined) {
    throw new Error("generative: malformed model (missing cell)");
  }
  return c;
}

export function modelExpected(k: Kernel, m: GenerativeModel): readonly NodeID[] {
  const kids = k.children(m.node);
  const list = kids[1];
  if (list === undefined) return [];
  return k.children(list);
}

export function modelPriors(k: Kernel, m: GenerativeModel): readonly NodeID[] {
  const kids = k.children(m.node);
  const list = kids[2];
  if (list === undefined) return [];
  return k.children(list);
}

export function modelPredictionFn(k: Kernel, m: GenerativeModel): NodeID {
  const kids = k.children(m.node);
  const fn = kids[3];
  if (fn === undefined) {
    throw new Error("generative: malformed model (missing prediction_fn)");
  }
  return fn;
}

// ---------------------------------------------------------------------------
// predict — run the prediction_fn over a sensory NodeID
// ---------------------------------------------------------------------------

// The prediction_fn is itself a recipe. Three calling conventions are
// supported, matching how Form code declares functions:
//
//   1. FNDEF closure — name|params|body shape; walk binds parameters, runs.
//   2. Identifier resolving to a native — invoked with (sensory_value) as the
//      single argument, wrapped as a nodeid Value.
//   3. Identity — if prediction_fn is a bare LIST/IDENT or the same recipe
//      shape as a passthrough, returns sensory_value unchanged.
//
// Returns the predicted-internal-update NodeID, or null if the prediction
// surface refuses (closure returns non-nodeid, native raises, etc.).
export function predict(
  k: Kernel,
  model: GenerativeModel,
  sensory_value: NodeID,
): NodeID | null {
  const fn = modelPredictionFn(k, model);
  const frame = new Frame(null);

  // Walk fn first so FNDEF binds its name into the frame and returns a
  // closure value. If it's an IDENT or a literal, walk produces the underlying
  // value directly.
  let fnVal: Value;
  try {
    fnVal = walk(k, fn, frame);
  } catch {
    return null;
  }

  // Build a FNCALL recipe: [callee=fn-name-as-string, arg=sensory-as-nodeid-literal]
  // Then bind the sensory Value into the frame under a fresh name and walk it.
  // Simpler path: if fnVal is a closure with arity 1, invoke directly.
  if (fnVal.kind === "closure") {
    const cl = fnVal.closure;
    if (cl.params.length !== 1) {
      return null;
    }
    const callFrame = new Frame(cl.env);
    callFrame.bind(cl.params[0]!, { kind: "nodeid", nodeid: sensory_value });
    let result: Value;
    try {
      result = walk(k, cl.body, callFrame);
    } catch {
      return null;
    }
    if (result.kind === "nodeid") return result.nodeid;
    return null;
  }

  // If fnVal is already a nodeid (e.g. prediction_fn is the identity recipe —
  // a substrate node we treat as the predicted update directly), return it.
  if (fnVal.kind === "nodeid") return fnVal.nodeid;

  return null;
}

// ---------------------------------------------------------------------------
// surpriseScore — compare actual sensory to expected
// ---------------------------------------------------------------------------

// Surprise = Hamming-style mismatch between the actual sensory NodeID and the
// model's expected_sensory set. 0 when actual is a member of expected; rises
// with structural distance otherwise. This is the lattice-native scalar that
// #29's free-energy intern will weight by.
//
// Distance metric:
//   - Exact NodeID match in expected → 0
//   - Same category (recipe shape family) as any expected → 1
//   - Otherwise → 1 + min(|kids_actual - kids_expected|) across expected
//     plus a penalty if no expected is present at all
//
// Returns a non-negative number. Higher = greater prediction error.
export function surpriseScore(
  k: Kernel,
  model: GenerativeModel,
  actual_sensory: NodeID,
): number {
  const expected = modelExpected(k, model);
  if (expected.length === 0) {
    // No declared expectations — every sensory is unexpected. Score = 1.
    return 1;
  }

  // Exact match → no surprise.
  const actualKey = nodeKey(actual_sensory);
  for (const e of expected) {
    if (nodeKey(e) === actualKey) return 0;
  }

  // Same-shape match → small surprise.
  const actualCat = k.category(actual_sensory);
  const actualCatKey = nodeKey(actualCat);
  const actualKids = k.children(actual_sensory);
  let best = Infinity;
  for (const e of expected) {
    const eCat = k.category(e);
    const eKids = k.children(e);
    if (nodeKey(eCat) === actualCatKey) {
      // Same recipe family — surprise is the child-count delta plus a small
      // structural floor.
      const delta = Math.abs(actualKids.length - eKids.length);
      const score = 1 + delta;
      if (score < best) best = score;
    }
  }
  if (best !== Infinity) return best;

  // No family match — large surprise. Bounded but distinguishable from the
  // "no expectations" baseline so callers can tell the two apart.
  return 10;
}

// ---------------------------------------------------------------------------
// composeModels — two cells compose, their generative models compose
// ---------------------------------------------------------------------------

// Composition is union over expected_sensory and prior_belief (de-duplicated
// by NodeID equality), and a delegating prediction_fn. Because the inputs to
// intern are sorted-then-deduped and the prediction_fn is composed from both
// children, the result is content-addressed: compose(a,b) === compose(b,a)
// and compose(compose(a,b),c) === compose(a,compose(b,c)).
//
// The composed prediction_fn is a SEQUENCE recipe carrying both source fns
// as children. The walker semantics for SEQUENCE return the last value; in
// practice a free-energy-aware caller (deferred to #29) picks among the
// children by which one minimizes surprise. For now we surface both so the
// composition is observable structurally.
//
// composeModels does NOT register the composed model against any cell — it
// returns a free-standing GenerativeModel. Callers register it explicitly
// via makeGenerativeModel with their composed-cell NodeID if desired.
// Canonical SEQUENCE category — kept inline to avoid a circular import.
const SEQUENCE_CAT: NodeID = {
  pkg: 1,
  level: Level.BASIC,
  type: RBasic.BLOCK,
  inst: 2, // RBlock.SEQUENCE
};

// Was this node produced by composeModels as its composed-cell sentinel?
// We mark composed cells with a LIST recipe whose first child is a string
// trivial "composed:" — the convention lets recursive composeModels flatten
// rather than nest.
function isComposedCellSentinel(k: Kernel, n: NodeID): boolean {
  if (n.level !== Level.BASIC || n.type !== RBasic.LIST) return false;
  const kids = k.children(n);
  const first = kids[0];
  if (
    first === undefined ||
    first.level !== Level.TRIVIAL ||
    first.type !== Triv.STRING
  ) {
    return false;
  }
  return k.nameStr(first.inst) === "composed:";
}

// Extract cell children from either a leaf cell (returns [cell]) or a
// composed-cell sentinel (returns the flattened list of leaf cells).
function unwrapCells(k: Kernel, cell: NodeID): NodeID[] {
  if (!isComposedCellSentinel(k, cell)) return [cell];
  return k.children(cell).slice(1); // drop the "composed:" tag
}

// Extract prediction-fn children: if fn is a SEQUENCE recipe produced by a
// prior composeModels call, return its children; otherwise return [fn].
function unwrapPredictionFns(k: Kernel, fn: NodeID): NodeID[] {
  if (fn.level !== Level.BASIC) return [fn];
  const cat = k.category(fn);
  if (cat.type !== RBasic.BLOCK) return [fn];
  // Only flatten SEQUENCE produced by composition — heuristic: SEQUENCE
  // recipes with all children that themselves look like fns (FNDEF or
  // identifiers resolving to fns). We accept any SEQUENCE here since the
  // wrapper SEQUENCE is the one we create ourselves.
  if (cat.inst !== 2) return [fn]; // not SEQUENCE
  return [...k.children(fn)];
}

export function composeModels(
  k: Kernel,
  a: GenerativeModel,
  b: GenerativeModel,
): GenerativeModel {
  // Union by content-address. Sort by nodeKey for canonical ordering so the
  // resulting LIST recipe interns to the same NodeID regardless of arg order.
  const expectedSet = new Map<string, NodeID>();
  for (const e of modelExpected(k, a)) expectedSet.set(nodeKey(e), e);
  for (const e of modelExpected(k, b)) expectedSet.set(nodeKey(e), e);
  const expected = [...expectedSet.entries()]
    .sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0))
    .map(([, n]) => n);

  const priorsSet = new Map<string, NodeID>();
  for (const p of modelPriors(k, a)) priorsSet.set(nodeKey(p), p);
  for (const p of modelPriors(k, b)) priorsSet.set(nodeKey(p), p);
  const priors = [...priorsSet.entries()]
    .sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0))
    .map(([, n]) => n);

  // Composed prediction_fn: flatten any prior composed SEQUENCE on either
  // side, dedupe by nodeKey, then sort. Result is the same regardless of
  // how we associate, so compose is both commutative and associative.
  const fnSet = new Map<string, NodeID>();
  for (const f of unwrapPredictionFns(k, modelPredictionFn(k, a)))
    fnSet.set(nodeKey(f), f);
  for (const f of unwrapPredictionFns(k, modelPredictionFn(k, b)))
    fnSet.set(nodeKey(f), f);
  const orderedFns = [...fnSet.entries()]
    .sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0))
    .map(([, n]) => n);
  // If only one fn after dedup, use it directly — don't wrap a singleton
  // SEQUENCE around a single fn (preserves equality with the leaf case).
  const predictionFn =
    orderedFns.length === 1
      ? orderedFns[0]!
      : k.intern(SEQUENCE_CAT, orderedFns);

  // Composed cell sentinel: flatten any prior composed-cell sentinels,
  // dedupe leaf cells by nodeKey, sort, then wrap with a "composed:" tag
  // so this sentinel is distinguishable from a leaf cell and the next
  // composition can flatten through it.
  const cellSet = new Map<string, NodeID>();
  for (const c of unwrapCells(k, modelCell(k, a))) cellSet.set(nodeKey(c), c);
  for (const c of unwrapCells(k, modelCell(k, b))) cellSet.set(nodeKey(c), c);
  const orderedCells = [...cellSet.entries()]
    .sort(([x], [y]) => (x < y ? -1 : x > y ? 1 : 0))
    .map(([, n]) => n);
  const composedTag = k.internString("composed:");
  const composedCell = internList(k, [composedTag, ...orderedCells]);

  const expectedList = internList(k, expected);
  const priorsList = internList(k, priors);
  const node = k.intern(generativeCategory(), [
    composedCell,
    expectedList,
    priorsList,
    predictionFn,
  ]);
  return brand(node);
}

// ---------------------------------------------------------------------------
// Helpers exported for tests and future free-energy integration
// ---------------------------------------------------------------------------

export function isGenerativeModel(k: Kernel, n: NodeID): boolean {
  if (n.level !== Level.BASIC) return false;
  const cat = k.category(n);
  return cat.type === RBasic.GENERATIVE;
}

// Wrap an existing NodeID known to be a GENERATIVE recipe back into the
// branded type. Throws if the node is not a generative recipe.
export function asGenerativeModel(k: Kernel, n: NodeID): GenerativeModel {
  if (!isGenerativeModel(k, n)) {
    throw new Error(
      `asGenerativeModel: node ${nodeKey(n)} is not a GENERATIVE recipe`,
    );
  }
  return brand(n);
}

// Re-exported for callers building cell NodeIDs without round-tripping through
// kernel internals.
export { Triv };
