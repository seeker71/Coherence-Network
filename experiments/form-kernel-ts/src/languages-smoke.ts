// languages-smoke.ts — smoke test for the language-as-substrate-cell
// architecture.
//
// Registers a tiny reverse-polish-notation calculator language and
// verifies that parsing "1 2 +" produces a recipe tree whose walk
// evaluates to 3. The point is to prove the substrate-resident grammar
// shape is real, not to demonstrate a complete language.
//
// Run with: tsx src/languages-smoke.ts

import { Kernel, RBasic, Level, type NodeID } from "./kernel.ts";
import { buildFormatLibrary } from "./formats.ts";
import {
  capturedChildren,
  capturedCtor,
  emitThrough,
  eJoin,
  gAlt,
  gCapture,
  gPlus,
  gLiteral,
  gTokenClass,
  parseThrough,
  registerLanguage,
} from "./languages.ts";

function assertEq<T>(actual: T, expected: T, label: string): void {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${String(expected)}, got ${String(actual)}`);
  }
  console.log(`  ok  ${label} = ${String(actual)}`);
}

// Evaluate a captured RPN tree to a number. Walks the tree the parser
// produced; this is the consumer side of the substrate-resident
// language shape.
function evalRpn(k: Kernel, tree: NodeID): number {
  const ctor = capturedCtor(k, tree);
  if (ctor === "program") {
    // The program ctor wraps a list of tokens; evaluate them on a stack.
    const stack: number[] = [];
    for (const tok of capturedChildren(k, tree)) {
      const tokCtor = capturedCtor(k, tok);
      if (tokCtor === "num") {
        const numNode = capturedChildren(k, tok)[0];
        if (!numNode) throw new Error("num: missing value");
        if (numNode.type === 1) { // INT32
          stack.push(numNode.inst | 0);
        } else if (numNode.type === 7) { // FLOAT64
          stack.push(k.decodeFloat64(numNode.inst));
        } else {
          throw new Error(`num: unexpected trivial type ${numNode.type}`);
        }
      } else if (tokCtor === "op") {
        // The op ctor captures the operator literal as its first child.
        const opNode = capturedChildren(k, tok)[0];
        if (!opNode) throw new Error("op: missing operator");
        const op = k.strs[opNode.inst] ?? "";
        const b = stack.pop();
        const a = stack.pop();
        if (a === undefined || b === undefined) {
          throw new Error("rpn: stack underflow");
        }
        switch (op) {
          case "+":
            stack.push(a + b);
            break;
          case "-":
            stack.push(a - b);
            break;
          case "*":
            stack.push(a * b);
            break;
          case "/":
            stack.push(a / b);
            break;
          default:
            throw new Error(`rpn: unknown operator "${op}"`);
        }
      } else {
        throw new Error(`rpn: unexpected ctor "${tokCtor}"`);
      }
    }
    if (stack.length !== 1) {
      throw new Error(`rpn: stack should have one value, has ${stack.length}`);
    }
    return stack[0]!;
  }
  throw new Error(`rpn: top-level ctor should be "program", was "${ctor}"`);
}

function main(): void {
  console.log("languages-smoke: registering RPN calculator…");
  const k = new Kernel();
  const fmts = buildFormatLibrary(k);

  // Grammar:
  //   program = (num | op)+
  //   num     = <number-token>             (capture as "num")
  //   op      = "+" | "-" | "*" | "/"      (capture as "op")
  const numRule = gCapture(k, "num", gTokenClass(k, "number"));
  const opRule = gCapture(
    k,
    "op",
    gAlt(k, gLiteral(k, "+"), gLiteral(k, "-"), gLiteral(k, "*"), gLiteral(k, "/")),
  );
  const tokenRule = gAlt(k, numRule, opRule);
  const programRule = gCapture(k, "program", gPlus(k, tokenRule));

  // Emission template: rejoin children with a single space. This is
  // the round-trip shape; pretty-printers will grow per-ctor rules.
  const emissionTemplate = eJoin(k, " ", 0, -1);

  const numericDefaults = new Map([
    ["int", fmts.INT32],
    ["float", fmts.FP64],
  ]);

  const lang = registerLanguage(k, {
    name: "rpn",
    version: "0.1.0",
    ingestionGrammar: programRule,
    emissionTemplate,
    numericDefaults,
  });

  console.log(`  ok  registered language "${lang.name}" v${lang.version} at NodeID inst=${lang.nodeID.inst}`);

  // Two registrations of the same language intern to the same NodeID
  // — content-addressing of the Language cell.
  const langB = registerLanguage(k, {
    name: "rpn",
    version: "0.1.0",
    ingestionGrammar: programRule,
    emissionTemplate,
    numericDefaults,
  });
  assertEq(langB.nodeID.inst, lang.nodeID.inst, "Language cell content-addressing");

  // Parse "1 2 +" and verify the recipe shape.
  const tree = parseThrough(k, lang, "1 2 +");
  assertEq(capturedCtor(k, tree), "program", "top-level ctor");
  const tokens = capturedChildren(k, tree);
  assertEq(tokens.length, 3, "token count");
  assertEq(capturedCtor(k, tokens[0]!), "num", "token[0] ctor");
  assertEq(capturedCtor(k, tokens[1]!), "num", "token[1] ctor");
  assertEq(capturedCtor(k, tokens[2]!), "op", "token[2] ctor");

  // Evaluate via the recipe walk.
  const result = evalRpn(k, tree);
  assertEq(result, 3, "evaluate(1 2 +)");

  // A second program: "10 3 -" = 7
  const tree2 = parseThrough(k, lang, "10 3 -");
  assertEq(evalRpn(k, tree2), 7, "evaluate(10 3 -)");

  // Cross-program identity: parsing "1 2 +" twice yields the same NodeID
  // (the recipe tree is content-addressed via the substrate).
  const tree3 = parseThrough(k, lang, "1 2 +");
  assertEq(tree3.inst, tree.inst, "parse content-addressing");

  // Round-trip through emission. The toy template joins children with
  // spaces; for the RPN language that recovers the source up to
  // whitespace.
  const emitted = emitThrough(k, lang, tree);
  console.log(`  ok  emit_through("1 2 +") = "${emitted}"`);

  console.log("languages-smoke: all checks passed.");
}

main();
