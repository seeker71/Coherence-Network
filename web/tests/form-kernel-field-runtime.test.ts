import { describe, expect, it } from "vitest";

import { Kernel } from "../lib/form-kernel/vendor/kernel.ts";
import {
  fieldStep,
  intervene,
  liftGraphToField,
  liftSequenceToField,
  makeDiffusionRule,
  makeFieldBlueprint,
  makeFieldRule,
  makeOhmCurrentRule,
  makeSequenceWindowRule,
  projectSequence,
  reverseReceipt,
  type FieldCell,
  type FieldSite,
} from "../lib/form-kernel/field-runtime";

const OBSERVER = { name: "browser-fmf-observer", policy: "all-compatible" as const };

function site(field: FieldCell, id: string): FieldSite {
  const found = field.state.sites.find((candidate) => candidate.id === id);
  if (!found) throw new Error(`missing site ${id}`);
  return found;
}

describe("browser Field Model Form runtime", () => {
  it("executes DNA sequence field recipes forward and reverses intervention receipts", () => {
    const k = new Kernel();
    const bp = makeFieldBlueprint(
      k,
      "dna-sequence-field",
      "sequence",
      "next-previous",
      { index: "integer", symbol: "nucleotide" },
      { index: "nt" },
      "start-end",
    );
    const hbbCdsPrefix = "ATGGTGCATCTGACTCCTGAGGAGAAGTCT";
    const field = liftSequenceToField(k, "HBB_NM_000518_5_prefix", bp, hbbCdsPrefix);

    expect(projectSequence(field)).toBe(hbbCdsPrefix);

    const result = fieldStep(k, field, [
      makeSequenceWindowRule(k, "start-codon", "ATG"),
      makeSequenceWindowRule(k, "glutamate-codon", "GAG"),
    ], OBSERVER);

    expect(result.receipt.candidates).toHaveLength(3);
    expect(result.field.state.traces.map((trace) => trace.rule)).toEqual([
      "start-codon",
      "glutamate-codon",
      "glutamate-codon",
    ]);
    expect(result.residual.budgetExhausted).toBe(false);

    const changed = intervene(k, field, OBSERVER, [
      { op: "set-site", site: "p19", key: "symbol", value: "T" },
    ]);
    expect(projectSequence(changed.field)).toBe("ATGGTGCATCTGACTCCTGTGGAGAAGTCT");
    expect(projectSequence(reverseReceipt(k, changed).field)).toBe(hbbCdsPrefix);
  });

  it("executes graph-field laws with unit-carrying receipts", () => {
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

    expect(result.field.state.edges[0]?.fiber?.current_A).toBeCloseTo(0.005);
    expect(result.receipt.selected[0]?.rule.evidence).toBe("validated");
  });

  it("keeps simultaneous execution snapshot-relative and exposes conflicts as residuals", () => {
    const k = new Kernel();
    const bp = makeFieldBlueprint(
      k,
      "bioelectric-cell-graph",
      "cell-graph",
      "gap-junction",
      { voltage_mV: "scalar", label: "string" },
      { voltage_mV: "mV" },
      "membrane",
    );
    const field = liftGraphToField(
      k,
      "two-cell-vmem",
      bp,
      [
        { id: "cellA", fiber: { voltage_mV: -30, label: "quiet" } },
        { id: "cellB", fiber: { voltage_mV: -70 } },
      ],
      [{ from: "cellA", to: "cellB", kind: "gap-junction" }],
    );

    const diffused = fieldStep(k, field, [
      makeDiffusionRule(k, "vmem-gap-diffusion", "voltage_mV", "gap-junction", 0.25),
    ], OBSERVER);

    expect(site(diffused.field, "cellA").fiber.voltage_mV).toBe(-40);
    expect(site(diffused.field, "cellB").fiber.voltage_mV).toBe(-60);

    const markHot = makeFieldRule(
      k,
      "mark-hot",
      "conflict-demo",
      () => [{ bindings: { site: "cellA" } }],
      () => [{ op: "set-site", site: "cellA", key: "label", value: "hot" }],
    );
    const markCool = makeFieldRule(
      k,
      "mark-cool",
      "conflict-demo",
      () => [{ bindings: { site: "cellA" } }],
      () => [{ op: "set-site", site: "cellA", key: "label", value: "cool" }],
    );

    const conflicted = fieldStep(k, field, [markHot, markCool], OBSERVER);

    expect(site(conflicted.field, "cellA").fiber.label).toBe("hot");
    expect(conflicted.receipt.conflicts).toEqual(["conflict:site:cellA:label"]);
    expect(conflicted.residual.conflicts).toEqual(["conflict:site:cellA:label"]);
  });
});
