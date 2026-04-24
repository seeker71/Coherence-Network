import { describe, it, expect, vi } from "vitest";

import { createRenderSession, postRenderEvent } from "../lib/render-session";

function makeFakeTimers() {
  let currentTime = 0;
  const timers: Array<{ id: number; fireAt: number; cb: () => void }> = [];
  let nextId = 1;
  return {
    now: () => currentTime,
    setTimeout: ((cb: () => void, ms: number) => {
      const id = nextId++;
      timers.push({ id, fireAt: currentTime + ms, cb });
      return id as unknown as ReturnType<typeof setTimeout>;
    }) as typeof setTimeout,
    clearTimeout: ((id: ReturnType<typeof setTimeout>) => {
      const idx = timers.findIndex((t) => t.id === (id as unknown as number));
      if (idx !== -1) timers.splice(idx, 1);
    }) as typeof clearTimeout,
    advance(ms: number) {
      currentTime += ms;
      // Fire any timers whose time has come
      const toFire = timers.filter((t) => t.fireAt <= currentTime);
      for (const t of toFire) {
        const idx = timers.indexOf(t);
        if (idx !== -1) timers.splice(idx, 1);
      }
      for (const t of toFire) t.cb();
    },
  };
}

describe("createRenderSession", () => {
  it("fires onTimeout if markReady is not called within 5s (R10)", () => {
    const clock = makeFakeTimers();
    const onTimeout = vi.fn();
    const session = createRenderSession({
      assetId: "a1",
      rendererId: "r1",
      readerId: "u1",
      onTimeout,
      now: clock.now,
      setTimeoutFn: clock.setTimeout,
      clearTimeoutFn: clock.clearTimeout,
    });
    clock.advance(5001);
    expect(onTimeout).toHaveBeenCalledTimes(1);
    expect(session.hasTimedOut()).toBe(true);
    expect(session.isReady()).toBe(false);
  });

  it("does not fire onTimeout if markReady is called in time", () => {
    const clock = makeFakeTimers();
    const onTimeout = vi.fn();
    const session = createRenderSession({
      assetId: "a1",
      rendererId: "r1",
      readerId: "u1",
      onTimeout,
      now: clock.now,
      setTimeoutFn: clock.setTimeout,
      clearTimeoutFn: clock.clearTimeout,
    });
    clock.advance(100);
    session.markReady();
    clock.advance(10000);
    expect(onTimeout).not.toHaveBeenCalled();
    expect(session.hasTimedOut()).toBe(false);
    expect(session.isReady()).toBe(true);
  });

  it("uses custom timeoutMs when provided", () => {
    const clock = makeFakeTimers();
    const onTimeout = vi.fn();
    createRenderSession({
      assetId: "a1",
      rendererId: "r1",
      readerId: "u1",
      timeoutMs: 1000,
      onTimeout,
      now: clock.now,
      setTimeoutFn: clock.setTimeout,
      clearTimeoutFn: clock.clearTimeout,
    });
    clock.advance(500);
    expect(onTimeout).not.toHaveBeenCalled();
    clock.advance(600);
    expect(onTimeout).toHaveBeenCalledTimes(1);
  });

  it("engagement duration prefers trackEngagement over wall time when reported", () => {
    const clock = makeFakeTimers();
    const session = createRenderSession({
      assetId: "a1",
      rendererId: "r1",
      readerId: "u1",
      now: clock.now,
      setTimeoutFn: clock.setTimeout,
      clearTimeoutFn: clock.clearTimeout,
    });
    session.markReady();
    clock.advance(10_000);
    session.trackEngagement(7);
    clock.advance(5_000);
    // Engagement reported 7s; wall time elapsed is 15s. Engagement wins.
    const payload = session.getEventPayload();
    expect(payload.duration_ms).toBe(7_000);
  });

  it("engagement tracking only moves forward, not backward", () => {
    const session = createRenderSession({
      assetId: "a1",
      rendererId: "r1",
      readerId: "u1",
    });
    session.markReady();
    session.trackEngagement(10);
    session.trackEngagement(5); // lower value — should not overwrite
    const payload = session.getEventPayload();
    expect(payload.duration_ms).toBe(10_000);
  });

  it("getEventPayload falls back to wall time when no engagement reported", () => {
    const clock = makeFakeTimers();
    const session = createRenderSession({
      assetId: "a1",
      rendererId: "r1",
      readerId: "u1",
      now: clock.now,
      setTimeoutFn: clock.setTimeout,
      clearTimeoutFn: clock.clearTimeout,
    });
    session.markReady();
    clock.advance(3_500);
    const payload = session.getEventPayload();
    expect(payload.duration_ms).toBe(3_500);
  });

  it("dispose prevents onTimeout from firing after unmount", () => {
    const clock = makeFakeTimers();
    const onTimeout = vi.fn();
    const session = createRenderSession({
      assetId: "a1",
      rendererId: "r1",
      readerId: "u1",
      onTimeout,
      now: clock.now,
      setTimeoutFn: clock.setTimeout,
      clearTimeoutFn: clock.clearTimeout,
    });
    session.dispose();
    clock.advance(10_000);
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it("payload carries asset, renderer, and reader ids", () => {
    const session = createRenderSession({
      assetId: "asset:42",
      rendererId: "gltf-viewer-v1",
      readerId: "contributor:charlie",
    });
    session.markReady();
    session.trackEngagement(1);
    const payload = session.getEventPayload();
    expect(payload.asset_id).toBe("asset:42");
    expect(payload.renderer_id).toBe("gltf-viewer-v1");
    expect(payload.reader_id).toBe("contributor:charlie");
  });
});

describe("postRenderEvent", () => {
  it("returns parsed body on success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "evt-1", cc_pool: "0.15" }),
    });
    globalThis.fetch = fetchMock;
    const result = await postRenderEvent({
      asset_id: "a",
      renderer_id: "r",
      reader_id: "u",
      duration_ms: 1000,
    });
    expect(result).toEqual({ id: "evt-1", cc_pool: "0.15" });
  });

  it("returns null on network failure", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network"));
    const result = await postRenderEvent({
      asset_id: "a",
      renderer_id: "r",
      reader_id: "u",
      duration_ms: 1000,
    });
    expect(result).toBeNull();
  });

  it("returns null on non-2xx response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const result = await postRenderEvent({
      asset_id: "a",
      renderer_id: "r",
      reader_id: "u",
      duration_ms: 1000,
    });
    expect(result).toBeNull();
  });
});
