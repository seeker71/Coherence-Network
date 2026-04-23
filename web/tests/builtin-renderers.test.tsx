import { describe, it, expect, beforeEach } from "vitest";

import {
  findRendererForMime,
  _resetRegistryForTests,
} from "../lib/renderer-sdk";
import { registerBuiltinRenderers } from "../lib/builtin-renderers";

describe("builtin-renderers registerBuiltinRenderers()", () => {
  beforeEach(() => {
    _resetRegistryForTests();
  });

  it("registers markdown renderer for text/markdown", () => {
    registerBuiltinRenderers();
    expect(findRendererForMime("text/markdown")?.id).toBe("builtin-markdown-v1");
  });

  it("registers image renderer for jpeg and png", () => {
    registerBuiltinRenderers();
    expect(findRendererForMime("image/jpeg")?.id).toBe("builtin-image-v1");
    expect(findRendererForMime("image/png")?.id).toBe("builtin-image-v1");
  });

  it("registers image renderer for webp and gif too", () => {
    registerBuiltinRenderers();
    expect(findRendererForMime("image/webp")?.id).toBe("builtin-image-v1");
    expect(findRendererForMime("image/gif")?.id).toBe("builtin-image-v1");
  });

  it("registers html renderer", () => {
    registerBuiltinRenderers();
    expect(findRendererForMime("text/html")?.id).toBe("builtin-html-v1");
  });

  it("registers pdf renderer", () => {
    registerBuiltinRenderers();
    expect(findRendererForMime("application/pdf")?.id).toBe("builtin-pdf-v1");
  });

  it("is idempotent — calling twice does not throw", () => {
    registerBuiltinRenderers();
    expect(() => registerBuiltinRenderers()).not.toThrow();
  });

  it("returns undefined for unregistered mime types", () => {
    registerBuiltinRenderers();
    expect(findRendererForMime("model/gltf+json")).toBeUndefined();
    expect(findRendererForMime("audio/midi")).toBeUndefined();
  });
});
