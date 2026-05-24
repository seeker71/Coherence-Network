// lang-typescript.test.ts — proof-of-shape tests for the TypeScript
// Language cell (task #16).
//
// Run with: npx tsx src/lang-typescript.test.ts
// Exits non-zero on failure.
//
// What this exercises:
//   • Tokenization of TS surface (numbers including bigint, strings of
//     all three flavors, identifiers, operators).
//   • Grammar walk over a representative TS program — function
//     declarations with type annotations, recursive expressions,
//     ternary conditional, comparison + arithmetic operators.
//   • Round-trip: source → recipe → source recovers an equivalent TS
//     program (whitespace normalized).
//   • Evaluation: `fib(10)` computed by walking the recipe tree
//     produces 55, proving the recipe carries enough semantics for
//     execution without re-tokenizing.
//   • Content-addressing: parsing the same source twice produces the
//     same NodeID (recipe is interned by structural identity).
//   • Numeric defaults: number → FP64 with INT32 inference on
//     integer-range literals; bigint → INT64.

import { Kernel, Level } from "./kernel.ts";
import {
  buildTypeScriptLanguage,
  parseTypeScript,
  emitTypeScript,
  evalTypeScript,
  callFunction,
} from "./lang-typescript.ts";

let failures = 0;
let count = 0;

function eq<T>(name: string, actual: T, expected: T): void {
  count++;
  if (actual === expected) {
    console.log(`  ok  ${name}`);
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
    console.error(`  FAIL ${name}${detail ? `\n    ${detail}` : ""}`);
  }
}

// ---------------------------------------------------------------------------
console.log("[test] Language cell registration");
{
  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);
  eq("language name", ts.language.name, "typescript");
  eq("language version", ts.language.version, "5.7");
  ok(
    "ingestion grammar interned",
    ts.language.ingestionGrammar.inst > 0,
    `inst=${ts.language.ingestionGrammar.inst}`,
  );
  ok(
    "stdlib bindings present",
    ts.language.stdlibBindings.has("console.log") &&
      ts.language.stdlibBindings.has("Math.abs") &&
      ts.language.stdlibBindings.has("Array.length") &&
      ts.language.stdlibBindings.has("Map") &&
      ts.language.stdlibBindings.has("Set") &&
      ts.language.stdlibBindings.has("Promise") &&
      ts.language.stdlibBindings.has("JSON"),
  );
  ok(
    "numeric defaults: number → FP64",
    ts.numericDefaults.get("number")!.semanticKind === 4 && // SemanticKind.REAL
      ts.numericDefaults.get("number")!.bits === 64,
    "FP64 format recipe (REAL, 64-bit) should be registered under 'number'",
  );
  ok(
    "numeric defaults: bigint → INT64",
    ts.numericDefaults.has("bigint"),
  );
  ok(
    "numeric defaults: int32 inference slot",
    ts.numericDefaults.has("int32"),
  );

  // Second build interns to the same Language NodeID — content-addressed.
  const ts2 = buildTypeScriptLanguage(k);
  eq("Language cell content-addressing", ts2.language.nodeID.inst, ts.language.nodeID.inst);
}

// ---------------------------------------------------------------------------
console.log("[test] Numeric literal defaults");
{
  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);
  const r1 = parseTypeScript(k, ts.grammar, "42");
  // recipe: program → [SEQ-list of topStmt] → exprStmt → conditional →
  // … → primary → numLit → trivial. The trivial type should be INT32
  // (slot 1) for an integer-range literal.
  const numStmt = k.recipeAt(r1)!;
  ok("program ctor present", numStmt.children.length === 1);

  // Drill: program children[0] is a SEQ-list; element[0] is exprStmt
  const stmtsList = k.recipeAt(numStmt.children[0]!)!;
  const exprStmt = k.recipeAt(stmtsList.children[0]!)!;
  // exprStmt: [expr, ";"?]
  // Walk all the way down to the trivial number.
  let node = exprStmt.children[0]!;
  while (node.level !== Level.TRIVIAL) {
    const r = k.recipeAt(node);
    if (!r || r.children.length === 0) break;
    node = r.children[0]!;
  }
  eq("integer 42 → INT32 trivial type", node.type, 1); // Triv.INT32 = 1
  eq("integer 42 value", node.inst | 0, 42);

  // Floating literal stays FP64.
  const r2 = parseTypeScript(k, ts.grammar, "3.14");
  let node2 = k.recipeAt(r2)!;
  let cur = node2.children[0]!;
  while (cur.level !== Level.TRIVIAL) {
    const r = k.recipeAt(cur);
    if (!r || r.children.length === 0) break;
    cur = r.children[0]!;
  }
  eq("float 3.14 → FP64 trivial type", cur.type, 7); // Triv.FLOAT64 = 7

  // Bigint suffix.
  const r3 = parseTypeScript(k, ts.grammar, "123n");
  let cur3 = k.recipeAt(r3)!.children[0]!;
  while (cur3.level !== Level.TRIVIAL) {
    const r = k.recipeAt(cur3);
    if (!r || r.children.length === 0) break;
    cur3 = r.children[0]!;
  }
  eq("bigint 123n → INT64 trivial type", cur3.type, 5); // Triv.INT64 = 5
  eq("bigint 123n value", k.decodeInt64(cur3.inst), 123n);
}

// ---------------------------------------------------------------------------
console.log("[test] Parse + emit + evaluate fib(10)");
{
  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);
  const source = "function fib(n: number): number { return n < 2 ? n : fib(n-1) + fib(n-2); }";

  const recipe = parseTypeScript(k, ts.grammar, source);
  ok("fib parses to a program recipe", recipe.level === Level.BASIC);

  // Emit back via the emission walker.
  const emitted = emitTypeScript(k, recipe);
  // The round-trip is whitespace-normalized; verify the emitted source
  // re-parses to the same NodeID (structural equivalence).
  const recipe2 = parseTypeScript(k, ts.grammar, emitted);
  eq("round-trip preserves recipe identity", recipe2.inst, recipe.inst);
  // And the emission is recognizable TS (sanity-check a few tokens).
  ok(
    "emit contains the function signature",
    emitted.includes("function fib(n: number)") && emitted.includes(": number"),
    `emitted: ${emitted}`,
  );
  ok("emit contains ternary", emitted.includes("?") && emitted.includes(":"));

  // Evaluate via tree-walk.
  const env = evalTypeScript(k, recipe);
  const result = callFunction(env, "fib", 10);
  eq("fib(10) = 55", result, 55);
  eq("fib(0) = 0", callFunction(env, "fib", 0), 0);
  eq("fib(7) = 13", callFunction(env, "fib", 7), 13);
}

// ---------------------------------------------------------------------------
console.log("[test] Content-addressing across parses");
{
  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);
  const src = "function add(x: number, y: number): number { return x + y; }";
  const r1 = parseTypeScript(k, ts.grammar, src);
  const r2 = parseTypeScript(k, ts.grammar, src);
  eq("same source → same NodeID", r2.inst, r1.inst);

  // Same shape with renamed identifiers should NOT collide (the ident
  // strings are part of the captured tree).
  const r3 = parseTypeScript(k, ts.grammar, "function mul(a: number, b: number): number { return a * b; }");
  ok("different source → different NodeID", r3.inst !== r1.inst);
}

// ---------------------------------------------------------------------------
console.log("[test] Statement and expression coverage");
{
  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);

  // if / else
  const r1 = parseTypeScript(k, ts.grammar,
    "function abs(n: number): number { if (n < 0) { return -n; } else { return n; } }");
  const env1 = evalTypeScript(k, r1);
  eq("abs(-5) = 5", callFunction(env1, "abs", -5), 5);
  eq("abs(7) = 7", callFunction(env1, "abs", 7), 7);

  // C-style for loop
  const r2 = parseTypeScript(k, ts.grammar,
    "function sumTo(n: number): number { let s = 0; for (let i = 1; i <= n; i++) { s = s + i; } return s; }");
  const env2 = evalTypeScript(k, r2);
  eq("sumTo(10) = 55", callFunction(env2, "sumTo", 10), 55);

  // while loop
  const r3 = parseTypeScript(k, ts.grammar,
    "function countDown(n: number): number { let c = 0; while (n > 0) { n = n - 1; c = c + 1; } return c; }");
  const env3 = evalTypeScript(k, r3);
  eq("countDown(8) = 8", callFunction(env3, "countDown", 8), 8);

  // for..of
  const r4 = parseTypeScript(k, ts.grammar,
    "function sumArr(xs: number): number { let s = 0; for (const x of xs) { s = s + x; } return s; }");
  const env4 = evalTypeScript(k, r4);
  eq("sumArr([1,2,3,4]) = 10", callFunction(env4, "sumArr", [1, 2, 3, 4]), 10);

  // arrow function as expression statement
  const r5 = parseTypeScript(k, ts.grammar,
    "const inc = (x: number) => x + 1;");
  const env5 = evalTypeScript(k, r5);
  const inc = (env5.vars.get("inc") as (n: number) => number);
  eq("arrow (x: number) => x + 1 of 41", inc(41), 42);

  // array + object literals
  const r6 = parseTypeScript(k, ts.grammar,
    "function pair(a: number, b: number): number { const obj = {x: a, y: b}; const arr = [obj.x, obj.y]; return arr[0] + arr[1]; }");
  const env6 = evalTypeScript(k, r6);
  eq("pair(3, 4) = 7", callFunction(env6, "pair", 3, 4), 7);

  // interface + type alias parse cleanly (we don't eval them — they're
  // type-level constructs erased at runtime).
  const r7 = parseTypeScript(k, ts.grammar,
    "interface P { x: number; y: number; } type Pt = P;");
  ok("interface + type alias parsed", r7.level === Level.BASIC);

  // String concatenation through binOp
  const r8 = parseTypeScript(k, ts.grammar,
    'function greet(name: string): string { return "hello " + name; }');
  const env8 = evalTypeScript(k, r8);
  eq("greet('world') = 'hello world'", callFunction(env8, "greet", "world"), "hello world");

  // Logical operators
  const r9 = parseTypeScript(k, ts.grammar,
    "function both(a: number, b: number): number { return a > 0 && b > 0; }");
  const env9 = evalTypeScript(k, r9);
  eq("both(1, 2) true", callFunction(env9, "both", 1, 2), true);
  ok("both(-1, 2) falsy",
    !callFunction(env9, "both", -1, 2));
}

// ---------------------------------------------------------------------------
console.log("[test] Cross-language structural shape — captured ctor names");
{
  // The ctor names CAPTURE wraps under should be the canonical ones
  // sibling languages also use. This locks the contract before sibling
  // PRs land.
  const k = new Kernel();
  const ts = buildTypeScriptLanguage(k);
  const r = parseTypeScript(k, ts.grammar, "function f(x: number): number { return x + 1; }");
  // Top-level ctor
  const programRecipe = k.recipeAt(r)!;
  eq("top-level captured ctor is 'program'",
    k.strs[programRecipe.category.inst] ?? "",
    "program");

  // First statement is funcDecl. CAPTURE splices the STAR-list body of
  // the `program` rule, so program.children IS the top-level statement
  // sequence directly (no intermediate LIST-cat-0 wrapper).
  const first = k.recipeAt(programRecipe.children[0]!)!;
  eq("first stmt is funcDecl",
    k.strs[first.category.inst] ?? "",
    "funcDecl");
}

// ---------------------------------------------------------------------------
console.log("");
console.log(`[summary] ${count - failures}/${count} passed`);
if (failures > 0) {
  console.error(`${failures} failure(s)`);
  process.exit(1);
}
