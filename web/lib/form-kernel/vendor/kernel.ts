// form-kernel-ts — vertical-slice host for Form-on-top.
//
// Reads `.fk` S-expression source files, parses straight into recipe trees,
// walks them. Carries everything Form-on-top can't write itself:
//
//   • Substrate          — NodeID + content-addressed intern table
//   • Walker             — 9 RBasic dispatch arms (matches form-kernel-go/rust)
//   • Frames + closures  — scope, lookup, capture
//   • Native primitives  — strings, lists, file I/O, substrate-write surface
//   • Bootstrap reader   — see ./reader.ts
//
// Aligned with api/app/services/substrate/category.py and the Go/Rust
// kernels. Cross-kernel NodeID agreement is the conformance contract.

// ---------------------------------------------------------------------------
// Substrate — NodeID + Recipe + intern table
// ---------------------------------------------------------------------------

// NodeID — the 4-tuple identity. Two structurally-equal recipes hash to the
// same NodeID via content-addressing. Trivials encode their value in `inst`.
//
// Packed into a single number for hot-path map keys: (pkg << 24) | (level
// << 16) | (type << 8) | inst is too small; we use BigInt for the full
// 4×u32 range. But Map<NodeID-as-object, _> has structural-equality
// problems in JS — Maps use reference equality. The kernel keeps two
// projections of every NodeID: an object (for ergonomic access) and a
// canonical string key (`pkg.level.type.inst`) for Map.
export interface NodeID {
  readonly pkg: number;
  readonly level: number;
  readonly type: number;
  readonly inst: number;
}

export const Level = {
  TRIVIAL: 1,
  BASIC: 2,
  COMPLEX_1: 3,
  COMPLEX_2: 4,
  COMPLEX_3: 5,
  COMPLEX_4: 6,
  COMPLEX_5: 7,
  COMPLEX_6: 8,
  COMPLEX_7: 9,
} as const;

// LevelValue — any concrete level constant. Used by universe-polymorphic
// FNDEFs (#22) to bind level-parameters at specialization time.
export type LevelValue = (typeof Level)[keyof typeof Level];

// RBasic — aligned with api/app/services/substrate/category.py
//
// Higher-math arms (slots 70+) — substrate cells govern their semantics:
//   QUOTIENT (70): canonicalization under an equivalence relation —
//     see ./quotient.ts. The category instance carries the equivalence
//     family code; children are [carrier-recipe, equivalence-recipe].
export const RBasic = {
  UNDEFINED: 0,         // honest "no Form category settled yet"
  WITNESS: 6,           // substrate self-attestation
  BLOCK: 9,
  CALL: 10,             // invoke external effect (I/O, tool)
  COND: 11,
  MATH: 12,
  COMPARE: 13,
  LOGIC: 14,
  ACCESS: 15,           // read property / field
  METHOD: 27,           // transform on a cell-like value
  FNDEF: 31,
  FNCALL: 32,
  IDENT: 33,
  LIST: 34,
  CHOICE: 35,           // pattern-match arm (extended in #21 with totality)
  QUOTIENT: 70,         // #19 — equivalence-class types
  INDUCTIVE: 71,        // #21 — algebraic datatypes
  CONSTRUCTOR: 72,      // #21 — constructor application / value-shape
  PROOF: 73,            // #20 — propositions-as-types (Curry-Howard)
  INFERENCE: 74,        // #20 — inference rules + applications
  ALIAS: 75,            // #8  — compile-time bindings (substrate cells)
  TRANSMUTE: 76,        // present value through Blueprint without changing identity
                        //       (typed-numeric casts, generic→specific views,
                        //        object-as-primitive narrowings). Distinct from
                        //        PROJECT (spatial) and METHOD (cell-transform).
  BLANKET: 80,          // #25 — Markov blanket (cell boundary recipe)
  PROJECT: 81,          // #28 — holographic PROJECT operation
  GENERATIVE: 82,       // #26 — generative model recipes (per-cell)
  VECTOR: 83,           // #9  — vector format-recipe (parameterized over element + width)
  TILE: 84,             // #9  — parallel pattern: tile loop by tile_size
  PARALLELIZE: 85,      // #9  — parallel pattern: dispatch op across num_threads
  VECTORIZE: 86,        // #9  — parallel pattern: lower op to simd_width-wide SIMD
  OBSERVER: 87,         // #27 — observer context (active QUOTIENTs for an observer)
  FIELD: 88,            // #30 — field state/value distributed over a carrier
  CARRIER: 89,          // #30 — sequence / graph / mesh / attention carrier
  TOPOLOGY: 90,         // #30 — adjacency / boundary shape
  FIBER: 91,            // #30 — per-site value shape
  REGION: 92,           // #30 — named carrier subset
  BOUNDARY: 93,         // #30 — membrane / constraint surface
  NEIGHBORHOOD: 94,     // #30 — local context relation
  MATCH_FIELD: 95,      // #30 — region / subgraph / gradient field match
  DELTA: 96,            // #30 — snapshot-relative mutation candidate
  RESOLVE: 97,          // #30 — conflict algebra
  COMMIT: 98,           // #30 — atomic logical-time commit
  STEP: 99,             // #30 — freeze/match/choose/delta/commit cycle
  LIFT: 100,            // #30 — linear/graph data into field
  SAMPLE: 101,          // #30 — point or region probe
  OBSERVE: 102,         // #30 — projection plus observer receipt
  INTERVENE: 103,       // #30 — consented perturbation
  RESIDUAL: 104,        // #30 — loss / budget remainder
  RECEIPT: 105,         // #30 — transparent execution record
  COST: 106,            // #30 — observer cost ledger
  CONSENT: 107,         // #30 — permission surface
  EVIDENCE: 108,        // #30 — observed / inferred / simulated status
} as const;

// Triv — trivial RTypes.
//
// Backward-compat: `INT` keeps slot 1 (aliased to INT32 in this kernel).
// New typed numerics get higher slots. Wide types (64-bit) route through
// per-type overflow tables; ≤32-bit types encode inline in NodeID.inst.
//
// See docs/coherence-substrate/numeric-types-plan.md for the cross-kernel
// migration plan.
export const Triv = {
  INT: 1, // ← INT32 (backward-compat alias)
  STRING: 2,
  BOOL: 3,
  NULL: 4,
  INT32: 1, // same slot as INT
  INT64: 5, // overflow table
  FLOAT32: 6, // inline (IEEE 754 bits reinterpret)
  FLOAT64: 7, // overflow table
  INT8: 8, // inline
  INT16: 9, // inline
  UINT8: 10, // inline
  UINT16: 11, // inline
  UINT32: 12, // inline
  UINT64: 13, // overflow table
  QUOTIENT_LEAF: 14, // canonical-form leaf produced by a QUOTIENT canonicalization;
  //                     the inst indexes a (quotient-recipe, canonical-children-tuple)
  //                     entry in the kernel's quotient cache. See ./quotient.ts.
  CONSTRUCTOR_TAG: 15, // #21 — small-int tag used by walker for ctor values
} as const;

// MATH instance encoding — width-aware. The low nibble carries the op
// (PLUS/MINUS/MUL/DIV/MOD); the high nibble carries the width marker so
// MATH.PLUS_F64 is a distinct NodeID from MATH.PLUS_I32.
//
//   inst = (width_marker << 4) | op_marker
//
//   width_marker  0=i32 (default)  1=i8  2=i16  3=i64
//                 4=u8  5=u16  6=u32  7=u64
//                 8=f32  9=f64
//   op_marker     1=PLUS 2=MINUS 3=MUL 4=DIV 5=MOD
export const RMathWidth = {
  I32: 0,
  I8: 1,
  I16: 2,
  I64: 3,
  U8: 4,
  U16: 5,
  U32: 6,
  U64: 7,
  F32: 8,
  F64: 9,
} as const;

export const RMath = { PLUS: 1, MINUS: 2, MUL: 3, DIV: 4, MOD: 5 } as const;

export function mathInst(width: number, op: number): number {
  return ((width & 0xf) << 4) | (op & 0xf);
}

export function mathWidth(inst: number): number {
  return (inst >> 4) & 0xf;
}

export function mathOp(inst: number): number {
  return inst & 0xf;
}
export const RCmp = { EQ: 1, NE: 2, LT: 3, LE: 4, GT: 5, GE: 6 } as const;
export const RLogic = { AND: 1, OR: 2, NOT: 3 } as const;
export const RCond = { IF_THEN: 1, IF_THEN_ELSE: 2 } as const;
export const RBlock = { DO: 1, SEQUENCE: 2, LET: 3 } as const;

// NameID — interned identifier handle. The same number used to encode a
// name trivial's NodeID instance is what every runtime name-lookup
// compares. String comparison happens once at parse time, never in the
// hot path.
export type NameID = number;

// Recipe — composite storage. Trivials are NOT stored; their NodeID carries
// the value.
interface Recipe {
  readonly category: NodeID;
  readonly children: readonly NodeID[];
}

// Stable, content-addressed hash key for a recipe. Same shape ⇒ same key.
function recipeKey(category: NodeID, children: readonly NodeID[]): string {
  let k = `C|${category.pkg}.${category.level}.${category.type}.${category.inst}`;
  for (const c of children) {
    k += `|${c.pkg}.${c.level}.${c.type}.${c.inst}`;
  }
  return k;
}

export function nodeKey(n: NodeID): string {
  return `${n.pkg}.${n.level}.${n.type}.${n.inst}`;
}

// Pack a NodeID into a single number for fast Map keys when pkg ≤ 255 and
// inst ≤ 2^32 — the common case. Uses BigInt encoding to keep all 4 u32s.
// In the hot path we use `nodeKey` (string) since V8's Map for string
// keys is well-optimized and BigInt conversions in inner loops are slow.

export type NativeFn = (k: Kernel, args: Value[]) => Value;

// KernelHost — optional effects supplied by the embedding runtime.
// Browser callers omit these and keep evaluation local/in-memory. CLI callers
// pass Node adapters so the same kernel can still read files and write traces.
export interface KernelHost {
  readonly readTextFile?: (path: string) => string;
  readonly readBinaryFile?: (path: string) => Uint8Array;
  readonly writeStdout?: (text: string) => void;
  readonly writeStderr?: (text: string) => void;
}

// NativeEntry — a native's function plus the Form category it expresses.
// Carries Blueprint attribution into the kernel: when the walker dispatches
// through a native, the trace records the category alongside the FNCALL
// arm. UNDEFINED is the honest marker for natives whose Form attribution
// hasn't been settled yet.
export interface NativeEntry {
  readonly category: NodeID;
  readonly fn: NativeFn;
}

// Trace — per-(arm, inst) dispatch counters. Sibling-parity with the Go and
// Rust kernels' Trace structures. Hot path stays free when trace is
// undefined. Storing (ty, inst) instead of just ty surfaces typed-numeric
// distribution — MATH.PLUS_F64 becomes distinguishable from MATH.PLUS_I32
// in the report.
export class Trace {
  totalWalks = 0;
  // Key: encoded as (ty << 32) | inst — JS Map handles this as a number key.
  // Since JS numbers are doubles (53-bit mantissa), this is safe for any
  // u32 ty + u32 inst combination that fits in 53 bits (well beyond our use).
  armCounts = new Map<number, number>();
  choiceAttempts = 0;
  choiceSuccesses = 0;
  choiceFailures = 0;

  private static encodeKey(ty: number, inst: number): number {
    // ty * 2^32 + inst — fits in JS number safely for our slot ranges.
    return ty * 0x100000000 + inst;
  }
  private static decodeKey(k: number): { ty: number; inst: number } {
    const ty = Math.floor(k / 0x100000000);
    const inst = k - ty * 0x100000000;
    return { ty, inst };
  }

  record(armTy: number, armInst: number): void {
    this.totalWalks++;
    const k = Trace.encodeKey(armTy, armInst);
    this.armCounts.set(k, (this.armCounts.get(k) ?? 0) + 1);
  }

  static armName(armTy: number): string {
    switch (armTy) {
      case RBasic.BLOCK: return "BLOCK";
      case RBasic.COND: return "COND";
      case RBasic.MATH: return "MATH";
      case RBasic.COMPARE: return "COMPARE";
      case RBasic.LOGIC: return "LOGIC";
      case RBasic.IDENT: return "IDENT";
      case RBasic.FNDEF: return "FNDEF";
      case RBasic.FNCALL: return "FNCALL";
      case RBasic.LIST: return "LIST";
      case RBasic.WITNESS: return "WITNESS";
      case RBasic.CALL: return "CALL";
      case RBasic.ACCESS: return "ACCESS";
      case RBasic.METHOD: return "METHOD";
      case RBasic.TRANSMUTE: return "TRANSMUTE";
      case RBasic.FIELD: return "FIELD";
      case RBasic.CARRIER: return "CARRIER";
      case RBasic.TOPOLOGY: return "TOPOLOGY";
      case RBasic.FIBER: return "FIBER";
      case RBasic.REGION: return "REGION";
      case RBasic.BOUNDARY: return "BOUNDARY";
      case RBasic.NEIGHBORHOOD: return "NEIGHBORHOOD";
      case RBasic.MATCH_FIELD: return "MATCH_FIELD";
      case RBasic.DELTA: return "DELTA";
      case RBasic.RESOLVE: return "RESOLVE";
      case RBasic.COMMIT: return "COMMIT";
      case RBasic.STEP: return "STEP";
      case RBasic.LIFT: return "LIFT";
      case RBasic.SAMPLE: return "SAMPLE";
      case RBasic.OBSERVE: return "OBSERVE";
      case RBasic.INTERVENE: return "INTERVENE";
      case RBasic.RESIDUAL: return "RESIDUAL";
      case RBasic.RECEIPT: return "RECEIPT";
      case RBasic.COST: return "COST";
      case RBasic.CONSENT: return "CONSENT";
      case RBasic.EVIDENCE: return "EVIDENCE";
      default: return "OTHER";
    }
  }

  /// Variant name — readable label for an (arm_ty, arm_inst) pair.
  /// Returns "MATH.PLUS", "COMPARE.LE", "BLOCK.LET", etc. For MATH in
  /// the TS kernel the inst encodes (width<<4)|op, so the variant becomes
  /// "MATH.PLUS_I32" / "MATH.MINUS_F64" etc. Sibling-parity with the
  /// Rust + Go kernels for the basic (width=0) cases.
  static armVariantName(armTy: number, armInst: number): string {
    const base = Trace.armName(armTy);
    let variant = "";
    switch (armTy) {
      case RBasic.MATH: {
        const width = (armInst >> 4) & 0xf;
        const op = armInst & 0xf;
        let opName = "";
        switch (op) {
          case RMath.PLUS: opName = "PLUS"; break;
          case RMath.MINUS: opName = "MINUS"; break;
          case RMath.MUL: opName = "MUL"; break;
          case RMath.DIV: opName = "DIV"; break;
          case RMath.MOD: opName = "MOD"; break;
        }
        if (!opName) break;
        const widthName = (() => {
          switch (width) {
            case RMathWidth.I32: return ""; // default; matches Rust/Go bare names
            case RMathWidth.I8: return "I8";
            case RMathWidth.I16: return "I16";
            case RMathWidth.I64: return "I64";
            case RMathWidth.U8: return "U8";
            case RMathWidth.U16: return "U16";
            case RMathWidth.U32: return "U32";
            case RMathWidth.U64: return "U64";
            case RMathWidth.F32: return "F32";
            case RMathWidth.F64: return "F64";
            default: return "";
          }
        })();
        variant = widthName ? `${opName}_${widthName}` : opName;
        break;
      }
      case RBasic.COMPARE:
        switch (armInst) {
          case RCmp.EQ: variant = "EQ"; break;
          case RCmp.NE: variant = "NE"; break;
          case RCmp.LT: variant = "LT"; break;
          case RCmp.LE: variant = "LE"; break;
          case RCmp.GT: variant = "GT"; break;
          case RCmp.GE: variant = "GE"; break;
        }
        break;
      case RBasic.LOGIC:
        switch (armInst) {
          case RLogic.AND: variant = "AND"; break;
          case RLogic.OR: variant = "OR"; break;
          case RLogic.NOT: variant = "NOT"; break;
        }
        break;
      case RBasic.COND:
        switch (armInst) {
          case RCond.IF_THEN: variant = "IF"; break;
          case RCond.IF_THEN_ELSE: variant = "IF_ELSE"; break;
        }
        break;
      case RBasic.BLOCK:
        switch (armInst) {
          case RBlock.DO: variant = "DO"; break;
          case RBlock.SEQUENCE: variant = "SEQ"; break;
          case RBlock.LET: variant = "LET"; break;
        }
        break;
    }
    return variant ? `${base}.${variant}` : base;
  }

  toJSON(): Record<string, unknown> {
    // Per-(ty, inst) records — preserves typed-numeric distribution.
    const variants = Array.from(this.armCounts.entries())
      .map(([k, count]) => {
        const { ty, inst } = Trace.decodeKey(k);
        return {
          arm_ty: ty,
          arm_inst: inst,
          arm_name: Trace.armName(ty),
          arm_variant_name: Trace.armVariantName(ty, inst),
          count,
        };
      })
      .sort((a, b) => b.count - a.count);

    // Per-ty aggregate — backward-compatible coarser shape.
    const byTy = new Map<number, number>();
    for (const [k, count] of this.armCounts) {
      const { ty } = Trace.decodeKey(k);
      byTy.set(ty, (byTy.get(ty) ?? 0) + count);
    }
    const arms = Array.from(byTy.entries())
      .map(([armTy, count]) => ({
        arm_ty: armTy,
        arm_name: Trace.armName(armTy),
        count,
      }))
      .sort((a, b) => b.count - a.count);

    return {
      total_walks: this.totalWalks,
      arms,        // aggregated by ty (backward-compatible)
      variants,    // full (ty, inst) granularity
      choice_attempts: this.choiceAttempts,
      choice_successes: this.choiceSuccesses,
      choice_failures: this.choiceFailures,
      choice_success_rate:
        this.choiceAttempts > 0
          ? this.choiceSuccesses / this.choiceAttempts
          : 0,
    };
  }
}

// Native-attribution category constructors. Each names the Form-shape a
// native expresses; the walker records them in the trace when the native
// fires. Mirrors Rust/Go kernel's cat_call / cat_witness / cat_access /
// cat_method / cat_list_nat / cat_undefined.
export function catCall(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.CALL, inst: 1 };
}
export function catWitness(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.WITNESS, inst: 1 };
}
export function catAccess(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.ACCESS, inst: 1 };
}
export function catMethod(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.METHOD, inst: 1 };
}
export function catListNat(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.LIST, inst: 1 };
}
export function catTransmute(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.TRANSMUTE, inst: 1 };
}
export function catField(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.FIELD, inst: 1 };
}
export function catFieldPrimitive(type: number): NodeID {
  return { pkg: 1, level: Level.BASIC, type, inst: 1 };
}
export function catDelta(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.DELTA, inst: 1 };
}
export function catReceipt(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.RECEIPT, inst: 1 };
}
export function catResidual(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.RESIDUAL, inst: 1 };
}
export function catCompareEq(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.COMPARE, inst: RCmp.EQ };
}
export function catUndefined(): NodeID {
  return { pkg: 1, level: Level.BASIC, type: RBasic.UNDEFINED, inst: 0 };
}

export class Kernel {
  // Composite recipes — keyed by content (recipeKey) for intern dedup,
  // and by NodeID (nodeKey) for walker access.
  private byKey = new Map<string, NodeID>();
  byID = new Map<string, Recipe>();
  private nextInst = 1; // next instance number for composites

  // String table — substrate strings + identifier names share this table.
  // A name's NodeID.inst is its index into `strs`.
  strs: string[] = [];
  private strIdx = new Map<string, NameID>();

  // Overflow tables for 64-bit numerics. Each is content-addressed by
  // value: `intern_int64(42)` returns the same inst every call.
  //
  // Float canonicalization on intern:
  //   - NaN bit patterns collapse to the quiet-NaN canonical
  //   - -0.0 and +0.0 share an entry (canonical +0.0)
  //   - +Inf and -Inf keep distinct identity
  private i64s: bigint[] = [];
  private i64Idx = new Map<bigint, number>();
  private u64s: bigint[] = [];
  private u64Idx = new Map<bigint, number>();
  private f64s: number[] = [];
  private f64Idx = new Map<string, number>(); // keyed by IEEE bit pattern as hex

  // Natives — map from NameID to NativeEntry (fn + Blueprint category).
  // Lookup is u32-keyed. The category lets the walker record which
  // Form-shape a native expresses, alongside the FNCALL arm.
  natives = new Map<NameID, NativeEntry>();

  // Optional tracing — undefined for hot-path runs, set by trace
  // subcommand. Sibling-parity with Go/Rust kernels.
  trace?: Trace;

  // Optional per-CTOR dispatch counter for Language-cell evaluators
  // (lang-python.ts, lang-go.ts, lang-rust.ts) that have their own
  // dispatch loop rather than going through `walk()`. The python-trace
  // subcommand sets this; evalNode bumps the count for each constructor
  // (CTOR.module, CTOR.def_, CTOR.while_, ...) it dispatches through.
  // Surfaces the structural shape of evaluated Python at its own altitude.
  ctorCounts?: Map<string, number>;

  constructor(private readonly host: KernelHost = {}) {
    this.registerNatives();
  }

  // intern — content-addressed insertion. Same shape ⇒ same NodeID.
  intern(category: NodeID, children: readonly NodeID[]): NodeID {
    const k = recipeKey(category, children);
    const existing = this.byKey.get(k);
    if (existing) return existing;
    const nid: NodeID = {
      pkg: 1,
      level: category.level,
      type: category.type,
      inst: this.nextInst++,
    };
    this.byKey.set(k, nid);
    this.byID.set(nodeKey(nid), { category, children });
    return nid;
  }

  internTrivialInt(n: number): NodeID {
    const inst = (n | 0) >>> 0;
    return { pkg: 1, level: Level.TRIVIAL, type: Triv.INT, inst };
  }

  internString(s: string): NodeID {
    const idx = this.internName(s);
    return { pkg: 1, level: Level.TRIVIAL, type: Triv.STRING, inst: idx };
  }

  internTrivialBool(b: boolean): NodeID {
    return { pkg: 1, level: Level.TRIVIAL, type: Triv.BOOL, inst: b ? 1 : 0 };
  }

  internTrivialNull(): NodeID {
    return { pkg: 1, level: Level.TRIVIAL, type: Triv.NULL, inst: 0 };
  }

  // ---- Typed numerics — inline (≤32 bit) ----

  internTrivialInt8(n: number): NodeID {
    const v = (n << 24) >> 24; // sign-extend
    return {
      pkg: 1,
      level: Level.TRIVIAL,
      type: Triv.INT8,
      inst: v >>> 0,
    };
  }

  internTrivialInt16(n: number): NodeID {
    const v = (n << 16) >> 16;
    return {
      pkg: 1,
      level: Level.TRIVIAL,
      type: Triv.INT16,
      inst: v >>> 0,
    };
  }

  internTrivialUint8(n: number): NodeID {
    return {
      pkg: 1,
      level: Level.TRIVIAL,
      type: Triv.UINT8,
      inst: n & 0xff,
    };
  }

  internTrivialUint16(n: number): NodeID {
    return {
      pkg: 1,
      level: Level.TRIVIAL,
      type: Triv.UINT16,
      inst: n & 0xffff,
    };
  }

  internTrivialUint32(n: number): NodeID {
    return {
      pkg: 1,
      level: Level.TRIVIAL,
      type: Triv.UINT32,
      inst: n >>> 0,
    };
  }

  internTrivialFloat32(f: number): NodeID {
    // Reinterpret f32 bits as u32, store inline.
    const buf = new ArrayBuffer(4);
    new Float32Array(buf)[0] = f;
    const inst = new Uint32Array(buf)[0]!;
    return { pkg: 1, level: Level.TRIVIAL, type: Triv.FLOAT32, inst };
  }

  // ---- Typed numerics — overflow tables (64-bit) ----

  internTrivialInt64(n: bigint): NodeID {
    const existing = this.i64Idx.get(n);
    if (existing !== undefined) {
      return { pkg: 1, level: Level.TRIVIAL, type: Triv.INT64, inst: existing };
    }
    const idx = this.i64s.length;
    this.i64s.push(n);
    this.i64Idx.set(n, idx);
    return { pkg: 1, level: Level.TRIVIAL, type: Triv.INT64, inst: idx };
  }

  internTrivialUint64(n: bigint): NodeID {
    if (n < 0n) throw new Error(`uint64: negative value ${n}`);
    const existing = this.u64Idx.get(n);
    if (existing !== undefined) {
      return { pkg: 1, level: Level.TRIVIAL, type: Triv.UINT64, inst: existing };
    }
    const idx = this.u64s.length;
    this.u64s.push(n);
    this.u64Idx.set(n, idx);
    return { pkg: 1, level: Level.TRIVIAL, type: Triv.UINT64, inst: idx };
  }

  internTrivialFloat64(f: number): NodeID {
    // Float canonicalization for content-addressing:
    //   - all NaN bit patterns → one canonical quiet NaN
    //   - -0.0 → +0.0
    let canonical = f;
    if (Number.isNaN(f)) {
      canonical = NaN; // JS NaN is canonical-quiet already
    } else if (f === 0 && 1 / f === -Infinity) {
      canonical = 0;
    }
    // Key the index by the IEEE 754 bit pattern so equal-bits ⇒ same index.
    const buf = new ArrayBuffer(8);
    new Float64Array(buf)[0] = canonical;
    const lo = new Uint32Array(buf)[0]!;
    const hi = new Uint32Array(buf)[1]!;
    const key = `${hi.toString(16)}_${lo.toString(16)}`;
    const existing = this.f64Idx.get(key);
    if (existing !== undefined) {
      return {
        pkg: 1,
        level: Level.TRIVIAL,
        type: Triv.FLOAT64,
        inst: existing,
      };
    }
    const idx = this.f64s.length;
    this.f64s.push(canonical);
    this.f64Idx.set(key, idx);
    return { pkg: 1, level: Level.TRIVIAL, type: Triv.FLOAT64, inst: idx };
  }

  // ---- Decoders for the overflow tables ----

  decodeInt64(inst: number): bigint {
    const v = this.i64s[inst];
    if (v === undefined) throw new Error(`int64: bad index ${inst}`);
    return v;
  }

  decodeUint64(inst: number): bigint {
    const v = this.u64s[inst];
    if (v === undefined) throw new Error(`uint64: bad index ${inst}`);
    return v;
  }

  decodeFloat64(inst: number): number {
    const v = this.f64s[inst];
    if (v === undefined) throw new Error(`float64: bad index ${inst}`);
    return v;
  }

  decodeFloat32(inst: number): number {
    const buf = new ArrayBuffer(4);
    new Uint32Array(buf)[0] = inst;
    return new Float32Array(buf)[0]!;
  }

  // boxValue — wrap a NodeID into a Value-of-kind-nodeid for native returns.
  boxValue(n: NodeID): Value {
    return { kind: "nodeid", nodeid: n };
  }

  internName(s: string): NameID {
    const existing = this.strIdx.get(s);
    if (existing !== undefined) return existing;
    const idx = this.strs.length;
    this.strs.push(s);
    this.strIdx.set(s, idx);
    return idx;
  }

  category(n: NodeID): NodeID {
    if (n.level === Level.TRIVIAL) return n;
    const r = this.byID.get(nodeKey(n));
    return r ? r.category : n;
  }

  children(n: NodeID): readonly NodeID[] {
    const r = this.byID.get(nodeKey(n));
    return r ? r.children : [];
  }

  recipeAt(n: NodeID): Recipe | undefined {
    return this.byID.get(nodeKey(n));
  }

  trivialValue(n: NodeID): Value {
    if (n.level !== Level.TRIVIAL) {
      throw new Error(`trivialValue: ${nodeKey(n)} is composite`);
    }
    switch (n.type) {
      case Triv.INT32: {
        // (same slot as Triv.INT)
        const u = n.inst >>> 0;
        const i = u > 0x7fffffff ? u - 0x100000000 : u;
        return { kind: "int", int: i };
      }
      case Triv.STRING: {
        const s = this.strs[n.inst];
        if (s === undefined) {
          throw new Error(`trivialValue: string index ${n.inst} out of range`);
        }
        return { kind: "str", str: s };
      }
      case Triv.BOOL:
        return { kind: "bool", bool: n.inst !== 0 };
      case Triv.NULL:
        return { kind: "null" };
      case Triv.INT8: {
        const u = n.inst >>> 0;
        const i = u > 0x7f ? (u | 0xffffff00) | 0 : u;
        return { kind: "i8", int: i };
      }
      case Triv.INT16: {
        const u = n.inst >>> 0;
        const i = u > 0x7fff ? (u | 0xffff0000) | 0 : u;
        return { kind: "i16", int: i };
      }
      case Triv.UINT8:
        return { kind: "u8", int: n.inst & 0xff };
      case Triv.UINT16:
        return { kind: "u16", int: n.inst & 0xffff };
      case Triv.UINT32:
        return { kind: "u32", int: n.inst >>> 0 };
      case Triv.INT64:
        return { kind: "i64", bigint: this.decodeInt64(n.inst) };
      case Triv.UINT64:
        return { kind: "u64", bigint: this.decodeUint64(n.inst) };
      case Triv.FLOAT32:
        return { kind: "f32", float: this.decodeFloat32(n.inst) };
      case Triv.FLOAT64:
        return { kind: "f64", float: this.decodeFloat64(n.inst) };
      default:
        throw new Error(`trivialValue: unknown trivial type ${n.type}`);
    }
  }

  identID(n: NodeID): NameID {
    // Bare string trivial — the NameID IS the inst.
    if (n.level === Level.TRIVIAL && n.type === Triv.STRING) {
      return n.inst;
    }
    // IDENT recipe wrapping a string trivial.
    const kids = this.children(n);
    if (
      kids.length === 1 &&
      kids[0] !== undefined &&
      kids[0].level === Level.TRIVIAL &&
      kids[0].type === Triv.STRING
    ) {
      return kids[0].inst;
    }
    throw new Error(`identID: ${nodeKey(n)} is not an identifier shape`);
  }

  nameStr(id: NameID): string {
    const s = this.strs[id];
    if (s === undefined) {
      throw new Error(`nameStr: NameID ${id} out of range`);
    }
    return s;
  }

  render(v: Value): string {
    switch (v.kind) {
      case "null":
        return "null";
      case "int":
      case "i8":
      case "i16":
      case "u8":
      case "u16":
      case "u32":
        return String(v.int);
      case "i64":
      case "u64":
        return String(v.bigint);
      case "f32":
      case "f64":
        return String(v.float);
      case "str":
        return JSON.stringify(v.str);
      case "bool":
        return v.bool ? "true" : "false";
      case "list":
        return "[" + v.list.map((x) => this.render(x)).join(", ") + "]";
      case "closure":
        return "<closure>";
      case "nodeid":
        return `@${nodeKey(v.nodeid)}`;
      case "ctor":
        return `${v.ctor_name}(${v.args.map((a) => this.render(a)).join(", ")})`;
    }
  }

  // -------------------------------------------------------------------------
  // Native primitives — registered once; called by FNCALL when the callee
  // identifier resolves to a NameID in the natives map.
  // -------------------------------------------------------------------------

  private registerNative(name: string, category: NodeID, fn: NativeFn): void {
    this.natives.set(this.internName(name), { category, fn });
  }

  // setNative — public registration helper for language adapters
  // (lang-go.ts, lang-python.ts, etc.) that previously reached into the
  // natives map directly. Default category is UNDEFINED (honest about
  // unsettled Form attribution); pass an explicit category to opt in.
  setNative(name: string, fn: NativeFn, category: NodeID = catUndefined()): void {
    this.natives.set(this.internName(name), { category, fn });
  }

  private registerNatives(): void {
    // Blueprint attribution discipline (mirrors Rust/Go kernels):
    //   catCall      — invoke external effect (I/O, tool)
    //   catAccess    — read property / field
    //   catMethod    — transform on a cell-like value
    //   catCompareEq — equality (str_eq)
    //   catListNat   — construct/destructure a List
    //   catWitness   — substrate self-attestation
    //   catUndefined — honest "no Form category settled yet"

    this.registerNative("print", catCall(), (_k, args) => {
      const parts = args.map((a) => this.renderForPrint(a));
      this.host.writeStdout?.(parts.join(" ") + "\n");
      return { kind: "null" };
    });
    // String ops
    this.registerNative("str_len", catAccess(), (_k, args) => ({
      kind: "int",
      int: argStr(args, 0).length,
    }));
    this.registerNative("substring", catAccess(), (_k, args) => ({
      kind: "str",
      str: argStr(args, 0).slice(argInt(args, 1), argInt(args, 2)),
    }));
    this.registerNative("char_at", catAccess(), (_k, args) => {
      const s = argStr(args, 0);
      const i = argInt(args, 1);
      return { kind: "str", str: s[i] ?? "" };
    });
    this.registerNative("str_concat", catMethod(), (_k, args) => ({
      kind: "str",
      str: argStr(args, 0) + argStr(args, 1),
    }));
    this.registerNative("str_eq", catCompareEq(), (_k, args) => ({
      kind: "bool",
      bool: argStr(args, 0) === argStr(args, 1),
    }));
    // int_to_str — value-to-string for trivial leaves. Historical name
    // (first use: line numbers in cell-trace.fk); semantics is "render
    // any trivial value as text" so emit-engine.fk's leaf walker can
    // pass node_value of any leaf type through it. Multi-target emit
    // (universal codec lattice — emit.fk + emits/json.fk) depends on
    // string + bool + null passthrough.
    this.registerNative("int_to_str", catMethod(), (_k, args) => {
      const v = args[0]!;
      if (v.kind === "str") return { kind: "str", str: v.str ?? "" };
      if (v.kind === "bool") return { kind: "str", str: v.bool ? "true" : "false" };
      if (v.kind === "null") return { kind: "str", str: "null" };
      return { kind: "str", str: String(argInt(args, 0)) };
    });
    this.registerNative("str_to_int", catMethod(), (_k, args) => ({
      kind: "int",
      int: parseInt(argStr(args, 0), 10) || 0,
    }));
    this.registerNative("ord", catAccess(), (_k, args) => {
      const s = argStr(args, 0);
      return { kind: "int", int: s.length === 0 ? -1 : s.charCodeAt(0) };
    });
    // List ops
    this.registerNative("list", catListNat(), (_k, args) => ({
      kind: "list",
      list: args.slice(),
    }));
    this.registerNative("cons", catListNat(), (_k, args) => {
      const head = args[0] ?? { kind: "null" };
      const tail = argList(args, 1);
      return { kind: "list", list: [head, ...tail] };
    });
    this.registerNative("head", catListNat(), (_k, args) => {
      const lst = argList(args, 0);
      return lst[0] ?? { kind: "null" };
    });
    this.registerNative("tail", catListNat(), (_k, args) => ({
      kind: "list",
      list: argList(args, 0).slice(1),
    }));
    this.registerNative("len", catAccess(), (_k, args) => {
      const v = args[0];
      if (v?.kind === "list") return { kind: "int", int: v.list.length };
      if (v?.kind === "str") return { kind: "int", int: v.str.length };
      return { kind: "int", int: 0 };
    });
    this.registerNative("nth", catAccess(), (_k, args) => {
      const lst = argList(args, 0);
      const i = argInt(args, 1);
      return lst[i] ?? { kind: "null" };
    });
    this.registerNative("empty", catListNat(), () => ({ kind: "list", list: [] }));
    // Common Python builtins. Sibling-parity with Rust + Go.
    this.registerNative("min", catMethod(), (_k, args) => {
      const v = args[0];
      if (v?.kind === "list") {
        if (v.list.length === 0) throw new Error("min: empty list");
        let best = (v.list[0] as { int: number }).int;
        for (let i = 1; i < v.list.length; i++) {
          const x = (v.list[i] as { int: number }).int;
          if (x < best) best = x;
        }
        return { kind: "int", int: best };
      }
      return { kind: "int", int: argInt(args, 0) };
    });
    this.registerNative("max", catMethod(), (_k, args) => {
      const v = args[0];
      if (v?.kind === "list") {
        if (v.list.length === 0) throw new Error("max: empty list");
        let best = (v.list[0] as { int: number }).int;
        for (let i = 1; i < v.list.length; i++) {
          const x = (v.list[i] as { int: number }).int;
          if (x > best) best = x;
        }
        return { kind: "int", int: best };
      }
      return { kind: "int", int: argInt(args, 0) };
    });
    this.registerNative("sum", catMethod(), (_k, args) => {
      const v = args[0];
      if (v?.kind === "list") {
        let total = 0;
        for (const e of v.list) total += (e as { int: number }).int ?? 0;
        return { kind: "int", int: total };
      }
      return { kind: "int", int: 0 };
    });
    this.registerNative("abs", catMethod(), (_k, args) => {
      const n = argInt(args, 0);
      return { kind: "int", int: n < 0 ? -n : n };
    });
    // Polymorphic `+` for Python: int+int=add, str+str=concat,
    // str+int / int+str = concat-via-stringify, list+list=concat.
    this.registerNative("_plus", catMethod(), (_k, args) => {
      const a = args[0];
      const b = args[1];
      if (a?.kind === "int" && b?.kind === "int") return { kind: "int", int: a.int + b.int };
      if (a?.kind === "str" && b?.kind === "str") return { kind: "str", str: a.str + b.str };
      if (a?.kind === "str" && b?.kind === "int") return { kind: "str", str: a.str + String(b.int) };
      if (a?.kind === "int" && b?.kind === "str") return { kind: "str", str: String(a.int) + b.str };
      if (a?.kind === "list" && b?.kind === "list") return { kind: "list", list: [...a.list, ...b.list] };
      throw new Error(`_plus: unsupported operand types`);
    });
    // range(n) / range(a,b) / range(a,b,s) — eager list of integers.
    // Matches CPython semantics. Sibling-parity with Rust + Go kernels.
    this.registerNative("range", catListNat(), (_k, args) => {
      let start = 0, stop = 0, step = 1;
      if (args.length === 1) {
        stop = argInt(args, 0);
      } else if (args.length === 2) {
        start = argInt(args, 0);
        stop = argInt(args, 1);
      } else {
        start = argInt(args, 0);
        stop = argInt(args, 1);
        step = argInt(args, 2);
      }
      const out: Value[] = [];
      if (step === 0) return { kind: "list", list: out };
      if (step > 0) {
        for (let i = start; i < stop; i += step) out.push({ kind: "int", int: i });
      } else {
        for (let i = start; i > stop; i += step) out.push({ kind: "int", int: i });
      }
      return { kind: "list", list: out };
    });
    // File I/O
    this.registerNative("read_file", catCall(), (_k, args) => {
      try {
        const readTextFile = this.host.readTextFile;
        if (!readTextFile) return { kind: "null" };
        return { kind: "str", str: readTextFile(argStr(args, 0)) };
      } catch {
        return { kind: "null" };
      }
    });
    // Byte-level file read — returns a list of ints (0-255), one per byte.
    // Pair with `nth` for byte-at-index access. The codec stays universal
    // across text and binary formats: text grammars walk a string with
    // char_at + ord; binary grammars walk a byte-list with nth.
    this.registerNative("read_file_bytes", catCall(), (_k, args) => {
      try {
        const readBinaryFile = this.host.readBinaryFile;
        if (!readBinaryFile) return { kind: "null" };
        const buf = readBinaryFile(argStr(args, 0));
        const out: Value[] = new Array(buf.length);
        for (let i = 0; i < buf.length; i++) {
          out[i] = { kind: "int", int: buf[i]! };
        }
        return { kind: "list", list: out };
      } catch {
        return { kind: "null" };
      }
    });

    // Substrate write surface — all attributed as WITNESS.
    this.registerNative("make_nodeid", catWitness(), (_k, args) => ({
      kind: "nodeid",
      nodeid: {
        pkg: argInt(args, 0),
        level: argInt(args, 1),
        type: argInt(args, 2),
        inst: argInt(args, 3),
      },
    }));
    this.registerNative("intern_trivial_int", catWitness(), (k, args) => ({
      kind: "nodeid",
      nodeid: k.internTrivialInt(argInt(args, 0)),
    }));
    this.registerNative("intern_trivial_string", catWitness(), (k, args) => ({
      kind: "nodeid",
      nodeid: k.internString(argStr(args, 0)),
    }));
    this.registerNative("intern_node", catWitness(), (k, args) => {
      const cat = argNodeID(args, 0);
      const kids = argList(args, 1).map((v) => {
        if (v.kind !== "nodeid")
          throw new Error("intern_node: children must be nodeids");
        return v.nodeid;
      });
      return { kind: "nodeid", nodeid: k.intern(cat, kids) };
    });
    const fieldNode = (
      nativeName: string,
      categoryType: number,
      categoryInst: number,
    ): NativeFn => (k, args) => {
      const kids = argList(args, 0).map((v) => {
        if (v.kind !== "nodeid") {
          throw new Error(`${nativeName}: children must be nodeids`);
        }
        return v.nodeid;
      });
      return {
        kind: "nodeid",
        nodeid: k.intern(
          { pkg: 1, level: Level.BASIC, type: categoryType, inst: categoryInst },
          kids,
        ),
      };
    };
    const fieldConstructors: Array<[string, number, number]> = [
      ["field_blueprint", RBasic.FIELD, 1],
      ["field_cell", RBasic.FIELD, 2],
      ["field_carrier", RBasic.CARRIER, 1],
      ["field_topology", RBasic.TOPOLOGY, 1],
      ["field_fiber", RBasic.FIBER, 1],
      ["field_region", RBasic.REGION, 1],
      ["field_boundary", RBasic.BOUNDARY, 1],
      ["field_neighborhood", RBasic.NEIGHBORHOOD, 1],
      ["field_match", RBasic.MATCH_FIELD, 1],
      ["field_delta", RBasic.DELTA, 1],
      ["field_resolve", RBasic.RESOLVE, 1],
      ["field_commit", RBasic.COMMIT, 1],
      ["field_step", RBasic.STEP, 1],
      ["field_lift", RBasic.LIFT, 1],
      ["field_sample", RBasic.SAMPLE, 1],
      ["field_observe", RBasic.OBSERVE, 1],
      ["field_intervene", RBasic.INTERVENE, 1],
      ["field_residual", RBasic.RESIDUAL, 1],
      ["field_receipt", RBasic.RECEIPT, 1],
      ["field_cost", RBasic.COST, 1],
      ["field_consent", RBasic.CONSENT, 1],
      ["field_evidence", RBasic.EVIDENCE, 1],
    ];
    for (const [nativeName, categoryType, categoryInst] of fieldConstructors) {
      this.registerNative(
        nativeName,
        catFieldPrimitive(categoryType),
        fieldNode(nativeName, categoryType, categoryInst),
      );
    }
    this.registerNative("node_category", catWitness(), (k, args) => ({
      kind: "nodeid",
      nodeid: k.category(argNodeID(args, 0)),
    }));
    this.registerNative("node_children", catWitness(), (k, args) => {
      const kids = k.children(argNodeID(args, 0));
      return {
        kind: "list",
        list: kids.map((c) => ({ kind: "nodeid", nodeid: c } as Value)),
      };
    });
    this.registerNative("node_value", catWitness(), (k, args) =>
      k.trivialValue(argNodeID(args, 0)),
    );
    // node_eq — structural compare of two NodeIDs by their four
    // components. Sibling parity with Go's node_eq + Rust's node_eq.
    this.registerNative("node_eq", catWitness(), (_k, args) => {
      const a = argNodeID(args, 0);
      const b = argNodeID(args, 1);
      const equal =
        a.pkg === b.pkg &&
        a.level === b.level &&
        a.type === b.type &&
        a.inst === b.inst;
      return { kind: "bool", bool: equal };
    });
    this.registerNative("walk_recipe", catWitness(), (k, args) =>
      walk(k, argNodeID(args, 0), new Frame(null)),
    );

    // native_blueprint — introspection: return a native's Form category.
    this.registerNative("native_blueprint", catWitness(), (k, args) => {
      const name = argStr(args, 0);
      const id = k.lookupName(name);
      if (id === undefined) return { kind: "null" };
      const ne = k.natives.get(id);
      if (ne === undefined) return { kind: "null" };
      return { kind: "nodeid", nodeid: ne.category };
    });

    // Typed-numeric construction and decoding — attributed as WITNESS
    // (substrate-write for typed trivials) and METHOD (value conversion).
    this.registerNative("make_int8", catWitness(), (k, args) => k.boxValue(k.internTrivialInt8(argInt(args, 0))));
    this.registerNative("make_int16", catWitness(), (k, args) => k.boxValue(k.internTrivialInt16(argInt(args, 0))));
    this.registerNative("make_int32", catWitness(), (k, args) => k.boxValue(k.internTrivialInt(argInt(args, 0))));
    this.registerNative("make_int64", catWitness(), (k, args) => k.boxValue(k.internTrivialInt64(argBigInt(args, 0))));
    this.registerNative("make_uint8", catWitness(), (k, args) => k.boxValue(k.internTrivialUint8(argInt(args, 0))));
    this.registerNative("make_uint16", catWitness(), (k, args) => k.boxValue(k.internTrivialUint16(argInt(args, 0))));
    this.registerNative("make_uint32", catWitness(), (k, args) => k.boxValue(k.internTrivialUint32(argInt(args, 0))));
    this.registerNative("make_uint64", catWitness(), (k, args) => k.boxValue(k.internTrivialUint64(argBigInt(args, 0))));
    this.registerNative("make_float32", catWitness(), (k, args) => k.boxValue(k.internTrivialFloat32(argFloat(args, 0))));
    this.registerNative("make_float64", catWitness(), (k, args) => k.boxValue(k.internTrivialFloat64(argFloat(args, 0))));

    // Width-conversion casts — TRANSMUTE: present a value through a different
    // numeric Blueprint without changing its underlying identity. Same content
    // viewed through a different width. The canonical example the user named
    // for typed numerics: a recipe declares "a number"; at the call site the
    // specific type is recorded; a cast presents the value through a different
    // Blueprint while preserving identity through content-addressing.
    this.registerNative("i64", catTransmute(), (_k, args) => ({ kind: "i64", bigint: argBigInt(args, 0) }));
    this.registerNative("u64", catTransmute(), (_k, args) => ({ kind: "u64", bigint: argBigInt(args, 0) }));
    this.registerNative("f32", catTransmute(), (_k, args) => ({ kind: "f32", float: Math.fround(argFloat(args, 0)) }));
    this.registerNative("f64", catTransmute(), (_k, args) => ({ kind: "f64", float: argFloat(args, 0) }));
    this.registerNative("i32", catTransmute(), (_k, args) => ({ kind: "int", int: argInt(args, 0) | 0 }));

    // Debug — no Form category claimed; honest about being outside the
    // structural vocabulary.
    this.registerNative("trace", catUndefined(), (_k, args) => {
      if (args.length >= 2) {
        const label = args[0]?.kind === "str" ? args[0].str : "trace";
        this.host.writeStderr?.(
          `[trace ${label}] ${this.renderForPrint(args[1] ?? { kind: "null" })}\n`,
        );
        return args[1] ?? { kind: "null" };
      }
      const v = args[0] ?? { kind: "null" };
      this.host.writeStderr?.(`[trace] ${this.renderForPrint(v)}\n`);
      return v;
    });
  }

  // lookupName — internal-only name → NameID lookup, used by
  // native_blueprint. Returns undefined for unbound names.
  lookupName(s: string): NameID | undefined {
    return this.strIdx.get(s);
  }

  private renderForPrint(v: Value): string {
    switch (v.kind) {
      case "null":
        return "null";
      case "int":
      case "i8":
      case "i16":
      case "u8":
      case "u16":
      case "u32":
        return String(v.int);
      case "i64":
      case "u64":
        return String(v.bigint);
      case "f32":
      case "f64":
        return String(v.float);
      case "str":
        return v.str;
      case "bool":
        return v.bool ? "true" : "false";
      case "list":
        return "[" + v.list.map((x) => this.renderForPrint(x)).join(" ") + "]";
      case "closure":
        return "<closure>";
      case "nodeid":
        return `@${nodeKey(v.nodeid)}`;
      case "ctor":
        return `${v.ctor_name}(${v.args.map((a) => this.render(a)).join(", ")})`;
    }
  }
}

// argN helpers — typed extraction with friendly errors.
function argInt(args: Value[], i: number): number {
  const v = args[i];
  if (!v) throw new Error(`arg ${i}: missing`);
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return v.int;
  if (v.kind === "i64" || v.kind === "u64") return Number(v.bigint);
  throw new Error(`arg ${i}: expected int-like, got ${v.kind}`);
}
function argFloat(args: Value[], i: number): number {
  const v = args[i];
  if (!v) throw new Error(`arg ${i}: missing`);
  if (v.kind === "f32" || v.kind === "f64") return v.float;
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return v.int;
  if (v.kind === "i64" || v.kind === "u64") return Number(v.bigint);
  throw new Error(`arg ${i}: expected number, got ${v.kind}`);
}
function argBigInt(args: Value[], i: number): bigint {
  const v = args[i];
  if (!v) throw new Error(`arg ${i}: missing`);
  if (v.kind === "i64" || v.kind === "u64") return v.bigint;
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return BigInt(v.int);
  throw new Error(`arg ${i}: expected integer, got ${v.kind}`);
}
function argStr(args: Value[], i: number): string {
  const v = args[i];
  if (v?.kind !== "str") throw new Error(`arg ${i}: expected str`);
  return v.str;
}
function argList(args: Value[], i: number): Value[] {
  const v = args[i];
  if (v?.kind !== "list") throw new Error(`arg ${i}: expected list`);
  return v.list;
}
function argNodeID(args: Value[], i: number): NodeID {
  const v = args[i];
  if (v?.kind !== "nodeid") throw new Error(`arg ${i}: expected nodeid`);
  return v.nodeid;
}

// ---------------------------------------------------------------------------
// Values — runtime tagged values
// ---------------------------------------------------------------------------

export type Value =
  | { kind: "null" }
  | { kind: "int"; int: number } // INT32 (alias kept for backward-compat)
  | { kind: "i8"; int: number }
  | { kind: "i16"; int: number }
  | { kind: "u8"; int: number }
  | { kind: "u16"; int: number }
  | { kind: "u32"; int: number }
  | { kind: "i64"; bigint: bigint }
  | { kind: "u64"; bigint: bigint }
  | { kind: "f32"; float: number }
  | { kind: "f64"; float: number }
  | { kind: "str"; str: string }
  | { kind: "bool"; bool: boolean }
  | { kind: "list"; list: Value[] }
  | { kind: "closure"; closure: Closure }
  | { kind: "nodeid"; nodeid: NodeID }
  | { // #21 — INDUCTIVE-typed value (constructor application result)
      kind: "ctor";
      inductive: NodeID;
      ctor_name: string;
      ctor_index: number;
      args: Value[];
    };

export interface Closure {
  readonly params: readonly NameID[];
  readonly body: NodeID;
  readonly env: Frame;
}

// ---------------------------------------------------------------------------
// Frame — scope primitive
// ---------------------------------------------------------------------------

export class Frame {
  readonly parent: Frame | null;
  private readonly keys: NameID[] = [];
  private readonly vals: Value[] = [];

  constructor(parent: Frame | null = null) {
    this.parent = parent;
  }

  bind(name: NameID, value: Value): void {
    const idx = this.keys.indexOf(name);
    if (idx >= 0) {
      this.vals[idx] = value;
      return;
    }
    this.keys.push(name);
    this.vals.push(value);
  }

  lookup(name: NameID): Value | undefined {
    let frame: Frame | null = this;
    while (frame !== null) {
      const idx = frame.keys.indexOf(name);
      if (idx >= 0) return frame.vals[idx];
      frame = frame.parent;
    }
    return undefined;
  }
}

// ---------------------------------------------------------------------------
// Walker — recipe → value
// ---------------------------------------------------------------------------

export function walk(k: Kernel, node: NodeID, frame: Frame): Value {
  if (node.level === Level.TRIVIAL) {
    return k.trivialValue(node);
  }
  const cat = k.category(node);
  const kids = k.children(node);

  // Tracing hook: when k.trace is set, record arm dispatch. Pure
  // counter increment — no allocation, no IO. Sibling-parity with the
  // Rust and Go kernels. Records (ty, inst) so typed-numeric
  // distribution stays distinguishable.
  if (k.trace !== undefined) {
    k.trace.record(cat.type, cat.inst);
  }

  switch (cat.type) {
    case RBasic.IDENT: {
      const id = k.identID(node);
      const v = frame.lookup(id);
      if (v !== undefined) return v;
      // Identifiers can also resolve to natives (callable values).
      const nat = k.natives.get(id);
      if (nat !== undefined) {
        return {
          kind: "closure",
          closure: { params: [], body: node, env: frame } as Closure,
        };
      }
      throw new Error(`unbound identifier: ${k.nameStr(id)}`);
    }
    case RBasic.MATH:
      return walkMath(k, cat.inst, kids, frame);
    case RBasic.COMPARE:
      return walkCompare(k, cat.inst, kids, frame);
    case RBasic.LOGIC:
      return walkLogic(k, cat.inst, kids, frame);
    case RBasic.COND:
      return walkCond(k, cat.inst, kids, frame);
    case RBasic.BLOCK:
      return walkBlock(k, cat.inst, kids, frame);
    case RBasic.FNDEF:
      return walkFnDef(k, kids, frame);
    case RBasic.FNCALL:
      return walkFnCall(k, kids, frame);
    case RBasic.LIST: {
      const items = kids.map((c) => walk(k, c, frame));
      return { kind: "list", list: items };
    }
    case RBasic.INDUCTIVE:
      // INDUCTIVE recipes are type definitions. Walking one yields the
      // NodeID of the type itself.
      return { kind: "nodeid", nodeid: node };
    case RBasic.CONSTRUCTOR:
      return walkConstructor(k, node, kids, frame);
    case RBasic.CHOICE:
      return walkChoice(k, node, kids, frame);
    case RBasic.QUOTIENT:
      // QUOTIENT recipes — walking one yields its NodeID so structural
      // reasoning over equivalence-class types can address them.
      return { kind: "nodeid", nodeid: node };
    case RBasic.ALIAS:
      // ALIAS recipes (#8) — children: [name-trivial, target-nodeid].
      // Walking returns the target NodeID so alias resolution is transparent.
      if (kids.length >= 2) return { kind: "nodeid", nodeid: kids[1]! };
      return { kind: "nodeid", nodeid: node };
    case RBasic.BLANKET:
    case RBasic.PROJECT:
    case RBasic.GENERATIVE:
    case RBasic.PROOF:
    case RBasic.INFERENCE:
    case RBasic.VECTOR:
    case RBasic.TILE:
    case RBasic.PARALLELIZE:
    case RBasic.VECTORIZE:
    case RBasic.TRANSMUTE:
      // Higher-architecture recipes — walking returns the NodeID itself,
      // letting downstream code reason structurally without crashing on
      // recipes whose semantics are interpreted by their own module
      // (blanket.ts, project.ts, generative.ts, proof.ts, vector.ts, parallel.ts).
      // TRANSMUTE follows the same passthrough pattern: the substrate
      // identity of the value is preserved through the cast/view; consumers
      // that want the concrete cast semantics can use the typed-numeric
      // natives (i32, i64, f32, f64, u64, ...) which already carry the
      // TRANSMUTE Blueprint attribution in the trace.
      return { kind: "nodeid", nodeid: node };
    default:
      throw new Error(`walk: unsupported RBasic type ${cat.type}`);
  }
}

// CONSTRUCTOR recipe shape:
//   children: [inductive-ref, ctor-name-trivial, ctor-index-trivial, args...]
function walkConstructor(
  k: Kernel,
  _node: NodeID,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length < 3) {
    throw new Error("constructor: need 3+ children (inductive, name, index)");
  }
  const inductive = kids[0]!;
  const nameNode = kids[1]!;
  const indexNode = kids[2]!;
  if (nameNode.level !== Level.TRIVIAL || nameNode.type !== Triv.STRING) {
    throw new Error("constructor: name must be a string trivial");
  }
  if (indexNode.level !== Level.TRIVIAL || indexNode.type !== Triv.INT32) {
    throw new Error("constructor: index must be an int trivial");
  }
  const args: Value[] = [];
  for (let i = 3; i < kids.length; i++) {
    args.push(walk(k, kids[i]!, frame));
  }
  const indexVal = k.trivialValue(indexNode);
  return {
    kind: "ctor",
    inductive,
    ctor_name: k.nameStr(nameNode.inst),
    ctor_index: indexVal.kind === "int" ? indexVal.int : 0,
    args,
  };
}

// CHOICE recipe shape:
//   children: [scrutinee, arm0-ctor-name, arm0-body, ...]
function walkChoice(
  k: Kernel,
  _node: NodeID,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length < 1) throw new Error("choice: need scrutinee");
  if ((kids.length - 1) % 2 !== 0) {
    throw new Error("choice: arms must be (name, body) pairs");
  }
  const scrutinee = walk(k, kids[0]!, frame);
  if (scrutinee.kind !== "ctor") {
    throw new Error(`choice: scrutinee must be ctor value (got ${scrutinee.kind})`);
  }
  const armNames: string[] = [];
  const armBodies: NodeID[] = [];
  for (let i = 1; i < kids.length; i += 2) {
    const nameNode = kids[i]!;
    if (nameNode.level !== Level.TRIVIAL || nameNode.type !== Triv.STRING) {
      throw new Error("choice: arm name must be string trivial");
    }
    armNames.push(k.nameStr(nameNode.inst));
    armBodies.push(kids[i + 1]!);
  }
  // Totality check — only when scrutinee carries an inductive ref
  const indRecipe = k.recipeAt(scrutinee.inductive);
  if (indRecipe !== undefined && indRecipe.category.type === RBasic.INDUCTIVE) {
    // Walk inductive's constructors to find missing arms
    const ctorChildren = indRecipe.children.slice(2); // skip name + params
    const ctorNames: string[] = [];
    for (const ctorNid of ctorChildren) {
      const ctorRecipe = k.recipeAt(ctorNid);
      if (ctorRecipe && ctorRecipe.category.type === RBasic.CONSTRUCTOR) {
        const cName = ctorRecipe.children[1];
        if (cName && cName.level === Level.TRIVIAL && cName.type === Triv.STRING) {
          ctorNames.push(k.nameStr(cName.inst));
        }
      }
    }
    const missing = ctorNames.filter((n) => !armNames.includes(n));
    if (missing.length > 0) {
      throw new Error(
        `choice: non-total — missing constructor${missing.length > 1 ? "s" : ""}: ${missing.join(", ")}`,
      );
    }
  }
  // Dispatch
  for (let i = 0; i < armNames.length; i++) {
    if (armNames[i] === scrutinee.ctor_name) {
      const body = armBodies[i]!;
      const bodyRecipe = k.recipeAt(body);
      if (bodyRecipe === undefined) {
        return walk(k, body, frame);
      }
      if (bodyRecipe.category.type === RBasic.FNDEF) {
        const params = k.children(bodyRecipe.children[1]!);
        const armFrame = new Frame(frame);
        for (let j = 0; j < params.length; j++) {
          const p = params[j]!;
          if (p.level !== Level.TRIVIAL || p.type !== Triv.STRING) {
            throw new Error("choice: arm params must be string trivials");
          }
          armFrame.bind(p.inst, scrutinee.args[j] ?? { kind: "null" });
        }
        return walk(k, bodyRecipe.children[2]!, armFrame);
      }
      return walk(k, body, frame);
    }
  }
  throw new Error(`choice: no arm matches constructor ${scrutinee.ctor_name}`);
}

function expectInt(v: Value, op: string): number {
  if (
    v.kind !== "int" &&
    v.kind !== "i8" &&
    v.kind !== "i16" &&
    v.kind !== "u8" &&
    v.kind !== "u16" &&
    v.kind !== "u32"
  )
    throw new Error(`${op}: expected int-like, got ${v.kind}`);
  return v.int;
}

function expectFloat(v: Value, op: string): number {
  if (v.kind === "f32" || v.kind === "f64") return v.float;
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return v.int;
  if (v.kind === "i64" || v.kind === "u64") return Number(v.bigint);
  throw new Error(`${op}: expected number-like, got ${v.kind}`);
}

function expectBigInt(v: Value, op: string): bigint {
  if (v.kind === "i64" || v.kind === "u64") return v.bigint;
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return BigInt(v.int);
  throw new Error(`${op}: expected integer-like, got ${v.kind}`);
}

function walkMath(
  k: Kernel,
  inst: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length < 2) throw new Error("math: need at least 2 args");
  const width = mathWidth(inst);
  const op = mathOp(inst);

  // Float64 — typed path, no boxing inside the loop.
  if (width === RMathWidth.F64) {
    let acc = expectFloat(walk(k, kids[0]!, frame), "math.f64");
    for (let i = 1; i < kids.length; i++) {
      const x = expectFloat(walk(k, kids[i]!, frame), "math.f64");
      switch (op) {
        case RMath.PLUS:
          acc = acc + x;
          break;
        case RMath.MINUS:
          acc = acc - x;
          break;
        case RMath.MUL:
          acc = acc * x;
          break;
        case RMath.DIV:
          acc = acc / x;
          break;
        case RMath.MOD:
          acc = acc - Math.floor(acc / x) * x;
          break;
        default:
          throw new Error(`math.f64: unknown op ${op}`);
      }
    }
    return { kind: "f64", float: acc };
  }

  // Float32 — same shape, narrow to f32 at boundary.
  if (width === RMathWidth.F32) {
    let acc = expectFloat(walk(k, kids[0]!, frame), "math.f32");
    for (let i = 1; i < kids.length; i++) {
      const x = expectFloat(walk(k, kids[i]!, frame), "math.f32");
      switch (op) {
        case RMath.PLUS:
          acc = Math.fround(acc + x);
          break;
        case RMath.MINUS:
          acc = Math.fround(acc - x);
          break;
        case RMath.MUL:
          acc = Math.fround(acc * x);
          break;
        case RMath.DIV:
          acc = Math.fround(acc / x);
          break;
        case RMath.MOD:
          acc = Math.fround(acc - Math.floor(acc / x) * x);
          break;
        default:
          throw new Error(`math.f32: unknown op ${op}`);
      }
    }
    return { kind: "f32", float: acc };
  }

  // Int64 / Uint64 — typed path via BigInt.
  if (width === RMathWidth.I64 || width === RMathWidth.U64) {
    let acc = expectBigInt(walk(k, kids[0]!, frame), "math.i64");
    for (let i = 1; i < kids.length; i++) {
      const x = expectBigInt(walk(k, kids[i]!, frame), "math.i64");
      switch (op) {
        case RMath.PLUS:
          acc = acc + x;
          break;
        case RMath.MINUS:
          acc = acc - x;
          break;
        case RMath.MUL:
          acc = acc * x;
          break;
        case RMath.DIV:
          if (x === 0n) throw new Error("division by zero");
          acc = acc / x;
          break;
        case RMath.MOD:
          if (x === 0n) throw new Error("modulo by zero");
          acc = acc % x;
          break;
        default:
          throw new Error(`math.i64: unknown op ${op}`);
      }
    }
    return width === RMathWidth.I64
      ? { kind: "i64", bigint: acc }
      : { kind: "u64", bigint: acc };
  }

  // I32 default path — backward-compat fast path.
  let acc = expectInt(walk(k, kids[0]!, frame), "math.i32");
  for (let i = 1; i < kids.length; i++) {
    const x = expectInt(walk(k, kids[i]!, frame), "math.i32");
    switch (op) {
      case RMath.PLUS:
        acc = (acc + x) | 0;
        break;
      case RMath.MINUS:
        acc = (acc - x) | 0;
        break;
      case RMath.MUL:
        acc = Math.imul(acc, x);
        break;
      case RMath.DIV:
        if (x === 0) throw new Error("division by zero");
        acc = (acc / x) | 0;
        break;
      case RMath.MOD:
        if (x === 0) throw new Error("modulo by zero");
        acc = acc - ((acc / x) | 0) * x;
        break;
      default:
        throw new Error(`math.i32: unknown op ${op}`);
    }
  }
  return { kind: "int", int: acc };
}

function walkCompare(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length !== 2) throw new Error("compare: need exactly 2 args");
  const av = walk(k, kids[0]!, frame);
  const bv = walk(k, kids[1]!, frame);

  if (op === RCmp.EQ || op === RCmp.NE) {
    const equal = valueEqual(av, bv);
    return { kind: "bool", bool: op === RCmp.EQ ? equal : !equal };
  }

  // Width-mixing in comparisons: if either side is float, compare as float;
  // if either side is bigint, compare as bigint; else as int.
  let r: boolean;
  if (av.kind === "f32" || av.kind === "f64" || bv.kind === "f32" || bv.kind === "f64") {
    const a = expectFloat(av, "compare");
    const b = expectFloat(bv, "compare");
    switch (op) {
      case RCmp.LT: r = a < b; break;
      case RCmp.LE: r = a <= b; break;
      case RCmp.GT: r = a > b; break;
      case RCmp.GE: r = a >= b; break;
      default: throw new Error(`compare: unknown op ${op}`);
    }
  } else if (av.kind === "i64" || av.kind === "u64" || bv.kind === "i64" || bv.kind === "u64") {
    const a = expectBigInt(av, "compare");
    const b = expectBigInt(bv, "compare");
    switch (op) {
      case RCmp.LT: r = a < b; break;
      case RCmp.LE: r = a <= b; break;
      case RCmp.GT: r = a > b; break;
      case RCmp.GE: r = a >= b; break;
      default: throw new Error(`compare: unknown op ${op}`);
    }
  } else {
    const a = expectInt(av, "compare");
    const b = expectInt(bv, "compare");
    switch (op) {
      case RCmp.LT: r = a < b; break;
      case RCmp.LE: r = a <= b; break;
      case RCmp.GT: r = a > b; break;
      case RCmp.GE: r = a >= b; break;
      default: throw new Error(`compare: unknown op ${op}`);
    }
  }
  return { kind: "bool", bool: r };
}

function valueEqual(a: Value, b: Value): boolean {
  // Cross-width numeric equality: compare numerically across widths.
  const aNum = isNumericValue(a);
  const bNum = isNumericValue(b);
  if (aNum && bNum) {
    if (a.kind === "i64" || a.kind === "u64" || b.kind === "i64" || b.kind === "u64") {
      return numericToBig(a) === numericToBig(b);
    }
    return numericToNum(a) === numericToNum(b);
  }
  if (a.kind !== b.kind) return false;
  switch (a.kind) {
    case "null":
      return true;
    case "str":
      return a.str === (b as { str: string }).str;
    case "bool":
      return a.bool === (b as { bool: boolean }).bool;
    default:
      return false;
  }
}

function isNumericValue(
  v: Value,
): v is
  | { kind: "int"; int: number }
  | { kind: "i8"; int: number }
  | { kind: "i16"; int: number }
  | { kind: "u8"; int: number }
  | { kind: "u16"; int: number }
  | { kind: "u32"; int: number }
  | { kind: "i64"; bigint: bigint }
  | { kind: "u64"; bigint: bigint }
  | { kind: "f32"; float: number }
  | { kind: "f64"; float: number } {
  return (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32" ||
    v.kind === "i64" ||
    v.kind === "u64" ||
    v.kind === "f32" ||
    v.kind === "f64"
  );
}

function numericToNum(v: Value): number {
  if (v.kind === "f32" || v.kind === "f64") return v.float;
  if (v.kind === "i64" || v.kind === "u64") return Number(v.bigint);
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return v.int;
  throw new Error(`numericToNum: ${v.kind} is not numeric`);
}

function numericToBig(v: Value): bigint {
  if (v.kind === "i64" || v.kind === "u64") return v.bigint;
  if (v.kind === "f32" || v.kind === "f64") return BigInt(Math.trunc(v.float));
  if (
    v.kind === "int" ||
    v.kind === "i8" ||
    v.kind === "i16" ||
    v.kind === "u8" ||
    v.kind === "u16" ||
    v.kind === "u32"
  )
    return BigInt(v.int);
  throw new Error(`numericToBig: ${v.kind} is not numeric`);
}

function walkLogic(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (op === RLogic.NOT) {
    if (kids.length !== 1) throw new Error("not: need exactly 1 arg");
    const v = walk(k, kids[0]!, frame);
    if (v.kind !== "bool") throw new Error("not: expected bool");
    return { kind: "bool", bool: !v.bool };
  }
  if (kids.length < 2) throw new Error("and/or: need at least 2 args");
  for (let i = 0; i < kids.length; i++) {
    const v = walk(k, kids[i]!, frame);
    if (v.kind !== "bool") throw new Error("and/or: expected bool");
    if (op === RLogic.AND && !v.bool) return { kind: "bool", bool: false };
    if (op === RLogic.OR && v.bool) return { kind: "bool", bool: true };
    if (i === kids.length - 1) return v;
  }
  return { kind: "bool", bool: op === RLogic.AND };
}

function walkCond(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (op === RCond.IF_THEN) {
    if (kids.length !== 2) throw new Error("if: need 2 args");
    const c = walk(k, kids[0]!, frame);
    if (c.kind !== "bool") throw new Error("if: condition must be bool");
    return c.bool ? walk(k, kids[1]!, frame) : { kind: "null" };
  }
  if (kids.length !== 3) throw new Error("if/else: need 3 args");
  const c = walk(k, kids[0]!, frame);
  if (c.kind !== "bool") throw new Error("if: condition must be bool");
  return c.bool ? walk(k, kids[1]!, frame) : walk(k, kids[2]!, frame);
}

function walkBlock(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (op === RBlock.LET) {
    if (kids.length !== 2) throw new Error("let: need 2 args (name, value)");
    const name = kids[0]!;
    if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
      throw new Error("let: name must be a string trivial");
    }
    const value = walk(k, kids[1]!, frame);
    frame.bind(name.inst, value);
    return value;
  }
  // DO or SEQUENCE — evaluate each, return last
  let result: Value = { kind: "null" };
  for (const c of kids) {
    result = walk(k, c, frame);
  }
  return result;
}

// FNDEF children:  [name-trivial, params-SEQUENCE-of-name-trivials, body]
// (matches Go kernel's defn shape)
function walkFnDef(
  k: Kernel,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length !== 3) {
    throw new Error("defn: need 3 children (name, params, body)");
  }
  const name = kids[0]!;
  const paramsBlock = kids[1]!;
  const body = kids[2]!;

  if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) {
    throw new Error("defn: name must be string trivial");
  }
  const nameID = name.inst;

  const paramKids = k.children(paramsBlock);
  const params: NameID[] = paramKids.map((p) => {
    if (p.level !== Level.TRIVIAL || p.type !== Triv.STRING) {
      throw new Error("defn: params must be string trivials");
    }
    return p.inst;
  });

  const closure: Closure = { params, body, env: frame };
  const value: Value = { kind: "closure", closure };
  frame.bind(nameID, value);
  return value;
}

// FNCALL children: [callee, arg0, arg1, ...]
// Callee is either an IDENT recipe, a bare string trivial, or any expression
// that evaluates to a closure.
function walkFnCall(
  k: Kernel,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length < 1) throw new Error("call: need callee");
  const calleeNode = kids[0]!;

  // Fast path: callee is a bare name. Resolve directly through frame or
  // natives without going through walk → IDENT dispatch.
  let calleeName: NameID | null = null;
  if (
    calleeNode.level === Level.TRIVIAL &&
    calleeNode.type === Triv.STRING
  ) {
    calleeName = calleeNode.inst;
  } else if (
    calleeNode.level === Level.BASIC &&
    calleeNode.type === RBasic.IDENT
  ) {
    calleeName = k.identID(calleeNode);
  }

  if (calleeName !== null) {
    // Native dispatch
    const ne = k.natives.get(calleeName);
    if (ne !== undefined) {
      const args: Value[] = [];
      for (let i = 1; i < kids.length; i++) {
        args.push(walk(k, kids[i]!, frame));
      }
      // Native Blueprint attribution — record the Form category the
      // native expresses alongside the FNCALL arm. The kernel knows
      // itself even when the call leaves Form-land.
      if (k.trace !== undefined && ne.category.type !== RBasic.UNDEFINED) {
        k.trace.record(ne.category.type, ne.category.inst);
      }
      return ne.fn(k, args);
    }
    // Closure via frame
    const v = frame.lookup(calleeName);
    if (v === undefined) {
      throw new Error(`call: unbound ${k.nameStr(calleeName)}`);
    }
    if (v.kind !== "closure") {
      throw new Error(
        `call: ${k.nameStr(calleeName)} is not a closure (got ${v.kind})`,
      );
    }
    return invokeClosure(k, v.closure, kids, frame);
  }

  // General path: callee is an expression
  const calleeVal = walk(k, calleeNode, frame);
  if (calleeVal.kind !== "closure") {
    throw new Error(`call: callee is not a closure (got ${calleeVal.kind})`);
  }
  return invokeClosure(k, calleeVal.closure, kids, frame);
}

function invokeClosure(
  k: Kernel,
  closure: Closure,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length - 1 !== closure.params.length) {
    throw new Error(
      `call: arity mismatch (expected ${closure.params.length}, got ${kids.length - 1})`,
    );
  }
  const callFrame = new Frame(closure.env);
  for (let i = 0; i < closure.params.length; i++) {
    const v = walk(k, kids[i + 1]!, frame);
    callFrame.bind(closure.params[i]!, v);
  }
  return walk(k, closure.body, callFrame);
}
