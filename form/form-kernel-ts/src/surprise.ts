// surprise.ts — free-energy-aware intern + surprise metrics.
//
// When a cell interns a NodeID, the cell's generative model (from #26) carries
// expectations over what shapes are likely. If the interned value's shape is
// novel relative to those expectations, the intern is *surprising* — high
// prediction error — and the substrate records that score on the resulting
// NodeID.
//
// Read the foundation in docs/coherence-substrate/free-energy-holographic-
// foundation.md §5 ("Free-energy-aware intern — surprise as signal"). The
// substrate becomes self-modeling: high-surprise NodeIDs point at the regions
// where a cell's model is wrong, and `mostSurprising` is the introspective
// lens that surfaces them.
//
// Recipe shape:
//   Intern proceeds unchanged (no new RBasic slot — surprise is metadata,
//   not structure). The resulting NodeID is the same node it would have been
//   without the surprise call. The score is held in a side-channel registry,
//   keyed by (kernel, NodeID), so structural identity stays exact.
//
// Pairs with:
//   - generative.ts (#26) — surpriseScore over a sensory NodeID
//   - blanket.ts (#25)    — when the surprising intern arrives via a cell's
//                           sensory channel, the blanket says "this came from
//                           outside the cell"; surprise then carries cross-cell
//                           predictive-error meaning, not just self-mismatch.
//
// What's deliberately not here:
//   - Threshold-based refusal of high-surprise interns. Default behavior is
//     "intern proceeds." Refusal belongs at the policy layer above the kernel.
//   - Model updates as side effects. `refineModelFromSurprise` *suggests*
//     a refinement (returns a structured proposal); applying it is the
//     caller's choice.
//   - Free-energy as a probabilistic quantity. We carry the lattice-native
//     `surpriseScore` (from generative.ts) directly. Probabilistic upgrades
//     are an open question named in the foundation doc (§"Open questions").

import { Kernel, NodeID, nodeKey } from "./kernel.ts";
import {
  GenerativeModel,
  modelOf,
  surpriseScore,
} from "./generative.ts";

// ---------------------------------------------------------------------------
// Per-kernel surprise registry
// ---------------------------------------------------------------------------

// SurpriseRecord — one observation. We keep the cell that interned and the
// score; downstream code may want to aggregate by cell.
export interface SurpriseRecord {
  readonly node: NodeID;
  readonly cell: NodeID;
  readonly score: number;
}

// WeakMap keyed by Kernel — same scope rule as generative.ts's model registry.
// Two maps inside each entry:
//   - byNode    : last-write-wins score per NodeID (the "metric on the resulting
//                 NodeID" called for by the foundation doc).
//   - byCell    : append-only log of (NodeID, score) per cell, used by
//                 refineModelFromSurprise to compute aggregates.
interface KernelRegistry {
  byNode: Map<string, SurpriseRecord>;
  byCell: Map<string, SurpriseRecord[]>;
}

const registries = new WeakMap<Kernel, KernelRegistry>();

function registryFor(k: Kernel): KernelRegistry {
  let r = registries.get(k);
  if (r === undefined) {
    r = { byNode: new Map(), byCell: new Map() };
    registries.set(k, r);
  }
  return r;
}

function recordSurprise(
  k: Kernel,
  cell: NodeID,
  node: NodeID,
  score: number,
): void {
  const reg = registryFor(k);
  const rec: SurpriseRecord = { node, cell, score };
  reg.byNode.set(nodeKey(node), rec);
  const cellKey = nodeKey(cell);
  let log = reg.byCell.get(cellKey);
  if (log === undefined) {
    log = [];
    reg.byCell.set(cellKey, log);
  }
  log.push(rec);
}

// ---------------------------------------------------------------------------
// internWithSurprise — intern + measure prediction error
// ---------------------------------------------------------------------------

// Interns `(category, children)` through the kernel's content-addressed intern
// table, then computes a surprise score relative to the cell's registered
// generative model. Recording is best-effort: if the cell has no model, the
// score is 0 (nothing is "surprising" without an expectation against which to
// be surprised — that's not a fact about the value, it's a fact about the
// observer) and no record is added — only cells with models participate in the
// metric.
//
// Returns the NodeID exactly as `k.intern` would have. Surprise lives in the
// side-channel; the substrate's identity stays clean.
export function internWithSurprise(
  k: Kernel,
  cell: NodeID,
  category: NodeID,
  children: readonly NodeID[],
): NodeID {
  const node = k.intern(category, children);
  const model = modelOf(k, cell);
  if (model === null) {
    // No model registered — nothing to predict against. The intern still
    // happened (the substrate stayed itself); we just don't record anything.
    return node;
  }
  const score = surpriseScore(k, model, node);
  recordSurprise(k, cell, node, score);
  return node;
}

// Convenience: intern with surprise where a model is supplied directly rather
// than looked up from the cell registry. Useful when comparing the same node
// against an alternative model without registering it as the cell's current
// generative model.
export function internWithSurpriseAgainst(
  k: Kernel,
  cell: NodeID,
  model: GenerativeModel,
  category: NodeID,
  children: readonly NodeID[],
): { node: NodeID; score: number } {
  const node = k.intern(category, children);
  const score = surpriseScore(k, model, node);
  recordSurprise(k, cell, node, score);
  return { node, score };
}

// ---------------------------------------------------------------------------
// surpriseMetricsFor — lookup recorded score
// ---------------------------------------------------------------------------

// Returns the most recent SurpriseRecord for a node, or null if no record was
// ever made. The caller can read .score for the scalar; the .cell field gives
// the introspective "which cell saw this as surprising" context.
export function surpriseMetricsFor(
  k: Kernel,
  node: NodeID,
): SurpriseRecord | null {
  const reg = registries.get(k);
  if (reg === undefined) return null;
  return reg.byNode.get(nodeKey(node)) ?? null;
}

// ---------------------------------------------------------------------------
// mostSurprising — introspective sense: which NodeIDs surprised us most
// ---------------------------------------------------------------------------

// Returns the top-N records by descending score. Ties broken by recency
// (later insertion comes first) so equally-surprising nodes still produce a
// stable order — the most recently observed surprise wins.
//
// Lattice introspection: walk this list and you're looking at the places the
// substrate's own generative models are weakest. Refinement candidates.
export function mostSurprising(
  k: Kernel,
  top_n: number,
): readonly SurpriseRecord[] {
  if (top_n <= 0) return [];
  const reg = registries.get(k);
  if (reg === undefined) return [];
  const all = [...reg.byNode.values()];
  // Sort by score desc; stable ordering within ties is implementation-defined
  // in V8 — explicit secondary key keeps it deterministic across runs.
  all.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    // Tiebreak: prefer the one whose node has the larger inst (later intern).
    return b.node.inst - a.node.inst;
  });
  return all.slice(0, top_n);
}

// All records, no truncation. Useful for cross-cell aggregation or for tests
// that want to count observations.
export function allSurpriseRecords(
  k: Kernel,
): readonly SurpriseRecord[] {
  const reg = registries.get(k);
  if (reg === undefined) return [];
  return [...reg.byNode.values()];
}

// ---------------------------------------------------------------------------
// refineModelFromSurprise — suggest a refinement to a cell's generative model
// ---------------------------------------------------------------------------

// A ModelRefinement is a proposal — not an action. The caller decides whether
// to apply it (typically by calling makeGenerativeModel again with the
// suggested expected[] union).
//
// Heuristic logic:
//   - If the cell has fewer than 2 observations, we don't have enough signal
//     to suggest anything yet. Return null.
//   - If the mean surprise across observations is small (< 1), the model is
//     predicting well; no refinement needed. Return null.
//   - Otherwise, the high-surprise nodes are *novel patterns the cell keeps
//     seeing that its model doesn't expect*. Surface them as `suggestExpected`
//     so the caller can add them to the model's expected[] list (which would
//     drop their future surprise to 0).
//
// The reasoning: surprise = "I didn't predict this." Repeated surprise =
// "I keep not predicting this." The healing move is to update the model so
// the next observation IS predicted. That IS the canonicalization-rule
// refinement the foundation doc calls for.
export interface ModelRefinement {
  readonly cell: NodeID;
  // Observations the cell saw with surprise > 0, ranked desc.
  readonly highSurpriseNodes: readonly NodeID[];
  // Mean surprise across all observations (signal strength).
  readonly meanSurprise: number;
  // Suggested addition to the model's expected[] list — the top novel shapes
  // the cell keeps encountering. Adding these drops their surprise to 0 on
  // future interns of the same shape.
  readonly suggestExpected: readonly NodeID[];
  // Human-readable rationale for the suggestion. Logged, not parsed.
  readonly rationale: string;
}

export function refineModelFromSurprise(
  k: Kernel,
  cell: NodeID,
): ModelRefinement | null {
  const reg = registries.get(k);
  if (reg === undefined) return null;
  const log = reg.byCell.get(nodeKey(cell));
  if (log === undefined || log.length < 2) return null;

  let total = 0;
  for (const r of log) total += r.score;
  const meanSurprise = total / log.length;

  // If the model is predicting well on average, no refinement.
  if (meanSurprise < 1) return null;

  // Gather the high-surprise observations, dedupe by node, rank by score desc.
  const seen = new Map<string, SurpriseRecord>();
  for (const r of log) {
    if (r.score <= 0) continue;
    const key = nodeKey(r.node);
    const prior = seen.get(key);
    if (prior === undefined || r.score > prior.score) {
      seen.set(key, r);
    }
  }
  const ranked = [...seen.values()].sort((a, b) => b.score - a.score);
  const highSurpriseNodes = ranked.map((r) => r.node);

  // Suggest adding the top three novel shapes to the expected[] list. Three
  // is a tuning parameter — keeps the proposal focused without overwhelming
  // a model that's broadly miscalibrated.
  const suggestExpected = highSurpriseNodes.slice(0, 3);

  const rationale =
    `cell observed ${log.length} interns with mean surprise ${meanSurprise.toFixed(2)}; ` +
    `${highSurpriseNodes.length} distinct novel shapes; ` +
    `adding top ${suggestExpected.length} to expected[] would reduce future surprise to 0 for those shapes`;

  return {
    cell,
    highSurpriseNodes,
    meanSurprise,
    suggestExpected,
    rationale,
  };
}

// ---------------------------------------------------------------------------
// Test/maintenance helpers
// ---------------------------------------------------------------------------

// Clears the surprise registry for a kernel. Useful for tests that want a
// fresh observation log without re-creating the kernel.
export function clearSurpriseRegistry(k: Kernel): void {
  registries.delete(k);
}
