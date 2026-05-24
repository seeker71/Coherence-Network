// generative.test.ts — runnable test suite for substrate-resident generative
// model recipes. Tests follow the conformance-runner pattern: plain tsx
// execution, assertion failures exit with non-zero.
//
//   tsx src/generative.test.ts

import {
  Kernel,
  Level,
  RBasic,
  RBlock,
  Triv,
  nodeKey,
  NodeID,
} from "./kernel.ts";
import {
  makeGenerativeModel,
  modelOf,
  modelCell,
  modelExpected,
  modelPriors,
  modelPredictionFn,
  predict,
  surpriseScore,
  composeModels,
  isGenerativeModel,
  asGenerativeModel,
} from "./generative.ts";

let pass = 0;
let fail = 0;

function check(name: string, cond: boolean, detail?: string): void {
  if (cond) {
    pass++;
    process.stdout.write(`  ok  ${name}\n`);
  } else {
    fail++;
    process.stdout.write(`  FAIL  ${name}${detail ? ` — ${detail}` : ""}\n`);
  }
}

function eq<T>(a: T, b: T): boolean {
  return Object.is(a, b);
}

// ---------------------------------------------------------------------------
// Test helpers — small constructors for cells, sensory recipes, prediction fns
// ---------------------------------------------------------------------------

// Make a "cell" — a freshly-interned LIST recipe carrying an int marker.
function makeCell(k: Kernel, marker: number): NodeID {
  const listCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.LIST,
    inst: 0,
  };
  return k.intern(listCat, [k.internTrivialInt(marker)]);
}

// Make a "sensory" recipe — a LIST recipe carrying a string trivial. Two
// sensory recipes with the same string intern to the same NodeID.
function makeSensory(k: Kernel, label: string): NodeID {
  const listCat: NodeID = {
    pkg: 1,
    level: Level.BASIC,
    type: RBasic.LIST,
    inst: 0,
  };
  return k.intern(listCat, [k.internString(label)]);
}

// Make an identity-prediction-fn: an FNDEF closure (fn (s) s) that returns
// its sensory argument as the predicted internal update.
function makeIdentityFn(k: Kernel, fnName: string, paramName: string): NodeID {
  const nameTriv: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(fnName),
  };
  const paramTriv: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(paramName),
  };
  // params is a SEQUENCE block of name trivials
  const paramsBlock = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    [paramTriv],
  );
  // Body is an IDENT recipe that resolves the parameter from the call frame.
  const body = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 1 },
    [paramTriv],
  );
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 1 },
    [nameTriv, paramsBlock, body],
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

function testBasicShape(): void {
  process.stdout.write("\n# basic shape — cell + model + lookup\n");
  const k = new Kernel();
  const cell = makeCell(k, 1);
  const expected = [makeSensory(k, "ping"), makeSensory(k, "pong")];
  const priors = [makeSensory(k, "world-is-quiet")];
  const fn = makeIdentityFn(k, "id-fn", "s");

  const model = makeGenerativeModel(k, cell, expected, priors, fn);

  check(
    "model node is a GENERATIVE recipe",
    isGenerativeModel(k, model.node),
  );
  check(
    "modelOf returns the registered model",
    modelOf(k, cell)?.node === model.node,
  );
  check("modelOf for unknown cell is null", modelOf(k, makeCell(k, 999)) === null);

  check("modelCell round-trips", nodeKey(modelCell(k, model)) === nodeKey(cell));
  check(
    "modelExpected returns 2 items",
    modelExpected(k, model).length === 2,
    `got ${modelExpected(k, model).length}`,
  );
  check("modelPriors returns 1 item", modelPriors(k, model).length === 1);
  check(
    "modelPredictionFn round-trips",
    nodeKey(modelPredictionFn(k, model)) === nodeKey(fn),
  );
  check(
    "asGenerativeModel re-brands a known node",
    asGenerativeModel(k, model.node).node === model.node,
  );
}

function testPredict(): void {
  process.stdout.write("\n# predict — running the prediction fn\n");
  const k = new Kernel();
  const cell = makeCell(k, 2);
  const sensory = makeSensory(k, "alpha");
  const expected = [sensory];
  const priors: NodeID[] = [];
  const fn = makeIdentityFn(k, "predict-id", "s");

  const model = makeGenerativeModel(k, cell, expected, priors, fn);
  const predicted = predict(k, model, sensory);
  check(
    "identity prediction returns the input sensory NodeID",
    predicted !== null && nodeKey(predicted) === nodeKey(sensory),
  );

  // A novel sensory still passes through identity
  const novel = makeSensory(k, "beta");
  const predicted2 = predict(k, model, novel);
  check(
    "identity prediction passes novel sensory through",
    predicted2 !== null && nodeKey(predicted2) === nodeKey(novel),
  );
}

function testSurprise(): void {
  process.stdout.write("\n# surprise — scoring prediction error\n");
  const k = new Kernel();
  const cell = makeCell(k, 3);
  const sensoryA = makeSensory(k, "expected-A");
  const sensoryB = makeSensory(k, "expected-B");
  const fn = makeIdentityFn(k, "s-fn", "s");

  const model = makeGenerativeModel(k, cell, [sensoryA, sensoryB], [], fn);

  check(
    "surprise=0 when actual matches expected",
    surpriseScore(k, model, sensoryA) === 0,
  );
  check(
    "surprise=0 when actual matches other expected",
    surpriseScore(k, model, sensoryB) === 0,
  );

  // Same shape (LIST with one string child), different content → small surprise
  const sameShape = makeSensory(k, "novel");
  const surpriseSame = surpriseScore(k, model, sameShape);
  check(
    "surprise=1 when actual is same-shape but different content (delta=0, base=1)",
    surpriseSame === 1,
    `got ${surpriseSame}`,
  );

  // Empty model — every sensory is surprising
  const emptyModel = makeGenerativeModel(k, makeCell(k, 99), [], [], fn);
  check(
    "surprise=1 when model has no expected (empty baseline)",
    surpriseScore(k, emptyModel, sensoryA) === 1,
  );

  // Completely different category — high surprise (>1)
  const bareInt = k.internTrivialInt(42);
  const surpriseBig = surpriseScore(k, model, bareInt);
  check(
    "surprise large when actual is unrelated category",
    surpriseBig >= 10,
    `got ${surpriseBig}`,
  );
}

function testContentAddressing(): void {
  process.stdout.write("\n# content-addressing — same shape → same NodeID\n");
  const k = new Kernel();
  const cell = makeCell(k, 4);
  const e1 = makeSensory(k, "x");
  const e2 = makeSensory(k, "y");
  const fn = makeIdentityFn(k, "ca-fn", "s");

  const a = makeGenerativeModel(k, cell, [e1, e2], [], fn);
  const b = makeGenerativeModel(k, cell, [e1, e2], [], fn);
  check(
    "same (cell, expected, priors, fn) → same model NodeID",
    nodeKey(a.node) === nodeKey(b.node),
  );

  // Different expected → different NodeID
  const e3 = makeSensory(k, "z");
  const c = makeGenerativeModel(k, cell, [e1, e3], [], fn);
  check(
    "different expected → different model NodeID",
    nodeKey(a.node) !== nodeKey(c.node),
  );
}

function testComposeCommutativity(): void {
  process.stdout.write("\n# composeModels — commutativity through content-addressing\n");
  const k = new Kernel();
  const cellA = makeCell(k, 10);
  const cellB = makeCell(k, 11);
  const sA = makeSensory(k, "A");
  const sB = makeSensory(k, "B");
  const pA = makeSensory(k, "priorA");
  const pB = makeSensory(k, "priorB");
  const fnA = makeIdentityFn(k, "fnA", "s");
  const fnB = makeIdentityFn(k, "fnB", "t");

  const mA = makeGenerativeModel(k, cellA, [sA], [pA], fnA);
  const mB = makeGenerativeModel(k, cellB, [sB], [pB], fnB);

  const ab = composeModels(k, mA, mB);
  const ba = composeModels(k, mB, mA);
  check(
    "compose(A,B) === compose(B,A) via content-addressing",
    nodeKey(ab.node) === nodeKey(ba.node),
  );

  // Composed model carries union of expected
  const expectedKeys = new Set(modelExpected(k, ab).map(nodeKey));
  check(
    "composed expected contains A's sensory",
    expectedKeys.has(nodeKey(sA)),
  );
  check(
    "composed expected contains B's sensory",
    expectedKeys.has(nodeKey(sB)),
  );

  // Union of priors
  const priorKeys = new Set(modelPriors(k, ab).map(nodeKey));
  check("composed priors contains A's prior", priorKeys.has(nodeKey(pA)));
  check("composed priors contains B's prior", priorKeys.has(nodeKey(pB)));
}

function testComposeAssociativity(): void {
  process.stdout.write("\n# composeModels — associativity through content-addressing\n");
  const k = new Kernel();
  const cells = [makeCell(k, 20), makeCell(k, 21), makeCell(k, 22)];
  const sensors = [makeSensory(k, "p"), makeSensory(k, "q"), makeSensory(k, "r")];
  const fn = makeIdentityFn(k, "fn-assoc", "s");

  const m0 = makeGenerativeModel(k, cells[0]!, [sensors[0]!], [], fn);
  const m1 = makeGenerativeModel(k, cells[1]!, [sensors[1]!], [], fn);
  const m2 = makeGenerativeModel(k, cells[2]!, [sensors[2]!], [], fn);

  const left = composeModels(k, composeModels(k, m0, m1), m2);
  const right = composeModels(k, m0, composeModels(k, m1, m2));
  check(
    "compose(compose(A,B),C) === compose(A,compose(B,C))",
    nodeKey(left.node) === nodeKey(right.node),
    `left=${nodeKey(left.node)} right=${nodeKey(right.node)}`,
  );

  // Triple union expected
  const expectedKeys = new Set(modelExpected(k, left).map(nodeKey));
  check(
    "triple-composed expected contains all three sensors",
    expectedKeys.size === 3 &&
      sensors.every((s) => expectedKeys.has(nodeKey(s))),
  );
}

function testDuplicateSuppression(): void {
  process.stdout.write("\n# composeModels — duplicate expected/priors deduped by content\n");
  const k = new Kernel();
  const cell = makeCell(k, 30);
  const shared = makeSensory(k, "shared");
  const onlyA = makeSensory(k, "only-A");
  const fn = makeIdentityFn(k, "dup-fn", "s");

  const mA = makeGenerativeModel(k, cell, [shared, onlyA], [], fn);
  const mB = makeGenerativeModel(k, cell, [shared], [], fn);
  const composed = composeModels(k, mA, mB);

  const expected = modelExpected(k, composed);
  const keys = expected.map(nodeKey);
  const uniqueKeys = new Set(keys);
  check(
    "composed expected has no duplicates",
    keys.length === uniqueKeys.size,
    `keys=${keys.join(",")}`,
  );
  check(
    "composed expected has exactly the union size (2)",
    expected.length === 2,
    `got ${expected.length}`,
  );
}

function testKernelSlot(): void {
  process.stdout.write("\n# kernel slot — GENERATIVE = 82\n");
  check("RBasic.GENERATIVE === 82", eq(RBasic.GENERATIVE, 82));
}

function main(): void {
  process.stdout.write("# generative.test.ts\n");
  testKernelSlot();
  testBasicShape();
  testPredict();
  testSurprise();
  testContentAddressing();
  testComposeCommutativity();
  testComposeAssociativity();
  testDuplicateSuppression();

  process.stdout.write(`\nresults: ${pass} ok, ${fail} fail\n`);
  if (fail > 0) process.exit(1);
}

main();
