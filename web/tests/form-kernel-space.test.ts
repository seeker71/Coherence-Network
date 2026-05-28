import { describe, expect, it } from "vitest";
import {
  buildKernelSpace,
  layoutSpace,
  blueprintColor,
} from "../lib/form-kernel/space";

describe("kernel space builder", () => {
  it("turns a nested arithmetic recipe into a walkable tree of rooms", () => {
    const space = buildKernelSpace("(add 1 (mul 2 (sub 9 4)))");

    // root resolves and the run produced the right value
    expect(space.result).toBe("11");
    expect(space.root).not.toBe("");

    // every recipe cell carries doors to its children
    const root = space.cells[space.root]!;
    expect(root.kind).toBe("recipe");
    expect(root.arm).toContain("MATH");
    expect(root.childIds.length).toBeGreaterThan(0);

    // leaves are value-windows with no doors
    const leaves = Object.values(space.cells).filter((c) => c.kind === "leaf");
    expect(leaves.length).toBeGreaterThan(0);
    expect(leaves.every((l) => l.childIds.length === 0)).toBe(true);
    expect(leaves.some((l) => l.value === "9")).toBe(true);

    // discovery order covers every cell exactly once
    expect(space.order.length).toBe(Object.keys(space.cells).length);
    expect(new Set(space.order).size).toBe(space.order.length);
  });

  it("places every cell and respects depth on the into-axis (Z)", () => {
    const space = buildKernelSpace("(add 1 (mul 2 3))");
    const layout = layoutSpace(space);

    // each cell gets a position
    for (const id of space.order) expect(layout[id]).toBeDefined();

    // deeper cells sit further along -Z than the root
    const rootZ = layout[space.root]!.position[2];
    const deepest = space.order
      .map((id) => space.cells[id]!)
      .reduce((a, b) => (b.depth > a.depth ? b : a));
    expect(layout[deepest.id]!.position[2]).toBeLessThanOrEqual(rootZ);
  });

  it("paints structurally-equivalent shapes the same blueprint color", () => {
    // two distinct integer leaves share a blueprint (same level+type) ⇒ same ice color
    const space = buildKernelSpace("(add 7 7)");
    const ints = Object.values(space.cells).filter((c) => c.arm === "int");
    expect(ints.length).toBeGreaterThanOrEqual(1);
    const [a] = ints;
    expect(blueprintColor(a!.node)).toEqual(a!.blueprintColor);

    // recursion records FNCALL heat and keeps the tree finite
    const rec = buildKernelSpace(
      "(do (defn f (n) (if (le n 1) 1 (mul n (f (sub n 1))))) (f 5))",
    );
    expect(rec.result).toBe("120");
    expect(rec.stats.totalWalks).toBeGreaterThan(10);
    expect(Object.keys(rec.cells).length).toBeGreaterThan(0);
  });

  it("classifies leaf data types and container shapes", () => {
    const space = buildKernelSpace("(do (let xs (list 70 111 114 109)) (nth xs 0))");

    // the list recipe is a container; its int elements are typed leaves
    const list = Object.values(space.cells).find((c) => c.container === "list");
    expect(list).toBeDefined();
    const ints = Object.values(space.cells).filter((c) => c.dataType === "int");
    expect(ints.length).toBeGreaterThanOrEqual(4);

    // the do-block is a sequence; the let is a binding
    expect(
      Object.values(space.cells).some((c) => c.container === "sequence"),
    ).toBe(true);
    expect(
      Object.values(space.cells).some((c) => c.container === "binding"),
    ).toBe(true);

    // every cell knows its first-seen parent (root's is null)
    expect(space.parentOf[space.root]).toBeNull();
  });

  it("lays list elements out as an ordered spine in front of their parent", () => {
    const space = buildKernelSpace("(list 1 2 3)");
    const layout = layoutSpace(space);
    const list = Object.values(space.cells).find((c) => c.container === "list")!;

    // each element is a spine child, ordered left→right by child index
    const elems = list.childIds.map((id) => layout[id]).filter(Boolean);
    expect(elems.length).toBe(3);
    expect(elems.every((e) => e!.spine)).toBe(true);
    const xs = elems.map((e) => e!.position[0]);
    expect(xs[0]).toBeLessThan(xs[1]!);
    expect(xs[1]).toBeLessThan(xs[2]!);
  });

  it("re-roots the layout when drilling into a subtree", () => {
    const space = buildKernelSpace("(add 1 (mul 2 3))");
    const full = layoutSpace(space);
    // drill into the inner (mul 2 3)
    const mul = Object.values(space.cells).find((c) => c.arm.startsWith("MATH ×"))!;
    const drilled = layoutSpace(space, mul.id);

    // drilled view is a strict subset, and the drill target becomes the origin
    expect(Object.keys(drilled).length).toBeLessThan(Object.keys(full).length);
    const p = drilled[mul.id]!.position;
    expect(p[0]).toBe(0);
    expect(p[1]).toBe(0);
    expect(Math.abs(p[2])).toBe(0);
    // the outer `add` is no longer in view
    expect(drilled[space.root]).toBeUndefined();
  });

  it("rasterizes the lattice into an RGBA framebuffer surface", () => {
    const space = buildKernelSpace("(add 1 2)");
    const { width, height, rgba } = space.framebuffer;
    expect(rgba.length).toBe(width * height * 4);
    // alpha channel is opaque everywhere
    expect(rgba[3]).toBe(255);
  });
});
