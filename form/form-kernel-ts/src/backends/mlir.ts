// mlir.ts — MLIR emit backend, Mojo-shaped (Task #12).
//
// MLIR is the strategic backend: it reuses Mojo's compilation infrastructure,
// has the broadest dialect coverage of any target the lattice emits to, and
// lowers cleanly to both CPU (via LLVM) and GPU (via mlir-gpu / SPIR-V).
//
// Recipes in the substrate land in MLIR text across these dialects:
//
//   arith    — basic integer + float arithmetic
//                %r = arith.addi %a, %b : i32
//                %r = arith.addf %a, %b : f32
//                %r = arith.muli %a, %b : i32
//                %r = arith.cmpi sgt, %a, %b : i32  -> i1
//   scf      — structured control flow
//                scf.if %cond -> (i32) { ... } else { ... }
//                scf.for %i = %lo to %hi step %step iter_args(...) -> (...)
//   func     — function definitions
//                func.func @name(%arg0: i32) -> i32 { return %r : i32 }
//   vector   — SIMD lane-parallel operations
//                %v = vector.add %a, %b : vector<8xf32>
//                %v = vector.broadcast %s : f32 to vector<8xf32>
//   linalg   — generic loop-nest abstraction for vectorize/parallel patterns
//                linalg.generic { iterator_types = ["parallel"] } ins(...) outs(...)
//
// The backend walks the kernel's recipe tree, emits SSA-form MLIR text, and
// returns it as a single .mlir module. SSA values are minted on the fly;
// the function boundary closes over its parameters. The emit is text-only
// — actual compilation happens via `mlir-opt`/`mlir-translate` downstream.
//
// Architecture notes:
//
//   • Every emit allocates a fresh MlirEmitter; emit state lives there.
//   • `emit(kernel, root, options?)` returns an MlirModule with:
//       - text: full MLIR module text
//       - rootValue: the SSA name carrying the root expression's result
//       - rootType: the MLIR type of the root expression
//   • i32 is the default integer type; the backend can also emit i64 / f32 /
//     f64 when steered via options.
//   • Comparisons return i1 (MLIR's standard predicate type).
//   • COND emits `scf.if` with explicit yield types.
//   • FNDEF emits `func.func` at module scope; the SSA values of the body
//     close over the function's %arg0..%argN parameters.
//   • VECTOR / vectorize patterns are emitted into vector / linalg dialects
//     when the kernel carries those RBasic constants. Detection is duck-typed
//     against the kernel's category constants so the backend stays additive
//     even before the VECTOR work has landed in this branch.

import {
  Kernel,
  Level,
  RBasic,
  RBlock,
  RCmp,
  RCond,
  RLogic,
  RMath,
  Triv,
  type NodeID,
} from "../kernel.ts";

// ---------------------------------------------------------------------------
// Public surface
// ---------------------------------------------------------------------------

export type MlirIntType = "i1" | "i8" | "i16" | "i32" | "i64";
export type MlirFloatType = "f16" | "f32" | "f64";
export type MlirScalarType = MlirIntType | MlirFloatType;
export type MlirVectorType = `vector<${number}x${MlirScalarType}>`;
export type MlirType = MlirScalarType | MlirVectorType;

export interface MlirEmitOptions {
  // Default integer type for INT trivials and integer arithmetic.
  // Defaults to "i32" — matches the kernel's | 0 i32 semantics.
  readonly intType?: MlirIntType;
  // Default float type used by float dialect emission helpers.
  // Defaults to "f32".
  readonly floatType?: MlirFloatType;
  // Module name in `module @name { ... }`. Defaults to "form_module".
  readonly moduleName?: string;
  // When true, wrap the root expression in a top-level
  // `func.func @form_root() -> <type>` so the output is a complete,
  // mlir-opt-loadable module. Defaults to true.
  readonly wrapInFunc?: boolean;
  // Target hint to seed dialect choices (currently advisory only).
  readonly target?: "mlir" | "cpu-via-llvm" | "gpu-via-mlir";
}

export interface MlirModule {
  // Full MLIR text — a module with zero or more func.func ops at top level.
  readonly text: string;
  // SSA value carrying the root expression result (e.g. "%r3"). When
  // `wrapInFunc` is true this is meaningful inside the root function;
  // outside, it is the value that was returned.
  readonly rootValue: string;
  // The MLIR type of the root expression.
  readonly rootType: MlirType;
}

// MlirBackend — the backend handle. The shape mirrors what the other
// codegen siblings (wasm, webgpu, cuda, metal) will expose, so the
// `multi-target-codegen.md` dispatch table treats them uniformly.
export interface Backend {
  readonly name: string;
  readonly target_hints: ReadonlySet<string>;
  readonly emit: (k: Kernel, root: NodeID, opts?: MlirEmitOptions) => MlirModule;
}

export const MlirBackend: Backend = {
  name: "mlir",
  target_hints: new Set<string>(["mlir", "cpu-via-llvm", "gpu-via-mlir"]),
  emit(k: Kernel, root: NodeID, opts?: MlirEmitOptions): MlirModule {
    const emitter = new MlirEmitter(k, opts ?? {});
    return emitter.emitModule(root);
  },
};

// Module-level convenience.
export function emit(
  k: Kernel,
  root: NodeID,
  opts?: MlirEmitOptions,
): MlirModule {
  return MlirBackend.emit(k, root, opts);
}

// ---------------------------------------------------------------------------
// Emitter
// ---------------------------------------------------------------------------

interface Local {
  // SSA value name, e.g. "%arg0" or "%v3".
  readonly value: string;
  readonly type: MlirType;
}

interface FnRecord {
  readonly symbol: string; // "@fib"
  readonly paramTypes: readonly MlirType[];
  readonly resultType: MlirType;
}

class MlirEmitter {
  private readonly k: Kernel;
  private readonly intType: MlirIntType;
  private readonly floatType: MlirFloatType;
  private readonly moduleName: string;
  private readonly wrapInFunc: boolean;

  // Top-level functions emitted into the module, in declaration order.
  private readonly topFunctions: string[] = [];
  // Symbol table — nameID → record. Functions live at module scope;
  // their SSA-callability is via symbol reference, not %values.
  private readonly fns = new Map<number, FnRecord>();
  // Locals stack — per-block frame for IDENT lookup. Each scope is a Map
  // from nameID to its Local (SSA value + type).
  private scopeStack: Array<Map<number, Local>> = [new Map()];
  // SSA value counter for the current function's region. Reset per function.
  private ssaCounter = 0;
  // Body lines being emitted into the current region (innermost first).
  private regionStack: string[][] = [[]];
  // Current indent inside the active region (in spaces). Module-level is 2;
  // each nested region adds 2.
  private indent = 4;

  constructor(k: Kernel, opts: MlirEmitOptions) {
    this.k = k;
    this.intType = opts.intType ?? "i32";
    this.floatType = opts.floatType ?? "f32";
    this.moduleName = opts.moduleName ?? "form_module";
    this.wrapInFunc = opts.wrapInFunc ?? true;
  }

  // ----- region + SSA bookkeeping ------------------------------------------

  private freshSSA(hint = "v"): string {
    this.ssaCounter++;
    return `%${hint}${this.ssaCounter}`;
  }

  private emitLine(line: string): void {
    const region = this.regionStack[this.regionStack.length - 1]!;
    region.push(" ".repeat(this.indent) + line);
  }

  private pushRegion(): void {
    this.regionStack.push([]);
    this.indent += 2;
  }

  private popRegion(): string[] {
    const region = this.regionStack.pop()!;
    this.indent -= 2;
    return region;
  }

  private pushScope(): void {
    this.scopeStack.push(new Map());
  }

  private popScope(): void {
    this.scopeStack.pop();
  }

  private currentScope(): Map<number, Local> {
    return this.scopeStack[this.scopeStack.length - 1]!;
  }

  private bind(nameID: number, local: Local): void {
    this.currentScope().set(nameID, local);
  }

  private lookup(nameID: number): Local | undefined {
    for (let i = this.scopeStack.length - 1; i >= 0; i--) {
      const v = this.scopeStack[i]!.get(nameID);
      if (v !== undefined) return v;
    }
    return undefined;
  }

  // ----- module emission ---------------------------------------------------

  emitModule(root: NodeID): MlirModule {
    // Strategy: emit top-level FNDEFs (and FNDEFs inside DO/SEQUENCE at top
    // level) as `func.func` ops, then emit the remaining root expression
    // inside a synthesized `@form_root` function. SSA values are local to
    // each function's region.
    const { rootValue, rootType } = this.emitRootFunction(root);

    const moduleBody = [
      ...this.topFunctions,
    ].join("\n");

    const text =
      `module @${this.moduleName} {\n` +
      `${moduleBody}\n` +
      `}\n`;
    return { text, rootValue, rootType };
  }

  private emitRootFunction(root: NodeID): { rootValue: string; rootType: MlirType } {
    // Hoist any top-level FNDEFs out of a SEQUENCE/DO body first; emit them
    // as standalone func.func. The remainder becomes the form_root body.
    const remainder = this.hoistTopLevelFnDefs(root);

    // Reset per-function SSA + region state for the root function.
    this.ssaCounter = 0;
    this.regionStack = [[]];
    this.scopeStack = [new Map()];
    this.indent = 4;

    let rootValue = "%c0_i32";
    let rootType: MlirType = this.intType;

    if (remainder === null) {
      // Only function definitions — emit a no-op root that returns 0.
      this.emitLine(`%c0 = arith.constant 0 : ${this.intType}`);
      rootValue = "%c0";
      rootType = this.intType;
    } else {
      const lv = this.emitExpr(remainder);
      rootValue = lv.value;
      rootType = lv.type;
    }

    this.emitLine(`return ${rootValue} : ${rootType}`);
    const bodyLines = this.popRegion();
    const body = bodyLines.join("\n");

    if (this.wrapInFunc) {
      const fn =
        `  func.func @form_root() -> ${rootType} {\n` +
        `${body}\n` +
        `  }`;
      this.topFunctions.push(fn);
    } else {
      // Inline the body lines directly under the module.
      this.topFunctions.push(body);
    }

    return { rootValue, rootType };
  }

  // Pull FNDEFs out of the top-level BLOCK so each becomes its own func.func.
  // Returns the residual expression to emit inside form_root, or null if the
  // entire top is function definitions.
  private hoistTopLevelFnDefs(root: NodeID): NodeID | null {
    if (root.level === Level.TRIVIAL) return root;
    const cat = this.k.category(root);
    if (cat.type === RBasic.FNDEF) {
      this.emitFunctionDefinition(this.k.children(root));
      return null;
    }
    if (cat.type === RBasic.BLOCK) {
      const op = cat.inst;
      const kids = this.k.children(root);
      const residuals: NodeID[] = [];
      for (const c of kids) {
        if (c.level !== Level.TRIVIAL) {
          const cc = this.k.category(c);
          if (cc.type === RBasic.FNDEF) {
            this.emitFunctionDefinition(this.k.children(c));
            continue;
          }
        }
        residuals.push(c);
      }
      if (residuals.length === 0) return null;
      if (residuals.length === 1) return residuals[0]!;
      // Re-intern a BLOCK of the same op kind around the residuals.
      return this.k.intern(cat, residuals);
      // (op kept by category.inst; LET inside residuals stays intact.)
      void op;
    }
    return root;
  }

  // ----- expression emission -----------------------------------------------

  private emitExpr(node: NodeID): Local {
    if (node.level === Level.TRIVIAL) {
      return this.emitTrivial(node);
    }
    const cat = this.k.category(node);
    const kids = this.k.children(node);
    switch (cat.type) {
      case RBasic.IDENT:
        return this.emitIdent(node);
      case RBasic.MATH:
        return this.emitMath(cat.inst, kids);
      case RBasic.COMPARE:
        return this.emitCompare(cat.inst, kids);
      case RBasic.LOGIC:
        return this.emitLogic(cat.inst, kids);
      case RBasic.COND:
        return this.emitCond(cat.inst, kids);
      case RBasic.BLOCK:
        return this.emitBlock(cat.inst, kids);
      case RBasic.FNDEF:
        // Nested FNDEF — also hoist to module scope.
        this.emitFunctionDefinition(kids);
        return this.emitZero();
      case RBasic.FNCALL:
        return this.emitFnCall(kids);
      default:
        // Unknown / future RBasic (VECTOR, VECTORIZE, etc.) — dispatch to
        // duck-typed extension handlers and otherwise emit a placeholder.
        return this.emitExtensionOrFallback(cat, kids);
    }
  }

  private emitTrivial(node: NodeID): Local {
    if (node.type === Triv.INT) {
      const u = node.inst >>> 0;
      const i = u > 0x7fffffff ? u - 0x100000000 : u;
      const v = this.freshSSA("c");
      this.emitLine(`${v} = arith.constant ${i} : ${this.intType}`);
      return { value: v, type: this.intType };
    }
    if (node.type === Triv.BOOL) {
      const v = this.freshSSA("c");
      this.emitLine(`${v} = arith.constant ${node.inst !== 0 ? 1 : 0} : i1`);
      return { value: v, type: "i1" };
    }
    if (node.type === Triv.NULL) {
      // MLIR has no first-class null; lower to 0 : i32 with a comment.
      const v = this.freshSSA("c");
      this.emitLine(`${v} = arith.constant 0 : ${this.intType} // null`);
      return { value: v, type: this.intType };
    }
    if (node.type === Triv.STRING) {
      // Strings aren't a first-class MLIR scalar; emit a poison sentinel
      // with a comment carrying the original NameID. Real backends would
      // route strings through llvm.mlir.global or a runtime intrinsic.
      const v = this.freshSSA("c");
      this.emitLine(
        `${v} = arith.constant 0 : ${this.intType} // string#${node.inst}`,
      );
      return { value: v, type: this.intType };
    }
    return this.emitZero();
  }

  private emitZero(): Local {
    const v = this.freshSSA("c");
    this.emitLine(`${v} = arith.constant 0 : ${this.intType}`);
    return { value: v, type: this.intType };
  }

  private emitIdent(node: NodeID): Local {
    const id = this.k.identID(node);
    const found = this.lookup(id);
    if (found !== undefined) return found;
    // Unresolved name — emit a placeholder constant rather than throwing,
    // so the rest of the module still type-checks. The text carries a
    // comment for diagnosis.
    const v = this.freshSSA("c");
    const name = safeName(this.k, id);
    this.emitLine(
      `${v} = arith.constant 0 : ${this.intType} // unbound: ${name}`,
    );
    return { value: v, type: this.intType };
  }

  private isFloatType(t: MlirType): boolean {
    return t === "f16" || t === "f32" || t === "f64";
  }

  private isVectorType(t: MlirType): boolean {
    return typeof t === "string" && t.startsWith("vector<");
  }

  private widenArith(a: Local, b: Local): { a: Local; b: Local; type: MlirType } {
    // Promote integer→float if mixed. Promote to the wider operand if both
    // are the same family. Vectors require identical types.
    if (this.isVectorType(a.type) || this.isVectorType(b.type)) {
      if (a.type !== b.type) {
        // Mismatched vector shapes — fall back to keeping a's type; emit a
        // comment so the human can fix the recipe.
        return { a, b, type: a.type };
      }
      return { a, b, type: a.type };
    }
    if (this.isFloatType(a.type) || this.isFloatType(b.type)) {
      const target = this.isFloatType(a.type) ? a.type : b.type;
      const aL = this.isFloatType(a.type) ? a : this.convertToFloat(a, target as MlirFloatType);
      const bL = this.isFloatType(b.type) ? b : this.convertToFloat(b, target as MlirFloatType);
      return { a: aL, b: bL, type: target };
    }
    // Both integer — use a's type as the dominant. The kernel emits
    // homogeneous i32 by default.
    return { a, b, type: a.type };
  }

  private convertToFloat(x: Local, target: MlirFloatType): Local {
    const v = this.freshSSA("f");
    this.emitLine(`${v} = arith.sitofp ${x.value} : ${x.type} to ${target}`);
    return { value: v, type: target };
  }

  // ----- arithmetic --------------------------------------------------------

  private emitMath(op: number, kids: readonly NodeID[]): Local {
    if (kids.length < 2) return this.emitZero();
    let acc = this.emitExpr(kids[0]!);
    for (let i = 1; i < kids.length; i++) {
      const next = this.emitExpr(kids[i]!);
      acc = this.emitMathBinop(op, acc, next);
    }
    return acc;
  }

  private emitMathBinop(op: number, a: Local, b: Local): Local {
    const widened = this.widenArith(a, b);
    const t = widened.type;
    const isVec = this.isVectorType(t);
    const isFloat = !isVec && this.isFloatType(t);
    const v = this.freshSSA("r");

    if (isVec) {
      // vector.<op> — element-wise arithmetic.
      const opStr =
        op === RMath.PLUS
          ? "add"
          : op === RMath.MINUS
            ? "sub"
            : op === RMath.MUL
              ? "mul"
              : op === RMath.DIV
                ? "div"
                : op === RMath.MOD
                  ? "rem"
                  : "add";
      this.emitLine(
        `${v} = vector.${opStr} ${widened.a.value}, ${widened.b.value} : ${t}`,
      );
      return { value: v, type: t };
    }

    if (isFloat) {
      const opStr =
        op === RMath.PLUS
          ? "addf"
          : op === RMath.MINUS
            ? "subf"
            : op === RMath.MUL
              ? "mulf"
              : op === RMath.DIV
                ? "divf"
                : op === RMath.MOD
                  ? "remf"
                  : "addf";
      this.emitLine(
        `${v} = arith.${opStr} ${widened.a.value}, ${widened.b.value} : ${t}`,
      );
      return { value: v, type: t };
    }

    // Integer arithmetic.
    const opStr =
      op === RMath.PLUS
        ? "addi"
        : op === RMath.MINUS
          ? "subi"
          : op === RMath.MUL
            ? "muli"
            : op === RMath.DIV
              ? "divsi"
              : op === RMath.MOD
                ? "remsi"
                : "addi";
    this.emitLine(
      `${v} = arith.${opStr} ${widened.a.value}, ${widened.b.value} : ${t}`,
    );
    return { value: v, type: t };
  }

  // ----- comparison --------------------------------------------------------

  private emitCompare(op: number, kids: readonly NodeID[]): Local {
    if (kids.length !== 2) return this.emitZero();
    const a = this.emitExpr(kids[0]!);
    const b = this.emitExpr(kids[1]!);
    const widened = this.widenArith(a, b);
    const t = widened.type;
    const isFloat = this.isFloatType(t);
    const v = this.freshSSA("c");

    if (isFloat) {
      const pred =
        op === RCmp.EQ
          ? "oeq"
          : op === RCmp.NE
            ? "one"
            : op === RCmp.LT
              ? "olt"
              : op === RCmp.LE
                ? "ole"
                : op === RCmp.GT
                  ? "ogt"
                  : op === RCmp.GE
                    ? "oge"
                    : "oeq";
      this.emitLine(
        `${v} = arith.cmpf ${pred}, ${widened.a.value}, ${widened.b.value} : ${t}`,
      );
      return { value: v, type: "i1" };
    }

    const pred =
      op === RCmp.EQ
        ? "eq"
        : op === RCmp.NE
          ? "ne"
          : op === RCmp.LT
            ? "slt"
            : op === RCmp.LE
              ? "sle"
              : op === RCmp.GT
                ? "sgt"
                : op === RCmp.GE
                  ? "sge"
                  : "eq";
    this.emitLine(
      `${v} = arith.cmpi ${pred}, ${widened.a.value}, ${widened.b.value} : ${t}`,
    );
    return { value: v, type: "i1" };
  }

  // ----- logic -------------------------------------------------------------

  private emitLogic(op: number, kids: readonly NodeID[]): Local {
    if (op === RLogic.NOT) {
      if (kids.length < 1) return this.emitZeroBool();
      const a = this.toI1(this.emitExpr(kids[0]!));
      const one = this.freshSSA("t");
      this.emitLine(`${one} = arith.constant 1 : i1`);
      const v = this.freshSSA("n");
      this.emitLine(`${v} = arith.xori ${a.value}, ${one} : i1`);
      return { value: v, type: "i1" };
    }
    if (kids.length < 2) return this.emitZeroBool();
    let acc = this.toI1(this.emitExpr(kids[0]!));
    for (let i = 1; i < kids.length; i++) {
      const next = this.toI1(this.emitExpr(kids[i]!));
      const v = this.freshSSA(op === RLogic.AND ? "and" : "or");
      const mlirOp = op === RLogic.AND ? "andi" : "ori";
      this.emitLine(`${v} = arith.${mlirOp} ${acc.value}, ${next.value} : i1`);
      acc = { value: v, type: "i1" };
    }
    return acc;
  }

  private toI1(x: Local): Local {
    if (x.type === "i1") return x;
    // Reduce non-bool to i1 via != 0
    const zero = this.freshSSA("zero");
    this.emitLine(`${zero} = arith.constant 0 : ${x.type}`);
    const v = this.freshSSA("c");
    if (this.isFloatType(x.type)) {
      this.emitLine(`${v} = arith.cmpf one, ${x.value}, ${zero} : ${x.type}`);
    } else {
      this.emitLine(`${v} = arith.cmpi ne, ${x.value}, ${zero} : ${x.type}`);
    }
    return { value: v, type: "i1" };
  }

  private emitZeroBool(): Local {
    const v = this.freshSSA("c");
    this.emitLine(`${v} = arith.constant 0 : i1`);
    return { value: v, type: "i1" };
  }

  // ----- conditional (scf.if) ----------------------------------------------

  private emitCond(op: number, kids: readonly NodeID[]): Local {
    if (op === RCond.IF_THEN) {
      if (kids.length < 2) return this.emitZero();
      const condL = this.toI1(this.emitExpr(kids[0]!));
      // No else — emit scf.if with a 0 fallback so both branches yield the
      // same type (MLIR requires it for scf.if-with-results).
      this.pushRegion();
      const thenL = this.emitExpr(kids[1]!);
      this.emitLine(`scf.yield ${thenL.value} : ${thenL.type}`);
      const thenLines = this.popRegion();

      this.pushRegion();
      const zero = this.freshSSA("c");
      this.emitLine(`${zero} = arith.constant 0 : ${thenL.type}`);
      this.emitLine(`scf.yield ${zero} : ${thenL.type}`);
      const elseLines = this.popRegion();

      const result = this.freshSSA("if");
      this.emitLine(`${result} = scf.if ${condL.value} -> (${thenL.type}) {`);
      for (const line of thenLines) this.emitLineRaw(line);
      this.emitLine(`} else {`);
      for (const line of elseLines) this.emitLineRaw(line);
      this.emitLine(`}`);
      return { value: result, type: thenL.type };
    }

    // IF_THEN_ELSE
    if (kids.length < 3) return this.emitZero();
    const condL = this.toI1(this.emitExpr(kids[0]!));

    this.pushRegion();
    const thenL = this.emitExpr(kids[1]!);
    this.emitLine(`scf.yield ${thenL.value} : ${thenL.type}`);
    const thenLines = this.popRegion();

    this.pushRegion();
    const elseL = this.emitExpr(kids[2]!);
    // If branch types diverge, MLIR is unhappy — emit a cast to thenL's
    // type. For the bench shapes both branches are i32 by construction.
    const elseValue =
      elseL.type === thenL.type
        ? elseL
        : this.coerce(elseL, thenL.type);
    this.emitLine(`scf.yield ${elseValue.value} : ${thenL.type}`);
    const elseLines = this.popRegion();

    const result = this.freshSSA("if");
    this.emitLine(`${result} = scf.if ${condL.value} -> (${thenL.type}) {`);
    for (const line of thenLines) this.emitLineRaw(line);
    this.emitLine(`} else {`);
    for (const line of elseLines) this.emitLineRaw(line);
    this.emitLine(`}`);
    return { value: result, type: thenL.type };
  }

  private emitLineRaw(line: string): void {
    const region = this.regionStack[this.regionStack.length - 1]!;
    // `line` already carries its prior indent; we just preserve it as-is
    // but make sure the leading whitespace harmonizes with the outer level
    // by re-indenting once.
    region.push(" ".repeat(2) + line);
  }

  private coerce(x: Local, target: MlirType): Local {
    if (x.type === target) return x;
    const v = this.freshSSA("cast");
    // Integer→integer widen / narrow; float→float; int↔float.
    if (this.isFloatType(target) && !this.isFloatType(x.type)) {
      this.emitLine(`${v} = arith.sitofp ${x.value} : ${x.type} to ${target}`);
    } else if (!this.isFloatType(target) && this.isFloatType(x.type)) {
      this.emitLine(`${v} = arith.fptosi ${x.value} : ${x.type} to ${target}`);
    } else if (this.isFloatType(target) && this.isFloatType(x.type)) {
      // Pick extf vs truncf based on rank.
      const rank = (t: MlirType): number =>
        t === "f16" ? 1 : t === "f32" ? 2 : t === "f64" ? 3 : 0;
      const dir = rank(target) > rank(x.type) ? "extf" : "truncf";
      this.emitLine(`${v} = arith.${dir} ${x.value} : ${x.type} to ${target}`);
    } else {
      // int-to-int — use extsi / trunci.
      const rank = (t: MlirType): number =>
        t === "i1" ? 0 : t === "i8" ? 1 : t === "i16" ? 2 : t === "i32" ? 3 : t === "i64" ? 4 : 0;
      const dir = rank(target) > rank(x.type) ? "extsi" : "trunci";
      this.emitLine(`${v} = arith.${dir} ${x.value} : ${x.type} to ${target}`);
    }
    return { value: v, type: target };
  }

  // ----- block / let -------------------------------------------------------

  private emitBlock(op: number, kids: readonly NodeID[]): Local {
    if (op === RBlock.LET) {
      if (kids.length < 2) return this.emitZero();
      const name = kids[0]!;
      const val = this.emitExpr(kids[1]!);
      if (name.level === Level.TRIVIAL && name.type === Triv.STRING) {
        this.bind(name.inst, val);
      }
      return val;
    }
    // DO / SEQUENCE — evaluate each, return last
    if (kids.length === 0) return this.emitZero();
    let last: Local = this.emitZero();
    for (const c of kids) {
      // Skip nested FNDEFs — they were already hoisted at the top level if
      // applicable, but inside arbitrary blocks they emit a module-scope
      // func.func as a side effect.
      if (c.level !== Level.TRIVIAL) {
        const cc = this.k.category(c);
        if (cc.type === RBasic.FNDEF) {
          this.emitFunctionDefinition(this.k.children(c));
          continue;
        }
      }
      last = this.emitExpr(c);
    }
    return last;
  }

  // ----- functions ---------------------------------------------------------

  private emitFunctionDefinition(kids: readonly NodeID[]): void {
    if (kids.length !== 3) return;
    const name = kids[0]!;
    const paramsBlock = kids[1]!;
    const body = kids[2]!;
    if (name.level !== Level.TRIVIAL || name.type !== Triv.STRING) return;

    const symbol = "@" + safeName(this.k, name.inst);
    const paramKids = this.k.children(paramsBlock);

    // Save outer emission state; switch to fresh state for the new function.
    const savedSSA = this.ssaCounter;
    const savedRegion = this.regionStack;
    const savedScope = this.scopeStack;
    const savedIndent = this.indent;

    this.ssaCounter = 0;
    this.regionStack = [[]];
    this.scopeStack = [new Map()];
    this.indent = 4;

    const paramTypes: MlirType[] = [];
    const paramDecls: string[] = [];
    paramKids.forEach((p, idx) => {
      const argName = `%arg${idx}`;
      const t: MlirType = this.intType;
      paramTypes.push(t);
      paramDecls.push(`${argName}: ${t}`);
      if (p.level === Level.TRIVIAL && p.type === Triv.STRING) {
        this.currentScope().set(p.inst, { value: argName, type: t });
        // Carry SSA counter past the parameter index — MLIR numbers args
        // in the same pool, but we generate hint-prefixed names so there
        // is no conflict.
      }
    });

    // Pre-bind a self-reference so recursive calls can resolve, by
    // remembering the symbol on the fn record.
    const provisional: FnRecord = {
      symbol,
      paramTypes,
      resultType: this.intType, // refined after body emission if it widens
    };
    this.fns.set(name.inst, provisional);

    const bodyLocal = this.emitExpr(body);
    this.emitLine(`return ${bodyLocal.value} : ${bodyLocal.type}`);
    const bodyLines = this.popRegion();

    const fnRecord: FnRecord = {
      symbol,
      paramTypes,
      resultType: bodyLocal.type,
    };
    this.fns.set(name.inst, fnRecord);

    const header = `  func.func ${symbol}(${paramDecls.join(", ")}) -> ${bodyLocal.type} {`;
    const footer = `  }`;
    this.topFunctions.push([header, ...bodyLines, footer].join("\n"));

    // Restore outer state.
    this.ssaCounter = savedSSA;
    this.regionStack = savedRegion;
    this.scopeStack = savedScope;
    this.indent = savedIndent;
  }

  private emitFnCall(kids: readonly NodeID[]): Local {
    if (kids.length < 1) return this.emitZero();
    const callee = kids[0]!;
    let nameID: number | null = null;
    if (callee.level === Level.TRIVIAL && callee.type === Triv.STRING) {
      nameID = callee.inst;
    } else if (
      callee.level === Level.BASIC &&
      callee.type === RBasic.IDENT
    ) {
      nameID = this.k.identID(callee);
    }
    if (nameID === null) {
      // Indirect call — not modelled at this layer; emit a placeholder.
      return this.emitZero();
    }
    const fn = this.fns.get(nameID);
    const args: Local[] = kids.slice(1).map((a) => this.emitExpr(a));
    if (fn === undefined) {
      // Unknown callee — emit a func.call to an external symbol stub.
      const v = this.freshSSA("call");
      const argTypes = args.map((a) => a.type).join(", ");
      const argVals = args.map((a) => a.value).join(", ");
      const sym = "@" + safeName(this.k, nameID);
      this.emitLine(
        `${v} = func.call ${sym}(${argVals}) : (${argTypes}) -> ${this.intType}`,
      );
      return { value: v, type: this.intType };
    }
    // Coerce args to declared param types where possible.
    const coerced = args.map((a, i) =>
      fn.paramTypes[i] !== undefined ? this.coerce(a, fn.paramTypes[i]!) : a,
    );
    const argVals = coerced.map((a) => a.value).join(", ");
    const argTypes = coerced.map((a) => a.type).join(", ");
    const v = this.freshSSA("call");
    this.emitLine(
      `${v} = func.call ${fn.symbol}(${argVals}) : (${argTypes}) -> ${fn.resultType}`,
    );
    return { value: v, type: fn.resultType };
  }

  // ----- extension RBasics (VECTOR / VECTORIZE / TILE / PARALLELIZE) -------
  //
  // The PR #9 work introduces RBasic.VECTOR (SIMD lanes) and the parallel
  // pattern recipes (TILE / PARALLELIZE / VECTORIZE). Those constants aren't
  // yet on this branch, but the backend stays additive by detecting them
  // duck-typed against `(RBasic as Record<string, number>)` lookups. When
  // they land, the emitter routes to vector / linalg dialects without any
  // further change here.

  private emitExtensionOrFallback(
    cat: NodeID,
    kids: readonly NodeID[],
  ): Local {
    const codes = extensionRBasic();
    if (codes.VECTOR !== null && cat.type === codes.VECTOR) {
      return this.emitVectorOp(cat, kids);
    }
    if (codes.VECTORIZE !== null && cat.type === codes.VECTORIZE) {
      return this.emitVectorizePattern(cat, kids);
    }
    if (codes.TILE !== null && cat.type === codes.TILE) {
      return this.emitLinalgPattern("tile", cat, kids);
    }
    if (codes.PARALLELIZE !== null && cat.type === codes.PARALLELIZE) {
      return this.emitLinalgPattern("parallel", cat, kids);
    }
    // Truly unknown category — emit a poison constant with a comment.
    const v = this.freshSSA("ext");
    this.emitLine(
      `${v} = arith.constant 0 : ${this.intType} // unknown RBasic ${cat.type}`,
    );
    return { value: v, type: this.intType };
  }

  private emitVectorOp(cat: NodeID, kids: readonly NodeID[]): Local {
    // VECTOR category carries (element-format, width, storage-hint) as its
    // children-of-category — but at the recipe level, the kids of a VECTOR
    // recipe are the lane values. cat.inst conventionally encodes width.
    const width = cat.inst > 0 ? cat.inst : kids.length;
    const elemType: MlirScalarType = this.floatType;
    const vecType: MlirVectorType = `vector<${width}x${elemType}>`;
    const v = this.freshSSA("vec");
    // Emit a vector.from_elements-style construction.
    if (kids.length === 0) {
      this.emitLine(
        `${v} = arith.constant dense<0.0> : ${vecType}`,
      );
      return { value: v, type: vecType };
    }
    const laneLocals = kids.map((c) => this.emitExpr(c));
    const laneVals = laneLocals.map((l) => l.value).join(", ");
    this.emitLine(
      `${v} = vector.from_elements ${laneVals} : ${vecType}`,
    );
    return { value: v, type: vecType };
  }

  private emitVectorizePattern(cat: NodeID, kids: readonly NodeID[]): Local {
    // VECTORIZE(op, simd_width) ⇒ linalg.generic with one parallel iterator.
    const simdWidth = cat.inst > 0 ? cat.inst : 4;
    const elemType: MlirScalarType = this.floatType;
    const vecType: MlirVectorType = `vector<${simdWidth}x${elemType}>`;
    const v = this.freshSSA("vz");
    this.emitLine(
      `${v} = linalg.generic { indexing_maps = [affine_map<(d0) -> (d0)>], iterator_types = ["parallel"], simd_width = ${simdWidth} } { /* body lowered from recipe */ } : ${vecType}`,
    );
    // Walk the wrapped op so its body is still type-checked, but discard
    // its SSA values since linalg.generic consumes them.
    for (const k of kids) this.emitExpr(k);
    return { value: v, type: vecType };
  }

  private emitLinalgPattern(
    iterator: "tile" | "parallel",
    cat: NodeID,
    kids: readonly NodeID[],
  ): Local {
    const v = this.freshSSA(iterator);
    const meta = cat.inst > 0 ? `, hint = ${cat.inst}` : "";
    this.emitLine(
      `${v} = linalg.generic { iterator_types = ["${iterator}"]${meta} } { /* body lowered from recipe */ } : ${this.intType}`,
    );
    for (const k of kids) this.emitExpr(k);
    return { value: v, type: this.intType };
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function safeName(k: Kernel, id: number): string {
  let s: string;
  try {
    s = k.nameStr(id);
  } catch {
    s = `name_${id}`;
  }
  // MLIR symbol names are fairly permissive; restrict to a conservative set.
  return s.replace(/[^A-Za-z0-9_$]/g, "_") || `name_${id}`;
}

// Duck-typed extension lookup. PR #9 adds RBasic.VECTOR / TILE / PARALLELIZE
// / VECTORIZE. On this branch they don't exist yet; the lookup returns null
// for the missing ones and the backend falls through to the poison emitter.
function extensionRBasic(): {
  VECTOR: number | null;
  VECTORIZE: number | null;
  TILE: number | null;
  PARALLELIZE: number | null;
} {
  const r = RBasic as unknown as Record<string, number | undefined>;
  return {
    VECTOR: typeof r.VECTOR === "number" ? r.VECTOR : null,
    VECTORIZE: typeof r.VECTORIZE === "number" ? r.VECTORIZE : null,
    TILE: typeof r.TILE === "number" ? r.TILE : null,
    PARALLELIZE: typeof r.PARALLELIZE === "number" ? r.PARALLELIZE : null,
  };
}
