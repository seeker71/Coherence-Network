// proof.test.ts — vertical tests for PROOF + INFERENCE.
//
// Run: tsx src/proof.test.ts
//
// No external test framework — standalone runner that prints PASS/FAIL.
// Exits non-zero on any failure so CI can gate on the same script.

import { Kernel, Level, RBasic, Triv, nodeKey, type NodeID } from "./kernel.ts";
import {
  Prop,
  apply,
  axiom,
  builtinRules,
  hole,
  makeInferenceRule,
  makeProof,
  proofOf,
  valid,
} from "./proof.ts";

let passed = 0;
let failed = 0;

function check(name: string, ok: boolean, detail?: string): void {
  if (ok) {
    passed++;
    process.stdout.write(`  PASS  ${name}\n`);
  } else {
    failed++;
    process.stdout.write(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}\n`);
  }
}

function header(name: string): void {
  process.stdout.write(`\n${name}\n`);
}

// ---------------------------------------------------------------------------
// Helpers: atomic propositions = string-trivial labels ("P", "Q", "R", ...).
// They're regular substrate cells; the proof machinery doesn't care about
// their internal shape.
// ---------------------------------------------------------------------------

function atom(k: Kernel, name: string): NodeID {
  return k.internString(name);
}

// ---------------------------------------------------------------------------
// Test 1 — P → Q, P ⊢ Q via modus ponens
// ---------------------------------------------------------------------------

header("Test 1: modus ponens (P → Q, P ⊢ Q)");
{
  const k = new Kernel();
  const rules = builtinRules(k);
  const P = atom(k, "P");
  const Q = atom(k, "Q");
  const PimpliesQ = Prop.implies(k, P, Q);

  const proofPimpliesQ = axiom(k, PimpliesQ);
  const proofP = axiom(k, P);
  const proofQ = apply(k, rules.modusPonens, [proofPimpliesQ, proofP]);

  check("modus ponens yields a proof", proofQ !== null);
  if (proofQ) {
    check(
      "concluded proposition is Q",
      nodeKey(proofOf(k, proofQ)) === nodeKey(Q),
    );
    check("proof is valid", valid(k, proofQ));
  }
}

// ---------------------------------------------------------------------------
// Test 2 — proof irrelevance: same proof shape → same NodeID
// ---------------------------------------------------------------------------

header("Test 2: proof irrelevance via content-addressing");
{
  const k = new Kernel();
  const rules = builtinRules(k);
  const P = atom(k, "P");
  const Q = atom(k, "Q");
  const PimpliesQ = Prop.implies(k, P, Q);

  const a1 = axiom(k, PimpliesQ);
  const a2 = axiom(k, P);
  const proofA = apply(k, rules.modusPonens, [a1, a2])!;

  // Independently constructed second proof of Q with the same shape.
  const b1 = axiom(k, PimpliesQ);
  const b2 = axiom(k, P);
  const proofB = apply(k, rules.modusPonens, [b1, b2])!;

  check(
    "two structurally identical proofs share NodeID",
    nodeKey(proofA.node) === nodeKey(proofB.node),
  );
  check(
    "axiom of P interns once",
    nodeKey(a1.node) !== nodeKey(a2.node) &&
      nodeKey(a2.node) === nodeKey(b2.node),
  );
}

// ---------------------------------------------------------------------------
// Test 3 — and-intro / and-elim round trip
// ---------------------------------------------------------------------------

header("Test 3: and-intro and and-elim round trip");
{
  const k = new Kernel();
  const rules = builtinRules(k);
  const P = atom(k, "P");
  const Q = atom(k, "Q");

  const proofP = axiom(k, P);
  const proofQ = axiom(k, Q);
  const proofPandQ = apply(k, rules.andIntro, [proofP, proofQ])!;
  check(
    "and-intro: ⊢ P ∧ Q",
    nodeKey(proofPandQ.proposition) === nodeKey(Prop.and(k, P, Q)),
  );

  const reExtractedP = apply(k, rules.andElim1, [proofPandQ])!;
  const reExtractedQ = apply(k, rules.andElim2, [proofPandQ])!;
  check("and-elim-1 yields P", nodeKey(reExtractedP.proposition) === nodeKey(P));
  check("and-elim-2 yields Q", nodeKey(reExtractedQ.proposition) === nodeKey(Q));
  check("nested proof valid", valid(k, reExtractedP));
}

// ---------------------------------------------------------------------------
// Test 4 — valid() rejects malformed proofs
// ---------------------------------------------------------------------------

header("Test 4: valid() rejects malformed proofs");
{
  const k = new Kernel();
  const rules = builtinRules(k);
  const P = atom(k, "P");
  const Q = atom(k, "Q");
  const R = atom(k, "R");
  const PimpliesQ = Prop.implies(k, P, Q);

  // (a) Mismatched conclusion — claim to prove R via modus ponens of
  //     P→Q and P. Construction would be valid for Q, not R.
  const construction = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.INFERENCE, inst: 0 },
    [rules.modusPonens.node, axiom(k, PimpliesQ).node, axiom(k, P).node],
  );
  const fakeProof = makeProof(k, R, construction);
  check("rejects proof with wrong conclusion", valid(k, fakeProof) === false);

  // (b) Wrong premise — claim modus ponens with two non-implication axioms.
  const bad1 = axiom(k, P);
  const bad2 = axiom(k, Q);
  const bogus = apply(k, rules.modusPonens, [bad1, bad2]);
  check("apply returns null on premise shape mismatch", bogus === null);

  // (c) Arity mismatch
  const arity = apply(k, rules.modusPonens, [axiom(k, P)]);
  check("apply returns null on arity mismatch", arity === null);
}

// ---------------------------------------------------------------------------
// Test 5 — proof of `Nat.succ(Nat.zero) : Nat` by constructor introduction
//
// Models the INDUCTIVE cross-composition without depending on the sister
// file: encodes Nat constructors as plain recipes and uses an inference rule
// "nat-succ-intro" (n : Nat ⊢ succ(n) : Nat) and an axiom "nat-zero-intro"
// (⊢ zero : Nat). Demonstrates the same shape #21's INDUCTIVE would
// produce — when inductive.ts arrives, its constructor cells slot in as the
// proposition recipes here.
// ---------------------------------------------------------------------------

header("Test 5: ⊢ succ(zero) : Nat by constructor introduction");
{
  const k = new Kernel();

  // Proposition shape: "x : Nat" encoded as FNCALL(":", x, Nat)
  const colon = k.internString(":");
  const Nat = k.internString("Nat");
  const fncall = (head: NodeID, ...args: NodeID[]): NodeID =>
    k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
      [head, ...args],
    );
  const hasType = (term: NodeID): NodeID => fncall(colon, term, Nat);

  const zero = fncall(k.internString("zero"));
  const succ = (n: NodeID): NodeID => fncall(k.internString("succ"), n);

  // Axiom: ⊢ zero : Nat
  const zeroIsNat = axiom(k, hasType(zero));
  check("zero axiom valid", valid(k, zeroIsNat));

  // Rule: n : Nat ⊢ succ(n) : Nat
  const n = hole(k, "n");
  const succRule = makeInferenceRule(
    k,
    "nat-succ-intro",
    [hasType(n)],
    hasType(succ(n)),
  );

  const succZeroIsNat = apply(k, succRule, [zeroIsNat])!;
  check("succ(zero) : Nat proof exists", succZeroIsNat !== null);
  check(
    "concluded proposition is succ(zero) : Nat",
    nodeKey(succZeroIsNat.proposition) === nodeKey(hasType(succ(zero))),
  );
  check("succ-intro proof valid", valid(k, succZeroIsNat));
}

// ---------------------------------------------------------------------------
// Test 6 — kernel additions: PROOF=73, INFERENCE=74 reserved
// ---------------------------------------------------------------------------

header("Test 6: kernel additions (additive only)");
{
  check("RBasic.PROOF = 73", RBasic.PROOF === 73);
  check("RBasic.INFERENCE = 74", RBasic.INFERENCE === 74);

  // Trivial sanity — existing arms untouched.
  check("RBasic.BLOCK = 9", RBasic.BLOCK === 9);
  check("RBasic.FNDEF = 31", RBasic.FNDEF === 31);
  check("RBasic.LIST = 34", RBasic.LIST === 34);
  check("Level.BASIC = 2", Level.BASIC === 2);
  check("Triv.STRING = 2", Triv.STRING === 2);
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

process.stdout.write(`\n${passed} passed, ${failed} failed\n`);
process.exit(failed > 0 ? 1 : 0);
