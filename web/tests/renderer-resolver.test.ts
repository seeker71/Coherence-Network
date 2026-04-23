import { describe, it, expect, beforeEach, vi } from "vitest";

import {
  registerRenderer,
  _resetRegistryForTests,
} from "../lib/renderer-sdk";
import {
  resolveRendererForMime,
  type RemoteRendererDescriptor,
} from "../lib/renderer-resolver";

describe("resolveRendererForMime", () => {
  beforeEach(() => {
    _resetRegistryForTests();
  });

  it("returns local descriptor when MIME is in the local registry", async () => {
    registerRenderer({
      id: "local-md-v1",
      mimeTypes: ["text/markdown"],
      // @ts-expect-error stub
      component: () => null,
    });
    const descriptor = await resolveRendererForMime("text/markdown");
    expect(descriptor).not.toBeNull();
    expect(descriptor!.source).toBe("local");
    if (descriptor!.source === "local") {
      expect(descriptor!.config.id).toBe("local-md-v1");
    }
  });

  it("falls back to remote fetcher when local has no match", async () => {
    const remoteResult: RemoteRendererDescriptor = {
      source: "remote",
      id: "gltf-v1",
      name: "GLTF Viewer",
      componentUrl: "https://cdn.example.com/gltf.js",
      version: "1.0.0",
    };
    const fetcher = vi.fn().mockResolvedValue(remoteResult);
    const descriptor = await resolveRendererForMime("model/gltf+json", fetcher);
    expect(fetcher).toHaveBeenCalledWith("model/gltf+json");
    expect(descriptor).toEqual(remoteResult);
  });

  it("returns null when neither local nor remote has a match", async () => {
    const fetcher = vi.fn().mockResolvedValue(null);
    const descriptor = await resolveRendererForMime("audio/midi", fetcher);
    expect(descriptor).toBeNull();
  });

  it("does not call remote fetcher when local has a match", async () => {
    registerRenderer({
      id: "local-png",
      mimeTypes: ["image/png"],
      // @ts-expect-error stub
      component: () => null,
    });
    const fetcher = vi.fn().mockResolvedValue(null);
    await resolveRendererForMime("image/png", fetcher);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
