// inductive.test.ts — proof-of-shape tests for INDUCTIVE + CHOICE totality.
//
// Run with: npx tsx src/inductive.test.ts
// Exits non-zero on failure.

import { Frame, Kernel, Level, RBasic, Triv, walk, type Value } from "./kernel.ts";
import {
  install_builtin_inductives,
  make_constructor,
  make_inductive,
  match_value,
  nat_of,
  nat_to_int,
  list_cons,
  list_nil,
  list_length,
  constructorNames,
  is_total,
} from "./inductive.ts";

let failures = 0;
let count = 0;

function eq<T>(name: string, actual: T, expected: T): void {
  count++;
  const aj = JSON.stringify(actual);
  const ej = JSON.stringify(expected);
  if (aj === ej) {
    console.log(`  ok  ${name}`);
  } else {
    failures++;
    console.error(`  FAIL ${name}\n    expected: ${ej}\n    actual:   ${aj}`);
  }
}

function ok(name: string, cond: boolean, detail?: string): void {
  count++;
  if (cond) {
    console.log(`  ok  ${name}`);
  } else {
    failures++;
    console.error(`  FAIL ${name}${detail ? "\n    " + detail : ""}`);
  }
}

function raises(name: string, fn: () => void, matchSub?: string): void {
  count++;
  try {
    fn();
    failures++;
    console.error(`  FAIL ${name} (expected to throw)`);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (matchSub !== undefined && !msg.includes(matchSub)) {
      failures++;
      console.error(
        `  FAIL ${name}\n    expected substring: ${matchSub}\n    got message:        ${msg}`,
      );
    } else {
      console.log(`  ok  ${name}  (raised: ${msg})`);
    }
  }
}

// ---------------------------------------------------------------------------

console.log("[test] Nat: build succ(succ(zero)) and walk to 2");
{
  const k = new Kernel();
  const inds = install_builtin_inductives(k);
  const two = nat_of(k, inds, 2);
  const v = walk(k, two, new Frame(null));
  ok("walks to ctor", v.kind === "ctor", `kind=${v.kind}`);
  eq("nat_to_int(2) === 2", nat_to_int(v), 2);

  // Round-trip up to 5
  for (let i = 0; i < 6; i++) {
    const node = nat_of(k, inds, i);
    eq(`nat_to_int(${i})`, nat_to_int(walk(k, node, new Frame(null))), i);
  }
}

console.log("[test] List[int]: cons(1, cons(2, nil)) walks to length 2");
{
  const k = new Kernel();
  const inds = install_builtin_inductives(k);
  const one = k.internTrivialInt(1);
  const two = k.internTrivialInt(2);
  const lst = list_cons(k, inds, one, list_cons(k, inds, two, list_nil(k, inds)));
  const v = walk(k, lst, new Frame(null));
  ok("list walks to ctor", v.kind === "ctor");
  eq("list_length === 2", list_length(v), 2);
}

console.log("[test] Option totality — covering arms");
{
  const k = new Kernel();
  const inds = install_builtin_inductives(k);
  const someFive = make_constructor(k, inds.Option, "some", [
    k.internTrivialInt(5),
  ]);
  const v = walk(k, someFive, new Frame(null));
  const r = match_value(k, v, [
    ["none", () => -1],
    ["some", (args) => (args[0]!.kind === "int" ? args[0]!.int : -1)],
  ]);
  eq("matched some(5)", r, 5);

  // None branch
  const none = make_constructor(k, inds.Option, "none", []);
  const vn = walk(k, none, new Frame(null));
  const rn = match_value(k, vn, [
    ["none", () => -1],
    ["some", () => 0],
  ]);
  eq("matched none", rn, -1);
}

console.log("[test] Option totality — missing arm raises");
{
  const k = new Kernel();
  const inds = install_builtin_inductives(k);
  const someFive = make_constructor(k, inds.Option, "some", [
    k.internTrivialInt(5),
  ]);
  const v = walk(k, someFive, new Frame(null));
  raises(
    "match missing 'none' arm",
    () => {
      match_value(k, v, [["some", (args) => args[0]]]);
    },
    "missing: none",
  );
}

console.log("[test] CHOICE recipe — walker totality check");
{
  const k = new Kernel();
  const inds = install_builtin_inductives(k);
  // Build a CHOICE recipe directly: match Option.some(5) covering only 'some'.
  const some5 = make_constructor(k, inds.Option, "some", [
    k.internTrivialInt(5),
  ]);

  // Arm: bare expression that returns 99 (no binding).
  const ninetyNine = k.internTrivialInt(99);
  const someArmName = k.internString("some");

  const cat: { pkg: number; level: number; type: number; inst: number } = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.CHOICE,
    inst: 1,
  };
  const choice = k.intern(cat, [some5, someArmName, ninetyNine]);

  raises(
    "CHOICE walker rejects missing 'none' arm",
    () => {
      walk(k, choice, new Frame(null));
    },
    "missing constructor",
  );

  // Add the none arm and re-walk — should succeed.
  const noneArmName = k.internString("none");
  const zeroLit = k.internTrivialInt(0);
  const choiceTotal = k.intern(cat, [
    some5,
    someArmName,
    ninetyNine,
    noneArmName,
    zeroLit,
  ]);
  const v = walk(k, choiceTotal, new Frame(null));
  eq("CHOICE returned 99 for 'some' arm", v, { kind: "int", int: 99 } as Value);
}

console.log("[test] Custom inductive — Color := red | green | blue");
{
  const k = new Kernel();
  const Color = make_inductive(k, "Color", [], [
    { ctor_name: "red", ctor_index: 0, arg_types: [] },
    { ctor_name: "green", ctor_index: 1, arg_types: [] },
    { ctor_name: "blue", ctor_index: 2, arg_types: [] },
  ]);
  eq("constructorNames", constructorNames(k, Color), ["red", "green", "blue"]);
  ok("total when all covered", is_total(k, Color, ["red", "green", "blue"]));
  ok("not total when missing blue", !is_total(k, Color, ["red", "green"]));

  // Two structurally-identical Color definitions intern to the same NodeID.
  const Color2 = make_inductive(k, "Color", [], [
    { ctor_name: "red", ctor_index: 0, arg_types: [] },
    { ctor_name: "green", ctor_index: 1, arg_types: [] },
    { ctor_name: "blue", ctor_index: 2, arg_types: [] },
  ]);
  ok(
    "structurally identical Color → same NodeID",
    Color.pkg === Color2.pkg &&
      Color.level === Color2.level &&
      Color.type === Color2.type &&
      Color.inst === Color2.inst,
    `Color=${JSON.stringify(Color)} Color2=${JSON.stringify(Color2)}`,
  );
}

console.log("[test] RBasic / Triv constants");
{
  eq("RBasic.INDUCTIVE", RBasic.INDUCTIVE, 71);
  eq("RBasic.CONSTRUCTOR", RBasic.CONSTRUCTOR, 72);
  eq("RBasic.QUOTIENT (reserved for #19)", RBasic.QUOTIENT, 70);
  eq("Triv.CONSTRUCTOR_TAG", Triv.CONSTRUCTOR_TAG, 15);
}

console.log("");
console.log(`[summary] ${count - failures}/${count} passed`);
if (failures > 0) {
  console.error(`${failures} failure(s)`);
  process.exit(1);
}
