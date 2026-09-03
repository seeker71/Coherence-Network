import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

import {
  PRESENCE_NODE_TYPES,
  resolvePresenceGraphNode,
  type PresenceNodeFetcher,
  type PresenceNodeRecord,
} from "../lib/presence-node";

const REPO_ROOT = resolve(__dirname, "..", "..");

function routedFetcher(
  responses: Record<string, PresenceNodeRecord | null>,
): PresenceNodeFetcher {
  return vi.fn(async (path: string) => responses[path] ?? null);
}

describe("resolvePresenceGraphNode", () => {
  it("resolves the Urs refinement slug to its canonical graph node", async () => {
    const canonical = {
      id: "contributor:seeker71",
      slug: "urs-muff",
      aliases: ["seeker71", "urs-muff", "ursmuff", "urs"],
      name: "Urs Muff",
    };
    const fetcher = routedFetcher({
      "/api/graph/nodes?type=contributor&limit=500": {
        items: [canonical],
      },
    });

    await expect(
      resolvePresenceGraphNode("urs-muff", fetcher),
    ).resolves.toEqual(canonical);
    expect(fetcher).toHaveBeenCalledWith("/api/graph/nodes/urs-muff");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/graph/nodes/contributor%3Aurs-muff",
    );
  });

  it("resolves aliases through the same shared identity path", async () => {
    const canonical = {
      id: "contributor:seeker71",
      slug: "urs-muff",
      aliases: ["urs"],
    };
    const fetcher = routedFetcher({
      "/api/graph/nodes?type=contributor&limit=500": {
        items: [canonical],
      },
    });

    await expect(resolvePresenceGraphNode("urs", fetcher)).resolves.toEqual(
      canonical,
    );
  });

  it.each(PRESENCE_NODE_TYPES)(
    "resolves a declared alias on a %s presence",
    async (type) => {
      const canonical = {
        id: `${type}:canonical-cell`,
        type,
        slug: `canonical-${type}`,
        aliases: [`shared-${type}-alias`],
      };
      const fetcher = routedFetcher({
        [`/api/graph/nodes?type=${encodeURIComponent(type)}&limit=500`]: {
          items: [canonical],
        },
      });

      await expect(
        resolvePresenceGraphNode(`shared-${type}-alias`, fetcher),
      ).resolves.toEqual(canonical);
    },
  );

  it("returns a canonical node without scanning the contributor list", async () => {
    const canonical = { id: "contributor:seeker71", name: "Urs Muff" };
    const fetcher = routedFetcher({
      "/api/graph/nodes/contributor%3Aseeker71": canonical,
    });

    await expect(
      resolvePresenceGraphNode("contributor:seeker71", fetcher),
    ).resolves.toEqual(canonical);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});

describe("presence refinement deployment contract", () => {
  it("requires editor content on the slug-based refinement route", () => {
    const source = readFileSync(
      resolve(REPO_ROOT, "scripts", "verify_web_api_deploy.sh"),
      "utf8",
    );

    expect(source).toContain("/people/urs-muff/edit");
    expect(source).toContain("Refine Urs Muff");
  });
});
