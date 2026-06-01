import { describe, expect, it } from "vitest";
import {
  LOCAL_FIELD_RUNTIME_PROOF,
  LOCAL_FORM_EXAMPLES,
  LOCAL_FORM_PROOF_MARKERS,
  runLocalFormBinary,
} from "../lib/form-kernel/client";

describe("browser-facing Form kernel", () => {
  it("runs a text-encoded .fk binary locally", () => {
    const run = runLocalFormBinary("(add 1 (mul 2 3))");

    expect(run.result).toBe("7");
    expect(run.root).toMatch(/^@1\./);
    expect(run.trace.total_walks).toBeGreaterThan(0);
  });

  it("keeps recursive recipes executable in the embedded TS kernel", () => {
    const run = runLocalFormBinary(LOCAL_FORM_EXAMPLES[1].source);

    expect(run.result).toBe("40320");
    expect(run.trace.total_walks).toBeGreaterThan(10);
  });

  it("publishes the browser FMF runtime proof marker", () => {
    expect(LOCAL_FIELD_RUNTIME_PROOF.marker).toBe("field-model-form-browser-runtime-proof:4");
    expect(LOCAL_FIELD_RUNTIME_PROOF.score).toBe(4);
    expect(LOCAL_FIELD_RUNTIME_PROOF.checks).toContain("intervene-reverseReceipt");
    expect(LOCAL_FORM_PROOF_MARKERS).toContain(LOCAL_FIELD_RUNTIME_PROOF.marker);
    expect(LOCAL_FORM_PROOF_MARKERS).toContain("field-model-form-bml-runtime-proof:63");
  });
});
