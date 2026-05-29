// form-kernel-ts — vertical-slice host for Form-on-top.
//
// Executes Form recipe trees and binary artifacts. The CLI carries the
// source-to-recipe adapter for current tests; this module holds the
// substrate, walker, host primitives, and binary artifact loader.
//
//   • Substrate          — NodeID + content-addressed intern table
//   • Walker             — 9 RBasic dispatch arms (matches form-kernel-go/rust)
//   • Frames + closures  — scope, lookup, capture
//   • Native primitives  — strings, lists, file I/O, substrate-write surface
//   • Binary loader      — Form artifact bytes → recipe tree
//
// Aligned with api/app/services/substrate/category.py and the Go/Rust
// kernels. Cross-kernel NodeID agreement is the conformance contract.

import { closeSync, openSync, readFileSync, readSync, statSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { BP_TABLE } from "./bp_table";

// ---------------------------------------------------------------------------
// Substrate — NodeID + Recipe + intern table
// ---------------------------------------------------------------------------

// NodeID — the 4-tuple identity. Registered substrate ids use pkg=1.
// Runtime-interned composites use pkg=0 so temporary recipe ids cannot collide
// with registered/basic categories across an execution context boundary.
// Trivials encode their value in `inst`.
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

function nodeFromKey(key: string): NodeID {
  const [pkg = 0, level = 0, type = 0, inst = 0] = key
    .split(".")
    .map((part) => Number(part));
  return { pkg, level, type, inst };
}

// Pack a NodeID into a single number for fast Map keys when pkg ≤ 255 and
// inst ≤ 2^32 — the common case. Uses BigInt encoding to keep all 4 u32s.
// In the hot path we use `nodeKey` (string) since V8's Map for string
// keys is well-optimized and BigInt conversions in inner loops are slow.

export type NativeFn = (k: Kernel, args: Value[]) => Value;

// EnvAwareNativeFn — natives that need the caller's env (walk_recipe_here).
// Separate registry path to avoid changing the NativeFn signature across
// every existing native.
export type EnvAwareNativeFn = (
  k: Kernel,
  env: Frame,
  args: Value[],
) => Value;

export interface EnvAwareNativeEntry {
  readonly name: NameID;
  readonly category: NodeID;
  readonly fn: EnvAwareNativeFn;
}

// NativeEntry — a native's function plus the Form category it expresses.
// Carries Blueprint attribution into the kernel: when the walker dispatches
// through a native, the trace records the category alongside the FNCALL
// arm. UNDEFINED is the honest marker for natives whose Form attribution
// hasn't been settled yet.
export interface NativeEntry {
  readonly name: NameID;
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
  fnCounts = new Map<string, number>();
  nativeCounts = new Map<string, number>();
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

  recordFn(name: string): void {
    this.fnCounts.set(name, (this.fnCounts.get(name) ?? 0) + 1);
  }

  recordNative(name: string): void {
    this.nativeCounts.set(name, (this.nativeCounts.get(name) ?? 0) + 1);
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
    const functions = Array.from(this.fnCounts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
    const natives = Array.from(this.nativeCounts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);

    return {
      total_walks: this.totalWalks,
      arms,        // aggregated by ty (backward-compatible)
      variants,    // full (ty, inst) granularity
      functions,
      natives,
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
  private sourceAttr = new Map<string, { file: NameID; line: number; col: number }>();
  private importSeq = 1;
  private walkCache = new Map<string, Value>();
  private walkCacheHits = 0;
  private walkCacheMisses = 0;
  private activeRoots: NodeID[] = [];

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
  envNatives = new Map<NameID, EnvAwareNativeEntry>();
  // methods — the blueprint method table (BML/NUMS reference: methods live on
  // the blueprint/type, shared by all instances, name-dispatched). Keyed by
  // `${nodeKey(blueprint)}:${nameID}` → the method's Closure.
  methods = new Map<string, Closure>();

  // jitAliases — Form-function-name → native-name redirect. When a
  // function call's name is in this map, the walker substitutes the
  // aliased name before native lookup. Form recipes are canonical
  // truth; `register_jit` opts a call into a kernel-resident optimized
  // native. Removing the entry restores the Form walk.
  jitAliases = new Map<NameID, NameID>();

  // jitCompiled — closure-body-NodeID → CompiledFn. When (jit_compile
  // "name") fires, the closure under `name` has its body compiled via
  // compiler.ts and stored here. The walker checks this map on every
  // FNCALL — if the closure body has a compiled version, dispatch
  // through it instead of walking. Keyed by content-addressed body
  // NodeID, so re-defining the same body re-uses the cached compile.
  // Indexed by stringified NodeID tuple (pkg.level.type.inst).
  jitCompiled = new Map<string, (frame: Frame) => Value>();

  // jitCompileHook — pluggable Form→host-asm compiler. Installed at
  // startup by main.ts via compiler.ts. The kernel holds the hook
  // pointer rather than importing the compiler directly so this module
  // stays the canonical foundation (compiler.ts imports kernel.ts;
  // hoisting compiler into kernel would create a cycle). When the hook
  // is null, the jit_compile native returns 0 honestly — telling the
  // Form caller "no compiler available on this kernel."
  jitCompileHook: ((k: Kernel, body: NodeID) => (frame: Frame) => Value) | null = null;

  // Optional tracing — undefined for hot-path runs, set by trace
  // subcommand. Sibling-parity with Go/Rust kernels.
  trace?: Trace;

  // Optional per-CTOR dispatch counter for Language-cell evaluators
  // that have their own dispatch loop rather than going through `walk()`.
  // Surfaces a language adapter's structural shape at its own altitude.
  ctorCounts?: Map<string, number>;

  constructor() {
    this.registerNatives();
  }

  // intern — content-addressed insertion. Same shape ⇒ same NodeID.
  intern(category: NodeID, children: readonly NodeID[]): NodeID {
    const k = recipeKey(category, children);
    const existing = this.byKey.get(k);
    if (existing) return existing;
    const nid: NodeID = {
      pkg: 0,
      level: category.level,
      type: category.type,
      inst: this.nextInst++,
    };
    this.byKey.set(k, nid);
    this.byID.set(nodeKey(nid), { category, children });
    return nid;
  }

  nextImportScope(): number {
    return this.importSeq++;
  }

  setActiveRoots(roots: readonly NodeID[]): void {
    this.activeRoots = [...roots];
  }

  pushActiveRoot(root: NodeID): void {
    this.activeRoots.push(root);
  }

  remapImportedLeaf(scope: number, nid: NodeID): NodeID {
    if (nid.pkg !== 0) return nid;
    return this.intern(catUndefined(), [
      this.internTrivialInt(scope),
      this.internTrivialInt(nid.level),
      this.internTrivialInt(nid.type),
      this.internTrivialInt(nid.inst),
    ]);
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

  substrateMark(): Value[] {
    return [
      { kind: "int", int: this.nextInst },
      { kind: "int", int: this.strs.length },
      { kind: "int", int: this.byID.size },
    ];
  }

  substrateCounts(): Value[] {
    return [
      { kind: "int", int: this.byID.size },
      { kind: "int", int: this.strs.length },
    ];
  }

  substrateRelease(mark: Value[]): number {
    const next = mark[0]?.kind === "int" ? mark[0].int : 0;
    const strLen = mark[1]?.kind === "int" ? mark[1].int : -1;
    if (next <= 0 || strLen < 0 || strLen > this.strs.length) return 0;
    let released = 0;
    for (const key of Array.from(this.byID.keys())) {
      const nid = nodeFromKey(key);
      if (nid.pkg === 0 && nid.inst >= next) {
        this.byID.delete(key);
        this.sourceAttr.delete(key);
        this.walkCache.delete(key);
        released += 1;
      }
    }
    for (const [key, nid] of Array.from(this.byKey.entries())) {
      if (nid.pkg === 0 && nid.inst >= next) {
        this.byKey.delete(key);
      }
    }
    for (let i = strLen; i < this.strs.length; i += 1) {
      const s = this.strs[i];
      if (s !== undefined) this.strIdx.delete(s);
    }
    this.strs.length = strLen;
    this.nextInst = next;
    this.walkCache.clear();
    return released;
  }

  private markStringNode(n: NodeID, liveStrings: Set<NameID>): void {
    if (n.pkg === 1 && n.level === Level.TRIVIAL && n.type === Triv.STRING) {
      liveStrings.add(n.inst);
    }
  }

  private markNode(n: NodeID, liveNodes: Set<string>, liveStrings: Set<NameID>): void {
    this.markStringNode(n, liveStrings);
    const key = nodeKey(n);
    if (n.pkg !== 0 || liveNodes.has(key)) return;
    const recipe = this.byID.get(key);
    if (recipe === undefined) return;
    liveNodes.add(key);
    this.markNode(recipe.category, liveNodes, liveStrings);
    for (const child of recipe.children) {
      this.markNode(child, liveNodes, liveStrings);
    }
  }

  private markValue(
    value: Value,
    liveNodes: Set<string>,
    liveStrings: Set<NameID>,
    liveFrames: Set<Frame>,
  ): void {
    if (value.kind === "list") {
      for (const item of value.list) this.markValue(item, liveNodes, liveStrings, liveFrames);
    } else if (value.kind === "closure") {
      liveStrings.add(value.closure.name);
      this.markNode(value.closure.body, liveNodes, liveStrings);
      this.markFrame(value.closure.env, liveNodes, liveStrings, liveFrames);
    } else if (value.kind === "nodeid") {
      this.markNode(value.nodeid, liveNodes, liveStrings);
    }
  }

  private markFrame(
    frame: Frame | null,
    liveNodes: Set<string>,
    liveStrings: Set<NameID>,
    liveFrames: Set<Frame>,
  ): void {
    for (let cur = frame; cur !== null; cur = cur.parent) {
      if (liveFrames.has(cur)) return;
      liveFrames.add(cur);
      for (const [name, value] of cur.entries()) {
        liveStrings.add(name);
        this.markValue(value, liveNodes, liveStrings, liveFrames);
      }
    }
  }

  substrateGC(roots: readonly Value[], stack: Frame | null = null): Value[] {
    const liveNodes = new Set<string>();
    const liveStrings = new Set<NameID>();
    const liveFrames = new Set<Frame>();
    for (const name of this.natives.keys()) liveStrings.add(name);
    for (const loc of this.sourceAttr.values()) liveStrings.add(loc.file);
    for (const root of this.activeRoots) this.markNode(root, liveNodes, liveStrings);
    for (const root of roots) this.markValue(root, liveNodes, liveStrings, liveFrames);
    this.markFrame(stack, liveNodes, liveStrings, liveFrames);
    let changed = true;
    while (changed) {
      const beforeNodes = liveNodes.size;
      const beforeStrings = liveStrings.size;
      for (const [key, value] of this.walkCache.entries()) {
        if (liveNodes.has(key)) {
          this.markValue(value, liveNodes, liveStrings, liveFrames);
        }
      }
      changed = liveNodes.size !== beforeNodes || liveStrings.size !== beforeStrings;
    }
    let freed = 0;
    for (const key of Array.from(this.byID.keys())) {
      const nid = nodeFromKey(key);
      if (nid.pkg === 0 && !liveNodes.has(key)) {
        this.byID.delete(key);
        this.sourceAttr.delete(key);
        this.walkCache.delete(key);
        freed += 1;
      }
    }
    for (const [key, nid] of Array.from(this.byKey.entries())) {
      if (nid.pkg === 0 && !liveNodes.has(nodeKey(nid))) {
        this.byKey.delete(key);
      }
    }
    for (const key of Array.from(this.walkCache.keys())) {
      if (!liveNodes.has(key)) this.walkCache.delete(key);
    }
    let pruned = 0;
    if (stack !== null) {
      while (this.strs.length > 0) {
        const idx = this.strs.length - 1;
        if (liveStrings.has(idx)) break;
        const s = this.strs.pop();
        if (s !== undefined) this.strIdx.delete(s);
        pruned += 1;
      }
    }
    return [
      { kind: "int", int: freed },
      { kind: "int", int: pruned },
    ];
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
      case "record":
        return `<record @${nodeKey(v.record.blueprint)} #${v.record.fields.length}fields>`;
    }
  }

  // -------------------------------------------------------------------------
  // Native primitives — registered once; called by FNCALL when the callee
  // identifier resolves to a NameID in the natives map.
  // -------------------------------------------------------------------------

  private registerNative(name: string, category: NodeID, fn: NativeFn): void {
    const id = this.internName(name);
    this.natives.set(id, { name: id, category, fn });
  }

  private registerEnvNative(
    name: string,
    category: NodeID,
    fn: EnvAwareNativeFn,
  ): void {
    const id = this.internName(name);
    this.envNatives.set(id, { name: id, category, fn });
  }

  // setNative — public registration helper for language adapters that
  // need to extend the native map. Default category is UNDEFINED
  // (honest about unsettled Form attribution); pass an explicit category
  // to opt in.
  setNative(name: string, fn: NativeFn, category: NodeID = catUndefined()): void {
    const id = this.internName(name);
    this.natives.set(id, { name: id, category, fn });
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
      process.stdout.write(parts.join(" ") + "\n");
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
    // pow — integer exponentiation in native code (no Form recursion).
    // (pow base exp) → base**exp. Negative exponents return 0 (Python's
    // int**-n is a float; floats on this path are a later breath).
    this.registerNative("pow", catMethod(), (_k, args) => {
      const base = argInt(args, 0);
      const exp = argInt(args, 1);
      if (exp < 0) return { kind: "int", int: 0 };
      let result = 1;
      for (let i = 0; i < exp; i++) result *= base;
      return { kind: "int", int: result };
    });
    // --- struct/object primitive (BML reference, rung 2) ----------------
    // A Record is the kernel's first MUTABLE value: a struct/object with
    // identity. Every language's class/struct compiles onto these natives.
    // Blueprint NodeID tags the type; fields are a name→value map.
    //
    // record_new — (record_new blueprint k1 v1 k2 v2 ...) → record.
    this.registerNative("record_new", catMethod(), (k, args) => {
      const rec: Record = { blueprint: argNodeID(args, 0), fields: [] };
      let i = 1;
      while (i + 1 < args.length) {
        recordSet(rec, k.internName(argStr(args, i)), args[i + 1]!);
        i += 2;
      }
      return { kind: "record", record: rec };
    });
    // record_get — (record_get rec "field") → value, or null if absent.
    this.registerNative("record_get", catAccess(), (k, args) => {
      const r = args[0]!;
      if (r.kind !== "record") throw new Error("record_get: not a record");
      const v = recordGet(r.record, k.internName(argStr(args, 1)));
      return v ?? { kind: "null" };
    });
    // record_set — (record_set rec "field" value) → the record (mutated in
    // place; shared identity means all holders see it). BML's `self.x = v`.
    this.registerNative("record_set", catMethod(), (k, args) => {
      const r = args[0]!;
      if (r.kind !== "record") throw new Error("record_set: not a record");
      recordSet(r.record, k.internName(argStr(args, 1)), args[2]!);
      return r;
    });
    // record_has — (record_has rec "field") → bool.
    this.registerNative("record_has", catAccess(), (k, args) => {
      const r = args[0]!;
      if (r.kind !== "record") return { kind: "bool", bool: false };
      const v = recordGet(r.record, k.internName(argStr(args, 1)));
      return { kind: "bool", bool: v !== undefined };
    });
    // record_blueprint — (record_blueprint rec) → the blueprint NodeID.
    this.registerNative("record_blueprint", catAccess(), (_k, args) => {
      const r = args[0]!;
      if (r.kind !== "record") throw new Error("record_blueprint: not a record");
      return { kind: "nodeid", nodeid: r.record.blueprint };
    });
    // record? — (record? v) → bool type predicate.
    this.registerNative("record?", catAccess(), (_k, args) => ({
      kind: "bool",
      bool: args[0]!.kind === "record",
    }));
    // --- methods on the blueprint (BML/NUMS reference, rung 2b) ----------
    // Methods live on the blueprint/type, shared by all records of that type,
    // name-dispatched. The keystone that makes a Record a real object.
    //
    // method_define — (method_define blueprint "name" closure) → blueprint.
    this.registerNative("method_define", catMethod(), (k, args) => {
      const cl = args[2]!;
      if (cl.kind !== "closure") {
        throw new Error("method_define: third arg must be a closure");
      }
      const bp = argNodeID(args, 0);
      const key = `${nodeKey(bp)}:${k.internName(argStr(args, 1))}`;
      k.methods.set(key, cl.closure);
      return args[0]!;
    });
    // method_has — (method_has record-or-blueprint "name") → bool.
    this.registerNative("method_has", catAccess(), (k, args) => {
      const a0 = args[0]!;
      let bp: NodeID;
      if (a0.kind === "record") bp = a0.record.blueprint;
      else if (a0.kind === "nodeid") bp = a0.nodeid;
      else return { kind: "bool", bool: false };
      const key = `${nodeKey(bp)}:${k.internName(argStr(args, 1))}`;
      return { kind: "bool", bool: k.methods.has(key) };
    });
    // method_invoke — (method_invoke record "name" arg1 ...) → value.
    // Dispatches by the record's blueprint; the method's FIRST param is the
    // receiver (Python `self`), remaining params bind to call args.
    this.registerNative("method_invoke", catMethod(), (k, args) => {
      const a0 = args[0]!;
      if (a0.kind !== "record") {
        throw new Error("method_invoke: first arg must be a record");
      }
      const bp = a0.record.blueprint;
      const key = `${nodeKey(bp)}:${k.internName(argStr(args, 1))}`;
      const cl = k.methods.get(key);
      if (!cl) {
        throw new Error(
          `method_invoke: no method '${argStr(args, 1)}' on blueprint @${nodeKey(bp)}`,
        );
      }
      const callArgs = args.slice(2);
      if (cl.params.length === 0) {
        throw new Error(
          `method '${argStr(args, 1)}' must declare a receiver param (self)`,
        );
      }
      if (callArgs.length !== cl.params.length - 1) {
        throw new Error(
          `method '${argStr(args, 1)}' wants ${cl.params.length - 1} args, got ${callArgs.length}`,
        );
      }
      const callFrame = new Frame(cl.env);
      callFrame.bind(cl.params[0]!, a0); // receiver
      for (let i = 0; i < callArgs.length; i++) {
        callFrame.bind(cl.params[i + 1]!, callArgs[i]!);
      }
      return walk(k, cl.body, callFrame);
    });
    // str_find — JS-level substring search starting at index `from`.
    // (str_find s needle from) → int (index or -1). Whole search in this
    // JS String.indexOf call; no Form callback per byte, no Form recursion.
    this.registerNative("str_find", catAccess(), (_k, args) => {
      const s = argStr(args, 0);
      const needle = argStr(args, 1);
      const from = argInt(args, 2);
      const idx = s.indexOf(needle, from);
      // `kind: "int"` carries a JS Number — using BigInt here would
      // poison downstream arithmetic with "Cannot mix BigInt and other
      // types" when callers do plain int math on the result.
      return { kind: "int", int: idx };
    });
    // scan_run — return the end-index where a contiguous run of bytes
    // matching `class_code` ends (exclusive). Sibling parity with Go +
    // Rust scan_run. Generic per-byte loop in JS avoids the walker
    // dispatch a pure-Form recursion would pay per character.
    // Class codes: 0=ws, 1=digit, 2=alpha, 3=identifier-char,
    //              4=non-quote-non-escape, 5=non-newline.
    this.registerNative("scan_run", catAccess(), (_k, args) => {
      const s = argStr(args, 0);
      const from = Math.max(0, argInt(args, 1));
      const cls = argInt(args, 2);
      const n = s.length;
      let end = Math.min(from, n);
      switch (cls) {
        case 0: { // whitespace
          while (end < n) {
            const c = s.charCodeAt(end);
            if (c !== 32 && c !== 9 && c !== 10 && c !== 13) break;
            end++;
          }
          break;
        }
        case 1: { // ascii digit
          while (end < n) {
            const c = s.charCodeAt(end);
            if (c < 48 || c > 57) break;
            end++;
          }
          break;
        }
        case 2: { // ascii alpha
          while (end < n) {
            const c = s.charCodeAt(end);
            if (!((c >= 97 && c <= 122) || (c >= 65 && c <= 90))) break;
            end++;
          }
          break;
        }
        case 3: { // identifier char
          while (end < n) {
            const c = s.charCodeAt(end);
            const isAlnum = (c >= 97 && c <= 122) || (c >= 65 && c <= 90) || (c >= 48 && c <= 57);
            if (!(isAlnum || c === 95 || c === 45)) break;
            end++;
          }
          break;
        }
        case 4: { // non-quote-non-escape
          while (end < n) {
            const c = s.charCodeAt(end);
            if (c === 34 || c === 92) break;
            end++;
          }
          break;
        }
        case 5: { // non-newline
          while (end < n) {
            if (s.charCodeAt(end) === 10) break;
            end++;
          }
          break;
        }
        default:
          throw new Error(`scan_run: unknown class_code ${cls} (valid: 0-5)`);
      }
      return { kind: "int", int: end };
    });
    // string_fold — JS-level streaming iteration over a string's chars.
    // Signature: (string_fold s init step) where step is a closure of
    // (acc, char) → acc. Whole iteration in this JS for-loop; no Form-
    // level recursion. Lets the substrate process arbitrary-length input
    // streams without piling kernel stack frames.
    this.registerNative("string_fold", catCall(), (k, args) => {
      const s = argStr(args, 0);
      let acc = args[1]!;
      const fnVal = args[2]!;
      if (fnVal.kind !== "closure") {
        throw new Error("string_fold: third arg must be a closure");
      }
      const cl = fnVal.closure;
      if (cl.params.length !== 2) {
        throw new Error(
          `string_fold: step closure wants 2 params (acc char), got ${cl.params.length}`,
        );
      }
      for (let i = 0; i < s.length; i++) {
        const callFrame = new Frame(cl.env);
        callFrame.bind(cl.params[0]!, acc);
        callFrame.bind(cl.params[1]!, { kind: "str", str: s[i]! });
        acc = walk(k, cl.body, callFrame);
      }
      return acc;
    });
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
    this.registerNative("byte_to_str", catAccess(), (_k, args) => {
      const b = argInt(args, 0);
      return { kind: "str", str: b >= 0 && b <= 255 ? String.fromCharCode(b) : "" };
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
      if (v?.kind === "list") {
        // Dict-aware: tagged "__dict__" lists report pair count,
        // matching Python's len(d) semantics.
        if (
          v.list.length > 0 &&
          v.list[0]!.kind === "str" &&
          v.list[0]!.str === "__dict__"
        ) {
          return { kind: "int", int: (v.list.length - 1) / 2 };
        }
        return { kind: "int", int: v.list.length };
      }
      if (v?.kind === "str") return { kind: "int", int: v.str.length };
      return { kind: "int", int: 0 };
    });
    this.registerNative("nth", catAccess(), (_k, args) => {
      const lst = argList(args, 0);
      const i = argInt(args, 1);
      return lst[i] ?? { kind: "null" };
    });
    this.registerNative("empty", catListNat(), () => ({ kind: "list", list: [] }));
    // --- Dict natives — sibling-parity with Rust _dict_* + _get + _in ---
    // Dicts are first-class but ride on Value{kind:"list"} with a
    // "__dict__" tag in slot 0 followed by alternating key/value pairs:
    //   ["__dict__", k0, v0, k1, v1, ...]
    // Keys can be strings or ints; equality uses value-level compare.
    // Updates are immutable: _dict_set returns a fresh dict.
    // Plain boolean predicate (not a TS type guard) so the kind narrowing
    // after the dict branch still allows the regular "list" path through.
    const isDictValue = (v: Value): boolean =>
      v.kind === "list" &&
      v.list.length > 0 &&
      v.list[0]!.kind === "str" &&
      v.list[0]!.str === "__dict__";
    const dictKeyEq = (a: Value, b: Value): boolean => {
      if (a.kind === "str" && b.kind === "str") return a.str === b.str;
      if (a.kind === "int" && b.kind === "int") return a.int === b.int;
      return false;
    };
    this.registerNative("_dict_new", catListNat(), (_k, args) => ({
      kind: "list",
      list: [{ kind: "str", str: "__dict__" }, ...args],
    }));
    // Local helper to access the underlying list of a dict-shaped value
    // without losing type info — TS narrows away the "list" branch after
    // the boolean predicate, so this cast is the cheapest reconciliation.
    const dictList = (v: Value): Value[] => (v as { kind: "list"; list: Value[] }).list;
    this.registerNative("_dict_get", catAccess(), (_k, args) => {
      const d = args[0]!;
      const key = args[1]!;
      if (!isDictValue(d)) return { kind: "null" };
      const xs = dictList(d);
      for (let i = 1; i + 1 < xs.length; i += 2) {
        if (dictKeyEq(xs[i]!, key)) return xs[i + 1]!;
      }
      return { kind: "null" };
    });
    this.registerNative("_dict_set", catMethod(), (_k, args) => {
      const d = args[0]!;
      const key = args[1]!;
      const val = args[2]!;
      if (!isDictValue(d)) return d;
      const out = dictList(d).slice();
      for (let i = 1; i + 1 < out.length; i += 2) {
        if (dictKeyEq(out[i]!, key)) {
          out[i + 1] = val;
          return { kind: "list", list: out };
        }
      }
      out.push(key, val);
      return { kind: "list", list: out };
    });
    this.registerNative("_dict_has", catCompareEq(), (_k, args) => {
      const d = args[0]!;
      const key = args[1]!;
      if (!isDictValue(d)) return { kind: "bool", bool: false };
      const xs = dictList(d);
      for (let i = 1; i + 1 < xs.length; i += 2) {
        if (dictKeyEq(xs[i]!, key)) return { kind: "bool", bool: true };
      }
      return { kind: "bool", bool: false };
    });
    this.registerNative("_dict_keys", catAccess(), (_k, args) => {
      const d = args[0]!;
      if (!isDictValue(d)) return { kind: "list", list: [] };
      const xs = dictList(d);
      const out: Value[] = [];
      for (let i = 1; i + 1 < xs.length; i += 2) out.push(xs[i]!);
      return { kind: "list", list: out };
    });
    this.registerNative("_dict_values", catAccess(), (_k, args) => {
      const d = args[0]!;
      if (!isDictValue(d)) return { kind: "list", list: [] };
      const xs = dictList(d);
      const out: Value[] = [];
      for (let i = 1; i + 1 < xs.length; i += 2) out.push(xs[i + 1]!);
      return { kind: "list", list: out };
    });
    // _get — polymorphic subscript. Dispatches list[i]/str[i] to nth and
    // dict[k] to _dict_get. The Python emitter compiles subscript to
    // (_get value index) so the same .fk runs over either container.
    this.registerNative("_get", catAccess(), (_k, args) => {
      const v = args[0]!;
      const idx = args[1]!;
      if (isDictValue(v)) {
        const xs = dictList(v);
        for (let i = 1; i + 1 < xs.length; i += 2) {
          if (dictKeyEq(xs[i]!, idx)) return xs[i + 1]!;
        }
        return { kind: "null" };
      }
      if (v.kind === "list") {
        const i = idx.kind === "int" ? idx.int : 0;
        if (i < 0 || i >= v.list.length) return { kind: "null" };
        return v.list[i]!;
      }
      if (v.kind === "str") {
        const i = idx.kind === "int" ? idx.int : 0;
        if (i < 0 || i >= v.str.length) return { kind: "str", str: "" };
        return { kind: "str", str: v.str[i] ?? "" };
      }
      return { kind: "null" };
    });
    // _iter — turn any container into a flat list suitable for the
    // for-loop emitter's head/tail walk. Lists pass through; dicts
    // become their keys (Python's `for k in d:`); strings split per char.
    this.registerNative("_iter", catListNat(), (_k, args) => {
      const v = args[0]!;
      if (isDictValue(v)) {
        const xs = dictList(v);
        const out: Value[] = [];
        for (let i = 1; i + 1 < xs.length; i += 2) out.push(xs[i]!);
        return { kind: "list", list: out };
      }
      if (v.kind === "list") return v;
      if (v.kind === "str") {
        return {
          kind: "list",
          list: v.str.split("").map((c) => ({ kind: "str", str: c }) as Value),
        };
      }
      return { kind: "list", list: [] };
    });
    // _in — polymorphic membership. (`k in d` → _in d k). Dict keys,
    // list elements, or substring presence in a string.
    this.registerNative("_in", catCompareEq(), (_k, args) => {
      const needle = args[0]!;
      const hay = args[1]!;
      if (isDictValue(hay)) {
        const xs = dictList(hay);
        for (let i = 1; i + 1 < xs.length; i += 2) {
          if (dictKeyEq(xs[i]!, needle))
            return { kind: "bool", bool: true };
        }
        return { kind: "bool", bool: false };
      }
      if (hay.kind === "list") {
        for (const v of hay.list) {
          if (
            (needle.kind === "int" && v.kind === "int" && needle.int === v.int) ||
            (needle.kind === "str" && v.kind === "str" && needle.str === v.str) ||
            (needle.kind === "bool" && v.kind === "bool" && needle.bool === v.bool)
          ) {
            return { kind: "bool", bool: true };
          }
        }
        return { kind: "bool", bool: false };
      }
      if (needle.kind === "str" && hay.kind === "str") {
        return { kind: "bool", bool: hay.str.includes(needle.str) };
      }
      return { kind: "bool", bool: false };
    });
    // --- Substrate read primitives — kernel reaches the REST surface ----
    // Sibling-parity with the Rust kernel's http_get + _json_get + _json_to_dict.
    // The kernel walker is synchronous, so HTTP rides on curl via execFileSync
    // rather than on Node's async fetch. Matches Rust's blocking ureq path.
    // Surface stays /api/substrate/* shaped (public read, no credentials).
    //
    // http_get(url) → str|null. null on transport error so Form-side caller
    // can match and decide.
    this.registerNative("http_get", catCall(), (_k, args) => {
      const url = argStr(args, 0);
      try {
        // -sS: silent but show errors; --fail: non-2xx exits non-zero.
        const out = execFileSync("curl", ["-sS", "--fail", "--max-time", "30", url], {
          encoding: "utf8",
          maxBuffer: 64 * 1024 * 1024, // 64 MB — enough for the substrate's
                                         // largest read surfaces (histograms,
                                         // cell lists) without truncation.
          stdio: ["ignore", "pipe", "ignore"],
        });
        return { kind: "str", str: out };
      } catch {
        return { kind: "null" };
      }
    });
    // _json_get(json_str, key) → str|int|float|bool|null. Parse a top-level
    // JSON object and extract obj[key]. Returns null on miss / parse error.
    // Nested objects come back as JSON strings so Form code composes via
    // repeated _json_get (jq-pipeline shape).
    this.registerNative("_json_get", catAccess(), (_k, args) => {
      const body = argStr(args, 0);
      const key = argStr(args, 1);
      let parsed: unknown;
      try {
        parsed = JSON.parse(body);
      } catch {
        return { kind: "null" };
      }
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        return { kind: "null" };
      }
      const v = (parsed as Record<string, unknown>)[key];
      if (v === undefined || v === null) return { kind: "null" };
      if (typeof v === "boolean") return { kind: "bool", bool: v };
      if (typeof v === "number") {
        return Number.isInteger(v)
          ? { kind: "int", int: v }
          : { kind: "f64", float: v };
      }
      if (typeof v === "string") return { kind: "str", str: v };
      // Arrays / nested objects: re-serialize so the caller can re-parse.
      return { kind: "str", str: JSON.stringify(v) };
    });
    // _json_to_dict(json_str) → __dict__-tagged list. Convenience for the
    // common /api/substrate/lattice/stats shape — a flat object the caller
    // wants to address as a dict directly. Nested values come back as JSON
    // string children, consistent with _json_get.
    this.registerNative("_json_to_dict", catMethod(), (_k, args) => {
      const body = argStr(args, 0);
      let parsed: unknown;
      try {
        parsed = JSON.parse(body);
      } catch {
        return { kind: "null" };
      }
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        return { kind: "null" };
      }
      const out: Value[] = [{ kind: "str", str: "__dict__" }];
      for (const [k, v] of Object.entries(parsed)) {
        out.push({ kind: "str", str: k });
        if (v === null) out.push({ kind: "null" });
        else if (typeof v === "boolean") out.push({ kind: "bool", bool: v });
        else if (typeof v === "number") {
          out.push(
            Number.isInteger(v)
              ? { kind: "int", int: v }
              : { kind: "f64", float: v },
          );
        } else if (typeof v === "string") out.push({ kind: "str", str: v });
        else out.push({ kind: "str", str: JSON.stringify(v) });
      }
      return { kind: "list", list: out };
    });
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
    // ── Python `math` module — a tight kernel-native shape ─────────
    // The Python adapter rewrites `math.sqrt(x)` → `(math_sqrt x)`,
    // `math.pi` → `(math_pi)`, etc. at parse time, so imports compile to
    // nothing at runtime. Sibling-parity with the Rust kernel; the
    // entries are deliberately tight (sqrt, pi, floor, ceil, pow) —
    // demonstrably useful for substrate code without enlarging the
    // bootstrap surface.
    this.registerNative("math_sqrt", catMethod(), (_k, args) => {
      return { kind: "f64", float: Math.sqrt(argFloat(args, 0)) };
    });
    this.registerNative("math_pi", catMethod(), () => ({
      kind: "f64",
      float: Math.PI,
    }));
    // math.floor — CPython 3 returns an `int`. We follow suit so
    // parity-suite string comparisons match. Math.floor in JS returns
    // a number; we coerce to int explicitly.
    this.registerNative("math_floor", catMethod(), (_k, args) => {
      return { kind: "int", int: Math.floor(argFloat(args, 0)) };
    });
    this.registerNative("math_ceil", catMethod(), (_k, args) => {
      return { kind: "int", int: Math.ceil(argFloat(args, 0)) };
    });
    // math.pow — always returns float, matching CPython's behaviour.
    // (CPython's `math.pow(2, 3)` returns `8.0`, not `8`. The built-in
    // `pow()` would return int for int arguments; we don't expose that.)
    this.registerNative("math_pow", catMethod(), (_k, args) => {
      return {
        kind: "f64",
        float: Math.pow(argFloat(args, 0), argFloat(args, 1)),
      };
    });
    // ── Python `typing` module — opaque sentinels ───────────────────
    // Every typing import (List, Optional, Dict, Tuple, Any, Callable,
    // Union, Iterable, Iterator, Mapping, Sequence, Set, FrozenSet) binds
    // to this single native. Type annotations are parse-and-ignored at
    // compile time, so this never fires in real code; its existence makes
    // the `from typing import …` binding round-trip honest. Any accidental
    // runtime reference returns the same opaque string in all three
    // runtimes (CPython, TS eval, Rust kernel).
    this.registerNative("typing_opaque", catMethod(), () => ({
      kind: "str",
      str: "<typing>",
    }));
    // File I/O
    this.registerNative("read_file", catCall(), (_k, args) => {
      try {
        return { kind: "str", str: readFileSync(argStr(args, 0), "utf8") };
      } catch {
        return { kind: "null" };
      }
    });
    // Byte-level host file read — returns a list of ints (0-255), one per byte.
    this.registerNative("read_file_bytes", catCall(), (_k, args) => {
      try {
        const buf = readFileSync(argStr(args, 0));
        const out: Value[] = new Array(buf.length);
        for (let i = 0; i < buf.length; i++) {
          out[i] = { kind: "int", int: buf[i]! };
        }
        return { kind: "list", list: out };
      } catch {
        return { kind: "null" };
      }
    });
    // random_bytes(n) — open the doorway. Reads n bytes from
    // /dev/urandom every call. Different per invocation, per kernel
    // process. lc-divergence-is-the-doorway: this native intentionally
    // violates sibling parity when invoked — the divergence is the
    // substrate's signal of live field-touch.
    this.registerNative("random_bytes", catCall(), (_k, args) => {
      const n = argInt(args, 0);
      if (n <= 0) return { kind: "list", list: [] };
      try {
        const fd = openSync("/dev/urandom", "r");
        const buf = Buffer.alloc(n);
        let read = 0;
        while (read < n) {
          const got = readSync(fd, buf, read, n - read, null);
          if (got <= 0) break;
          read += got;
        }
        closeSync(fd);
        if (read !== n) return { kind: "null" };
        const out: Value[] = new Array(n);
        for (let i = 0; i < n; i++) {
          out[i] = { kind: "int", int: buf[i]! };
        }
        return { kind: "list", list: out };
      } catch {
        return { kind: "null" };
      }
    });
    // ---- bitwise primitives -----------------------------------
    // True kernel primitives — cannot be expressed in pure Form
    // without exponential cost. Operate on 32-bit-unsigned semantics
    // (>>> 0 to coerce back to unsigned) so SHA-256-style recipes
    // compose round functions over machine-word integers consistently.
    this.registerNative("band", catMethod(), (_k, args) => ({
      kind: "int",
      int: (argInt(args, 0) & argInt(args, 1)) >>> 0,
    }));
    this.registerNative("bor", catMethod(), (_k, args) => ({
      kind: "int",
      int: (argInt(args, 0) | argInt(args, 1)) >>> 0,
    }));
    this.registerNative("bxor", catMethod(), (_k, args) => ({
      kind: "int",
      int: (argInt(args, 0) ^ argInt(args, 1)) >>> 0,
    }));
    this.registerNative("bnot_u32", catMethod(), (_k, args) => ({
      kind: "int",
      int: ~argInt(args, 0) >>> 0,
    }));
    this.registerNative("shl_u32", catMethod(), (_k, args) => ({
      kind: "int",
      int: (argInt(args, 0) << (argInt(args, 1) & 31)) >>> 0,
    }));
    this.registerNative("shr_u32", catMethod(), (_k, args) => ({
      kind: "int",
      int: argInt(args, 0) >>> (argInt(args, 1) & 31),
    }));
    this.registerNative("rotr_u32", catMethod(), (_k, args) => {
      const a = argInt(args, 0) >>> 0;
      const n = argInt(args, 1) & 31;
      return { kind: "int", int: ((a >>> n) | (a << (32 - n))) >>> 0 };
    });
    // add_u32: modular 32-bit addition — SHA-256's round constants
    // and message schedule both require this discipline.
    this.registerNative("add_u32", catMethod(), (_k, args) => ({
      kind: "int",
      int: (argInt(args, 0) + argInt(args, 1)) >>> 0,
    }));
    // sha256_bytes / bytes_sum / bytes_hash were temporarily added as
    // natives here but composted: those are composites, not primitives.
    // SHA-256 lives in form-stdlib/sha256.fk as a Form recipe over the
    // bitwise primitives above. The real JIT path (Form recipe → host
    // JS via compiler.ts + new Function) is the next walk; this kernel
    // currently relies on recipe-walk for composite operations.
    // register_jit form-name-str native-name-str → 1 on bind, 0 if
    // native-name has no registered native (refuse silent miss).
    // Inserts (form-name → native-name) into k.jitAliases. After this,
    // every (form-name ...) call goes through the aliased native instead
    // of walking the Form definition. Form recipes are canonical truth;
    // register_jit is the opt-in that promotes a recipe to host-native
    // execution. Removing the entry restores the Form walk.
    this.registerNative("register_jit", catWitness(), (k, args) => {
      const formName = argStr(args, 0);
      const nativeName = argStr(args, 1);
      const nativeID = k.internName(nativeName);
      if (!k.natives.has(nativeID) && !k.envNatives.has(nativeID)) {
        return { kind: "int", int: 0 };
      }
      const formID = k.internName(formName);
      k.jitAliases.set(formID, nativeID);
      return { kind: "int", int: 1 };
    });
    // unregister_jit form-name-str → 1 if removed, 0 if no alias was
    // bound. Restores the Form-recipe walk path for that name.
    this.registerNative("unregister_jit", catWitness(), (k, args) => {
      const formName = argStr(args, 0);
      const formID = k.internName(formName);
      if (k.jitAliases.has(formID)) {
        k.jitAliases.delete(formID);
        return { kind: "int", int: 1 };
      }
      return { kind: "int", int: 0 };
    });
    // jit_aliased? form-name-str → 1 if a JIT alias is currently bound
    // for this name, else 0. Lets Form code introspect dispatch routing.
    this.registerNative("jit_aliased?", catCompareEq(), (k, args) => {
      const formName = argStr(args, 0);
      const formID = k.internName(formName);
      return { kind: "int", int: k.jitAliases.has(formID) ? 1 : 0 };
    });
    // recipe_to_bytes nid → list-of-bytes (or null on error).
    //   Serializes a Recipe subtree to the .fkb wire format as a byte
    //   list — usable over any byte channel without a file detour.
    this.registerNative("recipe_to_bytes", catWitness(), (k, args) => {
      const nid = argNodeID(args, 0);
      const bytes = serializeRecipeArtifact(k, nid);
      const out: Value[] = new Array(bytes.length);
      for (let i = 0; i < bytes.length; i++) {
        out[i] = { kind: "int", int: bytes[i]! };
      }
      return { kind: "list", list: out };
    });
    // bytes_to_recipe bytes-list → nid (or null on parse error).
    this.registerNative("bytes_to_recipe", catWitness(), (k, args) => {
      const a0 = args[0];
      if (!a0 || a0.kind !== "list") return { kind: "null" };
      const bytes = new Uint8Array(a0.list.length);
      for (let i = 0; i < a0.list.length; i++) {
        const v = a0.list[i];
        bytes[i] = v && v.kind === "int" ? v.int & 0xff : 0;
      }
      try {
        const nid = deserializeRecipeArtifact(k, bytes);
        return { kind: "nodeid", nodeid: nid };
      } catch {
        return { kind: "null" };
      }
    });
    // jit_compile form-name-str → 1 if a host-JIT compile succeeded
    // for the closure under this name, 0 if no compiler is available
    // (Rust + Go return 0 today; cranelift + plugin paths are future
    // walks), -1 if the name isn't bound to a closure in the current
    // env. After a successful compile, every (form-name args...) call
    // dispatches through the compiled function instead of walking the
    // recipe tree — same canonical Form recipe; host-native speed.
    this.registerEnvNative("jit_compile", catWitness(), (k, env, args) => {
      if (k.jitCompileHook === null) {
        // Compiler not installed on this kernel build — honest 0 so
        // sibling-Form code can branch on availability.
        return { kind: "int", int: 0 };
      }
      const formName = argStr(args, 0);
      const formID = k.internName(formName);
      const v = env.lookup(formID);
      if (v === undefined || v.kind !== "closure") {
        return { kind: "int", int: -1 };
      }
      const compiled = k.jitCompileHook(k, v.closure.body);
      k.jitCompiled.set(
        `${v.closure.body.pkg}.${v.closure.body.level}.${v.closure.body.type}.${v.closure.body.inst}`,
        compiled,
      );
      return { kind: "int", int: 1 };
    });
    // seeded_bytes(seed, count) — deterministic LCG byte stream.
    // Same (seed, count) → byte-identical output across Go / Rust / TS.
    // glibc rand(): state = (state * 1103515245 + 12345) & 0x7FFFFFFF
    // BigInt used because intermediate product exceeds Number safe range.
    this.registerNative("seeded_bytes", catCall(), (_k, args) => {
      const count = argInt(args, 1);
      if (count <= 0) return { kind: "list", list: [] };
      let state = BigInt(argInt(args, 0)) & 0x7FFFFFFFn;
      const A = 1103515245n;
      const C = 12345n;
      const M = 0x7FFFFFFFn;
      const F = 0xFFn;
      const out: Value[] = new Array(count);
      for (let i = 0; i < count; i++) {
        state = (state * A + C) & M;
        out[i] = { kind: "int", int: Number(state & F) };
      }
      return { kind: "list", list: out };
    });
    // sum_bytes_list(list) — fast O(n) compiled sum, used by the
    // private-channel protocol to verify large payloads agree without
    // walking the list through interpreted Form recursion.
    this.registerNative("sum_bytes_list", catCall(), (_k, args) => {
      const a = args[0]!;
      if (a.kind !== "list") return { kind: "int", int: 0 };
      let s = 0;
      for (const v of a.list) {
        if (v.kind === "int") s += v.int;
      }
      return { kind: "int", int: s };
    });
    // write_form_binary — emit a Recipe to .fkb in the full artifact
    // format (string table + tree). Sibling to read_form_binary.
    this.registerNative("write_form_binary", catCall(), (k, args) => {
      const path = argStr(args, 0);
      const nid = argNodeID(args, 1);
      const bytes = serializeRecipeArtifact(k, nid);
      try {
        writeFileSync(path, bytes);
        // `kind: "int"` carries a JS Number — BigInt poisons downstream
        // arithmetic with "Cannot mix BigInt and other types" when
        // callers do plain int math on the byte count.
        return { kind: "int", int: bytes.length };
      } catch {
        return { kind: "int", int: -1 };
      }
    });
    this.registerNative("read_form_binary", catCall(), (k, args) => {
      try {
        return {
          kind: "nodeid",
          nodeid: deserializeRecipeArtifact(k, readFileSync(argStr(args, 0))),
        };
      } catch {
        return { kind: "null" };
      }
    });
    this.registerNative("write_form_binary", catCall(), (k, args) => {
      try {
        const bytes = serializeRecipeArtifact(k, argNodeID(args, 1));
        writeFileSync(argStr(args, 0), bytes);
        return { kind: "int", int: bytes.length };
      } catch {
        return { kind: "int", int: -1 };
      }
    });
    this.registerNative("file_size", catCall(), (_k, args) => {
      try {
        return { kind: "int", int: statSync(argStr(args, 0)).size };
      } catch {
        return { kind: "int", int: -1 };
      }
    });
    // file_mtime — modification time in unix seconds; -1 if missing.
    // Sibling parity with Go + Rust file_mtime; powers Form-side cache
    // layers that regenerate .fkb projections when source files drift.
    this.registerNative("file_mtime", catCall(), (_k, args) => {
      try {
        return { kind: "int", int: Math.floor(statSync(argStr(args, 0)).mtimeMs / 1000) };
      } catch {
        return { kind: "int", int: -1 };
      }
    });
    this.registerNative("file_byte_at", catCall(), (_k, args) => {
      const offset = argInt(args, 1);
      if (offset < 0) return { kind: "int", int: -1 };
      let fd: number | undefined;
      try {
        fd = openSync(argStr(args, 0), "r");
        const buf = Buffer.allocUnsafe(1);
        const n = readSync(fd, buf, 0, 1, offset);
        return { kind: "int", int: n === 1 ? buf[0]! : -1 };
      } catch {
        return { kind: "int", int: -1 };
      } finally {
        if (fd !== undefined) closeSync(fd);
      }
    });
    this.registerNative("read_file_slice", catCall(), (_k, args) => {
      const offset = argInt(args, 1);
      const length = argInt(args, 2);
      if (offset < 0 || length <= 0) return { kind: "str", str: "" };
      let fd: number | undefined;
      try {
        fd = openSync(argStr(args, 0), "r");
        const buf = Buffer.allocUnsafe(length);
        const n = readSync(fd, buf, 0, length, offset);
        return { kind: "str", str: buf.subarray(0, n).toString("utf8") };
      } catch {
        return { kind: "str", str: "" };
      } finally {
        if (fd !== undefined) closeSync(fd);
      }
    });
    // write_file_bytes — sibling of read_file_bytes; writes a byte list.
    // Sibling-parity with form-kernel-go + form-kernel-rust. Values out of
    // 0..255 truncate per Go's `byte(v.Int)` and Rust's `as u8`.
    this.registerNative("write_file_bytes", catCall(), (_k, args) => {
      try {
        const path = argStr(args, 0);
        const list = argList(args, 1);
        const buf = Buffer.alloc(list.length);
        for (let i = 0; i < list.length; i++) {
          buf[i] = argInt(list, i) & 0xff;
        }
        writeFileSync(path, buf);
        return { kind: "int", int: buf.length };
      } catch {
        return { kind: "int", int: -1 };
      }
    });
    // Host text output. Byte codecs still use write_file_bytes in kernels
    // that expose it; text compilers do not need to materialize byte lists.
    this.registerNative("write_file_text", catCall(), (_k, args) => {
      try {
        const text = argStr(args, 1);
        writeFileSync(argStr(args, 0), text, "utf8");
        return { kind: "int", int: Buffer.byteLength(text, "utf8") };
      } catch {
        return { kind: "int", int: -1 };
      }
    });

    // --- Socket natives — L1 physical layer for inter-cell IO ---------
    // Sibling parity with form-kernel-go + form-kernel-rust at the API
    // surface. TS scope limit: socket_listen / socket_accept / socket_recv
    // are panic-stubs because Node's event-loop architecture cannot do
    // blocking accept/read without a worker-thread + SharedArrayBuffer
    // shim — that work is deferred to a later breath. socket_close is
    // safe on -1 (sibling-parity no-op returning -1), so the band can
    // witness API existence without crossing into the panic-stub region.
    // TODO: implement TS sockets when we have a blocking shim
    //       (Atomics.wait + worker_threads sync read).
    this.registerNative("socket_listen", catCall(), (_k, _args) => {
      throw new Error(
        "socket_listen: TS kernel has no blocking-accept shim yet — " +
          "sibling-loud-divergent panic-stub; use Go or Rust kernel for " +
          "server-side socket work this breath.",
      );
    });
    this.registerNative("socket_accept", catCall(), (_k, _args) => {
      throw new Error(
        "socket_accept: TS kernel has no blocking-accept shim yet — " +
          "sibling-loud-divergent panic-stub; use Go or Rust kernel.",
      );
    });
    this.registerNative("socket_connect", catCall(), (_k, _args) => {
      throw new Error(
        "socket_connect: TS kernel has no blocking-IO shim yet — " +
          "sibling-loud-divergent panic-stub; use Go or Rust kernel.",
      );
    });
    this.registerNative("socket_send", catCall(), (_k, _args) => {
      throw new Error(
        "socket_send: TS kernel has no blocking-IO shim yet — " +
          "sibling-loud-divergent panic-stub; use Go or Rust kernel.",
      );
    });
    this.registerNative("socket_recv", catCall(), (_k, _args) => {
      throw new Error(
        "socket_recv: TS kernel has no blocking-IO shim yet — " +
          "sibling-loud-divergent panic-stub; use Go or Rust kernel.",
      );
    });
    // socket_close — the one socket native that has a sibling-safe
    // sentinel branch on all three kernels: a -1 handle returns -1
    // without touching the (nonexistent) TS connection table. Used by
    // tests/socket-band.fk to witness that the API surface EXISTS on
    // all three kernels even when the implementation diverges.
    this.registerNative("socket_close", catCall(), (_k, args) => {
      const h = argInt(args, 0);
      if (h < 0) return { kind: "int", int: -1 };
      // No connection table in TS — handles > 0 are necessarily stale
      // (we never returned one), so -1 is the honest response.
      return { kind: "int", int: -1 };
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
    // bp — Blueprint name → NodeID, looked up in the generated BP_TABLE.
    // Unknown name resolves to the undefined node (1,2,0,0).
    this.registerNative("bp", catWitness(), (_k, args) => {
      const name = argStr(args, 0);
      const entry = BP_TABLE[name];
      const [pkg, level, type, inst] = entry ?? [1, 2, 0, 0];
      return { kind: "nodeid", nodeid: { pkg, level, type, inst } };
    });
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
    this.registerNative("substrate_mark", catWitness(), (k, _args) => ({
      kind: "list",
      list: k.substrateMark(),
    }));
    this.registerNative("substrate_counts", catWitness(), (k, _args) => ({
      kind: "list",
      list: k.substrateCounts(),
    }));
    this.registerNative("substrate_release", catWitness(), (k, args) => ({
      kind: "int",
      int: k.substrateRelease(argList(args, 0)),
    }));
    this.registerNative("substrate_gc", catWitness(), (k, args) => ({
      kind: "list",
      list: k.substrateGC(argList(args, 0)),
    }));
    this.registerNative("intern_node_at", catWitness(), (k, args) => {
      const cat = argNodeID(args, 0);
      const kids = argList(args, 1).map((v) => {
        if (v.kind !== "nodeid")
          throw new Error("intern_node_at: children must be nodeids");
        return v.nodeid;
      });
      const nid = k.intern(cat, kids);
      const file = k.internName(argStr(args, 2));
      k.sourceAttr.set(nodeKey(nid), {
        file,
        line: argInt(args, 3),
        col: argInt(args, 4),
      });
      return { kind: "nodeid", nodeid: nid };
    });
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
    this.registerNative("node_pkg", catWitness(), (_k, args) => ({
      kind: "int",
      int: argNodeID(args, 0).pkg,
    }));
    this.registerNative("node_level", catWitness(), (_k, args) => ({
      kind: "int",
      int: argNodeID(args, 0).level,
    }));
    this.registerNative("node_type", catWitness(), (_k, args) => ({
      kind: "int",
      int: argNodeID(args, 0).type,
    }));
    this.registerNative("node_inst", catWitness(), (_k, args) => ({
      kind: "int",
      int: argNodeID(args, 0).inst,
    }));
    this.registerNative("node_source", catWitness(), (k, args) => {
      const loc = k.sourceAttr.get(nodeKey(argNodeID(args, 0)));
      if (!loc) return { kind: "list", list: [] };
      return {
        kind: "list",
        list: [
          { kind: "str", str: k.strs[loc.file] ?? "" },
          { kind: "int", int: loc.line },
          { kind: "int", int: loc.col },
        ],
      };
    });
    this.registerNative("framebuffer-events", catWitness(), (k, _args) => ({
      kind: "list",
      list: Array.from(k.sourceAttr.keys()).map((key) => {
        return { kind: "nodeid", nodeid: nodeFromKey(key) } as Value;
      }),
    }));
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
    // value_eq — polymorphic equality across Value kinds. Returns true
    // when both args have the same kind AND compare equal within that
    // kind. Cross-kind returns false. Use when a Form-side function
    // holds tagged values that may be either strings or NodeIDs —
    // e.g. domain/lens in bmf-symbol-context.
    this.registerNative("value_eq", catCompareEq(), (_k, args) => {
      const a = args[0]!;
      const b = args[1]!;
      return { kind: "bool", bool: valueEqual(a, b) };
    });
    this.registerNative("serialize-recipe", catWitness(), (k, args) => {
      const out: number[] = [];
      serializeNode(k, argNodeID(args, 0), out);
      return {
        kind: "list",
        list: out.map((byte) => ({ kind: "int", int: byte } as Value)),
      };
    });
    this.registerNative("deserialize-recipe", catWitness(), (k, args) => {
      const bytes = Uint8Array.from(argList(args, 0).map((v) => {
        if (v.kind !== "int") throw new Error("deserialize-recipe: bytes must be ints");
        return v.int & 0xff;
      }));
      const [root, end] = deserializeRawNode(k, bytes, 0, k.nextImportScope());
      if (end !== bytes.length) throw new Error("deserialize-recipe: trailing bytes");
      return { kind: "nodeid", nodeid: root };
    });
    this.registerNative("walk_recipe", catWitness(), (k, args) =>
      walk(k, argNodeID(args, 0), new Frame(null)),
    );
    // walk_recipe_here — walks a Recipe in the CALLER's env, so let-
    // bindings inside the Recipe land in the caller's scope. Matches
    // the Go and Rust kernels' env-aware variant.
    this.registerEnvNative("walk_recipe_here", catWitness(), (k, env, args) => {
      // Pin the recipe root as an active root so substrate_gc keeps the
      // definitions reachable. Closures bound here hold body NodeIDs that
      // aren't reachable from the source-parsed root, so without this pin
      // a subsequent substrate_gc would sweep them and leave env holding
      // closures with deleted bodies.
      const root = argNodeID(args, 0);
      k.pushActiveRoot(root);
      return walk(k, root, env);
    });
    const walkParallel: NativeFn = (k, args) => {
      const roots = argList(args, 0).map((value) => {
        if (value.kind !== "nodeid")
          throw new Error("walk_parallel: first argument must be a list of NodeIDs");
        return value.nodeid;
      });
      const workers = Math.max(1, argInt(args, 1));
      const sequential = (): Value => ({
        kind: "list",
        list: roots.map((root) => walk(k, root, new Frame(null))),
      });
      if (
        workers <= 1 ||
        roots.length <= 1 ||
        k.trace !== undefined ||
        roots.some((root) => !isParallelPure(k, root, new Set<string>()))
      ) {
        return sequential();
      }
      const out: Value[] = new Array(roots.length);
      const workerCount = Math.min(workers, roots.length);
      for (let worker = 0; worker < workerCount; worker++) {
        for (let i = worker; i < roots.length; i += workerCount) {
          out[i] = walk(k, roots[i]!, new Frame(null));
        }
      }
      return { kind: "list", list: out };
    };
    this.registerNative("walk_parallel", catWitness(), walkParallel);
    this.registerNative("walk-parallel", catWitness(), walkParallel);
    const walkParallelCached: NativeFn = (k, args) => {
      const roots = argList(args, 0).map((value) => {
        if (value.kind !== "nodeid")
          throw new Error("walk_parallel_cached: first argument must be a list of NodeIDs");
        return value.nodeid;
      });
      const workers = Math.max(1, argInt(args, 1));
      const allPure = roots.every((root) => isParallelPure(k, root, new Set<string>()));
      const sequential = (cache: boolean): Value => {
        const local = new Map<string, Value>();
        const list = roots.map((root) => {
          const key = nodeKey(root);
          if (cache) {
            const cached = k.walkCache.get(key);
            if (cached !== undefined) {
              k.walkCacheHits++;
              return cached;
            }
            const localCached = local.get(key);
            if (localCached !== undefined) {
              k.walkCacheHits++;
              return localCached;
            }
            k.walkCacheMisses++;
          }
          const value = walk(k, root, new Frame(null));
          if (cache) {
            k.walkCache.set(key, value);
            local.set(key, value);
          }
          return value;
        });
        return { kind: "list", list };
      };
      if (!allPure) return sequential(false);
      if (
        workers <= 1 ||
        roots.length <= 1 ||
        k.trace !== undefined
      ) {
        return sequential(k.trace === undefined);
      }
      const out: Value[] = new Array(roots.length);
      const jobs: Array<[number, NodeID]> = [];
      const first = new Map<string, number>();
      const fanout = new Map<number, number[]>();
      for (let i = 0; i < roots.length; i++) {
        const root = roots[i]!;
        const key = nodeKey(root);
        const cached = k.walkCache.get(key);
        if (cached !== undefined) {
          k.walkCacheHits++;
          out[i] = cached;
        } else if (first.has(key)) {
          k.walkCacheHits++;
          const primary = first.get(key)!;
          const duplicates = fanout.get(primary) ?? [];
          duplicates.push(i);
          fanout.set(primary, duplicates);
        } else {
          k.walkCacheMisses++;
          first.set(key, i);
          jobs.push([i, root]);
        }
      }
      const workerCount = Math.min(workers, roots.length);
      for (let worker = 0; worker < workerCount; worker++) {
        for (let i = worker; i < jobs.length; i += workerCount) {
          const [idx, root] = jobs[i]!;
          out[idx] = walk(k, root, new Frame(null));
        }
      }
      for (const [idx, root] of jobs) {
        k.walkCache.set(nodeKey(root), out[idx]!);
        for (const dup of fanout.get(idx) ?? []) {
          out[dup] = out[idx]!;
        }
      }
      return { kind: "list", list: out };
    };
    this.registerNative("walk_parallel_cached", catWitness(), walkParallelCached);
    this.registerNative("walk-parallel-cached", catWitness(), walkParallelCached);
    this.registerNative("walk-cached", catWitness(), (k, args) => {
      const nid = argNodeID(args, 0);
      const key = nodeKey(nid);
      const cached = k.walkCache.get(key);
      if (cached !== undefined) {
        k.walkCacheHits++;
        return cached;
      }
      k.walkCacheMisses++;
      const value = walk(k, nid, new Frame(null));
      k.walkCache.set(key, value);
      return value;
    });
    this.registerNative("walk-cache-clear", catWitness(), (k, _args) => {
      k.walkCache.clear();
      k.walkCacheHits = 0;
      k.walkCacheMisses = 0;
      return { kind: "null" };
    });
    this.registerNative("walk-cache-size", catWitness(), (k, _args) => ({
      kind: "int",
      int: k.walkCache.size,
    }));
    this.registerNative("walk-cache-stats", catWitness(), (k, _args) => ({
      kind: "list",
      list: [
        { kind: "int", int: k.walkCacheHits },
        { kind: "int", int: k.walkCacheMisses },
        { kind: "int", int: k.walkCache.size },
      ],
    }));

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

    // --- BMF native rule runtime (Path C) ------------------------------
    //
    // bmf_apply_rule_native — additive fast path for engine.fk's
    // apply-object-rule. Sibling port of Go's implementation; the
    // returned Recipe shape (caps alist with "objects" + "result" keys,
    // bmf-match-source captures + span, the result bmf-object as
    // ("cell" rule-name recipe source inverse)) is byte-identical under
    // node_eq to what apply-object-rule produces.
    //
    // POC scope this breath — flat sequence of object-literal matchers,
    // no captures, no choice, no star/opt/cut. Every other shape THROWS
    // loudly so callers can't silently fall off the fast path. Captures
    // + choice + star/opt are queued for a later breath; see
    // docs/coherence-substrate/bmf-native-runtime.form.
    this.registerNative("bmf_apply_rule_native", catWitness(), (k, args) => {
      if (args.length !== 2) {
        throw new Error("bmf_apply_rule_native: expects (rule object-stream)");
      }
      const rule = args[0]!;
      const stream = args[1]!;
      if (rule.kind !== "list" || rule.list.length < 3) {
        throw new Error(
          "bmf_apply_rule_native: rule must be (name pattern action ...)",
        );
      }
      const ruleName = rule.list[0]!;
      const pattern = rule.list[1]!;
      const action = rule.list[2]!;
      const ruleInverse: Value =
        rule.list.length > 3 ? rule.list[3]! : { kind: "null" };
      if (
        pattern.kind !== "list" ||
        pattern.list.length === 0 ||
        pattern.list[0]!.kind !== "str"
      ) {
        throw new Error("bmf_apply_rule_native: pattern must be a tagged list");
      }
      const tag = (pattern.list[0] as { kind: "str"; str: string }).str;
      if (tag !== "sequence") {
        throw new Error(
          `bmf_apply_rule_native: TODO: pattern tag '${tag}' not yet supported (POC: 'sequence' of 'object' literals only)`,
        );
      }
      // Validate every child is an "object" literal — no nesting yet.
      const children = pattern.list.slice(1);
      for (let i = 0; i < children.length; i++) {
        const child = children[i]!;
        if (
          child.kind !== "list" ||
          child.list.length < 3 ||
          child.list[0]!.kind !== "str"
        ) {
          throw new Error(`bmf_apply_rule_native: child ${i} malformed`);
        }
        const ctag = (child.list[0] as { kind: "str"; str: string }).str;
        if (ctag !== "object") {
          throw new Error(
            `bmf_apply_rule_native: TODO: sequence child '${ctag}' not yet supported (POC: 'object' literals only)`,
          );
        }
      }
      // State-machine walk: consume one stream object per literal child.
      if (stream.kind !== "list") {
        throw new Error("bmf_apply_rule_native: object-stream must be a list");
      }
      const streamList = stream.list;
      let consumed = 0;
      for (const child of children) {
        // We validated shape above; narrow now.
        const cl = (child as { kind: "list"; list: Value[] }).list;
        const wantKind =
          cl[1]!.kind === "str" ? (cl[1] as { str: string }).str : "";
        const wantValue =
          cl[2]!.kind === "str" ? (cl[2] as { str: string }).str : "";
        if (consumed >= streamList.length) {
          return {
            kind: "list",
            list: [
              { kind: "str", str: "fail" },
              { kind: "str", str: "expected BMF object" },
            ],
          };
        }
        const obj = streamList[consumed]!;
        if (
          obj.kind !== "list" ||
          obj.list.length < 3 ||
          obj.list[0]!.kind !== "str" ||
          (obj.list[0] as { kind: "str"; str: string }).str !== "cell"
        ) {
          throw new Error("bmf_apply_rule_native: stream item is not a cell");
        }
        const gotKind =
          obj.list[1]!.kind === "str"
            ? (obj.list[1] as { str: string }).str
            : "";
        const gotValue =
          obj.list[2]!.kind === "str"
            ? (obj.list[2] as { str: string }).str
            : "";
        if (gotKind !== wantKind) {
          return {
            kind: "list",
            list: [
              { kind: "str", str: "fail" },
              {
                kind: "str",
                str: `object kind mismatch: expected ${wantKind}`,
              },
            ],
          };
        }
        if (wantValue !== "" && gotValue !== wantValue) {
          return {
            kind: "list",
            list: [
              { kind: "str", str: "fail" },
              {
                kind: "str",
                str: `object value mismatch: expected ${wantValue}`,
              },
            ],
          };
        }
        consumed++;
      }
      // Build captures-as-collection. POC scope: no named captures, so
      // the collection wraps an empty objects list — same shape Form's
      // (bmf-caps-to-collection (cap-empty 0)) produces.
      const emptyCollection: Value = {
        kind: "list",
        list: [
          { kind: "str", str: "bmf-collection" },
          { kind: "list", list: [] },
        ],
      };
      // Consumed prefix slice — what Form's (take N stream) returns.
      const span: Value = { kind: "list", list: streamList.slice(0, consumed) };
      // bmf-match-source captures span.
      const matchSource: Value = {
        kind: "list",
        list: [
          { kind: "str", str: "bmf-match-source" },
          emptyCollection,
          span,
        ],
      };
      // Invoke the action closure: (rule-action captures-collection) →
      // recipe. The only Form re-entry; everything above is native.
      if (action.kind !== "closure") {
        throw new Error(
          "bmf_apply_rule_native: rule action must be a closure",
        );
      }
      const cl = action.closure;
      if (cl.params.length !== 1) {
        throw new Error(
          `bmf_apply_rule_native: action closure takes ${cl.params.length} params, expected 1`,
        );
      }
      const callFrame = new Frame(cl.env);
      callFrame.bind(cl.params[0]!, emptyCollection);
      const recipe = walk(k, cl.body, callFrame);
      // Result bmf-object — ("cell" rule-name recipe source inverse).
      const resultObject: Value = {
        kind: "list",
        list: [
          { kind: "str", str: "cell" },
          ruleName,
          recipe,
          matchSource,
          ruleInverse,
        ],
      };
      // caps alist — cons "result" then "objects" so the alist order
      // matches engine.fk's (cap-set (cap-set ... "objects" ...) "result").
      const caps: Value = {
        kind: "list",
        list: [
          {
            kind: "list",
            list: [{ kind: "str", str: "result" }, resultObject],
          },
          {
            kind: "list",
            list: [{ kind: "str", str: "objects" }, emptyCollection],
          },
        ],
      };
      const rest: Value = { kind: "list", list: streamList.slice(consumed) };
      return {
        kind: "list",
        list: [{ kind: "str", str: "match" }, caps, rest],
      };
    });

    // `now_unix_ms` — current wall-clock as a millisecond unix timestamp.
    // External effect (reads the host clock) so it's catCall. Sibling
    // parity holds on shape, NOT on value: every kernel returns an int,
    // every kernel's int is > a recent past epoch — but the exact
    // milliseconds diverge between invocations. Bands check shape only.
    this.registerNative("now_unix_ms", catCall(), (_k, _args) => ({
      kind: "int",
      int: Date.now(),
    }));

    // Debug — no Form category claimed; honest about being outside the
    // structural vocabulary.
    this.registerNative("trace", catUndefined(), (_k, args) => {
      if (args.length >= 2) {
        const label = args[0]?.kind === "str" ? args[0].str : "trace";
        process.stderr.write(
          `[trace ${label}] ${this.renderForPrint(args[1] ?? { kind: "null" })}\n`,
        );
        return args[1] ?? { kind: "null" };
      }
      const v = args[0] ?? { kind: "null" };
      process.stderr.write(`[trace] ${this.renderForPrint(v)}\n`);
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
      case "record":
        return `<record @${nodeKey(v.record.blueprint)} #${v.record.fields.length}fields>`;
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
  | { kind: "record"; record: Record } // mutable struct/object (BML rung 2)
  | { // #21 — INDUCTIVE-typed value (constructor application result)
      kind: "ctor";
      inductive: NodeID;
      ctor_name: string;
      ctor_index: number;
      args: Value[];
    };

// Record — a mutable struct/object with identity (BML reference, rung 2).
// The first mutable Value the kernel carries; required for `self.x = v`. A
// JS object reference gives shared mutable identity — two bindings to the same
// record see each other's mutations (object semantics, not value-copy).
// blueprint tags the record's type (class / method-table NodeID); fields is
// an ordered name→value map.
export interface Record {
  blueprint: NodeID;
  fields: { name: NameID; val: Value }[];
}

export function recordGet(r: Record, name: NameID): Value | undefined {
  for (let i = r.fields.length - 1; i >= 0; i--) {
    if (r.fields[i]!.name === name) return r.fields[i]!.val;
  }
  return undefined;
}

export function recordSet(r: Record, name: NameID, val: Value): void {
  for (const f of r.fields) {
    if (f.name === name) {
      f.val = val;
      return;
    }
  }
  r.fields.push({ name, val });
}

export interface Closure {
  readonly name: NameID;
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

  entries(): readonly [NameID, Value][] {
    return this.keys.map((key, i) => [key, this.vals[i] ?? { kind: "null" }]);
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

function isParallelPure(k: Kernel, node: NodeID, seen: Set<string>): boolean {
  if (node.level === Level.TRIVIAL) return true;
  const key = nodeKey(node);
  if (seen.has(key)) return true;
  seen.add(key);
  const cat = k.category(node);
  switch (cat.type) {
    case RBasic.MATH:
    case RBasic.COMPARE:
    case RBasic.LOGIC:
    case RBasic.COND:
    case RBasic.LIST:
      return k.children(node).every((child) => isParallelPure(k, child, seen));
    default:
      return false;
  }
}

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
          closure: { name: id, params: [], body: node, env: frame } as Closure,
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
    case "nodeid": {
      const bn = (b as { nodeid: NodeID }).nodeid;
      return (
        a.nodeid.pkg === bn.pkg &&
        a.nodeid.level === bn.level &&
        a.nodeid.type === bn.type &&
        a.nodeid.inst === bn.inst
      );
    }
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

  const closure: Closure = { name: nameID, params, body, env: frame };
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
    const rawName = calleeName;
    // JIT alias: if this Form function-name is JIT-registered, swap to
    // the aliased native-name before native lookup. Form recipes are
    // canonical truth; `register_jit form-name native-name` opts calls
    // into a kernel-resident optimized native.
    const aliased = k.jitAliases.get(rawName);
    const dispatchName = aliased !== undefined ? aliased : rawName;
    // Env-aware natives first — need the caller's env (walk_recipe_here).
    const envNe = k.envNatives.get(dispatchName);
    if (envNe !== undefined && frame.lookup(dispatchName) === undefined) {
      const envArgs: Value[] = [];
      for (let i = 1; i < kids.length; i++) {
        envArgs.push(walk(k, kids[i]!, frame));
      }
      if (envNe.category.type !== RBasic.UNDEFINED) {
        k.trace?.record(envNe.category.type, envNe.category.inst);
      }
      k.trace?.recordNative(k.nameStr(envNe.name));
      return envNe.fn(k, frame, envArgs);
    }
    // Native dispatch
    const ne = k.natives.get(dispatchName);
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
      k.trace?.recordNative(k.nameStr(ne.name));
      return ne.fn(k, args);
    }
    // Closure via frame — use the ORIGINAL function-name (not the JIT-
    // aliased one): the user defined this function under rawName and
    // wants their version when no JIT mapping resolved a native.
    const v = frame.lookup(rawName);
    if (v === undefined) {
      throw new Error(`call: unbound ${k.nameStr(rawName)}`);
    }
    if (v.kind !== "closure") {
      throw new Error(
        `call: ${k.nameStr(rawName)} is not a closure (got ${v.kind})`,
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
  k.trace?.recordFn(k.nameStr(closure.name));
  // JIT-compiled fast path: if this closure's body has been compiled
  // via (jit_compile ...), dispatch through the host-JIT'd function
  // instead of walking the recipe tree. Form recipe stays canonical
  // truth; the compiled fn is opt-in bootstrap to host speed.
  const compiled = k.jitCompiled.get(nodeIDKey(closure.body));
  if (compiled !== undefined) return compiled(callFrame);
  return walk(k, closure.body, callFrame);
}

function nodeIDKey(nid: NodeID): string {
  return `${nid.pkg}.${nid.level}.${nid.type}.${nid.inst}`;
}

const FORM_BINARY_MAGIC_V1 = Buffer.from("FORMBIN1", "ascii");
const FORM_BINARY_MAGIC = Buffer.from("FORMBIN2", "ascii");
const FORM_BINARY_LEAF = 0;
const FORM_BINARY_COMPOSITE = 1;

function pushU32(out: number[], v: number): void {
  const n = v >>> 0;
  out.push((n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff);
}

function readU32(bytes: Uint8Array, pos: number): [number, number] {
  if (pos + 4 > bytes.length) throw new Error("form binary: truncated u32");
  const v =
    ((bytes[pos]! << 24) >>> 0) |
    (bytes[pos + 1]! << 16) |
    (bytes[pos + 2]! << 8) |
    bytes[pos + 3]!;
  return [v >>> 0, pos + 4];
}

function serializeNode(k: Kernel, nid: NodeID, out: number[]): void {
  const recipe = k.recipeAt(nid);
  if (recipe) {
    pushU32(out, FORM_BINARY_COMPOSITE);
    serializeNode(k, recipe.category, out);
    pushU32(out, recipe.children.length);
    for (const child of recipe.children) serializeNode(k, child, out);
    return;
  }
  pushU32(out, FORM_BINARY_LEAF);
  pushU32(out, nid.pkg);
  pushU32(out, nid.level);
  pushU32(out, nid.type);
  pushU32(out, nid.inst);
}

function deserializeRawNode(k: Kernel, bytes: Uint8Array, pos: number, scope: number): [NodeID, number] {
  let tag: number;
  [tag, pos] = readU32(bytes, pos);
  if (tag === FORM_BINARY_LEAF) {
    let pkg: number;
    let level: number;
    let type: number;
    let inst: number;
    [pkg, pos] = readU32(bytes, pos);
    [level, pos] = readU32(bytes, pos);
    [type, pos] = readU32(bytes, pos);
    [inst, pos] = readU32(bytes, pos);
    return [k.remapImportedLeaf(scope, { pkg, level, type, inst }), pos];
  }
  let category: NodeID;
  [category, pos] = deserializeRawNode(k, bytes, pos, scope);
  let count: number;
  [count, pos] = readU32(bytes, pos);
  const children: NodeID[] = [];
  for (let i = 0; i < count; i++) {
    let child: NodeID;
    [child, pos] = deserializeRawNode(k, bytes, pos, scope);
    children.push(child);
  }
  return [k.intern(category, children), pos];
}

function deserializeNode(
  k: Kernel,
  bytes: Uint8Array,
  strings: readonly string[],
  pos: number,
  scope: number,
): [NodeID, number] {
  let tag: number;
  [tag, pos] = readU32(bytes, pos);
  if (tag === FORM_BINARY_LEAF) {
    let pkg: number;
    let level: number;
    let type: number;
    let inst: number;
    [pkg, pos] = readU32(bytes, pos);
    [level, pos] = readU32(bytes, pos);
    [type, pos] = readU32(bytes, pos);
    [inst, pos] = readU32(bytes, pos);
    if (level === Level.TRIVIAL && type === Triv.STRING) {
      const value = strings[inst];
      if (value === undefined) throw new Error(`form binary: bad string index ${inst}`);
      return [k.internString(value), pos];
    }
    return [k.remapImportedLeaf(scope, { pkg, level, type, inst }), pos];
  }
  let category: NodeID;
  [category, pos] = deserializeNode(k, bytes, strings, pos, scope);
  let count: number;
  [count, pos] = readU32(bytes, pos);
  const children: NodeID[] = [];
  for (let i = 0; i < count; i++) {
    let child: NodeID;
    [child, pos] = deserializeNode(k, bytes, strings, pos, scope);
    children.push(child);
  }
  return [k.intern(category, children), pos];
}

function deserializeNodeV1(
  k: Kernel,
  bytes: Uint8Array,
  strings: readonly string[],
  pos: number,
  scope: number,
): [NodeID, number] {
  let pkg: number;
  let level: number;
  let type: number;
  let inst: number;
  let count: number;
  [pkg, pos] = readU32(bytes, pos);
  [level, pos] = readU32(bytes, pos);
  [type, pos] = readU32(bytes, pos);
  [inst, pos] = readU32(bytes, pos);
  [count, pos] = readU32(bytes, pos);
  if (count === 0) {
    if (level === Level.TRIVIAL && type === Triv.STRING) {
      const value = strings[inst];
      if (value === undefined) throw new Error(`form binary: bad string index ${inst}`);
      return [k.internString(value), pos];
    }
    return [k.remapImportedLeaf(scope, { pkg, level, type, inst }), pos];
  }
  const category =
    level === Level.TRIVIAL && type === Triv.STRING
      ? k.internString(readBinaryString(strings, inst))
      : { pkg, level, type, inst };
  const children: NodeID[] = [];
  for (let i = 0; i < count; i++) {
    let child: NodeID;
    [child, pos] = deserializeNodeV1(k, bytes, strings, pos, scope);
    children.push(child);
  }
  return [k.intern(category, children), pos];
}

function readBinaryString(strings: readonly string[], index: number): string {
  const value = strings[index];
  if (value === undefined) throw new Error(`form binary: bad string index ${index}`);
  return value;
}

export function serializeRecipeArtifact(k: Kernel, root: NodeID): Buffer {
  const out: number[] = Array.from(FORM_BINARY_MAGIC);
  pushU32(out, k.strs.length);
  for (const s of k.strs) {
    const encoded = Buffer.from(s, "utf8");
    pushU32(out, encoded.length);
    for (const byte of encoded) out.push(byte);
  }
  serializeNode(k, root, out);
  return Buffer.from(out);
}

export function deserializeRecipeArtifact(k: Kernel, bytes: Uint8Array): NodeID {
  const isV1 = hasMagic(bytes, FORM_BINARY_MAGIC_V1);
  const isV2 = hasMagic(bytes, FORM_BINARY_MAGIC);
  if (!isV1 && !isV2) throw new Error("form binary: bad magic");
  let pos = isV1 ? FORM_BINARY_MAGIC_V1.length : FORM_BINARY_MAGIC.length;
  let stringCount: number;
  [stringCount, pos] = readU32(bytes, pos);
  const strings: string[] = [];
  for (let i = 0; i < stringCount; i++) {
    let len: number;
    [len, pos] = readU32(bytes, pos);
    if (pos + len > bytes.length) throw new Error("form binary: truncated string");
    strings.push(Buffer.from(bytes.subarray(pos, pos + len)).toString("utf8"));
    pos += len;
  }
  const scope = k.nextImportScope();
  const [root, end] = isV1
    ? deserializeNodeV1(k, bytes, strings, pos, scope)
    : deserializeNode(k, bytes, strings, pos, scope);
  if (end !== bytes.length) throw new Error("form binary: trailing bytes");
  return root;
}

function hasMagic(bytes: Uint8Array, magic: Buffer): boolean {
  if (bytes.length < magic.length) return false;
  for (let i = 0; i < magic.length; i++) {
    if (bytes[i] !== magic[i]) return false;
  }
  return true;
}

