// lang-python.test.ts — proof-of-shape tests for the Python Language cell.
//
// Run with: npx tsx src/lang-python.test.ts
// Exits non-zero on failure.

import { Kernel, nodeKey } from "./kernel.ts";
import {
  CTOR,
  buildPythonLanguage,
  emitPython,
  evalPython,
  parsePython,
} from "./lang-python.ts";
import { capturedChildren, capturedCtor } from "./languages.ts";

let failures = 0;
let count = 0;

function eq<T>(name: string, actual: T, expected: T): void {
  count++;
  const aj = JSON.stringify(actual, bigintReplacer);
  const ej = JSON.stringify(expected, bigintReplacer);
  if (aj === ej) {
    console.log(`  ok  ${name}`);
  } else {
    failures++;
    console.log(`  FAIL ${name}`);
    console.log(`       expected: ${ej}`);
    console.log(`       actual:   ${aj}`);
  }
}

function bigintReplacer(_k: string, v: unknown): unknown {
  return typeof v === "bigint" ? v.toString() + "n" : v;
}

function assert(name: string, cond: boolean): void {
  count++;
  if (cond) {
    console.log(`  ok  ${name}`);
  } else {
    failures++;
    console.log(`  FAIL ${name}`);
  }
}

// --------------------- 1. Language cell registration ----------------------

console.log("lang-python.test: registering Python Language cell…");
{
  const k = new Kernel();
  const { lang, formats } = buildPythonLanguage(k);
  eq("Language.name", lang.name, "python");
  eq("Language.version", lang.version, "3.13");
  // Numeric defaults: int → INT64, float → FP64.
  const intFmt = lang.numericDefaults.get("int");
  const floatFmt = lang.numericDefaults.get("float");
  assert("numericDefaults.int is INT64", intFmt?.nodeID.inst === formats.INT64.nodeID.inst);
  assert("numericDefaults.float is FP64", floatFmt?.nodeID.inst === formats.FP64.nodeID.inst);
  // Stdlib bindings cover the required names.
  for (const name of [
    "len",
    "range",
    "print",
    "str",
    "int",
    "float",
    "list",
    "dict",
    "True",
    "False",
    "None",
  ]) {
    assert(`stdlib binding ${name}`, lang.stdlibBindings.has(name));
  }
  // Content-addressing of the Language cell itself: a second
  // identical registration interns to the same NodeID.
  const k2 = new Kernel();
  const { lang: langB } = buildPythonLanguage(k2);
  // NodeIDs across separate kernel instances aren't directly
  // comparable by inst (they're per-kernel counters), but the
  // structural shape is identical. Verify by re-registering inside
  // the same kernel.
  const second = buildPythonLanguage(k);
  assert(
    "Language cell content-addressing (same kernel, same shape)",
    second.lang.nodeID.inst === lang.nodeID.inst,
  );
  // Cross-kernel re-registration produces a Language whose name/version
  // match — semantic identity holds even if instance counters differ.
  eq("cross-kernel name match", langB.name, lang.name);
  eq("cross-kernel version match", langB.version, lang.version);
}

// --------------------- 2. Numeric literal parsing -------------------------

console.log("\nlang-python.test: numeric literals…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  const intTree = parsePython(k, "42");
  const intStmt = capturedChildren(k, intTree)[0]!;
  eq("int literal: module wraps expr-stmt", capturedCtor(k, intStmt), CTOR.expr_stmt);
  const intExpr = capturedChildren(k, intStmt)[0]!;
  eq("int literal ctor", capturedCtor(k, intExpr), CTOR.int_literal);
  eq("int literal value", evalPython(k, intTree), { kind: "int", int: 42 });

  const floatTree = parsePython(k, "3.14");
  const floatStmt = capturedChildren(k, floatTree)[0]!;
  const floatExpr = capturedChildren(k, floatStmt)[0]!;
  eq("float literal ctor", capturedCtor(k, floatExpr), CTOR.float_literal);
  const fv = evalPython(k, floatTree);
  assert("float literal value ≈ 3.14", fv.kind === "f64" && Math.abs(fv.float - 3.14) < 1e-9);
}

// --------------------- 3. String / bool / None literals -------------------

console.log("\nlang-python.test: string + bool + None…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  eq('"hello" → "hello"', evalPython(k, parsePython(k, '"hello"')), {
    kind: "str",
    str: "hello",
  });
  eq("'world' → world", evalPython(k, parsePython(k, "'world'")), {
    kind: "str",
    str: "world",
  });
  eq('"""triple"""', evalPython(k, parsePython(k, '"""triple"""')), {
    kind: "str",
    str: "triple",
  });
  eq("True", evalPython(k, parsePython(k, "True")), { kind: "bool", bool: true });
  eq("False", evalPython(k, parsePython(k, "False")), { kind: "bool", bool: false });
  eq("None", evalPython(k, parsePython(k, "None")), { kind: "null" });
}

// --------------------- 4. Arithmetic + comparisons ------------------------

console.log("\nlang-python.test: arithmetic + comparisons…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  eq("1 + 2", evalPython(k, parsePython(k, "1 + 2")), { kind: "int", int: 3 });
  eq("10 - 4", evalPython(k, parsePython(k, "10 - 4")), { kind: "int", int: 6 });
  eq("3 * 4", evalPython(k, parsePython(k, "3 * 4")), { kind: "int", int: 12 });
  eq("2 + 3 * 4", evalPython(k, parsePython(k, "2 + 3 * 4")), { kind: "int", int: 14 });
  eq("(2 + 3) * 4", evalPython(k, parsePython(k, "(2 + 3) * 4")), {
    kind: "int",
    int: 20,
  });
  eq("10 % 3", evalPython(k, parsePython(k, "10 % 3")), { kind: "int", int: 1 });
  eq("2 < 3", evalPython(k, parsePython(k, "2 < 3")), { kind: "bool", bool: true });
  eq("5 == 5", evalPython(k, parsePython(k, "5 == 5")), { kind: "bool", bool: true });
  eq("5 != 6", evalPython(k, parsePython(k, "5 != 6")), { kind: "bool", bool: true });
  eq("True and False", evalPython(k, parsePython(k, "True and False")), {
    kind: "bool",
    bool: false,
  });
  eq("True or False", evalPython(k, parsePython(k, "True or False")), {
    kind: "bool",
    bool: true,
  });
  eq("not True", evalPython(k, parsePython(k, "not True")), { kind: "bool", bool: false });
}

// --------------------- 5. List / dict / tuple ------------------------------

console.log("\nlang-python.test: collections…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  const lst = evalPython(k, parsePython(k, "[1, 2, 3]"));
  assert("list literal kind", lst.kind === "list" && lst.list.length === 3);
  const tup = parsePython(k, "(1, 2)");
  const tupStmt = capturedChildren(k, tup)[0]!;
  const tupExpr = capturedChildren(k, tupStmt)[0]!;
  eq("tuple literal ctor", capturedCtor(k, tupExpr), CTOR.tuple_literal);
  const dictTree = parsePython(k, "{1: 2}");
  const dictStmt = capturedChildren(k, dictTree)[0]!;
  const dictExpr = capturedChildren(k, dictStmt)[0]!;
  eq("dict literal ctor", capturedCtor(k, dictExpr), CTOR.dict_literal);
}

// --------------------- 6. Function call / method call ---------------------

console.log("\nlang-python.test: calls…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  const callTree = parsePython(k, "len([1, 2, 3])");
  const result = evalPython(k, callTree);
  eq("len([1,2,3])", result, { kind: "int", int: 3 });
  const rangeTree = parsePython(k, "len(range(10))");
  eq("len(range(10))", evalPython(k, rangeTree), { kind: "int", int: 10 });
  // Method call
  const methodTree = parsePython(k, '"hello".upper()');
  eq('"hello".upper()', evalPython(k, methodTree), { kind: "str", str: "HELLO" });
}

// --------------------- 7. Lambda + conditional expression -----------------

console.log("\nlang-python.test: lambda + conditional expr…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  // Bind a lambda and call it.
  const tree = parsePython(k, "f = lambda x: x + 1");
  // Direct lambda + call is tricky without assignment; use the
  // conditional expression test first.
  const condTree = parsePython(k, "1 if 2 > 1 else 0");
  eq("1 if 2>1 else 0", evalPython(k, condTree), { kind: "int", int: 1 });
  const condTree2 = parsePython(k, "1 if 2 < 1 else 0");
  eq("1 if 2<1 else 0", evalPython(k, condTree2), { kind: "int", int: 0 });
  // Lambda as expression — verify the ctor shape.
  const lambTree = parsePython(k, "lambda x: x + 1");
  const lambStmt = capturedChildren(k, lambTree)[0]!;
  const lambExpr = capturedChildren(k, lambStmt)[0]!;
  eq("lambda ctor", capturedCtor(k, lambExpr), CTOR.lambda_);
  // tree result not used; reference to silence unused-var.
  void tree;
}

// --------------------- 8. def + return + recursion (fib) ------------------

console.log("\nlang-python.test: def + return + recursion (fib)…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  const src = "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)\nfib(10)";
  const tree = parsePython(k, src);
  // Top-level shape: module with 2 statements (def, expr-stmt fib(10)).
  eq("top-level module ctor", capturedCtor(k, tree), CTOR.module);
  const topKids = capturedChildren(k, tree);
  eq("top-level statement count", topKids.length, 2);
  eq("first stmt is def", capturedCtor(k, topKids[0]!), CTOR.def_);
  // Evaluate.
  const result = evalPython(k, tree);
  eq("fib(10) = 55", result, { kind: "int", int: 55 });
}

// --------------------- 9. for + while loops -------------------------------

console.log("\nlang-python.test: for + while…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  // for x in [1,2,3]: x — last expression value
  const forSrc = "def sum_list():\n    s = 0\n    for x in [1, 2, 3]:\n        s = s + x\n    return s\nsum_list()";
  // Note: we don't have assignment-as-statement; verify the for ctor is
  // produced, evaluating side-effects is out of scope without =.
  const forTree = parsePython(k, "for x in [1, 2]: x + 1");
  const forStmt = capturedChildren(k, forTree)[0]!;
  eq("for ctor", capturedCtor(k, forStmt), CTOR.for_);

  // while ctor
  const whileTree = parsePython(k, "while False: 1");
  const whileStmt = capturedChildren(k, whileTree)[0]!;
  eq("while ctor", capturedCtor(k, whileStmt), CTOR.while_);
  // Evaluate while False — produces null without iterating.
  eq("while False: 1 → null", evalPython(k, whileTree), { kind: "null" });
  void forSrc;
}

// --------------------- 10. Round-trip (parse → emit) ----------------------

console.log("\nlang-python.test: round-trip parse → emit…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  const src = "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)";
  const tree = parsePython(k, src);
  const emitted = emitPython(k, tree);
  console.log(`     emit("${src}") =`);
  console.log(`       ${emitted.replace(/\n/g, "\\n")}`);
  // Round-trip is whitespace-tolerable; verify by re-parsing.
  const reparsed = parsePython(k, emitted);
  // The re-parsed tree should evaluate identically with a fib(10) call appended.
  const reparseSrc = emitted + "\nfib(10)";
  const reparseTree = parsePython(k, reparseSrc);
  eq("re-parsed fib(10) = 55", evalPython(k, reparseTree), { kind: "int", int: 55 });
  // The original and re-parsed bodies should share top-level shape.
  eq("re-parsed top-level ctor", capturedCtor(k, reparsed), CTOR.module);
  // Emit again — round-trip stable across two cycles.
  const emittedAgain = emitPython(k, reparsed);
  // Tolerate whitespace differences; verify lexical normalization.
  eq("double-emit normalized stable", normalize(emitted), normalize(emittedAgain));
}

function normalize(s: string): string {
  return s
    .replace(/\s+/g, " ")
    .replace(/\(\s+/g, "(")
    .replace(/\s+\)/g, ")")
    .replace(/\s*,\s*/g, ",")
    .trim();
}

// --------------------- 11. Content-addressing of recipes ------------------

console.log("\nlang-python.test: content-addressing…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  const src = "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)";
  const treeA = parsePython(k, src);
  const treeB = parsePython(k, src);
  eq("parse twice → same NodeID", nodeKey(treeA), nodeKey(treeB));
  // Even a different surface that captures the same shape should
  // share the recipe — semantically:
  //   "1 + 2" should produce the same recipe each time, and the
  //   inner add-recipe should intern to the same NodeID as one built
  //   directly.
  const addA = parsePython(k, "1 + 2");
  const addB = parsePython(k, "1 + 2");
  eq("parse '1 + 2' twice → same NodeID", nodeKey(addA), nodeKey(addB));
  // Slightly different whitespace, same recipe:
  const addC = parsePython(k, "1+2");
  eq("'1+2' and '1 + 2' share NodeID (whitespace-blind)", nodeKey(addA), nodeKey(addC));
}

// --------------------- 12. Lambda evaluation via call ---------------------

console.log("\nlang-python.test: lambda call (inline)…");
{
  const k = new Kernel();
  buildPythonLanguage(k);
  // The IIFE shape: (lambda x: x + 1)(10) → 11
  const src = "(lambda x: x + 1)(10)";
  const tree = parsePython(k, src);
  eq("(lambda x: x+1)(10) → 11", evalPython(k, tree), { kind: "int", int: 11 });
}

// ----- summary -----

console.log(`\nlang-python.test: ${count - failures}/${count} passed`);
if (failures > 0) {
  console.log(`lang-python.test: ${failures} FAILURES`);
  process.exit(1);
}
console.log("lang-python.test: all checks passed.");
