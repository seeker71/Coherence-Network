// Bench harness — native TS vs kernel TS.
//
// Same four workloads as the Go and Rust kernels in form-kernel-comparison.md,
// using the same `.fk` source verbatim so cross-kernel NodeID agreement holds.
//
// `opaque` is V8's equivalent of Go's //go:noinline barrier: it forces V8 to
// observe the recursive call site as opaque so constant-folding can't elide
// the whole computation when inputs are compile-time constants. Without it,
// V8 may turbofan the function into a single arithmetic constant.
//
// %NeverOptimizeFunction-style intrinsics aren't available without the
// --allow-natives-syntax flag, so we use a global-array reference pattern
// that V8's optimizer treats as side-effectful.

import { Frame, Kernel, walk, type Value } from "./kernel.ts";
import { readForm } from "./reader.ts";
import { compileNode, type CompiledFn } from "./compiler.ts";

// Opaque sink. V8 cannot prove this side-effect-free, so calls cannot be
// folded across it. Used to wrap the recursive argument so the native
// reference measures actual recursive work, not constant folds.
const sink: number[] = [];
function opaque(n: number): number {
  if (sink.length > 1_000_000) sink.length = 0;
  return n;
}

function nativeFib(n: number): number {
  if (n <= 1) return n;
  return nativeFib(opaque(n - 1)) + nativeFib(opaque(n - 2));
}

function nativeFact(n: number): number {
  if (n <= 1) return 1;
  return n * nativeFact(opaque(n - 1));
}

function nativeSum(n: number, acc: number): number {
  if (n === 0) return acc;
  return nativeSum(opaque(n - 1), opaque(acc + n));
}

function nativeAck(m: number, n: number): number {
  if (m === 0) return n + 1;
  if (n === 0) return nativeAck(opaque(m - 1), 1);
  return nativeAck(opaque(m - 1), nativeAck(m, opaque(n - 1)));
}

interface Case {
  name: string;
  src: string;
  nativeIters: number;
  native: () => number;
}

const CASES: Case[] = [
  {
    name: "fib28",
    src: `(do (defn fib (n) (if (le n 1) n (add (fib (sub n 1)) (fib (sub n 2))))) (fib 28))`,
    nativeIters: 100,
    native: () => nativeFib(28),
  },
  {
    name: "fact12",
    src: `(do (defn fact (n) (if (le n 1) 1 (mul n (fact (sub n 1))))) (fact 12))`,
    nativeIters: 500_000,
    native: () => nativeFact(12),
  },
  {
    name: "sum1000",
    src: `(do (defn sum (n acc) (if (eq n 0) acc (sum (sub n 1) (add acc n)))) (sum 1000 0))`,
    nativeIters: 50_000,
    native: () => nativeSum(1000, 0),
  },
  {
    name: "ackermann",
    src: `(do (defn ack (m n) (if (eq m 0) (add n 1) (if (eq n 0) (ack (sub m 1) 1) (ack (sub m 1) (ack m (sub n 1)))))) (ack 3 6))`,
    nativeIters: 100,
    native: () => nativeAck(3, 6),
  },
];

const KERNEL_ITERS = 5;

function timeNs(fn: () => void): bigint {
  const start = process.hrtime.bigint();
  fn();
  return process.hrtime.bigint() - start;
}

function formatNs(ns: bigint): string {
  const n = Number(ns);
  if (n < 1_000) return `${n.toFixed(0)} ns`;
  if (n < 1_000_000) return `${(n / 1_000).toFixed(2)} µs`;
  if (n < 1_000_000_000) return `${(n / 1_000_000).toFixed(2)} ms`;
  return `${(n / 1_000_000_000).toFixed(2)} s`;
}

function valueToString(v: Value): string {
  switch (v.kind) {
    case "int":
      return String(v.int);
    case "str":
      return JSON.stringify(v.str);
    case "bool":
      return String(v.bool);
    case "null":
      return "null";
    case "list":
      return "[…]";
    case "closure":
      return "<closure>";
    case "nodeid":
      return "<nodeid>";
  }
}

interface Result {
  name: string;
  result: string;
  nativeNs: bigint;
  walkerNs: bigint;
  compiledNs: bigint;
  walkerOver: number;
  compiledOver: number;
}

function runOne(c: Case): Result {
  // Native — measure per-iteration time
  let nativeResult = 0;
  const nativeTotal = timeNs(() => {
    for (let i = 0; i < c.nativeIters; i++) {
      nativeResult = c.native();
    }
  });
  const nativeNs = nativeTotal / BigInt(c.nativeIters);

  // Walker — fresh kernel + parsed once; walk many iters
  const kWalker = new Kernel();
  const root = readForm(kWalker, c.src);
  const env = new Frame(null);
  // Warmup
  walk(kWalker, root, env);
  let walkerResult: Value = { kind: "null" };
  const walkerTotal = timeNs(() => {
    for (let i = 0; i < KERNEL_ITERS; i++) {
      walkerResult = walk(kWalker, root, new Frame(null));
    }
  });
  const walkerNs = walkerTotal / BigInt(KERNEL_ITERS);

  // Compiled — fresh kernel, compile root, invoke compiled fn many iters
  const kComp = new Kernel();
  const rootComp = readForm(kComp, c.src);
  const compiled: CompiledFn = compileNode(kComp, rootComp);
  // Warmup — runs the compiled fn so V8 sees it hot
  compiled(new Frame(null));
  compiled(new Frame(null));
  let compiledResult: Value = { kind: "null" };
  const compIters = c.name === "fib28" || c.name === "ackermann" ? 20 : 200;
  const compTotal = timeNs(() => {
    for (let i = 0; i < compIters; i++) {
      compiledResult = compiled(new Frame(null));
    }
  });
  const compiledNs = compTotal / BigInt(compIters);

  // Reality check: all three must agree
  const nativeStr = String(nativeResult);
  const walkerStr = valueToString(walkerResult);
  const compiledStr = valueToString(compiledResult);
  if (nativeStr !== walkerStr || walkerStr !== compiledStr) {
    throw new Error(
      `${c.name}: result mismatch — native=${nativeStr} walker=${walkerStr} compiled=${compiledStr}`,
    );
  }

  return {
    name: c.name,
    result: nativeStr,
    nativeNs,
    walkerNs,
    compiledNs,
    walkerOver: Number(walkerNs) / Number(nativeNs),
    compiledOver: Number(compiledNs) / Number(nativeNs),
  };
}

export function runBench(): void {
  const results: Result[] = [];
  for (const c of CASES) {
    results.push(runOne(c));
  }

  console.log(
    `${"workload".padEnd(12)} ${"result".padEnd(12)} ${"native".padEnd(14)} ${"walker".padEnd(14)} ${"walk-over".padEnd(10)} ${"compiled".padEnd(14)} ${"comp-over"}`,
  );
  for (const r of results) {
    console.log(
      `${r.name.padEnd(12)} ${r.result.padEnd(12)} ${formatNs(r.nativeNs).padEnd(14)} ${formatNs(r.walkerNs).padEnd(14)} ${(r.walkerOver.toFixed(0) + "×").padEnd(10)} ${formatNs(r.compiledNs).padEnd(14)} ${r.compiledOver.toFixed(0)}×`,
    );
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runBench();
}
