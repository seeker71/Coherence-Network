// numeric-bench.ts — measure format-recipe-driven arithmetic.
//
// Three workloads exercise three storage/arithmetic-hint paths:
//   - FP64 (native-fp)           — the hot path V8 JITs to f64 instructions
//   - FP8 simulated (table-lookup-via-fp32) — narrow float, software emulation
//   - BitNet ternary (native-int) — small-int arithmetic on {-1, 0, 1}
//
// Each workload runs through:
//   1. native TS (reference) — JS arithmetic, no format dispatch
//   2. format-driven dispatcher (Pass 0 — naive: applyArith per op)
//   3. format-driven with handler cache (Pass 1 — monomorphized via FormatTable)
//   4. compiled path with format-aware emit (Pass 2 — specialized JS)
//
// The arc:
//   Pass 0 vs native — measures the cost of generic format dispatch
//   Pass 1 vs Pass 0 — measures the cache win (monomorphization)
//   Pass 2 vs Pass 1 — measures the compile-to-JS win
//
// Same opaque-barrier trick as bench.ts to keep V8 honest.

import { Kernel } from "./kernel.ts";
import {
  applyArith,
  ArithHintCode,
  buildFormatLibrary,
  type ArithOp,
  type FormatRecipe,
  type Numberish,
} from "./formats.ts";
import { FormatTable, registerFormats } from "./numeric.ts";

const sink: number[] = [];
function opaque(n: number): number {
  if (sink.length > 1_000_000) sink.length = 0;
  return n;
}

// ── Native references (no format dispatch) ──────────────────────────────

function nativeFp64Sum(n: number, acc: number): number {
  // Σ i * 0.5 for i in 1..n
  if (n === 0) return acc;
  return nativeFp64Sum(opaque(n - 1), opaque(acc + n * 0.5));
}

// FP8-like: simulate by rounding to 256 representable values per
// fp32-aligned range. Use Math.fround as a stand-in.
function nativeFp8Sum(n: number, acc: number): number {
  if (n === 0) return acc;
  const x = Math.fround(n * 0.0625); // simulate small dynamic range
  return nativeFp8Sum(opaque(n - 1), Math.fround(acc + x));
}

// BitNet ternary: dot-product-style accumulator of {-1, 0, 1} values.
// Random-ish but deterministic so cross-runs agree.
function nativeBitnetDot(n: number, acc: number): number {
  if (n === 0) return acc;
  const t = ((n * 13) % 3) - 1; // gives -1, 0, or 1
  return nativeBitnetDot(opaque(n - 1), opaque(acc + t));
}

// ── Pass 0 — naive format dispatcher (no cache) ──────────────────────────

function pass0Fp64Sum(
  fmt: FormatRecipe,
  n: number,
  acc: number,
): number {
  if (n === 0) return acc;
  const x = applyArith(fmt, "mul", n, 0.5) as number;
  const acc2 = applyArith(fmt, "add", acc, x) as number;
  return pass0Fp64Sum(fmt, opaque(n - 1), acc2);
}

function pass0Fp8Sum(fmt: FormatRecipe, n: number, acc: number): number {
  if (n === 0) return acc;
  const x = applyArith(fmt, "mul", n, 0.0625) as number;
  const acc2 = applyArith(fmt, "add", acc, x) as number;
  return pass0Fp8Sum(fmt, opaque(n - 1), acc2);
}

function pass0BitnetDot(fmt: FormatRecipe, n: number, acc: number): number {
  if (n === 0) return acc;
  const t = ((n * 13) % 3) - 1;
  const acc2 = applyArith(fmt, "add", acc, t) as number;
  return pass0BitnetDot(fmt, opaque(n - 1), acc2);
}

// ── Pass 1 — specialized handler closures from the FormatTable cache ──
//
// The FormatTable.handler(h, op) compiles per-(format, op) closures via
// `new Function` whose body is exactly the right operator for that
// format. V8 JITs them like any user code. The bench drives them
// through function pointers — the cost is a typed indirect call per
// op, no dispatch, no boxing.

function pass1Sum(
  add: (a: Numberish, b: Numberish) => Numberish,
  mul: (a: Numberish, b: Numberish) => Numberish,
  n: number,
  acc: number,
  scale: number,
): number {
  if (n === 0) return acc;
  const x = mul(n, scale) as number;
  const acc2 = add(acc, x) as number;
  return pass1Sum(add, mul, opaque(n - 1), acc2, scale);
}

function pass1BitnetDot(
  add: (a: Numberish, b: Numberish) => Numberish,
  n: number,
  acc: number,
): number {
  if (n === 0) return acc;
  const t = ((n * 13) % 3) - 1;
  const acc2 = add(acc, t) as number;
  return pass1BitnetDot(add, opaque(n - 1), acc2);
}

// ── Pass 2 — recipe-driven JS code generation ────────────────────────────
//
// Generic emitter: given a format-recipe, emit a JS expression for
// each arithmetic op. The same emitter produces native-fp code for FP64,
// fround-wrapped code for FP8 (table-lookup-via-fp32), and |0 code for
// BitNet (native-int). The recipe drives the emit — no hardcoded
// per-workload source strings.
//
// This is the load-bearing architectural property: the kernel/compiler
// stays format-blind; format-recipes carry the codegen rules; new
// formats become new substrate writes, not compiler patches.

function emitOpExpr(fmt: FormatRecipe, op: ArithOp, aSrc: string, bSrc: string): string {
  switch (fmt.arithHintCode) {
    case ArithHintCode.NATIVE_FP:
      return `(${aSrc} ${jsOp(op)} ${bSrc})`;
    case ArithHintCode.NATIVE_INT:
      if (op === "mul") return `Math.imul(${aSrc}|0, ${bSrc}|0)`;
      return `(((${aSrc}) ${jsOp(op)} (${bSrc})) | 0)`;
    case ArithHintCode.NATIVE_INT_NARROW:
      if (op === "mul")
        return `(((${aSrc}|0) * (${bSrc}|0)) << ${32 - fmt.bits} >> ${32 - fmt.bits})`;
      return `((((${aSrc}) ${jsOp(op)} (${bSrc})) << ${32 - fmt.bits}) >> ${32 - fmt.bits})`;
    case ArithHintCode.BIGINT:
      return `(BigInt(${aSrc}) ${jsOp(op)} BigInt(${bSrc}))`;
    case ArithHintCode.TABLE_LOOKUP_VIA_FP32:
    case ArithHintCode.DEQUANT_FP32_THEN_NATIVE:
    case ArithHintCode.SOFTWARE_FP_VIA_FP32:
      return `Math.fround((${aSrc}) ${jsOp(op)} (${bSrc}))`;
    case ArithHintCode.LOGADDEXP_LOGSUBEXP:
      // multiplication in log-space is addition; for the bench we only
      // exercise add — emit logaddexp inline.
      if (op === "add") {
        return `((function(){var _a=(${aSrc}),_b=(${bSrc});var m=Math.max(_a,_b);return m+Math.log1p(Math.exp(-Math.abs(_a-_b)));})())`;
      }
      if (op === "mul") return `((${aSrc}) + (${bSrc}))`;
      return `((${aSrc}) - (${bSrc}))`;
    case ArithHintCode.XOR_POPCOUNT:
      if (op === "add" || op === "sub") return `(((${aSrc}) ^ (${bSrc})) & 1)`;
      if (op === "mul") return `((${aSrc}) & (${bSrc}) & 1)`;
      return `0`;
    default:
      throw new Error(`emit: arith-hint ${fmt.arithmeticHint} not supported`);
  }
}

function jsOp(op: ArithOp): string {
  return op === "add" ? "+" : op === "sub" ? "-" : op === "mul" ? "*"
    : op === "div" ? "/" : "%";
}

// compileSum — for any format, emit a JS function computing
// sum_{i=1..n} (i * scale).
function compileSum(fmt: FormatRecipe): (n: number, acc: number) => number {
  const mulSrc = emitOpExpr(fmt, "mul", "n", "scale");
  const addSrc = emitOpExpr(fmt, "add", "acc", "x");
  const src = `
    return function f(n, acc) {
      if (n === 0) return acc;
      var x = ${mulSrc};
      return f(opaque(n - 1), ${addSrc});
    };
  `;
  return new Function("opaque", "scale", src)(opaque, /*scale placeholder*/ 0) as (
    n: number,
    acc: number,
  ) => number;
}

// compileSumWithScale — bind a scale value into the compiled fn's closure.
function compileSumWithScale(
  fmt: FormatRecipe,
  scale: number,
): (n: number, acc: number) => number {
  const mulSrc = emitOpExpr(fmt, "mul", "n", String(scale));
  const addSrc = emitOpExpr(fmt, "add", "acc", "x");
  const src = `
    return function f(n, acc) {
      if (n === 0) return acc;
      var x = ${mulSrc};
      return f(opaque(n - 1), ${addSrc});
    };
  `;
  return new Function("opaque", src)(opaque) as (n: number, acc: number) => number;
}

// compileBitnetDot — emit a sum-accumulator that reads {-1, 0, 1} per i.
function compileBitnetDot(fmt: FormatRecipe): (n: number, acc: number) => number {
  const tExpr = "(((n * 13) % 3) - 1)";
  const addSrc = emitOpExpr(fmt, "add", "acc", "t");
  const src = `
    return function f(n, acc) {
      if (n === 0) return acc;
      var t = ${tExpr};
      return f(opaque(n - 1), ${addSrc});
    };
  `;
  return new Function("opaque", src)(opaque) as (n: number, acc: number) => number;
}

interface Pass2Fns {
  fp64Sum: (n: number, acc: number) => number;
  fp8Sum: (n: number, acc: number) => number;
  bitnetDot: (n: number, acc: number) => number;
}

function buildPass2(
  fp64: FormatRecipe,
  fp8: FormatRecipe,
  bitnet: FormatRecipe,
): Pass2Fns {
  return {
    fp64Sum: compileSumWithScale(fp64, 0.5),
    fp8Sum: compileSumWithScale(fp8, 0.0625),
    bitnetDot: compileBitnetDot(bitnet),
  };
}

// ── Driver ──────────────────────────────────────────────────────────────

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

interface Row {
  workload: string;
  native: bigint;
  pass0: bigint;
  pass1: bigint;
  pass2: bigint;
}

function runRow(
  name: string,
  native: () => void,
  nativeIters: number,
  pass0: () => void,
  pass0Iters: number,
  pass1: () => void,
  pass1Iters: number,
  pass2: () => void,
  pass2Iters: number,
): Row {
  // Warmup
  native();
  pass0();
  pass1();
  pass2();

  const nNs = timeNs(() => {
    for (let i = 0; i < nativeIters; i++) native();
  }) / BigInt(nativeIters);

  const p0Ns = timeNs(() => {
    for (let i = 0; i < pass0Iters; i++) pass0();
  }) / BigInt(pass0Iters);

  const p1Ns = timeNs(() => {
    for (let i = 0; i < pass1Iters; i++) pass1();
  }) / BigInt(pass1Iters);

  const p2Ns = timeNs(() => {
    for (let i = 0; i < pass2Iters; i++) pass2();
  }) / BigInt(pass2Iters);

  return { workload: name, native: nNs, pass0: p0Ns, pass1: p1Ns, pass2: p2Ns };
}

export function runNumericBench(): void {
  const k = new Kernel();
  const lib = buildFormatLibrary(k);
  const formats = new FormatTable();
  registerFormats(formats, lib);

  const fp64 = lib.FP64;
  const fp8 = lib.FP8_E4M3;
  const bitnet = lib.BITNET_158;

  // Pass 1 — pre-fetch the specialized handler closures.
  const fp64Add = formats.handler(formats.register(fp64), "add");
  const fp64Mul = formats.handler(formats.register(fp64), "mul");
  const fp8Add = formats.handler(formats.register(fp8), "add");
  const fp8Mul = formats.handler(formats.register(fp8), "mul");
  const bitnetAdd = formats.handler(formats.register(bitnet), "add");

  const p2 = buildPass2(fp64, fp8, bitnet);

  // Run sizes — picked so each path is measurable.
  const N = 1000;

  const rowFp64 = runRow(
    "fp64",
    () => { nativeFp64Sum(N, 0); }, 50_000,
    () => { pass0Fp64Sum(fp64, N, 0); }, 1_000,
    () => { pass1Sum(fp64Add, fp64Mul, N, 0, 0.5); }, 50_000,
    () => { p2.fp64Sum(N, 0); }, 50_000,
  );

  const rowFp8 = runRow(
    "fp8",
    () => { nativeFp8Sum(N, 0); }, 50_000,
    () => { pass0Fp8Sum(fp8, N, 0); }, 1_000,
    () => { pass1Sum(fp8Add, fp8Mul, N, 0, 0.0625); }, 50_000,
    () => { p2.fp8Sum(N, 0); }, 50_000,
  );

  const rowBitnet = runRow(
    "bitnet",
    () => { nativeBitnetDot(N, 0); }, 50_000,
    () => { pass0BitnetDot(bitnet, N, 0); }, 1_000,
    () => { pass1BitnetDot(bitnetAdd, N, 0); }, 50_000,
    () => { p2.bitnetDot(N, 0); }, 50_000,
  );

  const rows = [rowFp64, rowFp8, rowBitnet];

  console.log(
    `${"format".padEnd(10)} ${"native".padEnd(12)} ${"pass0(naïve)".padEnd(14)} ${"p0-over".padEnd(8)} ${"pass1(cached)".padEnd(15)} ${"p1-over".padEnd(8)} ${"pass2(JIT)".padEnd(12)} ${"p2-over"}`,
  );
  for (const r of rows) {
    const p0Over = Number(r.pass0) / Number(r.native);
    const p1Over = Number(r.pass1) / Number(r.native);
    const p2Over = Number(r.pass2) / Number(r.native);
    console.log(
      `${r.workload.padEnd(10)} ${formatNs(r.native).padEnd(12)} ${formatNs(r.pass0).padEnd(14)} ${(p0Over.toFixed(0) + "×").padEnd(8)} ${formatNs(r.pass1).padEnd(15)} ${(p1Over.toFixed(0) + "×").padEnd(8)} ${formatNs(r.pass2).padEnd(12)} ${p2Over.toFixed(1)}×`,
    );
  }
}

if (import.meta.url === `file://${process.argv[1]}` && import.meta.url.includes("numeric-bench")) {
  runNumericBench();
}
