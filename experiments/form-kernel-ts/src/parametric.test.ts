// Tests for parametric format-recipes + strict-typed FNDEF + alias.
//
// Standalone runnable via `tsx src/parametric.test.ts`. Each `test(...)`
// throws on failure; first failure aborts the run. Designed to live next
// to the existing kernel files until the experiment grows a real harness.

import { Kernel, Level, RBasic, Triv, type NodeID } from "./kernel.ts";
import { readAll, readForm } from "./reader.ts";
import {
  makeAlias,
  parameterizedFnDef,
  readFnDef,
  registerAliasFromRecipe,
  resolveAlias,
  specializeFnDef,
} from "./parametric.ts";

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

function assertNodeEq(a: NodeID, b: NodeID, msg = ""): void {
  if (a.pkg !== b.pkg || a.level !== b.level || a.type !== b.type || a.inst !== b.inst) {
    throw new Error(
      `${msg ? msg + ": " : ""}nodes differ ${JSON.stringify(a)} vs ${JSON.stringify(b)}`,
    );
  }
}

// ---------------------------------------------------------------------------
// 1. Reader parses parametric defn with type-parameter metadata
// ---------------------------------------------------------------------------

test("reader: parametric defn with [T:Format] and per-arg types", () => {
  const k = new Kernel();
  const node = readForm(
    k,
    "(defn add_t :tparams (T:Format) (a:T b:T) :ret T (add a b))",
  );
  const cat = k.category(node);
  assertEq(cat.type, RBasic.FNDEF, "category type");
  assertEq(cat.inst, 2, "inst=2 marks typed shape");

  const shape = readFnDef(k, node);
  assertEq(shape.name, "add_t");
  assertEq(shape.typeParams.length, 1);
  assertEq(shape.typeParams[0]!.name, "T");
  assertEq(shape.typeParams[0]!.constraint, "Format");
  assertEq(shape.params.length, 2);
  assertEq(shape.params[0]!.name, "a");
  assertEq(shape.params[0]!.type, "T");
  assertEq(shape.params[1]!.name, "b");
  assertEq(shape.params[1]!.type, "T");
  assertEq(shape.returnType, "T");
});

// ---------------------------------------------------------------------------
// 2. specializeFnDef with T=f64 produces an f64-typed FNDEF
// ---------------------------------------------------------------------------

test("specialize: T=f64 ⇒ f64-typed params and return", () => {
  const k = new Kernel();
  const generic = readForm(
    k,
    "(defn add_t :tparams (T:Format) (a:T b:T) :ret T (add a b))",
  );
  const specialized = specializeFnDef(k, generic, { T: "f64" });
  const shape = readFnDef(k, specialized);
  assertEq(shape.typeParams.length, 0, "type params consumed");
  assertEq(shape.params[0]!.type, "f64");
  assertEq(shape.params[1]!.type, "f64");
  assertEq(shape.returnType, "f64");
});

// ---------------------------------------------------------------------------
// 3. specializeFnDef with T=i32
// ---------------------------------------------------------------------------

test("specialize: T=i32 ⇒ i32-typed params and return", () => {
  const k = new Kernel();
  const generic = parameterizedFnDef(
    k,
    "mul_t",
    [{ name: "T", constraint: "Format" }],
    [
      { name: "a", type: "T" },
      { name: "b", type: "T" },
    ],
    readForm(k, "(mul a b)"),
    "T",
  );
  const specialized = specializeFnDef(k, generic, { T: "i32" });
  const shape = readFnDef(k, specialized);
  assertEq(shape.params[0]!.type, "i32");
  assertEq(shape.params[1]!.type, "i32");
  assertEq(shape.returnType, "i32");
});

// ---------------------------------------------------------------------------
// 4. Alias: read + resolveAlias returns target NodeID
// ---------------------------------------------------------------------------

test("alias: WIDTH = 8 ⇒ resolveAlias returns the integer NodeID", () => {
  const k = new Kernel();
  const program = readAll(k, "(alias WIDTH 8)");
  // The top-level was a single form (program === alias node).
  registerAliasFromRecipe(k, program);
  const resolved = resolveAlias(k, "WIDTH");
  if (resolved === undefined) throw new Error("WIDTH did not resolve");
  assertEq(resolved.level, Level.TRIVIAL);
  assertEq(resolved.type, Triv.INT);
  assertEq(resolved.inst, 8);
});

test("alias: makeAlias() round-trips via resolveAlias()", () => {
  const k = new Kernel();
  const target = k.internTrivialInt(42);
  makeAlias(k, "ANSWER", target);
  const resolved = resolveAlias(k, "ANSWER");
  if (resolved === undefined) throw new Error("ANSWER did not resolve");
  assertNodeEq(resolved, target, "round-trip");
});

// ---------------------------------------------------------------------------
// 5. Content-addressing: same parametric definition ⇒ same NodeID
// ---------------------------------------------------------------------------

test("content-addressing: same parametric defn ⇒ same NodeID", () => {
  const k = new Kernel();
  const a = readForm(
    k,
    "(defn f :tparams (T:Format) (x:T) :ret T (add x x))",
  );
  const b = readForm(
    k,
    "(defn f :tparams (T:Format) (x:T) :ret T (add x x))",
  );
  assertNodeEq(a, b, "structural identity");
});

test("content-addressing: parameterizedFnDef and reader produce same NodeID", () => {
  const k = new Kernel();
  const fromReader = readForm(
    k,
    "(defn g :tparams (T:Format) (x:T) :ret T (add x x))",
  );
  const fromBuilder = parameterizedFnDef(
    k,
    "g",
    [{ name: "T", constraint: "Format" }],
    [{ name: "x", type: "T" }],
    readForm(k, "(add x x)"),
    "T",
  );
  assertNodeEq(fromReader, fromBuilder, "reader matches builder");
});

// ---------------------------------------------------------------------------
// 6. Back-compat: untyped defn parses identically to before
// ---------------------------------------------------------------------------

test("back-compat: (defn foo (a) a) still parses as inst=1", () => {
  const k = new Kernel();
  const node = readForm(k, "(defn foo (a) a)");
  const cat = k.category(node);
  assertEq(cat.type, RBasic.FNDEF);
  assertEq(cat.inst, 1, "untyped FNDEF stays at inst=1");
  const kids = k.children(node);
  assertEq(kids.length, 3, "3 children for back-compat shape");

  const shape = readFnDef(k, node);
  assertEq(shape.name, "foo");
  assertEq(shape.typeParams.length, 0);
  assertEq(shape.params.length, 1);
  assertEq(shape.params[0]!.name, "a");
  assertEq(shape.params[0]!.type, null);
  assertEq(shape.returnType, null);
});

test("back-compat: untyped multi-arg defn unchanged", () => {
  const k = new Kernel();
  const node = readForm(k, "(defn add2 (a b) (add a b))");
  const cat = k.category(node);
  assertEq(cat.inst, 1);
  const shape = readFnDef(k, node);
  assertEq(shape.params.map((p) => p.name).join(","), "a,b");
  assertEq(shape.params.every((p) => p.type === null), true);
});

// ---------------------------------------------------------------------------
// 7. Strict-typed (no type-params) FNDEF
// ---------------------------------------------------------------------------

test("strict-typed: (defn foo (a:i32 b:i32) :ret i32 (add a b))", () => {
  const k = new Kernel();
  const node = readForm(k, "(defn foo (a:i32 b:i32) :ret i32 (add a b))");
  const cat = k.category(node);
  assertEq(cat.inst, 2, "typed FNDEF uses inst=2");
  const shape = readFnDef(k, node);
  assertEq(shape.typeParams.length, 0);
  assertEq(shape.params[0]!.type, "i32");
  assertEq(shape.params[1]!.type, "i32");
  assertEq(shape.returnType, "i32");
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

process.stdout.write(`\nparametric: ${passed} passed, ${failed} failed\n`);
if (failed > 0) process.exit(1);
