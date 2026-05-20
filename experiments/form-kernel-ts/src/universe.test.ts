// universe.test.ts — tests for task #22 universe polymorphism.
//
// Run with `node --import tsx --test src/universe.test.ts`.
//
// These tests prove three properties:
//
//   1. Authoring — `parameterizedByLevel` produces an FNDEF NodeID that
//      the existing walker accepts and runs as a normal closure once a
//      level binding is supplied and the resulting closure is FNCALL'd.
//   2. Specialization — `specializeByLevel` substitutes the bound level
//      values for every level-param reference in the body, returns a
//      structurally well-formed FNDEF, and respects the `oneOf`
//      constraint (rejecting out-of-set bindings).
//   3. Content-addressing — re-specializing the same function with the
//      same bindings returns the same NodeID.

import { describe, it } from "node:test";
import { strict as assert } from "node:assert";

import {
  Frame,
  Kernel,
  Level,
  RBasic,
  RBlock,
  Triv,
  type NodeID,
  walk,
} from "./kernel.ts";
import {
  makeApply,
  makeCompose,
  makeId,
  parameterizedByLevel,
  specializeByLevel,
} from "./universe.ts";

// Helper — build an FNCALL of an already-defined function name with
// already-interned argument NodeIDs.
function call(k: Kernel, fnName: string, args: readonly NodeID[]): NodeID {
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(fnName),
  };
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNCALL, inst: 0 },
    [nameTrivial, ...args],
  );
}

// Helper — wrap one or more nodes in a DO block so the walker evaluates
// them in sequence and returns the value of the last child. This lets
// us bind a top-level FNDEF and then call it in the same recipe tree.
function doBlock(k: Kernel, children: readonly NodeID[]): NodeID {
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.DO },
    children,
  );
}

describe("universe.parameterizedByLevel", () => {
  it("produces a runnable FNDEF for id at any level", () => {
    const k = new Kernel();
    const fn = makeId(k);

    // Specialize to TRIVIAL — the underlying body has no level-param
    // references, so this is a metadata-only change.
    const specialized = specializeByLevel(
      k,
      fn,
      new Map([[k.internName("L"), Level.TRIVIAL]]),
    );

    // Run `(do <fndef> (id 42))` and confirm we get 42 back.
    const arg = k.internTrivialInt(42);
    const expr = doBlock(k, [specialized.fnDef, call(k, "id", [arg])]);
    const result = walk(k, expr, new Frame(null));
    assert.equal(result.kind, "int");
    assert.equal(result.kind === "int" && result.int, 42);
  });

  it("produces a runnable FNDEF for apply", () => {
    const k = new Kernel();
    const fn = makeApply(k);
    const specialized = specializeByLevel(
      k,
      fn,
      new Map([[k.internName("L"), Level.BASIC]]),
    );

    // Define `inc`, then apply it to 10. Result should be 11.
    const incSrc = readSimpleDefn(k, "inc", ["n"], (kk, params) => {
      // Body: (+ n 1)
      const n = params[0]!;
      const one = kk.internTrivialInt(1);
      return kk.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: 1 },
        [n, one],
      );
    });

    const expr = doBlock(k, [
      specialized.fnDef,
      incSrc,
      call(k, "apply", [identExpr(k, "inc"), k.internTrivialInt(10)]),
    ]);
    const result = walk(k, expr, new Frame(null));
    assert.equal(result.kind, "int");
    assert.equal(result.kind === "int" && result.int, 11);
  });

  it("produces a runnable FNDEF for compose", () => {
    const k = new Kernel();
    const fn = makeCompose(k);
    const specialized = specializeByLevel(
      k,
      fn,
      new Map([[k.internName("L"), Level.COMPLEX_1]]),
    );

    // Define `inc` and `double`, then compose them: (compose inc double 5)
    // → inc(double(5)) = 11.
    const incSrc = readSimpleDefn(k, "inc", ["n"], (kk, params) => {
      const one = kk.internTrivialInt(1);
      return kk.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: 1 },
        [params[0]!, one],
      );
    });
    const doubleSrc = readSimpleDefn(k, "double", ["n"], (kk, params) => {
      const two = kk.internTrivialInt(2);
      return kk.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.MATH, inst: 3 },
        [params[0]!, two],
      );
    });

    const expr = doBlock(k, [
      specialized.fnDef,
      incSrc,
      doubleSrc,
      call(k, "compose", [
        identExpr(k, "inc"),
        identExpr(k, "double"),
        k.internTrivialInt(5),
      ]),
    ]);
    const result = walk(k, expr, new Frame(null));
    assert.equal(result.kind, "int");
    assert.equal(result.kind === "int" && result.int, 11);
  });
});

describe("universe.specializeByLevel", () => {
  it("substitutes the bound level value for body-level references", () => {
    const k = new Kernel();
    const L = k.internName("L");

    // A function whose body references L directly: `defn level_of[L] () = L`.
    // After specialization the body should be an int-trivial whose `inst`
    // equals the bound level.
    const body = k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
      [{ pkg: 1, level: Level.TRIVIAL, type: Triv.STRING, inst: L }],
    );
    const fn = parameterizedByLevel(
      k,
      k.internName("level_of"),
      [{ name: L, constraint: { kind: "any" } }],
      [],
      body,
    );

    const specialized = specializeByLevel(
      k,
      fn,
      new Map([[L, Level.COMPLEX_3]]),
    );

    // Confirm the rewritten body is an int trivial with the right value.
    const recipe = k.recipeAt(specialized.fnDef);
    assert.ok(recipe, "FNDEF must be interned");
    const newBody = recipe!.children[2]!;
    assert.equal(newBody.level, Level.TRIVIAL);
    assert.equal(newBody.type, Triv.INT);
    assert.equal(newBody.inst, Level.COMPLEX_3);

    // Walk it via (do <fndef> (level_of)) and confirm we get the level
    // value back as an int.
    const expr = doBlock(k, [specialized.fnDef, call(k, "level_of", [])]);
    const result = walk(k, expr, new Frame(null));
    assert.equal(result.kind, "int");
    assert.equal(result.kind === "int" && result.int, Level.COMPLEX_3);
  });

  it("rejects bindings that violate a oneOf constraint", () => {
    const k = new Kernel();
    const L = k.internName("L");
    const x = k.internName("x");
    const fn = parameterizedByLevel(
      k,
      k.internName("only_basic"),
      [
        {
          name: L,
          constraint: { kind: "oneOf", levels: [Level.BASIC] },
        },
      ],
      [{ name: x, levelBinding: L }],
      k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
        [{ pkg: 1, level: Level.TRIVIAL, type: Triv.STRING, inst: x }],
      ),
    );

    assert.throws(
      () => specializeByLevel(k, fn, new Map([[L, Level.TRIVIAL]])),
      /not in the constraint/,
    );
    // The allowed binding does work.
    const ok = specializeByLevel(k, fn, new Map([[L, Level.BASIC]]));
    assert.equal(ok.levelParams.length, 0);
  });

  it("rejects partial bindings", () => {
    const k = new Kernel();
    const L = k.internName("L");
    const M = k.internName("M");
    const x = k.internName("x");
    const fn = parameterizedByLevel(
      k,
      k.internName("two_params"),
      [
        { name: L, constraint: { kind: "any" } },
        { name: M, constraint: { kind: "any" } },
      ],
      [{ name: x, levelBinding: L }],
      k.intern(
        { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
        [{ pkg: 1, level: Level.TRIVIAL, type: Triv.STRING, inst: x }],
      ),
    );

    assert.throws(
      () => specializeByLevel(k, fn, new Map([[L, Level.BASIC]])),
      /arity mismatch/,
    );
  });

  it("is content-addressed — same bindings produce same NodeID", () => {
    const k = new Kernel();
    const fn = makeId(k);
    const bindings = new Map([[k.internName("L"), Level.BASIC]]);
    const a = specializeByLevel(k, fn, bindings);
    const b = specializeByLevel(k, fn, bindings);
    assert.deepEqual(a.fnDef, b.fnDef);
  });

  it("different level bindings produce different specializations when body uses L", () => {
    const k = new Kernel();
    const L = k.internName("L");
    const body = k.intern(
      { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
      [{ pkg: 1, level: Level.TRIVIAL, type: Triv.STRING, inst: L }],
    );
    const fn = parameterizedByLevel(
      k,
      k.internName("level_of"),
      [{ name: L, constraint: { kind: "any" } }],
      [],
      body,
    );
    const a = specializeByLevel(k, fn, new Map([[L, Level.BASIC]]));
    const b = specializeByLevel(k, fn, new Map([[L, Level.COMPLEX_2]]));
    assert.notDeepEqual(a.fnDef, b.fnDef);
  });
});

// ---------------------------------------------------------------------------
// Local helpers used only by the tests above.
// ---------------------------------------------------------------------------

// readSimpleDefn — build an FNDEF with the given name, params, and a
// body produced by `bodyFn`, which receives the kernel and the param
// IDENT recipe nodes. Mirrors the shape the walker expects in
// `walkFnDef`.
function readSimpleDefn(
  k: Kernel,
  name: string,
  params: readonly string[],
  bodyFn: (k: Kernel, paramIdents: readonly NodeID[]) => NodeID,
): NodeID {
  const paramKids: NodeID[] = params.map((p) => ({
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(p),
  }));
  const paramsSeq = k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.BLOCK, inst: RBlock.SEQUENCE },
    paramKids,
  );
  const paramIdents = params.map((p) => identExpr(k, p));
  const body = bodyFn(k, paramIdents);
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(name),
  };
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.FNDEF, inst: 0 },
    [nameTrivial, paramsSeq, body],
  );
}

function identExpr(k: Kernel, name: string): NodeID {
  const nameTrivial: NodeID = {
    pkg: 1,
    level: Level.TRIVIAL,
    type: Triv.STRING,
    inst: k.internName(name),
  };
  return k.intern(
    { pkg: 1, level: Level.BASIC, type: RBasic.IDENT, inst: 0 },
    [nameTrivial],
  );
}
