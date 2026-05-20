// numeric.ts — generic numeric leaf interface, format-recipe driven.
//
// A numeric value is a NodeID whose level=BASIC, type=RBasicNumeric,
// and inst encodes:
//   - the format-recipe handle (small int, looked up in the kernel's
//     format-table) in the upper 16 bits
//   - the inline-value-handle in the lower 16 bits (for values that
//     fit; larger values become a single child carrying encoded bits)
//
// This is Tier 1 — format-recipe-driven. Tier 0 (existing INT, FP64
// trivials) remains as a fast-path alias for hot formats; nothing
// here forces removing them.

import { Kernel, Level, type NodeID } from "./kernel.ts";
import {
  applyArith,
  ArithHintCode,
  canonicalize,
  type ArithOp,
  type FormatLibrary,
  type FormatRecipe,
  type Numberish,
} from "./formats.ts";

// RBasic.NUMERIC — a new well-known RBasic category for format-recipe-
// driven numeric leaves. Distinct from RBasic.MATH (operations); this
// is for VALUES carrying a format identity.
export const RBasicNumeric = 51;

// Format-handle assignment. The kernel keeps a sequential table of
// format-recipes; each registered format gets an integer handle.
// Cross-kernel agreement requires the handle order to be deterministic
// per the canonical bootstrap library.
export class FormatTable {
  private byHandle: FormatRecipe[] = [];
  private byNodeID = new Map<string, number>();

  register(fmt: FormatRecipe): number {
    const key = `${fmt.nodeID.pkg}.${fmt.nodeID.level}.${fmt.nodeID.type}.${fmt.nodeID.inst}`;
    const existing = this.byNodeID.get(key);
    if (existing !== undefined) return existing;
    const h = this.byHandle.length;
    this.byHandle.push(fmt);
    this.byNodeID.set(key, h);
    return h;
  }

  get(h: number): FormatRecipe | undefined {
    return this.byHandle[h];
  }

  // Cache: format-handle → (op, ArithOp) → compiled (a, b) => result.
  // Populated lazily on first use; subsequent ops hit the cache.
  // The cache is the Pass 1 efficiency optimization — monomorphizes
  // dispatch from "read format-recipe, branch on arithmetic-hint" to
  // "lookup compiled handler".
  private handlers = new Map<string, (a: Numberish, b: Numberish) => Numberish>();

  // handler — Pass 1 efficiency optimization.
  //
  // For each (format, op) combination, generate a specialized closure
  // via `new Function` that contains ONLY the relevant arithmetic. No
  // dispatch on hint or op inside the closure; V8 JITs it to the same
  // machine code a direct JS operator would produce.
  //
  // Cold path: emits source, eval-compiles via `new Function`. ~µs once.
  // Hot path: direct closure call, inlined.
  //
  // This is what makes the format-recipe architecture pay no runtime
  // tax. Format-recipes carry the codegen rules; the cache materializes
  // them as JIT'd closures the first time they're asked for.
  handler(
    h: number,
    op: ArithOp,
  ): (a: Numberish, b: Numberish) => Numberish {
    const key = `${h}:${op}`;
    const cached = this.handlers.get(key);
    if (cached) return cached;
    const fmt = this.byHandle[h];
    if (!fmt) throw new Error(`unknown format-handle ${h}`);
    const fn = compileHandler(fmt, op);
    this.handlers.set(key, fn);
    return fn;
  }
}

// compileHandler — emit a per-(format, op) JS closure. The body is the
// format's arithmetic-hint specialized to just this op.
function compileHandler(
  fmt: FormatRecipe,
  op: ArithOp,
): (a: Numberish, b: Numberish) => Numberish {
  const body = arithBody(fmt, op);
  // Build a closure via `new Function` so V8 sees specialized JS code
  // rather than a generic dispatcher.
  return new Function("a", "b", body) as (
    a: Numberish,
    b: Numberish,
  ) => Numberish;
}

function arithBody(fmt: FormatRecipe, op: ArithOp): string {
  switch (fmt.arithHintCode) {
    case ArithHintCode.NATIVE_FP: {
      const opStr = jsBinop(op);
      if (op === "mod") return `return a - Math.floor(a / b) * b;`;
      return `return (+a) ${opStr} (+b);`;
    }
    case ArithHintCode.NATIVE_INT: {
      if (op === "mul") return `return Math.imul(a | 0, b | 0);`;
      const opStr = jsBinop(op);
      if (op === "div") return `return b === 0 ? 0 : ((a | 0) / (b | 0)) | 0;`;
      if (op === "mod")
        return `return b === 0 ? 0 : (a | 0) - (((a | 0) / (b | 0)) | 0) * (b | 0);`;
      return `return ((a | 0) ${opStr} (b | 0)) | 0;`;
    }
    case ArithHintCode.NATIVE_INT_NARROW: {
      const shift = 32 - fmt.bits;
      if (op === "mul")
        return `return ((Math.imul(a | 0, b | 0)) << ${shift}) >> ${shift};`;
      const opStr = jsBinop(op);
      return `return (((a | 0) ${opStr} (b | 0)) << ${shift}) >> ${shift};`;
    }
    case ArithHintCode.BIGINT: {
      const opStr = jsBinop(op);
      return `return (typeof a === "bigint" ? a : BigInt(a)) ${opStr} (typeof b === "bigint" ? b : BigInt(b));`;
    }
    case ArithHintCode.TABLE_LOOKUP_VIA_FP32:
    case ArithHintCode.DEQUANT_FP32_THEN_NATIVE:
    case ArithHintCode.SOFTWARE_FP_VIA_FP32: {
      if (op === "mod") return `return Math.fround(a - Math.floor(a / b) * b);`;
      const opStr = jsBinop(op);
      return `return Math.fround((+a) ${opStr} (+b));`;
    }
    case ArithHintCode.LOGADDEXP_LOGSUBEXP:
      if (op === "add")
        return `var m = Math.max(+a, +b); return m + Math.log1p(Math.exp(-Math.abs((+a) - (+b))));`;
      if (op === "mul") return `return (+a) + (+b);`;
      if (op === "div") return `return (+a) - (+b);`;
      if (op === "sub")
        return `if ((+b) >= (+a)) return -Infinity; return (+a) + Math.log1p(-Math.exp((+b) - (+a)));`;
      return `throw new Error("log-prob: op not defined");`;
    case ArithHintCode.XOR_POPCOUNT:
      if (op === "add" || op === "sub") return `return ((a | 0) ^ (b | 0)) & 1;`;
      if (op === "mul") return `return (a | 0) & (b | 0) & 1;`;
      return `return 0;`;
    default:
      throw new Error(
        `compileHandler: arithmetic-hint code ${fmt.arithHintCode} unsupported`,
      );
  }
}

function jsBinop(op: ArithOp): string {
  return op === "add" ? "+" : op === "sub" ? "-" : op === "mul" ? "*"
    : op === "div" ? "/" : "%";
}

// Encode a numeric leaf NodeID. For values that fit in 16 bits, inline;
// otherwise the value lives as a single child trivial.
export function internNumeric(
  k: Kernel,
  formats: FormatTable,
  fmt: FormatRecipe,
  rawValue: Numberish,
): NodeID {
  const handle = formats.register(fmt);
  const canonical = canonicalize(fmt, rawValue);

  // For inline-fitting integer-like values in formats ≤16 bits with
  // simple integer encoding, encode value into inst's lower 16 bits.
  // For larger / float values, route through a child trivial.
  if (
    fmt.bits <= 16 &&
    fmt.arithmeticHint === "native-int" &&
    typeof canonical === "number" &&
    Number.isInteger(canonical) &&
    canonical >= -32768 && canonical <= 32767
  ) {
    const inst = ((handle & 0xffff) << 16) | (canonical & 0xffff);
    return {
      pkg: 1,
      level: Level.BASIC,
      type: RBasicNumeric,
      inst,
    };
  }

  // General path: composite with one child carrying the encoded value
  // through the substrate's number/string overflow mechanisms.
  const valueRecipe = encodeOverflowValue(k, fmt, canonical);
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasicNumeric, inst: handle },
    [valueRecipe],
  );
}

// Encode a value into a substrate leaf that the kernel can decode
// without knowing the format. For doubles, route through the f64
// overflow table; for bigints, through i64. The encoding is opaque
// to the substrate — the format-recipe's storage-hint tells the
// decoder how to interpret it.
function encodeOverflowValue(
  k: Kernel,
  fmt: FormatRecipe,
  v: Numberish,
): NodeID {
  if (typeof v === "bigint") return k.internTrivialInt64(v);
  // Use the f64 overflow table for any float-shaped value.
  return k.internTrivialFloat64(v);
}

export function decodeNumeric(
  k: Kernel,
  formats: FormatTable,
  n: NodeID,
): { fmt: FormatRecipe; value: Numberish } {
  if (n.type !== RBasicNumeric) {
    throw new Error(`decodeNumeric: not a numeric NodeID: ${n.type}`);
  }
  // Inline encoding? Lower 16 bits are the value, upper 16 are the
  // format-handle.
  // Detection: inline values carry a 16-bit value range; we use a flag
  // bit by convention — but for v0 we differentiate by whether the
  // NodeID is composite (has children in byID) or not.
  const recipe = k.byID.get(`${n.pkg}.${n.level}.${n.type}.${n.inst}`);
  if (!recipe) {
    // Inline path
    const handle = (n.inst >>> 16) & 0xffff;
    const u16 = n.inst & 0xffff;
    const value = u16 & 0x8000 ? u16 - 0x10000 : u16;
    const fmt = formats.get(handle);
    if (!fmt) throw new Error(`inline numeric: unknown handle ${handle}`);
    return { fmt, value };
  }
  // Composite path
  const handle = n.inst;
  const fmt = formats.get(handle);
  if (!fmt) throw new Error(`numeric: unknown format-handle ${handle}`);
  const valueChild = recipe.children[0];
  if (!valueChild) throw new Error("numeric composite: no value child");
  // Decode the value child through the kernel's trivial decoder.
  const tv = k.trivialValue(valueChild);
  let value: Numberish;
  if (tv.kind === "f64" || tv.kind === "f32") value = tv.float;
  else if (tv.kind === "i64" || tv.kind === "u64") value = tv.bigint;
  else if (
    tv.kind === "int" ||
    tv.kind === "i8" || tv.kind === "i16" ||
    tv.kind === "u8" || tv.kind === "u16" || tv.kind === "u32"
  )
    value = tv.int;
  else throw new Error(`numeric composite: unsupported value kind ${tv.kind}`);
  return { fmt, value };
}

// applyMath — invoke arithmetic through the format-handler cache.
// This is the Pass 1 hot-path optimization. After Pass 2, the
// compiler emits direct calls bypassing this dispatcher for known
// formats; Pass 1 path remains for the walker and unknown formats.
export function applyMath(
  formats: FormatTable,
  fmt: FormatRecipe,
  op: ArithOp,
  a: Numberish,
  b: Numberish,
): Numberish {
  const handle = formats.register(fmt);
  return formats.handler(handle, op)(a, b);
}

// Format-library helper: register all canonical formats into the table
// so they can be referenced by handle.
export function registerFormats(table: FormatTable, lib: FormatLibrary): void {
  for (const fmt of Object.values(lib)) {
    table.register(fmt);
  }
}
