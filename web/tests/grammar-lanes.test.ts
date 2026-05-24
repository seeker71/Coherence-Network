import { describe, expect, it } from "vitest";
import {
  compileActionLanguage,
  compileCrossModalityRecipe,
  compileGrammarBuilder,
  compilePythonToForm,
} from "../lib/form-kernel/grammar-lanes";

describe("grammar lane compilers", () => {
  it("keeps BML action language loadable as Form", () => {
    const out = compileActionLanguage(
      "delegate @concept(lc-trust-over-fear) to @concept(lc-permission-is-interior)",
    );

    expect(out.loadableExpression).toContain("delegate @concept");
    expect(out.steps).toContain("verb: delegate");
  });

  it("turns a Python function into a method-shaped recipe skeleton", () => {
    const out = compilePythonToForm(`def add_one(x):
    return x + 1`);

    expect(out.form).toContain("method add_one");
    expect(out.form).toContain("let x = .arg0;");
    expect(out.form).toContain("x + 1");
  });

  it("builds a grammar rule with captures and semantic action", () => {
    const out = compileGrammarBuilder(
      "when {trigger} appears, offer {practice}",
      "trigger, practice",
      "emit teaching_recipe(trigger, practice)",
    );

    expect(out.form).toContain('pattern "when {trigger} appears, offer {practice}"');
    expect(out.form).toContain("capture trigger as @field(trigger)");
    expect(out.form).toContain("emit teaching_recipe(trigger, practice)");
  });

  it("extracts cross-modal recipe channels by recipe kind", () => {
    const out = compileCrossModalityRecipe("Name the claim, run the proof.", "verification recipe");

    expect(out.form).toContain('"verification recipe"');
    expect(out.form).toContain('"claim"');
    expect(out.form).toContain("verify embodied_transfer");
  });
});
