// Standalone FMF tests. Run with:
//   cd form/form-kernel-ts && npx tsx src/field.test.ts

import { Kernel, type NodeID } from "./kernel.ts";
import {
  fieldStep,
  intervene,
  liftGraphToField,
  liftSequenceToField,
  makeBindingRule,
  makeDiffusionRule,
  makeFieldBlueprint,
  makeFieldRule,
  makeOhmCurrentRule,
  makeSequenceWindowRule,
  projectGraph,
  projectSequence,
  reverseReceipt,
  type FieldCell,
  type FieldEdge,
  type FieldMatch,
  type FieldSite,
} from "./field.ts";

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void): void {
  try {
    fn();
    passed++;
    process.stdout.write(`  ok  ${name}\n`);
  } catch (e) {
    failed++;
    const msg = e instanceof Error ? e.message : String(e);
    process.stdout.write(`  FAIL ${name}: ${msg}\n`);
  }
}

function assertEq<T>(actual: T, expected: T, msg = ""): void {
  if (actual !== expected) {
    throw new Error(
      `${msg ? msg + ": " : ""}expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
    );
  }
}

function assertApprox(actual: number, expected: number, epsilon = 1e-9): void {
  if (Math.abs(actual - expected) > epsilon) {
    throw new Error(`expected ${expected}, got ${actual}`);
  }
}

function assertNodeEq(a: NodeID, b: NodeID, msg = ""): void {
  if (a.pkg !== b.pkg || a.level !== b.level || a.type !== b.type || a.inst !== b.inst) {
    throw new Error(`${msg ? msg + ": " : ""}nodes differ`);
  }
}

function site(field: FieldCell, id: string): FieldSite {
  const found = field.state.sites.find((candidate) => candidate.id === id);
  if (!found) throw new Error(`missing site ${id}`);
  return found;
}

function edge(field: FieldCell, index: number): FieldEdge {
  const found = field.state.edges[index];
  if (!found) throw new Error(`missing edge ${index}`);
  return found;
}

const OBSERVER = { name: "fmf-test-observer", policy: "all-compatible" as const };

test("DNA/RNA sequence field: HBB CDS prefix lifts, executes codon rules, projects back", () => {
  const k = new Kernel();
  // NCBI NM_000518.5 CDS starts with this prefix.
  const hbbCdsPrefix = "ATGGTGCATCTGACTCCTGAGGAGAAGTCT";
  const bp = makeFieldBlueprint(
    k,
    "dna-sequence-field",
    "sequence",
    "next-previous",
    { index: "integer", symbol: "nucleotide" },
    { index: "nt" },
    "start-end",
  );
  const field = liftSequenceToField(k, "HBB_NM_000518_5_prefix", bp, hbbCdsPrefix);
  assertEq(projectSequence(field), hbbCdsPrefix);

  const start = makeSequenceWindowRule(k, "start-codon", "ATG");
  const glu = makeSequenceWindowRule(k, "glutamate-codon", "GAG");
  const result = fieldStep(k, field, [start, glu], OBSERVER);

  assertEq(result.receipt.candidates.length, 3, "ATG once and GAG twice");
  assertEq(result.field.state.traces.length, 3, "trace count");
  assertEq(result.residual.budgetExhausted, false);

  const changed = intervene(k, field, OBSERVER, [
    { op: "set-site", site: "p19", key: "symbol", value: "T" },
  ]);
  assertEq(projectSequence(changed.field), "ATGGTGCATCTGACTCCTGTGGAGAAGTCT");
  const reversed = reverseReceipt(k, changed);
  assertEq(projectSequence(reversed.field), hbbCdsPrefix);
});

test("chemistry graph field: aspirin graph round-trips and ester grammar fires", () => {
  const k = new Kernel();
  const bp = makeFieldBlueprint(
    k,
    "chemistry-molecular-graph",
    "graph",
    "atom-bond",
    { element: "chemical-element", order: "bond-order" },
    {},
    "molecule",
  );
  // PubChem CID 2244: ConnectivitySMILES CC(=O)OC1=CC=CC=C1C(=O)O, formula C9H8O4.
  const atoms: FieldSite[] = [
    { id: "a0", fiber: { element: "C", role: "acetyl-methyl" } },
    { id: "a1", fiber: { element: "C", role: "acetyl-carbonyl" } },
    { id: "a2", fiber: { element: "O", role: "carbonyl-oxygen" } },
    { id: "a3", fiber: { element: "O", role: "ester-oxygen" } },
    { id: "a4", fiber: { element: "C", role: "ring" } },
    { id: "a5", fiber: { element: "C", role: "ring" } },
    { id: "a6", fiber: { element: "C", role: "ring" } },
    { id: "a7", fiber: { element: "C", role: "ring" } },
    { id: "a8", fiber: { element: "C", role: "ring" } },
    { id: "a9", fiber: { element: "C", role: "ring-carboxyl" } },
    { id: "a10", fiber: { element: "C", role: "carboxyl-carbonyl" } },
    { id: "a11", fiber: { element: "O", role: "carbonyl-oxygen" } },
    { id: "a12", fiber: { element: "O", role: "hydroxyl-oxygen" } },
  ];
  const bonds: FieldEdge[] = [
    { from: "a0", to: "a1", kind: "bond", fiber: { order: 1 } },
    { from: "a1", to: "a2", kind: "bond", fiber: { order: 2 } },
    { from: "a1", to: "a3", kind: "bond", fiber: { order: 1 } },
    { from: "a3", to: "a4", kind: "bond", fiber: { order: 1 } },
    { from: "a4", to: "a5", kind: "bond", fiber: { order: 2 } },
    { from: "a5", to: "a6", kind: "bond", fiber: { order: 1 } },
    { from: "a6", to: "a7", kind: "bond", fiber: { order: 2 } },
    { from: "a7", to: "a8", kind: "bond", fiber: { order: 1 } },
    { from: "a8", to: "a9", kind: "bond", fiber: { order: 2 } },
    { from: "a9", to: "a4", kind: "bond", fiber: { order: 1 } },
    { from: "a9", to: "a10", kind: "bond", fiber: { order: 1 } },
    { from: "a10", to: "a11", kind: "bond", fiber: { order: 2 } },
    { from: "a10", to: "a12", kind: "bond", fiber: { order: 1 } },
  ];
  const field = liftGraphToField(k, "aspirin-cid-2244", bp, atoms, bonds);
  const projected = projectGraph(field);
  assertEq(projected.sites.length, 13);
  assertEq(projected.edges.length, 13);

  const esterRule = makeFieldRule(
    k,
    "ester-site",
    "chemical-subgraph",
    (snapshot) => {
      const matches: FieldMatch[] = [];
      for (const carbon of snapshot.sites.filter((candidate) => candidate.fiber.element === "C")) {
        const carbonBonds = snapshot.edges.filter((candidate) => candidate.from === carbon.id || candidate.to === carbon.id);
        const doubleO = carbonBonds.find((candidate) => Number(candidate.fiber?.order) === 2 && atomElement(snapshot.sites, other(candidate, carbon.id)) === "O");
        const singleO = carbonBonds.find((candidate) => Number(candidate.fiber?.order) === 1 && atomElement(snapshot.sites, other(candidate, carbon.id)) === "O");
        if (!doubleO || !singleO) continue;
        const oxygen = other(singleO, carbon.id);
        const oxygenToCarbon = snapshot.edges.find((candidate) =>
          candidate !== singleO &&
          (candidate.from === oxygen || candidate.to === oxygen) &&
          atomElement(snapshot.sites, other(candidate, oxygen)) === "C"
        );
        if (oxygenToCarbon) {
          matches.push({
            bindings: {
              carbonyl_c: carbon.id,
              carbonyl_o: other(doubleO, carbon.id),
              ester_o: oxygen,
              alkyl_or_aryl_c: other(oxygenToCarbon, oxygen),
            },
          });
        }
      }
      return matches;
    },
    (match) => [
      {
        op: "trace",
        trace: { rule: "ester-site", kind: "chemical-subgraph", bindings: match.bindings },
      },
    ],
    { evidence: "observed", consent: "observe" },
  );
  const result = fieldStep(k, field, [esterRule], OBSERVER);
  assertEq(result.receipt.selected.length, 1);
  assertEq(result.field.state.traces[0]?.bindings.carbonyl_c, "a1");
});

test("bioelectric cell graph: voltage field executes snapshot-relative diffusion", () => {
  const k = new Kernel();
  const bp = makeFieldBlueprint(
    k,
    "bioelectric-cell-graph",
    "cell-graph",
    "gap-junction",
    { voltage_mV: "scalar" },
    { voltage_mV: "mV" },
    "membrane",
  );
  const field = liftGraphToField(
    k,
    "two-cell-vmem",
    bp,
    [
      { id: "cellA", fiber: { voltage_mV: -30 } },
      { id: "cellB", fiber: { voltage_mV: -70 } },
    ],
    [{ from: "cellA", to: "cellB", kind: "gap-junction" }],
  );
  const result = fieldStep(k, field, [
    makeDiffusionRule(k, "vmem-gap-diffusion", "voltage_mV", "gap-junction", 0.25),
  ], OBSERVER);
  assertEq(site(result.field, "cellA").fiber.voltage_mV, -40);
  assertEq(site(result.field, "cellB").fiber.voltage_mV, -60);
});

test("cell signaling graph: Notch/Delta site grammar binds across contact edge", () => {
  const k = new Kernel();
  const bp = makeFieldBlueprint(
    k,
    "cell-signaling-site-graph",
    "cell-graph",
    "contact-sites",
    { notch_receptor: "bool", delta_ligand: "bool" },
  );
  const field = liftGraphToField(
    k,
    "notch-delta-contact",
    bp,
    [
      { id: "sender", fiber: { delta_ligand: true } },
      { id: "receiver", fiber: { notch_receptor: true } },
    ],
    [{ from: "sender", to: "receiver", kind: "contact" }],
  );
  const result = fieldStep(k, field, [
    makeBindingRule(k, "notch-delta-bind", "delta_ligand", "notch_receptor"),
  ], OBSERVER);
  assertEq(site(result.field, "sender").fiber.bound, true);
  assertEq(site(result.field, "receiver").fiber.bound, true);
});

test("plant communication field: volatile signal diffuses with cost receipt", () => {
  const k = new Kernel();
  const bp = makeFieldBlueprint(
    k,
    "plant-voc-field",
    "graph",
    "air-neighborhood",
    { methyl_jasmonate_ppb: "scalar" },
    { methyl_jasmonate_ppb: "ppb" },
  );
  const field = liftGraphToField(
    k,
    "damaged-leaf-neighbor",
    bp,
    [
      { id: "damaged_leaf", fiber: { methyl_jasmonate_ppb: 100 } },
      { id: "neighbor_leaf", fiber: { methyl_jasmonate_ppb: 10 } },
    ],
    [{ from: "damaged_leaf", to: "neighbor_leaf", kind: "air" }],
  );
  const result = fieldStep(k, field, [
    makeDiffusionRule(k, "voc-air-diffusion", "methyl_jasmonate_ppb", "air", 0.1),
  ], OBSERVER);
  assertEq(site(result.field, "damaged_leaf").fiber.methyl_jasmonate_ppb, 91);
  assertEq(site(result.field, "neighbor_leaf").fiber.methyl_jasmonate_ppb, 19);
  assertEq(result.receipt.selected[0]?.cost.disturbance, 1);
});

test("electric field graph: Ohm-law recipe computes current with units", () => {
  const k = new Kernel();
  const bp = makeFieldBlueprint(
    k,
    "electric-circuit-field",
    "graph",
    "node-edge-circuit",
    { voltage_V: "scalar", resistance_ohm: "scalar", current_A: "scalar" },
    { voltage_V: "V", resistance_ohm: "ohm", current_A: "A" },
    "terminals",
  );
  const field = liftGraphToField(
    k,
    "five-volt-one-k-resistor",
    bp,
    [
      { id: "source", fiber: { voltage_V: 5 } },
      { id: "ground", fiber: { voltage_V: 0 } },
    ],
    [{ from: "source", to: "ground", kind: "resistor", fiber: { resistance_ohm: 1000 } }],
  );
  const result = fieldStep(k, field, [makeOhmCurrentRule(k)], OBSERVER);
  assertApprox(Number(edge(result.field, 0).fiber?.current_A), 0.005);
});

test("conversation attention graph: unresolved choice becomes visible receipt", () => {
  const k = new Kernel();
  const bp = makeFieldBlueprint(
    k,
    "conversation-attention-field",
    "attention-graph",
    "reply-choice",
    { unresolved_choice: "bool", choice_visible: "bool" },
  );
  const field = liftGraphToField(
    k,
    "choice-thread",
    bp,
    [
      { id: "ask", fiber: { unresolved_choice: true, text: "which rule fires?" } },
      { id: "reply", fiber: { unresolved_choice: false } },
    ],
    [{ from: "ask", to: "reply", kind: "reply-to" }],
  );
  const exposeChoice = makeFieldRule(
    k,
    "expose-choice",
    "attention-choice",
    (snapshot) =>
      snapshot.sites
        .filter((candidate) => candidate.fiber.unresolved_choice === true)
        .map((candidate) => ({ bindings: { site: candidate.id } })),
    (match) => [
      { op: "set-site", site: String(match.bindings.site), key: "choice_visible", value: true },
      {
        op: "trace",
        trace: { rule: "expose-choice", kind: "choice-receipt", bindings: match.bindings },
      },
    ],
    { evidence: "observed", consent: "observe", cost: { attention: 1, disturbance: 0 } },
  );
  const result = fieldStep(k, field, [exposeChoice], OBSERVER);
  assertEq(site(result.field, "ask").fiber.choice_visible, true);
  assertEq(result.receipt.selected.length, 1);
  assertNodeEq(result.residual.nodeID, result.residual.nodeID, "residual is substrate-resident");
});

function atomElement(sites: readonly FieldSite[], id: string): string | null {
  const atom = sites.find((candidate) => candidate.id === id);
  return typeof atom?.fiber.element === "string" ? atom.fiber.element : null;
}

function other(edge: FieldEdge, id: string): string {
  return edge.from === id ? edge.to : edge.from;
}

if (failed > 0) {
  process.stdout.write(`\n${passed} passed, ${failed} failed\n`);
  process.exit(1);
}

process.stdout.write(`\n${passed} passed, 0 failed\n`);
