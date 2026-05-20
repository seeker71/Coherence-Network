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

import { readFileSync } from "node:fs";

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
} as const;

// RBasic — aligned with api/app/services/substrate/category.py
//
// Higher-math arms (slots 70+) — substrate cells govern their semantics:
//   QUOTIENT (70): canonicalization under an equivalence relation —
//     see ./quotient.ts. The category instance carries the equivalence
//     family code; children are [carrier-recipe, equivalence-recipe].
export const RBasic = {
  BLOCK: 9,
  COND: 11,
  MATH: 12,
  COMPARE: 13,
  LOGIC: 14,
  FNDEF: 31,
  FNCALL: 32,
  IDENT: 33,
  LIST: 34,
  CHOICE: 35,           // pattern-match arm (extended in #21 with totality)
  QUOTIENT: 70,         // #19 — equivalence-class types
  INDUCTIVE: 71,        // #21 — algebraic datatypes
  CONSTRUCTOR: 72,      // #21 — constructor application / value-shape
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

  // Natives — map from NameID to NativeFn. Lookup is u32-keyed.
  natives = new Map<NameID, NativeFn>();

  constructor() {
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
        return "[" + v.list.map((x) => this.render(x)).join(" ") + "]";
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

  private registerNative(name: string, fn: NativeFn): void {
    this.natives.set(this.internName(name), fn);
  }

  private registerNatives(): void {
    this.registerNative("print", (_k, args) => {
      const parts = args.map((a) => this.renderForPrint(a));
      process.stdout.write(parts.join(" ") + "\n");
      return { kind: "null" };
    });
    // String ops
    this.registerNative("str_len", (_k, args) => ({
      kind: "int",
      int: argStr(args, 0).length,
    }));
    this.registerNative("substring", (_k, args) => ({
      kind: "str",
      str: argStr(args, 0).slice(argInt(args, 1), argInt(args, 2)),
    }));
    this.registerNative("char_at", (_k, args) => {
      const s = argStr(args, 0);
      const i = argInt(args, 1);
      return { kind: "str", str: s[i] ?? "" };
    });
    this.registerNative("str_concat", (_k, args) => ({
      kind: "str",
      str: argStr(args, 0) + argStr(args, 1),
    }));
    this.registerNative("str_eq", (_k, args) => ({
      kind: "bool",
      bool: argStr(args, 0) === argStr(args, 1),
    }));
    this.registerNative("int_to_str", (_k, args) => ({
      kind: "str",
      str: String(argInt(args, 0)),
    }));
    this.registerNative("str_to_int", (_k, args) => ({
      kind: "int",
      int: parseInt(argStr(args, 0), 10) || 0,
    }));
    this.registerNative("ord", (_k, args) => {
      const s = argStr(args, 0);
      return { kind: "int", int: s.length === 0 ? -1 : s.charCodeAt(0) };
    });
    // List ops
    this.registerNative("list", (_k, args) => ({
      kind: "list",
      list: args.slice(),
    }));
    this.registerNative("cons", (_k, args) => {
      const head = args[0] ?? { kind: "null" };
      const tail = argList(args, 1);
      return { kind: "list", list: [head, ...tail] };
    });
    this.registerNative("head", (_k, args) => {
      const lst = argList(args, 0);
      return lst[0] ?? { kind: "null" };
    });
    this.registerNative("tail", (_k, args) => ({
      kind: "list",
      list: argList(args, 0).slice(1),
    }));
    this.registerNative("len", (_k, args) => {
      const v = args[0];
      if (v?.kind === "list") return { kind: "int", int: v.list.length };
      if (v?.kind === "str") return { kind: "int", int: v.str.length };
      return { kind: "int", int: 0 };
    });
    this.registerNative("nth", (_k, args) => {
      const lst = argList(args, 0);
      const i = argInt(args, 1);
      return lst[i] ?? { kind: "null" };
    });
    this.registerNative("empty", () => ({ kind: "list", list: [] }));
    // File I/O
    this.registerNative("read_file", (_k, args) => {
      try {
        return { kind: "str", str: readFileSync(argStr(args, 0), "utf8") };
      } catch {
        return { kind: "null" };
      }
    });

    // Substrate write surface — Form code holds NodeIDs as values and
    // constructs recipes via these natives. Closes the form-runtime-in-
    // form gaps W1–W3.
    this.registerNative("make_nodeid", (_k, args) => ({
      kind: "nodeid",
      nodeid: {
        pkg: argInt(args, 0),
        level: argInt(args, 1),
        type: argInt(args, 2),
        inst: argInt(args, 3),
      },
    }));
    this.registerNative("intern_trivial_int", (k, args) => ({
      kind: "nodeid",
      nodeid: k.internTrivialInt(argInt(args, 0)),
    }));
    this.registerNative("intern_trivial_string", (k, args) => ({
      kind: "nodeid",
      nodeid: k.internString(argStr(args, 0)),
    }));
    this.registerNative("intern_node", (k, args) => {
      const cat = argNodeID(args, 0);
      const kids = argList(args, 1).map((v) => {
        if (v.kind !== "nodeid")
          throw new Error("intern_node: children must be nodeids");
        return v.nodeid;
      });
      return { kind: "nodeid", nodeid: k.intern(cat, kids) };
    });
    this.registerNative("node_category", (k, args) => ({
      kind: "nodeid",
      nodeid: k.category(argNodeID(args, 0)),
    }));
    this.registerNative("node_children", (k, args) => {
      const kids = k.children(argNodeID(args, 0));
      return {
        kind: "list",
        list: kids.map((c) => ({ kind: "nodeid", nodeid: c } as Value)),
      };
    });
    this.registerNative("node_value", (k, args) =>
      k.trivialValue(argNodeID(args, 0)),
    );
    this.registerNative("walk_recipe", (k, args) =>
      walk(k, argNodeID(args, 0), new Frame(null)),
    );

    // Typed-numeric construction and decoding
    this.registerNative("make_int8", (k, args) => k.boxValue(k.internTrivialInt8(argInt(args, 0))));
    this.registerNative("make_int16", (k, args) => k.boxValue(k.internTrivialInt16(argInt(args, 0))));
    this.registerNative("make_int32", (k, args) => k.boxValue(k.internTrivialInt(argInt(args, 0))));
    this.registerNative("make_int64", (k, args) => k.boxValue(k.internTrivialInt64(argBigInt(args, 0))));
    this.registerNative("make_uint8", (k, args) => k.boxValue(k.internTrivialUint8(argInt(args, 0))));
    this.registerNative("make_uint16", (k, args) => k.boxValue(k.internTrivialUint16(argInt(args, 0))));
    this.registerNative("make_uint32", (k, args) => k.boxValue(k.internTrivialUint32(argInt(args, 0))));
    this.registerNative("make_uint64", (k, args) => k.boxValue(k.internTrivialUint64(argBigInt(args, 0))));
    this.registerNative("make_float32", (k, args) => k.boxValue(k.internTrivialFloat32(argFloat(args, 0))));
    this.registerNative("make_float64", (k, args) => k.boxValue(k.internTrivialFloat64(argFloat(args, 0))));

    // Width-conversion casts (operate on values, not nodeids — Form's
    // common case for narrowing/widening at runtime)
    this.registerNative("i64", (_k, args) => ({ kind: "i64", bigint: argBigInt(args, 0) }));
    this.registerNative("u64", (_k, args) => ({ kind: "u64", bigint: argBigInt(args, 0) }));
    this.registerNative("f32", (_k, args) => ({ kind: "f32", float: Math.fround(argFloat(args, 0)) }));
    this.registerNative("f64", (_k, args) => ({ kind: "f64", float: argFloat(args, 0) }));
    this.registerNative("i32", (_k, args) => ({ kind: "int", int: argInt(args, 0) | 0 }));

    // Debug
    this.registerNative("trace", (_k, args) => {
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
    default:
      throw new Error(`walk: unsupported RBasic type ${cat.type}`);
  }
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
    const nat = k.natives.get(calleeName);
    if (nat !== undefined) {
      const args: Value[] = [];
      for (let i = 1; i < kids.length; i++) {
        args.push(walk(k, kids[i]!, frame));
      }
      return nat(k, args);
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
