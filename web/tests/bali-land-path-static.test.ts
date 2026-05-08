import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";
import {
  ENTRY_PATHS,
  getEntryPathForSurface,
  getEntryPathsForSurface,
  type EntryPath,
} from "../lib/entry-paths";

const root = join(__dirname, "..");

describe("Bali land design path", () => {
  it("keeps the living compound registered for the public entry surfaces", () => {
    const bali = ENTRY_PATHS.find((entry) => entry.id === "bali-living-compound");

    expect(bali).toMatchObject({
      href: "/silence/built",
      kind: "land-design-draft",
      tone: "emerald",
    });
    expect(bali?.audiences).toContain("land-steward");
    expect(bali?.excludedKinds).toEqual(
      expect.arrayContaining(["hospital", "care-institution"]),
    );
    for (const surface of ["home-ground", "come-in-explore", "come-in-doors"] as const) {
      expect(getEntryPathForSurface("bali-living-compound", surface)).toBeDefined();
    }
  });

  it("renders the registered entry path from home and come-in", () => {
    const homeSource = readFileSync(join(root, "app/page.tsx"), "utf8");
    const comeInSource = readFileSync(join(root, "app/come-in/page.tsx"), "utf8");

    expect(homeSource).toContain(
      'getEntryPathForSurface("bali-living-compound", "home-ground")',
    );
    expect(comeInSource).toContain(
      'getEntryPathForSurface("bali-living-compound", "come-in-explore")',
    );
    expect(comeInSource).toContain(
      'getEntryPathForSurface("bali-living-compound", "come-in-doors")',
    );
    expect(homeSource).not.toContain('href="/silence/built"');
    expect(comeInSource).not.toContain('href="/silence/built"');
  });

  it("keeps the localized come-in door keys present", () => {
    for (const locale of ["en", "de", "es", "id"]) {
      const messages = JSON.parse(
        readFileSync(join(root, `messages/${locale}.json`), "utf8"),
      ) as { comeIn?: Record<string, unknown> };

      for (const key of ["doorBuiltEyebrow", "doorBuiltLabel", "doorBuiltBody"]) {
        expect(
          Object.prototype.hasOwnProperty.call(messages.comeIn ?? {}, key),
          `${locale} missing comeIn.${key}`,
        ).toBe(true);
      }
    }
  });

  it("does not route the land path through Bumi Sehat as a community example", () => {
    const alignedSource = readFileSync(
      join(root, "app/vision/aligned/[communityId]/page.tsx"),
      "utf8",
    );
    const publicEntrySource = [
      readFileSync(join(root, "app/page.tsx"), "utf8"),
      readFileSync(join(root, "app/come-in/page.tsx"), "utf8"),
      readFileSync(join(root, "app/silence/built/page.tsx"), "utf8"),
    ].join("\n");

    expect(alignedSource).not.toContain("Bumi Sehat");
    expect(publicEntrySource).not.toContain("Bumi Sehat");
  });

  it("keeps registered entry-path hrefs resolvable to app routes", () => {
    for (const entry of ENTRY_PATHS) {
      expect(entry.href.startsWith("/"), `${entry.id} should be internal`).toBe(true);
      const routePath = join(root, "app", entry.href.slice(1), "page.tsx");
      expect(readFileSync(routePath, "utf8").length).toBeGreaterThan(0);
    }
  });

  it("does not expose excluded kinds on land-design surfaces", () => {
    const entries = [
      ...getEntryPathsForSurface("home-ground"),
      ...getEntryPathsForSurface("come-in-explore"),
      ...getEntryPathsForSurface("come-in-doors"),
    ];
    const byId = new Map<string, EntryPath>();
    for (const entry of entries) byId.set(entry.id, entry);

    for (const entry of byId.values()) {
      if (entry.kind === "land-design-draft" || entry.kind === "community-living-example") {
        expect(entry.excludedKinds).toEqual(
          expect.arrayContaining(["hospital", "care-institution"]),
        );
        expect(entry.kind).not.toBe("hospital");
        expect(entry.kind).not.toBe("care-institution");
      }
    }
  });
});
