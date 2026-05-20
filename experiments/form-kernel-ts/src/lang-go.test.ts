// lang-go.test.ts — sibling-shaped standalone test for the Go Language cell.
//
// Run:    npx tsx src/lang-go.test.ts
// Passes: exit 0 + "lang-go: all tests passed" on stdout.
// Fails:  throws an AssertionError, exit 1.
//
// Matches the smoke-test rhythm of lang-python / lang-ts / lang-rust:
// content-addressing, parse round-trip, walker evaluation, stdlib bindings.

import { Frame, Kernel, walk, type Value } from "./kernel.ts";
import {
  createGoLanguage,
  emitGo,
  formatForGoType,
  goTypeForFormat,
  parseGo,
  RFormat,
} from "./lang-go.ts";

let passed = 0;
let failed = 0;

function assert(cond: unknown, msg: string): void {
  if (cond) {
    passed++;
  } else {
    failed++;
    console.error(`  ✗ ${msg}`);
  }
}

function assertEq<T>(actual: T, expected: T, msg: string): void {
  if (actual === expected) {
    passed++;
  } else {
    failed++;
    console.error(
      `  ✗ ${msg}\n    expected: ${JSON.stringify(expected)}\n    actual:   ${JSON.stringify(actual)}`,
    );
  }
}

function valueInt(v: Value): number {
  if (v.kind !== "int") throw new Error(`expected int, got ${v.kind}`);
  return v.int;
}

// ---------------------------------------------------------------------------
// 1. Language cell descriptor — content-addressing of the cell itself.
// ---------------------------------------------------------------------------

{
  const k1 = new Kernel();
  const k2 = new Kernel();
  const c1 = createGoLanguage(k1);
  const c2 = createGoLanguage(k1);
  const c3 = createGoLanguage(k2);

  assertEq(c1.id, "lang.go", "cell id");
  assertEq(c1.version, "1.23", "cell version");
  assertEq(
    c1.nodeId.inst,
    c2.nodeId.inst,
    "two cells in the same kernel share a NodeID inst (content-addressed)",
  );
  // Different kernels have independent intern tables; the NodeID *shape*
  // (level/type) matches even though inst counters differ.
  assertEq(c1.nodeId.level, c3.nodeId.level, "cell level matches across kernels");
  assertEq(c1.nodeId.type, c3.nodeId.type, "cell type matches across kernels");

  const bindings = c1.bindings();
  assert(bindings.includes("len"), "stdlib binding: len");
  assert(bindings.includes("make"), "stdlib binding: make");
  assert(bindings.includes("append"), "stdlib binding: append");
  assert(bindings.includes("cap"), "stdlib binding: cap");
  assert(bindings.includes("fmt.Println"), "stdlib binding: fmt.Println");
  assert(bindings.includes("string"), "stdlib binding: string");
}

// ---------------------------------------------------------------------------
// 2. Format-recipe mapping.
// ---------------------------------------------------------------------------

{
  assertEq(formatForGoType("int"), RFormat.INT64, "int → INT64 (canonical cross-language)");
  assertEq(formatForGoType("int64"), RFormat.INT64, "int64 → INT64");
  assertEq(formatForGoType("int32"), RFormat.INT32, "int32 → INT32");
  assertEq(formatForGoType("uint32"), RFormat.UINT32, "uint32 → UINT32");
  assertEq(formatForGoType("float64"), RFormat.FP64, "float64 → FP64");
  assertEq(formatForGoType("byte"), RFormat.UINT8, "byte → UINT8");
  assertEq(formatForGoType("rune"), RFormat.INT32, "rune → INT32");
  assertEq(goTypeForFormat(RFormat.INT64), "int64", "INT64 → int64");
  assertEq(goTypeForFormat(RFormat.FP64), "float64", "FP64 → float64");
}

// ---------------------------------------------------------------------------
// 3. Content-addressing: same source twice → same NodeID.
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  createGoLanguage(k);
  const src = `func fib(n int64) int64 { if n < 2 { return n }; return fib(n-1) + fib(n-2) }`;
  const a = parseGo(k, src);
  const b = parseGo(k, src);
  assertEq(a.inst, b.inst, "parse(src) twice → same NodeID.inst");
  assertEq(a.level, b.level, "parse(src) twice → same level");
  assertEq(a.type, b.type, "parse(src) twice → same type");
}

// ---------------------------------------------------------------------------
// 4. Parse + walk: fib(10) = 55.
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  createGoLanguage(k);
  const src = `
    func fib(n int64) int64 {
      if n < 2 {
        return n
      }
      return fib(n-1) + fib(n-2)
    }
  `;
  const node = parseGo(k, src);
  const frame = new Frame(null);
  // Walk the FNDEF so the closure is bound into the frame.
  walk(k, node, frame);

  // Now invoke fib(10) by constructing an explicit call recipe through the
  // surface parser — same kernel, same frame, same NodeIDs.
  const callNode = parseGo(k, `fib(10)`);
  const result = walk(k, callNode, frame);
  assertEq(valueInt(result), 55, "fib(10) = 55 via parse + walk");

  // Sanity checks for adjacent values.
  const five = walk(k, parseGo(k, `fib(5)`), frame);
  assertEq(valueInt(five), 5, "fib(5) = 5");
  const seven = walk(k, parseGo(k, `fib(7)`), frame);
  assertEq(valueInt(seven), 13, "fib(7) = 13");
}

// ---------------------------------------------------------------------------
// 5. Emission template round-trips Go source — emit(parse(src)) parses back
//    to the same NodeID. (Textual equality is too brittle for whitespace;
//    NodeID equality is the structural contract.)
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  createGoLanguage(k);
  const src = `func add(a int64, b int64) int64 { return a + b }`;
  const a = parseGo(k, src);
  const emitted = emitGo(k, a);
  const b = parseGo(k, emitted);
  assertEq(a.inst, b.inst, "emit ∘ parse round-trips to same NodeID for func+return");

  // Round-trip a sequence containing if-else, var, and a call.
  const src2 = `
    func clamp(x int64, lo int64) int64 {
      if x < lo {
        return lo
      } else {
        return x
      }
    }
  `;
  const c = parseGo(k, src2);
  const emitted2 = emitGo(k, c);
  const d = parseGo(k, emitted2);
  assertEq(c.inst, d.inst, "emit ∘ parse round-trips if-else");
}

// ---------------------------------------------------------------------------
// 6. var x int = v   /   x := v   — both produce a LET recipe.
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  createGoLanguage(k);
  const a = parseGo(k, `var x int = 7\nx`);
  const b = parseGo(k, `x := 7\nx`);
  // Both bind the same name to the same value, so walking yields the same int.
  const f1 = new Frame(null);
  const f2 = new Frame(null);
  const r1 = walk(k, a, f1);
  const r2 = walk(k, b, f2);
  assertEq(valueInt(r1), 7, "var x int = 7 evaluates to 7");
  assertEq(valueInt(r2), 7, "x := 7 evaluates to 7");
}

// ---------------------------------------------------------------------------
// 7. Slice literal + len.
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  createGoLanguage(k);
  const src = `len([]int64{1, 2, 3, 4, 5})`;
  const node = parseGo(k, src);
  const result = walk(k, node, new Frame(null));
  assertEq(valueInt(result), 5, "len([]int64{1,2,3,4,5}) = 5");
}

// ---------------------------------------------------------------------------
// 8. append + cap.
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  createGoLanguage(k);
  const node = parseGo(k, `cap(append([]int64{1, 2}, 3))`);
  const result = walk(k, node, new Frame(null));
  assertEq(valueInt(result), 3, "cap(append([]int64{1,2}, 3)) = 3");
}

// ---------------------------------------------------------------------------
// 9. Boolean / comparison.
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  createGoLanguage(k);
  const r1 = walk(k, parseGo(k, `1 < 2 && 3 == 3`), new Frame(null));
  assertEq(r1.kind, "bool", "comparison result kind");
  assertEq((r1 as { bool: boolean }).bool, true, "1 < 2 && 3 == 3");
  const r2 = walk(k, parseGo(k, `!(1 == 2)`), new Frame(null));
  assertEq((r2 as { bool: boolean }).bool, true, "!(1 == 2)");
}

// ---------------------------------------------------------------------------
// 10. Struct literal round-trip (no evaluation — emitter shape only).
// ---------------------------------------------------------------------------

{
  const k = new Kernel();
  createGoLanguage(k);
  const src = `func mk() int64 { return Point{X: 3, Y: 4}.X }`;
  // The walker doesn't evaluate struct field access yet (deferred); but the
  // parse → emit → parse cycle must structurally close.
  const a = parseGo(k, src);
  const emitted = emitGo(k, a);
  const b = parseGo(k, emitted);
  assertEq(a.inst, b.inst, "struct literal round-trips structurally");
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

if (failed > 0) {
  console.error(`\nlang-go: ${failed} test(s) failed, ${passed} passed`);
  process.exit(1);
}
console.log(`lang-go: all tests passed (${passed} assertions)`);
