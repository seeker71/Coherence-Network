// form-kernel-ts — vertical-slice host for Form-on-top.
//
// Reads `.fk` S-expression source files, parses straight into recipe trees,
// walks them. Carries everything Form-on-top can't write itself:
//
//   • Substrate          — NodeID + content-addressed intern table
//   • Walker             — RBasic dispatch arms (v0: math/compare/logic/
//                          cond/block/ident/fndef/fncall)
//   • Frames + closures  — scope, lookup, capture
//   • Native primitives  — arithmetic (v0); strings/lists/I/O deferred
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
// All fields are non-negative integers < 2^32. Stored as plain number for
// idiomatic TS; bit-width matches Go/Rust (uint32) for cross-kernel parity.
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
export const RBasic = {
  BLOCK: 9,
  COND: 11,
  MATH: 12,
  COMPARE: 13,
  LOGIC: 14,
  // Kernel-demo additions (extending RBasic for self-hosting needs)
  FNDEF: 31,
  FNCALL: 32,
  IDENT: 33,
  LIST: 34,
} as const;

export const Triv = {
  INT: 1,
  STRING: 2,
  BOOL: 3,
  NULL: 4,
} as const;

// Per-RBasic instance constants
export const RMath = { PLUS: 1, MINUS: 2, MUL: 3, DIV: 4, MOD: 5 } as const;
export const RCmp = { LT: 1, LE: 2, GT: 3, GE: 4, EQ: 5, NE: 6 } as const;
export const RLogic = { AND: 1, OR: 2, NOT: 3 } as const;
export const RCond = { IF: 1 } as const;
export const RBlock = { DO: 1 } as const;

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

function nodeKey(n: NodeID): string {
  return `${n.pkg}.${n.level}.${n.type}.${n.inst}`;
}

export class Kernel {
  // Composite recipes — keyed by content (recipeKey) for intern dedup,
  // and by NodeID (nodeKey) for walker access.
  private byKey = new Map<string, NodeID>();
  private byID = new Map<string, Recipe>();
  private next = 1; // next instance number for composites

  // String table — substrate strings + identifier names share this table.
  // A name's NodeID.inst is its index into `strs`.
  private strs: string[] = [];
  private strIdx = new Map<string, NameID>();

  // intern — content-addressed insertion. Same shape ⇒ same NodeID.
  intern(category: NodeID, children: readonly NodeID[]): NodeID {
    const k = recipeKey(category, children);
    const existing = this.byKey.get(k);
    if (existing) return existing;
    const nid: NodeID = {
      pkg: 1,
      level: category.level,
      type: category.type,
      inst: this.next++,
    };
    this.byKey.set(k, nid);
    this.byID.set(nodeKey(nid), { category, children });
    return nid;
  }

  internTrivialInt(n: number): NodeID {
    // 32-bit signed range encoded in inst. Larger ints would need a
    // separate big-int table; v0 stays in i32.
    const inst = (n | 0) >>> 0; // coerce to u32 bit pattern
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

  // internName — fast path when the caller already holds the string and
  // only needs the NameID (no NodeID wrapper).
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

  trivialValue(n: NodeID): Value {
    if (n.level !== Level.TRIVIAL) {
      throw new Error(`trivialValue: ${nodeKey(n)} is composite`);
    }
    switch (n.type) {
      case Triv.INT: {
        // Reinterpret u32 inst as i32
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
      default:
        throw new Error(`trivialValue: unknown trivial type ${n.type}`);
    }
  }

  identID(n: NodeID): NameID {
    // An identifier in v0 is either a string trivial directly, or a
    // single-child IDENT recipe wrapping a string trivial.
    if (n.level === Level.TRIVIAL && n.type === Triv.STRING) {
      return n.inst;
    }
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

  // Render — used by the CLI to print a result. Matches Go kernel output
  // format for cross-kernel diffing.
  render(v: Value): string {
    switch (v.kind) {
      case "null":
        return "null";
      case "int":
        return String(v.int);
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
    }
  }
}

// ---------------------------------------------------------------------------
// Values — runtime tagged values
// ---------------------------------------------------------------------------

export type Value =
  | { kind: "null" }
  | { kind: "int"; int: number }
  | { kind: "str"; str: string }
  | { kind: "bool"; bool: boolean }
  | { kind: "list"; list: Value[] }
  | { kind: "closure"; closure: Closure }
  | { kind: "nodeid"; nodeid: NodeID };

export interface Closure {
  readonly params: readonly NameID[];
  readonly body: NodeID;
  readonly env: Frame;
}

// ---------------------------------------------------------------------------
// Frame — scope primitive
// ---------------------------------------------------------------------------

// Frame — scope primitive. Bindings as a small ordered list; the common
// case (function call with 1-3 args) beats a hash map at this size.
export class Frame {
  private readonly parent: Frame | null;
  private readonly keys: NameID[] = [];
  private readonly vals: Value[] = [];

  constructor(parent: Frame | null = null) {
    this.parent = parent;
  }

  bind(name: NameID, value: Value): void {
    // Shadow within the same frame: overwrite if present.
    const idx = this.keys.indexOf(name);
    if (idx >= 0) {
      this.vals[idx] = value;
      return;
    }
    this.keys.push(name);
    this.vals.push(value);
  }

  lookup(name: NameID): Value | undefined {
    const idx = this.keys.indexOf(name);
    if (idx >= 0) return this.vals[idx];
    if (this.parent) return this.parent.lookup(name);
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

  if (cat.type === RBasic.IDENT) {
    const id = k.identID(node);
    const v = frame.lookup(id);
    if (v === undefined) {
      throw new Error(`unbound identifier: ${k.nameStr(id)}`);
    }
    return v;
  }

  if (cat.type === RBasic.MATH) {
    return walkMath(k, cat.inst, kids, frame);
  }
  if (cat.type === RBasic.COMPARE) {
    return walkCompare(k, cat.inst, kids, frame);
  }
  if (cat.type === RBasic.LOGIC) {
    return walkLogic(k, cat.inst, kids, frame);
  }
  if (cat.type === RBasic.COND) {
    return walkCond(k, cat.inst, kids, frame);
  }
  if (cat.type === RBasic.BLOCK) {
    return walkBlock(k, cat.inst, kids, frame);
  }
  if (cat.type === RBasic.FNDEF) {
    return walkFnDef(k, kids, frame);
  }
  if (cat.type === RBasic.FNCALL) {
    return walkFnCall(k, kids, frame);
  }
  if (cat.type === RBasic.LIST) {
    const items = kids.map((c) => walk(k, c, frame));
    return { kind: "list", list: items };
  }

  throw new Error(`walk: unsupported RBasic type ${cat.type}`);
}

function expectInt(v: Value, op: string): number {
  if (v.kind !== "int") throw new Error(`${op}: expected int, got ${v.kind}`);
  return v.int;
}

function walkMath(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length < 2) throw new Error("math: need at least 2 args");
  const first = kids[0];
  if (first === undefined) throw new Error("math: missing first arg");
  let acc = expectInt(walk(k, first, frame), "math");
  for (let i = 1; i < kids.length; i++) {
    const child = kids[i];
    if (child === undefined) continue;
    const x = expectInt(walk(k, child, frame), "math");
    switch (op) {
      case RMath.PLUS:
        acc += x;
        break;
      case RMath.MINUS:
        acc -= x;
        break;
      case RMath.MUL:
        acc *= x;
        break;
      case RMath.DIV:
        if (x === 0) throw new Error("division by zero");
        acc = Math.trunc(acc / x);
        break;
      case RMath.MOD:
        if (x === 0) throw new Error("modulo by zero");
        acc = acc - Math.trunc(acc / x) * x;
        break;
      default:
        throw new Error(`math: unknown op ${op}`);
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
  if (kids.length !== 2 || kids[0] === undefined || kids[1] === undefined) {
    throw new Error("compare: need exactly 2 args");
  }
  const av = walk(k, kids[0], frame);
  const bv = walk(k, kids[1], frame);

  if (op === RCmp.EQ || op === RCmp.NE) {
    const equal = valueEqual(av, bv);
    return { kind: "bool", bool: op === RCmp.EQ ? equal : !equal };
  }

  const a = expectInt(av, "compare");
  const b = expectInt(bv, "compare");
  let r: boolean;
  switch (op) {
    case RCmp.LT:
      r = a < b;
      break;
    case RCmp.LE:
      r = a <= b;
      break;
    case RCmp.GT:
      r = a > b;
      break;
    case RCmp.GE:
      r = a >= b;
      break;
    default:
      throw new Error(`compare: unknown op ${op}`);
  }
  return { kind: "bool", bool: r };
}

function valueEqual(a: Value, b: Value): boolean {
  if (a.kind !== b.kind) return false;
  switch (a.kind) {
    case "null":
      return true;
    case "int":
      return a.int === (b as { int: number }).int;
    case "str":
      return a.str === (b as { str: string }).str;
    case "bool":
      return a.bool === (b as { bool: boolean }).bool;
    default:
      return false;
  }
}

function walkLogic(
  k: Kernel,
  op: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (op === RLogic.NOT) {
    if (kids.length !== 1 || kids[0] === undefined)
      throw new Error("not: need exactly 1 arg");
    const v = walk(k, kids[0], frame);
    if (v.kind !== "bool") throw new Error("not: expected bool");
    return { kind: "bool", bool: !v.bool };
  }
  if (kids.length < 2) throw new Error("and/or: need at least 2 args");
  for (let i = 0; i < kids.length; i++) {
    const c = kids[i];
    if (c === undefined) continue;
    const v = walk(k, c, frame);
    if (v.kind !== "bool") throw new Error("and/or: expected bool");
    if (op === RLogic.AND && !v.bool)
      return { kind: "bool", bool: false };
    if (op === RLogic.OR && v.bool) return { kind: "bool", bool: true };
    if (i === kids.length - 1) return v;
  }
  return { kind: "bool", bool: op === RLogic.AND };
}

function walkCond(
  k: Kernel,
  _op: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (
    kids.length !== 3 ||
    kids[0] === undefined ||
    kids[1] === undefined ||
    kids[2] === undefined
  ) {
    throw new Error("if: need 3 args (cond, then, else)");
  }
  const c = walk(k, kids[0], frame);
  if (c.kind !== "bool") throw new Error("if: condition must be bool");
  return c.bool ? walk(k, kids[1], frame) : walk(k, kids[2], frame);
}

function walkBlock(
  k: Kernel,
  _op: number,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  let result: Value = { kind: "null" };
  for (const c of kids) {
    result = walk(k, c, frame);
  }
  return result;
}

// FNDEF children:  [name-trivial, [param-trivials...], body]
// Encoded as: child(0) = name string trivial
//             child(1) = LIST recipe of param identifiers
//             child(2) = body recipe
function walkFnDef(
  k: Kernel,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (
    kids.length !== 3 ||
    kids[0] === undefined ||
    kids[1] === undefined ||
    kids[2] === undefined
  ) {
    throw new Error("defn: need 3 children (name, params, body)");
  }
  const nameID = k.identID(kids[0]);
  const paramKids = k.children(kids[1]);
  const params: NameID[] = paramKids.map((p) => k.identID(p));
  const closure: Closure = {
    params,
    body: kids[2],
    env: frame,
  };
  frame.bind(nameID, { kind: "closure", closure });
  return { kind: "closure", closure };
}

// FNCALL children: [callee-ident, arg0, arg1, ...]
function walkFnCall(
  k: Kernel,
  kids: readonly NodeID[],
  frame: Frame,
): Value {
  if (kids.length < 1 || kids[0] === undefined)
    throw new Error("call: need callee");
  const calleeNode = kids[0];
  const calleeVal = walk(k, calleeNode, frame);
  if (calleeVal.kind !== "closure") {
    throw new Error(`call: callee is not a closure (got ${calleeVal.kind})`);
  }
  const args = kids.slice(1).map((c) => walk(k, c, frame));
  const closure = calleeVal.closure;
  if (args.length !== closure.params.length) {
    throw new Error(
      `call: arity mismatch (expected ${closure.params.length}, got ${args.length})`,
    );
  }
  const callFrame = new Frame(closure.env);
  for (let i = 0; i < closure.params.length; i++) {
    const p = closure.params[i];
    const a = args[i];
    if (p === undefined || a === undefined) continue;
    callFrame.bind(p, a);
  }
  return walk(k, closure.body, callFrame);
}
