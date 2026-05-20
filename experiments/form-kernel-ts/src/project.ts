// PROJECT — holographic zoom over the substrate.
//
// `(PROJECT cell-recipe target-level)` views a cell at a chosen compositional
// depth. The fractal property says the shape is the same at every level;
// PROJECT exposes that shape at a chosen granularity.
//
//   • projectDown — shrink the view. Replace values with category-only
//     placeholders, collapse sub-trees whose depth exceeds target-level into
//     a "shape token" at their category. The result has the same outer
//     category-tree as the source but no leaf content.
//
//   • projectUp   — expand the view. Walk the intern table for recipes whose
//     children include this NodeID, then those that contain those, up to
//     target-level. The result is the smallest containing composite at the
//     requested level, or the source itself if nothing contains it.
//
//   • makeProjection — intern `RBasic.PROJECT[source, level-trivial]` so a
//     projection is itself a first-class substrate value, addressable by
//     content. Two projections of the same source at the same level share
//     a NodeID.
//
//   • structuralShape — convenience for projectDown to level 2 (BASIC). The
//     "blueprint shape" with values stripped; two semantically-different but
//     structurally-identical cells share the same shape NodeID.
//
// Additive only — no existing walk/intern semantics changed. Projections
// are interned recipes like everything else; the kernel walker doesn't yet
// dispatch on RBasic.PROJECT (no semantic call required — the projection
// IS the result, expressed structurally).

import {
  type Kernel,
  type NodeID,
  Level,
  RBasic,
  Triv,
  nodeKey,
} from "./kernel.js";

// ---------------------------------------------------------------------------
// Compositional depth — derived from tree shape
// ---------------------------------------------------------------------------

// Compositional depth of a NodeID is the height of its recipe tree:
//   • a trivial leaf has depth 1
//   • a composite has depth = 1 + max(child depth)
//
// This is the operational reading of "level" for PROJECT. It is computed
// from the actual tree, not from the NodeID.level field (which intern()
// keeps tagged as the category's level for content-addressing).
export function compositionalDepth(k: Kernel, n: NodeID): number {
  if (n.level === Level.TRIVIAL) return 1;
  const kids = k.children(n);
  if (kids.length === 0) return 1;
  let max = 0;
  for (const c of kids) {
    const d = compositionalDepth(k, c);
    if (d > max) max = d;
  }
  return 1 + max;
}

// ---------------------------------------------------------------------------
// projectDown — view at a lower compositional depth
// ---------------------------------------------------------------------------

// Down-project a NodeID to `targetLevel`. Higher levels keep more detail;
// lower levels keep only outer structure.
//
// Semantics:
//   • If the source is already at-or-below targetLevel, return it unchanged.
//   • Otherwise replace every trivial value descendant with a "shape token"
//     for that trivial's category (so the type survives but the value does
//     not). Composites whose subtree exceeds the remaining budget collapse
//     to their category alone.
//
// The returned NodeID is interned — two cells with the same structural
// shape produce the same projection NodeID.
export function projectDown(
  k: Kernel,
  n: NodeID,
  targetLevel: number,
): NodeID {
  if (targetLevel < 1) {
    throw new Error(`projectDown: targetLevel must be >= 1, got ${targetLevel}`);
  }
  // targetLevel is the max depth of the resulting tree. A trivial alone has
  // depth 1, a category with trivial children has depth 2, etc.
  return projectDownToBudget(k, n, targetLevel);
}

function projectDownToBudget(
  k: Kernel,
  n: NodeID,
  remaining: number,
): NodeID {
  // remaining = how many levels (including current) we still allow.
  // Already a shape token (string starting "@shape:" or zero-inst trivial)?
  // Pass through — idempotent.
  if (isShapeToken(k, n)) return n;

  if (remaining <= 1) {
    // Only current level — collapse to a category-only shape token.
    return shapeToken(k, n);
  }
  if (n.level === Level.TRIVIAL) {
    // Trivial: strip value, keep type. Depth 1.
    return trivialShapeToken(k, n);
  }
  const kids = k.children(n);
  if (kids.length === 0) {
    return shapeToken(k, n);
  }
  const cat = k.category(n);
  const projectedKids = kids.map((c) =>
    projectDownToBudget(k, c, remaining - 1),
  );
  return k.intern(cat, projectedKids);
}

// isShapeToken — recognise already-stripped trivials so structuralShape is
// idempotent. shapeToken(composite) → STRING starting "@shape:";
// trivialShapeToken → trivial of the source type at inst=0.
function isShapeToken(k: Kernel, n: NodeID): boolean {
  if (n.level !== Level.TRIVIAL) return false;
  if (n.type === Triv.STRING) {
    if (n.inst === 0) return true;
    const s = k.strs[n.inst];
    return typeof s === "string" && s.startsWith("@shape:");
  }
  // Other trivial types: inst=0 is the shape-token sentinel.
  return n.inst === 0;
}

// shapeToken — a depth-1 placeholder for a node at a given category. When a
// composite collapses out-of-budget, we encode its category as a STRING
// trivial whose value is the canonical "pkg.level.type.inst" of the
// category NodeID. The trivial keeps depth at 1 and stays content-addressed
// (same category ⇒ same string ⇒ same trivial NodeID across calls).
function shapeToken(k: Kernel, n: NodeID): NodeID {
  if (n.level === Level.TRIVIAL) return trivialShapeToken(k, n);
  const cat = k.category(n);
  const tag = `@shape:${cat.pkg}.${cat.level}.${cat.type}.${cat.inst}`;
  return k.internString(tag);
}

// trivialShapeToken — replace a concrete trivial value with a category-only
// placeholder. INT 42 and INT 7 both project to the same token; STRING "a"
// and STRING "b" both project to the same token; INT and STRING differ.
function trivialShapeToken(k: Kernel, n: NodeID): NodeID {
  switch (n.type) {
    case Triv.INT:
      // Distinct sentinel inst that no real int reaches: use 0.
      return { pkg: 1, level: Level.TRIVIAL, type: Triv.INT, inst: 0 };
    case Triv.STRING:
      // The empty string interned at index 0-or-found.
      return { pkg: 1, level: Level.TRIVIAL, type: Triv.STRING, inst: 0 };
    case Triv.BOOL:
      return { pkg: 1, level: Level.TRIVIAL, type: Triv.BOOL, inst: 0 };
    case Triv.NULL:
      return { pkg: 1, level: Level.TRIVIAL, type: Triv.NULL, inst: 0 };
    default:
      // Unknown trivial type — preserve type, zero the inst.
      return { pkg: 1, level: Level.TRIVIAL, type: n.type, inst: 0 };
  }
}

// ---------------------------------------------------------------------------
// projectUp — view at a higher compositional depth (containment)
// ---------------------------------------------------------------------------

// Up-project a NodeID: find recipes in the kernel's intern table whose
// children include this NodeID, then the recipes containing those, walking
// the containment graph up to compositional depth `targetLevel`.
//
// Returns:
//   • the source itself if nothing contains it,
//   • otherwise the deepest containing composite at-or-below targetLevel.
//
// When multiple recipes contain the source at the same level, returns the
// one with the lowest NodeID inst (deterministic; first interned wins).
export function projectUp(
  k: Kernel,
  n: NodeID,
  targetLevel: number,
): NodeID {
  if (targetLevel < 1) {
    throw new Error(`projectUp: targetLevel must be >= 1, got ${targetLevel}`);
  }
  let current = n;
  let currentDepth = compositionalDepth(k, current);
  // Walk up until we reach targetLevel or no container exists.
  while (currentDepth < targetLevel) {
    const container = findContainer(k, current);
    if (container === undefined) break;
    current = container;
    currentDepth = compositionalDepth(k, current);
  }
  return current;
}

// findContainer — scan the intern table for a recipe whose children include
// the given NodeID. Returns the first (lowest-inst) match, or undefined if
// no composite contains it.
//
// Scan cost is O(total-recipes * avg-children). For the kernel sizes we
// run (sub-10k recipes per session), this is sub-millisecond; PROJECT is
// not on the hot path.
export function findContainer(
  k: Kernel,
  n: NodeID,
): NodeID | undefined {
  const target = nodeKey(n);
  let best: { inst: number; nid: NodeID } | undefined;
  for (const [key, recipe] of k.byID) {
    for (const c of recipe.children) {
      if (nodeKey(c) === target) {
        // Reconstruct NodeID from key — cheaper to keep both.
        const parts = key.split(".");
        const pkg = parts[0] ? parseInt(parts[0], 10) : 1;
        const level = parts[1] ? parseInt(parts[1], 10) : Level.BASIC;
        const type = parts[2] ? parseInt(parts[2], 10) : 0;
        const inst = parts[3] ? parseInt(parts[3], 10) : 0;
        const nid: NodeID = { pkg, level, type, inst };
        if (best === undefined || inst < best.inst) {
          best = { inst, nid };
        }
        break; // one match per container is enough
      }
    }
  }
  return best?.nid;
}

// findAllContainers — every recipe whose children include this NodeID.
// Useful for surveying a cell's full containment context.
export function findAllContainers(k: Kernel, n: NodeID): NodeID[] {
  const target = nodeKey(n);
  const out: NodeID[] = [];
  for (const [key, recipe] of k.byID) {
    for (const c of recipe.children) {
      if (nodeKey(c) === target) {
        const parts = key.split(".");
        const pkg = parts[0] ? parseInt(parts[0], 10) : 1;
        const level = parts[1] ? parseInt(parts[1], 10) : Level.BASIC;
        const type = parts[2] ? parseInt(parts[2], 10) : 0;
        const inst = parts[3] ? parseInt(parts[3], 10) : 0;
        out.push({ pkg, level, type, inst });
        break;
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// makeProjection — first-class projection recipes
// ---------------------------------------------------------------------------

// Intern a `RBasic.PROJECT[source, level]` recipe so a projection is itself
// a substrate value. The category carries PROJECT; the two children are the
// source NodeID-wrapped-as-trivial-shape and a level integer trivial.
//
// Holding a projection as a first-class cell lets far cells exchange the
// statement "I am viewing X at level L" without serializing the projected
// content — the receiver can re-derive the content from the source.
export function makeProjection(
  k: Kernel,
  source: NodeID,
  level: number,
): NodeID {
  if (level < 1) {
    throw new Error(`makeProjection: level must be >= 1, got ${level}`);
  }
  const projectCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.PROJECT,
    inst: 1,
  };
  // Encode source as its NodeID-tuple via four int trivials. This keeps the
  // projection content-addressed: same (source, level) ⇒ same NodeID.
  const srcPkg = k.internTrivialInt(source.pkg);
  const srcLvl = k.internTrivialInt(source.level);
  const srcTyp = k.internTrivialInt(source.type);
  const srcIns = k.internTrivialInt(source.inst);
  const lvl = k.internTrivialInt(level);
  return k.intern(projectCat, [srcPkg, srcLvl, srcTyp, srcIns, lvl]);
}

// ---------------------------------------------------------------------------
// structuralShape — the canonical "blueprint shape" at level BASIC
// ---------------------------------------------------------------------------

// Project to level 2 (BASIC) — strip all values, keep the category tree.
// Two semantically-different but structurally-identical cells share the
// same shape NodeID. This is the equivalence the substrate promises:
// shape-level identity comes for free, no manual normalization needed.
export function structuralShape(k: Kernel, n: NodeID): NodeID {
  return projectDown(k, n, Level.BASIC);
}
