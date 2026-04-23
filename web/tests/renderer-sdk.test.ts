import { describe, it, expect, beforeEach } from "vitest";
import {
  registerRenderer,
  findRendererForMime,
  listRegisteredRenderers,
  _resetRegistryForTests,
  type RendererConfig,
  type RendererProps,
} from "../lib/renderer-sdk";

function makeConfig(overrides: Partial<RendererConfig> = {}): RendererConfig {
  return {
    id: "test-renderer",
    mimeTypes: ["text/plain"],
    // @ts-expect-error — test stub, not a real component
    component: (_props: RendererProps) => null,
    ...overrides,
  };
}

describe("renderer-sdk", () => {
  beforeEach(() => {
    _resetRegistryForTests();
  });

  it("registers a renderer under each of its mime types", () => {
    registerRenderer(
      makeConfig({ id: "gltf-viewer-v1", mimeTypes: ["model/gltf+json", "model/gltf-binary"] }),
    );
    expect(findRendererForMime("model/gltf+json")?.id).toBe("gltf-viewer-v1");
    expect(findRendererForMime("model/gltf-binary")?.id).toBe("gltf-viewer-v1");
  });

  it("returns undefined for unregistered mime type", () => {
    expect(findRendererForMime("audio/midi")).toBeUndefined();
  });

  it("rejects registration without id", () => {
    expect(() => registerRenderer(makeConfig({ id: "" }))).toThrow();
  });

  it("rejects registration without mime types", () => {
    expect(() => registerRenderer(makeConfig({ mimeTypes: [] }))).toThrow();
  });

  it("last registration for a mime type wins", () => {
    registerRenderer(makeConfig({ id: "v1", mimeTypes: ["text/markdown"] }));
    registerRenderer(makeConfig({ id: "v2", mimeTypes: ["text/markdown"] }));
    expect(findRendererForMime("text/markdown")?.id).toBe("v2");
  });

  it("listRegisteredRenderers returns unique entries", () => {
    registerRenderer(
      makeConfig({ id: "multi", mimeTypes: ["text/plain", "text/markdown"] }),
    );
    const all = listRegisteredRenderers();
    expect(all).toHaveLength(1);
    expect(all[0].id).toBe("multi");
  });
});
