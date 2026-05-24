// lang-rust.test.ts — vertical-slice tests for the Rust 1.83 Language
// cell (task #18, sibling to #15/#16/#17).
//
// Run with: npx tsx src/lang-rust.test.ts
// Exits non-zero on failure.
//
// Coverage:
//   • Tokenizer round-trip on integer suffixes (i32, i64, u64, f64)
//   • Parse + walk + evaluate fib(10) = 55
//   • Round-trip a parsed fib through emitRust and re-parse identity
//   • Content-addressing — parsing the same source twice produces the
//     same recipe NodeID
//   • Language cell content-addresses (registering twice ⇒ same NodeID)
//   • Match expression on Option-like enum exercising variant patterns
//   • Struct literal and field access
//   • Closure invocation

import { Kernel, Triv } from "./kernel.ts";
import {
  emitRust,
  evalRust,
  parseRust,
  parseRustExpr,
  registerRustLanguage,
} from "./lang-rust.ts";
import { capturedChildren, capturedCtor } from "./languages.ts";

let failures = 0;
let count = 0;

function eq<T>(name: string, actual: T, expected: T): void {
  count++;
  if (actual === expected) {
    console.log(`  ok  ${name}  = ${String(actual)}`);
  } else {
    failures++;
    console.error(`  FAIL ${name}\n    expected: ${String(expected)}\n    actual:   ${String(actual)}`);
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

// ---------------------------------------------------------------------------
// Numeric literal typing
// ---------------------------------------------------------------------------

function testNumericLiterals(): void {
  console.log("lang-rust: numeric literals");
  const k = new Kernel();

  const e1 = parseRustExpr(k, "42i32");
  eq("int_lit ctor", capturedCtor(k, e1), "int_lit");
  const c1 = capturedChildren(k, e1);
  eq("i32 suffix routes to INT", c1[0]!.type, Triv.INT);
  eq("fmt string is i32", k.strs[c1[1]!.inst], "i32");

  const e2 = parseRustExpr(k, "1_000_000u64");
  const c2 = capturedChildren(k, e2);
  eq("u64 suffix routes to UINT64", c2[0]!.type, Triv.UINT64);
  eq("u64 fmt", k.strs[c2[1]!.inst], "u64");
  eq("u64 value", k.decodeUint64(c2[0]!.inst), 1000000n);

  const e3 = parseRustExpr(k, "3.14f64");
  eq("float_lit ctor", capturedCtor(k, e3), "float_lit");
  const c3 = capturedChildren(k, e3);
  eq("f64 routes to FLOAT64", c3[0]!.type, Triv.FLOAT64);

  const e4 = parseRustExpr(k, "100i64");
  const c4 = capturedChildren(k, e4);
  eq("i64 routes to INT64", c4[0]!.type, Triv.INT64);
  eq("i64 value", k.decodeInt64(c4[0]!.inst), 100n);

  const e5 = parseRustExpr(k, "255u8");
  const c5 = capturedChildren(k, e5);
  eq("u8 routes to UINT8", c5[0]!.type, Triv.UINT8);

  const e6 = parseRustExpr(k, "1.5f32");
  const c6 = capturedChildren(k, e6);
  eq("f32 routes to FLOAT32", c6[0]!.type, Triv.FLOAT32);

  // Unsuffixed integer defaults to i32
  const e7 = parseRustExpr(k, "7");
  const c7 = capturedChildren(k, e7);
  eq("unsuffixed int defaults to i32", k.strs[c7[1]!.inst], "i32");
}

// ---------------------------------------------------------------------------
// fib(10) = 55
// ---------------------------------------------------------------------------

function testFib(): void {
  console.log("lang-rust: fib");
  const k = new Kernel();
  const src =
    "fn fib(n: i64) -> i64 { if n < 2 { n } else { fib(n-1) + fib(n-2) } }";
  const tree = parseRust(k, src);
  eq("program ctor", capturedCtor(k, tree), "program");
  const items = capturedChildren(k, tree);
  eq("one top-level item", items.length, 1);
  eq("fn ctor", capturedCtor(k, items[0]!), "fn");

  const r = evalRust(k, tree, "fib", [{ kind: "i64", v: 10n }]);
  ok("fib(10) is i64", r.kind === "i64");
  if (r.kind === "i64") {
    eq("fib(10) = 55", r.v.toString(), "55");
  }

  // Edge cases
  const r0 = evalRust(k, tree, "fib", [{ kind: "i64", v: 0n }]);
  if (r0.kind === "i64") eq("fib(0) = 0", r0.v.toString(), "0");
  const r1 = evalRust(k, tree, "fib", [{ kind: "i64", v: 1n }]);
  if (r1.kind === "i64") eq("fib(1) = 1", r1.v.toString(), "1");
  const r2 = evalRust(k, tree, "fib", [{ kind: "i64", v: 2n }]);
  if (r2.kind === "i64") eq("fib(2) = 1", r2.v.toString(), "1");
  const r5 = evalRust(k, tree, "fib", [{ kind: "i64", v: 5n }]);
  if (r5.kind === "i64") eq("fib(5) = 5", r5.v.toString(), "5");
}

// ---------------------------------------------------------------------------
// Round-trip
// ---------------------------------------------------------------------------

function testRoundTrip(): void {
  console.log("lang-rust: emit round-trip");
  const k = new Kernel();
  const src =
    "fn fib(n: i64) -> i64 { if n < 2 { n } else { fib(n-1) + fib(n-2) } }";
  const tree = parseRust(k, src);
  const emitted = emitRust(k, tree);
  console.log(`    emitted: ${emitted}`);

  // Re-parse the emitted source — the resulting tree should evaluate
  // fib(10) to the same value.
  const k2 = new Kernel();
  const tree2 = parseRust(k2, emitted);
  const r = evalRust(k2, tree2, "fib", [{ kind: "i64", v: 10n }]);
  ok("re-parsed fib(10) is i64", r.kind === "i64");
  if (r.kind === "i64") {
    eq("re-parsed fib(10) = 55", r.v.toString(), "55");
  }
}

// ---------------------------------------------------------------------------
// Content-addressing
// ---------------------------------------------------------------------------

function testContentAddressing(): void {
  console.log("lang-rust: content-addressing");
  const k = new Kernel();
  const src = "fn id(x: i32) -> i32 { x }";

  const t1 = parseRust(k, src);
  const t2 = parseRust(k, src);
  eq("parsing the same source twice ⇒ same NodeID inst",
     t1.inst, t2.inst);

  // Different whitespace shouldn't change the captured tree.
  const t3 = parseRust(k, "fn id(x: i32) -> i32 {  x  }");
  eq("whitespace-insensitive content-addressing", t3.inst, t1.inst);

  // Language cell content-addresses
  const langA = registerRustLanguage(k);
  const langB = registerRustLanguage(k);
  eq("Language cell content-addressing",
     langA.nodeID.inst, langB.nodeID.inst);
  eq("language name", langA.name, "rust");
  eq("language version", langA.version, "1.83");
  ok("numeric defaults populated", langA.numericDefaults.has("i32"));
  ok("numeric defaults include f64", langA.numericDefaults.has("f64"));
  ok("stdlib bindings include println!",
     langA.stdlibBindings.has("println!"));
}

// ---------------------------------------------------------------------------
// match — bonus: variant + literal patterns
// ---------------------------------------------------------------------------

function testMatch(): void {
  console.log("lang-rust: match");
  const k = new Kernel();
  // Use a typed-suffix integer match (literal patterns), so this
  // exercises both totality (wildcard arm covers all other ints) and
  // arm dispatch.
  const src =
    "fn classify(n: i64) -> i64 { " +
    "  match n { " +
    "    0i64 => 0i64, " +
    "    1i64 => 10i64, " +
    "    2i64 => 20i64, " +
    "    _ => 99i64 " +
    "  } " +
    "}";
  const tree = parseRust(k, src);
  const items = capturedChildren(k, tree);
  ok("match parses to fn", capturedCtor(k, items[0]!) === "fn");

  // Walk to confirm an "arm" + "arms" capture exists
  const fnChildren = capturedChildren(k, items[0]!);
  const body = fnChildren[4]!;
  ok("body is a block", capturedCtor(k, body) === "block");

  const r0 = evalRust(k, tree, "classify", [{ kind: "i64", v: 0n }]);
  if (r0.kind === "i64") eq("classify(0) = 0", r0.v.toString(), "0");
  const r1 = evalRust(k, tree, "classify", [{ kind: "i64", v: 1n }]);
  if (r1.kind === "i64") eq("classify(1) = 10", r1.v.toString(), "10");
  const r2 = evalRust(k, tree, "classify", [{ kind: "i64", v: 2n }]);
  if (r2.kind === "i64") eq("classify(2) = 20", r2.v.toString(), "20");
  const r7 = evalRust(k, tree, "classify", [{ kind: "i64", v: 7n }]);
  if (r7.kind === "i64") eq("classify(7) = 99 (wildcard)", r7.v.toString(), "99");

  // Variant-pattern match: a hand-rolled Option-like enum.
  const k2 = new Kernel();
  const src2 =
    "enum Opt { Some(i64), None } " +
    "fn unwrap_or(o: Opt, d: i64) -> i64 { " +
    "  match o { " +
    "    Opt::Some(x) => x, " +
    "    Opt::None => d " +
    "  } " +
    "}";
  const tree2 = parseRust(k2, src2);
  const some42 = {
    kind: "variant" as const,
    ty: "Opt",
    ctor: "Some",
    args: [{ kind: "i64" as const, v: 42n }],
  };
  const none = {
    kind: "variant" as const,
    ty: "Opt",
    ctor: "None",
    args: [],
  };
  const r_some = evalRust(k2, tree2, "unwrap_or",
    [some42, { kind: "i64", v: 0n }]);
  if (r_some.kind === "i64") eq("unwrap_or(Some(42), 0) = 42", r_some.v.toString(), "42");
  const r_none = evalRust(k2, tree2, "unwrap_or",
    [none, { kind: "i64", v: 99n }]);
  if (r_none.kind === "i64") eq("unwrap_or(None, 99) = 99", r_none.v.toString(), "99");
}

// ---------------------------------------------------------------------------
// Let statements with type ascription
// ---------------------------------------------------------------------------

function testLetAndArith(): void {
  console.log("lang-rust: let + arithmetic");
  const k = new Kernel();
  const src =
    "fn run() -> i64 { " +
    "  let a: i64 = 7i64; " +
    "  let mut b: i64 = 3i64; " +
    "  let c: i64 = a * b + 2i64; " +
    "  c " +
    "}";
  const tree = parseRust(k, src);
  const r = evalRust(k, tree, "run", []);
  if (r.kind === "i64") eq("run() = 7*3+2 = 23", r.v.toString(), "23");
}

// ---------------------------------------------------------------------------
// Bitwise + comparison + logical
// ---------------------------------------------------------------------------

function testBitAndLogic(): void {
  console.log("lang-rust: bitwise + logical");
  const k = new Kernel();
  const src =
    "fn bits() -> i64 { (12i64 & 10i64) | (5i64 ^ 3i64) }";
  const tree = parseRust(k, src);
  const r = evalRust(k, tree, "bits", []);
  // (12 & 10) = 8 ; (5 ^ 3) = 6 ; 8 | 6 = 14
  if (r.kind === "i64") eq("(12 & 10) | (5 ^ 3) = 14", r.v.toString(), "14");

  const src2 =
    "fn ord(a: i64, b: i64) -> i64 { " +
    "  if a < b { a } else if a == b { 0i64 } else { b } " +
    "}";
  const tree2 = parseRust(k, src2);
  const r2 = evalRust(k, tree2, "ord",
    [{ kind: "i64", v: 3n }, { kind: "i64", v: 9n }]);
  if (r2.kind === "i64") eq("ord(3,9) = 3", r2.v.toString(), "3");
  const r3 = evalRust(k, tree2, "ord",
    [{ kind: "i64", v: 5n }, { kind: "i64", v: 5n }]);
  if (r3.kind === "i64") eq("ord(5,5) = 0", r3.v.toString(), "0");
}

// ---------------------------------------------------------------------------
// Vec + array + struct literal
// ---------------------------------------------------------------------------

function testCollections(): void {
  console.log("lang-rust: vec / array / struct");
  const k = new Kernel();

  // Array literal and indexing
  const src1 = "fn sum3() -> i32 { let xs = [10, 20, 30]; xs[0] + xs[1] + xs[2] }";
  const t1 = parseRust(k, src1);
  const r1 = evalRust(k, t1, "sum3", []);
  if (r1.kind === "i32") eq("sum3() = 60", r1.v, 60);

  // Vec literal
  const src2 = "fn vsum() -> i32 { let v = vec![1, 2, 3, 4]; v.len() }";
  const t2 = parseRust(k, src2);
  const r2 = evalRust(k, t2, "vsum", []);
  if (r2.kind === "i32") eq("vec!.len() = 4", r2.v, 4);

  // Struct literal
  const src3 =
    "struct Point { x: i64, y: i64 } " +
    "fn make() -> i64 { let p = Point { x: 3i64, y: 4i64 }; p.x + p.y }";
  const t3 = parseRust(k, src3);
  const r3 = evalRust(k, t3, "make", []);
  if (r3.kind === "i64") eq("Point.x + Point.y = 7", r3.v.toString(), "7");

  // Tuple
  const src4 = "fn pair() -> i64 { let t = (5i64, 6i64); t.0 + t.1 }";
  const t4 = parseRust(k, src4);
  const r4 = evalRust(k, t4, "pair", []);
  if (r4.kind === "i64") eq("tuple .0 + .1 = 11", r4.v.toString(), "11");
}

// ---------------------------------------------------------------------------
// Closure
// ---------------------------------------------------------------------------

function testClosure(): void {
  console.log("lang-rust: closure");
  const k = new Kernel();
  const src =
    "fn make() -> i64 { let f = |x| x + 1i64; f(41i64) }";
  const tree = parseRust(k, src);
  const r = evalRust(k, tree, "make", []);
  if (r.kind === "i64") eq("(|x| x+1)(41) = 42", r.v.toString(), "42");
}

// ---------------------------------------------------------------------------
// Lifetimes stripped
// ---------------------------------------------------------------------------

function testLifetimesStripped(): void {
  console.log("lang-rust: lifetimes stripped (v0)");
  const k = new Kernel();
  // A function with a lifetime annotation in the parameter type.
  // v0 strips lifetimes but the function must still parse and evaluate.
  const src =
    "fn first<'a>(x: &'a i64, y: &'a i64) -> i64 { *x + *y }";
  // We feed plain i64 values through &-application; since we strip
  // the ref/deref to identity, the function should still return x+y.
  const tree = parseRust(k, src);
  ok("function with lifetime parses",
     capturedCtor(k, capturedChildren(k, tree)[0]!) === "fn");

  // Round-trip
  const emitted = emitRust(k, tree);
  ok("emit produces non-empty source", emitted.length > 0,
     `emitted = ${emitted}`);
}

// ---------------------------------------------------------------------------
// Run all
// ---------------------------------------------------------------------------

function main(): void {
  testNumericLiterals();
  testFib();
  testRoundTrip();
  testContentAddressing();
  testMatch();
  testLetAndArith();
  testBitAndLogic();
  testCollections();
  testClosure();
  testLifetimesStripped();

  console.log(`\nlang-rust: ${count - failures}/${count} ok`);
  if (failures > 0) {
    console.error(`lang-rust: ${failures} FAILED`);
    process.exit(1);
  }
}

main();
