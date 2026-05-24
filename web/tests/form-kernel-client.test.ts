import { describe, expect, it } from "vitest";
import {
  LOCAL_FORM_EXAMPLES,
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
});
