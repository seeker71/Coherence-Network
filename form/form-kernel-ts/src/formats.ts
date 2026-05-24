// formats.ts — substrate-resident numeric format library.
//
// Each format is a structural recipe describing semantic-kind, bit-width,
// encoding rules, and implementation hints (storage + arithmetic). The
// kernel reads these recipes at runtime; the compiler reads them at
// compile time to emit specialized code. No format hardcoded in the
// kernel's switch statements — they all live here as data.
//
// See docs/coherence-substrate/numeric-types-plan.md for the architecture.

import {
  Kernel,
  Level,
  RBasic,
  type NodeID,
} from "./kernel.ts";

// SemanticKind — the small stable vocabulary describing what a number
// MEANS (not how it's encoded). Used by promotion rules and unit
// systems; never hardcoded in arithmetic.
export const SemanticKind = {
  CARDINAL: 1,
  INTEGER: 2,
  RATIONAL: 3,
  REAL: 4,
  COMPLEX: 5,
  BIT_PATTERN: 6,
  LOG_VALUE: 7,
  PROBABILITY: 8,
  INTERVAL: 9,
  ORDINAL: 10,
  AMPLITUDE: 11,
  PHASE: 12,
  MEASURE: 13,
} as const;

// EncodingKind — the encoding family. Each kind has its own parameter
// shape carried in the format-recipe's children.
export const EncodingKind = {
  TWOS_COMPLEMENT: 1,
  SIGN_MAGNITUDE: 2,
  UNSIGNED: 3,
  IEEE_754: 4,
  POSIT: 5,
  LOOKUP_TABLE: 6,
  BLOCK_FP: 7,
  LOG_SPACE: 8,
  RATIONAL_PAIR: 9,
  COMPLEX_PAIR: 10,
  RAW_BITS: 11,
} as const;

// StorageHint — strings the kernel and compiler dispatch off. Adding
// a new storage strategy = adding a new string here + a handler.
export type StorageHint =
  | "v8-double" // raw JS number, V8 stores as smi or double
  | "v8-double-narrowed" // JS number with Math.fround narrowing per op
  | "i32-smi" // i32 in JS number, V8 keeps SMI
  | "bigint" // JS BigInt
  | "u8-array" // packed into Uint8Array slot
  | "u16-array"
  | "u32-array"
  | "nibble-packed" // 4 bits in a u8 slot
  | "crumb-packed" // 2 bits in a u8 slot
  | "bitfield" // 1 bit per value
  | "pair-of-bigints"; // for rationals

export type ArithmeticHint =
  | "native-fp" // JS + - * / on Number
  | "native-int" // | 0 chains + Math.imul
  | "native-int-narrow" // native-int with explicit clamp
  | "bigint" // BigInt operators
  | "table-lookup-via-fp32" // dequant to fp32, op in fp32, requant
  | "dequant-fp32-then-native" // dequant once, then native, no requant
  | "software-fp-via-fp32" // narrow ieee-754 in software, fp32 accumulator
  | "software-posit"
  | "xor-popcount" // 1-bit Boolean network ops
  | "logaddexp-logsubexp" // log-space probability
  | "rational-bigint"; // numerator/denominator BigInts

// ArithHintCode — Pass 1 efficiency. The arithmetic-hint string is
// projected to a small int once at format-recipe creation, so the hot
// path switches on a u8 instead of a string. V8 turns this into a
// jump table; no string-equality comparisons in the inner loop.
export const ArithHintCode = {
  NATIVE_FP: 1,
  NATIVE_INT: 2,
  NATIVE_INT_NARROW: 3,
  BIGINT: 4,
  TABLE_LOOKUP_VIA_FP32: 5,
  DEQUANT_FP32_THEN_NATIVE: 6,
  SOFTWARE_FP_VIA_FP32: 7,
  SOFTWARE_POSIT: 8,
  XOR_POPCOUNT: 9,
  LOGADDEXP_LOGSUBEXP: 10,
  RATIONAL_BIGINT: 11,
} as const;

const HINT_TO_CODE: Record<ArithmeticHint, number> = {
  "native-fp": ArithHintCode.NATIVE_FP,
  "native-int": ArithHintCode.NATIVE_INT,
  "native-int-narrow": ArithHintCode.NATIVE_INT_NARROW,
  "bigint": ArithHintCode.BIGINT,
  "table-lookup-via-fp32": ArithHintCode.TABLE_LOOKUP_VIA_FP32,
  "dequant-fp32-then-native": ArithHintCode.DEQUANT_FP32_THEN_NATIVE,
  "software-fp-via-fp32": ArithHintCode.SOFTWARE_FP_VIA_FP32,
  "software-posit": ArithHintCode.SOFTWARE_POSIT,
  "xor-popcount": ArithHintCode.XOR_POPCOUNT,
  "logaddexp-logsubexp": ArithHintCode.LOGADDEXP_LOGSUBEXP,
  "rational-bigint": ArithHintCode.RATIONAL_BIGINT,
};

export const ArithOpCode = {
  ADD: 1,
  SUB: 2,
  MUL: 3,
  DIV: 4,
  MOD: 5,
} as const;

const OP_TO_CODE: Record<ArithOp, number> = {
  add: ArithOpCode.ADD,
  sub: ArithOpCode.SUB,
  mul: ArithOpCode.MUL,
  div: ArithOpCode.DIV,
  mod: ArithOpCode.MOD,
};

export function opCode(op: ArithOp): number {
  return OP_TO_CODE[op];
}

// FormatRecipe — the structural identity of a format. Stored as a
// substrate recipe; the values here mirror the recipe's children for
// fast in-kernel access without re-reading the tree on every op.
export interface FormatRecipe {
  readonly nodeID: NodeID;
  readonly name: string; // canonical name for diagnostics + cell binding
  readonly semanticKind: number;
  readonly encoding: number;
  readonly bits: number; // 0 = unbounded (rational, bigint)
  readonly storageHint: StorageHint;
  readonly arithmeticHint: ArithmeticHint;
  readonly arithHintCode: number; // ← Pass 1: pre-projected for jump-table dispatch
  // Encoding-specific parameters
  readonly mantissaBits?: number; // IEEE 754
  readonly exponentBits?: number;
  readonly exponentBias?: number;
  readonly lookupValues?: readonly number[]; // NF4, BitNet, FP4-lookup
  readonly positN?: number; // posit
  readonly positEs?: number;
}

// FORMAT category — a new RBasic slot for format-recipes. Format-
// recipes are composite recipes whose category is RBasic.FORMAT and
// whose instance carries the EncodingKind. Children describe the
// encoding parameters. Two recipes with identical structure share
// NodeID via content-addressing.
//
// Aligned with the plan doc; cross-kernel agreement requires every
// implementation to use the same category numbering.
export const RBasicFormat = 50; // new well-known RBasic category

// NUMERIC trivial type — Tier 1 path. A numeric value's NodeID is
//   (TRIVIAL, NUMERIC, inst=format-recipe-id × VALUES_PER_FORMAT + value-index)
// for inline-fittable values, or a composite when the value can't fit
// inline. The Tier 0 fast slots (existing INT, FP64) remain as
// aliases for hot paths; nothing in this library forces their removal.

// ---------------------------------------------------------------------------
// Bootstrap format library — interned once per kernel instance.
// Cross-kernel agreement comes from interning the SAME tree structure.
// ---------------------------------------------------------------------------

function makeFormatRecipe(
  k: Kernel,
  name: string,
  semanticKind: number,
  encoding: number,
  bits: number,
  storageHint: StorageHint,
  arithmeticHint: ArithmeticHint,
  extras: Partial<FormatRecipe> = {},
): FormatRecipe {
  // The recipe's NodeID is computed via content-addressing over the
  // (encoding, child-vector) shape. Children encode the parameters as
  // trivial integers — same parameters always intern to same NodeID.
  const children: NodeID[] = [
    k.internTrivialInt(semanticKind),
    k.internTrivialInt(encoding),
    k.internTrivialInt(bits),
    k.internString(storageHint),
    k.internString(arithmeticHint),
  ];
  // Optional extras: pack into the children list for content-addressing.
  if (extras.mantissaBits !== undefined)
    children.push(k.internTrivialInt(extras.mantissaBits));
  if (extras.exponentBits !== undefined)
    children.push(k.internTrivialInt(extras.exponentBits));
  if (extras.exponentBias !== undefined)
    children.push(k.internTrivialInt(extras.exponentBias));
  if (extras.positN !== undefined) children.push(k.internTrivialInt(extras.positN));
  if (extras.positEs !== undefined)
    children.push(k.internTrivialInt(extras.positEs));
  if (extras.lookupValues !== undefined) {
    // Lookup values — interned as a list of FP64s (which themselves intern
    // via the FP64 format's path, but since this is bootstrap, we hash
    // their bit patterns directly into trivials for stable identity).
    for (const v of extras.lookupValues) {
      const buf = new ArrayBuffer(8);
      new Float64Array(buf)[0] = v;
      // Store both 32-bit halves so identity is deterministic across hosts.
      children.push(k.internTrivialInt(new Uint32Array(buf)[0]! | 0));
      children.push(k.internTrivialInt(new Uint32Array(buf)[1]! | 0));
    }
  }
  const nodeID = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasicFormat, inst: encoding },
    children,
  );
  return {
    nodeID,
    name,
    semanticKind,
    encoding,
    bits,
    storageHint,
    arithmeticHint,
    arithHintCode: HINT_TO_CODE[arithmeticHint],
    ...extras,
  };
}

// FormatLibrary — the canonical bootstrap set, interned at kernel
// startup. New formats can be added as substrate writes by Form code;
// they don't need to be in this list.
export interface FormatLibrary {
  // ── REALs ────────────────────────────────────────────────────────
  FP64: FormatRecipe;
  FP32: FormatRecipe;
  BF16: FormatRecipe;
  FP8_E4M3: FormatRecipe;
  FP8_E5M2: FormatRecipe;
  FP4_UNIFORM: FormatRecipe;
  NF4: FormatRecipe;
  // ── INTEGERs ─────────────────────────────────────────────────────
  INT8: FormatRecipe;
  INT16: FormatRecipe;
  INT32: FormatRecipe;
  INT64: FormatRecipe;
  UINT8: FormatRecipe;
  UINT16: FormatRecipe;
  UINT32: FormatRecipe;
  UINT64: FormatRecipe;
  INT4: FormatRecipe;
  // ── Ternary, binary, exotic ──────────────────────────────────────
  BITNET_158: FormatRecipe;
  BIT_1: FormatRecipe;
  // ── Probability / log-space ─────────────────────────────────────
  LOG_PROB: FormatRecipe;
}

// NF4 normalized-float-4 quantile lookup table — used in QLoRA and
// other 4-bit weight quantization. Sixteen distinguishable values
// chosen to match a normal distribution's quantiles.
const NF4_VALUES = [
  -1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
  -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
  0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
  0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
  0.7229568362236023, 1.0,
];

export function buildFormatLibrary(k: Kernel): FormatLibrary {
  return {
    FP64: makeFormatRecipe(
      k, "fp64", SemanticKind.REAL, EncodingKind.IEEE_754, 64,
      "v8-double", "native-fp",
      { mantissaBits: 52, exponentBits: 11, exponentBias: 1023 },
    ),
    FP32: makeFormatRecipe(
      k, "fp32", SemanticKind.REAL, EncodingKind.IEEE_754, 32,
      "v8-double-narrowed", "native-fp",
      { mantissaBits: 23, exponentBits: 8, exponentBias: 127 },
    ),
    BF16: makeFormatRecipe(
      k, "bf16", SemanticKind.REAL, EncodingKind.IEEE_754, 16,
      "u16-array", "software-fp-via-fp32",
      { mantissaBits: 7, exponentBits: 8, exponentBias: 127 },
    ),
    FP8_E4M3: makeFormatRecipe(
      k, "fp8-e4m3", SemanticKind.REAL, EncodingKind.IEEE_754, 8,
      "u8-array", "table-lookup-via-fp32",
      { mantissaBits: 3, exponentBits: 4, exponentBias: 7 },
    ),
    FP8_E5M2: makeFormatRecipe(
      k, "fp8-e5m2", SemanticKind.REAL, EncodingKind.IEEE_754, 8,
      "u8-array", "table-lookup-via-fp32",
      { mantissaBits: 2, exponentBits: 5, exponentBias: 15 },
    ),
    FP4_UNIFORM: makeFormatRecipe(
      k, "fp4-uniform", SemanticKind.REAL, EncodingKind.IEEE_754, 4,
      "nibble-packed", "table-lookup-via-fp32",
      { mantissaBits: 2, exponentBits: 1, exponentBias: 1 },
    ),
    NF4: makeFormatRecipe(
      k, "nf4", SemanticKind.REAL, EncodingKind.LOOKUP_TABLE, 4,
      "nibble-packed", "dequant-fp32-then-native",
      { lookupValues: NF4_VALUES },
    ),
    INT8: makeFormatRecipe(
      k, "i8", SemanticKind.INTEGER, EncodingKind.TWOS_COMPLEMENT, 8,
      "i32-smi", "native-int-narrow",
    ),
    INT16: makeFormatRecipe(
      k, "i16", SemanticKind.INTEGER, EncodingKind.TWOS_COMPLEMENT, 16,
      "i32-smi", "native-int-narrow",
    ),
    INT32: makeFormatRecipe(
      k, "i32", SemanticKind.INTEGER, EncodingKind.TWOS_COMPLEMENT, 32,
      "i32-smi", "native-int",
    ),
    INT64: makeFormatRecipe(
      k, "i64", SemanticKind.INTEGER, EncodingKind.TWOS_COMPLEMENT, 64,
      "bigint", "bigint",
    ),
    UINT8: makeFormatRecipe(
      k, "u8", SemanticKind.CARDINAL, EncodingKind.UNSIGNED, 8,
      "i32-smi", "native-int-narrow",
    ),
    UINT16: makeFormatRecipe(
      k, "u16", SemanticKind.CARDINAL, EncodingKind.UNSIGNED, 16,
      "i32-smi", "native-int-narrow",
    ),
    UINT32: makeFormatRecipe(
      k, "u32", SemanticKind.CARDINAL, EncodingKind.UNSIGNED, 32,
      "i32-smi", "native-int",
    ),
    UINT64: makeFormatRecipe(
      k, "u64", SemanticKind.CARDINAL, EncodingKind.UNSIGNED, 64,
      "bigint", "bigint",
    ),
    INT4: makeFormatRecipe(
      k, "i4", SemanticKind.INTEGER, EncodingKind.TWOS_COMPLEMENT, 4,
      "nibble-packed", "native-int-narrow",
    ),
    BITNET_158: makeFormatRecipe(
      k, "bitnet-158", SemanticKind.INTEGER, EncodingKind.LOOKUP_TABLE, 2,
      "crumb-packed", "native-int",
      { lookupValues: [-1, 0, 1] },
    ),
    BIT_1: makeFormatRecipe(
      k, "bit-1", SemanticKind.BIT_PATTERN, EncodingKind.RAW_BITS, 1,
      "bitfield", "xor-popcount",
    ),
    LOG_PROB: makeFormatRecipe(
      k, "log-prob", SemanticKind.PROBABILITY, EncodingKind.LOG_SPACE, 64,
      "v8-double", "logaddexp-logsubexp",
    ),
  };
}

// ---------------------------------------------------------------------------
// Arithmetic handler — driven by arithmetic-hint.
// ---------------------------------------------------------------------------

// One arithmetic operator, per format. Returns the raw computed value
// in the format's native storage representation (number, bigint, etc.).
export type ArithOp = "add" | "sub" | "mul" | "div" | "mod";

export type Numberish = number | bigint;

// applyArith — dispatch on integer hint+op codes. V8 turns the outer
// switch on small consecutive ints into a flat jump table; no string
// comparisons in the hot path.
export function applyArith(
  fmt: FormatRecipe,
  op: ArithOp,
  a: Numberish,
  b: Numberish,
): Numberish {
  return applyArithCode(fmt, OP_TO_CODE[op], a, b);
}

export function applyArithCode(
  fmt: FormatRecipe,
  opc: number,
  a: Numberish,
  b: Numberish,
): Numberish {
  switch (fmt.arithHintCode) {
    case ArithHintCode.NATIVE_FP: {
      const fa = Number(a);
      const fb = Number(b);
      switch (opc) {
        case ArithOpCode.ADD: return fa + fb;
        case ArithOpCode.SUB: return fa - fb;
        case ArithOpCode.MUL: return fa * fb;
        case ArithOpCode.DIV: return fa / fb;
        case ArithOpCode.MOD: return fa - Math.floor(fa / fb) * fb;
      }
      return 0;
    }
    case ArithHintCode.NATIVE_INT: {
      const ia = Number(a) | 0;
      const ib = Number(b) | 0;
      switch (opc) {
        case ArithOpCode.ADD: return (ia + ib) | 0;
        case ArithOpCode.SUB: return (ia - ib) | 0;
        case ArithOpCode.MUL: return Math.imul(ia, ib);
        case ArithOpCode.DIV: return ib === 0 ? 0 : (ia / ib) | 0;
        case ArithOpCode.MOD: return ib === 0 ? 0 : ia - ((ia / ib) | 0) * ib;
      }
      return 0;
    }
    case ArithHintCode.NATIVE_INT_NARROW: {
      const ia = Number(a) | 0;
      const ib = Number(b) | 0;
      const bits = fmt.bits;
      switch (opc) {
        case ArithOpCode.ADD: return narrowInt((ia + ib) | 0, bits);
        case ArithOpCode.SUB: return narrowInt((ia - ib) | 0, bits);
        case ArithOpCode.MUL: return narrowInt(Math.imul(ia, ib), bits);
        case ArithOpCode.DIV: return ib === 0 ? 0 : narrowInt((ia / ib) | 0, bits);
        case ArithOpCode.MOD: return ib === 0 ? 0 : narrowInt(ia - ((ia / ib) | 0) * ib, bits);
      }
      return 0;
    }
    case ArithHintCode.BIGINT: {
      const ba = typeof a === "bigint" ? a : BigInt(a);
      const bb = typeof b === "bigint" ? b : BigInt(b);
      switch (opc) {
        case ArithOpCode.ADD: return ba + bb;
        case ArithOpCode.SUB: return ba - bb;
        case ArithOpCode.MUL: return ba * bb;
        case ArithOpCode.DIV: return bb === 0n ? 0n : ba / bb;
        case ArithOpCode.MOD: return bb === 0n ? 0n : ba % bb;
      }
      return 0n;
    }
    case ArithHintCode.TABLE_LOOKUP_VIA_FP32:
    case ArithHintCode.DEQUANT_FP32_THEN_NATIVE:
    case ArithHintCode.SOFTWARE_FP_VIA_FP32: {
      const fa = Number(a);
      const fb = Number(b);
      switch (opc) {
        case ArithOpCode.ADD: return Math.fround(fa + fb);
        case ArithOpCode.SUB: return Math.fround(fa - fb);
        case ArithOpCode.MUL: return Math.fround(fa * fb);
        case ArithOpCode.DIV: return Math.fround(fa / fb);
        case ArithOpCode.MOD: return Math.fround(fa - Math.floor(fa / fb) * fb);
      }
      return 0;
    }
    case ArithHintCode.LOGADDEXP_LOGSUBEXP: {
      const la = Number(a);
      const lb = Number(b);
      switch (opc) {
        case ArithOpCode.ADD: {
          const m = Math.max(la, lb);
          return m + Math.log1p(Math.exp(-Math.abs(la - lb)));
        }
        case ArithOpCode.SUB: {
          if (lb >= la) return -Infinity;
          return la + Math.log1p(-Math.exp(lb - la));
        }
        case ArithOpCode.MUL: return la + lb;
        case ArithOpCode.DIV: return la - lb;
        case ArithOpCode.MOD: throw new Error("log-prob: mod not defined");
      }
      return 0;
    }
    case ArithHintCode.XOR_POPCOUNT: {
      const ia = Number(a) | 0;
      const ib = Number(b) | 0;
      switch (opc) {
        case ArithOpCode.ADD: return (ia ^ ib) & 1;
        case ArithOpCode.SUB: return (ia ^ ib) & 1;
        case ArithOpCode.MUL: return ia & ib & 1;
        case ArithOpCode.DIV:
        case ArithOpCode.MOD: return 0;
      }
      return 0;
    }
    case ArithHintCode.SOFTWARE_POSIT:
    case ArithHintCode.RATIONAL_BIGINT:
      throw new Error(
        `arithmetic-hint ${fmt.arithmeticHint}: not yet implemented`,
      );
  }
  return 0;
}

function narrowInt(v: number, bits: number): number {
  if (bits >= 32) return v | 0;
  const mask = (1 << bits) - 1;
  const signBit = 1 << (bits - 1);
  const u = v & mask;
  return (u & signBit) !== 0 ? u | ~mask : u;
}

// canonicalize — apply the format's canonical-form rules to a value
// (NaN to canonical NaN, -0 to +0, etc.).
export function canonicalize(fmt: FormatRecipe, v: Numberish): Numberish {
  if (
    fmt.arithmeticHint === "native-fp" ||
    fmt.arithmeticHint === "table-lookup-via-fp32" ||
    fmt.arithmeticHint === "dequant-fp32-then-native" ||
    fmt.arithmeticHint === "software-fp-via-fp32"
  ) {
    const f = Number(v);
    if (Number.isNaN(f)) return NaN;
    if (f === 0) return 0; // collapses -0 → +0
    return f;
  }
  return v;
}
