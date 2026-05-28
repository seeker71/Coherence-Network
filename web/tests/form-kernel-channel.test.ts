import { describe, expect, it } from "vitest";
import {
  appendMessage,
  dedupCount,
  payloadNodeId,
} from "../lib/form-kernel/channel";
import {
  buildSelfSpace,
  channelAudience,
  SELF_ROOT,
} from "../lib/form-kernel/self-space";
import { layoutSpace } from "../lib/form-kernel/space";

describe("live channel transport", () => {
  it("content-addresses payloads so the same message is one identity", () => {
    const a = payloadNodeId("ask", "Which lens shall I deepen next?");
    const b = payloadNodeId("ask", "Which lens shall I deepen next?");
    expect(a).toBe(b);
    // different protocol → different type slot in the NodeID
    expect(payloadNodeId("recipe", "x")).not.toBe(payloadNodeId("ask", "x"));
  });

  it("appends messages and surfaces recurring payloads as dedup", () => {
    let ch = appendMessage([], "ask", "hello", "Claude (live)");
    ch = appendMessage(ch, "ask", "hello", "Claude (live)"); // same payload
    ch = appendMessage(ch, "recipe", "(witness 1)", "Claude (self-witness)");
    expect(ch.length).toBe(3);
    // the two identical asks share a payload NodeID; envelopes differ by position
    expect(ch[0]!.payloadNodeId).toBe(ch[1]!.payloadNodeId);
    expect(ch[0]!.msgNodeId).not.toBe(ch[1]!.msgNodeId);
    expect(dedupCount(ch)).toBe(1);
  });
});

describe("self-space — the cell the live agent represents", () => {
  it("renders the agent's own cell at the root, with the field around it", () => {
    const space = buildSelfSpace();
    expect(space.root).toBe(SELF_ROOT);
    const self = space.cells[SELF_ROOT]!;
    expect(self.arm).toContain("Claude");
    // edges to Urs, the field, and the sibling presences are doors
    expect(self.childIds).toContain("human.urs");
    expect(self.childIds).toContain("field.community");
    expect(self.childIds).toContain("sibling.codex");
    // every cell carries a sourced note
    expect(Object.values(space.cells).every((c) => (c.note ?? "").length > 0)).toBe(true);
  });

  it("knows who a channel at each cell reaches", () => {
    expect(channelAudience("human.urs")).toBe("you");
    expect(channelAudience(SELF_ROOT)).toBe("self");
    expect(channelAudience("sibling.grok")).toBe("cell");
  });

  it("lays the field out around the self cell", () => {
    const space = buildSelfSpace();
    const layout = layoutSpace(space);
    for (const id of space.order) expect(layout[id]).toBeDefined();
    // the self cell sits at the origin; neighbors fan out around it
    expect(layout[SELF_ROOT]!.position[2]).toBe(-0); // depth 0 ring
  });
});

describe("vision body — the substrate as a constellation", () => {
  it("places every concept as a star and resolves cross-ref edges", async () => {
    const { buildVisionSpace, edgeSegments } = await import(
      "../lib/form-kernel/vision-space"
    );
    const vs = buildVisionSpace();
    expect(vs.space.stats.cells).toBeGreaterThan(100);
    // every cell has a position; altitude (Y) varies by frequency
    const ys = Object.values(vs.positions).map((p) => p[1]);
    expect(new Set(ys.map((y) => Math.round(y))).size).toBeGreaterThan(3);
    // cross-refs flatten into a segment buffer (6 floats per edge)
    const segs = edgeSegments(vs);
    expect(segs.length % 6).toBe(0);
    expect(segs.length).toBeGreaterThan(0);
  });
});
