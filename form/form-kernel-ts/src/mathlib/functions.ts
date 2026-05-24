// functions.ts — Function, Injection, Surjection, Bijection.
//
// A Function is a triple (domain, codomain, rule). Injection / Surjection
// / Bijection refine that triple with the corresponding axiom proposition.
//
// The rule is itself a substrate cell — typically a FNDEF NodeID, or an
// alias-string for primitive operations like "identity" or "compose".
//
// Composition of bijections is built constructively: take two bijection
// cells (g: B→C, f: A→B) and return a Bijection (A→C, g∘f) by composing
// the rules and asserting the bijection axiom via a worked proof (see
// proofs.ts).

import { Kernel, Level, RBasic, type NodeID } from "../kernel.ts";
import { make_constructor, make_inductive } from "../inductive.ts";

function ax(k: Kernel, label: string, fn: NodeID): NodeID {
  const head = k.internString(label);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [head, fn],
  );
}

export const FnAxioms = {
  injective: (k: Kernel, fn: NodeID) => ax(k, "injective", fn),
  surjective: (k: Kernel, fn: NodeID) => ax(k, "surjective", fn),
  bijective: (k: Kernel, fn: NodeID) => ax(k, "bijective", fn),
} as const;

function placeholder(k: Kernel, name: string): NodeID {
  return k.internString(name);
}

export interface FunctionCells {
  Function: NodeID;
  Injection: NodeID;
  Surjection: NodeID;
  Bijection: NodeID;
}

export function buildFunctionCells(k: Kernel): FunctionCells {
  const dom_ty = placeholder(k, "domain");
  const cod_ty = placeholder(k, "codomain");
  const rule_ty = placeholder(k, "rule");
  const axiom_ty = placeholder(k, "axiom");

  const Function = make_inductive(k, "Function", [], [
    {
      ctor_name: "mk_function",
      ctor_index: 0,
      arg_types: [dom_ty, cod_ty, rule_ty],
    },
  ]);

  const Injection = make_inductive(k, "Injection", [], [
    {
      ctor_name: "mk_injection",
      ctor_index: 0,
      arg_types: [dom_ty, cod_ty, rule_ty, axiom_ty],
    },
  ]);

  const Surjection = make_inductive(k, "Surjection", [], [
    {
      ctor_name: "mk_surjection",
      ctor_index: 0,
      arg_types: [dom_ty, cod_ty, rule_ty, axiom_ty],
    },
  ]);

  const Bijection = make_inductive(k, "Bijection", [], [
    {
      ctor_name: "mk_bijection",
      ctor_index: 0,
      arg_types: [dom_ty, cod_ty, rule_ty, axiom_ty, axiom_ty, axiom_ty],
    },
  ]);

  return { Function, Injection, Surjection, Bijection };
}

export interface FunctionInstance {
  readonly cell: NodeID;
  readonly domain: NodeID;
  readonly codomain: NodeID;
  readonly rule: NodeID;
}

export function make_function(
  k: Kernel,
  cells: FunctionCells,
  domain: NodeID,
  codomain: NodeID,
  rule: NodeID,
): FunctionInstance {
  const cell = make_constructor(k, cells.Function, "mk_function", [
    domain, codomain, rule,
  ]);
  return { cell, domain, codomain, rule };
}

export function make_injection(
  k: Kernel,
  cells: FunctionCells,
  domain: NodeID,
  codomain: NodeID,
  rule: NodeID,
): FunctionInstance {
  const cell = make_constructor(k, cells.Injection, "mk_injection", [
    domain, codomain, rule,
    FnAxioms.injective(k, rule),
  ]);
  return { cell, domain, codomain, rule };
}

export function make_surjection(
  k: Kernel,
  cells: FunctionCells,
  domain: NodeID,
  codomain: NodeID,
  rule: NodeID,
): FunctionInstance {
  const cell = make_constructor(k, cells.Surjection, "mk_surjection", [
    domain, codomain, rule,
    FnAxioms.surjective(k, rule),
  ]);
  return { cell, domain, codomain, rule };
}

export function make_bijection(
  k: Kernel,
  cells: FunctionCells,
  domain: NodeID,
  codomain: NodeID,
  rule: NodeID,
): FunctionInstance {
  const cell = make_constructor(k, cells.Bijection, "mk_bijection", [
    domain, codomain, rule,
    FnAxioms.injective(k, rule),
    FnAxioms.surjective(k, rule),
    FnAxioms.bijective(k, rule),
  ]);
  return { cell, domain, codomain, rule };
}

// compose_rule — pair two function-rules into a "compose" cell. The
// substrate sees this as `compose(g, f)` regardless of how the JS code got
// here, so g∘f and any other path that produced the same composition share
// a NodeID.
export function compose_rule(
  k: Kernel,
  g: NodeID,
  f: NodeID,
): NodeID {
  const head = k.internString("compose");
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [head, g, f],
  );
}

// compose_bijections — given bijections g: B→C and f: A→B return the
// bijection A→C whose rule is compose(g, f). The bijection axiom on the
// composite is asserted at the recipe layer; proofs.ts builds the
// constructed PROOF for "composition of bijections is bijective".
export function compose_bijections(
  k: Kernel,
  cells: FunctionCells,
  g: FunctionInstance,
  f: FunctionInstance,
): FunctionInstance {
  // f: A→B, g: B→C. Check codomain(f) = domain(g).
  // (Domain/codomain equality is structural here; mismatched call is a
  // programming error, not a math one.)
  if (f.codomain.pkg !== g.domain.pkg ||
      f.codomain.level !== g.domain.level ||
      f.codomain.type !== g.domain.type ||
      f.codomain.inst !== g.domain.inst) {
    throw new Error("compose_bijections: codomain(f) ≠ domain(g)");
  }
  const rule = compose_rule(k, g.rule, f.rule);
  return make_bijection(k, cells, f.domain, g.codomain, rule);
}
